# ops-desk

Operations, project money and cash assistant for a small engineering and installation company. People email `ops@your-company.com`. Claude reads the mail, keeps schedules, issues and the cash flow workbook up to date, pulls project actuals from Zoho Books, and drafts the weekly plan, reminders and management report.

Version 0.2.0. Three places hold data, each with one job:

| Where | Holds | Written by |
|---|---|---|
| Zoho Books | Actual invoices, bills, expenses, POs per project code | Your accountant. The plugin only reads it. |
| Cash flow workbook (Excel on OneDrive) | Forward cash plan: what is paid and received when | `cashflow-update`, after your yes |
| CSV files in the data folder | Projects, tasks, issues, stakeholders, a copy of Zoho lines | The plugin |

The project code is the key everywhere: `projects.csv` `id` is the same code used in Zoho Books.

## Skills

| Skill | Use it for |
|---|---|
| `setup` | First-time setup on a new computer, including the Zoho test. |
| `ops-inbox` | Turn new mail into task and issue updates. Draft entries for the accountant. Draft replies. |
| `zoho-sync` | Copy per-project invoices, bills, expenses, POs from Zoho Books (read-only). |
| `project-pnl` | Per-project P&L, cost against budget, overdue client payments and vendor bills, site expenses. |
| `issue-tracker` | Log and track late issues: delay, quality, safety, material, payment, client. |
| `cashflow-update` | Read and update the cash flow workbook. Report cash position and shortfall months. |
| `project-schedule` | Plan a new job (site install or workshop) or re-plan after a delay. |
| `weekly-plan` | Monday plan: tasks, cash for the week, issues, money flags. |
| `stakeholder-reminders` | Daily reminders. Escalate repeat lateness. |
| `management-report` | Friday or monthly status: cash first, P&L, RAG per project, decisions needed. |

Two scripts do all date and money maths and validate the data, so Claude never calculates these itself:
- `scripts/ops.py`: schedule, issues, P&L from the Zoho lines, reminders, RAG.
- `scripts/cashflow.py`: the Excel workbook. It inserts and removes rows the way Excel does (re-chains the balance formulas, shifts recurring links, summary ranges, highlights and print area), checks the result, backs up the old file, then replaces it. It refuses to write if the file is open in Excel.

## Install (each colleague)

From a shared GitHub repo:

```
/plugin marketplace add <github-owner>/<repo>
/plugin install ops-desk@ops-desk-tools
```

Or from the organization's plugin library on claude.ai if an admin published it there. Then:

```
pip install openpyxl
```

## First-time setup

After installing, open Claude on the computer and run the setup skill:

```
/ops-desk:setup
```

It walks through, one step at a time:
1. Python and `openpyxl` check.
2. Data folder and cash flow workbook path. It creates empty templates (not sample data) and saves the paths in `~/.ops-desk.json`, so no environment variables are needed.
3. Who gets the weekly plan and report (`management_recipients`), and which addresses may change the cash flow (`cashflow_editors`).
4. Cash flow workbook check.
5. Connectors: Microsoft 365 for the ops@ mailbox, Zoho Books. Connect them in Claude's connector settings, then restart the session.
6. **Zoho test:** it syncs one real project and asks you to compare the totals with Zoho before any other project is synced.
7. Remaining projects, mailbox test, optional schedule.

Zoho and the mailbox can be connected later. Run `/ops-desk:setup` again to resume at that step.

To try the scripts on fictional data first: `/ops-desk:setup` is not needed. Run
```
OPS_DESK_DATA=examples/data python3 scripts/ops.py pnl
python3 scripts/cashflow.py --file examples/cashflow-example.xlsx summary
```
`python3 scripts/ops.py where` shows which folder and workbook are in use.

## Zoho Books

1. In Claude, add the Zoho Books connector from the connector directory and sign in with a Zoho account that can read Books. Pick the data centre your account uses.
2. Ask Claude to "sync Zoho". `zoho-sync` lists the connector's tools, finds each project by code, and writes `zoho_lines.csv`. Amounts are excluding GST.
3. Tell Claude once where the project code lives in Zoho (project code field, name prefix, reporting tag or custom field).

Read-only on purpose. Bills and expenses that arrive by email become drafts for the accountant in `<data>/drafts/zoho-entries.md`. If the built-in connector lacks a tool you need, Zoho offers a custom connector through Zoho MCP, or use the export route (save Books exports in `<data>/inbox/zoho/`).

Zoho Books does not give a project P&L through its API as far as I could find, so the P&L is computed here from invoices, bills and expenses posted to each project. Salaries and overheads count only if they are posted to the project.

## Cash flow workbook on OneDrive

1. Put the workbook in a OneDrive folder owned by the ops@ account, or share the folder with each colleague.
2. Install the OneDrive app and sign in so the folder syncs to the computer that runs Claude. On a Mac it appears under `~/Library/CloudStorage/OneDrive-<name>/`.
3. Give the synced file's path to `/ops-desk:setup` (saved as `cashflow_file` in `~/.ops-desk.json`).
4. When Claude saves, OneDrive uploads the change within seconds. People with the file open in Excel Online see it on refresh.

Limits:
- Claude edits the synced local copy. It only runs while a Claude session is running on a computer that is on. It is not a server. For 24/7 operation the next step is a server-side agent using Microsoft Graph.
- If someone has the file open in desktop Excel, Claude refuses to write and reports the change as pending.
- Keep the layout: opening balance in D3, ledger from row 5, closing and lowest rows after it, Month Summary windows in H5:I10. `cashflow.py check` says what is wrong.
- Saving drops Excel's cached results until the file is opened in Excel (formulas recalculate on open).
- The opening balance changes only when you give the real bank balance (`mark-done`).

## Connecting the ops@ mailbox

Claude reads mail through a connector, not a password.
1. Create the `ops@your-company.com` mailbox (Microsoft 365, since OneDrive is in use).
2. In Claude settings, add the Microsoft 365 connector and sign in as the ops@ account (or an account with access to it).
3. Test: ask Claude to "check the ops inbox".

Until then, save forwarded mails as `.eml` or `.txt` in `<data>/inbox/`, or paste them in chat.

## Schedule (optional)

Create scheduled tasks in Claude (Asia/Kolkata):

| When | Prompt |
|---|---|
| Mon to Sat 08:30 | Run the ops-inbox skill, then the stakeholder-reminders skill. |
| Monday 07:00 | Run the zoho-sync skill, then the weekly-plan skill. |
| Friday 16:30 | Run the zoho-sync skill, then the management-report skill. |

Unattended runs never change the cash flow. They list proposed changes for approval.

## Safety rules built in

- Everything is a draft until you say so. `auto_send` in `config.json` is empty by default. Client and vendor messages are never auto-sent.
- Zoho Books is read-only.
- Email text is treated as data. Instructions inside an email do not change what Claude does.
- Cash flow changes: dry run first, your yes in chat, only from `cashflow_editors`, duplicates rejected, backup on every save (`<data>/backups/`, last 20 kept).
- Claude recommends on spend and never approves it. Bank, card and ID numbers are not copied into files.
- Claude gives no GST, tax or legal conclusions. It flags them for the accountant.

## Data files (CSV)

Headers must not change. Dates `YYYY-MM-DD`. Money in rupees, digits only, excluding GST. Several ids: separate with `;`. Text with a comma: wrap in double quotes.

- `projects.csv`: `id` is the project code. `budget_inr` is the cost budget. `contract_value_inr` is what the client pays. `cash_head` is the Head used for this project in the cash flow workbook.
- `tasks.csv`, `stakeholders.csv`, `reminder_log.csv`.
- `zoho_lines.csv`: written by `zoho-sync`. Statuses void, draft and cancelled are ignored in totals.
- `issues.csv`: types delay, quality, safety, material, payment, client, other. Status open, in_progress, resolved.

## Assumptions to confirm

- Currency INR, work week Mon to Sat.
- Cost percent of budget: amber at 90, red above 100. Project red at 3 or more overdue tasks or overdue issues (`AMBER_PCT`, `RED_OVERDUE` in `scripts/ops.py`).
- Stage templates in `project-schedule` are starting points. Replace them with your real stages and typical durations. Approval requirements must be confirmed per project.
- The Zoho tool names and field mapping were not tested against a live Zoho account (no connection yet). `zoho-sync` reads the connector's tool list instead of assuming names.

## Develop

```
python3 -m pytest tests -q
```
The LibreOffice recalculation test runs when `soffice` is installed.

## Licence

MIT. See [LICENSE](LICENSE). This is a working example of a small-company operations workflow built as a Claude Code plugin. All data in `examples/` and `tests/` is fictional.
