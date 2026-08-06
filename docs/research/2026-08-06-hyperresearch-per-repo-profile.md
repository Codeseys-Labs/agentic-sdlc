# Hyperresearch model pins: solved per-repository, upstream-supported

**Date:** 2026-08-06 · **Status:** verified end-to-end by execution · **Supersedes** the
"do not vendor hyperresearch / static model pins are a blocker" conclusion in
`2026-08-05-vendoring-install-ux-memo.md` and `2026-08-05-plugin-restructure-recommendation.md`.

## The answer

Per-repository customization is not a workaround — it is hyperresearch's own designed
mechanism, and it fully resolves the model-pin conflict with `RuntimeAssignment` doctrine
**without vendoring anything, without patching generated files, and without any global
mutation.**

A `[profile.<name>]` table in a project's `.hyperresearch/config.toml` accepts **per-agent
model assignments**, and the installer renders those values into the agents' `model:`
frontmatter at install time. Quoting `hyperresearch/core/profiles.py` (v0.10.0):

> "A profile is a named, validated bundle of every knob that governs research scale:
> source-count gates, fetcher fan-out, loci caps, depth budgets, draft counts, word targets,
> critic caps, **and per-agent model assignments**."

and on `ModelMap`:

> "Per-agent model assignments, rendered into installed agent frontmatter. Values are whatever
> Claude Code accepts in an agent's `model:` line — an alias (`haiku`, `sonnet`, `opus`) **or a
> full model ID**."

## Verified end-to-end

All of the following was executed in throwaway `HOME`s and project dirs; nothing global was
written (confirmed: the operator's `~/.claude/agents/` stayed at 14 files throughout, and the
isolated `HOME` received 0).

1. **Per-project install lands entirely in-project.** `hyperresearch install . --profile light`
   (no `--global`) wrote **16 agents + 19 skills into `./.claude/`** and **zero** files into
   `$HOME/.claude`.
2. **Built-in profiles do not vary models.** `light` and `premier` both render 7 `sonnet` +
   9 `opus`. The built-in gears control *scale* (source counts, draft counts, critic caps), not
   model choice — so "switch profiles" alone does not fix the pins.
3. **A user-defined profile does.** The correct key is `[profile.<name>]` (not
   `[pipeline.profiles.<name>]`, which my first guess used and which is silently ignored). It
   supports `extends`, and `hyperresearch profile list` then reports it as
   `sdlc (user-defined gear) *current gear`.
4. **Exact model IDs render.** With all 13 `ModelMap` slots pinned, a re-install produced
   agents whose frontmatter carried **only exact IDs — zero `sonnet`/`opus`/`haiku` aliases
   remaining**:

   | rendered `model:` | agents |
   |---|---|
   | `claude-fable-5` | 5 |
   | `claude-opus-5` | 4 |
   | `claude-sonnet-5` | 4 |
   | `claude-haiku-4-5-20251001` | 3 |

The 13 overridable slots: `fetcher`, `source_analyst`, `loci_analyst`, `depth_investigator`,
`corpus_critic`, `cite_checker`, `browser_fetcher`, `draft_orchestrator`, `synthesizer`,
`critics`, `patcher`, `polish_auditor`, `readability_recommender`. `ModelMap` is
`extra="forbid"`, so a typo'd slot name fails loudly rather than being ignored — a fail-closed
property worth relying on. Unspecified agents keep their defaults.

## Why this fits the bundle's existing shape

This mirrors the lifecycle split `AGENTS.md` already states — *"Global installation and
per-repository activation are separate lifecycle planes."* Hyperresearch has the same split, so
it composes rather than conflicts:

| Plane | Action | Scope |
|---|---|---|
| Global (optional) | `hyperresearch install --global` | entry skill only, every session |
| **Per-repository** | `hyperresearch install . --profile <name>` + `[profile.<name>]` in `.hyperresearch/config.toml` | the 16 agents + step skills, **models chosen per repo** |

The per-repo config is a **reviewable, committed artifact** in the target repository — which is
exactly the provenance posture the doctrine wants. The conductor's model choices become a
checked-in file, not an ambient global setting, and different repos can carry different lanes.

## Corrections to earlier conclusions

- ~~"No discoverable license or provenance"~~ — **wrong.** PyPI reports **MIT**, upstream
  `jordan-gibbs/hyperresearch`, current version **0.10.0**.
- ~~"Unrendered Jinja/template artifacts"~~ — **mostly wrong.** The `{{` occurrences are
  literal braces inside JSON code fences in the prompts, not broken templating.
- ~~"Static model pins are a vendoring blocker"~~ — **obsolete.** The pins are *generated
  output* of a renderer the operator configures. Patching them post-hoc (by mise or otherwise)
  would be overwritten by the next `install`; configuring the profile is the supported path.
- **Still true:** the closed 14-role roster (`count: 14` + 14 pinned sha256 in
  `runtime-assignment-normative-contract-v1.json`, enforced at `validate_bundle.py:915-935`)
  means hyperresearch's agents must remain an *external optional capability*, never entries in
  this bundle's `agents/`. Per-repo rendering keeps them outside that contract, which is why
  this approach works at all.

## Recommended wiring

Pin the upstream tool with the already-pinned `uv` — no new `[tools]` entry, so no mise.lock
regeneration and no frozen-fixture churn (a new mise *task* is free; `validate_mise` only
requires `REQUIRED_TASKS` be a subset):

```toml
[tasks."research:install"]
description = "Install the pinned upstream hyperresearch harness into this repository"
run = "uv tool run --python 3.12.11 --from hyperresearch==0.10.0 hyperresearch install . --profile sdlc"
run_windows = "uv.exe tool run --python 3.12.11 --from hyperresearch==0.10.0 hyperresearch install . --profile sdlc"
```

Pinning the interpreter matters: unpinned, the tool warns `Python 3.14 is not yet supported`;
with `--python 3.12.11` the warning is gone. Ship a documented `[profile.sdlc]` template for
target repos to copy, and let `/sdlc-init` treat it as reviewed per-repository activation.

## Cross-check against pi-lab's independent evaluation (added 2026-08-06)

pi-lab evaluated hyperresearch separately in
`pi-lab/docs/research/20260727/hyperresearch.md` and reached **"FORK-EDIT; do not SOURCE or
BUILD from zero"** — a more cautious disposition than this memo's, and it raises control costs I
did not examine. Reading it changes the confidence of the recommendation above, though not its
shape. Its findings split cleanly:

**Objections that target `hyperresearch-pi@0.1.6` — a third-party *Pi wrapper*, not upstream, and
not what this memo proposes:**
- The wrapper auto-runs `pip install hyperresearch` at extension startup with **no version pin or
  hash**, resolving the executable from ambient `PATH`/`HYPERRESEARCH_BIN`. This is the single
  strongest objection and **the `uvx` proposal above already answers it**:
  `--from hyperresearch==0.10.0 --python 3.12.11` pins both package and interpreter, and resolves
  no ambient binary.
- The wrapper writes `~/.pi/agent/hyperresearch-models.json`, rewrites project agent files on
  every `session_start`, and its uninstall **recursively deletes** a project directory without
  distinguishing generated files from operator edits. The per-repo `install` path proposed here
  is operator-invoked, not session-triggered, and deletes nothing — but the underlying hazard
  (generated files indistinguishable from authored ones) is real and argues for keeping rendered
  output in a clearly generated location and committing it deliberately.

**Findings pi-lab attributes to *upstream*, which therefore do apply if the tool's model-callable
surface is ever exposed:**
- `note new --body-file` reads the given path with **no containment check**, so an absolute path
  or `../` traversal can pull any process-readable file into a vault note that `note show` can
  later surface to a model — a local-file-disclosure path.
- The built-in web provider follows redirects with **no host allowlist and no private-address or
  loopback guard** (SSRF-shaped target selection), and `hr_academic` reaches external scholarly
  APIs directly — unapproved network egress from a model-callable tool.

**Why this does not overturn the recommendation, and where it narrows it.** This memo proposes
using exactly one verb — `hyperresearch install . --profile <name>` — to *render agent files*, and
never exposes `hr_*`/`note` tools to a model. Under that usage the traversal and SSRF findings are
latent, not active. But they become live the moment anyone actually *runs* the pipeline, which is
the entire point of installing it. So the honest position is: **pinning and rendering is safe;
operating the pipeline carries unreviewed egress and file-read surface that neither this memo nor
pi-lab's has cleared.** Treat pipeline operation as a separate, still-unapproved decision, and
prefer pi-lab's FORK-EDIT posture over SOURCE if it ever becomes a bundled capability rather than
an optional operator tool.

Procedural lesson, same as the ECC correction: pi-lab's research corpus had already done deeper
diligence than this session's, and I did not consult it before recommending. Read
`pi-lab/docs/research/**` first for any source pi-lab already evaluated.

## Still open

- Whether a `[profile.<name>]` overlay can also alter the *effort* dimension
  (`model_reasoning_effort`), which `RuntimeAssignment` treats as a distinct requested field.
  `ModelMap` covers `model` only; I did not find an effort slot.
- Whether the rendered `model:` values survive hyperresearch's own auto-bootstrap path (the
  entry skill runs `install --steps-only` on first `/hyperresearch` in a project) — that path
  installs step *skills*, not agents, so it likely does not re-render agents, but I did not
  verify it.

No outward effect is authorized by this document; nothing in the bundle was changed.
