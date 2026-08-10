# ADR-0012 — Per-model context windows are owned by the gateway, the session carries one conservative floor, and the recorded truth lives in the calibration table

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Relates to:** `docs/research/2026-08-07-context-window-accommodation.md` (the executed
  probe record and the full per-model table),
  `docs/research/2026-08-07-muse-spark-qualification.md` (§5.8 measured shared window, §6.1
  starvation hazard), `docs/research/2026-07-22-claude-code-multi-model-routing.md` (the
  earlier dated design note whose version-gating claim this record verified rather than
  inherited), `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md` (the
  gateway this record configures), `docs/adr/0007-muse-spark-direct-route.md` (the route whose
  window is measured and shared),
  `skills/model-tier-rightsizing/references/model-routing-calibration.md` (the table this
  record makes authoritative)

## Context

The served catalog holds models whose real context windows differ by more than a factor of
ten — from 100,000 tokens to a measured 1,048,576 — and the operator asked whether the client
and the gateway support accommodating that per model, and if not, how to document it and work
around it.

Three facts from the executed probes decide the shape of the answer, and the second is the one
that was assumed wrong going in.

**The client cannot hold a per-model window.** Every relevant control is process-wide: one
maximum-context assumption, one auto-compaction window, one output ceiling, resolved against
whichever model is active. This was verified positively (the maximum-context variable is
documented against "the active model", singular; a settings environment block applies "to
every session") and negatively, which is what makes it a finding rather than an absence of
reading. No settings key maps a model to a window — the one key that *is* keyed by model ID
maps model IDs to provider-specific ID strings and carries no context field. Agent and
subagent definitions have no context field in either the frontmatter or the SDK type. And the
vendor already ships a per-tier environment-variable suffix family for prompt caching and
deliberately did not extend it to context. The only genuinely per-model context lever is a
binary extended-context marker read *per variable*, not an arbitrary token count. So a session
that switches models, or fans subagents across models in one process, cannot give each model
its own window through any documented configuration.

**The gateway already models per-model windows, and already ships a mechanism that converts
the process-wide client knob into a per-model floor.** This is the correction to the premise
this work started from. The gateway computes a real window for six of the served models and
exposes them per model. More importantly, its auto-context mechanism — on by default —
decides *per model* whether that model's selector carries the extended-context marker, and the
client applies the minimum of what it believes the window is and the environment value.
One environment number therefore behaves as a per-model floor: a marked large model compacts
at the floor while an unmarked smaller model is accounted at its own size. The marking
predicate refuses to mark any model whose window is below the floor, precisely because marking
one would put the compaction net behind the model's real limit. That safety property is the
whole design, and it already existed.

**The discovery catalog does not carry the numbers, even where the gateway knows them.** The
client reads an Anthropic-shaped list that does have a window field, and that field is null on
ten of eleven entries — populated only on a synthesized extended-context row where the
advertised number equals what the client will actually believe. That silence is deliberate and
correct, and it is also why per-model accommodation cannot ride on discovery.

Two gaps in the current state sharpen the decision. The gateway's compiled window for one
model family sits 100,000 tokens **above** the provider's current subscription catalog — an
over-promise on exactly the axis where over-promising causes mid-session failure, and not
correctable from configuration because those windows are compiled in. And four served models,
including the two with the largest measured window, have no gateway-computed window at all,
so no per-model floor can be computed for them and the largest window in the catalog is the
least usable.

## Considered options

1. **The gateway owns the per-model number, the session carries one conservative floor, and
   the calibration table owns the recorded truth (chosen).** Uses the mechanism that already
   exists rather than inventing one, puts each fact in the only layer that can hold it, and
   keeps the floor safe for the smallest reachable model with a documented single-model
   opt-in for the case where an operator knowingly stays on one model. Accepts that the
   floor is a compromise in any genuinely mixed-model session, because the client constraint
   admits no alternative.
2. **Set the session floor per model at dispatch time.** Rejected on mechanics, not on taste:
   there is no per-model context field anywhere in the client's configuration surface, so this
   option does not exist to be chosen. Attempting it via one process per model is the option
   below.
3. **One client process per model, each with its own floor.** Rejected as the default. It does
   deliver true per-model windows and remains available for a deliberately homogeneous run,
   but it forfeits in-process multi-model fan-out, multiplies process and authentication
   envelopes, and pays that cost on every mission rather than only when a session is genuinely
   context-bound. Keeping it as an operator-chosen escape hatch preserves the benefit without
   imposing the cost.
4. **Tune the floor to the largest served window so no capacity is wasted.** Rejected, and it
   is the tempting option. Raising the floor is two-sided: the marking predicate requires a
   model's window to be at least the floor, so raising it past a mid-size model's window
   silently unmarks that model, and raising it past a smaller model's real ceiling puts the
   compaction net behind the point where requests start failing. Wasted capacity is
   recoverable; a compaction net behind the real limit is a mid-session failure.
5. **Set the maximum-context variable instead of the compaction window.** Rejected as the
   default lever. That variable's behavior inverts on whether the model ID *looks*
   vendor-shaped — applied directly for unrecognized names, ignored for recognized ones unless
   compaction is also disabled — and this route's discovery IDs are vendor-shaped strings, so
   which branch applies was not settled by these probes. The compaction-window path has
   documented, uniform semantics and a documented clamp against the model's real window.
6. **Record the numbers in the launcher or in the gateway config as the source of truth.**
   Rejected. Configuration drifts silently and a launcher constant is invisible to a reviewer.
   A table in the installed calibration, pinned by a test, is reviewable and cannot diverge
   from the default it recommends without failing.
7. **Do nothing and document only the mismatch.** Rejected as leaving a measured 1,048,576-token
   window unusable and leaving a known 100,000-token over-promise in force with no recorded
   operating limit.

## Decision

1. **The gateway owns the per-model window.** Wherever a per-model window can be recorded in
   the gateway, that is where it is recorded — one place, applying to every client and
   surviving a new process. Session environment variables are reserved for the single fact the
   gateway cannot express, which is the per-session floor. The general rule: configure the
   gateway, not the session, whenever the gateway can hold the fact.

2. **The session floor is 272000 tokens, and it is derived rather than picked.** The rule is:
   the floor is the smallest real window among the models the operator actually selects. For
   the selected set of the gpt-5.6 family, Claude 5, and muse 1.2, that smallest real window is
   the 5.6 family's provider-served 272000. The rule outranks the number — **the floor must be
   re-derived whenever the selected set changes**, and a reader who adds a smaller model is
   obliged to lower it rather than inherit 272000.

   The gateway's compiled 372000 was considered and rejected: at 372000 the compaction net
   sits *behind* the model's real ceiling, so the failure mode becomes provider-side truncation
   instead of a clean local compaction. Because the client applies the minimum of its believed
   window and the environment value, a smaller model stays accounted at its own window rather
   than being pulled up to the floor. A route whose window is at or below the client's
   documented minimum floor cannot be protected by this variable at all and is kept to bounded
   packets with manual compaction as its recovery.

   This floor **under-uses the two roughly-1M models by design**. That is the accepted cost of
   one process-wide value serving a mixed model set, recorded as a known consequence rather
   than discovered later.

3. **A larger window is an explicit, per-session opt-in for a knowingly single-model session,
   and that opt-in is the pressure valve rather than a workaround.** Raising the floor is
   permitted when the operator is deliberately staying on one model, accepting that mid-size
   models are unmarked for the duration. It is never a global default, because it cannot be
   verified for the operator that no model switch will occur.

4. **The proactive-compaction percentage is an opinionated 85 (amended 2026-08-08; was
   "stays unset until measured").** The override is one-directional — it can only compact earlier,
   and a value above the (undocumented) default is silently ignored — so 85 is safe before
   measurement: if the true default is ≤85 it is a no-op, if the true default is near 100% it
   compacts materially earlier at ~0.85×272000≈231200. The launchers ship it as
   `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85` only when the operator has not already exported a value
   (`assets/claude/session-inheritance.sh` and the fallback in both `scripts/*-claude.sh`), so an
   installer tunes per environment with `export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=<1-100>` before
   `ccodex launch`. The research memo still records the procedure that would settle the true
   default — the decisive test is an A/B on `claude_code.compaction` `pre_tokens` — and replacing
   85 with a measured value is an adjustment under this record, not a reversal.

5. **The output ceiling is set explicitly for shared-pool sessions.** The client defaults its
   output maximum to 32000 for model IDs it does not recognize, which includes every
   gateway-served name, and raising that value reduces the context available before compaction.
   On a shared-pool model the trade is arithmetic rather than approximate, and an insufficient
   budget returns a successful status with empty content. Accepting the default silently on a
   shared-pool route is therefore a defect, not a neutral choice.

6. **Per-model truth is recorded in
   `skills/model-tier-rightsizing/references/model-routing-calibration.md`**, in a Context
   windows section that is the sole owner of the per-model numbers, the shared-versus-separate
   input/output shape, the adopted floor and its derivation rule, and the layer-ownership rule.
   `skills/agentic-sdlc/references/tiered-orchestration.md`
   points at that section rather than restating any number. One owner per fact.

7. **A requested context form is a request and never proof of the served window.** This
   applies the existing requested-versus-readback boundary to context, on specific evidence:
   extended-context request forms read back the base model ID, the gateway's own computed
   window for one family disagrees with the provider's catalog, four models have no known
   window, and discovery returns a null window for nearly every entry. Context readback is
   recorded as unavailable unless transport telemetry independently exposes effective context
   behavior, and a requested value is never copied into a resolved or readback field.

8. **An unknown window is recorded as unknown.** No window is inferred from a sibling model,
   a family pattern, or a third-party aggregator. A model with no sourced window gets no
   marker, which is conservative and correct. The four models the gateway does not know are
   recorded through the routed provider's per-model window map, using the measured value rather
   than a rounded one.

9. **No configuration mutation is authorized by this record.** The recipes for recording a
   routed provider's per-model window and for pinning a session floor are written as recipes.
   The operator's live gateway configuration was verified untouched at the time of writing —
   no per-model window map on either provider, no client-settings block, no context cap — so
   applying any of these requires the operator's own operation-specific authorization.

## Consequences

The measured shared-pool window becomes usable only after the operator applies the recorded
recipe; until then the largest window in the catalog remains the least usable, and that is
recorded rather than papered over. The one model family whose gateway window exceeds the
provider's current catalog now has a documented lower operating limit that an operator can
apply, but the gateway value itself cannot be corrected from configuration, so the mismatch
persists as a known condition rather than a fixed defect.

Any genuinely mixed-model session accepts a floor sized for its smallest reachable model, and
therefore accepts unused capacity on its largest. That is the cost of the client's per-session
constraint, taken deliberately, in exchange for never placing the compaction net behind a real
limit.

The shared-pool hazard now carries a dispatch consequence rather than only a caveat: a health
or liveness check on a shared-pool route must assert non-empty output text, because an
insufficient output budget returns a successful status with empty content while still billing
reasoning tokens.

## Reversal conditions

Three changes reopen this record rather than being absorbed as adjustments:

1. **A gateway release that advertises per-model windows on the discovery catalog the client
   reads, or that adds a per-model write surface for its compiled-in windows.** The field
   already exists and is deliberately null; populating it truthfully removes the need for the
   configuration recipe in Decision item 1 and changes where the number is best owned.
2. **A client release with per-model context limits** — a settings structure keyed by model
   that carries a window, or a per-alias token count rather than the binary extended-context
   toggle. That removes the per-session constraint that forces Decision items 2 and 3, and the
   conservative floor would then be an unnecessary compromise.
3. **The gateway correcting its 5.6-family window to the provider's current value, or the
   provider restoring the higher one.** Either resolves the mismatch behind Decision item 2's
   lower-ceiling clause and changes the recommended default.

Separately, if the measured shared-pool window is ever contradicted by a provider-published
figure, the measurement does not automatically win: it measured admission arithmetic only, and
window *usefulness* across a filled window remains an unmeasured vendor hypothesis. That
conflict would need re-derivation, not a table edit.

This record is evidence for a conductor to cite; it authorizes no configuration mutation,
gateway write, session launch, credential use, push, publication, merge, deployment, or other
outward effect on its own.
