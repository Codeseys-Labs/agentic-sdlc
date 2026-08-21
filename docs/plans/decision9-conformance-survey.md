# Implementation Decision 9 conformance survey — every command surface, measured

Dated 2026-08-21. Umbrella seed `agentic-sdlc-4253`.

## What this document is, and is not

Seed `agentic-sdlc-4253` was filed on 2026-08-18 as "converge the six nonconforming command
surfaces". Its **count is stale and its shape was wrong**, and this survey is the corrected
deliverable rather than a six-surface change:

* The seed asserts "two of eight command surfaces" conform. There are not eight command surfaces in
  this tree; there are **48 distinct, of which 46 are reachable on Linux and were measured** (see
  `§ The roster, exactly` for the exact arithmetic). Any convergence plan built on "eight known, six
  broken" would have closed the wrong set.
* The gate/activation family it names as the two conformers still conforms, and
  `agentic-sdlc-d7b3` has since converged `ccodex sdlc uninstall`/`recover`, so two of the seed's
  six presumed offenders are already closed.
* So the umbrella's deliverable is **enumeration + child-seed proposals**, not a code change.
  Exactly one worked example is fixed here (`§ Worked example`), under the umbrella's one-fix
  budget; every other deviation is queued as a `SeedProposal` paragraph at the end.

## The contract being measured

Verbatim from `docs/plans/claude-code-first-harness/agentic-sdlc-product-spec.md:219-222`:

> 9. **Effect-aware exits.** New lifecycle and control surfaces use: 0 for a valid query or closed
>    requested result; 1 for unexpected internal failure; 2 for grammar/schema/input error; 3 for
>    clean refusal before effect; and 4 after an admitted partial or unknown effect.

Two properties of that sentence govern every classification below.

1. **"New lifecycle and control surfaces"** is a scope, not a universal. A pre-Decision-9 surface
   that never claimed the contract is `NOT-APPLICABLE (out of scope)`, not `NONCONFORMING` — but a
   surface that *cites* Decision 9 in its own docstring has opted in and is judged against it.
2. **Classes 3 and 4 are conditional on having an effect to be before, or partway through.** A pure
   projection cannot honestly emit either. `skills/agentic-sdlc/tools/wave-verdict.py:2056` states
   the pattern the effect-free tools all follow:

   > "Implementation Decision 9's 3 and 4 do not apply: a command that causes no effect can [...]"

   Such a surface is `CONFORMING` with a 3-class vocabulary `{0,1,2}`; the absence of 3 and 4 is the
   contract being honoured, not a gap. The observability projection's `EPILOG`
   (`skills/agentic-sdlc/tools/sdlc-observability-projection.py:1850`) is the canonical statement.

A third property is a *derived* rule this survey applies and recommends every child seed adopt:
**codes above 4 are admissible only when named and justified as outside the reserved block.**
`scripts/gate_receipt.py:98-103` is the model:

> `5` and `6` sit outside that reserved block because the producer must also report a verdict it
> merely observed, and a gate's own exit code is never passed through: mirroring it would make a
> gate that exits `3` indistinguishable from the producer's refusal.

## How each surface was measured

Every row below is **executed**, not read. Each surface was driven on four axes, and the observed
exit recorded:

| axis | probe |
| --- | --- |
| success / valid query | `--help`, and where cheap a real valid invocation |
| grammar | no arguments; `--zzz-not-a-flag`; `no-such-verb` |
| input / schema | a supplied-but-**missing** path; a non-JSON file; a well-formed wrong-shape file |
| refusal (3) / partial (4) | a valid request against a target that must be refused; and, on a `/tmp` plane only, an interrupted effect |

The `--zzz-not-a-flag` and supplied-but-missing probes are the two that found every defect in this
survey, because they separate *not supplied* from *supplied and unusable* — the distinction Decision
9's 2-versus-1 boundary is made of.

One input-axis rule the conforming rows share, stated so a child seed does not invent a fourth
answer: a supplied-but-missing operand may legitimately land on **0 with a named MISSING reason**
(a pure projection whose contract is to report what it read — row 16), on **2** (the operand is
part of the command's input contract — most rows), or on **3** (the tool's contract names the
missing target a refusal — rows 13-14). What Decision 9 forbids is only landing it on **1**; each
surface must follow its own documented class, and that class must be documented.

Reproduce any row with, from the repository root:

```
uv run --python 3.12.11 <surface> <probe args>; echo "exit=$?"
```

## The roster, exactly

54 entrypoint files exist across `scripts/`, `skills/agentic-sdlc/tools/`,
`skills/codex-research-os/scripts/`, `skills/model-tier-rightsizing/scripts/`, and the shell
launchers (the first draft of this survey scoped itself to the first two directories plus the
launchers without stating the exclusion; the adversarial verification found three caller-facing
surfaces outside it, two of them nonconforming — rows 48-50). Two are PowerShell wrappers
(`scripts/run-git-bash.ps1`, `scripts/run-windows-mise.ps1`) that a Linux host cannot drive.
`scripts/activation_planner.py` and `scripts/instruction_generator.py` are `os.execv` forwarders
onto their canonical tool and so are the SAME surface, and `scripts/ccodex_sdlc_{install,update,
uninstall,recover}.py` are dispatcher-owned modules whose own `__main__` refuses any direct vector
("This module owns no grammar; it admits exactly the vector its dispatcher forwards",
`ccodex_sdlc_install.py:1764`) — the same non-surface class, judged through row 20. That gives
54 − 2 forwarders − 4 dispatcher-owned = **48 distinct surfaces**, of which **46 are Linux-reachable**.
`scripts/sanitize_mermaid_svg.mjs` is not counted: it is invoked only by the renderer wrapper and has
no caller-facing argument grammar.

## Disposition table

`exits observed` records the exit each probe actually produced. `—` means the axis is unreachable
for that surface by construction, not that it went unprobed.

| # | surface | success | grammar | input | refusal/partial | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `skills/agentic-sdlc/tools/wave-verdict.py` | 0 | 2 | 2 | — (effect-free) | CONFORMING |
| 2 | `skills/agentic-sdlc/tools/wave-submission.py` | 0 | 2 | 2 | — | CONFORMING |
| 3 | `skills/agentic-sdlc/tools/mission-contract.py` | 0 | 2 | 2 | — | CONFORMING |
| 4 | `skills/agentic-sdlc/tools/receipt-envelope.py` | 0 | 2 | 2 | — | CONFORMING |
| 5 | `skills/agentic-sdlc/tools/runtime-assignment.py` | 0 | 2 | 2 | — | CONFORMING |
| 6 | `skills/agentic-sdlc/tools/activation-result.py` | 0 | 2 | 2 | — | CONFORMING |
| 7 | `skills/agentic-sdlc/tools/auto-envelope.py` | 0 | 2 | 2 | — | CONFORMING |
| 8 | `skills/agentic-sdlc/tools/drift-classifier.py` | 0 | 2 | 2 | — | CONFORMING |
| 9 | `skills/agentic-sdlc/tools/planning-snapshot.py` | 0 | 2 | 2 | — (all-or-nothing write) | CONFORMING |
| 10 | `skills/agentic-sdlc/tools/wave-plan-compiler.py` | 0 | 2 | 2 | 4 declared | CONFORMING |
| 11 | `skills/agentic-sdlc/tools/wave-plan-admission.py` | 0 | 2 | 2 | 4 declared | CONFORMING |
| 12 | `skills/agentic-sdlc/tools/wave-journal.py` | 0 | 2 | 2 | 3, 4 declared | CONFORMING |
| 13 | `skills/agentic-sdlc/tools/repository-classifier.py` | 0 | 2 | 2 | 3 (`classify` against a `target does not exist`) | CONFORMING |
| 14 | `skills/agentic-sdlc/tools/repository-contract.py` | 0 | 2 | 2 | 3 (its verb against a `target does not exist`) | CONFORMING |
| 15 | `skills/agentic-sdlc/tools/repository-contract-writer.py` | 0 | 2 | 2 | 3, 4 declared | CONFORMING |
| 16 | `skills/agentic-sdlc/tools/sdlc-observability-projection.py` | 0 (incl. no-artifact and supplied-but-missing, distinguished in the BLUF) | 2 | 0 with a named unreadable reason | — (pure projection; EPILOG states it) | CONFORMING |
| 17 | `skills/agentic-sdlc/tools/pass-budget.py` | 0 | 2 | 2 | 3, 4 declared | CONFORMING |
| 18 | `scripts/gate_receipt.py` | 0 | 2 | 2 | 3, 4, plus named 5/6 outside the block | CONFORMING (the reference implementation) |
| 19 | `scripts/gate_baseline.py` | 0 | 2 | 2 | 3, 4, plus named 5 outside the block | CONFORMING |
| 20 | `scripts/ccodex_sdlc.py` | 0 | 2 (`unknown ccodex sdlc verb`, `accepts only optional --json`) | 2 | 3 (`blocked`, bound-Python refusal) | CONFORMING |
| 21-24 | `scripts/ccodex_sdlc_{install,update,uninstall,recover}.py` | dispatcher-owned — same surface as row 20; driven directly, each refuses ANY vector including `--help` at 3 (`admits exactly ['--host','claude']`), because the module owns no grammar (`ccodex_sdlc_install.py:1764`) | | | | NOT-APPLICABLE (judged through row 20; their 0/2/2/3/4 conduct under the dispatcher is row 20's, closed by `agentic-sdlc-d7b3`/`3bb8`) |
| 25 | `scripts/distribution_activation_receipt.py` | 0 | 2 | 2 | — (seal/validate are effect-free over one path) | CONFORMING |
| 26 | `scripts/install_skill_bundle.py` | 0 (`status`, `--dry-run`) | 2 (`--agent nope`) | 2 | 3, 4 declared | CONFORMING |
| 27 | `scripts/release_candidate.py` | 0 | 2 | 2 | 3, 4 declared | CONFORMING |
| 28 | `scripts/install_external_libraries.py` | 0 (`list`) | 2 | 2 | 3 declared | CONFORMING |
| 29 | `scripts/validate_bundle.py` | 0 | 2 | 2 | — (report-only) | CONFORMING |
| 30 | `scripts/bootstrap-agentic-sdlc.sh` | 0 (`--help`, `--print-path`, `--dry-run`, real fetch) | 2 (`unknown argument`, `--remote needs a value`) | 2 | 3 (credential-bearing remote, dirty tree, non-fast-forward) | CONFORMING |
| 31 | `scripts/muse-claude.sh` | 0 | 2 (`unknown subcommand`) | 2 | 3 declared | CONFORMING |
| 32 | `scripts/opencodex-claude.sh` | 0 | 2 (`unknown subcommand`) | 2 | 3 declared | CONFORMING |
| 33 | `scripts/activation_planner.py`, `scripts/instruction_generator.py` | forwarders — same surface as rows 41 and 42 | | | | NOT-APPLICABLE (`os.execv` onto the canonical tool) |
| 34 | `scripts/run-git-bash.ps1`, `scripts/run-windows-mise.ps1` | not drivable on Linux | | | | NOT-MEASURED (platform) |
| 35 | `scripts/bump-version.sh`, `scripts/install-skill-bundle.sh`, `scripts/validate-bundle.sh` | every probe exited 1 from `mise ERROR error parsing config file` before reaching the wrapper's own logic | | | | NOT-MEASURED (mise-gated; this survey may not invoke mise) |
| 36 | `scripts/run_all_hosts.py` | aggregate of two mise-gated host legs; `status` exited 1 from the WSL leg's mise failure | | | | NOT-MEASURED (mise-gated) |
| 37 | `skills/agentic-sdlc/tools/seeds-launcher.mjs` | 0 (`--help`/`-h` prints the usage line, performs nothing, and answers before the executing-Node admission; **was** 2 for `--help`) | 2 (unknown verb, no arguments, unadmitted record flag or flag value) | 2 (a supplied-but-missing `--target` or `--distribution`, distinguished from recorded state the launcher must re-read) | 3 for every clean pre-effect refusal (wrong Node, missing/partial/superseded receipt, tuple and hash drift, dirty distribution, occupied `.seeds`, compare-and-swap drift, prestate refusals) and 4 for `record`/`init` once a surface moved, including a post-writer readback divergence escalated by the effect ledger (**was** no 3 anywhere in the file, class 4 unreachable, and every one of these 2) | **CONFORMING** (closed by `agentic-sdlc-5a69`; the inspect verbs still report the Seeds child's own status, now named and justified as outside the reserved block in the module's own `EXITS` table) |
| 38 | **`skills/agentic-sdlc/tools/activation-planner.py`** | 0 | 2 | **1 (`status` traceback; `plan`/`apply` emit `status:refused, effect:none, exit_code:1`)** | 3, 4 exist but 86 certain + 2 indeterminate of 315 raise sites land on 1 | **NONCONFORMING** (SP-2), closed by `agentic-sdlc-3d9a` |
| 39 | `scripts/provision_mermaid_linux.py` | 0 (`--help` prints usage and provisions nothing; **was** a 358 MiB browser + `node_modules` download at 0) | 2 (**was** none — argv ignored) | — (accepts no arguments) | 3 pre-effect, 4 at or after `npm ci` (**was** neither) | **CONFORMING** (closed by `agentic-sdlc-bcdd`) |
| 40 | `scripts/secrets_scan.py` | 0 (`--help`, and a clean scan; **was** the whole scan for `--help` and `--zzz-not-a-flag`) | 2 (**was** none — argv ignored) | 2 (a path over the scanner's argv ceiling) | 3 (missing pinned config, absent `betterleaks`, failed enumeration; **was** 2); a found leak stays 1 | **CONFORMING** (closed by `agentic-sdlc-bcdd`) |
| 41 | `scripts/check-agentic-sdlc-prereqs.sh` | 0 (nothing missing); `--help` prints usage and runs no check (was argv-ignored, so `--help` ran the check too) | 2 (`--zzz-not-a-flag`; was none — argv ignored) | none | 5 for a completed check that names a MISSING prerequisite (was 1) | CONFORMING (closed by agentic-sdlc-d259) |
| 42 | `scripts/cmux-bus.sh` | 0 (`--help`/no-mode, now reachable without `cmux` on PATH; was unreachable without `cmux` and exited 1) | 2 | — | 3 for an absent `cmux`; 3 for "not inside cmux" (was 1 and a silent 0); a failed `cmux log` for `pub` now exits the named **6** (`EXIT_PUBLISH_FAILED`, outside the reserved block), never mirroring the child's own exit code (**was** mirrored, disclosed rather than translated) | CONFORMING (closed by agentic-sdlc-4d00; the `cmux log` translation landed under agentic-sdlc-d259) |
| 43 | `scripts/manage_claude_statusline.py` | 0 | 2 | 2 | 0 for all five read-only states, distinguished in the returned message rather than the code (was 1) | CONFORMING (closed by agentic-sdlc-d0a4) |
| 44 | `scripts/install_operator_tools.py` | 0 | 2 | 2 | 3 for the host precondition (`bin directory is not on PATH`), a new `HostPreconditionError` subclass so `main()` can tell it apart; 2 preserved for a genuine caller-input error (was 2 for both) | CONFORMING (closed by agentic-sdlc-92ff) |
| 45 | **`skills/agentic-sdlc/tools/instruction-generator.py`** | 0 | 2 | **1 + traceback for a supplied-but-missing manifest** | — | **NONCONFORMING** (SP-8) |
| 46 | **`scripts/render_mermaid_linux.py`** | **2 for `--help`, with no diagnostic at all** | 2 (silent) | 1 | 3 = unsupported platform | **NONCONFORMING** (SP-9) — help/grammar closed by `agentic-sdlc-61ce`; input axis still 1 (queued) |
| 47 | `skills/agentic-sdlc/tools/offline-inspect.py` | 0 | 2 | 2 | **was 1 for a derived NOT_READY** | **FIXED HERE** (worked example) |
| 48 | **`skills/codex-research-os/scripts/install_research_os.py`** | 0 | 2 | **1 with a raw `FileNotFoundError` traceback for `--target <missing> --dry-run`** (`:1441` `_open_root`, reached via `_apply_locked` `:2783`) | 3 declared | **NONCONFORMING** (SP-10) |
| 49 | **`skills/model-tier-rightsizing/scripts/receipt_admission.py`** | **none — argv ignored; `main()` (`:871`) reads stdin (`:874`), so `--help` returns `{"status":"invalid"}` at 2** | **2 for `--zzz-not-a-flag`, same path** | 2 | — | **NONCONFORMING** (SP-11) |
| 50 | `skills/model-tier-rightsizing/scripts/rightsize.py` | 0 | 2 | 2 | 3 declared (`evaluate` digest refusal) | CONFORMING |

The arithmetic closes exactly **as surveyed**. It is the original census and is deliberately not
recomputed each time a child seed closes, so a row's own verdict cell — not this paragraph — is the
current state. Rows 1-20, 25-32, and 50 were **29 conforming** surfaces. Rows 37-46
plus 48-49 were **12 nonconforming** surfaces and row 47 is **the one fixed here**. Rows 35 and 36 are
**4 unmeasurable** surfaces (3 mise-gated shells plus the mise-gated host aggregator):
29 + 12 + 1 + 4 = **46 Linux-reachable distinct surfaces**. Row 34's 2 PowerShell wrappers bring the
distinct roster to **48**. Rows 33 and 21-24 are listed for completeness and counted in neither
total: a forwarder or dispatcher-owned module is not a distinct surface — it is judged through the
tool that owns its grammar (rows 38, 45, and 20).

**The seed's "six" was an undercount of the offenders and an overcount of the work**: 12 surfaces
deviated, not 6, and the deliverable is 11 child seeds plus 1 worked example, not a six-surface change.

## Worked example: `offline-inspect.py`'s NOT_READY verdict (row 47)

`skills/agentic-sdlc/tools/offline-inspect.py:247` (pre-change) set `exit_code = 1` when the
inspection completed and named a refusal, so a *derived read-only verdict* occupied Decision 9's
unexpected-internal-failure code. A caller reading `$?` could not tell "I inspected the target and
it is not ready" from "I crashed".

This surface was chosen because it is the only one in the tree that satisfies both halves of this
umbrella's one-fix gate: the deviation is a single constant, and four existing assertions
(`tests/test_offline_observer_rc.py:136,154,172,402` pre-change) pinned the wrong value and were
available to flip. No other repository code reads its exit status — the only other reference is
`skills/agentic-sdlc/SKILL.md:107`, which documents the `READY`/`NOT_READY` document field and no
exit code — so the blast radius is the test module alone.

The replacement is `5`, not `0`, and the choice is taken from evidence rather than preference. Two
shipped precedents bound it: `skills/agentic-sdlc/tools/wave-verdict.py` holds that for an
effect-free derivation "a derived `blocked` is a result (0)", while `scripts/gate_baseline.py:112`
holds that a *ran-and-named-a-problem* verdict belongs at `5`, "Never inside the reserved block."
The only thing both agree on is that such a verdict may not occupy `1`. `5` satisfies both, keeps an
existing shell caller's nonzero signal intact, and cannot be confused with a crash (1) or a bad
argument (2). The fix also introduces the four named constants as the module's single derivation
point, so a future renumbering happens in one place.

CONDUCTOR RATIFICATION (2026-08-21): the `5` choice is ratified for this surface as documented
above. The two shipped precedents (`wave-verdict.py`'s derived-verdict-is-0 and
`gate_baseline.py`'s named-problem-is-5) genuinely conflict, and the global rule — when a derived
verdict is a 0-class result versus a named nonzero outside the reserved block — is deliberately
left to the child seeds, each of which must state which precedent its surface follows and why.



## SeedProposals

One paragraph per nonconforming surface. Each names its exact deviations with `file:line`, then the
class-closure fix shape the gate family already got: **one derivation point** for the exit vocabulary,
and **mutation tests in both directions** — a test that dies when the honest code is reverted to the
defective one, and a positive control that shows the same comparison can see the difference.

### SP-1 — `seeds-launcher.mjs` collapses every refusal onto 2 and passes the Seeds child's exit code through

Title: *Give the Seeds launcher a Decision 9 exit vocabulary: a clean refusal is 3, an unknown queue
effect is 4, and no child's exit code is ever mirrored.* This is the highest-severity surface in the
survey because `record` is the only queue MUTATOR in the tree. Deviations:
`skills/agentic-sdlc/tools/seeds-launcher.mjs:1517-1520` catches **every** thrown `LauncherError` and
sets `process.exitCode = 2`, so a receipt-hash refusal, a non-UTF-8 prestate, an ambiguous prestate,
`reviewed distribution is unavailable`, and an ordinary argument typo are one indistinguishable code;
there is no `3` anywhere in the file. `:1380` and `:1448` raise the two messages that ARE Decision 9's
class 4 — `Seeds init effect is unknown: the queue writer failed after moving the initialization
surface` and `Seeds record effect is unknown: the queue writer failed yet moved the queue` — through
that same `fail()` (`:106`), so the documented "a failed child after either surface moves is an
unknown effect; no movement is a clean refusal" distinction has **no exit code behind it at all** and
class 4 is unreachable. `:962` sets `process.exitCode = code === null ? 1 : code`, mirroring the Seeds
CLI's own status verbatim — exactly what `scripts/gate_receipt.py:101-103` forbids by name ("a gate's
own exit code is never passed through: mirroring it would make a gate that exits 3 indistinguishable
from the producer's refusal") — so a Seeds CLI exiting 2 is indistinguishable from the launcher's own
grammar error. Measured: `--help` exits **2**, so a help request is reported as a grammar error.
Fix shape: one `EXITS` table plus one `reportFailure(error)` choke point that derives the code from a
`class` field on `LauncherError` (`grammar` → 2, `refusal` → 3, `effectUnknown` → 4) rather than from
the throw site; a child status is translated, never mirrored, into 4 when a surface has already moved
and 3 when nothing has; `--help` becomes a 0-class query parsed before any receipt work. Mutation
tests both directions: revert any raise site's class and the corresponding test must die; drive a real
interrupted `record` on a `/tmp` queue and assert 4 with the queue digest named, paired with a
clean-refusal control on the same fixture that asserts 3 and a byte-identical queue.

REMEDIATION (2026-08-21, `agentic-sdlc-5a69`): the fix shape above landed and row 37 now records the
current conduct, so the exits measured earlier in this section are the dated record of the closed
defect rather than a claim still true of the module. One frozen `EXITS` table is the module's only
derivation point; `LauncherError` takes `code` as a required positional (the SP-2 lesson, applied
before the same defect could grow here); the bare `fail()` spelling is GONE, replaced by
`failGrammar`/`failRefusal`/`failEffectUnknown`/`failInternal` so no site can stay silent about its
class; and one `reportFailure(error)` produces every code a thrown refusal reaches (help's 0 and inspect's spawn-error 3 are set directly). Two
departures from the paragraph above are deliberate and are recorded here rather than left implicit.
**First**, the class a raise site names is a FLOOR, not the verdict: rather than re-classifying each
of the 26 `readback divergence` checks, `record` and `init` open an escalate-only effect ledger
before the queue writer starts and only a completed byte-identical readback of the whole queue
surface closes it, so a divergence found after a surface moved reports 4 — including a plan-cascade
divergence, which is why five expectations in `tests/test_seeds_launcher.py` flipped from 2 to 4 —
while a failure that proves nothing moved stays 3. That is the escalate-only ledger this survey
called exemplary at `activation-planner.py:2337`, applied where it recommended. **Second**, the
inspect verbs still report the Seeds child's own status; the `EXITS` table now names that as the one
code outside the reserved block and states the collision it accepts, because `check-agentic-sdlc-prereqs.sh:45`
returns that status verbatim and inspect exists to be that read-only child. `bootstrap` and `record`
translate their children's failures and never mirror them. Two boundaries stay open by choice:
`bootstrap`'s refusals after its `mise --locked install` remain 3 rather than 4 (the acquisition is
idempotent and re-converges, and the receipt publication is atomic, so no partial receipt exists to
admit), and the named 5 that would end the inspect passthrough collision is not taken here because it
would change every caller that reads Seeds' verdict through this seam.

### SP-2 — `activation-planner.py` reports 86 of its 315 refusals as unexpected internal failures

Title: *Make Decision 9's class a required argument of `ActivationError`, not a default.*
`skills/agentic-sdlc/tools/activation-planner.py:313-316` declares `def __init__(self, status: str,
reason: str, code: int = 1)`. An AST census of the module's 315 `ActivationError(...)` construction
sites finds 132 passing 4, 85 passing 2, 10 passing 3, exactly **1** passing 1 explicitly, **85
passing nothing at all**, and **2 passing a computed code** (`:1160` forwards a variable; `:3609`
computes `4 if active else 0`) — so 86 named refusals certainly land, and 2 more may land, on the
code Decision 9 reserves for an unexpected internal failure, 85 of them purely because a keyword
default says so. The measured
consequence: `plan --manifest <missing>` emits `{"status":"refused","effect":"none","exit_code":1}`
— a document that says *refused, nothing happened* while the exit says *I crashed* — from
`:461`'s `raise ActivationError("refused", f"cannot open {label}", 1)`, whose three siblings in the
same reader (`:446` BOM, `:450` malformed, `:452` noncanonical) all correctly use 2 and whose two
neighbours (`:465` unsafe, `:473` unstable) silently take the default. Separately, `status --target
<missing>` exits 1 with a raw `FileNotFoundError` traceback and emits **no result document**, so the
module's own single derivation point (`_report_failure`, `:2181`) is bypassed entirely on the most
ordinary operator mistake. Note the escalation logic itself is exemplary and must be preserved: the
ledger floor and escalate-only rule at `:2181-2210` are the model this survey recommends elsewhere.
Fix shape: drop the default so `code` is positional-required, convert all 85 defaulted sites deliberately (and pin the 2 computed-code sites) (a
`refused`/`effect: none` verdict is 3, an unusable supplied input is 2), and wrap the `status` verb's
target resolution so every `OSError` becomes an `ActivationError` before the choke point. Mutation
tests both directions: re-adding `= 1` to the signature must fail a test that asserts no
`effect: none` record ever exits 1; and a positive control must show the same assertion still passes
an honest `effect_unknown` record at 4, so it is not just banning the number 1.

REMEDIATION (2026-08-21, `agentic-sdlc-3d9a`): the fix shape above landed — `ActivationError.__init__`
dropped its `code` default, every construction site states its own class, and the AST census now also
pins the one forwarding site's (`_exact`) default to a non-1 constant — while the measured exits
recorded earlier in this section stay the dated record of the defect this closed, not a claim still
true of the module.

### SP-3 — `secrets_scan.py` and `provision_mermaid_linux.py` ignore argv entirely, so `--help` performs the operation

Title: *Give the two argv-less entrypoints a parsed grammar, so a query cannot trigger an effect.*
As surveyed, `scripts/secrets_scan.py` was `def main() -> int:` with no parameter, and
`scripts/provision_mermaid_linux.py` likewise, so neither surface read `sys.argv` at all. Every
argument was silently accepted and the surface performed its whole operation. Measured, and this is the
severe half: `uv run --python 3.12.11 scripts/provision_mermaid_linux.py --help` **provisioned** — it
downloaded the pinned `chrome-headless-shell 150.0.7871.24` and installed `node_modules`, 358 MiB plus
446 MiB, wrote `.mermaid-runtime/runtime-receipt.json`, and exited **0**. An operator typing `--help`
at a surface `AGENTS.md` describes as staying "an explicit operator step" because "provisioning
downloads a pinned browser" gets an unrequested network download reported as success. `secrets_scan.py
--zzz-not-a-flag` likewise ran the full scan at exit 0. Neither had any class 2 for an unknown
argument and neither had a 0-class query. Fix shape: one `argparse` parser per surface accepting no
positional arguments, `--help` as the only 0-class query, an unknown argument as 2 **before** any
`git ls-files`, `shutil.which`, or download; the scan's `SecretsScanError` mapping and the
provisioner's `ProvisionError` become a named 3-versus-4 split (nothing downloaded versus a partly
populated cache). Mutation tests both directions: removing the parser must fail a test asserting
`--zzz` exits 2 and that a sentinel-observed side effect did **not** occur; the positive control is
the same sentinel test over a real invocation, which must observe the effect, so "nothing happened"
is never vacuously true.

Closed by `agentic-sdlc-bcdd` (rows 39 and 40). Both entry points now take and parse `argv`
(`scripts/secrets_scan.py:156-157`, `scripts/provision_mermaid_linux.py:214-215`) and each module
docstring carries the exit table that derives its codes. The scan maps its three
before-anything-is-scanned reasons to 3 through one derivation point
(`PRECONDITION_REASONS`/`refusal_exit_code`, `scripts/secrets_scan.py:42-57`), keeps argparse on 2,
and leaves a found leak on 1 because `mise run check` reads that code. The provisioner's split is
positional rather than message-matched: the `mkdir`/`rmtree` block moved **below** tool resolution,
so the five refusals above the marked effect boundary
(`scripts/provision_mermaid_linux.py:152-157`) are 3 with nothing created or deleted, and every
failure below it — including a `RendererError` from the npm shim check — is re-raised as
`ProvisionPartialError` and reported as 4. Thirteen executed mutants (both directions per axis,
including re-mapping a pre-effect refusal back to 1, restoring the pre-move ordering, and moving the
finding code off 1) each killed a named test.

### SP-4 — `check-agentic-sdlc-prereqs.sh` reports a named missing prerequisite as an internal failure

Title: *Separate "I checked and something is missing" from "I failed to check".*
`scripts/check-agentic-sdlc-prereqs.sh:88` initialises `missing=0`, `:91`, `:108`, and `:111` set it to
`1`, and `:128` is `exit "$missing"` — so a completed read-only check that names a missing
prerequisite exits 1, Decision 9's unexpected-internal-failure code, and is indistinguishable from
the script dying mid-check. Measured: with exactly one `MISSING: valid locked active Seeds tuple
receipt` line the run exited 1. The script also reads no `$@` on its check path, so `--help` and
`--zzz-not-a-flag` both silently run the check. Fix shape: one exit table at the top of the file;
`--help` as the 0-class query; an unknown argument as 2; and the derived verdict at a code outside the
reserved block exactly as `scripts/gate_baseline.py:112`'s `EXIT_WORSENED` is, keeping 1 for a real
internal failure. Mutation tests both directions: a test asserting the missing-prerequisite exit is
NOT 1 must die when `:128` is reverted; the positive control drives a host where nothing is missing
and asserts 0, so the assertion distinguishes two real states rather than asserting one number.

REMEDIATION (2026-08-21, `agentic-sdlc-d259`): the fix shape above landed exactly as proposed. A
`case "${1:-}"` block parses the grammar before the check runs: `--help`/`-h` prints usage and
exits `EXIT_OK` (0) without touching a single prerequisite; any other supplied argument exits
`EXIT_USAGE` (2) naming it; the completed check's own outcome moved from a bare `exit "$missing"`
to an explicit `EXIT_OK`/`EXIT_MISSING` (5) split, with `EXIT_MISSING` documented in the same block
as "deliberately outside the reserved 0-4 block, exactly as `scripts/gate_baseline.py`'s
`EXIT_WORSENED` is." Two mutations were executed against the fixed file and reverted after: disabling
the new grammar `case` block reproduced the old argv-ignored behavior and killed both the `--help`
and the unknown-argument test; reverting the final `if`/`exit "$EXIT_MISSING"` back to `exit
"$missing"` killed the missing-prerequisite test by reproducing exit 1. `tests/test_preflight_capabilities.py`'s `ExactRuntimeWrapperTests` carries the four new assertions
(help, grammar, missing-prerequisite, and the nothing-missing positive control already present).

### SP-5 — `cmux-bus.sh` reports an absent dependency as 1 and a silent no-op as SUCCESS

Title: *Refuse cleanly at 3 when cmux is absent, never publish-as-no-op at 0, and never mirror
`cmux log`'s exit code.* `scripts/cmux-bus.sh:24` exits **1** when the `cmux` CLI is not on PATH — an
absent optional dependency, detected before any effect, reported as an unexpected internal failure;
this also makes the file's own documented help branch at `:71-73` **unreachable** on any host without
cmux, which is why `--help` measured 1. `:25` exits **0** when `CMUX_WORKSPACE_ID` is unset, so
`cmux-bus.sh pub <topic> <message>` outside cmux returns success while publishing nothing — a refusal
wearing the success code, the exact hazard Decision 9's 3 exists to prevent. `:36`'s
`cmux log ... >/dev/null 2>&1` is the last command in the `pub)` branch, so `cmux`'s own exit status
becomes the wrapper's, mirroring a foreign code into the wrapper's vocabulary; `:38-41`'s `seq` branch
ends in a pipeline whose status is Python's, so an unobservable bus surfaces as 1. The grammar codes
at `:32`, `:34`, `:44`, and `:75` are already correct and should be left alone. Fix shape: parse the
mode first so `--help` is reachable and 0; both dependency conditions become named 3 refusals; the
`cmux log` result is inspected and translated to 0 or a named non-reserved code, never mirrored. Mutation
tests both directions: a test asserting `pub` outside cmux is nonzero must die when `:25` is reverted
to `exit 0`; the positive control asserts a real `pub` inside a stub cmux is 0, so the test is not
simply requiring failure everywhere.

REMEDIATION (2026-08-21, `agentic-sdlc-4d00`): landed two of the three named deviations as fixes
and left the third disclosed rather than translated — not because the umbrella's child seed asked
for that split (it named no such scope; there is no record of it asking for disclosure-only on the
third deviation), but because the change that shipped simply stopped short of the fix shape's third
clause. `MODE` is now parsed before either dependency check, so the help/no-mode query is reachable
and exits `EXIT_OK` (0) on a host with no `cmux` CLI and no `CMUX_WORKSPACE_ID` at all — the
`--help`-measured-1 consequence named above is fixed as a side effect of that reordering. Both
`:24` and `:25`'s conditions now exit the named `EXIT_REFUSED` (3) instead of 1 and a silent 0,
respectively. `pub`'s `cmux log` passthrough was left exactly mirrored, and the file's header at
the time rationalized this after the fact ("that call IS the wrapper's one real effect, not a
refusal being disguised as one") rather than recording an agreed scope cut. `:38-41`'s `seq`-branch
pipeline-status residual is untouched and stays open. Three mutations were executed against the
fixed file and reverted after: reverting `:46`'s `EXIT_REFUSED` to `exit 1` killed the
absent-dependency test; reverting `:47`'s to `exit 0` killed the not-inside-cmux test; appending
`|| true` to the `cmux log` invocation killed the log-failure-is-mirrored test. `tests/test_cmux_bus.py`
is new (SP-5 had no prior test module) and carried all ten assertions, five of them explicit
positive controls, at the time.

REMEDIATION (2026-08-21, `agentic-sdlc-d259`): closes the mirrored-`cmux log` residual left open
above — the translation the original fix shape proposed shipped here, not disclosure. `EXIT_PUBLISH_FAILED=6`
is now named in the header's exit table, outside the reserved 0-4 block exactly as `gate_receipt.py`
names `EXIT_GATE_FAILED`/`EXIT_UNOBSERVED` there (its own header explains why: mirroring a foreign
exit code risks colliding with this wrapper's own clean-refusal 3, which a `cmux log` that itself
exits 3 would otherwise reproduce byte-for-byte). The `pub` branch now inspects `cmux log`'s exit
status and translates any failure to that one named code rather than passing the child's raw status
through; success (0) still exits 0, unchanged. `tests/test_cmux_bus.py`'s former
`test_cmux_log_failure_is_mirrored_not_swallowed` is renamed
`test_cmux_log_failure_is_translated_to_the_named_publish_failed_code` and now asserts child exit
statuses 1, 2, 3, and 7 all come out as 6; the child-0-stays-0 positive control is kept (renamed
`test_cmux_log_success_still_exits_zero`, since "mirrored" no longer describes what it proves). One
mutation was executed against the fixed file and reverted after: reverting the
`if ! cmux log ...; then ... exit "$EXIT_PUBLISH_FAILED"; fi` block back to the bare mirrored call
killed the re-pointed test at all four substituted statuses (1, 2, 3, 7). The help/no-mode query's
`sed` range was also widened from `2,22p` to `2,33p` to cover the grown header including the new
exit-table row — verified by running `--help` and confirming the table's last line reaches stdout,
not by assuming a wider range is automatically wide enough — and a new test assertion pins that
distinctive last line so a future truncation is caught by the suite rather than by eyeballing
output.

### SP-6 — `manage_claude_statusline.py` reports five distinct read-only states as one code

Title: *One derived read-only statusline state, one code — and none of them 1.*
`scripts/manage_claude_statusline.py` returns `1` for five different completed read-only verdicts:
`:436` `statusline is not managed`, `:484` `unmanaged statusline`, `:485` `statusline inactive`,
`:487` `statusline <operation> recovery pending`, and `:490` `statusline conflict`. All five collide
with each other and with the unexpected-internal-failure class; only `:491` (`active`) reaches 0 and
only `:529` reaches 2. Measured: `status --home <fresh>` exits 1 on `statusline inactive`, which is
the ordinary state of a host that has simply never activated the statusline — the same shape as the
defect fixed in `offline-inspect.py` under this umbrella, five times over. `AGENTS.md` already states
the intended distinction for the sibling surface ("reports a never-installed desired command as
`absent` and reserves `unmanaged` for a desired file that exists but is not owned"), so the state
names exist; only the codes are missing. Fix shape: one `EXITS` block and one `_exit_for(state)`
derivation; `inactive` and `not managed` are ordinary answers at 0 with the state in the document, and
`conflict`/`recovery pending` take a named non-reserved code. Mutation tests both directions: a test
asserting the five states map to distinct, non-1 codes must die when any `return 1` is restored; the
positive control asserts the `active` path is still 0 through the same mapping.

REMEDIATION (2026-08-21, `agentic-sdlc-d0a4`): the landed rule is stricter than the two-tier split
this paragraph proposed. Rather than giving `conflict`/`recovery pending` a named non-reserved code
distinct from `inactive`/`unmanaged`, the conductor's ratified rule for this surface is: **every**
completed answer from a non-mutating read is 0, full stop, with the five states distinguished only
in the returned message — never in the exit code — and a genuine read failure (corrupt settings,
an unreadable receipt, a foreign-owned path) still raises `StatuslineError`/`OperatorToolsError`
and is reported at 2 by `main()`, unchanged. This follows `wave-verdict.py`'s precedent from this
same umbrella's worked example ("a derived result is 0") rather than `gate_baseline.py`'s
("a named problem is 5"), because unlike `gate_baseline.py`'s comparison, none of these five states
is itself a problem: `deactivate` finding nothing to deactivate is the requested end state already
true, exactly as the two mutating verbs `activate`/`deactivate` were already 0 on success. `EXIT_OK
= 0` and `EXIT_REFUSED = 2` are now the module's one derivation point, both in the module docstring
and at every return site. Five mutations (reverting each `EXIT_OK` return to `1`) were executed
against an isolated `/tmp` mirror of the two scripts plus their shared test module and reverted
after: each killed its own test, and — checked in isolation — the `deactivate`-side mutation killed
`test_deactivation_recovers_after_settings_replacement` specifically at the `deactivate()` call
rather than being masked by an earlier assertion. The pre-existing `status`-pinning assertions in
`tests/test_manage_claude_statusline.py` were flipped from 1 to 0 in place; four new tests cover the
`inactive`/`unmanaged`/`conflict` states directly (no prior test exercised their return code), one
is a positive control for the unchanged `active` state, and one is a negative control proving a
genuine read failure still raises rather than returning 0. `scripts/opencodex-claude.sh` and
`docs/runbooks/verification.md` were checked for a consumer of this exit code and have none — the
runbook's own statusline line is `operator-tools:status`'s inventory entry, a different script.

### SP-7 — `install_operator_tools.py status` refuses a host precondition at the grammar code

Title: *A host precondition is a clean refusal (3), not an input error (2).*
`scripts/install_operator_tools.py:160` raises `operator-tools bin directory is not on PATH: {bin_dir}`
and the surface exits **2**, the code Decision 9 reserves for a grammar, schema, or input error, even
though nothing about the operator's command line was wrong — the PATH of the host was. Measured on a
`/tmp` HOME: `status` exited 2 and never reached the inventory that `AGENTS.md` documents it as
producing, so the documented `absent`/`unmanaged` reporting is unreachable on such a host. Fix shape:
split the error type so a caller-input problem stays 2 and a host-state problem becomes a named 3, from
one derivation point; and consider whether a read-only `status` should refuse on PATH at all rather than
reporting it as a finding. Mutation tests both directions: a test asserting the PATH refusal is 3 must
die when the raise is reverted to the input class; the positive control asserts a genuinely malformed
`--bin-dir` value still exits 2 through the same code path.

REMEDIATION (2026-08-21, `agentic-sdlc-92ff`): the error-type split landed as proposed; the
"consider removing the PATH refusal from `status` entirely" question was left open rather than
acted on, since narrowing what `status` refuses on is a separate design decision from naming the
refusal it already makes. A new `HostPreconditionError(OperatorToolsError)` subclass is raised only
from `validate_bin_dir`'s not-on-PATH branch; `main()` now catches it ahead of the general
`OperatorToolsError` handler and returns 3, while every other `OperatorToolsError` — including the
sibling "unsafe operator-tools bin directory" raise one line above it in the same function — still
returns 2 through the unchanged handler, so the fix is one raise site and one added `except`
clause, not a reclassification of the whole error hierarchy. Two mutations were executed against an
isolated `/tmp` copy of the script and reverted after: reverting the raise site back to plain
`OperatorToolsError` (leaving the new `except` clause in place) collapsed the not-on-PATH exit back
to 2, killing the refusal test; the unsafe-bin-dir positive control was independently confirmed to
stay at 2 both before and after that mutation, proving the fix does not depend on which
`except` clause happens to run first for every input. `tests/test_operator_tools.py` gained two CLI
subprocess tests (the refusal and its positive control) and one added assertion on the pre-existing
`test_path_preflight_refuses_unlisted_directory`, pinning the new exception subclass by `isinstance`
rather than only by message substring.

### SP-8 — `instruction-generator.py` leaks a traceback for a supplied-but-missing manifest

Title: *Move the read inside the `try` whose `except` already claims `OSError`.*
`skills/agentic-sdlc/tools/instruction-generator.py:171-176`: `_load` performs
`raw = path.read_bytes()` **outside** the `try` block, while that block's handler is
`except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: raise
GeneratorError("invalid canonical manifest")`. Because `OSError` is already named in the handler, the
author's intended class is unambiguous — 2 — but the read that raises it sits one line above the
`try`, so a missing manifest escapes as an uncaught exception. Measured: `plan --manifest
/tmp/nope.json --entry AGENTS.md` prints a raw `Traceback (most recent call last):` and exits **1**
(without the `plan` verb and `--entry`, argparse itself exits 2 first), while the same vector with a
non-JSON file correctly prints `ERROR: invalid canonical manifest` and exits 2. So the surface distinguishes
*supplied-and-malformed* from *supplied-and-missing* by accident, in the wrong direction. This is the
tree's smallest deviation and would have been this survey's worked example except that
`tests/test_instruction_generator.py` contains no exit-code assertion to flip, which the umbrella's
one-fix gate requires. Fix shape: one line moved, plus the module's first exit table. Mutation tests
both directions: a test asserting a missing manifest exits 2 with empty stdout and no `Traceback` in
stderr must die when the read is moved back out; the positive control asserts the malformed-manifest
path still exits 2 with the same message, so the new test is not merely accepting any nonzero.

### SP-9 — `render_mermaid_linux.py` reports `--help` as a silent grammar error

Title: *Give the renderer wrapper a 0-class help and a reason on every 2.*
As surveyed, `main` took `values = list(sys.argv[1:])` and returned
`EXIT_USAGE` whenever `len(values) != 2`, with **no message on any stream**. Measured: `--help`,
no arguments, and `--zzz-not-a-flag` each exited 2 having printed nothing at all, so an operator got a
bare failure with no statement of what the wrapper wanted. Decision 9 gives `--help` to 0, and a 2
that names nothing is indistinguishable from a crash that printed nothing. The arity restriction
itself must be preserved: `AGENTS.md` requires that "callers may invoke only
`scripts/render_mermaid_linux.py <definition> <final-svg>`", and `EXIT_UNSUPPORTED = 3` for a
non-Linux host is already an honest clean-refusal-before-effect. Fix shape: a `--help` branch that
prints the two-positional usage and returns 0, and one `usage(reason)` helper so every 2 names the
reason, both derived from the existing `EXIT_*` block. Mutation tests both directions: a test
asserting `--help` exits 0 and that a wrong-arity call exits 2 **with a nonempty stderr** must die
when either branch is reverted; the positive control asserts the valid two-argument path is
unaffected on a host where the runtime receipt is absent, i.e. that help was added without widening
what the wrapper will render.

Half-closed. The help and grammar axes are closed by `agentic-sdlc-61ce`: `USAGE_LINE` and
`_usage_error` are the single derivation point for every 2, and the `--help`/`-h` branch returns 0
(`scripts/render_mermaid_linux.py:556-574`). `agentic-sdlc-bcdd` added the boundary controls for
that branch — one test drives the `argv is None` dispatch through the real `sys.argv`, and one
asserts `main(["--help", "<absolute-out>"])` is a *render request* whose definition path is spelled
`--help`, refused at 1 naming `input path must be absolute and traversal-free` with nothing on
stdout, so the 0-class query stays exactly the whole-argv form. Row 46 is **not** flipped: the input
axis is still 1, because every `RendererError` — including an unusable supplied path — lands on
`EXIT_ERROR`. That remains queued.

### SP-10 — `install_research_os.py` leaks a traceback for a supplied-but-missing target

Title: *Convert the research-os installer's target resolution to a named exit-2 refusal.*
`skills/codex-research-os/scripts/install_research_os.py:1441` (`_open_root`, reached via
`_apply_locked` `:2783`): `--target /tmp/no-such-dir --dry-run` exits **1 with a raw
`FileNotFoundError` traceback** — SP-8's defect class on an *installer*, where a caller reading `$?`
cannot tell "you pointed me at nothing" from "I crashed mid-install". The repo's own
`tests/test_research_os_launcher.py` treats this as a task-gated surface, so the fix follows SP-8's
shape exactly: wrap the target resolution so the `OSError` becomes the module's named input error at
2, add the module's exit table as a single derivation point. Mutation tests both directions: a test
asserting a missing target exits 2 with no `Traceback` in stderr dies when the wrap is removed; the
positive control asserts a present-but-invalid target still takes its existing named path.

### SP-11 — `receipt_admission.py` ignores argv entirely, so no 0-class query exists

Title: *Give the receipt-admission CLI an argument grammar and a help path.*
`skills/model-tier-rightsizing/scripts/receipt_admission.py:871` (`main()`) takes no argv and reads
`sys.stdin` at `:874`, so `--help` and `--zzz-not-a-flag` each return `{"status":"invalid"}` at
**exit 2** — SP-3's argv-ignored class, on a surface `skills/model-tier-rightsizing/SKILL.md:144`
documents as a CLI. There is no 0-class query at all. Fix shape follows SP-3: an argparse front
door whose `--help` exits 0 without reading stdin, an unknown flag exits 2 with a usage line, and
the stdin-document path becomes the explicit default action. Mutation tests both directions: a test
asserting `--help` exits 0 with usage on stdout and nothing read from stdin dies when the front
door is removed; the positive control asserts a valid stdin document still admits or refuses
exactly as today.

## Residuals this survey did not close

* Three shell wrappers and one host aggregator (`bump-version.sh`, `install-skill-bundle.sh`,
  `validate-bundle.sh`, `run_all_hosts.py`) delegate to `mise`, which this survey was not permitted to
  invoke. Their own exit vocabulary is therefore unmeasured, not conforming; every probe exited 1 from
  `mise ERROR error parsing config file` before reaching the wrapper's logic.
* The two PowerShell wrappers cannot be driven from Linux.
* A measured residual inside the fixed surface: `offline-inspect.py`'s stdout-failure path exits
  **120**, the interpreter's own flush-at-exit code, outside its table entirely. It is recorded in the
  module rather than asserted as contract, and belongs to whichever child seed takes the
  "every surface's failure-to-deliver class" question.
* This survey drove `provision_mermaid_linux.py --help`, which downloaded 358 MiB of browser and
  446 MiB of `node_modules` into the worktree's gitignored `.mermaid-runtime/` and `node_modules/`.
  Both were absent before the probe and both were removed afterwards; `git status` was clean of them
  in both directions. That is the evidence for SP-3.

