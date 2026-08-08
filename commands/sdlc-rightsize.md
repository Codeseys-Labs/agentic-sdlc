---
name: sdlc-rightsize
description: Probe live routing evidence and produce a regenerable model-task map for certified dispatch.
---

Probe and calibrate ONE target's model-routing inputs, then emit a regenerable candidate map. Scope: $ARGUMENTS

1. Load [`skills/model-tier-rightsizing/SKILL.md`](../skills/model-tier-rightsizing/SKILL.md) and its [canonical calibration](../skills/model-tier-rightsizing/references/model-routing-calibration.md). Treat the calibration as generation-specific policy and the probe as route-specific evidence; neither selects a host default, authorizes an outward operation, or replaces the authenticated harness's admission boundary.

2. Parse arguments. The target defaults to `.`. Accept only:
   - `--probe-only` — collect and report live probe and vocabulary evidence without classifying or writing a map;
   - `--regenerate` — rebuild the generated JSON and Markdown companion from current admitted evidence;
   - `--force` — permit replacement of an existing generated pair whose calibration ID, target receipt, or generated-content digest differs; it never overrides a failed probe or safety gate;
   - `--output <json-path>` — write JSON there instead of `<target>/.agentic-sdlc/model-task-map.json`; require a `.json` suffix and write the Markdown companion at the same stem with `.md`;
   - `--dry-run` — perform read-only discovery, vocab checks, and any explicitly selected live canaries, then print the proposed paths, map, and replacement decision without writing files, changing configuration, trusting a checkout, or dispatching workers; and
   - `--ultra` — request consideration of the highest effort band only. It is not an override: admit it only when the exact route exposes the requested vocabulary, has the required live evidence and capacity, preserves the semantic gate, and can supply certified request-injection and identity-readback evidence. Otherwise record the lower certified choice or refuse that map cell.

   Reject unknown flags, duplicate flags with conflicting values, more than one target, a target outside a readable repository, a non-`.json` `--output`, or `--force` without `--regenerate`. Do not mutate a route registry, gateway configuration, Seeds queue, worktree, trust state, or global configuration.

3. Probe the two provider planes before classifying anything.
   - Request `GET http://127.0.0.1:10100/v1/models`, capture the complete catalog bytes, digest, timestamp, endpoint, HTTP result, and all served exact IDs. The gateway is live only if this response is parseable, authenticated where required, and contains the exact ID proposed for every gateway cell.
   - For every gateway canary, inject one exact model ID and requested effort through the real adapter, retain immutable request-injection evidence, and correlate its `requestId` with the gateway attribution record. Source `resolved_provider` and `resolvedModel` only from that attribution record; the response body's `model` value is inadmissible because it can echo the request. Treat `routeKind: "default-provider"`, a missing correlation, empty output, malformed output, or a different resolved model as a failed canary.
   - Apply G2 to every Muse gateway candidate: its requested ID must begin `muse/`, that exact prefixed ID must be present in the served catalog, and its correlated attribution record must not name the default provider. A bare Muse ID is a wrong-provider dispatch, not a fallback. The prefix alone never establishes catalog membership or model identity.
   - Run one bounded native-Bedrock canary through the selected native adapter. It must inject its exact model and requested effort, return non-empty output, and provide the native adapter's identity evidence. Record `native_bedrock_live: true` only after that canary passes; otherwise record `false` and omit or fail closed every native-Bedrock map cell.
   - Capture the effective accepted effort vocabulary for each selected surface. Never infer it from a peer route, a prompt, a settings value, or an echoed request. Keep requested effort separate from effective effort readback; record effective readback as `unavailable` when the transport cannot expose it.

4. Check vocabulary and route admission. Require every proposed `primary`, `complement`, and `fallback` exact ID to be live on its own provider plane, every proposed effort to be in that plane's observed vocabulary, and every context form to remain a requested form rather than a claimed served window. `--ultra` may select `max` only after the ultra gate in step 2 passes; a route whose top usable band is `xhigh` remains `xhigh`. Do not substitute aliases, provider-qualified aliases, bare Muse IDs, inherited settings, or a host default. A catalog-only route may appear only as an explicitly blocked candidate, never as a dispatchable primary or fallback.

5. Classify exactly these eight task classes across all six dimensions. Record the dimension values in each map entry's `classification` object, then choose a semantic tier by wrong-output consequence and gate strength rather than task prestige:

   | `task_class` | `blast_radius` | `determinism_of_gate` | `scope_of_mutation` | `authority_proximity` | `corpus_size` | `dependency_fanout` |
   |---|---|---|---|---|---|---|
   | `mechanical_redo` | local/reversible | complete | one bounded artifact | none | small | none |
   | `deterministic_gated_change` | contained/visible | compiler, test, schema, or exact diff | isolated files | low | small/medium | low |
   | `evidence_extraction` | contained/visible | evidence coverage or schema | read-only | low | medium/large | low |
   | `repository_discovery` | contained semantic omission | partitioned evidence inventory | read-only | low | large | medium |
   | `semantic_implementation` | contained silent degradation | partial; immutable review required | interacting bounded change | medium | medium | medium |
   | `semantic_review` | contained silent acceptance | explicit criteria plus independent review | immutable candidate | medium | medium | medium |
   | `integration_reconcile` | cross-branch or contract damage | re-gate on immutable integration head | multi-component fan-in | high | large | high |
   | `authority_or_frontier` | derail, trust, credential, data-loss, or settled-truth error | fail closed plus re-derivation | advisory only | direct | large when needed | high |

   Choose inside the eligible Sol/Fable, Terra/Opus, or Luna/Sonnet pair by verified transport, task fit, quota, independent perspective, and correlated-error risk. Use the cheapest certified capable-volume route only when a complete deterministic gate makes a wrong result cheap to redo. Fable is a bounded adversarial packet, never the truth-settling primary. Native Bedrock and gateway are separate route families: a success on one does not certify the other.

6. Emit the candidate JSON at `<target>/.agentic-sdlc/model-task-map.json` unless `--output` selects another JSON path. The JSON must use this shape; `map` has exactly the eight keys from step 5, and `provider_plane` is constrained to `gateway` or `native-bedrock`:

   ```json
   {
     "calibration_id": "string",
     "probe": {
       "catalog_ts": "RFC-3339 timestamp",
       "gateway": {
         "endpoint": "http://127.0.0.1:10100/v1/models",
         "live": true,
         "catalog_sha256": "sha256"
       },
       "live_ids": ["exact-model-id"],
       "effort_vocab": {
         "gateway": ["low", "medium", "high", "xhigh"],
         "native-bedrock": ["low", "medium", "high", "xhigh"]
       },
       "native_bedrock_live": true
     },
     "map": {
       "task_class": {
         "classification": {
           "blast_radius": "string",
           "determinism_of_gate": "string",
           "scope_of_mutation": "string",
           "authority_proximity": "string",
           "corpus_size": "string",
           "dependency_fanout": "string"
         },
         "provider_plane": "gateway",
         "primary": {
           "model": "exact-model-id",
           "effort": "observed-effort-vocabulary-value",
           "context": "requested-context-form"
         },
         "complement": "distinct bounded artifact or null",
         "fallback": ["same-control exact route or stop"],
         "gate": "required deterministic or independent control",
         "kill_criteria": "conditions that stop or reduce scope"
       }
     }
   }
   ```

   `calibration_id` must bind the canonical calibration revision, normalized target identity, catalog digest, native canary receipt digest or explicit unavailable state, and classifier version. Do not write secrets, credentials, raw prompts, raw transcripts, or mutable local paths into either output.

7. Emit the Markdown companion alongside the JSON. It must be a human-readable rendering of the same `calibration_id`, probe facts, eight-class dimensions, selected primary/complement/fallback, gate, kill criteria, unavailable evidence, and a short regeneration command. It must link back to [`skills/model-tier-rightsizing/SKILL.md`](../skills/model-tier-rightsizing/SKILL.md) and [`references/model-routing-calibration.md`](../skills/model-tier-rightsizing/references/model-routing-calibration.md), and it must state that the map is a recommendation, not a dispatch receipt or authorization.

8. Preserve idempotence. With the same normalized target, calibration revision, catalog bytes, canary receipts, classifier version, and arguments, render byte-identical JSON and Markdown. On a default run, create the absent pair only; if either output already exists, compare its generated-content digest and refuse replacement. `--regenerate` may replace an intact matching generated pair after the current probes pass. A stale probe, a changed calibration ID, a partial pair, or a user-edited/generated-digest mismatch requires `--regenerate --force`; `--force` still cannot replace an output after failed or incomplete live evidence. `--probe-only` and `--dry-run` never write.

9. Enforce exactly these five failure modes, each fail closed with the affected route or task class named:
   1. Gateway catalog unavailable, malformed, stale, or missing a proposed exact gateway ID.
   2. Missing `requestId` correlation, missing attribution `resolvedModel`, `default-provider` routing, unresolved identity, or a G2 Muse prefix/catalog failure.
   3. Native Bedrock canary failure, empty completion, missing injection evidence, or unavailable native identity evidence for a proposed native cell.
   4. Unsupported, inferred, or unverified effort/context vocabulary, including an `--ultra` request that does not meet the ultra gate.
   5. Unsafe output replacement, incomplete eight-class classification, missing gate/kill criteria, or any fallback that weakens the original semantic control.

10. Describe next steps without dispatching. A workflow looks up `task_class`, chooses the recorded route only if it remains live, and constructs one conductor-supplied `RuntimeAssignment`. Before spawn, the authenticated external harness must inject the exact requested model and effort, preserve immutable request-injection evidence, validate the canonical receipt, verify model identity/readback, and correlate the admitted receipt with spawn evidence. A map lookup, prompt prose, a requested value, a passing canary, or a generated file is never proof of injection and never authorization to spawn, mutate Seeds, merge, publish, deploy, or perform another outward operation.

Examples:

```text
/sdlc-rightsize --probe-only
/sdlc-rightsize . --dry-run
/sdlc-rightsize /repo --regenerate
/sdlc-rightsize /repo --regenerate --force --output /repo/.agentic-sdlc/model-task-map.json
/sdlc-rightsize /repo --regenerate --ultra
```
