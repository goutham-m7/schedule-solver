# Larger reproducible benchmark curves

Milestone: v0.2.0

## Problem
The generator and schema stop at 100 people and one search budget.

## Acceptance criteria
Support 200–500 people and 1200 requests; benchmark independent-pod and cross-pod contention families with multiple budgets, greedy comparison, bounds, timings and environment metadata.

## Test plan
Generator determinism and family topology tests; benchmark CLI integration; run measured 200/500-person curves without explanations.
