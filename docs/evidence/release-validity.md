# Release Validity — derivation of record

**What this is.** The human-readable conjunction over existing evidence that seed
`agentic-sdlc-c005` names: one row per clause of the product spec's Release Validity gate,
stating the clause, its evidence, and an honest status. It is a reading, not a mechanism.
ADR-0030 considered and rejected a derivation script — "It becomes worth writing when a second
wave exists and reading the file by eye has actually failed"
(`docs/adr/0030-record-wave-evidence-in-git-and-one-markdown-file.md:60-63`) — and that decision
stands: this file is never a gate leaf, nothing parses it, and no verdict below is machine-derived.

**What it derives against.** The Release Validity section of
`docs/plans/claude-code-first-harness/agentic-sdlc-product-spec.md:681-703` (cited below as
`spec:<line>`), in the spec as re-issued 2026-08-23 (commit `74dd70d`). Seed `agentic-sdlc-c005`'s description cites
spec:632-652; those are the pre-re-issue line numbers for the same section
(`docs/research/2026-08-21-product-ladder-audit.md:83` carries the original citation).

**Reading anchor.** Every pointer and every checkable claim below was read at commit `6c30728`
on 2026-08-23. Statuses are point-in-time readings, not standing guarantees: a later reader
re-checks the pointer rather than trusting the row.

## Reading rules

- **satisfied** — the clause's evidence exists at the anchor commit at the named pointer and was
  checked while writing the row.
- **satisfied-at-fan-in** — the clause's evidence is produced by wave `f194-w1`, in flight as this
  document is written, and lands at that wave's integration; the pointer names the committed
  destination. Until that integration the clause is unmet.
- **OPEN** — the clause is unmet, with the owning seed and evidence lane named. An OPEN row is a
  named gap, never a deferral by silence.

## The conjunction, clause by clause

| # | Clause (spec lines) | Evidence at `6c30728` | Status |
|---|---|---|---|
| 1 | Release identity, checksums, licence/NOTICE inventory verify; SBOM absence and the uncommanded runtime digests disclosed honestly (spec:686-687; Implementation Decision 68, spec:416) | `scripts/build_release.py`; `policy/release-candidate.v1.json` (`disclosures`: `sbom: absent`, `licensing: incomplete`, `provenance: unverified`; `NOTICE` and `LICENSE` in `payload.files`; `release_claim: "none"`); `scripts/write_acquisition_receipt.py`; `tests/test_build_release.py`, `tests/test_write_acquisition_receipt.py`, `tests/test_release_contract.py`. Executed, receipted build: `docs/evidence/waves/f194-w1/` (landed in the same integration as this document) | satisfied |
| 2 | install/status/update/recovery/removal preserve foreign state and have effect-aware exits (spec:688) | `scripts/ccodex_sdlc_install.py`, `scripts/ccodex_sdlc_update.py`, `scripts/ccodex_sdlc_uninstall.py`, `scripts/ccodex_sdlc_recover.py`, `scripts/ccodex_sdlc_readonly.py`; `tests/test_ccodex_sdlc_install.py`, `tests/test_ccodex_sdlc_update.py`, `tests/test_ccodex_sdlc_uninstall.py`, `tests/test_ccodex_sdlc_recover_apply.py`, `tests/test_lifecycle_exit_conformance.py`. Note: wave `f194-w1` surfaced an open defect against this same verb set — after a completed receipted uninstall, the status reader reports `degraded`/`owned-entry-conflict` (journey FINDING-1, seed `agentic-sdlc-42ec`). It does not unmeet this clause's literal text (foreign state preserved; exits effect-aware), but this row is not a clean bill for the readers | satisfied |
| 3 | One clean greenfield and one occupied brownfield activation journey pass from installed bytes (spec:689) | `docs/evidence/waves/f194-w1/` (landed in the same integration as this document; see note). Surface at the anchor: `skills/agentic-sdlc/tools/instruction-generator.py`, `commands/sdlc-init.md`, `tests/test_instruction_generator.py` | satisfied |
| 4 | Native-Claude minimum and stable-reference Workflow canaries pass for the exact tuple (spec:690) | None. No canary tooling exists in the tree; Testing Decision 12 (spec:534-536) defines what a Workflow canary binds, Testing Decision 37 (spec:604-605) places live canaries outside the offline gate as separate approved release evidence | OPEN — seed `agentic-sdlc-c005`, live-host operator lane |
| 5 | One complete Core wave reaches an honest `accepted` or intended `remediation-progress` outcome (spec:691) | `docs/evidence/waves/f83f-w1/verdict.json` (`state: "accepted"`, `wave_id: "wave-f83f-w1"`), landed on this lineage at `dc2976b` (blob `0faf907e`; originally recorded at the off-lineage `1a1be0c`), with `docs/evidence/waves/f83f-w1/gate-receipt.json` (`self_digest` `08d76fff95fc3c7b9f2412dd66552c7ea849cc0c7d2dae38d6589928a5d3cf49`) | satisfied |
| 6 | Runtime requests and observed identities remain separate; no silent fallback (spec:692) | `skills/agentic-sdlc/tools/runtime-assignment.py`; `policy/runtime-assignment-normative-contract-v1.json`; `tests/test_runtime_assignment.py`, `tests/test_runtime_contract_validation.py`; executed per-wave records `docs/evidence/waves/f83f-w1/admission-report.json` and the `classification-*.json` set | satisfied |
| 7 | Write custody, independent review, authorized serial fan-in, and integrated gates pass (spec:693) | Wave Acceptance Rules, `skills/agentic-sdlc/SKILL.md:195`; `scripts/gate_receipt.py`, `scripts/gate_baseline.py`; `tests/test_gate_receipts.py`, `tests/test_gate_receipt_producer.py`, `tests/test_gate_baseline.py`; executed record `docs/evidence/waves/f83f-w1/` | satisfied |
| 8 | status/doctor/inspect are read-only and render the same closed semantic record as JSON (spec:694) | Readers in `scripts/ccodex_sdlc.py` and `scripts/ccodex_sdlc_readonly.py`; closed record schema `policy/ccodex-sdlc-read-report.v1.json` (the sole descriptor since agentic-sdlc-7a2b W6 deleted the reader-less `.v2.json` scaffold); `tests/test_ccodex_sdlc.py`, `tests/test_ccodex_sdlc_doctor_lifecycle.py` | satisfied |
| 9 | Secrets, private content, undeclared egress, and incident fixtures remain redacted and fail closed (spec:695) | `mise.toml:146` (`secrets` task, pinned scanner) as a leaf of `check` (`mise.toml:156`); `.config/betterleaks.toml` (extend-only); `scripts/secrets_scan.py`; `tests/test_secrets_scan.py`; per-surface redaction assertions (see note) | satisfied |
| 10 | Product prose passes canonical vocabulary and prohibited-claim tests (spec:696) | `claim_lint` in `policy/release-contract.v1.json` (fixture root `tests/fixtures/release-claims`), executed by `scripts/validate_bundle.py` inside `mise run validate`; behavior pinned by `tests/test_release_contract.py`; canonical vocabulary pinned by `tests/test_product_spec_contract.py` | satisfied |
| 11 | No optional profile, companion, renderer, external provider, permission bypass, or product telemetry is enabled by default (spec:697-698) | Per-surface pointers collected in the note below — this row is the one place that cites them together | satisfied |
| R1 | Stable rider: migration and recovery coverage (spec:700) | `scripts/ccodex_sdlc_update.py` + `tests/test_ccodex_sdlc_update.py`; `scripts/ccodex_sdlc_recover.py` (`--dry-run`/`--apply`) + `tests/test_ccodex_sdlc_recover_apply.py`; single admitted ownership schema with other generations refused by name (`scripts/ccodex_sdlc_install.py:1802-1807`); the seven-verb namespace per Implementation Decision 91 (spec:483) | satisfied (offline) |
| R2 | Stable rider: at least one current certified Core tuple (spec:700-701) | `support_rows: []` in `policy/release-contract.v1.json` — empty by design, because `certification_requires_current_capability_evidence: true` and no live capability evidence exists | OPEN — seed `agentic-sdlc-c005`, live-host operator lane (same lane as clause 4) |

## Row notes

**Clause 1.** "Verify" is an executed property, not a code property. The mechanism is complete at
the anchor — `scripts/build_release.py` archives the committed HEAD only (a dirty tree is refused
with no override), and `scripts/write_acquisition_receipt.py` re-hashes every payload entry in
both directions against the root's own `manifest.json` — and the honest-disclosure leg is
discharged by policy bytes: Implementation Decision 68 (spec:416) records that the bundled-runtime
and candidate-digest stanzas were dropped at main `60496c3` and `sbom: absent` is disclosed
instead. What no committed artifact records at the anchor is an executed, receipted build; wave
`f194-w1` produces exactly that, so the row converts at its integration.

**Clause 3.** This row is deliberately a pointer. The journey workstream is producing
`docs/evidence/waves/f194-w1/` in a sibling worktree while this document is being written; per
wave write custody this document does not read another worktree's uncommitted files, so the row
stays pending-fan-in until the integrator lands that directory. The journey seed is
`agentic-sdlc-f194`; its evidence is the two installed-byte activation journeys (greenfield and
brownfield) plus a named refusal, executed from the activated plane's copied bytes with the
acquisition and activation receipts named.

**Clauses 4 and R2 (the two live gaps).** Both are live-host evidence by the spec's own design.
Testing Decision 37 (spec:604-605) keeps `mise run check` as the authoritative offline gate and
places live provider, billing, route, attribution, host-feature, and platform canaries as
separate approved release evidence; Testing Decision 12 (spec:534-536) enumerates what a Dynamic
Workflow canary must bind (exact Claude Code version, account/provider mode, plugin identity,
workflow behavior, approval, execution, artifacts, pause/stop/resume, readback). Nothing offline
in this tree can discharge either clause, and nothing in this tree pretends to. The remainder of
seed `agentic-sdlc-c005` is exactly these two rows.

**Clause 5.** The `wave-f83f-w1` verdict was produced by the typed wave stack that ADR-0030 later
deleted; decision 5 of that ADR keeps the directory as committed bytes that are readable but no
longer re-derivable, and this row cites the committed bytes. The first wave record in ADR-0030's
markdown format (`docs/evidence/waves/f194-w1.md`, conductor-owned) lands at this wave's fan-in;
clause 5 is satisfied today on the committed `f83f-w1` record alone.

**Clause 9.** The fail-closed leaf is the pinned secrets scan. The clause's private-content,
egress, and incident-fixture legs are carried as redaction assertions distributed across the
surface suites (`tests/test_secrets_scan.py`, `tests/test_ccodex_sdlc.py`,
`tests/test_gate_graph.py`, `tests/test_muse_claude.py`, `tests/test_opencodex_claude.py`,
`tests/test_product_spec_contract.py`), not as one dedicated incident-fixture corpus. That
distribution is stated here so this row cannot be read as claiming a corpus that does not exist.

**Clause 10.** The prohibited-claim lint is fixture-root-only by design
(`tests/test_release_contract.py` proves it never scans historical prose outside
`tests/fixtures/release-claims`); the operative product prose is pinned separately by
`tests/test_product_spec_contract.py` (the five-command Core closure, the six-outcome wave
vocabulary of Implementation Decision 61 at spec:397, the `ccodex sdlc` namespace order).

**Clause 11, surface by surface.** Each optional surface is behind its own explicit,
operation-specific step at the anchor:

- *Optional profile (statusline):* inactive until `claude:statusline:activate`;
  `scripts/manage_claude_statusline.py`, `tests/test_claude_statusline.py`,
  `tests/test_manage_claude_statusline.py`.
- *Hooks:* installing never enables; wiring is the per-hook `claude:hooks:activate`;
  `scripts/manage_claude_hooks.py`, `tests/test_manage_claude_hooks.py`.
- *Companion (external skill libraries):* opt-in through each library's own front door, dry-run
  without `--yes`; `scripts/install_external_libraries.py`, `tests/test_external_libraries.py`.
- *Renderer:* `mermaid:provision` is an explicit operator step and no Mermaid task is a leaf of
  `check` (`mise.toml:156` depends on exactly `validate`, `test`, `self-test`, `secrets`);
  `tests/test_mermaid_renderer_gate.py`.
- *External provider:* `ocx:configure` admits only named, registry-listed routes and writes the
  config file only; `scripts/opencodex-claude.sh`, `tests/test_opencodex_claude.py`.
- *Permission bypass:* `--yolo` is an explicit per-invocation opt-in consumed by the wrapper
  (`scripts/opencodex-claude.sh`); Testing Decision 11 (spec:531-533) requires bounded-autonomy
  tests proving YOLO is never selected.
- *Product telemetry:* no telemetry surface exists at the anchor —
  `grep -rn telemetry scripts/ policy/ mise.toml` returns no match — and default telemetry is an
  explicit non-goal (spec:717-718).

**Rider R1.** "Coverage" is discharged offline: update across candidates, recovery with a
dry-run/apply split, and the named refusal of any other ownership-state generation instead of a
silent migration. This document claims the coverage only; it does not claim the stable channel,
and R1 being satisfied does not soften R2 being OPEN.

## Verdict

**Verdict: OPEN.** With wave `f194-w1`'s evidence integrated alongside this document, clauses 1
and 3 are satisfied, and the conjunction still does not hold: clause 4 (the native-Claude minimum
and stable-reference Workflow canaries for the exact tuple) and rider R2 (at least one current
certified Core tuple; `support_rows` is empty by design until live capability evidence exists)
remain unmet — both live-host operator-lane evidence owned by seed `agentic-sdlc-c005`. Release
Validity therefore remains open, and `agentic-sdlc-c005` does not close on this document; its
remainder is exactly the two named live-host gaps.

## This document derives; it never authorizes

No release, tag, publication, PR mutation, support claim, or any other outward effect follows
from this document or from any status in it. The candidate policy's `release_claim` stays
`"none"` and a built archive remains "evidence of what was archived, never a release or a
publication"; the first-release/tagging decision remains deferred and requires its own explicit
authorization. The rider's channel-shape sentence is likewise policy at the anchor, not a claim
here: `channels.preview` in `policy/release-contract.v1.json` carries
`install_mode: "side-by-side"`, `may_overwrite_stable: false`, and
`inherits_stable_state: false` (spec:701). The gate's own closing sentence controls this file as
much as any other: "A passing gate remains evidence and never authorizes publication"
(spec:702-703).
