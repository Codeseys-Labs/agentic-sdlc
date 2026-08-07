# Conventional Commits v1.0.0 conformance

Self-contained: the grammar, the sixteen rules in applicable form, type selection, breaking-change
marking, footer syntax, the SemVer mapping, and where the widely used linter diverges from the
spec. You do not need `SKILL.md` or `commit.md` open to apply this.

Rule and FAQ text quoted here is from the Conventional Commits v1.0.0 specification, published at
`conventionalcommits.org` under CC BY 3.0.

## Does Conventional Commits apply here at all?

Answer this first. Getting it wrong is more damaging than any formatting error, because it means
rewriting a repository's established convention into a foreign one.

1. **Does the history or a policy file already use `type(scope): subject`?** Then conform to the
   **local dialect**, including local type names, not to any generic type list. A repository whose
   history contains `merge:` has `merge:` as a valid type in that repository, whatever a linter's
   default enum says.
2. **Does the repository run a Conventional Commits linter** (a commitlint config, a `commit-msg`
   hook, a release automation tool that parses commits)? Then **that configuration**, not the
   specification, is the operative constraint. Read the divergences below.
3. **Neither?** Then Conventional Commits is a **fallback only** — the last rung of the evidence
   ladder in `evidence-order.md`. Say so when proposing it, rather than presenting it as required.

The repository's own convention wins in all three cases. This file teaches a format; it never
converts that format into a mandate. That rule is normative in `commit.md` and this file is
subordinate to it.

## The grammar

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

The blank lines are part of the grammar, not typography. Without the blank line before the body,
a parser reads the body as part of the description; without the blank line before the footers, it
reads a footer as body prose.

## The sixteen rules, in applicable form

1. Commits are prefixed with a **type**, a noun, followed by an optional scope, an optional `!`,
   and a **required** terminal colon **and space**.
2. `feat` MUST be used when a commit adds a new feature.
3. `fix` MUST be used when a commit is a bug fix.
4. A scope MAY follow the type: a noun in parentheses naming a section of the codebase —
   `fix(parser):`.
5. The description immediately follows the colon and space.
6. A longer body MAY be provided, beginning **one blank line after** the description.
7. The body is free-form and MAY be any number of newline-separated paragraphs.
8. Footers MAY be provided one blank line after the body, each as a token, then either `: ` or
   ` #`, then a value.
9. **Footer tokens use `-` in place of whitespace** — `Reviewed-by`, `Acked-by`. This is precisely
   what lets a parser distinguish a footer from another body paragraph. `BREAKING CHANGE` is the
   sole exception.
10. A footer value MAY contain spaces and newlines; parsing stops at the next valid token and
    separator pair.
11. Breaking changes MUST be indicated **either** in the type/scope prefix **or** in a footer.
12. As a footer: uppercase `BREAKING CHANGE`, then a colon and space, then the description.
13. In the prefix: `!` immediately **before** the colon.
14. Types other than `feat` and `fix` MAY be used — `docs: update the reference`.
15. The units of information are case-insensitive to implementors, **except** `BREAKING CHANGE`,
    which MUST be uppercase.
16. `BREAKING-CHANGE` is synonymous with `BREAKING CHANGE` as a footer token.

## Type selection

Pick from the shape of the change, not from how it feels.

| The diff | Type |
|---|---|
| New user-reachable capability, new public API, CLI, or flag | `feat` |
| Corrects wrong behaviour a user could hit | `fix` |
| Documentation or comments only | `docs` |
| Behaviour-preserving restructure | `refactor` |
| Tests only | `test` |
| Measured performance change, no behaviour change | `perf` |
| Formatting or whitespace only | `style` |
| Build system, dependencies, packaging | `build` |
| CI configuration or workflows | `ci` |
| Reverts an earlier commit | `revert` |
| Repository chores, none of the above | `chore` |
| **Two of the above genuinely apply** | Split the commit. |

On the last row, the specification's FAQ is direct: "Go back and make multiple commits whenever
possible." A commit needing two types is two changes, and the message is the symptom.

Where the repository has its own types, they take precedence over this table.

## Scope

A noun naming the part of the codebase affected, in parentheses, before the colon. Use the
repository's existing scope vocabulary — sampled from history — rather than inventing a parallel
one. Omit the scope when the change is genuinely repository-wide; an invented scope is worse than
none, because it implies a boundary that does not exist.

## Breaking changes

Two legal forms, and one subtlety worth stating because it is the most common real error:

- **Footer:** `BREAKING CHANGE: <what breaks and what to do>`, uppercase, after a blank line.
- **Prefix marker:** `!` immediately before the colon — `feat!:` or `feat(api)!:`.

**With `!` and no footer, the description itself is the breaking-change text.** So if the
description does not actually state what breaks, add the footer as well. The specification's own
canonical example pairs them:

```
feat!: drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
```

A `!` on a description that reads like an ordinary feature tells a reader something broke without
telling them what — which is worse than either form used properly.

## The five failures this file exists to prevent

| Wrong | Right | Why |
|---|---|---|
| Body on the line after the description | Blank line between them | Rule 6. Otherwise the body is parsed as description. |
| `Reviewed by: alex` | `Reviewed-by: alex` | Rule 9. A space in the token means it is not a footer. |
| `breaking change: …` | `BREAKING CHANGE: …` | Rule 15. Lowercase means it is not a breaking change. |
| `feat!: refactor the client` | `feat!: require an explicit region argument` (or add the footer) | Rule 13 plus intent: with `!`, the description carries the break. |
| `feat: add the thing.` | `feat: add the thing` | Spec-legal but linter-illegal; see below. |

## SemVer mapping

`fix` maps to a PATCH release. `feat` maps to MINOR. A breaking change — in **any** type,
whether marked by `!` or by footer — maps to MAJOR.

This mapping is the entire reason the format exists, and it is why type selection is a
correctness question rather than a stylistic one: choosing `chore` for a change that adds a flag
means a release tool will not ship the MINOR bump that change earned.

## Specification versus linter

The commonly used `@commitlint/config-conventional` preset is **stricter than the specification**
in ways that matter when predicting whether a message will be rejected:

| Constraint | Specification | The preset |
|---|---|---|
| Allowed types | Any noun (rule 14) | A closed set: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test` |
| Type case | Case-insensitive to implementors (rule 15) | Must be lower-case |
| Trailing period on the subject | Legal | Rejected |
| Subject case | Unconstrained | Sentence-case, start-case, pascal-case, and upper-case rejected |
| Header length | No limit | Capped (commonly 100 characters) |
| Blank line before body / footer | Required by the grammar | Reported as a **warning**, which does not fail a run |

Two consequences worth holding onto. First, a message can be perfectly spec-conformant and still
fail a lint run — trailing periods and a non-preset type are the usual causes. Second, a
repository with local types **must extend the type list in its own configuration**, or the hook
rejects the repository's own established convention. That is a real failure mode here: this
repository's history contains `merge:`, which the unextended preset rejects.

Severity values are `0`, `1`, `2` for off, warning, error. A warning does not fail the run, so a
"passing" lint result can still contain the blank-line problems above.

## Judging a candidate message without tooling

Seven mechanical checks, all doable by reading:

1. Type is in the **repository's** accepted set.
2. Type is lowercase.
3. Scope is a parenthesised noun, or absent.
4. Colon and space present, in that order.
5. Description is non-empty, imperative, and has no trailing period.
6. Blank line before the body, and before the footers.
7. Footer tokens are hyphenated — except `BREAKING CHANGE`, which is uppercase with a space.

Where a linter is available in the repository, its verdict on the actual configuration beats this
checklist, because the configuration is the operative constraint. A linter result is evidence
about the text; it is not authorization to commit anything, and this file never runs one.

## Edge cases

**Before the first release.** The specification's FAQ says to "proceed as if you've already
released the product" — the types and breaking markers mean the same thing at 0.x, and getting
into the habit early is what makes the later release automation trustworthy.

**Wrong type used, caught before release.** History rewriting is the caller's operation and needs
their authorization; this file does not perform or instruct it.

**Wrong type used, already released.** Nothing to fix. The practical consequence is that the
commit "will be missed by tools" that parse types — a lost changelog entry or a missed version
bump, not a corruption.

**Contributors who do not follow the convention.** The FAQ's answer is a squash-based workflow
where "lead maintainers can clean up the commit messages as they're merged" — the convention
binds the merged history, not every contributor's local commits.

**Reverts.** The specification deliberately leaves revert semantics to tooling authors, so there
is no single correct footer form. Follow whatever the repository already does; if nothing exists,
`revert` as the type with the reverted commit's subject and hash in the body is the common shape.

## Attribution is not decided here

`Co-Authored-By: …` is a **grammatically valid** footer under rules 8 and 9. Whether it is
**permitted** on a given artifact is decided solely by `attribution-policy.md`, which
default-prohibits model, tool, and provider attribution. Grammar and permission are separate
questions, and this file answers only the first — adding an opinion on the second would fork a
normative source.
