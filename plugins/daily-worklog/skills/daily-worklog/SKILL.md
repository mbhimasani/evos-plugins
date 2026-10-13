---

## name: daily-worklog
description: Generate a daily work log and standup update from everything the user actually did in a day — Claude Code CLI sessions, Cursor chats, git commits across repos, Linear issues and status changes, Slack messages they sent, emails they replied to, and meetings they attended (Google Calendar + Granola notes) — and save it as a dated markdown file. Works for any role (engineers, QA, forward deployed engineers, engineering managers). Use this whenever the user asks for a standup, daily update, scrum update, end-of-day summary, work log, "what did I do today/yesterday", "what did I ship", a weekly recap built from daily activity, or when a scheduled task asks to run the daily worklog. Prefer this over a generic standup skill.



# Daily worklog

Build an accurate, skimmable record of one person's workday from the traces their tools already leave, then write it to `~/worklogs/YYYY-MM-DD.md` (or the configured folder) with a paste-ready standup block at the top.

The goal is a log the user would sign off on without editing: grounded in real activity, grouped by what they were working on rather than by which tool it came from, and free of anything they wouldn't want a teammate to read.

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

It prints JSON covering Claude Code sessions, Cursor chats, and git commits (for configured repos plus any repo it saw in a session). It reads only, redacts obvious secrets, and reports each source's `status` (`ok`, `not_found`, `disabled`, or `error: …`).

It also returns the user's settings from `~/.config/daily-worklog/config.json`:

- `output_dir`: where to write the file.
- `profile.role`: a free-text description of the user's role and what their work looks like. Use it to decide which activity matters most and how to phrase it. If empty, infer the role from the activity itself.
- `profile.standup`: the standup headings to use, the maximum number of plan bullets, and an optional `example` of how this user writes their plans. When an example is present, match its voice and level of detail.

If `config_found` is false, carry on with defaults and mention once, at the end, that copying `config.example.json` there lets them set their role, repos, and standup style.

## 3. Collect connected-tool activity

Use whichever of these tools are available in this session. If a source isn't connected, skip it quietly and list it under "Not checked" at the bottom of the file. Never stop the run over a missing source.

**Linear** — issues assigned to the user that were updated in the window, plus issues they created, commented on, or changed state on. Record identifier, title, project, current status, and any status transitions in the window (e.g. In Progress → In Review, In QA → Done). For QA work, issues the user verified, reopened, or filed as bugs are the core output even when they're assigned to someone else.

**Slack** — messages the user sent in the window (search `from:@me` with an `on:` or `after:`/`before:` date filter). Group by channel/thread and summarize the topic and outcome ("answered deploy question in #platform", "agreed on API shape with the payments team"). Don't quote messages, and skip social chatter and DMs that aren't about work. Note anything the user said they'd do ("I'll send this over tomorrow"); these are commitments for the plans.

**Gmail** — threads the user replied to or sent in the window (`in:sent after:YYYY/MM/DD before:YYYY/MM/DD`, with `before` being the day after the window ends). Summarize subject and purpose in a few words. Skip personal, automated, and newsletter mail. For customer-facing roles, external threads are often the main work, so give them the same weight as code. Note promised follow-ups.

**Meetings** — from Google Calendar, events in the window the user accepted or organized, excluding declined events, all-day events, and focus/hold blocks. From Granola, meeting notes in the window: pull decisions and action items assigned to the user. Match Granola notes to calendar events by time and title so each meeting appears once.

**Calendar for the plans day** — also fetch the user's accepted events on the plans day. Meetings that are themselves work (customer calls, design reviews, release go/no-go, interviews, planning) can belong in the plans. Recurring routine meetings (standup, team syncs, most 1:1s) don't.

## 4. Synthesize

Group everything into **workstreams**: a feature, bug, customer, release, hire, or initiative. Don't list activity per tool. Link the evidence together:

- Linear identifiers (like `ENG-123`) in branch names, commit messages, session prompts, or Slack messages tie that activity to the issue.
- Sessions and commits in the same repo and branch are the same workstream.
- A customer's name across emails, meetings, and Slack makes those one workstream.
- A meeting or thread about a topic belongs with that topic's workstream when the connection is clear; otherwise it goes under Communication or Meetings.

Write at the level a teammate cares about: "Added token-bucket rate limiting to the public API (ENG-42), tests passing, PR up for review", not "edited a.py, ran git commit". Keep file lists out of the summary unless a specific file is the point.

If the same work shows up in both Claude Code and Cursor, mention it once.

### Getting progress right

Activity shows what the user worked on, not how far they got. Before calling something finished:

- **Code:** commits, merged or opened PRs, and Linear status changes are evidence of completion. Session prompts alone are not.
- **Tickets:** trust the status transition in the window, not the issue title.
- **Meetings and threads:** an outcome counts only if the notes or messages show a decision, agreement, or delivered item.
- **Sequential work** (modules, phases, checklists, test plans): read the current contents of any progress-tracking file edited in the window, such as session notes, plan files, checklists, anything under `.plans/`, or files named like `*notes*.md`, `TODO.md`, or `PLAN.md`. Report every step finished in the window, not just the first one. Going back to finish an earlier step is its own progress ("closed the remaining gaps in step 1, completed step 2, started step 3").
- If none of this makes completion clear, describe the work without claiming it was finished.



### Writing the standup block

Use the headings from `profile.standup.headings`.

**Progress** (the first heading) covers the logged day: concrete outcomes, one bullet per workstream, following the progress rules above.

**Plans** (the second heading) covers the plans day. Build it from evidence, in this order of strength:

1. **Commitments:** action items assigned to the user in meeting notes, and things they told someone they'd do in Slack or email.
2. **Work in flight:** the next step on whatever the user was mid-way through. That might be the next steps of a sequence, an In Progress or In Review ticket, a PR awaiting feedback, an unfinished session, or a ticket sitting in the user's QA column.
3. **Scheduled work:** non-routine meetings on the plans day that are themselves work (customer calls, design reviews, release decisions, interviews).
4. **Deadlines** mentioned in notes, meetings, or messages.

Then write it the way the user would say it in standup:

- Lead each bullet with the workstream and a concrete target for the day. When there's a deadline and a countable remainder, work out the day's share: 9 items left with 3 days to the deadline means "items 3 to 5 today", followed by the overall deadline.
- Fold follow-ups that depend on finishing that work into the same bullet, introduced with "at that point". For example, sending a summary once testing wraps goes in the testing bullet, not in a separate bullet.
- Don't list backlog items (Todo, Backlog, unstarted) unless something says the user is starting them on the plans day. If notes say that work starts on a later date, leave it out.
- Use at most `profile.standup.max_plan_bullets` bullets. A couple of strong bullets beat a list of every open item.
- Never invent a plan. If the evidence doesn't show what's next for a workstream, leave it out rather than guess.

What the plans tend to look like by role (illustrations of shape, not text to copy):

> *Engineer:* Finish the retry logic for webhook delivery (ENG-512) and get the PR into review; address review comments on the rate limiter PR at that point.
>
> *QA:* Verify the 6 tickets in the QA column for Thursday's release - aiming for 3 today; file regressions against the release epic as I find them.
>
> *Forward deployed engineer:* Acme rollout - finish the SSO config with their IT team on the 2pm call and send the go-live checklist at that point; reply to Globex on the data export question.
>
> *Engineering manager:* Finalize the Q4 staffing plan for review Friday; run the two candidate debriefs and send hiring decisions at that point.



## 5. Write the file

Write to `<output_dir>/<YYYY-MM-DD>.md`. If the file already exists, regenerate everything except the `## Notes` section, which the user may have written by hand. Keep that section exactly as it is.

Use this structure, with the configured headings in place of the angle-bracket labels:

```markdown
# Work log — <Weekday, Month D, YYYY>

## Standup
**<progress heading>:**
- <bullets per "Writing the standup block">

**<plans heading>:**
- <bullets per "Writing the standup block">

**<blockers heading>:** <bullets, or "None">

## Workstreams
### <Workstream name> (<LINEAR-ID or customer> · <status>)
- What changed and why it matters, in a sentence or two
- Evidence: <repo/branch and commit count, tickets moved, meetings, threads — whichever apply>

## Linear
| Issue | Title | Status | Change in window |
|---|---|---|---|

## Meetings
- **<Meeting>** (<time>) — <decision or outcome>; action items for me: <…>

## Communication
- Slack: <channel/thread — topic and outcome>
- Email: <subject — purpose>

## Activity by repo
| Repo | Commits | Claude Code sessions | Cursor chats |
|---|---|---|---|

## Notes
<!-- Your own notes. Preserved when this file is regenerated. -->

---
Sources: <checked sources> · Not checked: <missing/failed sources>
```

Leave out any section with nothing in it, except Standup and Notes. For example, a manager with no coding activity gets no "Activity by repo" table. Keep the Standup block short enough to paste into Slack as-is.

## 6. Privacy rules

These logs live on the user's machine and may be pasted to teammates, so:

- Summarize; never paste raw email bodies, Slack messages, prompts, or code.
- Leave out anything that looks personal, HR-related, or confidential (compensation, performance, health, legal), even if it appeared in a work channel. For managers, this includes 1:1 content and performance or hiring discussions about named people: log that the meeting happened and any non-sensitive outcome, nothing more.
- Keep customer details at the level a teammate already knows: the customer name and what was done, not contract terms or the contents of their data.
- Keep the collector's `[REDACTED]` markers out of the log entirely; don't try to reconstruct what was there.
- Never post, send, or share the log anywhere. Write the file and stop. If the user asks to post the standup, show them the text and let them send it, or ask before using a send tool.



## 7. Finish

Reply with the file path and the Standup block. Then, in one line, name any sources that weren't checked and why (not connected, not installed, error). Nothing else.

## Weekly or multi-day recaps

If the user asks for a recap and daily files already exist in `output_dir` for those days, read them first and summarize from them rather than re-collecting everything. For days with no file, run the steps above.