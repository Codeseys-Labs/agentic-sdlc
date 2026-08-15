# Define the core harness and companion-profile boundary

Type: grilling
Status: resolved
Blocked by: 01, 03, 04
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Which capabilities must every Agentic SDLC installation own, which first-party capabilities are
optional profiles, and which external libraries remain operator-owned companions? Define what
"included" means for discovery, recommendation, installation, updates, collisions, removal, and
support without creating a second ownership channel.

## Answer

### Mandatory core

Every Agentic SDLC installation must be able to complete the first successful journey through
ordinary Claude Code and the user's native paid Claude account. The core owns:

- explicit install, status, update, and uninstall behavior backed by ownership receipts;
- the Claude Code plugin containing the canonical skills, roles, commands, and Dynamic Workflows;
- `/sdlc-init` and the frame-to-wave-to-review delivery loop;
- repository gate and hygiene contracts, including mise, lefthook, and betterleaks integration;
- durable work, decision, review, and follow-up artifacts; and
- runtime-assignment verification and authority boundaries, including in native-Claude-only use.

The core is route-aware but does not require a gateway, an external provider credential, or any
companion library.

### First-party optional profiles

`ccodex` is the packaged operator CLI and contains the routed-model profile. Ordinary `claude` runs
the core against the user's native Claude account; `ccodex launch` explicitly activates the OCX
gateway for that session and makes qualified non-Claude provider routes available without changing
the core plugin or repository contract. Installing `ccodex` does not configure providers or start
OCX. `/sdlc-init` may detect and explain the routing surface, but it must not configure or launch it
automatically.

Other first-party optional profiles are Research OS, operator UI and statusline activation, the
explicitly provisioned Linux Mermaid renderer, and adapters for companion hosts. Agentic SDLC
owns, versions, tests, updates, removes, and supports these profiles.

All first-party profiles follow one lifecycle contract: `ccodex sdlc` may advertise them without
activation; status and dry-run are read-only; installation or activation requires explicit,
operation-specific approval; owned artifacts have lifecycle receipts; conflicts or modified
destinations block replacement; updates are explicit and compatibility-checked; and uninstall
removes only verified, unchanged owned artifacts.

### External companion libraries

External libraries complement rather than complete the core product. "Included" means
discoverable in a closed curated catalog, detectable and recommendable at relevant workflow
handoffs, and interoperable at the documented integration boundary. It never means bundled,
vendored, automatically installed, or required by `/sdlc-init`.

Installation, update, and removal run only through the upstream library's own front door after
explicit approval. Agentic SDLC checks collisions and preserves foreign or modified state. It
supports its catalog and integration behavior, while upstream content and behavior remain the
library author's responsibility.
