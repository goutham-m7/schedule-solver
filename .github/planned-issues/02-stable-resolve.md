# Stable incremental re-solving

Milestone: v0.2.0

## Problem
A small edit currently allows unrelated assignments to move.

## Acceptance criteria
Expose a stateless Python and HTTP re-solve operation using an edited workload and previous meetings; maximize priority, then minimize changed existing meeting assignments before existing tie-breakers. Validate previous IDs, times and attendance. Add/move/cancel are workload edits, not a separate mutable store.

## Test plan
Real solver tests for addition, cancellation, forced moves, team changes, malformed previous assignments and HTTP validation.
