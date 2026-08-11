# ADR-0005 — opencodex is installed by default for split-plane non-Anthropic routing, with the subscription boundary enforced in the launcher

- **Status:** accepted
- **Note:** opencodex is still installed by default and still optional at runtime, but the
  SPLIT-PLANE framing below no longer holds: ADR-0014 replaced the two planes with one
  launch route serving both catalogs.
- **Date:** 2026-08-06
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Relates to:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md`,
  `docs/adr/0013-explicit-unsupported-claude-subscription-passthrough.md`,
  `docs/research/2026-08-05-gateway-selection-memo.md` and its 2026-08-05
  addendum, `docs/research/2026-08-07-opencodex-qualification-canary.md`
  (closes the Decision item 5 canary gate), `skills/repo-toolchain-gates/SKILL.md`

## Context

`docs/adr/0003` resolved the question that had kept opencodex deliberately
unpinned. It rejected subscription-passthrough-for-cost on authorization
grounds — the mechanism works, Anthropic's `legal-and-compliance`
documentation forbids the use case — while explicitly preserving a second,
legitimate purpose in its Decision item 2: **a gateway used with an explicit,
provider-issued credential to reach non-Anthropic models "sits fully within
the supported authentication model and is not gated by this ADR."**

`skills/repo-toolchain-gates/SKILL.md` had recorded the not-pinned stance
against the *unresolved* version of that question, resolved version 2.10.1,
and framed the tool's purpose here as subscription passthrough. With ADR-0003
in place that framing is stale on both counts: the question is closed, and the
purpose that remains open is the API-key/Codex-OAuth carve-out.

The operator's instruction is for that carve-out specifically, in a **split-plane**
shape: a second Claude Code process pointed at the gateway for OpenAI-model
work, while the operator's native Claude session and its config stay untouched.

**Two facts resolved firsthand, not assumed:**

1. **Packaging.** `npm view @bitkyc08/opencodex` reports version 2.10.2, MIT,
   with bins `{opencodex, ocx}` → `bin/ocx.mjs`. The npm mise backend locks
   version+backend only, with no per-platform checksum — the same integrity
   surface as the existing `npm:@os-eco/seeds-cli` and
   `npm:@mermaid-js/mermaid-cli` pins, and weaker than the aqua/github pins.
   Verified: `mise install` resolves and installs it with no credential in the
   environment, so the pin adds no second bootstrap prerequisite.
2. **The upstream default is the opposite of this bundle's boundary.** Reading
   the installed package's `src/cli/claude.ts` and `src/claude/auth-mode.ts`
   directly: `ocx claude` resolves auth to `subscription` markerMode whenever a
   Claude credential is *present* — and also when a source is *unreadable*
   (`auto-unknown` maps to subscription by design, so a failed read never flips
   a subscriber into proxy mode). In that mode it deliberately does not inject
   its own token, so Claude Code keeps its own OAuth and sends it to the proxy.
   That is exactly the shape ADR-0003 prohibits, and it is the tool's default
   path, not an opt-in. A comment in the same file records that opencodex is
   aware of the residual it leaves in subscription mode.

Fact 2 is the load-bearing one: adopting the tool without a wrapper would make
the prohibited route the *easy* route.

**Supervision, also resolved firsthand.** The operator additionally asked that
the launcher own the gateway lifecycle rather than merely attach. opencodex
already has real supervision, so the wrapper delegates to it instead of
building a second one: `ocx ensure` starts-if-down and waits, `ocx restart` is
stop+ensure, `ocx stop` stops cleanly, and `ocx health` performs an
**identity-checked** `/healthz` probe that requires the body to identify as
opencodex and cross-checks the pidfile — so a foreign server answering on the
port is not mistaken for the gateway. Single-instance behavior is native too:
`ocx start` refuses with "Proxy already running", and concurrent `ocx ensure`
calls leave the pid unchanged with one listener bound (verified).

Two upstream behaviors made a thin wrapper insufficient, and both are why the
health verdict is re-probed rather than inherited:

- **`ocx ensure` can exit 0 without starting anything.** Its first branch
  returns early when `codexAutoStart` is disabled (`config.codexAutoStart !==
  false`), printing "Codex autostart is disabled." and exiting successfully. A
  wrapper that trusted that exit code would report a healthy gateway while
  nothing was listening.
- **`ocx status` and `ocx observe logs` exit 0 with the proxy down.** Only
  `ocx health` returns a nonzero status. Driving a verdict from `status` would
  manufacture false health.

One upstream side effect is surfaced rather than hidden: `ocx ensure`/`start`
rewrite `~/.codex` to point Codex's `openai` provider at the proxy, and
`ocx stop` restores it. Isolation in this wrapper covers `CLAUDE_CONFIG_DIR`
only, so a supervision call does mutate shared Codex config.

## Decision

**2026-08-09 amendment.** The active packaging pin is now `2.11.1`. The original
`2.10.2` observations below remain historical evidence for the version actually
qualified on 2026-08-07; changing the active pin does not retroactively relabel
that evidence. The upgrade was installed through the reviewed mise path, and the
current wrapper/context-window behavior was re-verified separately.

1. **`npm:@bitkyc08/opencodex` version 2.11.1 is pinned in `mise.toml` and
   installed by default**, with `depends = ["node"]`, the npm backend, and a
   regenerated `mise.lock`. It joins the convenience tier: no gate consumes it,
   and its absence degrades developer experience without changing any verdict.
2. **`scripts/opencodex-claude.sh` is the only supported entry point**, with
   subcommands `ensure`, `launch`, `launch-ultracode`, `status`, `restart`, and `configure`
   (the existing `ocx:launch`, `ocx:ultracode`, `ocx:status`, `ocx:restart`, and
   `ocx:configure` mise compatibility tasks remain). The separate, explicit operator-tools
   lifecycle installs the `ccodex` dispatcher, whose shorthand and `ccodex ocx <verb>` long
   form both delegate to this canonical script. Historical `ocx-launch` and
   `ocx-ultracode` files remain recognized only so old lifecycle state and interrupted
   transitions can be recovered; fresh installs do not recreate them, and explicit
   retirement removes only unchanged removable owned copies. The Ultracode route injects
   only the session setting, does not bypass permissions, and refuses competing settings or
   bypass flags.
   `launch` runs the gateway-routed Claude Code process under an isolated
   `CLAUDE_CONFIG_DIR` beneath `XDG_STATE_HOME`, so the operator's native
   `~/.claude` session state, roster agents, and model cache are never mutated.
   Verified: a launch wrote opencodex's `ocx-*.md` roster agents and
   `gateway-models.json` into the isolated dir, and `~/.claude` was untouched.
3. **The launcher owns the gateway lifecycle, and it fails closed.** `launch` is
   ensure-then-exec: if the gateway is healthy it proceeds; if it is down it
   starts it (delegating to `ocx ensure`, logging to the state dir) and polls up
   to 15s for readiness; if something is bound or a pid is alive but no healthy
   identity probe succeeds ("half-up"), it restarts **once** and re-probes.
   Claude Code is never launched against a dead or half-up gateway — a gateway
   that will not come healthy aborts with a named reason and exit 1. Because the
   two fail-open paths above exist, **no ocx verb's exit code is accepted as the
   health verdict**; `ocx health` is re-probed after every supervision step and
   is the only verdict. Idempotence is delegated, not reimplemented: the wrapper
   adds no competing pidfile. `restart` refuses to re-ensure after an unclean
   stop, preserving ocx's own guard against re-injecting shared Codex config it
   did not cleanly release. The credential checks in item 4 run **before** any
   supervision, so a refused launch never leaves a gateway running that the
   operator did not ask for.
4. **The subscription-OAuth prohibition is enforced in code, not prose.** The
   launcher scrubs every `ANTHROPIC*`/`CLAUDE*` variable from the child
   environment (a prefix scrub, because credential slots, per-tier model slots,
   and routing flags like `CLAUDE_CODE_USE_BEDROCK` are all leak paths), and it
   refuses with exit 3 rather than launching when a subscription credential
   would still be reachable: an `sk-ant-oat*` token in the environment, a
   `claudeAiOauth` entry in the isolated dir's `.credentials.json`, an
   `oauthAccount` in the sibling `.claude.json`, or a
   `Claude Code-credentials` item in the macOS keychain (the one detector source
   an isolated config dir cannot mask). `configure` additionally refuses
   `ocx login anthropic` and `ocx login anthropic-apikey`.
5. **Installing and launching are not route qualification.** The canary in the
   gateway memo's §4 (probes A, C, D, E, F — fail-closed routing, per-subagent
   pinning, readback admissibility) is the qualification gate for trusting which
   model actually served a request. ADR-0003's Decision item 3 keeps probe B
   moot. Nothing in this ADR runs, satisfies, or substitutes for that canary.
   *Executed 2026-08-07 under separate explicit authorization; see the
   Consequences entry and `docs/research/2026-08-07-opencodex-qualification-canary.md`
   for the verdict and its eight binding conditions.*
6. **The recorded stance in `skills/repo-toolchain-gates/SKILL.md` is
   rewritten, not deleted.** It now states that the tool is pinned, names the
   resolved version and decision date, relocates the surviving boundary to the
   usage level, and generalizes the lesson: when a pinned tool's safe usage is
   narrower than its default behavior, the narrowing belongs in an executable
   wrapper, because prose in a skill file cannot refuse anything.
7. **`ccodex claude-subscription` is deliberately separate from the supported
   split plane.** It is unsupported, account-risk, and not provider-approved;
   its explicit invocation is informed operator choice, not authorization or a
   supported subscription entitlement route. Ordinary `launch` and
   `launch-ultracode` keep every subscription-OAuth refusal in item 4.

   It reads no OAuth value or credential store, uses plain `claude` rather than
   `ocx claude`, and exports only its locally verified `ANTHROPIC_BASE_URL`.
   Before even a gateway status check it refuses the presence of parent
   Anthropic/AWS/Claude routing or auth controls, forced fallback, and TLS
   downgrade controls; it inspects exported names only, never their values. It
   accepts exactly one explicit full native selector before the wrapper `--`, has
   no default, removes only that separator, and rejects aliases, `[1m]` variants,
   `modelMap` exact/date-stripped claims, admission keys, absent/unknown masked
   auth detection, disabled inbound, explicitly disabled native passthrough, and
   non-official native upstream configuration. ADR-0013 defines this narrower
   escape hatch without altering the ordinary route's boundary.

   The route never calls `ocx ensure`, `restart`, or configuration verbs: it
   requires an identity-checked already-healthy gateway so it cannot cause
   OpenCodex's documented shared `~/.codex` lifecycle mutation. In 2.11.1 the
   masked status endpoint cannot expose `nativePassthrough`; source documents
   default-on unless false, so direct scalar inspection plus the exact pin is an
   explicit bounded invariant, never a claim that status proves it at runtime.

## Consequences

- Positive: the split-plane use case is available through one reviewed entry
  point, and the prohibited route is now *harder* than the permitted one rather
  than being the tool's default.
- Positive: the pin adds no second bootstrap prerequisite. The npm registry
  needs no credential for a public package, so this is the same class as the
  two npm pins already present — unlike the `github:` backend, which needed
  `github.slsa = false` and `github.github_attestations = false` to avoid
  making `GITHUB_TOKEN` a prerequisite.
- Negative: the integrity surface is version+backend only. The npm backend
  locks no tarball hash and no transitive dependency integrity, so this pin
  proves *which version and registry*, not *which bytes*. That is a real and
  stated weakening relative to the checksum-locked tools, accepted here on the
  same grounds as the existing npm pins: nothing in the gate graph consumes it.
- Negative: the enforcement is a fail-closed set of checks against the
  credential sources opencodex's own detector reads. It is not a sandbox. A
  determined operator can still run `ocx claude` directly and bypass the
  wrapper entirely; the wrapper makes the boundary explicit and refusable at
  the supported entry point, and it does not claim to be a security boundary
  against the same OS user.
- ~~Negative: the qualification canary stays open, so no claim about *which model
  actually served a gateway-routed request* is supportable yet.~~ **Closed
  2026-08-07 by `docs/research/2026-08-07-opencodex-qualification-canary.md`:
  verdict QUALIFIED WITH CONDITIONS** for the non-Anthropic split-plane route.
  Probes A, C, D, E, F plus streaming, concurrency, and effort probes were
  executed against this deployment; probe B stays closed as prohibited. A claim
  about which model served a request is now supportable **only** from the
  `ocx observe logs --jsonl` `resolvedModel` field correlated by `requestId` —
  the response body's `model` field echoes caller aliases and suppresses dated
  snapshots, so it is inadmissible. The canary also supersedes the gateway memo's
  "always `anthropic/`-prefix" contract item: unknown IDs in any form fall
  through to `default-provider` rather than throwing, so the enforceable rule is
  catalog membership in `GET /v1/models`, not a prefix convention. A healthy
  `status` remains a reachability observation and nothing more.
- Negative: supervision mutates shared Codex config as an upstream side effect
  (`~/.codex` is repointed at the proxy on ensure/start and restored on stop),
  so `launch` and `restart` are not side-effect-free for a Codex user. This is
  surfaced in the script header rather than worked around.
- **Original 2026-08-06 confirmation:** `mise install` resolved 2.10.2 with no credential in the
  environment; `ocx --version` printed `opencodex 2.10.2` through `mise exec`;
  `bash -n scripts/opencodex-claude.sh` parses; `mise run check` passes. The
  supervision ladder was exercised end-to-end on this host, no login required:
  `status` against a stopped gateway reports DOWN and exits 1; `restart` from
  DOWN started it and reported healthy; `status` then showed pid/port/uptime and
  exited 0; `restart` while running cycled the pid; two concurrent `launch`
  calls left the pid unchanged with exactly one listener bound (idempotent);
  a `launch` completed end-to-end and `ocx claude --version` printed
  `2.1.223 (Claude Code)`, writing roster agents only into the isolated dir.
  Fail-closed was proven, not assumed: with a foreign `python3 -m http.server`
  bound to port 10100, the identity-checked probe refused it, `launch` aborted
  with "did not become healthy within 15s" at exit 1, and Claude Code was **not**
  launched; after freeing the port the gateway recovered. A stale pidfile
  pointing at a live unrelated process was reported HALF-UP, then recovered by
  the single restart, and that unrelated process was left alive. Each credential
  refusal returned exit 3 against synthetic non-credential fixtures, and a
  refusal with the gateway stopped left it stopped.

## Reversal condition

Reopened by either direction of measured change: if the pin's usage narrows to
nothing (no non-Anthropic provider is actually routed through it for a full
release cycle) the pin should be dropped rather than carried as unused
surface; and if ADR-0003's own reversal condition is ever met — a dated change
in Anthropic's published gateway or legal-and-compliance documentation removing
the enforcement clause, or a written exception naming this bundle — the
launcher's refusals become obsolete and must be revisited deliberately in a new
record rather than quietly relaxed.

This record is evidence for a conductor to cite; it authorizes no provider
login, credential configuration, gateway-routed session, model-routing claim,
or other outward effect on its own.
