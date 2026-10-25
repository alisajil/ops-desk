---
name: stakeholder-reminders
description: Draft reminders for people with tasks due soon or overdue (staff, vendors, client contacts) and escalate repeat lateness to management. Use daily, or for "send reminders", "who is late", "chase the team".
---

# Stakeholder reminders

## Conventions
Same as `ops-inbox`: data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py`, run `check` first, no manual arithmetic, log every change in `log.md`.

## Steps
1. `ops.py check`, then `ops.py reminders` (default: due within 2 days or overdue, skipping tasks already reminded in the last 2 days).
2. For each entry in `owners`, write one short message listing only that person's tasks: task, project, due date, days late if any, one clear ask ("reply with status or a new date"). Do not list other people's tasks.
   - `type` internal: direct and brief.
   - `type` client or vendor: polite, milestone-level only. No internal budget figures, no blame, no internal delays unless the user approved wording.
3. Create drafts with the mail connector's draft tool, or write them to `<data>/drafts/`. Send only if `internal_reminder` is in `config.json` `auto_send` and the recipient is internal. Client and vendor reminders are always drafts for the user to approve.
4. After a message is sent or the user confirms the draft is used, run `ops.py mark-reminded --owner "<name>" --tasks T001,T002`. Do not mark tasks you only drafted and the user did not accept.
5. `unmatched_owners`: tell the user these names are missing from `stakeholders.csv` and ask for email addresses.
6. `escalate_to_management`: tasks already reminded and now 3 or more days late. Put them in a short note to management with the owner, task, days late and the last reminder date. Draft only.

## Output to the user
A list of drafts created (who, how many tasks), anything needing their decision, and the escalation note.
