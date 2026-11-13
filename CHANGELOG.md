# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-11-13

### Added
- Bounded RRULE/RDATE/EXDATE busy-calendar import with explicit horizons, DST-aware local recurrence, all-day dates and exclusion sets. Detached overrides and EXRULE fail closed.
- Stateless Python `resolve()` and HTTP `POST /resolve`: edit the complete workload to add, move or cancel requests, then minimize changed retained assignments after scheduled priority. Result metadata reports changed request IDs and stability pass status.
- Minimum-cardinality fixed-schedule insertion conflicts for universes of at most 12 constraint labels. Larger universes retain deletion-minimal certificates with an explicit guarantee field.
- Checked iCalendar export through Python `export_ics()`, CLI `solve --ics`, demo `schedule.ics`, and HTTP `POST /export-ics`. Independent assignment validation checks hard constraints before serialization.
- Synthetic independent-pod and connected-ring benchmark families through 500 people / 1200 requests, multiple search budgets, objective bounds and runtime metadata.
- Local wheel/sdist build verification and frozen fresh-clone installation evidence. Nothing published or tagged.

### Changed
- Workload limits expand to 500 people and 1200 requests; the seven-day horizon remains unchanged.
- API version comes from installed package metadata.
- Meeting timestamps normalize to UTC and validate interval order and minute precision.
- `python-dateutil` is an explicit runtime dependency rather than an incidental transitive dependency.

### Fixed
- DST recurrence COUNT excludes nonexistent local instances; repeated fall-back times select the first fold.
- DURATION applies nominal days before elapsed hours/minutes across offset transitions.
- Lexicographic handoff evaluates the returned assignment's integer objective expression instead of trusting a possibly stale time-limited OR-Tools objective summary.

## [0.1.0]

### Added
- Offline CP-SAT scheduling, independent greedy baseline, checked insertion conflicts, strict calendar validation, local FastAPI endpoints, CLI and static HTML calendar.
