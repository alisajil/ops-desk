import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ops  # noqa: E402

TODAY = "2026-10-26"  # a Monday


@pytest.fixture
def data(tmp_path, monkeypatch):
    dst = tmp_path / "data"
    shutil.copytree(ROOT / "examples" / "data", dst)
    monkeypatch.setenv("OPS_DESK_DATA", str(dst))
    return dst


def run(capsys, *args):
    code = ops.main(["--today", TODAY, *args])
    return code, json.loads(capsys.readouterr().out)


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def project(out, code):
    return next(p for p in out["projects"] if p["project_id"] == code)


def test_check_passes_on_example_data(data, capsys):
    code, out = run(capsys, "check")
    assert code == 0 and out["ok"]
    assert (out["rows"]["tasks"], out["rows"]["zoho_lines"], out["rows"]["issues"]) == (10, 13, 3)


def test_check_reports_bad_date(data, capsys):
    edit(data / "tasks.csv", "2026-10-20", "20/10/2026")
    code, out = run(capsys, "check")
    assert code == 1
    assert any("bad due" in e for e in out["errors"])


def test_check_reports_unquoted_comma(data, capsys):
    with (data / "tasks.csv").open("a", encoding="utf-8") as f:
        f.write("T011,PRJ-003,Test, then dispatch,Anil,2026-11-05,2026-11-06,todo,,\n")
    code, out = run(capsys, "check")
    assert code == 1
    assert any("column count" in e for e in out["errors"])


def test_commands_refuse_to_run_on_invalid_data(data, capsys):
    edit(data / "projects.csv", ",active,", ",going,")
    code, out = run(capsys, "pnl")
    assert code == 1 and not out["ok"]


def test_zoho_line_with_unknown_project_code_is_rejected(data, capsys):
    edit(data / "zoho_lines.csv", "PRJ-002,invoice", "PRJ-009,invoice")
    code, out = run(capsys, "check")
    assert code == 1 and any("unknown project code 'PRJ-009'" in e for e in out["errors"])


def test_new_install_without_zoho_or_issue_files_still_works(data, capsys):
    (data / "zoho_lines.csv").unlink()
    (data / "issues.csv").unlink()
    code, out = run(capsys, "pnl")
    assert code == 0 and project(out, "PRJ-001")["revenue_billed_inr"] == 0
    assert run(capsys, "issues")[1]["open"] == []


def test_overdue_lists_worst_first(data, capsys):
    _, out = run(capsys, "overdue")
    assert [(t["id"], t["days_late"]) for t in out] == [("T003", 6), ("T007", 4)]


def test_week_flags_owner_clash(data, capsys):
    _, out = run(capsys, "week", "--start", TODAY)
    assert any(set(c["tasks"]) == {"T004", "T008"} for c in out["clashes"])
    assert "T005" not in {t["id"] for ts in out["projects"].values() for t in ts}


def test_pnl_per_project_from_zoho_lines(data, capsys):
    _, out = run(capsys, "pnl")
    p1 = project(out, "PRJ-001")
    assert (p1["revenue_billed_inr"], p1["revenue_received_inr"], p1["receivable_inr"]) == (1800000, 1000000, 800000)
    assert p1["overdue_receivable_inr"] == 800000 and p1["overdue_payable_inr"] == 0
    assert (p1["bills_inr"], p1["payable_inr"], p1["expenses_inr"]) == (1300000, 850000, 120000)
    assert (p1["cost_to_date_inr"], p1["committed_po_inr"]) == (1420000, 500000)
    assert (p1["profit_inr"], p1["margin_pct"], p1["cash_profit_inr"]) == (380000, 21.1, 430000)
    assert (p1["pct_budget_used"], p1["level"], p1["planned_margin_pct"]) == (76.8, "ok", 21.9)

    p2 = project(out, "PRJ-002")
    assert (p2["profit_inr"], p2["margin_pct"]) == (-190000, -34.5)
    assert (p2["pct_budget_used"], p2["level"]) == (92.5, "amber")

    p3 = project(out, "PRJ-003")
    assert (p3["margin_pct"], p3["pct_budget_used"], p3["level"]) == (None, 0.0, "ok")
    assert out["totals"]["profit_inr"] == 190000


def test_pnl_ignores_void_documents(data, capsys):
    _, out = run(capsys, "pnl")
    assert project(out, "PRJ-001")["revenue_billed_inr"] == 1800000  # void INV-0099 (999999) not counted


def test_site_expenses_use_configured_categories(data, capsys):
    _, out = run(capsys, "pnl")
    assert out["site_categories_configured"]
    assert project(out, "PRJ-001")["site_expenses_inr"] == 120000
    assert project(out, "PRJ-002")["site_expenses_inr"] == 0
    assert project(out, "PRJ-002")["expenses_by_category"] == {"labour": 40000}
    edit(data / "config.json", '"site travel", "site food", "site consumables", "site accommodation"', "")
    _, out = run(capsys, "pnl")
    assert not out["site_categories_configured"] and project(out, "PRJ-001")["site_expenses_inr"] == 0


def test_issues_open_overdue_and_cost(data, capsys):
    _, out = run(capsys, "issues")
    assert [(i["id"], i["days_overdue"]) for i in out["open"]] == [("I001", 2), ("I002", 0)]
    p1, p2 = out["by_project"]["PRJ-001"], out["by_project"]["PRJ-002"]
    assert (p1["open"], p1["overdue"], p1["delay_days_open"]) == (1, 1, 6)
    assert (p1["cost_impact_inr"], p1["cost_impact_open_inr"]) == (15000, 0)
    assert (p2["open"], p2["overdue"], p2["cost_impact_open_inr"]) == (1, 0, 25000)


def test_reminders_skip_after_mark_reminded(data, capsys):
    _, out = run(capsys, "reminders")
    owners = {o["owner"]: sorted(t["id"] for t in o["tasks"]) for o in out["owners"]}
    assert owners == {"Ravi": ["T003"], "Anil": ["T007", "T008"]}
    assert [e["id"] for e in out["escalate_to_management"]] == ["T007"]

    code, _ = run(capsys, "mark-reminded", "--owner", "Anil", "--tasks", "T007,T008")
    assert code == 0
    _, again = run(capsys, "reminders")
    assert [o["owner"] for o in again["owners"]] == ["Ravi"]


def test_mark_reminded_rejects_unknown_task(data, capsys):
    code, out = run(capsys, "mark-reminded", "--owner", "Anil", "--tasks", "T999")
    assert code == 1 and not out["ok"]


def test_reminders_report_owner_missing_from_stakeholders(data, capsys):
    edit(data / "tasks.csv", "T003,PRJ-001,Client and authority approval of drawings,Ravi", "T003,PRJ-001,Client and authority approval of drawings,Zed")
    _, out = run(capsys, "reminders")
    assert [u["owner"] for u in out["unmatched_owners"]] == ["Zed"]


def test_report_rag_amber_then_red(data, capsys):
    _, out = run(capsys, "report")
    assert {p["id"]: p["rag"] for p in out["projects"]} == {"PRJ-001": "amber", "PRJ-002": "amber", "PRJ-003": "green"}
    p1 = next(p for p in out["projects"] if p["id"] == "PRJ-001")
    assert "client payment overdue" in p1["reasons"] and "1 issue(s) overdue" in p1["reasons"]

    edit(data / "projects.csv", "2026-11-15,800000", "2026-11-15,700000")
    _, out = run(capsys, "report")
    p2 = next(p for p in out["projects"] if p["id"] == "PRJ-002")
    assert p2["rag"] == "red" and any("budget" in r for r in p2["reasons"])
