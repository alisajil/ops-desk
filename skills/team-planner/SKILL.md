---
name: team-planner
description: Organise the team: roles and skills, who has capacity, who is on leave, assigning new work fairly, and spotting overload before it causes delays. Use for "who can take this job", "plan the team for next week", "Ravi is on leave", "is anyone overloaded".
---

# Team planner

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Drafts only. Log changes in `<data>/log.md`.

## Files
- `team.csv`: `name`, `role`, `skills` (separate with `;`), `weekly_hours`. Names must match task owners and stakeholder names.
- `leave.csv`: `name`, `from`, `to`, `reason`. Dates inclusive.

## Look at the load
`ops.py workload` (default next 14 days) gives each person's open tasks, the day they have the most at once, and leave in the window. Owners of tasks who are not in `team.csv` are listed too. Ask the user to add them.
The warning limit is `max_concurrent_tasks` in `config.json` (default 4). Tasks do not carry effort hours yet, so load means the number of open tasks at once. If the user has estimates, suggest adding them first.

## Assign new work
1. List what the job needs (skills, dates).
2. Show a table: each candidate, matching skills, tasks that overlap, leave in the window.
3. Recommend one person per task and say why. Management or the project owner confirms.
4. Write owners into `tasks.csv` only after a yes. Run `ops.py check`.
5. A person should have at most three priorities in a week. If the plan gives more, say so and propose what to move.

## Leave
- Record leave from an email or message in `leave.csv` after the user confirms the dates.
- Run `ops.py risks`: a task owned by someone on leave is a warning. Propose who covers it, or a new date through `project-schedule`. Never change dates on your own.
- Tell the person's project owner and management, as a draft.

## Keep it structured
- Every task has an owner and a date. Every action from a huddle becomes a task.
- Spread critical tasks. If one person owns most of the critical path, flag it as a key-person risk.
- Each month: show who is over and under loaded, and which skills are missing for the bids in `bids.csv`.

## Never
Rate or rank people's performance, or make hiring, pay or disciplinary suggestions from workload data. Those are management's decisions and need far more than this data.
