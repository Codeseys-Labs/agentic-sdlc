# Project scope on a clean host — executed capability evidence for the (project) scope row

**Seed:** agentic-sdlc-7a2b (wave W6, the decision-debt close of the front-door train)
**Observed:** 2026-08-26T07:23:34Z, on Linux 6.18.33.2-microsoft-standard-WSL2 x86_64 (WSL2)
**Subject:** `ccodex install | status | uninstall --scope project --agent claude --project <repo>`
**Artifact under test:** the built release archive of commit `438ce67`
(`agentic-sdlc-0.7.5.tar.gz`, `sha256 4bf76b393607bc3c19fc0db20ba409ee01ebd0e7cfbced4d5ae5c13ecfed7202`),
extracted and placed as an acquisition candidate — not the checkout.

**Why this file exists.** ADR-0027 item 4 says Core and optional profiles, platforms, installation
methods, renderers, and companion hosts never inherit one another's tier, and the front-door plan's §5
applies that to the new scope axis: a (project) capability row gets its own evidence, and nothing is
inherited from the user-scope journeys. So every command below was executed against fixture planes that
share nothing with this host's real `~/.claude` or its real state root, and every result quoted is a
result that ran.

**What this file is not.** It is not a certification, and it is not evidence that any tuple is
`certified` or `capability-qualified` — those need the selected surface's current capability canaries
(ADR-0027 item 2). It is one executed journey on one host, plus the three defects it surfaced.

## Isolation: what was fresh, what was shared, and why

Fresh for this run, created empty and thrown away after: `HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME`,
`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `CODEX_HOME`, and the target repository. Every product plane the
lifecycle can write — the ownership ledger, the receipt-and-pointer plane, the statusline and hook
receipt stores, the configured Claude home — therefore resolved inside the fixture. `PATH` was an
allowlist, not the operator's.

**Two things were deliberately shared, and neither is product state.** `MISE_DATA_DIR` and
`MISE_CACHE_DIR` pointed at this host's real mise installation, so the pinned toolset resolved from
tools already downloaded rather than re-fetching about 1.3 GB; mise is the documented sole bootstrap
prerequisite, so reusing its install tree is reusing the prerequisite, not inheriting a product plane.
And trust was supplied **process-scoped** through `MISE_TRUSTED_CONFIG_PATHS`, naming only the
extracted candidate's own `mise.toml`. Nothing here ran `mise trust`: trust is scoped to an absolute
config path, a persistent trust mutation needs its own operator authorization, and a process-scoped
value leaves no state behind. That is the one step of the documented first-use sequence this transcript
substitutes for rather than performs, and it is named here rather than glossed.

Even so, the run downloaded a real 31.1 MiB CPython 3.12.11 into the fixture's own uv directory, which
is what a genuinely clean host pays on its first tool-needing verb. That line is left in the transcript
below instead of filtered out.

## The transcript

Paths are shown with the fixture root as `$FIX` and the target repository as `$REPO`
(`$FIX/project`); everything else is verbatim. Per-entry rows are elided where stated, with their
count and their uniform content given.

```
--- 0. when and where
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-08-26T07:23:34Z
$ uname -srm
Linux 6.18.33.2-microsoft-standard-WSL2 x86_64
$ sha256sum $HOME/.local/state/agentic-sdlc-installer/state.json   # the operator's REAL ledger
41c40fd4a59fd84cb1d4daef3463f5a4e7ebefea058025aaa1230ce5fc6eb2dc  $HOME/.local/state/agentic-sdlc-installer/state.json

--- 1. the fixture planes are empty; the repository is a fresh empty git checkout
$ ls -A $FIX/home $FIX/state
home:
state:
$ ls -A $REPO
.git
$ git -C $REPO log --oneline
e8a9f39 empty fresh repo

--- 2. ccodex doctor   (before: six stores, all absent)
Downloading cpython-3.12.11-linux-x86_64-gnu (download) (31.1MiB)
 Downloaded cpython-3.12.11-linux-x86_64-gnu (download)
Installed Python 3.12.11 in 3.43s
 + cpython-3.12.11-linux-x86_64-gnu (python3.12)
ccodex doctor: absent
checkout: 0.7.5 checkout-development; public channel: not-selected; public release: not-selected; certification: none
runtime: admitted (3.12.11, isolated=true)
bundle: absent
recovery: not-needed (no effects)
future dimensions: release=not-selected, activation=unsupported, waves=unsupported
state store [receipts/live]: absent ($FIX/state/agentic-sdlc)
state store [claude-hooks/live]: absent ($FIX/state/agentic-sdlc-claude-hooks)
state store [claude-statusline/live]: absent ($FIX/state/agentic-sdlc-claude-statusline)
state store [claude-workflows/retired]: absent ($FIX/state/agentic-sdlc-claude-workflows)
state store [bundle/live]: absent ($FIX/state/agentic-sdlc-installer)
state store [operator-tools/retired]: absent ($FIX/state/agentic-sdlc-operator-tools)
exit=0

--- 3. ccodex install --scope project --agent claude --project $REPO
ccodex install --scope project --agent claude: effect complete, terminal activated
candidate bc9c3c92fb87 resolved 0.7.5 via archive-manifest (requested: no version was requested)
mode: copy (this plane copies and never links; none was requested)
claude root: $FIX/project/.claude (copies, never links)
project root: $FIX/project (resolved; the plane is keyed by this root, so two worktrees of one repository are two independent planes)
session registry: this repository's own .claude/workflows/ is the host's only Workflow name registry and it is read once at session start (measured 2026-08-24, agentic-sdlc-4d2b), so this change takes effect at the target's NEXT Claude Code session
enablement: a workflow placed in this repository's .claude/workflows/ is discovered there and nowhere else, so this activation enables it; hook bytes land inert, since wiring one into settings is its own grant
the project root is a git repository; a committed copy is restorable from its index, so an uninstall's removal is recorded twice -- by its own receipt, and by git status plus the index
acquisition ticket: SEALED $FIX/state/agentic-sdlc/acquisition/receipts/4bf76b393607bc3c19fc0db20ba409ee01ebd0e7cfbced4d5ae5c13ecfed7202.json from the release root's own manifest.json, verified in both directions (a later run reuses exactly this document)
receipt: $FIX/state/agentic-sdlc/activation/receipts/install-claude-project-48caff0b367e3236-op-f26294f75487fc9d7af4f12a52192bab-20260826t072338z.json
active pointer $FIX/state/agentic-sdlc/activation/active/claude/project-48caff0b367e3236.json names this activation's receipt
public_channel null and release_claim none: this activation states no published release exists, and it authorizes no push, publication, merge, or deployment
exit=0
(29 per-entry rows elided; every one read "absent -> installed")

--- 4. what landed, and that it is copies
$ ls $REPO/.claude
agents commands hooks skills statusline workflows
$ find $REPO/.claude -type l | wc -l   # copy-only plane: must be 0
0
$ find $REPO/.claude -type f | wc -l
95
$ head -2 $REPO/.claude/workflows/sdlc-wave-scout.js
// workflow: sdlc-wave-scout
//
$ git -C $REPO status --short
?? .claude/

--- 5. the operator's own planes were not touched
$ sha256sum $HOME/.local/state/agentic-sdlc-installer/state.json
41c40fd4a59fd84cb1d4daef3463f5a4e7ebefea058025aaa1230ce5fc6eb2dc  $HOME/.local/state/agentic-sdlc-installer/state.json
$ ls $HOME/.claude/workflows | wc -l    # the real home's workflow collection
0
$ ls $HOME/.local/state/agentic-sdlc/activation/active/claude/
ls: cannot access '$HOME/.local/state/agentic-sdlc/activation/active/claude/': No such file or directory
$ echo "exit=$?"
exit=2

--- 6. ccodex doctor   (after: the two stores the run really wrote read present)
state store [receipts/live]: present ($FIX/state/agentic-sdlc)
state store [claude-hooks/live]: absent ($FIX/state/agentic-sdlc-claude-hooks)
state store [claude-statusline/live]: absent ($FIX/state/agentic-sdlc-claude-statusline)
state store [claude-workflows/retired]: absent ($FIX/state/agentic-sdlc-claude-workflows)
state store [bundle/live]: present ($FIX/state/agentic-sdlc-installer)
state store [operator-tools/retired]: absent ($FIX/state/agentic-sdlc-operator-tools)
exit=0

--- 7. a second identical install REUSES the acquisition ticket
ccodex install --scope project --agent claude: effect complete, terminal activated
acquisition ticket: REUSED $FIX/state/agentic-sdlc/acquisition/receipts/4bf76b393607bc3c19fc0db20ba409ee01ebd0e7cfbced4d5ae5c13ecfed7202.json (already filed for this archive digest, re-validated against its own seal; receipts are create-only and this run wrote none)
exit=0
$ ls $FIX/state/agentic-sdlc/acquisition/receipts/ | wc -l   # still exactly one
1

--- 8. ccodex uninstall --scope project --agent claude --project $REPO
ccodex sdlc uninstall: retired
retired activation: install-claude-project-48caff0b367e3236-op-f26294f75487fc9d7af4f12a52192bab-20260826t072355z (host claude, scope project:$FIX/project, resolved 0.7.5)
session registry: this repository's own .claude/workflows/ is the host's only Workflow name registry and it is read once at session start (measured 2026-08-24, agentic-sdlc-4d2b), so this change takes effect at the target's NEXT Claude Code session
journal: $FIX/state/agentic-sdlc/activation/journals/uninstall-install-claude-project-48caff0b367e3236-op-f26294f75487fc9d7af4f12a52192bab-20260826t072355z.json
terminal receipt: $FIX/state/agentic-sdlc/activation/receipts/uninstall-install-claude-project-48caff0b367e3236-op-f26294f75487fc9d7af4f12a52192bab-20260826t072355z.json (operation uninstall, effect complete, terminal retired)
a completed retirement is evidence: it authorizes no push, publication, PR mutation, merge, deployment, or any other outward effect
exit=0
(29 "removed: <entry>" rows elided)

--- 9. what the retirement left behind
$ find $REPO/.claude | sort
$REPO/.claude
$REPO/.claude/agents
$REPO/.claude/commands
$REPO/.claude/hooks
$REPO/.claude/skills
$REPO/.claude/statusline
$REPO/.claude/workflows
files: 0  dirs: 7  links: 0
$ git -C $REPO status --short
(no output = clean)
$ ledger entry count after retirement
entries: 0 pending: None version: 4
$ ls $FIX/state/agentic-sdlc/activation/active/claude/
project-48caff0b367e3236.json

--- 10. the other agent at this scope, on the same fixture
$ ccodex install --scope project --agent codex --project $REPO
error: ccodex install refused before any effect: ccodex install --scope project is not admissible for the Codex CLI plane (project-scope-unsupported-for-agent): its configured root IS its agent root, so a project root would place this bundle's collections at the repository's own top level, and nothing in this distribution measures a repository-local collection that host reads. Use --scope user for that plane; nothing was written
exit=3
```

The ledger's own rows were read directly at the point between steps 4 and 5: **29 entries**, all
`mode: copy` and `removable: True`, **all 29 under the project root** and **zero under the isolated
home** — so project scope really placed its payload under the repository and not under the configured
Claude home that happened to be adjacent to it.

## What this establishes, and what it does not

Established by execution: a project-scope activation of an acquired release root onto a fresh git
repository completes at exit 0; it seals its own acquisition ticket from the root's `manifest.json`
and reuses rather than rewrites it on a second run; it places 95 files across six collections as
**copies with zero symlinks**, which is the copy-only rule the plan makes non-negotiable for a
committable plane; it keys the plane by the resolved root (`project-48caff0b367e3236`, derived from
that root's path); it prints the session-registry sentence on both the install and the uninstall; and
it leaves this host's real ledger byte-identical and the real home's workflow collection empty. The
retirement removes all 29 entries, empties the ledger, and leaves `git status` clean.

Step 10 executed the other agent at the same scope on the same fixture: `--agent codex` refuses at exit
3 by name (`project-scope-unsupported-for-agent`), because a Codex configured root *is* its agent root,
and the refusal states that nothing was written.

Not established, and not claimed: any certification tier; that a placed workflow is actually
discovered by a Claude Code session (that is a live-host canary, not a filesystem observation); or the
behavior on macOS or native Windows.

## Three defects this journey surfaced

**1. The uninstall's success banner prints a RETIRED verb spelling.** The operator typed
`ccodex uninstall --scope project --agent claude --project <repo>` and the first line of a successful
run answered `ccodex sdlc uninstall: retired`. The spelling is hard-coded at
`scripts/ccodex_sdlc_uninstall.py:1453`, and `install` does not share the defect — its banner reads
`ccodex install --scope project --agent claude: …`, the invocation the operator actually used. Wave W3a
recorded this residual for the per-verb modules' **error** lines and had the seam cases assert those as
*emitted* rather than as *correct*; the success path was not covered by that note, and a completed
operation reporting itself under a spelling the dispatcher refuses is worse than a refusal doing it.
Not fixed here: the banner is another wave's file, and changing it moves output that seam cases pin.

**2. Seven empty directories survive the retirement, and nothing names them.** `<repo>/.claude/` and
its six collection directories are created by the install and are still there afterwards, because the
uninstall removes files and the ownership rows that cover them. `git status` reads clean only because
git does not track empty directories — so the transcript's "restorable from its index" story is intact
while the working tree is not actually back to its prestate. The deleted per-file workflows manager
recorded `created_claude_dir` and `created_workflows_dir` in its own receipt precisely so a deactivate
could remove a directory it had created; that capability did not survive the fold into project-scope
activation, and the output does not mention the leftover either way. Whether the fix is to remove
directories the install created or to name them in the report is a decision, not a bug fix.

**3. `doctor` and `status` report `bundle: absent` while 29 project rows are live.** Steps 6 and 7 show
`state store [bundle/live]: present` and the projection's `bundle: absent` in the same report, on a host
whose ledger holds 29 project-scope rows. This is the already-recorded status-narrowing gap (seed
agentic-sdlc-95e6, filed by W4): the bundle projection reads the configured home's plane, project rows
live under the repository root, and narrowing the body per (agent, scope, root) needs a scope dimension
in the digest-pinned report policy. It is restated here because this is the first transcript in which
the two lines contradict each other in front of an operator.

One behavior that looks like a defect and is not: the `(claude, project, <root>)` **pointer survives**
the ordinary retirement (step 9), where §2.2 item 6's records-only retirement of a vanished root
removes it. That asymmetry is deliberate and was stated in code by wave W4.

## Reproducing this

The archive is not committed. From this checkout at `438ce67` or later:

```
mise run release:build                    # refuses a dirty tree; writes dist/agentic-sdlc-<version>.tar.gz
# extract it to $FIX/data/agentic-sdlc/acquisition/candidates/<archive-sha256>/root
# git init a fresh $FIX/project
# run $CAND/bin/ccodex with HOME and every XDG_* pointed inside $FIX, MISE_DATA_DIR/MISE_CACHE_DIR
#   at your real mise install, and MISE_TRUSTED_CONFIG_PATHS=$CAND/mise.toml
```

The offline half of the same behavior is gated on every run by
`tests/test_project_scope_acceptance.py`; this document is the part a test cannot be — the real
dispatcher, the real archive, and a real repository.
