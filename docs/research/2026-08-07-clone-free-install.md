# Can this bundle be mise-installed globally from a remote without cloning?

- **Date:** 2026-08-07
- **Question (operator, verbatim):** "is there no way to mise-install globally from remote without having to clone the agentic-sdlc repo?"
- **Method:** executed commands on mise 2026.4.27 linux-x64, plus a container run against the public remote. Doc reading was used only to find candidate mechanisms; every claim below was checked by running it.
- **Answer:** No — not for the bundle. The clone can be *managed for the operator* but not eliminated. The premise of the question is correct for a single tool and false for this bundle, for structural reasons in this repository rather than a gap in mise.

## 1. What mise can and cannot do here

### Confirmed: a single pinned tool installs globally with no clone

The operator's own check holds. `mise use -g "npm:@bitkyc08/opencodex@2.10.2"`
installs one pinned tool from a remote with no repository present. That is the
capability the question generalizes from.

### Refuted: a plain HTTPS URL in `task_config.includes` — silent no-op

```toml
[task_config]
includes = ["https://raw.githubusercontent.com/Codeseys-Labs/agentic-sdlc/main/mise.toml"]
```

```
$ mise -C "$TD" tasks ls --no-header --name-only | wc -l
0
$ mise -C "$TD" tasks ls -vv
TRACE load_all_tasks 0
```

Zero tasks, exit 0, no error and no warning. This is the worst failure mode
found: it looks like it worked. A top-level `include = [...]` with a URL is at
least honest about it — `mise WARN unknown field in …/mise.toml: include`.

`mise run <url>` is rejected outright:

```
mise ERROR relative path syntax 'https://raw.githubusercontent.com/...' is not supported
```

`MISE_OVERRIDE_CONFIG_FILENAMES=<url>` produced no output and no tasks.

### Confirmed to exist, but clones anyway: experimental `git::` includes

mise does support remote task includes, documented as "Remote Git Includes
(experimental)" with the form
`git::<protocol>://<url>//<path>?ref=<ref>`. Pointed at this repository:

```toml
[task_config]
includes = ["git::https://github.com/Codeseys-Labs/agentic-sdlc.git//mise.toml?ref=main"]
```

```
mise ERROR Error parsing task file: ~/.cache/mise/remote-git-tasks-cache/8f8765ef…215e/mise.toml
mise ERROR TOML parse error at line 4, column 1
  |
4 | locked = true
  | ^^^^^^
unknown field `locked`, expected one of `description`, `alias`, `confirm`, `depends`, …
```

Three findings from that one error, each load-bearing.

**It is a clone, not a fetch.** Inspecting the cache mise created:

```
$ git -C ~/.cache/mise/remote-git-tasks-cache/8f8765ef…215e rev-parse HEAD
19f56f9e49cac34cf50e066132f3970deabb8d86
$ du -sh ~/.cache/mise/remote-git-tasks-cache/8f8765ef…215e
6.9M
```

A full working tree with an intact `.git`, plus `.claude/`, `skills/`, `scripts/`
and the rest. The clone-free-looking mechanism is a clone that mise performs and
owns, in a cache the operator has no opportunity to review first. Note the
`.git` suffix on the URL is required: without it the include resolved to zero
tasks silently.

**The schema is a task-file schema, not a config schema.** An included `.toml`
treats top-level tables as task *names*. Verified locally:

```toml
# tf/two.toml
[alpha]
run = "echo ALPHA"
[beta]
run = "echo BETA"
```

```
$ mise -C "$TD" tasks ls   →  alpha, beta
$ mise -C "$TD" run alpha  →  [alpha] $ echo ALPHA / ALPHA
```

So `[settings]`, `[tools]`, and `[tasks.<name>]` in this repository's `mise.toml`
are all unknown fields to an include. `locked = true` at line 4 is simply the
first one the parser reaches. This repository's `mise.toml` can never be a
valid include target.

**Includes carry tasks only — never `[tools]`.** With the `git::` include in
place, `mise ls --current` showed only tools from the ambient global config
(`~/.config/mise/config.toml`) — none of `uv`, `bun`, or the repo's 13 pins. The
pinned toolchain that every task depends on does not come along.

**Working-directory semantics are wrong for this repo.** An included task runs in
the *caller's* directory, not the task file's:

```
$ mise -C /tmp/tmp.1jeIzsVgnn run whereami   # task file lives in sub/
[whereami] $ echo CWD=$PWD
CWD=/tmp/tmp.1jeIzsVgnn
```

Since every task command here is a tree-relative path like
`scripts/validate_bundle.py`, remote-included tasks would resolve those paths
against wherever the operator happens to stand.

### No bundle, plugin-repo, or registry mechanism applies

`mise backends ls` lists `aqua asdf cargo conda core dotnet forgejo gem github
gitlab go npm pipx spm http s3 ubi vfox` — no git-repo-as-bundle backend.
`mise search agentic` → `tool agentic not found in registry` (999 registry
entries, none applicable). `mise plugins` is asdf/vfox tool plugins, a different
concept from this skill bundle. `mise generate bootstrap` generates a script to
download *mise itself*, not a project.

## 2. Clone-dependency map: what actually needs the tree at run time

The tree is a run-time dependency, not just an install-time one. Three distinct
coupling mechanisms, each independently sufficient to require it.

**`__file__`-anchored roots with no override flag.** Every Python entrypoint
computes its root from its own location:

| Entrypoint | Line |
|---|---|
| `scripts/install_skill_bundle.py` | `:2890` `config_repo_root = Path(__file__).resolve().parents[1]` |
| `scripts/install_operator_tools.py` | `:477` |
| `scripts/render_mermaid_linux.py` | `:28` |
| `scripts/provision_mermaid_linux.py` | `:21` |
| `scripts/manage_claude_statusline.py` | `:520` |
| `scripts/validate_bundle.py` | `:202-205`, `:1626` |

`parse_args` (`install_skill_bundle.py:2862-2876`) exposes no flag to override
it. Source discovery globs four tree paths — `skills/*/SKILL.md`,
`agents/claude/*.md`, `commands/*.md`, `agents/codex/*.toml`
(`discover_entries`, `:767-782`).

**Live pointers that survive install.** Default `--mode auto` symlinks into the
tree (`:984-985`), and the ownership record stores the absolute source path
(`:1032`), re-verified on every `status` through `os.path.samefile` (`:1069`,
`:1076`) and `resolve(strict=False)` (`:1081`). Delete the tree and an `ok` entry
becomes `conflict`. The PATH dispatcher is a byte copy but hard-codes the
install-time repository root and canonical launcher through placeholders in
`assets/launchers/ccodex.in`; `scripts/install_operator_tools.py` substitutes the
quoted absolute paths. ADR-0010's 2026-08-10 amendment retired the older dedicated
alias templates without changing this run-time dependency.

**`mise -C "$root"` re-entry.** The shell wrappers and launchers need the tree's
*trusted* `mise.toml` at run time, not just their own bytes:
`scripts/opencodex-claude.sh:57` computes `root` then runs
`mise -C "$root" exec -- ocx` (`:102`); `scripts/install-skill-bundle.sh:9,31`
does the same.

**Run-time tree reads beyond install:** the mermaid renderer reads
`policy/mermaid-renderer-linux-v1.json` (`render_mermaid_linux.py:28-29`),
`scripts/sanitize_mermaid_svg.mjs` (`:517`), `node_modules/` (`:333`), and
re-digests `package-lock.json` at render time (`:326`).

**Every task is tree-coupled.** Every `run` string in `mise.toml` either names a
repo-internal path or invokes a tool against the repository. The depends-only tasks are not
exceptions: `check`, `contributor:setup`, and its deprecated `setup` forwarder reach tasks
that read the tree, while `hooks:install` is `lefthook install`, which reads `lefthook.yml`
from cwd and writes `.git/hooks` in the tree.

**Genuinely clone-free surfaces — exactly two.** The installed statusline copy
(`assets/claude/statusline-command.sh`) is self-contained: no `BASH_SOURCE`,
`dirname`, or tree reads in its 167 lines. And the Claude marketplace plugin
plane, which `README.md:433-435` already advertises as needing "no clone, no
mise, and no toolchain trust step," because Claude Code dereferences the
within-marketplace symlinks into a real-file cache copy.

**So:** the bootstrap can be clone-free from the operator's point of view; the
bundle cannot be tree-free. `tools/seeds-launcher.mjs` is a partial exception
worth noting — it takes the tree as an explicit `--distribution` argument rather
than from `__file__`, so it needs *a* clean Git root, but not necessarily this
one.

## 3. Bootstrap shape chosen, and why

`scripts/bootstrap-agentic-sdlc.sh` — fetch into a managed location, record the
resolved commit, then stop and print the remaining commands.

Rejected alternatives and the reason each lost:

- **`git::` remote includes** — refuted above by execution.
- **`mise use -g` plus a fetch step** — installs the tools clone-free but
  delivers no skills, agents, commands, or gates. A pinned toolchain with nothing
  to run.
- **`curl … | bash` as the primary instruction** — executes bytes the operator
  has not read, against this repository's standing review-before-trust posture.
  Documented as a convenience only, after the verify-then-run form.
- **A bare two-liner** (`git clone --depth 1 … && mise -C … run contributor:setup`) — honest,
  but clobbers or half-updates on re-run and makes the operator hold the managed
  path themselves.

Properties of the chosen shape: managed clone at
`${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc` (override
`AGENTIC_SDLC_HOME`, discover with `--print-path`, remove with `rm -rf`);
receipt at `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/bootstrap-receipt.json`,
kept outside the clone so writing it never dirties the tree; `--dry-run` prints
the exact `git clone` and creates nothing; named refusals at exit 3 for wrong
remote, dirty tree, ref mismatch, non-fast-forward, and occupied non-git path;
exit 2 naming a missing mise or git. It never trusts a config, never resolves a
toolchain, and never installs bundle entries — it prints those four commands
instead, with the current trust state shown as evidence.

**Integrity, stated honestly.** HTTPS authenticates the transport, not the
contents. Nothing verifies a signature over the fetched commit; `--depth 1` means
the receipt's commit is the only history present; and the receipt detects
ordinary drift, not a same-UID racer rewriting the managed clone between fetch
and use. The script prints this in its own output rather than implying a verified
supply chain.

## 4. Container transcript

Image: `debian:13-slim`, non-root user `op`, only `curl git ca-certificates
unzip` plus mise pinned to `v2026.4.27`. Deliberately **no** node, python3, uv,
bun, or npm.

```
node -> ABSENT   python3 -> ABSENT   uv -> ABSENT   bun -> ABSENT   npm -> ABSENT
mise -> /home/op/.local/bin/mise     git -> /usr/bin/git
mise 2026.4.27 linux-x64
```

Run 1 — bootstrap behavior and refusals, against the public remote:

| Step | Exit |
|---|---|
| `curl` the bootstrap from remote `main` | 22 (404 — script not yet pushed; local copy used for the proof) |
| bootstrap `--dry-run` (created nothing) | 0 |
| bootstrap (real clone, resolved `19f56f9e49cac34cf50e066132f3970deabb8d86`) | 0 |
| bootstrap re-run on clean clone (`nothing to do`) | 0 |
| bootstrap `--update` on a dirtied tree | 3 (refused, named the path) |
| bootstrap with a mismatched `--remote` | 3 (refused, named both remotes) |

Run 2 — the full install chain from the managed clone:

| Step | Exit | Detail |
|---|---|---|
| bootstrap | 0 | commit `19f56f9` |
| `mise trust <managed>/mise.toml` | 0 | explicit, on the reviewed path |
| `mise --locked install` | **0 in one run** | 104s, all **13** tools |
| `mise run check` | **0** | 326s, `Ran 694 tests in 325.447s` |
| `mise run bundle:install` | 0 | link mode |
| `mise run bundle:status` | 0 | `38 ok, 0 conflict, 0 absent` |
| `mise run operator-tools:install` | 0 | installed the then-current statusline + launcher set |

Reachability afterwards: the installed skill symlink resolved to
`/home/op/.local/share/agentic-sdlc/skills/agentic-sdlc` — i.e. into the managed
clone, exactly as the coupling analysis predicts — and the then-shipped `ocx-launch`
alias was reachable on PATH. This transcript predates ADR-0010's 2026-08-10
alias-retirement amendment; fresh installs now expose `ccodex` instead.

**One real finding, worth recording rather than smoothing over.** The first
container attempt used `debian:13-slim` *without* `unzip`, and
`mise --locked install` exited **1** on both the first and second run:

```
npm error Failed to set up chrome v151.0.7922.71!
npm error - DefaultProvider: Extraction failed: no zip archiver is available.
npm error   Install `unzip` (or tar.exe/Powershell on Windows), or add the optional `yauzl` dependency.
mise ERROR Failed to install npm:@mermaid-js/mermaid-cli@11.16.0: npm exited with non-zero status: exit code 1
```

This is **not** the npm ordering bug that `depends = ["node"]` already fixed:
npm 10.8.1 installed cleanly in the first pass, and 12 of 13 tools resolved. It
is puppeteer's postinstall — a transitive dependency of the advisory
`mermaid-cli` pin — requiring a zip archiver the slim image lacks. Adding
`unzip` took the same single run to exit 0 with all 13 tools. Anyone reproducing
a from-scratch install in a minimal container needs `unzip` present, or the
otherwise-advisory mermaid pin will fail the whole install command.

Images `agentic-sdlc-bootstrap-proof:local` and
`agentic-sdlc-bootstrap-proof2:local` were built for this run and removed
afterwards.

## 5. Verification of what this change adds

- `bash -n scripts/bootstrap-agentic-sdlc.sh` → 0.
- `uv run --python 3.12.11 --script scripts/validate_bundle.py` →
  `validate-bundle: 0 error(s), 0 warning(s)`. The new script needs no task
  registration: it is not a mise task, and `validate_scripts`
  (`validate_bundle.py:1543-1549`) already `bash -n`s every `scripts/*.sh`, so it
  is covered by the existing glob rather than a new entry in `REQUIRED_TASKS` or
  `TASK_COMMANDS`.
- The operator's `~/.claude`, `~/.config/mise`, and `~/.local/bin` were not
  mutated. Every local probe ran in `mktemp -d` sandboxes; every install ran
  inside the container.

This document records executed evidence about these runs only. It authorizes no
clone, fetch, config trust, toolchain install, push, publication, merge,
deployment, or other outward effect.
