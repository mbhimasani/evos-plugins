# Examples for daily-worklog

Read the section you need. The names and IDs are invented; they show shape, not text to copy.

## Contents
- Combining overlapping sources (used with SKILL.md "One item, one entry")
- Plans bullets by role (used with SKILL.md "Writing the standup block")

## Combining overlapping sources

In each case, several traces become one entry, and each source contributes what only it knows.

**A PR review seen in four places**

Traces:
- GitHub `reviews_submitted`: `acme/api#412` "Add idempotency keys to payments webhook" by `jlee`, CHANGES_REQUESTED, 5 comments, at 11:20.
- Claude Code session 10:35–11:15 in `acme/api` on branch `jlee/idempotency-keys`. The prompts ask how retries interact with the dedupe table and whether the TTL is long enough.
- Slack, #payments-eng, 11:25: you posted the PR link and asked whether the 24h TTL matches the provider's retry window.
- GitHub notification email: "Review requested: acme/api#412". Skip it: this is a received notification, and GitHub was checked.

Combined, under the **Code review** workstream:

> **acme/api#412: Add idempotency keys to payments webhook** (author: jlee) · Changes requested, 5 comments
> - Spent ~40m reading it with Claude Code (10:35–11:15), focused on how retries interact with the dedupe table.
> - Main concern: the 24h key TTL may be shorter than the provider's retry window. Raised it in #payments-eng to confirm the window before approving.

Not: one bullet for the review, another for the Slack message, and a third under Communication.

**A ticket that moved because its PR merged**

Traces:
- Linear: `ENG-231` "Paginate audit log endpoint", In Review → Done at 15:02.
- GitHub `prs_merged`: `acme/api#398`, branch `eng-231-paginate-audit-log`, merged 14:58.
- git: 3 commits on that branch in the morning.
- Claude Code session 09:10–10:40 on the same branch. Notes written: cursor-based pagination chosen over offset because rows are inserted concurrently.

Combined, as one workstream:

> **Audit log pagination (ENG-231 · Done)**
> - Finished cursor-based pagination for the audit log endpoint; PR #398 merged at 14:58, and Linear closed with it.
> - Chose cursors over offsets: rows are inserted while users page through, so offsets would skip or repeat entries.
> - Evidence: `acme/api` / `eng-231-paginate-audit-log` · 3 commits · ~1h 30m in Claude Code.

The Linear table still lists ENG-231 and the Pull requests table still lists #398, because those are indexes. In the Standup block it appears once: "Shipped audit log pagination (ENG-231)."

**A meeting with notes and a follow-up**

Traces:
- Calendar: "Release 1.2 go/no-go", 16:00–16:30, accepted.
- Granola notes for the same slot: decision to ship Thursday; action item for you: confirm the migration rollback plan.
- Slack, #release, 16:45: you posted the rollback steps.

Combined, under Meetings or the release workstream:

> **Release 1.2 go/no-go** (16:00–16:30): decided to ship Thursday. My action item, confirming the migration rollback plan, was done right after; I posted the rollback steps in #release at 16:45.

It doesn't also appear under Communication, and the action item doesn't reappear in the plans because it's already done.

**A customer issue across email, Slack, and a call** (common for forward deployed roles)

Traces:
- Gmail, sent: reply to Globex, "SSO login loop after IdP change".
- Slack, #globex-deploy: you asked the platform team about SAML clock skew.
- Calendar and Granola: "Globex SSO debug", 13:00–13:45. Root cause was IdP clock drift; they'll fix NTP, and you'll verify tomorrow.

Combined, as one workstream:

> **Globex: SSO login loop**
> - Debugged on a call with their IT team (13:00–13:45). Root cause was clock drift on their IdP, which broke SAML assertion timing. They're fixing NTP on their side.
> - Confirmed the skew tolerance with the platform team in #globex-deploy, and replied to the Globex thread with next steps.
> - Next: verify logins once their NTP fix is in.

The verification becomes one plans bullet. The email and Slack thread don't appear again under Communication.

### Getting progress right

Activity shows what the user worked on, not how far they got. Before calling something finished:

- **Code:** commits, merged or opened PRs, and Linear status changes are evidence of completion. Session prompts alone are not. A merged PR is shipped; an opened PR is "up for review", not done.
- **Reviews:** a submitted review is completed work. Report its outcome (approved, changes requested, commented) and the number of comments.
- **Tickets:** trust the status transition in the window, not the issue title.
- **Meetings and threads:** an outcome counts only if the notes or messages show a decision, agreement, or delivered item.
- **Sequential work** (modules, phases, checklists, test plans): read the current contents of any progress-tracking file edited in the window, such as session notes, plan files, checklists, anything under `.plans/`, or files named like `*notes*.md`, `TODO.md`, or `PLAN.md`. Report every step finished in the window, not just the first one. Going back to finish an earlier step is its own progress ("closed the remaining gaps in step 1, completed step 2, started step 3").
- If none of this makes completion clear, describe the work without claiming it was finished.

## Plans bullets by role

Illustrations of shape. The user's own `standup.example` and saved preferences take priority.

> *Engineer:* Finish the retry logic for webhook delivery (ENG-512) and get the PR into review; address review comments on the rate limiter PR at that point.
>
> *QA:* Verify the 6 tickets in the QA column for Thursday's release - aiming for 3 today; file regressions against the release epic as I find them.
>
> *Forward deployed engineer:* Acme rollout - finish the SSO config with their IT team on the 2pm call and send the go-live checklist at that point; reply to Globex on the data export question.
>
> *Engineering manager:* Finalize the Q4 staffing plan for review Friday; run the two candidate debriefs and send hiring decisions at that point.