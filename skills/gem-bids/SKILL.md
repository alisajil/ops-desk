---
name: gem-bids
description: Track government tenders on the GeM portal from identification to award: go or no-go, document checklist built from the bid's own document, readiness against closing dates and document expiry, and what to set up after a win. Use for "new GeM bid", "are we ready to bid", "bid pipeline", "we won the bid".
---

# GeM bids

GeM is the Government e-Marketplace. Bids and their terms change. **Never assume a requirement.** The bid document and the portal's own help pages are the authority. Where you are unsure, say so and name where to check.

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Drafts only. Log changes in `<data>/log.md`.

## What you never do
- Log in to the portal, enter credentials, upload or submit a bid. A person does all of that.
- Decide the price. You prepare numbers; management approves the price.
- Treat bid prices, costing or buyer details as shareable outside the company.

## Files
- `bids.csv`: one row per bid (`portal` GeM, `bid_no`, `title`, `buyer`, `closing`, `opening`, `value_inr`, `security_inr` for any bid security the document asks for, `status`, `owner`).
- `bid_documents.csv`: the checklist for each bid. `doc_id` links a line to `documents.csv`, so expiry is checked against the closing date.
- Statuses: identified, preparing, submitted, won, lost, no_bid.
- Files: `Bids/<id>-<bid no>/Bid-document/` for the tender document and `Prepared-pack/` for what is ready to submit. `ops.py folders` creates them.

## Steps
1. **Identify.** The user gives you the bid document (PDF) or its details. Read it. Extract only what it states: bid number, closing and opening dates, bid security amount, the documents it asks for, eligibility conditions, delivery period, payment terms, performance security, penalties, clarification dates. Show the extraction and the page of each item. Write `bids.csv` after the user confirms.
2. **Go or no-go.** Prepare a one-page note for management: fit with what we do, a rough cost against the value (use `ops.py pnl` for comparable projects), bid security and performance security effect on cash (`cashflow-update` summary), people available (`ops.py workload`), documents ready (`ops.py bids`). Recommend go or no-go. Management decides. Record it in `decisions.md`. A no-go sets the status to no_bid with the reason in `notes`.
3. **Checklist.** For every document the bid asks for, add a `bid_documents.csv` row. Link `doc_id` where `documents.csv` has it. Mark status ready, needed, missing or na. Put an internal due date at least 3 working days before closing.
4. **Track.** `ops.py bids` shows blockers: missing documents, and documents that expire before the bid closes. Send reminders at 14, 7, 3 and 1 days. A blocker inside 7 days is a high warning in `early-warning`.
5. **Submit.** The user submits on the portal. Ask them to confirm the submission and then set the status to submitted. Note the opening date for follow-up.
6. **Result.** Won: set up the project with the `project-schedule` skill (project code, tasks from the bid's delivery terms, contract value, cash flow head, `client_type` govt). Then run `ops.py folders` and build the project's submission checklist with `project-submissions`. Plan invoices and any performance security in `cashflow-update`. Lost: record why in `notes` for the next bid.

## After the win
Watch the delivery date and payment terms stated in the order. Chase payment early and politely through `project-pnl` and `client-care`. Government payment timing is a cash risk: keep the cash flow workbook current.

## Common requirement types (check each bid)
Companies are often asked for registration and tax documents, quality or compliance certificates, financial statements or a bank letter, past order or experience certificates, maker authorisation letters, technical compliance sheets, and a price schedule. Some bids give relaxations to certain categories of seller. Do not assume which apply: read the bid and the portal's help pages, or ask the user.
