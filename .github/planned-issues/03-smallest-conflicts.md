# Minimum-cardinality conflict certificates

Milestone: v0.2.0

## Problem
Deletion-minimal cores can be larger than the smallest useful explanation.

## Acceptance criteria
For at most 12 constraint labels, enumerate smaller subsets and prove smallest cardinality; retain deletion-minimal certificates for larger universes with an explicit guarantee field. Never claim minimality on diagnostic timeout.

## Test plan
Enumerate all smaller subsets independently for small cases; test deterministic ties, fallback and insertable results.
