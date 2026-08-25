# Workflow prompt budget and `[1m]` usage

**Scope:** every `Workflow()` and subagent dispatcher in this bundle. Load this
when a workflow prompt fails `Prompt is too long`, when a brief needs to carry
corpus or repository evidence, or when choosing between `base` and `[1m]`
`requested_context_form`. This file owns no model, effort, or quota fact — it
points to the canonical calibration for those. It owns the prompt-budget
discipline that keeps dispatches inside the transport's window.

Keep four facts separate (from `model-routing-calibration.md`):

1. **Requested dispatch** — exact model ID, effort, and context form sent.
2. **Resolved readback**    — what the adapter or upstream independently reported.
3. **Task-local smoke result** — did a bounded lens receive a correct answer.
4. **Production recommendation** — blast-radius policy plus evidence.

`[1m]` touches only (1) and, indirectly, (2). It never proves (3) or (4).

## 1. What `[1m]` is and is not

`[1m]` is a **client-side context/compaction control** in the current
Codex/ccodex path. It requests a larger upstream context window after dispatch.
It does not name a different upstream model, does not prove an upstream 1M
window was granted, does not increase intelligence, and does not satisfy an
effort or capability claim on its own. **OCX Ultracode Workflow is a distinct
request-form policy:** every explicit `agent()` `model` ID must carry `[1m]`.
The exact marked model/effort/context tuple must be certified, admitted, and
readable before the call; otherwise stop before dispatch and return one
`SeedProposal`. Never remove the marker, select a base form, or retry an
unsuffixed form in that mode. The sibling receipt field
`requested_context_form` is the request; `context_readback_status` remains
`unavailable` unless transport telemetry independently exposes effective context
behaviour. Never copy `requested_context_form: "[1m]"` into a readback field.

Executed readback behaviour (from `model-routing-calibration.md §[1m] boundaries`):

- `gpt-5.6-sol[1m]` reads back as `gpt-5.6-sol`
- `gpt-5.6-terra[1m]` reads back as `gpt-5.6-terra`
- `gpt-5.6-luna[1m]` reads back as `gpt-5.6-luna`

Base-model readback also does not prove compaction occurred. Verify compaction
through client telemetry and a representative task that actually reaches the
boundary.

**One-million semantics** (from `policy/runtime-assignment-normative-contract-v1.json`):

> A `[1m]` request or base-ID readback proves neither intelligence, upstream
> context capacity, compaction, nor effort compliance.

If a brief claims "`[1m]` guarantees 1M and more intelligence," that claim is
wrong and must be rejected — see `tests/test_model_tier_rightsizing.py`.

## 2. Where `[1m]` is certified

From `policy/runtime-assignment-normative-contract-v1.json`
`certified_context_forms_by_model` and `certified_request_tuples`:

| Model | `base` | `[1m]` | Notes |
|---|---|---|---|
| `gpt-5.6-sol` | yes | **yes** | 10 tuples (5 efforts × 2 forms) |
| `gpt-5.6-terra` | yes | **yes** | same |
| `gpt-5.6-luna` | yes | **yes** | same |
| `claude-fable-5` | yes | **no** | exact Claude `[1m]` forms were not separately certified |
| `claude-opus-4-8` | yes | **no** | outside OCX Ultracode Workflow, compact packets / immutable deltas; inside it, stop before dispatch |
| `claude-sonnet-5` | yes | **no** | until those forms pass; never remove `[1m]` to dispatch in OCX Ultracode Workflow |
| `muse-spark-1.1` / `1.2` / `1.2-contributor` | no entry | **no** | Muse has no `[1m]` and no effort channel (`reasoning.effort` not exposed); see calibration §Muse two routes |

A `RuntimeAssignment` with `requested_context_form: "[1m]"` for a Claude
model is **invalid** until tuple-specific policy evidence exists — `receipt_admission.py`
will reject it. Do not append `[1m]` to a Claude or Muse model string to
"fix" a long prompt.

Valid `RuntimeAssignment` shape for a GPT long-context request:

```json
{
  "requested_model_id": "gpt-5.6-sol",
  "requested_effort": "xhigh",
  "requested_context_form": "[1m]"
}
```

Some harnesses spell this as `gpt-5.6-sol[1m]` in the outbound wire string;
the receipt splits it back into `requested_model_id` + `requested_context_form`.
Do not write both — use the canonical two-field form and let the adapter
encode the wire string.

## 3. When to use `[1m]` — and when not to

Outside OCX Ultracode Workflow mode, use `[1m]` **only** for a GPT assignment
that will carry a transcript-, corpus-, or repository-heavy payload and is on
a certified GPT route. The calibration's concrete triggers:

In OCX Ultracode Workflow mode, **every** explicit `agent()` model ID is
instead the exact marked request form. Do not infer that an unmarked model is
allowed because its prompt is small: certification, active-catalog admission,
and request/identity evidence decide whether it may run. An uncertified or
unsupported marked form, including a namespaced model whose active adapter has
not admitted `muse/muse-spark-1.2[1m]` as an exact tuple, stops before dispatch
and returns one `SeedProposal`; it does not reopen the base form.

- **Frame / Plan** that consumes repository-wide evidence (`sol xhigh [1m]`)
- **Discover** with repository-wide readers (`terra xhigh [1m]`)
- **Research** with long corpora (`terra xhigh/max [1m]`)
- Any phase where the corpus budget (next section) legitimately requires more
  than a compact packet

Do **not** use `[1m]`:

- To paper over a brief that dumps a tarball, bundle, or `dist` artifact
  whole into context — fix the brief (section 5) instead.
- For Claude or Muse work — keep packets compact; `Muse` has a shared
  input+output pool of exactly 1048576 but no `[1m]` marker, and
  `claude-fable-5`/`opus`/`sonnet` have no certified `[1m]` tuple.
- As a default "make every worker smarter" switch — route by blast radius
  (`deep-work-loop.md §Effort routing`), not by marker presence.
- To raise the session floor — see section 4.

Probe before use (from `model-routing-calibration.md §Rerun triggers`):
re-probe exact Claude `[1m]` forms before any repository-heavy Claude work,
and capture upstream resolved-effort telemetry for the exact requested band on
both `base` and `[1m]` where applicable.

## 4. Context windows, the session floor, and output-budget interaction

The calibration is the sole owner of per-model windows. The session floor lived
there is **272000** — the smallest real window among the *actually selected*
set (the 5.6 family's provider-served 272000 at the time it was adopted).
Re-derive it when the selected set changes; adding a smaller model obliges
lowering the floor.

Key facts that constrain `[1m]` use:

- **Session floor is process-wide.** One value per session, regardless of which
  model answers a request. Agents and subagents carry no context field. A
  session that fans out across models cannot hold a per-model window at the
  session layer — that is why the floor must be safe for the smallest reachable
  model, not the largest. Raising it toward 1M as a global default pushes the
  compaction net behind mid-size models' real ceilings and can disqualify them
  from extended-context marking. A single-model session that will genuinely stay
  on one large model may raise the floor to that model's own window explicitly
  and temporarily — document it as an opt-in, not a default.

- **Gateway vs provider windows disagree.** For the 5.6 family the gateway
  computed 372000 while the provider catalog serves 272000 on subscription; the
  dangerous direction is over-estimating, so the lower number is the operating
  limit until the two agree.

- **GPT vs Muse shapes are not interchangeable.** GPT publishes a separate
  input window plus an output reservation (e.g. 922000 in + 128000 out for the
  5.6 family, totalling 1050000 API / 272000 subscription). Muse has one
  **shared** pool of exactly 1048576 (`2^20`) measured by bisection:
  `max_output_tokens = 1048576 − counted_input`. Input and output compete
  directly. A large input silently shrinks the output allowance. An insufficient
  output budget on a shared pool returns HTTP 200 with empty content and
  `status: incomplete` while reasoning tokens are still billed — a liveness
  check that asserts only HTTP 200 is worthless there. On trivial prompts,
  reasoning consumption ranged 48–499 tokens, so an output budget below ~600
  risks an empty completion even for a one-word answer.

- **Output budget interacts with the window.** The client defaults
  `max_output_tokens` to 32000 for gateway-served model IDs it does not
  recognise, and raising that value reduces the context available before
  auto-compaction triggers even on separate-reservation models. On a shared pool
  the trade is exact. Set the output ceiling explicitly on shared-pool sessions
  — high enough to clear the ~600-token reasoning floor plus the task's expected
  output, low enough not to eat needed input capacity. Never raise it toward
  the window size on a shared pool.

- **Gateway unknown windows.** Four served models have no gateway-computed
  window at all (`gpt-5.4-mini` and the three `muse/*` entries). For a routed
  provider the recorded form (still operator-authorized, not yet applied) is
  `modelContextWindows: { "muse-spark-1.2": 1048576, ... }` with the measured
  `1048576`, not a rounded `1000000`.

## 5. Why `Prompt is too long` happens

In this bundle the failure has been observed when a **Workflow script builds
the prompt by interpolating the content of large files** (full `SKILL.md` plus
`model-routing-calibration.md` plus prior inventory JSON) into the string
passed to `agent()`. The harness then sends a prompt whose token count exceeds
the model's effective input window or the transport's limit, and the Workflow
agent errors before any task lens runs.

Typical shape that fails:

```js
// ANTI-PATTERN — embeds ~80k of calibration plus inventories into every call
const merged = await agent(`You are the synthesizer. Inventories:\n${JSON.stringify(inventories, null, 2)}\nTaxonomy A:\n${JSON.stringify(taxonomies[0], null, 2)}\n...`, { model: 'gpt-5.6-sol[1m]', effort: 'xhigh' })
// → Prompt is too long
```

The marked form does not excuse the oversized prompt. In OCX Ultracode Workflow
mode it is required only after its tuple clears certification/admission/readback;
if it does not, return a `SeedProposal` before this call rather than use
`gpt-5.6-sol` without `[1m]`.

`[1m]` does not fix this by itself:

- Claude `[1m]` is invalid, so it is not an available fix on Claude routes.
- On GPT, `[1m]` enlarges the window the client requests, but the embedded
  corpus is still wasteful, still competes with reasoning/output budget, and
  still risks truncation or starvation. A bundle that adds `[1m]` to keep
  dumping full-file contents has made the failure more expensive, not rarer.
- The session floor (272000) still governs compaction. A single `[1m]` worker
  does not raise the floor for fan-out workers in the same session.

## 6. Mitigations — in priority order

Do these **before** reaching for `[1m]`; apply `[1m]` only after the brief is
already disciplined and the remaining corpus is legitimately large.

### 6.1 File-first briefs (primary mitigation)

Instruct the worker to **read** files itself rather than embedding their
contents in the prompt. This is the `deep-work-loop.md §Context discipline`
pattern ("spend the window on purpose"):

```js
// GOOD — the prompt is a short instruction; the corpus stays on disk until
// the worker chooses a bounded read
await agent(
  `Read skills/model-tier-rightsizing/references/model-routing-calibration.md
   sections "Exact dispatch" and "[1m] boundaries" from disk (first 120 lines
   of each), then classify blast radius for the tasks in work/queue.json.
   Use targeted search: locate each symbol before reading its file region;
   cap any single file read to ~80 lines. Write the artifact to
   work/taxonomy.json and reply with its path + 3-line summary.`,
  { model: 'gpt-5.6-terra[1m]', effort: 'xhigh', schema: TAXONOMY_SCHEMA }
)
```

Rules for the brief author:

- Inspect the manifest / export list before opening a package or archive.
- Use targeted search with a small amount of surrounding context; cap how much
  of any one source file is read in one pass.
- Locate the symbol before reading only that region of a large file.
- Obtaining an artifact does not authorize dumping it whole into context.
- Record in the brief: the corpus bound and read plan, which tools are
  actually granted and reachable, the real permission/write boundary (not
  prose asking not to write), and the model/concurrency/budget/timeout
  assumptions. If any is unmeasured, rebrief or mark blocked — do not guess.

### 6.2 Pass summaries, not transcripts

Between pipeline stages, hand off **summaries and digests**, not full
transcripts. A synthesis agent should receive the prior stage's structured
output (`findings: string[]`, `gaps: string[]`) or a short digest, never the
full file contents of every prior artifact.

```js
// GOOD — handoff is a digest
const taxonomyInputs = inventories
  .filter(Boolean)
  .map(i => `- ${i.area}: ${i.findings.slice(0,3).join('; ')}`)
  .join('\n')
await agent(`Inventories (digests only):
${taxonomyInputs}

Design a 6-dimension task taxonomy ... Return TAXONOMY_SCHEMA.`,
  { model: 'gpt-5.6-sol[1m]', effort: 'xhigh', schema: TAXONOMY_SCHEMA })
```

### 6.3 Bound the corpus explicitly

Every brief that dispatches a worker sets a **corpus budget** before that worker
opens a package, archive, or generated file. The budget and read plan are part
of the brief (see `deep-work-loop.md §Context discipline`). Never read a
tarball, bundled, minified, or `dist` artifact wholesale.

### 6.4 Keep pipeline stages small and typed

Prefer `pipeline()` with **small typed schemas** over one mega-prompt with an
unbounded JSON blob. Each stage's schema is its own budget enforcement:

- `INVENTORY_SCHEMA: { area, findings: string[], evidence_refs, gaps }`
- `TAXONOMY_SCHEMA: { dimensions, task_classes[], effort_mapping, model_effort_table }`
- `SPEC_SCHEMA: { command_name, args, phases, live_probe, output_artifact }`

If a synthesis needs to merge two prior taxonomies, pass only the fields the
synthesizer needs, not `JSON.stringify(entirePriorResults, null, 2)`.

### 6.5 Keep the OCX Ultracode request form exact

After the brief is disciplined, an OCX Ultracode Workflow still uses `[1m]`
on **every** explicit model ID. This example shows the certified GPT route:

```js
// OCX Ultracode Workflow uses the certified marked model request form.
await agent(repoWideDiscoveryPrompt, {
  model: 'gpt-5.6-terra[1m]',
  effort: 'xhigh',
})

// The receipt records the corresponding requested_context_form: "[1m]".
// If that exact marked tuple is not certified/admitted/readable, return a
// SeedProposal before calling agent(); do not retry with gpt-5.6-terra.
```

Stay within the exact certified tuple set. A request for `claude-*` with
`[1m]` will currently be rejected by `receipt_admission.py`; a request for
`muse/*[1m]` has no admitted syntax or tuple in the current policy. In OCX
Ultracode Workflow mode, both are a stop-before-dispatch `SeedProposal`, not a
reason to remove `[1m]`. Outside that mode, use the canonical policy for a
compact base-form route.

### 6.6 Scale effort and width with the failure, not the prestige

- Do not raise effort, gate strength, or blast-radius class merely to make
  pressure disappear (`model-routing-calibration.md §Fallback and escalation`).
- An over-window request can surface as an opaque upstream refusal rather than
  a recoverable one when a gateway rewrites the error text — manual compaction
  is then the only recovery, and a wording-matched retry will not fire.
- Reduce fan-out on 429/overload; do not silently weaken the control predicate.

## 7. Opencodex-specific levers that are not `[1m]`

Originally grounded in the installed `2.10.2` source, then rechecked against the active
`2.11.1` package under its mise install root on 2026-08-09 (the docs site is not shipped in
the npm package). Re-checked on 2026-08-19 by diffing the published `2.28.0` tarball against
`2.11.1`, for the `2.11.1 → 2.28.0` pin bump: every mechanism named in this section survives
under the same names and file paths, and exactly one constant moved —
`AUTO_COMPACT_WINDOW_DEFAULT`, from `350_000` to `829_800` (§7.2, and it changes the injected-slot
`[1m]` floor). Read the version attribution on each number below literally. A figure that came from
the opencodex **source** is current for `2.28.0`. A figure that came from anywhere else is not: the
live-gateway catalog counts and per-model windows in §7.4 and any response-body behavior are still
`2.11.1` measurements, because the live gateway on this host was still `2.11.1` when the diff was
read, and the elided bundle's char/token size in §7.1 is a Claude Code artifact size measured on
2026-08-09 rather than a gateway constant at all. The `2.28.0` qualification canary is what
re-measures the gateway half; until it runs, do not restate one as a `2.28.0` observation. These
levers affect token pressure independent of `[1m]`.

### 7.1 `blockedSkills` elision — automatic ~136k saving on routed models

- `src/claude/inbound.ts` defines `DEFAULT_BLOCKED_SKILLS = ["claude-api"]` and
  `effectiveBlockedSkillNames()`. For any *routed* model (provider `openai`, the 5.6
  family), the proxy **elides** the bundled `claude-api` skill document before it
  reaches the model.
- The bundle is not small. The `Skill` tool's `tool_result` is a tiny
  "Launching skill: `<name>`" note, but the **~570k-char** / **~136k-token**
  document bundle rides as a **separate text block** in the same user message whose
  first line is `Base directory for this skill: <dir>/<skill-name>`
  (`inbound.ts: maybeElideSkillText`, `skillElisionStub`). For blocked routed
  models the proxy replaces that block with a ~30-token stub:
  `[opencodex] 'claude-api' skill document bundle (N chars) elided for routed models …`
- Native Anthropic passthrough (bare `claude-*` where `resolveInboundModel() === id`)
  **keeps the full bundle** — `src/claude/agents-inject.ts: blockedSkillsFor()` returns
  `[]` there.
- Generated subagent defs (`agents-inject.ts: renderAgentDef`) emit a guard line
  `Do not invoke blocked Claude Code skills: "claude-api". Their document bundles are
  intentionally omitted for routed models; continue without loading them.` and carry
  `blockedSkills` per def.
- **Implication for Workflow authors:** A routed-model worker already saves ~136k
  tokens without you doing anything. Do **not** re-introduce that cost by reading
  the `claude-api` skill bundle from disk or by interpolating its text into a prompt.
  A blocked worker that needs that skill's knowledge must answer from general
  knowledge — the stub says so explicitly. If a task genuinely needs the bundle,
  route it to native passthrough instead.

### 7.2 `autoContext` / `autoCompactWindow` — the real per-model floor

- `src/claude/context-windows.ts` owns the mechanism:
  `AUTO_COMPACT_WINDOW_DEFAULT = 829_800` in `2.28.0` — it was `350_000` through `2.11.1`, and
  this is the one constant the version diff moved — plus `AUTO_CONTEXT_FLOOR = 200_000`,
  `ONE_MILLION = 1_000_000`, and the accepted range `100_000–1_000_000` (unchanged, verified
  against the Claude Code 2.1.207 binary).
- `resolveAutoContext(claudeCode, envOverride) → {enabled, compactWindow}`.
  Disabled when `claudeCode.autoContext === false` **or** when legacy
  `maxContextTokens` is set — both `MAX_CONTEXT_TOKENS` and `DISABLE_COMPACT` then
  make `AUTO_COMPACT_WINDOW` and `[1m]` accounting inert.
- Marking predicate `shouldMarkOneMillion(window, auto)`:
  `window >= 1M` → always mark; otherwise
  `auto.enabled && window > 200_000 && window >= compactWindow`. The last conjunct
  is the safety property: marking a model whose real window is **below** the compact
  window would put the compaction safety net **behind** the real API limit
  (mid-session 400s).
- **What the raised default changes.** The predicate is the same; its second branch now demands
  far more. With `autoContext` on and no explicit compact window, an injected slot is marked only
  at `window >= 829_800`, where `2.11.1` marked from `350_000`. A 372k sol/terra/luna route was
  marked under the old default and is **not** marked under the new one. So a sub-1M `[1m]` mark is
  now an explicit floor decision — either the host sets `--compact-window` at or below the route's
  real window on purpose, or that route stops being marked — and a workflow that assumed the
  marking would appear on its own gets an unmarked slot with no error. The `window >= 1M` branch is
  untouched: a genuinely 1M model still marks regardless of the default.
- `effectiveModelEnv()` injects `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and the tier
  slots `ANTHROPIC_MODEL` / `ANTHROPIC_DEFAULT_OPUS/SONNET/FABLE/HAIKU_MODEL` with
  `withOneMillionMarker()` applied. The persistent write surface is
  `ocx claude config set --compact-window <tokens|default>` and
  `--auto-context <on|off>` (they write `claudeCode.autoCompactWindow` /
  `autoContext` in `~/.opencodex/config.json`), not `ocx models context …` which
  is a per-provider cap only.
- Subagent defs get a stricter predicate `withSubagentContextMarker()` in
  `agents-inject.ts`: it checks the **authoritative window**
  (`windows[selector] ?? windows[canonicalExact] ?? windows[bare]`) and marks only
  if `shouldMarkOneMillion(authoritativeWindow, AUTO_CONTEXT_OFF)` — i.e. **without**
  the main-session auto-context pairing. A 372k route is **not** marked there unless
  its window is genuinely ≥1M (the #854 defect guard).
- **Alive on this host, re-read 2026-08-20** (`ocx config show --json`, read-only, 2.28.0 CLI
  against the same config file): the adopted floor from
  `docs/research/2026-08-07-context-window-accommodation.md` §8 **has been applied**.
  `claudeCode.autoCompactWindow` is explicitly `272000` — the smallest real window in the selected
  set — so this host's pairing floor is 272000 and **not** the raised 829_800 default, and an
  explicit setting is what keeps a 372k route markable. `claudeCode` also carries `smallFastModel`
  and `authModeMigratedAt`; `claudeCode.autoContext` is absent, i.e. default-on. Two providers are
  configured (`openai`, the default, and `muse`), and the `muse` block **does** carry a
  `modelContextWindows` map. An earlier revision of this bullet said the live config was untouched
  with `autoCompactWindow: null` and no `claudeCode` block; that was true on 2026-08-09 and is
  false now, which is why the read is dated and re-runnable rather than asserted. Do **not**
  describe `[1m]` as the per-model floor — the floor is `CLAUDE_CODE_AUTO_COMPACT_WINDOW` via
  `min(believed window, env)`.

### 7.3 Reasoning effort — `ultra` is not a context lever

- `src/reasoning-effort.ts` defines `CODEX_REASONING_LEVELS = low..ultra` and
  `mapReasoningEffort()`: `ultra` maps to `max` before the provider wire. The
  gateway catalog advertises `ultra` only on `gpt-5.6-sol` / `terra` (`low..ultra`);
  a workflow that passes `ultra` to `luna`, `5.5`, `5.4`, or `muse/*` fails closed
  (unsupported vocab). Effort does not move windows.

### 7.4 What the catalog does and does not tell you about windows

- OpenAI-shaped `GET /v1/models` (no Anthropic header) returns 10 entries with
  only `id, reasoning_effort, reasoning_efforts, supports_reasoning_effort` —
  **no window field**.
- Anthropic-shaped list (`anthropic-version: 2023-06-01`, UA `claude-code/2.1.207`)
  returns 11 `claude-ocx-*` entries with `max_input_tokens` / `max_tokens`, but
  **10 of 11 are `null`** (only `gpt-5.4[1m]` is `1000000`). `ocx models live --json`
  and `ocx claude config status` carry the real per-model map (`contextWindow`:
  sol/terra/luna 372k, 5.5 272k, 5.4 1M, 5.3-codex-spark 100k, mini/muse absent).
  The calibration table — not discovery — is the source of truth.
- **Version attribution.** Those entry counts and per-model numbers are `2.11.1` live-catalog
  measurements from 2026-08-09; the `2.28.0` canary re-measures them, and the catalog also has five
  more registry providers available to add (`chutes`, `featherless`, `nous`, `novita`,
  `xiaomi-mimo`), so expect the counts to move. What the `2.28.0` source re-verified is the RULE
  that produces them: the Anthropic-shaped list still emits `claude-ocx-*` ids through the same
  codec, and an entry carries the `[1m]` mark and a non-null window only when its **authoritative**
  window is `>= 1e6`. So the shape is current and the counts are dated. A `null` window is the
  rule's ordinary output, not a defect, and catalog discovery is still not a window source.

## 8. Checklist for Workflow authors

Before dispatching a `Workflow()`:

- [ ] Every `agent()` prompt fits on one screen without scrolling — if it
      would not, the brief is embedding corpus that belongs on disk.
- [ ] No prompt interpolates `readFileSync` contents, full `JSON.stringify` of
      prior stage outputs, or multi-file concatenation.
- [ ] Each brief states its corpus bound, read plan, tool grant, and write
      boundary.
- [ ] The prompt tells the worker **which** sections to read and with what line
      cap, not "read everything."
- [ ] Handoffs between stages pass digests or typed schema outputs, not
      transcripts.
- [ ] In OCX Ultracode Workflow mode, every explicit `agent()` `model` ID ends
      with `[1m]`, and its exact marked model/effort/context tuple is certified,
      admitted, and readable before the call. An unsupported model form produces
      one stop-before-dispatch `SeedProposal`, never an unsuffixed retry.
- [ ] Outside OCX Ultracode Workflow mode, `[1m]` appears only on
      repository- or transcript-heavy certified GPT workers, and the
      `RuntimeAssignment` records `requested_context_form: "[1m]"` alongside a
      valid `requested_effort`.
- [ ] The session floor is still 272000 unless the session is genuinely
      single-model on a larger window and the raise is documented. That floor is an
      EXPLICIT `claudeCode.autoCompactWindow`, not the default — opencodex `2.28.0`
      defaults to 829_800, which would put the compaction net far behind a 372k route
      and drop its injected-slot `[1m]` mark (§7.2).
- [ ] Output budgets on shared-pool (`muse`) sessions are set explicitly
      (above ~600 + expected output, well below 1048576).

Before synthesising across prior stage outputs:

- [ ] The synthesis prompt receives at most a few lines per prior result
      (e.g. `findings.slice(0,3).join('; ')`), not full JSON dumps.
- [ ] If a full inventory is genuinely needed, the synthesizer reads it from
      the artifact path on disk rather than from an interpolated string.

## 9. What to do when a prompt still fails

1. **Classify** the failure: is the prompt too long because it carries a
   corpus, because it carries prior transcripts, or because the output schema
   itself is huge? The fix differs.
   - An **HTTP 413** carrying the error type `input_admission_refused` (new in 2.28.0; a live
     2.11.1 gateway never emits it) is its own class, not a transport fault: opencodex estimates
     the inbound token count and refuses **locally**, before any provider request, when the
     estimate exceeds the route's ceiling × 2.5. Such an attempt carries no upstream evidence —
     no provider request was dispatched, and the attribution log records the refusal itself, not
     a serve. Other 413s exist (local buffer/body limits, and Anthropic's own `request_too_large`
     upstream on the passthrough route), so match the error type, never the bare status. Treat the
     preflight class as "this prompt does not fit this route" and go to step 2 or 3; a retry
     against the same route and prompt refuses identically. `rightsize.py: identity_evidence` classifies it under that name so a 413 is never
     read as a provider or model fault, and a 413 mixed with any other non-200 stays the generic
     `transport-status` rather than being renamed after the 413.
2. **Re-brief** to remove the corpus from the prompt (section 6.1) and re-run
   the single stage with `resumeFromRunId` — unchanged prefixes replay from
   cache.
3. If the corpus is legitimately repository-wide and the brief is already
   disciplined, **move that one worker to `gpt-5.6-{sol,terra,luna}` with
   `requested_context_form: "[1m]"`** and re-probe. Do not move Claude or
   Muse workers to `[1m]`.
4. If pressure is global (many workers, large fan-out), **reduce width**
   before raising anything.
5. Record the probe: requested model/effort/context, outbound alias expansion,
   transcript model, resolved effort or `unknown`, context/fallback signal, stop
   reason, usage, and prompt/artifact digests — so a reviewer with source
   access can reconcile it.

## 10. Pointers

- `model-routing-calibration.md` — exact IDs, effort vocabulary, `[1m]`
  boundaries, context windows, Muse two-route rules, fallback and rerun
  triggers.
- `policy/runtime-assignment-normative-contract-v1.json` — the enforceable
  `allowed_context_forms`, `certified_context_forms_by_model`, and
  `certified_request_tuples`.
- `deep-work-loop.md §Context discipline` and `§Effort routing` — corpus
  budget, the three disclosure levels, and lane choice.
- `SKILL.md` — the stable blast-radius doctrine that owns tier eligibility.
