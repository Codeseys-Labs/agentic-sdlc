# 2026-08-24 install-UX research corpus

The evidence base behind issues #8 through #13 (the Install UX v2 decision record and its five
execution issues). Produced 2026-08-24 by an 11-agent research program against checkout `e0fbf92`
(v0.7.4) and live hosts (Claude Code 2.1.241, uv 0.11.8, mise 2026.8.12), in three adversarial
phases: five parallel researchers, three competing architecture designs argued at full strength,
three cross-assigned critiques instructed to refute. Load-bearing claims were re-verified against
the checkout or live hosts before the issues were filed; claims that could not be grounded are
marked UNVERIFIED in place.

Issue citations of the form `NN-*.md`, `design-*.md`, or `critique-*.md` resolve into this
directory. Bare `file:line` citations refer to the repository at `e0fbf92`.

## Research (phase 1)

| File | Scope |
|---|---|
| `01-installer-lifecycle.md` | The current install architecture end to end: four acquisition planes, the eight-layer stack, six state stores, 52 protected invariants, the friction audit, and why project scope is structurally absent |
| `02-decision-corpus.md` | What the ADR corpus and plans already decide; the SUPPORT/CONFLICT table against the proposed redesign; ADR-0031 in detail |
| `03-bun-facts.md` | Bun 1.4.x as a compiled-CLI platform, verified against live upstream sources; corrections to the repo's 2026-08-23 survey |
| `04-claude-plugin-channel.md` | First pass at the native plugin channel. **Superseded in part**: understates coverage; where it conflicts with `critique-c.md`'s live measurements, critique-c wins |
| `05-receipts-machinery.md` | The `ccodex sdlc` receipts lifecycle as implemented; the live-verified finding that both published prereleases ship a dead sdlc plane |

## Designs (phase 2, each argued at full strength)

| File | Architecture |
|---|---|
| `design-a-evolutionary.md` | Evolutionary inversion, no rewrite: mise acquires the release tree, ccodex is the one front door |
| `design-b-bun-rewrite.md` | Full Bun 1.4 compiled binary with embedded payload and self-update |
| `design-c-lean.md` | Native-channels-first: Claude's plugin marketplace as the Claude-plane front door, maximum deletion |

## Critiques (phase 3, cross-assigned, instructed to refute)

| File | Verdict |
|---|---|
| `critique-a.md` | ADOPT-WITH-CHANGES: adopt design A's subtractions, reject nearly all its additions; five confirmed factual errors |
| `critique-b.md` | REJECT the architecture, keep ADR-0031; harvest G1-G3 in Python |
| `critique-c.md` | ADOPT-WITH-CHANGES: central evidence correction confirmed by live measurement; five findings break the proposal as written |

The corpus is a dated snapshot, not a living document. Where a report and a critique disagree,
the critique's live measurement wins; where either disagrees with the tree at HEAD, the tree wins.
