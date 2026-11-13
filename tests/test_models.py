import copy

import pytest
from pydantic import ValidationError

from schedule_solver.models import Workload


def test_valid_workload(payload):
    work = Workload.model_validate(payload)
    assert work.people[0].max_meetings_per_day == 8
    assert work.requests[0].priority == 1


@pytest.mark.parametrize(
    "change",
    ["naive", "zone", "duplicate", "unknown", "duration", "empty", "window", "extra"],
)
def test_invalid_workload(payload, change):
    data = copy.deepcopy(payload)
    if change == "naive":
        data["start"] = "2027-01-04T09:00:00"
    if change == "zone":
        data["people"][0]["timezone"] = "Mars/Olympus"
    if change == "duplicate":
        data["people"].append(data["people"][0])
    if change == "unknown":
        data["requests"][0]["required_attendees"] = ["missing"]
    if change == "duration":
        data["requests"][0]["duration_minutes"] = 0
    if change == "empty":
        data["requests"][0]["required_attendees"] = []
    if change == "window":
        data["end"] = data["start"]
    if change == "extra":
        data["people"][0]["max_meetings"] = 2
    with pytest.raises(ValidationError):
        Workload.model_validate(data)
