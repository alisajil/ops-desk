---
name: zoho-sync
description: Pull per-project invoices, bills, expenses and open POs from Zoho Books into zoho_lines.csv, matched by project code. Use before a P&L, weekly plan or management report, or for "sync Zoho", "refresh the numbers", "update from Zoho Books".
---

# Zoho sync (read-only)

Zoho Books holds the actual money per project. This skill copies it into `zoho_lines.csv` so `ops.py pnl` can compute from it. It never creates, edits or deletes anything in Zoho.

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after. Log the sync in `log.md`.

## Connect
Use the Zoho Books connector from Claude's connector directory. If it is not connected, tell the user to connect it in Claude (the `/mcp` screen or Connectors settings) and sign in with a Zoho account that can read Books. If asked for a data centre, choose the one the Zoho account uses (India accounts are usually zoho.in). Do not ask for passwords, tokens or codes.

If the connector is missing a tool, or the user prefers, use the export route: the user saves Zoho Books exports (invoices, bills, expenses, purchase orders, filtered by project) into `<data>/inbox/zoho/`. Map their columns the same way.

## Steps
1. List the connector's tools. Do not assume names. You need: find projects, and list invoices, bills, expenses and purchase orders filtered by project. Say which of these the connector lacks.
2. Project codes: `projects.csv` `id` is the Zoho project code. Find each active or recently closed project in Zoho by that code. If the code is stored in a different place (project name prefix, reporting tag, custom field), ask the user once, and record the answer in `config.json` as `zoho_project_code_field`. If a project has no match, list it and skip it. Never guess a match.
3. For each matched project fetch all its documents (no date filter). Write void, draft and cancelled documents too, with their status. The script leaves them out of the totals.
4. Map to `zoho_lines.csv` columns:
   - `kind`: invoice, bill, expense, po. Only open POs matter for committed cost, but write all.
   - `doc_no`, `date`, `due` (blank for expenses), `party` (customer or vendor), `category` (expense account or item category), `status` (lower case Zoho status), `zoho_id`.
   - `amount_inr`: the amount excluding GST (sub total).
   - `paid_inr`: the settled part, also excluding GST: `amount_inr * (total - balance) / total`. Compute this in a short Python snippet, never by hand.
5. Rewrite the file idempotently: remove existing rows for the synced project codes, add the fresh rows, keep other projects' rows. Use a short Python snippet with the csv module. Header must stay exactly as in `examples/data/zoho_lines.csv`.
6. `ops.py check`. Write `<data>/last_zoho_sync.txt` with the ISO date and time.
7. Report: projects synced, rows per kind, projects skipped and why, and what changed since the last sync that matters (newly overdue invoices or bills, large new bills, new expenses).

## Never
- Write to Zoho. Entries the accountant should post (a site expense claim from an email, a vendor bill) go to `<data>/drafts/zoho-entries.md` as: project code, date, party, category, amount excluding GST, document number, source email subject.
- Copy bank, card or tax registration numbers into the CSV.
- Give GST, tax or legal conclusions. Flag them for the accountant.
