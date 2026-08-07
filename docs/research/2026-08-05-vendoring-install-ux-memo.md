# Vendoring + Install-UX Synthesis Memo

> **CORRECTION, 2026-08-07 — this memo's LICENSE/NOTICE prerequisite is SATISFIED. Do not
> re-derive it as a blocker.** §4's "License — blocks backlog #7–#10, #13 today" and the
> 2026-08-06 banner's closing "Still true: this repo has no `LICENSE`/`NOTICE` and declares
> `"license": "UNLICENSED"`" are both now stale. Verified in this working tree:
>
> - A root **`LICENSE`** (MIT) and a root **`NOTICE`** (343 lines, a per-donor provenance
>   register with a re-resolved commit, the grant reproduced where required, the origin
>   question answered separately from the licence question, and a what-is / what-is-not-derived
>   pair per donor) both exist.
> - **`.claude-plugin/plugin.json:8` now declares `"license": "MIT"`**, not `UNLICENSED`.
> - `NOTICE` carries its own **"Adding a donor to this file"** checklist, so the attribution
>   surface this memo asked for is not just present but has a documented entry procedure.
> - The decision behind it is recorded at
>   `docs/adr/0001-mit-license-and-root-notice-attribution.md`, which cites this memo's §4 as
>   the finding that forced it.
>
> Two naming/scope notes for anyone diffing this memo against the tree: the file landed as
> **`NOTICE`**, not as the `THIRD-PARTY-NOTICES.md` this memo named, and the register is
> currently **intra-family only** — it records pi-lab-family donors, and no third-party donor
> entry exists yet. The prerequisite is satisfied; it has simply never been exercised on a
> third-party donor.
>
> **Commit provenance, stated honestly.** The landing commit was reported to this pass as
> `01e1437`; that object does **not** resolve in this checkout (`git cat-file -t 01e1437` →
> "Not a valid object name"), and no sibling checkout or worktree resolves it either. In this
> repository's history the landing commit is **`043bd42`** — *"docs: add MIT LICENSE, NOTICE
> provenance register, and the first four ADRs"* — whose message states plainly that
> "plugin.json licence field corrected from UNLICENSED". Treat `01e1437` as a hash from a
> different (probably rebased) commit line for the same change, and cite `043bd42` when
> working from this checkout.
>
> **What this does NOT unblock.** The prerequisite being satisfied does not make this memo's
> vendoring backlog live. `docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md`
> decides the general question separately and on three grounds that have nothing to do with
> licensing: the four-gate proportionality test, ADR-0002's single-bootstrap-prerequisite rule,
> and the mechanical name-collision fact. A library the operator wants is the operator's own
> install; foreign material enters only as an adapted `references/*.md` plus a `NOTICE` donor
> entry. Read that record before reviving any row in §1's table.
>
> One more §4 blocker is also closed, recorded here for the same reason: **"Gate gap: skills
> are not model-pin-checked"** no longer holds. `validate_skills` in
> `scripts/validate_bundle.py` now parses skill frontmatter semantically and errors with
> `static model is forbidden` / `static model_reasoning_effort is forbidden`, matching what
> `validate_agents` already did for agent files.

> **CORRECTION, 2026-08-06 — the ECC licensing blocker in this memo is WRONG.** The later
> restructure judge concluded "ECC: no resolvable license on any candidate repo. Not
> redistributable. USER DECISION, blocking." pi-lab had already resolved this in
> `pi-lab/docs/research/20260727/ecc-everything-claude-code.md`, and I verified it against the
> live GitHub API:
>
> - Canonical repo is **`affaan-m/ECC`** (public, 238k stars-equivalent metric returned by the
>   API field), formerly `affaan-m/everything-claude-code`, which now 301-redirects to it —
>   which is why a search for the old name looked unresolvable.
> - **License: MIT.** `gh api repos/affaan-m/ECC --jq .license.spdx_id` → `MIT`, and a real
>   `LICENSE` file (1071 bytes) exists at pi-lab's independently pinned commit
>   `6a9f075cd97c139a5f7e84e1e3f2c9ab095adf64`.
>
> **ECC is redistributable with attribution.** It is not a user decision and not blocking. The
> lesson is procedural: pi-lab's research corpus had already answered this with executed
> evidence, and both of this repo's memos re-derived it wrongly by not consulting it. Check
> `pi-lab/docs/research/` before declaring an external source unresolvable.
>
> Still true: **this repo has no `LICENSE`/`NOTICE` and declares `"license": "UNLICENSED"`**, so
> attribution has nowhere to land yet. That is the real prerequisite, not ECC's license.

**Judge pass over 3 library harvests + 1 mise remote-install report with adversarial verification.** Target: `<repo>` @ `ada5ecd` on `release/offline-observer-rc`. Where the verifier refuted the researcher, the verifier wins. Where I could execute a check locally, I did — several claims on both sides changed.

## 0. Three facts that reframe everything below

**(a) The repo is private and has zero releases.** `gh api repos/Codeseys-Labs/agentic-sdlc` → `{"private":true,"visibility":"private","license":null}`; `git ls-remote --tags origin` → empty; `gh release list` → empty; only two remote heads (`main`, `feat/mise-cross-host-installer`). Every "one command from a fresh machine" design in the mise report assumes an anonymous public fetch. None of them work today without either flipping visibility or shipping credentials. This is the single largest gate on the user's stated goal and neither the researcher nor the verifier noticed it.

**(b) `claude plugin validate --strict .claude-plugin/plugin.json` exits 1 right now.** Executed locally:
```
plugin strict exit=1     marketplace strict exit=0
```
Two warnings, both real: `root: CLAUDE.md at the plugin root is not loaded as project context` and `agents/codex/research/README.md: No frontmatter block found`. `README.md:130` claims *"Both manifests pass `claude plugins validate --strict`"* — that claim is currently false. This makes ECC's `PLUGIN_SCHEMA_NOTES.md` the #1 steal, not a nice-to-have.

**(c) The mattpocock skill names are already occupied on this machine, by symlink, in the exact destination the installer writes to.** `<claude-home>/skills/tdd -> ../../.agents/skills/tdd` — and 8 more (`code-review`, `codebase-design`, `diagnosing-bugs`, `domain-modeling`, `grilling`, `prototype`, `research`, `resolving-merge-conflicts`), all pointing into a 23-dir `npx skills`-managed tree at `<agents-home>/skills/`. `scripts/install_skill_bundle.py:767-783` writes `skills/<dirname>` → `~/.claude/skills/<dirname>`, and its ownership logic classifies a non-owned link as `foreign` (`:1494-1520`) and preserves it. So vendoring any of those names as `skills/tdd/SKILL.md` doesn't shadow — **it hard-blocks the install of that entry.** The harvest reports called this a hypothetical precedence question; it is a mechanical conflict. Consequence: mattpocock content goes into `skills/agentic-sdlc/references/*.md`, never `skills/<name>/`.

---

## 1. Vendoring backlog (ranked, deduped across all three libraries)

Effort: **copy** = near-verbatim + attribution; **adapt** = restructure/de-couple; **reimplement** = pattern only, fresh text.

| # | Item | Source (exact) | Target in agentic-sdlc | Effort | Changes needed | Value | License |
|---|---|---|---|---|---|---|---|
| 1 | Plugin-manifest quirks doc | ECC `.claude-plugin/PLUGIN_SCHEMA_NOTES.md` (blob `61859c5d`, https://github.com/affaan-m/ECC) | `.claude-plugin/MANIFEST_NOTES.md` | reimplement | Record *our own* observed validator output (fact 0b), not ECC's history. Then either fix the two warnings or delete the false claim at `README.md:130`. Wire `claude plugin validate --strict` on both manifests into `scripts/validate_bundle.py` so it can't regress. | **high** — the install surface is currently broken-and-documented-as-passing | pattern only, no text copied |
| 2 | Single canonical install text | mattpocock `.agents/install-block.md` (blob `8971bde2`) | new `docs/install-block.md`, quoted verbatim by `README.md:141-296` + `AGENTS.md:100-130` | reimplement | Collapse ~180 lines of install prose spread across README + AGENTS into one authoritative block; every other surface quotes it. Directly serves "simplest possible install UX". | **high** | pattern only |
| 3 | Skill-authoring doctrine | mattpocock `skills/productivity/writing-for-agents/SKILL.md` (`c059d48c`) + `SKILL-MECHANICS.md` (`c28e3bf0`) | `skills/agentic-sdlc/references/skill-authoring.md` — **merge with** the pi-lab `skill-authoring-standard` item already ranked #6 in `docs/research/2026-08-05-pi-lab-harvest-memo.md:51` | adapt | De-Pocock the first person; drop `disable-model-invocation` mechanics into a host-specific subsection (it is a Claude/Pi frontmatter key, not Agent-Skills-universal). Do **not** ship as a top-level skill — it fails its own admission test. One reference, not two. | **high** — best authoring artifact in all three libraries | MIT; paraphrase + `NOTICE` entry |
| 4 | Mechanical tool-allowlist lock for advisory roles | hyperresearch `~/.claude/agents/hyperresearch-patcher.md:12` → `tools: Read, Edit` (verified locally); polish-auditor, synthesizer same shape | `agents/claude/sdlc-reviewer.md:4-8`, `agents/claude/sdlc-critic.md:4-7` | adapt | `sdlc-reviewer.md` declares *"never edits code"* yet holds `Bash` alongside `Read/Glob/Grep`. `sdlc-critic.md` is already clean (`Read, Glob, Grep`). Drop `Bash` from reviewer or justify it in-file; add explicit `disallowedTools` per the pi-lab dual-declaration finding (`pi-lab-harvest-memo.md:63`). | **high** — upgrades prose doctrine to enforced doctrine | pattern only |
| 5 | Install-state records **intent**, + `doctor`/`repair` split | ECC `scripts/doctor.js` (`80505d3f`), `scripts/auto-update.js` (`284e532c`), `scripts/lib/install-lifecycle.js` | `scripts/install_skill_bundle.py` state schema (`STATE_VERSION = 3`, `:28`) + new `bundle:doctor` / `bundle:repair` mise tasks | adapt | Persist the invoked `--agent`/plane args, not just per-entry ownership, so `repair` can replay. Diagnose-only must not mutate (ECC's cleanest idea). Needs new cases in `tests/` mirroring `mise run self-test`. Do **not** port the JS. | **high** — this is the "scalable update path" the user asked for | pattern only (ECC is MIT; implementation is Python here) |
| 6 | Reviewer anti-noise gate | ECC `agents/code-reviewer.md` (`884d94ec`) — verified sections: `### Pre-Report Gate` (L39), `### It Is Acceptable And Expected To Return Zero Findings` (L66), `## Common False Positives - Skip These` (L76) | `agents/claude/sdlc-reviewer.md`, `agents/claude/sdlc-critic.md` | adapt | Paraphrase the 4-question gate + skip-list; ECC's imperative voice clashes with this repo's advisory-submission framing. "Zero findings is a valid review" already aligns with `AGENTS.md`'s advisory-verdict doctrine. | **high** | MIT; paraphrase + `NOTICE` |
| 7 | TDD reference | mattpocock `skills/engineering/tdd/SKILL.md` (`ead7781d`) | `skills/agentic-sdlc/references/tdd.md` — **not** `skills/tdd/` (fact 0c) | adapt | Strip frontmatter entirely (it becomes a reference, not a skill). Keep the tautological-test rule (expected values must come from an independent source of truth). Point `agents/claude/sdlc-implementer.md` at it. | high | MIT verbatim-ok → **needs `NOTICE` first** (see §4) |
| 8 | Feedback-loop-first debugging | mattpocock `skills/engineering/diagnosing-bugs/SKILL.md` (`f400de7c`) | `skills/agentic-sdlc/references/debugging-loop.md` | adapt | Same de-skilling pass. Zero coverage in this repo today. The red-capable/deterministic/fast/agent-runnable checklist is the asset. | high | MIT + `NOTICE` |
| 9 | Two-axis diff review + Fowler smell baseline | mattpocock `skills/engineering/code-review/SKILL.md` (`62a18e4c`) | fold into `agents/claude/sdlc-reviewer.md` Method section | adapt | **Must strip** the hard dep at its L13/L29 on `docs/agents/issue-tracker.md` (written by `setup-matt-pocock-skills`) — this repo's spec source is Seeds + the plan/ADR, per `sdlc-reviewer.md:3`. Keep the Fowler baseline (cites *Refactoring* ch.3, generically valid). | medium-high | MIT + `NOTICE` |
| 10 | Merge-conflict hunk discipline | mattpocock `skills/engineering/resolving-merge-conflicts/SKILL.md` (`aadb3fcb`) | subsection of `skills/agentic-sdlc/references/worktree-integration.md` (79 lines today) | copy | Trivial. Complements — does not duplicate — the fan-in mechanics in `references/seeds-worktrees.md`. The never-`--abort` rule is a real guardrail for a rebase-heavy wave loop. | medium-high | MIT + `NOTICE` |
| 11 | MCP-connector budget rubric | ECC `docs/MCP-CONNECTOR-POLICY.md` (`80fb5666`) | `skills/agentic-sdlc/references/mcp-connector-policy.md` | adapt | Two-part test (universal + MCP genuinely beats CLI/skill) calibrated to this env's ~75 ToolSearch-deferred tools. Don't copy ECC's server list. | medium | pattern only |
| 12 | User-invoked-only frontmatter for destructive surfaces | mattpocock `SKILL-MECHANICS.md` (`disable-model-invocation: true`) | `commands/sdlc-init.md`, any future reset/deactivate command | adapt | Zero uses in this repo (`rg disable-model-invocation` → only a mention in `docs/research/...:96`). Host-specific: gate it behind a Claude-plane note so it doesn't leak into the host-agnostic contract. | medium | pattern only |
| 13 | Git-destructive-op PreToolUse hook | mattpocock `skills/misc/git-guardrails-claude-code/SKILL.md` (`d943c682`) | optional step in `commands/sdlc-init.md` | adapt | Blocks `git push`, `reset --hard`, `clean -f`, `branch -D`, `checkout .` before execution — a working enforcement of a policy this repo states only in prose. **Claude-Code-only**; must be presented as an optional per-repo activation, never a bundle default. | medium | MIT + `NOTICE` |
| 14 | Holistic skill-quality audit | ECC `skills/skill-stocktake/SKILL.md` (`6f207320`) | possible `mise run stocktake` (advisory, never in `tasks.check`) | reimplement | `scripts/validate_bundle.py:386-400` covers structure (name==dirname, ≤1024 desc, broken refs) but nothing judges quality. Low urgency at 8 skills. | low-medium | pattern only |
| 15 | Router-skill + fresh-loaded numbered step-skills | hyperresearch `~/.claude/skills/hyperresearch*/SKILL.md` (17 files verified locally: router + `1-decompose` … `16-readability-audit`) | — | **skip (audited, not needed)** | `skills/agentic-sdlc/SKILL.md` is 196 lines with 1,139 lines already disclosed across 11 `references/*.md`. That *is* progressive disclosure; the context-rot failure mode hyperresearch's V7→V8 changelog describes applies to monolithic skills, which this isn't. Revisit only if a phase measurably gets dropped. | low | n/a |
| 16 | Selective profile/module install manifests | ECC `manifests/install-profiles.json` (`15e42994`; verified: `minimal`/`opencode`/… → module lists) | — | **skip** | 8 skills, and `--agent claude|codex` is already the only axis anyone asks for. A profile→module→component manifest chain for 8 skills is pure overhead. Reconsider past ~25 skills. | low | n/a |
| 17 | hyperresearch rendered skills/agents (17 + 14 files) | `<claude-home>/skills/hyperresearch*/`, `<claude-home>/agents/hyperresearch-*.md` | — | **do not vendor** | Three independent blockers: (i) they are Jinja output — `<< p.models.X >>` / `{hpr_path}` resolved at install time, so a snapshot freezes one profile's knobs as static doctrine; (ii) `hyperresearch-patcher.md:11` carries `model: opus`, which `scripts/validate_bundle.py:1041` rejects outright (`static model is forbidden`) for agent files; (iii) upstream self-declares as a Claude-Code-only harness, inverting this bundle's cross-host `AGENTS.md` routing. | — | MIT, but structurally incompatible |
| 18 | hyperresearch CLI as a mise-pinned tool | PyPI `hyperresearch` 0.10.0 (verified live; local `uv tool list` → 0.8.6) | — | **skip as a `[tools]` pin** | `pipx:` is **version-only** in the lockfile (`jdx/mise@main:docs/dev-tools/mise-lock.md:329` — "📝 **Version only**: `asdf`, `npm`, `cargo`, `pipx`"), so it cannot be checksum-pinned under `mise.toml:4 locked = true` doctrine, and it drags crawl4ai + headless Chromium + pymupdf. `agents/claude/sdlc-researcher.md:48-50` already handles it correctly as an optional host-provided capability — no change needed. | low | MIT (as external dep) |
| 19 | Profile/gear render-at-install-time (pydantic `ModelMap`) | hyperresearch `hyperresearch/core/{profiles,render,hooks}.py` | — | **skip — doctrine downgrade** | Its `ModelMap` emits host aliases (`sonnet`/`opus`) with no receipt, no readback, no resolved/inherited/unresolved distinction. Adopting it without a RuntimeAssignment layer on top would move backwards from `policy/runtime-assignment-normative-contract-v1.json`. | low | n/a |
| 20 | `domain-modeling` + `codebase-design` | mattpocock `skills/engineering/{domain-modeling,codebase-design}/SKILL.md` | — | **defer** | Both presume a repo-wide `CONTEXT.md` glossary + `docs/adr/` convention this repo has not adopted. That's a doctrinal decision, not a vendoring decision. Also name-collides per fact 0c. | low | MIT |
| 21 | `wayfinder` / `to-spec` / `to-tickets` / `triage` | mattpocock `skills/engineering/*` | — | **skip** | All hard-depend on `docs/agents/issue-tracker.md` from `setup-matt-pocock-skills`, and their job — dependency-ordered decomposed backlog — is what Seeds already is. Vendoring them installs a second, competing queue-of-record. | low | MIT |
| 22 | ECC `hooks/hooks.json` inline `node -e` bootstrap | ECC `hooks/hooks.json` | — | **explicit anti-pattern; do not copy** | The plugin-root-resolution *problem* is real prior art if this bundle ever ships hooks; the inline-eval-in-JSON *implementation* is not. Reimplement as a named script. | — | n/a |

**Dedupe flags:**
- **hyperresearch ↔ `skills/codex-research-os/`** — genuine overlap (parallel research roles, evidence grading, review gates; 17 role TOMLs at `agents/codex/research/`). Flagged only, per instructions: a separate workflow is redesigning research-os. Item #18's "don't pin it" verdict holds regardless of how that lands.
- **#3 ↔ pi-lab `skill-authoring-standard`** (`docs/research/2026-08-05-pi-lab-harvest-memo.md:51,96`) — same destination file. Merge into one `references/skill-authoring.md`; do not land twice.
- **#6 ↔ mattpocock `code-review` (#9)** — both target `sdlc-reviewer.md`. Land #6 (gate + skip-list) first, then #9 (two axes + Fowler) as a second section; they compose.
- **#5 ↔ pi-lab receipt-vouching** (`pi-lab-harvest-memo.md:52`) — same state file. Any intent field added by #5 must be re-derived from the current reviewed manifest, never trusted from the receipt.

**Blocking prerequisite for #7–#10, #13 (and #3/#6 if any text survives paraphrase):** see §4 — the license gap.

---

## 2. Install-UX design

### Recommended: **committed mise bootstrap script + pinned-tag clone, plus the Claude marketplace as an independent second plane**

The verifier killed Design 1 (npm ad-hoc: root `postinstall` executes by default off-repo but is `--ignore-scripts`-suppressed inside this repo because `mise.toml:5` sets `npm.package_manager = "npm"` → opposite semantics for the same one-liner; plus `npm:` carries no lockfile checksum, confirmed at `mise.lock:158-160`) and Design 2 (`mise x github:… -- ./bin/install` — `./bin/install` resolves against the caller's CWD not the extracted tool store; `@v0.5.14` is the wrong pin form since mise strips the `v`; and it installs no uv/Python, so it cannot reach a working bundle). Both refutations hold. Design 4 is rejected, and the verifier is right about *why*: HTTP remote task files are **stable**, not experimental (`jdx/mise@main:docs/tasks/toml-tasks.md`) — reject them for being unchecksummed download-and-execute with a stale-tolerant cache, not for an experimental badge, or the next reviewer "fixes" it by switching forms.

That leaves the verifier's corrected Design 3, which I'm upgrading with something neither report found: **`mise generate bootstrap` embeds static per-platform SHA-256 checksums for the pinned mise version.** Executed locally with `--version 2026.4.27` (matching `mise.toml:1 min_version`), the generated script contains e.g. `checksum_linux_x86_64="54b838beaeb9a16e6fbfa4e1a410205e2493a87f7b71e09273d6d4d12638b1aa ./mise-v2026.4.27-linux-x64.tar.gz"` for all 17 platform/compression variants. Committing that script removes mise itself from the prerequisite list while *strengthening* provenance — the checksums are reviewed-in-tree, not fetched.

**Fresh machine → installed bundle (needs only `git` + `curl` + repo access):**
```bash
git clone --depth 1 --branch v0.7.2 https://github.com/Codeseys-Labs/agentic-sdlc.git ~/src/agentic-sdlc
cd ~/src/agentic-sdlc
MISE_PARANOID=1 mise trust ./mise.toml     # explicit, after reading it — never auto
MISE_PARANOID=1 ./bootstrap.sh run bundle:install
MISE_PARANOID=1 ./bootstrap.sh run bundle:status
```
`bootstrap.sh` = `mise generate bootstrap --version 2026.4.27 --write bootstrap.sh`, regenerated by `scripts/bump-version.sh` whenever `min_version` moves.

**Update path (same shape, replayable):**
```bash
cd ~/src/agentic-sdlc && git fetch --tags && git checkout v0.7.3
MISE_PARANOID=1 mise trust ./mise.toml     # paranoid hashes contents: a changed mise.toml re-prompts, by design
MISE_PARANOID=1 ./bootstrap.sh run bundle:install
```
With backlog item #5 landed, the second line becomes `bundle:repair` and replays the recorded plane/agent intent instead of re-deriving it.

**Second plane, Claude only — and it does work on a private repo:**
```
/plugin marketplace add git@github.com:Codeseys-Labs/agentic-sdlc.git#v0.7.2
/plugin install agentic-sdlc@agentic-sdlc
```
SSH URLs and `#<ref>` are both documented accepted forms of `/plugin marketplace add` (https://code.claude.com/docs/en/discover-plugins), and they use the operator's own git credentials — so this is the *only* path that reaches a private repo today with zero extra machinery. For byte-exact pinning, `.claude-plugin/marketplace.json` supports `source: {source: "url", url: …, ref: …, sha: …}` with sha as the effective pin (https://code.claude.com/docs/en/plugin-marketplaces). That is exactly how Anthropic's own catalog pins third parties — verified in `anthropics/claude-plugins-official@.claude-plugin/marketplace.json`, entry `mattpocock-skills`: `"source":{"source":"url","url":"https://github.com/mattpocock/skills.git","sha":"8b36d4fb2635b3c21998dcd8144439c9e5ba7302"}`.

`AGENTS.md`'s "for Claude, use either direct install or the marketplace, never both" stays intact: mise serves Codex/Gemini/OpenCode + the authoritative gate; the marketplace serves Claude-only convenience. Two planes, documented as mutually exclusive **for the Claude plane only**, per the existing rule.

### Why this survives the verifier and the repo's fail-closed doctrine

- **CI auto-trust hole closed.** `jdx/mise@main:docs/paranoid.md`: *"When mise detects that it is running in CI, configs are assumed to be trusted unless paranoid mode is enabled."* A bare `git clone && mise run bundle:install` one-liner in CI silently auto-trusts a just-downloaded `mise.toml` and executes its task. `MISE_PARANOID=1` on every line is load-bearing, not decoration — and the researcher's claim that Design 3 has "zero new trust surface" was wrong until it was added. Confirmed live: `mise trust --show` → `~/DevBox/custom-pi-setup/agentic-sdlc: untrusted`, and an untrusted-config error is exactly what a `bump-version.sh --check` attempt produced this session.
- **No experimental features.** `mise.toml` sets only `locked`/`npm.package_manager`; nothing here adds an `experimental` opt-in. `git::` task includes stay untouched.
- **No new backend, no new integrity tier.** The payload *is* the reviewed git tree, verified by tag + the pinned `mise.lock` (44 checksum entries across 11 platform keys) it already carries. Nothing is fetched through a backend that records version-only.
- **`locked = true` risk sidestepped.** The verifier's unresolved D3 (does `locked = true` fail-close an ad-hoc `mise x <backend>:…`?) never arises, because there is no ad-hoc `mise x` of an unlocked tool in this design. That open question stays open and stays harmless.
- **Deprecated primitive avoided.** `ubi:` is deprecated upstream (`jdx/mise@main:docs/dev-tools/backends/ubi.md`: *"The ubi backend is **deprecated**. Please use the GitHub backend instead."*). Not used.
- **Per-host planes preserved.** WSL and native Windows remain separate lifecycle planes; `bundle:install:all-hosts` (`mise.toml:56`) still reports them separately. No one-liner claims a cross-host install.

### Runner-up: `http:` tool-stub of a CI-attested release tarball

The verifier's alternative recommendation, and it is the right *eventual* answer — `http:` has full lockfile support (version + checksum + size + URL, `mise-lock.md:324`), needs no release-tag/`version_prefix` archaeology, runs no install scripts, and `mise generate tool-stub` produces a checked-in, checksum-pinned executable with an optional `--bootstrap` wrapper that installs mise if absent. **Blocked today by facts 0a**: no public release artifact, no CI attestation. Also still subject to the verifier's E3 dependency cycle — a fetched tarball ships no `uv`/Python, and every authoritative entrypoint in `mise.toml` is `uv run --python 3.12.11 --script …`, so the stub must re-invoke `mise install` against the tarball's own `mise.toml`, which reintroduces the per-absolute-path trust prompt. Adopt only if the repo goes public, and only with: (i) `actions/attest` in `.github/workflows/` so `mise lock` records real `github-attestations` instead of the negative-cache `"unavailable"`; (ii) `mise lock` run on every target platform, since cross-platform provenance is metadata-only; (iii) a bare discoverable bin name, never `./bin/install`.

*(If credentialed private fetch is ever wanted for the mise plane, `github:` does support private repos — `jdx/mise@main:docs/dev-tools/github-tokens.md:5` — via `MISE_GITHUB_TOKEN`, `gh` CLI tokens, or `github.credential_command`. Distinct `tool_alias` per artifact is mandatory: two `github:owner/repo` entries differing only in `matching` resolve to the same directory and the second overwrites the first.)*

### What was stolen from everything-claude-code's UX

1. **`PLUGIN_SCHEMA_NOTES.md` → our own manifest-notes doc** (backlog #1). Cashes in immediately against fact 0b.
2. **Install-state as single source of truth for `doctor`/`repair`/`update`** (backlog #5) — "what did I install and with what options" answerable without re-deriving it. This is the actual mechanism behind the user's "scalable update path".
3. **The explicit "pick exactly one path per harness, do not stack" warning, with worked Works/Avoid examples and a recovery sequence.** `AGENTS.md` states the rule in one clause; ECC documents its own failure mode in full. Worded here for the two planes above.
4. **Verdict on ECC's own remote-install story: not transferable.** `npx <pkg>` has no mise analogue, and `git clone && ./install.sh` is what this repo is trying to escape. ECC contributes UX *discipline*, not the remote-install mechanism.

### Free wins found locally, not in any report

- **`claude plugin tag`** exists in the installed CLI: *"Create a `{name}--v{version}` git tag for a plugin release, validating that plugin.json and any enclosing marketplace entry agree"* with `--dry-run`/`--push`. Wire it into `scripts/bump-version.sh` (which already drives `.version-bump.json`'s three targets: `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`) — it closes the manifest↔marketplace agreement gap for free and yields the exact tag the recommended clone one-liner pins to. `--dry-run` today correctly refuses on the dirty tree.
- **Third-party marketplace auto-update is OFF by default** (official Anthropic marketplaces are ON). So the Claude plane's "updates arrive automatically" is *false* for this repo unless the operator toggles it, or managed settings set `"autoUpdate": true` on the `extraKnownMarketplaces` entry. Say so in `docs/install-block.md` rather than implying subscription semantics.
- **`skills.sh` is a real third option, deliberately not recommended.** `vercel-labs/skills`, MIT, 28.1k stars, npm `skills@1.5.22`; `npx skills add <owner/repo>` supports GitHub shorthand, full URLs, GitLab, SSH, and local paths, has symlink mode and `npx skills update`. Rejected because its README documents **no version/ref/sha pinning of the source** — an unpinned auto-syncing fetch is incompatible with `locked = true` doctrine and with "never accept ambient provenance." It is, however, the vector by which the colliding names in fact 0c arrived on this machine.

---

## 3. Authoring principles registry

Destination: one new `skills/agentic-sdlc/references/skill-authoring.md`, pointed to from `AGENTS.md`'s "Adding a skill" bullet. Sources: mattpocock `writing-for-agents/SKILL.md` + `SKILL-MECHANICS.md` (MIT), plus items already ranked in `docs/research/2026-08-05-pi-lab-harvest-memo.md`.

1. **Context pointers: the pointer's wording, not its target, decides reach.** A must-have target behind a weak pointer is a variance bug — sharpen wording before inlining. Directly names what `scripts/validate_bundle.py:396` only measures as a length cap: the ≤1024-char description *is* the pointer, and it does triggering work.
2. **Two budgets, priced separately.** *Context load* = always-loaded tokens (a skill description, an `AGENTS.md` line) spent every turn whether or not it fires. *Cognitive load* = the human remembering what exists. Cognitive load is "the price of human agency" — spend it where judgement matters, don't minimise it reflexively. This is the sharpest framing available for what `AGENTS.md`'s "read `references/*.md` on demand only" is buying.
3. **Information hierarchy (3 rungs): in-file step > in-file reference > disclosed reference.** Push too little down and the top bloats; too much and you hide what's needed. **Branching is the disclosure test:** inline what every branch needs, disclose what only some branches reach. Validates this repo's existing 196-line `SKILL.md` + 1,139-line `references/` split as already correct — and is the standard to hold new skills to.
4. **Co-location beside the ladder.** Definition, rules, and caveats for one concept under one heading. Distinct from duplication: duplication repeats a meaning, scattering fragments one.
5. **Every step ends on a completion criterion, judged on clarity + demand.** Vague bounds invite *premature completion*. Fix the bound first; hide later steps only across a real context boundary (subagent dispatch or hand-off) — an inline call clears nothing. Pairs with pi-lab's `loop-design` rule (`pi-lab-harvest-memo.md:58`): stop conditions must be externally adjudicated, never self-graded.
6. **Prompt the positive; negation backfires.** Steering by prohibition drags the forbidden behaviour into context and makes it *more* available. A ban earns its place only as a hard guardrail you cannot phrase positively — and even then, pair it with the positive target. **Direct audit consequence for this repo**: `AGENTS.md` and several `references/*.md` are dense with "never", "fails closed", "is forbidden". Some are genuine guardrails (correct use). Others are unpaired prohibitions that should carry the positive target beside them.
7. **Leading words.** Reuse a compact concept already in pretraining (`tracer bullet`, `red`, `tight`) as a repeated *token*, never a restated sentence — it recruits priors free and anchors both execution and invocation. This repo already does this well (`wave`, `fan-in`, `conductor`, `Seed`, `backlog-zero`); the actionable half is the refactor hunt: find triads spelled out at three sites and collapse them.
8. **Single source of truth; the environment counts as one.** A doc restating `mise.toml` or `--help` output is a *cache* — it earns its load only when the lookup is expensive. Cache the unwritten convention and the gotcha; leave one-command lookups to the environment where they can't go stale. **This is the rule the install-block consolidation (backlog #2) enforces**, and the rule `README.md:130`'s stale strict-validation claim broke.
9. **Prune for relevance or accumulate sediment.** Stale layers settle because adding feels safe and removing feels risky. Pair with pi-lab's retire-by-redirect (never silent deletion) and its four-gate admission / ≥2-of-5 promotion tests (`pi-lab-harvest-memo.md:51`).
10. **Invocation is a cost choice, not a default.** Model-invoked = permanent context load bought for autonomous + cross-skill reach. User-invoked (`disable-model-invocation: true`) = zero context load, all cognitive load. Two user-invoked skills cannot reach each other's shared reference — it must live in a plain external file. Router skills exist to cure piled-up cognitive load, and a router must itself be user-invoked so it can't be double-invoked. Host-specific key; scope it to the Claude plane.
11. **Enforce non-mutation at the tool allowlist, not in prose.** hyperresearch's contribution (`tools: Read, Edit` on the patcher, verified locally). Mechanical > doctrinal. Backlog #4.
12. **Advisory roles recommend; the conductor applies.** hyperresearch's `readability-recommender` writes JSON only and the orchestrator issues the `Edit` calls — an independent reinvention of this repo's own "roles submit evidence, only an authorized integrator mutates." Cite it as convergent external validation of doctrine already in `AGENTS.md`.

---

## 4. Open questions and blockers

**License — blocks backlog #7–#10, #13 today.** `.claude-plugin/plugin.json:8` declares `"license": "UNLICENSED"`, and there is **no root `LICENSE` and no `NOTICE`** (`ls` confirms). MIT permits verbatim reuse *only with* the copyright line and permission notice preserved. Meanwhile `skills/change-writing/references/attribution-policy.md` default-prohibits model/tool attribution — which is about *authorship* attribution, not upstream *copyright* attribution, so it does not conflict, but the distinction must be stated or someone will strip a required notice citing that policy. **Prerequisite: land a root `THIRD-PARTY-NOTICES.md` recording, per item, the upstream repo URL, the exact commit SHA vendored from, the MIT text, and whether the item is copied or adapted** (the pi-lab NOTICE/provenance convention, `pi-lab-harvest-memo.md:73`, now with a concrete trigger). Until it exists, ship paraphrases only.

**Repo visibility is an unmade product decision.** Private + zero releases (fact 0a) forecloses every anonymous remote-install path. The recommended design works today via SSH-credentialed clone and `/plugin marketplace add git@…`. The runner-up (`http:` stub, CI-attested tarball) needs public visibility or a token-distribution story. Not my call to make.

**Gate gap: skills are not model-pin-checked.** `scripts/validate_bundle.py:1041,1054` rejects static `model:`/`model_reasoning_effort:` in `agents/claude/*.md` and `agents/codex/**/*.toml`. `validate_skills` (`:386-400`) checks only name==dirname, description presence/length, and reference existence — **no model-pin check**. A vendored `SKILL.md` carrying `model: opus` (exactly what hyperresearch's rendered artifacts do) would pass the gate. Close this before any vendoring pass, not after.

**Unverified — `locked = true` × ad-hoc `mise x`.** The verifier's D3 stands unresolved: docs say all mise settings are global in scope and `locked` fails installs lacking pre-resolved lockfile URLs, yet `mise-lock.md`'s own command table treats one-off installs as outside lockfile mediation, and this repo already coexists with a URL-less `npm:` entry (`mise.lock:158-160`). The two-command experiment is specified in the verification report. I did not run it (mutates the tool store, needs network, and I am read-only). Harmless for the recommended design; blocking for the runner-up.

**Independent supply-chain finding, unrelated to install UX.** `mise.toml:5` sets `npm.package_manager = "npm"`, which shells out to the npm CLI and thereby opts the Seeds acquisition path out of aube's `trustPolicy = no-downgrade` and `lowDownloadThreshold` gating — while `npm:` already contributes no lockfile checksum (`mise.lock:158-160` vs. the `provenance = "github-attestations"` entries for `uv`/`lefthook`). That is this repo's weakest existing supply-chain link and it exists regardless of which install design ships. File separately.

**hyperresearch's headline benchmark claim is unverified by its own README** ("currently leads the DeepResearch-Bench RACE leaderboard (benchmarked internally)… Third party validation is pending"). Do not cite it as fact anywhere. Version churn is real: PyPI is at 0.10.0 (verified live), local `uv tool` at 0.8.6.

**Unverified — whether `commands/` growth needs a router skill.** Four commands today (`sdlc-init`, `sdlc-frame`, `sdlc-wave`, `sdlc-mission`); `AGENTS.md` already routes them in prose. mattpocock's `ask-matt` pattern applies at a name count this repo hasn't reached. Revisit at ~8.

**Not investigated: ECC's remaining catalog.** 281 skills / 67 agents / 94 commands, of which ~10 files were actually read across the harvests. Everything unread is unvetted. ECC's own README carries a supply-chain warning about third-party re-uploads — pull only from `affaan-m/ECC` (confirmed canonical: `fork: false`, MIT, 238,009 stars) and its official npm packages, never a fork.
