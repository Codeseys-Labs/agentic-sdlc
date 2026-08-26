#!/usr/bin/env python3
"""``ccodex install --scope user --agent <claude|codex>``: copy-activate ONE acquired candidate.

WHAT LOADS THIS FILE, AND WHAT IT MAY RETURN. ``scripts/ccodex_sdlc.py`` parses the closed
lifecycle grammar, refuses it, or loads this file by absolute non-symlink path and calls
``main(["--host", <agent>])``.  That reader owns no writer authority and this module owns no
grammar: the two halves are deliberately separate.  The dispatcher's contract is narrow and this
file honours it exactly.

  * ``main`` returns an ``int`` in the exit class 0-4 and NEVER a ``bool``: ``dispatch_lifecycle``
    rejects ``bool`` explicitly, because ``True`` would otherwise read as exit 1.
  * Every failure this module can see BEFORE any effect returns 3 -- a clean refusal, named.  A
    raise that escapes to the dispatcher reads as exit 4 (an admitted unknown effect), so this
    module catches its own unexpected failures and classifies them against the ONE fact that
    decides the class: whether an effect had started.
  * ``SystemExit`` is never raised here for a verdict.  The dispatcher deliberately lets it
    propagate, so raising it would hand this module's verdict to a process-level status that no
    caller inspected.

THE FOUR PHASES, IN ORDER, EACH REFUSING BY NAME BEFORE THE NEXT COULD MOVE ANYTHING.

  1. ADMIT ONE EXACT ACQUIRED CANDIDATE PAYLOAD, SEALING ITS TICKET WHEN THE ROOT CARRIES NONE.
     The only admissible payload root is the exactly acquired local candidate (Seed
     agentic-sdlc-0cce) at the acquisition layout, and the document that admits it is one sealed
     ``release-candidate-acquisition-receipt/v1``: terminal phase ``installed-unselected``,
     ``selection`` and ``activation`` both ``absent`` INSIDE the seal, and the candidate root at the
     exact path that receipt records.  There are TWO ways that document comes to exist and exactly
     one way it is admitted:

       * REUSED.  A receipt already filed for this archive digest is re-validated and used as it is.
         Receipts are create-only files keyed by ``<archive-sha256>.json``, so reuse-not-overwrite is
         the only admissible idempotence: a second install of one archive seals no second ticket, and
         a receipt whose bytes disagree with their own seal is refused rather than replaced.
       * AUTO-SEALED (agentic-sdlc-7a2b, W3b).  A release root at the layout carrying its own
         ``manifest.json`` and NO receipt yet is verified against that manifest in both directions and
         its ticket is sealed HERE, by calling ``write_acquisition_receipt``'s own library seal path.
         That module stays the schema owner; this one supplies the root, the layout's own archive
         digest, and this run's observed instant, so the bytes equal what its CLI would have written.
         This retires the manual placement-bridge recipe's sealing step -- what it does NOT retire is
         the PLACEMENT, because a release root states no digest of the archive it was extracted from
         and the layout's own directory name is the only place that fact survives.

     There is no checkout payload, no archive payload, no ``--from``, and no discovery beyond one
     exact layout: two receipts, or two release roots, are each refused as an ambiguity rather than
     resolved.  Once admitted, the acquisition receipt is READ and never written: its bytes are
     digested at admission and re-digested after the whole run, and a change is an unknown effect
     rather than a success.  The auto-seal runs AFTER every other pre-effect admission -- platform,
     root verification, compatibility, marketplace overlap -- so a refusal from any of those leaves
     the state plane exactly as it was, and a preview never seals at all.
  2. CHECK THE PAYLOAD'S OWN COMPATIBILITY CLAIMS.  ``policy/release-contract.v1.json`` inside the
     admitted payload declares the host it is about, an eligibility floor, and
     ``known_incompatible_host_versions``.  A DECLARED incompatibility with the observed host is
     refused BY NAME.  No other version is ever substituted for the observed one (Seed
     agentic-sdlc-0faa: a requested or nominated identity never becomes a readback), and an
     unobservable host version is refused rather than assumed compatible -- the receipt's closed
     ``unknowns`` vocabulary cannot even express "the host version was unknown", so admitting one
     would produce a document that silently omits an admission input it could not make.
  3. COPY-ACTIVATE THE SELECTED HOST'S ENTRIES TRANSACTIONALLY.  Copies, never links.  Every entry is
     classified ``absent``/``owned``/``foreign``/``modified`` BEFORE anything is written, and a
     ``foreign`` or ``modified`` entry is PRESERVED and NAMED in both the journal and the receipt
     inventory rather than adopted, replaced, or dropped.  There is no wildcard, no ``--all``, no
     purge, and no presence-based overwrite or delete.  The per-entry effect runs through the
     shipped installer's crash-consistent transitions, so an interruption leaves a recoverable
     journal plus its one armed ownership transition, never a half-state reported complete.
  4. SEAL ONE ``distribution-activation@2`` RECEIPT.  The sibling T1 producer derives both seals
     over the observation this module made: operation ``install``, the exact resolved candidate
     identity, the per-entry inventory with digests and prestates, the effect state and terminal
     phase taken from that module's OWN matrices, ``public_channel`` null, ``release_claim``
     ``none``, and exactly one ``derived-from`` ancestor naming the acquisition receipt's
     ``operation_id``.  An install carries NO ``supersedes`` ancestor: only an update replaces an
     earlier receipt.
  5. POINT THE PLANE AT THAT RECEIPT.  ``activation/active/<agent>/user.json`` is the only statement
     of what this (agent, scope, root) plane owns, and it is the admission every later verb reads:
     ``ccodex sdlc update`` and ``ccodex sdlc uninstall`` admit the pointer for their OWN key and
     nothing else, so an install that sealed a receipt without writing it left a plane no later verb
     could act on.  THE FILENAME IS THE ADMISSION AUTHORITY: the agent segment, the filename shape,
     and -- for a project scope -- the root key are each compared against the pointed receipt's own
     ``scope``, so a hand-moved pointer cannot redirect a removal at another agent's or another
     root's bytes.  A pre-keyed ``activation/active-receipt.json`` is re-filed at the keyed path
     before this run's admission and announced in the report; both present is a named refusal.
     The order is fixed and is
     the same order ``ccodex sdlc update`` uses: the receipt is written create-only and DURABLY
     first, and only then is the pointer replaced atomically, so there is no window in which the
     pointer names a receipt no directory holds.  A partial or unknown effect files the receipt as
     evidence and leaves the pointer ALONE -- a pointer that claims an activation nobody completed
     is worse than an absent one -- and exit 0 therefore requires all three halves: every claimed
     effect complete, the receipt sealed, and the pointer naming it.

THE TWO OPTIONAL REQUESTS THE FRONT DOOR FORWARDS, each admitted here and neither dropped.

  * ``--mode auto|link|copy``.  ``auto`` and ``copy`` both RESOLVE to this plane's one publication
     mode, and the resolution is stated in the report rather than assumed: an acquired candidate is
     copy-activated because a link would make the activated plane depend on a payload root that can
     move or vanish.  ``link`` is therefore refused BY NAME instead of being silently downgraded --
     the live-edit loop it names needs a checkout payload, which this plane does not admit.  Nothing
     here forwards ``auto`` to the substrate: the substrate would resolve it to a LINK on Unix, and
     this module would then catch the wrong publication mode only AFTER bytes had moved.
  * ``--dry-run``.  The substrate's own read-only planning pass, surfaced through the new grammar:
     the payload is admitted, the release contract is checked, and every entry is classified, then
     the plan is PRINTED and the run stops before the acquisition seal, before the plan and journal
     documents, before any entry moves, and before any pointer is written.  It takes no installer
     lock, because taking one durably creates the state directory a preview must not create.  A
     preview that had sealed the acquisition ticket would have made "nothing was written" false, so
     the report names the ticket it WOULD seal instead of sealing it.

WHAT THIS MODULE DOES NOT DO, BECAUSE THE TICKET'S MUST-NOTs ARE THE POINT.  No repository
activation, no config trust, no OCX, no provider, no library, no statusline, no Claude launch, and
no gate-leaf wiring.  No release claim: ``public_channel`` is null and ``release_claim`` is
``none`` in every document written here.  A completed activation is EVIDENCE.  It authorizes no
push, publication, PR mutation, merge, deployment, or any other outward effect.

REUSE, NOT REIMPLEMENTATION.  ``install_skill_bundle`` already owns the transactional
create/replace protocol, the ownership records, the durability barriers, the state lock, and the
digest/equivalence primitives; ``distribution_activation_receipt`` already owns the receipt body,
its closed vocabularies, and its cross-field matrices.  Both are loaded as exact physical siblings
by absolute path, never through ambient ``sys.path``, and this file reads their module constants
instead of re-expressing them, so a vocabulary change there fails here loudly rather than drifting
quietly.  The installer's own CLI verbs stay the checkout plane and are not extended.

THE READ-ONLY GUARD IS DELIBERATELY ABSENT FROM THIS PROCESS.  ``ccodex_sdlc_readonly`` blocks
``write_state``, ``persist_state``, ``installer_lock``, ``atomic_write``, ``durable_mkdir`` and
``durable_unlink`` on every adapter the READER loads, which is exactly why the reader cannot borrow
this module's authority: those are the primitives an activation needs.  The reader also never loads
this file -- ``load_lifecycle_module`` installs no guard -- so the two processes stay separate by
construction rather than by convention.

DEFECT CLASSES THIS FILE IS WRITTEN AGAINST, EACH ONE OBSERVED IN THIS PROJECT.

  * Character classes are written ``[0-9a-f]`` and never ``\\d``: ``\\d`` matches the Arabic-Indic
    ``٩``, so a digest or a version spelled in Unicode digits would look equal and compare unequal.
  * A number that BECOMES non-finite while parsing (``1e400`` -> ``inf``) never calls
    ``parse_constant``, so every parsed document is walked iteratively for non-finite floats.
  * Dict-literal evaluation order drops data: ``{"unknowns": unknowns, "entries": [walk(...)]}``
    evaluates ``unknowns`` BEFORE the walk that appends to it, so the document loses every unknown
    the walk discovered -- and then passes its own unknown-consistency check.  Every observation
    here is hoisted into a local before the literal that reports it.
  * Admission consults RECORDED UNKNOWNS, not only recorded facts: an observation nobody could make
    is not a fact and appears nowhere in a fact-only walk, so "complete" is derived from the
    unknowns list as well as from the outcomes.
  * Control characters are escaped in every rendered line derived from an artifact or from a
    filesystem name: a bare newline forges a line that looks like this tool's own output, a
    carriage return overwrites the line already printed, and ``\\x1b[2J`` clears the reader's
    screen.  The stored values are never mutated.
  * Supplied-but-missing is not not-supplied.  Every injected observation in ``Config`` carries an
    explicit ``UNSUPPLIED`` sentinel, so "observe it yourself" and "I looked and could not see it"
    are different inputs with different named outcomes.

RESIDUALS, STATED EXACTLY.

  * The acquisition receipt's seal is RE-DERIVATION.  It catches drift, a hand-edit, and a
    mismatched pair; it is not a boundary against a same-UID forger who can rewrite the receipt and
    the payload together.
  * The payload subset this activation copies is verified against the candidate manifest's own
    inventory rows.  The rest of the payload tree is not walked, and the manifest is trusted as the
    acquisition receipt's evidence rather than re-derived from an archive.
  * A same-UID racer that mutates the candidate root, the Claude home, or the acquisition receipt
    between this module's checks and its effects is out of scope, exactly as it is for the shipped
    installer whose transactions this module reuses.
  * The instant recorded in ``stated_at`` is an OBSERVATION.  Nothing here is admitted or refused
    by comparing instants, because this project's WSL2 host steps ``CLOCK_REALTIME`` backwards
    (Seed agentic-sdlc-184b) and a tool that compared its own clock would refuse honest input at
    random.
  * Sealing a receipt is evidence of an activation, not of a review, an approval, a certification,
    or a published release.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace as dataclass_replace
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from types import ModuleType
from typing import Any

# ---- exit classes ---------------------------------------------------------------------------------

#: The receipt sealed and every claimed effect completed durably.
EXIT_OK = 0
#: A clean refusal BEFORE any effect, named.
EXIT_REFUSED = 3
#: An effect was admitted and its completion or its evidence cannot be claimed.
EXIT_UNKNOWN = 4

#: The plane this run activates is a PARAMETER, not a constant. Every per-agent fact -- the collection
#: beneath the configured root, the release contract's host token and which member carries its row, the
#: version-observation argv, and whether a Claude marketplace overlap blocks the plane -- lives in ONE
#: record per agent in ``ccodex_sdlc_host_planes``. Five parallel per-agent constants here could each
#: gain a second agent independently, and a plane widened in four of them would activate one host while
#: checking another's compatibility row (agentic-sdlc-7a2b, WX).
HOST_FLAG = "--host"
#: The OPERATOR SURFACE this module's messages name, spelled once (seed agentic-sdlc-67c9). The
#: retired `ccodex sdlc install` namespace refuses at the dispatcher, so a refusal that still named it
#: would send an operator to a spelling the dispatcher itself rejects. The vector this module admits is
#: still `--host <agent>`: that is the module ABI, built in exactly one place by the reader, and it is
#: deliberately not the operator's spelling.
SURFACE = "ccodex install"
#: The two optional requests the front door forwards. Neither is a value this module invents.
MODE_FLAG = "--mode"
DRY_RUN_FLAG = "--dry-run"
#: `--mode`'s closed set, re-expressed from the installer's own argparse choices and pinned against
#: them by a test. `auto` and `copy` resolve to this plane's one mode; `link` is refused by name.
INSTALL_MODES = ("auto", "link", "copy")
#: The ONE token every payload-versus-manifest disagreement carries, whichever side catches it: the
#: whole-root verification before a ticket is sealed, or the per-entry verification of the subset this
#: activation copies. One name for one class of defect, so a test greps for one string (§2.3).
MANIFEST_MISMATCH = "payload-manifest-mismatch"
OPERATION = "install"
#: Which part of the host plane this operation touches, as the receipt body's own closed union. The
#: kind is a PARAMETER of the run (`Config.scope_kind`), not a constant: `user` activates the
#: operator's own plane and carries no root, `project` activates one repository's plane and carries the
#: resolved root the pointer is keyed by. The v1 spelling (`activation_scope: "claude-home"`) is gone
#: -- the union is the one statement of this fact. `SCOPE_KIND` remains as the DEFAULT for a caller
#: that names no scope, which is the vector every pre-project dispatcher built.
SCOPE_USER = "user"
SCOPE_PROJECT = "project"
SCOPE_KINDS = (SCOPE_USER, SCOPE_PROJECT)
SCOPE_KIND = SCOPE_USER
SCOPE_FLAG = "--scope"
PROJECT_FLAG = "--project"
EMITTING_PLANE = "acquired-candidate"
#: Copies, never links: the activation plane must not depend on a checkout that can move or vanish.
ACTIVATION_MODE = "copy"
#: The version this activation resolved was READ from the candidate manifest, not from an adapter
#: readback and never from a request.
VERSION_SOURCE = "archive-manifest"

# ---- re-expressed contracts, each pinned by a test against the shipped artifact -------------------

#: The acquisition receipt's closed key set, re-expressed from its producer,
#: scripts/write_acquisition_receipt.py -> RECEIPT_KEYS.
ACQUISITION_RECEIPT_KEYS = (
    "activation",
    "archive_sha256",
    "candidate_root_absolute_physical_path",
    "effect_state",
    "installed_at",
    "journal_sha256",
    "operation_id",
    "plan_sha256",
    "public_channel",
    "record_sha256",
    "release_claim",
    "schema_version",
    "selection",
    "support",
    "terminal_phase",
)
#: The same policy's ``constants`` for that schema, plus its ``schema_version``. Every one of these
#: is verified INSIDE the seal: a terminal installed-unselected acquisition whose selection is not
#: ``absent`` is a payload some other operation already claimed.
ACQUISITION_RECEIPT_CONSTANTS = {
    "activation": "absent",
    "effect_state": "complete",
    "public_channel": None,
    "release_claim": "none",
    "schema_version": "release-candidate-acquisition-receipt/v1",
    "selection": "absent",
    "support": "unsupported",
    "terminal_phase": "installed-unselected",
}
#: The acquisition layout, re-expressed from the same producer's RECEIPT_LAYOUT and
#: CANDIDATE_ROOT_LAYOUT.
ACQUISITION_RECEIPT_SEGMENTS = ("agentic-sdlc", "acquisition", "receipts")
ACQUISITION_CANDIDATE_SEGMENTS = ("agentic-sdlc", "acquisition", "candidates")
ACQUISITION_CANDIDATE_LEAF = "root"
#: This module's own artifacts live beside the acquisition plane's, under the same state home.
ACTIVATION_SEGMENTS = ("agentic-sdlc", "activation")

# ---- the pointer plane, re-expressed ---------------------------------------------------------------
#
# The pointer FILENAME is the admission authority for every later lifecycle verb, so the writer and
# the admitters must derive the same path. These four names and the derivation below are re-expressed
# from ``distribution_activation_receipt`` rather than imported, for the reason this module
# re-expresses every other contract: a sibling is loaded by absolute path at RUN time, and a
# module-level property cannot wait for it. The agreement is pinned by a test that compares this
# helper against that module's own ``pointer_path`` for both scope kinds -- which is what makes the
# re-expression a checked copy instead of a second opinion.
ACTIVE_DIRECTORY = "active"
USER_POINTER_NAME = "user.json"
PROJECT_POINTER_PREFIX = "project-"
POINTER_SUFFIX = ".json"
#: The pre-keyed plane's single pointer name. Only (claude, user) can ever have written it.
LEGACY_ACTIVE_POINTER_NAME = "active-receipt.json"
ROOT_KEY_CHARACTERS = 16


def _pointer_path(activation_dir: Path, agent: str, kind: str, root: str | None = None) -> Path:
    """The ONE pointer path for one (agent, scope kind, resolved root)."""
    if kind == "user":
        return activation_dir / ACTIVE_DIRECTORY / agent / USER_POINTER_NAME
    if kind == "project":
        if not isinstance(root, str) or not root:
            raise Refusal("a project-scope pointer is named by its resolved root, and none was supplied")
        key = hashlib.sha256(root.encode("utf-8")).hexdigest()[:ROOT_KEY_CHARACTERS]
        return activation_dir / ACTIVE_DIRECTORY / agent / f"{PROJECT_POINTER_PREFIX}{key}{POINTER_SUFFIX}"
    raise Refusal(f"{kind!r} is not one of this plane's scope kinds")

CANDIDATE_MANIFEST_NAME = "manifest.json"
CANDIDATE_MANIFEST_SCHEMA = "release-candidate/v1"
CANDIDATE_ARTIFACT_KIND = "unpublished-candidate"
CANDIDATE_PLATFORM = "linux-x64"
#: The one certified platform of an ``unpublished-candidate``: linux x86_64. Another operating
#: system or architecture is refused BY NAME rather than attempted.
SUPPORTED_SYSTEM = "Linux"
SUPPORTED_MACHINES = ("x86_64", "amd64")

RELEASE_CONTRACT_NAME = "release-contract.v1.json"
RELEASE_CONTRACT_SCHEMA = "release-contract/v1"
#: Which contract host token and which ``compatibility`` member carry the selected plane's row are
#: both per-agent facts and live in the host-plane record, not here. The ONE member that is not a
#: keyed map is the primary product host's Core surface; re-expressed from
#: ``ccodex_sdlc_host_planes.CONTRACT_SECTION_CORE`` and pinned against it by a test.
CONTRACT_SECTION_CORE = "core"

PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-activation-plan@1"
JOURNAL_SCHEMA = "agentic-sdlc/ccodex-sdlc-activation-journal@1"

#: Prestates and dispositions are the receipt producer's closed vocabularies; they are read from
#: that module at runtime and these names exist only so this file reads intelligibly.
PRESTATE_ABSENT = "absent"
PRESTATE_OWNED = "owned"
PRESTATE_FOREIGN = "foreign"
PRESTATE_MODIFIED = "modified"
DISPOSITION_INSTALLED = "installed"
DISPOSITION_REFRESHED = "refreshed"
DISPOSITION_PRESERVED = "preserved"

ACTION_INSTALL = "install"
ACTION_REFRESH = "refresh"
ACTION_PRESERVE = "preserve"
#: PROJECT SCOPE ONLY (§3.7): take ownership of a destination whose bytes are already exactly this
#: payload entry's, inside the resolved project root. It writes an ownership row and NOTHING to disk,
#: which is why its receipt row is `owned` + `preserved`: the ownership model's answer for those bytes
#: is "ours, removable", and the disposition states honestly that nothing was published.
ACTION_ADOPT = "adopt"

#: Every class is written out. ``\\d`` and ``\\w`` admit Unicode, so a digest or a version spelled
#: in Arabic-Indic digits would read as the same value and compare unequal to it everywhere else.
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_OPERATION_ID = re.compile(r"op-[0-9a-f]{32}\Z")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_VERSION = re.compile(r"[0-9A-Za-z]([0-9A-Za-z.+-]*[0-9A-Za-z])?\Z")
_UTC_INSTANT = re.compile(
    r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z"
)
_ENTRY_NAME = re.compile(r"[A-Za-z0-9]([A-Za-z0-9._/-]*[A-Za-z0-9])?\Z")

_MAX_RECEIPT_BYTES = 1048576
_MAX_MANIFEST_BYTES = 8388608
_MAX_CONTRACT_BYTES = 1048576
_INFINITY = float("inf")

#: The observation argv is per-agent and comes from the host-plane record. It is a SOURCE constant
#: there and is never read from the payload's own contract: that document arrives inside an admitted
#: archive, so a contract-supplied argv would be an arbitrary command this activation runs for it.
_HOST_VERSION_TIMEOUT_SECONDS = 20


class Refusal(RuntimeError):
    """Declined BEFORE any effect could occur: exit class 3, always named."""


class UnknownEffect(RuntimeError):
    """An effect was admitted, so no absence of effect can be claimed: exit class 4."""


class _Unsupplied:
    """The third state of an injected observation: nobody supplied one at all.

    ``None`` is a VALUE here -- "I looked for the host version and could not see it" -- so a plain
    default of ``None`` would merge not-supplied with supplied-but-missing, and those two are
    different named outcomes.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<unsupplied>"


UNSUPPLIED = _Unsupplied()

_ESCAPES = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def escape_display(value: str) -> str:
    """Escape every control character before an artifact-derived value reaches a rendered line.

    The same rule as the receipt producer's own ``escape_display``, and the test module pins the two
    against each other so a divergence is a failure rather than a silent second spelling.  DEL
    (0x7f) is included because a naive ``< 0x20`` test passes it.
    """
    out: list[str] = []
    for char in value:
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\x{ord(char):02x}")
        else:
            out.append(char)
    return "".join(out)


def show(value: object) -> str:
    """Render one caller- or artifact-supplied value for a message, escaped and quoted."""
    if isinstance(value, str):
        return f"'{escape_display(value)}'"
    return escape_display(repr(value))


# ---- Config: every path, home, and observation is injectable ---------------------------------------


def default_state_home() -> Path:
    """``XDG_STATE_HOME`` or its documented default, without creating anything.

    Same convention the shipped installer's ``state_directory`` uses and the acquisition plane's
    ``--xdg-state-home`` names; this module invents no new location.
    """
    value = os.environ.get("XDG_STATE_HOME")
    if value and value.strip():
        return _absolute(Path(value))
    return _absolute(Path.home() / ".local" / "state")


def default_data_home() -> Path:
    """``XDG_DATA_HOME`` or its documented default: where an acquired candidate payload lands."""
    value = os.environ.get("XDG_DATA_HOME")
    if value and value.strip():
        return _absolute(Path(value))
    return _absolute(Path.home() / ".local" / "share")


def default_codex_home() -> Path:
    """Read only so the reused installer Config is complete; no Codex entry is ever touched."""
    value = os.environ.get("CODEX_HOME")
    if value and value.strip():
        return _absolute(Path(value))
    return _absolute(Path.home() / ".codex")


def _absolute(path: Path) -> Path:
    """Absolute without resolving links, aliases, or 8.3 spellings: the installer's own rule."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


@dataclass(frozen=True)
class Config:
    """Every location and every ambient observation this module depends on, in one injectable seam.

    The defaults are the ones the shipped scripts already use -- ``XDG_STATE_HOME`` for the
    acquisition and activation state planes, ``XDG_DATA_HOME`` for the acquired payload, the
    operator's home for the Claude plane -- so a test can relocate all of them without this module
    inventing a second location convention.
    """

    home: Path
    state_home: Path
    data_home: Path
    codex_home: Path
    #: WHICH PLANE this run activates. Every path and vocabulary below that differs per agent is
    #: derived from it through the host-plane record, so there is one selector and no second spelling.
    #: The default is the primary product host, and ``main`` replaces it with the dispatcher's own
    #: admitted ``--host`` value before this configuration reaches any admission logic.
    agent: str = "claude"
    #: WHICH SCOPE of that plane this run activates. The default is the operator's own plane, which is
    #: the vector every pre-project dispatcher built and the only scope a caller that names none can
    #: mean.
    scope_kind: str = SCOPE_KIND
    #: The resolved project root at project scope, and ``None`` at user scope. It is the configured root
    #: the ownership rows are bounded by AND the value the pointer filename's key is derived from; the
    #: operator's own ``home`` stays exactly what it is, because a marketplace overlap is a fact about
    #: the operator's plane whichever scope this run activates.
    project_root: Path | None = None
    #: ``None`` means "the installer's own default state root"; a path relocates the ownership state.
    installer_state_root: Path | None = None
    #: ``UNSUPPLIED`` observes the host itself; ``None`` is an observation that failed.
    observed_host_version: str | None | _Unsupplied = UNSUPPLIED
    observed_system: str | _Unsupplied = UNSUPPLIED
    observed_machine: str | _Unsupplied = UNSUPPLIED
    observed_instant: str | None | _Unsupplied = UNSUPPLIED

    def __post_init__(self) -> None:
        for name in ("home", "state_home", "data_home", "codex_home"):
            object.__setattr__(self, name, _absolute(getattr(self, name)))
        if self.installer_state_root is not None:
            object.__setattr__(
                self, "installer_state_root", _absolute(self.installer_state_root)
            )
        # NORMALISED HERE, once: the pointer's key is `sha256` over this exact string, and the
        # ownership rows are bounded by `relative_to` against it, so an unnormalised spelling would
        # produce a second key for one root and select no rows under it.
        if self.project_root is not None:
            object.__setattr__(self, "project_root", _absolute(self.project_root))

    @property
    def plane(self) -> Any:
        """The selected agent's one host-plane record."""
        return host_plane(self.agent)

    @property
    def configured_root(self) -> Path:
        """The root the operator SELECTED for this run, which the ownership rows are bounded by.

        At project scope that root is the RESOLVED PROJECT, for both halves of the ownership model at
        once: `install_skill_bundle.agent_root` derives `<root>/.claude` from it and
        `assert_safe_collection` keeps every destination inside it, so pointing the configured root at
        a repository reuses the escape check rather than adding a second one (§3.5).
        """
        if self.scope_kind == SCOPE_PROJECT:
            if self.project_root is None:
                raise Refusal(
                    "a project-scope activation is bounded by its resolved root, and none was supplied"
                )
            return self.project_root
        return self.home if self.plane.collection is not None else self.codex_home

    @property
    def plane_root(self) -> Path:
        """The collection root this agent's entries land in, derived from the installer's own model.

        The two scopes read two different fields of the plane record, because they are two different
        facts: a user scope's collection sits under the operator's configured home, and a project
        scope's sits under a repository root -- and a plane may have the first without the second.
        """
        if self.scope_kind == SCOPE_PROJECT:
            return self.plane.project_root_collection(self.configured_root)
        return self.plane.agent_root(self.configured_root)

    @property
    def acquisition_receipts_dir(self) -> Path:
        return self.state_home.joinpath(*ACQUISITION_RECEIPT_SEGMENTS)

    @property
    def acquisition_candidates_dir(self) -> Path:
        return self.data_home.joinpath(*ACQUISITION_CANDIDATE_SEGMENTS)

    @property
    def activation_dir(self) -> Path:
        return self.state_home.joinpath(*ACTIVATION_SEGMENTS)

    @property
    def active_receipt_path(self) -> Path:
        """This plane's ONE pointer, at the keyed path (agent, scope kind, root) names.

        The path is derived by the receipt family's own `pointer_path`, not spelled again here: the
        writer that lands a pointer and the verbs that admit one must agree on the filename, because
        the filename IS the admission authority. `active_pointer_path` on the sibling verbs resolves
        the same way for the same reason.
        """
        root = str(self.project_root) if self.scope_kind == SCOPE_PROJECT and self.project_root else None
        return _pointer_path(self.activation_dir, self.agent, self.scope_kind, root)

    @property
    def legacy_active_receipt_path(self) -> Path:
        """Where the pre-keyed plane wrote its single pointer. Only (claude, user) could have."""
        return self.activation_dir / LEGACY_ACTIVE_POINTER_NAME

    @property
    def migrates_legacy_pointer(self) -> bool:
        """Whether THIS plane could have written the pre-keyed pointer.

        Only (claude, user) could: every writer of ``activation/active-receipt.json`` spelled the scope
        ``claude-home``. So a codex run neither claims that document nor is blocked by it -- re-filing
        it under a codex key would move a claude statement onto a plane it was never about, and the
        same argument excludes every PROJECT scope: no pre-keyed writer ever activated a repository, so
        a project run that re-filed that document would claim one plane's activation for another.
        """
        return bool(self.plane.owns_legacy_pointer) and self.scope_kind == SCOPE_USER

    @property
    def plans_dir(self) -> Path:
        return self.activation_dir / "plans"

    @property
    def journals_dir(self) -> Path:
        return self.activation_dir / "journals"

    @property
    def receipts_dir(self) -> Path:
        return self.activation_dir / "receipts"


def default_config() -> Config:
    """The operator-facing defaults, observed once, from the conventions already in this tree."""
    return Config(
        home=Path.home(),
        state_home=default_state_home(),
        data_home=default_data_home(),
        codex_home=default_codex_home(),
    )


# ---- sibling modules: exact physical files, never ambient sys.path --------------------------------


def load_sibling(stem: str) -> ModuleType:
    """Load one named sibling by absolute non-symlink path, the reader's own admission shape.

    Identical posture to ``ccodex_sdlc.load_guard`` and ``ccodex_sdlc_readonly.load_sibling``: an
    exact physical sibling of THIS file, refused rather than searched for.  The read-only guard is
    NOT installed here, because it exists to block the very primitives an activation needs.
    """
    path = Path(__file__).with_name(f"{stem}.py")
    if path.is_symlink() or not path.is_file():
        raise Refusal(
            f"{SURFACE} requires the sibling module {show(str(path))}, which is absent or"
            " is a link"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_install_{stem}", path)
    if spec is None or spec.loader is None:
        raise Refusal(f"{SURFACE} cannot load the sibling module {show(str(path))}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an import failure here is still pre-effect
        raise Refusal(
            f"{SURFACE} cannot import the sibling module {show(str(path))}: {show(exc)}"
        ) from exc
    return module


@functools.lru_cache(maxsize=None)
def host_plane(agent: str) -> Any:
    """Resolve ONE agent's host-plane record from the closed table, or refuse before any effect.

    Cached because the record is read at several points in one run -- the configured root, the plane
    root, the contract row, the version observation, the report -- and the table is immutable pure
    data, so re-executing its module per access would be the same answer at a cost.  A refusal is not
    cached: an exception leaves no entry, so a tree repaired between calls is re-read.

    An unadmitted agent lands here only when a caller forwarded a vector its own grammar rejected, so
    the refusal names the table rather than restating the dispatcher's usage error.
    """
    planes = load_sibling("ccodex_sdlc_host_planes")
    try:
        return planes.plane_for(agent)
    except KeyError as exc:
        raise Refusal(
            f"{show(agent)} is not one of this lifecycle's host planes"
            f" ({', '.join(planes.AGENTS)})"
        ) from exc


# ---- strict document reading ----------------------------------------------------------------------


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """A repeated JSON key is a document with two meanings; choosing one is the guess refused here."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Refusal(f"a supplied document repeats the JSON key {show(key)}, so it has two meanings")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise Refusal(f"a supplied document carries the non-finite JSON constant {show(token)}")


def _reject_nonfinite(value: Any, subject: str) -> None:
    """Refuse a number that BECAME non-finite while parsing, which ``parse_constant`` cannot see.

    ``json.loads('{"n": 1e400}')`` yields ``inf`` without ever calling ``parse_constant``.  The walk
    is iterative because the decoder admits nesting a recursive walk would not survive.
    """
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, float) and not -_INFINITY < current < _INFINITY:
            raise Refusal(f"{subject} carries the non-finite number {show(current)}")
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def read_exact_file(path: Path, limit: int, subject: str) -> bytes:
    """Read one exact physical regular file, refusing a link, a directory, or an oversized blob."""
    try:
        item = path.lstat()
    except OSError as exc:
        raise Refusal(f"{subject} is unavailable at {show(str(path))}: {show(exc)}") from exc
    if stat.S_ISLNK(item.st_mode):
        raise Refusal(f"{subject} at {show(str(path))} is a symlink; an exact physical file is required")
    if not stat.S_ISREG(item.st_mode):
        raise Refusal(f"{subject} at {show(str(path))} is not a regular file")
    if item.st_size > limit:
        raise Refusal(
            f"{subject} at {show(str(path))} is {item.st_size} bytes, over the {limit}-byte limit"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise Refusal(f"{subject} cannot be read at {show(str(path))}: {show(exc)}") from exc


def parse_json_object(raw: bytes, subject: str) -> dict[str, Any]:
    """Parse one JSON object strictly: no duplicate key, no non-finite number, no non-object root."""
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise Refusal(f"{subject} is not UTF-8: {show(exc)}") from exc
    try:
        value = json.loads(
            text, object_pairs_hook=_reject_duplicate, parse_constant=_reject_constant
        )
    except Refusal:
        raise
    except ValueError as exc:
        raise Refusal(f"{subject} is not readable as JSON: {show(exc)}") from exc
    if not isinstance(value, dict):
        raise Refusal(f"{subject} is {type(value).__name__}, not a JSON object")
    _reject_nonfinite(value, subject)
    return value


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


# ---- phase 0: the platform this candidate is certified for ----------------------------------------


def observe_platform(config: Config) -> tuple[str, str]:
    """Observe the operating system and architecture, or take the injected observation."""
    system = platform.system() if isinstance(config.observed_system, _Unsupplied) else config.observed_system
    machine = (
        platform.machine() if isinstance(config.observed_machine, _Unsupplied) else config.observed_machine
    )
    return str(system), str(machine)


def admit_platform(config: Config) -> tuple[str, str]:
    """Refuse an uncertified platform BY NAME rather than attempting a linux-x64 payload on it.

    The message names the SELECTED plane rather than a hardcoded one: it read ``--host claude`` for
    every agent until this wave, so a codex run on macOS was refused by a sentence about Claude. The
    SCOPE was the surviving half of that same defect -- ``--scope user`` was still a literal here, so a
    ``--scope project`` run on Darwin was refused by a sentence naming a plane the operator had not
    selected (observed in the macOS CI seam transcript for main@818bf09, seed context
    ``ci-red-818bf09``). Both halves are now parameters of the run.
    """
    system, machine = observe_platform(config)
    selected = f"{SURFACE} --scope {escape_display(config.scope_kind)} --agent {escape_display(config.agent)}"
    if system != SUPPORTED_SYSTEM:
        raise Refusal(
            f"{selected} activates a {CANDIDATE_PLATFORM} candidate and is"
            f" certified only on {SUPPORTED_SYSTEM}; the observed operating system is"
            f" {show(system)}. Another platform is refused rather than attempted"
        )
    if machine.lower() not in SUPPORTED_MACHINES:
        raise Refusal(
            f"{selected} activates a {CANDIDATE_PLATFORM} candidate; the"
            f" observed architecture is {show(machine)}, not one of {list(SUPPORTED_MACHINES)}"
        )
    return system, machine


def observe_instant(config: Config) -> str:
    """One UTC instant for ``stated_at``, observed and never compared.

    The receipt producer reads no clock at all and requires the caller to supply the instant, so it
    is observed HERE, validated against the envelope's own shape, and used only as a recorded fact.
    """
    if isinstance(config.observed_instant, _Unsupplied):
        observed: str | None = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    else:
        observed = config.observed_instant
    if observed is None:
        raise Refusal(
            "the supplied UTC instant observation is missing, so this activation cannot state when"
            " it happened; the receipt envelope requires a YYYY-MM-DDTHH:MM:SSZ instant and this"
            " module never invents one"
        )
    if not isinstance(observed, str) or not _UTC_INSTANT.match(observed):
        raise Refusal(
            f"the observed UTC instant {show(observed)} is not a YYYY-MM-DDTHH:MM:SSZ value, so the"
            " receipt envelope would refuse it"
        )
    return observed


# ---- phase 1: admit ONE exact acquired candidate payload ------------------------------------------


@dataclass(frozen=True)
class PayloadCandidate:
    """The payload root this run resolved, BEFORE it holds an admitted acquisition ticket.

    It exists because the ticket is now sealed as late as possible: every field here is read from the
    root and its own manifest, so compatibility, the marketplace gate, and a preview can all be
    decided from it while the state plane is still untouched.  ``existing`` carries the already-filed
    receipt when there is one, which is what makes reuse and auto-seal one admission with two
    prestates rather than two admissions.
    """

    candidate_root: Path
    archive_sha256: str
    manifest: dict[str, Any]
    candidate_id: str
    resolved_version: str
    inventory: dict[str, dict[str, Any]]
    #: ``(path, bytes, document)`` for a receipt this run REUSES, or ``None`` when it must seal one.
    existing: tuple[Path, bytes, dict[str, Any]] | None


@dataclass(frozen=True)
class AdmittedPayload:
    """The one admitted payload: its acquisition receipt, its root, and its manifest identity."""

    receipt_path: Path
    receipt_bytes: bytes
    receipt: dict[str, Any]
    archive_sha256: str
    operation_id: str
    candidate_root: Path
    manifest: dict[str, Any]
    candidate_id: str
    resolved_version: str
    inventory: dict[str, dict[str, Any]]
    #: How this run came to hold the ticket above: ``reused`` or ``sealed``. Recorded because the two
    #: are different facts about the same document and the report must not merge them.
    acquisition: str


def _require_physical_directory(path: Path, subject: str) -> None:
    """Refuse a link, a non-directory, or a link anywhere in the chain that reaches it.

    Re-expresses ``ccodex_sdlc._candidate_root``'s posture for a payload root: the physical
    identity of the path must be the path itself, so a redirected component cannot silently move
    the activation's source outside the acquisition plane.
    """
    try:
        item = path.lstat()
    except OSError as exc:
        raise Refusal(f"{subject} is unavailable at {show(str(path))}: {show(exc)}") from exc
    if stat.S_ISLNK(item.st_mode) or not stat.S_ISDIR(item.st_mode):
        raise Refusal(f"{subject} at {show(str(path))} is not an exact physical directory")
    physical = os.path.realpath(path)
    if physical != os.fspath(path):
        raise Refusal(
            f"{subject} at {show(str(path))} resolves to {show(physical)}; a redirected component"
            " would move this activation's payload outside the acquisition plane"
        )


def acquisition_receipt_names(config: Config) -> list[str]:
    """Every ``<archive-sha256>.json`` filed in the acquisition receipts plane, in one sorted list.

    An absent or non-directory plane is an EMPTY list rather than a refusal: with the auto-seal there
    are two admissible prestates for a first install -- no receipt yet, and one already filed -- and a
    refusal here would decide the first one before the release root had been looked for.  A plane that
    exists but cannot be listed is still a refusal, because that is an unreadable answer rather than a
    negative one.
    """
    receipts_dir = config.acquisition_receipts_dir
    if not receipts_dir.is_dir() or receipts_dir.is_symlink():
        return []
    try:
        names = sorted(item.name for item in receipts_dir.iterdir())
    except OSError as exc:
        raise Refusal(
            f"the acquisition receipts directory {show(str(receipts_dir))} cannot be listed:"
            f" {show(exc)}"
        ) from exc
    return [name for name in names if name.endswith(".json") and _HEX64.match(name[: -len(".json")])]


def admit_acquisition_receipt(config: Config) -> tuple[Path, bytes, dict[str, Any], str]:
    """Admit exactly ONE sealed acquisition receipt, or refuse the ambiguity by name.

    This is the ONE admission both prestates pass through, and that is deliberate: a receipt this run
    sealed itself is re-read from disk and validated by exactly the checks a hand-placed one faces, so
    the auto-seal earns no trust from having been written here.
    """
    receipts_dir = config.acquisition_receipts_dir
    candidates = acquisition_receipt_names(config)
    if not candidates:
        raise Refusal(
            f"no acquired candidate is available: {show(str(receipts_dir))} holds no"
            " <archive-sha256>.json acquisition receipt"
        )
    if len(candidates) > 1:
        raise Refusal(
            f"{show(str(receipts_dir))} holds {len(candidates)} acquisition receipts"
            f" ({', '.join(show(name) for name in candidates)}); exactly one exactly acquired local"
            " candidate is admissible, and choosing between them would be a guess"
        )
    receipt_path = receipts_dir / candidates[0]
    raw = read_exact_file(receipt_path, _MAX_RECEIPT_BYTES, "the acquisition receipt")
    receipt = parse_json_object(raw, f"the acquisition receipt {show(str(receipt_path))}")
    archive_sha256 = candidates[0][: -len(".json")]
    validate_acquisition_receipt(receipt, receipt_path, archive_sha256)
    return receipt_path, raw, receipt, archive_sha256


def admit_release_root(config: Config) -> tuple[Path, str]:
    """Resolve the ONE release root at the acquisition layout that carries its own manifest.

    Reached only when no receipt is filed.  The enumeration is bounded to one exact layout and admits
    a directory only when it is named by 64 lowercase hexadecimal characters AND holds
    ``root/manifest.json``: the layout's own directory name is the archive digest, and it is the only
    place that fact survives extraction, because a release root states no digest of the archive it
    came from.  Two such roots are refused as an ambiguity for the same reason two receipts are --
    choosing would be a guess -- and none is the honest "no acquired candidate" refusal, naming both
    planes so an operator can see which half is missing.
    """
    candidates_dir = config.acquisition_candidates_dir
    roots: list[str] = []
    if candidates_dir.is_dir() and not candidates_dir.is_symlink():
        try:
            names = sorted(item.name for item in candidates_dir.iterdir())
        except OSError as exc:
            raise Refusal(
                f"the acquisition candidates directory {show(str(candidates_dir))} cannot be listed:"
                f" {show(exc)}"
            ) from exc
        for name in names:
            if not _HEX64.match(name):
                continue
            manifest = candidates_dir / name / ACQUISITION_CANDIDATE_LEAF / CANDIDATE_MANIFEST_NAME
            if manifest.is_file() and not manifest.is_symlink():
                roots.append(name)
    if not roots:
        raise Refusal(
            f"no acquired candidate is available: {show(str(config.acquisition_receipts_dir))} holds"
            " no <archive-sha256>.json acquisition receipt and"
            f" {show(str(candidates_dir))} holds no <archive-sha256>/"
            f"{ACQUISITION_CANDIDATE_LEAF}/{CANDIDATE_MANIFEST_NAME} release root to seal one from."
            " Acquire and place a candidate first; this operation never acquires one"
        )
    if len(roots) > 1:
        raise Refusal(
            f"{show(str(candidates_dir))} holds {len(roots)} release roots"
            f" ({', '.join(show(name) for name in roots)}) and no acquisition receipt names which one"
            " this activation is about; exactly one is admissible, and choosing between them would be"
            " a guess"
        )
    return require_candidate_layout(config, roots[0]), roots[0]


def acquisition_record_digest(receipt: dict[str, Any]) -> str:
    """Re-derive the acquisition receipt's own seal: sha256 over its canonical bytes MINUS the seal.

    The acquisition producer's exact pattern (``_seal`` pops the field, digests, writes it back), so
    a hand-edit of any other field makes this disagree.
    """
    without = {key: value for key, value in receipt.items() if key != "record_sha256"}
    canonical = (
        json.dumps(without, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")
    return sha256_bytes(canonical)


def validate_acquisition_receipt(receipt: dict[str, Any], path: Path, archive_sha256: str) -> None:
    """Every check names its field. The closed key set first, so an absence is never ignored."""
    subject = f"the acquisition receipt {show(str(path))}"
    present = set(receipt)
    missing = sorted(set(ACQUISITION_RECEIPT_KEYS) - present)
    unknown = sorted(present - set(ACQUISITION_RECEIPT_KEYS))
    if missing:
        raise Refusal(f"{subject} carries no {', '.join(missing)}, which its closed key set requires")
    if unknown:
        raise Refusal(
            f"{subject} carries the unknown field(s) {', '.join(show(key) for key in unknown)}; the"
            " immutable acquisition receipt is closed"
        )
    for key in sorted(ACQUISITION_RECEIPT_CONSTANTS):
        expected = ACQUISITION_RECEIPT_CONSTANTS[key]
        observed = receipt[key]
        if observed is not expected and observed != expected:
            raise Refusal(
                f"{subject} records {key} {show(observed)}, not {show(expected)}; only an exactly"
                " acquired, terminal, unselected candidate is an admissible payload root"
            )
    for key in ("archive_sha256", "journal_sha256", "plan_sha256", "record_sha256"):
        value = receipt[key]
        if not isinstance(value, str) or not _HEX64.match(value):
            raise Refusal(
                f"{subject}'s {key} is {show(value)}, not 64 lowercase hexadecimal characters; the"
                " class is written [0-9a-f] and never \\d, which admits Unicode digits"
            )
    if receipt["archive_sha256"] != archive_sha256:
        raise Refusal(
            f"{subject} records archive_sha256 {show(receipt['archive_sha256'])} but is filed as"
            f" {show(archive_sha256 + '.json')}; the receipt and its own location disagree"
        )
    operation_id = receipt["operation_id"]
    if not isinstance(operation_id, str) or not _OPERATION_ID.match(operation_id):
        raise Refusal(
            f"{subject}'s operation_id is {show(operation_id)}, not the op-<32 lowercase hex> form"
            " the acquisition plane records; the activation receipt names it as its ancestor and"
            " correlation compares that value literally"
        )
    installed_at = receipt["installed_at"]
    if not isinstance(installed_at, str) or not _UTC_INSTANT.match(installed_at):
        raise Refusal(f"{subject}'s installed_at is {show(installed_at)}, not a YYYY-MM-DDTHH:MM:SSZ instant")
    root_value = receipt["candidate_root_absolute_physical_path"]
    if not isinstance(root_value, str) or not root_value:
        raise Refusal(f"{subject}'s candidate_root_absolute_physical_path is {show(root_value)}")
    derived = acquisition_record_digest(receipt)
    if derived != receipt["record_sha256"]:
        raise Refusal(
            f"{subject} records record_sha256 {show(receipt['record_sha256'])} but its canonical"
            f" bytes minus that field seal to {show(derived)}; the receipt and its own seal are a"
            " mismatched pair, so this payload's provenance is not exact"
        )


def require_candidate_layout(config: Config, archive_sha256: str) -> Path:
    """The ONE path this data home's acquisition layout gives this archive digest, every component
    of it proven an exact physical directory.

    Factored out of ``admit_candidate_root`` so the auto-seal path proves the same physical identity
    for a root no receipt has named yet.  Without it a redirected component could move the payload a
    freshly sealed ticket attests to.
    """
    expected = config.acquisition_candidates_dir / archive_sha256 / ACQUISITION_CANDIDATE_LEAF
    _require_physical_directory(config.data_home, "the configured XDG data home")
    for depth in range(len(ACQUISITION_CANDIDATE_SEGMENTS) + 2):
        component = expected
        for _ in range(depth):
            component = component.parent
        _require_physical_directory(component, "a component of the acquired candidate root")
    return expected


def admit_candidate_root(config: Config, receipt: dict[str, Any], archive_sha256: str) -> Path:
    """The candidate root is the ONE path the acquisition layout and the sealed receipt both name."""
    expected = config.acquisition_candidates_dir / archive_sha256 / ACQUISITION_CANDIDATE_LEAF
    recorded = Path(str(receipt["candidate_root_absolute_physical_path"]))
    if os.fspath(recorded) != os.fspath(expected):
        raise Refusal(
            f"the acquisition receipt records the candidate root {show(str(recorded))}, but the"
            f" acquisition layout for this data home places it at {show(str(expected))}; a payload"
            " root outside that layout is not an exactly acquired local candidate"
        )
    return require_candidate_layout(config, archive_sha256)


def admit_candidate_manifest(candidate_root: Path) -> tuple[dict[str, Any], str, str]:
    """Admit the payload's own manifest identity: candidate id, product version, and platform."""
    path = candidate_root / CANDIDATE_MANIFEST_NAME
    raw = read_exact_file(path, _MAX_MANIFEST_BYTES, "the candidate manifest")
    manifest = parse_json_object(raw, f"the candidate manifest {show(str(path))}")
    subject = f"the candidate manifest {show(str(path))}"
    if manifest.get("schema_version") != CANDIDATE_MANIFEST_SCHEMA:
        raise Refusal(
            f"{subject} declares schema_version {show(manifest.get('schema_version'))}, not"
            f" {show(CANDIDATE_MANIFEST_SCHEMA)}"
        )
    if manifest.get("artifact_kind") != CANDIDATE_ARTIFACT_KIND:
        raise Refusal(
            f"{subject} declares artifact_kind {show(manifest.get('artifact_kind'))}, not"
            f" {show(CANDIDATE_ARTIFACT_KIND)}"
        )
    if manifest.get("platform") != CANDIDATE_PLATFORM:
        raise Refusal(
            f"{subject} declares platform {show(manifest.get('platform'))}, not"
            f" {show(CANDIDATE_PLATFORM)}"
        )
    if manifest.get("public_channel") is not None or manifest.get("release_claim") != "none":
        raise Refusal(
            f"{subject} claims public_channel {show(manifest.get('public_channel'))} and"
            f" release_claim {show(manifest.get('release_claim'))}; this plane activates only an"
            " unpublished candidate that claims no release"
        )
    candidate_id = manifest.get("candidate_id")
    if not isinstance(candidate_id, str) or not _HEX64.match(candidate_id):
        raise Refusal(
            f"{subject}'s candidate_id is {show(candidate_id)}, not 64 lowercase hexadecimal"
            " characters; payload identity is not a version label"
        )
    version = manifest.get("product_version")
    if not isinstance(version, str) or not version or len(version) > 64 or not _VERSION.match(version):
        raise Refusal(
            f"{subject}'s product_version is {show(version)}, which is not an ASCII version string"
            " of at most 64 characters; the resolved version is this receipt's whole subject"
        )
    return manifest, candidate_id, version


def manifest_inventory(manifest: dict[str, Any], candidate_root: Path) -> dict[str, dict[str, Any]]:
    """Index the manifest's inventory rows by relative path, refusing an unusable row by name."""
    rows = manifest.get("inventory")
    if not isinstance(rows, list) or not rows:
        raise Refusal(
            f"the candidate manifest at {show(str(candidate_root))} carries no usable inventory, so"
            " no payload entry could be verified against it"
        )
    index: dict[str, dict[str, Any]] = {}
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict):
            raise Refusal(f"candidate manifest inventory row {ordinal} is not an object")
        path_value = row.get("path")
        kind = row.get("type")
        if not isinstance(path_value, str) or not path_value or path_value.startswith("/"):
            raise Refusal(f"candidate manifest inventory row {ordinal} names the path {show(path_value)}")
        if ".." in Path(path_value).parts:
            raise Refusal(
                f"candidate manifest inventory row {ordinal} names {show(path_value)}, which"
                " carries a traversal segment"
            )
        if kind not in ("dir", "file", "symlink"):
            raise Refusal(
                f"candidate manifest inventory row {ordinal} declares the type {show(kind)}, not"
                " one of ['dir', 'file', 'symlink']"
            )
        if kind == "file" and (not isinstance(row.get("sha256"), str) or not _HEX64.match(str(row.get("sha256")))):
            raise Refusal(
                f"candidate manifest inventory row {ordinal} for {show(path_value)} carries the"
                f" sha256 {show(row.get('sha256'))}, not 64 lowercase hexadecimal characters"
            )
        if path_value in index:
            raise Refusal(
                f"the candidate manifest inventories {show(path_value)} twice, so which row"
                " describes it is unresolvable"
            )
        index[path_value] = row
    return index


def load_acquisition_producer() -> ModuleType:
    """The acquisition receipt's SCHEMA OWNER, loaded as an exact physical sibling.

    Its ``verify_root`` and ``write_receipt`` are the library boundary it declares; nothing here
    re-expresses its key set, its constants, or its derived digests, because a second producer of one
    document is how two spellings of one fact get written on two different days.
    """
    return load_sibling("write_acquisition_receipt")


def verify_release_root(producer: ModuleType, candidate_root: Path) -> None:
    """Re-hash a release root against its own manifest, both directions, before anything is sealed.

    The producer's own obligation, called rather than copied, and its refusal is re-raised carrying
    the ``payload-manifest-mismatch`` token §2.3 names -- so the same disagreement is named the same
    way whether it is caught here, on the seal, or per entry later.  This function writes nothing, so
    a mismatch is a clean refusal with the state plane and the host plane both untouched.
    """
    try:
        producer.verify_root(candidate_root)
    except producer.Refusal as exc:
        raise Refusal(
            f"{MANIFEST_MISMATCH}: the release root {show(str(candidate_root))} disagrees with its own"
            f" {CANDIDATE_MANIFEST_NAME}, so no acquisition ticket may attest to it: {show(exc)}."
            " Nothing was written"
        ) from exc
    except OSError as exc:
        raise Refusal(
            f"the release root {show(str(candidate_root))} could not be verified against its own"
            f" {CANDIDATE_MANIFEST_NAME}: {show(exc)}. Nothing was written"
        ) from exc


def classify_payload(config: Config, producer: ModuleType) -> PayloadCandidate:
    """Resolve the ONE payload root and say which acquisition prestate this run is in.

    Two prestates, both admissible and neither guessed at: a receipt already filed for this archive
    digest (REUSE), or a release root at the layout with none (AUTO-SEAL).  Nothing is written here --
    the seal happens later, after every other pre-effect admission -- so every refusal below leaves
    both planes exactly as they were.
    """
    filed = acquisition_receipt_names(config)
    if filed:
        receipt_path, raw, receipt, archive_sha256 = admit_acquisition_receipt(config)
        candidate_root = admit_candidate_root(config, receipt, archive_sha256)
        existing: tuple[Path, bytes, dict[str, Any]] | None = (receipt_path, raw, receipt)
    else:
        candidate_root, archive_sha256 = admit_release_root(config)
        verify_release_root(producer, candidate_root)
        existing = None
    manifest, candidate_id, version = admit_candidate_manifest(candidate_root)
    inventory = manifest_inventory(manifest, candidate_root)
    return PayloadCandidate(
        candidate_root=candidate_root,
        archive_sha256=archive_sha256,
        manifest=manifest,
        candidate_id=candidate_id,
        resolved_version=version,
        inventory=inventory,
        existing=existing,
    )


def admit_payload(
    config: Config, candidate: PayloadCandidate, producer: ModuleType, instant: str
) -> AdmittedPayload:
    """Hold an admitted acquisition ticket for this payload, sealing one first when there is none.

    THE SEAL IS A CALL, NOT A COPY: ``write_receipt`` verifies the root against its manifest again --
    its own obligation, which this module does not get to waive -- derives both digests, writes
    create-only, and reads the file back.  Everything this module supplies is a fact it already
    observed: the root, the layout's own archive digest, and this run's instant.  Given those, the
    bytes are the bytes that module's CLI would have written for the same root.

    Then the document is READ BACK OFF DISK and admitted by ``admit_acquisition_receipt`` -- the same
    validator a hand-placed receipt faces.  A run does not trust a receipt because it wrote it.
    """
    if candidate.existing is not None:
        receipt_path, raw, receipt = candidate.existing
        acquisition = "reused"
    else:
        try:
            producer.write_receipt(
                root=candidate.candidate_root,
                state_home=config.state_home,
                archive=None,
                archive_sha256=candidate.archive_sha256,
                operation_id=None,
                installed_at=instant,
            )
        except producer.Refusal as exc:
            raise Refusal(
                f"the acquisition ticket for the release root"
                f" {show(str(candidate.candidate_root))} could not be sealed, so this activation has"
                f" no admissible payload evidence: {show(exc)}. Nothing was written"
            ) from exc
        except producer.UnknownEffect as exc:
            raise UnknownEffect(
                f"the acquisition ticket for the release root"
                f" {show(str(candidate.candidate_root))} was written but this run cannot say what it"
                f" holds: {show(exc)}"
            ) from exc
        except OSError as exc:
            raise Refusal(
                f"the acquisition ticket for the release root"
                f" {show(str(candidate.candidate_root))} could not be sealed: {show(exc)}. Nothing"
                " was written"
            ) from exc
        receipt_path, raw, receipt, sealed_digest = admit_acquisition_receipt(config)
        if sealed_digest != candidate.archive_sha256:
            raise UnknownEffect(
                f"the acquisition ticket this run sealed is filed as {show(sealed_digest)} but the"
                f" release root it verified is keyed {show(candidate.archive_sha256)}; the acquisition"
                " plane now holds a document this run cannot correlate with its own payload"
            )
        acquisition = "sealed"
    return AdmittedPayload(
        receipt_path=receipt_path,
        receipt_bytes=raw,
        receipt=receipt,
        archive_sha256=candidate.archive_sha256,
        operation_id=str(receipt["operation_id"]),
        candidate_root=candidate.candidate_root,
        manifest=candidate.manifest,
        candidate_id=candidate.candidate_id,
        resolved_version=candidate.resolved_version,
        inventory=candidate.inventory,
        acquisition=acquisition,
    )


def reassert_acquisition_receipt(payload: AdmittedPayload, effect_started: bool) -> None:
    """The sealed acquisition receipt must be BYTE-IDENTICAL after the whole run.

    It is this activation's provenance and this module never writes it.  A change means either a
    concurrent writer or a defect here, and either way the run's evidence is no longer exact: after
    an effect that is an unknown, before one it is a clean refusal.
    """
    try:
        current = payload.receipt_path.read_bytes()
    except OSError as exc:
        message = (
            f"the acquisition receipt {show(str(payload.receipt_path))} could not be re-read to"
            f" prove it was not written: {show(exc)}"
        )
        raise (UnknownEffect if effect_started else Refusal)(message) from exc
    if current != payload.receipt_bytes:
        message = (
            f"the acquisition receipt {show(str(payload.receipt_path))} changed during this run"
            f" (admitted {show(sha256_bytes(payload.receipt_bytes))}, now"
            f" {show(sha256_bytes(current))}); this operation never writes it, so its provenance is"
            " no longer exact"
        )
        raise (UnknownEffect if effect_started else Refusal)(message)


# ---- phase 2: the payload's own release-contract compatibility claims ------------------------------


def observe_host_version(config: Config) -> str | None:
    """Observe the SELECTED host's version, or take the injected observation.

    The default observation runs that host's own ``--version`` once, with no shell, a bounded
    timeout, and an argument vector taken from the closed host-plane table -- never from the payload's
    own release contract, which arrives inside an admitted archive.  ``shutil.which`` is consulted
    rather than the ambient PATH being reshaped, because a test that strips PATH tests the developer's
    machine instead.  A host that cannot be observed yields ``None``, which is a DIFFERENT input from
    ``UNSUPPLIED``.
    """
    if not isinstance(config.observed_host_version, _Unsupplied):
        return config.observed_host_version
    command = tuple(config.plane.version_command)
    executable = shutil.which(command[0])
    if executable is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, bounded
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            timeout=_HOST_VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    match = re.search(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", completed.stdout or "")
    return match.group(0) if match is not None else None


def load_release_contract(candidate_root: Path) -> dict[str, Any]:
    path = candidate_root / "policy" / RELEASE_CONTRACT_NAME
    raw = read_exact_file(path, _MAX_CONTRACT_BYTES, "the payload's release contract")
    contract = parse_json_object(raw, f"the payload's release contract {show(str(path))}")
    if contract.get("schema_version") != RELEASE_CONTRACT_SCHEMA:
        raise Refusal(
            f"the payload's release contract {show(str(path))} declares schema_version"
            f" {show(contract.get('schema_version'))}, not {show(RELEASE_CONTRACT_SCHEMA)}"
        )
    compatibility = contract.get("compatibility")
    if not isinstance(compatibility, dict):
        raise Refusal(
            f"the payload's release contract {show(str(path))} carries no compatibility claims, so"
            " this activation cannot check the host it is about"
        )
    return contract


def _version_tuple(value: object, subject: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _SEMVER.match(value):
        raise Refusal(f"{subject} is {show(value)}, not a three-part SemVer of ASCII digits")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def select_compatibility_row(
    compatibility: dict[str, Any], plane: Any, agent: str
) -> tuple[dict[str, Any], str]:
    """Resolve the ONE compatibility row the selected plane is about, and the label that names it.

    Claude Code is the Core surface (ADR-0017) and every other host is a companion keyed by its agent
    token, because ADR-0027 item 4 says a companion host never inherits Core's tier -- so a codex
    activation that fell back to the Core row would be reading a claim about a different product host
    and calling it its own.  An absent companion row is refused BY NAME, naming the wave whose reviewed
    contract edit adds one; that is what keeps a grammar-admitted agent from activating against a
    contract that says nothing about it.
    """
    section = plane.contract_section
    if section == CONTRACT_SECTION_CORE:
        row = compatibility.get(section)
        label = f"compatibility.{section}"
        if not isinstance(row, dict):
            raise Refusal(f"the payload's release contract carries no {label} row")
        return row, label
    companions = compatibility.get(section)
    label = f"compatibility.{section}.{agent}"
    if not isinstance(companions, dict):
        raise Refusal(
            f"the payload's release contract carries no compatibility.{section} map, so it declares"
            f" nothing about the {plane.display} plane that {HOST_FLAG} {show(agent)} selects"
        )
    row = companions.get(agent)
    if not isinstance(row, dict):
        raise Refusal(
            f"the payload's release contract declares no {label} row, so it states no host, floor,"
            f" or required capability for the {plane.display} plane; this operation refuses rather"
            " than borrowing another host's compatibility claims"
        )
    return row, label


def check_compatibility(config: Config, candidate_root: Path) -> str:
    """Refuse a DECLARED incompatibility by name; never substitute another version for the observed.

    Three separate refusals, because collapsing them hides which half of the question was
    unanswerable: the contract row is about another host, the observed version is a version the payload
    DECLARES incompatible, or the observed version is below the declared eligibility floor.  A host
    version that could not be observed is refused too: the activation receipt's closed unknowns
    vocabulary has no way to say "the host version was unknown", so admitting one would seal a
    document that silently omits an admission input.

    EVERY ONE OF THOSE IS ABOUT THE SELECTED PLANE'S OWN ROW AND ITS OWN HOST'S VERSIONS.  A declared
    incompatibility names the host it is about, so a Claude Code version declared incompatible cannot
    refuse a Codex activation and the reverse cannot happen either: two hosts' version spaces are
    unrelated, and comparing an observation from one against a declaration about the other is the
    cross-agent defect this plane's keying exists to delete, one layer up.
    """
    plane = config.plane
    contract = load_release_contract(candidate_root)
    compatibility = contract["compatibility"]
    row, label = select_compatibility_row(compatibility, plane, config.agent)
    declared_host = row.get("host")
    if declared_host != plane.contract_host:
        raise Refusal(
            f"the payload's release contract states its {label} compatibility is about the host"
            f" {show(declared_host)}, not {show(plane.contract_host)}; {HOST_FLAG}"
            f" {show(config.agent)} selects the {plane.display} host plane and this operation"
            " activates no other one"
        )
    known = compatibility.get("known_incompatible_host_versions")
    if not isinstance(known, list):
        raise Refusal(
            "the payload's release contract carries no compatibility."
            "known_incompatible_host_versions list, so a declared incompatibility could not be read"
        )
    incompatible: dict[str, str] = {}
    for ordinal, record in enumerate(known):
        if not isinstance(record, dict) or set(record) != {"host", "reason", "version"}:
            raise Refusal(
                f"compatibility.known_incompatible_host_versions[{ordinal}] is not a"
                " {host, reason, version} record"
            )
        version = record["version"]
        _version_tuple(version, f"compatibility.known_incompatible_host_versions[{ordinal}].version")
        reason = record["reason"]
        if not isinstance(reason, str) or not reason:
            raise Refusal(
                f"compatibility.known_incompatible_host_versions[{ordinal}].reason is"
                f" {show(reason)}, not a non-empty string"
            )
        host = record["host"]
        if not isinstance(host, str) or not host:
            raise Refusal(
                f"compatibility.known_incompatible_host_versions[{ordinal}].host is {show(host)},"
                " not the non-empty name of the host that version is about"
            )
        if host != plane.contract_host:
            continue
        incompatible[str(version)] = reason

    observed = observe_host_version(config)
    if observed is None:
        raise Refusal(
            f"the {plane.display} host version could not be observed, so the payload's declared"
            " compatibility claims cannot be checked against this host. This operation refuses"
            " rather than assuming compatibility, and it never substitutes another version for the"
            " observed one"
        )
    if not isinstance(observed, str) or not _SEMVER.match(observed):
        raise Refusal(
            f"the observed {plane.display} host version {show(observed)} is not a three-part SemVer,"
            " so it cannot be compared with the payload's declared claims"
        )
    if observed in incompatible:
        raise Refusal(
            f"the payload DECLARES the observed {plane.display} host version {show(observed)}"
            f" incompatible: {show(incompatible[observed])}. A declared incompatibility is refused"
            " by name, and no other host version is substituted for the observed one"
        )
    floor = _version_tuple(row.get("minimum_host_version"), f"{label}.minimum_host_version")
    if _version_tuple(observed, f"the observed {plane.display} host version") < floor:
        raise Refusal(
            f"the observed {plane.display} host version {show(observed)} is below the payload's"
            f" declared eligibility floor {show(row.get('minimum_host_version'))}; meeting that"
            " floor is eligibility only and falling below it is a declared incompatibility"
        )
    return observed


# ---- phase 3a: classify every entry BEFORE anything is written -------------------------------------


@dataclass(frozen=True)
class PlannedEntry:
    """One managed entry, classified before any effect: what it is now and what will happen to it."""

    entry: Any
    destination: Path
    name: str
    prestate: str
    action: str
    record: dict[str, Any] | None
    detail: str


@dataclass
class Run:
    """The one fact that decides an exit class: had an effect started when this failed?

    Mutable and deliberately tiny.  Everything else about the run travels as a value; this flag is
    the boundary between a clean refusal (3) and an admitted unknown effect (4), so it lives in one
    place that every handler reads.
    """

    effect_started: bool = False
    completed_effects: int = 0
    failures: list[str] = dataclass_field(default_factory=list)
    #: Whether this plane's keyed pointer now names THIS run's receipt. False is the honest default:
    #: an unreplaced pointer is never reported as an activation, and exit 0 requires it.
    pointer_replaced: bool = False
    #: The one line a legacy-pointer migration owes the report, or None when there was nothing to
    #: migrate. Held here rather than printed where it happens, so the report stays one write.
    pointer_migration: str | None = None
    #: The one advisory line a project-scope run owes when the operator's own plane carries a
    #: marketplace overlap, or None. It is a NOTICE and never a refusal (§8 D5), and it is held here
    #: for the same reason the migration line is: the report stays one write.
    overlap_advisory: str | None = None
    #: The one line the acquisition ticket owes the report: which document admitted this payload and
    #: whether this run sealed it or reused one already filed.
    acquisition: str | None = None
    #: The ticket THIS run sealed, or None when it reused one. A refusal after the seal must name it:
    #: the seal is create-only immutable evidence about a verified root, so a later refusal leaves a
    #: real file behind and reporting "nothing was written" without naming it would be false. The next
    #: run reuses exactly this document, which is why the leftover is a resumption rather than debris.
    sealed_ticket: Path | None = None


def entry_display_name(destination: Path, agent_root: Path) -> str:
    """The receipt's ``entry_name``: one relative ASCII name inside the activated scope."""
    try:
        relative = destination.relative_to(agent_root).as_posix()
    except ValueError as exc:
        raise Refusal(
            f"the destination {show(str(destination))} is not inside the activated agent root"
            f" {show(str(agent_root))}"
        ) from exc
    if not _ENTRY_NAME.match(relative) or ".." in relative.split("/") or len(relative) > 256:
        raise Refusal(
            f"the entry name {show(relative)} is not a relative ASCII entry name the receipt"
            " inventory can carry"
        )
    return relative


def node_kind(path: Path) -> str:
    """The manifest's own three node types, observed without following anything."""
    item = path.lstat()
    if stat.S_ISLNK(item.st_mode):
        return "symlink"
    if stat.S_ISDIR(item.st_mode):
        return "dir"
    if stat.S_ISREG(item.st_mode):
        return "file"
    raise Refusal(f"the payload node {show(str(path))} is neither a file, a directory, nor a symlink")


def verify_entry_against_manifest(payload: PayloadCandidate, source: Path) -> None:
    """Verify the payload subset this activation copies against the candidate manifest's own rows.

    Both directions, because each catches a different defect: an observed node with no row is
    content the manifest never inventoried, and a row with no observed node is a payload the
    manifest says is more complete than it is.  The walk is ``rglob('*')`` exactly as the installer's
    own ``digest`` walks it, so verification and the digest that lands in the receipt see one set.
    """
    root = payload.candidate_root
    try:
        prefix = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise Refusal(
            f"the payload entry {show(str(source))} is not inside the admitted candidate root"
            f" {show(str(root))}"
        ) from exc
    observed: dict[str, Path] = {prefix: source}
    if source.is_dir() and not source.is_symlink():
        for child in sorted(source.rglob("*")):
            observed[child.relative_to(root).as_posix()] = child
    inventoried = {
        name
        for name in payload.inventory
        if name == prefix or name.startswith(f"{prefix}/")
    }
    for name in sorted(set(observed) - inventoried):
        raise Refusal(
            f"{MANIFEST_MISMATCH}: the candidate payload carries {show(name)}, which its manifest does"
            " not inventory, so this activation would copy content the payload's own identity does not"
            " cover"
        )
    for name in sorted(inventoried - set(observed)):
        raise Refusal(
            f"{MANIFEST_MISMATCH}: the candidate manifest inventories {show(name)}, which is absent"
            " from the payload, so the admitted candidate is not the payload its manifest describes"
        )
    for name in sorted(observed):
        path = observed[name]
        row = payload.inventory[name]
        kind = node_kind(path)
        if row.get("type") != kind:
            raise Refusal(
                f"{MANIFEST_MISMATCH}: the candidate payload node {show(name)} is a {kind} while its"
                f" manifest row declares {show(row.get('type'))}"
            )
        if kind == "file":
            digest = sha256_file(path)
            if digest != row.get("sha256"):
                raise Refusal(
                    f"{MANIFEST_MISMATCH}: the candidate payload file {show(name)} digests to"
                    f" {show(digest)} but its manifest row records {show(row.get('sha256'))}"
                )
        elif kind == "symlink":
            target = os.readlink(path)
            if target != row.get("target"):
                raise Refusal(
                    f"{MANIFEST_MISMATCH}: the candidate payload symlink {show(name)} points at"
                    f" {show(target)} but its manifest row records {show(row.get('target'))}"
                )


def classify_entries(
    bundle: ModuleType,
    bundle_config: Any,
    state: dict[str, Any],
    payload: PayloadCandidate,
    agent: str,
    project_root: Path | None = None,
) -> list[PlannedEntry]:
    """Per-entry prestate classification, entirely before any write.

    ``foreign`` and ``modified`` are PRESERVED and NAMED here, never adopted, replaced, or dropped:
    an inventory that omitted them would read as a clean activation of a collided plane.  There is
    no wildcard, no presence-based overwrite, and no delete anywhere in this function.

    The entry filter is the SELECTED agent, not a constant: the payload carries both planes' entries
    and the installer's own ``discover_entries`` labels each one, so selecting by the run's own agent
    is what keeps a codex activation out of the Claude collections and the reverse.

    ONE ARM IS PROJECT-SCOPE ONLY, and ``project_root`` is what turns it on (§3.7).  In the shared user
    home, a byte-identical unowned destination is adopted as ``removable: False`` -- correct there,
    because nothing authorises this lifecycle to remove bytes it did not place in an operator's own
    home.  Inside a root the operator NAMED, the answer differs: a repository that commits its own
    ``<repo>/.claude/**`` payload would otherwise be permanently un-installable on a teammate's fresh
    clone (any byte differs) or permanently un-uninstallable (every byte matches).  The project root is
    the authorisation boundary the user home does not provide, so a destination byte-identical to the
    planned source AND inside that root is adopted ``removable: True``.  Containment is re-checked here
    against the resolved root rather than inferred from the configured root, because this is the arm
    that decides removability.
    """
    # NO KIND IS EXCLUDED AT PROJECT SCOPE (agentic-sdlc-7a2b, W5). W4 filtered the `workflow` kind out
    # here while `claude:workflows:activate` was a second authority over the same destinations; deleting
    # that manager restored single authority, so the payload set is now the same at both scopes and the
    # filter is the selected agent alone.
    discovered = [
        entry for entry in bundle.discover_entries(payload.candidate_root) if entry.agent == agent
    ]
    if not discovered:
        raise Refusal(
            f"the admitted candidate payload at {show(str(payload.candidate_root))} carries no"
            f" {escape_display(agent)}-host entries, so there is nothing this activation could copy"
        )
    outstanding = state.get("pending")
    if isinstance(outstanding, dict):
        raise Refusal(
            "the installer ownership state holds an outstanding lifecycle transition for"
            f" {show(str(outstanding.get('path')))}; recovery is a separate explicit operation and"
            " this activation never resolves one"
        )
    planned: list[PlannedEntry] = []
    for entry in discovered:
        verify_entry_against_manifest(payload, entry.source)
        try:
            destination = bundle.destination_for(entry, bundle_config)
            bundle.assert_safe_collection(entry, destination, bundle_config)
            agent_root = bundle.agent_root(entry, bundle_config)
        except bundle.InstallerError as exc:
            raise Refusal(
                f"the {escape_display(entry.agent)} activation destination is not admissible: {show(exc)}"
            ) from exc
        name = entry_display_name(destination, agent_root)
        key = str(destination)
        record = state.get("entries", {}).get(key)
        if isinstance(record, dict):
            planned.append(_classify_owned(bundle, bundle_config, entry, destination, name, key, record))
            continue
        if bundle.path_present(destination):
            adopted = _project_adoption(bundle, entry, destination, name, project_root)
            planned.append(
                adopted
                if adopted is not None
                else PlannedEntry(
                    entry=entry,
                    destination=destination,
                    name=name,
                    prestate=PRESTATE_FOREIGN,
                    action=ACTION_PRESERVE,
                    record=None,
                    detail=(
                        "an entry this lifecycle does not own already occupies the destination; it is"
                        " preserved and named, never adopted, overwritten, or deleted"
                    ),
                )
            )
            continue
        planned.append(
            PlannedEntry(
                entry=entry,
                destination=destination,
                name=name,
                prestate=PRESTATE_ABSENT,
                action=ACTION_INSTALL,
                record=None,
                detail="no entry occupies the destination; the payload entry will be copied in",
            )
        )
    return planned


def _project_adoption(
    bundle: ModuleType,
    entry: Any,
    destination: Path,
    name: str,
    project_root: Path | None,
) -> PlannedEntry | None:
    """The §3.7 arm: one adoptable destination, or ``None`` when this one is an ordinary collision.

    Every condition is required and each excludes a different way of being wrong:

      * ``project_root is not None`` -- user scope has no such rule at all.
      * the destination is INSIDE that root, re-derived here rather than assumed from the configured
        root, because this is the decision that makes an entry removable.
      * it is not a link and not a junction: a link's bytes live somewhere this receipt does not
        describe, so it stays a named collision however its target reads.
      * its content is exactly the planned source's, by the substrate's own equivalence -- the same
        predicate the user-home adoption arm uses, so "byte-identical" means one thing in both.
      * the published node type matches the kind: an empty directory and an empty file must not be
        adopted as each other.
    """
    if project_root is None or destination.is_symlink() or bundle.is_junction(destination):
        return None
    if not bundle.path_within(destination, project_root):
        return None
    if bundle.is_directory_object(destination) != (entry.kind in bundle.DIRECTORY_KINDS):
        return None
    try:
        if not bundle.content_equivalent(destination, entry.source):
            return None
        installed_digest = bundle.digest(destination)
    except (bundle.InstallerError, OSError):
        return None
    return PlannedEntry(
        entry=entry,
        destination=destination,
        name=name,
        # `owned` is the ownership model's answer for these bytes at this scope, and the row this run
        # writes is what makes it true; the disposition says nothing was published, which is also true.
        prestate=PRESTATE_OWNED,
        action=ACTION_ADOPT,
        record=bundle.entry_record(
            entry, ACTIVATION_MODE, removable=True, installed_digest=installed_digest
        ),
        detail=(
            "the destination is already byte-identical to this payload entry and sits inside the"
            " resolved project root, so it is adopted as removable and nothing is written to it"
        ),
    )


def _classify_owned(
    bundle: ModuleType,
    bundle_config: Any,
    entry: Any,
    destination: Path,
    name: str,
    key: str,
    record: dict[str, Any],
) -> PlannedEntry:
    """Classify one destination that this lifecycle already owns a record for.

    A retargeted root, a changed entry, another plane's mode, and an adopted preserved copy are four
    different facts and each keeps its own named preservation, because replacing any of them would
    be a mutation the operator never asked for.
    """
    def preserved(prestate: str, detail: str) -> PlannedEntry:
        return PlannedEntry(
            entry=entry,
            destination=destination,
            name=name,
            prestate=prestate,
            action=ACTION_PRESERVE,
            record=record,
            detail=detail,
        )

    try:
        authority_matches = bundle.record_authority_matches(key, record, bundle_config)
    except bundle.InstallerError as exc:
        return preserved(
            PRESTATE_MODIFIED,
            f"the recorded destination could not be re-checked, so it is preserved: {escape_display(str(exc))}",
        )
    if not authority_matches:
        return preserved(
            PRESTATE_MODIFIED,
            "the recorded configured root or collection identity no longer matches, so the record is"
            " retargeted; it is preserved and named rather than rewritten",
        )
    if not bundle.entry_matches_record(destination, record):
        return preserved(
            PRESTATE_MODIFIED,
            "the owned entry no longer has its recorded identity, so it was modified outside this"
            " lifecycle; it is preserved and named",
        )
    if record.get("mode") != ACTIVATION_MODE:
        return preserved(
            PRESTATE_OWNED,
            f"the destination is owned in {show(record.get('mode'))} mode by another installation"
            " plane; this activation copies and never converts an existing mode",
        )
    if record.get("removable", True) is False:
        return preserved(
            PRESTATE_OWNED,
            "the destination is an adopted copy preserved on uninstall; it is left exactly as it is",
        )
    try:
        source_digest = bundle.digest(entry.source)
    except (bundle.InstallerError, OSError) as exc:
        return preserved(
            PRESTATE_OWNED,
            f"the payload entry could not be digested, so the owned entry is preserved: {escape_display(str(exc))}",
        )
    same_source = record.get("source") == str(entry.source.resolve())
    if same_source and record.get("digest") == source_digest:
        return preserved(
            PRESTATE_OWNED,
            "the owned copy is already exactly this payload entry, so nothing is written",
        )
    return PlannedEntry(
        entry=entry,
        destination=destination,
        name=name,
        prestate=PRESTATE_OWNED,
        action=ACTION_REFRESH,
        record=record,
        detail="the owned copy differs from this payload entry and will be refreshed transactionally",
    )


# ---- phase 3b: the plan and the journal, both written BEFORE any entry moves ------------------------


def canonical_document_bytes(receipts: ModuleType, document: dict[str, Any], subject: str) -> bytes:
    """One canonical spelling for every document this module writes: the receipt producer's own."""
    try:
        return receipts.canonical_bytes(document)
    except (TypeError, ValueError) as exc:
        raise Refusal(f"{subject} cannot be encoded canonically: {show(exc)}") from exc


def write_replaceable_document(bundle: ModuleType, path: Path, raw: bytes, subject: str) -> None:
    """Durably replace one of this module's own documents, atomically and never in place."""
    try:
        bundle.durable_mkdir(path.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise Refusal(f"{subject} cannot be prepared at {show(str(path.parent))}: {show(exc)}") from exc
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".activation-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            bundle.flush_descriptor(handle.fileno(), full=True)
        os.replace(temporary, path)
        temporary = None
        bundle.fsync_directory(path.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise Refusal(f"{subject} cannot be written at {show(str(path))}: {show(exc)}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def write_new_document(bundle: ModuleType, path: Path, raw: bytes, subject: str) -> None:
    """Create one document that must not already exist: prior evidence is never overwritten."""
    try:
        bundle.durable_mkdir(path.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise UnknownEffect(f"{subject} cannot be prepared at {show(str(path.parent))}: {show(exc)}") from exc
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise UnknownEffect(
            f"{subject} already exists at {show(str(path))}; this operation never overwrites an"
            " existing receipt, because that document is the only evidence of the run that wrote it"
        ) from exc
    except OSError as exc:
        raise UnknownEffect(f"{subject} cannot be created at {show(str(path))}: {show(exc)}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            bundle.flush_descriptor(handle.fileno(), full=True)
        bundle.fsync_directory(path.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise UnknownEffect(f"{subject} cannot be written at {show(str(path))}: {show(exc)}") from exc


def build_plan_document(
    config: Config,
    payload: AdmittedPayload,
    planned: list[PlannedEntry],
    host_version: str,
    instant: str,
) -> dict[str, Any]:
    """The pre-effect intent, in one canonical document whose digest the receipt binds.

    The entries are hoisted into a local before the literal that reports them, the same discipline
    the receipt producer applies to its own body: a comprehension inside the literal would be
    evaluated after the sibling keys, and any observation it made would be dropped from the document
    that exists to report it.
    """
    rows = [
        {
            "action": item.action,
            "destination": str(item.destination),
            "detail": item.detail,
            "entry_name": item.name,
            "prestate": item.prestate,
        }
        for item in planned
    ]
    return {
        "archive_sha256": payload.archive_sha256,
        "candidate_id": payload.candidate_id,
        "candidate_root": str(payload.candidate_root),
        "entries": rows,
        "host": config.agent,
        "mode": ACTIVATION_MODE,
        "observed_host_version": host_version,
        "operation": OPERATION,
        # WHICH COLLECTION ROOT this activation copies into. It replaces the pre-WX `claude_root`,
        # whose name asserted one plane in a document that now states which plane it is about.
        "plane_root": str(config.plane_root),
        "planned_at": instant,
        "public_channel": None,
        "release_claim": "none",
        "resolved_version": payload.resolved_version,
        "schema_version": PLAN_SCHEMA,
        # The plan states the scope in the receipt body's own union spelling, so the intent and the
        # evidence say it identically. The plan is what the receipt's `plan_sha256` binds, and two
        # spellings of one scope across that pair would be one more place they could disagree.
        "scope": scope_object(config),
        "version_source": VERSION_SOURCE,
    }


def scope_object(config: Config) -> dict[str, Any]:
    """The receipt body's closed scope union for this run: EXACT key set per kind.

    One construction site, read by the plan and by the receipt, because the pointer that admits every
    later verb is keyed by exactly these values. A user scope carries no ``root`` and a project scope
    must carry one: the receipt family compares the key sets rather than checking a prose guard, so a
    third spelling here would be refused at the seal.
    """
    if config.scope_kind == SCOPE_PROJECT:
        return {"agent": config.agent, "kind": SCOPE_PROJECT, "root": str(config.configured_root)}
    return {"agent": config.agent, "kind": SCOPE_USER}


def build_journal_document(
    config: Config,
    payload: AdmittedPayload,
    plan_sha256: str,
    installer_state_path: Path,
    phase: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """The effect journal: the plan it binds, the installer state that journals each transaction,
    and one record per entry.  Written ``armed`` before the first effect and ``terminal`` after the
    last, so an interruption leaves a recoverable journal rather than a half-state reported
    complete."""
    rows = [dict(record) for record in records]
    return {
        "candidate_id": payload.candidate_id,
        "entries": rows,
        "host": config.agent,
        "installer_state_path": str(installer_state_path),
        "operation": OPERATION,
        "phase": phase,
        "plan_sha256": plan_sha256,
        "schema_version": JOURNAL_SCHEMA,
    }


# ---- phase 3c: the transactional copy-activation ---------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One entry's observed outcome, with the content digest that lands in the receipt inventory.

    ``mode`` is the mode this run PUBLISHED at that destination, or ``None`` for a row it published
    nothing at -- a preserved foreign collision, or an entry an earlier failure never reached. The
    receipt's per-row mode is where copy-only binds, so it records an observation (the mode
    ``transactional_create``/``transactional_replace`` reported) rather than the mode this run asked
    for.
    """

    name: str
    prestate: str
    disposition: str
    detail: str
    content_sha256: str | None
    unknown_detail: str | None
    mode: str | None = None


def observe_content(bundle: ModuleType, path: Path) -> tuple[str | None, str | None]:
    """Digest one entry that exists, or name why it could not be digested.

    A null digest under a content-bearing disposition is supplied-but-missing, so it must be NAMED
    as an unknown rather than written as a hole; the receipt producer refuses the hole by name.
    """
    try:
        return bundle.digest(path), None
    except (bundle.InstallerError, OSError) as exc:
        return None, f"the entry could not be digested: {escape_display(str(exc))}"


def _preserved_outcome(bundle: ModuleType, item: PlannedEntry, detail: str) -> Outcome:
    """One preserved entry, digested only when there is content a digest could be OF.

    ``absent`` plus ``preserved`` means nothing was there and nothing was written, so a digest there
    would describe content that does not exist and the receipt producer refuses it by name.  That
    null is not-supplied and needs no unknown; a null under a content-bearing disposition is
    supplied-but-missing and does.
    """
    if item.prestate == PRESTATE_ABSENT:
        return Outcome(
            name=item.name,
            prestate=item.prestate,
            disposition=DISPOSITION_PRESERVED,
            detail=detail,
            content_sha256=None,
            unknown_detail=None,
        )
    content, unknown = observe_content(bundle, item.destination)
    return Outcome(
        name=item.name,
        prestate=item.prestate,
        disposition=DISPOSITION_PRESERVED,
        detail=detail,
        content_sha256=content,
        unknown_detail=unknown,
    )


def _unattempted_outcomes(bundle: ModuleType, remaining: list[PlannedEntry]) -> list[Outcome]:
    """Name every managed entry the failure stopped, starting with the one that failed.

    An inventory that dropped them would read as an activation of fewer entries than this operation
    managed, and the receipt's whole job is that the plane it touched is fully named.  The body-level
    ``effect_state`` carries the uncertainty; no entry row claims an effect nobody observed.
    """
    outcomes: list[Outcome] = []
    for ordinal, item in enumerate(remaining):
        detail = (
            "this entry's transaction failed, so no effect on it is claimed; the installer's own"
            " journal is the recovery evidence"
            if ordinal == 0
            else "not attempted, because an earlier entry's transaction failed first"
        )
        outcomes.append(_preserved_outcome(bundle, item, detail))
    return outcomes


def activate(
    bundle: ModuleType,
    bundle_config: Any,
    state: dict[str, Any],
    planned: list[PlannedEntry],
    run: Run,
) -> list[Outcome]:
    """Copy-activate every planned entry transactionally, stopping at the first failure.

    Stopping is deliberate: once one entry's transaction failed, the next one would widen an already
    unknown effect, and a partial activation with a named boundary is more recoverable than a
    half-finished sweep.
    """
    outcomes: list[Outcome] = []
    for index, item in enumerate(planned):
        if item.action == ACTION_PRESERVE:
            outcomes.append(_preserved_outcome(bundle, item, item.detail))
            continue
        if item.action == ACTION_ADOPT:
            # AN OWNERSHIP EFFECT WITH NO BYTE EFFECT. The row is written through the substrate's own
            # `save_owned_entry`, so it is one atomic state write like every other row this run makes,
            # and `effect_started` is set because the ownership document HAS moved -- a failure after
            # this point may not claim an absence of effect. Nothing is written to the destination, so
            # the row's disposition stays `preserved` and its published mode stays null.
            run.effect_started = True
            assert item.record is not None  # built by `_project_adoption`
            try:
                bundle.save_owned_entry(bundle_config, state, str(item.destination), item.record)
            except Exception as exc:  # noqa: BLE001 - an unwritten row leaves this entry unowned
                run.failures.append(
                    f"adoption of {escape_display(item.name)} failed: {escape_display(str(exc))}"
                )
                outcomes.extend(_unattempted_outcomes(bundle, planned[index:]))
                break
            run.completed_effects += 1
            outcomes.append(_preserved_outcome(bundle, item, item.detail))
            continue
        run.effect_started = True
        try:
            bundle.ensure_collection(item.entry, item.destination, bundle_config)
            if item.action == ACTION_INSTALL:
                mode = bundle.transactional_create(
                    item.entry, item.destination, bundle_config, state
                )
                disposition = DISPOSITION_INSTALLED
            else:
                assert item.record is not None  # classified as owned, so a record exists
                mode = bundle.transactional_replace(
                    item.entry,
                    item.destination,
                    bundle_config,
                    state,
                    item.record,
                    action_name="refresh",
                )
                disposition = DISPOSITION_REFRESHED
        except Exception as exc:  # noqa: BLE001 - any failure here leaves this entry's effect unknown
            run.failures.append(
                f"{item.action} of {escape_display(item.name)} failed: {escape_display(str(exc))}"
            )
            outcomes.extend(_unattempted_outcomes(bundle, planned[index:]))
            break
        if mode != ACTIVATION_MODE:
            run.failures.append(
                f"{item.action} of {escape_display(item.name)} published"
                f" {show(mode)} rather than a copy"
            )
            outcomes.extend(_unattempted_outcomes(bundle, planned[index:]))
            break
        content, unknown = observe_content(bundle, item.destination)
        run.completed_effects += 1
        outcomes.append(
            Outcome(
                name=item.name,
                prestate=item.prestate,
                disposition=disposition,
                detail=item.detail,
                content_sha256=content,
                unknown_detail=unknown,
                # The mode the substrate REPORTED publishing, already checked against this plane's
                # copy-only rule above. Recording the observation rather than ACTIVATION_MODE is the
                # difference between a receipt that reads back what happened and one that restates
                # what was asked for.
                mode=mode,
            )
        )
    return outcomes


def build_inventory(
    outcomes: list[Outcome], journal_sha256: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The receipt's inventory and its unknowns, built together and returned as two locals.

    Returned rather than assembled inside a literal, because ``{"unknowns": unknowns, "entries":
    [walk(o) for o in outcomes]}`` evaluates ``unknowns`` BEFORE the walk that appends to it: every
    unknown the walk discovered would be dropped from the document that exists to report it, and the
    body would then pass its own unknown-consistency check because the check reads the list that lost
    the record.
    """
    unknowns: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for outcome in outcomes:
        entries.append(
            {
                "content_sha256": outcome.content_sha256,
                "disposition": outcome.disposition,
                "entry_name": outcome.name,
                # Null for a row this run published nothing at. The receipt family requires a mode
                # exactly where the disposition says bytes were published, and refuses a project-scope
                # row that published anything but a copy.
                "mode": outcome.mode,
                "prestate": outcome.prestate,
            }
        )
        if outcome.content_sha256 is None and outcome.unknown_detail is not None:
            unknowns.append(
                {
                    "detail": outcome.unknown_detail[:512],
                    "observation": "entry-content",
                    "subject": outcome.name,
                }
            )
    if journal_sha256 is None:
        unknowns.append(
            {
                "detail": (
                    "the activation journal could not be digested, so the effect's own record is"
                    " unavailable"
                ),
                "observation": "journal-digest",
                "subject": "journal_sha256",
            }
        )
    return entries, unknowns


def derive_effect_state(
    receipts: ModuleType, run: Run, journal_sha256: str | None, unknowns: list[dict[str, Any]]
) -> tuple[str, str]:
    """Effect state and terminal phase, taken from the receipt producer's OWN matrices.

    Reading the matrices instead of re-expressing them is what keeps this module and the checker
    from disagreeing exactly once, on the run nobody re-validated.  A missing journal binding forces
    ``unknown``: the effect may well have completed, but its own record could not be written, so its
    completeness cannot be evidenced.

    The RECORDED UNKNOWNS are an input, not a decoration.  An effect whose own observations could not
    all be made is partial, never complete, and a derivation that read only the outcomes would have
    claimed complete precisely because an unmade observation is not one of them.
    """
    if journal_sha256 is None:
        state = "unknown"
    elif run.failures and run.completed_effects:
        state = "partial"
    elif run.failures:
        state = "unknown"
    elif unknowns:
        state = "partial"
    else:
        state = "complete"
    admitted = receipts.EFFECT_PHASES[state]
    phase = admitted[0]
    for preference in ("activated", "activated-partial", "unknown", "not-activated"):
        if preference in admitted and preference in receipts.OPERATION_PHASES[OPERATION]:
            phase = preference
            break
    return state, phase


def build_receipt_body(
    receipts: ModuleType,
    config: Config,
    payload: AdmittedPayload,
    entries: list[dict[str, Any]],
    unknowns: list[dict[str, Any]],
    plan_sha256: str,
    journal_sha256: str | None,
    effect_state: str,
    terminal_phase: str,
) -> dict[str, Any]:
    """Write the closed ``distribution-activation-body@2`` observation from already-built locals.

    Both lists arrive complete from ``build_inventory``, which is the whole point: nothing is
    discovered while this literal is being evaluated, so nothing can be dropped by the order in which
    Python evaluates it.
    """
    return {
        "archive_sha256": payload.archive_sha256,
        "candidate_id": payload.candidate_id,
        "effect_state": effect_state,
        "entries": entries,
        "journal_sha256": journal_sha256,
        "operation": OPERATION,
        "plan_sha256": plan_sha256,
        "public_channel": None,
        # The explicit unsealed placeholder: seal WRITES this field, and an absent key would let the
        # producer fill a value the observation never asked it to.
        "record_sha256": "",
        "release_claim": "none",
        # A request is not a readback (Seed agentic-sdlc-0faa). This grammar carries no version
        # request at all, and null says so rather than leaving the key absent.
        "requested_version": None,
        "resolved_version": payload.resolved_version,
        "schema_version": receipts.BODY_SCHEMA,
        # The closed union, not a display token: a reader derives any string it needs from this, and
        # the pointer this run lands is keyed by exactly these values.
        "scope": scope_object(config),
        "terminal_phase": terminal_phase,
        "unknowns": unknowns,
        "version_source": VERSION_SOURCE,
    }


def seal_receipt(
    receipts: ModuleType,
    body: dict[str, Any],
    payload: AdmittedPayload,
    receipt_id: str,
    instant: str,
) -> dict[str, Any]:
    """Derive the sealed receipt through the T1 producer, or carry its named refusals outward.

    Exactly ONE ``derived-from`` ancestor, naming the acquisition receipt this activation drew its
    payload from, and NO ``supersedes``: only an update replaces an earlier receipt, and an install
    that claimed to would retire a record it did not replace.
    """
    document = {
        "ancestors": [
            {
                "expected_kind": receipts.RECEIPT_KIND,
                "receipt_id": payload.operation_id,
                "relation": "derived-from",
            }
        ],
        "body": body,
        "content_digest": "",
        "emitting_plane": EMITTING_PLANE,
        "receipt_id": receipt_id,
        "receipt_kind": receipts.RECEIPT_KIND,
        "schema": receipts.ENVELOPE_SCHEMA,
        "stated_at": instant,
    }
    try:
        result = receipts.derive("seal", document, "the claude activation observation")
    except receipts.InputError as exc:
        raise UnknownEffect(
            f"the activation receipt could not be derived, so this run's effect has no sealed"
            f" evidence: {show(exc)}"
        ) from exc
    if result["verdict"] != receipts.VERDICT_SEALED or not isinstance(result.get("receipt"), dict):
        reasons = "; ".join(escape_display(str(reason)) for reason in result.get("reasons", []))
        raise UnknownEffect(
            "the activation receipt was refused by its own producer, so this run's effect has no"
            f" sealed evidence: {reasons or 'no reason was reported'}"
        )
    return result["receipt"]


def scope_token(config: Config) -> str:
    """The scope's discriminator inside a per-run filename: empty at user scope, keyed at project.

    ONE derivation, read by the receipt identity and by the journal name, because both are filenames
    that must be distinct per run and both were previously distinct only per agent. The user scope adds
    nothing: an agent has exactly one user plane, so the agent already separates them, and appending a
    constant would rename every existing document for no fact.
    """
    if config.scope_kind != SCOPE_PROJECT:
        return ""
    key = hashlib.sha256(str(config.configured_root).encode("utf-8")).hexdigest()[:ROOT_KEY_CHARACTERS]
    return f"{SCOPE_PROJECT}-{key}-"


def receipt_identity(config: Config, payload: AdmittedPayload, instant: str) -> str:
    """One lowercase token identifying this receipt, derived from facts and never from a counter.

    THE AGENT IS PART OF THE IDENTITY, and it has to be: the acquisition receipt's ``operation_id``
    names one payload, so activating that one payload into both planes yields the same
    (operation, payload, instant) triple twice.  Receipts are create-only, so without the agent the
    second plane's install would refuse against the first plane's filed receipt -- and a run whose
    instants happened to differ would instead file two documents an operator cannot tell apart.

    AT PROJECT SCOPE THE ROOT KEY IS PART OF IT TOO, for exactly the same reason one level down: one
    agent has ONE user plane but N project planes, so (operation, agent, payload, instant) repeats
    across two repositories activated from one payload in the same second.  The user scope adds no
    token, because the agent already discriminates the only root it can have; the discriminator is
    added precisely where two runs can differ (agentic-sdlc-7a2b, W4).
    """
    compact = instant.replace("-", "").replace(":", "").lower()
    token = f"{OPERATION}-{config.agent}-{scope_token(config)}{payload.operation_id}-{compact}"
    if not re.match(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z", token):
        raise Refusal(f"the derived receipt identity {show(token)} is not a lowercase ASCII token")
    return token


def migrate_legacy_pointer(bundle: ModuleType, config: Config) -> str | None:
    """Re-file the pre-keyed pointer at its keyed path, BEFORE this run's own admission logic.

    Only (claude, user) can ever have written ``activation/active-receipt.json``, because every writer
    of it spelled the scope ``claude-home``. So the migration is exactly that one move, it runs once,
    and it is announced in the report rather than performed silently.

    BOTH POINTERS PRESENT IS A REFUSAL, not a preference. Choosing one would be this module deciding
    which of two statements about the same plane is current, which is precisely the guess a pointer
    exists to remove; the refusal names both paths and the remedy. That is also how the migration's
    own crash window resolves: the keyed pointer is written durably before the legacy one is unlinked,
    so an interruption between the two leaves both present and the next verb refuses by name instead
    of acting on an ambiguity.

    A PLANE THAT COULD NOT HAVE WRITTEN IT DOES NOT TOUCH IT. A codex run returns immediately: the
    legacy document is a claude statement, so re-filing it under a codex key would move one plane's
    activation onto another, and refusing on its mere presence would block a plane it says nothing
    about. The claude plane still migrates and still refuses the ambiguity, so nothing is weakened for
    the one plane the document can be about.

    Returns the one line to report, or ``None`` when there was nothing to migrate.
    """
    if not config.migrates_legacy_pointer:
        return None
    legacy = config.legacy_active_receipt_path
    keyed = config.active_receipt_path
    try:
        item = legacy.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Refusal(
            f"the legacy active pointer {show(str(legacy))} cannot be inspected, so whether this plane"
            f" already states an activation is unknown: {show(exc)}"
        ) from exc
    if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode):
        raise Refusal(
            f"the legacy active pointer {show(str(legacy))} is a link or not a regular file; a"
            " lifecycle plane resolves a fixed path, and a redirection there is state nobody recorded"
        )
    if bundle.path_present(keyed):
        raise Refusal(
            f"legacy-pointer-ambiguity: this plane carries both the legacy pointer"
            f" {show(str(legacy))} and the keyed pointer {show(str(keyed))}. Two statements of what one"
            " plane owns is an ambiguity this verb refuses rather than resolves; remove the one that is"
            " not current and run this verb again. Nothing was written"
        )
    raw = read_exact_file(legacy, _MAX_RECEIPT_BYTES, "the legacy active pointer")
    write_replaceable_document(bundle, keyed, raw, "the migrated active receipt pointer")
    try:
        legacy.unlink()
        bundle.fsync_directory(legacy.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise Refusal(
            f"the legacy active pointer {show(str(legacy))} was copied to {show(str(keyed))} but could"
            f" not be removed, so this plane now states its activation twice: {show(exc)}. Remove the"
            " legacy path by hand; nothing else was written"
        ) from exc
    return (
        f"migrated the legacy active pointer {escape_display(str(legacy))} to the keyed path"
        f" {escape_display(str(keyed))} (one pointer per agent, scope, and root)"
    )


def replace_active_pointer(bundle: ModuleType, config: Config, raw: bytes) -> None:
    """Point the plane at THIS receipt, atomically, only after it is durably filed.

    ``os.replace`` plus a parent fsync inside ``write_replaceable_document``: a kill before this call
    leaves the plane with no pointer at all -- exactly the state ``ccodex sdlc update`` and
    ``ccodex sdlc uninstall`` refuse by name -- and a kill after it leaves this receipt, which is
    already durably filed under its own id.  There is no window in which the pointer names a receipt
    no directory holds.

    This mirrors ``ccodex_sdlc_update.replace_active_pointer`` deliberately and is RE-EXPRESSED
    rather than imported: importing that ticket's module here would make its refusals this module's
    behaviour.  A failure is never a clean refusal, because the entries have already moved and the
    receipt is already filed: it is an unknown effect that names the pointer this run could not
    write, so an operator reads a sealed receipt beside a plane with no active statement rather than
    a success that was never activated.
    """
    try:
        write_replaceable_document(bundle, config.active_receipt_path, raw, "the active receipt pointer")
    except Refusal as exc:
        raise UnknownEffect(
            f"the activation completed but the active pointer {show(str(config.active_receipt_path))}"
            f" could not be written, so this plane states no active receipt: {exc}"
        ) from exc


# ---- the run --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Options:
    """The whole admitted vector: one selected plane and the two optional requests.

    A record rather than three returned values, because a caller that unpacked a tuple in the wrong
    order would run a real activation for an operator who asked for a preview.
    """

    agent: str
    #: The scope the dispatcher admitted, defaulting to the operator's own plane for a caller that named
    #: none -- which is the vector every pre-project dispatcher built.
    scope_kind: str = SCOPE_KIND
    #: The project root the operator NAMED, or ``None``. It is a request here and not yet a root: the
    #: resolution ladder judges it, and a run resolves one from the working directory when none was
    #: named.
    requested_project: Path | None = None
    #: The mode the operator REQUESTED, or ``None`` for "take the plane's own". Kept distinct from the
    #: mode this plane publishes, so the report can state the resolution instead of hiding it.
    requested_mode: str | None = None
    dry_run: bool = False

    @property
    def resolved_mode(self) -> str:
        """The mode the substrate is asked for. ``link`` never reaches here -- it is refused first."""
        return ACTIVATION_MODE

    #: WHY THE REPORT WORDING AVOIDS "publication": that word is an authority token in the shipped
    #: non-authority scanner's closed vocabulary, and a line about a copy carries no denial marker, so
    #: naming the mode a "publication mode" made an honest sentence read as an authorization claim
    #: (caught by `tests/test_lifecycle_exit_conformance.py`'s NonAuthorityTest, not by review).


def parse_argv(argv: list[str]) -> Options:
    """This module owns no grammar; it admits exactly the vector its dispatcher forwards.

    A direct invocation with any other vector is a pre-effect refusal, not a usage error, because
    the dispatcher already owns usage and a second opinion here would report the same defect twice.
    The shape is fixed: the selected plane first, then at most one each of ``--scope <kind>``,
    ``--project <path>``, ``--mode <value>``, and ``--dry-run``, in that order.  A repeated or
    reordered flag is refused rather than tolerated, because this vector is BUILT by one caller and a
    shape it did not build is a caller defect, not an operator's typo.

    ``--scope`` is OPTIONAL and defaults to the user plane, because that is the vector every
    pre-project dispatcher built and the only scope a caller that names none can mean.  ``--project``
    without ``--scope project`` is refused here as well as at the dispatcher: the two flags are one
    request, and a module that accepted a root it would not use would activate the wrong plane.
    """
    planes = load_sibling("ccodex_sdlc_host_planes")
    admitted = (
        f"[{HOST_FLAG!r}, <{'|'.join(planes.AGENTS)}>] optionally followed by"
        f" [{SCOPE_FLAG!r}, <{'|'.join(SCOPE_KINDS)}>], [{PROJECT_FLAG!r}, <path>],"
        f" [{MODE_FLAG!r}, <{'|'.join(INSTALL_MODES)}>] and {DRY_RUN_FLAG!r}"
    )
    rest = list(argv)
    if len(rest) < 2 or rest[0] != HOST_FLAG or rest[1] not in planes.HOST_PLANES:
        raise Refusal(
            f"{SURFACE} admits exactly {admitted}; this module received"
            f" {[escape_display(item) for item in argv]}"
        )
    agent, rest = rest[1], rest[2:]
    scope_kind = SCOPE_KIND
    if len(rest) >= 2 and rest[0] == SCOPE_FLAG:
        if rest[1] not in SCOPE_KINDS:
            raise Refusal(
                f"{SURFACE} {SCOPE_FLAG} admits {', '.join(SCOPE_KINDS)}; this module received"
                f" {show(rest[1])}"
            )
        scope_kind, rest = rest[1], rest[2:]
    requested_project: Path | None = None
    if len(rest) >= 2 and rest[0] == PROJECT_FLAG:
        if scope_kind != SCOPE_PROJECT:
            raise Refusal(
                f"{SURFACE} {PROJECT_FLAG} is admitted only with {SCOPE_FLAG} {SCOPE_PROJECT}; a"
                " user-scope run has no project root to name"
            )
        if not rest[1]:
            raise Refusal(f"{SURFACE} {PROJECT_FLAG} was supplied with an empty path")
        requested_project, rest = Path(rest[1]), rest[2:]
    requested_mode: str | None = None
    if len(rest) >= 2 and rest[0] == MODE_FLAG:
        if rest[1] not in INSTALL_MODES:
            raise Refusal(
                f"{SURFACE} {MODE_FLAG} admits {', '.join(INSTALL_MODES)}; this module received"
                f" {show(rest[1])}"
            )
        requested_mode, rest = rest[1], rest[2:]
    dry_run = False
    if rest and rest[0] == DRY_RUN_FLAG:
        dry_run, rest = True, rest[1:]
    if rest:
        raise Refusal(
            f"{SURFACE} admits exactly {admitted}; this module received"
            f" {[escape_display(item) for item in argv]}"
        )
    return Options(
        agent=agent,
        scope_kind=scope_kind,
        requested_project=requested_project,
        requested_mode=requested_mode,
        dry_run=dry_run,
    )


def admit_mode(options: Options) -> str:
    """Resolve the requested mode to this plane's one publication mode, or refuse ``link`` by name.

    ``link`` is not silently downgraded to a copy, because the operator asked for a specific
    publication shape and getting a different one without being told is the drop this wiring exists to
    delete.  It is also not forwarded to the substrate: the substrate would publish a link, and this
    module's copy-only check would then catch it only after the bytes had moved.
    """
    if options.requested_mode == "link":
        raise Refusal(
            f"{SURFACE} {MODE_FLAG} link is not admissible for an acquired candidate payload"
            " (mode-forbidden-for-acquired-payload): this plane copies and never links, because a link"
            " would make every activated entry depend on a payload root under the acquisition plane"
            " that a later acquisition can replace or remove. The live-edit loop that mode names is a"
            " checkout payload, which this receipted plane does not admit. Pass"
            f" {MODE_FLAG} copy, {MODE_FLAG} auto, or omit {MODE_FLAG}; nothing was written"
        )
    return options.resolved_mode


def mode_report_line(options: Options) -> str:
    """One line stating what the mode request resolved to, so a resolution is never silent."""
    if options.requested_mode is None:
        return f"mode: {ACTIVATION_MODE} (this plane copies and never links; none was requested)"
    return (
        f"mode: requested {escape_display(options.requested_mode)}, resolved"
        f" {ACTIVATION_MODE} (this plane copies and never links)"
    )


def marketplace_advisory(config: Config) -> str:
    """The project-scope overlap NOTICE: one named line, stating what it does and does not mean."""
    return (
        f"overlap: a Claude marketplace overlap is present under"
        f" {escape_display(str(config.home / '.claude'))}, which is the operator's own plane and not"
        " this project; the same entries may reach a session from both, and this project activation"
        " proceeded"
    )


def admit_scope(config: Config, options: Options, bundle: ModuleType) -> Config:
    """Resolve the scope this run activates, or refuse by name before any payload work.

    A user scope has nothing to resolve. A project scope resolves ONE root through the substrate's
    ordered ladder and returns a configuration carrying it, so every later property -- the configured
    root, the plane root, the pointer key, the receipt's scope union -- derives from one value that was
    judged once.

    THE PLANE'S OWN LAYOUT DECIDES WHETHER PROJECT SCOPE EXISTS FOR IT. A plane with no project
    collection refuses here by name rather than deriving a root: for Codex that would mean publishing
    this bundle's `skills/` and `agents/` at a repository's own top level, because its configured root
    IS its agent root. The refusal names the plane and the scope that does serve it.

    AN EXPLICITLY NAMED PATH THAT DOES NOT EXIST is `unresolvable-project-root` HERE, even though the
    ladder reports it as merely absent: an install publishes bytes, and there is no directory to
    publish into. `uninstall` is the one verb that admits that state, because records can be retired
    for a root whose bytes are already gone.
    """
    if config.scope_kind != SCOPE_PROJECT:
        return config
    plane = config.plane
    if plane.project_collection is None:
        raise Refusal(
            f"{SURFACE} {SCOPE_FLAG} {SCOPE_PROJECT} is not admissible for the"
            f" {escape_display(plane.display)} plane (project-scope-unsupported-for-agent): its"
            " configured root IS its agent root, so a project root would place this bundle's"
            " collections at the repository's own top level, and nothing in this distribution measures"
            " a repository-local collection that host reads. Use"
            f" {SCOPE_FLAG} {SCOPE_USER} for that plane; nothing was written"
        )
    resolution = bundle.resolve_project_root(
        options.requested_project,
        cwd=Path.cwd(),
        operator_home=config.home,
        plane_roots=(config.home, config.codex_home),
    )
    if resolution.state == bundle.PROJECT_ABSENT:
        raise Refusal(
            f"{SURFACE} {SCOPE_FLAG} {SCOPE_PROJECT} cannot activate"
            f" {show(str(resolution.root))} (unresolvable-project-root): the path does not exist, so"
            " there is no repository to publish a plane into. Nothing was written"
        )
    if not resolution.admitted:
        raise Refusal(
            f"{SURFACE} {SCOPE_FLAG} {SCOPE_PROJECT} refused this root"
            f" ({resolution.refusal}): {escape_display(resolution.detail)}. Nothing was written"
        )
    return dataclass_replace(config, project_root=resolution.root)


def run_install(config: Config, options: Options, run: Run) -> int:
    """The four phases, in order, each refusing by name before the next could move anything."""
    plane = config.plane
    # THE MODE REQUEST IS ADMITTED BEFORE THE PLATFORM, deliberately. A mode this plane can never
    # publish is a property of the request and of the payload class, not of the host, so refusing it
    # first gives one answer on every host -- which is what lets the seam suite and the shipped
    # artifact's smoke manifest assert ONE expected text instead of a per-platform pairing (the W0
    # recorded gap). The platform refusal is about the payload and still fires for every other vector.
    admit_mode(options)
    admit_platform(config)
    instant = observe_instant(config)
    receipts = load_sibling("distribution_activation_receipt")
    bundle = load_sibling("install_skill_bundle")
    producer = load_acquisition_producer()
    # THE SCOPE IS RESOLVED BEFORE ANY PAYLOAD WORK, so a refused root costs no acquisition read and
    # leaves no ticket behind. Everything below reads the returned configuration.
    config = admit_scope(config, options, bundle)

    # The legacy pointer is re-filed BEFORE this run's own admission, so every later decision reads
    # one plane with one pointer. It is a pre-effect move of this module's own bookkeeping document,
    # not a host-plane effect, and a refusal here leaves the plane exactly as it was. A PREVIEW DOES
    # NOT MOVE IT: re-filing is a write, and a preview that performed one would make its own "nothing
    # was changed" false, so it is reported as pending instead.
    candidate = classify_payload(config, producer)
    host_version = check_compatibility(config, candidate.candidate_root)

    # THE CONFIGURED ROOT IS THE SCOPE'S ROOT: at project scope `config.configured_root` is the
    # resolved repository, so the substrate derives `<root>/.claude` through its own `agent_root` and
    # `assert_safe_collection` keeps every destination inside it. Nothing about the ownership model
    # changes; what changes is which root it is pointed at.
    bundle_config = bundle.Config(
        candidate.candidate_root,
        config.configured_root if config.scope_kind == SCOPE_PROJECT else config.home,
        config.codex_home,
        options.resolved_mode,
        options.dry_run,
        config.agent,
        config.installer_state_root,
    )
    # A marketplace overlap is a per-plane gate: only Claude has a plugin channel that can publish the
    # same entries this bundle owns, so only Claude's activation can be blocked by one. The check is
    # selected by the plane's own field rather than by an inline agent comparison, so the reason it is
    # Claude-only stays beside the plane's other properties.
    #
    # AT PROJECT SCOPE IT IS AN ADVISORY LINE AND BLOCKS NOTHING (ratified §8 D5). The overlap it names
    # is a fact about the OPERATOR'S OWN plane -- `config.home`, never the project root, whichever scope
    # this run activates -- and a marketplace plugin does not own a repository's `.claude/`, so there is
    # no second publisher of these destinations to collide with. What an operator may still want to know
    # is that the same entries reach their session from two places, so the line is emitted and the
    # activation proceeds. Escalating it would need a measurement of an actual session's load, which is
    # what D5 defers.
    overlap = bool(plane.checks_marketplace_overlap and bundle.marketplace_overlap(config.home))
    if overlap and config.scope_kind != SCOPE_PROJECT:
        raise Refusal(
            f"a Claude marketplace overlap is present under {show(str(config.home / '.claude'))};"
            " for Claude, use either direct installation or the marketplace, never both. The"
            " overlap blocks this Claude activation and nothing was written"
        )
    run.overlap_advisory = marketplace_advisory(config) if overlap else None

    if options.dry_run:
        # THE PREVIEW STOPS HERE, above every write this module can make: no legacy-pointer migration,
        # no acquisition seal, no plan, no journal, no entry, no pointer. `installer_lock` is entered
        # with `dry_run` set, which the substrate answers by yielding without creating the state
        # directory a lock file would need -- so a preview on a host with no state plane leaves it
        # with no state plane.
        with bundle.installer_lock(bundle_config):
            try:
                state = bundle.load_config_state(bundle_config)
                bundle.validate_state(bundle_config, state)
            except bundle.InstallerError as exc:
                raise Refusal(f"the installer ownership state is not admissible: {show(exc)}") from exc
            planned = classify_entries(
                bundle, bundle_config, state, candidate, config.agent, config.project_root
            )
        report_preview(config, options, candidate, planned, host_version, run)
        return EXIT_OK

    run.pointer_migration = migrate_legacy_pointer(bundle, config)
    payload = admit_payload(config, candidate, producer, instant)
    run.acquisition = acquisition_report_line(payload)
    run.sealed_ticket = payload.receipt_path if payload.acquisition == "sealed" else None

    with bundle.installer_lock(bundle_config):
        try:
            state = bundle.load_config_state(bundle_config)
        except bundle.InstallerError as exc:
            # Every ownership schema but the installer's current one is refused HERE, by
            # `load_config_state`, whose message names the version it found and the remedy.
            # There is no per-generation branch left to take: demolition rank 4 deleted the
            # v1/v2/v3 readers and their migrations, so a document this installer did not
            # write is one refusal rather than several.
            raise Refusal(f"the installer ownership state is not readable: {show(exc)}") from exc
        try:
            bundle.validate_state(bundle_config, state)
        except bundle.InstallerError as exc:
            raise Refusal(f"the installer ownership state is not admissible: {show(exc)}") from exc

        planned = classify_entries(
                bundle, bundle_config, state, candidate, config.agent, config.project_root
            )
        plan_document = build_plan_document(config, payload, planned, host_version, instant)
        plan_raw = canonical_document_bytes(receipts, plan_document, "the activation plan")
        plan_sha256 = sha256_bytes(plan_raw)
        plan_path = (
            config.plans_dir
            / f"{OPERATION}-{config.agent}-{payload.candidate_id}-{plan_sha256[:12]}.json"
        )
        write_replaceable_document(bundle, plan_path, plan_raw, "the activation plan")

        # THE AGENT AND THE SCOPE ARE PART OF THE JOURNAL NAME, and both have to be: one payload
        # activated into two planes -- or into two project roots -- shares a candidate id, this document
        # is written replaceably, and the receipt binds its digest, so a name that omitted either would
        # let the second run overwrite the first's journal and leave that receipt naming a
        # `journal_sha256` no file on disk carries. The scope token is derived exactly as the receipt
        # identity's is, from the same one place.
        journal_path = (
            config.journals_dir
            / f"{OPERATION}-{config.agent}-{scope_token(config)}{payload.candidate_id}.json"
        )
        armed_records = [
            {"action": item.action, "entry_name": item.name, "phase": "armed", "prestate": item.prestate}
            for item in planned
        ]
        armed_raw = canonical_document_bytes(
            receipts,
            build_journal_document(
                config, payload, plan_sha256, bundle_config.state_path, "armed", armed_records
            ),
            "the activation journal",
        )
        write_replaceable_document(bundle, journal_path, armed_raw, "the activation journal")

        # Everything above this line is a read or one of this module's own pre-effect documents.
        # Below it, the host plane can change.
        outcomes = activate(bundle, bundle_config, state, planned, run)

        terminal_records = [
            {
                "action": "preserve" if outcome.disposition == DISPOSITION_PRESERVED else outcome.disposition,
                "detail": outcome.detail,
                "disposition": outcome.disposition,
                "entry_name": outcome.name,
                "phase": "complete",
                "prestate": outcome.prestate,
            }
            for outcome in outcomes
        ]
        for failure in run.failures:
            terminal_records.append(
                {
                    "action": OPERATION,
                    "detail": failure,
                    "disposition": "none",
                    "entry_name": "",
                    "phase": "failed",
                    "prestate": "",
                }
            )
        journal_sha256: str | None
        try:
            terminal_raw = canonical_document_bytes(
                receipts,
                build_journal_document(
                    config, payload, plan_sha256, bundle_config.state_path, "terminal", terminal_records
                ),
                "the activation journal",
            )
            write_replaceable_document(bundle, journal_path, terminal_raw, "the activation journal")
            journal_sha256 = sha256_bytes(terminal_raw)
        except Refusal as exc:
            # The effect already ran, so a failure here is never a clean refusal: it is a missing
            # binding, and the receipt records the effect as unknown rather than complete.
            run.failures.append(f"the activation journal could not be finalised: {escape_display(str(exc))}")
            journal_sha256 = None

        entries, unknowns = build_inventory(outcomes, journal_sha256)
        effect_state, terminal_phase = derive_effect_state(receipts, run, journal_sha256, unknowns)
        body = build_receipt_body(
            receipts,
            config,
            payload,
            entries,
            unknowns,
            plan_sha256,
            journal_sha256,
            effect_state,
            terminal_phase,
        )
        receipt_id = receipt_identity(config, payload, instant)
        receipt = seal_receipt(receipts, body, payload, receipt_id, instant)
        receipt_raw = canonical_document_bytes(receipts, receipt, "the activation receipt")
        receipt_path = config.receipts_dir / f"{receipt_id}.json"
        write_new_document(bundle, receipt_path, receipt_raw, "the activation receipt")

        # The pointer moves LAST and only once the receipt above is durably filed, so the plane never
        # names a receipt no directory holds. A partial or unknown effect leaves the receipt filed as
        # evidence and the pointer untouched, because a statement that claims an activation nobody
        # completed is worse than one an operator can still read.
        if not run.failures and effect_state == "complete":
            replace_active_pointer(bundle, config, receipt_raw)
            run.pointer_replaced = True

    reassert_acquisition_receipt(payload, run.effect_started)
    report(config, options, payload, outcomes, effect_state, terminal_phase, receipt_path, run)
    # Exit 0 requires all three halves: every claimed effect completed durably, the receipt sealed,
    # and the plane's active statement naming it. An effect state the producer would not call
    # complete is exit 4 even with no failure recorded, because an observation nobody could make is
    # not a completion; an unmoved pointer is exit 4 because no later verb could act on this plane.
    if run.failures or effect_state != "complete" or not run.pointer_replaced:
        raise UnknownEffect(
            "the activation did not complete every claimed effect and activate its own receipt: the"
            f" sealed receipt records effect_state {show(effect_state)} with terminal_phase"
            f" {show(terminal_phase)}, and the active pointer"
            f" {'names this activation' if run.pointer_replaced else 'was not written'}:"
            f" {'; '.join(run.failures) or 'an observation this run needed could not be made'}"
        )
    return EXIT_OK


def acquisition_report_line(payload: AdmittedPayload) -> str:
    """Name the ticket that admitted this payload, and which of the two prestates produced it.

    Sealed and reused are different facts about the same document, so they are different lines: an
    operator reading "reused" knows this run added no evidence, and one reading "sealed" knows a new
    create-only file exists that the next run will reuse.
    """
    if payload.acquisition == "reused":
        return (
            f"acquisition ticket: REUSED {escape_display(str(payload.receipt_path))} (already filed for"
            " this archive digest, re-validated against its own seal; receipts are create-only and this"
            " run wrote none)"
        )
    return (
        f"acquisition ticket: SEALED {escape_display(str(payload.receipt_path))} from the release root's"
        f" own {CANDIDATE_MANIFEST_NAME}, verified in both directions (a later run reuses exactly this"
        " document)"
    )


def scope_report_lines(config: Config) -> list[str]:
    """What a project-scope run owes its operator, and nothing at user scope.

    Four facts, each said once:

      * WHICH ROOT was resolved, because the operator may have named none and the walk chose one.
      * THAT THE CHANGE TAKES EFFECT AT THE TARGET'S NEXT SESSION, read from the plane table's own
        `project_session_note` -- the sentence carried over from the deleted workflows manager's
        `SESSION_SNAPSHOT_NOTE`. It is the SAME string `update` and `uninstall` print, because all three
        mutations are equally invisible to a registry that was already read.
      * WHAT THAT MEANS FOR THE TWO KINDS WHOSE ENABLEMENT DIFFERS: placing a workflow into a project's
        `.claude/workflows/` enables it, because that directory is the host's only name-discovery
        surface, while hook bytes land inert since settings wiring is its own separate grant. This half
        is install-specific -- it is about placing bytes -- so it is not in the shared note.
      * THAT A COMMITTED COPY IS DOUBLY RECOVERABLE (audit N4). The uninstall's own receipt records the
        removal, and for a git-tracked file `git status` shows the deletion and the index restores it.
        The root always admits as a git project -- the ladder refuses every other kind -- so this line
        is unconditional at project scope rather than guessing at the root's shape.

    The W4 line naming a deferred kind is GONE with the deferral itself (W5): this scope now publishes
    the whole selected agent's payload set, so there is nothing left to name as withheld.
    """
    if config.scope_kind != SCOPE_PROJECT:
        return []
    # Unreachable rather than unlikely, and asserted rather than defaulted: a plane with no project
    # collection is refused by name long before any report, and the plane table pins the note to exactly
    # the planes that have one. An `or ""` here would print a blank line instead of failing loudly, and
    # this function runs AFTER the effects, so a refusal raised here would misclassify a completed run.
    note = config.plane.project_session_note
    assert note is not None  # pinned to `project_collection` by the plane table's own test
    return [
        f"project root: {escape_display(str(config.configured_root))} (resolved; the plane is keyed by"
        " this root, so two worktrees of one repository are two independent planes)",
        note,
        "enablement: a workflow placed in this repository's .claude/workflows/ is discovered there and"
        " nowhere else, so this activation enables it; hook bytes land inert, since wiring one into"
        " settings is its own grant",
        "the project root is a git repository; a committed copy is restorable from its index, so an"
        " uninstall's removal is recorded twice -- by its own receipt, and by git status plus the index",
    ]


def report_preview(
    config: Config,
    options: Options,
    candidate: PayloadCandidate,
    planned: list[PlannedEntry],
    host_version: str,
    run: Run,
) -> None:
    """What a real run WOULD do, with every write named as pending rather than performed.

    Every line here is derived from the same admission a real run makes, which is what makes this a
    preview of THIS operation rather than a second opinion about it.
    """
    ticket = config.acquisition_receipts_dir / f"{candidate.archive_sha256}.json"
    lines = [
        f"{SURFACE} {SCOPE_FLAG} {escape_display(config.scope_kind)}"
        f" --agent {escape_display(config.agent)} {DRY_RUN_FLAG}: nothing was"
        " written, and nothing was previewed that this run could not admit",
        f"candidate {escape_display(candidate.candidate_id[:12])} resolves"
        f" {escape_display(candidate.resolved_version)} via {VERSION_SOURCE} from"
        f" {escape_display(str(candidate.candidate_root))}",
        f"observed {escape_display(config.plane.display)} host version"
        f" {escape_display(host_version)}: admitted against the payload's declared claims",
        mode_report_line(options),
        f"{escape_display(config.agent)} root: {escape_display(str(config.plane_root))}",
    ]
    lines.extend(scope_report_lines(config))
    if run.overlap_advisory is not None:
        lines.append(run.overlap_advisory)
    if candidate.existing is not None:
        lines.append(
            f"acquisition ticket: would REUSE {escape_display(str(candidate.existing[0]))}"
        )
    else:
        lines.append(
            f"acquisition ticket: would SEAL {escape_display(str(ticket))} from the release root's own"
            f" {CANDIDATE_MANIFEST_NAME}, which this preview verified in both directions without"
            " writing it"
        )
    if config.migrates_legacy_pointer and config.legacy_active_receipt_path.is_file():
        lines.append(
            f"legacy pointer {escape_display(str(config.legacy_active_receipt_path))} would be re-filed"
            f" at {escape_display(str(config.active_receipt_path))}; this preview left it alone"
        )
    for item in planned:
        lines.append(
            f"entry {escape_display(item.name)}: {escape_display(item.prestate)} would be"
            f" {escape_display(item.action)}ed -- {escape_display(item.detail)}"
        )
    lines.append(
        f"active pointer {escape_display(str(config.active_receipt_path))} would name the receipt a real"
        " run seals; this preview wrote no receipt and no pointer"
    )
    lines.append(
        "public_channel null and release_claim none: a preview states no published release exists, and"
        " it authorizes no push, publication, merge, or deployment"
    )
    sys.stdout.write("\n".join(lines) + "\n")


def report(
    config: Config,
    options: Options,
    payload: AdmittedPayload,
    outcomes: list[Outcome],
    effect_state: str,
    terminal_phase: str,
    receipt_path: Path,
    run: Run,
) -> None:
    """One line per fact, every artifact-derived value escaped, and no claim beyond the evidence."""
    lines = [
        f"{SURFACE} {SCOPE_FLAG} {escape_display(config.scope_kind)}"
        f" --agent {escape_display(config.agent)}:"
        f" effect {escape_display(effect_state)}, terminal {escape_display(terminal_phase)}",
        f"candidate {escape_display(payload.candidate_id[:12])} resolved"
        f" {escape_display(payload.resolved_version)} via {VERSION_SOURCE}"
        f" (requested: no version was requested)",
        mode_report_line(options),
        f"{escape_display(config.agent)} root: {escape_display(str(config.plane_root))}"
        " (copies, never links)",
    ]
    lines.extend(scope_report_lines(config))
    if run.overlap_advisory is not None:
        lines.append(run.overlap_advisory)
    if run.acquisition is not None:
        lines.append(run.acquisition)
    if run.pointer_migration is not None:
        lines.append(run.pointer_migration)
    for outcome in outcomes:
        lines.append(
            f"entry {escape_display(outcome.name)}: {escape_display(outcome.prestate)} ->"
            f" {escape_display(outcome.disposition)} -- {escape_display(outcome.detail)}"
        )
    for failure in run.failures:
        lines.append(f"failure: {escape_display(failure)}")
    lines.append(f"receipt: {escape_display(str(receipt_path))}")
    lines.append(
        f"active pointer {escape_display(str(config.active_receipt_path))} "
        + (
            "names this activation's receipt"
            if run.pointer_replaced
            else "was NOT written, so this plane states no active receipt and no later lifecycle"
            " verb can act on it"
        )
    )
    lines.append(
        "public_channel null and release_claim none: this activation states no published release"
        " exists, and it authorizes no push, publication, merge, or deployment"
    )
    sys.stdout.write("\n".join(lines) + "\n")


def report_sealed_ticket(run: Run) -> None:
    """Name a ticket this run sealed before it refused, so no refusal implies an empty state plane.

    The acquisition seal is create-only immutable evidence about a VERIFIED ROOT rather than a
    statement about any activation, so a refusal after it is still a clean refusal on the host plane --
    but "refused before any effect" would read as "the state plane is untouched", which would be false.
    The next run reuses exactly this document, which is why it is named rather than removed: removing
    it would be a second effect, and this module removes nothing it did not put there for one run.
    """
    if run.sealed_ticket is None:
        return
    print(
        f"note: the acquisition ticket {escape_display(str(run.sealed_ticket))} was sealed before this"
        " refusal and is left in place as evidence that the release root verified against its own"
        f" {CANDIDATE_MANIFEST_NAME}; a later run reuses it rather than sealing a second one",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    """The dispatcher's entry point: always an ``int`` in the exit class 0-4, never a ``bool``."""
    selected = list(sys.argv[1:] if argv is None else argv)
    run = Run()
    try:
        options = parse_argv(selected)
        # The admitted selector REPLACES the configuration's default plane, so there is exactly one
        # statement of which plane this run touches and it is the one the dispatcher forwarded. A
        # configuration that carried its own agent and an argv that carried another would be two
        # spellings of one fact, which is the shape this wave exists to delete everywhere else.
        return run_install(
            dataclass_replace(default_config(), agent=options.agent, scope_kind=options.scope_kind),
            options,
            run,
        )
    except Refusal as exc:
        if run.effect_started:
            # A refusal raised after an effect started is not a clean refusal; reporting it as one
            # would claim an absence of effect nobody observed.
            print(
                f"error: {SURFACE} left an unknown effect: {escape_display(str(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(f"error: {SURFACE} refused before any effect: {escape_display(str(exc))}", file=sys.stderr)
        report_sealed_ticket(run)
        return EXIT_REFUSED
    except UnknownEffect as exc:
        print(f"error: {SURFACE} left an unknown effect: {escape_display(str(exc))}", file=sys.stderr)
        return EXIT_UNKNOWN
    except Exception as exc:  # noqa: BLE001 - classified against the one fact that decides the class
        if run.effect_started:
            print(
                f"error: {SURFACE} failed after an effect started, so its effect is"
                f" unknown: {escape_display(repr(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(
            f"error: {SURFACE} failed before any effect: {escape_display(repr(exc))}",
            file=sys.stderr,
        )
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
