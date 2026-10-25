---
name: project-schedule
description: Create or re-plan a project schedule for an engineering company (site installation, workshop fabrication or repair jobs) as rows in tasks.csv. Use for "plan this project", "add a job", "we are delayed, re-plan", or "who is double-booked".
---

# Project schedule

## Conventions
Same as `ops-inbox`: data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`), run `check` first, no manual arithmetic, log every change in `log.md`.

## Templates (editable starting points, not facts)
**Site installation (for example fire protection or mechanical systems):** site survey, design and calculations, drawings, client approval, authority approval (only where the project needs it; confirm local requirements with the user, do not assume), procurement (list long-lead items such as pumps and valves first), workshop prefabrication, delivery to site, installation (header, risers, branch lines, heads, hydrants or detectors as applicable), flushing and hydro test, commissioning, client inspection and handover documents.

**Workshop job (repair or fabrication):** receive and inspect, quote and approval, strip and diagnose, parts procurement, machining or fabrication, assembly, pressure or function test, paint and pack, dispatch.

## New project
1. Collect from the user or the email: project code (the one used in Zoho Books), name, client, site, type, owner, start, target end, cost budget and contract value in INR excluding GST, and the cash flow head used in the workbook. Ask only for what is missing.
2. Draft the task list from the right template. Use durations the user gives. Where you estimate, write `est` in `notes`. Say plainly that estimates are yours.
3. Show the proposed table (id, task, owner, start, due, depends_on) and wait for a yes before writing.
4. On yes: add the project row (`status` planned or active), then the tasks. Task ids continue from the highest existing `T###`. Use `;` between ids in `depends_on`. Respect `work_week` in `config.json`.
5. Run `ops.py check`, then `ops.py week` to look for clashes.
6. Run `ops.py folders` to create the project's folder in the Claude folder, then offer the `project-submissions` skill to build its submission checklist.

## Delay or change
1. Update the late task. Move dependent tasks by the same slip unless the user says otherwise.
2. Show a before and after table of changed dates and the new project end date. Ask for a yes before writing.
3. If the end date moves, flag it for the management report and for the client contact. Draft a note, do not send.

## Clash check
`ops.py week --start YYYY-MM-DD` lists owners with overlapping tasks. Report each clash and suggest who or what to move. It is a flag, not an error.
