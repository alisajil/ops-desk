---
name: project-pnl
description: Per-project profit and loss, cost against budget, overdue client payments and vendor bills, and site expenses, from Zoho Books data. Use for "project P&L", "how is project X doing financially", "site expenses this month", "who owes us money", "which project is losing money".
---

# Project P&L

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first. Never calculate money yourself. Amounts excluding GST, shown in lakh and crore.

## Steps
1. Check freshness: read `<data>/last_zoho_sync.txt`. If missing or older than 7 days, say the numbers are as of that date and offer the `zoho-sync` skill. Do not sync unasked inside a scheduled run unless the task says so.
2. `ops.py pnl` for all projects, or pick one project code from the output.
3. For each project report:
   - Contract value, billed, received, receivable, and overdue receivable (client payments late).
   - Cost to date (bills plus expenses), committed (open POs), cost budget, percent used, level.
   - Profit to date and margin on billed revenue, planned margin from contract minus budget, cash profit (received minus paid).
   - Site expenses, and expenses by category. `site_categories_configured` false means `site_expense_categories` is not set in `config.json`: say so and ask which categories count as site expenses.
   - Overdue vendor bills (`overdue_payable_inr`).
4. Totals across projects from `totals`.

## Reading the numbers honestly
- A project early in its life shows a loss because costs come before invoices. Compare to percent billed before calling it a problem. Say "not yet billed" rather than alarm.
- The P&L is project-level only: bills and expenses posted to the project in Zoho. Salaries and overheads count only if posted to the project. Say that in one line.
- Cost percent used above 90 is amber, above 100 is red (set in `ops.py`).
- Compare overdue receivables with the cash flow workbook: if the workbook expects a receipt that Zoho shows as overdue, flag the gap. Do not edit the workbook from here. Use `cashflow-update` after the user confirms.

## Follow-ups (drafts only)
- Overdue receivable: a polite payment reminder draft to the client contact in `stakeholders.csv`. No internal budget figures, no margins.
- Overdue vendor bill that blocks work: flag to management with the amount and what it blocks.
