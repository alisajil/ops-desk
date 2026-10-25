---
name: company-documents
description: Keep a register of company documents (registrations, tax, quality, financial, experience, authorisations, insurance) with expiry dates and file locations, warn before they expire, and assemble the document list for a bid or client audit. Use for "add this certificate", "what is expiring", "what documents do we have", "prepare the document pack".
---

# Company documents

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Drafts only. Log changes in `<data>/log.md`.

## The register (`documents.csv`)
`id` (D001, continue from the highest), `name`, `category`, `number` (the certificate or registration number), `issued`, `expiry` (blank when the document does not expire), `location` (the path relative to the Claude folder, for example `Company/tax/tax-registration.pdf`), `owner` (who renews it).

Suggested categories: registration, tax, quality, financial, experience, authorisation, insurance, bank, technical, policy, people.

## Add a document
1. The user gives a file or its path. Read it. Extract the name, number, issue date and expiry date. Show what you found and where you found it. Write the row only after the user confirms. If a date is unclear, ask. Never guess an expiry.
2. Set `location` to where the file lives, relative to the Claude folder. Files belong in `Company/<category>/`. If the file is elsewhere, tell the user and suggest moving it. Do not move, rename or delete files yourself. `ops.py folders --check` and `ops.py documents` report files that are not where the register says.
3. `ops.py check`.

## Watch expiry
- `ops.py documents` lists everything by days left with status: expired, expiring, valid, no expiry.
- Warnings fire at 60 days (low), 30 (medium) and 7 (high), and for anything expired. Set the days in `config.json` `document_warning_days`.
- At 60 days, propose a renewal task for the owner with a due date 30 days before expiry. Add it to `tasks.csv` after a yes.
- A document that expires before a bid closes blocks that bid (`gem-bids`).

## Prepare a document pack
For a bid, client audit or tender:
1. List what is asked. Take it from the bid document or the client's request, not from memory.
2. Match each item to a register row. Report: found and valid, found but expiring or expired, not in the register.
3. Give the user a list of file locations to attach. You do not attach or upload. For a project's documents use `project-submissions`.
4. For documents not in the register, ask who holds them and by when.

## Care with sensitive data
- Registration, tax and bank numbers stay in the register in the data folder. In any message, show only the last four characters.
- Do not paste a document's full contents into chat or drafts. Quote only the fields you need.
- Never put the register or the files in a public place.
