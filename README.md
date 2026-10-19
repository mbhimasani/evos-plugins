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

- `role`**:** a sentence or two about what your work looks like. This shapes what the log mphasizes. Examples:
  - "QA engineer. My work is verifying tickets in the QA column, regression testing before releases, and filing bugs in Linear."
  - "Forward deployed engineer for Acme and Globex. Most of my work is customer calls, email, and deployment config in the customer-configs repo."
  - "Engineering manager for the platform team. My work is 1:1s, planning, PR reviews, hiring, and cross-team coordination."
- `repo_roots`**:** the folder(s) holding your repos (e.g. `~/code`). Every direct child with a `.git` folder gets scanned. Repos you worked in through Claude Code or Cursor are picked up automatically even without this. Leave it empty if you don't write code.
- `standup`**:** your standup headings, how many plan bullets you want, and optionally an `example` plans bullet written the way you'd say it. The example is the best way to get plans in your own voice.


| Setting                    | Default                                                 | Notes                                                                                                       |
| -------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `role`                     | empty (inferred from activity)                          | Free text; the more specific, the better                                                                    |
| `output_dir`               | `~/worklogs`                                            | Where daily files go                                                                                        |
| `repo_roots`               | `[]`                                                    | Folders whose immediate children are repos                                                                  |
| `repos`                    | `[]`                                                    | Individual repo paths                                                                                       |
| `git_author_emails`        | per-repo `git config user.email`                        | Add more if you commit from multiple emails                                                                 |
| `standup.headings`         | Previous Work day Progress / Plans for today / Blockers | Rename to match your team's format                                                                          |
| `standup.max_plan_bullets` | `3`                                                     | Upper limit; the skill often uses fewer                                                                     |
| `standup.example`          | empty                                                   | One plans bullet in your own words                                                                          |
| `notes_patterns`           | `.plans/`, `*notes*.md`, `*plan*.md`, `*todo*.md`, …    | Files where Claude Code keeps your session notes. What gets written to them each day feeds the detailed log |
| `sources.cursor` etc.      | `true`                                                  | Set `false` to skip a local source                                                                          |


**3. Make sure Python 3 is available.** Run `python3 --version`. If macOS prompts you to install the Command Line Tools, accept. The collector uses only the standard library.

**4. GitHub** The skill reads your PR activity through the GitHub CLI: reviews you gave, PRs you opened, merged, or commented on, open review requests, and your open PRs. It uses your own login, so private org repos work too.

```bash
brew install gh
gh auth login        # choose GitHub.com, then HTTPS, then log in with a browser
gh auth status       # should show you as logged in
```

If your org uses SSO, authorize the CLI's token for the org when GitHub prompts you (or under GitHub → Settings → Applications). To keep personal repos out of your log, set `github.orgs` in your config, for example `"github": {"orgs": ["your-org"]}`.

Config table rows:

| `github.orgs` | `[]` (all repos) | Only include PRs from these orgs |
| `sources.github` | `true` | Set `false` to skip GitHub |

What it reads (privacy section):

- **GitHub:** via `gh api`, with your own login. PR titles, states, review outcomes and comment counts, and the summary text of reviews you wrote. It doesn't read code, diffs, or the contents of inline review comments.

## Use it

Ask Claude Code in plain language:

- "Write my work log for today"
- "Prep my standup for yesterday"
- "Give me a recap of this week"

Re-running for the same day regenerates the file but keeps anything you wrote under `## Notes`.

## Teaching it your preferences

When a log isn't quite right, tell Claude in the same session, for example "the first bullet is wrong, I also finished module 2", "keep plans to one bullet", or "stop listing my Todo tickets".

Claude fixes the log right away. If the feedback is something that should apply from now on (wording, length, what to include, how to name workstreams), it also saves it to `~/.config/daily-worklog/preferences.md` and tells you in one line what it saved. Every future run reads that file first. One-off corrections about a single day's facts fix that log only. If Claude can't tell which kind your feedback is, it asks.

Words like "always", "from now on", or "remember this" make sure a rule gets saved. You can also manage the file directly:

- "What are my worklog preferences?" shows the file.
- "Forget the rule about Linear tickets" removes that rule.
- Or open `preferences.md` and edit it yourself. It's plain markdown, organized by section.

Your preferences file is personal, lives outside the plugin, and survives plugin updates. Preferences can make the privacy rules stricter, but never looser.

## Run it automatically

Use a **local** scheduled task, not a cloud routine. A cloud routine can't see your Claude Code history, Cursor data, or local repos.

In the Claude desktop app: **Code → Routines → New routine → Local**. Set the schedule (e.g. weekdays at 5:30 pm, or 8:45 am for the previous day) and use a prompt like:

> Run the daily-worklog skill for today. Write the file and reply with the standup block only.

For a morning run, use "for yesterday" instead. The skill treats yesterday as Friday on Mondays.

The desktop app has to be open for local tasks to fire.

## Including Claude chat conversations

The collector reads what's on your Mac. That covers Claude Code sessions from the terminal, and should also cover local sessions in the desktop app's Code tab, which store their history in the same place. It doesn't cover regular Claude chats on [claude.ai](http://claude.ai), the desktop app, or mobile: those conversations are stored with your [claude.ai](http://claude.ai) account in the cloud, and there's no way for the plugin to read them. Cloud (remote) Claude Code sessions aren't covered either.

When a chat was real work (a design discussion, debugging help, a planning session), add a summary of it to that day's log by hand. The skill reads the `## Notes` section as evidence and folds it into the right workstream and the Timeline.

**1. At the end of the chat, ask Claude to summarize it:**

> Summarize this conversation for my work log: what I was trying to do, what we worked out, decisions made and why, open questions, and next steps. Include ticket IDs, repo names, and people's names exactly. Format it as markdown under a `### Chat: <short title> (<start time>–<end time>)` heading.

**2. Copy the summary and add it to the Notes section of that day's log.** Notes is always the last section of the file, so you can simply append to it. With the summary on your clipboard, this adds it to today's log, creating the file if needed:

```bash
f=~/worklogs/$(date +%F).md; [ -f "$f" ] || printf '## Notes\n' > "$f"; { echo; pbpaste; echo; } >> "$f"

```

Change `~/worklogs` if you set a different `output_dir`. For an earlier day, replace `$(date +%F)` with the date, e.g. `2026-10-12`.

**3. Generate (or regenerate) the log as usual.** It's fine to add notes before the log exists; the skill builds the rest of the file above them. Regenerating never changes anything from `## Notes` down.

Doing this right after a chat ends works best. The summary is most accurate while the conversation is fresh, and the times in the heading let the skill put it in the Timeline.

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