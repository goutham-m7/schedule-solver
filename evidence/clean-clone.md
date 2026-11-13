# Clean-clone verification

A temporary local Git clone of commit `ff664c5` was checked out with no copied
virtual environment or generated artifacts. Its temporary local-path origin was
removed before installation. No network remote was added and nothing was pushed.
The original repository remained unchanged and has no remotes.

Reproducible procedure (SOURCE and DEST are caller-selected local directories):

```sh
git clone --bare --no-hardlinks "$SOURCE" "$DEST/.git"
git --git-dir "$DEST/.git" --work-tree "$DEST" checkout HEAD -- .
git --git-dir "$DEST/.git" remote remove origin
# Run the following from DEST:
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=schedule_solver --cov-report=term-missing --cov-fail-under=90 -q
uv run schedule-solver demo --people 5 --seed 7 --time-limit 10 --output artifacts/demo
```

Observed installation, lint and format: PASS.

```text
Required test coverage of 90% reached. Total coverage: 95.62%
75 passed, 3 warnings in 17.95s
```

Observed demo table:

```text
| People | Requests | Algorithm | Scheduled | Priority | Gap-min | Spread-min | Solve-s | Priority status |
|---:|---:|:---|---:|---:|---:|---:|---:|:---|
| 5 | 12 | greedy-first-fit | 8 | 18 | 120 | 60 | 0.001 | n/a |
| 5 | 12 | cp-sat | 10 | 20 | 30 | 60 | 0.031 | OPTIMAL |
```

An additional import probe verified that `schedule_solver.__file__` resolves
inside the clean clone, not the original working tree. The warnings were upstream
Starlette/httpx and bool-inversion import deprecations; none was suppressed.
Only documentation changed after the checked commit.
