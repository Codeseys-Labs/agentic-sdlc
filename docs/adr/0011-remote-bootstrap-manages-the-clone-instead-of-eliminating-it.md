# ADR-0011 — a remote bootstrap manages the clone instead of eliminating it

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (question and decision), agent (executed evidence and mechanism)
- **Relates to:** `scripts/bootstrap-agentic-sdlc.sh`, `docs/research/2026-08-07-clone-free-install.md`, `docs/plans/2026-08-14T163833Z-Install-UX.md`, `docs/adr/0002-mise-is-the-single-front-door.md`, `README.md`

## Context

The operator asked whether this bundle can be installed globally from a remote
with mise alone, without cloning the repository. The premise is sound: mise
demonstrably installs an individual pinned tool from a remote with no clone at
all, e.g. `mise use -g "npm:@bitkyc08/opencodex@2.10.2"`. The question is
whether the same is true of *this* bundle.

It is not, and the reason is structural rather than a gap in mise. Two facts,
both established by execution rather than by reading docs, decide it.

First, mise can consume remote *tasks*, but only by cloning. `mise` 2026.4.27
supports an experimental `git::` form in `task_config.includes`. Pointing it at
this repository's `mise.toml` produced a parse error naming
`~/.cache/mise/remote-git-tasks-cache/<sha256>/mise.toml`, and that cache turned
out to be a full 6.9 MB clone with an intact `.git`, checked out at commit
`19f56f9`. So the mechanism that looks clone-free is a clone that mise performs
and owns. It is also the wrong shape twice over: an included file is parsed
against the *task-file* schema, where top-level tables are task names, so
`[settings]`, `[tools]`, and `[tasks.x]` are all rejected as unknown fields
(`locked` was the first one it hit); and includes carry tasks only, never
`[tools]`, so the pinned toolchain this bundle depends on would not come along.
An included task also runs with the *caller's* working directory, not the task
file's, which is precisely wrong for tasks whose commands are tree-relative
paths. A plain HTTPS URL in `includes` is worse than an error: it silently
resolves zero tasks and exits 0. There is no `git`-style backend in
`mise backends ls` and no bundle or plugin-repo concept in the registry that
would apply.

Second, and decisively, the tree is a hard run-time dependency of this bundle,
not merely an install-time one. Every runnable task in `mise.toml` ultimately
reaches a repo-internal path, and no task is tree-independent: `check`,
`contributor:setup`, and its deprecated `setup` forwarder have no `run` at all,
only `depends` on tasks that do. Every Python entrypoint anchors
its root at `Path(__file__).resolve().parents[1]` with no override flag
(`scripts/install_skill_bundle.py:2890`, `scripts/install_operator_tools.py:477`,
`scripts/render_mermaid_linux.py:28`). Default-mode installs are symlinks *into*
the tree (`scripts/install_skill_bundle.py:984-985`), and ownership state records
the absolute source path (`:1032`), re-verified on every `status` via
`os.path.samefile` (`:1069`); deleting the tree turns an `ok` entry into
`conflict`. The PATH launchers bake an absolute in-tree exec target through
`@CANONICAL_LAUNCHER@` (`scripts/install_operator_tools.py:112-113`). Trust is
scoped to an absolute config path, so whatever tree exists must be trusted where
it sits.

The honest reframing is therefore that the clone cannot be eliminated, but the
*operator's* act of cloning can be. The user should never choose a directory,
clone by hand, or track where the tree lives.

## Considered options

1. **Remote `git::` task includes.** Rejected on executed evidence. It clones
   anyway, into a cache the operator cannot review before it is populated; it
   cannot parse this repository's `mise.toml`; it would not carry `[tools]`; and
   the working-directory semantics break tree-relative task commands.
2. **`mise use -g` for the tools, then a separate fetch.** Rejected as a primary
   path. It genuinely installs the pinned tools clone-free, but it delivers none
   of the skills, agents, commands, gates, or tasks, which are the bundle. It
   would leave a global toolchain pinned with nothing to run.
3. **`curl … | bash` as the primary instruction.** Rejected as primary, offered
   as a convenience only. Piping a remote script into a shell executes bytes the
   operator has not read, which contradicts this repository's standing posture
   that review precedes trust.
4. **A documented two-liner:** `git clone --depth 1 <url> <managed-path> && mise -C <managed-path> run contributor:setup`.
   Rejected as insufficient on its own — it is honest but silently clobbers,
   re-clones, or half-updates on the second run, and it makes the operator hold
   the managed path in their head.
5. **A small fetch-and-report bootstrap script, run from a file the operator can
   read first.** Chosen.

## Decision

Ship `scripts/bootstrap-agentic-sdlc.sh`: a stdlib-shell script that fetches
this repository into a managed location, records what it fetched, and then
**stops and prints** the remaining commands rather than running them.

The managed clone lives at `${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc`,
overridable with `AGENTIC_SDLC_HOME`. `--print-path` reports it, so an operator
never has to remember it, and removal is `rm -rf` of that path plus the state
directory. The fetch receipt — remote, ref, resolved commit, path — is written
to `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/bootstrap-receipt.json`,
outside the clone, so recording it never makes the tree dirty.

The script's boundary is deliberate: it fetches and reports, and it never trusts
a config, resolves a toolchain, or installs bundle entries. Those three remain
separate operator approvals against a tree they have read. `mise trust` is a
persistent per-path mutation and stays exactly as gated as it is today. The
script reads the current trust state and prints it, which is evidence, not a
grant. It requires mise and git, installs neither, and exits 2 naming whichever
is missing.

Re-running is idempotent and fails closed with named reasons and exit 3: a clone
whose `origin` is not the expected remote, a dirty or untracked tree, a ref
mismatch under `--update`, a non-fast-forward, or a non-empty non-git directory
at the managed path each refuse rather than clobber. `--dry-run` prints the exact
`git clone` it would run and creates nothing.

This does not add a bootstrap prerequisite and so does not disturb ADR-0002.
mise remains the only managed-tool bootstrap; git was already a documented
runtime-readiness capability, and this script consumes both rather than
introducing a third.

## Consequences

- Positive: one readable command replaces a five-step manual quickstart, and the
  operator's own directories are never touched.
- Positive: the resolved commit is recorded, so an install is reproducible and
  auditable after the fact.
- Positive: the failure modes that made the hand-rolled two-liner unsafe —
  clobbering, silent re-clone, partial update — are now named refusals.
- Negative: **the clone-free claim is narrow, and overstating it would be the
  main risk of this record.** The tasks still come from a tree on disk; the tree
  is merely managed on the operator's behalf. Anyone wanting a genuinely
  tree-free install should use the Claude marketplace plane instead, which
  already needs no clone and no toolchain trust step, at the cost of delivering
  only the plugin payload.
- Negative: **HTTPS authenticates the transport, not the contents.** Nothing here
  verifies a signature over the fetched commit, and this ADR claims no verified
  supply chain. The script says so in its own output rather than implying
  otherwise. `--depth 1` also means the receipt's commit is the only history
  present.
- Negative: the receipt detects ordinary drift, not a same-UID attacker who
  rewrites the managed clone between fetch and use.
- **Confirmation:** proven end to end in a `debian:13-slim` container as a
  non-root user with only curl, git, ca-certificates, unzip, and mise
  2026.4.27 — no node, python3, uv, bun, or npm on PATH. Bootstrap exited 0 and
  resolved `19f56f9`; the dirty-tree and wrong-remote refusals exited 3; `mise
  --locked install` exited 0 in **one** run installing all 13 tools;
  `mise run check` exited 0 over 694 tests in 325s; `bundle:install` exited 0;
  `bundle:status` reported `38 ok, 0 conflict, 0 absent`; the installed skill
  symlink resolved into the managed clone; and the then-shipped `ocx-launch`
  alias was reachable on PATH. That historical confirmation predates ADR-0010's
  2026-08-10 alias-retirement amendment; fresh operator-tools installs now expose
  `ccodex` instead. One caveat found by that run and worth recording: `unzip` must be
  present or puppeteer's postinstall — a transitive dependency of the advisory
  `mermaid-cli` pin — fails and takes `mise --locked install` to exit 1 with it,
  on both the first and second attempt. That is a container-image gap, not the
  npm ordering bug ADR-era `depends` already fixed; npm 10.8.1 installed cleanly
  in the first pass.

## 2026-08-14 prospective release-artifact amendment

The operator has selected a second distribution shape that is different from the remote-task
mechanism rejected here: a versioned, self-contained GitHub release archive installed with
`mise use -g github:Codeseys-Labs/agentic-sdlc`. The GitHub backend installs one release artifact;
it does not import this repository's `[tools]` table. The archive must therefore carry `ccodex`,
the authored bundle payload, and its private runtime dependencies, resolve its distribution root
relative to its executable, and copy explicitly activated host entries so pruning an old mise
version cannot break them. Host-plane activation remains a separate collision-checked operation.
The managed checkout remains the contribution, customization, gates, and release-building path.

This is a prospective amendment, not a claim that the reversal has shipped. The repository has no
GitHub release or tag for mise to resolve, the current dispatcher still points into a checkout, and
current bundle activation still uses checkout-backed links. ADR-0011 therefore remains the current
install decision until the archive builder, release workflow, copy activation, clean-host tests,
and first release exist. At that point a new ADR must supersede this one rather than editing away
its executed evidence. The exact proposed UX and implementation order are recorded in
[`docs/plans/2026-08-14T163833Z-Install-UX.md`](../plans/2026-08-14T163833Z-Install-UX.md).

## Reversal condition

If mise gains the ability to consume a remote config's `[tools]` and `[tasks]`
together, with a reviewable local checkout and task commands resolved relative
to that checkout, this ADR is superseded rather than silently violated: the new
record must name the mise version, show the executed evidence that all three
properties hold, and state what happens to the managed clone and its receipt.
Equally, if this bundle is ever restructured so its entrypoints stop anchoring
on `__file__` and its installed artifacts stop pointing into the tree, the
clone-dependency premise here no longer holds and should be re-litigated.

This record is evidence for a conductor to cite; it authorizes no clone, fetch,
network call, config trust, toolchain install, credential use, push,
publication, merge, deployment, or other outward effect on its own.

## Amendment — 2026-08-24: the first prerelease exists, and the mise `github:` acquisition leg is executed evidence

The archive builder, copy activation, and clean-host journey this record was waiting on now have
executed evidence, and the first release artifact exists: `v0.7.3` was published as a
`--prerelease` (tag at `4c7f7c2`, archive sha256 `fc820fc2…711349`, notes inside the claim plane —
`release_claim: "none"`, no support tuple, disclosures verbatim). Container proof the same day:
`mise install` of the exact version resolved the prerelease-flagged release and re-hashed 231/231
manifest entries clean, and the receipted activation journey ran end to end from the downloaded
bytes (26/26 digests, clean post-uninstall status). Two measured facts bound the claim: the
UNVERSIONED `mise use -g` form fails for two reasons (prerelease exclusion and mise's built-in
`minimum_release_age` filter) and stays unclaimed, and mise exposed the whole `scripts/` directory
as the tool's bin path — resolved by committing `bin/ccodex`, a self-locating dispatcher, so the
release tree exposes exactly one command (adopted per the operator's 2026-08-24 direction; the
first release carrying it is `v0.7.4`).

This publication amends the Install-UX plan's implementation order (its publish step ran before
its steps 3, 5, and 7) rather than following it; the plan document remains the UX record. The
managed clone stays the supported distribution for gates, Seeds, and contribution — the release
tree carries no `.git`, so those surfaces refuse there by design, which is the copy-versus-link
boundary executing as recorded. ADR-0021 remains proposed: runtimes are auto-installed from the
tree's pins, not packaged, and its self-contained-artifact legs are unexecuted. This amendment
records executed evidence and authorizes nothing further.
