import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ops  # noqa: E402
import risk  # noqa: E402

TODAY = "2026-10-26"  # a Monday
TODAY_D = date.fromisoformat(TODAY)


@pytest.fixture
def data(tmp_path, monkeypatch):
    dst = tmp_path / "data"
    shutil.copytree(ROOT / "examples" / "data", dst)
    monkeypatch.setenv("OPS_DESK_DATA", str(dst))
    monkeypatch.setenv("OPS_DESK_SETTINGS", str(tmp_path / "no-settings.json"))
    monkeypatch.delenv("OPS_DESK_CASHFLOW_FILE", raising=False)
    return dst


def run(capsys, *args):
    code = ops.main(["--today", TODAY, *args])
    return code, json.loads(capsys.readouterr().out)


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def loaded():
    rows, errors = ops.load_all()
    assert not errors
    return rows, ops.config()


def ids(items):
    return {i["id"]: i["severity"] for i in items}


def test_risks_report_the_expected_warnings_with_severity(data, capsys):
    code, out = run(capsys, "risks", "--no-cash")
    assert code == 0 and out["summary"] == {"high": 7, "medium": 7, "low": 1}
    found = ids(out["items"])
    assert found["cost:PRJ-001"] == "high" and found["cost:PRJ-002"] == "high"
    assert found["client:complaint:PRJ-002"] == "high" and found["client:contact:PRJ-002"] == "medium"
    assert found["document:D007"] == "high" and found["document:D004"] == "high" and found["document:D003"] == "medium"
    assert found["bid:B001"] == "high" and found["bid:B002"] == "low" and found["bid:passed:B003"] == "medium"
    assert found["team:leave:Ravi:T005"] == "high"
    assert found["schedule:blocked:T008"] == "medium" and found["receivable:overdue:PRJ-001"] == "medium"


def test_risks_are_sorted_high_first_then_soonest(data, capsys):
    _, out = run(capsys, "risks", "--no-cash")
    order = [risk.SEVERITY_ORDER[i["severity"]] for i in out["items"]]
    assert order == sorted(order)
    high_days = [i["days_until"] if i["days_until"] is not None else 0 for i in out["items"] if i["severity"] == "high"]
    assert high_days == sorted(high_days)


def test_low_warnings_beyond_the_horizon_are_hidden(data, capsys):
    _, out = run(capsys, "risks", "--no-cash")
    assert "document:D006" not in ids(out["items"])  # expires in 55 days, low, outside the 30 day horizon


def test_cash_shortfall_is_a_high_warning_even_far_out(data):
    rows, cfg = loaded()
    cash = {"lowest_inr": -9600000.0, "lowest_on": "2026-12-30", "closing_inr": -8000000.0,
            "shortfall_months": ["Nov 2026", "Dec 2026"]}
    out = risk.risks(rows, TODAY_D, cfg, cash)
    item = next(i for i in out["items"] if i["id"] == "cash:shortfall")
    assert item["severity"] == "high" and item["days_until"] == 65 and "Nov 2026" in item["detail"]
    assert out["cash_checked"] is True
    assert "cash:shortfall" not in ids(risk.risks(rows, TODAY_D, cfg, {**cash, "lowest_inr": 10.0})["items"])


def test_without_a_workbook_the_cash_check_is_skipped_with_a_reason(data, capsys):
    _, out = run(capsys, "risks")
    assert out["cash_checked"] is False and out["cash_note"] == "no cash flow workbook configured"


def test_client_contact_window_comes_from_config(data, capsys):
    edit(data / "config.json", '"client_update_days": 7', '"client_update_days": 30')
    _, out = run(capsys, "risks", "--no-cash")
    found = ids(out["items"])
    assert "client:contact:PRJ-002" not in found and "client:complaint:PRJ-002" in found


def test_a_later_update_clears_a_complaint(data, capsys):
    with (data / "client_log.csv").open("a", encoding="utf-8") as f:
        f.write("2026-10-25,PRJ-002,update,Call held and new delivery date agreed\n")
    _, out = run(capsys, "risks", "--no-cash")
    found = ids(out["items"])
    assert "client:complaint:PRJ-002" not in found and "client:contact:PRJ-002" not in found


def test_team_overload_flagged_when_the_limit_is_low(data, capsys):
    edit(data / "config.json", '"max_concurrent_tasks": 4', '"max_concurrent_tasks": 1')
    _, out = run(capsys, "risks", "--no-cash")
    assert ids(out["items"])["team:load:Anil"] == "medium"


def test_documents_view_sorted_by_expiry_with_status(data, capsys):
    _, out = run(capsys, "documents")
    assert [(d["id"], d["status"]) for d in out["documents"]][:4] == [
        ("D007", "expired"), ("D004", "expiring"), ("D003", "expiring"), ("D006", "expiring")]
    assert out["summary"] == {"expired": 1, "expiring": 3, "no expiry": 3}


def test_bid_blockers_include_documents_that_expire_before_closing(data, capsys):
    _, out = run(capsys, "bids")
    by_id = {b["id"]: b for b in out["bids"]}
    assert by_id["B001"]["ready_to_submit"] is False and by_id["B001"]["days_to_close"] == 7
    assert any("expires 2026-10-31, before the bid closes" in b for b in by_id["B001"]["blockers"])
    assert by_id["B004"]["blockers"] == [] and by_id["B004"]["ready_to_submit"] is False  # already submitted


def test_a_bid_with_a_complete_valid_checklist_is_ready_and_quiet(data, capsys):
    edit(data / "documents.csv", "2026-10-31", "2027-01-31")
    edit(data / "bid_documents.csv", "B001,Technical compliance sheet,,missing", "B001,Technical compliance sheet,,ready")
    edit(data / "bid_documents.csv", "B001,Price schedule,,needed", "B001,Price schedule,,ready")
    _, out = run(capsys, "bids")
    assert next(b for b in out["bids"] if b["id"] == "B001")["ready_to_submit"] is True
    _, out = run(capsys, "risks", "--no-cash")
    assert "bid:B001" not in ids(out["items"])


def test_a_bid_without_any_checklist_is_blocked(data, capsys):
    (data / "bid_documents.csv").write_text("bid_id,doc_name,doc_id,status,owner,due,notes\n")
    _, out = run(capsys, "bids")
    assert next(b for b in out["bids"] if b["id"] == "B001")["blockers"] == ["No document checklist yet"]


def test_workload_shows_leave_and_owners_missing_from_the_team_file(data, capsys):
    edit(data / "tasks.csv", "T010,PRJ-003,Receive cylinders and inspect,Anil", "T010,PRJ-003,Receive cylinders and inspect,Zed")
    _, out = run(capsys, "workload")
    people = {p["name"]: p for p in out["people"]}
    assert people["Ravi"]["on_leave"] == [{"from": "2026-11-02", "to": "2026-11-06", "reason": "Annual leave"}]
    assert people["Zed"]["in_team_file"] is False and people["Zed"]["tasks"] == ["T010"]
    assert people["Priya"]["open_tasks"] == 0 and people["Anil"]["skills"] == ["fabrication", "hydraulics"]


def test_daily_huddle_lists_what_needs_attention_today(data, capsys):
    _, out = run(capsys, "huddle", "--no-cash")
    assert out["kind"] == "daily" and "pnl_totals" not in out
    assert [t["id"] for t in out["overdue"]] == ["T003", "T007"]
    assert [t["id"] for t in out["blocked"]] == ["T008"]
    assert len(out["top_risks"]) <= 5 and all(r["severity"] == "high" for r in out["top_risks"])
    assert [b["id"] for b in out["bids_closing_14_days"]] == ["B001"]
    assert {d["id"] for d in out["documents_expiring_30_days"]} == {"D007", "D004", "D003"}
    assert out["clients_needing_contact"] == ["PRJ-002"]
    assert [i["id"] for i in out["issues_overdue"]] == ["I001"]


def test_weekly_huddle_adds_money_week_and_workload(data, capsys):
    _, out = run(capsys, "huddle", "--kind", "weekly", "--no-cash")
    assert out["pnl_totals"]["revenue_billed_inr"] == 2350000
    assert "projects" in out["week"] and {p["name"] for p in out["workload"]} >= {"Ravi", "Anil", "Priya"}


def test_new_files_are_validated(data, capsys):
    edit(data / "leave.csv", "Ravi,2026-11-02", "Nobody,2026-11-02")
    edit(data / "bid_documents.csv", "B001,Company registration certificate,D001", "B001,Company registration certificate,D999")
    edit(data / "client_log.csv", "PRJ-001,update", "PRJ-001,gossip")
    edit(data / "projects.csv", ",Ravi,govt", ",Ravi,council")
    code, out = run(capsys, "check")
    text = " ".join(out["errors"])
    assert code == 1
    assert "'Nobody' is not in team.csv" in text and "doc_id 'D999'" in text
    assert "kind 'gossip'" in text and "client_type 'council'" in text


def test_a_new_install_has_none_of_the_new_files(data, capsys):
    for name in ("team", "leave", "documents", "bids", "bid_documents", "client_log"):
        (data / f"{name}.csv").unlink()
    code, out = run(capsys, "risks", "--no-cash")
    assert code == 0 and all(i["area"] not in ("document", "bid", "team") for i in out["items"])
