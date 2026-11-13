# Interoperable solved schedule export

Milestone: v0.2.0

## Problem
Solved assignments cannot be imported into a calendar client.

## Acceptance criteria
Export UTC VEVENTs with deterministic UID, escaped summaries and attendee IDs through Python, CLI and HTTP; validate assignments against workload before exporting.

## Test plan
Round-trip with icalendar and busy importer; special characters, stable IDs, empty schedules, invalid results and CLI/HTTP contracts.
