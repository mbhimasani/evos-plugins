# daily-worklog

A Claude Code plugin that writes a daily work log and standup update from what you actually did:

- **Local:** Claude Code CLI sessions, Cursor chats, git commits across your repos
- **Connected:** Linear issues and status changes, Slack messages you sent, emails you replied to, Google Calendar meetings, Granola meeting notes

Output is a dated markdown file (default `~/worklogs/2026-10-13.md`) with a paste-ready standup block at the top. Nothing is ever posted automatically.

It works for any role. Engineers, QA, forward deployed engineers, and engineering managers leave different traces (commits, tickets, customer threads, meetings), and the skill weighs them based on the role you describe in your config.

macOS only.

## Install

In Claude Code:

```
/plugin marketplace add mbhimasani/evos-plugins
/plugin install daily-worklog@meghana-evos-plugins
```

Restart Claude Code after installing so the skill loads.

## One-time setup

**1. Connect your tools in claude.ai.** Go to claude.ai → Settings → Connectors and connect whichever of these you use: Linear, Slack, Gmail, Google Calendar, Granola. Claude Code uses the same connectors as long as you're logged in with the same claude.ai account. To check, run `/mcp` in Claude Code; they're listed as claude.ai connectors. If they're missing, run `/login`.

You don't need all of them. The skill uses whatever is connected and lists the rest as "not checked" at the bottom of each log.

**2. Create your config.** This is where you tell the skill about your role and your standup style.

```bash
mkdir -p ~/.config/daily-worklog
cp ~/.claude/plugins/*/daily-worklog/skills/daily-worklog/config.example.json ~/.config/daily-worklog/config.json
```

If the copy command doesn't find the file, run `/plugin` to see where the plugin was installed.

Then edit it:

- `role`**:** a sentence or two about what your work looks like. This shapes what the log emphasizes. Examples:
  - "QA engineer. My work is verifying tickets in the QA column, regression testing before releases, and filing bugs in Linear."
  - "Forward deployed engineer for Acme and Globex. Most of my work is customer calls, email, and deployment config in the customer-configs repo."
  - "Engineering manager for the platform team. My work is 1:1s, planning, PR reviews, hiring, and cross-team coordination."
- `repo_roots`**:** the folder(s) holding your repos (e.g. `~/code`). Every direct child with a `.git` folder gets scanned. Repos you worked in through Claude Code or Cursor are picked up automatically even without this. Leave it empty if you don't write code.
- `standup`**:** your standup headings, how many plan bullets you want, and optionally an `example` plans bullet written the way you'd say it. The example is the best way to get plans in your own voice.


| Setting                    | Default                                                 | Notes                                       |
| -------------------------- | ------------------------------------------------------- | ------------------------------------------- |
| `role`                     | empty (inferred from activity)                          | Free text; the more specific, the better    |
| `output_dir`               | `~/worklogs`                                            | Where daily files go                        |
| `repo_roots`               | `[]`                                                    | Folders whose immediate children are repos  |
| `repos`                    | `[]`                                                    | Individual repo paths                       |
| `git_author_emails`        | per-repo `git config user.email`                        | Add more if you commit from multiple emails |
| `standup.headings`         | Previous Work day Progress / Plans for today / Blockers | Rename to match your team's format          |
| `standup.max_plan_bullets` | `3`                                                     | Upper limit; the skill often uses fewer     |
| `standup.example`          | empty                                                   | One plans bullet in your own words          |
| `notes_patterns`           | `.plans/`, `*notes*.md`, `*plan*.md`, `*todo*.md`, …    | Files where Claude Code keeps your session notes. What gets written to them each day feeds the detailed log |
| `sources.cursor` etc.      | `true`                                                  | Set `false` to skip a local source          |


**3. Make sure Python 3 is available.** Run `python3 --version`. If macOS prompts you to install the Command Line Tools, accept. The collector uses only the standard library.

## Use it

Ask Claude Code in plain language:

- "Write my work log for today"
- "Prep my standup for yesterday"
- "Give me a recap of this week"

Re-running for the same day regenerates the file but keeps anything you wrote under `## Notes`.

## Run it automatically

Use a **local** scheduled task, not a cloud routine. A cloud routine can't see your Claude Code history, Cursor data, or local repos.

In the Claude desktop app: **Code → Routines → New routine → Local**. Set the schedule (e.g. weekdays at 5:30 pm, or 8:45 am for the previous day) and use a prompt like:

> Run the daily-worklog skill for today. Write the file and reply with the standup block only.

For a morning run, use "for yesterday" instead. The skill treats yesterday as Friday on Mondays.

The desktop app has to be open for local tasks to fire.

## What it reads, and privacy

- **Claude Code:** `~/.claude/projects/**/*.jsonl`. Reads only the prompts you typed, which files were edited, and git commands that were run.
- **Cursor:** `~/Library/Application Support/Cursor/User/` (`globalStorage/state.vscdb` and `workspaceStorage/`*). The database is copied to a temp file and read from the copy, so Cursor's live file is never touched. Cursor's storage format isn't documented and changes between versions; if Cursor shows `unsupported_schema` or an error, everything else still works.
- **Git:** `git log` for your own commits in the window.
- Obvious secrets (API keys, tokens, `password=` strings) are redacted before anything reaches Claude.
- The log summarizes; it doesn't paste emails, messages, prompts, or code. It skips personal, HR, and other sensitive topics.
- Files stay on your machine. Sharing is up to you.



## Troubleshooting

Run the collector directly to see what it finds:

```bash
python3 <plugin-dir>/skills/daily-worklog/scripts/collect_local.py --date today | less
```

Each source reports a `status`. `not_found` means the folder doesn't exist (for example, Cursor isn't installed), and that's fine.

## Repo layout

```
.claude-plugin/marketplace.json          # marketplace catalog
plugins/daily-worklog/
  .claude-plugin/plugin.json             # plugin manifest
  skills/daily-worklog/
    SKILL.md                             # what Claude does
    config.example.json
    scripts/collect_local.py             # local collector
```

To change the output format or what counts as noise, edit `SKILL.md`. Bump `version` in `plugin.json` when you push changes so teammates pick them up.