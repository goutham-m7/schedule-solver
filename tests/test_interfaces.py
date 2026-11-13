import json
import subprocess
import sys

from fastapi.testclient import TestClient

from schedule_solver.api import app
from schedule_solver.synthetic import generate


def test_api_solve_compare_and_calendar(payload):
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    result = client.post("/solve", json={"workload": payload, "time_limit": 2})
    assert result.status_code == 200
    assert result.json()["metrics"]["meetings_scheduled"] == 1
    assert result.json()["explanations"][0]["kind"] == "scheduled"
    comparison = client.post("/compare", json={"workload": payload})
    assert comparison.status_code == 200
    assert comparison.json()["greedy"]["metrics"]["meetings_scheduled"] == 1
    calendar = client.post("/calendar", json={"workload": payload})
    assert calendar.status_code == 200
    assert "text/html" in calendar.headers["content-type"]
    assert "Time, used intentionally" in calendar.text


def test_api_rejects_invalid_and_unbounded_work(payload):
    client = TestClient(app)
    assert client.post("/solve", json={"workload": payload, "time_limit": 999}).status_code == 422
    payload["requests"][0]["required_attendees"] = ["unknown"]
    assert client.post("/solve", json={"workload": payload}).status_code == 422


def test_cli_solve_and_invalid_file(payload, tmp_path):
    path = tmp_path/"work.json"
    path.write_text(json.dumps(payload))
    process = subprocess.run([sys.executable, "-m", "schedule_solver", "solve", str(path), "--time-limit", "2"], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["metrics"]["meetings_scheduled"] == 1
    path.write_text("{}")
    process = subprocess.run([sys.executable, "-m", "schedule_solver", "solve", str(path)], capture_output=True, text=True)
    assert process.returncode == 2
    assert "error:" in process.stderr and "Traceback" not in process.stderr


def test_demo_offline_writes_real_outputs(tmp_path):
    process = subprocess.run([sys.executable, "-m", "schedule_solver", "demo", "--people", "5", "--output", str(tmp_path), "--time-limit", "2"], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert "greedy-first-fit" in process.stdout and "cp-sat" in process.stdout
    assert "Conflict:" in process.stdout
    assert (tmp_path/"calendar.html").exists()
    assert json.loads((tmp_path/"result.json").read_text())["meetings"]


def test_synthetic_reproducibility():
    assert generate(20, seed=7) == generate(20, seed=7)
    assert len(generate(100).people) == 100
