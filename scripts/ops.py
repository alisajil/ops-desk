#!/usr/bin/env python3
"""Deterministic ops numbers for the ops-desk plugin (stdlib only).

Data dir: $OPS_DESK_DATA, else "data_dir" in ~/.ops-desk.json, else ~/ops-desk-data (CSV files, see README).
Every command validates the data first and prints JSON, so the agent never
does date or money arithmetic itself.

`projects.csv` `id` is the project code, the same code used in Zoho Books.
`zoho_lines.csv` holds invoices, bills, expenses and open POs pulled from Zoho Books
(amounts excluding GST); `pnl` is computed from it.
"""
import argparse
import csv
import json
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

SCHEMA = {
    "projects": ["id", "name", "client", "site", "type", "status", "start", "end", "budget_inr", "contract_value_inr", "cash_head", "owner", "client_type"],
    "tasks": ["id", "project_id", "task", "owner", "start", "due", "status", "depends_on", "notes"],
    "stakeholders": ["name", "email", "role", "type", "projects", "notify"],
    "zoho_lines": ["project_id", "kind", "doc_no", "date", "due", "party", "category", "amount_inr", "paid_inr", "status", "zoho_id"],
    "issues": ["id", "project_id", "raised", "type", "description", "owner", "status", "due", "days_delay", "cost_impact_inr"],
    "reminder_log": ["date", "owner", "task_id"],
    "team": ["name", "role", "skills", "weekly_hours"],
    "leave": ["name", "from", "to", "reason"],
    "documents": ["id", "name", "category", "number", "issued", "expiry", "location", "owner"],
    "bids": ["id", "portal", "bid_no", "title", "buyer", "closing", "opening", "value_inr", "security_inr", "status", "owner", "notes"],
    "bid_documents": ["bid_id", "doc_name", "doc_id", "status", "owner", "due", "notes"],
    "client_log": ["date", "project_id", "kind", "note"],
    "project_submissions": ["project_id", "doc_name", "doc_id", "status", "due", "submitted_on", "submitted_to", "location", "owner", "notes"],
}
# a new install has none of these yet
OPTIONAL = {
    "zoho_lines", "issues", "reminder_log", "team", "leave", "documents", "bids", "bid_documents", "client_log",
    "project_submissions",
}
TASK_STATUS = {"todo", "doing", "blocked", "done"}
PROJECT_STATUS = {"planned", "active", "on_hold", "done", "cancelled"}
ISSUE_STATUS = {"open", "in_progress", "resolved"}
ISSUE_TYPES = {"delay", "quality", "safety", "material", "payment", "client", "other"}
ZOHO_KINDS = {"invoice", "bill", "expense", "po"}
CLIENT_TYPES = {"private", "govt"}  # blank counts as private
BID_STATUS = {"identified", "preparing", "submitted", "won", "lost", "no_bid"}
BID_DOC_STATUS = {"needed", "ready", "missing", "na"}
CLIENT_LOG_KINDS = {"update", "meeting", "complaint", "praise", "payment_followup"}
SUBMISSION_STATUS = {"needed", "ready", "submitted", "accepted", "rejected", "na"}
IGNORED_STATUS = {"void", "draft", "cancelled"}  # Zoho documents that do not count
DATE_FIELDS = {
    "projects": ["start", "end"], "tasks": ["start", "due"], "reminder_log": ["date"],
    "zoho_lines": ["date", "due"], "issues": ["raised", "due"], "leave": ["from", "to"],
    "documents": ["issued", "expiry"], "bids": ["closing", "opening"], "bid_documents": ["due"],
    "client_log": ["date"], "project_submissions": ["due", "submitted_on"],
}
NUM_FIELDS = {
    "projects": ["budget_inr", "contract_value_inr"], "zoho_lines": ["amount_inr", "paid_inr"],
    "issues": ["days_delay", "cost_impact_inr"], "team": ["weekly_hours"], "bids": ["value_inr", "security_inr"],
}
AMBER_PCT = 90  # ponytail: one global threshold, per-project column if needed
RED_OVERDUE = 3  # overdue tasks or issues that turn a project red; days late that trigger escalation


def settings():
    """Per-user pointers written by the setup skill: ~/.ops-desk.json (override: $OPS_DESK_SETTINGS)."""
    path = Path(os.environ.get("OPS_DESK_SETTINGS") or Path.home() / ".ops-desk.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"{path} is not valid JSON ({e}). Fix it or delete it and run the setup skill again.")


def claude_folder():
    """The OneDrive folder that holds data, company documents and project folders, or None if not set."""
    chosen = os.environ.get("OPS_DESK_FOLDER") or settings().get("claude_folder")
    return Path(chosen).expanduser() if chosen else None


def data_dir():
    folder = claude_folder()
    chosen = (
        os.environ.get("OPS_DESK_DATA") or settings().get("data_dir")
        or (folder / "data" if folder else None) or Path.home() / "ops-desk-data"
    )
    return Path(chosen).expanduser()


def config():
    path = data_dir() / "config.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def to_date(s):
    return date.fromisoformat(s) if s else None


def num(s):
    return float(s) if s else 0.0


def read(name):
    path = data_dir() / f"{name}.csv"
    if not path.exists():
        return ([], []) if name in OPTIONAL else ([], [f"{name}.csv: missing"])
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SCHEMA[name]:
            return [], [f"{name}.csv: header must be {','.join(SCHEMA[name])}"]
        raw = list(reader)
    errors = [
        f"{name}.csv row {i}: wrong column count (quote text that contains commas)"
        for i, r in enumerate(raw, start=2)
        if None in r or None in r.values()
    ]
    rows = [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in raw]
    return rows, errors


def _bad_values(data):
    errors = []
    for name, fields in DATE_FIELDS.items():
        for i, r in enumerate(data[name], start=2):
            for f in fields:
                try:
                    to_date(r[f])
                except ValueError:
                    errors.append(f"{name}.csv row {i}: bad {f} '{r[f]}' (use YYYY-MM-DD)")
    for name, fields in NUM_FIELDS.items():
        for i, r in enumerate(data[name], start=2):
            for f in fields:
                try:
                    num(r[f])
                except ValueError:
                    errors.append(f"{name}.csv row {i}: {f} '{r[f]}' is not a number (digits only, no commas or symbols)")
    return errors


def validate(data):
    errors = _bad_values(data)
    if errors:
        return errors
    pids = {r["id"] for r in data["projects"]}
    tids = {r["id"] for r in data["tasks"]}
    for name in ("projects", "tasks", "issues"):
        ids = [r["id"] for r in data[name]]
        for dup in sorted({x for x in ids if ids.count(x) > 1}):
            errors.append(f"{name}.csv: duplicate id {dup}")
    for i, r in enumerate(data["projects"], start=2):
        if not r["id"]:
            errors.append(f"projects.csv row {i}: project code (id) is required")
        if r["status"] not in PROJECT_STATUS:
            errors.append(f"projects.csv row {i}: status '{r['status']}' not in {sorted(PROJECT_STATUS)}")
    for i, r in enumerate(data["tasks"], start=2):
        if r["status"] not in TASK_STATUS:
            errors.append(f"tasks.csv row {i}: status '{r['status']}' not in {sorted(TASK_STATUS)}")
        if r["project_id"] not in pids:
            errors.append(f"tasks.csv row {i}: unknown project_id '{r['project_id']}'")
        if not r["due"]:
            errors.append(f"tasks.csv row {i}: due is required")
        elif r["start"] and r["start"] > r["due"]:
            errors.append(f"tasks.csv row {i}: start is after due")
        for dep in filter(None, r["depends_on"].split(";")):
            if dep not in tids:
                errors.append(f"tasks.csv row {i}: depends_on '{dep}' not found")
    for i, r in enumerate(data["zoho_lines"], start=2):
        if r["project_id"] not in pids:
            errors.append(f"zoho_lines.csv row {i}: unknown project code '{r['project_id']}'")
        if r["kind"] not in ZOHO_KINDS:
            errors.append(f"zoho_lines.csv row {i}: kind '{r['kind']}' not in {sorted(ZOHO_KINDS)}")
    for i, r in enumerate(data["issues"], start=2):
        if r["project_id"] not in pids:
            errors.append(f"issues.csv row {i}: unknown project code '{r['project_id']}'")
        if r["status"] not in ISSUE_STATUS:
            errors.append(f"issues.csv row {i}: status '{r['status']}' not in {sorted(ISSUE_STATUS)}")
        if r["type"] not in ISSUE_TYPES:
            errors.append(f"issues.csv row {i}: type '{r['type']}' not in {sorted(ISSUE_TYPES)}")
        if not r["raised"]:
            errors.append(f"issues.csv row {i}: raised date is required")
    for i, r in enumerate(data["reminder_log"], start=2):
        if r["task_id"] not in tids:
            errors.append(f"reminder_log.csv row {i}: unknown task_id '{r['task_id']}'")
    return errors + validate_planning(data, pids)


def validate_planning(data, pids):
    """Checks for the team, document, bid and client files."""
    errors = []
    for i, r in enumerate(data["projects"], start=2):
        if r["client_type"] and r["client_type"] not in CLIENT_TYPES:
            errors.append(f"projects.csv row {i}: client_type '{r['client_type']}' not in {sorted(CLIENT_TYPES)} (or blank)")
    names = {r["name"] for r in data["team"]}
    for i, r in enumerate(data["leave"], start=2):
        if r["name"] not in names:
            errors.append(f"leave.csv row {i}: '{r['name']}' is not in team.csv")
        if not r["from"] or not r["to"] or r["from"] > r["to"]:
            errors.append(f"leave.csv row {i}: needs from and to dates, from not after to")
    doc_ids = [r["id"] for r in data["documents"]]
    for dup in sorted({x for x in doc_ids if doc_ids.count(x) > 1}):
        errors.append(f"documents.csv: duplicate id {dup}")
    bid_ids = [r["id"] for r in data["bids"]]
    for dup in sorted({x for x in bid_ids if bid_ids.count(x) > 1}):
        errors.append(f"bids.csv: duplicate id {dup}")
    for i, r in enumerate(data["bids"], start=2):
        if r["status"] not in BID_STATUS:
            errors.append(f"bids.csv row {i}: status '{r['status']}' not in {sorted(BID_STATUS)}")
        if not r["closing"]:
            errors.append(f"bids.csv row {i}: closing date is required")
    for i, r in enumerate(data["bid_documents"], start=2):
        if r["bid_id"] not in bid_ids:
            errors.append(f"bid_documents.csv row {i}: unknown bid_id '{r['bid_id']}'")
        if r["status"] not in BID_DOC_STATUS:
            errors.append(f"bid_documents.csv row {i}: status '{r['status']}' not in {sorted(BID_DOC_STATUS)}")
        if r["doc_id"] and r["doc_id"] not in doc_ids:
            errors.append(f"bid_documents.csv row {i}: doc_id '{r['doc_id']}' not in documents.csv")
    for i, r in enumerate(data["project_submissions"], start=2):
        if r["project_id"] not in pids:
            errors.append(f"project_submissions.csv row {i}: unknown project code '{r['project_id']}'")
        if r["status"] not in SUBMISSION_STATUS:
            errors.append(f"project_submissions.csv row {i}: status '{r['status']}' not in {sorted(SUBMISSION_STATUS)}")
        if r["doc_id"] and r["doc_id"] not in doc_ids:
            errors.append(f"project_submissions.csv row {i}: doc_id '{r['doc_id']}' not in documents.csv")
        if r["status"] in ("submitted", "accepted") and not r["submitted_on"]:
            errors.append(f"project_submissions.csv row {i}: submitted_on is required once submitted")
    for i, r in enumerate(data["client_log"], start=2):
        if r["project_id"] not in pids:
            errors.append(f"client_log.csv row {i}: unknown project code '{r['project_id']}'")
        if r["kind"] not in CLIENT_LOG_KINDS:
            errors.append(f"client_log.csv row {i}: kind '{r['kind']}' not in {sorted(CLIENT_LOG_KINDS)}")
        if not r["date"]:
            errors.append(f"client_log.csv row {i}: date is required")
    return errors


def load_all():
    data, errors = {}, []
    for name in SCHEMA:
        data[name], errs = read(name)
        errors += errs
    return data, errors or validate(data)


def open_tasks(data):
    live = {p["id"] for p in data["projects"] if p["status"] not in ("done", "cancelled")}
    return [t for t in data["tasks"] if t["status"] != "done" and t["project_id"] in live]


def overdue(data, today):
    rows = [
        {
            "id": t["id"], "project_id": t["project_id"], "task": t["task"], "owner": t["owner"],
            "due": t["due"], "days_late": (today - to_date(t["due"])).days, "status": t["status"],
        }
        for t in open_tasks(data)
        if to_date(t["due"]) < today
    ]
    return sorted(rows, key=lambda x: -x["days_late"])


def week(data, start):
    end = start + timedelta(days=6)
    rows = []
    for t in open_tasks(data):
        due = to_date(t["due"])
        begin = to_date(t["start"]) or due
        if begin <= end and due >= start:
            rows.append((t, begin, due))
    rows.sort(key=lambda x: x[2])
    projects = {}
    for t, _, _ in rows:
        projects.setdefault(t["project_id"], []).append({k: t[k] for k in ("id", "task", "owner", "start", "due", "status")})
    clashes = [  # ponytail: O(n^2) pairwise scan, fine below a few hundred open tasks
        {"owner": a["owner"], "tasks": [a["id"], b["id"]]}
        for i, (a, sa, da) in enumerate(rows)
        for b, sb, db in rows[i + 1:]
        if a["owner"] and a["owner"] == b["owner"] and sa <= db and sb <= da
    ]
    return {"from": start.isoformat(), "to": end.isoformat(), "projects": projects, "clashes": clashes}


def _counted(lines, kind):
    return [z for z in lines if z["kind"] == kind and z["status"].lower() not in IGNORED_STATUS]


def _outstanding_late(rows, today):
    return sum(
        num(z["amount_inr"]) - num(z["paid_inr"])
        for z in rows
        if z["due"] and to_date(z["due"]) < today and num(z["amount_inr"]) > num(z["paid_inr"])
    )


def _sum(rows, field="amount_inr"):
    return sum(num(z[field]) for z in rows)


def pnl(data, today, cfg):
    site_cats = {c.lower() for c in cfg.get("site_expense_categories", [])}
    out = []
    for p in data["projects"]:
        lines = [z for z in data["zoho_lines"] if z["project_id"] == p["id"]]
        invoices, bills, expenses = _counted(lines, "invoice"), _counted(lines, "bill"), _counted(lines, "expense")
        open_pos = [z for z in _counted(lines, "po") if z["status"].lower() == "open"]
        by_cat = {}
        for z in expenses:
            key = z["category"] or "(none)"
            by_cat[key] = by_cat.get(key, 0.0) + num(z["amount_inr"])
        billed, received = _sum(invoices), _sum(invoices, "paid_inr")
        cost = _sum(bills) + _sum(expenses)
        committed = _sum(open_pos)
        budget_inr, contract = num(p["budget_inr"]), num(p["contract_value_inr"])
        exposure = cost + committed
        pct = round(exposure / budget_inr * 100, 1) if budget_inr else None
        level = "ok"
        if pct is not None:
            level = "red" if pct > 100 else "amber" if pct >= AMBER_PCT else "ok"
        out.append({
            "project_id": p["id"], "name": p["name"],
            "contract_value_inr": contract, "cost_budget_inr": budget_inr,
            "planned_margin_pct": round((contract - budget_inr) / contract * 100, 1) if contract else None,
            "revenue_billed_inr": billed, "revenue_received_inr": received,
            "receivable_inr": billed - received, "overdue_receivable_inr": _outstanding_late(invoices, today),
            "bills_inr": _sum(bills), "bills_paid_inr": _sum(bills, "paid_inr"),
            "payable_inr": _sum(bills) - _sum(bills, "paid_inr"), "overdue_payable_inr": _outstanding_late(bills, today),
            "expenses_inr": _sum(expenses), "expenses_by_category": dict(sorted(by_cat.items())),
            "site_expenses_inr": sum(v for k, v in by_cat.items() if k.lower() in site_cats),
            "committed_po_inr": committed, "cost_to_date_inr": cost, "cost_exposure_inr": exposure,
            "profit_inr": billed - cost, "margin_pct": round((billed - cost) / billed * 100, 1) if billed else None,
            "cash_profit_inr": received - _sum(bills, "paid_inr") - _sum(expenses),
            "pct_budget_used": pct, "level": level,
        })
    keys = ("revenue_billed_inr", "revenue_received_inr", "receivable_inr", "overdue_receivable_inr", "payable_inr",
            "overdue_payable_inr", "cost_to_date_inr", "profit_inr", "site_expenses_inr")
    return {
        "as_of": today.isoformat(), "site_categories_configured": bool(site_cats),
        "projects": out, "totals": {k: round(sum(x[k] for x in out), 2) for k in keys},
    }


def issues(data, today):
    per = {}
    for p in data["projects"]:
        mine = [i for i in data["issues"] if i["project_id"] == p["id"]]
        open_ = [i for i in mine if i["status"] != "resolved"]
        late = [i for i in open_ if i["due"] and to_date(i["due"]) < today]
        per[p["id"]] = {
            "open": len(open_), "overdue": len(late),
            "delay_days_open": sum(num(i["days_delay"]) for i in open_),
            "cost_impact_inr": sum(num(i["cost_impact_inr"]) for i in mine),
            "cost_impact_open_inr": sum(num(i["cost_impact_inr"]) for i in open_),
        }
    rows = [
        {
            "id": i["id"], "project_id": i["project_id"], "type": i["type"], "description": i["description"],
            "owner": i["owner"], "status": i["status"], "due": i["due"],
            "age_days": (today - to_date(i["raised"])).days,
            "days_overdue": max((today - to_date(i["due"])).days, 0) if i["due"] else 0,
            "days_delay": num(i["days_delay"]), "cost_impact_inr": num(i["cost_impact_inr"]),
        }
        for i in data["issues"]
        if i["status"] != "resolved"
    ]
    rows.sort(key=lambda x: (-x["days_overdue"], -x["age_days"]))
    return {"as_of": today.isoformat(), "open": rows, "by_project": per}


def reminders(data, today, days, resend_after):
    last = {}
    for r in data["reminder_log"]:
        d = to_date(r["date"])
        if d > last.get(r["task_id"], date.min):
            last[r["task_id"]] = d
    people = {s["name"].lower(): s for s in data["stakeholders"]}
    horizon = today + timedelta(days=days)
    by_owner, escalate = {}, []
    for t in open_tasks(data):
        due = to_date(t["due"])
        late = (today - due).days
        item = {"id": t["id"], "project_id": t["project_id"], "task": t["task"], "due": t["due"], "days_late": late}
        if late >= RED_OVERDUE and t["id"] in last:
            escalate.append({**item, "owner": t["owner"], "last_reminded": last[t["id"]].isoformat()})
        if due > horizon:
            continue
        if t["id"] in last and (today - last[t["id"]]).days < resend_after:
            continue
        by_owner.setdefault(t["owner"], []).append(item)
    owners, unmatched = [], []
    for name, tasks in sorted(by_owner.items()):
        s = people.get(name.lower())
        if s:
            owners.append({"owner": name, "email": s["email"], "type": s["type"], "tasks": tasks})
        else:
            unmatched.append({"owner": name, "tasks": tasks})
    return {"as_of": today.isoformat(), "owners": owners, "unmatched_owners": unmatched, "escalate_to_management": escalate}


def mark_reminded(data, owner, task_ids, today):
    known = {t["id"] for t in data["tasks"]}
    bad = [t for t in task_ids if t not in known]
    if bad:
        return {"ok": False, "errors": [f"unknown task ids: {','.join(bad)}"]}
    path = data_dir() / "reminder_log.csv"
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if fresh:
            w.writerow(SCHEMA["reminder_log"])
        for tid in task_ids:
            w.writerow([today.isoformat(), owner, tid])
    return {"ok": True, "logged": len(task_ids)}


def report(data, today, cfg):
    money = {x["project_id"]: x for x in pnl(data, today, cfg)["projects"]}
    iss = issues(data, today)
    late = overdue(data, today)
    open_ = open_tasks(data)
    projects = []
    for p in data["projects"]:
        if p["status"] in ("done", "cancelled"):
            continue
        mine_late = [t for t in late if t["project_id"] == p["id"]]
        blocked = [t for t in open_ if t["project_id"] == p["id"] and t["status"] == "blocked"]
        b, i = money[p["id"]], iss["by_project"][p["id"]]
        red, amber = [], []
        if b["level"] == "red":
            red.append(f"cost {b['pct_budget_used']}% of budget")
        if len(mine_late) >= RED_OVERDUE:
            red.append(f"{len(mine_late)} tasks overdue")
        if i["overdue"] >= RED_OVERDUE:
            red.append(f"{i['overdue']} issues overdue")
        if p["end"] and to_date(p["end"]) < today:
            red.append("past project end date")
        if b["level"] == "amber":
            amber.append(f"cost {b['pct_budget_used']}% of budget")
        if mine_late and len(mine_late) < RED_OVERDUE:
            amber.append(f"{len(mine_late)} task(s) overdue")
        if 0 < i["overdue"] < RED_OVERDUE:
            amber.append(f"{i['overdue']} issue(s) overdue")
        if blocked:
            amber.append(f"{len(blocked)} task(s) blocked")
        if b["overdue_receivable_inr"] > 0:
            amber.append("client payment overdue")
        upcoming = sorted(t["due"] for t in open_ if t["project_id"] == p["id"] and to_date(t["due"]) >= today)
        projects.append({
            "id": p["id"], "name": p["name"], "owner": p["owner"], "status": p["status"], "end": p["end"],
            "rag": "red" if red else "amber" if amber else "green", "reasons": red + amber,
            "overdue": mine_late, "blocked": blocked, "pnl": b, "issues": i,
            "open_issues": [x for x in iss["open"] if x["project_id"] == p["id"]],
            "next_due": upcoming[0] if upcoming else None,
        })
    return {"as_of": today.isoformat(), "projects": projects, "week": week(data, today)}


EMPTY_CONFIG = {
    "management_recipients": [], "cashflow_editors": [], "site_expense_categories": [], "auto_send": [],
    "currency": "INR", "timezone": "Asia/Kolkata", "work_week": "Mon-Sat",
}


def init(target, cashflow_file, with_examples, claude=None):
    """First-time setup: data folder with header-only CSVs (or the fictional examples), the Claude folder layout, ~/.ops-desk.json."""
    target = Path(target).expanduser().resolve()
    if cashflow_file and not Path(cashflow_file).expanduser().exists():
        return {"ok": False, "errors": [f"cashflow file not found: {cashflow_file}"]}
    target.mkdir(parents=True, exist_ok=True)
    created = []
    root = None
    if claude:
        import vault  # late import: vault.py imports this module

        root = Path(claude).expanduser().resolve()
        created += [f"folder:{p}" for p in vault.ensure_structure(root)]
    examples = Path(__file__).resolve().parent.parent / "examples" / "data"
    if with_examples:
        for src in examples.iterdir():
            if src.is_file() and not src.name.startswith(".") and not (target / src.name).exists():
                shutil.copy2(src, target / src.name)
                created.append(src.name)
    else:
        for name, cols in SCHEMA.items():
            if not (target / f"{name}.csv").exists():
                (target / f"{name}.csv").write_text(",".join(cols) + "\n", encoding="utf-8")
                created.append(f"{name}.csv")
        if not (target / "config.json").exists():
            (target / "config.json").write_text(json.dumps(EMPTY_CONFIG, indent=2) + "\n", encoding="utf-8")
            created.append("config.json")
    path = Path(os.environ.get("OPS_DESK_SETTINGS") or Path.home() / ".ops-desk.json")
    merged = {**settings(), "data_dir": str(target)}
    if root:
        merged["claude_folder"] = str(root)
    if cashflow_file:
        merged["cashflow_file"] = str(Path(cashflow_file).expanduser().resolve())
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "data_dir": str(target), "created": created, "settings_file": str(path), "settings": merged}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--today", help="override today, YYYY-MM-DD (for tests)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "overdue", "pnl", "issues", "report"):
        sub.add_parser(name)
    sub.add_parser("week").add_argument("--start", help="first day of the 7-day window, default today")
    sub.add_parser("documents", help="company document register with expiry status")
    sub.add_parser("submissions", help="per-project submissions with blockers")
    sub.add_parser("folders", help="create project and bid folders in the Claude folder").add_argument(
        "--check", dest="check_only", action="store_true", help="report only, create nothing")
    sub.add_parser("bids", help="bid list with document readiness")
    sub.add_parser("workload").add_argument("--days", type=int, default=14, help="look-ahead window")
    sub.add_parser("risks", help="early warnings for the next weeks").add_argument(
        "--no-cash", action="store_true", help="skip the cash flow workbook")
    h = sub.add_parser("huddle", help="agenda data for the daily or weekly operations huddle")
    h.add_argument("--kind", choices=["daily", "weekly"], default="daily")
    h.add_argument("--no-cash", action="store_true", help="skip the cash flow workbook")
    r = sub.add_parser("reminders")
    r.add_argument("--days", type=int, default=2, help="include tasks due within N days")
    r.add_argument("--resend-after", type=int, default=2, help="skip tasks reminded in the last N days")
    m = sub.add_parser("mark-reminded")
    m.add_argument("--owner", required=True)
    m.add_argument("--tasks", required=True, help="comma-separated task ids")
    sub.add_parser("where", help="print the data folder and cash flow workbook paths in use")
    i = sub.add_parser("init", help="first-time setup of the data folder and ~/.ops-desk.json")
    i.add_argument("--data-dir", help="default: the current data dir (~/ops-desk-data)")
    i.add_argument("--cashflow-file", help="path to the synced cash flow workbook")
    i.add_argument("--claude-folder", help="the OneDrive folder for data, company documents and project folders")
    i.add_argument("--with-examples", action="store_true", help="copy the fictional sample data instead of empty templates")
    a = ap.parse_args(argv)

    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.cmd == "where":
        settings_path = Path(os.environ.get("OPS_DESK_SETTINGS") or Path.home() / ".ops-desk.json")
        print(json.dumps({
            "data_dir": str(data_dir()), "data_dir_exists": data_dir().exists(),
            "cashflow_file": os.environ.get("OPS_DESK_CASHFLOW_FILE") or settings().get("cashflow_file"),
            "claude_folder": str(claude_folder()) if claude_folder() else None,
            "settings_file": str(settings_path), "settings_file_exists": settings_path.exists(),
        }, indent=2))
        return 0
    if a.cmd == "init":
        target = a.data_dir or (Path(a.claude_folder).expanduser() / "data" if a.claude_folder else data_dir())
        out = init(target, a.cashflow_file, a.with_examples, a.claude_folder)
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1
    data, errors = load_all()
    if a.cmd == "check" or errors:
        counts = {k: len(v) for k, v in data.items()}
        print(json.dumps({"ok": not errors, "errors": errors, "rows": counts}, indent=2))
        return 1 if errors else 0
    cfg = config()
    import risk  # late imports: these modules import this one
    import vault

    cash, cash_note = (None, "skipped") if getattr(a, "no_cash", True) else risk.cash_summary()
    commands = {
        "documents": lambda: risk.documents_view(data, today, cfg),
        "submissions": lambda: risk.submissions_view(data, today, cfg),
        "folders": lambda: vault.sync(data, a.check_only),
        "bids": lambda: risk.bids_view(data, today),
        "workload": lambda: risk.workload(data, today, a.days),
        "risks": lambda: {**risk.risks(data, today, cfg, cash), "cash_note": cash_note},
        "huddle": lambda: {**risk.huddle(data, today, cfg, a.kind, cash), "cash_note": cash_note},
        "overdue": lambda: overdue(data, today),
        "week": lambda: week(data, date.fromisoformat(a.start) if a.start else today),
        "pnl": lambda: pnl(data, today, cfg),
        "issues": lambda: issues(data, today),
        "reminders": lambda: reminders(data, today, a.days, a.resend_after),
        "mark-reminded": lambda: mark_reminded(data, a.owner, [t for t in a.tasks.split(",") if t], today),
        "report": lambda: report(data, today, cfg),
    }
    out = commands[a.cmd]()
    print(json.dumps(out, indent=2))
    return 0 if not isinstance(out, dict) or out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
