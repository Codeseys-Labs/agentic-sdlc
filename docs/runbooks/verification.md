# Operator verification runbook

This is a living runbook, not a one-time report. It generalizes the executed evidence in
`docs/progress/2026-08-20-fresh-env-and-routing-verification.md` into repeatable steps any
operator can run again. Point-in-time counts, wall times, and version strings belong to that
progress record and to whichever seeds it opened (`agentic-sdlc-927e`, `agentic-sdlc-b3aa`,
`agentic-sdlc-1565`, `agentic-sdlc-41cb`); this document cites them rather than restating them,
because a number copied here would go stale the next time the bundle, the upstream libraries, or
the toolchain pins change. Where a command below is shown with its actual captured output, that
output is an **example transcript**, labeled with the host it came from, not a promise that the
exact integers repeat. The guarantee is the *shape* of the line — the tool's own contract — not
the digits in it.

Four variants are covered: a fresh, credential-free install; a Bedrock-configured Claude Code
without `ccodex`; the `ccodex` gateway plane; and the external skill-library front doors. A
caveats section closes the runbook.

## 1. Fresh-environment install

This is the sequence AGENTS.md's "Installing this bundle" section documents, run start to finish
on a machine that has never seen this checkout. Each step's success shape is the line the tool
itself guarantees — never a count, version, or wall time pulled from a specific run.

1. **Clone** the repository. Nothing to verify yet beyond `git status` reporting a clean,
   non-dirty tree at the commit you intend to install from.
2. **Review `mise.toml` and `mise.lock`** by reading them. This is a human review step; there is
   no tool-guaranteed success line, because the point is that a person looked.
3. **`mise trust ./mise.toml`** for that exact reviewed path, after explicit operator approval.
   Success shape: the command exits 0 and prints that the config is now trusted. Every later
   `mise` invocation in this tree fails closed with `Config files in <path> are not trusted`
   until this step has run for that path — a linked worktree needs its own trust, not the
   parent's.
4. **`mise --locked install`**. Success shape: the pinned toolchain resolves and the command
   exits 0. AGENTS.md records this as roughly 1.3 GB across twelve pinned tools; that figure and
   any wall time are point-in-time and belong to the progress record, not to a repeatable
   assertion here.
5. **`mise run lifecycle:install -- --agent claude`** and/or **`-- --agent codex`**. Each plane
   installs independently; a Claude marketplace overlap blocks only the Claude plane, so a
   selected Codex plane still proceeds. `--dry-run` and `--help` are read-only and safe to run
   first.
6. **`mise run lifecycle:status`**. This task's guaranteed terminal line is always one of exactly
   two shapes: `no owned entries for this host`, or `N ok, M conflict, K absent` (a silent exit 0
   with neither line is a defect in the tool, not a clean host). Example captured today in the
   `asdlc-fresh` container, after both planes were installed — a snapshot, not a standing count:

   ```
   ok: /home/dev/.codex/skills/reviewing-overengineering
   ok: /home/dev/.codex/skills/stacked-prs
   ok: /home/dev/.codex/skills/stacked-prs-gh-cli
   43 ok, 0 conflict, 0 absent
   ```

7. **`mise run claude:statusline:status`**. The statusline is a bundle ledger row, so step 6
   already published it; this step reads whether it is wired into settings. It prints one of five
   distinguishable states — `active`, `inactive`, `unmanaged`, `conflict`, or a pending recovery —
   in the MESSAGE and not in the exit code, so read the line rather than the status.

   The step this replaced ran `mise run operator-tools:install` then `operator-tools:status`, and
   both tasks are deleted along with the PATH plane they managed (gh #10 phase 4). There is no
   longer a step that puts a second `ccodex` on `PATH`: `bin/ccodex` is committed and self-locating.
   If a host being verified was set up under an earlier release, README's retirement section has
   the manual removal, and `ccodex sdlc doctor` names the leftover store.

8. **`./scripts/install-skill-bundle.sh self-test`**. Success shape: the process exits 0 and the
   last line is literally `self-test passed`. Observed verbatim in `asdlc-fresh` today.
9. **`mise run validate`**. Success shape: exit 0 with a line of the form
   `validate-bundle: 0 error(s), 0 warning(s)`. A nonzero error count exits 1; warnings exit 0 —
   the gate does not fail on them, so treat a nonzero warning count as a stop yourself rather
   than a note to move past. Observed verbatim in `asdlc-fresh` today:

   ```
   validate-bundle: 0 error(s), 0 warning(s)
   ```

Customization boundary: a hand-written operator skill placed beside the installed plane stays a
plain, unowned file — the installer never adopts, overwrites, or reports it as owned. This was
verified by execution in the progress record's Lane 1 and is not re-verified here.

## 2. Bedrock-configured Claude Code without `ccodex`

This variant never touches `ccodex` or the gateway. It answers a narrower question: does a
Claude Code installation that is already routed to Amazon Bedrock still see this bundle's
installed skills, once the same install sequence from Section 1 has run against it.

**Environment prerequisites, by name** (all three must be present; none of them are optional
defaults). Check for them by name only — never `env | grep AWS`, which would print the token:

```
env | grep -oE '^(CLAUDE_CODE_USE_BEDROCK|AWS_REGION|AWS_BEARER_TOKEN_BEDROCK)='
```


- `CLAUDE_CODE_USE_BEDROCK` — set truthy to switch Claude Code's provider routing to Bedrock.
- `AWS_BEARER_TOKEN_BEDROCK` (or, alternatively, a configured AWS credential profile) — the
  credential Bedrock authenticates the call with.
- `AWS_REGION` — the Bedrock region the calls are billed and routed against.

Confirmed present by name in the `asdlc-bedrock` container today (values not reproduced here):
`AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `CLAUDE_CODE_USE_BEDROCK`.

**Smoke probe.** Run `claude --version` first — a plain version string confirms the binary
launches at all before spending a model call. Then send one short non-interactive prompt to
confirm the routed call itself answers. The progress record's Lane 3 recorded this smoke ping
answering through `us.anthropic.claude-haiku-4-5-20251001-v1:0`; that exact model id is a
point-in-time fact of that run's Bedrock model-mapping configuration, cited rather than assumed
to repeat.

**The honest verification pattern: ask for a skill listing, never a file-path confirmation.**
Do not verify a Bedrock-routed session by asking `claude -p` to confirm a file exists at some
path, or to describe "this repository" from an arbitrary invocation directory — a non-interactive
`-p` session answers from training-data convention in that case, not from disk, because the
session sandbox scopes to the invocation's current working directory and a generic prompt gives
it no reason to actually look. Instead, `cd` into the installed checkout and ask the session to
enumerate the skills available to it by name. A correct answer requires the session to have
actually resolved its own installed-skill surface, which a convention-shaped guess cannot fake.

Run today against `asdlc-bedrock` (`cd ~/agentic-sdlc && claude -p "List the names of every skill
available to you in this session, one per line, nothing else."`): the response enumerated this
bundle's installed skills (`agentic-sdlc`, `model-tier-rightsizing`, `dispatching-exact-ocx-models`,
`reviewing-overengineering`, and the rest of the twelve this bundle installs), this repository's
five `sdlc-*` slash commands, and a handful of the container's other pre-existing global skills —
proving the routed session resolved the real, installed surface rather than reciting a generic
answer. The exact roster is this session's snapshot; re-run the same probe rather than trusting
this transcript on a different host or after any bundle change.

## 3. `ccodex` gateway plane

This variant is the operator-facing gateway wrapper (`ccodex`, ADR-0014) — no isolated plane, no
private `~/.codex`, using the operator's own `~/.claude` login for the native half.

**`ccodex status`'s provider table and its honesty lines.** `status` prints gateway supervision
state, the configured-provider table, a configured-vs-live comparison, and a route-reachability
line that is `ok`, `BYPASSED` (something in the environment or settings would route around the
gateway even if it were up), `MISROUTED` (a model slot exported in this shell — `ANTHROPIC_MODEL`,
an `ANTHROPIC_DEFAULT_*_MODEL` tier slot, or `ANTHROPIC_SMALL_FAST_MODEL` — holds a
cloud-provider-shaped id, so that family would be served by the DEFAULT provider instead of
Anthropic), `MISBILLED` (an `sk-ant-api*` Console key would take the native branch but bill API
credits), or `UNKNOWN` (a settings document it could not read); the separate
supervision line above it is `healthy`, `HALF-UP`, or `DOWN`. `status` never asserts liveness it
cannot verify — a `DOWN` gateway is reported as down, not guessed at. Captured live on the operator host today, with `CLAUDE_CODE_USE_BEDROCK` exported in
this shell:

```
== gateway supervision ==
  state   : healthy
  ...
== configured vs LIVE catalog ==
  ok      : every configured provider is served by the running gateway

== gateway route reachability ==
  BYPASSED: CLAUDE_CODE_USE_BEDROCK is exported; a launch would reach a cloud provider, not this gateway
```

**The expected exit-3 refusal on a provider-routing host is a positive control, not a bug.** A
host that exports a provider-routing variable like `CLAUDE_CODE_USE_BEDROCK` should see
`ccodex launch` *refuse* rather than silently proceed — a launch that "succeeded" here would
actually prove nothing, because Claude Code would have bypassed the gateway entirely. Run today on
this same operator host, in the background so a refusal can't be mistaken for a hang:

```
$ ccodex launch --version   # backgrounded; process exited 3
REFUSED: CLAUDE_CODE_USE_BEDROCK is exported and in force, which routes Claude Code to a cloud
provider and bypasses the gateway entirely; unset it -- a switch whose value is 0, false, or
empty already counts as off -- or set it per command in front of a plain `claude` run for that
route
```

Treat that exit-3 refusal, on a host where a provider-routing variable is genuinely exported, as
the control confirming the refusal logic is live — the same way a null-hypothesis test confirms
an experiment can detect a real effect. A clean environment (no `CLAUDE_CODE_USE_BEDROCK`-class
variable, no `apiKeyHelper`, no `sk-ant-api*` Console key, no blocking `--settings` value) is the
condition under which `launch` proceeds to ensure the gateway and then hand off to Claude Code
under the operator's own login; the progress record's Lane 4 recorded exactly that clean-launch
path serving the native ping end to end, which this runbook cites rather than re-executes, since
a live launch starts an interactive Claude Code session.

**Routed-serve verification, and the observe-log rolling-window caveat.** `status` itself prints
the exact observe-log invocation as its own "attribution log stream" line:

```
mise -C <repo> exec -- ocx observe logs --follow --jsonl
```

Use this to confirm which provider actually served a routed request — a friendly model id, a
cache id, and the gateway's own normalized id can all reach the same provider, and the gateway
strips the `claude-ocx-<provider>--` prefix and any `[1m]` marker before matching. The
progress record's Lane 4, and seed `agentic-sdlc-1565`, record the corrected, receipt-verified
result: routed selection worked end to end, with `status=200` receipts naming the real upstream
provider. **One empty or inconclusive query against the observe log is unknown, not a negative
result.** The log is a bounded, non-deterministic rolling window — the same seed recorded it
holding 200, then 16, then 200 entries across a few minutes of the same session, with tail order
not equal to time order and rows appearing and disappearing between queries. Re-query, sort the
results by timestamp yourself, and do not conclude "did not route" from a single miss. Separately,
Claude Code prints a `[claude-code:unrecognized_model]` line on every routed launch because the
routed id is absent from Claude Code's own local model-metadata registry; this is cosmetic and
does not mean the request failed to route — do not treat its presence as a routing failure.

## 4. External libraries

External libraries install through their own front doors (`libraries:list`, `libraries:install`,
`libraries:status`) — never through `lifecycle:install` or any gate — and every install below is
dry-run by default; the tool requires an explicit `--yes` to actually invoke a front door.

**Dry-run first.** `mise run libraries:install -- <library>` with no `--yes` prints the same
per-library block `libraries:list` shows (front door, licence, working dir, write target,
selection-surface cost, and any precheck) and then states plainly that nothing was run. Captured
today in `asdlc-fresh`:

```
$ mise run libraries:install -- hyperresearch
=== hyperresearch ===
...
DRY RUN: nothing was run. Re-run with --yes to invoke the front door above.

Dry run is the default. No library was installed and no command was run.
```

**Then `--yes` per library**, one at a time, after reading the dry-run block — ECC additionally
gates behind `--acknowledge-ecc-surface` given the size of its selection-surface cost, independent
of any version check.

**Landing-path checks in the operator home.** Each front door writes to the operator's own
`~/.claude` (or `~/.codex`), never into this repository:

- ECC and hyperresearch's rendered skills land flat under `~/.claude/skills/`, alongside this
  bundle's own entries in the same namespace — first-writer-wins on a name collision.
  hyperresearch additionally writes agent files under `~/.claude/agents/`.
- mattpocock's Claude-marketplace path lands plugin-namespaced under `~/.claude/plugins/`, not
  flat — a bare-name collision there duplicates a capability rather than blocking the install.
  When another channel already holds flat copies of the same upstream (the exact collision this
  split creates), `mise run libraries:migrate` is the sanctioned path: it retires that channel's
  copies through that channel's own removal path before installing.

`mise run libraries:status` reports what it can detect this way for each library by name
(`not detected`, an `M/N` present count against its own enumeration, or `unknown` when the
surface isn't enumerable offline) — detection reads the filesystem only and proves presence, not
provenance. Seed `agentic-sdlc-927e` recorded the failure mode to watch for here: the bundle's
enumeration once trailed the installed CLI's real output by two agent files, so a clean-looking
`N/N present` line under-reported the surface. Since that fix, hyperresearch's agent count is
stated against a *recorded* upstream-version set, and `status` separately reports any
prefix-matching file the recorded set does not name — a residue line there means the surface is
wider than the count and the set needs re-recording against the current upstream.

**The idempotence re-run.** Running the same library's `--yes` install a second time against a
home that already has it should change nothing — the progress record's Lane 2 confirmed exactly
this for ECC by running it twice and diffing the result.

**mattpocock/skills: verify BOTH front doors separately, because they need different prerequisites.**

1. *Claude marketplace path* (`claude plugins install mattpocock-skills`, per `libraries:list`'s
   own printed front-door line — the Claude CLI treats `plugin` and `plugins` as the same
   command) **requires a Claude Code session with at least one configured marketplace, which in
   practice means an authenticated one**: a fresh logged-out install has none configured. Seed
   `agentic-sdlc-b3aa` recorded this by execution: on an unauthenticated, freshly installed
   Claude Code, `claude plugin marketplace list` showed no configured marketplaces and the
   install failed honestly with `not-found-in-any-configured-marketplace` — this bundle's task
   reported the real failure rather than a false success, but the upstream README's "no add step
   needed" claim does not hold for a logged-out session. Since that seed's fix, a failed
   marketplace install with no configured marketplace also prints the prerequisite plus a
   `DIRECTED:` line naming the CLI door below, so the dead-end-looking message now points at the
   working alternative.
2. *`skills` CLI path* (`npx skills` or `bunx skills`, mise pins both Node and Bun so either
   runner resolves inside a trusted checkout) **works without any Claude Code auth**, because it
   writes flat files the operator owns rather than going through a plugin marketplace. Verified
   grammar, captured today by running `npx --yes skills --help` (and confirmed identical via
   `bunx skills --help`) inside `asdlc-fresh` — quoting only what was observed, not the tool's
   documentation:

   ```
   Manage Skills:
     add <package>        Add a skill package (alias: a)
                          e.g. vercel-labs/agent-skills
                               https://github.com/vercel-labs/agent-skills
     use <package>@<skill>
                          Generate a prompt for using one skill without installing it
     remove [skills]      Remove installed skills
     list, ls             List installed skills
     find [query]         Search for skills interactively

   Add Options:
     -g, --global           Install skill globally (user-level) instead of project-level
     -a, --agent <agents>   Specify agents to install to (use '*' for all agents)
     -s, --skill <skills>   Specify skill names to install (use '*' for all skills)
     -y, --yes              Skip confirmation prompts
     ...
     --all                  Shorthand for --skill '*' --agent '*' -y
   ```

   So the observed grammar for mattpocock through this front door is `npx skills add
   mattpocock/skills` (or `skills@latest add mattpocock/skills`, per `libraries:list`'s own note
   on this alternative), taking the `owner/repo` package spec the tool's own example shows.

**Remove blast-radius caveat.** `npx skills remove --help`, captured today in `asdlc-fresh`,
documents the hazard directly in its own option table:

```
Options:
  -g, --global       Remove from global scope (~/) instead of project scope
  -a, --agent        Remove from specific agents (omit to clean all agent links)
  ...
Examples:
  $ skills remove --global my-skill          # remove from global scope
  $ skills rm --agent claude-code my-skill   # remove from specific agent
```

A global `remove` without `--agent` cleans *every* agent's link to that skill, including the
canonical copy — `--agent claude-code` (or the relevant agent name) is the surgical, single-agent
scope. Prefer the scoped form whenever the intent is "unlink this from one agent," not "delete
this skill everywhere."

## 5. Caveats

- **`git safe.directory` on read-only bind mounts.** Cloning from a read-only bind-mounted source
  (the pattern this runbook's container harness uses to keep a pristine, reusable checkout on the
  host) trips git's dubious-ownership guard on every git invocation until the mount's path is
  added to `safe.directory`. Confirmed today in `asdlc-fresh`: `git config --global --get-all
  safe.directory` returned exactly the two paths the harness needed (`/src/.git` and `/src`) for
  git commands against the clone to run clean. A real operator cloning directly from a remote
  never hits this — it is an artifact of the read-only-mount harness, not of the bundle.
- **Containers as the cheap fresh-environment harness.** Running each variant in a disposable
  container (rather than a real fresh machine) is what makes re-running this runbook cheap enough
  to actually do. Give the container a bounded memory cap rather than an unbounded one — check
  what a running container was actually given with
  `docker inspect <name> --format '{{.HostConfig.Memory}}'` rather than assuming a default, since
  an unbounded search or install inside an uncapped container can exhaust the host, not just the
  container.
- **Where the executed evidence lives.** The full narrative for the run this runbook generalizes —
  exact counts, wall times, and every seed opened from a real finding — is in
  `docs/progress/2026-08-20-fresh-env-and-routing-verification.md`. This runbook is the repeatable
  procedure; that record is the dated evidence for one specific pass through it.
- **A fully green pass here is evidence, never authorization.** Completing every section proves
  the installed surface works as described on that host, and nothing more — no push, publication,
  PR mutation, merge, deployment, or credential operation is authorized by it.
