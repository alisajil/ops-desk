import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ops  # noqa: E402
import vault  # noqa: E402

TODAY = "2026-10-26"  # a Monday
PROJECT_DIR = "Projects/PRJ-001-warehouse-sprinkler-retrofit"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """No data folder, no Claude folder: a clean machine."""
    monkeypatch.delenv("OPS_DESK_DATA", raising=False)
    monkeypatch.delenv("OPS_DESK_FOLDER", raising=False)
    monkeypatch.delenv("OPS_DESK_CASHFLOW_FILE", raising=False)
    monkeypatch.setenv("OPS_DESK_SETTINGS", str(tmp_path / "settings.json"))
    return tmp_path


@pytest.fixture
def plain(env, monkeypatch):
    """Sample data in a plain data folder, no Claude folder."""
    dst = env / "data"
    shutil.copytree(ROOT / "examples" / "data", dst)
    monkeypatch.setenv("OPS_DESK_DATA", str(dst))
    return dst


@pytest.fixture
def vaulted(env, capsys):
    """A Claude folder set up with the sample data inside it."""
    root = env / "Claude"
    ops.main(["init", "--claude-folder", str(root), "--with-examples"])
    capsys.readouterr()
    return root


def run(capsys, *args):
    code = ops.main(["--today", TODAY, *args])
    return code, json.loads(capsys.readouterr().out)


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def ids(items):
    return {i["id"]: i["severity"] for i in items}


# ---------- Claude folder ----------

def test_init_builds_the_folder_layout_and_remembers_it(env, capsys):
    root = env / "Claude"
    code, out = run(capsys, "init", "--claude-folder", str(root))
    assert code == 0
    for name in ("data", "Company/tax", "Company/registration", "Projects", "Bids", "Cash"):
        assert (root / name).is_dir()
    assert (root / "data" / "projects.csv").exists()
    settings = json.loads((env / "settings.json").read_text())
    assert settings["claude_folder"] == str(root.resolve()) and settings["data_dir"] == str((root / "data").resolve())
    _, where = run(capsys, "where")
    assert where["claude_folder"] == str(root.resolve()) and where["data_dir_exists"]
    code, checked = run(capsys, "check")
    assert code == 0 and checked["rows"]["projects"] == 0


def test_data_folder_defaults_to_data_inside_the_claude_folder(env, monkeypatch):
    monkeypatch.setenv("OPS_DESK_FOLDER", str(env / "Claude"))
    assert ops.data_dir() == env / "Claude" / "data"


def test_folders_creates_project_and_bid_folders_once(vaulted, capsys):
    code, out = run(capsys, "folders")
    assert code == 0 and out["ok"]
    assert f"{PROJECT_DIR}/Submissions" in out["created"] and f"{PROJECT_DIR}/Commercial" in out["created"]
    assert "Bids/B001-sample-b-0000001/Prepared-pack" in out["created"]
    assert (vaulted / PROJECT_DIR / "Documents").is_dir()
    _, again = run(capsys, "folders")
    assert again["created"] == []


def test_folders_check_creates_nothing(vaulted, capsys):
    _, out = run(capsys, "folders", "--check")
    assert out["check_only"] and f"{PROJECT_DIR}/Site" in out["would_create"]
    assert not (vaulted / "Projects" / "PRJ-001-warehouse-sprinkler-retrofit").exists()


def test_folders_report_unknown_folders_and_missing_files(vaulted, capsys):
    (vaulted / "Projects" / "PRJ-999-old-job").mkdir()
    (vaulted / "Bids" / "old-bid").mkdir()
    (vaulted / "Company" / "tax" / "tax-registration.pdf").write_text("x")
    _, out = run(capsys, "folders", "--check")
    assert out["unknown_project_folders"] == ["Projects/PRJ-999-old-job"]
    assert out["unknown_bid_folders"] == ["Bids/old-bid"]
    missing = {(m["kind"], m["id"]) for m in out["missing_files"]}
    assert ("document", "D002") not in missing and ("document", "D001") in missing
    assert ("submission", "PRJ-002") in missing  # the submitted test report is not saved where the record says


def test_folders_without_a_claude_folder_explains_what_to_do(plain, capsys):
    code, out = run(capsys, "folders")
    assert code == 1 and "no Claude folder configured" in out["errors"][0]


def test_a_location_cannot_climb_out_of_the_folder(env, monkeypatch):
    monkeypatch.setenv("OPS_DESK_FOLDER", str(env / "Claude"))
    (env / "Claude").mkdir()
    (env / "outside.pdf").write_text("x")
    assert vault.resolve("../outside.pdf") is None and vault.file_found("../outside.pdf") is None
    assert vault.file_found("Company/none.pdf") is False


def test_documents_show_whether_the_file_is_there(vaulted, capsys):
    (vaulted / "Company" / "tax" / "tax-registration.pdf").write_text("x")
    _, out = run(capsys, "documents")
    found = {d["id"]: d["file_found"] for d in out["documents"]}
    assert found["D002"] is True and found["D001"] is False


def test_a_missing_document_file_is_a_warning_only_when_a_folder_is_set(vaulted, plain, capsys, monkeypatch):
    _, out = run(capsys, "risks", "--no-cash")
    assert ids(out["items"])["document-file:D001"] == "medium"
    monkeypatch.delenv("OPS_DESK_FOLDER", raising=False)
    (vaulted.parent / "settings.json").write_text("{}")
    monkeypatch.setenv("OPS_DESK_DATA", str(plain))
    _, out = run(capsys, "risks", "--no-cash")
    assert not any(i["area"] == "document-file" for i in out["items"])


# ---------- project submissions ----------

def test_submissions_view_shows_blockers_and_counts(plain, capsys):
    _, out = run(capsys, "submissions")
    rows = {(r["project_id"], r["doc_name"]): r for r in out["submissions"]}
    insurance = rows[("PRJ-001", "Insurance policy")]
    assert insurance["blockers"] == ["linked document expires 2026-10-20, before the due date"]
    assert rows[("PRJ-002", "Type test report")]["blockers"] == []
    assert rows[("PRJ-003", "Work order acknowledgement")]["overdue"] is True
    assert out["by_project"]["PRJ-001"] == {"needed": 2, "ready": 1, "submitted": 0, "accepted": 0, "rejected": 0, "na": 0, "overdue": 0}
    assert out["by_project"]["PRJ-003"]["overdue"] == 1
    assert out["submissions"][0]["project_id"] == "PRJ-003"  # most overdue first


def test_submission_warnings(plain, capsys):
    _, out = run(capsys, "risks", "--no-cash")
    found = ids(out["items"])
    assert found["submission:PRJ-003:Work order acknowledgement"] == "high"
    assert found["submission:PRJ-001:Insurance policy"] == "high"
    assert found["submission:PRJ-001:Tax registration certificate"] == "low"  # ready, due in 3 days: send it
    assert "submission:PRJ-001:Site safety plan" not in found  # due in 15 days
    assert "submission:PRJ-002:Type test report" not in found  # already submitted


def test_a_rejected_submission_is_high(plain, capsys):
    edit(plain / "project_submissions.csv", "PRJ-002,Type test report,,submitted", "PRJ-002,Type test report,,rejected")
    _, out = run(capsys, "risks", "--no-cash")
    assert ids(out["items"])["submission:PRJ-002:Type test report"] == "high"


def test_finished_projects_raise_no_submission_warnings(plain, capsys):
    edit(plain / "projects.csv", "PRJ-003,Hydraulic cylinder repair batch,Sample Client C,Workshop,repair,planned", "PRJ-003,Hydraulic cylinder repair batch,Sample Client C,Workshop,repair,done")
    _, out = run(capsys, "risks", "--no-cash")
    assert "submission:PRJ-003:Work order acknowledgement" not in ids(out["items"])


def test_a_missing_linked_file_blocks_the_submission(vaulted, capsys):
    _, out = run(capsys, "submissions")
    row = next(r for r in out["submissions"] if r["doc_name"] == "Tax registration certificate")
    assert row["blockers"] == ["file not found at Company/tax/tax-registration.pdf"]
    (vaulted / "Company" / "tax" / "tax-registration.pdf").write_text("x")
    _, out = run(capsys, "submissions")
    assert next(r for r in out["submissions"] if r["doc_name"] == "Tax registration certificate")["blockers"] == []


def test_the_huddle_lists_submissions_due_within_two_weeks(plain, capsys):
    _, out = run(capsys, "huddle", "--no-cash")
    assert {s["doc_name"] for s in out["submissions_due_14_days"]} == {
        "Work order acknowledgement", "Insurance policy", "Tax registration certificate"}


def test_submission_rows_are_validated(plain, capsys):
    edit(plain / "project_submissions.csv", "PRJ-001,Tax registration certificate,D002,ready", "PRJ-001,Tax registration certificate,D999,waiting")
    edit(plain / "project_submissions.csv", "PRJ-002,Type test report,,submitted,2026-10-20,2026-10-19", "PRJ-002,Type test report,,submitted,2026-10-20,")
    code, out = run(capsys, "check")
    text = " ".join(out["errors"])
    assert code == 1 and "doc_id 'D999'" in text and "status 'waiting'" in text and "submitted_on is required" in text
