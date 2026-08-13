---
name: dispatching-exact-ocx-models
description: Use when a conductor-selected exact OCX route must be injected into an Agent or Workflow worker, especially for generated ocx agent types, namespaced provider IDs, or tool surfaces whose compatibility and post-run identity need verification. Not for choosing a tier or evaluating candidates; use model-tier-rightsizing first.
---

# Dispatching exact OCX models

Load `model-tier-rightsizing` first. This skill consumes its resolved `RuntimeAssignment`; it does
not choose a preferred model or make an unresolved route dispatchable.

## Preconditions

Require `resolution_state: resolved`, an exact model ID, explicit effort and context form, compatible
tools, immutable injection evidence, and a known post-run receipt path. An inherited/default model,
prompt prose, alias, missing injection support, incompatible tool surface, or absent receipt stops
before spawn.

## Select the real injection surface

- **generated `ocx-*` Agent types:** the agent definition owns the exact route. Its public `model`
  argument is a placeholder and may be ignored. Use only the generated type whose pinned route
  exactly matches the assignment; never put another ID in the prompt or placeholder and claim it
  was selected.
- **Workflow `agent()` calls:** every `agent()` call carries the assignment's exact `model` and `effort`.
  Do not inherit either. The context request must use the adapter's supported request form;
  prose such as “use 1m” is not injection.
- **Namespaced provider IDs:** preserve the full ID, for example
  `muse/muse-spark-1.2-contributor`. Never strip the provider prefix or replace it with a nominal
  family name.

Choose an agent type/tool set compatible with the route before dispatch. Muse tool names must be
at most 64 characters; remove unnecessary model-visible tools and avoid structured-output tooling
when that extra tool is incompatible. Do not broaden permissions merely to retain a convenient
agent type.

## Verify, then admit

After the call, correlate the concrete request with adapter readback or gateway attribution and
compare observed provider/model to the assignment. Requested identity is not readback; neither a
prompt echo nor a response-body model label proves the route. Record effective effort/context only
when independently exposed, otherwise mark them unavailable rather than copying requested values.

If identity is ambiguous, mismatched, or uncorrelated, discard the result and stop or use the
assignment's predeclared fallback. **No verified receipt, no dispatch** means no result may enter the
production handoff as if the assignment ran.

## Output

Return the bounded worker artifact plus its verified receipt, or one refusal/SeedProposal naming
the missing injection, compatibility, or receipt capability. Never silently substitute a model.

## Admission rationale

This skill clears all four admission gates: its description selects exact dispatch rather than tier
choice; its recurring share justifies one small row; exact OCX routes and both dispatch surfaces
exist now; and it is task-shaped rather than always-on. It clears all five promotion signals:
**Recurs; needs sequencing; has repeated failure modes; has stable input/output; benefits from
explicit handoff**.
