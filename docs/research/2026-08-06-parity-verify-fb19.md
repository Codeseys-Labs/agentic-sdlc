## Per-claim adjudication

### Row 1 — Resolved/inherited/unresolved model-identity tri-state → **PARTIALLY CONFIRMED** (verdict AGENTIC-SDLC AHEAD stands, grade overstated)

- Contract field list confirmed at the cited lines: `policy/runtime-assignment-normative-contract-v1.json:49-66` lists `resolution_state` (:56) through `context_readback_evidence` (:65).
- Enforcement is real executable code: `skills/model-tier-rightsizing/scripts/receipt_admission.py:420-421` — `if receipt["resolution_state"] != "resolved": errors.append("resolution_state must equal resolved")`. 462 lines confirmed. Ran `python3 -m pytest tests/test_runtime_contract_validation.py -q` → `41 passed, 77 subtests passed`.
- **Overstatement:** only 9 of those 41 tests touch receipt admission at all (measured by splitting the file on `def test_`); the other 32 are bundle/roster/generator pinning tests. And the *tri-state* is not an enum in code — code accepts exactly one value (`resolved`) and `inherited`/`unresolved` exist only as prose plus regex greps over doctrine text (`tests/test_model_tier_rightsizing.py:393,420`). Corrected grade: **SHIPPED (fail-closed rejection of non-resolved) + DESIGNED (the tri-state vocabulary itself)**.
- pi-lab absence confirmed: `rg -n "resolution_state|resolutionState"` over pi-lab (excluding node_modules/dist) → zero hits. `driven-agents.md:143` quote is verbatim accurate.

### Row 2 — Three-rung vocabulary, "PI-LAB AHEAD on operated evidence volume" → **REFUTED on "operated"**

pi-lab's own code states the ledger is inert: `pi-lab/scripts/lib/capability-crosswalk.ts:337` — *"`S-157` (`pi-lab-6bb9`) records that `docs/route-ledger/*` is read by no code. Do not read a row below as a qualification claim."* Corroborated by `pi-lab/docs/workstreams/backlog-megaloop/2026-07-28-wave3/triage/legacy-and-ideas.md:56` (`NEEDS_DECISION`, "source search finds only its unit-test reader"). `rg -n "route-ledger" src/ scripts/ tests/` → only that comment plus `tests/unit/route-ledger.test.ts`. The file is hand-authored (`projectionOf: "manifests/profile-deep-work.json"`), no writer exists, and `rg -nw "mined"` / `"roster-benchmarks"` / `"class.observed"` over pi-lab `src/ scripts/ schemas/ manifests/ tests/` → **zero hits**, so the declared/mined/observed layer is unimplemented in pi-lab too.

Also: the analyst's own counts are wrong. Actual distribution (`python3` over the file): 17 `route-probed-positive`, **4** `route-probed-negative` (not one), 1 `unprobed`; qualification 17 `route-probed` / 5 `catalog-only`. And the three-rung enum is *pre-existing* in `route.schema.json:130-137`, not designed by `right-sizing-design.md:172-255` (which designs declared/mined/observed at :152-172 and explicitly says "everything in `route.schema.json` stays as-is", :175-177).

**Corrected verdict: PI-LAB AHEAD only on populated data + one schema-invariant test (`bun test tests/unit/route-ledger.test.ts` → 8 pass, verified). Neither project operates a meter.**

### Row 3 — Executable multi-provider gateway → **CONFIRMED as code, REFUTED as capability match**

`pi-bedrock-mantle/extensions/mantle/*.ts` = 1,026 lines confirmed exactly. Test count is *undercounted*: I ran `bun test` → **107 pass, 0 fail, 506 expect() calls across 9 files** (not 34). `no-unverified-widening.test.ts` and `no-self-audited-retention-lint.test.ts` exist.

But the capability is a **Pi provider extension minting a presigned-SigV4 Bedrock bearer** (`bin/mantle-token:117` "expiry from the token itself (presigned SigV4 X-Amz-Date + X-Amz-Expires)") — not the memo's subject, which is an HTTP gateway doing Claude-Code OAuth/token passthrough. Also a scoping double standard: this is a **separate repo** (`pi-lab/manifests/profile-deep-work.json:81-89`, `kind: git`, `localRelativePath: ../pi-bedrock-mantle`), counted as "PI-LAB AHEAD", while equally-sibling agentic-sdlc artifacts (rows 4-5) are counted as "not inside its own tree." agentic-sdlc's ABSENT column is correct (`rg -in gateway AGENTS.md README.md` → 0 hits, exit 1).

### Row 4 — Gateway qualification harness → **CONFIRMED, and understated**

`bedrock-mantle-frontier-bundle/config/gateway.qualification.example.yaml` is 60 lines and contains exactly the cited controls (`api-keys: [__CCODEX_GATEWAY_TOKEN_JSON__]`, `quota-exceeded.switch-project: false`, `request-retry: 0`, `logging-to-file: false`). Stronger than claimed: it is **wired to a driver and tests** — `scripts/qualify-cohort:271` (`template="$CCODEX_BUNDLE_ROOT/config/gateway.qualification.example.yaml"`) and `tests/test-gateway-offline.sh:311,335,384`. Memo Probes A–F confirmed at `docs/research/2026-08-05-gateway-selection-memo.md:100-112`. Verdict stands.

### Row 5 — Dynamic multi-model Workflow routing → **REFUTED (self-contradictory verdict)**

The artifact is real: `config/dynamic-workflow-routing.md` = 199 lines, 12 numbered invariants (`rg -n "^[0-9]+\."` → items 1-12), `CLAUDE_CODE_SUBAGENT_MODEL` unset at :27, `ulimit -n 256` at :50, `claude-sonnet-5-mantle` → `anthropic.claude-sonnet-5` at :60. But the row's own source cell says *"N/A — no single external source prescribes this"* and then returns **BOTH SHORT OF SOURCES**. You cannot fall short of a prescription that does not exist. **Corrected verdict: BOTH ABSENT from installable surface; no source gap.**

### Row 6 — "Effort/context readback honesty… mechanically forbids requested-as-readback" → **REFUTED. This is the most important error.**

I executed the validator. The code does the **opposite** of the doctrine:

```
readback_evidence_errors()  # receipt_admission.py:355-362
top_level = receipt["requested_effort"] if name == "effort" else receipt["requested_context_form"]
if evidence[value_key] != top_level:
    errors.append(f"{name} readback evidence does not bind the top-level {name} value")
```

Executed consequences:
1. A receipt whose `effort_readback_status`/`context_readback_status` are `verified` but whose "observed" values are **nothing but a copy of the request** validates cleanly: `python3 skills/model-tier-rightsizing/scripts/receipt_admission.py < echo_receipt.json` → `{"digest_sha256":"91219009…","status":"validated"}`, exit 0. The digest is `sha256({"effort":"high"})` — computable by anyone holding the request, so it carries zero readback provenance.
2. An **honest divergent** readback is *rejected*: setting `observed_effort: "medium"` against `requested_effort: "high"` yields `['effort readback evidence does not bind the top-level effort value', 'effort readback evidence digest does not bind the top-level effort value']`. The schema structurally cannot record a transport that downgraded the effective effort — the single case readback exists to detect.
3. The test the analyst cites as proof (`test_receipt_validation_rejects_closed_evidence_shapes_and_copied_readback`, `tests/test_runtime_contract_validation.py:1158-1172`) passes only because its mutant uses the **wrong field name** (`request_bytes_sha256` instead of `readback_bytes_sha256`). Reproduced: errors are `['effort readback evidence missing fields: assignment_binding_sha256, readback_bytes_sha256', '… unexpected fields: request_bytes_sha256']` — a *shape* rejection, not a provenance one. Rename the field and the identical copied receipt passes.

`ALLOWED_EVIDENCE["transport_readback"]["statuses"] = ["verified","unavailable"]` (`receipt_admission.py:28-32`) is confirmed present, but it forbids only a third *label*; it does not prevent `verified` from being a request echo. **Corrected verdict: DESIGNED in doctrine (AGENTS.md:95 verbatim confirmed), NOT enforced. The claim that this "would catch a gateway silently promoting a request echo to a verified readback" is falsified by execution — BOTH SHORT.** The same refutation kills "original invention" bullet #2.

### Row 7 — Node version-pin enforcement → **CONFIRMED**

`node --version` → `v26.6.0`; `node skills/agentic-sdlc/tools/seeds-launcher.mjs inspect --target . --version` → `launcher Node version mismatch: expected 22.22.3, got 26.6.0`, exit 2. Fails closed. The row's own "narrow claim / not routing itself" hedge is accurate.

### Row 8 — Static pins forbidden → **CONFIRMED for agentic-sdlc; REFUTED for pi-lab's column**

agentic-sdlc side is real: `_assert_no_static_model_selection` (`tests/test_model_tier_rightsizing.py:371-377`) parses frontmatter/TOML and asserts `"model" not in metadata`; 22 test functions / 879 lines confirmed; suite → `22 passed, 287 subtests passed`.

pi-lab column is backwards. `pi-agentic-sdlc-skills/agents/` has 9 agents and **all 9 carry hard static pins** — e.g. `sdlc-integrator.md:5: model: amazon-bedrock/global.anthropic.claude-opus-5`, `sdlc-researcher.md:5: model: bedrock-mantle/openai.gpt-5.6-sol`. That is the *opposite* of a non-static-pin discipline; `right-sizing-design.md:563-566` calls such tables "vendor-locked" and slates them for deletion. The quoted evidence is also wrong: `rg -n "variants/deep-work" src/ scripts/ tests/` returns **12 hits across 7 files**, not "zero hits" (they are secrets-scanner and ADR-park references, so the tier map still has no *routing* consumer — the conclusion survives, the cited measurement does not).

### Row 9 — Gateway-mandatory contradiction → **CONFIRMED, with a double standard**

Confirmed: `rg -in gateway AGENTS.md README.md` → exit 1, zero hits. `SESSION-HANDOFF.md:65,79,96,185` ("Gateway is required for normal inference") and `docs/progress/2026-07-21-product-progress-snapshot.md:34,81,115,151` confirmed, including the self-flagged conflict at :81. pi-lab's falsifiability clause is real and specific (`right-sizing-design.md:703-726`, "What would reopen it", three measured conditions).

**But:** `git status --porcelain` shows `docs/research/2026-08-05-gateway-selection-memo.md` and `…pi-lab-harvest-memo.md` are **also untracked (`??`)**. The analysis treats the memo as authoritative while disqualifying the progress snapshot for the same untracked status. Additionally, `docs/research/2026-08-05-pi-lab-harvest-memo.md` (untracked) already records the fork the analyst presents as a new finding: *"These are not fully reconciled — worth a direct comparison before agentic-sdlc commits to 'gateway mandatory' as policy."* Verdict stands; the novelty claim does not.

### Row 10 — Live-meter discipline → **REFUTED on pi-lab's side** (same evidence as Row 2). No meter writes pi-lab's ledger; pi-lab's own crosswalk declares it read by no code. **Corrected verdict: BOTH DESIGNED.**

### Section-3 claim: README.md:130 plugin validation → **CONFIRMED**
`claude plugin validate --strict .claude-plugin/plugin.json` → exit **1**, `✘ Validation failed (--strict treats warnings as errors)`. README.md:130 asserts *"Both manifests pass `claude plugins validate --strict`."*

---

## Single most important error

**Row 6 / invention-bullet #2 invert the actual behavior of the only executable artifact in this domain.** `receipt_admission.py:355-362` requires the "observed" readback value to *equal the requested value*, so (a) a receipt built purely from the request validates as `verified` with exit 0, and (b) an honest readback reporting a divergent effective effort is **rejected**. The enforcement the analysis calls agentic-sdlc's sharpest original contribution — "requested values never become readback," graded SHIPPED and "mechanically forbids a third requested-as-readback state" — is exactly what the code cannot do; the anti-copy test that appears to prove it passes only on a misspelled field name. This should be regraded **DESIGNED / BOTH SHORT**, and it is a live correctness bug, not merely a mis-grade: the pipeline will stamp `verified` readback digests on receipts containing no readback evidence at all.

Files: `<repo>/skills/model-tier-rightsizing/scripts/receipt_admission.py`, `<repo>/tests/test_runtime_contract_validation.py`, `<workspace>/pi-lab/scripts/lib/capability-crosswalk.ts`, `<workspace>/pi-agentic-sdlc-skills/agents/`, `<workspace>/bedrock-mantle-frontier-bundle/scripts/qualify-cohort`.