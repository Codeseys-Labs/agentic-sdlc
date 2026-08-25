# Evidence order

Author every claim from the strongest available evidence. Walk this six-step ladder in order and
stop at the strongest source that answers the question; never assert what no step supports.

1. **The verified diff.** What actually changed — files, hunks, added/removed symbols — as observed
   in the diff the caller provides, not as remembered from the conversation.
2. **Gate and test evidence.** Only results the caller has actually run and shown. A passing gate is
   a claim only when its command and outcome are in hand.
3. **Repository policy.** Root and applicable subtree instruction files, commit/PR templates, and
   `CONTRIBUTING`-style docs that dictate message shape and required sections.
4. **Observed history.** The style of recent commits and merged PRs on this repository (prefix
   scheme, tense, body structure) as the concrete local convention.
5. **Linked work items.** Issue or ticket references the caller supplied or that the diff itself
   makes unambiguous — never guessed from a plausible number.
6. **Generic convention.** Conventional Commits and similar defaults, used only as a **fallback**
   when no repo-native convention is detectable.

## Omit-or-placeholder rule

When evidence for a claim is missing, do one of two things and nothing else:

- **Omit the claim** — leave it out of the message entirely; or
- **Emit a concrete `TODO:` placeholder** the caller must resolve, e.g. `TODO: link the tracking
  issue` or `TODO: confirm the migration was run in staging`.

Never fill a gap with plausible prose. Do not invent test results, issue links, risks, reviewers,
breaking changes, benchmark numbers, or user impact. An unverifiable "all tests pass" is worse than
silence, because the reader trusts it.
