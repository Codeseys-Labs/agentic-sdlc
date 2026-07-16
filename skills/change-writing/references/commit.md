# Commit message

A commit message describes one logical change: an imperative subject line and, when the change
needs justification, a body that explains **why**, not a restatement of the diff.

## Subject line

- Imperative mood, present tense: "Add", "Fix", "Remove" — not "Added" or "Fixes".
- One line, kept short (target ~50 characters, hard-stop well under the reader's wrap width).
- No trailing period.
- Describe the change's effect, not the mechanics of editing files.

## Repo-native prefix detection wins

Detect the repository's own convention before choosing any format:

- Read root and applicable subtree instruction files and any commit template.
- Sample recent history (`git log` output the caller provides) for the prevailing prefix scheme
  (area prefixes like `parser:`, ticket prefixes, or Conventional Commits `type(scope):`).

The detected repository convention **wins** and must be preserved. **Conventional Commits is only a
fallback** when no repo-native convention is detectable — never a mandate layered on top of an
established local style.

## Body

- Separate from the subject by one blank line.
- Explain motivation, context, and consequences a reviewer cannot infer from the diff.
- State only verified facts. Route claims through `evidence-order.md`; when evidence is absent,
  omit the claim or leave a `TODO:` placeholder.
- Attribution follows `attribution-policy.md`: no model/tool/provider trailers, footers, or badges
  unless explicitly requested for this artifact.
