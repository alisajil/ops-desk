---
name: management-report
description: Produce the management status report (weekly on Friday or monthly) with cash position, project P&L, RAG per project, issues and decisions needed. Use for "management report", "status for the directors", "month-end ops summary".
---

# Management report

## Conventions
Same as `ops-inbox`: data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py`, run `check` first, no manual arithmetic, log every change in `log.md`. Amounts in Indian style (lakh, crore).

## Steps
1. `ops.py check`, `ops.py report`, `ops.py pnl`, `ops.py issues`, `ops.py overdue`, `cashflow.py check`, `cashflow.py summary`. Read `<data>/last_zoho_sync.txt`. If it is older than 7 days, offer `zoho-sync` first, or state the as-of date at the top of the report.
2. Write the report:
   - Summary: three lines. Overall status, the biggest risk, the biggest decision needed.
   - Cash position first when it is negative: opening, closing at the end of the cash flow, lowest balance and its date, and the months in shortfall (from `cashflow.py summary`). Add the largest pending payments by head and the receipts the plan depends on.
   - Table: project code, name, owner, RAG, next due date, percent billed, profit to date and margin, cost percent of budget, open and overdue issues.
   - For each amber or red project: the reasons from the script, the cause if known from `notes` or `log.md` (say "cause not recorded" if not), and the recommended action.
   - Project P&L (follow the `project-pnl` rules, including the note that early projects show a loss before billing): billed, received, overdue receivables, cost to date, committed, profit and margin per project, then totals.
   - Site expenses per project and by category, and any month-on-month jump.
   - Issues: overdue first, total delay days open, total cost impact, and any safety issue stated plainly.
   - Early warnings (`early-warning`): every high item, and medium items open more than 7 days, each with a recommendation. Add the bids pipeline (`gem-bids`), documents expiring (`company-documents`) and client contact and complaints (`client-care`).
   - Lookahead: key tasks due in the next 14 days (`ops.py week --start <date>` twice).
   - Decisions needed: numbered, each with a recommended answer and the date it is needed by.
3. For a monthly report, add: projects completed, projects started, total exposure against total approved, and the top three recurring causes of delay from `log.md`.
4. Save to `<data>/reports/management-YYYY-MM-DD.md`. Draft to `management_recipients`. Send only if `management_report` is in `config.json` `auto_send`.

## Rules
Report what the data shows. If the CSVs look stale (newest `log.md` entry older than 7 days), say that at the top of the report. Do not give legal, tax or GST conclusions; flag them for the accountant.
