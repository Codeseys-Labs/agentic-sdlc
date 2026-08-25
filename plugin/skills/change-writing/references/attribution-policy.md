# Attribution policy

Model, tool, and provider attribution is **default-prohibited**. It is included only when the user
**explicitly requests** it for the current artifact. A general "use an agent" instruction, or a
repository's general use of AI, does **not** authorize attribution.

## Default-deny tokens

Omit any of the following from commit messages, PR titles/bodies, and squash messages unless
explicitly requested for this specific artifact:

- `Co-Authored-By: Claude <noreply@anthropic.com>` — and any `Co-Authored-By:` trailer naming a
  model, agent, or provider (Claude, Codex, GPT, Copilot, Gemini, and the like).
- `Co-Authored-By: Codex ...` — same rule for any coding-agent identity.
- `Generated with ...`, `🤖 Generated with ...`, "Generated with Claude Code", and any
  generated-by footer.
- Model or provider names used as an authorship or marketing footer, e.g. "Written by Opus 4.8".
- Model/AI authorship stated **mid-sentence**, not only as a footer — e.g. "This PR was written by
  an AI assistant". The claim is prohibited wherever it appears in the text, not just on a trailing
  line.
- Agent or provider **badges** — markdown image links (`![Built with Claude](...)`) **and** HTML
  image tags (`<img alt="Made with Claude" src=...>`) whose alt text names a model, agent, or AI.

The robot glyph 🤖 used as a generated-by badge is itself a deny token — both the "🤖 Generated
with …" footer and a **standalone 🤖 badge line**. A 🤖 mentioned mid-sentence in prose (for
example when the change itself is about emoji handling) is not attribution and is allowed.

## Human co-author carve-out

A `Co-Authored-By:` trailer for a **real human** collaborator is allowed when it is backed by a
genuine human identity and evidence of contribution, or when the user explicitly instructs it. The
discriminator is authorship, not the trailer keyword: a human co-author trailer passes; a
model/agent/provider one does not. Do not ban the `Co-Authored-By:` trailer wholesale — that would
suppress legitimate human credit.

## Explicit opt-in scope

When the user explicitly requests attribution, it applies **only to the current artifact**. It does
not become a standing default for later commits, PRs, or squash messages.
