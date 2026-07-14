# Decision register

This register distills binding direction from the approved plan, the canonical Seeds queue, and the approved change-writing design. It explains decisions; it does not grant execution authority.

| ID | Decision | Status and consequence | Evidence |
|---|---|---|---|
| D-01 | **Agentic SDLC** and `agentic-sdlc` become the intended canonical public identity. | Accepted direction. The atomic identity-cutover Seed owns the implementation; local checkout and GitHub repository renames remain separate approval-gated work. | [Approved plan](approved-plan.md), [Seeds `0ec5`](seeds-dependency-map.md#identity-and-release) |
| D-02 | Remove CAO rather than retain compatibility tombstones. | Accepted direction. The removal Seed permits a private regression denylist and negative fixtures only; it does not preserve a shipped compatibility surface. | [Approved plan](approved-plan.md), [Seeds `9b26`](seeds-dependency-map.md#identity-and-release) |
| D-03 | Git remains the interoperability, integration, receipt, CI, branch, and forge authority. | Invariant. jj is an explicit opt-in substrate only after certification and uses an immutable Git handoff. | [Approved plan](approved-plan.md), [jj sources](#primary-sources-carried-forward) |
| D-04 | Do not mix jj work with a Git worktree in one assignment. | Invariant. jj work uses native jj workspaces and fails closed for unsupported conditions. | [Approved plan](approved-plan.md) |
| D-05 | Keep role separation while sharing contracts. | Accepted direction. One integrator owns fan-in; planners/directors do not implement or disposition Seeds; critics and reviewers remain advisory. | [Approved plan](approved-plan.md), [Seeds `9140`](seeds-dependency-map.md#capability-lanes) |
| D-06 | Build a bounded dynamic-workflow loop. | Accepted direction. Decompose first, keep one writer per worktree and integrator WIP at one, and do not create a second queue or unbounded recursive delegation. | [Approved plan](approved-plan.md), [routing receipt](workflow-routing-certification.md) |
| D-07 | Build the Mermaid family as one router plus one installable skill per documented type. | Accepted direction. A browser/dependency certification and SVG-safety foundation precede the five type-family lanes, router, and conformance. | [Approved plan](approved-plan.md), [Mermaid sources](#primary-sources-carried-forward) |
| D-08 | Change writing is a standalone output-only capability. | Accepted design. It proposes commit, PR, squash, and draft-review text from verified evidence; it does not gain Git or forge mutation authority. Attribution is opt-in for the specific artifact. | [Approved design](intent-audit.md#approved-auxiliary-design) and [Seeds `7c70`](seeds-dependency-map.md#capability-lanes) |
| D-09 | Mise is the managed bootstrap and `mise run check` is the authoritative repository gate. | Invariant. Passing a gate is evidence, not authorization for an outward effect. | [Approved plan](approved-plan.md), repository instructions |
| D-10 | Route substantive work explicitly but record only verified resolution facts. | Certified only for call success and base-model visibility. Resolved effort and a distinct resolved `[1m]` context signal are unverified, so downstream work uses bounded decomposition. | [Routing certification](workflow-routing-certification.md) |
| D-11 | Preserve authorization boundaries. | Local implementation approval does not authorize fan-in, push, PR creation or mutation, merge, checkout rename, trust/config mutation, or repository rename. | [Approved plan](approved-plan.md) |

## Primary sources carried forward

These are the primary jj and Mermaid citations already recorded by the approved plan. They are reproduced as citations only; this archive performed no web browsing or fresh verification.

### jj

- <https://docs.jj-vcs.dev/latest/git-compatibility/>
- <https://docs.jj-vcs.dev/latest/operation-log/>
- <https://docs.jj-vcs.dev/latest/working-copy/>
- <https://docs.jj-vcs.dev/latest/conflicts/>

### Mermaid

- <https://mermaid.js.org/intro/>
- <https://mermaid.js.org/config/usage.html>
- <https://mermaid.js.org/config/setup/mermaid/interfaces/Mermaid.html>
- <https://github.com/mermaid-js/mermaid-cli>
