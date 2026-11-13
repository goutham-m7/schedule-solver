# Observed verification

Commands run locally:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=schedule_solver --cov-report=term-missing --cov-fail-under=90 -q
uv run schedule-solver demo --people 5 --seed 7 --time-limit 10 --output artifacts/demo
uv run schedule-solver benchmark --seed 7 --time-limit 10 --output artifacts/benchmark
uv run schedule-solver import-ics examples/workload.json p000 examples/busy.ics --output artifacts/merged.json
uv run schedule-solver solve artifacts/merged.json --time-limit 2
```

- Lint and format: passed. 75 tests passed; 95.62% statement coverage.
- One unsuppressed upstream Starlette TestClient/httpx deprecation warning.
- Demo: 10 scheduled versus greedy 8; 30 versus 120 gap-minutes.
- Benchmark: primary priority proven optimal at all requested sizes; several
  secondary passes FEASIBLE, not globally proven optimal. Raw values in benchmark.json.
- Repeat benchmark: all non-timing metrics matched at all three sizes.
- Real Uvicorn socket POST /solve: HTTP 200, 10 scheduled, 12 explanations.
  Server stopped after inspection. Response summary in api-smoke.json.
- Real browser inspection: 10 event cards, 12 explanation disclosures; wide lanes
  scroll at a mobile-width viewport. Observed capture in calendar.webp.
- Documented ICS import plus solve: 10 scheduled.
- No hosted LLM credential or paid live provider was exercised.
- Source repository has no remotes; no push, network remote or package publish.

Environment: macOS arm64; CPython 3.12.15; OR-Tools 9.15.6755; uv 0.13.5.
