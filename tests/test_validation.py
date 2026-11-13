"""Check returned schedules independently of the solver's encoded constraints."""

from collections import Counter
from datetime import timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

import pytest

from schedule_solver.greedy import greedy
from schedule_solver.models import Workload
from schedule_solver.solver import solve
from schedule_solver.synthetic import generate


def assert_valid(work, result):
    people = {p.id: p for p in work.people}
    requests = {r.id: r for r in work.requests}
    counts = Counter()
    loads = Counter()
    assert len(result.meetings) == len({m.request_id for m in result.meetings})
    for m in result.meetings:
        r = requests[m.request_id]
        assert r.earliest <= m.start < m.end <= r.latest
        assert (m.end - m.start).total_seconds() == r.duration_minutes * 60
        assert work.start <= m.start and m.end <= work.end
        assert (m.start - work.start).total_seconds() % (work.grid_minutes * 60) == 0
        assert set(r.required_attendees) <= set(m.attendees)
        for attr in ("skills", "roles"):
            for skill, n in getattr(r, attr).items():
                assert (
                    sum(skill in getattr(people[pid], attr) for pid in m.attendees) >= n
                )
        for pid in m.attendees:
            p = people[pid]
            left = m.start - timedelta(minutes=p.buffer_before_minutes)
            right = m.end + timedelta(minutes=p.buffer_after_minutes)
            assert any(f.start <= left and right <= f.end for f in p.availability)
            assert all(right <= b.start or b.end <= left for b in p.busy)
            local = left.astimezone(ZoneInfo(p.timezone))
            local_end = right.astimezone(ZoneInfo(p.timezone))
            assert local.weekday() in p.working_hours.weekdays
            assert local.date() == local_end.date()
            assert p.working_hours.start <= local.time().replace(tzinfo=None)
            assert local_end.time().replace(tzinfo=None) <= p.working_hours.end
            counts[pid, m.start.astimezone(ZoneInfo(p.timezone)).date()] += 1
            loads[pid] += r.duration_minutes
    for (pid, _), count in counts.items():
        assert count <= people[pid].max_meetings_per_day
    for a, b in combinations(result.meetings, 2):
        for pid in set(a.attendees) & set(b.attendees):
            pad = timedelta(
                minutes=people[pid].buffer_before_minutes
                + people[pid].buffer_after_minutes
            )
            assert a.end + pad <= b.start or b.end + pad <= a.start
    if work.max_load_difference_minutes is not None:
        assert (
            max(loads[p.id] for p in work.people)
            - min(loads[p.id] for p in work.people)
            <= work.max_load_difference_minutes
        )


@pytest.mark.parametrize("seed", [1, 7, 19])
@pytest.mark.parametrize("algorithm", [greedy, solve])
def test_seeded_results_satisfy_independent_constraints(seed, algorithm):
    work = generate(10, seed)
    result = algorithm(work)
    assert_valid(work, result)


def test_hard_fairness_result_satisfies_independent_constraints(payload):
    payload["people"].append({**payload["people"][0], "id": "bob"})
    payload["max_load_difference_minutes"] = 0
    work = Workload.model_validate(payload)
    assert_valid(work, solve(work))
