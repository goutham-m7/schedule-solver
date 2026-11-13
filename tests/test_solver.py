import itertools

from conftest import ts

from schedule_solver.models import Workload
from schedule_solver.solver import solve


def request(id, start=9, end=10, duration=60, priority=1, **kw):
    return {
        "id": id,
        "duration_minutes": duration,
        "earliest": ts(start).isoformat(),
        "latest": ts(end).isoformat(),
        "required_attendees": ["ada"],
        "priority": priority,
        **kw,
    }


def test_priority_is_primary(payload):
    payload["requests"] = [request("low"), request("high", priority=5)]
    r = solve(Workload.model_validate(payload))
    assert [m.request_id for m in r.meetings] == ["high"]
    assert r.passes[0].status == "OPTIMAL"


def test_buffers_and_daily_caps(payload):
    payload["people"][0].update(
        buffer_before_minutes=15, buffer_after_minutes=15, max_meetings_per_day=2
    )
    payload["requests"] = [request(str(i), end=12, duration=30) for i in range(5)]
    r = solve(Workload.model_validate(payload))
    assert len(r.meetings) == 2
    meetings = sorted(r.meetings, key=lambda m: m.start)
    assert (meetings[1].start - meetings[0].end).total_seconds() >= 30 * 60


def test_skill_role_and_optional_attendees(payload):
    payload["people"].append(
        {**payload["people"][0], "id": "bob", "skills": ["rust"], "roles": ["lead"]}
    )
    payload["requests"] = [
        request(
            "pair",
            required_attendees=[],
            skills={"python": 1, "rust": 1},
            roles={"lead": 1},
        )
    ]
    r = solve(Workload.model_validate(payload))
    assert set(r.meetings[0].attendees) == {"ada", "bob"}
    payload["requests"] = [request("optional", optional_attendees=["bob"])]
    assert "bob" in solve(Workload.model_validate(payload)).meetings[0].attendees


def test_packing_removes_avoidable_gaps(payload):
    payload["requests"] = [
        request("fixed", end=10),
        request("flex", end=12, duration=30),
    ]
    r = solve(Workload.model_validate(payload))
    assert r.metrics.gap_minutes == 0


def test_fairness_balances_interchangeable_people(payload):
    payload["people"].append({**payload["people"][0], "id": "bob"})
    payload["requests"] = [
        request(
            str(i), end=12, duration=30, required_attendees=[], skills={"python": 1}
        )
        for i in range(4)
    ]
    r = solve(Workload.model_validate(payload))
    assert r.metrics.load_spread_minutes == 0
    assert sum(len(m.attendees) for m in r.meetings) == 4


def test_hard_fairness_can_forbid_unbalanced_meeting(payload):
    payload["people"].append({**payload["people"][0], "id": "bob", "skills": []})
    payload["max_load_difference_minutes"] = 0
    assert solve(Workload.model_validate(payload)).unscheduled == ["review"]


def test_priority_matches_exhaustive_subset_oracle(payload):
    specs = [(9, 10, 2), (9, 11, 3), (10, 11, 4), (11, 12, 1)]
    payload["requests"] = [
        request(str(i), a, b, (b - a) * 60, p) for i, (a, b, p) in enumerate(specs)
    ]
    feasible_scores = []
    for bits in itertools.product([0, 1], repeat=len(specs)):
        chosen = [s for s, bit in zip(specs, bits, strict=True) if bit]
        if all(
            a[1] <= b[0] or b[1] <= a[0] for a, b in itertools.combinations(chosen, 2)
        ):
            feasible_scores.append(sum(s[2] for s in chosen))
    r = solve(Workload.model_validate(payload))
    assert r.metrics.priority_scheduled == max(feasible_scores)


def test_empty_and_impossible(payload):
    payload["requests"] = []
    assert solve(Workload.model_validate(payload)).metrics.meetings_scheduled == 0
    payload["requests"] = [
        request("missing", required_attendees=[], skills={"quantum": 1})
    ]
    assert solve(Workload.model_validate(payload)).unscheduled == ["missing"]
