# Claude Code Auto mode controls and the ccodex boundary

**Captured:** 2026-08-12
**Local CLI:** Claude Code 2.1.229
**Evidence:** current Anthropic documentation, local CLI behavior, and this repository's ccodex
launcher

## Conclusion

Claude Code does **not** expose a supported control for choosing Auto mode's runtime safety-
classifier model arbitrarily. The main session model, the runtime classifier, and the one-off
rule critic are three distinct selections:

| Selection | Supported control | Effect |
|---|---|---|
| Main session model | `claude --model`, `/model`, or the `model` setting | Chooses the model doing the task. It does not normally choose Auto's classifier. |
| Auto safety classifier | No direct client selector | Claude Code defaults to Sonnet 5, subject to a server-configured override and documented fallbacks. |
| Rule critique model | `claude auto-mode critique --model <model>` | Chooses only the AI call that reviews custom Auto rules; it does not change the live classifier. |

Anthropic documents the runtime choice precisely: Sonnet 5 is the default rather than the
session's `/model`; a server-configured classifier takes precedence. If the session uses Sonnet
4.6, or `availableModels` excludes Sonnet 5, the classifier falls back to the session model; a
Fable 5 session instead receives an Opus fallback. The first Auto request settles that selection
for the session. These are constrained fallback rules, not a way to name an arbitrary classifier.
[`availableModels` also restricts session model selection, so using it merely to influence this
fallback would have a wider effect.][permission-modes]

## Supported controls

The starting mode can be selected per invocation with `--permission-mode auto`, or persistently in
user or managed settings:

```json
{
  "permissions": {
    "defaultMode": "auto"
  },
  "autoMode": {
    "environment": ["$defaults", "Source control: github.example.com/acme"],
    "allow": ["$defaults"],
    "soft_deny": ["$defaults"],
    "hard_deny": ["$defaults"],
    "classifyAllShell": true
  }
}
```

`autoMode.environment`, `allow`, `soft_deny`, and `hard_deny` are natural-language rule lists.
`classifyAllShell: true` routes every Bash and PowerShell command through the classifier instead
of allowing narrow shell permission rules to resolve first; it increases classifier coverage and
latency but does not select its model. Auto configuration is read from user settings, managed
settings, and inline `--settings`. Current Claude Code deliberately ignores `autoMode` in project
and local settings. Likewise, `permissions.defaultMode: "auto"` from project or local settings is
ignored, so a repository cannot grant itself Auto mode. See Anthropic's [Auto configuration
reference][auto-config], [permission-mode reference][permission-modes], and [settings
reference][settings].

`"$defaults"` is a safety-significant splice marker, not decoration. For each of the four rule
lists, including it inherits the built-ins at that position; setting a list without it replaces
that section's built-ins completely. Omitting it from `soft_deny` drops built-in blocks such as
force push, `curl | bash`, production deploys, and Auto-mode bypass, while omitting it from
`hard_deny` drops the built-in exfiltration boundary. Sections are independent. Any ccodex-owned
profile should preserve `"$defaults"` unless replacement is an explicit, separately reviewed
operation, then verify the expanded result with `claude auto-mode config`.

Other controls are intentionally fixed. Claude Code pauses Auto and resumes prompting after three
consecutive blocks or twenty total blocks; those thresholds are not configurable. The server-side
classifier override is not client-configurable. Neither `autoMode.model` nor
`autoMode.classifierModel` is a documented setting. `claude auto-mode critique --model` is not an
exception: the command is documented and described by its help as feedback on custom rules.

## ccodex implications

Ordinary `ccodex launch` preserves accepted Claude arguments when forwarding them to `ocx claude`,
so an operator can already try `ccodex launch --permission-mode auto` or provide one inline settings
document. Since 2026-08-13, it validates every explicit settings value before gateway startup and
refuses malformed, uncheckable, or route-bypassing documents without rewriting accepted argv.
[`ccodex ultracode` is different: it owns `--settings` and rejects a competing settings
argument.][ccodex-launcher] A dedicated Auto profile therefore cannot safely be implemented by
blindly appending another `--settings` flag.

**Empirical local probe, Claude Code 2.1.229:** two repeated `--settings` flags were not merged.
With the first document setting `autoMode.environment` and the second setting only
`autoMode.allow`, `claude auto-mode config` retained the second document and returned the built-in
environment, not the first document's sentinel. In a same-field probe, only the second sentinel
survived. Treat repeated `--settings` as last-wins for this version.

There is also an eligibility boundary. Anthropic documents Auto only for specific Claude main-
model families, with the exact set depending on the provider. A ccodex session whose main model is
a routed GPT or Muse model is outside that documented set. The executed GPT probe below shows that
Claude Code 2.1.229 currently admits the routed GPT model and runs the native Sonnet classifier,
but that is version-specific observed behavior rather than a documented compatibility contract.
Muse and genuine-Claude routes still need separate executed probes. Do not claim support for an
untested ccodex route from config or help output alone.

### Executed ccodex probe

On 2026-08-12, a live `ccodex launch --permission-mode auto` probe on Claude Code 2.1.229
separated the working model from the classifier directly. The working turn used
`claude-ocx-native--gpt-5.6-sol[1m]`. A harmless, explicitly authorized
`mkdir /tmp/ccodex-auto-classifier-probe-20260812` forced a classifier decision because it wrote
outside the working directory. Claude's debug log recorded:

```text
[auto-mode] new action being classified: Bash mkdir /tmp/ccodex-auto-classifier-probe-20260812
classifier_request_started ... model=claude-sonnet-5[1m] ...
classifier_request_finished ... outcome=ok
```

The gateway attribution stream independently recorded the main request as `gpt-5.6-sol` through
the `openai` provider, the classifier request as `claude-sonnet-5` through
`anthropic-native`, and the following main request as `gpt-5.6-sol` again. The effective user
settings contained neither `ANTHROPIC_SMALL_FAST_MODEL` nor `ANTHROPIC_DEFAULT_HAIKU_MODEL`.
The exact empty probe directory was removed afterward.

This executed result refutes the idea that Claude Code's Haiku/small-fast alias selects Auto's
classifier. `ANTHROPIC_DEFAULT_HAIKU_MODEL` controls the `haiku` alias and background
functionality; its deprecated predecessor is `ANTHROPIC_SMALL_FAST_MODEL`. `ccodex set-fast-model`
delegates to OpenCodex's compatibility mapping for that slot; it still does not select Auto's
classifier. Auto's classifier is a separate Sonnet 5 request under the documented default selection
path. See Anthropic's [model configuration reference][model-config].

### Experimental per-launch fallback recipe

The only documented indirect experiment for a non-Claude session is to exclude Sonnet 5 from one
launch's `availableModels`. Current Claude Code then falls back to the session model when that route
is otherwise Auto-eligible:

```bash
# Experimental and per-launch: this does not persist a classifier setting.
auto_settings='{"availableModels":["gpt-5.6-sol"]}'
ccodex launch \
  --model gpt-5.6-sol \
  --permission-mode auto \
  --settings "$auto_settings"
```

Replace `gpt-5.6-sol` in both places with the same exact routed ID being tested. Keep all desired
inline settings in this **one** document because repeated `--settings` is last-wins in the observed
CLI version. This is not a supported arbitrary classifier selector: routed GPT and Muse models are
outside Anthropic's documented Auto model set, and fallback may be refused, unavailable, or change
between Claude Code versions.

`availableModels` also constrains the launch's session, subagent, workflow, skill, and advisor model
selection. A one-entry list therefore prevents switching to other models for the whole launch; it
is not a classifier-only filter. Do not persist it merely to influence Auto.

A real classifier claim requires a separately approved canary. Before running one, display the
exact synthetic prompt/action, selected model, inline `availableModels` document, turn count,
timeout, provider/quota implications, attribution capture, and stop conditions. Admit the result
only from correlated gateway request IDs plus resolved provider/model evidence—not the requested
value or a response-body model label—and record refusal, fallback, or ambiguity as such.

## Recommended direction

Add an explicit ccodex Auto launch/profile surface that:

1. composes one validated inline settings document rather than emitting repeated `--settings`;
2. starts with `--permission-mode auto`, while allowing an explicit caller mode to win;
3. preserves `"$defaults"` in every customized list and uses `permissions.ask`/`deny` for firm
   pre-classifier boundaries;
4. prints or checks `claude auto-mode config` before launch so the operator can inspect the exact
   expanded policy; and
5. qualifies genuine-Claude, GPT, and Muse routes separately with real Auto actions and records
   unavailable/fallback behavior without treating a requested model as observed classifier
   identity.

Do not add a `classifierModel` option: it would promise a control Claude Code does not support.
Expose `auto-mode critique --model` only as a separately named policy-review operation.

## Verification performed

```text
claude --version
claude --help
claude auto-mode --help
claude auto-mode config --help
claude auto-mode defaults --help
claude auto-mode critique --help
claude auto-mode reset --help

# Isolated repeated-settings probes, with a temporary CLAUDE_CONFIG_DIR:
claude --settings '<first sentinel JSON>' --settings '<second sentinel JSON>' auto-mode config

# Unsupported-key probes, also isolated:
claude --settings '{"autoMode":{"model":"gpt-5.6-sol"}}' auto-mode config
claude --settings '{"autoMode":{"classifierModel":"gpt-5.6-sol"}}' auto-mode config

git status --short
rg -n 'autoMode|auto-mode|permission-mode|defaultMode|--settings' scripts tests docs skills
```

The unsupported-key probes returned no classifier model field in effective Auto configuration;
that is corroboration, not the basis of the conclusion. The first-party documentation's explicit
selection rules and statement that Claude Code chooses the classifier are authoritative.

[auto-config]: https://code.claude.com/docs/en/auto-mode-config
[permission-modes]: https://code.claude.com/docs/en/permission-modes
[settings]: https://code.claude.com/docs/en/settings
[model-config]: https://code.claude.com/docs/en/model-config
[ccodex-launcher]: ../../scripts/opencodex-claude.sh
