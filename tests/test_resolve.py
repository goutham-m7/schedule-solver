from copy import deepcopy

import pytest
from conftest import ts
from fastapi.testclient import TestClient

from schedule_solver import solver
from schedule_solver.api import app
from schedule_solver.models import Meeting, Workload


def old(request_id="review", hour=10, attendees=None):
    return Meeting(
        request_id=request_id,
        start=ts(hour),
        end=ts(hour, 30),
        attendees=attendees or ["ada"],
    )


def test_addition_preserves_unaffected_assignment(payload):
    payload["requests"].append(
        dict(payload["requests"][0], id="added", earliest=ts(9), latest=ts(9, 30))
    )
    result = solver.resolve(Workload.model_validate(payload), [old()])
    meetings = {m.request_id: m for m in result.meetings}
    assert meetings["review"] == old()
    assert meetings["added"].start == ts(9)
    assert result.changed_requests == []
    assert result.passes[1].name == "stability"
    assert result.passes[1].status == "OPTIMAL"


def test_cancellation_does_not_count_as_unintended_change(payload):
    result = solver.resolve(
        Workload.model_validate(payload), [old(), old("cancelled", 11)]
    )
    assert result.meetings == [old()]
    assert result.changed_requests == []


def test_edited_window_moves_only_necessary_meeting(payload):
    payload["requests"][0].update(earliest=ts(9), latest=ts(9, 30))
    result = solver.resolve(Workload.model_validate(payload), [old()])
    assert result.meetings[0].start == ts(9)
    assert result.changed_requests == ["review"]


def test_priority_precedes_stability(payload):
    payload["requests"][0].update(earliest=ts(10), latest=ts(10, 30))
    payload["requests"].append(dict(payload["requests"][0], id="urgent", priority=10))
    result = solver.resolve(Workload.model_validate(payload), [old()])
    assert [m.request_id for m in result.meetings] == ["urgent"]
    assert result.changed_requests == ["review"]


def test_preserves_alternative_skill_team(payload):
    payload["people"].append(dict(deepcopy(payload["people"][0]), id="bea"))
    payload["requests"][0].update(required_attendees=[], skills={"python": 1})
    previous = old(attendees=["bea"])
    result = solver.resolve(Workload.model_validate(payload), [previous])
    assert result.meetings == [previous]


@pytest.mark.parametrize(
    "change", ["duplicate", "unknown_person", "duplicate_attendee", "negative_duration"]
)
def test_rejects_malformed_previous_assignments(payload, change):
    previous = [old()]
    if change == "duplicate":
        previous *= 2
    elif change == "unknown_person":
        previous[0].attendees = ["ghost"]
    elif change == "duplicate_attendee":
        previous[0].attendees *= 2
    else:
        previous[0].end = ts(9)
    with pytest.raises(ValueError):
        solver.resolve(Workload.model_validate(payload), previous)


def test_http_resolve_and_openapi_contract(payload):
    client = TestClient(app)
    response = client.post(
        "/resolve",
        json={
            "workload": payload,
            "previous": [old().model_dump(mode="json")],
            "explanations": False,
        },
    )
    assert response.status_code == 200
    assert (
        response.json()["meetings"][0]["start"]
        == old().model_dump(mode="json")["start"]
    )
    assert client.get("/openapi.json").json()["paths"]["/resolve"]
    assert (
        client.post(
            "/resolve",
            json={
                "workload": payload,
                "previous": [old(attendees=["unknown"]).model_dump(mode="json")],
            },
        ).status_code
        == 422
    )


def test_meeting_contract_normalizes_dst_duration():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    meeting = Meeting(
        request_id="dst",
        start=datetime(2027, 3, 14, 1, 30, tzinfo=zone),
        end=datetime(2027, 3, 14, 3, 30, tzinfo=zone),
        attendees=["ada"],
    )
    assert (meeting.end - meeting.start).total_seconds() == 3600
