# Per-model context windows: what each layer knows, and the accommodation

Status: executed evidence, researched 2026-08-07. Probes were read-only against the
operator's live gateway on `127.0.0.1:10100`; the two mutation tests ran against throwaway
`OPENCODEX_HOME` directories that were deleted afterward (§7). No Claude session was
launched, no operator config was modified, and no gateway state was written. This record
authorizes nothing.

The operator's question was: *every model has a separate context window that we should try
to accommodate for. does claude-code and ocx support that? if not how can we document it and
set up a workaround for it?*

**The short answer is more favorable than expected, and the surprise is in the middle
layer.** ocx already models per-model context windows *and* already ships a mechanism that
converts one process-wide Claude Code knob into a per-model floor. Claude Code has no
per-model context setting at all and cannot get one from configuration. So the honest
accommodation is not a new invention — it is turning on and pinning a mechanism that
already exists, then recording the numbers where they cannot rot.

---

## 1. The three layers, and which one can hold a per-model number

| Layer | Per-model window? | Evidence |
|---|---|---|
| Provider (OpenAI / Meta) | yes — genuinely different per model | §5 |
| ocx gateway | **yes, and it computes them** — but per-model *editability* is uneven | §3 |
| Claude Code session | **no. Every knob is process-wide** | §4 |

The load-bearing constraint is the third row, and it is worth stating precisely because it
is what forces the design: a single Claude Code process has exactly one
`CLAUDE_CODE_AUTO_COMPACT_WINDOW`, one `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, and one
`CLAUDE_CODE_MAX_OUTPUT_TOKENS`. A session that switches models mid-conversation, or a
workflow that fans out subagents onto different models inside one process, cannot give each
model its own number through any documented configuration.

That constraint is confirmed, not merely inherited from the earlier
`docs/research/2026-07-22-claude-code-multi-model-routing.md` memo. §4 records what current
official documentation says, including the negative searches.

---

## 2. What the gateway catalog does and does not carry

The catalog has **two shapes**, and the earlier framing of this question tested only one of
them. This matters because Claude Code reads the other.

### 2.1 The OpenAI-shaped list carries no window field at all

`GET http://127.0.0.1:10100/v1/models` with no Anthropic headers returns 10 entries whose
per-entry fields are exactly:

```
created, id, object, owned_by, reasoning_effort, reasoning_efforts, supports_reasoning_effort
```

There is no context, window, limit, or token field anywhere in that response. A client doing
discovery against this shape learns each model's **reasoning effort ladder** and nothing
whatsoever about its context window.

### 2.2 The Anthropic-shaped list carries a window field, and it is almost entirely null

Claude Code does not get the shape above. `src/server/index.ts` branches on the
`anthropic-version` request header (which Claude Code sends) and serves a different list.
Reproduced:

```
curl -H "anthropic-version: 2023-06-01" -H "user-agent: claude-code/2.1.207" \
     http://127.0.0.1:10100/v1/models
```

11 entries, each with these top-level fields:

```
capabilities, created_at, display_name, id, max_input_tokens, max_tokens, type
```

So a window field **does** exist on the surface Claude Code reads. Its observed values:

| Discovery id | `max_input_tokens` | `max_tokens` |
|---|---:|---:|
| `claude-ocx-native--gpt-5.6-sol` | null | null |
| `claude-ocx-native--gpt-5.6-terra` | null | null |
| `claude-ocx-native--gpt-5.6-luna` | null | null |
| `claude-ocx-native--gpt-5.5` | null | null |
| `claude-ocx-native--gpt-5.4` | null | null |
| `claude-ocx-native--gpt-5.4[1m]` | **1000000** | null |
| `claude-ocx-native--gpt-5.4-mini` | null | null |
| `claude-ocx-native--gpt-5.3-codex-spark` | null | null |
| `claude-ocx-muse--muse-spark-1.1` | null | null |
| `claude-ocx-muse--muse-spark-1.2` | null | null |
| `claude-ocx-muse--muse-spark-1.2-contributor` | null | null |

`max_tokens` is null on every entry by design — `src/claude/model-info.ts` documents "no
authoritative output limit exists proxy-side."

**The interesting part is that the nulls are not ignorance.** ocx knows a window for six of
those seven gpt models (§3.1) and deliberately does not advertise it on the base rows. It
publishes a number only on the synthesized `[1m]` variant row, and only when the real window
is at least 1M. The source comment in `model-info.ts` names the reason: marking a row `[1m]`
makes Claude Code account exactly 1,000,000 tokens for it, so marking a 372K route would have
Claude Code over-fill it — recorded there as "the #854 defect [that] does not come back."

So the accurate statement is not "the catalog carries no window." It is: **the catalog
deliberately advertises a window only where the number equals what Claude Code will actually
believe, and stays silent otherwise.** That is the correct conservative choice, and it is
also why the per-model accommodation has to happen through a different channel.

---

## 3. What ocx supports

Version probed: `opencodex 2.10.2` (`ocx --version`).

### 3.1 ocx knows real per-model windows

`ocx models live --json` returns them directly:

| Model | ocx `contextWindow` |
|---|---:|
| `gpt-5.4` | 1000000 |
| `gpt-5.6-sol` | 372000 |
| `gpt-5.6-terra` | 372000 |
| `gpt-5.6-luna` | 372000 |
| `gpt-5.5` | 272000 |
| `gpt-5.3-codex-spark` | 100000 |
| `gpt-5.4-mini` | *field absent* |
| `muse/muse-spark-1.1` | *field absent* |
| `muse/muse-spark-1.2` | *field absent* |
| `muse/muse-spark-1.2-contributor` | *field absent* |

`ocx claude config status` exposes the same numbers as a selector map (18 entries — each
model registered under its bare slug, its hashed Desktop alias, and its readable
`claude-ocx-*` alias). The four models with an absent field are absent from that map too.

### 3.2 The exact `ocx models context` surface — it is per **provider**, not per model

The parent usage line is what `--help` prints, and it hides the verb structure. The real
surface, read from `src/cli/models-runtime.ts`:

```
ocx models context <status|value <tokens>|provider <name> <on|off>|all <on|off>> [--json]
```

Four actions, no `--model` flag anywhere:

- `status` — read current state (this is the default with no action).
- `value <tokens>` — set the single global cap number, and re-point every already-enabled
  provider to it.
- `provider <name> <on|off>` — enable or disable the cap for one provider.
- `all <on|off>` — enable or clear the cap for every provider at once.

Live read on the operator's gateway:

```
$ ocx models context status --json
{ "cap": 350000, "value": 350000, "caps": {} }
```

Reading the handler (`src/server/management/provider-routes.ts:586`) fixes what those three
fields mean, and the operator's state is **not** what the bare numbers suggest:

- `cap: 350000` is `DEFAULT_PROVIDER_CONTEXT_CAP`, a compiled-in constant
  (`src/providers/context-cap.ts`), not an applied value.
- `value: 350000` is the configured global cap value, falling back to that same constant
  because the operator has set nothing.
- **`caps: {}` is the live state that matters: no provider has the cap enabled.** So
  **nothing is currently being clamped at all.** The 350000 is a number waiting to be
  applied, not a ceiling in force.

Two further properties, both from `applyProviderContextCap`:

- The cap **only ever clamps downward** (`contextWindow > cap ? cap : contextWindow`). It
  can never raise a model above its real window, so it cannot be used to unlock muse's 1M.
- It is keyed by provider. Every model on one provider gets the same cap. Since all seven
  gpt entries share the provider `openai`, one cap cannot distinguish sol (372K) from
  codex-spark (100K).

**Answer to the operator's specific question: `ocx models context` is global-and-per-provider
only. It cannot set a per-model window.**

### 3.3 But per-model windows *are* settable — through a different, config-only path

`OcxProviderConfig` has a `modelContextWindows: Record<string, number>` field
(`src/types.ts:1145`) consumed by `configuredContextWindow()`. Verified working in an
isolated throwaway config (§7): a `muse` provider with
`"modelContextWindows": {"muse-spark-1.2": 1048576, "muse-spark-1.1": 1048576}` produced

```
muse (default provider):
  muse-spark-1.2 * (1049k)
  muse-spark-1.1 (1049k)
```

Two hard limits on this path:

1. **There is no CLI flag for it on real providers.** `ocx provider add|edit` has no
   `--context-window` option (the source has no `context` match at all in
   `src/cli/provider.ts`). The `--context-window` flag that does exist belongs to
   `ocx models add|edit`, which manages *custom* models — ones "the provider catalog does not
   advertise yet" — keyed by UUID or `<provider>/<modelId>`. So for an existing provider,
   `modelContextWindows` is a hand-edit of `~/.opencodex/config.json`.
2. **It does not reach the seven native gpt models.** Those resolve through
   `nativeOpenAiContextWindow(slug)`, which takes **no config argument** and reads a
   hard-coded override table (`src/codex/catalog/metadata.ts:58`). Confirmed empirically: a
   throwaway config setting `modelContextWindows`, `contextWindow`, `contextCapValue`, and
   `providerContextCaps` all to 50000 for `gpt-5.6-sol` did not move it. The native windows
   are compiled in and not operator-editable.

So per-model editability splits: **routed providers (muse) yes, native gpt models no.**

### 3.4 The mechanism that actually solves the problem: `autoContext`

This is the finding that changes the recommendation, and it is already on.

`ocx claude config status` reports `autoContext: true` — the default. The mechanism is
documented in `src/cli/claude.ts:170`:

> Auto-context: `min(believed window, env)` inside the CLI means **one global env acts as a
> per-model floor** — `[1m]`-marked models compact here while unmarked (200k-accounted)
> models keep their default behavior.

Concretely, when `ocx claude` launches Claude Code it injects
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` at `AUTO_COMPACT_WINDOW_DEFAULT = 350_000`, and it decides
per model whether that model's selector carries the `[1m]` marker. The marking predicate
(`shouldMarkOneMillion`) is:

- window ≥ 1,000,000 → always mark;
- otherwise mark only if `autoContext` is on **and** window > `AUTO_CONTEXT_FLOOR` (200,000)
  **and** window ≥ the compact window.

The last conjunct is the safety property, and its comment states the hazard directly:
"marking a model whose real window is BELOW the compact window would put the compaction
safety net behind the real API limit (mid-session 400s)."

Because Claude Code takes the **minimum** of what it believes the window is and the env
value, a single env number behaves as a per-model floor: a marked 1M model compacts at
350,000, while an unmarked model is accounted at its own smaller believed size and compacts
there. That is a genuine per-model accommodation built out of a process-wide knob — the only
shape the constraint in §4 permits.

Its current effect on this operator is limited by two things. `effectiveModelEnv` is `{}`
because no model slots are configured (`model`, `tierModels`, `smallFastModel` all empty), so
no selector is being marked today. And it cannot help the four models with no known window
(§3.1) — an unknown window fails `shouldMarkOneMillion` and gets no marker, which is
conservative and correct but leaves muse's measured 1,048,576 tokens unusable.

The `--compact-window <tokens|default>` and `--auto-context <on|off>` flags on
`ocx claude config set` are the supported write surface for this. `maxContextTokens` is the
legacy alternative and is mutually exclusive: setting it makes `resolveAutoContext` return
`AUTO_CONTEXT_OFF`, which disables auto-context and `[1m]` accounting entirely (the launcher
pairs it with `DISABLE_COMPACT=1`, matching the Claude Code rule in §4.1).

---

## 4. What Claude Code supports, and the per-session constraint

All quotations below are from `code.claude.com/docs/en/env-vars.md` unless another page is
named. `docs.claude.com/en/docs/claude-code/settings` 301-redirects to
`code.claude.com/docs/en/settings`.

### 4.1 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` — exists, and is purpose-built for this case

> Override the context window size Claude Code assumes for the active model. As of v2.1.193,
> applied directly for model names Claude Code does not recognize as a Claude model; for
> recognized Claude models it only takes effect when `DISABLE_COMPACT` is also set. Use this
> when routing to a model through `ANTHROPIC_BASE_URL` whose context window does not match
> the built-in size for its name

This **confirms** the version gating that the 2026-07-22 memo recorded, so that dated claim
stands. Note the phrase "the active model" — one value resolved at request time, not a map.
No default and no range are documented.

The recognition cliff is a real trap: the same variable has opposite behavior depending on
whether the model ID *looks* Claude-shaped. The gateway's discovery IDs are
`claude-ocx-native--gpt-5.6-sol` and similar — Claude-shaped strings — so whether Claude Code
classifies them as recognized Claude models determines whether this variable works at all
without `DISABLE_COMPACT=1`. That is not something these probes settled, and it is the main
reason to prefer the auto-compact-window path over this one.

### 4.2 `CLAUDE_CODE_AUTO_COMPACT_WINDOW` — the right knob, with an exact range

> Set the auto-compact window in tokens, from `100000` to `1000000`. Accepts a plain integer
> such as `500000` only: a value like `500k` reads as `500` and clamps to the 100K minimum.
> Takes precedence over the `/autocompact` command, the `--autocompact` flag, and the
> `autoCompactWindow` setting. The status line's `used_percentage` always measures against
> the model's full context window, so once this variable is set, that percentage no longer
> indicates when compaction will run

Range **100000–1000000**, confirming the operator's brief. On the default: `settings.md`
says of `autoCompactWindow` that "when unset, Claude Code uses a window tuned for your
model" — so there is **no documented default of 500000**; the 500000 that appears in
`settings.md` is an *example* value. The brief's "default 500000" is not supported by current
docs and should not be repeated.

`context-window.md` adds the property that makes §3.4 work: **"Claude Code caps the window at
the model's context window."** That is the `min()` the auto-context mechanism relies on.

The `used_percentage` caveat matters operationally: once this variable is set, the status
line stops indicating when compaction will run.

### 4.3 `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` — exists, one-directional

> Set the percentage (1-100) of the auto-compact window at which auto-compaction triggers.
> Use lower values like `50` to compact earlier; the variable can't raise the threshold, so
> values above the default percentage are ignored. It applies only in sessions that compact
> before the model's context limit. Applies to both main conversations and subagents

Range 1–100; it can only compact *earlier*. The default percentage is not stated anywhere in
the doc set. Note "applies to both main conversations and subagents" — that is scope
*broadening*, further evidence against per-model scoping.

### 4.4 `CLAUDE_CODE_DISABLE_1M_CONTEXT` — exists, Claude-models only

> Set to `1` to disable 1M context window support. When set, 1M model variants are
> unavailable in the model picker, and Sonnet 5 sessions are treated as having a 200K window.
> Useful for enterprise environments with compliance requirements

This governs Anthropic 1M variants and the model picker. It is not a lever for gateway-served
gpt or muse models.

### 4.5 Related knobs that bear on the shared-window hazard

- `CLAUDE_CODE_MAX_OUTPUT_TOKENS`: "Claude Code defaults to **32000 for model IDs it doesn't
  recognize, such as gateway-specific names**, and lowers values above a model's cap to the
  cap. **Increasing this value reduces the effective context window available before
  auto-compaction triggers**." Both halves are load-bearing here.
- `DISABLE_COMPACT`: "disable all compaction: both automatic compaction and the manual
  `/compact` command." The un-prefixed name is correct; `CLAUDE_CODE_DISABLE_COMPACT` does
  not exist in the docs.
- `DISABLE_AUTO_COMPACT`: disables automatic compaction while leaving `/compact` available.
- `MAX_THINKING_TOKENS`: capped at one token below the request's max output tokens.

### 4.6 The constraint, confirmed: per-session, not per-model

**Confirmed. No documented per-model override exists for context size or compaction
thresholds.** The positive evidence is that `CLAUDE_CODE_MAX_CONTEXT_TOKENS` is defined
against "the active model" (singular) and that `settings.md` describes an `env` block as
applying "to every session and to subprocesses Claude Code spawns from it."

The negative searches are what make this a finding rather than an absence of reading, and two
are strong:

- **No settings key carries a window.** The model/context/compaction settings keys are
  `advisorModel`, `autoCompactEnabled`, `autoCompactWindow`, `availableModels`,
  `enforceAvailableModels`, `fallbackModel`, `modelOverrides`, `model`,
  `switchModelsOnFlag`, `teammateDefaultModel`. `modelOverrides` *is* keyed by model ID — but
  it maps Anthropic model IDs to provider-specific ID strings only, and carries no
  context-window or compaction field.
- **The per-tier env pattern exists and was not extended to context.** Anthropic ships
  `DISABLE_PROMPT_CACHING_{HAIKU,SONNET,OPUS,FABLE}` and `model-config.md` calls these "the
  per-model settings." No analogous suffix family exists for context or compaction. The
  pattern was available and deliberately not used here.
- **Agent and subagent definitions have no context field.** The full frontmatter field list
  (`sub-agents.md`) is `name, description, tools, disallowedTools, model, permissionMode,
  maxTurns, skills, mcpServers, hooks, memory, background, effort, isolation, color,
  initialPrompt`. The SDK `AgentDefinition` type matches. There is no `contextWindow` or
  `maxContextTokens`. The SDK does expose per-model `contextWindow` — but read-only, in
  `ModelUsage` telemetry, not as configuration.

Two things *are* genuinely per-model, and both are narrow. Window **size** is derived per
agent: "a subagent's context window is sized by its own model, not the parent's. Delegating
to a model with a smaller window gives that subagent the smaller window" (`sub-agents.md`).
And the `[1m]` suffix is read **per variable**: "On Amazon Bedrock, Google Cloud's Agent
Platform, and Microsoft Foundry, a model ID without `[1m]` in one variable uses 200K context
even if another variable sets the same model with the suffix" (`model-config.md`). That
per-variable reading is exactly the seam `autoContext` exploits — a binary 200K/1M toggle per
alias slot, not an arbitrary token count.

### 4.7 The docs address the gateway case directly, including the opaque-400 failure

`llm-gateway-connect.md` carries a troubleshooting row that describes failure mode (b) in §6
before it happens:

> **Error:** `400` errors stating a context or token limit in the gateway's own words, such
> as `ContextWindowExceededError` or `prompt token count of N exceeds the limit of M`
> **Cause:** The gateway enforces a smaller context than the model's native window and
> rewrites the upstream error, so the automatic compact-and-retry, which matches Anthropic's
> `prompt is too long` wording, doesn't fire
> **Fix:** Run `/compact` to recover the session. To prevent it, set
> `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to the gateway's limit; the value is clamped to at least
> 100,000 tokens and at most the model's context window, so a gateway limit below 100,000
> can't be matched and `/compact` remains the recovery there. Also set
> `CLAUDE_CODE_MAX_OUTPUT_TOKENS` below the gateway model's output limit

Two consequences worth pinning. The rewritten-error mechanism explains why an over-window
request surfaces opaquely: Claude Code's compact-and-retry is **wording-matched** to
Anthropic's own `prompt is too long`, so a gateway that rephrases the error silently disables
the recovery. And the 100,000 clamp floor means `gpt-5.3-codex-spark` at exactly 100,000
sits on the boundary — a window at or below the floor cannot be matched by this variable at
all.

Also relevant: `model-config.md` notes that when `ANTHROPIC_BASE_URL` points at a gateway,
"Claude Code can't verify 1M support," and such sessions "budget the window at 200K instead."
And the support boundary, from `llm-gateway.md`: Anthropic "doesn't endorse, maintain, or
audit third-party gateway products, and doesn't support routing Claude Code to non-Claude
models through any gateway." This route is unsupported by the vendor by construction.

---

## 5. Per-model windows, with sources

Numbers differ by *surface* for the same model ID, so a single column would be a lie. The
`ocx` column is what the gateway currently computes and is the number that actually governs
this operator's sessions.

| Model | ocx | Provider API docs | Codex/subscription surface | Notes |
|---|---:|---:|---:|---|
| `gpt-5.6-sol` | 372000 | 1050000 (922000 in + 128000 out) | 272000 | ocx uses a third value; see below |
| `gpt-5.6-terra` | 372000 | 1050000 (922000 in + 128000 out) | 272000 | ChatGPT Business documents 128000 |
| `gpt-5.6-luna` | 372000 | 1050000 (922000 in + 128000 out) | 272000 | ChatGPT Business documents 128000 |
| `gpt-5.5` | 272000 | 1050000 total; max input **unknown** | 272000 | ocx agrees with the Codex surface |
| `gpt-5.4` | 1000000 | 1050000 total; max input **unknown** | 272000 default / 1000000 max | only model ocx marks `[1m]` |
| `gpt-5.4-mini` | **unknown** | 400000 (272000 in + 128000 out) | 272000 | ocx has **no** window for it |
| `gpt-5.3-codex-spark` | 100000 | **unknown** — no API model page | 128000 (announcement) | ocx is *below* the announced figure |
| `muse/muse-spark-1.1` | **unknown** | — | — | see §5.2 |
| `muse/muse-spark-1.2` | **unknown** | 1048576 **measured** (shared) | — | see §5.2 |
| `muse/muse-spark-1.2-contributor` | **unknown** | 1048576 **measured** (shared) | — | see §5.2 |

Sources. Provider-API figures are from OpenAI's own model pages under
`developers.openai.com/api/docs/models/<id>.md` (`platform.openai.com/docs/models` now
redirects there). Where both fields are published the arithmetic is exact — 922000 + 128000 =
1050000 and 272000 + 128000 = 400000 — so OpenAI's "context window" is an **input window plus
a separate output reservation**, not a shared pool. `gpt-5.5` and `gpt-5.4` publish a total
and an output cap but omit the "Maximum input tokens" line, so their input ceiling is
recorded as unknown rather than inferred. `gpt-5.3-codex-spark` has **no** API model page
(404) and appears on `learn.chatgpt.com/docs/models.md` with `API Access: false`; its only
provider-stated number is "a 128k context window" in the launch announcement
(`openai.com/index/introducing-gpt-5-3-codex-spark`). A third-party claim of 32K max output
for Spark exists and is *not* provider-documented.

Codex-surface figures come from OpenAI's own shipped catalog
(`codex-rs/models-manager/models.json` in `github.com/openai/codex`), corroborated by the
Codex CLI changelog: "corrected their context windows to **272,000 tokens**" for Sol, Terra,
and Luna (CLI 0.144.6). That surface also applies a 95% effective factor
(`default_effective_context_window_percent() -> 95`), so 272000 × 0.95 = 258400 effective.
The 272000 figure is not arbitrary — it is OpenAI's long-context billing threshold, above
which input is priced at 2× and output at 1.5×. ChatGPT Business is documented separately and
smaller still: "The context window is 128K for GPT-5.6 Luna and GPT-5.6 Terra, and 272K for
GPT-5.6 Sol" (`help.openai.com/en/articles/12003714`).

### 5.1 ocx's 372000 for the 5.6 family is a fourth value, and it is a stale one

ocx pins `NATIVE_GPT56_CONTEXT_WINDOW = 372_000` (`src/codex/catalog/metadata.ts:58`) and its
bundled snapshot agrees. But 372000 is precisely the number OpenAI shipped at Sol's launch
and **reverted within about eight hours**, because "it resulted in more usage being charged
than intended" — reverted to 272000 with an intent to restore 372K later. ocx's own registry
carries both constants (`OPENAI_CODEX_GPT56_CONTEXT_WINDOW = 372_000` alongside
`OPENAI_API_GPT56_CONTEXT_WINDOW = 1_050_000`).

So the number governing this operator's 5.6 sessions is **100,000 tokens above what OpenAI's
current Codex catalog says**, on the surface (Codex OAuth) whose own catalog says 272000. This
is the highest-priority item in the table: it is not a conservative over-estimate, it is an
over-promise on the exact axis where over-promising causes mid-session failures (§6b). It is
also not fixable from config — native windows are compiled in (§3.3).

### 5.2 muse: measured at 1,048,576, and the window is SHARED

The muse window is the best-evidenced number in this document and the worst-served by the
tooling. `docs/research/2026-08-07-muse-spark-qualification.md` §5.8 measured it by
bisection, twice, at different input sizes:

| Input | `count_tokens` | Largest accepted `max_output_tokens` | Smallest refused | Sum |
|---|---:|---:|---:|---:|
| `"x"` | 165 | 1048411 | 1048412 | **1048576** |
| `"hi"` | 165 | 1048411 | 1048412 | **1048576** |
| ~9.7k filler | 9765 | 1038811 | 1038812 | **1048576** |

Every row sums to exactly 2^20 with zero remainder, and the relation
`max_output_tokens = 1048576 − count_tokens` was confirmed as a predictive oracle in both
directions. The finding: **the window is exactly 1,048,576 tokens and it is a shared
input+output budget** — not 1M input plus separate output. Input and output compete.

This is the one place where the provider model differs structurally from OpenAI's. OpenAI
publishes input and output as separate reservations that sum to the advertised window; muse
has one pool. A per-model table that records only a single number per model cannot express
that difference, which is why the calibration table gets an explicit shared/separate column.

Note also that §5.8 found the failure *above* the window changes class: `max_output_tokens:
999999999` returned **429 `rate_limit_exceeded`**, not 400. A client with retry-on-429 would
retry a request that can never succeed.

Two caveats on the measurement. §5.8 is explicit that only *admission arithmetic* was
measured — nothing shows quality holds across a filled window, so window **usefulness**
remains `vendor-hypothesis`. And `count_tokens` carries a ~165-token constant offset versus
billed `input_tokens` (§6.4 of that memo); it is nonetheless the correct **admission** oracle,
because it is what predicts the boundary exactly.

---

## 6. The failure modes an operator will actually hit

**(a) One compaction threshold across models of different sizes wastes the large ones and
truncates the small ones early.** With `autoContext` on, the injected
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` is 350,000, and Claude Code applies `min(believed window,
env)`. For a model believed to be 1M this compacts at 350,000 and leaves roughly 650,000
tokens unreachable. Tune it upward for the large model and the marking predicate stops
marking mid-size models — `shouldMarkOneMillion` requires `window >= auto.compactWindow`, so
raising the compact window past 372,000 unmarks the entire 5.6 family, and past 1,000,000
unmarks `gpt-5.4` too. The knob is genuinely two-sided: there is no single value that is
right for a 100,000-token model and a 1,048,576-token model in one session.

**(b) A request over a smaller model's window surfaces as an opaque upstream 400.** This is
documented rather than hypothesized (§4.7): when a gateway "enforces a smaller context than
the model's native window and rewrites the upstream error," Claude Code's automatic
compact-and-retry does not fire, because that recovery is **matched to Anthropic's own
`prompt is too long` wording**. The session needs a manual `/compact`. This route makes the
mismatch concrete in two places. ocx believes the 5.6 family holds 372,000 while OpenAI's
Codex catalog currently says 272,000 (§5.1), so a session that fills toward ocx's number is
aimed 100,000 tokens past the real ceiling. And `gpt-5.3-codex-spark` at 100,000 sits exactly
on `CLAUDE_CODE_AUTO_COMPACT_WINDOW`'s documented clamp floor, so that variable cannot
protect it at all — `/compact` is the only recovery there.

**(c) muse's shared window means a large input silently starves the output budget.** Because
input and output draw on one 1,048,576-token pool (§5.2, measured), a large input
mechanically shrinks the output allowance. What makes this a silent failure rather than an
error is the companion measurement in §6.1 of the muse memo: an insufficient output budget
returns **HTTP 200** with empty content — `status: incomplete`,
`incomplete_details.reason: max_output_tokens`, reasoning tokens billed, `output: []`. The
reasoning tokens are consumed *before* any visible text, so the whole budget can be spent
with nothing to show. Observed reasoning consumption on trivial prompts spanned 48–499 tokens
across efforts, so a budget under roughly 600 risks an empty completion for a one-word
answer.

Three specific traps follow. Any health check asserting only HTTP 200 passes against a route
that cannot emit a word — the distinguishing signal is `status` / `stop_reason`, not the HTTP
code. `CLAUDE_CODE_MAX_OUTPUT_TOKENS` defaults to **32000 for unrecognized gateway model
IDs**, and the docs state that raising it "reduces the effective context window available
before auto-compaction triggers" — on a shared-pool model that trade is direct, not
approximate. And ocx currently has **no window at all** for the muse models (§3.1), so
nothing in the toolchain knows the 1,048,576 figure, no `[1m]` marker is applied, and Claude
Code falls back to a conservative default — leaving the largest window in the catalog the one
least usable.

**(d) A silent-truncation risk from the four unknown windows.** `gpt-5.4-mini` and the three
muse models have no window in ocx. That is conservative for compaction, but it also means the
one layer that could compute a per-model floor has nothing to compute from.

---

## 7. Probe isolation

Two tests needed a config mutation. Both ran in a throwaway directory via `OPENCODEX_HOME`,
which `resolveConfigDir()` (`src/config.ts:547`) honors ahead of `~/.opencodex`, with a port
(10999 / 10998) different from the operator's 10100 and a placeholder credential string. The
isolation is demonstrable rather than asserted: `ocx models context status` inside the
throwaway `HOME` returned `Error: Proxy is not running`, proving the probe could not reach
the operator's daemon. Both directories were deleted with `rm -rf` and verified gone. No
`ocx models context value|provider|all` mutation and no `ocx claude config set` was ever run
against the operator's real config, which still has no `claudeCode` block and no
`contextCapValue` / `providerContextCaps` keys.

---

## 8. The workaround, specified

The design follows from one fact: Claude Code cannot hold a per-model number (§4.6), and ocx
can (§3.1, §3.4). So **the gateway owns the per-model number and the session owns a
conservative floor.**

As adopted by the operator on 2026-08-07, the concrete settings are:

| Setting | Value | Why |
|---|---|---|
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | **272000** | smallest real window in the selected model set (§8.2) |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | **unset** — measure first | one-directional against an undocumented default; procedure in §8.2.1 |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | set explicitly for shared-pool sessions | defaults to 32000 on unrecognized IDs and trades against input (§8.2.2) |
| provider `modelContextWindows` | recorded for the four unknown models | the gateway is the right home for the fact (§8.3) |

### 8.1 Layer ownership

| Fact | Owning layer | Why |
|---|---|---|
| Per-model context window | **ocx** | it is the only layer with a per-model map, and it applies to every client, not one session |
| Whether a selector may be `[1m]`-marked | **ocx** (`autoContext`) | the marking predicate is the only per-model mechanism that survives the per-session constraint |
| The session compaction floor | **Claude Code env**, injected by ocx | process-wide by construction; must be safe for the *smallest* model in the session |
| Output-budget ceiling | **Claude Code env** | `CLAUDE_CODE_MAX_OUTPUT_TOKENS`; on muse this trades directly against input |
| The recorded truth for each window | **this repository's calibration table** | config drifts and vendor catalogs move; the table is reviewable and testable |

The rule: **configure the gateway, not the session, whenever the gateway can hold the fact.**
A gateway setting applies to every client and survives a new terminal; an env var applies to
one process and is easy to forget. Env vars are reserved for the one thing the gateway
genuinely cannot express — the single per-session floor.

### 8.2 The adopted floor: `CLAUDE_CODE_AUTO_COMPACT_WINDOW=272000`

**Operator decision, 2026-08-07.** The proposal on the table was 372,000 — ocx's compiled 5.6
number. The finding in §5.1 decided against it: 372,000 sits roughly 100,000 tokens *above*
what the provider's current subscription catalog serves for that family, so at 372,000 the
compaction net sits **behind** the model's real ceiling and the failure mode becomes
provider-side truncation rather than a clean local compaction. The verified floor was chosen
instead.

272,000 is inside the real limit for both the 5.6 family and `gpt-5.5`. Because Claude Code
applies `min(believed window, env)` (§4.2), a smaller model is unaffected: `gpt-5.3-codex-spark`
stays accounted at its own 100,000 rather than being pulled up to the floor.

**Record the derivation rule, not just the number.** The floor is *the smallest real window
among the models the operator actually selects* — sized for the smallest model reachable in the
session, **never the largest**. It was derived from a selected set of the
gpt-5.6 family, Claude 5, and muse 1.2, whose smallest real window is 272,000. The number
therefore expires when the set changes: **a reader who adds a 100,000-token model must lower
the floor to match it, not inherit 272,000.** Re-derive on any change to the selected set.

Two consequences to state plainly rather than bury:

- **This under-uses `gpt-5.4` and muse, by design.** Both carry roughly 1M, so a 272,000 floor
  leaves most of their window unreachable. That is the accepted cost of one process-wide value
  serving a mixed model set.
- **The pressure valve is the single-model opt-in, not a workaround.** A session that will
  genuinely stay on one large model may raise the value to that model's own window, accepting
  that mid-size models go unmarked for the duration (§6a). Raising it as a global default is
  precisely the error the floor exists to prevent.

Anything at or below 100,000 is not protectable by this variable at all — that is the
documented clamp floor (§4.2, §4.7) — so Spark work stays in bounded packets with `/compact` as
its recovery.

### 8.2.1 `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is deliberately left UNSET, pending measurement

**Operator decision, 2026-08-07.** The request was 70%. It is deferred, and §4.3 is why: the
override is **one-directional** — it can only compact earlier, and "values above the default
percentage are ignored" — while **the default percentage is not documented anywhere**. So `70`
is either a real change or a silent no-op, and documentation alone cannot distinguish those two
outcomes. A setting whose effect is unknown does not ship.

What makes this settleable in one pass is that the arithmetic needed is
`default_pct = pre_tokens / effective_window`, and both terms are observable.

**The surfaces that carry the signal.** Of everything checked, exactly one gives a token count
for the main conversation at the compaction boundary:

| Surface | Carries | Use |
|---|---|---|
| OpenTelemetry `claude_code.compaction` event | `trigger` (`auto`/`manual`), `pre_tokens`, `post_tokens`, `success`, `duration_ms` | **the measurement** — the only main-thread source of `pre_tokens` |
| `PreCompact` / `PostCompact` hooks | `trigger`, `custom_instructions` / `compact_summary` | unambiguous auto-vs-manual boundary marker; **no token count** |
| `/autocompact` with no argument | the current window in tokens (v2.1.221+) | reads the denominator |
| Statusline `context_window.*` | `used_percentage`, `total_input_tokens`, `context_window_size` | last usage before the boundary; see caveats |
| `SessionStart` `source: "compact"` | that a compaction occurred | weaker — does not distinguish auto from manual |
| Subagent transcript `compact_boundary` | `compactMetadata.preTokens` | secondary source, but a different conversation and window |

No surface reports the effective *percentage*. `/context` shows usage by category and an
over-limit warning, but not the threshold in force.

**The procedure.** Before launching, export `CLAUDE_CODE_ENABLE_TELEMETRY=1` with
`OTEL_LOGS_EXPORTER=console` (the compaction event is a log/event, not a metric — a metrics-only
exporter will not show it) and redirect output to a file. Register a `PreCompact`/`PostCompact`
pair that logs `trigger` with a timestamp. Then:

1. Put the session into a mode that compacts *before* the model's limit — the override "applies
   only in sessions that compact before the model's context limit." Launching with
   `--autocompact 200000` is the deterministic way, and the flag is not preempted by a
   higher-priority settings scope.
2. Run `/autocompact` with no argument and record the window **W**.
3. Grow context naturally until auto-compaction fires. Do not run `/compact`.
4. In the telemetry log find `claude_code.compaction` with `trigger: "auto"` and record
   `pre_tokens`.
5. Compute `pre_tokens / W`. If it is at or below 0.70, then `70` is at or above the default and
   would be **ignored**. If it is near 1.0, the default is near 100% and `70` would materially
   change behavior.

**The decisive confirmation is an A/B, and it is cheaper than trusting the arithmetic:** repeat
the identical run with `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` and compare `pre_tokens`. Dropping
to roughly `0.70 × W` means it took effect; unchanged means it was ignored and buys nothing.

**Four caveats that will invalidate a careless reading.** `pre_tokens` is documented as
"approximate," so a two-point difference is not resolvable. Auto-compaction has two causes —
proactive-before-limit and recovery-from-a-context-limit-error — only the first is governed by a
percentage, a recovery compaction reads as ~100% regardless, and **no field distinguishes them**
(`trigger` is `"auto"` for both). Auto-compaction may pre-compute a summary in the background,
so a summarization request appearing is not evidence the threshold was crossed — use the
compaction event, not a `query_source: "compact"` request. And once
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` is set, the statusline's `used_percentage` "no longer
indicates when compaction will run" because it always measures against the model's *full*
window, so it cannot substitute for the telemetry reading.

One collection trap: Claude Code strips `OTEL_*` exporter variables from every subprocess it
spawns, including hooks, so a hook cannot re-read the telemetry configuration.

### 8.2.2 The output budget must be set for a shared-pool session

`CLAUDE_CODE_MAX_OUTPUT_TOKENS` defaults to **32,000 for model IDs Claude Code does not
recognize** — which is every gateway-served name here — and the docs state that raising it
"reduces the effective context window available before auto-compaction triggers" (§4.5). So
output budget and input capacity are coupled even on a separate-reservation model.

On muse the coupling is exact rather than approximate, because the 1,048,576 tokens are one
shared pool (§5.2). A long conversation mechanically starves the output allowance, and that is
the **measured cause of the very first muse probe returning empty output with
`status: incomplete`** — the budget was consumed by reasoning tokens before any visible text
(§6.1 of the muse memo).

For a muse-heavy session, set the ceiling explicitly rather than accepting the default: above
the observed reasoning floor of roughly 600 tokens plus the task's expected output, and low
enough that it does not consume the input capacity the task needs. Do not raise it toward the
window's size on a shared pool — that starves input directly.

### 8.3 The per-model override recipe

**For a routed provider (muse), record the real window in the gateway.** This is the durable
fix and it is the one that unlocks muse's measured window, and it is also where the four models
ocx does not know (`gpt-5.4-mini` plus all three muse entries) belong. Because there is no CLI
flag (§3.3), it is a config edit adding to the `muse` provider block in
`~/.opencodex/config.json`:

```json
"modelContextWindows": {
  "muse-spark-1.2": 1048576,
  "muse-spark-1.1": 1048576,
  "muse-spark-1.2-contributor": 1048576
}
```

After which ocx knows the window, `shouldMarkOneMillion` marks those selectors (1048576 ≥
1000000, so it marks unconditionally), and Claude Code accounts 1M for them while compacting
at the session floor. Two hard conditions on doing it: the number must be the **measured**
1048576 from §5.2 and not a rounded 1000000 — the rounded figure is both wrong and changes
whether the marking predicate fires — and because the pool is **shared**, the output ceiling
must be set deliberately per §8.2.2.

**The operator's live config is currently untouched, and that is verified rather than assumed.**
Re-checked at implementation time: both the `openai` and `muse` provider blocks have
`modelContextWindows` **absent** and `contextWindow` absent, there is no `claudeCode` block, and
`contextCapValue` is unset. So this snippet is a documented, deliberate step requiring the
operator's own authorization — not a description of current state, and not something already
applied by this memo.

**For the native gpt models, the gateway cannot be corrected from config** (§3.3) — the
window is compiled in. The only lever is the compact window, and the adopted floor (§8.2) is
set through the gateway's own persistent setting rather than a per-shell export:

```
ocx claude config set --compact-window 272000    # the adopted floor, per 8.2
ocx claude config set --compact-window default   # restore ocx's 350000 default
```

That is a persistent gateway-side setting (it writes `claudeCode.autoCompactWindow`), so it
survives new terminals — preferable to exporting `CLAUDE_CODE_AUTO_COMPACT_WINDOW` per shell.
A user-exported value still wins if present, and ocx feeds it into the marking predicate so
the marker and the threshold can never separate.

**The single-model opt-in.** The session floor is only safe because it assumes the smallest
model. An operator who is deliberately staying on one model for the whole session can raise
it to that model's own window — accepting that mid-size models are unmarked for the duration.
That is the honest shape of "opt into a bigger window": it is per-session, it requires knowing
you will not switch models, and it is not something the tooling can verify for you.

### 8.4 Where per-model truth is recorded so it does not rot

`skills/model-tier-rightsizing/references/model-routing-calibration.md` gains a **Context
windows** section carrying the §5 table, the shared-versus-separate column, the layer
ownership rule, the adopted floor with its derivation rule, and the requested-versus-served
distinction. `tests/test_context_windows.py` pins that table's internal consistency and its
agreement with the adopted floor, so the documented windows and the configured number cannot
silently diverge — including a pin that the floor never exceeds the smallest window it claims
to protect, and that the deferred percentage override stays unset until measured (§9).

`skills/agentic-sdlc/references/tiered-orchestration.md` points at that table rather than
restating it. One owner per fact.

### 8.5 The requested-versus-served rule, applied to context

The calibration already separates a *requested* value from a *readback*. Context takes the
same treatment, and the reason is specific rather than formal: a `RuntimeAssignment`'s
`requested_context_form` is a **request**. It is never proof of the served window.

The evidence is in this document. `[1m]` requests read back the base model ID and prove
nothing about the upstream window. ocx's compiled 372,000 for the 5.6 family disagrees with
OpenAI's current 272,000, so even the gateway's own number is a belief, not a served fact.
Four models have no known window at all. And the Anthropic-shaped catalog returns
`max_input_tokens: null` for ten of eleven entries, so discovery does not supply the fact
either. Record `context_readback_status: unavailable` unless transport telemetry independently
exposes effective context behavior, and never copy a requested form into a readback field.

---

## 9. Reversal conditions

Three changes would reopen this design:

1. **A gateway release that advertises per-model windows on the Anthropic-shaped catalog.**
   The field already exists (`max_input_tokens`) and is deliberately null on unmarked rows.
   If ocx begins populating it truthfully — or exposes a per-model CLI write surface for
   native models — the config-edit recipe in §8.3 becomes unnecessary.
2. **A Claude Code release with per-model context limits.** A settings structure keyed by
   model that carries a window, or a per-alias token count rather than the binary `[1m]`
   toggle, would remove the per-session constraint that forces the conservative floor.
3. **ocx correcting the 5.6 family to 272,000**, or OpenAI restoring 372,000. Either
   resolves the §5.1 mismatch and changes the recommended default.

Until then: the gateway owns the per-model number, the session owns a conservative floor, and
the calibration table owns the recorded truth.
