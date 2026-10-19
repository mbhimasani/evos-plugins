---

## name: daily-worklog
description: Generate a daily work log and standup update from everything the user actually did in a day — Claude Code CLI sessions, Cursor chats, git commits across repos, GitHub pull requests (reviews given, PRs opened and merged, review requests), Linear issues and status changes, Slack messages they sent, emails they replied to, and meetings they attended (Google Calendar + Granola notes) — and save it as a dated markdown file. Works for any role (engineers, QA, forward deployed engineers, engineering managers). Use this whenever the user asks for a standup, daily update, scrum update, end-of-day summary, work log, "what did I do today/yesterday", "what did I ship", a weekly recap built from daily activity, or when a scheduled task asks to run the daily worklog. Also use it when the user gives feedback on a work log or standup ("that bullet is wrong", "don't include X", "remember this for next time") or asks to view or change their worklog preferences. Prefer this over a generic standup skill.



# Daily worklog

Build an accurate, skimmable record of one person's workday from the traces their tools already leave, then write it to `~/worklogs/YYYY-MM-DD.md` (or the configured folder) with a paste-ready standup block at the top.

The goal is a log the user would sign off on without editing: grounded in real activity, grouped by what they were working on rather than by which tool it came from, and free of anything they wouldn't want a teammate to read.

The file serves two readers, and each part is written for one of them:

- **The Standup block** is shared with the team. Keep it short and outcome-focused.
- **Everything below it** is the user's own record, read weeks or months later to recall exactly what they did, where the time went, what they learned, and how their thinking moved. Make it detailed and specific. A reader should be able to pick up the thread of a workstream from the log alone, without a vague "worked on X".

People in different roles leave very different traces. An engineer's day shows up in commits and coding sessions; a QA engineer's in tickets moved through verification and bugs filed; a forward deployed engineer's in customer calls, emails, and deployments; an engineering manager's in meetings, 1:1s, reviews, and decisions. Don't assume code is the main signal. Weigh whatever sources actually carry this person's work.

## 1. Pick the time window

- Default: today, local time, midnight to midnight.
- "yesterday", a weekday name, or a date → that day. On a Monday morning, "yesterday's standup" means Friday unless the user says otherwise.
- A range ("this week", "since Thursday") → the full range; produce one file named `YYYY-MM-DD_to_YYYY-MM-DD.md`.
- When run from a scheduled task with no date, use today.

The **plans day** is the next workday after the logged day (Monday after a Friday).

## 2. Collect local activity

Run the bundled collector from this skill's directory:

```bash
python3 scripts/collect_local.py --date <YYYY-MM-DD|today|yesterday>
# or for a range:
python3 scripts/collect_local.py --since <start> --until <end>
```

It prints JSON covering Claude Code sessions, Cursor chats, git commits (for configured repos plus any repo it saw in a session), and GitHub pull request activity (through the user's `gh` CLI login). It reads only, redacts obvious secrets, and reports each source's `status` (`ok`, `not_found`, `disabled`, or `error: …`).

If the script isn't in this skill's `scripts/` folder, say so plainly in the final reply ("collect_local.py is missing from the skill folder; reinstall the plugin"). Don't try to reproduce it by hand.

Each Claude Code session includes:

- `prompts`: what the user asked, in order, each prefixed with its time. Read them as the trail of the user's thinking: the questions they had, where they got stuck, when they changed direction. For long sessions this is an evenly spread sample (`prompt_count` is the real total, `prompts_omitted` the number left out).
- `details_file`: the session's complete record, with every prompt, any `compact_summaries` (Claude Code's own summaries written when the session's context filled up), and all text written to notes files, untruncated. The digest is a compact view; the details file is the source of truth for the session.
- `long_session`: true when the digest view is incomplete (prompts or notes were cut) or the session ran long. See "Long sessions and big days" below.
- `active_minutes`: estimated hands-on time (idle gaps excluded), plus `start` and `end`.
- `notes_written`: the exact text Claude Code wrote during the window into the user's notes or plan files (session notes, `.plans/`, TODO or progress files). This is the richest source of what was learned, what was confusing, and what's next. Because it's only what was written in the window, it won't mix in older or later notes.

The `github` source contains:

- `reviews_submitted`: reviews the user gave in the window, each with the PR, the review state (APPROVED, CHANGES_REQUESTED, COMMENTED), the number of inline comments, and the review's summary text if the user wrote one. For the Focus column, use that summary, plus any Claude Code session where the user reviewed the PR. Otherwise leave Focus blank rather than guess.
- `prs_opened` and `prs_merged`: the user's own PRs opened or merged in the window.
- `prs_commented_on`: PRs the user commented on outside a formal review.
- `review_requests_open` and `my_open_prs`: current state, not limited to the window. These are the user's review queue and their PRs still in flight, which feed the plans.

If its status is `not_installed` or `not_authenticated`, list GitHub under "Not checked" with the hint (`brew install gh && gh auth login`).

`progress_files` lists those notes files. Read their current contents as well, for the surrounding context (overall plan, step list, earlier open questions now resolved), but attribute progress to the logged day only from `notes_written`, session prompts, and other in-window evidence.

It also returns the user's settings from `~/.config/daily-worklog/config.json`:

- `output_dir`: where to write the file.
- `profile.role`: a free-text description of the user's role and what their work looks like. Use it to decide which activity matters most and how to phrase it. If empty, infer the role from the activity itself.
- `profile.standup`: the standup headings to use, the maximum number of plan bullets, and an optional `example` of how this user writes their plans. When an example is present, match its voice and level of detail.

It also returns `preferences`: the contents of the user's learned-preferences file (see "9. Learn from feedback"). **Read it before writing anything and follow it throughout.** These are corrections the user made to past logs, so honoring them is how the log stops repeating the same mistakes. Precedence, highest first: what the user asks in this session, then `preferences`, then `config.json`, then this skill's defaults. The one exception is the privacy rules, which a preference can make stricter but never looser.

If `config_found` is false, carry on with defaults and mention once, at the end, that copying `config.example.json` there lets them set their role, repos, and standup style.

## 3. Collect connected-tool activity

Use whichever of these tools are available in this session. If a source isn't connected, skip it quietly and list it under "Not checked" at the bottom of the file. Never stop the run over a missing source.

**Linear** — issues assigned to the user that were updated in the window, plus issues they created, commented on, or changed state on. Record identifier, title, project, current status, and any status transitions in the window (e.g. In Progress → In Review, In QA → Done). For QA work, issues the user verified, reopened, or filed as bugs are the core output even when they're assigned to someone else.

**Slack** — messages the user sent in the window (search `from:@me` with an `on:` or `after:`/`before:` date filter). Group by channel/thread and summarize the topic and outcome ("answered deploy question in #platform", "agreed on API shape with the payments team"). Don't quote messages, and skip social chatter and DMs that aren't about work. Note anything the user said they'd do ("I'll send this over tomorrow"); these are commitments for the plans.

**Gmail** — threads the user replied to or sent in the window (`in:sent after:YYYY/MM/DD before:YYYY/MM/DD`, with `before` being the day after the window ends). Summarize subject and purpose in a few words. Skip personal, automated, and newsletter mail. This query only returns mail the user sent, so tool notifications they received (GitHub, Linear, calendar invites) never come in through Gmail. For customer-facing roles, external threads are often the main work, so give them the same weight as code. Note promised follow-ups.

**Meetings** — from Google Calendar, events in the window the user accepted or organized, excluding declined events, all-day events, and focus/hold blocks. From Granola, meeting notes in the window: pull decisions and action items assigned to the user. Match Granola notes to calendar events by time and title so each meeting appears once.

**Calendar for the plans day** — also fetch the user's accepted events on the plans day. Meetings that are themselves work (customer calls, design reviews, release go/no-go, interviews, planning) can belong in the plans. Recurring routine meetings (standup, team syncs, most 1:1s) don't.

## 4. Long sessions and big days

The digest keeps the run fast on ordinary days, but it's a sample. Whenever it isn't the whole picture, read the full record. Use subagents to do that when there's a lot of it, so the raw material doesn't crowd out the rest of the day.

**Use subagents when any of these is true:**

- Two or more sessions have `long_session: true`.
- `summary.total_prompts` is over about 150, or `summary.total_active_minutes` is over about 5 hours.
- The window covers more than one day.
- Slack or Gmail returns far more items than usual (dozens of threads).

**Otherwise**, read the `details_file` of any single long session yourself, in chunks if it's large, and carry on.

**How to delegate:** read `references/subagents.md` before launching any subagent. It has the split, the exact instructions to give each subagent (they must extract specifics, not summarize), and what stays with you. Linking, deduplication, the Timeline, the Standup block, and writing the file always stay in the main agent.

## 5. Synthesize

Group everything into **workstreams**: a feature, bug, customer, release, hire, or initiative. Don't list activity per tool. Link the evidence together:

- Linear identifiers (like `ENG-123`) in branch names, commit messages, session prompts, or Slack messages tie that activity to the issue.
- Sessions and commits in the same repo and branch are the same workstream.
- A PR belongs to the workstream of its branch, or of the Linear ID in its title or branch name. The user's own PRs (opened, merged, reviewed by others) are evidence for that workstream.
- Reviews of other people's PRs usually form a **Code review** workstream of their own, listing each PR reviewed, its author, the outcome, and what the review focused on. A review that's part of the user's own feature work belongs with that workstream instead.
- A customer's name across emails, meetings, and Slack makes those one workstream.
- A meeting or thread about a topic belongs with that topic's workstream when the connection is clear; otherwise it goes under Communication or Meetings.

Write at the level a teammate cares about: "Added token-bucket rate limiting to the public API (ENG-42), tests passing, PR up for review", not "edited a.py, ran git commit". Keep file lists out of the summary unless a specific file is the point.

If the same work shows up in both Claude Code and Cursor, mention it once.

### One item, one entry

The same piece of work often leaves traces in several tools: a PR you reviewed appears in GitHub, maybe in a Slack message where you shared it, and in the Claude Code session where you read it; a meeting appears in Calendar and Granola; a ticket moves in Linear when its PR merges. Merge these into one item before writing anything.

- **Each kind of item has one source of truth:** PRs and reviews come from GitHub; tickets from Linear; meetings from Calendar, with Granola for content; code activity from Claude Code, Cursor, and git. Slack and Gmail add conversations between people. They never create a second copy of a PR, ticket, or meeting.
- **Notifications are signals, not items.** Messages from GitHub, Linear, Google Calendar, Granola, Notion, Vercel, CI, and similar tools, whether email or Slack bot posts, only point at something the real source already covers. Ignore them when that source was checked. If the source wasn't checked (for example, `gh` isn't authenticated), a notification can stand in as evidence; say that it did.
- **Match on stable identifiers:** PR URL or `repo#number`, Linear ID, meeting start time and title, email or Slack thread, Claude Code session ID. Two mentions with the same identifier are the same item. Same topic without a shared identifier counts only when the link is clear.
- **When sources overlap, combine what each adds.** The review outcome comes from GitHub, what you focused on from the Claude Code session, and the follow-up discussion from Slack. All of it goes into one entry.
- **Each item appears once per section.** In the Standup block, each workstream appears at most once across the progress and plans bullets combined, unless the progress and the plan are genuinely different steps. Under Communication, list only conversations that aren't already covered under a workstream. The Linear and Pull requests tables are indexes, so it's expected that an item appears both there and in its workstream, but never twice in the same table.

Before writing the file, check for repeats one last time: the same PR number, Linear ID, meeting, or thread should appear in no more than one bullet per section.

For worked examples of several traces becoming one entry (a PR review seen in four places, a ticket closed by its PR merging, a meeting with a follow-up, a customer issue across email, Slack, and a call), read `references/examples.md` when sources overlap in a way these rules don't obviously settle.

### Writing the detailed log

For each workstream, write the record the user would want when coming back to it later. Draw the specifics from `notes_written`, the prompt trail, Linear issue descriptions and comments, meeting notes, and commits. Cover what applies:

- **Time:** roughly how long, across which sessions or meetings (e.g. "~3h 10m across 2 Claude Code sessions, 9:40–11:15 and 1:30–3:05"). Use `active_minutes`; call it approximate.
- **What I did:** the sequence of work, in order, with enough detail to retrace it: which areas, files, docs, or tickets, and what each step was for.
- **What I learned:** concrete knowledge gained: how something works, where it lives, why it's built that way. Name the specific modules, files, functions, services, or concepts. "Learned the platform" is useless; "the dashboard reads each operator's Convex deployment via raw `fetch`, so there's no shared client or typing" is the level to aim for.
- **Gaps, confusion, and open questions:** where docs and code disagreed, what was unclear, what took several attempts, what's still unanswered, and anything that looked like a bug or risk. Say whether each was resolved and how.
- **Decisions and reasoning:** choices made and why, including approaches tried and abandoned. Reconstruct this from the prompt trail and notes ("started by reading the architecture map, found it out of date, switched to tracing from the code instead").
- **Next steps:** what the notes or the user said comes next.
- **Evidence:** repo/branch, commit count, tickets, sessions, meetings, and the path to the notes file for full detail.

Write it as compact, specific bullets in plain language. Paraphrase the user's notes rather than pasting them wholesale; short phrases from their own notes are fine where the exact wording matters. Skip a heading when there's nothing real to put under it, rather than padding. A heavy day on one workstream can run to 20–30 lines; a small item needs only a line or two.

Also build a **Timeline**: the day in chronological order, one row per session or meeting, with times, approximate duration, what it was, and which workstream it belongs to. This is what answers "where did my time go?"

### Writing the standup block

Use the headings from `profile.standup.headings`.

**Progress** (the first heading) covers the logged day: concrete outcomes, one bullet per workstream, following the progress rules above.

**Plans** (the second heading) covers the plans day. Build it from evidence, in this order of strength:

1. **Commitments:** action items assigned to the user in meeting notes, and things they told someone they'd do in Slack or email.
2. **Work in flight:** the next step on whatever the user was mid-way through. That might be the next steps of a sequence, an In Progress or In Review ticket, an unfinished session, or a ticket sitting in the user's QA column. From GitHub: open review requests (`review_requests_open`) are the user's review queue, and the user's own open PRs with changes requested need their attention.
3. **Scheduled work:** non-routine meetings on the plans day that are themselves work (customer calls, design reviews, release decisions, interviews).
4. **Deadlines** mentioned in notes, meetings, or messages.

Then write it the way the user would say it in standup:

- Lead each bullet with the workstream and a concrete target for the day. When there's a deadline and a countable remainder, work out the day's share: 9 items left with 3 days to the deadline means "items 3 to 5 today", followed by the overall deadline.
- Fold follow-ups that depend on finishing that work into the same bullet, introduced with "at that point". For example, sending a summary once testing wraps goes in the testing bullet, not in a separate bullet.
- Don't list backlog items (Todo, Backlog, unstarted) unless something says the user is starting them on the plans day. If notes say that work starts on a later date, leave it out.
- Use at most `profile.standup.max_plan_bullets` bullets. A couple of strong bullets beat a list of every open item.
- Never invent a plan. If the evidence doesn't show what's next for a workstream, leave it out rather than guess.

If the user has no `standup.example` and no saved preferences about plans, read the plans-by-role illustrations in `references/examples.md` (engineer, QA, forward deployed engineer, engineering manager) before writing plans. They show shape only, never text to copy.

## 6. Write the file

Write to `<output_dir>/<YYYY-MM-DD>.md`. `## Notes` is always the last section of the file, and it belongs to the user. If the file already exists, keep everything from the `## Notes` heading to the end of the file exactly as it is, and regenerate everything above it.

**Read the Notes section before you synthesize, and treat it as evidence.** Users add summaries of Claude chat conversations there (usually under `### Chat: <title>` headings, sometimes with a time), since those chats live in the cloud where the collector can't see them. They may also add notes about offline work. Fold this material into the matching workstreams, add a Timeline row when a time is given, and let it inform the Standup block. If the file contains only a Notes section, that's expected: the user added notes before the log was first generated. Files from older versions of this skill have a `Sources:` footer after the Notes section; when regenerating one, remove that old footer line and the `---` above it, and keep the rest of Notes untouched.

Use this structure, with the configured headings in place of the angle-bracket labels:

```markdown
# Work log — <Weekday, Month D, YYYY>

## Standup
**<progress heading>:**
- <bullets per "Writing the standup block">

**<plans heading>:**
- <bullets per "Writing the standup block">

**<blockers heading>:** <bullets, or "None">

## Timeline
| Time | Duration | Activity | Workstream |
|---|---|---|---|
| <9:40–11:15> | <~1h 35m> | <Claude Code session: …> | <…> |

## Workstreams
### <Workstream name> (<LINEAR-ID or customer> · <status>)
**Time:** <~Xh Ym across …>

**What I did**
- <step, in order, with specifics>

**What I learned**
- <specific fact, with the file, module, or concept it concerns>

**Gaps, confusion, and open questions**
- <what was unclear or inconsistent; resolved how, or still open>

**Decisions and reasoning**
- <choice made and why; approaches tried and dropped>

**Next steps**
- <from notes, meetings, or messages>

**Evidence:** <repo/branch and commits · tickets · sessions · meetings · notes file path>

## Linear
| Issue | Title | Status | Change in window |
|---|---|---|---|

## Pull requests
**Reviewed**
| PR | Author | Outcome | Comments | Focus |
|---|---|---|---|---|

**Mine:** <opened / merged / changes requested, with links>

**Awaiting my review:** <open review requests, oldest first>

## Meetings
- **<Meeting>** (<time>) — <decision or outcome>; action items for me: <…>

## Communication
- Slack: <channel/thread — topic and outcome>
- Email: <subject — purpose>

## Activity by repo
| Repo | Commits | Claude Code sessions | Cursor chats |
|---|---|---|---|

---
Sources: <checked sources> · Not checked: <missing/failed sources>

## Notes
<!-- Your own notes and Claude chat summaries. Preserved when this file is regenerated. -->
```

Leave out any section with nothing in it, except Standup and Notes. For example, a manager with no coding activity gets no "Activity by repo" table. Keep the Standup block short enough to paste into Slack as-is.

## 7. Privacy rules

These logs live on the user's machine and may be pasted to teammates, so:

- Summarize; never paste raw email bodies, Slack messages, or code. Prompts and the user's own notes can be paraphrased in detail in the sections below the Standup block, which are their private record.
- Leave out benefits, payroll, retirement accounts, personal purchases, and expense-receipt admin entirely, including from Communication. They aren't work output.
- Leave out anything that looks personal, HR-related, or confidential (compensation, performance, health, legal), even if it appeared in a work channel. For managers, this includes 1:1 content and performance or hiring discussions about named people: log that the meeting happened and any non-sensitive outcome, nothing more.
- Keep customer details at the level a teammate already knows: the customer name and what was done, not contract terms or the contents of their data.
- Keep the collector's `[REDACTED]` markers out of the log entirely; don't try to reconstruct what was there.
- Never post, send, or share the log anywhere. Write the file and stop. If the user asks to post the standup, show them the text and let them send it, or ask before using a send tool.

## 8. Finish

Reply with the file path and the Standup block. Then, in one line, name any sources that weren't checked and why (not connected, not installed, error). Nothing else.

## Weekly or multi-day recaps

If the user asks for a recap and daily files already exist in `output_dir` for those days, read them first and summarize from them rather than re-collecting everything. For days with no file, run the steps above.

## 9. Learn from feedback

After a log is written, the user may correct it: "that first bullet is wrong", "make the plans more specific", "stop listing my Todo tickets", "call it the Grokbot work, not team tooling". Handle every correction in two parts.

**First, fix the log.** Update the file now (only what was corrected, leaving `## Notes` untouched) and show the corrected Standup block if it changed.

**Then decide whether the correction should apply to future logs:**

- **A fact about this day** (what was actually finished, a wrong time, a misattributed meeting) → fix the log only. Don't save it as a preference. If the error came from a pattern that will recur, though, such as misreading how the user's notes mark progress, save the pattern.
- **A standing preference** (wording, length, tone, what to include or leave out, how to group or name workstreams, how to phrase plans, which sources to trust for what, terms and names to use) → save it.
- **Unclear** → ask in one short question: "Should I keep doing it this way in future logs?"

When saving, tell the user in one line what was recorded ("Saved: plans lead with the day's target, then the deadline"). Don't ask for permission when the correction is clearly general or the user said "always", "from now on", "remember", or "next time".

**The preferences file** lives at `preferences.path` from the digest (default `~/.config/daily-worklog/preferences.md`). Create it on the first save, using this structure:

```markdown
# Daily worklog preferences
<!-- Maintained by the daily-worklog skill from your feedback. Edit freely. -->

## Standup
- <rule> (added YYYY-MM-DD)

## Detailed log
## Workstreams and naming
## Sources and filtering
## Terms and people
```

How to write entries:

- **One rule per bullet, stated so a future run can follow it cold.** Write "Plans bullets: lead with today's concrete target, then the overall deadline", not "user didn't like the plans". Include the reason when it helps apply the rule in new situations.
- **Keep the user's own words** for headings, names, and phrasing they specifically asked for.
- **Update rather than append.** If a new rule changes or contradicts an existing one, edit that bullet and update its date instead of adding a second one. Merge near-duplicates.
- **Keep it short.** If the file grows past about 60 bullets, consolidate overlapping rules and tell the user you tidied it.
- **Never save** secrets, personal or HR matters, or facts about a single day. Also never save anything that loosens the privacy rules in section 7. If asked to, explain in one line that the privacy rules stay as they are.

**When the user asks to see or change their preferences** ("what do you remember about my standup?", "forget the rule about Linear tickets"), show or edit the file directly. When asked to remove a rule, delete the bullet entirely.