---
name: weekly-plan
description: Build the weekly operations plan (per project and per person) and draft it to management and the team. Use every Monday, or for "plan the week", "what is on this week", "send the weekly plan".
---

# Weekly plan

## Conventions
Same as `ops-inbox`: data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py`, run `check` first, no manual arithmetic, log every change in `log.md`.

## Steps
1. Run `ops.py check`, `ops.py report`, `ops.py overdue`. Start the week on Monday (use `week --start <that Monday>` if run on another day and the user wants the coming week). Run `cashflow.py check` and `cashflow.py list --pending --from <Monday> --to <Sunday>` for the week's payments and receipts, and `cashflow.py summary` for the cash position.
2. Compose the plan:
   - Headline: one sentence on the state of the week.
   - Per project: RAG, what is due this week (task, owner, date), what is overdue, what is blocked and by what.
   - Per person: their tasks this week in date order.
   - Clashes from `week`, with a suggested fix.
   - Cash this week: payments and receipts due (date, item, amount), the balance after each day's items, the lowest balance in the next 30 days. If any month is in shortfall, say so in the headline.
   - Open issues per project, overdue ones first (from `ops.py issues`), with owner and what is needed.
   - Money flags: projects with cost over 90 percent of budget, overdue client payments, overdue vendor bills that block work (from `ops.py pnl`; state the date of the last Zoho sync).
   - Decisions needed from management, each with a recommended answer.
3. Save the plan to `<data>/reports/weekly-YYYY-MM-DD.md`.
4. Drafts:
   - Management: full plan, to `management_recipients` in `config.json`.
   - Each internal owner (stakeholders with type `internal`): only their own section.
   - Clients and vendors: nothing, unless the user asks. Their updates come from `stakeholder-reminders` or the project owner.
5. Create drafts with the mail connector's draft tool, or write them to `<data>/drafts/`. Send only if `weekly_plan` is in `config.json` `auto_send`. Otherwise tell the user the drafts are waiting.

## Style
Short sentences. Dates as `Tue 27 Oct`. No internal budget figures in anything a client could see.
