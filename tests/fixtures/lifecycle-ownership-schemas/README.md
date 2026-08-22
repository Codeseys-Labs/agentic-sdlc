# Installer ownership documents, one per schema generation

Three ownership-state documents, used by `tests/test_lifecycle_exit_conformance.py` to prove that
`ccodex sdlc`'s old-schema readers READ each generation without retrofitting it on disk.

| file | `version` | shape |
| --- | --- | --- |
| `v1.json` | 1 | `entries` only, and each record carries just `agent`, `digest`, `kind`, `mode`, `name`, `source` |
| `v2.json` | 2 | `entries` plus `transactions`, with the full record `install_skill_bundle.py` writes today |
| `v3.json` | 3 | byte-for-byte `v2.json` with `version` 3 -- the two generations differ only in that field |

The record shapes are the ones `scripts/install_skill_bundle.py` itself produces: the v2/v3 records
are the keys a real `ccodex sdlc install --host claude` writes, and the v1 records are exactly the
keys `v1_record_structure_valid` reads. The suite re-derives both key sets from the shipped module on
every run, so a fixture that drifts away from the installer fails rather than agreeing with itself.

Two placeholders are substituted per test, because a v1 destination key must be an absolute path and
an ownership record names its source by absolute path:

- `@CLAUDE_HOME@` -> the temporary plane's `<home>/.claude`
- `@SOURCE_ROOT@` -> the temporary plane's acquired candidate payload root

`stat-v2:...` identity tokens are placeholders too: physical identity is per-host and per-run, and no
reader under test in this module validates it. A test that needs real identity builds real state by
running the shipped installer instead of reading these files.
