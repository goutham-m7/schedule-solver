"""Synthetic quality/time curves; construction and warm starts count in solve time."""

import platform
from importlib.metadata import version

from .greedy import greedy
from .solver import solve
from .synthetic import generate


def environment():
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ortools": version("ortools"),
        "schedule-solver": version("schedule-solver"),
    }


def curves(sizes, budgets, families, seed):
    if (
        not sizes
        or not budgets
        or not families
        or any(not 0 < budget <= 120 for budget in budgets)
    ):
        raise ValueError("benchmark needs sizes, families and budgets in (0, 120]")
    for family in families:
        for size in sizes:
            work = generate(size, seed, family=family)
            baseline = greedy(work)
            for budget in budgets:
                result = solve(work, budget)
                yield (
                    work,
                    baseline,
                    result,
                    {
                        "people": size,
                        "seed": seed,
                        "family": family,
                        "time_limit": budget,
                        "workload": work.model_dump(mode="json"),
                        "greedy": baseline.model_dump(mode="json"),
                        "optimized": result.model_dump(mode="json"),
                    },
                )
