---
name: sdlc-rightsize
description: Discover eligible routes, plan bounded local evaluations, and render a Pareto model-task map.
---

Build or refresh ONE target's evidence-backed model-task map. Scope: $ARGUMENTS

1. Load [`skills/model-tier-rightsizing/SKILL.md`](../skills/model-tier-rightsizing/SKILL.md), its [canonical calibration](../skills/model-tier-rightsizing/references/model-routing-calibration.md), and the [v2 map contract](../skills/model-tier-rightsizing/references/model-task-map-schema.md). The map is a recommendation, not a dispatch receipt or authorization.

   Do not dispatch any worker while running this command: not a generic `Explore` or `Plan` agent, not a generated `ocx-*` agent, not a workflow worker, and not an inherited/default subagent. A host-visible placeholder such as `model: "haiku"` is not proof of an OCX pin and may select a real Claude model on a generic agent type. Discovery, canaries, and evaluations below are direct bounded calls through the reviewed evaluator; never delegate around missing route evidence.

2. Parse arguments. The target defaults to `.`. Accept:

   - `--spec <json-path>` — non-interactive `rightsize-run-spec/v1`; use `-` for stdin;
   - `--evidence <json-path>` — reuse a compatible `rightsize-evidence/v1` through the evaluator's `render` subcommand;
   - `--probe-only` — discover and, after approval, probe selected exact routes without task qualification;
   - `--pilot` — run the selected smoke or representative pack; pilot evidence never promotes;
   - `--qualify` — run a target-representative pack under the qualification thresholds;
   - `--task-pack <json-path|builtin:harness-smoke-v1>`;
   - repeated `--source`, `--model`, and `--task-class` selections;
   - `--attempts <n>`, `--max-calls <n>`, `--max-wall-seconds <n>`, `--max-api-equivalent-usd <amount>`, and `--expected-peak-input-tokens <n>`;
   - `--pareto-objective <reliability|api-equivalent-cost|tokens-or-quota|wall-time>`;
   - `--allow-usage-credits` and `--ack-target-data-egress` — explicit acknowledgements, never inferred;
   - `--output <json-path>` — default `.agentic-sdlc/model-task-map.json`;
   - `--regenerate` and `--force` — `--force` requires `--regenerate` and never overrides failed evidence;
   - `--dry-run` — discover and plan only; no model calls or output writes.

   Reject unknown flags, conflicting depth flags, duplicate conflicting values, multiple targets, a non-repository target, an output outside the target, or a non-`.json` output. Keep `--probe-only`, `--regenerate`, `--force`, `--output`, and `--dry-run` compatible with earlier invocations. Retire `--ultra`: use an exact per-route effort in `--spec`; do not translate it into a global band.

3. Run read-only discovery first:

   ```text
   uv run --python 3.12.11 --script skills/model-tier-rightsizing/scripts/rightsize.py discover --target <target>
   ```

   It reads the raw loopback gateway catalog, `ocx models live --json`, configured providers, the checked-in runtime policy, and a PII-stripped `claude auth status --json`. Keep these states separate:

   - provider registry presence;
   - configured provider;
   - exact live catalog member;
   - successful route probe;
   - locally role-qualified route;
   - exact tuple admitted by `runtime-assignment-receipt-v1.json`.

   Claude subscription passthrough is a `gateway-claude-subscription-passthrough` route using the operator's existing `claude.ai` login; it is not an OCX catalog row or a separate plane. Never read, print, copy, or persist credential, email, or organization values.

4. If `--spec` did not resolve every choice, ask only environment-relevant questions. Ask at most four questions per tool call and at most four options per question. `AskUserQuestion` supplies its own free-text **Other** path; never add a duplicate Other option.

   - **Sources** — multi-select among live configured OCX providers and usable Claude subscription passthrough. Do not show registry-only providers as selectable.
   - **Models** — multi-select exact IDs or families found for the selected sources. Batch long lists into groups of four. A free-text model remains a blocked candidate until its exact route is discovered and probed.
   - **Task classes** — present the eight classes as two four-option multi-select questions; omit a class already fixed by a selected task pack.
   - **Depth** — probe, pilot, qualification, or reuse compatible evidence. Qualification requires an explicit target-representative pack.
   - **Objective** — reliability, API-equivalent cost, tokens/quota, or wall time.
   - **Budget/context** — ask for call count, wall time, API-equivalent spend, attempts, and expected peak input only when not supplied. Free text carries numeric custom values.
   - **Effects** — if target content leaves the machine, require data-egress acknowledgement. If Fable or Claude `[1m]` may consume usage credits, require `allow_usage_credits`; `$0` is never assumed.
   - **Replacement** — create, regenerate, or regenerate with force only when outputs already exist.

   Normalize answers into one closed `rightsize-run-spec/v1`. In a non-interactive host, unresolved input fails as `question-required:<field>`; never select all providers, a host default, or a budget silently.

5. Model every route as an exact tuple:

   ```json
   {
     "transport_surface": "claude-code-gateway",
     "route_kind": "gateway-routed-provider",
     "provider": "openai",
     "auth_basis": "provider-credential",
     "billing_basis": "api-token",
     "requested_model_id": "gpt-5.6-luna",
     "requested_effort": "high",
     "requested_context_form": "base"
   }
   ```

   For subscription passthrough use `route_kind: "gateway-claude-subscription-passthrough"`, `provider: "anthropic"`, `auth_basis: "operator-claude-login"`, and `billing_basis: "claude-subscription"`. Do not use aliases.

6. Plan before any live call:

   ```text
   uv run --python 3.12.11 --script skills/model-tier-rightsizing/scripts/rightsize.py plan --target <target> --spec <spec>
   ```

   Show the normalized routes, task pack and verifier types, exact call count, selected providers as data-egress destinations, call/time/API-equivalent-cost limits, possible subscription quota or usage-credit effects, output paths, stop conditions, and `authorization_digest`.

   - `--dry-run` stops here.
   - Otherwise ask one final single-select question: **Run evaluation**, **Adjust choices**, or **Cancel**.
   - Only **Run evaluation** authorizes the exact displayed plan. Pass its digest to `evaluate`. A changed catalog, task pack, spec, budget, target identity, or benchmark snapshot changes the digest and requires a new confirmation.

7. Evaluate through the existing launcher only:

   ```text
   uv run --python 3.12.11 --script skills/model-tier-rightsizing/scripts/rightsize.py evaluate \
     --target <target> --spec <spec> --authorization-digest <digest>
   ```

   The evaluator pins the full model, effort, and context request form; disables fallback and session persistence; uses safe mode, ordinary `dontAsk` permissions, structured output, and the task pack's closed tools. It copies fixtures into an isolated temporary workspace and never mutates the target. Bash, web, subagents, workflows, permission bypass, ambient secrets, path-escaping symlinks, and unbounded gates are forbidden.

   Capture gateway attribution before each serial attempt and correlate only new records. For routed providers require raw catalog membership, intended provider, non-`default-provider` routing, and gateway-log `resolvedModel`; the response body `model` is inadmissible. A Muse candidate must use its exact `muse/` ID. For Claude passthrough require an exact `claude-*` ID, `anthropic-native` attribution, no fallback, and the checked-in unambiguous mapping; missing or ambiguous identity blocks the route. Requested effort/context never become effective readback.

8. Apply the local evidence ladder:

   - `catalog-only` — exact ID discovered, no live call;
   - `route-probed` — exact route answered with verified identity;
   - `role-qualified` — only a qualification pack may write this task-class-scoped rung.

   `builtin:harness-smoke-v1` tests harness mechanics only and can never promote. Qualification requires a digest-bound target-representative pack, at least five distinct held-out tasks per selected class, three attempts per task, at least 90% accepted attempts, a 95% Wilson lower bound of at least 0.70, zero route/identity failures, and zero critical-task failures. Every `authority_or_frontier` case is critical and must pass every attempt. A new exact tuple remains production-blocked until the checked-in runtime receipt policy admits it; local qualification does not rewrite that policy.

9. Compute task-class-specific Pareto fronts after hard-filtering route identity, context fit, semantic control, qualification, and runtime-policy admission. Record:

   - accepted rate and 95% Wilson interval;
   - transport/identity failure rate;
   - input, uncached input, cache-read, cache-write, reasoning, visible-output, and total tokens;
   - wall time, first-output latency, and steps;
   - mean/median cost, tokens, and wall time per attempt;
   - observed cost, tokens, and wall time per accepted result;
   - subscription quota/usage-credit state and cost provenance.

   `observed cost per accepted = compatible observed cost / accepted successes`; it is unavailable at zero successes. Claude subscription marginal cost is `null`, never `$0`; API-equivalent cost may remain useful but must be labeled. Missing dimensions are not zero and cannot establish dominance. Never merge active-agent wall time with decode-time estimates, or average `observed`, `declared`, and `mined` evidence; precedence remains `observed > declared > mined`.

10. Treat context as a hard feasibility constraint. Use expected peak input plus output reserve and the policy margin. Select the smallest certified request form that fits. Keep `requested_model_id` and `requested_context_form` separate in JSON; Markdown may render the familiar `[1m]` suffix. Native 1M-base models and Muse's shared pool stay `base`. Never choose `[1m]` because it ranks higher, infer it from a family, or claim served context from a request. An uncertified `[1m]` tuple is blocked.

11. Emit a fail-closed trio:

   - `<stem>.json` — `model-task-map/v2` with all eight classifications, exact route registry, structured primary/complement/fallback routes, Pareto front, qualification and runtime-admission states, gates, and kill criteria;
   - `<stem>.md` — the same recommendation and limitations for humans;
   - `<stem>.evidence.json` — non-sensitive observed metrics, closed attribution excerpts, and digests.

   Never write raw prompts, completions, transcripts, repository content, credentials, PII, secret-shaped values, or mutable absolute paths. Identical evidence renders byte-identical output. Default creation refuses existing artifacts; regeneration requires a complete valid v2 trio. A partial set, v1 artifact, stale/generated-digest mismatch, or user edit requires `--regenerate --force`; failed evidence never replaces prior outputs.

12. Published evidence in [`model-benchmark-evidence-2026-08-12.json`](../skills/model-tier-rightsizing/references/model-benchmark-evidence-2026-08-12.json) may nominate or order already route-probed candidates for evaluation. It cannot raise a qualification rung, fill a scale-setter slot, prove context, or grant runtime admission. The full applicability/limitation record is in [`docs/research/2026-08-12-model-rightsizing-benchmarks.md`](../docs/research/2026-08-12-model-rightsizing-benchmarks.md).

13. Stop after reporting the recommendation, blocked routes, provenance, and reproduction command. Do not mutate provider configuration, gateway configuration, Seeds, worktrees, trust, global settings, or production assignments. Do not spawn, merge, publish, deploy, or perform another outward operation. **Before spawn**, the authenticated external harness still builds and validates one `RuntimeAssignment` immediately before any separately authorized worker.

Examples:

```text
/sdlc-rightsize --dry-run
/sdlc-rightsize . --pilot --task-pack builtin:harness-smoke-v1
/sdlc-rightsize /repo --qualify --task-pack .agentic-sdlc/evals/change-writing-v1.json
/sdlc-rightsize /repo --spec .agentic-sdlc/rightsize-run.json --dry-run
/sdlc-rightsize /repo --spec .agentic-sdlc/rightsize-run.json --regenerate --force
```
