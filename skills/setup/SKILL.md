---
name: setup
description: First-time setup of ops-desk on a new computer: data folder, cash flow workbook, ops@ mailbox and Zoho Books connection, with a check that the Zoho numbers match Zoho. Use right after installing the plugin, or for "set up ops-desk", "connect Zoho", "test the plugin".
---

# Setup

Walk the user through this one step at a time, in plain English. Run each check and report the result before moving on. Do not skip a failed step.

Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ops.py"` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Cash flow script: `cashflow.py` in the same folder.

## 1. Python and openpyxl
Run `python3 -c "import openpyxl"`. If it fails, tell the user `pip install openpyxl` is needed and ask before running it.

## 2. Data folder and settings
Ask where to keep the data folder (default `~/ops-desk-data`). If the colleagues share one, it should be a synced OneDrive folder. Ask for the cash flow workbook path (the synced file) if it exists yet.
Run `ops.py init --data-dir <folder> [--cashflow-file <file>]`. This creates empty templates, not sample data, and writes `~/.ops-desk.json` so no environment variables are needed. Run `ops.py where` and `ops.py check` and show the result.

## 3. Who gets what (`config.json` in the data folder)
Ask, then write:
- `management_recipients`: who gets the weekly plan and management report.
- `cashflow_editors`: only mail from these addresses can change the cash flow.
- `site_expense_categories`: leave empty until step 6, then choose from the real Zoho categories.
Leave `auto_send` empty. Everything stays a draft.

## 4. Cash flow workbook
If a path is set: run `cashflow.py check`, then `cashflow.py summary`. Report opening, closing and lowest balance and any shortfall months. If check fails, show the errors and stop. Do not edit the workbook during setup.

## 5. Connectors
Check which tools you have. Do not guess.
- **Mail (ops@):** Microsoft 365 connector. If it is missing, tell the user to add it in Claude's connector settings and sign in as the ops@ account, then restart the session. Until then, the inbox fallback works: forwarded mails saved as `.eml` or `.txt` in `<data>/inbox/`.
- **Zoho Books:** if no Zoho tools are listed, tell the user to add the Zoho Books connector (pick the data centre their Zoho account uses), sign in, and restart the session. Never ask for passwords, tokens or codes. Stop here for Zoho and continue with the rest. Resume at step 6 later.

## 6. Zoho test (the check that matters)
Only when Zoho tools exist.
1. List the Zoho tools. Say which of these are missing: find projects, list invoices, bills, expenses and purchase orders by project.
2. Ask where the project code lives in Zoho (project code field, name prefix, reporting tag or custom field). Save the answer in `config.json` as `zoho_project_code_field`.
3. List the Zoho projects and show them as a table. The user picks one real project with invoices, bills and some site expenses. Put it in `projects.csv` only after the user confirms the row: code, name, client, site, type, status, dates, cost budget and contract value in INR excluding GST, `cash_head` (the Head used for it in the workbook; list the heads from `cashflow.py summary` to choose), owner.
4. Run the `zoho-sync` skill for that one project.
5. Run `ops.py pnl` and show: invoices total, bills total, expenses total, receivable, payable. Ask the user to open the same project in Zoho and compare these totals. A mismatch means the field mapping is wrong: find out why (GST included or excluded, void or draft documents, a missing document type, wrong project match) and fix it before syncing any other project.
6. Show the expense categories seen on that project. The user picks which count as site expenses. Save them in `site_expense_categories`.

## 7. Add the other projects
List the remaining Zoho projects. Propose rows for `projects.csv`. Write them after the user confirms. Then run `zoho-sync` for all of them and `ops.py pnl`.

## 8. Mailbox test
If the mail connector exists: ask the user to send a short test mail to ops@, then run the `ops-inbox` skill. Check that it is classified, nothing is sent, and a draft appears.

## 9. Schedule (offer, do not create without a yes)
Offer the three scheduled tasks from the README (morning inbox and reminders, Monday plan, Friday report). Explain they only run while Claude is open on a computer that is on, and that unattended runs never change the cash flow.

## Finish
Report a checklist: what works, what is waiting (for example Zoho not connected yet), and the next action for the user.
