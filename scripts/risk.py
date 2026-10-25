"""Early warnings, workload, documents, bids and huddle data for the ops-desk plugin (stdlib only).

Everything here is a rule over the CSV data, so the assistant reports numbers it did not make up.
Thresholds come from config.json; the defaults are below. Imported by ops.py, which owns the CLI.
"""
import os
from datetime import timedelta
from pathlib import Path

import ops
from ops import num, to_date

DEFAULTS = {
    "horizon_days": 30,               # show non-high warnings that land within this many days
    "document_warning_days": [60, 30, 7],  # low / medium / high when a document expires within these days
    "bid_warning_days": [30, 14, 7],  # low / medium / high when a bid with blockers closes within these days
    "client_update_days": 7,          # warn when an active project has had no client contact for this long
    "max_concurrent_tasks": 4,        # warn when one person has more open tasks than this on the same day
    "progress_gap_pct": [15, 30],     # medium / high when cost % of budget runs this far ahead of tasks done %
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
CONTACT_KINDS = {"update", "meeting", "payment_followup"}  # we reached the client (complaint and praise: they reached us)
OPEN_BID = {"identified", "preparing"}
TEAM_WINDOW_DAYS = 14


def setting(cfg, key):
    return cfg.get(key, DEFAULTS[key])


def inr(x):
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e7:
        return f"{sign}₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"{sign}₹{x / 1e5:.1f} L"
    return f"{sign}₹{x:,.0f}"


def _item(area, key, severity, title, detail, project_id="", days_until=None):
    return {
        "id": f"{area}:{key}", "area": area, "severity": severity, "project_id": project_id,
        "title": title, "detail": detail, "days_until": days_until,
    }


def _bucket(days, limits):
    """high / medium / low by how soon: limits sorted ascending, e.g. [7, 30, 60]."""
    for level, limit in zip(("high", "medium", "low"), sorted(limits)):
        if days <= limit:
            return level
    return None


def _active(data):
    return [p for p in data["projects"] if p["status"] == "active"]


def _begin(t):
    return to_date(t["start"]) or to_date(t["due"])


def _end(t, today):
    return max(to_date(t["due"]), today)  # an overdue task is still occupying its owner


# ---------- schedule ----------

def schedule_risks(data, today):
    out = []
    late = ops.overdue(data, today)
    tasks = ops.open_tasks(data)
    for p in _active(data):
        mine = [t for t in late if t["project_id"] == p["id"]]
        if mine:
            worst = mine[0]
            out.append(_item(
                "schedule", f"overdue:{p['id']}", "high" if len(mine) >= ops.RED_OVERDUE else "medium",
                f"{p['id']}: {len(mine)} task(s) overdue",
                f"Worst: {worst['id']} {worst['task']}, {worst['days_late']} days late, owner {worst['owner']}.",
                p["id"], 0))
        open_p = [t for t in tasks if t["project_id"] == p["id"]]
        if open_p and p["end"]:
            slip = (max(to_date(t["due"]) for t in open_p) - to_date(p["end"])).days
            if slip > 0:
                out.append(_item(
                    "schedule", f"overrun:{p['id']}", "high" if slip > 7 else "medium",
                    f"{p['id']}: plan finishes {slip} days after the project end date",
                    f"Project end {p['end']}. The last open task is due {slip} days later.",
                    p["id"], (to_date(p["end"]) - today).days))
    for t in tasks:
        if t["status"] != "blocked":
            continue
        waiting = [d for d in tasks if t["id"] in d["depends_on"].split(";")]
        if not waiting:
            continue
        nearest = min(waiting, key=lambda d: to_date(d["due"]))
        days = (to_date(nearest["due"]) - today).days
        out.append(_item(
            "schedule", f"blocked:{t['id']}", "high" if days <= 7 else "medium",
            f"{t['project_id']}: blocked {t['id']} holds up {nearest['id']}",
            f"{t['task']} is blocked ({t['notes'] or 'no reason recorded'}). {nearest['id']} {nearest['task']} is due {nearest['due']}.",
            t["project_id"], days))
    return out


# ---------- money ----------

def _oldest_overdue_days(data, pid, today, kind):
    ages = [
        (today - to_date(z["due"])).days
        for z in data["zoho_lines"]
        if z["project_id"] == pid and z["kind"] == kind and z["status"].lower() not in ops.IGNORED_STATUS
        and z["due"] and to_date(z["due"]) < today and num(z["amount_inr"]) > num(z["paid_inr"])
    ]
    return max(ages, default=0)


def cost_risks(data, today, cfg, money):
    medium_gap, high_gap = setting(cfg, "progress_gap_pct")
    out = []
    for p in _active(data):
        mine = [t for t in data["tasks"] if t["project_id"] == p["id"]]
        b = money[p["id"]]
        pct = b["pct_budget_used"]
        if pct is None or not mine:
            continue
        progress = round(sum(t["status"] == "done" for t in mine) / len(mine) * 100, 1)  # ponytail: tasks done, not effort
        gap = pct - progress
        if pct > 100:
            severity, title = "high", f"{p['id']}: cost is over budget"
        elif gap >= high_gap:
            severity, title = "high", f"{p['id']}: cost is running far ahead of progress"
        elif gap >= medium_gap:
            severity, title = "medium", f"{p['id']}: cost is running ahead of progress"
        else:
            continue
        out.append(_item(
            "cost", p["id"], severity, title,
            f"Cost and open POs are {pct}% of budget ({inr(b['cost_exposure_inr'])} of {inr(b['cost_budget_inr'])}) "
            f"while {progress}% of tasks are done.", p["id"]))
    return out


def money_risks(data, today, money):
    out = []
    for p in data["projects"]:
        if p["status"] in ("done", "cancelled"):
            continue
        b = money[p["id"]]
        govt = " Government client." if p["client_type"] == "govt" else ""
        if b["overdue_receivable_inr"] > 0:
            age = _oldest_overdue_days(data, p["id"], today, "invoice")
            out.append(_item(
                "receivable", f"overdue:{p['id']}", "high" if age > 30 else "medium",
                f"{p['id']}: client payment overdue",
                f"{inr(b['overdue_receivable_inr'])} overdue, oldest {age} days.{govt}", p["id"], 0))
        for z in data["zoho_lines"]:
            if (z["project_id"] == p["id"] and z["kind"] == "invoice" and z["status"].lower() not in ops.IGNORED_STATUS
                    and z["due"] and 0 <= (to_date(z["due"]) - today).days <= 7 and num(z["amount_inr"]) > num(z["paid_inr"])):
                out.append(_item(
                    "receivable", f"due-soon:{z['doc_no']}", "low", f"{p['id']}: invoice {z['doc_no']} due this week",
                    f"{inr(num(z['amount_inr']) - num(z['paid_inr']))} due {z['due']}. Follow up before the date.{govt}",
                    p["id"], (to_date(z["due"]) - today).days))
        if b["overdue_payable_inr"] > 0:
            out.append(_item(
                "payable", f"overdue:{p['id']}", "medium", f"{p['id']}: vendor bills overdue",
                f"{inr(b['overdue_payable_inr'])} overdue to vendors. Supply and goodwill are at risk.", p["id"], 0))
    return out


def cash_risks(cash, today):
    if not cash or cash["lowest_inr"] >= 0:
        return []
    days = (ops.to_date(cash["lowest_on"]) - today).days
    months = ", ".join(cash.get("shortfall_months", [])) or "none listed"
    return [_item(
        "cash", "shortfall", "high", f"Cash goes negative: lowest {inr(cash['lowest_inr'])} on {cash['lowest_on']}",
        f"Closing balance {inr(cash['closing_inr'])}. Months in shortfall: {months}.", "", days)]


# ---------- clients ----------

def client_risks(data, today, cfg):
    window = setting(cfg, "client_update_days")
    out = []
    for p in _active(data):
        logs = [c for c in data["client_log"] if c["project_id"] == p["id"]]
        contact = max((to_date(c["date"]) for c in logs if c["kind"] in CONTACT_KINDS), default=None)
        if contact is None or (today - contact).days > window:
            gap = "no client contact logged" if contact is None else f"no client contact for {(today - contact).days} days"
            out.append(_item("client", f"contact:{p['id']}", "medium", f"{p['id']}: {gap}",
                             f"Policy: contact every {window} days. Send a short status update.", p["id"], 0))
        complaint = max((to_date(c["date"]) for c in logs if c["kind"] == "complaint"), default=None)
        if complaint and (contact is None or contact < complaint):
            out.append(_item("client", f"complaint:{p['id']}", "high", f"{p['id']}: complaint with no reply logged",
                             f"Complaint on {complaint}. No update or meeting logged since.", p["id"], 0))
    for i in data["issues"]:
        if i["type"] == "client" and i["status"] != "resolved" and i["due"] and to_date(i["due"]) < today:
            out.append(_item("client", f"issue:{i['id']}", "high", f"{i['project_id']}: client issue {i['id']} overdue",
                             f"{i['description']} (owner {i['owner']}, due {i['due']}).", i["project_id"], 0))
    return out


# ---------- documents and bids ----------

def _doc_status(days_left, warn):
    if days_left is None:
        return "no expiry"
    if days_left < 0:
        return "expired"
    return "expiring" if days_left <= max(warn) else "valid"


def documents_view(data, today, cfg):
    warn = setting(cfg, "document_warning_days")
    rows = []
    for d in data["documents"]:
        left = (to_date(d["expiry"]) - today).days if d["expiry"] else None
        rows.append({
            "id": d["id"], "name": d["name"], "category": d["category"], "expiry": d["expiry"] or None,
            "days_left": left, "status": _doc_status(left, warn), "owner": d["owner"], "location": d["location"],
        })
    rows.sort(key=lambda r: (r["days_left"] is None, r["days_left"] if r["days_left"] is not None else 0))
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"as_of": today.isoformat(), "summary": counts, "documents": rows}


def document_risks(data, today, cfg):
    warn = setting(cfg, "document_warning_days")
    out = []
    for d in data["documents"]:
        if not d["expiry"]:
            continue
        left = (to_date(d["expiry"]) - today).days
        severity = "high" if left < 0 else _bucket(left, warn)
        if severity:
            when = f"expired {-left} days ago" if left < 0 else f"expires in {left} days"
            out.append(_item("document", d["id"], severity, f"{d['name']} {when}",
                             f"Expiry {d['expiry']}. Owner {d['owner'] or 'not set'}. Needed for bids and client audits.", "", left))
    return out


def _bid_blockers(data, bid, docs_by_id):
    rows = [r for r in data["bid_documents"] if r["bid_id"] == bid["id"] and r["status"] != "na"]
    if not rows:
        return ["No document checklist yet"]
    closing = to_date(bid["closing"])
    out = []
    for r in rows:
        if r["status"] in ("needed", "missing"):
            out.append(f"{r['doc_name']}: {r['status']}")
        doc = docs_by_id.get(r["doc_id"])
        if doc and doc["expiry"] and to_date(doc["expiry"]) < closing:
            out.append(f"{r['doc_name']}: document expires {doc['expiry']}, before the bid closes")
    return out


def bids_view(data, today):
    docs = {d["id"]: d for d in data["documents"]}
    out = []
    for b in data["bids"]:
        is_open = b["status"] in OPEN_BID
        blockers = _bid_blockers(data, b, docs) if is_open else []
        days = (to_date(b["closing"]) - today).days
        counts = {s: 0 for s in ("ready", "needed", "missing", "na")}
        for r in data["bid_documents"]:
            if r["bid_id"] == b["id"]:
                counts[r["status"]] += 1
        out.append({
            "id": b["id"], "portal": b["portal"], "bid_no": b["bid_no"], "title": b["title"], "buyer": b["buyer"],
            "closing": b["closing"], "days_to_close": days, "status": b["status"], "owner": b["owner"],
            "value_inr": num(b["value_inr"]), "security_inr": num(b["security_inr"]),
            "docs": counts, "blockers": blockers, "ready_to_submit": is_open and days >= 0 and not blockers,
        })
    out.sort(key=lambda r: (r["status"] not in OPEN_BID, r["days_to_close"]))
    return {"as_of": today.isoformat(), "bids": out}


def bid_risks(data, today, cfg):
    out = []
    for b in bids_view(data, today)["bids"]:
        if b["status"] not in OPEN_BID:
            continue
        days = b["days_to_close"]
        if days < 0:
            out.append(_item("bid", f"passed:{b['id']}", "medium", f"Bid {b['bid_no'] or b['id']}: closing date passed",
                             f"Closed {-days} days ago but status is still {b['status']}. Update it (submitted, no_bid or lost).",
                             "", days))
            continue
        severity = _bucket(days, setting(cfg, "bid_warning_days")) if b["blockers"] else None
        if severity:
            shown = "; ".join(b["blockers"][:3]) + (f"; and {len(b['blockers']) - 3} more" if len(b["blockers"]) > 3 else "")
            out.append(_item("bid", b["id"], severity,
                             f"Bid {b['bid_no'] or b['id']} closes in {days} days with {len(b['blockers'])} blocker(s)",
                             f"{b['title']} ({b['buyer']}). {shown}.", "", days))
    return out


# ---------- team ----------

def team_risks(data, today, cfg):
    limit = setting(cfg, "max_concurrent_tasks")
    window = [today + timedelta(days=i) for i in range(TEAM_WINDOW_DAYS)]
    tasks = ops.open_tasks(data)
    out = []
    for name in sorted({t["owner"] for t in tasks if t["owner"]}):
        mine = [t for t in tasks if t["owner"] == name]
        load = {d: sum(1 for t in mine if _begin(t) <= d <= _end(t, today)) for d in window}
        peak_day = max(window, key=lambda d: load[d])
        if load[peak_day] > limit:
            out.append(_item("team", f"load:{name}", "medium", f"{name} has {load[peak_day]} open tasks on {peak_day}",
                             f"More than {limit} at once. Reassign or re-sequence.", "", (peak_day - today).days))
    for lv in data["leave"]:
        start, end = to_date(lv["from"]), to_date(lv["to"])
        if end < today:
            continue
        for t in (t for t in tasks if t["owner"] == lv["name"]):
            if _begin(t) <= end and _end(t, today) >= start:
                days = max((start - today).days, 0)
                out.append(_item("team", f"leave:{lv['name']}:{t['id']}", "high" if days <= 7 else "medium",
                                 f"{lv['name']} is on leave while {t['id']} is due",
                                 f"Leave {lv['from']} to {lv['to']}. {t['task']} runs {t['start'] or t['due']} to {t['due']}.",
                                 t["project_id"], days))
    return out


def workload(data, today, days=14):
    window = [today + timedelta(days=i) for i in range(days)]
    tasks = ops.open_tasks(data)
    team = {r["name"]: r for r in data["team"]}
    people = []
    for name in sorted(set(team) | {t["owner"] for t in tasks if t["owner"]}):
        mine = [t for t in tasks if t["owner"] == name]
        load = {d: sum(1 for t in mine if _begin(t) <= d <= _end(t, today)) for d in window}
        peak_day = max(window, key=lambda d: load[d]) if window else None
        people.append({
            "name": name, "in_team_file": name in team, "role": team.get(name, {}).get("role", ""),
            "skills": [s for s in team.get(name, {}).get("skills", "").split(";") if s],
            "weekly_hours": num(team.get(name, {}).get("weekly_hours", "")),
            "open_tasks": len(mine), "tasks": [t["id"] for t in mine],
            "peak_concurrent": load[peak_day] if peak_day else 0, "peak_day": str(peak_day) if mine and peak_day else None,
            "on_leave": [
                {"from": lv["from"], "to": lv["to"], "reason": lv["reason"]} for lv in data["leave"]
                if lv["name"] == name and to_date(lv["to"]) >= today and to_date(lv["from"]) <= window[-1]
            ] if window else [],
        })
    return {"as_of": today.isoformat(), "days": days, "people": people}


# ---------- cash (optional) ----------

def cash_summary():
    """Cash headline from the workbook, or (None, why not). Needs openpyxl and a configured workbook."""
    path = os.environ.get("OPS_DESK_CASHFLOW_FILE") or ops.settings().get("cashflow_file")
    if not path:
        return None, "no cash flow workbook configured"
    try:
        import openpyxl

        import cashflow
    except ImportError:
        return None, "openpyxl is not installed"
    try:
        wb = openpyxl.load_workbook(Path(path).expanduser())
        errors, _ = cashflow.check_workbook(wb)
        if errors:
            return None, "workbook check failed: " + "; ".join(errors[:2])
        ws = wb[cashflow.SHEET]
        figures = cashflow.key_figures(ws)
        figures["shortfall_months"] = [m["month"] for m in cashflow.months(wb, ws) if m["shortfall"]]
        return figures, ""
    except (OSError, ValueError, KeyError, cashflow.CashflowError) as e:
        return None, f"could not read the workbook: {e}"


# ---------- put together ----------

def risks(data, today, cfg, cash=None):
    money = {x["project_id"]: x for x in ops.pnl(data, today, cfg)["projects"]}
    items = (
        schedule_risks(data, today) + cost_risks(data, today, cfg, money) + money_risks(data, today, money)
        + client_risks(data, today, cfg) + document_risks(data, today, cfg) + bid_risks(data, today, cfg)
        + team_risks(data, today, cfg) + cash_risks(cash, today)
    )
    horizon = setting(cfg, "horizon_days")
    shown = [i for i in items if i["severity"] == "high" or i["days_until"] is None or i["days_until"] <= horizon]
    shown.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], i["days_until"] if i["days_until"] is not None else 0, i["id"]))
    summary = {s: sum(1 for i in shown if i["severity"] == s) for s in SEVERITY_ORDER}
    return {
        "as_of": today.isoformat(), "horizon_days": horizon, "cash_checked": cash is not None,
        "summary": summary, "items": shown,
    }


def _task_view(t, today):
    return {"id": t["id"], "project_id": t["project_id"], "task": t["task"], "owner": t["owner"],
            "due": t["due"], "status": t["status"], "days_late": max((today - to_date(t["due"])).days, 0)}


def huddle(data, today, cfg, kind="daily", cash=None):
    tasks = ops.open_tasks(data)
    found = risks(data, today, cfg, cash)
    bids = [b for b in bids_view(data, today)["bids"] if b["status"] in OPEN_BID and 0 <= b["days_to_close"] <= 14]
    docs = [d for d in documents_view(data, today, cfg)["documents"] if d["days_left"] is not None and d["days_left"] <= 30]
    out = {
        "as_of": today.isoformat(), "kind": kind, "risk_summary": found["summary"],
        "top_risks": [i for i in found["items"] if i["severity"] == "high"][:5],
        "overdue": ops.overdue(data, today),
        "due_today": [_task_view(t, today) for t in tasks if to_date(t["due"]) == today],
        "due_next_2_days": [_task_view(t, today) for t in tasks if 0 < (to_date(t["due"]) - today).days <= 2],
        "blocked": [_task_view(t, today) for t in tasks if t["status"] == "blocked"],
        "issues_overdue": [i for i in ops.issues(data, today)["open"] if i["days_overdue"] > 0],
        "bids_closing_14_days": bids,
        "documents_expiring_30_days": docs,
        "clients_needing_contact": [i["project_id"] for i in found["items"] if i["id"].startswith("client:contact:")],
        "cash": cash,
    }
    if kind == "weekly":
        out["pnl_totals"] = ops.pnl(data, today, cfg)["totals"]
        out["week"] = ops.week(data, today)
        out["workload"] = workload(data, today)["people"]
    return out
