import json
import sys

import pytest

from schedule_solver.cli import main


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["schedule-solver", *map(str, args)])
    main()


def test_solve_and_html_inprocess(payload, tmp_path, monkeypatch, capsys):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload))
    invoke(monkeypatch, "solve", path, "--html", tmp_path / "view.html")
    result = json.loads(capsys.readouterr().out)
    assert result["explanations"][0]["kind"] == "scheduled"
    assert "ada" in (tmp_path / "view.html").read_text()
    invoke(monkeypatch, "solve", path, "--no-explanations")
    assert json.loads(capsys.readouterr().out)["explanations"] == []


def test_import_ics_updates_busy_calendar(payload, tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload))
    ics = tmp_path / "busy.ics"
    ics.write_text(
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20270104T100000Z\nDTEND:20270104T110000Z\nEND:VEVENT\nEND:VCALENDAR"
    )
    target = tmp_path / "merged.json"
    invoke(monkeypatch, "import-ics", path, "ada", ics, "--output", target)
    assert len(json.loads(target.read_text())["people"][0]["busy"]) == 1
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "import-ics", path, "nobody", ics, "--output", target)
    assert error.value.code == 2


def test_demo_and_benchmark_run_offline(tmp_path, monkeypatch, capsys):
    invoke(
        monkeypatch, "demo", "--people", "5", "--output", tmp_path, "--time-limit", "2"
    )
    assert "Conflict:" in capsys.readouterr().out
    invoke(monkeypatch, "benchmark", "--output", tmp_path, "--time-limit", "0.001")
    records = json.loads((tmp_path / "benchmark.json").read_text())
    assert [r["people"] for r in records] == [20, 50, 100]
    assert all(r["optimized"]["metrics"]["meetings_scheduled"] > 0 for r in records)


def test_provider_missing_key_fails_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SCHEDULE_LLM_API_KEY", raising=False)
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "demo",
            "--people",
            "5",
            "--output",
            tmp_path,
            "--provider",
            "openai",
            "--time-limit",
            "2",
        )
    assert error.value.code == 2
    assert "key and model" in capsys.readouterr().err


def test_invalid_inputs_are_errors(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "solve", tmp_path / "missing.json")
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        invoke(monkeypatch, "demo", "--people", "3", "--output", tmp_path)
