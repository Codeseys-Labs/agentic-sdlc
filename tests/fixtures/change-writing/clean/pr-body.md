## Summary

Move feature-flag resolution to request entry and cache the snapshot for the
lifetime of the request, removing per-access network fetches on hot paths.

## Verification

- `mise run test` — full unittest suite green.
- `mise run check` — validator, tests, and self-test all pass.

## Risks and recovery

Snapshotting at entry means a mid-request flag flip is not observed until the
next request. Revert this commit to restore per-access resolution.
