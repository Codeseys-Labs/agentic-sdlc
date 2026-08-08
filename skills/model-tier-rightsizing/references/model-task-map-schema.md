# `model-task-map.json` schema

Companion to [`sdlc-rightsize`](../../../../commands/sdlc-rightsize.md).
Emitted at `<target>/.agentic-sdlc/model-task-map.json` with a Markdown twin
at the same stem plus `.md`. Calibration owns windows and tiers; the probe owns
liveness; this file owns the on-disk shape downstream `Workflow()` DAG nodes read.

Links: [SKILL](../SKILL.md) · [calibration](model-routing-calibration.md) ·
[prompt budget](workflow-prompt-budget.md)

> The map is a recommendation, not a dispatch receipt or authorization. A
> `Workflow` still builds a `RuntimeAssignment` with injection evidence and
> readback before spawn.

## Top-level shape

```json
{
  "calibration_id": "six-tier-2026-07-14|<target-sha256>|<catalog-sha256>|<native-receipt-sha256|unavailable>|<classifier-version>",
  "probe": {
    "catalog_ts": "2026-08-08T13:58:00Z",
    "gateway": {
      "endpoint": "http://127.0.0.1:10100/v1/models",
      "live": true,
      "catalog_sha256": "sha256 of raw GET bytes"
    },
    "live_ids": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "muse/muse-spark-1.2"],
    "effort_vocab": {
      "gateway": ["low", "medium", "high", "xhigh"],
      "native-bedrock": ["low", "medium", "high", "xhigh"]
    },
    "native_bedrock_live": true
  },
  "map": {
    "<task_class>": {
      "classification": {
        "blast_radius": "string",
        "determinism_of_gate": "string",
        "scope_of_mutation": "string",
        "authority_proximity": "string",
        "corpus_size": "string",
        "dependency_fanout": "string"
      },
      "provider_plane": "gateway | native-bedrock",
      "primary": { "model": "exact-id", "effort": "low..max", "context": "base | [1m]" },
      "complement": "distinct bounded artifact or null",
      "fallback": ["same-control exact route or stop"],
      "gate": "required deterministic or independent control",
      "kill_criteria": "conditions that stop or reduce scope"
    }
  }
}
```

| Field | Constraint |
|---|---|
| `calibration_id` | binds calibration revision, normalized target identity, catalog digest, native canary receipt digest or `unavailable`, and classifier version |
| `probe.catalog_ts` | RFC 3339 capture time of the `GET /v1/models` bytes |
| `probe.gateway` | liveness of the gateway plane; `false` fails closed every gateway cell |
| `probe.live_ids` | exact IDs correlated via `requestId` → `resolvedModel`; body `model` inadmissible; bare `muse-*` is wrong-provider (G2) |
| `probe.effort_vocab` | observed vocabulary per plane; never inferred from a peer, a prompt, or `requested_effort` echo |
| `probe.native_bedrock_live` | native `claude --model fable/opus/sonnet --print` canary; `false` omits every `native-bedrock` cell |
| `map` | exactly the eight keys from `sdlc-rightsize` §5 |
| `provider_plane` | `gateway` or `native-bedrock`; a success on one does not certify the other |
| `primary.context` | requested form `base` or `[1m]`; Muse has no `[1m]`; Claude `[1m]` not certified until `policy/runtime-assignment-normative-contract-v1.json` lists it |

## The eight task classes

| `task_class` | `blast_radius` | `determinism_of_gate` |
|---|---|---|
| `mechanical_redo` | local/reversible | complete |
| `deterministic_gated_change` | contained/visible | compiler, test, schema, or exact diff |
| `evidence_extraction` | contained/visible | evidence coverage or schema |
| `repository_discovery` | contained semantic omission | partitioned evidence inventory |
| `semantic_implementation` | contained silent degradation | partial; immutable review required |
| `semantic_review` | contained silent acceptance | explicit criteria plus independent review |
| `integration_reconcile` | cross-branch or contract damage | re-gate on immutable integration head |
| `authority_or_frontier` | derail, trust, credential, data-loss, or settled-truth error | fail closed plus re-derivation |

Full six-dimension rows (adding `scope_of_mutation`, `authority_proximity`, `corpus_size`, `dependency_fanout`) live in `sdlc-rightsize` §5. Record all six in each `classification`.

## Tier and fallback illustration

| Task class | Tier | `provider_plane` | `primary` | `complement` | Fallback |
|---|---|---|---|---|---|
| `authority_or_frontier` | Frontier | `gateway` | `gpt-5.6-sol` `xhigh` `base` | bounded Fable adversarial packet (`native-bedrock` when live, otherwise qualified-not-live note) | same-control frontier only, else stop |
| `semantic_implementation` | Judgment | `gateway` | `gpt-5.6-terra` `xhigh` `base` | Opus delta review (`native-bedrock` when live) | same-control judgment, never volume |
| `mechanical_redo` | Volume/mechanical | `gateway` | `gpt-5.6-luna` `low` `base` | `muse/muse-spark-1.2` experiment (`gateway`, no effort) or cheapest certified peer | cheapest certified with complete check |

Fallback never weakens the original semantic control (frontier→frontier, judgment→judgment). Fable never settles truth. Muse sits on mechanical only.

## Example rows

`authority_or_frontier` (`native-bedrock` not live on gateway):

```json
"authority_or_frontier": {
  "classification": { "blast_radius": "derail, trust, credential, data-loss, or settled-truth error", "determinism_of_gate": "fail closed plus re-derivation", "scope_of_mutation": "advisory only", "authority_proximity": "direct", "corpus_size": "large when needed", "dependency_fanout": "high" },
  "provider_plane": "gateway",
  "primary": { "model": "gpt-5.6-sol", "effort": "xhigh", "context": "base" },
  "complement": "claude-fable-5 max (native-bedrock, not-live today) — bounded adversarial packet",
  "fallback": ["stop — no same-control live fallback"],
  "gate": "independent re-derivation; conductor adjudicates",
  "kill_criteria": "unresolved authority boundary or missing peer re-derivation"
}
```

`semantic_implementation` (contained):

```json
"semantic_implementation": {
  "classification": { "blast_radius": "contained silent degradation", "determinism_of_gate": "partial; immutable review required", "scope_of_mutation": "interacting bounded change", "authority_proximity": "medium", "corpus_size": "medium", "dependency_fanout": "medium" },
  "provider_plane": "gateway",
  "primary": { "model": "gpt-5.6-terra", "effort": "xhigh", "context": "base" },
  "complement": "claude-opus-4-8 high — immutable delta review",
  "fallback": ["gpt-5.6-sol high — same judgment control, higher cost"],
  "gate": "explicit acceptance criteria plus independent review of immutable candidate",
  "kill_criteria": "criteria unmet after bounded backflow (act 3)"
}
```

`mechanical_redo` (cheap redo):

```json
"mechanical_redo": {
  "classification": { "blast_radius": "local/reversible", "determinism_of_gate": "complete", "scope_of_mutation": "one bounded artifact", "authority_proximity": "none", "corpus_size": "small", "dependency_fanout": "none" },
  "provider_plane": "gateway",
  "primary": { "model": "gpt-5.6-luna", "effort": "low", "context": "base" },
  "complement": "muse/muse-spark-1.2 — routed mechanical experiment (no effort channel; shared-pool output budget set explicitly)",
  "fallback": ["claude-sonnet-5 low (native-bedrock, requires live canary)"],
  "gate": "complete deterministic check (compiler/test/schema/diff); retry or escalate on any mismatch",
  "kill_criteria": "no complete check available — escalate to capable volume"
}
```

## Consumer contract

```js
const entry = map[task_class];
const candidate = entry.provider_plane === "gateway" ? probe.gateway.live : probe.native_bedrock_live;
if (!candidate || !probe.live_ids.includes(entry.primary.model)) throw new Error(`not-live: ${task_class}`);
const assignment = {
  requested_model_id: entry.primary.model,
  requested_effort: entry.primary.effort,
  requested_context_form: entry.primary.context,
  // harness still injects, preserves request_injection_evidence,
  // validates receipt, correlates resolvedModel by requestId, and records
  // model/effort/context readback as unavailable unless transport exposes it
};
```

## Regeneration triggers

Regenerate on: `calibration_id` change, catalog membership change
(`GET /v1/models` digest differs), effort vocabulary change (e.g. `ultra`
appears/disappears), `modelContextWindows` or `autoCompactWindow` change, or
`native-bedrock` canary flip. Treat any of these as stale until re-probed.

## Failure handling

`sdlc-rightsize` §9 — five fail-closed modes (catalog unavailable, attribution
mismatch/G2 prefix, native canary failure, unsupported vocab/context, unsafe
replacement or incomplete eight-class map). A stale, partial, or user-edited
pair requires `--regenerate --force`; `--force` never overrides a failed probe.
