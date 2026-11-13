from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from schedule_solver.explain import explain_result
from schedule_solver.models import Period, Workload
from schedule_solver.solver import solve


def test_diagnostic_respects_attendance_eligibility_under_hard_fairness(payload):
    payload["people"].append({**payload["people"][0], "id": "bob", "skills": []})
    payload["max_load_difference_minutes"] = 0
    work = Workload.model_validate(payload)
    e = explain_result(work, solve(work)).explanations[0]
    assert e.kind == "insertion_conflict"
    assert "fairness" in e.conflict


def test_utc_normalization_preserves_fall_back_interval():
    zone = ZoneInfo("America/New_York")
    start = datetime(2027, 11, 7, 1, 45, tzinfo=zone, fold=0)
    end = datetime(2027, 11, 7, 1, 15, tzinfo=zone, fold=1)
    period = Period(start=start, end=end)
    assert (period.end - period.start).total_seconds() == 1800
    assert period.start.tzinfo == UTC


def test_search_without_incumbent_preserves_valid_warm_start(payload):
    work = Workload.model_validate(payload)
    result = solve(work, time_limit=0.000001)
    assert result.metrics.meetings_scheduled == 1
    assert result.passes[0].status == "UNKNOWN"


@pytest.mark.parametrize("limit", [0, -1, 121, float("nan")])
def test_search_rejects_invalid_limits(payload, limit):
    with pytest.raises(ValueError):
        solve(Workload.model_validate(payload), limit)
