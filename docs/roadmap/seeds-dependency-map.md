# Seeds dependency map

This is a readable reference projection of the canonical [`.seeds/issues.jsonl`](../../.seeds/issues.jsonl) store. IDs, statuses, titles, direct `blockedBy`, and direct `blocks` values below are transcribed from that store. An em dash means the field is absent. The table does not infer unrecorded dependencies.

**Source receipt:** SHA-256 `0f239c6d0dbe14506b800cfc7ddb2a38cea030d1460e29c38ca2014606cf98e7` at archive generation.

## Queue summary

- **5 epics:** all open.
- **36 non-epic work items:** 1 closed, 3 in progress, 32 open.
- **33 work items have direct blockers** in the canonical store.

## Epics

| ID | Status | Priority | Title |
|---|---|---:|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` | open | 0 | Recover and rename Agentic SDLC |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` | open | 1 | Expand Agentic SDLC capabilities |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-faa6` | open | 1 | Certify and enable jj opt-in |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` | open | 1 | Build the complete Mermaid skill family |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` | open | 2 | Build Evolutionary Core and portability |

## Identity and release

| ID | Epic | Type | Status | Priority | Title | Blocked by (direct) | Blocks (direct) |
|---|---|---|---|---:|---|---|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-addd` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | task | closed | 0 | Certify workflow model routing | — | — |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-9fe9` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | task | in_progress | 1 | Archive plans and roadmap evidence | — | — |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-b3f6` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | feature | in_progress | 0 | Finish exact Seeds 0.5.14 execution contract | — | `agentic-sdlc-orchestrator-wt-roadmap-docs-e4c5` — Review and integrate Seeds 0.5.14 wave |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-e4c5` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | task | open | 0 | Review and integrate Seeds 0.5.14 wave | `agentic-sdlc-orchestrator-wt-roadmap-docs-b3f6` — Finish exact Seeds 0.5.14 execution contract | `agentic-sdlc-orchestrator-wt-roadmap-docs-9b26` — Remove CAO completely |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-9b26` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | feature | open | 0 | Remove CAO completely | `agentic-sdlc-orchestrator-wt-roadmap-docs-e4c5` — Review and integrate Seeds 0.5.14 wave | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | feature | open | 0 | Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-9b26` — Remove CAO completely | `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` — Harden release lifecycle before Core<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-9140` — Consolidate shared role and artifact contracts<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-7c70` — Build attribution-free change-writing skill<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-6983` — Harden Git-default sdlc-init<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-dd16` — Consolidate Git change-flow knowledge<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-69b0` — Harden repository toolchain and security gates<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-ab53` — Certify jj 0.43.0 compatibility and handoff<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-a0cd` — Certify Mermaid dependency and browser foundation<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc` — Profile all six workflow model tiers and effort levels |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | feature | open | 1 | Harden release lifecycle before Core | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-3989` — Rename local checkout directory<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-1b9b` — Rename GitHub repository to Codeseys-Labs/agentic-sdlc<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-3989` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | task | open | 2 | Rename local checkout directory | `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` — Harden release lifecycle before Core | — |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-1b9b` | `agentic-sdlc-orchestrator-wt-roadmap-docs-29fb` — Recover and rename Agentic SDLC | task | open | 2 | Rename GitHub repository to Codeseys-Labs/agentic-sdlc | `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` — Harden release lifecycle before Core | — |

## Capability lanes

| ID | Epic | Type | Status | Priority | Title | Blocked by (direct) | Blocks (direct) |
|---|---|---|---|---:|---|---|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-9140` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 1 | Consolidate shared role and artifact contracts | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-2ade` — Build bounded Deep Work Loop<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-9e29` — Harden HyperResearch and Research OS |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-7c70` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 1 | Build attribution-free change-writing skill | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-6983` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 1 | Harden Git-default sdlc-init | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-2f4c` — Generate hierarchical repository instructions<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-85fb` — Add jj-colocated profile to sdlc-init |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-2f4c` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 2 | Generate hierarchical repository instructions | `agentic-sdlc-orchestrator-wt-roadmap-docs-6983` — Harden Git-default sdlc-init | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-2ade` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 2 | Build bounded Deep Work Loop | `agentic-sdlc-orchestrator-wt-roadmap-docs-9140` — Consolidate shared role and artifact contracts | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-9e29` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 2 | Harden HyperResearch and Research OS | `agentic-sdlc-orchestrator-wt-roadmap-docs-9140` — Consolidate shared role and artifact contracts | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-dd16` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 2 | Consolidate Git change-flow knowledge | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-69b0` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 2 | Harden repository toolchain and security gates | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | task | in_progress | 0 | Profile all six workflow model tiers and effort levels | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-7fe3` — Update bundled and global model-rightsizing skills |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-7fe3` | `agentic-sdlc-orchestrator-wt-roadmap-docs-c558` — Expand Agentic SDLC capabilities | feature | open | 1 | Update bundled and global model-rightsizing skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc` — Profile all six workflow model tiers and effort levels | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |

## jj opt-in

| ID | Epic | Type | Status | Priority | Title | Blocked by (direct) | Blocks (direct) |
|---|---|---|---|---:|---|---|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-ab53` | `agentic-sdlc-orchestrator-wt-roadmap-docs-faa6` — Certify and enable jj opt-in | feature | open | 1 | Certify jj 0.43.0 compatibility and handoff | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-9b8b` — Implement explicit jj-colocated opt-in |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-9b8b` | `agentic-sdlc-orchestrator-wt-roadmap-docs-faa6` — Certify and enable jj opt-in | feature | open | 2 | Implement explicit jj-colocated opt-in | `agentic-sdlc-orchestrator-wt-roadmap-docs-ab53` — Certify jj 0.43.0 compatibility and handoff | `agentic-sdlc-orchestrator-wt-roadmap-docs-85fb` — Add jj-colocated profile to sdlc-init |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-85fb` | `agentic-sdlc-orchestrator-wt-roadmap-docs-faa6` — Certify and enable jj opt-in | feature | open | 2 | Add jj-colocated profile to sdlc-init | `agentic-sdlc-orchestrator-wt-roadmap-docs-9b8b` — Implement explicit jj-colocated opt-in<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-6983` — Harden Git-default sdlc-init | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |

## Mermaid skill family

| ID | Epic | Type | Status | Priority | Title | Blocked by (direct) | Blocks (direct) |
|---|---|---|---|---:|---|---|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-a0cd` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 1 | Certify Mermaid dependency and browser foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` — Cut over to canonical agentic-sdlc identity atomically | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 1 | Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-a0cd` — Certify Mermaid dependency and browser foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-6cd7` — Build structural Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-b761` — Build planning Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-1718` — Build quantitative Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-c1a7` — Build technical Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-aa2a` — Build conceptual Mermaid diagram skills |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-6cd7` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build structural Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-b761` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build planning Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-1718` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build quantitative Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-c1a7` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build technical Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-aa2a` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build conceptual Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` — Build Mermaid validator and SVG safety foundation | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | feature | open | 2 | Build Mermaid umbrella router | `agentic-sdlc-orchestrator-wt-roadmap-docs-6cd7` — Build structural Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-b761` — Build planning Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-1718` — Build quantitative Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-c1a7` — Build technical Mermaid diagram skills<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-aa2a` — Build conceptual Mermaid diagram skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-cdb7` — Certify Mermaid bundle conformance |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-cdb7` | `agentic-sdlc-orchestrator-wt-roadmap-docs-214e` — Build the complete Mermaid skill family | task | open | 1 | Certify Mermaid bundle conformance | `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` — Build Mermaid umbrella router | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 |

## Evolutionary Core and portability

| ID | Epic | Type | Status | Priority | Title | Blocked by (direct) | Blocks (direct) |
|---|---|---|---|---:|---|---|---|
| `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` | `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` — Build Evolutionary Core and portability | feature | open | 1 | Build Evolutionary Core Milestone 2 | `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` — Harden release lifecycle before Core<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-7c70` — Build attribution-free change-writing skill<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-2f4c` — Generate hierarchical repository instructions<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-2ade` — Build bounded Deep Work Loop<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-9e29` — Harden HyperResearch and Research OS<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-dd16` — Consolidate Git change-flow knowledge<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-69b0` — Harden repository toolchain and security gates<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-85fb` — Add jj-colocated profile to sdlc-init<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-cdb7` — Certify Mermaid bundle conformance<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-7fe3` — Update bundled and global model-rightsizing skills | `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` — Build Claude Golden Wave Milestone 3 |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` | `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` — Build Evolutionary Core and portability | feature | open | 2 | Build Claude Golden Wave Milestone 3 | `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` — Build Evolutionary Core Milestone 2 | `agentic-sdlc-orchestrator-wt-roadmap-docs-7c4e` — Build portability and pack lifecycle Milestone 4<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-87ef` — Certify CCP and ccodex behavior |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-7c4e` | `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` — Build Evolutionary Core and portability | feature | open | 2 | Build portability and pack lifecycle Milestone 4 | `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` — Build Claude Golden Wave Milestone 3 | `agentic-sdlc-orchestrator-wt-roadmap-docs-e541` — Implement optional CCP and ccodex lifecycle |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-87ef` | `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` — Build Evolutionary Core and portability | task | open | 3 | Certify CCP and ccodex behavior | `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` — Build Claude Golden Wave Milestone 3 | `agentic-sdlc-orchestrator-wt-roadmap-docs-e541` — Implement optional CCP and ccodex lifecycle |
| `agentic-sdlc-orchestrator-wt-roadmap-docs-e541` | `agentic-sdlc-orchestrator-wt-roadmap-docs-ea8d` — Build Evolutionary Core and portability | feature | open | 3 | Implement optional CCP and ccodex lifecycle | `agentic-sdlc-orchestrator-wt-roadmap-docs-7c4e` — Build portability and pack lifecycle Milestone 4<br>`agentic-sdlc-orchestrator-wt-roadmap-docs-87ef` — Certify CCP and ccodex behavior | — |

## Direct-edge reading aid

An edge `A → B` means A directly blocks B. This list is mechanically derived from the canonical `blocks` fields and is redundant with the tables above so reviewers can inspect topology without resolving two columns.

- `agentic-sdlc-orchestrator-wt-roadmap-docs-b3f6` → `agentic-sdlc-orchestrator-wt-roadmap-docs-e4c5`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-e4c5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-9b26`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-9b26` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-9140`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-7c70`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-6983`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-dd16`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-69b0`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-ab53`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-a0cd`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0ec5` → `agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` → `agentic-sdlc-orchestrator-wt-roadmap-docs-3989`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` → `agentic-sdlc-orchestrator-wt-roadmap-docs-1b9b`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-4cef` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-9140` → `agentic-sdlc-orchestrator-wt-roadmap-docs-2ade`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-9140` → `agentic-sdlc-orchestrator-wt-roadmap-docs-9e29`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-7c70` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-6983` → `agentic-sdlc-orchestrator-wt-roadmap-docs-2f4c`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-6983` → `agentic-sdlc-orchestrator-wt-roadmap-docs-85fb`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-2f4c` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-2ade` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-9e29` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-dd16` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-69b0` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-ab53` → `agentic-sdlc-orchestrator-wt-roadmap-docs-9b8b`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-9b8b` → `agentic-sdlc-orchestrator-wt-roadmap-docs-85fb`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-85fb` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-a0cd` → `agentic-sdlc-orchestrator-wt-roadmap-docs-8459`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` → `agentic-sdlc-orchestrator-wt-roadmap-docs-6cd7`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` → `agentic-sdlc-orchestrator-wt-roadmap-docs-b761`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` → `agentic-sdlc-orchestrator-wt-roadmap-docs-1718`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` → `agentic-sdlc-orchestrator-wt-roadmap-docs-c1a7`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-8459` → `agentic-sdlc-orchestrator-wt-roadmap-docs-aa2a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-6cd7` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-b761` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-1718` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-c1a7` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-aa2a` → `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-0f3a` → `agentic-sdlc-orchestrator-wt-roadmap-docs-cdb7`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-cdb7` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92` → `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` → `agentic-sdlc-orchestrator-wt-roadmap-docs-7c4e`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-cf4a` → `agentic-sdlc-orchestrator-wt-roadmap-docs-87ef`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-7c4e` → `agentic-sdlc-orchestrator-wt-roadmap-docs-e541`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-87ef` → `agentic-sdlc-orchestrator-wt-roadmap-docs-e541`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc` → `agentic-sdlc-orchestrator-wt-roadmap-docs-7fe3`
- `agentic-sdlc-orchestrator-wt-roadmap-docs-7fe3` → `agentic-sdlc-orchestrator-wt-roadmap-docs-fb92`

## Current work

- **In progress:** `agentic-sdlc-orchestrator-wt-roadmap-docs-9fe9` — Archive plans and roadmap evidence; `agentic-sdlc-orchestrator-wt-roadmap-docs-b3f6` — Finish exact Seeds 0.5.14 execution contract; `agentic-sdlc-orchestrator-wt-roadmap-docs-f4dc` — Profile all six workflow model tiers and effort levels.
- **Closed:** `agentic-sdlc-orchestrator-wt-roadmap-docs-addd` — Certify workflow model routing.
