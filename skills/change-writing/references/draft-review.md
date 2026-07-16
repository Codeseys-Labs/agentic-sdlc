# Draft review

Audit an existing change message (commit, PR, or squash) against evidence, convention, and policy.
Return findings and a corrected draft as text; do not apply anything.

## Checklist

1. **Accuracy vs. evidence.** Every claim traces to the verified diff or shown gate results
   (`evidence-order.md`). Flag any assertion — test pass, issue link, risk, reviewer, breaking
   change, user impact — with no backing evidence. Recommend omit or a `TODO:` placeholder.
2. **Scope.** For a PR/squash, the message describes the merge-base footprint, not just the HEAD
   diff (`pull-request.md`).
3. **Convention.** The message follows the repository's detected convention; Conventional Commits is
   only a fallback (`commit.md`).
4. **Attribution.** No model/tool/provider trailer, generated-by footer, or agent badge unless the
   user explicitly requested it for this artifact (`attribution-policy.md`). A real human
   `Co-Authored-By:` trailer is allowed and must not be stripped.
5. **Form.** Imperative subject, blank line before body, body explains why not what.

## Output

- A short list of concrete findings (what is unsupported, off-convention, or policy-violating).
- A corrected draft the caller may choose to use. The caller still owns publication; this review
  never edits history or a PR itself.
