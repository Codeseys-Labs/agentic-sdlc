"""The ONE closed per-agent host-plane table every receipted lifecycle verb reads.

WHY THIS FILE EXISTS. Before it, each of ``ccodex_sdlc_install``, ``ccodex_sdlc_update``, and
``ccodex_sdlc_uninstall`` carried its own parallel ``HOST``, ``HOST_COLLECTION``,
``RELEASE_CONTRACT_HOST``, ``ENTRY_AGENT``, and ``_HOST_VERSION_COMMAND`` constants, each pinned to
Claude.  Widening that plane to a second agent by adding a second constant beside every one of them
would have produced five parallel per-agent lookups that can drift independently: a table that gained
``codex`` in four places and not the fifth would activate a codex plane while checking Claude's
release-contract row, or observe Claude's version to admit a Codex host.  One record per agent, in one
place, makes a half-widened plane unrepresentable rather than merely unlikely.

WHAT IS AND IS NOT A FIELD HERE, AND WHY THE BOUNDARY MATTERS.

  * ``version_command`` is a SOURCE constant and is deliberately NOT read from the payload's release
    contract.  ``check_compatibility`` reads that contract out of the ADMITTED CANDIDATE PAYLOAD, so a
    contract-supplied argv would be an arbitrary command this lifecycle executes on behalf of a
    downloaded archive.  The contract may DECLARE which host it is about and what floor it requires;
    it may never decide what this tool runs.
  * ``collection`` is the installer's own ownership model, re-expressed rather than reinvented:
    ``install_skill_bundle.configured_root`` names the root an operator selects and ``agent_root``
    names the collection root beneath it.  Claude's configured root is the selected home and its agent
    root is that home plus ``.claude``; Codex's configured root IS its agent root, so its collection is
    ``None``.  A caller derives both from this one field through ``agent_root`` below.
  * ``contract_host`` is the host APPLICATION's own name, which is a different fact from the ``agent``
    selector: ``--host codex`` selects the plane, and ``codex-cli`` is what the Codex CLI calls itself
    (`codex --version` answers ``codex-cli 0.148.0``, observed 2026-08-25; see
    ``docs/evidence/2026-08-25-codex-host-plane.md``).
  * ``checks_marketplace_overlap`` is a per-agent gate rather than an inline ``agent == "claude"``
    test at the one call site, because the reason it is Claude-only -- a Claude plugin marketplace
    can publish the same entries this bundle owns -- is a property of the plane and belongs beside the
    plane's other properties.

WHAT THIS MODULE DOES NOT DO.  It reads nothing, writes nothing, spawns nothing, and imports nothing
beyond the stdlib names its two dataclasses need, so it can be loaded by a read-only process and by
every mutating verb through the same absolute-path sibling admission the rest of the plane uses.  A
row here is a location and a vocabulary; it is never an authorization, and a plane present in this
table is not evidence that any host was observed, certified, or qualified.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HostPlane:
    """Every per-agent fact one receipted lifecycle verb needs, in one frozen record."""

    #: The ``--host`` token, the ownership record's ``agent``, and the receipt body's ``scope.agent``.
    #: One spelling of one fact across all three, which is why they are not three fields.
    agent: str
    #: The collection beneath the configured root, or ``None`` when the configured root IS the agent
    #: root. Mirrors ``install_skill_bundle.agent_root`` exactly.
    collection: str | None
    #: The collection beneath a PROJECT root, or ``None`` when this plane has no project-scope layout
    #: at all and a project-scope verb must refuse for it by name.
    #:
    #: It is a separate field from ``collection`` rather than derived from it, because the two are
    #: independent facts about different roots. Claude's answer is the same string twice only by
    #: coincidence of convention: ``<home>/.claude`` is where Claude Code reads a user's entries and
    #: ``<repo>/.claude`` is where it reads a repository's, and the second is a MEASURED discovery
    #: surface (agentic-sdlc-4d2b) rather than an inference from the first. Codex's answers differ:
    #: its configured root IS its agent root, and no evidence in this tree says the Codex CLI reads
    #: any repository-local collection, so there is no layout to publish into and inventing one would
    #: put this bundle's payload at a repository's own top level. That refusal is a property of the
    #: plane and belongs here beside its other properties, not as an inline agent comparison at a
    #: call site (agentic-sdlc-7a2b, W4).
    project_collection: str | None
    #: The host application's own name, as its release-contract compatibility row declares it.
    contract_host: str
    #: Which ``compatibility`` member carries that row: Claude Code is the Core surface (ADR-0017),
    #: and every other host is a companion keyed by its agent token (ADR-0027 item 4 -- a companion
    #: host never inherits Core's tier).
    contract_section: str
    #: The argv observed once, with no shell and a bounded timeout, to read this host's version.
    version_command: tuple[str, ...]
    #: Whether a Claude plugin marketplace overlap blocks this plane's activation.
    checks_marketplace_overlap: bool
    #: Whether this plane could have written the pre-keyed ``activation/active-receipt.json`` pointer.
    #: Only Claude's user plane could: every writer of that file spelled ``activation_scope:
    #: claude-home``. A plane that could not is neither blocked by that document nor allowed to re-file
    #: it under its own key, because that would move one plane's statement onto another.
    owns_legacy_pointer: bool
    #: How this plane is NAMED in a refusal or a report line.
    display: str

    def agent_root(self, configured_root: Path) -> Path:
        """The collection root this agent's entries land in, given its configured root."""
        return configured_root if self.collection is None else configured_root / self.collection

    def project_root_collection(self, project_root: Path) -> Path:
        """Where this agent's entries land under one project root.

        A plane with no project layout has no answer, and this raises rather than returning the root
        itself: the caller that reached here without checking would otherwise publish a bundle's
        collections at a repository's own top level.
        """
        if self.project_collection is None:
            raise ValueError(f"the {self.agent} plane has no project-scope collection")
        return project_root / self.project_collection


#: The contract member that carries the primary product host's compatibility row.
CONTRACT_SECTION_CORE = "core"
#: The contract member that carries every companion host's row, keyed by agent token.
CONTRACT_SECTION_COMPANION = "companion_hosts"

#: The closed table. Two entries, and a third arrives with its own reviewed contract row plus its own
#: ADR-0027 capability evidence -- never by widening a tuple somewhere else and leaving this alone.
HOST_PLANES: dict[str, HostPlane] = {
    "claude": HostPlane(
        agent="claude",
        collection=".claude",
        # A repository's own `.claude/` is a measured discovery surface: its `workflows/` is read once
        # at session start (agentic-sdlc-4d2b), which is why project-scope activation is a grant of its
        # own rather than a placement detail.
        project_collection=".claude",
        contract_host="claude-code",
        contract_section=CONTRACT_SECTION_CORE,
        version_command=("claude", "--version"),
        checks_marketplace_overlap=True,
        owns_legacy_pointer=True,
        display="Claude Code",
    ),
    "codex": HostPlane(
        agent="codex",
        collection=None,
        # NO PROJECT LAYOUT, and the absence is the reviewed decision rather than an omission: this
        # tree carries no evidence that the Codex CLI reads any repository-local collection, and the
        # two shapes that could be invented for it are both wrong. `<repo>/` itself would scatter this
        # bundle's `skills/` and `agents/` across a repository's top level, and `<repo>/.claude/` would
        # file a Codex plane under another host's directory. A project-scope verb therefore refuses for
        # this plane by name; if a repository-local Codex surface is ever measured, this field is where
        # it arrives, with its own evidence (agentic-sdlc-7a2b, W4).
        project_collection=None,
        contract_host="codex-cli",
        contract_section=CONTRACT_SECTION_COMPANION,
        version_command=("codex", "--version"),
        # Codex has no plugin marketplace channel that publishes these entries, so there is no second
        # publisher to collide with. Recorded as a per-plane fact rather than as an absent branch.
        checks_marketplace_overlap=False,
        owns_legacy_pointer=False,
        display="Codex CLI",
    ),
}

#: The admitted ``--host`` vocabulary, derived from the table so a row and the grammar cannot disagree.
#: Sorted, so every refusal message that lists it lists it in one order.
AGENTS: tuple[str, ...] = tuple(sorted(HOST_PLANES))


def plane_for(agent: object) -> HostPlane:
    """Resolve one agent's plane, or raise ``KeyError`` naming what was asked for.

    Callers classify the failure themselves: the dispatcher's grammar already refused an unadmitted
    host at exit 2, so a miss here means a caller forwarded a vector its own grammar rejected, and
    each verb reports that in its own exit class rather than through a shared exception type.
    """
    if not isinstance(agent, str) or agent not in HOST_PLANES:
        raise KeyError(agent)
    return HOST_PLANES[agent]
