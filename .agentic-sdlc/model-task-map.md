# Model task map

> This map is a recommendation, not a dispatch receipt or authorization. It never authorizes
> spawn, queue mutation, merge, publication, deployment, credentials, or another outward effect.

- **Calibration ID:** `six-tier-2026-07-14|1e6422877ea14dc1bd54f0a3a16a1614c69d0ca8e2b315502d3582da5c9b3bd3|975289e1dac10d62ae8aa3da467934682df7351a2012d07d6bc0af41f83b9241|unavailable|eight-class-v1`
- **Calibration revision:** `six-tier-2026-07-14`
- **Classifier:** `eight-class-v1`
- **Normalized target digest:** `1e6422877ea14dc1bd54f0a3a16a1614c69d0ca8e2b315502d3582da5c9b3bd3` (clean Git commit/tree identity)
- **Gateway catalog:** `2026-08-12T15:56:04Z` · HTTP 200 · SHA-256 `975289e1dac10d62ae8aa3da467934682df7351a2012d07d6bc0af41f83b9241`
- **Gateway GPT canary receipt digest:** `0471bd29231004bf852eb4f97f6ce646d2272db099f016cc1e54a5f2ca0bf111`
- **Gateway Muse canary receipt digest:** `d2b6e069b94ac7a29af17ceef015b033ff0ecf5a48d20a03a3513dd5c69a079a`
- **Native Bedrock:** unavailable; no native-Bedrock selector and identity channel was present

Policy: [model-tier-rightsizing](../skills/model-tier-rightsizing/SKILL.md) ·
[canonical calibration](../skills/model-tier-rightsizing/references/model-routing-calibration.md)

## Probe evidence

The gateway was live at `http://127.0.0.1:10100/v1/models`. The following selected tuples
returned non-empty output and were uniquely correlated by `requestId` to `provider=openai`,
the exact `resolvedModel`, and `routeKind=native` (never `default-provider`):

| Model | Requested effort | Request ID | Identity |
|---|---:|---|---|
| `gpt-5.6-luna` | `high` | `ocx-msp86s1q-dd` | verified |
| `gpt-5.6-luna` | `low` | `ocx-msp86c6o-d6` | verified |
| `gpt-5.6-sol` | `xhigh` | `ocx-msp87izh-dj` | verified |
| `gpt-5.6-terra` | `xhigh` | `ocx-msp87g5b-dh` | verified |

The following effort-free Muse requests also returned non-empty output. Each exact namespaced
catalog ID correlated to `provider=muse`, `routeKind=explicit-provider`, and the matching
provider-native `resolvedModel`; none used `default-provider`. The namespace is the gateway
dispatch form, while the attribution record deliberately reports the provider-native suffix:

| Exact dispatch ID | Resolved model | Request ID | G2 identity |
|---|---|---|---|
| `muse/muse-spark-1.1` | `muse-spark-1.1` | `ocx-msq9iuq4-j4` | verified |
| `muse/muse-spark-1.2` | `muse-spark-1.2` | `ocx-msq9iw2b-j5` | verified |
| `muse/muse-spark-1.2-contributor` | `muse-spark-1.2-contributor` | `ocx-msq9iy77-j6` | verified |

The selected GPT routes share the catalog-observed gateway vocabulary `low`, `medium`, `high`,
`xhigh`, and `max`; this map selected only the correlated `low`, `high`, and `xhigh` tuples
above. Muse advertises no effort channel, so none was sent or inferred. The attribution records
did not expose independent effective-effort or context-window readback for these routes.
Those fields are therefore **unavailable**, not copied from requested values. `base` in the map
is a requested context form, not a served-window claim.

Native Bedrock was not probed because this host exposed no genuine native-Bedrock adapter,
selector, or identity evidence. The ordinary Claude subscription passthrough is a different
route and was not relabeled as Bedrock. Consequently no native-Bedrock primary, complement,
or dispatchable fallback appears below.

## Complete ccodex catalog

All ten served IDs were inspected. The three selected GPT IDs received effort-bearing role
canaries; all three Muse IDs received effort-free G2 route canaries. The remaining GPT rows
are catalog evidence only. The `ultra` label was not requested; the adapter boundary maps it
to `max`, so it is not admitted by this run. Muse is dispatchable but remains tier/role-unproven.

| Exact catalog ID | Advertised effort values | Dispatch status in this map |
|---|---|---|
| `gpt-5.6-sol` | low, medium, high, xhigh, max, ultra | selected and correlated |
| `gpt-5.6-terra` | low, medium, high, xhigh, max, ultra | selected and correlated |
| `gpt-5.6-luna` | low, medium, high, xhigh, max | selected and correlated |
| `gpt-5.5` | low, medium, high, xhigh | catalog-only; not dispatchable |
| `gpt-5.4` | low, medium, high, xhigh | catalog-only; not dispatchable |
| `gpt-5.4-mini` | low, medium, high, xhigh | catalog-only; not dispatchable |
| `gpt-5.3-codex-spark` | low, medium, high, xhigh | catalog-only; not dispatchable |
| `muse/muse-spark-1.1` | none advertised | dispatchable and G2-correlated; mechanical experiment only |
| `muse/muse-spark-1.2` | none advertised | dispatchable and G2-correlated; mechanical experiment only |
| `muse/muse-spark-1.2-contributor` | none advertised | dispatchable and G2-correlated; mechanical experiment only |

## Eight-class recommendation

### `mechanical_redo`

- **Classification:** blast radius `local/reversible`; gate `complete`; mutation `one bounded artifact`; authority `none`; corpus `small`; fanout `none`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-luna` · effort `low` · requested context `base`
- **Complement:** muse/muse-spark-1.2 — routed mechanical experiment (no effort channel; shared-pool output budget set explicitly)
- **Fallback:** gpt-5.6-luna high — same capable-volume route; preserve the complete deterministic check
- **Gate:** complete deterministic check (compiler, test, schema, or exact diff)
- **Kill criteria:** no complete check is available — escalate to deterministic_gated_change

### `deterministic_gated_change`

- **Classification:** blast radius `contained/visible`; gate `compiler, test, schema, or exact diff`; mutation `isolated files`; authority `low`; corpus `small/medium`; fanout `low`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-luna` · effort `high` · requested context `base`
- **Complement:** none
- **Fallback:** gpt-5.6-terra xhigh — stronger certified route; retain the deterministic gate
- **Gate:** compiler, test, schema, or exact-diff acceptance check
- **Kill criteria:** gate still fails after one bounded same-tuple retry — reduce scope or escalate

### `evidence_extraction`

- **Classification:** blast radius `contained/visible`; gate `evidence coverage or schema`; mutation `read-only`; authority `low`; corpus `medium/large`; fanout `low`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-luna` · effort `high` · requested context `base`
- **Complement:** gpt-5.6-terra xhigh — bounded source-coverage audit
- **Fallback:** gpt-5.6-terra xhigh — stronger certified route; retain schema and source-coverage checks
- **Gate:** closed output schema plus source-by-source evidence coverage
- **Kill criteria:** required sources, citations, or schema fields remain unaccounted for

### `repository_discovery`

- **Classification:** blast radius `contained semantic omission`; gate `partitioned evidence inventory`; mutation `read-only`; authority `low`; corpus `large`; fanout `medium`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-terra` · effort `xhigh` · requested context `base`
- **Complement:** gpt-5.6-luna high — partitioned inventory cross-check
- **Fallback:** gpt-5.6-sol xhigh — stronger certified route; retain the partitioned inventory control
- **Gate:** partitioned evidence inventory with explicit unknowns and omission cross-check
- **Kill criteria:** unexplained partition gaps or unknowns would change the plan

### `semantic_implementation`

- **Classification:** blast radius `contained silent degradation`; gate `partial; immutable review required`; mutation `interacting bounded change`; authority `medium`; corpus `medium`; fanout `medium`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-terra` · effort `xhigh` · requested context `base`
- **Complement:** gpt-5.6-sol xhigh — bounded immutable-delta risk review
- **Fallback:** gpt-5.6-sol xhigh — stronger certified route; retain independent immutable-candidate review
- **Gate:** explicit acceptance criteria plus a separate review of the immutable candidate
- **Kill criteria:** acceptance criteria remain unmet after bounded backflow

### `semantic_review`

- **Classification:** blast radius `contained silent acceptance`; gate `explicit criteria plus independent review`; mutation `immutable candidate`; authority `medium`; corpus `medium`; fanout `medium`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-terra` · effort `xhigh` · requested context `base`
- **Complement:** gpt-5.6-sol xhigh — bounded adversarial re-derivation
- **Fallback:** gpt-5.6-sol xhigh — stronger certified route; preserve explicit criteria and adjudication
- **Gate:** explicit review criteria plus separate adversarial re-derivation; conductor adjudicates
- **Kill criteria:** material disagreement remains unresolved or the candidate changes during review

### `integration_reconcile`

- **Classification:** blast radius `cross-branch or contract damage`; gate `re-gate on immutable integration head`; mutation `multi-component fan-in`; authority `high`; corpus `large`; fanout `high`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-terra` · effort `xhigh` · requested context `base`
- **Complement:** gpt-5.6-sol xhigh — immutable integration-head contract audit
- **Fallback:** gpt-5.6-sol xhigh — stronger certified route; re-gate the same immutable integration head
- **Gate:** full repository gate and independent contract review on the immutable integration head
- **Kill criteria:** conflict semantics are unclear, a contract check fails, or the integration head moves

### `authority_or_frontier`

- **Classification:** blast radius `derail, trust, credential, data-loss, or settled-truth error`; gate `fail closed plus re-derivation`; mutation `advisory only`; authority `direct`; corpus `large when needed`; fanout `high`
- **Provider plane:** `gateway`
- **Primary:** `gpt-5.6-sol` · effort `xhigh` · requested context `base`
- **Complement:** none
- **Fallback:** stop — no live certified independent frontier peer on native-bedrock
- **Gate:** independent non-model re-derivation and conductor adjudication; advisory scope only
- **Kill criteria:** authority boundary is unresolved or independent re-derivation is unavailable

## Unavailable and blocked evidence

- Effective effort readback: unavailable for the selected gateway Responses route.
- Effective context readback: unavailable; every `base` value is request-only.
- Native Bedrock: unavailable; all native-Bedrock cells are omitted.
- Claude Fable/Opus/Sonnet: not certified on native Bedrock by this run and not dispatchable here.
- Muse: all three namespaced routes are dispatchable and G2-correlated, but advertise no effort channel.
  They remain bounded to complete-deterministic-gate mechanical experiments and are not selected as a calibrated primary.
- Remaining GPT catalog IDs: live catalog entries only; no task-map role canary was run.

## Regeneration

From the repository root, run:

```text
/sdlc-rightsize . --regenerate
```

Regenerate when the calibration revision, target identity, catalog bytes, selected tuple
evidence, effort vocabulary, context policy, or native-Bedrock availability changes.
A workflow must still recheck route liveness and construct one conductor-supplied
`RuntimeAssignment` with immutable request-injection evidence, receipt validation, and
model identity/readback before spawn.
