# Dynamic Workflows extension contract for a Claude-Code-first harness

**Question.** Against current first-party Anthropic documentation and observable
Claude Code surfaces, what can an installable harness distribute, configure, and
verify around Dynamic Workflows?

**Decision gated.** Whether to make Dynamic Workflows a supported, installable
execution surface for the harness, and which claims must remain runtime-canary
evidence rather than plugin metadata.

**Research date and scope.** 2026-08-14. This is limited to current official
Anthropic/Claude Code documentation and its documented CLI/UI surfaces. It is
not a claim about a particular installed CLI binary, gateway, provider route, or
future release.

## BLUF

**Recommendation — adopt a plugin-distributed workflow surface, but treat
execution identity as a mandatory runtime canary. Confidence: high.**

Claude Code now documents Dynamic Workflows as a supported, generally available
runtime: a plugin can ship versioned JavaScript workflow scripts, named in the
plugin namespace, alongside agent definitions, skills, hooks, and MCP
configuration. A harness can therefore distribute repeatable workflow graphs and
stage-specific *requested* models through those scripts. It can also package
agent types with model, effort, tool, turn, and worktree-isolation controls.

It cannot turn the plugin manifest into an admission proof. Dynamic Workflow
scripts have no direct shell/filesystem/module access; spawned agents remain
subject to Claude Code permissions, allowlists, policy substitution, CPU/runtime
caps, and session/provider configuration. The documented progress UI can show a
requested-to-substituted-model warning, prompts, tool calls, results, token use,
and elapsed time, but the sources do not define a plugin/API receipt of the
actual provider, model ID, effort, or gateway route. A harness must preserve the
requested assignment separately and accept only an observed transcript/transport
receipt from an executed canary as effective-identity evidence.

**Operational shape:** distribute `workflows/` plus restrictive reusable
`agents/`; invoke a namespaced saved workflow; permit a user/admin to enable it;
then verify a small canary in `/workflows` and correlated harness/provider logs.
Do not set `CLAUDE_CODE_SUBAGENT_MODEL` in the generic launcher, because it
overrides each workflow-stage model request.

## Supported contract

| Area | Current documented fact | Harness implication |
| --- | --- | --- |
| Availability | **[Verified]** Dynamic Workflows require Claude Code v2.1.154+ and are available on paid plans, with Anthropic API access, and on Amazon Bedrock, Google Cloud's Agent Platform, and Microsoft Foundry. Pro requires the `/config` enablement. [Workflows: availability](https://code.claude.com/docs/en/workflows#orchestrate-subagents-at-scale-with-dynamic-workflows) | Refuse/mark unsupported below the minimum version and probe the selected provider/entitlement; do not infer a provider's support from a plugin install. |
| Runtime model | **[Verified]** A workflow is a JavaScript script Claude writes and the runtime executes in the background; script variables, rather than the parent context, hold intermediate results. [Workflows: overview](https://code.claude.com/docs/en/workflows#orchestrate-subagents-at-scale-with-dynamic-workflows) | Ship repeatable scripts, but retain a small user-visible approval/canary path for their first execution. |
| Distribution | **[Verified]** A plugin may contain a root `workflows/` directory or declare a `workflows` file/directory field; plugin workflows are namespaced, e.g. `/acme-tools:release-audit`. [Workflows: distribute in a plugin](https://code.claude.com/docs/en/workflows#distribute-a-workflow-in-a-plugin), [plugin schema](https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema) | The harness can distribute a fixed workflow graph as an ordinary plugin component without a separate installer plane. Keep its namespaced command as the stable public API. |
| Discovery/storage | **[Verified]** Saved project workflows live in `.claude/workflows/`; personal ones live in `~/.claude/workflows/` (or `CLAUDE_CONFIG_DIR/workflows/`). Project definitions are discovered along the path and the closest wins; a project name beats a personal name. Runtime-generated scripts are recorded beneath the session directory in `~/.claude/projects/`. [Workflows: save/reuse](https://code.claude.com/docs/en/workflows#save-the-workflow-for-reuse), [runtime storage](https://code.claude.com/docs/en/workflows#how-a-workflow-runs) | Keep durable, reviewed graphs in the plugin; do not depend on ephemeral session-script paths. Avoid command-name collisions with project workflows. |
| Plugin integration | **[Verified]** Plugins package workflows with agents, skills, hooks and MCP servers. Plugin agents can have `model`, `effort`, `tools`, `disallowedTools`, `maxTurns`, `skills`, `memory`, `background`, and `isolation`; plugin-agent `permissionMode`, `mcpServers`, and `hooks` frontmatter are not supported. [Plugin reference](https://code.claude.com/docs/en/plugins-reference#plugin-components-reference), [subagent fields](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields) | Put role-specific model/effort/tool restrictions in agent definitions. Put shared MCP/hook configuration at supported plugin-level locations, and do not promise per-plugin-agent hooks/MCP/permission mode. |
| Model injection | **[Verified]** Workflow agents inherit the session model unless the script routes a stage differently; `CLAUDE_CODE_SUBAGENT_MODEL` overrides both. An `availableModels` policy can substitute a blocked request, and `/workflows` warns with requested and substituted models. [Workflows: model routing](https://code.claude.com/docs/en/workflows#cost) | Store exact requested route IDs in the workflow/agent source and leave the overriding environment variable unset. Record substitutions as a failed exact-route canary, not success. |
| Effort injection | **[Verified]** Agent definitions support `effort` (`low`, `medium`, `high`, `xhigh`, `max`) and it overrides session effort when active; valid values remain model-dependent. [Subagent fields](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields) **[Verified]** `ultracode` combines `xhigh` effort with automatic workflow orchestration, is session-only, and needs v2.1.203+. [Workflows: ultracode](https://code.claude.com/docs/en/workflows#let-claude-decide-with-ultracode) | A fixed workflow should request effort in its named agent definitions. Treat `/effort ultracode` as optional ambient orchestration, not the harness's exact per-stage contract. |
| Tool access | **[Verified]** The script itself has no direct filesystem/shell access and cannot load modules; agents perform work. Workflow agents run in `acceptEdits`, inherit the session tool allowlist, and can still prompt for shell, web, and non-allowlisted MCP tools. [Workflow limits/permissions](https://code.claude.com/docs/en/workflows#behavior-and-limits), [run approval](https://code.claude.com/docs/en/workflows#approve-the-plan-before-it-runs) **[Verified]** Background subagents retain MCP tools but only a documented built-in subset; agent `tools`/`disallowedTools` further restrict the pool. [Subagent tools](https://code.claude.com/docs/en/sub-agents#available-tools) | Keep orchestration pure. Declare least-privilege roles, preflight required tool/MCP approval, and regard a completed install as no proof the run will have its required tools. |
| Graph/scale limits | **[Verified]** A workflow has at most 16 concurrent agents (possibly fewer on constrained CPUs) and 1,000 total agents. The `small`/`medium`/`large` size guideline is advice, not a cap. [Workflow limits](https://code.claude.com/docs/en/workflows#behavior-and-limits), [size guideline](https://code.claude.com/docs/en/workflows#set-a-size-guideline) **[Verified]** The underlying subagent facility defaults to nesting no more than three layers below the main conversation; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` can lower/raise it, while the normal Agent-tool concurrent limit defaults to 20. [Subagent nesting](https://code.claude.com/docs/en/sub-agents#let-subagents-spawn-their-own-subagents) | Design workflow graphs so the 16/1,000 caps alone make them safe. If a graph depends on nested workers, add a version-pinned canary: the docs state the generic subagent limit but do not define a separate Dynamic-Workflow nesting guarantee. |
| Persistence/resume | **[Verified]** Stopped workflows may resume only in the same Claude Code session; completed agents can be replayed from cached results, but exiting Claude Code starts a fresh run. [Workflow resume](https://code.claude.com/docs/en/workflows#resume-after-a-pause) | Persist only authored workflow source and harness receipts. Do not model an in-flight run as durable cross-session state. |
| User interaction/approval | **[Verified]** A running workflow has no mid-run user input except agent permission prompts; default/accept-edits sessions prompt per run unless approved, while bypass, `-p`, and Agent SDK runs do not. [Workflow approval](https://code.claude.com/docs/en/workflows#approve-the-plan-before-it-runs) **[Verified]** The `ultracode`/natural-language trigger is accepted only for human-originated prompts; it does not trigger from `-p`, scheduled, webhook, or unmarked Agent SDK prompts. [Trigger boundary](https://code.claude.com/docs/en/workflows#where-the-keyword-works) | A noninteractive harness must invoke an already-saved workflow through a supported path, not rely on putting `ultracode` in `-p` input. Split human sign-off stages into separate workflows. |
| Observability/identity | **[Verified]** `/workflows` exposes phases, agent count, token total, elapsed time, agent prompt, recent tool calls, and result; model-policy substitution gets a requested/substituted warning. [Workflow progress](https://code.claude.com/docs/en/workflows#watch-the-run), [substitution](https://code.claude.com/docs/en/workflows#cost) **[Inferred]** These documented surfaces are strong run evidence but not a provider/model/effort receipt: Anthropic documents no workflow-manifest field or progress API that attests the backend provider, exact final model ID, effective effort, or gateway route. | Capture the run/script path, `/workflows` model warning state, and correlated independent transport/provider evidence. Never convert a request echo or a clean progress screen into route identity proof. |
| Versioning | **[Verified]** Marketplace/plugin versions determine cache paths and update detection. A fixed `plugin.json` version must be bumped every release; otherwise unchanged version strings leave users on cached content. [Marketplace versioning](https://code.claude.com/docs/en/plugin-marketplaces#version-resolution-and-release-channels) | Version the workflow and role definitions atomically with the plugin. Record both plugin version and minimum Claude Code version in each runtime receipt. |

## Boundaries and adversarial findings

1. **Installability is not enablement.** The documented `disableWorkflows` setting and `CLAUDE_CODE_DISABLE_WORKFLOWS=1` suppress workflow commands and Ultracode; organizations can set the same restriction in managed settings. A plugin must surface this as an unavailable capability rather than attempting to bypass it. [Workflow disablement](https://code.claude.com/docs/en/workflows#turn-workflows-off) **[Verified]**

2. **The workflow script is not a general Node extension point.** No `import()` and no direct shell/filesystem access are admitted. Use agents for work and package auxiliary code only for tools/agents/hooks that have a separately supported invocation path. [Workflow limits](https://code.claude.com/docs/en/workflows#behavior-and-limits) **[Verified]**

3. **Requested model and effective model can diverge.** Environment override and organization allowlist substitution are documented; the product warns rather than failing closed. A multi-provider or exact-model harness must fail its own qualification when the observation differs. [Workflow model routing](https://code.claude.com/docs/en/workflows#cost) **[Verified]**

4. **Plugin defaults cannot silently grant workflow privileges.** Workflow workers auto-accept edits, but tool/MCP operations outside the pre-existing allowlist may still prompt. Plugin-agent permission-mode frontmatter is ignored. [Workflow approval](https://code.claude.com/docs/en/workflows#approve-the-plan-before-it-runs), [subagent fields](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields) **[Verified]**

5. **Current documentation makes runtime evidence necessary.** It documents a script, lifecycle UI, and requested-to-substituted warning, not a stable workflow-result provenance schema. **[Inferred from the cited product contract]** The cheapest decisive experiment is one fixed two-stage plugin workflow whose stages request distinct permitted models/efforts, each produces a unique harmless artifact, while the launcher records outbound provider/model metadata. Compare those independent records with the script path and `/workflows` details; then repeat with a deliberately policy-blocked model to ensure the harness rejects substitution.

## Decision and acceptance checklist

Proceed with Dynamic Workflows as an **optional, version-gated Claude Code plugin capability**. The harness can claim only:

- a versioned, namespaced workflow and versioned agent-role bundle was distributed;
- the required Claude Code version/config/tool permissions were observed before launch;
- the workflow executed within its documented 16-concurrent/1,000-total envelope; and
- requested model/effort inputs plus any visible substitution warning were recorded.

It must not claim exact model/provider/effort identity, workflow persistence after session exit, unbounded graph execution, or noninteractive Ultracode triggering without the canary above. Treat failed policy admission, prompt-required tooling, missing entitlement, unsupported version, or any requested/effective model mismatch as a named blocked state.

## Contradictions and open unknowns

- **Naming drift:** current workflow docs say Google Cloud's *Agent Platform*; the launch post says Vertex AI. The current documentation is the operational source of truth; the harness should probe the actual configured provider rather than bake either label into capability logic. [Current docs](https://code.claude.com/docs/en/workflows#orchestrate-subagents-at-scale-with-dynamic-workflows), [launch post](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code) **[Documented contradiction]**
- The public workflow guide says a script can route a stage to a different model, but it does not publish a complete stable schema for every script-level agent option. **[Documented gap]** Author workflow code through Claude Code/current SDK guidance and validate it against the minimum supported CLI before release.
- The first-party pages reviewed do not specify an attested effective-effort readback, backend provider receipt, or gateway-route receipt for a workflow run. **[Documented absence / inference]** Keep those as external canary evidence, not metadata promises.

## Sources

All sources below are first-party Anthropic/Claude Code material, retrieved 2026-08-14.

- [Dynamic Workflows](https://code.claude.com/docs/en/workflows)
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Introducing Dynamic Workflows in Claude Code](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code)
