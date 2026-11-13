# Build and verify v0.2.0 distributions

Milestone: v0.2.0

## Problem
The release needs reproducible installation and documented contracts.

## Acceptance criteria
Bump package and API version; build wheel and sdist locally, install wheel into an isolated environment and exercise entry point; refresh README, changelog and fresh-clone verification evidence. No publication or tags.

## Test plan
Full pytest, Ruff, build, isolated wheel CLI and fresh local clone install/test/lint/demo.
