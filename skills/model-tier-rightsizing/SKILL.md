---
name: model-tier-rightsizing
description: |
  Route workflow agents by wrong-output blast radius, verification strength, and
  available capacity. Use when assigning an exact model and requested effort to
  each agent, planning a gated fan-out, preserving a high-impact decision lane,
  or escalating after null output, semantic uncertainty, throttling, or missing
  provider readback. Keeps stable routing doctrine here and delegates all
  generation-specific IDs, effort bands, evidence, quotas, and roadmap mappings
  to one canonical reference.
---

# Model-tier rightsizing

Route the consequence of a wrong answer, not task prestige or marketing rank.

## Dispatch ladder

1. **Derail:** the output sets scope, authority, cross-system invariants, data-loss
   policy, or final stop/go and later work will treat it as settled truth. Use the
   strongest certified decision lane, normally solo, and require re-derivation.
2. **Degrade:** an error may pass ordinary gates and silently weaken an artifact.
   Use a certified judgment lane against explicit acceptance criteria, then review
   an immutable candidate independently.
3. **Retry:** a compiler, test, schema, deterministic comparison, or evidence check
   makes a wrong answer visible. Use the certified gated-volume lane and retry or
   escalate on failure.
4. **Mechanical redo:** extraction, inventory, formatting, or another bounded
   transform is cheap to repeat. Use the least expensive certified lane whose
   output is completely checked.

A task moves down only when a real gate changes its failure from silent damage to a
visible retry. Importance alone never moves it up.

## Required dispatch contract

Every delegated call must state:

- an **exact model ID** accepted by the active transport; never rely on an inherited
  model or an unverified alias;
- the requested effort and context form, kept separate from resolved model, resolved
  effort, provider, and context telemetry;
- one bounded artifact, owner, stop condition, and wrong-output class;
- the gate or independent reviewer that detects failure;
- the fallback and escalation action before work starts.

Record resolved facts only from adapter readback. If readback is absent, record the
field as inherited, unknown, or unresolved; a requested value and echoed prompt text
are not resolution evidence.

## Fallback discipline

Treat null, malformed, truncated, missing, or transport-rejected output as failure.
Classify transport failure versus task-output failure, apply bounded backoff, and
retry the same certified cell once. Reduce fan-out on capacity pressure, but do not
silently weaken the blast-radius class or gate. A fallback may cross lanes only when
an added verifier genuinely preserves the failure boundary. If no certified route
exists, stop or decompose into smaller verifiable artifacts.

## Canonical calibration

Load `references/model-routing-calibration.md` before dispatch. It is the sole human
reference for current exact IDs, requested effort bands, alias behavior, context
boundaries, smoke evidence, quotas, roadmap-family lanes, vendor complements,
fallbacks, rerun triggers, and auditable receipts. Do not copy its matrices here;
recalibrate the reference when transport, lineup, telemetry, or representative
results change.

For a second scheduling axis, model context footprint, and the boundary between
Dynamic Workflows, CLIProxyAPI, and process-wide Claude Code compaction, read the
flagship skill reference `references/claude-code-multi-model-routing.md`.
