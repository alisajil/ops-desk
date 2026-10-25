---
name: early-warning
description: Scan for problems that are coming in the next weeks (schedule slips, cost running ahead of progress, late client payments, unhappy clients, expiring documents, bids with missing documents, overloaded or absent people, cash shortfall) and warn management early with a recommendation. Use daily, or for "what could go wrong", "any risks", "heads-up for management".
---

# Early warning

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first. Drafts only. Log changes in `<data>/log.md`.

## Steps
1. If the Zoho data is more than 3 days old, offer `zoho-sync` first. Say the as-of date if you skip it.
2. `ops.py risks`. Without `--no-cash` it also reads the cash flow workbook. If `cash_note` says the workbook was not read, say so in the report.
3. For each item, in the order given (high first, soonest first), write:
   - **What:** the title, in plain words.
   - **When:** `days_until` as a date. Negative means it already happened.
   - **Impact:** money, delay or client effect, using only figures in the detail. If unknown, say unknown.
   - **Rule that fired:** for example "cost 77% of budget while 33% of tasks are done".
   - **Recommendation:** one concrete action with an owner.
   - **Decision needed by:** a date, if management must decide.
4. Compare with `<data>/risk_log.md`. It lists each warning id with the date first seen and its status. New items get a line. Items open more than 7 days are marked repeat and go up one level. Items that disappeared are marked cleared with the date.
5. Write the heads-up as a draft to `management_recipients` in `config.json`. High items go the same day. Do not wait for the weekly report.

## Be honest about what these are
- These are rules over the data, not forecasts. Say which rule fired and what new data would change the call.
- Progress is the share of tasks done, which is rough. Ask the project owner for a better progress figure before a big decision.
- Separate **measured** (overdue now) from **predicted** (will overrun if nothing changes).
- Do not raise alarm for early-stage projects that show cost before billing. Show the rule and let the numbers speak.
- Thresholds (days, percentages, limits) are in `config.json`. If management keeps ignoring a rule, suggest changing it. Do not silently stop reporting it.

## Areas covered
schedule, cost, receivable and payable (money), client contact and complaints, documents, bids, team load and leave, cash.
