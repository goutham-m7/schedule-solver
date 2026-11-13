from itertools import combinations

from schedule_solver.explain import InsertionModel, explain_result
from schedule_solver.models import Workload
from schedule_solver.solver import solve


def test_small_certificate_is_globally_smallest_cardinality(payload):
    payload["people"][0]["max_meetings_per_day"] = 0
    work = Workload.model_validate(payload)
    result = solve(work)
    diagnostic = InsertionModel(work, result, work.requests[0])
    conflict, guarantee = diagnostic.minimum_conflict()
    assert guarantee == "minimum-cardinality"
    assert not diagnostic.check(set(conflict))[0]
    for size in range(len(conflict)):
        for subset in combinations(diagnostic.labels, size):
            assert diagnostic.check(set(subset))[0]
    assert diagnostic.minimum_conflict() == (conflict, guarantee)
    explanation = explain_result(work, result).explanations[0]
    assert explanation.guarantee == guarantee
    assert "Minimum-cardinality" in explanation.facts[0]


def test_larger_universe_retains_honest_inclusion_guarantee(payload):
    payload["people"][0]["max_meetings_per_day"] = 0
    work = Workload.model_validate(payload)
    diagnostic = InsertionModel(work, solve(work), work.requests[0])
    conflict, guarantee = diagnostic.minimum_conflict(max_labels=0)
    assert guarantee == "inclusion-minimal"
    for label in conflict:
        assert diagnostic.check(set(conflict) - {label})[0]


def test_insertable_has_no_conflict_guarantee(payload):
    work = Workload.model_validate(payload)
    result = solve(work)
    result.meetings = []
    diagnostic = InsertionModel(work, result, work.requests[0])
    assert diagnostic.minimum_conflict() == (None, "none")
    assert explain_result(work, result).explanations[0].guarantee == "none"
