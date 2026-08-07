# Authoring Mermaid diagrams for SDLC artifacts

Self-contained: how to scope a diagram, pick its type, set its depth, label it so it carries
information, and avoid the parse traps that either fail loudly or — worse — succeed while drawing
something other than what you wrote. You do not need any `SKILL.md` open to use this.

**Scope.** This file covers *authoring*: the source text and whether it says what you meant.
Rendering, export, and format conversion are a separate concern owned by the repository's pinned
rendering pipeline and by whichever host diagram skill is loaded. Nothing here pins a renderer.

**Promotion trigger.** This is a reference rather than its own skill deliberately: the host
environments this bundle targets generally already carry a general-purpose diagram skill, and this
bundle currently ships no diagrams of its own. Promote this to `skills/mermaid-diagrams/` when
either condition changes — when diagrams become a routine, recurring artifact of the SDLC loop
here (several per release, in ADRs or design docs), or when a host without a diagram skill becomes
a supported target. Until then a second selection-surface entry would cost description bytes for a
capability that fires rarely and overlaps an incumbent.

## Step 1 — name the perspective before drawing anything

One diagram answers **one question**. Name which, in words, before writing a line of source. The
common perspectives:

| Perspective | The question it answers |
|---|---|
| `overall-architecture` | What parts exist, and how do they relate? |
| `request-lifecycle` | How does a request enter the system and get handled, end to end? |
| `data-flow` | Where does data come from, what transforms it, where does it land? |
| `dependency-map` | What depends on what, and what is shared? |
| `external-integrations` | What does this connect to outside itself, and why? |
| `state-transitions` | What states exist, and what triggers each change? |
| `command-surface` | What commands exist, and how are they dispatched? |
| `pipeline` | What are the stages, in what order, with what gates? |
| `storage` | What persists where — database, cache, queue, object store? |
| `extension-points` | Where can this be extended, and what registers an extension? |

**If you cannot name the perspective, you are drawing a picture rather than answering a
question.** Two perspectives in one diagram means two diagrams — and that is the single most
common reason a diagram is unreadable, ahead of every syntax issue in this file.

The perspective catalog and the leaf/group recursion in step 3 are adapted as ideas from the
oh-my-mermaid project (MIT-licensed). The wording here is this bundle's own; no upstream text is
reproduced, and no affiliation is claimed.

## Step 2 — pick the diagram type

| The question | Type |
|---|---|
| What are the parts and how do they connect? | `flowchart` (or `graph`) |
| Who calls whom, in what order, over time? | `sequenceDiagram` |
| What states exist and what triggers transitions? | `stateDiagram-v2` |
| What entities and relations does the schema hold? | `erDiagram` |
| What types exist and how do they inherit? | `classDiagram` |
| What work happens over calendar time? | `gantt` |
| What is the branch and merge topology? | `gitGraph` |
| Decomposition of an idea with no edges worth labelling | `mindmap` |

Two types to treat with care: the C4 diagram types are marked experimental upstream and their
syntax can change, and `architecture-beta` is new with a small built-in icon set. For anything
that must keep rendering across upstream versions, a labelled `flowchart` with `subgraph`
boundaries is the durable choice.

## Step 3 — set the depth with the leaf-or-group test

For each node, ask: **does this contain distinct internal components worth their own diagram?**

- **Yes → it is a group.** Write a child diagram for it and recurse there. In the parent, it stays
  one node.
- **No → it is a leaf.** Stop. A single file, a trivial wrapper, or an external system you do not
  control is always a leaf.

Name group nodes after the directory or section they correspond to, in kebab-case, so the diagram
tree mirrors the actual tree and stays navigable as both drift.

**Every node gets a description somewhere** — in the label, in adjacent prose, or in the child
diagram. An undocumented node asserts that something exists without saying what it does, which
sends the reader to the source anyway.

## Step 4 — the authoring rules

1. **Every edge carries a meaningful label.** `A -->|"validates the receipt"| B`. An unlabelled
   edge asserts that a relationship exists without saying what it is, and the reader cannot
   recover the difference between "calls", "depends on", "writes to", and "is deployed with".
2. **Make nodes traceable.** Where a node maps to a real file or module, put the path in the
   label alongside the display name, so a reader can go look.
3. **`graph LR` by default; `graph TD` for hierarchies.** Left-to-right reads naturally for
   pipelines and flows; top-down for containment and trees. Valid direction keywords: `TB` (same
   as `TD`), `BT`, `LR`, `RL`.
4. **Cap the node count at roughly fifteen.** Past that, either split by perspective or push
   detail into a child diagram. A diagram nobody can read at a glance has failed regardless of
   correctness.
5. **Use `classDef` for styling, not external CSS.** Mermaid's own documentation notes that
   external CSS does not reliably apply, because Mermaid's internal styles win on specificity.
   Keep one semantic palette across a family of diagrams — entry point, external system, store,
   concern — and pair dark fills with light strokes so the result survives both light and dark
   viewing themes.
6. **Link across diagrams by name rather than duplicating a subtree.** A subtree copied into two
   diagrams will diverge, and the reader has no way to know which copy is current.
7. **Committed `.mmd` files are diffable source; inline fenced blocks render in place.** Use a
   file when the diagram is an artifact in its own right and will be reviewed or re-rendered; use
   an inline fence when it exists to serve the prose immediately around it.

## Step 5 — the parse traps

Every row below was executed against `@mermaid-js/mermaid-cli` 11.16.0 on 2026-08-07 and reflects
observed behaviour, not inherited claims.

### Traps that fail loudly (exit 1)

These are the easy ones — you find out immediately.

| Trap | Reproducer | Fix |
|---|---|---|
| Lowercase `end` as a node ID | `a[Start] --> end[Finish]` | Capitalize it (`End`), rename, or wrap it. In sequence diagrams, enclose with `()`, `""`, `{}`, or `[]`. |
| `class` as a node ID | `class[Class] --> B` | Rename or suffix — `class-node`. |
| `style` as a node ID | `style[S] --> B` | Rename. |
| `graph` as a node ID | `graph[G] --> B` | Rename. |
| `subgraph` as a node ID | `subgraph[S] --> B` | Rename. |
| Unquoted label containing `(` or `,` | `A[Label with (parens), and commas] --> B` | **Always quote** labels containing `(`, `)`, `,`, `;`, or `:`. The quoted form parses cleanly. |
| Unbalanced sequence activation across `alt` branches | `A->>+B: go`, then `-` deactivation in **both** the `alt` and `else` branches | Deactivate **after** the block closes, not once per branch. The error reads `Trying to inactivate an inactive participant`. |

### Traps that succeed and draw the wrong thing

These are the dangerous ones, because exit code 0 tells you nothing is wrong.

| Trap | Reproducer | What actually happens |
|---|---|---|
| `o`-prefixed node ID directly after `---` | `A---oB` | The `o` is consumed as a **circle edge marker**. Verified: the output carries `marker-end="…circleEnd"` and the node label renders as `B`, not `oB`. Adding a space — `A --- oB` — produces no marker and the correct `oB` label. Capitalizing also works. |
| `x`-prefixed node ID directly after `---` | `A---xB` | Same failure with a **cross** marker; the label renders as `B`. Same fixes. |
| Misspelled frontmatter config key | `diagramPaddingx: abc` under `config: flowchart:` | **Silently ignored.** Exit 0, no diagnostic, no warning. Never assume a config setting took effect — verify against the rendered output. |

### Claims that do NOT reproduce — do not teach these

Checked and found harmless in 11.16.0. Each parses cleanly at exit 0, so do not add them to a
reserved-word list or "fix" source that uses them:

- `click` as a node ID — fine.
- `default` as a node ID — fine.
- An edge label beginning with `o` (`A -->|ok| B`) — fine. The `o` trap is specific to a **node
  ID** immediately following `---` with no space, not to label text.

## Step 6 — verify, and know what verification proves

A parse check is the cheap first gate: a clean parse means the source is syntactically valid.

**A clean parse does not mean a good diagram.** The `o`/`x` marker traps and the silently-ignored
config key above are exactly the class of defect that passes the parser and fails the reader. Two
things a parse check cannot tell you: whether the layout is legible, and whether the diagram
answers the perspective you named in step 1. Look at the rendered output, or hand it to whichever
render pipeline the repository has pinned.

A parse result — like any check result in this bundle — is evidence about the artifact. It
authorizes nothing.

## Reviewing someone else's diagram

In order, because the first failure usually makes the rest moot:

1. Can you name the one question it answers? If not, it needs splitting before anything else.
2. Are there unlabelled edges? Each one is missing information the author had and the reader does
   not.
3. Is the node count past roughly fifteen?
4. Does every node correspond to something real, and can you tell what it is?
5. Are the group nodes' names still accurate against the tree they mirror?
6. If the source uses `---` links, check for `o` or `x` immediately after the dashes.
