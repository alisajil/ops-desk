---
name: issue-tracker
description: Log, update and report project issues (delays, quality, safety, material, payment, client) in issues.csv with owner, due date, days of delay and cost impact. Use for "log this issue", "what is late", "open issues on project X", "close the issue", or when an email or site report describes a problem.
---

# Issue tracker

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Log changes in `log.md`. Drafts only for anything sent out.

## Columns (`issues.csv`)
`id` (I001, continue from the highest), `project_id` (project code), `raised` (date), `type` (delay, quality, safety, material, payment, client, other), `description` (one line, quote text containing commas), `owner`, `status` (open, in_progress, resolved), `due` (date to resolve), `days_delay`, `cost_impact_inr`.

## Log an issue
1. Source: an email, a site report, or the user. Take project code, what happened, who owns it, and by when. Ask only for what is missing.
2. `days_delay` and `cost_impact_inr`: write only figures the source states or the user gives. Otherwise leave them 0 and say they are unknown. Never estimate.
3. Check for a duplicate first: same project and a similar description still open. If found, update it instead.
4. Add the row. `ops.py check`.
5. Follow-ups:
   - `delay` with days: offer `project-schedule` to re-plan dependent tasks and flag a moved end date.
   - `payment`: link it to the overdue receivable in `project-pnl`.
   - `material`: check the related task in `tasks.csv` and mark it blocked if work cannot proceed (ask first).
   - `safety`: put it first in the digest and the management note. State facts only. Do not give regulatory conclusions.

## Update or close
Change `status`, `due`, or figures on the existing row. Closing needs the user's yes or a clear statement in the source. Keep resolved rows. They feed cost-impact history.

## Report
`ops.py issues` gives open issues sorted by days overdue, and per project: open, overdue, delay days, cost impact (all and open). Show:
- Overdue issues first (owner, days overdue, what is needed).
- Per project counts, total delay days open, total cost impact.
- Issues with no due date or no owner. Ask the user to set them.
- A project with 3 or more overdue issues turns red in `ops.py report`.

## Reminders
Overdue issue owners get a reminder through `stakeholder-reminders` style drafts: one short message listing only their issues. Never list other people's issues.
