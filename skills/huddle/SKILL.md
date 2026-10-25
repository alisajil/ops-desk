---
name: huddle
description: Run the daily or weekly operations huddle: build the agenda from live data, record decisions and actions, turn actions into tasks with owners and dates, and send the recap. Use for "prepare the huddle", "daily stand-up", "weekly ops meeting", "write the minutes".
---

# Huddle

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first. Drafts only. Log changes in `<data>/log.md`.

## Before the meeting
1. `ops.py huddle --kind daily` (15 minutes) or `--kind weekly` (45 minutes). Add `--no-cash` only if the workbook is not set up.
2. Read the previous minutes in `<data>/huddles/`. List actions that were due and say which are done and which are not.
3. Write the agenda, timeboxed, from the data:
   - **Daily:** what is late, what is due today and in two days, what is blocked, the top risks, bids closing within 14 days, project submissions due or overdue, documents expiring within 30 days, clients who need contact.
   - **Weekly:** all of the above, plus profit and loss totals, the week ahead and clashes, each person's workload, cash position and decisions waiting.
   - Each item names an owner and the question to settle. Put the biggest risk first.
4. Share the agenda as a draft to the attendees in `stakeholders.csv` (internal only).

## During the meeting
The user dictates or pastes notes. Capture:
- **Decisions:** what, who decided, why, review date.
- **Actions:** owner, due date, project code. No owner or no date: ask. Maximum three priorities per person per week. Say so when a person has more.
- **Risks accepted:** who accepted, until when.

## After the meeting
1. Save minutes to `<data>/huddles/YYYY-MM-DD-<daily|weekly>.md`: attendees, decisions, actions, risks accepted, next huddle.
2. Add decisions to `<data>/decisions.md`.
3. Turn each action into a task in `tasks.csv` (next free `T###`, owner, due, project code). Show the rows and wait for a yes before writing. Then `ops.py check`.
4. Draft a recap to the attendees: decisions, and each person's own actions with dates. Do not list other people's actions to external people.

## Rules
- A huddle is about decisions, not status reading. Skip items with nothing to decide.
- An action raised twice and still open is a risk: put it on the risk list.
- If a person is on leave in the next two weeks (`ops.py workload`), say who covers their actions.
