#!/usr/bin/env python3
"""
collect_local.py - gather a day's local coding activity on macOS.

Sources:
  * Claude Code CLI sessions  (~/.claude/projects/**/*.jsonl)
  * Cursor composer/agent chats (Cursor's state.vscdb SQLite databases)
  * Git commits across repos   (configured repos + repos seen in sessions)

Writes a compact JSON digest to stdout (or --out). Read-only: never modifies
any source. Standard library only, Python 3.9+ (macOS system python works).

Usage:
  python3 collect_local.py                      # today, local time
  python3 collect_local.py --date 2026-10-12    # a specific day
  python3 collect_local.py --date yesterday
  python3 collect_local.py --since 2026-10-09 --until 2026-10-13   # a range
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "daily-worklog" / "config.json"

DEFAULTS = {
    "output_dir": "~/worklogs",
    "repos": [],              # explicit repo paths
    "repo_roots": [],         # folders whose immediate children are repos
    "git_author_emails": [],  # empty -> uses `git config user.email` per repo
    "sources": {"claude_code": True, "cursor": True, "git": True},
    "claude_projects_dir": "~/.claude/projects",
    "cursor_user_dir": "~/Library/Application Support/Cursor/User",
    "role": "",               # free text: what this person's work looks like
    "standup": {
        "headings": {
            "progress": "Previous work day progress",
            "plans": "Plans for today",
            "blockers": "Blockers",
        },
        "max_plan_bullets": 3,
        "example": "",        # optional: a plans bullet written in your own voice
    },
    # Limits for the compact digest only. Nothing is lost past these limits:
    # every session's full prompt trail and notes go to a per-session details
    # file (see details_dir), which the skill reads for long sessions.
    "max_prompts_per_session": 50,
    "max_prompt_chars": 1000,
    "details_dir": "~/.cache/daily-worklog",
    "max_detail_prompt_chars": 4000,
    "long_session_minutes": 90,   # sessions longer than this are flagged long
    # Files that hold your own session notes / plans. Text Claude Code wrote
    # to these during the window is captured so the log can say what you learned.
    "notes_patterns": [
        "*/.plans/*", "*notes*.md", "*plan*.md", "*todo*.md",
        "*learnings*.md", "*journal*.md", "*progress*.md",
    ],
    "max_notes_chars_per_file": 8000,
    "idle_gap_minutes": 15,   # gaps longer than this don't count as active time
}

EDIT_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}

# Best-effort redaction so obvious secrets never reach the summary.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"lin_(api|oauth)_[A-Za-z0-9]{16,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def expand(p):
    return Path(os.path.expandvars(os.path.expanduser(p)))


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULTS))
    found = False
    if path.exists():
        found = True
        with open(path) as f:
            user = json.load(f)
        for k, v in user.items():
            if k == "sources" and isinstance(v, dict):
                cfg["sources"].update(v)
            elif k == "standup" and isinstance(v, dict):
                for sk, sv in v.items():
                    if sk == "headings" and isinstance(sv, dict):
                        cfg["standup"]["headings"].update(sv)
                    else:
                        cfg["standup"][sk] = sv
            else:
                cfg[k] = v
    return cfg, found


def redact(text):
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def clip_block(text, limit):
    """Clip but keep line breaks (for notes)."""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def is_notes_file(path, patterns):
    low = path.lower()
    return any(fnmatch.fnmatch(low, pat.lower()) for pat in patterns)


def active_minutes(times, gap_minutes):
    """Sum of intervals between consecutive events, ignoring idle gaps."""
    if not times:
        return 0
    times = sorted(times)
    gap = timedelta(minutes=gap_minutes)
    total = timedelta()
    for a, b in zip(times, times[1:]):
        if b - a <= gap:
            total += b - a
    return int(round(total.total_seconds() / 60))


def clip(text, limit):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def from_ms(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def iso_local(dt):
    return dt.astimezone().isoformat(timespec="minutes") if dt else None


def git_toplevel(path):
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def resolve_window(args):
    def to_date(s):
        if s == "today":
            return date.today()
        if s == "yesterday":
            return date.today() - timedelta(days=1)
        return date.fromisoformat(s)

    if args.since:
        start_d = to_date(args.since)
        end_d = to_date(args.until) if args.until else date.today()
    else:
        start_d = end_d = to_date(args.date)
    local_tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(start_d, time.min, tzinfo=local_tz)
    end = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=local_tz)
    return start, end


def in_window(dt, start, end):
    return dt is not None and start <= dt < end


# --------------------------------------------------------------------------- #
# Claude Code
# --------------------------------------------------------------------------- #
def text_from_content(content):
    """User message text, ignoring tool results and images."""
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def is_noise_prompt(text):
    t = text.strip()
    if not t:
        return True
    noise_prefixes = (
        "<command-name>", "<command-message>", "<local-command-stdout>",
        "<system-reminder>", "Caveat:", "[Request interrupted",
    )
    return t.startswith(noise_prefixes)


def sample_evenly(n, k):
    """Indices of up to k items spread across n: always the first and last few."""
    if n <= k:
        return list(range(n))
    edge = min(5, k // 4)
    middle = k - 2 * edge
    picks = set(range(edge)) | set(range(n - edge, n))
    span = n - 2 * edge
    for j in range(middle):
        picks.add(edge + int(j * span / middle))
    return sorted(picks)


def fmt_hm(dt):
    return dt.astimezone().strftime("%H:%M") if dt else "--:--"


def collect_claude(cfg, start, end, details_dir=None):
    root = expand(cfg["claude_projects_dir"])
    if not root.exists():
        return {"status": "not_found", "path": str(root), "sessions": []}

    sessions = {}
    start_ts = start.timestamp()
    for f in root.rglob("*.jsonl"):
        try:
            if f.stat().st_mtime < start_ts:
                continue  # untouched since the window began
        except OSError:
            continue
        try:
            fh = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(e, dict):
                    continue
                sid = e.get("sessionId") or f.stem
                if e.get("type") == "summary" and e.get("summary"):
                    # session titles; not timestamped, attach if session exists
                    sessions.setdefault(sid, _new_session(sid))["titles"].add(e["summary"])
                    continue
                ts = parse_iso(e.get("timestamp"))
                if not in_window(ts, start, end):
                    continue
                s = sessions.setdefault(sid, _new_session(sid))
                s["times"].append(ts)
                s["first"] = min(filter(None, [s["first"], ts]))
                s["last"] = max(filter(None, [s["last"], ts]))
                if e.get("cwd"):
                    s["cwds"].add(e["cwd"])
                if e.get("gitBranch"):
                    s["branches"].add(e["gitBranch"])
                msg = e.get("message") or {}
                if e.get("type") == "user" and not e.get("isMeta") and not e.get("isSidechain"):
                    txt = text_from_content(msg.get("content"))
                    if e.get("isCompactSummary") or txt.lstrip().startswith(
                            "This session is being continued from a previous conversation"):
                        # Claude Code's own summary written when context was compacted
                        s["compact_summaries"].append(
                            {"time": iso_local(ts),
                             "text": clip_block(redact(txt), cfg["max_notes_chars_per_file"])})
                    elif not is_noise_prompt(txt):
                        s["prompts"].append((ts, redact(txt)))
                elif e.get("type") == "assistant":
                    s["turns"] += 1
                    for block in msg.get("content") or []:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        name = block.get("name", "")
                        inp = block.get("input") or {}
                        if name in EDIT_TOOLS:
                            fp = inp.get("file_path") or inp.get("notebook_path")
                            if fp:
                                s["files"].add(fp)
                                if is_notes_file(fp, cfg["notes_patterns"]):
                                    written = []
                                    if name == "Write":
                                        written.append(inp.get("content", ""))
                                    elif name == "Edit":
                                        written.append(inp.get("new_string", ""))
                                    elif name == "MultiEdit":
                                        for ed in inp.get("edits") or []:
                                            if isinstance(ed, dict):
                                                written.append(ed.get("new_string", ""))
                                    for w in written:
                                        if w and w.strip():
                                            s["notes"].setdefault(fp, []).append(redact(w))
                        elif name == "Bash":
                            cmd = str(inp.get("command", ""))
                            if re.search(r"\b(git (commit|push|merge|rebase)|gh pr (create|merge))\b", cmd):
                                s["vcs_commands"].append(clip(redact(cmd), 200))

    out = []
    for s in sessions.values():
        if s["first"] is None:
            continue  # only a title line matched; no activity in window
        repo = None
        for c in s["cwds"]:
            repo = git_toplevel(c) or repo
        files = sorted(s["files"])
        if repo:
            files = [os.path.relpath(p, repo) if p.startswith(repo) else p for p in files]
        all_prompts = sorted(s["prompts"], key=lambda x: x[0])
        picked = sample_evenly(len(all_prompts), cfg["max_prompts_per_session"])
        prompts = [
            f"{fmt_hm(all_prompts[i][0])} {clip(all_prompts[i][1], cfg['max_prompt_chars'])}"
            for i in picked
        ]
        minutes = active_minutes(s["times"], cfg["idle_gap_minutes"])
        notes_full = {fp: "\n\n---\n\n".join(chunks) for fp, chunks in s["notes"].items()}
        notes_truncated = any(len(t) > cfg["max_notes_chars_per_file"] for t in notes_full.values())
        long_session = (
            len(all_prompts) > len(picked)
            or minutes >= cfg["long_session_minutes"]
            or notes_truncated
            or bool(s["compact_summaries"])
        )
        details_file = None
        if details_dir is not None:
            details_file = details_dir / f"claude-{s['id']}.json"
            details_file.write_text(json.dumps({
                "session_id": s["id"],
                "title": sorted(s["titles"])[0] if s["titles"] else None,
                "repo": repo,
                "branches": sorted(s["branches"]),
                "start": iso_local(s["first"]),
                "end": iso_local(s["last"]),
                "active_minutes": minutes,
                "prompts": [
                    {"time": fmt_hm(t), "text": clip_block(txt, cfg["max_detail_prompt_chars"])}
                    for t, txt in all_prompts
                ],
                "compact_summaries": s["compact_summaries"],
                "notes_written": [
                    {"file": fp, "text": t} for fp, t in notes_full.items()
                ],
                "files_edited": files,
                "vcs_commands": s["vcs_commands"],
            }, indent=2, ensure_ascii=False))
        out.append({
            "session_id": s["id"],
            "title": sorted(s["titles"])[0] if s["titles"] else None,
            "repo": repo,
            "cwd": sorted(s["cwds"])[0] if s["cwds"] else None,
            "branches": sorted(s["branches"]),
            "start": iso_local(s["first"]),
            "end": iso_local(s["last"]),
            "assistant_turns": s["turns"],
            "prompt_count": len(all_prompts),
            "prompts": prompts,
            "prompts_omitted": len(all_prompts) - len(picked),
            "long_session": long_session,
            "details_file": str(details_file) if details_file else None,
            "compact_summary_count": len(s["compact_summaries"]),
            "files_edited": files[:40],
            "files_edited_count": len(files),
            "active_minutes": minutes,
            "notes_written": [
                {
                    "file": (os.path.relpath(fp, repo) if repo and fp.startswith(repo) else fp),
                    "abs_path": fp,
                    "text": clip_block(t, cfg["max_notes_chars_per_file"]),
                    "truncated": len(t) > cfg["max_notes_chars_per_file"],
                }
                for fp, t in notes_full.items()
            ],
            "vcs_commands": s["vcs_commands"][:10],
        })
    out.sort(key=lambda x: x["start"] or "")
    return {"status": "ok", "path": str(root), "sessions": out}


def _new_session(sid):
    return {
        "id": sid, "titles": set(), "first": None, "last": None,
        "cwds": set(), "branches": set(), "prompts": [], "files": set(),
        "vcs_commands": [], "turns": 0, "times": [], "notes": {},
        "compact_summaries": [],
    }


# --------------------------------------------------------------------------- #
# Cursor
# --------------------------------------------------------------------------- #
def snapshot_db(path):
    """Copy a live SQLite DB via the backup API so we never touch Cursor's file."""
    tmpdir = tempfile.mkdtemp(prefix="dwl-")
    dst = Path(tmpdir) / "snap.vscdb"
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try:
        dst_conn = sqlite3.connect(dst)
        with dst_conn:
            src.backup(dst_conn)
        dst_conn.close()
    finally:
        src.close()
    return dst, tmpdir


def cursor_workspace_map(user_dir):
    """composerId -> workspace folder, from per-workspace databases."""
    mapping = {}
    ws_root = user_dir / "workspaceStorage"
    if not ws_root.exists():
        return mapping
    for ws in ws_root.iterdir():
        wjson = ws / "workspace.json"
        db = ws / "state.vscdb"
        if not (wjson.exists() and db.exists()):
            continue
        try:
            folder_uri = json.loads(wjson.read_text()).get("folder") or ""
            folder = unquote(urlparse(folder_uri).path) if folder_uri else None
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key='composer.composerData'"
            ).fetchone()
            conn.close()
        except (sqlite3.Error, OSError, json.JSONDecodeError):
            continue
        if not row or not folder:
            continue
        try:
            data = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            continue
        for c in data.get("allComposers", []) or []:
            cid = c.get("composerId") if isinstance(c, dict) else None
            if cid:
                mapping[cid] = folder
    return mapping


def collect_cursor(cfg, start, end):
    user_dir = expand(cfg["cursor_user_dir"])
    gdb = user_dir / "globalStorage" / "state.vscdb"
    if not gdb.exists():
        return {"status": "not_found", "path": str(gdb), "sessions": []}

    try:
        snap, tmpdir = snapshot_db(gdb)
    except sqlite3.Error as e:
        return {"status": f"error: {e}", "path": str(gdb), "sessions": []}

    sessions = []
    try:
        conn = sqlite3.connect(snap)
        has_kv = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'"
        ).fetchone()
        if not has_kv:
            return {"status": "unsupported_schema", "path": str(gdb), "sessions": []}

        ws_map = cursor_workspace_map(user_dir)
        rows = conn.execute(
            "SELECT key, CAST(value AS TEXT) FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
        ).fetchall()
        for key, val in rows:
            try:
                comp = json.loads(val)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(comp, dict):
                continue
            cid = comp.get("composerId") or key.split(":", 1)[1]
            updated = from_ms(comp.get("lastUpdatedAt") or comp.get("createdAt"))
            created = from_ms(comp.get("createdAt"))
            if not in_window(updated, start, end):
                continue

            prompts, ai_msgs, files = [], 0, set()
            bubbles = []
            # Newer format: headers only; bubble bodies stored separately.
            for h in comp.get("fullConversationHeadersOnly") or []:
                bid = h.get("bubbleId")
                if not bid:
                    continue
                r = conn.execute(
                    "SELECT CAST(value AS TEXT) FROM cursorDiskKV WHERE key=?",
                    (f"bubbleId:{cid}:{bid}",),
                ).fetchone()
                if r:
                    try:
                        bubbles.append(json.loads(r[0]))
                    except (TypeError, json.JSONDecodeError):
                        pass
            # Older format: conversation inline.
            if not bubbles:
                bubbles = comp.get("conversation") or []

            for b in bubbles:
                if not isinstance(b, dict):
                    continue
                btime = from_ms(b.get("createdAt")) or parse_iso(b.get("createdAt") or "")
                if btime is not None and not in_window(btime, start, end):
                    continue
                if b.get("type") == 1:
                    txt = b.get("text") or ""
                    if txt.strip():
                        prompts.append(clip(redact(txt), cfg["max_prompt_chars"]))
                elif b.get("type") == 2:
                    ai_msgs += 1
            for uri in (comp.get("codeBlockData") or {}).keys():
                p = unquote(urlparse(uri).path) if "://" in uri else uri
                if p:
                    files.add(p)

            folder = ws_map.get(cid)
            repo = git_toplevel(folder) if folder and Path(folder).exists() else None
            base = repo or folder
            rel_files = sorted(
                os.path.relpath(p, base) if base and p.startswith(base) else p
                for p in files
            )
            k = cfg["max_prompts_per_session"]
            if len(prompts) > k:
                prompts = prompts[: k - 3] + ["…"] + prompts[-2:]
            sessions.append({
                "composer_id": cid,
                "title": comp.get("name"),
                "mode": comp.get("unifiedMode") or comp.get("forceMode"),
                "workspace": folder,
                "repo": repo,
                "created": iso_local(created),
                "last_updated": iso_local(updated),
                "prompts": prompts,
                "ai_messages": ai_msgs,
                "files_touched": rel_files[:40],
                "files_touched_count": len(rel_files),
            })
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    sessions.sort(key=lambda x: x["last_updated"] or "")
    return {"status": "ok", "path": str(gdb), "sessions": sessions}


# --------------------------------------------------------------------------- #
# Git
# --------------------------------------------------------------------------- #
def discover_repos(cfg, extra_paths):
    repos = set()
    for p in cfg.get("repos", []):
        top = git_toplevel(expand(p))
        if top:
            repos.add(top)
    for root in cfg.get("repo_roots", []):
        r = expand(root)
        if not r.is_dir():
            continue
        for child in r.iterdir():
            if (child / ".git").exists():
                repos.add(str(child.resolve()))
    for p in extra_paths:
        if p:
            repos.add(p)
    return sorted(repos)


def collect_git(cfg, start, end, extra_repo_paths):
    repos = discover_repos(cfg, extra_repo_paths)
    results = []
    sep = "\x1f"
    for repo in repos:
        emails = list(cfg.get("git_author_emails") or [])
        if not emails:
            try:
                me = subprocess.run(
                    ["git", "-C", repo, "config", "user.email"],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip()
                if me:
                    emails = [me]
            except (OSError, subprocess.SubprocessError):
                pass
        if not emails:
            continue
        cmd = [
            "git", "-C", repo, "log", "--all", "--no-merges",
            f"--since={start.isoformat()}", f"--until={end.isoformat()}",
            f"--pretty=format:%h{sep}%s{sep}%aI{sep}%D",
            "--shortstat",
        ]
        for em in emails:
            cmd.append(f"--author={em}")
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode != 0:
            continue
        commits = []
        for line in out.stdout.splitlines():
            if sep in line:
                h, subj, when, refs = (line.split(sep) + ["", "", "", ""])[:4]
                commits.append({"sha": h, "subject": redact(subj), "time": when,
                                "refs": refs or None, "stat": None})
            elif line.strip() and commits and "changed" in line:
                commits[-1]["stat"] = line.strip()
        if not commits:
            continue
        try:
            branch = subprocess.run(
                ["git", "-C", repo, "branch", "--show-current"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            branch = None
        results.append({"repo": repo, "name": Path(repo).name,
                        "current_branch": branch, "commits": commits})
    return {"status": "ok", "repos_scanned": len(repos), "repos": results}


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default="today", help="YYYY-MM-DD, 'today', or 'yesterday'")
    ap.add_argument("--since", help="start of a multi-day range (inclusive)")
    ap.add_argument("--until", help="end of a multi-day range (inclusive)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    ap.add_argument("--out", help="write JSON here instead of stdout")
    args = ap.parse_args()

    cfg, cfg_found = load_config(expand(args.config))
    start, end = resolve_window(args)

    digest = {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "config_path": str(expand(args.config)),
        "config_found": cfg_found,
        "output_dir": str(expand(cfg["output_dir"])),
        "profile": {"role": cfg.get("role", ""), "standup": cfg["standup"]},
        "sources": {},
    }
    srcs = cfg["sources"]

    label = start.date().isoformat()
    if (end - start).days > 1:
        label += "_to_" + (end - timedelta(days=1)).date().isoformat()
    details_dir = expand(cfg["details_dir"]) / label
    try:
        if details_dir.exists():
            shutil.rmtree(details_dir)  # fresh each run
        details_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(details_dir, 0o700)
        digest["details_dir"] = str(details_dir)
    except OSError:
        details_dir = None
        digest["details_dir"] = None

    def safe(name, fn, *a):
        try:
            return fn(*a)
        except Exception as e:  # never let one source kill the run
            return {"status": f"error: {type(e).__name__}: {e}"}

    if srcs.get("claude_code", True):
        digest["sources"]["claude_code"] = safe("claude_code", collect_claude, cfg, start, end, details_dir)
        files = {}
        for sess in digest["sources"]["claude_code"].get("sessions", []):
            for n in sess.get("notes_written", []):
                files.setdefault(n["abs_path"], []).append(sess["session_id"])
        digest["progress_files"] = [
            {"abs_path": fp, "exists": Path(fp).exists(), "sessions": sids}
            for fp, sids in sorted(files.items())
        ]
    else:
        digest["sources"]["claude_code"] = {"status": "disabled"}

    if srcs.get("cursor", True):
        digest["sources"]["cursor"] = safe("cursor", collect_cursor, cfg, start, end)
    else:
        digest["sources"]["cursor"] = {"status": "disabled"}

    if srcs.get("git", True):
        seen = set()
        for s in digest["sources"]["claude_code"].get("sessions", []):
            seen.add(s.get("repo"))
        for s in digest["sources"]["cursor"].get("sessions", []):
            seen.add(s.get("repo"))
        digest["sources"]["git"] = safe("git", collect_git, cfg, start, end, seen)
    else:
        digest["sources"]["git"] = {"status": "disabled"}

    cc = digest["sources"]["claude_code"].get("sessions", [])
    digest["summary"] = {
        "claude_sessions": len(cc),
        "long_sessions": sum(1 for x in cc if x.get("long_session")),
        "total_prompts": sum(x.get("prompt_count", 0) for x in cc),
        "total_active_minutes": sum(x.get("active_minutes", 0) for x in cc),
        "cursor_chats": len(digest["sources"]["cursor"].get("sessions", [])),
        "days": max(1, (end - start).days),
    }
    text = json.dumps(digest, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()