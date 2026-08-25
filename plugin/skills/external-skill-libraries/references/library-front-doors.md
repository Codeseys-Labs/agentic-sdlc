# Library front doors (per-library invocation and its evidence)

Use this file when installing, updating, or removing one of the three third-party skill
libraries this bundle knows how to reach, or when a recorded fact about one needs
re-verifying. These three rows are the complete supported catalog: `mattpocock/skills`,
`affaan-m/ECC`, and hyperresearch. Unlisted libraries—including gstack—remain operator-owned
foreign state; this bundle has no install, status, migration, uninstall, adoption, or ownership
claim over them. Every invocation below was read out of the library's own README or registry
metadata rather than inferred — **a guessed flag is worse than a gap, because a guess runs.**
Re-read the upstream doc before editing any row here.

The tool is `scripts/install_external_libraries.py` (`libraries:list`, `libraries:install`,
`libraries:migrate`, `libraries:status`). It is dry-run by default, refuses without an explicitly
named library, and is reachable from no gate and no install task. Running a library's own
installer is not vendoring: no bytes enter this repository, so no `NOTICE` donor obligation
attaches.

**A README is a claim; the published artifact is the fact.** ECC's row below is the cautionary
case: its documented front door does not exist in what npm actually serves. Where the two
disagree, verify against the artifact — `npm view <pkg> bin`, the package's own `--help`, and a
`--dry-run` in a throwaway `HOME` — and record what you ran.

## mattpocock/skills

- **Front door:** `claude plugins install mattpocock-skills`
- **Evidence:** README, "Installation (30-second setup)" → "Claude Code". The same section
  states it is already in Claude Code's official marketplace — "there's nothing to add
  first" — true only once **at least one marketplace is configured**, which in practice means
  an authenticated Claude Code session with that marketplace already registered. Executed
  2026-08-20 on a logged-out Claude Code 2.1.238: `claude plugin marketplace list` prints "No
  marketplaces configured" at exit 0, and this door is not reachable from that state.
- **Second front door, printed by this tool but never invoked:**
  `npx -y skills@latest add mattpocock/skills --global --agent claude-code --skill '*' --yes`
  (the `bunx` variant drops npm's `-y`).
- **Uninstall:** `claude plugins uninstall mattpocock-skills`
- **Version:** 1.2.3 in both `package.json` and `.claude-plugin/plugin.json`; the repo's own
  `check-plugin-version` script keeps the two in sync.
- **Licence:** MIT.
- **Surface:** 25 skills, declared explicitly in `.claude-plugin/plugin.json`'s `skills`
  array. Note that the repository's `skills/` directory contains **category** directories
  (`engineering`, `productivity`, `misc`, `in-progress`, `deprecated`), not skills — counting
  those yields 5 and is wrong. `in-progress` and `deprecated` entries are not all declared in
  the plugin manifest, so the manifest is the authority on what installs.
- **Enumerate:**
  ```bash
  gh api repos/mattpocock/skills/contents/.claude-plugin/plugin.json --jq '.content' | base64 -d
  ```
- **Channel:** plugin, therefore namespaced. It cannot *lose* a name to another writer; its
  failure mode is duplication instead, which upstream names itself: "Pick one — installing
  both leaves you with every skill twice."
- **Alternative front door, deliberately not wired for installing:**
  `npx skills@latest add mattpocock/skills` writes editable flat files the operator owns. It is
  the channel that competes for flat names, and it prompts interactively for which skills and
  which agents to take, so it is not something to run non-interactively on someone's behalf.
- **Its removal path IS wired, for migration only.** When that channel already holds the names,
  `libraries:migrate -- mattpocock` retires them through the channel's own verb:
  ```bash
  npx -y skills@latest remove --global --agent claude-code --yes <names…>
  ```
  Evidence: `npx -y skills@latest remove --help` (skills CLI 1.5.22), plus its `removeCommand`
  source for the scoping behaviour below.
- **Provenance identifiers this channel records** (read from a real
  `~/.agents/.skill-lock.json`, schema `version: 3`): `source: "mattpocock/skills"`,
  `sourceType: "github"`, `sourceUrl: "https://github.com/mattpocock/skills.git"`,
  `pluginName: "mattpocock-skills"`, plus a `skillFolderHash` and timestamps. These are what
  `migrate` matches on; without a match it removes nothing.
- **Why `--agent claude-code` and not a bare `remove`:** a bare `remove --global` targets every
  agent in that CLI's registry. It deletes the canonical `~/.agents/skills/<name>`, every other
  agent's link to it, and the lock entry — verified against its source and in a fixture home.
  Scoped to one agent it removes only `~/.claude/skills/<name>`; the canonical copy, the other
  hosts' links, and the lock entry survive, so the change is narrow and re-linkable.
- **Lock path resolution:** `$XDG_STATE_HOME/skills/.skill-lock.json` when that variable is set,
  otherwise `~/.agents/.skill-lock.json`. A lock at a schema version below 3 is discarded by the
  CLI's own reader, so it must not be credited as provenance here either.
- **Its own post-install step:** `/setup-matt-pocock-skills`, once per repository. It asks for
  an issue tracker, triage labels, and a docs location.

## affaan-m/ECC

- **Front door:**
  ```bash
  npx -y -p ecc-universal ecc install --target claude --profile full
  ```
- **The README's front door does not exist in the published artifact.** `npx ecc-universal setup`
  fails with npm's "could not determine executable to run", and it always will: the 2.1.0
  tarball's `package.json` declares bins `ecc`, `ecc-control-pane`, `ecc-install`,
  `ecc-memory-mcp`, and `ecc-plan-canvas` — **no `ecc-universal` bin** — and `ecc`'s own command
  table has no `setup` verb. `-p ecc-universal ecc` is therefore required: it names the package
  and the real bin separately. This is independent of the version question below; fixing the
  version alone would not make `setup` appear.
- **Evidence:** `npm view ecc-universal bin`, the tarball's own `package.json`, `ecc --help`'s
  command table, and `ecc install --help`'s usage block — all read from the artifact npm serves.
  `--profile` (or `--modules`/`--with`/`--config`) is **mandatory**: given none, the CLI exits
  "No install profile, module IDs, included components, or legacy languages were provided".
- **Uninstall:** `npx -y -p ecc-universal ecc uninstall --target claude`, which "remove[s]
  ECC-managed files recorded in install-state for the current context" and supports `--dry-run`.
  This *is* wired — the earlier "repo-local only, needs a clone" record described the repository's
  `scripts/uninstall.js`, but the published artifact ships that verb behind its own CLI. Its
  README still notes a plugin install must be removed through Claude Code separately.
- **Version — an accepted caveat, not a block.** npm `latest` serves **2.1.0** while ECC's README
  documents guided commands requiring "2.2.0 or newer". The operator accepted npm `latest`
  (ADR-0009 amendment, 2026-08-07), so this no longer refuses. It is **not** dropped: it prints as
  a `caveat:` line on every plan and in `list`, and because the documented entrypoint may be
  absent from the fetched artifact, a nonzero front-door exit is reported as a failed install
  rather than assumed to be a finished one.
- **Licence:** MIT (verified in npm metadata and the README's own statement).
- **Surface:** **284** declared; **280** measured as distinct flat skill names in the resolved
  `full` plan. The whole plan is 983 file operations: 280 skills, 67 agents, 94 commands, 122
  rules files, 170 scripts, 2 hooks. The 67/94 figures match upstream's self-report exactly.
- **Enumerate — use its own dry run, not a directory listing.** The plan reflects the *resolved
  profile*; the repository's `skills/` tree is the whole catalogue and overcounts what a given
  profile installs:
  ```bash
  npx -y -p ecc-universal ecc install --target claude --profile full --dry-run --json
  ```
  Every operation carries a `destinationPath`; the flat skill names are the distinct
  `\.claude/skills/([^/]+)/` captures. `libraries:list` prints the full extraction one-liner.
  `ecc catalog profiles --json` lists the seven profiles offline (`minimal`, `opencode`, `core`,
  `developer`, `security`, `research`, `full`) and `ecc catalog components` their modules.
- **Channel:** flat. The plan's own destinations confirm `~/.claude/skills/<skill-name>/` — the
  same single namespace this bundle's own 10 entries occupy — so all of those names are
  first-writer-wins claims. It also writes `~/.claude/.agents/skills/` (39 names, 38 of them
  duplicating its flat set).
- **Gated behind one flag:** `--acknowledge-ecc-surface`, which is about **cost**. The surface
  still cannot be enumerated without running its front door, so `--names-from <file>` remains
  available and is the only way to get a real comparison; without it the plan reports
  `precheck: SKIPPED, not passed` rather than silently reading as clean.
- **A measured collision, as an example of why the precheck matters:** against a real home, the
  280 names collided on exactly one — `benchmark`, held by an unrelated local skill with no lock
  entry. Unattributable, so not migratable, and a correct refusal.
- **Its own warning, worth repeating:** "Do not stack install methods. Installing ECC twice
  into the same harness can duplicate skills, commands, hooks, or configuration."
- Its README also names official-source verification as a supply-chain concern of its own,
  listing the repository, the `ecc-universal` and `ecc-agentshield` npm packages, its GitHub
  App, the `ecc@ecc` plugin slug, and its website as the only channels it maintains.

## hyperresearch

- **Front door:** `uv tool install hyperresearch`
- **Evidence:** the PyPI README documents `pip install hyperresearch && hyperresearch install`.
  `uv tool` is substituted for `pip` deliberately: `uv` is already a pinned tool in this
  repository, so using it adds **no bootstrap prerequisite**, and a tool install keeps the CLI
  off whatever ambient interpreter happens to be first on PATH.
- **Uninstall:** `uv tool uninstall hyperresearch` removes the CLI **only**. There is no
  `uninstall` verb on the CLI itself (confirmed: it errors "No such command 'uninstall'"), so
  files its `install` verb already rendered into a home or a project stay where they are.
- **Version:** 0.10.0 on PyPI. `requires-python >=3.11,<3.14` — 3.14 is explicitly not
  supported yet.
- **Licence:** MIT (`license_expression: MIT`), Jordan Gibbs.
- **Surface:** 17 skills and 16 agent files when installed globally. Installing the *tool*
  writes none of them.
- **It is a renderer, not a library.** The CLI's own `install` verb does the writing:
  - `hyperresearch install [PATH]` — per-project: vault init, `CLAUDE.md` injection, hooks.
  - `hyperresearch install --global` — "Install Claude Code entry skill + agents to
    `~/.claude/` so `/hyperresearch` works in every Claude Code session anywhere. Skips vault
    init, CLAUDE.md, and the 16 step skills (those happen per-project on first
    `/hyperresearch` run)."
  - `--steps-only` writes the 16 step skills to `<PATH>/.claude/skills/` and is documented as
    internal, "Not normally invoked by users."
- **Enumerate:** `hyperresearch install --help` documents the destinations; the rendered names
  are all `hyperresearch`-prefixed.
- **Channel:** flat, but every name carries the `hyperresearch` prefix, so its collision
  surface against this bundle is **structurally** empty rather than merely observed to be
  empty. An occupied `hyperresearch*` name is its own earlier install being refreshed, and the
  precheck reads it that way rather than as a foreign occupant.
- **Why its output must never be vendored:** its rendered agent files carry static `model:`
  frontmatter, which `scripts/validate_bundle.py` rejects for agent files. That is a reason
  not to copy its output into this repository. It is **not** a reason to refuse to run its
  renderer in an operator's home, where this repository's validator has no jurisdiction.
- The README's own upstream benchmark claim ("currently leads the DeepResearch-Bench RACE
  leaderboard (benchmarked internally)") is a vendor claim with third-party validation
  described as pending. Record it as the vendor's, never as measured here.

## Rules that apply to every row

- **Dry run first, always.** The default prints the exact command, its working directory, the
  version, the destination, and the skill count. `--yes` is the only way anything runs — for
  `migrate` too, which additionally prints the exact removal command and the exact names.
- **Fail closed with a named reason.** A missing front-door tool, a refused precheck, a
  network failure, and an unexpected version each stop that library by name. Nothing retries,
  because a network failure and a refused install exit the same way and mean different things.
- **Verify the artifact, not the README.** A documented command that the published package does
  not expose is a guaranteed failure wearing the costume of a recorded fact. Check
  `npm view <pkg> bin`, run the CLI's own `--help`, and prefer the tool's own `--dry-run` output
  over any hand-maintained list.
- **Removal happens only through the owning channel's own verb.** This tool contains no
  deletion primitive at all — no `rm`, no `unlink` — and removes a name only when the other
  channel's own record proves it is the same upstream. Anything unproven is left alone.
- **No credential ever.** Nothing here reads, writes, stores, forwards, or accepts a token. A
  front door needing authentication is the operator's to authenticate separately.
- **No network trust claim.** The tool makes no request of its own; the front-door subprocess
  does, under its own package manager's integrity model. No tarball, signature, or transitive
  dependency is verified here.
- **A successful install is evidence, not authorization.** It authorizes no push, no
  publication, no merge, no deployment, and no further install.
