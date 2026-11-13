from schedule_solver.solver import solve
from schedule_solver.synthetic import generate


def test_time_limited_fairness_pass_reports_its_returned_assignment_value():
    # At this deterministic budget OR-Tools 9.15 can report objective_value=120
    # while value(high-low)=90 in its returned solution. Fix the next pass to the
    # actual expression value, not the stale response objective summary.
    result = solve(generate(200), time_limit=60)
    fairness = next(p for p in result.passes if p.name == "fairness")
    assert fairness.status in {"OPTIMAL", "FEASIBLE"}
    assert fairness.value == result.metrics.load_spread_minutes
