import json
import sys

import pytest

from schedule_solver.cli import main
from schedule_solver.synthetic import generate


@pytest.mark.parametrize("size", [200, 500])
def test_larger_family_is_deterministic_and_valid(size):
    work = generate(size, seed=42)
    assert len(work.people) == size
    assert len(work.requests) == size * 12 // 5
    assert generate(size, seed=42) == work


def test_ring_family_connects_neighbor_pods_without_global_dense_staffing():
    independent = generate(20)
    ring = generate(20, family="ring")
    assert len(ring.requests) == len(independent.requests)
    assert "build-3" in ring.people[3].skills
    assert "build-0" in ring.people[8].skills
    assert len([p for p in ring.people if "build-0" in p.skills]) == 4
    assert len([p for p in independent.people if "build-0" in p.skills]) == 2
    with pytest.raises(ValueError, match="family"):
        generate(20, family="unknown")


def test_benchmark_curves_record_budgets_bounds_and_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "schedule-solver",
            "benchmark",
            "--sizes",
            "5",
            "--families",
            "independent",
            "ring",
            "--budgets",
            "0.001",
            "1",
            "--output",
            str(tmp_path),
        ],
    )
    main()
    records = json.loads((tmp_path / "benchmark.json").read_text())
    assert len(records) == 4
    assert {(r["family"], r["time_limit"]) for r in records} == {
        ("independent", 0.001),
        ("independent", 1),
        ("ring", 0.001),
        ("ring", 1),
    }
    assert all(
        r["optimized"]["metrics"]["priority_scheduled"]
        >= r["greedy"]["metrics"]["priority_scheduled"]
        for r in records
    )
    assert all("bound" in r["optimized"]["passes"][0] for r in records)
    metadata = json.loads((tmp_path / "environment.json").read_text())
    assert metadata["python"] and metadata["ortools"] and metadata["platform"]
    assert "ring" in (tmp_path / "benchmark.md").read_text()
