# ADR-0010 — A gateway-launched Claude Code session inherits inert session data and the statusLine stanza; settings.json is constructed key-by-key and never copied, because the global file carries a live credential

- **Status:** accepted
- **Note:** scoped to `scripts/muse-claude.sh` by ADR-0014. `scripts/opencodex-claude.sh` no longer
  has a plane to inherit into, and ADR-0014 changed nothing inside
  `assets/claude/session-inheritance.sh`. That file did change on 2026-08-18, for this record's own
  Amendment A: see Amendment A.1 below, which records the allow-by-name half being implemented and
  wired. It changed again on 2026-08-19 for Amendment A.2, which adds the closed unprefixed
  credential-NAME grammar to the deny half.
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Relates to:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md`
  (the credential boundary this record must not weaken — its refusals are unchanged),
  `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`
  (Decision item 3 and its Consequences described `CLAUDE_CONFIG_DIR` isolation as total;
  this record narrows that description to the credential-bearing half),
  `docs/adr/0007-muse-spark-direct-route.md`
  (the second launcher, which gets the identical treatment through the same helper),
  `assets/claude/session-inheritance.sh` (the shared mechanism),
  `scripts/opencodex-claude.sh`, `scripts/muse-claude.sh`,
  `tests/test_opencodex_claude.py`, `tests/test_muse_claude.py`

## Context

ADR-0005 gave the gateway-routed Claude Code process an isolated `CLAUDE_CONFIG_DIR` under
`XDG_STATE_HOME`, and ADR-0007 did the same for the Muse direct route. The reason was concrete
and still holds: `ocx` syncs its own roster agents and gateway model cache into the effective
config dir, so sharing `~/.claude` would mutate the operator's live session state, and the
ADR-0003 boundary requires that no subscription credential be reachable from the gateway plane.

That isolation was total, and totality had a cost the ADRs did not weigh. **A launched session
opened blank**: no prompt history, no project list, no `/resume` candidates, and no statusline.
The operator's own history and projects were sitting in `~/.claude` and were invisible to the
plane that was supposed to be a second view of the same work.

**The operator's decision, stated explicitly:** a gateway-launched session must inherit session
storage and statusline configuration from the global installation, and credentials must never
cross. They chose this over full isolation and over the simpler-sounding alternative of
inheriting all of `settings.json`.

Two findings on this host make the shape of that decision non-obvious, and both were verified
rather than assumed.

**Finding 1 — the global `settings.json` is a credential carrier.** Verified 2026-08-07: this
operator's `~/.claude/settings.json` `env` block holds a live `AWS_BEARER_TOKEN_BEDROCK`
alongside `CLAUDE_CODE_USE_BEDROCK`, `AWS_REGION`, and four `ANTHROPIC_DEFAULT_*_MODEL` pins. So
"inherit the settings file" and "never let a credential cross" are directly contradictory
instructions for that file. Copying or symlinking it would hand a live bearer token to the
gateway plane. Worse than the leak, it would also be self-defeating: both launchers scrub every
`ANTHROPIC*`/`CLAUDE*` variable out of the child environment precisely so the child cannot be
re-pointed, and a settings `env` block is applied by Claude Code itself *after* that scrub —
`CLAUDE_CODE_USE_BEDROCK` would route the gateway plane to Bedrock, and on the Muse route an
inherited `ANTHROPIC_BASE_URL` would send the process somewhere other than the endpoint its own
probe just verified.

**Finding 2 — the shared session stores are inert, and the sharing mechanism must survive
concurrent access.** `history.jsonl` and `projects/` are data Claude Code reads and appends;
they carry no auth, permission, or routing input. `shell-snapshots/` was checked specifically
because a captured shell environment *could* carry a credential: all 11 present on this host
hold functions and aliases only, with zero credential-shaped variable names and no occurrence of
`AWS_BEARER_TOKEN_BEDROCK`. But sharing one append-target between two live Claude Code processes
raises a corruption question that had to be answered before choosing symlinks over copies.

**The concurrency answer, verified against the installed CLI (2.1.224) rather than assumed.**
Claude Code writes prompt history under a `proper-lockfile` mutex: the save path calls it with
`{stale:1e4, retries:{retries:3,minTimeout:50}}` and reports `history_save_lock_failed`
separately from `history_save_write_failed`. The bundled `proper-lockfile` defaults
`realpath:!0`, and its resolver canonicalizes the target with `fs.realpath` **before** deriving
the lock path as `${resolved}.lock`. Therefore a plane opening a symlink and a plane opening the
real path resolve to the **same** lock directory and serialize against each other. Confirmed
empirically: an append through the symlink lands in the global file and leaves the link intact,
and a second acquirer of the same lock directory receives `EEXIST` (the loser retries; a lock
held past the 10s stale threshold is broken rather than deadlocking). `projects/` needed no
mutex argument — transcripts are per-session files under distinct session IDs, so two planes
never contend for one file.

## Considered options

1. **Keep full isolation.** Rejected: it is the status quo the operator asked to change, and
   the blank session was the whole complaint. It was never a *safety* requirement for the inert
   half — ADR-0003 constrains credentials, not prompt history.

2. **Copy the global `settings.json` into the isolated dir, then delete the `env` block.** A
   denylist. Rejected on two grounds. It leaks by default: any credential-shaped key upstream
   adds that a future edit did not predict (`apiKeyHelper` and `awsAuthRefresh` already exist
   and both name a credential-producing command) crosses until someone notices. And it would
   silently import unrelated global policy — `permissions`, `model`, `enabledPlugins` — into a
   plane whose whole point is different routing.

3. **Copy the shared session stores instead of linking them.** Rejected on the concurrency
   finding. A copy needs a merge-back to be useful, and there is no mutex for a merge-back: the
   plane would either diverge from the operator's real history or clobber it. Symlinks inherit
   the CLI's own realpath'd lock for free, which is strictly stronger than anything a launcher
   could add from outside.

4. **Inherit the statusLine by hardcoding this repo's packaged `assets/claude/statusline-command.sh`.**
   Rejected: the operator's statusline is their own choice, and pinning the packaged one would
   mean a global statusline change silently failed to appear in the launched plane.

5. **Selected: split the config dir by class.** Inert per-session data is shared by symlink; the
   isolated `settings.json` is constructed key-by-key from a one-key allowlist; everything
   credential-bearing stays private.

## Decision

1. **Inert per-session data is SHARED with the global install by symlink.** The shared set is
   `history.jsonl`, `projects/`, `todos/`, `shell-snapshots/`, `file-history/`. A missing global
   entry is not invented, and a global entry that is itself a symlink is not followed — it could
   point anywhere, including at a credential store, and the launcher must not launder that
   indirection.

2. **The isolated `settings.json` is CONSTRUCTED, never copied and never linked.** Exactly one
   stanza is inherited: `statusLine`. This is an allowlist, so an unpredicted credential-shaped
   key upstream is excluded by default rather than by having been enumerated. The `env` block is
   never inherited, and neither is `permissions`, `model`, or `enabledPlugins`.

3. **`AWS_BEARER_TOKEN_BEDROCK` in the global `env` block is the concrete, named reason for item
   2.** This is recorded as a finding about a real host, not a hypothetical: as long as any
   operator's `settings.json` can carry a live credential in `env`, that file is not copyable
   across this boundary. Reviewers changing item 2 must re-derive this finding, not assume it
   has expired.

4. **The constructed document is asserted credential-free before it is written.** The check is a
   post-condition on the built document — any `env`/`apiKeyHelper`/`awsAuthRefresh` key, any key
   containing token/secret/password/credential/bearer/apikey, and any `AWS_*` or `ANTHROPIC_*`
   key — and it refuses the write rather than sanitizing. Deliberately redundant with the
   allowlist: if a future edit admitted `env`, the write fails loudly instead of shipping the
   token. An unwritten `settings.json` costs a statusline; a written one that smuggled a
   credential is the failure this record exists to prevent.

5. **`statusLine` is inherited BY VALUE from whatever the global settings declare.** On this host
   that resolves to a `command` type naming an absolute script in the global config dir, which
   the launched session will therefore execute. **Accepted deliberately:** it is the operator's
   own script, already trusted by their own primary session, and it runs with strictly less in
   scope in the gateway plane than in the global one. A `statusLine` that is absent, malformed,
   or whose referenced command does not exist is **not a failure** — the launched session simply
   has no statusline, and the launch proceeds.

6. **The credential boundary is unchanged and re-proven.** Every `ANTHROPIC*`/`CLAUDE*` variable
   is still scrubbed, the ADR-0003 subscription refusal still fires with exit 3, and inheritance
   runs only *after* every credential assertion — so a refused or fail-closed launch links
   nothing and writes nothing. `.credentials.json`, the sibling `.claude.json` (which holds
   `oauthAccount` and `primaryApiKey`), `sessions/`, `session-env/`, `plugins/`, `agents/`,
   `statsig/`, and `cache/` all stay private.

7. **Inheritance is fail-soft and never destructive.** It is a convenience, never a gate: any
   entry that cannot be linked is skipped with a named reason and the launch continues. No
   existing plane data is ever deleted or overwritten to make room for a link — an isolated
   entry that already holds real data (the `ocx` plane held 102 MB of `projects/` on this host)
   keeps its data and stays private. Only a link the helper itself created is re-pointed.

8. **One mechanism serves both launchers.** `assets/claude/session-inheritance.sh` is sourced by
   `scripts/opencodex-claude.sh` and `scripts/muse-claude.sh`, so what crosses the boundary is
   defined once. It is sourced lazily inside each launch path, so `status`, `restart`,
   `configure`, and `probe` never link anything.

9. **`operator-tools:status` now distinguishes `absent` from `unmanaged`.** A file that was never
   installed is reported `absent` with the install command named; `unmanaged` is reserved for a
   file that exists but is not owned. Both still exit 1. The previous wording reported a missing
   file as `unmanaged`, which sent an operator looking for a conflict that did not exist.

## Consequences

The operator's launched session now shows their real prompt history and project list, and
carries their statusline. A prompt typed in the gateway plane appears in the global history,
because there is one file and one lock rather than two diverging copies.

The description of `CLAUDE_CONFIG_DIR` isolation in ADR-0005 (Decision item 3, Consequences) and
ADR-0007 is now **narrower than it reads**: isolation covers the credential-bearing and
plane-owned half, not the whole dir. Those records are not superseded — their credential
conclusions are unchanged — but a reader who cites "the config dir is isolated" as evidence that
no data is shared would be citing them wrongly. Both launcher headers, the launch output, and
the README have been corrected to say which half is which, because an isolation claim that is
half true is worse than one that is explicit about its boundary.

The statusline command inherited by value executes in the gateway plane. That is a real
consequence, not a hidden one: a global statusline script that assumes the primary session's
environment may render differently or degrade there, and the launcher does not repair it.

A new store that Claude Code adds under the config dir lands **outside** the allowlist and stays
unshared until someone reviews it. That is the intended default and will occasionally look like
a missing feature rather than a decision.

This record makes no claim that every future session store is concurrency-safe. The claim is
narrow and evidence-backed: history is append-under-a-realpath'd-lock, and project transcripts
are per-session files. A future store with different write semantics needs its own analysis
before it joins the shared set.

## Amendment — 2026-08-07: the environment-variable policy, one `ccodex` dispatcher, and the reuse of that name

Three operator decisions landed after the record above was accepted. Each is adjacent to it and
none changes the credential conclusion.

### A. The environment scrub was wrong in both directions, and is now an explicit policy

**The defect, found by running the launcher rather than by reading it.** Both launchers scrubbed
`^(ANTHROPIC|CLAUDE)` by prefix. Under a planted parent environment, `AWS_BEARER_TOKEN_BEDROCK`
exported in the operator's shell **reached the child process intact** — a live Bedrock credential
in the gateway plane, which is exactly what Decision item 6 above claims cannot happen. The
settings.json allowlist did not save it, because Claude Code resolves **shell environment above
settings `env`**, so closing one path and not the other left the boundary open. The same prefix
rule was simultaneously too coarse: it deleted `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and would
delete the operator's inert preferences, discarding deliberate choices.

**The design tension, and how it resolves.** A prefix rule broad enough to catch every model pin
(about twenty names across `ANTHROPIC_DEFAULT_*_MODEL`, its `_NAME`/`_DESCRIPTION`/
`_SUPPORTED_CAPABILITIES` variants, and `ANTHROPIC_CUSTOM_MODEL_OPTION*`) would also swallow inert
`CLAUDE_*` preferences. The two namespaces get **opposite rules**, because their contents differ:

- `ANTHROPIC_*` and `AWS_*` — **denied by prefix**, no exceptions. Every documented variable there
  is a credential, a destination, an identifier, or a model pin; none is an inert preference, so a
  prefix rule loses nothing and a new upstream name fails closed rather than needing prediction.
- `CLAUDE_*` — **denied by default, allowed by name**. This namespace genuinely mixes routing and
  auth flags (`CLAUDE_CODE_USE_BEDROCK`, the client-certificate trio) with inert preferences
  (accessibility, compaction, bash limits). Only an enumeration is honest, so an unrecognized new
  `CLAUDE_*` variable is dropped rather than guessed at.
- unprefixed — **denied by name**: `NODE_TLS_REJECT_UNAUTHORIZED` (a TLS downgrade),
  `FALLBACK_FOR_ALL_PRIMARY_MODELS` (silent substitution against a restricted catalog, the
  canary's C1 hazard), and `API_TIMEOUT_MS` (inert, but a value tuned for a direct endpoint is the
  wrong number for a loopback gateway, and a wrong timeout reads as a hung model).

**Privacy flags are preserved explicitly, not incidentally.** `DISABLE_TELEMETRY`,
`DISABLE_ERROR_REPORTING`, `DO_NOT_TRACK`, and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` are
**set-to-activate**: any non-empty value enables them, unset disables. So dropping a *set*
`DISABLE_TELEMETRY` re-enables telemetry in the launched plane — a privacy regression the operator
never asked for. Preservation is implemented as capture-then-restore around the scrub rather than
left to a prefix rule's mercy.

**Routing variables are denied and then set fresh.** `ANTHROPIC_BASE_URL` is not merely scrubbed:
`ocx claude` sets it to the loopback proxy afterwards, with "user wins" semantics
(`src/cli/claude.ts` line 93). The same file sets `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`
and, when it owns an auth token, `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` — which makes Claude Code
strip provider-managed variables from settings-sourced env. This bundle therefore does **not** set
those three itself; inheriting a stale value would override the gateway's own choice.
`CLAUDE_CODE_REMOTE`, `CLAUDE_CODE_ACCOUNT_UUID`, and `CLAUDE_CODE_MESSAGING_SOCKET` are neither
inherited nor set, because Claude Code owns them and ignores them from an env block.

A bug worth recording because it was self-inflicted and silent: the policy lists are themselves
`CLAUDE_*`-named, so the prefix scrub unset the very lists it was iterating, aborting the launch
under `set -u`. They are copied to locals first. The same lists are excluded from the status
report, since reporting launcher state as "a denied variable you set" would be a false statement
about the operator's shell.

### A.1 The allow half was prose for eleven days; implemented 2026-08-18

**What was actually shipped in A, and what was not.** The deny half landed in code: both launchers
swept `ANTHROPIC_*`/`CLAUDE_*`/`AWS_*` by prefix and the three unprefixed hazards by name. The
`CLAUDE_*` **allow-by-name** half did not. The enumeration and the capture-then-restore existed in
`assets/claude/session-inheritance.sh` with **zero callers** — `scrub_and_restore_claude_env`,
`CLAUDE_INHERITED_ENV_VARS`, `CLAUDE_DENIED_ENV_VARS`, and `report_env_policy` were all orphans —
while `scripts/muse-claude.sh` ran a private prefix scrub that dropped every `CLAUDE_*` variable.
So the concrete regression this amendment names, a set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`
being swept and thereby **re-enabling** nonessential traffic under set-to-activate semantics, was
live for eleven days. Prose is not policy; only a called function is.

**Now one shared helper, one enumeration, one caller.** `scrub_and_restore_claude_env` is the
launcher's only scrub, `scripts/muse-claude.sh` calls it in place of its deleted private copy, and
`report_env_policy` is wired into that launcher's `status` route — the one place that can answer
"will the flag I set survive a launch?" without launching. The list stays in the shared asset rather
than moving into its single consumer, so a future plane inherits the reviewed boundary. **The ocx
launcher is deliberately NOT a second caller:** ADR-0014 deleted its plane and its scrub, because
that route's whole premise is presenting the operator's own environment and login. Item 8's "one
mechanism serves both launchers" therefore now reads as *one mechanism serves any plane that
prepares a child*, and there is exactly one today.

**Two failures were found by wiring it, both invisible while it was dead code.** First, the
capture-then-restore round-tripped values as `name=value` LINES, so a value the operator controls
could inject a second name: `CLAUDE_CODE_ACCESSIBILITY=$'1\nAWS_BEARER_TOKEN_BEDROCK=<token>'`
exported a Bedrock bearer token into the child and truncated the real preference to `1` — the exact
boundary failure this amendment exists to close, arriving through the half meant to preserve inert
preferences. Both lists are now bash arrays and the restore uses parallel name/value arrays, so a
restored name can only come from the literal enumeration, and a value is never re-parsed. (Arrays
cannot be exported, so the policy state is now also structurally incapable of reaching the child.)
Second, a missing or empty list would have failed silently in opposite directions — an empty
denylist scrubs nothing, an empty allowlist drops the privacy flags — so both are refused by name
instead of defaulted.

**The list checks itself, because allow-by-name fails by allowing too much.**
`assert_env_allowlist_is_admissible` runs on every scrub and refuses the launch, before anything is
unset, for an entry that is not an exact upper-case name (which is what forbids a prefix or glob
from ever becoming an allow rule), is not `CLAUDE_*`, or is credential-, destination-, model-pin-,
or plane-selector-shaped. `CLAUDE_CONFIG_DIR` is refused rather than merely absent, since a restored
value would point the child at `~/.claude`. Every entry now carries its own in-code reason, and the
admission test is about the NAME's whole value space, never about the value an operator happens to
have set. Ordering at the call site is unchanged and load-bearing: the subscription refusal reads
`ANTHROPIC_*` and so still precedes the scrub, which the `CLAUDE_*`-only allow half cannot weaken;
the route slots are exported after the restore, so no preserved preference can shadow them.

### A.2 The unprefixed half was three names; it is now three names plus a closed credential grammar (2026-08-19)

**The defect, measured against HEAD rather than argued.** The deny half of A closed
`ANTHROPIC_*`/`CLAUDE_*`/`AWS_*` by prefix and exactly three unprefixed hazards by name, so an
unprefixed **credential** was never swept. Reproduced by the Fable-lane credential-boundary review
of agentic-sdlc-71f4 and again against HEAD, so it is pre-existing rather than a regression: an
exported `MODEL_API_KEY` **reached the child verbatim**, alongside the `ANTHROPIC_AUTH_TOKEN`
carrying the same value that the prefix sweep did remove. The boundary was closed for the namespaced
spelling of a secret and open for the unnamespaced one. `MODEL_API_KEY` is not a hypothetical name
here — it is `scripts/muse-claude.sh`'s own documented credential input.

**The decision: the unprefixed class gains a credential-NAME grammar, and stays a name policy.**
`assets/claude/session-inheritance.sh` denies any variable whose whole final word is one of ten
endings — `API_KEY`, `APIKEY`, `AUTH_TOKEN`, `ACCESS_TOKEN`, `TOKEN`, `SECRET`, `SECRET_KEY`,
`PASSWORD`, `CREDENTIALS`, `PRIVATE_KEY` — matched as `(^|_)WORD$`, so `MODEL_API_KEY`,
`MODEL_APIKEY`, a bare `API_KEY`, `GITHUB_TOKEN`, and `CI_JOB_TOKEN` all go while
`MODEL_API_TIMEOUT`, `MODEL_API_KEYS`, `MONKEY`, and `TOKENIZER_PARALLELISM` all stay. `TOKEN` was
added after `GITHUB_TOKEN` and `CI_JOB_TOKEN` were found reaching the child verbatim under the
original nine-ending grammar: neither name ends in `AUTH_TOKEN` or `ACCESS_TOKEN`, so the bare-word
ending was missing. A name that merely *contains* a credential word is deliberately not swept:
`*KEY*`-style containment is how a deny grammar starts eating the operator's inert preferences,
which is the failure the whole of A exists to prevent.

**Why this is not the value scanner A ruled out.** A's constraint is unchanged and this amendment
does not relax it: no value is read, scanned, matched, or classified anywhere in the policy. Value
inspection is the wrong instrument in both directions — it misses a low-entropy secret and deletes a
high-entropy preference — so what is denied is a NAME whose final word declares that its value space
is a credential. The grammar is **closed** (an enumerated word list, not a heuristic) and
self-checking: `credential_shaped_env_name_ere` refuses a glob, an alternation, a digit, or a
leading/trailing underscore rather than expanding it, so the deny list cannot quietly widen into a
pattern rule any more than the allow list can quietly widen into a prefix rule. A missing or empty
grammar refuses the launch by name, before anything is unset, exactly as an empty allow or deny list
already does.

**The two halves are structurally incapable of disagreeing, and that is tested.** Every one of the
ten endings is already refused from the allowlist by `assert_env_allowlist_is_admissible`'s
credential-shape patterns, so no *admissible* allowlist entry can match the grammar and the sweep
needs no exception for an allowed name. Capture-then-restore is independent belt: it captures before
every sweep and restores after, so an allowlisted preference survives regardless.
`tests/test_muse_claude.py` proves both halves per ending, reading the word list from the shipped
array rather than re-typing it, so narrowing the shipped grammar fails the gate.

**One grammar, two consumers.** The sweep and the `status` classification read the same ERE. A second
hand-maintained copy of the word list is how a status route ends up promising that a variable
survives a scrub that removes it, so `report_env_policy` now classifies the unprefixed credential
class from that ERE, reports a name that satisfies both a prefix rule and the grammar exactly once,
and continues to print no value. The grammar list is itself `CLAUDE_*`-named, so — like the two lists
before it — it is resolved into a local before the prefix sweep can unset it, and excluded from the
report as launcher state rather than operator environment.

**Sweeping this launcher's own credential input is safe because of ordering, not luck.**
`resolve_credential` copies `MODEL_API_KEY` into a shell variable *before* `prepare_child_environment`
runs, and the route's `ANTHROPIC_AUTH_TOKEN` slot is exported *after* the scrub. That ordering was
already load-bearing for the subscription refusal; it now carries this too.

**What this does not close, recorded rather than solved.** A secret an operator stores under a name
the grammar does not describe — `MY_THING`, `DEPLOY_PW`, or any allowlisted preference — still crosses
as that variable's value. A name policy cannot see it. The same review recorded that limit, and this
amendment narrows the gap rather than closing it.

### B. One `ccodex` dispatcher, not N commands, and the clone is required

The operator wants to use the installed system without mise. There are 36 mise tasks; most are
repository maintenance (`test`, `validate`, `check`, `secrets`, `self-test`, `mermaid:*`,
`hooks:install`) and belong to working *on* this repo, not to using what it installed. Shipping
them on an operator's PATH would present a maintenance surface as a product surface.

**Decision: one owned dispatcher, `ccodex <domain> <verb>`,** covering ensure/launch/ultracode/
status/restart/configure, providers, models, bundle, libraries, and statusline. Plain `claude` is
the native Anthropic-routed CLI; `ccodex launch` is the explicit separate non-Anthropic gateway
route. A bare `ccodex launch` and `ccodex status` are the shorthand for the common case; `ccodex
ocx launch` is accepted as the explicit long form, because that is what a reader guesses and
silently failing a reasonable guess is worse than accepting both spellings.

**Amendment (2026-08-10): stop installing historical alias files.** Fresh operator-tools installs
own only `ccodex` and the packaged statusline support command. `ocx-launch` and `ocx-ultracode`
remain recognized names in legacy/current ownership state and in pending install, refresh, or
unlink transitions, so shrinking the desired set does not invalidate or strand an old lifecycle.
They are not required and are never reported absent. `operator-tools:retire-aliases` explicitly
unlinks only an unchanged removable owned copy using the existing crash-consistent uninstall
transition. A changed, foreign, or adopted alias is preserved and reported. Full uninstall still
handles an unchanged owned alias. `ocx:*` mise tasks and `ccodex ocx <verb>` remain compatibility
surfaces; only the redundant PATH entries retire.

The alternative, a dozen named commands, loses on exactly the cost the dispatcher avoids: every
added verb becomes a new PATH entry, a new ownership record, and a new collision risk against a
name the operator may already use.

**`ccodex models` reads the LIVE catalog, not the configured list.** These disagree, and the
disagreement is the point: verified 2026-08-07, `ocx models list` showed a single muse entry while
the running gateway served ten ids. Only the live catalog answers "what can a launched session
pick," so a configured-only view would be a confidently wrong answer.

**The repository clone is required, and this is reported rather than solved here.** Every route
executes code inside the checkout; `ccodex` is a thin owned entry point, not a self-contained copy.
A moved or deleted clone makes each route fail with a named error rather than misbehave. To let a
clone-free bootstrap meet this work halfway, the root is resolved **at run time** —
`AGENTIC_SDLC_ROOT` overrides an install-time default — so a managed clone at a stable path can be
pointed at without reinstalling the command. `mise` is required for the `ocx` routes only (`ocx` is
not on PATH by itself); `uv` is required for the Python routes and works from a bare PATH
(verified).

**`operator-tools:status` now distinguishes `absent` from `unmanaged`.** A never-installed command
reports `absent` with the install command named; `unmanaged` is reserved for a file that exists but
is not owned. Both still exit nonzero. On this host all three were reported `unmanaged` while no
state file existed at all, which sent the operator hunting for a conflict that did not exist.

### C. The `ccodex` name is reused deliberately

`ccodex` previously named a CLIProxyAPI-era launcher whose premise — Claude subscription
passthrough — ADR-0003 declared ToS-blocked. **Only the name is reused; that design is not
adopted, revived, or endorsed.** The reuse is safe because the retired system is gone: its state
(`~/.local/state/claude-code-proxy`, dead since 2026-07-22) and cache (`~/.cache/ccodex`) were
swept before this change, and no `ccodex` binary exists anywhere on the host — not on PATH, not as
an npm global (verified). Real Codex (`~/.local/bin/codex`, `~/.codex`) and the opencodex config
(`~/.opencodex`) are untouched and unrelated.

Any state this dispatcher introduces lives under the bundle's own root
(`$XDG_STATE_HOME/agentic-sdlc/...`), never at the retired paths, so a future reader cannot confuse
the two systems by their footprints. `docs/research/2026-07-22-claude-code-multi-model-routing.md`
records the old design; a pointer there now names this reuse so the retired premise and the shipped
command cannot be conflated.

**Reversal condition for the name:** if a third-party `ccodex` becomes widely established, or if
any part of the retired subscription-passthrough design is ever proposed for revival, the name is
reopened — the second case would additionally require ADR-0003's own reversal condition to be met
first, and a new record rather than an amendment here.

## Amendment — 2026-08-07: help is not a side-effecting operation, and inheritance is opt-in-migratable rather than silently skipped

Two defects in the shipped surface, both **reproduced against the installed command** rather than
read out of the source. Neither changes the credential conclusion; both change what the operator
is told and what a help request is allowed to do.

### D. A help request must not prepare a plane

**The defect.** `ccodex launch --help` ran the *entire* launch preparation before handing `--help`
to Claude Code: it mounted session inheritance, constructed `settings.json` inside the isolated
dir, and against a healthy gateway would have ensured the gateway and launched. Top-level `help`,
`-h`, and `--help` were already correct; the verb level was not. `ccodex ocx --help` was worse in
a smaller way — it errored with `unknown ccodex ocx verb: --help` and exited 2, answering a
reasonable spelling of a question with a failure.

**Why it survived a verification pass, which is the more useful half of this record.** The check
that cleared it compared exit codes with output discarded. Against a launch path that ends in a
`claude` process which exits 0, `exit=0` cannot distinguish *printed usage* from *launched Claude
Code, which then exited cleanly*. **An exit code is not an observation of behavior when the
success and failure paths share it.** Every assertion added here reads stdout, and the
side-effect assertions are negative and specific: the string `preparing gateway-routed Claude
Code` must be absent, and the isolated config dir must not exist afterwards.

**The semantic, chosen deliberately.** A bare `-h`/`--help` in the **first** position after a verb
means "explain this command". It does not mean "prepare a gateway plane, mount session state, and
then ask Claude Code for its help text" — nobody types the second thing, and a help request that
writes into a config dir is a defect no matter how good the text it eventually prints. So the
first-position form is intercepted, prints the wrapper's own per-verb help, and exits 0 having
touched nothing.

**Pass-through remains possible, because a wrapper that can never forward an argument is its own
defect.** `--` ends the wrapper's options in the ordinary POSIX sense: `ccodex launch -- --help`
prepares a real session and forwards `--help` verbatim (verified: the child receives exactly
`--help`; under `ultracode` it receives `--settings {"ultracode":true} --help`). Only the first
argument is inspected, so `launch --model x --help` still forwards — a heuristic that tried to
guess which later `--help` was "really" for Claude Code would have to tell a flag from a flag's
value, and guessing wrong either swallows an operator's argument or launches when they asked a
question. The intercepted help text names both escapes (`-- --help`, and `claude --help` inside a
session), because an interception that does not say how to forward is a silent capability removal.

One exception, and it is not cosmetic: under `configure`, the bare word `help` is **not**
intercepted. `ocx help <verb>` is the documented way to inspect the upstream surface and is
already an admitted read-only route; swallowing it would remove the only route that answers "what
can upstream actually do". The flag spellings are still intercepted there.

### E. Silently never inheriting is not the feature the operator asked for

**The defect.** Decision item 7 above — never delete or overwrite plane data to make room for a
link — was implemented correctly and reported dishonestly. Every entry that already existed was
skipped with `not shared (isolated copy already has its own data)`, which reads as a benign note
about an implementation detail. On the operator's own host, verified 2026-08-07, **every entry in
the shared set already held real data from launches predating this feature** (`history.jsonl`,
`projects/`, `shell-snapshots/`, `file-history/`, all dated earlier), so inheritance was a
**permanent no-op** and the transcript never said so. Measured after the fix on that same host:
`0 of 4 inheritable entries shared`.

**The tension, stated rather than resolved by preference.** Refusing to clobber the operator's
data is right. Silently never delivering the feature they asked for is also wrong. Both horns are
real, so the resolution splits them by *who decides*:

- **A launch still refuses, and now says so unmistakably.** The per-entry line reads `NOT
  INHERITED -- this plane has its own pre-existing data`, followed by a summary that names the
  count, states that the state is permanent until migrated, and prints the exact remedy commands.
  The old wording is removed, not supplemented.
- **The remedy is a separate operation the operator names,** `ccodex session <status|adopt>`.
  `status` is read-only and classifies every entry (shared / not-inherited / linked-elsewhere /
  absent / nothing-to-inherit / refused-because-the-global-entry-is-a-link). `adopt` **prints a
  plan and moves nothing**; `adopt --migrate` performs exactly that plan.
- **Nothing is ever deleted.** A blocking plane copy is `mv`d into
  `<plane>/pre-inheritance-backup-<UTC stamp>/` and only then linked. The move is checked before
  the link, because a link created after a failed move would point the plane at the global copy
  while its own data still sat in the way — the one intermediate state that could look like a
  successful migration and be a loss. An unwanted migration is undone by moving the entry back,
  which is why no `--force` exists.
- **A missing global source is a refusal (exit 3), not a skip.** Moving the plane's only copy
  aside when there is nothing to link to would hide the operator's data to deliver nothing.
- **`status` surfaces `session inheritance: N of M inheritable entries shared`.** A plane whose
  inheritance never took effect is indistinguishable from one where it did until someone notices
  their history is missing, so the count belongs in the ordinary status view rather than behind a
  special command. Both session routes work with the gateway down and without `mise`: "why is my
  history missing" must be answerable exactly when the gateway is not.

**The consequence is stated rather than discovered.** After a migration the launched session shows
the **global** history and projects, so the plane's own past prompts stop appearing in it. They
are on disk in the printed backup path. Item 7's guarantee is unchanged for launches — no launch
moves anything — and this record does **not** authorize migrating any operator's data; the
migration is an operation they run.

**The credential boundary was re-proven by execution, not by reading.** The constructed
`settings.json` was built through the real launch path in a throwaway `HOME` whose global
`settings.json` carried a planted `AWS_BEARER_TOKEN_BEDROCK` next to a `statusLine` stanza. The
result contains the `statusLine` (inherited by value, `padding` included) and none of:
the planted value, `AWS_BEARER_TOKEN_BEDROCK`, `env`, `apiKeyHelper`, `AWS_REGION`,
`CLAUDE_CODE_USE_BEDROCK`, the global `model`, or `permissions`. It is a regular file at mode 600,
neither a link nor a copy of the source.

## Reversal condition

Reopen this record if any of the following becomes true.

An operator wants the *plane's* history to win a migration rather than the global one. The
migration is deliberately one-directional (plane data aside, global linked in) because a merge of
two append-only histories has no defined order; a two-way merge would need its own record.

Claude Code stops locking history appends, changes `proper-lockfile`'s `realpath` default, or
begins passing `lockfilePath` explicitly — any of these breaks the shared-lock property that
made symlinks safe, and the shared set would have to shrink to `projects/` or be re-derived.

Claude Code begins rewriting `history.jsonl` in place (truncate-and-write rather than append),
which no lock shared between two planes makes safe for concurrent readers.

`settings.json` gains a key that must be inherited for the launched session to be usable and
that cannot be admitted without carrying a credential. The allowlist would then need a real
decision rather than an extension.

An operator's global `settings.json` stops being able to carry a credential in `env` — for
instance if Claude Code moved `env` to a separate non-credential file. Item 2's *reason* would
change, though the allowlist would likely still be the right default.

The shared session stores stop being inert: if `shell-snapshots/` or `file-history/` begin
capturing environment variables, they leave the shared set immediately and this record is
amended rather than reinterpreted.

If ADR-0003's own reversal condition is met, that record — not this one — governs the credential
boundary, and this record's item 6 must be revisited deliberately in a new record rather than
quietly relaxed.

This record is evidence for a conductor to cite; it authorizes no launch, credential
configuration, install, push, publication, merge, deployment, or other outward effect on its own.
