# Library front doors (per-library invocation and its evidence)

Use this file when installing, updating, or removing one of the three third-party skill
libraries this bundle knows how to reach, or when a recorded fact about one needs
re-verifying. Every invocation below was read out of the library's own README or registry
metadata rather than inferred — **a guessed flag is worse than a gap, because a guess runs.**
Re-read the upstream doc before editing any row here.

The tool is `scripts/install_external_libraries.py` (`libraries:list`, `libraries:install`,
`libraries:status`). It is dry-run by default, refuses without an explicitly named library,
and is reachable from no gate and no install task. Running a library's own installer is not
vendoring: no bytes enter this repository, so no `NOTICE` donor obligation attaches.

## mattpocock/skills

- **Front door:** `claude plugins install mattpocock-skills`
- **Evidence:** README, "Installation (30-second setup)" → "Claude Code". The same section
  states it is already in Claude Code's official marketplace — "there's nothing to add
  first" — so there is deliberately **no** `marketplace add` step to run.
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
- **Alternative front door, deliberately not wired:** `npx skills@latest add mattpocock/skills`
  writes editable flat files the operator owns. It is the channel that competes for flat
  names, and it prompts interactively for which skills and which agents to take, so it is not
  something to run non-interactively on someone's behalf.
- **Its own post-install step:** `/setup-matt-pocock-skills`, once per repository. It asks for
  an issue tracker, triage labels, and a docs location.

## affaan-m/ECC

- **Front door:** `npx ecc-universal setup`
- **Evidence:** README, "Install ECC" → "Guided setup (recommended)". The multi-harness form
  is `npx ecc-universal install --guided`; other runners are documented as `pnpm dlx`,
  `yarn dlx`, and `bunx` against the same package.
- **Uninstall:** repo-local only — `node scripts/uninstall.js --dry-run`, then without the
  flag — which needs a clone of the repository, so no uninstall front door is wired.
  Its README also notes the plugin install must be removed through Claude Code separately.
- **Version:** npm `latest` serves **2.1.0**; the repository is at 2.2.0. This matters
  because ECC's own install section says the guided commands "require `ecc-universal` 2.2.0
  or newer" — so the documented front door is **newer than the published artifact**, and
  `setup` is not known to exist in what npm would actually fetch. This is a standing block,
  independent of surface cost, and it clears when npm publishes 2.2.0.
- **Licence:** MIT (verified in npm metadata and the README's own statement).
- **Surface:** **284** skills (`gh api repos/affaan-m/ECC/contents/skills --paginate` returns
  284), plus a self-reported 67 agents and 94 legacy command shims.
- **Enumerate:**
  ```bash
  gh api repos/affaan-m/ECC/contents/skills --paginate --jq '.[].name'
  ```
- **Channel:** flat. Its manual install "place[s] each skill directly under
  `~/.claude/skills/<skill-name>/`" — the same single namespace this bundle's own 9 entries
  occupy — so all 284 names are first-writer-wins claims.
- **Gated behind two flags:** `--acknowledge-ecc-surface` **and** `--names-from <file>`. The
  second is not bureaucracy: 284 names cannot be enumerated without network, and a precheck
  that cannot run must not report a pass.
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
- **Surface:** 17 skills and 14 agent files when installed globally. Installing the *tool*
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
  version, the destination, and the skill count. `--yes` is the only way anything runs.
- **Fail closed with a named reason.** A missing front-door tool, a refused precheck, a
  network failure, and an unexpected version each stop that library by name. Nothing retries,
  because a network failure and a refused install exit the same way and mean different things.
- **No credential ever.** Nothing here reads, writes, stores, forwards, or accepts a token. A
  front door needing authentication is the operator's to authenticate separately.
- **No network trust claim.** The tool makes no request of its own; the front-door subprocess
  does, under its own package manager's integrity model. No tarball, signature, or transitive
  dependency is verified here.
- **A successful install is evidence, not authorization.** It authorizes no push, no
  publication, no merge, no deployment, and no further install.
