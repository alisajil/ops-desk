import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ops  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.delenv("OPS_DESK_DATA", raising=False)
    monkeypatch.setenv("OPS_DESK_SETTINGS", str(tmp_path / "settings.json"))
    return tmp_path


def run(capsys, *args):
    code = ops.main(list(args))
    return code, json.loads(capsys.readouterr().out)


def test_init_creates_empty_templates_and_settings_then_check_passes(home, capsys):
    target = home / "ops-data"
    code, out = run(capsys, "init", "--data-dir", str(target))
    assert code == 0 and "projects.csv" in out["created"] and "config.json" in out["created"]
    assert (target / "projects.csv").read_text().startswith("id,name,client")
    assert json.loads((home / "settings.json").read_text())["data_dir"] == str(target.resolve())
    code, out = run(capsys, "check")  # no env var: data dir comes from the settings file
    assert code == 0 and out["rows"]["projects"] == 0


def test_init_keeps_existing_files(home, capsys):
    target = home / "ops-data"
    run(capsys, "init", "--data-dir", str(target))
    (target / "projects.csv").write_text("id,name,client,site,type,status,start,end,budget_inr,contract_value_inr,cash_head,owner\nPRJ-9,x,,,,active,,,0,0,,\n")
    _, out = run(capsys, "init", "--data-dir", str(target))
    assert out["created"] == [] and "PRJ-9" in (target / "projects.csv").read_text()


def test_init_with_examples_copies_sample_data(home, capsys):
    target = home / "ops-data"
    run(capsys, "init", "--data-dir", str(target), "--with-examples")
    code, out = run(capsys, "check")
    assert code == 0 and out["rows"]["tasks"] == 10


def test_init_records_cashflow_file_and_rejects_missing_one(home, capsys):
    target, book = home / "ops-data", home / "cf.xlsx"
    code, out = run(capsys, "init", "--data-dir", str(target), "--cashflow-file", str(book))
    assert code == 1 and "not found" in out["errors"][0]
    book.write_bytes(b"x")
    code, out = run(capsys, "init", "--data-dir", str(target), "--cashflow-file", str(book))
    assert code == 0 and out["settings"]["cashflow_file"] == str(book.resolve())


def test_where_reports_paths_before_and_after_init(home, capsys):
    _, out = run(capsys, "where")
    assert out["settings_file_exists"] is False and out["cashflow_file"] is None
    book = home / "cf.xlsx"
    book.write_bytes(b"x")
    run(capsys, "init", "--data-dir", str(home / "ops-data"), "--cashflow-file", str(book))
    _, out = run(capsys, "where")
    assert out["settings_file_exists"] and out["data_dir_exists"] and out["cashflow_file"] == str(book.resolve())


def test_env_var_beats_settings_file(home, capsys, monkeypatch):
    run(capsys, "init", "--data-dir", str(home / "from-settings"))
    other = home / "from-env"
    monkeypatch.setenv("OPS_DESK_DATA", str(other))
    assert ops.data_dir() == other


def test_invalid_settings_file_stops_with_a_clear_message(home):
    (home / "settings.json").write_text("{not json")
    with pytest.raises(SystemExit) as e:
        ops.settings()
    assert "not valid JSON" in str(e.value)
