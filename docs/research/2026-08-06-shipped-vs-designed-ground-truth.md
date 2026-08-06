# Shipped vs designed: measured ground truth for agentic-sdlc

**Date:** 2026-08-06 · **Method:** executed checks against the working tree, not agent
inference · **Purpose:** the honest denominator for any parity review, and three corrections to
`2026-08-05-pi-lab-harvest-memo.md` / `docs/progress/2026-07-21-product-progress-snapshot.md`.

## 0. Read this first: "shipped" here means the working tree, not HEAD

A workflow verifier flagged this and it is the right correction to lead with. Almost everything
graded SHIPPED below — the activation transaction, its 51 tests, and the `validate_skills`
model-pin gate added this session — is **present in the working tree but NOT committed**:

```
$ git ls-files --error-unmatch tests/test_activation_transaction.py
error: pathspec '...' did not match any file(s) known to git
```

`skills/agentic-sdlc/tools/activation-planner.py`, `.../instruction-generator.py`,
`tests/test_activation_transaction.py`, and `tests/test_prime_candidate_custody.py` are all
**untracked**; `scripts/validate_bundle.py` and `tests/test_runtime_contract_validation.py` carry
uncommitted modifications. So a fresh clone of `HEAD` (`ada5ecd`) has **none of it**.

Every grade below therefore means "works in this checkout." Against HEAD, the honest grade for
Safe PRIME activation is still the snapshot's **preview-only**, and the progress snapshot was
*accurate when written*. This distinction matters for any parity claim: pi-lab's artifacts are
committed and pushed; a meaningful share of agentic-sdlc's strongest capabilities are one
`git add` away from existing at all. **Committing this work is the cheapest possible way to
convert measured capability into actual capability.**

## 1. Test coverage is not what the raw count suggests

`mise run check` runs **409 tests across 23 files** and exits 0. Classified by whether a test
actually exercises code or only asserts on prose:

| Class | Tests | Files |
|---|---|---|
| Exercises code only (imports `scripts.*`, runs subprocesses) | 63 | 5 |
| Exercises code **and** asserts on markdown | 269 | 10 |
| **Asserts on markdown prose only — no code executed** | **77** | **8** |

The 77 prose-only tests are in `test_authority_corrections.py` (9), `test_cao_removal.py` (8),
`test_change_writing.py` (10), `test_deep_work_loop.py` (11), `test_git_change_flow_router.py`
(6), `test_model_tier_rightsizing.py` (22), `test_pr_safety_doctrine.py` (3),
`test_role_submissions.py` (8).

This is **not a criticism** — doctrine-consistency tests are a legitimate and unusual strength
(they stop a SKILL.md from drifting away from its own rules, which is exactly the
"UNWIRED CAPABILITY / STALE INSTRUCTIONS" failure class pi-lab's repo-hygiene skill names). But
**19% of the suite proves prose is self-consistent, not that a capability works**, and a parity
review that counts 409 tests as behavioral coverage is overstating what ships. Grade a capability
SHIPPED only when a test in the first two rows covers it.

## 2. Correction: Safe PRIME activation is no longer "preview only"

`docs/progress/2026-07-21-product-progress-snapshot.md:33` states:

> "Safe PRIME activation | **Preview only** | … the public CLI exposes only `plan`. There is no
> supported transactional apply → verify → recover journey."

and `:80` repeats it. **Both are now stale.** Executed:

```
$ activation-planner.py --help
usage: activation-planner.py [-h] {plan,apply,status,recover} ...
```

All four verbs are exposed (`add_parser` for `plan`/`apply`/`status`/`recover`, plus an
`inspect` parser in the module), in a 2,948-line tool, backed by
**`tests/test_activation_transaction.py` with 51 tests** plus 5 in `test_activation_planner.py`.
This is the largest single capability change since the snapshot was written, and it is the #1
item on the harvest memo's 43-item backlog — **substantially delivered, not pending.** The
snapshot and `commands/sdlc-init.md`'s drift note should be updated; right now the repo
understates itself, which is the rarer and less dangerous direction of doc-vs-code drift but
still drift.

Note this work is **uncommitted** in the working tree (`skills/agentic-sdlc/tools/activation-planner.py`
is untracked, `scripts/activation_planner.py` modified), so the snapshot was accurate for HEAD
when written.

## 3. Correction: RuntimeAssignment is mechanically enforced, not doctrine-only

The harvest memo grades typed evidence/contracts as *"Partial — `RuntimeAssignment` and role
contracts ship"* and elsewhere frames model routing as prose discipline. There is in fact a
**462-line executable admission checker**, `skills/model-tier-rightsizing/scripts/receipt_admission.py`,
referenced by `tests/test_runtime_contract_validation.py`. It reads a receipt on stdin and
fails closed. Executed:

- A receipt with a wrong field name → `{"status":"invalid","errors":["missing fields:
  context_readback_evidence, context_readback_status, effort_readback_evidence,
  effort_readback_status, model_identity_basis, model_readback_evidence, model_readback_status,
  request_injection_evidence, request_injection_status, requested_context_form, requested_effort,
  requested_model_id, resolved_model_id, resolved_provider", "unexpected fields: requested_model"]}`
  — **14 required fields**, and unknown fields are rejected rather than ignored.
- A receipt claiming `resolution_state: resolved` while readback is `unavailable` →
  `invalid`, with `"model_readback_status must equal verified"`,
  `"request_injection_status must equal verified"`, and
  `"requested model/effort/context tuple is not certified"`.

So the doctrinal rule *"resolved is recorded only after adapter readback"* is **enforced by code
that refuses**, not merely asserted in a SKILL.md. Regrade this capability upward.

## 4. Confirmed unchanged: Seeds really is read-only

`skills/agentic-sdlc/tools/seeds-launcher.mjs` admits `prime`, `ready`, `blocked` (and
`--version`) only. A `'close'` string in that file is a Node `child.once('close', …)` event
handler at line 909, **not** a Seeds verb — worth stating because a naive grep for mutation verbs
finds it and concludes a mutation seam exists. There is none. Harvest-memo backlog item #3 stands
as written.

## 5. Zero decision records, against pi-lab's 23

`fd -t d -i adr` finds **no ADR tree** in agentic-sdlc. pi-lab has **23 ADRs** covering decisions
this repo currently faces and has never recorded — most pointedly:

| pi-lab ADR | Decision it records | Live open question here |
|---|---|---|
| `0003-licence-and-visibility` | MIT now, public after dogfooding | repo is `"license": "UNLICENSED"`, no `LICENSE`, private, blocking all vendoring |
| `0021-mcp-adapter-mediated-support-zero-default-servers` | MCP is operator-owned; ship zero default servers | the plugin work concluded "ship no `.mcp.json`" — same conclusion, unrecorded |
| `0008-skills-off-payload-and-off-path` | keep the in-tree skill corpus off the load path for selection-budget cost | the plugin install measured ~1,092 always-on tokens; no recorded position |
| `0015-nub-is-the-mise-front-door-not-the-product-runtime` | separate bootstrap front door from runtime | mirrors this repo's "mise is the only bootstrap prerequisite" doctrine, unrecorded |

This repo **specced** an ADR skill (`2026-08-05-adr-skill-spec.md`) but has authored no ADRs. The
cheapest high-value gap in this review: the decisions already made across these 13 memos are
exactly the ADR backlog, and several are being re-litigated across sessions because nothing
records them.

## 6. Bearing on the parity question

pi-lab's honest self-assessment is that it *"has never delivered a capability to anybody"* with a
4.5:1 doc-to-code ratio. agentic-sdlc's position is materially better but not as far ahead as a
409-test count implies: it has **real transactional activation with 51 tests**, **real
fail-closed receipt admission**, a **real offline inspector**, and a **real installer with 82
tests** — four genuinely shipped vertical slices — against **read-only Seeds**, **no mission
engine**, **no gateway route qualification**, and **19% of its suite proving prose rather than
behavior**.

No outward effect is authorized by this document. Nothing in the bundle was changed to produce it.
