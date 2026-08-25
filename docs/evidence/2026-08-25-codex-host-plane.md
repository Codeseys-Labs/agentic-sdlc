# Codex host plane — capability evidence for the release contract's companion row

**Seed:** agentic-sdlc-7a2b (wave WX, the Codex arm of the receipted lifecycle)
**Observed:** 2026-08-25T19:05:07Z, on Linux 6.18.33.2-microsoft-standard-WSL2 x86_64 (WSL2)
**Subject:** `policy/release-contract.v1.json` → `compatibility.companion_hosts.codex`

**Why this file exists.** ADR-0027 item 1 requires each product surface to publish a minimum host
and feature requirement, and item 4 says a companion host never inherits Core's tier. So the codex
row cannot borrow the Claude Code Core row's floor or its capability canary, and this document is
the row's own evidence — including, deliberately, the parts of it that are **not** evidenced.
Nothing here is inherited from the user-scope Claude journeys.

## What was observed, verbatim

```
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-08-25T19:05:07Z

$ uname -srm
Linux 6.18.33.2-microsoft-standard-WSL2 x86_64

$ command -v codex
/home/codeseys/.local/bin/codex

$ codex --version
codex-cli 0.148.0
$ echo "exit $?"
exit 0
```

Two further facts read from the same binary, because both bear on how the lifecycle observes it:

- Its first four bytes are `\x7fELF`, so it is a native x86-64 executable of 251,271,488 bytes and
  **not** a `#!/usr/bin/env node` script. The interpreter-resolution hazard AGENTS.md records for
  the pinned `ocx` (a shebang script whose interpreter the kernel resolves by NAME from the child's
  PATH, agentic-sdlc-21f4) therefore does not apply to this observation.
- The version banner `codex-cli 0.148.0` yields exactly `0.148.0` under the version regex the
  lifecycle modules use (`(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)`, written out
  rather than with `\d` so a Unicode-digit lookalike is a different token), and that value is an
  anchored three-part SemVer, which is what `check_compatibility` compares against the row's floor.

## What each row field is, and what it rests on

| Field | Value | What it rests on |
|---|---|---|
| key | `codex` | The agent selector the closed host-plane table and `--host` admit. Not a claim about the host application's name. |
| `host` | `codex-cli` | **The host's own name for itself**, read from its `--version` banner above. Not chosen. |
| `minimum_host_version` | `0.148.0` | The **only version this project has ever observed**. See the honesty note below — this is not a measured feature floor. |
| `minimum_is_eligibility_only` | `true` | ADR-0027 item 2: meeting a minimum makes a tuple eligible for assessment and nothing more. |
| `required_capabilities` | `["configured-home-skill-and-agent-discovery"]` | **Declared and unevidenced.** See below. |
| `surface` | `companion-codex` | Its own surface, never Core's (`core`), per ADR-0027 item 4. |
| `certification_requires_current_capability_evidence` | `true` | Same rule as Core's: a qualified tuple needs a current canary. |

## The minimum is an observation, not a measured floor — read this before moving it

The Claude Code Core minimum `2.1.154` comes from vendor documentation of the Dynamic Workflows
feature floor (ADR-0027's Context section cites it). **No equivalent vendor document was found for
Codex CLI's discovery of skills and agent definitions from its configured home**, so there is no
measured floor to publish. The row states the version this project observed and refuses every older
version instead:

- Refusing an unobserved older host is **failing closed**. It is not a claim that those versions do
  not work; it is a refusal to assert compatibility with a host nobody here has run.
- `minimum_is_eligibility_only: true` is what keeps that honest. Meeting `0.148.0` admits the
  activation; it certifies nothing.
- The consequence to accept: an operator on an older Codex CLI is refused by name and their remedy
  is to upgrade or to gather the evidence that lowers this floor. That is the deliberate trade.

A later wave that measures a real floor should **lower** this value with its own transcript. Raising
it as codex releases move would be the "blanket latest" claim the claim-lint forbids.

## The required capability is declared and unevidenced, on purpose

The codex payload is skills plus `agents/*.toml` definitions, copied into the configured home. What
the plane actually depends on from its host is that the host **reads** them from there. That is the
capability the row names: `configured-home-skill-and-agent-discovery`.

**It is not evidenced here, and could not be without a live authorized session.** Proving the host
loads an installed skill means running a real Codex turn — network, credentials, and a model
response — which is a separately authorized effect and not this wave's to take. So:

- The capability is **DECLARED** in the row, which makes a future codex support row uncertifiable
  until a live journey records it passing (`_validate_release_support_rows` requires a
  `certified`/`capability-qualified` row's `capability_evidence.passed_capabilities` to cover its
  surface's `required_capabilities`).
- `compatibility.support_rows` carries **no** codex tuple. Nothing in this contract states that any
  codex tuple is certified, capability-qualified, or experimental.
- An **empty** capability list was the alternative and was rejected: it would assert that the codex
  plane needs nothing from its host, which is false, and it would let a future support row certify
  with nothing to pass.

## What this evidence does NOT establish

- That Codex CLI 0.148.0 discovers, loads, or executes any installed skill or agent definition.
  Nothing was run beyond `--version`.
- That `0.148.0` is the lowest working version, or that any newer version works.
- That the installed bytes are correct for this host's expectations: the lifecycle verifies each
  entry against the candidate manifest, which is a claim about the payload, not about the host.
- Any tier for any codex tuple. Installing seals a receipt; a receipt is evidence of an activation
  and authorizes no push, publication, merge, or deployment.

## Where the machine-checked half lives

- `scripts/validate_bundle.py` pins this row's host, surface, floor, and capability list, and
  requires the row to exist for every agent the receipted lifecycle admits — so deleting it fails
  `mise run validate` rather than surfacing at an operator's first codex install.
- `tests/test_release_contract.py::ReleaseContractCompanionHostTests` exercises each of those in
  both directions, including that the companion floor is deliberately **not** compared against the
  Core minimum (an optional-profile floor at the same value is refused, which is the control).
- `tests/test_ccodex_sdlc_two_agent_plane.py::ContractRowAdmissionTest` drives the shipped install
  module: the floor is compared against the codex host's own observed version, an unobservable
  version refuses rather than assuming compatibility, and a payload whose contract declares no
  codex row refuses by name instead of borrowing Core's claims.
