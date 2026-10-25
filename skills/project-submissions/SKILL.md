---
name: project-submissions
description: Track the documents each project must submit (statutory and company documents, plus project-specific submissions such as safety plans, test reports and drawings), keep their files in the project's folder in the Claude folder, and warn before a submission is due, blocked or rejected. Use for "what must we submit for this project", "prepare the submission pack", "we submitted X to the client", "which submissions are overdue".
---

# Project submissions

Every project has documents that must go to the client or an authority: company and statutory documents, and documents made for this project. This skill makes sure none is late, expired or missing.

## Conventions
Data folder (`ops.py where` prints its path; `<data>` means that folder), script `ops.py` under `${CLAUDE_PLUGIN_ROOT}/scripts/` (fallback: `find ~/.claude/plugins -path '*ops-desk*/scripts/ops.py'`). Run `ops.py check` first and after edits. Drafts only. Log changes in `<data>/log.md`.

## Where files live (the Claude folder)
- Company and statutory documents: `Company/<category>/` (registered in `documents.csv`).
- Per project: `Projects/<code>-<name>/` with `Submissions/` (what we send or have sent), `Documents/` (orders, contracts, approvals, drawings received), `Site/` (reports, photos), `Commercial/` (quotes, invoice copies).
- `location` columns hold paths relative to the Claude folder, for example `Projects/PRJ-001-warehouse-sprinkler-retrofit/Submissions/safety-plan.pdf`.
- `ops.py folders` creates any missing project and bid folders and reports missing files and unknown folders. Run it whenever a project is added. `ops.py folders --check` only reports.

## The checklist (`project_submissions.csv`)
`project_id` (project code), `doc_name`, `doc_id` (links a company document in `documents.csv`, blank for project-specific), `status` (needed, ready, submitted, accepted, rejected, na), `due`, `submitted_on`, `submitted_to`, `location`, `owner`, `notes`.

## Build the checklist for a new project
1. Get the list from the order, contract, tender document or client request. Read it. **Do not assume which statutory documents a client or authority wants.** If the requirement is not written down, ask the user or the client contact.
2. For each required item add a row. Link `doc_id` when the document is in the register. If a company document is not in the register, add it with the `company-documents` skill first.
3. Set `due` from the order's terms, and an internal due date a few working days earlier. Set an owner for each row.
4. Show the table and wait for a yes before writing. Then run `ops.py check` and `ops.py folders`.

## Work the list
- `ops.py submissions` shows each row with days left, file found or not, and blockers: a linked document that expires before the due date, or whose file is not where the register says.
- `ops.py risks` raises warnings: overdue (high), needed within 3 days (high), within 7 (medium), within 14 (low), a ready item to send within 3 days (low), a rejected item (high).
- When a document is ready, save the file in the project's `Submissions/` folder (or link the company document), set `location`, and set the status to ready. Do not copy company documents into project folders. Link them from `Company/`.
- When the user says it was sent: set `submitted`, `submitted_on` and `submitted_to`. Move to `accepted` when the client confirms. If it is rejected, record the reason in `notes`, set `rejected`, and raise it in the huddle.

## Prepare a pack
List the files to attach: for each needed row, the file path, its expiry and its status. Say what is missing and who owns it. You do not attach or send. The user does.

## Save files from email
When a mail has an attachment that belongs in a project, say where you would save it and ask first. Save only after a yes. Never overwrite an existing file. Use the name `<date>-<short name>.<ext>`.

## Never
Invent a statutory requirement, claim a document is valid without its expiry date, or send a submission without the user's yes.
