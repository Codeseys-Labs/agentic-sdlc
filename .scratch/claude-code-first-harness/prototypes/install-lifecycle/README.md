# PROTOTYPE — installation lifecycle

This throwaway terminal prototype asks one question: does a Claude-first lifecycle with one
product control command, two acquisition paths, separately approved core/profile activation, and
receipt-backed update/rollback/recovery feel coherent when driven through real state transitions?

The validated namespace is `ccodex sdlc` for Agentic SDLC lifecycle operations. Installing the
`ccodex` operator CLI does not activate routed execution: ordinary `claude` can use the installed
core, while `ccodex launch` activates the separately approved OCX-routed session surface.

The validated primary topology is:

```text
mise use -g github:Codeseys-Labs/agentic-sdlc@<version>
ccodex sdlc inspect
ccodex sdlc doctor
ccodex sdlc install --host claude
```

The versioned mise release contains the CLI and private payload. Inspection and doctor are
read-only; Claude activation is a separate receipt-backed approval. A managed checkout is for
contribution and customization, not a normal-use prerequisite. A marketplace copy conflicts with
direct activation and is preserved rather than co-installed.

Mise owns release acquisition and version selection. After selecting a new or previous release,
the operator reviews it, reruns offline doctor, then explicitly runs `ccodex sdlc refresh`; the CLI
does not self-update. Routing starts per session through `ccodex launch`. First-party profiles live
under `ccodex sdlc profiles`, while external companions remain under `ccodex libraries` and their
own upstream front doors.

The prototype also adapts only the safe portions of the current `npx skills` design: bounded
discovery, explicit selectors, declarative host projection, deterministic intent, sanitization,
and granular diagnostics. It rejects implied consent, wildcard mutation, presence-based deletion,
non-transactional update, ambient credentials, and default egress.

Run it from the repository root:

```bash
python3 .scratch/claude-code-first-harness/prototypes/install-lifecycle/install_lifecycle_tui.py
```

In a real terminal this opens the interactive driver. In a non-interactive command runner it
prints a scripted acquisition-to-update walkthrough and exits successfully. State is in memory;
nothing is installed, trusted, configured, updated, or removed.
