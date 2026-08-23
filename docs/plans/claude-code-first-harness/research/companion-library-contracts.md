# Companion-library contracts: HyperResearch, ECC, mattpocock/skills, and SimpleEnglish

- **Question.** What installation, update, removal, licensing, namespace, runtime-dependency, and selection-surface contracts do the four identified upstream libraries publish, and which actions may this harness safely automate?
- **Decision gated.** Whether a Claude-Code-first harness can add any of these as a supported companion library through its upstream-maintained front door, versus requiring explicit operator choice or a separate onboarding decision.
- **Scope date.** 2026-08-14. This is a read-only review of upstream repositories and package metadata; it does not authorize installation, updating, removal, vendoring, or marketplace configuration.

## BLUF

**Recommendation — high confidence.** Keep the harness's current rule: never vendor any
of these libraries; expose only a closed, reviewed list of upstream *front doors* and make
every install, update, and removal an explicit operator action. It is safe to automate
read-only discovery, dry-run/plan display, exact-identity checks, and collision reporting.
It is **not** safe to turn any mutating lifecycle action into setup, a gate leaf, or a
default because each changes a host/project selection surface and three have material
additional choices (scope/profile/model/rules).

The appropriate companion-library disposition is:

- **HyperResearch:** retain as a separate, explicit Claude Code research harness only;
  do not add a generic library install/update/remove action. It renders Claude files and
  model-pinned subagents, and no upstream removal lifecycle for rendered output was found.
- **ECC:** allow only the documented Claude plugin route (`ecc@ecc`) after explicit
  scope/selection-surface approval. Do not automate npm setup: upstream says the released
  `ecc-universal` 2.1.0 lacks the described 2.2.0 guided commands.
- **mattpocock/skills:** a reasonable optional companion via *one* chosen channel. Prefer
  the Claude plugin for managed updates; use `skills` only when the operator explicitly
  wants editable selected files and accepts its project/global destination.
- **AminBlg/SimpleEnglish:** eligible for closed-catalog onboarding as a low-surface,
  one-skill optional companion, but that is a **new onboarding decision**: this bundle has
  not reviewed its install state/collision behavior or adopted its two alternate channels.

All four are MIT-licensed, which permits redistribution under their licence terms; that
does **not** override this repository's no-vendoring rule. [verified: HyperResearch
license](https://github.com/jordan-gibbs/hyperresearch/blob/main/LICENSE),
[ECC license](https://github.com/affaan-m/ECC/blob/main/LICENSE),
[mattpocock license](https://github.com/mattpocock/skills/blob/main/LICENSE), and
[SimpleEnglish license](https://github.com/AminBlg/SimpleEnglish/blob/main/LICENSE).

## Compact contract table

| Upstream identity | Supported own front door and update/removal | Namespace and selection surface | Runtime / host assumptions | Harness disposition |
|---|---|---|---|---|
| **HyperResearch** — `jordan-gibbs/hyperresearch`, PyPI `hyperresearch` 0.10.0 [verified: package metadata](https://pypi.org/pypi/hyperresearch/json) | Upstream documents `pip install hyperresearch && hyperresearch install`; `--global` installs the entry skill and agents under `~/.claude`, while normal install initializes a project vault and injects Claude integration. [verified](https://github.com/jordan-gibbs/hyperresearch/blob/main/README.md#install) `uv tool uninstall hyperresearch` removes only the tool, **not proven to remove rendered files**. | Global mode deliberately adds one always-reachable entry point; first project use adds the step skills lazily. The pipeline is advertised as 16 steps. [verified](https://github.com/jordan-gibbs/hyperresearch/blob/main/README.md#the-16-step-research-pipeline) Its names are `hyperresearch*`, so collision with unrelated bare skill names is low, but an existing `hyperresearch*` install must be treated as foreign. [inferred from installer naming](https://github.com/jordan-gibbs/hyperresearch/blob/main/src/hyperresearch/cli/install.py) | Python `>=3.11,<3.14`; base distribution depends on Crawl4AI, PyMuPDF, HTTPX, Jinja, etc. [verified](https://github.com/jordan-gibbs/hyperresearch/blob/main/pyproject.toml) It is explicitly a Claude Code harness; generated agent frontmatter receives profile model values, defaulting to `sonnet` and `opus`. [verified](https://github.com/jordan-gibbs/hyperresearch/blob/main/src/hyperresearch/core/profiles.py) | Explicit operator-selected research capability only; no generic auto-removal or cross-host promise. |
| **Everything Claude Code (ECC)** — source `affaan-m/ECC`; Claude plugin `ecc@ecc`; npm `ecc-universal` [verified identifiers](https://github.com/affaan-m/ECC/blob/main/README.md#naming--migration-note-ecc-ecc-affaan-m-ecc-ecc-universal) | Claude route: add its marketplace then install `ecc@ecc`; upstream says stop there and do not layer a full manual install. [verified](https://github.com/affaan-m/ECC/blob/main/README.md#install-with-claude-code) Uninstall is plugin removal plus its recorded-state scoped uninstaller; it preserves files it cannot prove it owns. [verified](https://github.com/affaan-m/ECC/blob/main/README.md#reset--uninstall-ecc) | Plugin identifier is namespaced (`ecc@ecc` and `/ecc:*`); manual Claude installations write flat `~/.claude/skills/<name>` and can conflict. [verified](https://github.com/affaan-m/ECC/blob/main/README.md#advanced-install-options) Upstream currently declares 68 agents, 284 skills, and 94 command shims. [verified](https://github.com/affaan-m/ECC/blob/main/README.md#ecc) | Npm `latest` is 2.1.0 (Node >=18), while repository `package.json` is 2.2.0; upstream says guided npm commands are unavailable until 2.2.0 publishes. [verified: npm metadata](https://registry.npmjs.org/ecc-universal), [verified: upstream warning](https://github.com/affaan-m/ECC/blob/main/README.md#install-ecc) Plugin-managed hooks; separately copied rules are an explicit choice. | Closed-catalog, Claude-plugin-only candidate; require scope, hook, rules, and 284-skill surface acknowledgement. Never automate npm setup against the current release. |
| **mattpocock/skills** — Claude plugin `mattpocock-skills`; source `mattpocock/skills` [verified manifest](https://github.com/mattpocock/skills/blob/main/.claude-plugin/plugin.json) | Plugin: `claude plugins install mattpocock-skills`, managed read-only and auto-updating. Editable alternate: `npx skills@latest add mattpocock/skills`, later `npx skills update`; upstream says pick one because both duplicate every skill. [verified](https://github.com/mattpocock/skills/blob/main/README.md#installation-30-second-setup) The underlying `skills` CLI documents `remove`. [verified](https://github.com/vercel-labs/skills/blob/main/README.md#other-commands) | The plugin manifest declares 25 skills. [verified](https://github.com/mattpocock/skills/blob/main/.claude-plugin/plugin.json) The plugin is managed; the `skills` path puts selected skills into agent/project or global directories, whose flat names can collide. [verified: installer scope](https://github.com/vercel-labs/skills/blob/main/README.md#installation-scope) | Plugin is Claude-specific. `skills` package metadata currently requires Node >=22.20.0. [verified](https://registry.npmjs.org/skills) No static `model:` or `tools:` frontmatter was found in the upstream SKILL.md corpus in this review. [verified by source scan; not a forward-compatibility guarantee] | Keep optional. Operator must choose plugin **or** editable channel and, for its engineering flows, explicitly run the upstream's once-per-repo configuration that writes issue-tracker/label/docs choices. [verified](https://github.com/mattpocock/skills/blob/main/README.md#2-run-setup-matt-pocock-skills) |
| **SimpleEnglish** — `AminBlg/SimpleEnglish`; plugin `simple-english@simple-english` [verified manifest](https://github.com/AminBlg/SimpleEnglish/blob/main/.claude-plugin/marketplace.json) | Upstream documents either `npx skills add AminBlg/SimpleEnglish` or its Claude marketplace/plugin route. [verified](https://github.com/AminBlg/SimpleEnglish/blob/main/README.md#-install) Updates/removal are not specified in that repository; the selected host/package manager owns them. `skills` documents generic update/remove, but applying either remains an operator action. [documented](https://github.com/vercel-labs/skills/blob/main/README.md#other-commands) | Exactly one declared `simple-english` skill, plus its local references; plugin also offers an opt-in always-on Claude output style. [verified](https://github.com/AminBlg/SimpleEnglish/blob/main/README.md#-install) A preflight still must detect an occupied `simple-english` name when using the editable path. | The skill declares Agent Skills compatibility with Claude Code, Cursor, Codex, Gemini CLI, and OpenCode; it has no static model or tools declaration. [verified](https://github.com/AminBlg/SimpleEnglish/blob/main/skills/simple-english/SKILL.md) | Low-surface **new** closed-catalog onboarding candidate. Do not silently choose its output style, prompt fallback, or marketplace scope. |

## What the harness may and may not automate

### Safe to automate (read-only)

1. Validate repository/package/plugin identity and licence from the cited official source.
2. List the exact upstream command that would be run, required executable, destination/scope,
   known selection-surface count, and acknowledged caveats.
3. Preflight the selected destination for an occupied name; a foreign/ambiguous path is a
   refusal, never an overwrite. For the `skills` CLI, use its `--list` or explicit
   `--skill` selection before a mutating run. [documented](https://github.com/vercel-labs/skills/blob/main/README.md#options)
4. Show version drift (particularly ECC repo versus npm) and stop until the operator selects
   a supported channel.

### Require an explicit operator choice

1. **Every installation/update/removal.** These write home or project state and alter the
   agent's selection surface. A dry run is not permission for the real operation.
2. **Channel and scope:** plugin versus copied/editable files; project versus global; and
   one channel per harness where upstream warns against stacking.
3. **ECC:** Claude scope, hook profile, optional rule packs, and acceptance of the 284-skill
   surface. Do not substitute an unpublished package interface for the installed 2.1.0 npm
   artifact.
4. **HyperResearch:** project versus global mode; Python environment/tool ownership;
   profile and all rendered model assignments; browser/runtime side effects; and a bespoke
   removal plan that inventories rendered files before deletion.
5. **mattpocock:** selected subset, `setup-matt-pocock-skills` configuration decisions, and
   the files that setup will write.
6. **SimpleEnglish:** plugin versus `skills` CLI, whether to enable its always-on output style,
   and whether a short technical-writing trigger deserves a new global selection entry.

## Rejected alternatives

- **Vendor a snapshot or a selected upstream skill. Rejected.** MIT makes it legally possible,
  but this repository's policy forbids foreign bytes and requires own-front-door installation.
  HyperResearch's renderer/profile model bindings make a snapshot especially unsafe.
- **Add all four to automatic contributor setup. Rejected.** It would silently mutate an
  operator's host and force unreviewed selection-surface and hook/model choices.
- **Treat ECC's npm README examples as current. Rejected.** The project's own README says the
  released 2.1.0 package does not provide the planned 2.2.0 guided commands.
- **Use one generic delete routine. Rejected.** ECC has state-scoped uninstall semantics;
  HyperResearch lacks an equivalent published cleanup contract; `skills` and plugins have
  their own lifecycle managers.

## Open risks and contradictions

- **ECC release contradiction — verified.** Source `main` identifies `ecc-universal` 2.2.0,
  whereas the official npm registry serves 2.1.0. This is not an acceptable gap for a
  noninteractive harness command; use the plugin route or wait for the package release.
- **HyperResearch removal gap — documented absence / high confidence inference.** Its package
  declares install commands and its source writes rendered integration, but neither the README,
  `pyproject` command definition, nor CLI installer examined here exposes an uninstall command.
  Cheapest decisive experiment before any onboarding: install into a disposable HOME/project,
  capture a file manifest, invoke the documented tool uninstaller, and compare the manifest.
- **SimpleEnglish lifecycle gap — documented absence.** Its README provides install routes but
  no project-specific update/uninstall contract. Do not manufacture one; use the chosen
  channel's documented lifecycle only after a destination preflight.
- **Selection surfaces change with upstream releases.** Counts here are dated evidence, not
  permanent contracts; re-read manifests/catalogs before implementing an installer.

## Sources and evidence standard

All external evidence above is first-party: upstream GitHub repository/manifest/source files,
the official PyPI project JSON, and official npm registry metadata. “Verified” means directly
observed in those sources on 2026-08-14. “Inferred” is explicitly labelled and limited to a
recommendation drawn from the documented file destinations/naming. No secondary source was used.
