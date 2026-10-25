---
name: client-care
description: Keep clients happy: log every client contact, send regular status updates, answer complaints fast, chase payments politely, and spot unhappy signals early. Use for "update the client", "log this complaint", "which clients have we not spoken to", "draft a client update", "client payment follow-up".
---

# Client care

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Drafts only: nothing goes to a client without a yes in chat. Log changes in `<data>/log.md`.

## The contact log (`client_log.csv`)
`date`, `project_id` (project code), `kind`, `note` (one line, no private figures).
- `update`, `meeting`, `payment_followup`: we reached the client. These reset the contact clock.
- `complaint`, `praise`: the client reached us. A complaint stays open until an update or meeting is logged after it.

## Rhythm
- Every active project gets a contact at least every `client_update_days` (default 7, set in `config.json`). `ops.py risks` warns when a project goes past that.
- Government clients may have their own reporting duties in the order. Follow the order and ask the user for the cadence. Do not assume one.

## Draft a status update
1. Pull the facts: tasks done and next milestone (`ops.py report`), open issues for this project, anything we need from the client (approvals, access, payment).
2. Write a short message: where we are, what happens next and when, what we need from them and by when. Plain words, no internal margins, costs or blame.
3. Do not promise a date, price or credit that management has not approved. Use dates from the schedule and say "planned".
4. Show the draft. After the user sends it (or says to use it), add an `update` row to `client_log.csv`.

## Complaints
1. Log a `complaint` row with the date and what the client said. Open an issue of type client in `issues.csv` with an owner and a due date (the `issue-tracker` skill).
2. Draft an acknowledgement for the same day: we heard you, who owns it, when you will hear back. Management approves anything that admits fault, offers a credit or changes a date.
3. Find the cause with the project owner. Propose a fix and a date. Draft the reply and wait for a yes.
4. After the reply, log an `update` row. That clears the warning. Close the issue only when the client confirms or the user says so.
5. Tell management about any complaint the same day, with the project code and the owner.

## Payments
Overdue client payment (`ops.py pnl`, `overdue_receivable_inr`): draft a polite reminder with the invoice number, amount excluding GST, and the due date. Offer a call. Log a `payment_followup` row after it is sent. If an invoice is more than 30 days overdue, raise it to management with a suggested next step.

## Signals of an unhappy client
No reply for two reminders, a complaint without a follow-up, repeated change requests after sign-off, a delay that has not been explained, a late payment from a client that used to pay on time. Report these in the huddle as risks, with the evidence.

## Never
Share another client's information, discuss internal costs or margins with a client, or send anything on the user's behalf without a yes.
