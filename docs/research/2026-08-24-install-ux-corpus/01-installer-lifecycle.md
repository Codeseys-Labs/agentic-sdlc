# 01 — Current Install Architecture, End to End

Repo: `/tmp/asdlc-research` (Codeseys-Labs/agentic-sdlc, v0.7.4, HEAD `e0fbf92`).
Method: files read directly. `mise` was never invoked as a task runner (config deliberately left
untrusted); the `mise WARN ... not trusted` line in shell output is incidental noise from the
ambient mise shim, not a task run.

Every claim below carries a `path:line` citation. Claims I could not verify by execution are
marked **UNVERIFIED** with the reason.

---

## (a) The exact layer diagram today

### A.1 There are four independent *acquisition* planes, not one

| # | Acquisition plane | Entry command(s) | What lands on disk | Needs mise trust? | Needs a tree on disk? |
|---|---|---|---|---|---|
| 1 | Hand clone | `git clone` + `cd` (`README.md:11`, `README.md:320-326`) | full checkout incl. `.git`, `tests/`, `docs/` | yes (`README.md:332-338`) | yes |
| 2 | Managed fetch | `scripts/bootstrap-agentic-sdlc.sh` (`README.md:285-291`) | clone at `${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc` + receipt at `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/bootstrap-receipt.json` (`scripts/bootstrap-agentic-sdlc.sh:26-29`) | yes, printed as step 2 of its handoff (`scripts/bootstrap-agentic-sdlc.sh:266-267`) | yes |
| 3 | Versioned mise release (prerelease, EXACT-VERSION ONLY) | `[tools."github:Codeseys-Labs/agentic-sdlc"] version = "0.7.4", prerelease = true` + `mise install` (`README.md:266-276`) | release tree with **no `.git`**; exposes exactly one command, `bin/ccodex` (`README.md:269-274`, payload allowlist `policy/release-candidate.v1.json` → `payload.trees` includes `bin`, `scripts`, `skills`, `plugin`, `policy`, `assets`, `hooks`, `workflows`, `agents`, `commands`) | yes, on the release tree's own `mise.toml` (`README.md:270-272`, `bin/ccodex:114-137`) | yes |
| 4 | Claude Code marketplace | `claude plugin marketplace add <git url>` + `claude plugin install agentic-sdlc@agentic-sdlc` (`README.md:852-855`) | `plugin/` copied into Claude's versioned plugin cache; `extraKnownMarketplaces` + `enabledPlugins` written to user settings (`README.md:857-859`) | **no** — "needs no clone, no mise, and no toolchain trust step" (`README.md:848-849`) | no |

Plane 4 is mutually exclusive with the direct Claude bundle install: `marketplace_overlap()`
detects it and blocks the whole Claude plane (`scripts/install_skill_bundle.py:939-955`,
`:1328-1342`; doctrine at `README.md:840-844`, `AGENTS.md:614-616`).

### A.2 The install layers, in the order the README puts them

```
LAYER 0  BOOTSTRAP PREREQUISITE
  mise >= 2026.4.27                       mise.toml:1   README.md:389
  (git is a "runtime-readiness capability", not a 2nd prerequisite  README.md:320-321)
        |
LAYER 1  TRUST  (persistent, per-absolute-config-path, operator-only)
  mise trust ./mise.toml                  README.md:12, 332-338
  never performed by any script:          bin/ccodex:111-137   README.md:306-309
        |
LAYER 2  TOOLCHAIN  (12 pinned tools, ~1.3 GB)
  mise --locked install                   README.md:13, 344-352
  [settings] locked = true                mise.toml:3-4
  tools: uv 0.12.5, lefthook 2.1.10, node 22.23.2, bun 1.4.0, npm 10.8.1,
         ripgrep, fd, jq 1.8.2, gh        mise.toml:14-35
         npm:@os-eco/seeds-cli 0.5.15     mise.toml:37-39
         github:betterleaks 1.8.1         mise.toml:44-45
         npm:@bitkyc08/opencodex 2.28.0   mise.toml:69-71   (installed BY DEFAULT, ADR-0005)
  auto_install is on, so skipping this step does not avoid the cost  README.md:346-348
        |
LAYER 3  BUNDLE ENTRIES  ->  ~/.claude  and  ~/.codex
  mise run bundle:install                 mise.toml:78-81    (defaults to --agent all)
  mise run bundle:install -- --agent claude|codex            README.md:359-363
  scripts/install_skill_bundle.py
        |
LAYER 4  PATH SURFACE  ->  ${XDG_BIN_HOME:-$HOME/.local/bin}
  mise run operator-tools:install          mise.toml:158-161
  scripts/install_operator_tools.py  installs exactly 2 files:
     agentic-sdlc-statusline, ccodex       scripts/install_operator_tools.py:30
        |
LAYER 5  SEPARATELY-AUTHORIZED ACTIVATIONS (each installed-but-inert until run)
  mise run claude:statusline:activate      mise.toml:212-215
  mise run claude:hooks:activate -- --hook <name>            mise.toml:227-230
  mise run claude:workflows:activate -- --workflow <n> --target <repo>   mise.toml:242-245
  mise run libraries:install <name> --yes  mise.toml:192-195
        |
LAYER 6  GATEWAY PLANE (never a gate, never a dependency)
  scripts/opencodex-claude.sh  {ensure|launch|launch-ultracode|status|restart|configure}
                                           scripts/opencodex-claude.sh:2641-2681
  reachable as mise run ocx:*              mise.toml:252-270
  or as ccodex <verb>                      assets/launchers/ccodex.in:380-409
        |
LAYER 7  CONTRIBUTOR-ONLY
  mise run hooks:install (lefthook)        mise.toml:300-302
  mise run contributor:setup = bundle:install + hooks:install   mise.toml:304-306
  mise run setup -> deprecated forwarder   mise.toml:308-310
  mise run check = validate + test + self-test + secrets        mise.toml:154-156
```

The 5-line install block at the top of the README is exactly Layers 1→4
(`README.md:10-16`).

### A.3 What Layer 3 discovers and where each kind lands

Discovery is a fixed, sorted glob set (`scripts/install_skill_bundle.py:596-618`):

| Source glob | Kind | Claude destination | Codex destination |
|---|---|---|---|
| `skills/*/SKILL.md` → parent dir | `skill` (the only *tree* kind, `:74`) | `<home>/.claude/skills/<name>` | `<codex_home>/skills/<name>` |
| `agents/claude/*.md` | `agent` | `<home>/.claude/agents/<name>.md` | — |
| `agents/codex/*.toml` | `agent` | — | `<codex_home>/agents/<name>.toml` |
| `commands/*.md` | `command` (Claude-only, `:71`) | `<home>/.claude/commands/<name>.md` | — |
| `workflows/*.js` | `workflow` (Claude-only) | `<home>/.claude/workflows/<name>.js` | — |
| `hooks/*.sh` | `hook` (Claude-only) | `<home>/.claude/hooks/<name>.sh` | — |

Kind→collection is one table (`:63-69`) and everything downstream reads it rather than branching
per kind ("a kind is added here and nowhere else", `:60-62`).

Measured counts in this checkout: 13 skills, 8 `agents/claude/*.md`, 8 `agents/codex/*.toml`,
5 `commands/*.md`, 1 `workflows/*.js`, 1 `hooks/*.sh`. So `discover_entries()` yields **49 Entry
objects** (13 skills × 2 planes = 26, plus 8 + 5 + 8 + 1 + 1); `--agent claude` selects 28,
`--agent codex` selects 21.

Destination root selection: Claude entries get `config.home / ".claude"`; Codex entries get
`config.codex_home` **directly** (no `.codex` component appended) —
`scripts/install_skill_bundle.py:297-302`, `:621-628`.

Mode: `auto` (default) tries a link and falls back to copy on OSError; `link` is strict and
re-raises; `copy` never links (`:857-870`). On Windows, directories become junctions and files
become file symlinks (`:845-855`). README states the same at `:493-495`.

### A.4 What Layer 4 installs, and what it binds at install time

`desired_files()` (`scripts/install_operator_tools.py:320-373`) renders exactly two files:

1. `agentic-sdlc-statusline` — verbatim bytes of `assets/claude/statusline-command.sh`.
2. `ccodex` — `assets/launchers/ccodex.in` with **six** install-time substitutions:
   `@PINNED_BASH@` (the shebang, unquoted), `@CANONICAL_ROOT@`, `@CANONICAL_LAUNCHER@`,
   `@PINNED_OCX@`, `@PINNED_JQ@`, `@PINNED_UV@`, `@PINNED_NODE@`, `@PINNED_SDLC_PYTHON@`
   (`:350-361`; template placeholders at `assets/launchers/ccodex.in:1`, `:53-58`).

Each binding is resolved before any byte is written:

- bash: first admissible absolute candidate from the **closed** list `(/usr/bin/bash, /bin/bash)`,
  rejecting whitespace-bearing and non-executable paths, nothing executed
  (`scripts/install_operator_tools.py:49`, `:209-239`).
- `ocx`, `jq`, `uv`, `node`: `mise -C <repo_root> which <tool>`, then re-checked as an executable
  regular file (`:242-266`). `node` is bound because the pinned `ocx` is a
  `#!/usr/bin/env node` script (`:334-339`, `assets/launchers/ccodex.in:63-72`).
- sdlc Python: `uv python find --managed-python --no-config --no-project --offline
  --no-python-downloads 3.12.11`, then executed with `-I -B` to assert the version is **exactly**
  `3.12.11` (`:269-317`).

Files are written mode `0o755` (`:629`, `:637`) into `config.bin_dir`, default
`${XDG_BIN_HOME:-$HOME/.local/bin}` (`:101-103`).

### A.5 Two `ccodex` dispatchers exist, and they are deliberately different

| | `bin/ccodex` (committed) | rendered `ccodex` (installed) |
|---|---|---|
| Shebang | `#!/usr/bin/env bash` (`bin/ccodex:1`) | absolute pinned bash (`assets/launchers/ccodex.in:1`) |
| Root resolution | self-located: parent of its own `bin/` (`bin/ccodex:32-37`) | `${AGENTIC_SDLC_ROOT:-@CANONICAL_ROOT@}` (`ccodex.in:53-59`) |
| Tool resolution | `mise -C <root> exec --` per call (`bin/ccodex:141-155`) | absolute install-bound paths; no mise (`ccodex.in:61-73`, `:165-196`) |
| Needs mise at run time | yes for every verb except `version`/`--help` (`bin/ccodex:111-137`, `:321-331`) | no (`ccodex.in:41-44`) |
| `set-fast-model` bare | refused, exit 3 (`bin/ccodex:255-259`) | interactive selector (`ccodex.in:297-354`) |
| sdlc Python | asks pinned uv, and will `uv python install 3.12.11` if absent (`bin/ccodex:169-187`) | uses the install-bound interpreter, exit 3 if gone (`ccodex.in:185-196`) |

The three divergences are declared in the committed file's own header (`bin/ccodex:9-22`).

### A.6 Layer 6's shape

`scripts/opencodex-claude.sh` is 2681 lines and dispatches six verbs
(`:9`, `:2641-2681`). Structural summary:

- Root/state: `root` from `BASH_SOURCE`, logs at `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/ocx-logs`, outer readiness bound 15s / 1s poll (`:92-108`).
- Help interception before any effect (`:110-146`, `:2646-2650`); `--` disables it and forwards verbatim (`:148-153`, `:2655-2660`).
- Tool routes: `ocx()` prefers `$AGENTIC_SDLC_OCX` else `mise -C $root exec -- ocx` (`:397-415`); `launch_ocx_claude()` resolves then execs directly from the caller's workspace (`:416-430`).
- `jq()` admits exactly two routes — an **absolute** `$AGENTIC_SDLC_JQ`, or the pinned `mise exec` route — and maps anything else (bare name, relative path) to an `unadmitted` sentinel returning 127 (`:431-493`). `jq_available()` is deliberately uncached (`:494-505`).
- Supervision delegated to `ocx ensure|restart|stop`; `ocx health` is the **only** health verdict (`:33-43`, `:584-590`).
- Route-integrity refusals (`:981-1648`) classify env vars, three classes of settings document, and explicit `--settings` values; refusal exits 3 (`:565-582`).
- Subcommand bodies at `:1650-2639`, incl. `cmd_launch` (`:1683`), `cmd_launch_ultracode` (`:1792`), `cmd_status` (`:1843`), `cmd_configure` (`:2532`).

### A.7 A fifth, parallel lifecycle exists: `ccodex sdlc`

`scripts/ccodex_sdlc.py` owns a *closed* grammar of reader verbs
(`inspect|status|doctor|recover`, `:31`) plus three mutating verbs
(`install --host claude`, `update`, `uninstall`, `:44-48`) with `install` requiring an explicit
host and no wildcard (`:50-51`). `recover --apply <plan-sha256>` is digest-approved (`:52-58`).

Its module docstring says the per-verb modules "are absent today, so every mutating verb refuses
BY NAME at exit 3" (`:44-48`) — but `scripts/ccodex_sdlc_install.py` (1999 lines),
`ccodex_sdlc_update.py` (2581), `ccodex_sdlc_uninstall.py` (1391) and `ccodex_sdlc_recover.py`
(926) all exist on disk. **The docstring is stale relative to the tree.**

`ccodex sdlc install --host claude` is a *separate* activation lifecycle over the same
`install_skill_bundle` transactional primitives: it admits one sealed acquisition receipt,
copy-activates Claude entries (copies, never links), and seals one
`distribution-activation@1` receipt plus an `active-receipt.json` pointer
(`scripts/ccodex_sdlc_install.py:20-64`). Its home is hardcoded `Path.home()`
(`:415`), state under `XDG_STATE_HOME/agentic-sdlc/{acquisition,activation}` and payload under
`XDG_DATA_HOME/agentic-sdlc/acquisition/candidates` (`:203-211`, `:320-345`).

---

## (b) The ownership / state model

### B.1 Ownership is byte identity — and only byte identity

`entry_matches_record()` is "the whole ownership test"
(`scripts/install_skill_bundle.py:914-936`): mode agreement, plus the recorded link target for a
link/junction, plus `digest(destination) == record["digest"]` for a copy. There is no
`stat`/`statx` birth-time witness, no device/inode ownership token, and no settlement probe
anywhere in the module (`:8-15`). The one `stat`-vs-`stat` comparison left is
`_readonly_read_file`'s torn-read guard, which only decides whether a read-only *snapshot* is
stable (`:12-16`, `:1474-1495`).

Two consequences are stated rather than implied (`:17-26`, echoed at `README.md:805-811` and
`AGENTS.md:600-602`):

- A destination the operator **modified** is refused and preserved. That direction stays fail-closed.
- A destination the operator replaced with a **byte-identical** copy of the payload IS removed by
  uninstall. Declared as an "accepted, honestly weaker doctrine."

`digest()` is a length-prefixed, node-typed, sorted `rglob` stream so the byte stream is
prefix-free and a boundary splice cannot forge a sibling's header (`:700-727`). Directory kinds
must be directories and file kinds must be files, so an empty dir cannot match an empty file's
digest (`:927-932`).

Adoption has two shapes, and they differ in removability:
- an exact legacy link to the same source → `removable: True`, reported `adopted:` (`:1386-1406`)
- a byte-identical (CRLF/LF-tolerant, `:730-737`, `:755-775`) copy → `removable: False`, reported
  `adopted (preserved on uninstall):` (`:1407-1416`), and `uninstall` reports
  `kept: … (adopted pre-existing entry)` (`:1722-1724`).

### B.2 Six independent state stores (plus one foreign lock that is only ever read)

| Store | Path | Schema version | Lock | Source |
|---|---|---|---|---|
| Bundle entries | `<state_dir>/agentic-sdlc-installer/state.json`, mode `0600` | `4` | `installer.lock` sibling, `flock`/`msvcrt` | `install_skill_bundle.py:127-135`, `:58`, `:547`, `:557-593` |
| Operator commands | `<state_root>/agentic-sdlc-operator-tools/state.json`, mode `0600` | `2` (accepts `1`) | `<state_root>/agentic-sdlc-operator-tools/lock` | `install_operator_tools.py:84-89`, `:24-25`, `:429-430`, `:495-507` |
| Statusline | `<state_root>/agentic-sdlc-claude-statusline/receipt.json` | — | — | `manage_claude_statusline.py:61` |
| Claude hooks | `<state_root>/agentic-sdlc-claude-hooks/` | — | — | `manage_claude_hooks.py:72` |
| Claude workflows | `<state_root>/agentic-sdlc-claude-workflows/<name>.<sha256[:16]>.json` | `1` | `manager.lock` in that dir | `manage_claude_workflows.py:82-91`, `:102-110` |
| `ccodex sdlc` activation | `<state_home>/agentic-sdlc/activation/{active-receipt.json,receipts,plans,journals}`; acquisition at `<state_home>/agentic-sdlc/acquisition/receipts`, candidates at `<data_home>/agentic-sdlc/acquisition/candidates` | `distribution-activation@1` | — | `ccodex_sdlc_install.py:203-211`, `:383-397` |
| Bootstrap receipt | `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/bootstrap-receipt.json` | — | — | `bootstrap-agentic-sdlc.sh:27-29` |
| *(foreign, read-only)* skills-CLI lock | `$XDG_STATE_HOME/skills/.skill-lock.json` else `~/.agents/.skill-lock.json` | reads v`3` | — | `install_external_libraries.py:451-465`, `:468` |

`<state_dir>` for the bundle is `state_directory()`: on Windows `LOCALAPPDATA` else
`~/AppData/Local`; on Unix `XDG_STATE_HOME` else `Path.home()/.local/state`
(`install_skill_bundle.py:220-230`). **Note it uses `Path.home()`, not `config.home`** — so
`--claude-home <somewhere-else>` does *not* move the state document. That is pinned by
`tests/test_install_skill_bundle.py:819` (`test_default_state_path_does_not_follow_configured_home_alias`).

`legacy_state_path` is the home-relative spelling (`:132-135`, `:233-247`). `load_config_state()`
refuses outright if a *second* document exists in that legacy location and is not the same file
(`:1307-1318`), pinned by `tests/test_install_skill_bundle.py:1249`.

`install_external_libraries.py` owns **no** state of its own; it reads Claude's
`installed_plugins.json` / `known_marketplaces.json` and the competing channel's lock
(`:436-465`).

### B.3 Record schemas

Bundle record — a **closed seven-field** set, keyed by its own absolute destination
(`install_skill_bundle.py:76`, built at `:873-889`, validated at `:348-390`):

```
{ "agent": "claude"|"codex", "kind": <one of skill|agent|command|workflow|hook>,
  "name": <basename, not "" "." "..">, "source": <absolute str>,
  "mode": "copy"|"link"|"junction", "digest": <64 lowercase hex>, "removable": bool }
```

Structural validation is deliberately ordered so an unhashable `kind` (a JSON list/object) is a
*refused record* rather than a `TypeError` traceback (`:357-361`). The key must be absolute, its
basename must equal `name`, its parent must be the kind's collection, and for Claude its
grandparent must literally be `.claude` (`:372-379`). A `codex` record carrying a Claude-only kind
is refused (`:367`).

Operator-tools record — a **closed three-field** set (`install_operator_tools.py:380-388`):
`{"path": <== key>, "digest": <64 hex>, "removable": "true"|"false"}` (note: strings, not bools).
Only `RECOGNIZED_COMMANDS` keys are admitted (`:30-32`, `:434`).

### B.4 Conflict semantics

Both installers use one vocabulary. Bundle side (`install_skill_bundle.py:1321-1431`,
`:1656-1688`, `:1691-1730`):

| Live state | `install` | `status` | `uninstall` |
|---|---|---|---|
| absent + no record | `installed: <dest> (<mode>)` | not listed | — |
| record + digest match, copy, removable | `refreshed:` (unconditional refresh each run) | `ok:` | `removed:` |
| record + digest match, copy, `removable=false` | `ok (preserved on uninstall):` | `ok:` | `kept: … (adopted pre-existing entry)` |
| record + link, source changed | `retargeted: <dest> (<mode>)` | `ok:` | `removed:` |
| record + digest mismatch | `conflict:` + `preserved:` , exit 1 | `conflict:` , exit 1 | `conflict:` + `preserved:` , exit 1 |
| record + destination gone | republish (record retired first) | `absent:` , exit 1 | `absent:` + record forgotten |
| no record + exact legacy link | `adopted:` (or `replaced link with copy:` in copy mode) | — | — |
| no record + byte-identical copy | `adopted (preserved on uninstall):` | — | — |
| no record + anything else present | `conflict:` "a non-bundle entry already exists", exit 1 | not listed | — |
| Claude marketplace overlap | `marketplace overlap:` + `preserved:`, whole Claude plane skipped, exit 1 | same, counted as 1 conflict | not checked |

Every conflict line is a *pair*: the name, then a `preserved: … (reason; inspect and resolve it
before retrying)` next step (`:152-158`). Every write command ends in one terminal summary
(`:170-202`); `status` always ends in one counted line, or the
`no owned entries for this host (run: mise run bundle:install)` line (`:1441-1445`). Partial
success is exit **1**, fatal is exit **2** (`:1431`, `:1839-1841`).

Operator-tools adds `unmanaged:` as a distinct fact from `absent:` (`:666-684`) and a whole
alias sub-vocabulary: `kept historical alias (unmanaged|adopted pre-existing entry|changed since
install)`, `retirable historical alias`, `historical alias ownership record retained; file is
missing` (`:685-703`, `:708-753`).

### B.5 Crash consistency: exactly one armed `pending` slot

Both modules use the same shape: arm the intended transition durably → move the bytes → commit;
a later run reads the *live* bytes and decides commit/abort by comparing them to the armed
`before`/`after` (`install_skill_bundle.py:33-36`, `:1069-1177`;
`install_operator_tools.py:514-554`, `:568-588`).

Three operations only: `install|refresh|uninstall` (`install_skill_bundle.py:78`,
`install_operator_tools.py:395`). `validate_pending` cross-checks each against the live `entries`
map (`install_skill_bundle.py:403-444`, `install_operator_tools.py:391-417`). One deliberate
divergence is documented in-line: the bundle's `refresh` does **not** require `before != after`,
because a copy-mode entry is refreshed on every run, whereas operator-tools *does* require
differing digests (`install_skill_bundle.py:431-437` vs `install_operator_tools.py:410-411`).

A second divergence: when the live bytes match neither recorded record, the bundle **reports and
preserves** (`install_skill_bundle.py:1165-1173`), whereas operator-tools **raises**
(`install_operator_tools.py:541-542`).

`publish()` uses the strongest single move available; a directory on either side forces a
rename-aside pair, and the interval between the two renames is the one accepted window. A crash
inside it parks the old tree at `.<name>.old-*` and the next run *names* it — never deletes it
(`:1033-1066`, `:993-1015`). `transactional_delete` renames aside, commits, then removes
(`:1265-1287`).

Durability: `atomic_write` = `durable_mkdir` → `mkstemp` sibling → `fchmod` → write → flush →
`F_FULLFSYNC` on Darwin / `fsync` elsewhere → `os.replace` → parent-dir fsync
(`install_skill_bundle.py:507-540`). A barrier failure raises `DurabilityError` and stops the
mutation (`:452-463`). Windows has no parent-dir barrier, so it claims process-crash recovery
only (`:468-471`; `README.md:830-831`; `AGENTS.md:595-599`).

---

## (c) Every invariant the code deliberately protects

Grouped; each is something a redesign must preserve or consciously drop.

### C.1 Fail-closed / refuse-rather-than-guess

1. **One ownership schema, no migration.** A document with any other `version` is refused by name
   with the remedy "remove it and reinstall"; bytes are never rewritten. There is no
   `--migrate-state` flag (`install_skill_bundle.py:266-289`; pinned by
   `tests/test_install_skill_bundle.py:367,1192,1216,1232`; doctrine `README.md:813-818`).
2. **Second state document → refuse.** A doc in the legacy location that is not the same file is
   fatal (`install_skill_bundle.py:1307-1318`; test `:1249`).
3. **Unknown top-level state field → refuse** (`:285-288`; test `:1232`).
4. **Malformed record → refuse before any destination is examined**
   (`:393-400`, `:348-390`; tests `:685`, `:703`).
5. **Inadmissible armed transition is refused rather than persisted** (`:1078-1094`; test `:1779`).
6. **Collection root must not be a link, and the boundary is asserted BEFORE the destination is
   read**, so a collection replaced with a link is refused by name rather than followed
   (`:631-654`, called at `:1345`, `:1675`, `:1712`; tests `:479`, `:498`).
7. **Destination must not escape the configured agent root** (`:651-654`; test `:661`).
8. **Post-publish validation.** Every create/replace re-proves `entry_matches_record` on the
   published bytes and raises `PublicationConflict` otherwise (`:1215-1216`, `:1253-1254`).
9. **`rename_absent` refuses rather than clobbers** (`:1018-1030`; test `:932`).
10. **Codex home must not be the repository root** (`:1824-1830`); **empty `CODEX_HOME` is fatal**
    (`:1817-1820`; test `:347`).
11. **Duplicate `--agent` selectors are rejected** so fixed mise tasks cannot be overridden
    (`:93-99`; test `:351`).
12. **Strict `link` mode never silently falls back to copy** (`:862-870`; test `:312`).
13. **Marketplace overlap blocks the Claude plane** rather than co-installing (`:939-955`,
    `:1328-1342`; tests `:588`, `:608`).
14. **Operator-tools: unsubstituted template placeholder is fatal** — "it renders a file that
    installs cleanly and cannot exec" (`install_operator_tools.py:362-369`).
15. **Operator-tools: no admissible bash → exit 2, before any file is written**
    (`:209-239`; tests `:1494`, `:1558`).
16. **Operator-tools: pinned tool that is not an executable file → refuse** (`:264-266`;
    test `:384`, `:458`).
17. **Operator-tools: uv-managed Python must be exactly `3.12.11`, verified by executing it**
    (`:302-317`; test `:422`).
18. **Operator-tools: native Windows is refused first, before any `Path.home()` is evaluated**
    (`:1093-1099`).
19. **Operator-tools: unsafe bin dir refused** — filesystem anchor, the repo root, or anything
    under it; non-physical directory; ancestor not owned by the current uid (`:181-202`;
    test `:216`).
20. **Launcher: `ocx health` is the only health verdict**; no `ocx` verb's exit code is ever
    accepted (`opencodex-claude.sh:40-43`, `:584-590`).
21. **Launcher: `jq` is never resolved from ambient PATH.** Only an absolute
    `$AGENTIC_SDLC_JQ` or the pinned `mise exec` route; a bare name or relative path becomes
    `unadmitted` → 127, and every consumer takes its own named fail-closed branch. No silent
    substitution either way (`:431-493`).
22. **Launcher: a setting that would defeat the gateway route → exit 3 before the gateway starts**
    (`:565-582`, `:981-1648`).
23. **`ccodex set-fast-model <provider>/<id>`: a provider the live gateway does not serve is
    REFUSED (exit 3), because the gateway would forward it to the DEFAULT provider and bill the
    wrong account** — but an *unreadable* catalog WARNS and proceeds, deliberately weaker than
    launch's refusal (`assets/launchers/ccodex.in:244-295`).
24. **`bin/ccodex`: a missing script/entry file is refused by name before mise is consulted**
    (`bin/ccodex:141-150`, `:169-175`).

### C.2 Never-edits-PATH, never-trusts, never-runs-what-it-installs

25. **The lifecycle never edits PATH and never creates a shell alias.** If the bin dir is absent
    from PATH the refusal names the directory and tells the operator to update shell config, start
    a new shell, and retry — and it is a *distinct exit class* (`3`,
    `HostPreconditionError`) reserved for exactly that one raise site
    (`install_operator_tools.py:56-63`, `:122-128`, `:187-190`, `:1120-1125`; epilog `:1052-1056`;
    tests `:174`, `:192`).
26. **The precondition check runs BEFORE the lock is taken**, because `lifecycle_lock` is itself an
    effect (`durable_mkdir` + `O_CREAT`) — "admitting it before the precondition check would make
    the 'before any effect' refusal untrue" (`:644-651`, `:756-760`, `:1032-1036`).
27. **No script ever runs `mise trust`.** `bin/ccodex` detects the untrusted config from a
    stdin-closed `mise tasks` probe and exits 3 naming the exact remedy
    (`bin/ccodex:111-137`, `:26-27`, `:328-330`); the bootstrap script prints trust as a step and
    does not run it (`bootstrap-agentic-sdlc.sh:13-15`, `:261-267`); README repeats the rule
    (`:306-309`, `:425-429`).
28. **Installing a `workflow` or a `hook` never runs it, enables it, reloads a host, or grants it
    authority.** For hooks this is load-bearing twice: `~/.claude/hooks/` is not an
    auto-discovery surface, so wiring into `settings.json` is a separate authorized step
    (`install_skill_bundle.py:305-320`; tests `test_hook_entry_kind.py`,
    `test_workflow_entry_kind.py`).
29. **The statusline is not activated by installation** (`README.md:779-781`); activation mutates
    only `statusLine.type` and `statusLine.command` (`README.md:790-793`), and
    `exact_owned_statusline()` refuses unless the exact owned bytes are installed and no pending
    transition exists (`install_operator_tools.py:557-565`).
30. **The bundle installer owns no shell aliases, no PATH, no global Claude settings**
    (`README.md:517-519`); the global settings document is read, never written, copied, or linked
    (`README.md:775-776`).
31. **Only the USE surface goes on PATH.** Maintenance verbs (`test`, `validate`, `check`,
    `secrets`, `self-test`, `mermaid:*`, `hooks:install`) are deliberately absent from `ccodex`
    (`assets/launchers/ccodex.in:23-31`, `:134-136`; `bin/ccodex:95-97`; test
    `tests/test_operator_tools.py:503`).
32. **No gate leaf reaches an opt-in installer.** `check` = `validate + test + self-test + secrets`
    (`mise.toml:154-156`); `contributor:setup` = `bundle:install + hooks:install`
    (`:304-306`); `libraries:*`, `mermaid:provision`, `rightsize:evaluate`, `usage:report` are
    explicitly outside every gate (`:183-186`, `:123-126`, `:272-275`, `:290-294`).
33. **Third-party libraries are never vendored**; installs go through each library's own front
    door and `install` refuses without an explicitly named library (`mise.toml:183-186`;
    `README.md:71-88`).
34. **Help is never a side-effecting operation** — at the launcher verb level
    (`opencodex-claude.sh:110-146`, `:2646-2650`), the dispatcher sub-verb level
    (`ccodex.in:366-377`, `bin/ccodex:213-218`), and `providers`/`models` are the two named
    exceptions because they take no options of their own (`README.md:605-607`). `version` and
    `--help` answer before mise, trust, or any download (`bin/ccodex:23-25`).

### C.3 Dry-run and read-only guarantees

35. **`--dry-run` writes nothing and takes no lock.** `install`/`uninstall` skip
    `installer_lock` entirely when dry (`install_skill_bundle.py:1434-1438`, `:1733-1737`);
    `write_state` early-returns (`:542-548`); `installer_lock` yields immediately
    (`:557-561`). Tests: `:297` (fresh host: neither home nor state created), `:788`
    (no mutators called at all), `:1816` (dry run over an armed transition writes nothing),
    `:236`, `:1241`.
36. **A read-only recovery report takes no durability barrier**, so a barrier failure cannot turn a
    report into a `DurabilityError` (`:1144-1148`; test `:1623`).
37. **`status` is lock-free** so a never-installed inspection creates nothing; operator-tools
    detects a racing writer by snapshotting the state document before and after the scan and
    reports `interrupted status: … retry` (`install_operator_tools.py:986-996`; test `:1256`,
    `:163`).
38. **`readonly_projection` never locks, migrates, repairs, or writes**, types malformed / racy /
    symlinked / ambiguous evidence as findings, and renders *locators*
    (`bundle-entry://<agent>/<kind>/<n>`) instead of state-owned paths so hostile state cannot
    reach a public report (`install_skill_bundle.py:1448-1471`, `:1502-1504`, `:1507-1634`;
    `install_operator_tools.py:771-983`; tests `:1293`, `:1330`, `:1367`).
39. **Ownership records for an earlier configured home are retained and left unselected**, never
    reinterpreted as a conflict (`install_skill_bundle.py:1572-1577`; test `:411`, `:1490`).
40. **`ccodex sdlc` readers install a process guard that blocks the lifecycle mutators** before
    projecting (`ccodex_sdlc.py:1443-1457`).
41. **`ccodex sdlc recover`: the approval IS the digest.** `--dry-run` renders a plan sha256;
    `--apply <sha>` re-derives and refuses by name when the digest differs
    (`ccodex_sdlc.py:52-58`; `ccodex.in:113-121`).

### C.4 Self-test

42. **`bundle self-test` runs install → status → uninstall in a throwaway home AND a throwaway
    state root**, and fails if any exit code is nonzero (`install_skill_bundle.py:1740-1758`;
    `mise.toml:141-144`; test `:1044`).
43. **`operator-tools self-test`** does the same with `require_path=False` and additionally asserts
    that no recognized command file survives (`install_operator_tools.py:1039-1046`;
    `mise.toml:178-181`; test `:251`).
44. **`self-test` is a leaf of the authoritative gate** (`mise.toml:154-156`), and lefthook's
    pre-push runs it too (`README.md:886-888`).

### C.5 Other structural invariants worth naming

45. `operational_path()` makes paths absolute **without** resolving aliases, links, junctions, or
    8.3 spellings (`install_skill_bundle.py:210-212`; test `:770`).
46. Junction creation rejects cmd.exe metacharacters (`:824-834`; test `:729`).
47. Private staging containers are `0700`, created **beside** the destination so `os.replace` stays
    a same-filesystem rename (`:958-970`); a published entry leaves no private sibling
    behind (test `:136`).
48. Leftover private siblings are named, never removed on the operator's behalf — "deleting it on
    their behalf would be this lifecycle throwing away the evidence of its own interruption"
    (`:993-1015`). The wording avoids the token "publication" because
    `tests/test_lifecycle_exit_conformance.py` scans rendered lines for authority-shaped tokens
    (`:1000-1002`).
49. Exit vocabulary is one derivation point per module and is conformance-tested:
    0 ok · 1 failure · 2 usage/grammar · 3 refused before effect · 4 admitted partial/unknown
    (`bin/ccodex:98-99`, `ccodex.in:138-139`;
    `tests/test_lifecycle_exit_conformance.py:789-1172`).
50. The `ccodex` PATH plane is deliberately **one file, not N commands**: one ownership record, one
    place a verb appears, no PATH namespace land-grab (`ccodex.in:23-31`).
51. `AGENTIC_SDLC_ROOT` lets a moved checkout be selected without reinstalling the dispatcher, but
    moving the mise tool store requires an explicit `operator-tools:install` refresh
    (`ccodex.in:46-52`, `:36-44`; `README.md:686-691`).
52. `ccodex` prepends the pinned node's directory to `PATH` for every child — and names the
    consequence that the same directory's `npm`/`npx`/`corepack` also precede the caller's,
    including inside a launched Claude Code session (`ccodex.in:63-73`).

---

## (d) Friction audit — where a fresh operator gets hurt

### D.1 The command count is 5, not 4, and the two documented sequences disagree

The headline block is 5 commands (`README.md:11-15`): clone, trust, `--locked install`,
`bundle:install`, `operator-tools:install`. The Quickstart section says **"Five steps"**
(`README.md:316`) and then lists **six numbered items** (`:320, 328, 332, 344, 354, 370`).

Worse, the two disagree on the most consequential argument:

- Headline: `mise run bundle:install` → task has no `--agent`, so `args.agent or "all"` selects
  **both** planes (`mise.toml:78-81`; `install_skill_bundle.py:1831`) → writes into `~/.claude`
  *and* `~/.codex`.
- Quickstart step 5: "**Choose an install plane explicitly**" with
  `bundle:install -- --agent claude` (`README.md:354-363`).

A fresh operator following the headline gets a Codex plane they did not ask for; one following the
Quickstart gets a different result from the same document.

### D.2 `operator-tools:install` requires PATH to already contain the directory

`validate_bin_dir` raises `HostPreconditionError` (exit 3) if
`${XDG_BIN_HOME:-$HOME/.local/bin}` is not in `PATH`
(`install_operator_tools.py:181-190`). The refusal is correct and deliberate (invariant #25), but
the recovery loop is: edit shell rc → **start a new shell** → re-run the mise task from the
checkout. That is three operator actions inserted mid-install, and on a host where
`~/.local/bin` is not pre-seeded into `PATH` it is unavoidable.

A smaller divergence: `README.md:372-373` and the CLI epilog (`:1052-1056`) both say the directory
must "already exist". The code does not require existence — it walks to the first existing
ancestor for the ownership/physicality checks (`:191-197`) and `_install` calls
`durable_mkdir(config.bin_dir)` (`:634`). Docs are stricter than code.

### D.3 `operator-tools:install` drags the entire gateway toolchain, and its remedy message is wrong

`desired_files()` resolves `ocx`, `jq`, `uv`, `node`, **and** a uv-managed CPython 3.12.11 before
writing a single byte (`install_operator_tools.py:330-340`). So an operator who wants nothing but
`ccodex bundle status` on PATH still needs the pinned `opencodex` 2.28.0 npm install (which pulls
`bun` 1.3.14, an 89 MB binary — `mise.toml:66-67`) installed and executable.

The Python resolution is `--offline --no-python-downloads` (`:283-292`), and on failure it says
"run `mise --locked install` in <repo_root>" (`:297-300`). But `mise --locked install` installs the
**uv binary**, not uv's managed CPython — nothing in `[tools]` pins a Python
(`mise.toml:14-35`). The interpreter appears as a side effect of the first
`uv run --python 3.12.11 --script …` (i.e. the first `bundle:*`/`validate`/`test` task). The
committed `bin/ccodex` handles the same gap correctly by running `uv python install 3.12.11`
(`bin/ccodex:176-185`); `install_operator_tools.py` does not.

Net effect: `operator-tools:install` run *before* any other uv-backed task on a cold host should
refuse with a remedy that will not fix it. **UNVERIFIED end-to-end** — inferred from
`--offline --no-python-downloads` plus the absence of a Python pin; not executed, because doing so
would require trusting `mise.toml`.

### D.4 Three-way split with no single "am I installed?" answer

Ownership lives in six stores (§B.2). The aggregated reader,
`ccodex sdlc inspect|status|doctor`, projects **only two** of them — operator-tools and the bundle
(`ccodex_sdlc.py:1453-1454`, `:1487-1488`). `grep -c 'statusline|manage_claude'
scripts/ccodex_sdlc.py` = **0**. So statusline, hooks, workflows, and external-library state are
invisible to the one command that looks like an inventory.

Answering "what is on this machine" today takes at minimum:
`bundle:status`, `operator-tools:status`, `claude:statusline:status`, `claude:hooks:status`,
`claude:workflows:status -- --target <repo>` (per repo), `libraries:status`, `ocx:status`.

### D.5 `bundle:status` cannot see a collision; you need a different command

`status` iterates only recorded entries (`install_skill_bundle.py:1666-1670`) and README says so
explicitly: "It does not inventory unowned names in a configured collection… use
`bundle:install -- --agent <…> --dry-run`" (`README.md:379-385`; test
`tests/test_install_skill_bundle.py:1072`,
`test_unmanaged_codex_skill_is_found_by_install_dry_run_not_owned_status`). A fresh operator with a
pre-existing `~/.claude/skills/agentic-sdlc/` therefore gets `no owned entries for this host` from
the command named "status", and must know to run `install --dry-run` to see the problem.

### D.6 Partial success is exit 1, so "did it work?" has no clean answer

Any single conflict makes the whole `install` exit 1 (`install_skill_bundle.py:1431`) while the
other 48 entries land fine. The README's success criterion is a *string*
(`N ok, 0 conflict, 0 absent`, `README.md:18`), not an exit code. A fresh operator with one
pre-existing skill directory sees a red exit on a substantially successful install.

### D.7 Installed-but-inert payloads

Three of the five entry kinds do nothing after `bundle:install`:

- **workflows** — `bundle:install` lands bytes in `~/.claude/workflows/`, but the live host
  discovers workflows **only** from a *project's* own `.claude/workflows/`, read once at session
  start. "Installing distributes bytes no session ever discovers"
  (`manage_claude_workflows.py:6-14`). Enabling requires
  `claude:workflows:activate -- --workflow <n> --target <repo>`, per repo
  (`mise.toml:242-245`), and every completed activation must state that the change only takes
  effect at the target's *next* session (`manage_claude_workflows.py:66-70`).
- **hooks** — `~/.claude/hooks/` is not an auto-discovery surface; wiring needs
  `claude:hooks:activate` (`install_skill_bundle.py:314-320`; `mise.toml:227-230`).
- **statusline** — installed by `operator-tools:install`, inactive until
  `claude:statusline:activate` (`README.md:779-788`).

None of these three tasks appears anywhere in the README (§D.8).

### D.8 Documentation drift a fresh operator will hit

- `README.md:463` claims "Every task this repository defines, so `mise tasks` never reveals an
  undocumented one." `mise.toml` defines **44** `[tasks…]` blocks; the table
  (`README.md:465-491`) omits eight: `release:build`, `claude:hooks:{status,activate,deactivate}`,
  `claude:workflows:{status,activate,deactivate}`, `usage:report`. `grep -c` for each of
  `release:build`, `claude:hooks`, `claude:workflows`, `usage:report` in `README.md` returns **0**.
- `assets/launchers/ccodex.in:23` states "There are 36 mise tasks". Actual: 44.
- `scripts/ccodex_sdlc.py:44-48` states the mutating-verb modules "are absent today"; all four
  exist (`scripts/ccodex_sdlc_{install,update,uninstall,recover}.py`).
- `README.md:316` "Five steps" vs six numbered items (§D.1).

### D.9 Other named sharp edges

- **A shell function or alias named `ccodex` silently shadows the installed command**; the symptom
  is `ccodex --help` printing the *wrapped tool's* help, and `which` does not detect it —
  only `type ccodex` does (`README.md:618-623`).
- **`mise trust` is per-absolute-path and is NOT inherited by linked worktrees**
  (`README.md:457-461`), so every worktree re-triggers the approval gate.
- **~1.3 GB before any bundle byte is written**, and skipping `mise --locked install` does not
  avoid it because `auto_install` fires on the first `mise run` (`README.md:344-348`).
- **A state document from another generation is a hard stop** whose only remedy is delete +
  reinstall (`install_skill_bundle.py:266-289`) — safe, but a bad first-upgrade experience.
- **Provider onboarding is a five-command ordered sequence** where step 3 (`ccodex restart`) must
  precede step 4 (`add-key`), and the upstream error for getting it wrong is
  `unknown provider` where it means *configured but not yet published*
  (`README.md:631-668`).
- **`ccodex restart` interrupts in-flight turns in every routed session and rewrites shared
  `~/.codex`** (`README.md:551`; `opencodex-claude.sh:63-65`).

---

## (e) What "project scope" would mean today

### E.1 There is no first-class project scope, but there are four partial paths

| Path | Repo-local target | State location | Status |
|---|---|---|---|
| `bundle:install --claude-home <repo>` | `<repo>/.claude/{skills,agents,commands,workflows,hooks}` | **user-global** (`~/.local/state/agentic-sdlc-installer/state.json`) | works mechanically; not documented, not intended |
| `claude:workflows:activate --target <repo>` | `<repo>/.claude/workflows/<name>.js` | user-global receipts | **the only designed project-scope path**, and only for the `workflow` kind |
| `claude:statusline:*` / `claude:hooks:*` `--claude-config-dir <repo>/.claude` | `<repo>/.claude/settings.json` | user-global receipts | undocumented accidental capability |
| `instruction-generator.py apply --target <repo>` | one marked block in `AGENTS.md` / `CLAUDE.md` / a nested `AGENTS.md` / a `claude_rule` file | none (evidence is Git history) | works, but no manifest ships |

### E.2 `--claude-home <repo>` is the closest thing, and it is a trap

`--claude-home`/`--home` sets the root under which `.claude` is created
(`install_skill_bundle.py:1794-1802`), and Claude destinations are exactly
`config.home / ".claude" / <collection> / <name>` (`:297-302`, `:621-628`). There is **no guard
against pointing it at a repository** — the only repo-root refusal in `main()` is for
`--codex-home` (`:1824-1830`).

But four things make it unfit as project scope:

1. **State is not repo-local.** `state_directory()` uses `Path.home()`, not `config.home`
   (`:220-230`), so ownership for a repo-local install is recorded in the *user's* global state
   document. Pinned deliberately by
   `tests/test_install_skill_bundle.py:819`. Two repos installed this way share one state file
   keyed by absolute destination — workable, but there is no per-project boundary, no
   per-project uninstall scope, and nothing a `.gitignore` can contain.
2. **The legacy-state check can fire spuriously.** With `--claude-home <repo>` and no
   `XDG_STATE_HOME`, `legacy_state_path` becomes
   `<repo>/.local/state/agentic-sdlc-installer/state.json` (`:233-247`); if anything ever puts a
   document there, every command becomes fatal `unexpected state location` (`:1307-1318`).
3. **The record validator hardcodes `.claude`** as the grandparent for Claude records
   (`:377-378`), so the scheme is `<anything>/.claude/...` — fine for a repo root, but it means
   "project scope" can only ever mean "a `.claude` dir inside the project", never a different
   layout.
4. **`mise run bundle:install -- --claude-home <repo>` still installs the Codex plane** into
   `<repo>/.codex` unless `--agent claude` is also passed — and `--codex-home` defaults to
   `--claude-home/.codex` (`:1803-1808`, `:1815-1822`).

### E.3 The one real project-scope design already in the tree

`scripts/manage_claude_workflows.py` is a worked example of what project scope looks like when it
is designed rather than emergent:

- The ownership unit is **one file in the target repository**: `<target>/.claude/workflows/<n>.js`
  (`:16-17`, `:98-99`).
- It is a **copy, never a symlink**, with three reasons stated: a repo-committed entry must be
  self-contained; a link would embed a user-specific absolute path (forbidden in distributable
  payload); and a later bundle refresh must not silently change what the target's sessions execute
  without new per-repo authorization (`:18-23`).
- Receipts are keyed by `(workflow, destination)` so the same workflow can be enabled in many
  targets (`:85-91`), but they live in the **user's** state root (`:82-83`) — the repo carries only
  the payload file.
- It refuses to place a workflow that is absent, unowned, or digest-drifted from its bundle
  ownership record, and refuses an occupied foreign destination (`:23-26`).
- It refuses a `--target` that resolves to the installed home plane itself (`:522-523`).
- Every completed verb states the session-start-snapshot fact (`:66-70`).

That is the template a general project scope would follow: repo-local payload, home-local receipt,
copies only, per-target key, refuse rather than adopt.

### E.4 Project scope was built once at repository level, then deleted

ADR-0022 ("Activate repositories through digest-approved plans") is `accepted` but **amended**:
decision items 1, 2, 3, and 7 "no longer bind" — the transaction engine, the tracked
`.agentic-sdlc/repo.toml`, the machine-local activation receipt, and the write-ready/
remediation-ready vocabulary "are deleted, and the files named in **Relates to** below no longer
exist" (`docs/adr/0022-…:3-10`). Confirmed: `skills/agentic-sdlc/tools/` contains no
`activation-planner.py`. `.gitignore:20-26` records the same removal and explicitly warns not to
re-add ignore rules for paths nothing writes (and keeps `.agentic-sdlc/rightsize/` deliberately
visible to Git, `.gitignore:27-29`).

What survives is items 4–6, carried by
`skills/agentic-sdlc/tools/instruction-generator.py`: greenfield/brownfield classification from
nine `CONTRACT_SURFACES` (`AGENTS.md`, `CLAUDE.md`, `mise.toml`, `lefthook.yml`, `.seeds`,
`docs/adr`, `.github`, `.gitlab-ci.yml`, `.agentic-sdlc` — `:53-64`), and `apply --target
--manifest --entry` which splices one marked block into a repo file, printing a unified diff and
requiring `--yes` (exit 3 without it, `:85-92`, `:313-336`). `--target` must be the repository
root; a subdirectory is refused by name (`:23-25`). It creates no directories. Four output kinds
exist — `root_agents`, `root_claude`, `subtree_agents`, `claude_rule` (`:49`) — so a
`claude_rule` entry *can* target a repo-local `.claude/` file, but no operator-facing manifest
ships (only `tests/` fixtures and `docs/evidence/waves/f194-w1/instruction-manifest.json`).

### E.5 The product spec already names scope as an explicit axis

`docs/plans/claude-code-first-harness/issues/08-choose-installation-and-update-experience.md:56-57`:
"Every host and scope is selected explicitly. Detection may suggest a value but never authorizes a
mutation, and there is no wildcard `--all` lifecycle operation." The adjacent research on the
upstream `npx skills` CLI records that its "noninteractive update auto-selects project scope when
it detects project skills, otherwise global"
(`docs/plans/claude-code-first-harness/research/npx-skills-cli-lifecycle.md:181`) — and the
harness disposition is to keep noninteractive mode "a presentation mode, never an approval mode".

So project scope is a *decided-but-unimplemented* axis: the spec requires it be explicit, the
workflow manager is the only implementation, and the general installer's `--claude-home` is an
undesigned side door whose state model does not follow it.

### E.6 Note: this repo's own `.claude/` is not installer-managed

`.claude/` in the checkout contains only `output-styles/bluf.md`. `.gitignore` reserves
`.claude/worktrees/` and `.claude/settings.local.json` (`:16-17`) — i.e. repo-local `.claude` is
already a live, partially-git-tracked surface with its own conventions that a project-scope
installer would have to coexist with.

---

## Appendix — invariants pinned by `tests/test_install_skill_bundle.py`

78 tests, 5 classes. Grouped by the invariant each protects (line = `def test…`).

**Discovery / shape** — `:91` only supported top-level payloads; `:904` an owned copy must have
the node type its kind implies; `:1030` a nested symlink is not equivalent to a regular file.

**Mode selection** — `:153` links when supported; `:312` auto falls back to copy but `link` is
strict; `:329` auto falls back for a failed Windows junction; `:636` Windows prefers junction for
dirs and symlink for files; `:729` junction rejects cmd metacharacters; `:1016` a read-only copy
installs without changing mode.

**Adoption / retarget** — `:168` owned link retargeted to the current repo; `:196` adopts an
identical copy and an exact legacy link; `:217`/`:236`/`:252` copy-mode replaces / dry-run
preserves / restores an exact legacy link; `:269` recognizes a Windows junction; `:277` adopts a
line-ending-only copy but preserves it on uninstall; `:870` a relative legacy symlink is adopted
and replaced without dereference damage.

**Byte-identity doctrine** (`ByteIdentityDoctrineTests`, `:1386`) — `:1394` tree digest refuses the
boundary splice; `:1424` a modified tree is refused and preserved; `:1446` an edited file *inside*
an owned tree is refused; `:1459` a byte-identical operator recopy is now removed (the accepted
weakening); `:1490` a repointed configured home removes an identical copy and preserves a different
one; `:1539` a relinked owned link is refused; `:1562` a recreated link to the same source is now
removed.

**Collection boundary** — `:479` rejects a linked collection root; `:498` a retargeted collection
link cannot redirect uninstall; `:661` uninstall rejects a noncanonical state destination; `:520`
the marketplace skip does not validate unused Claude collections.

**State schema** (`StateSchemaTests`, `:1186`) — `:1192` every retired schema refused without a
rewrite; `:1216` a newer schema refused without a rewrite; `:1232` an unknown top-level field
refused; `:1249` a second document in the legacy location is refused, not selected; `:1272`
`atomic_write` succeeds where `os.fchmod` does not exist; `:367` the CLI offers no state-migration
flag; `:387`/`:398` invalid state is fatal / exit 2.

**Ownership-record structure** — `:685` a record with an unknown field is refused before mutation;
`:703` a stale structural record has no deletion authority.

**Pending transitions** (`PendingTransitionTests`, `:1584`) — `:1595` install interrupted before
publish → abort; `:1643` after publish → commit; `:1669` refresh after publish → commit; `:1695`
uninstall after the aside rename → commit; `:1723` bytes matching neither record are preserved and
the leftover named; `:1758` a blocked transition does not stop the other entries; `:1779` an
inadmissible transition is refused rather than persisted; `:1816` a dry run over an armed
transition writes nothing; `:1623` a read-only recovery report takes no durability barrier.

**Publish primitives** — `:932` `rename_absent` refuses a destination that appeared; `:951`
replaces a file destination in one namespace operation; `:970` uses a named aside for a directory;
`:990` restores the previous tree when the swap fails; `:136` a published entry leaves no private
sibling behind.

**Dry run / read-only** — `:297` fresh host creates neither home nor state; `:788` calls no
mutators; `ReadOnlyProjectionTests` `:1293` reports an armed transition without a lock or write,
`:1330` types malformed and foreign evidence without repair, `:1367` healthy for an ordinary
installed plane.

**Home/plane selection** — `:347` rejects empty `CODEX_HOME`; `:351` rejects duplicate `--agent`;
`:379` explicit `--claude-home` alias; `:819` the default state path does **not** follow the
configured home alias; `:1163` a codex-home alias is an allowed configured root; `:411` a changed
codex home preserves old records and installs the new home; `:770` operational path spelling is not
resolved.

**Marketplace** — `:588` overlap skips only Claude; `:608` visible in status once and leaves Codex
readable.

**Convergence / partial failure** — `:447` persists earlier ownership when a later install fails;
`:542` uninstall removes an owned dangling link; `:559` install republishes a recorded destination
the operator deleted.

**Output contract** — `:1056` status on a clean host names the empty result and the next command;
`:1072` an unmanaged Codex skill is found by `install --dry-run`, not by owned `status`; `:1110`
status always ends with a counted summary line; `:1130` write summaries are terminal and conflicts
name preservation; `:1153` the status summary is terminal for every counted shape; `:356` CLI help
names configured roots, agent selection, and read-only modes.

**Integration** — `:734` the compatibility wrapper (`scripts/install-skill-bundle.sh`) preserves
lifecycle dispatch; `:1044` self-test runs an isolated lifecycle.
