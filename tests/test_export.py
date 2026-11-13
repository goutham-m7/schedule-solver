import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar

from schedule_solver import calendars
from schedule_solver.api import app
from schedule_solver.models import Workload
from schedule_solver.solver import solve


def test_export_roundtrip_and_stable_uid(payload):
    payload["requests"][0]["id"] = "review,;\\\n日本語"
    work = Workload.model_validate(payload)
    result = solve(work)
    first = Calendar.from_ical(calendars.export_ics(work, result)).walk("VEVENT")[0]
    second = Calendar.from_ical(calendars.export_ics(work, result)).walk("VEVENT")[0]
    assert first["UID"] == second["UID"]
    assert str(first["SUMMARY"]) == work.requests[0].id
    assert json.loads(str(first["X-SCHEDULE-ATTENDEES"])) == ["ada"]
    assert first.decoded("DTSTART") == result.meetings[0].start
    assert "ATTENDEE" not in first  # IDs are not email addresses.
    periods = calendars.import_ics(calendars.export_ics(work, result), "UTC")
    assert periods[0].start == result.meetings[0].start
    assert periods[0].end == result.meetings[0].end


@pytest.mark.parametrize(
    "change",
    [
        "unknown_request",
        "unknown_person",
        "duplicate",
        "duration",
        "calendar",
        "team",
        "overlap",
        "cap",
        "fairness",
    ],
)
def test_invalid_schedule_cannot_be_exported(payload, change):
    work = Workload.model_validate(payload)
    result = solve(work)
    if change == "unknown_request":
        result.meetings[0].request_id = "ghost"
    elif change == "unknown_person":
        result.meetings[0].attendees = ["ghost"]
    elif change == "duplicate":
        result.meetings *= 2
    elif change == "duration":
        result.meetings[0].end = work.end
    elif change == "calendar":
        work.people[0].busy = work.people[0].availability
    elif change == "team":
        result.meetings[0].attendees = []
    elif change == "overlap":
        work.requests.append(work.requests[0].model_copy(update={"id": "second"}))
        result.meetings.append(
            result.meetings[0].model_copy(update={"request_id": "second"})
        )
    elif change == "cap":
        work.people[0].max_meetings_per_day = 0
    else:
        work.people.append(work.people[0].model_copy(update={"id": "bea"}))
        work.max_load_difference_minutes = 0
    with pytest.raises(ValueError):
        calendars.export_ics(work, result)


def test_empty_schedule_exports_valid_calendar(payload):
    work = Workload.model_validate(payload)
    result = solve(work)
    result.meetings = []
    assert Calendar.from_ical(calendars.export_ics(work, result)).walk("VEVENT") == []


def test_http_and_cli_export(payload, tmp_path):
    response = TestClient(app).post(
        "/export-ics", json={"workload": payload, "explanations": False}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert len(Calendar.from_ical(response.text).walk("VEVENT")) == 1
    source = tmp_path / "work.json"
    source.write_text(json.dumps(payload))
    target = tmp_path / "schedule.ics"
    run = subprocess.run(
        [
            "schedule-solver",
            "solve",
            str(source),
            "--no-explanations",
            "--ics",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert len(Calendar.from_ical(Path(target).read_text()).walk("VEVENT")) == 1
