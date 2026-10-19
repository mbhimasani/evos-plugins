# Subagent instructions for daily-worklog

Read this when SKILL.md section 4 says to delegate. It covers how to split the work, the exact instructions to give each subagent, and what the main agent keeps.

## Splitting the work

Launch the subagents in parallel with Claude Code's subagent tool, using a general-purpose agent:

- One subagent per long session, given its `details_file`, the current contents of any notes file it wrote to, the window, and the user's role.
- For a multi-day range, one subagent per day. Each runs SKILL.md steps 2–3 for its day and returns per-day findings in the same format.
- For a very large Slack or Gmail day, one subagent per source.

## Instructions for a session or day subagent

Each subagent's job is to extract, not to summarize. The detailed log is only as good as what comes back, so give each one these instructions in full:

> Read the material for this session and return a detailed, chronological account. Keep specifics; don't generalize. For each phase of the session (with approximate times from the prompt timestamps), report: what the user was trying to do; what they explored (files, modules, functions, docs, tickets, commands, by name); what they learned, as concrete facts; where they were confused, where docs and code disagreed, or what took several attempts, and whether and how it was resolved; decisions made and why, including approaches tried and dropped; and next steps they noted. Preserve every Linear ID, branch, repo, PR, customer name, and person's name exactly; the main agent uses them to link sources. Paraphrase rather than pasting long text; short phrases from the user's own notes are fine where wording matters. Don't evaluate the user's work or add advice. Leave out anything personal, HR-related, benefits, payroll, or secrets (including `[REDACTED]` markers). Length should match the session: a 4-hour session can warrant 40+ lines.

## Instructions for a Slack or Gmail subagent

> Return one line per thread: channel or subject, topic, outcome, any commitment the user made, and any ticket IDs, PR numbers, customers, or people mentioned, exactly as written. Skip notifications from tools (GitHub, Linear, calendar, CI) and anything personal, HR-related, benefits, payroll, or secrets.

## What stays with the main agent

Linking across sources, deduplication, the Timeline, the Standup block, and writing the file all stay in the main agent. Build workstreams by combining the subagents' accounts with everything else; don't paste a subagent's account in as a workstream unchanged. If subagents aren't available, read the details files directly in chunks instead. The result should be the same, just slower.