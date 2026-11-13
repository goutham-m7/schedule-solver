from schedule_solver.models import Workload
from schedule_solver.solver import solve


def test_daily_membership_across_horizon(payload):
    payload["end"] = "2027-01-05T12:00:00Z"
    payload["people"][0]["availability"][0]["end"] = payload["end"]
    payload["people"][0]["max_meetings_per_day"] = 1
    base = {**payload["requests"][0], "latest": payload["end"]}
    payload["requests"] = [{**base, "id": str(i)} for i in range(3)]
    result = solve(Workload.model_validate(payload), 2)
    assert result.metrics.meetings_scheduled == 2
    assert len({m.start.date() for m in result.meetings}) == 2


def test_caps_use_local_dates_not_utc_dates(payload):
    payload.update(start="2027-01-04T23:00:00Z", end="2027-01-05T01:00:00Z")
    payload["people"][0].update(
        timezone="America/Los_Angeles",
        max_meetings_per_day=1,
        availability=[{"start": payload["start"], "end": payload["end"]}],
    )
    payload["requests"] = [
        {
            "id": str(i),
            "duration_minutes": 30,
            "earliest": s,
            "latest": e,
            "required_attendees": ["ada"],
        }
        for i, (s, e) in enumerate(
            [
                ("2027-01-04T23:00:00Z", "2027-01-04T23:30:00Z"),
                ("2027-01-05T00:00:00Z", "2027-01-05T00:30:00Z"),
            ]
        )
    ]
    assert solve(Workload.model_validate(payload)).metrics.meetings_scheduled == 1
