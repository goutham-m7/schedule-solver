# Roadmap

## v0.2.0

Local-only milestone. All workloads and measurements are synthetic. No remote operations.

### 01. Bounded recurring calendar import

- Status: complete.
- Problem: Recurring busy events are rejected, so ordinary weekly calendars cannot be used.
- Acceptance: Expand RRULE, RDATE and EXDATE inside an explicit horizon; preserve local wall times across DST; reject floating timestamps and detached overrides; bound expansion work.
- Test plan: ICS integration tests for exclusions, DST gaps/folds, all-day dates, clipping, invalid rules and expansion limits.
- Delivery commits: `d8c04e9` (implementation and tests).

### 02. Stable incremental re-solving

- Status: complete.
- Problem: A small edit currently allows unrelated assignments to move.
- Acceptance: Expose a stateless Python and HTTP re-solve operation using an edited workload and previous meetings; maximize priority, then minimize changed existing meeting assignments before existing tie-breakers. Validate previous IDs, times and attendance. Add/move/cancel are workload edits, not a separate mutable store.
- Test plan: Real solver tests for addition, cancellation, forced moves, team changes, malformed previous assignments and HTTP validation.
- Delivery commits: `7cc48f2` (implementation and tests).

### 03. Minimum-cardinality conflict certificates

- Status: complete.
- Problem: Deletion-minimal cores can be larger than the smallest useful explanation.
- Acceptance: For at most 12 constraint labels, enumerate smaller subsets and prove smallest cardinality; retain deletion-minimal certificates for larger universes with an explicit guarantee field. Never claim minimality on diagnostic timeout.
- Test plan: Enumerate all smaller subsets independently for small cases; test deterministic ties, fallback and insertable results.
- Delivery commits: `df1a735` (implementation and tests).

### 04. Interoperable solved schedule export

- Status: complete.
- Problem: Solved assignments cannot be imported into a calendar client.
- Acceptance: Export UTC VEVENTs with deterministic UID, escaped summaries and attendee IDs through Python, CLI and HTTP; validate assignments against workload before exporting.
- Test plan: Round-trip with icalendar and busy importer; special characters, stable IDs, empty schedules, invalid results and CLI/HTTP contracts.
- Delivery commits: `af7ebcf` (implementation and tests).

### 05. Larger reproducible benchmark curves

- Status: planned.
- Problem: The generator and schema stop at 100 people and one search budget.
- Acceptance: Support 200–500 people and 1200 requests; benchmark independent-pod and cross-pod contention families with multiple budgets, greedy comparison, bounds, timings and environment metadata.
- Test plan: Generator determinism and family topology tests; benchmark CLI integration; run measured 200/500-person curves without explanations.
- Delivery commits: pending.

### 06. Build and verify v0.2.0 distributions

- Status: planned.
- Problem: The release needs reproducible installation and documented contracts.
- Acceptance: Bump package and API version; build wheel and sdist locally, install wheel into an isolated environment and exercise entry point; refresh README, changelog and fresh-clone verification evidence. No publication or tags.
- Test plan: Full pytest, Ruff, build, isolated wheel CLI and fresh local clone install/test/lint/demo.
- Delivery commits: pending.

## Future work

Rooms/resource capacities, weighted time and back-to-back preferences, detached recurrence overrides, global rearrangement infeasibility proofs and authenticated production API deployment remain out of scope. The existing FastAPI API already supplies OpenAPI and strict request validation; extending its contracts is part of the items above, not a new REST scaffold.
