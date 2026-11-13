# Bounded recurring calendar import

Milestone: v0.2.0

## Problem
Recurring busy events are rejected, so ordinary weekly calendars cannot be used.

## Acceptance criteria
Expand RRULE, RDATE and EXDATE inside an explicit horizon; preserve local wall times across DST; reject floating timestamps and detached overrides; bound expansion work.

## Test plan
ICS integration tests for exclusions, DST gaps/folds, all-day dates, clipping, invalid rules and expansion limits.
