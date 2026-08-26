#!/usr/bin/env python3
"""``ccodex sdlc uninstall --host <claude|codex>``: receipt-directed retirement of one activation.

WHAT THIS MODULE IS
-------------------
``scripts/ccodex_sdlc.py`` owns the closed grammar of the three mutating lifecycle verbs.  It loads
this file by absolute non-symlink path and enters ``main(["--host", <agent>])``; the integer returned is the exit
class, and a raise after import reads as exit 4 there because the module was already entered.  So
every refusal here is a NAMED return, never an exception escaping to the caller.

AN ORDERED ADMISSION LADDER, WITH EVERY RUNG NAMED
--------------------------------------------------
1. THE KEYED POINTER FOR THIS (AGENT, SCOPE, ROOT).  ``activation/active/<agent>/user.json`` -- or
   ``.../project-<root-key>.json`` -- is this plane's one statement of what it owns, and THE FILENAME
   IS THE ADMISSION AUTHORITY: it is compared against the pointed receipt's own ``scope`` on the kind,
   agent, and root-key axes before a single path is stat'ed, so a hand-moved pointer refuses instead of
   redirecting this removal at another agent's or another root's bytes.  The receipt is validated
   through the sibling-loaded ``distribution_activation_receipt.py``, and its entry inventory is the
   ONLY candidate set on this rung.  Both generations are readable: a ``@1`` receipt is admitted once,
   as the outgoing document this retirement consumes, and the receipt this run seals is always ``@2``.
   A pre-keyed ``activation/active-receipt.json`` is re-filed at the keyed path before the ladder reads
   anything; both present is ``legacy-pointer-ambiguity``, refused by name.
2. THIS SCOPE'S OWNERSHIP ROWS, ANNOUNCED AS A LEGACY-UNRECEIPTED RETIREMENT.  When no pointer exists
   but the ownership document holds rows this scope's root selects, the candidate set is those rows,
   the removal is the substrate's own ``transactional_delete`` (which proves and removes all three
   publication modes, because a legacy plane's rows are honestly links on Unix), and the sealed
   evidence carries ``prestate_evidence: "ledger"`` with NO ancestor -- there is no receipt to derive
   from, and a fabricated one would forge the evidence this rung exists to admit the absence of.  The
   rung exists because ``bundle install`` wrote rows for years without sealing anything, and a
   repository root could be handed to it as a configured home, so those rows would otherwise be
   selected by no verb at all.

There is no wildcard, no ``--all``, no purge, and no directory listing on either rung: a file this
plane never recorded is not a candidate, and with neither a pointer nor a row the run refuses by name
rather than reconstructing a candidate set from directory contents.

OWNERSHIP IS PROVED BEFORE EVERY DELETION
-----------------------------------------
An entry is removed only when THE INVENTORY ROW ITSELF CLAIMS THIS LIFECYCLE OWNED THE BYTES -- a
recorded ``prestate`` of ``absent`` or ``owned`` -- and it exists, is not a symlink surprise, is
reached without traversing a symlinked parent inside the plane, and its CURRENT content digest equals
the digest the inventory recorded, under the one reused digest definition in
``install_skill_bundle.digest``.  Both halves are load-bearing and neither substitutes for the other:
an activation that preserved a foreign or already-modified destination records the OPERATOR'S OWN
digest for that row, so the digest half alone would prove the bytes unchanged and delete a file this
lifecycle explicitly refused to adopt.  Modified,
foreign, retargeted, unreadable, unprovable, and absent entries are PRESERVED and NAMED.  Detection
authorizes nothing: an entry outside the inventory is never removed, adopted, repaired, or reported
as owned, and the collection directories themselves are never removed even when the last inventory
child leaves one empty.

THE OWNERSHIP ROWS THE ACTIVATION WROTE ARE RETIRED WITH THE BYTES
------------------------------------------------------------------
``ccodex sdlc install`` records every activated entry as one row in the shared installer ownership
document through ``install_skill_bundle``'s own transactions, and the read-only projection honestly
reports an owned row whose destination is absent as ``owned-entry-conflict``.  A retirement that
removed the bytes and left the rows therefore made the very next ``ccodex sdlc status`` contradict
the terminal receipt it had just sealed (agentic-sdlc-42ec, wave f194-w1 FINDING-1).  So each
removal that proves an entry owned ALSO retires the matching row, through the installer's own
crash-consistent pending slot and never by a hand-edit of the document: the transition is armed
durably before the quarantine rename and committed once the destination has left the plane, which
is ``transactional_delete``'s own order.  An interruption between the two leaves the armed slot,
and ``install_skill_bundle.recover_pending`` resolves it from the live bytes -- a destination still
matching ``before`` aborts, an absent one commits -- exactly as it resolves every other transition
in that document.  Preservation is never weakened for entries that are NOT part of the retirement:
a row is retired only when it names this exact destination under this configured home AND
``entry_matches_record`` proves the live bytes are the bytes the row records; a row for another
home or for other bytes is preserved and NAMED, and a destination with no row retires nothing.

WHAT IS NEVER TOUCHED
---------------------
Credentials, the Claude login, user settings, plugins, external skill libraries, repositories, Seeds
queues, and ADRs.  None of them can be a candidate, because the candidate set is the receipt's own
inventory and nothing else.  The sealed acquisition receipt and the retired activation receipt are
READ and never written, moved, or re-sealed: their bytes before and after this operation are
identical.

DELIBERATE RESIDUALS
--------------------
  * A validated receipt is a well-formed statement, not a true one.  This module re-proves every
    digest on disk rather than trusting the inventory, but it cannot prove that the plane's entries
    were ever what the receipt says they were.
  * The digest re-proofs narrow a window; they are not a boundary against a same-UID racer mutating
    a destination between the proof and the rename.  ``install_skill_bundle.rename_absent`` likewise
    proves its target absent and then renames, which is two syscalls rather than one atomic
    no-replace rename: the same racer is out of scope for it too.
  * A completed retirement is EVIDENCE.  It authorizes no push, publication, PR mutation, merge,
    deployment, or any other outward effect.
  * ``terminal_phase`` comes from the receipt family's closed matrix, not from this module's opinion:
    a partial retirement terminates ``unknown`` because ``activated-partial`` is not an uninstall
    phase there.

ANCESTOR RELATION, RECORDED DEVIATION
-------------------------------------
The ticket text asks for a ``supersedes`` ancestor to the receipt this retires.  The shipped receipt
family REFUSES that: ``check_ancestors`` admits ``supersedes`` only for ``operation: update`` and
names an install or an uninstall that claimed it as retiring "a record it did not replace", with a
test pinning the rule.  A receipt sealed with ``supersedes`` here would therefore fail its own
family's validation, which is a worse outcome than a differently-typed link.  This module records
the retired receipt as the single required ``derived-from`` ancestor with
``expected_kind: distribution-activation``, which is literally true -- every payload fact in the
terminal receipt is drawn from the receipt it retires -- and the test suite proves the emitted
document validates through the family's own checker.

On the ledger-directed rung there is no receipt to name at all, and the family's own
``prestate_evidence: "ledger"`` variant makes that shape representable: ZERO ancestors, with the
payload facts answered from what this run can read rather than inherited.  What it can read is the
distribution's bump driver -- ``.version-bump.json``'s ``current`` field, recorded as
``version_source: "checkout-tree"`` beside a ``checkout`` object -- so there is no archive to digest
and ``archive_sha256`` is null as NOT-SUPPLIED rather than as an unknown.  ``checkout.dirty`` is
always ``true`` there, and that is honesty rather than caution: the field means "this receipt does not
assert the payload tree equals the commit it names", and nothing here compares a worktree to a commit.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import stat
import sys
import time
import dataclasses
from dataclasses import dataclass
import functools
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

#: Exit classes.  The dispatcher admits 0-4 and treats anything else as an unknown effect.
EXIT_RETIRED = 0
#: A clean refusal BEFORE any effect.  Nothing moved.
EXIT_REFUSED = 3
#: An ADMITTED PARTIAL EFFECT: this run sealed a terminal receipt for a plane it did not fully retire,
#: because at least one inventory entry was preserved or already absent.  Spec Implementation Decision
#: 9 assigns 4 to "an admitted partial or unknown effect" and 1 to "unexpected internal failure", and
#: nothing about a named preservation is unexpected -- so the value is 4, spelled with this repository's
#: own name for that class (``gate_baseline``/``gate_receipt`` both use ``EXIT_PARTIAL = 4``).  It was
#: 1 for one release, borrowed from the installer's ``_uninstall`` convention; a caller that branched
#: on the documented vocabulary read an admitted partial effect as a crash (agentic-sdlc-d7b3).
EXIT_PARTIAL = 4
#: Something moved and the outcome cannot be proved.  No absence of effect may be claimed.  It shares
#: exit 4 with ``EXIT_PARTIAL`` because Decision 9 has ONE class for both admitted-effect states; the
#: two constants stay distinct because the receipt's ``effect_state`` distinguishes them.
EXIT_UNKNOWN = 4

JOURNAL_SCHEMA = "agentic-sdlc/ccodex-sdlc-uninstall-journal@1"
PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-uninstall-plan@1"

#: The plane this run retires is a PARAMETER, and the ONLY default is the primary product host, which
#: ``main`` replaces with the dispatcher's own admitted ``--host`` value before any admission runs.
#: Every per-agent fact -- the collection beneath the configured root, the version-observation argv, the
#: contract row -- lives in ONE record per agent in ``ccodex_sdlc_host_planes`` (agentic-sdlc-7a2b, WX).
HOST_FLAG = "--host"
DEFAULT_HOST = "claude"
#: The one ``host`` token and the one ``activation_scope`` token a v1 body could carry, frozen with that
#: generation.  These are facts about DOCUMENTS a retired writer produced, not about which plane a run
#: selects, so widening the selector must never widen these.
LEGACY_HOST = "claude"
LEGACY_ACTIVATION_SCOPE = "claude-home"

#: The two scope kinds of the receipt family's own union.  The scope decides three things and nothing
#: else: which pointer filename admits this run, which root bounds the removal, and which scope the
#: sealed retirement states.  Everything downstream -- classification, the removal walk, the journal
#: -- is scope-agnostic, which is what makes the project arm a parameter rather than a second verb.
SCOPE_USER = "user"
SCOPE_PROJECT = "project"

SUPPORTED_PLATFORM = "Linux"

# ---- the pointer plane, re-expressed ---------------------------------------------------------------
#
# Re-expressed from ``distribution_activation_receipt`` rather than imported, because the sibling is
# loaded by absolute path at RUN time and a Config property cannot wait for it.  A test pins this
# helper against that module's own ``pointer_path`` for both scope kinds.
ACTIVE_DIRECTORY = "active"
USER_POINTER_NAME = "user.json"
PROJECT_POINTER_PREFIX = "project-"
POINTER_SUFFIX = ".json"
#: The pre-keyed plane's single pointer name.  Only (claude, user) can ever have written it.
LEGACY_ACTIVE_POINTER_NAME = "active-receipt.json"
ROOT_KEY_CHARACTERS = 16

#: The one authoritative file a ``checkout-tree`` version is read from: the bump driver's own current
#: value.  A mid-bump tree whose sibling manifests disagree is a legitimate state here; that drift is
#: the repository gate's business.
VERSION_DRIVER_NAME = ".version-bump.json"
VERSION_SOURCE_CHECKOUT = "checkout-tree"
CHECKOUT_COMMIT_UNKNOWN = "unknown"
_MAX_DRIVER_BYTES = 65536
_MAX_GIT_FILE_BYTES = 4096


def _pointer_path(activation_root: Path, agent: str, kind: str, root: str | None = None) -> Path:
    """The ONE pointer path for one (agent, scope kind, resolved root)."""
    if kind == SCOPE_USER:
        return activation_root / ACTIVE_DIRECTORY / agent / USER_POINTER_NAME
    if kind == SCOPE_PROJECT:
        if not isinstance(root, str) or not root:
            raise Refusal("a project-scope pointer is named by its resolved root, and none was supplied")
        key = hashlib.sha256(root.encode("utf-8")).hexdigest()[:ROOT_KEY_CHARACTERS]
        return activation_root / ACTIVE_DIRECTORY / agent / f"{PROJECT_POINTER_PREFIX}{key}{POINTER_SUFFIX}"
    raise Refusal(f"{kind!r} is not one of this plane's scope kinds")

#: Every character class is written out.  ``\\d`` and ``\\w`` admit Unicode, so an identity spelled
#: with the Arabic-Indic ``٩`` would read as the same token while comparing unequal to it.
_TOKEN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_VERSION = re.compile(r"[0-9A-Za-z]([0-9A-Za-z.+-]*[0-9A-Za-z])?\Z")
_INSTANT = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")

#: The operations whose receipt describes a LIVE activation this verb can retire.  A receipt whose
#: own operation is ``uninstall`` already records a retirement, and retiring it again would remove
#: entries a second time on the strength of a record that says they are gone.
RETIRABLE_OPERATIONS = ("install", "update")
#: The terminal phases of a live activation.  ``not-activated`` moved nothing, so there is nothing to
#: retire, and ``unknown`` means the activation's own effect was never established -- removing on the
#: strength of it would turn an unknown into a deletion.
RETIRABLE_PHASES = ("activated", "activated-partial")

#: The prestates a validated inventory row can carry, re-expressed rather than imported so this
#: decision can still be made when the sibling that owns the vocabulary is unavailable.  A row whose
#: prestate is not one of these four is an UNKNOWN, never an ownership claim.
RECORDED_PRESTATES = ("absent", "owned", "foreign", "modified")
#: The recorded prestates that say the activation NEVER OWNED the bytes at that destination, mapped to
#: the class each one gets here.  ``foreign`` means an entry this lifecycle does not own already
#: occupied the destination; ``modified`` means an owned entry had already lost its recorded identity.
#: In BOTH cases the activation preserved the operator's bytes and recorded THE OPERATOR'S OWN digest
#: as that row's ``content_sha256``, so a current==recorded comparison proves the bytes are unchanged
#: since that observation and proves NOTHING about ownership.  Consulting the record here is what
#: keeps the digest proof from authorizing the one deletion the activation explicitly refused.
UNOWNED_PRESTATE_CLASS = {"foreign": "recorded-foreign", "modified": "recorded-modified"}
#: One sentinel, so a row that supplies no ``prestate`` key at all is distinguishable from a row that
#: supplies the key with an unusable value.  ``None`` cannot serve: it is itself a supplied value.
_PRESTATE_NOT_SUPPLIED = object()

#: The closed classification vocabulary.  Exactly one applies to each inventory entry, and each maps
#: to one receipt prestate.  ``owned-exact`` is the ONLY removable class.
CLASSES = (
    "owned-exact",
    "absent",
    "modified-content",
    "recorded-foreign",
    "recorded-modified",
    "unrecorded-prestate",
    "unrecognised-prestate",
    "foreign-symlink",
    "foreign-type",
    "foreign-unreadable",
    "retargeted-parent",
    "unprovable-inventory",
    "ambiguous-name",
)
CLASS_PRESTATE = {
    "owned-exact": "owned",
    "absent": "absent",
    "modified-content": "modified",
    "recorded-foreign": "foreign",
    "recorded-modified": "modified",
    "unrecorded-prestate": "foreign",
    "unrecognised-prestate": "foreign",
    "foreign-symlink": "foreign",
    "foreign-type": "foreign",
    "foreign-unreadable": "foreign",
    "retargeted-parent": "foreign",
    "unprovable-inventory": "foreign",
    "ambiguous-name": "foreign",
}
CLASS_REASON = {
    "owned-exact": "the current content digest equals the digest the inventory recorded",
    "absent": "the inventory records this entry as owned and nothing is there",
    "modified-content": "the current content digest differs from the digest the inventory recorded",
    "recorded-foreign": (
        "the activation recorded this destination as foreign and preserved it, so the digest the "
        "inventory carries is the operator's own content; matching it proves the bytes are unchanged "
        "since that observation and never proves this lifecycle owns them"
    ),
    "recorded-modified": (
        "the activation recorded this destination as already modified outside this lifecycle and "
        "preserved it, so the digest the inventory carries is the operator's own content; matching it "
        "proves the bytes are unchanged since that observation and never proves ownership"
    ),
    "unrecorded-prestate": (
        "the inventory row supplies no prestate at all, so what the activation observed at this "
        "destination is not recorded and ownership cannot be proved"
    ),
    "unrecognised-prestate": (
        "the inventory row supplies a prestate outside the closed set, so what the activation "
        "observed at this destination cannot be read and ownership cannot be proved"
    ),
    "foreign-symlink": (
        "a link stands where the inventory recorded activated content; this plane is copy-activated, "
        "and removing a link whose target may lie outside the plane is not a removal this receipt "
        "authorizes"
    ),
    "foreign-type": "the object at this path is not a file, directory, or link this plane can prove",
    "foreign-unreadable": "the current content could not be digested, so ownership cannot be proved",
    "retargeted-parent": (
        "a parent inside the plane is a link, so a deletion here could take effect outside the plane"
    ),
    "unprovable-inventory": (
        "the inventory records no content digest for this entry, so there is nothing to prove "
        "unchanged ownership against"
    ),
    "ambiguous-name": "the recorded entry name does not resolve to one path inside the plane",
}


class Refusal(Exception):
    """A named decline BEFORE any effect (exit 3)."""


class UnknownEffect(Exception):
    """Something already moved, so no absence of effect can be claimed (exit 4)."""


@dataclass(frozen=True)
class Config:
    """Every location this verb reads or writes, injectable, with grounded defaults.

    ``default_config`` derives the defaults from the same sources the shipped scripts use, so a test
    can relocate every path without a single environment variable and without touching the operator's
    real plane.
    """

    scripts_dir: Path
    home: Path
    state_root: Path
    activation_root: Path
    #: Codex's configured root, read so the selected plane's boundary can be resolved without this
    #: module inventing a second location convention: ``CODEX_HOME`` or the operator's ``~/.codex``,
    #: exactly as the shipped installer's own CLI resolves it.
    codex_home: Path
    host: str = DEFAULT_HOST
    platform_system: str = SUPPORTED_PLATFORM
    stated_at: str | None = None
    emitting_plane: str = "ccodex-sdlc-uninstall"
    checkpoint: Callable[[str, dict[str, Any]], None] | None = None
    #: Which scope this run retires.  The default is the operator's user plane, which is the only
    #: scope today's grammar can select; the project arm is wired to a resolved root by its own wave,
    #: and everything here already reads the boundary from ``boundary_home``.
    scope_kind: str = SCOPE_USER
    #: The resolved project root at project scope, and ``None`` at user scope.  It is the removal
    #: boundary AND the value the pointer filename's key is derived from.
    project_root: Path | None = None

    @property
    def boundary_home(self) -> Path:
        """The ROOT this run's removal is bounded by: the configured home, or the project root.

        One property, read by the plane root and by the installer configuration this module borrows,
        because a removal bounded by one root while its ownership rows are selected against another
        would be a boundary in name only.
        """
        if self.scope_kind == SCOPE_PROJECT:
            if self.project_root is None:
                raise Refusal("a project-scope retirement is bounded by its resolved root, and none was supplied")
            return self.project_root
        return self.configured_home

    @property
    def plane(self) -> Any:
        """The selected agent's one host-plane record."""
        return host_plane(self.scripts_dir, self.host)

    @property
    def configured_home(self) -> Path:
        """The root the operator SELECTED for this agent at user scope.

        Claude's configured root is the selected home, whose agent root is that home plus ``.claude``;
        Codex's configured root IS its agent root.  Both are the installer's own model, read from the
        plane record rather than re-decided here.
        """
        return self.home if self.plane.collection is not None else self.codex_home

    @property
    def plane_root(self) -> Path:
        """The agent root this run's removal is bounded by."""
        return self.plane.agent_root(self.boundary_home)

    @property
    def retires_legacy_pointer(self) -> bool:
        """Whether THIS plane could have written the pre-keyed pointer, or a v1 body at all."""
        return bool(self.plane.owns_legacy_pointer)

    @property
    def active_receipt_path(self) -> Path:
        """This plane's ONE pointer, at the keyed path (agent, scope kind, root) names."""
        root = str(self.project_root) if self.scope_kind == SCOPE_PROJECT and self.project_root else None
        return _pointer_path(self.activation_root, self.host, self.scope_kind, root)

    @property
    def legacy_active_receipt_path(self) -> Path:
        """Where the pre-keyed plane wrote its single pointer.  Only (claude, user) could have."""
        return self.activation_root / LEGACY_ACTIVE_POINTER_NAME

    def scope_object(self) -> dict[str, Any]:
        """The receipt body's closed scope union for this run: EXACT key set per kind."""
        if self.scope_kind == SCOPE_PROJECT:
            return {"agent": self.host, "kind": SCOPE_PROJECT, "root": str(self.boundary_home)}
        return {"agent": self.host, "kind": SCOPE_USER}

    @property
    def receipts_dir(self) -> Path:
        return self.activation_root / "receipts"

    @property
    def journals_dir(self) -> Path:
        return self.activation_root / "journals"


def absolute(path: Path) -> Path:
    """Make a path absolute without resolving links, junctions, or 8.3 spelling."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def default_config(bundle: ModuleType) -> Config:
    """Defaults grounded in the shipped scripts, not in new invention.

    ``state_root`` is the installer's own ``state_directory()`` -- ``XDG_STATE_HOME`` on Unix,
    ``LOCALAPPDATA`` on Windows -- and the activation root sits beside the acquisition root the
    bundle validator already pins as ``$XDG_STATE_HOME/agentic-sdlc/acquisition``.
    """
    state_root = bundle.state_directory()
    home = absolute(Path.home())
    return Config(
        scripts_dir=Path(__file__).resolve().parent,
        home=home,
        state_root=state_root,
        activation_root=state_root / "agentic-sdlc" / "activation",
        codex_home=default_codex_home(home),
        platform_system=platform.system(),
    )


def default_codex_home(home: Path) -> Path:
    """``CODEX_HOME`` or the documented default, exactly as the shipped installer's CLI resolves it.

    An empty or whitespace-only value is NOT a location: it is treated as unset rather than as the
    current directory, which is what the installer's own argument handling does with the same variable.
    """
    value = os.environ.get("CODEX_HOME")
    if value and value.strip():
        return absolute(Path(value))
    return home / ".codex"


# ---- sibling loading -----------------------------------------------------------------------------


def load_sibling(scripts_dir: Path, stem: str) -> ModuleType:
    """Load one named sibling by absolute file path, never through ambient ``sys.path``.

    The same admission the dispatcher applies to this file: an exact physical sibling, never a
    symlink.  The read-only guard is deliberately NOT installed here -- it exists to block the very
    effects this module owns -- so it is detected instead, in ``refuse_read_only_guard``.
    """
    candidate = scripts_dir / f"{stem}.py"
    if candidate.is_symlink() or not candidate.is_file():
        raise Refusal(f"ccodex sdlc uninstall cannot load its adapter {str(candidate)!r}: it is absent or a link")
    name = f"_ccodex_sdlc_uninstall_{stem}"
    spec = importlib.util.spec_from_file_location(name, candidate)
    if spec is None or spec.loader is None:
        raise Refusal(f"ccodex sdlc uninstall cannot load its adapter {str(candidate)!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an adapter that cannot import is a pre-effect refusal
        raise Refusal(f"ccodex sdlc uninstall adapter {str(candidate)!r} failed to import: {exc!r}") from exc
    return module


@functools.lru_cache(maxsize=None)
def host_plane(scripts_dir: Path, agent: str) -> Any:
    """Resolve ONE agent's host-plane record from the closed table, or refuse before any effect.

    Cached because the record is read at several points in one run and the table is immutable pure
    data.  A refusal is not cached: an exception leaves no entry, so a repaired tree is re-read.
    """
    planes = load_sibling(scripts_dir, "ccodex_sdlc_host_planes")
    try:
        return planes.plane_for(agent)
    except KeyError as exc:
        raise Refusal(
            f"{agent!r} is not one of this lifecycle's host planes ({', '.join(planes.AGENTS)})"
        ) from exc


def refuse_read_only_guard() -> None:
    """Refuse cleanly if this process already installed the reader's read-only guard.

    ``ccodex_sdlc_readonly.install`` patches ``builtins.open``, ``os``, ``shutil``, ``Path``, and
    ``fcntl`` process-globally, and ``block_lifecycle_mutators`` pins the very names this module
    reuses (``write_state``, ``persist_state``, ``installer_lock``).  The shipped dispatcher hands off
    BEFORE it builds any read-only projection, so the guard is never installed on this path; if some
    other caller changes that, a lifecycle mutation must fail as a named refusal before any effect
    rather than as a ``ReadOnlyViolation`` traceback the dispatcher would have to classify as an
    unknown effect.
    """
    guard = sys.modules.get("_ccodex_sdlc_readonly_guard")
    if guard is not None and getattr(guard, "_INSTALLED", False):
        raise Refusal(
            "ccodex sdlc uninstall refuses: this process already installed the read-only guard, whose "
            "stdlib mutation blocks would fail this operation partway through"
        )


# ---- receipt admission ---------------------------------------------------------------------------


def read_receipt_document(dar: ModuleType, path: Path, label: str) -> dict[str, Any]:
    """Read one receipt document, distinguishing not-supplied from supplied-and-unusable.

    The symlink check is this module's own addition on top of the family's reader: the family answers
    "is what I would read a regular file", which is the right question for a supplied argument, while
    a lifecycle plane resolves a FIXED path and a link there is a redirection nobody recorded.
    """
    try:
        item = path.lstat()
    except FileNotFoundError as exc:
        raise Refusal(
            f"ccodex sdlc uninstall found no active {label} at {str(path)!r}; the receipt is the only "
            "statement of what this plane owns, and there is nothing to reconstruct it from"
        ) from exc
    except OSError as exc:
        raise Refusal(f"ccodex sdlc uninstall cannot inspect the active {label} {str(path)!r}: {exc}") from exc
    if stat.S_ISLNK(item.st_mode):
        raise Refusal(
            f"the active {label} {str(path)!r} is a link; a lifecycle plane resolves a fixed path, and "
            "a redirection there is state nobody recorded"
        )
    if not stat.S_ISREG(item.st_mode):
        raise Refusal(f"the active {label} {str(path)!r} is not a regular file, so it cannot be read")
    try:
        return dar.load_document(str(path), label)
    except dar.InputError as exc:
        raise Refusal(f"the active {label} {str(path)!r} is unusable: {dar.escape_display(str(exc))}") from exc


def admit_active_receipt(dar: ModuleType, document: dict[str, Any], path: Path) -> dict[str, Any]:
    """Validate the active receipt through the family's own checker, then admit it for retirement.

    A refused or partly-refused seal is a NAMED refusal: this module never removes anything on the
    strength of a document its own family will not validate.  The reasons are escaped before they
    reach a line, because a receipt's ``detail`` is free text observed in the field.
    """
    result = dar.derive("validate", document, f"the active receipt {path}")
    if result["verdict"] != dar.VERDICT_VALIDATED:
        reasons = "; ".join(dar.escape_display(reason) for reason in result["reasons"][:4])
        raise Refusal(
            f"the active receipt {str(path)!r} does not validate as {dar.BODY_SCHEMA}, so it cannot "
            f"authorize a removal: {reasons}"
        )
    receipt = result["receipt"]
    if not isinstance(receipt, dict):
        raise Refusal(f"the active receipt {str(path)!r} validated without reporting a document")
    return receipt


def migrate_legacy_pointer(bundle: ModuleType, config: Config) -> str | None:
    """Re-file the pre-keyed pointer at its keyed path, BEFORE this run's own admission logic.

    Only (claude, user) can ever have written ``activation/active-receipt.json``, because every writer
    of it spelled the scope ``claude-home``.  At project scope there is nothing to migrate: that
    pointer is a statement about the user plane, and this run does not touch it.

    BOTH POINTERS PRESENT IS A REFUSAL, not a preference.  Choosing one would be this module deciding
    which of two statements about one plane is current -- the guess a pointer exists to remove -- and
    the refusal names both paths and the remedy.  It is also how the migration's own crash window
    resolves: the keyed pointer is written durably before the legacy one is unlinked, so an
    interruption leaves both present and the next verb refuses by name instead of acting.
    """
    if config.scope_kind != SCOPE_USER:
        return None
    if not config.retires_legacy_pointer:
        return None
    legacy = config.legacy_active_receipt_path
    keyed = config.active_receipt_path
    try:
        item = legacy.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Refusal(
            f"the legacy active pointer {str(legacy)!r} cannot be inspected, so whether this plane "
            f"already states an activation is unknown: {exc}"
        ) from exc
    if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode):
        raise Refusal(
            f"the legacy active pointer {str(legacy)!r} is a link or not a regular file; a lifecycle "
            "plane resolves a fixed path, and a redirection there is state nobody recorded"
        )
    if bundle.path_present(keyed):
        raise Refusal(
            f"legacy-pointer-ambiguity: this plane carries both the legacy pointer {str(legacy)!r} and "
            f"the keyed pointer {str(keyed)!r}. Two statements of what one plane owns is an ambiguity "
            "this verb refuses rather than resolves; remove the one that is not current and run this "
            "verb again. Nothing was removed"
        )
    raw = legacy.read_bytes()
    bundle.durable_mkdir(keyed.parent)
    descriptor = os.open(keyed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, raw)
        bundle.flush_descriptor(descriptor, full=True)
    finally:
        os.close(descriptor)
    bundle.fsync_directory(keyed.parent)
    try:
        legacy.unlink()
        bundle.fsync_directory(legacy.parent)
    except OSError as exc:
        raise Refusal(
            f"the legacy active pointer {str(legacy)!r} was copied to {str(keyed)!r} but could not be "
            f"removed, so this plane now states its activation twice: {exc}. Remove the legacy path by "
            "hand; nothing was removed"
        ) from exc
    return (
        f"migrated the legacy active pointer {dar_escape(str(legacy))} to the keyed path "
        f"{dar_escape(str(keyed))} (one pointer per agent, scope, and root)"
    )


def admit_pointer_agreement(dar: ModuleType, body: dict[str, Any], path: Path) -> None:
    """Refuse a pointer whose FILENAME disagrees with the receipt it points at.

    The filename is the admission authority, so the agreement is checked before a single destination is
    classified: a hand-moved pointer must not redirect this removal at another agent's or another
    root's bytes.  A v1 receipt carries no scope union to compare against, and the one pointer name it
    could have been filed under fixes its key already.
    """
    if not isinstance(body.get("scope"), dict):
        return
    disagreements = dar.pointer_disagreements(path, body)
    if disagreements:
        raise Refusal(
            "pointer-receipt-disagreement: "
            + "; ".join(dar_escape(str(reason)) for reason in disagreements)
            + ". Nothing was removed"
        )


def admit_retired_scope(dar: ModuleType, body: dict[str, Any], config: Config, path: Path) -> None:
    """Admit the retired receipt's scope, in whichever generation's spelling it carries.

    A v2 receipt states the closed union and must name exactly this run's (agent, kind, root).  A v1
    receipt states the token ``claude-home``, which only (claude, user) could have written, and it is
    admitted at user scope as the outgoing document this retirement consumes -- once.  The receipt
    this run seals is v2 either way.
    """
    scope = body.get("scope")
    if isinstance(scope, dict):
        expected = config.scope_object()
        if scope != expected:
            raise Refusal(
                f"the active receipt {str(path)!r} records scope {scope!r}, not {expected!r}; a "
                "receipt about another scope, agent, or root describes a plane this run never bounded"
            )
        return
    legacy = body.get("activation_scope")
    if (
        config.scope_kind == SCOPE_USER
        and config.retires_legacy_pointer
        and legacy == LEGACY_ACTIVATION_SCOPE
        and body.get("schema_version") == dar.BODY_SCHEMA_V1
    ):
        return
    raise Refusal(
        f"the active receipt {str(path)!r} states neither this run's scope union "
        f"({config.scope_object()!r}) nor a historical {LEGACY_ACTIVATION_SCOPE!r} scope of a "
        f"{dar.BODY_SCHEMA_V1!r} document this plane could have written; a receipt about another scope "
        "describes a plane this run never bounded"
    )


def admit_retirable(dar: ModuleType, receipt: dict[str, Any], config: Config, path: Path) -> dict[str, Any]:
    """Admit only a validated receipt that describes a LIVE activation of THIS host plane."""
    body = receipt["body"]
    operation = body["operation"]
    if operation not in RETIRABLE_OPERATIONS:
        raise Refusal(
            f"the active receipt {str(path)!r} records operation {operation!r}; only "
            f"{list(RETIRABLE_OPERATIONS)} describe a live activation, and retiring a retirement "
            "would delete a second time on the strength of a record that says the entries are gone"
        )
    # WHICH PLANE, ONCE. A v2 receipt states it as `scope.agent`, and `admit_retired_scope` compares
    # the whole union -- agent included -- against this run's own. A v1 receipt states it as a
    # separate `host` token, which is the only generation that has one to check.
    # A v1 body could only ever have been written for the plane that owns the pre-keyed pointer, so on
    # any other plane it is not history to be retired: this arm compares against THAT plane, and
    # `admit_retired_scope` refuses the document outright where it could not have come from.
    if body.get("schema_version") == dar.BODY_SCHEMA_V1:
        expected_host = LEGACY_HOST if config.retires_legacy_pointer else config.host
        if body.get("host") != expected_host:
            raise Refusal(
                f"the active receipt {str(path)!r} records host "
                f"{dar.escape_display(str(body.get('host')))!r}, not {expected_host!r}; a receipt names "
                "the one host plane it observed"
            )
    phase = body["terminal_phase"]
    if phase not in RETIRABLE_PHASES:
        raise Refusal(
            f"the active receipt {str(path)!r} terminates {phase!r}; only {list(RETIRABLE_PHASES)} "
            "describe a plane with activated entries, and removing on the strength of an unestablished "
            "effect would turn an unknown into a deletion"
        )
    if not isinstance(body.get("entries"), list) or not body["entries"]:
        raise Refusal(
            f"the active receipt {str(path)!r} carries no entry inventory, and the inventory is the "
            "only candidate set a removal may draw from"
        )
    admit_retired_scope(dar, body, config, path)
    return body


# ---- classification: ownership is proved, never assumed -------------------------------------------


def resolve_destination(config: Config, entry_name: Any) -> Path | None:
    """Resolve one inventory entry name to one path INSIDE the plane, or refuse to resolve it.

    The family already refuses ``..`` in an entry name.  This is the second, independent check, on the
    resolved path rather than on the spelling, because a receipt is evidence and never authorization:
    the value that decides where a deletion lands is re-derived here.
    """
    if not isinstance(entry_name, str) or not entry_name:
        return None
    if entry_name.startswith("/") or entry_name.startswith("\\") or ".." in Path(entry_name).parts:
        return None
    candidate = Path(os.path.normpath(str(config.plane_root / entry_name)))
    root = Path(os.path.normpath(str(config.plane_root)))
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def parent_is_retargeted(config: Config, destination: Path) -> bool:
    """Is any directory between the plane root and this entry a link, or unprovable either way?

    A deletion reached through a link takes effect wherever the link points, which is outside what
    this receipt describes.  ``lstat`` on each component, never ``resolve``, so the question asked is
    "is this component a link" and not "where does it end up".  An ``lstat`` that raises reports
    retargeted rather than clear (agentic-sdlc-7c7d): a component this walk cannot even inspect is a
    component this walk cannot clear of being a link, and the per-entry digest proof downstream of
    this call is a second, independent gate -- it never depends on this fail-open having existed --
    so failing closed here costs nothing except calling one more destination "preserved" than a fully
    successful walk would have.
    """
    root = Path(os.path.normpath(str(config.plane_root)))
    current = destination.parent
    while True:
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except OSError:
            return True
        if current == root or current == current.parent:
            return False
        current = current.parent


def classify_entry(
    bundle: ModuleType, config: Config, entry: dict[str, Any]
) -> tuple[str, Path | None, str | None]:
    """Return ``(class, destination, current_digest)`` for one inventory entry.

    THE RECORDED PRESTATE IS CONSULTED BEFORE ANY DISK FACT (agentic-sdlc-9b9a).  A digest comparison
    answers "are these bytes what was observed", which is not the question a deletion needs answered.
    An activation that found an entry it does not own occupying a destination records
    ``prestate: foreign, disposition: preserved`` and -- honestly, because that is what it observed --
    stores THE OPERATOR'S OWN digest as that row's ``content_sha256``.  A consumer that proves
    removability from ``current == recorded`` alone therefore deletes exactly the file the activation
    refused to adopt, and it deletes it because the record is accurate.  So the record's own statement
    about ownership is read first, and a row that does not claim owned bytes is preserved and named
    the same way a modified owned entry is.  A prestate that is missing or outside the closed set is an
    unknown, and an unknown is never removable either.

    The recorded digest is consulted next, because an inventory row whose ``content_sha256`` is null
    -- a supplied-but-missing digest the receipt declared as an unknown -- can never be proved
    unchanged, and reading a null as "no proof needed" is exactly the defect that would delete an
    entry nobody digested.
    """
    name = entry.get("entry_name")
    destination = resolve_destination(config, name)
    if destination is None:
        return "ambiguous-name", None, None

    # Not digested, and the destination is not even stat'ed, for the classes below: none of them can
    # ever be removed, so no disk fact could change the outcome, and a read through a parent that may
    # itself be a link would leave the plane this receipt describes for no gain.
    recorded_prestate = entry.get("prestate", _PRESTATE_NOT_SUPPLIED)
    if recorded_prestate is _PRESTATE_NOT_SUPPLIED:
        return "unrecorded-prestate", destination, None
    if recorded_prestate not in RECORDED_PRESTATES:
        return "unrecognised-prestate", destination, None
    if recorded_prestate in UNOWNED_PRESTATE_CLASS:
        return UNOWNED_PRESTATE_CLASS[recorded_prestate], destination, None

    recorded = entry.get("content_sha256")
    recorded_ok = isinstance(recorded, str) and bool(_HEX64.match(recorded))

    if not bundle.path_present(destination):
        return "absent", destination, None
    if parent_is_retargeted(config, destination):
        return "retargeted-parent", destination, None
    if destination.is_symlink() or bundle.is_junction(destination):
        # Digested for the record: ``digest`` hashes the link's own target bytes and never follows it.
        return "foreign-symlink", destination, safe_digest(bundle, destination)
    if not destination.is_file() and not destination.is_dir():
        return "foreign-type", destination, None
    current = safe_digest(bundle, destination)
    if current is None:
        return "foreign-unreadable", destination, None
    if not recorded_ok:
        return "unprovable-inventory", destination, current
    if current != recorded:
        return "modified-content", destination, current
    return "owned-exact", destination, current


def safe_digest(bundle: ModuleType, path: Path) -> str | None:
    """The one reused digest definition, with an unreadable object reported as an honest unknown."""
    try:
        return bundle.digest(path)
    except (OSError, bundle.InstallerError, ValueError):
        return None


# ---- the plan ------------------------------------------------------------------------------------


def build_plan(config: Config, body: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """The closed, canonical statement of what this run intends, derived before any effect.

    Both lists are built ABOVE the returned literal.  Written the other way, Python would evaluate the
    ``remove`` key's comprehension and the ``preserve`` key's comprehension into a new dict in source
    order -- which happens to work here -- but the plan is what the receipt's ``plan_sha256`` binds,
    and a plan assembled from a value read before the walk that produced it is the same
    evaluation-order defect that drops data.
    """
    remove: list[dict[str, Any]] = []
    preserve: list[dict[str, Any]] = []
    for item in observations:
        if item["class"] == "owned-exact":
            remove.append(
                {
                    "destination": str(item["destination"]),
                    "entry_name": item["entry_name"],
                    "expected_sha256": item["current_sha256"],
                }
            )
        else:
            preserve.append({"entry_name": item["entry_name"], "reason_code": item["class"]})
    remove.sort(key=lambda row: (row["entry_name"], row["destination"]))
    preserve.sort(key=lambda row: (row["entry_name"], row["reason_code"]))
    plan = {
        "candidate_id": body["candidate_id"],
        # This run's own selector, not a field read back out of the retired body: the receipt states
        # the plane once, in its scope union, and `admit_retired_scope` has already proved the two
        # agree before this plan is built.
        "host": config.host,
        "plane_root": str(config.plane_root),
        "preserve": preserve,
        "remove": remove,
        "resolved_version": body["resolved_version"],
        "retired_receipt_id": None,
        "schema_version": PLAN_SCHEMA,
        # The plan states the scope the way the receipt does, so the intent and the evidence say it
        # identically; the plan is what the sealed receipt's ``plan_sha256`` binds.
        "scope": config.scope_object(),
    }
    return plan


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ---- the journal ---------------------------------------------------------------------------------


class Journal:
    """The durable removal journal: what is intended, what moved, and what is outstanding.

    Every transition is written through the installer's own ``write_state`` -- atomic replace plus a
    parent-directory fsync -- so a process that dies between two lines leaves a record naming the
    quarantine container and the destination it came from, never a clean-looking half-state.
    """

    def __init__(self, bundle: ModuleType, path: Path, document: dict[str, Any]) -> None:
        self._bundle = bundle
        self.path = path
        self.document = document

    def write(self, phase: str, *, before_any_effect: bool = False) -> None:
        """Record one durable transition.

        A journal this run cannot write BEFORE anything moved is a clean refusal: there is no effect
        to have lost track of.  After the first quarantine the same failure is an unknown effect,
        because the record of what moved is exactly what is now missing.
        """
        self.document["phase"] = phase
        try:
            self._bundle.write_state(self.path, self.document, False)
        except (OSError, self._bundle.InstallerError) as exc:
            message = f"the removal journal {str(self.path)!r} could not be written: {exc}"
            raise (Refusal(message) if before_any_effect else UnknownEffect(message)) from exc

    def digest(self) -> str | None:
        try:
            return digest_bytes(self.path.read_bytes())
        except OSError:
            return None


# ---- the installer ownership rows ------------------------------------------------------------------


@dataclass
class RowRetirement:
    """One matched installer ownership row, retired through the installer's own pending slot.

    ``armed`` is True exactly while the shared state document carries this row's armed ``uninstall``
    transition.  A crash in that window is the recoverable state, not a defect:
    ``install_skill_bundle.recover_pending`` resolves the slot from the live bytes -- a destination
    still matching ``before`` aborts, an absent destination commits -- so the row and the bytes can
    never silently disagree for longer than one recovery.
    """

    installer_config: Any
    state: dict[str, Any]
    record: dict[str, Any]
    entry_name: str
    armed: bool = False


def admit_ownership_state(bundle: ModuleType, installer_config: Any) -> dict[str, Any]:
    """Admit the shared installer ownership document whose rows this retirement must keep truthful.

    ``ccodex sdlc install`` writes one row per activated entry into this document through the
    installer's own transactions, so removing the bytes while leaving the rows would make the very
    next ``ccodex sdlc status`` contradict the terminal receipt this run seals: the projection
    honestly reports an owned row whose destination is absent as a conflict (agentic-sdlc-42ec).
    Admission happens BEFORE any effect, with the same three named refusals the install verb
    applies: an unreadable document, an inadmissible one, and an outstanding armed transition --
    recovery is a separate explicit operation, and arming this run's transitions over an
    outstanding one would silently discard the record recovery needs.
    """
    try:
        state = bundle.load_config_state(installer_config)
        bundle.validate_state(installer_config, state)
    except (bundle.InstallerError, OSError) as exc:
        raise Refusal(
            "the installer ownership state is not readable, so the ownership rows of the entries "
            f"this retirement would remove cannot be retired with their bytes: {dar_escape(str(exc))}"
        ) from exc
    if isinstance(state.get("pending"), dict):
        raise Refusal(
            "the installer ownership state holds an outstanding lifecycle transition; recovery is a "
            "separate explicit operation and this retirement never resolves or overwrites one"
        )
    return state


def matched_ownership_row(
    bundle: ModuleType, installer_config: Any, state: dict[str, Any], row: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Return the one ownership row this removal may retire, or NAME why a present row is preserved.

    Three facts must agree before a row is armed, because retiring on fewer would weaken the
    preservation the installer promises for entries that are NOT part of this retirement: the row
    is keyed by exactly this destination, it still describes THIS configured home (the installer
    deliberately retains rows for earlier homes), and ``entry_matches_record`` proves the live
    bytes are the bytes the row records -- the same proof ``transactional_delete`` demands before
    it removes anything.  A destination with no row retires nothing and raises no attention: a
    plane activated before rows existed is healthy, not suspect.
    """
    record = state["entries"].get(row["destination"])
    if not isinstance(record, dict):
        return None, None
    if not bundle.destination_is_configured(row["destination"], record, installer_config):
        return None, (
            f"the installer ownership row for {dar_escape(row['entry_name'])} describes another "
            "configured home, so the row is preserved rather than retired"
        )
    if not bundle.entry_matches_record(Path(row["destination"]), record):
        return None, (
            f"the installer ownership row for {dar_escape(row['entry_name'])} does not record the "
            "bytes this retirement proved on disk, so the row is preserved rather than retired"
        )
    return record, None


def roll_back_row_retirement(
    bundle: ModuleType, journal: Journal, retirement: RowRetirement | None
) -> None:
    """Resolve one armed row retirement as an abort, after a removal that moved nothing.

    A roll-back that itself fails is NAMED in the journal's attention and left for the installer's
    own recovery, which reads the untouched destination as ``before`` and aborts; escalating it
    here would turn a self-resolving bookkeeping state into a second failure mode.
    """
    if retirement is None or not retirement.armed:
        return
    try:
        bundle.persist_state(
            retirement.installer_config,
            retirement.state,
            bundle.resolved_pending_state(retirement.state, "abort"),
        )
    except Exception as exc:  # noqa: BLE001 - the armed slot is recoverable; the failure is recorded
        journal.document["attention"].append(
            {
                "entry_name": retirement.entry_name,
                "reason": (
                    "the armed ownership-row retirement could not be rolled back; the installer's "
                    f"own recovery resolves it against the untouched destination: {exc!r}"
                ),
            }
        )
    else:
        retirement.armed = False


# ---- the removal walk ----------------------------------------------------------------------------


def checkpoint(config: Config, point: str, detail: dict[str, Any]) -> None:
    """One test seam for interruption, called at each named transition. No production effect."""
    if config.checkpoint is not None:
        config.checkpoint(point, detail)


def remove_one(
    bundle: ModuleType,
    config: Config,
    journal: Journal,
    row: dict[str, Any],
    outcome: dict[str, bool],
    *,
    nothing_moved_yet: bool,
    retirement: RowRetirement | None = None,
) -> None:
    """Quarantine one proved-owned entry, then delete the quarantined copy. Reused primitives only.

    The shape is the installer's own ``transactional_delete``: reserve a private container beside the
    destination, record the armed transaction durably, rename the destination into the container in
    one namespace operation once ``rename_absent`` has proved the target absent, record the
    quarantine, then remove the quarantined payload and the now-empty container.  A failure BEFORE
    the rename moved nothing and is reported as attention;
    a failure AFTER it is an unknown effect, because the entry has left the plane and this module will
    not claim where it ended up.

    ``retirement`` is the matched installer ownership row, when one exists (agentic-sdlc-42ec).  Its
    transitions bracket the rename in ``transactional_delete``'s own order -- armed immediately
    before it, committed once the destination has left the plane -- so every crash window resolves
    through ``recover_pending`` against the live bytes, and the row can never survive the bytes it
    described.

    ``outcome`` is filled rather than returned, because the caller needs to know whether this entry
    left the plane even on the paths that raise -- and an exception carries no return value.  EVERY
    statement that can fail after the container is reserved lives inside the try: a checkpoint or a
    journal write left outside it would escape the classification this function exists to make.
    """
    destination = Path(row["destination"])
    expected = row["expected_sha256"]

    # Re-prove immediately before the move. This narrows the window; it is not a boundary against a
    # same-UID racer.
    current = safe_digest(bundle, destination)
    if destination.is_symlink() or bundle.is_junction(destination) or current != expected:
        raise Refusal(
            f"the entry {dar_escape(row['entry_name'])} changed between its ownership proof and its "
            "removal, so it was preserved untouched"
        )

    try:
        artifact = bundle.reserve_private_artifact(destination, "backup")
    except Exception as exc:  # noqa: BLE001 - nothing moved, so this entry is preserved and named
        raise Refusal(
            f"no private quarantine could be reserved beside {dar_escape(row['entry_name'])}, so it was "
            f"preserved untouched: {exc!r}"
        ) from exc
    journal.document["pending"] = {
        "container": str(artifact.container),
        "destination": str(destination),
        "entry_name": row["entry_name"],
        "expected_sha256": expected,
        "payload": str(artifact.payload),
    }

    moved = False
    try:
        journal.write("armed", before_any_effect=nothing_moved_yet)
        checkpoint(config, "after-armed", dict(journal.document["pending"]))
        if safe_digest(bundle, destination) != expected:
            raise Refusal(
                f"the entry {dar_escape(row['entry_name'])} changed after its transaction was armed, "
                "so it was preserved untouched"
            )
        if retirement is not None:
            # The row's retirement is armed in the shared installer state IMMEDIATELY before the
            # rename, mirroring `transactional_delete`: an interruption from here to the commit
            # below is resolved by `recover_pending` from the live bytes.
            try:
                bundle.arm_pending(
                    retirement.installer_config,
                    retirement.state,
                    "uninstall",
                    row["destination"],
                    retirement.record,
                    None,
                )
            except Exception as exc:  # noqa: BLE001 - nothing moved; the entry is preserved by name
                raise Refusal(
                    f"the ownership row of {dar_escape(row['entry_name'])} could not be armed for "
                    f"retirement, so the entry was preserved untouched: {exc!r}"
                ) from exc
            retirement.armed = True
        bundle.rename_absent(destination, artifact.payload)
        moved = True
        outcome["moved"] = True
        journal.write("quarantined")
        checkpoint(config, "after-quarantined", dict(journal.document["pending"]))
        if retirement is not None and retirement.armed:
            # The destination has left the plane, so the row describes nothing there any more: the
            # commit lands exactly where `transactional_delete` commits its own.  A failure here
            # falls to the unknown-effect classification below with the slot still armed, and
            # recovery commits it from the absent destination.
            bundle.commit_pending(retirement.installer_config, retirement.state)
            retirement.armed = False
        if safe_digest(bundle, artifact.payload) != expected:
            raise UnknownEffect(
                f"the quarantined copy of {dar_escape(row['entry_name'])} no longer matches its proved "
                f"digest, so the effect of this removal is unknown: {str(artifact.container)!r}"
            )
        bundle.remove_path(artifact.payload)
        artifact.container.rmdir()
        bundle.fsync_directory(artifact.container.parent)
    except Refusal:
        if moved:
            raise UnknownEffect(
                f"the entry {dar_escape(row['entry_name'])} was already quarantined when the removal "
                f"stopped, so its effect is unknown: {str(artifact.container)!r}"
            ) from None
        cleanup_unused_container(bundle, artifact)
        roll_back_row_retirement(bundle, journal, retirement)
        journal.document["pending"] = None
        journal.write("planned", before_any_effect=nothing_moved_yet)
        raise
    except UnknownEffect:
        raise
    except BaseException as exc:  # noqa: BLE001 - a Ctrl-C between the rename and the delete is the
        # exact case that must not report an absence of effect, and KeyboardInterrupt is not an
        # `Exception`, so catching only that class would let the honest classification be skipped.
        if moved:
            raise UnknownEffect(
                f"the removal of {dar_escape(row['entry_name'])} failed after it was quarantined, so "
                f"its effect is unknown: {str(artifact.container)!r} ({exc!r})"
            ) from exc
        cleanup_unused_container(bundle, artifact)
        roll_back_row_retirement(bundle, journal, retirement)
        journal.document["pending"] = None
        journal.write("planned", before_any_effect=nothing_moved_yet)
        if not isinstance(exc, Exception):
            # An interrupt is a decision to stop, not one entry's defect: it stops the whole walk.
            raise
        raise Refusal(
            f"the entry {dar_escape(row['entry_name'])} could not be quarantined, so it was preserved "
            f"untouched: {exc!r}"
        ) from exc

    journal.document["pending"] = None
    journal.document["completed"].append(
        {"destination": str(destination), "entry_name": row["entry_name"], "expected_sha256": expected}
    )
    outcome["settled"] = True
    try:
        journal.write("settled")
        checkpoint(config, "after-settled", {"entry_name": row["entry_name"]})
    except UnknownEffect:
        raise
    except BaseException as exc:  # noqa: BLE001 - the entry is gone; an unrecorded removal is unknown
        raise UnknownEffect(
            f"the entry {dar_escape(row['entry_name'])} was removed but its settlement could not be "
            f"recorded, so the state of this retirement is unknown: {exc!r}"
        ) from exc


def cleanup_unused_container(bundle: ModuleType, artifact: Any) -> None:
    """Remove an empty quarantine container this run created and never used."""
    try:
        if bundle.path_present(artifact.payload):
            return
        artifact.container.rmdir()
        bundle.fsync_directory(artifact.container.parent)
    except OSError:
        return


#: Bound at run time to the receipt family's own escaper, so a rendered line can never carry a
#: control character out of an artifact or a filesystem name.
_ESCAPE: Callable[[str], str] | None = None


def dar_escape(value: Any) -> str:
    text = value if isinstance(value, str) else repr(value)
    if _ESCAPE is None:
        return "".join(character if 0x20 <= ord(character) != 0x7F else "?" for character in text)
    return _ESCAPE(text)


# ---- the terminal receipt ------------------------------------------------------------------------


def terminal_receipt_id(retired_id: str) -> str:
    candidate = f"uninstall-{retired_id}"
    if not _TOKEN.match(candidate):
        raise Refusal(
            f"the retired receipt id {dar_escape(retired_id)!r} does not compose a lowercase token, so "
            "this retirement cannot be named"
        )
    return candidate


def resolved_instant(config: Config) -> str:
    """The instant this receipt states, injectable and never inferred from an artifact.

    This project's WSL2 host steps ``CLOCK_REALTIME`` backwards, so the value is a STATEMENT of when
    the operation ran and never evidence of ordering.  A caller may supply it exactly.
    """
    if config.stated_at is not None:
        if not _INSTANT.match(config.stated_at):
            raise Refusal(
                f"the supplied stated_at {dar_escape(config.stated_at)!r} is not a YYYY-MM-DDTHH:MM:SSZ "
                "instant"
            )
        return config.stated_at
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def retirement_inventory(
    dar: ModuleType, observations: list[dict[str, Any]], removed: set[str]
) -> list[dict[str, Any]]:
    """The retirement's own inventory rows, built ABOVE any literal that reports them.

    A dict literal that read ``entries`` before the loop that fills it would seal a receipt whose
    inventory is empty and whose own checks would then pass, because the check reads the list that
    lost the records.

    ``mode`` records what was PUBLISHED at each destination when this run can name it -- the ledger
    row's own mode on the ledger-directed path -- and null where it cannot.  A removal publishes
    nothing, so a null there is not-supplied rather than supplied-but-missing.
    """
    entries: list[dict[str, Any]] = []
    for item in observations:
        name = item["entry_name"]
        mode = item.get("mode")
        if name in removed:
            # ``removed`` leaves nothing to digest, and the family refuses a digest beside it.
            entries.append(
                {
                    "content_sha256": None,
                    "disposition": "removed",
                    "entry_name": name,
                    "mode": mode,
                    "prestate": "owned",
                }
            )
            continue
        prestate = item.get("prestate") or CLASS_PRESTATE[item["class"]]
        content = item["current_sha256"] if dar.content_bearing(prestate, "preserved") else None
        entries.append(
            {
                "content_sha256": content,
                "disposition": "preserved",
                "entry_name": name,
                "mode": mode,
                "prestate": prestate,
            }
        )
    entries.sort(key=lambda row: str(row["entry_name"]))
    return entries


def build_receipt(
    dar: ModuleType,
    config: Config,
    payload: dict[str, Any],
    retired_id: str | None,
    observations: list[dict[str, Any]],
    removed: set[str],
    plan_sha256: str,
    journal_sha256: str | None,
    effect_state: str,
    terminal_phase: str,
    *,
    prestate_evidence: str,
    receipt_id: str,
) -> dict[str, Any]:
    """Assemble the one unsealed terminal observation, for EITHER prestate evidence.

    ``payload`` carries the facts about what was retired -- candidate identity, archive digest,
    resolved version and its source, and an optional checkout object.  On the receipt-directed path
    those are the retired receipt's own; on the ledger-directed path they are what this run could
    observe about the distribution it is retiring from, because no activation receipt exists to
    inherit them from.

    ``prestate_evidence`` selects the ancestor shape, and the two are checked against each other by
    the receipt family: receipt evidence NAMES the receipt it retires, and ledger evidence names none.
    """
    entries = retirement_inventory(dar, observations, removed)
    observation = {
        "archive_sha256": payload["archive_sha256"],
        "candidate_id": payload["candidate_id"],
        "effect_state": effect_state,
        "entries": entries,
        "journal_sha256": journal_sha256,
        "operation": "uninstall",
        "plan_sha256": plan_sha256,
        "prestate_evidence": prestate_evidence,
        "public_channel": None,
        "record_sha256": dar.UNSEALED,
        "release_claim": "none",
        # An uninstall requests no version. Null is the statement "no version was requested", which is
        # not the "unknown" a null digest means.
        "requested_version": None,
        "resolved_version": payload["resolved_version"],
        "schema_version": dar.BODY_SCHEMA,
        "scope": config.scope_object(),
        "terminal_phase": terminal_phase,
        "unknowns": [],
        "version_source": payload["version_source"],
    }
    if payload.get("checkout") is not None:
        observation["checkout"] = payload["checkout"]
    ancestors: list[dict[str, Any]] = []
    if retired_id is not None:
        ancestors.append(
            {
                "expected_kind": dar.RECEIPT_KIND,
                "receipt_id": retired_id,
                "relation": "derived-from",
            }
        )
    return {
        "ancestors": ancestors,
        "body": observation,
        "content_digest": dar.UNSEALED,
        "emitting_plane": config.emitting_plane,
        "receipt_id": receipt_id,
        "receipt_kind": dar.RECEIPT_KIND,
        "schema": dar.ENVELOPE_SCHEMA,
        "stated_at": resolved_instant(config),
    }


def retired_payload(body: dict[str, Any]) -> dict[str, Any]:
    """The payload facts a receipt-directed retirement inherits from the receipt it retires."""
    payload = {
        "archive_sha256": body["archive_sha256"],
        "candidate_id": body["candidate_id"],
        "resolved_version": body["resolved_version"],
        "version_source": body["version_source"],
        "checkout": body.get("checkout"),
    }
    return payload


def seal_receipt(dar: ModuleType, unsealed: dict[str, Any]) -> dict[str, Any]:
    result = dar.derive("seal", unsealed, "this retirement's observation")
    if result["verdict"] != dar.VERDICT_SEALED or not isinstance(result["receipt"], dict):
        reasons = "; ".join(dar.escape_display(reason) for reason in result["reasons"][:4])
        raise UnknownEffect(
            f"this retirement's terminal receipt could not be sealed, so the operation ends without "
            f"the record it owes: {reasons}"
        )
    return result["receipt"]


def write_terminal_receipt(bundle: ModuleType, dar: ModuleType, path: Path, receipt: dict[str, Any]) -> None:
    """Write the terminal receipt create-only and durably. An existing path is never replaced."""
    raw = dar.canonical_bytes(receipt)
    bundle.durable_mkdir(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, raw)
        bundle.flush_descriptor(descriptor, full=True)
    finally:
        os.close(descriptor)
    bundle.fsync_directory(path.parent)


# ---- the report ----------------------------------------------------------------------------------


def render_report(
    state: str,
    retired_label: str,
    facts: dict[str, Any],
    observations: list[dict[str, Any]],
    removed: set[str],
    outstanding: set[str],
    receipt_path: Path | None,
    journal_path: Path,
    effect_state: str,
    terminal_phase: str,
    attention: list[str],
) -> list[str]:
    """One offline report: removed, preserved, attention. Every artifact-derived value is escaped.

    ``facts`` is what this run can SAY about the plane it retired -- host, scope, resolved version, the
    unknowns it inherited, and the announcement a legacy-unreceipted retirement owes.  It is passed
    explicitly rather than read out of a retired receipt body, because the ledger-directed path has no
    such body: its prestate evidence is the ownership rows themselves.
    """
    lines = [f"ccodex sdlc uninstall: {state}"]
    for announcement in facts.get("announcements", []):
        lines.append(str(announcement))
    lines.append(
        f"retired activation: {dar_escape(retired_label)} (host {dar_escape(facts['host'])},"
        f" scope {dar_escape(facts['scope'])}, resolved {dar_escape(facts['resolved_version'])})"
    )
    for item in sorted(observations, key=lambda row: str(row["entry_name"])):
        name = dar_escape(item["entry_name"])
        if item["entry_name"] in outstanding:
            lines.append(
                f"removed with an outstanding quarantine: {name} (the destination left the plane and "
                "the journal names the container that still holds it)"
            )
        elif item["entry_name"] in removed:
            lines.append(f"removed: {name}")
        elif item["class"] == "absent":
            lines.append(f"absent: {name} ({CLASS_REASON['absent']})")
        else:
            reason = {**CLASS_REASON, **LEDGER_CLASS_REASON}.get(
                item["class"], "this class carries no recorded reason"
            )
            lines.append(f"preserved: {name} ({item['class']}: {reason})")
    for note in attention:
        lines.append(f"attention: {note}")
    for record in facts.get("unknowns", []):
        if isinstance(record, dict):
            # `detail` is free text observed in the field, so it reaches this line ESCAPED: a bare
            # newline would forge a second line of this command's own output, a carriage return would
            # overwrite the line already printed, and an escape sequence would rewrite the terminal.
            lines.append(
                f"inherited unknown: {dar_escape(record.get('observation'))}"
                f" about {dar_escape(record.get('subject'))}"
                f" ({dar_escape(record.get('detail'))})"
            )
    lines.append(f"journal: {journal_path}")
    lines.append(
        f"terminal receipt: {receipt_path if receipt_path is not None else 'not written'}"
        f" (operation uninstall, effect {effect_state}, terminal {terminal_phase})"
    )
    lines.append(
        "a completed retirement is evidence: it authorizes no push, publication, PR mutation, merge, "
        "deployment, or any other outward effect"
    )
    return lines


# ---- the run -------------------------------------------------------------------------------------


def classify_all(bundle: ModuleType, config: Config, body: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for entry in body["entries"]:
        if not isinstance(entry, dict):
            raise Refusal("the active receipt's inventory carries a row that is not an entry record")
        classification, destination, current = classify_entry(bundle, config, entry)
        observations.append(
            {
                "class": classification,
                "current_sha256": current,
                "destination": destination,
                "entry_name": entry.get("entry_name"),
            }
        )
    return observations


def run(bundle: ModuleType, dar: ModuleType, config: Config, ledger: dict[str, bool]) -> tuple[int, list[str]]:
    """Admit, plan, remove, then record. Returns the exit class and the report lines.

    ADMISSION IS AN ORDERED LADDER, and every rung is named.  The pointer for THIS (agent, scope, root)
    is preferred: its receipt's inventory is the candidate set, and the pointer filename is checked
    against that receipt's own scope before anything is classified.  When no pointer exists but this
    scope's ownership rows do, the run takes the LEDGER-DIRECTED path instead, announced as a
    legacy-unreceipted retirement and sealing a ``prestate_evidence: "ledger"`` receipt.  That second
    rung exists because "a receipted plane is the only plane" is factually false: ``bundle install``
    wrote ownership rows for years without sealing anything, and a repository root could be handed to
    it as a configured home, so those rows would otherwise be selected by NO verb -- the write-only
    record this program exists to stop leaving behind.  Neither rung guesses: with no pointer and no
    rows, the run refuses by name and points at ``install``.

    ``ledger['moved']`` is set the instant the first destination leaves the plane, so a caller that
    catches an interrupt escaping this function can classify it honestly instead of guessing.
    """
    if config.platform_system != SUPPORTED_PLATFORM:
        raise Refusal(
            f"ccodex sdlc uninstall is certified on {SUPPORTED_PLATFORM} only and refuses on "
            f"{dar_escape(config.platform_system)}; the candidate plane it retires is Linux x64 only"
        )

    # The legacy pointer is re-filed at its keyed path BEFORE the ladder below reads anything, so the
    # admission sees one plane with one pointer.  A refusal here removed nothing.
    announcement = migrate_legacy_pointer(bundle, config)
    announcements = [announcement] if announcement is not None else []

    if not bundle.path_present(config.active_receipt_path):
        return run_ledger_directed(bundle, dar, config, ledger, announcements)
    return run_receipt_directed(bundle, dar, config, ledger, announcements)


def run_receipt_directed(
    bundle: ModuleType,
    dar: ModuleType,
    config: Config,
    ledger: dict[str, bool],
    announcements: list[str],
) -> tuple[int, list[str]]:
    """The pointer's own receipt is the candidate set: today's proven path, sealing a v2 receipt."""
    receipt_document = read_receipt_document(dar, config.active_receipt_path, "distribution-activation receipt")
    validated = admit_active_receipt(dar, receipt_document, config.active_receipt_path)
    # THE FILENAME IS THE ADMISSION AUTHORITY, so its agreement with the receipt it points at is the
    # first thing checked: a pointer that does not describe this plane is refused as a pointer
    # disagreement, before the scope admission below asks whether the receipt matches THIS run.
    admit_pointer_agreement(dar, validated["body"], config.active_receipt_path)
    body = admit_retirable(dar, validated, config, config.active_receipt_path)
    retired_id = validated["receipt_id"]
    if not isinstance(retired_id, str) or not _TOKEN.match(retired_id):
        raise Refusal("the active receipt carries no lowercase-token receipt_id to retire")

    receipt_id = terminal_receipt_id(retired_id)
    receipt_path = config.receipts_dir / f"{receipt_id}.json"
    journal_path = config.journals_dir / f"{receipt_id}.json"
    if bundle.path_present(receipt_path):
        raise Refusal(
            f"this activation already carries the terminal receipt {str(receipt_path)!r}; a second "
            "retirement of one activation is refused rather than repeated, and an outstanding unknown "
            "effect is an operator decision"
        )

    observations = classify_all(bundle, config, body)
    plan = build_plan(config, body, observations)
    plan["retired_receipt_id"] = retired_id
    plan_sha256 = digest_bytes(dar.canonical_bytes(plan))

    journal = Journal(
        bundle,
        journal_path,
        {
            "attention": [],
            "completed": [],
            "host": config.host,
            "pending": None,
            "phase": "planned",
            "plan": plan,
            "plan_sha256": plan_sha256,
            "plane_root": str(config.plane_root),
            "receipt_id": receipt_id,
            "retired_receipt_id": retired_id,
            "schema_version": JOURNAL_SCHEMA,
        },
    )

    removed: set[str] = set()
    outstanding: set[str] = set()
    attention: list[str] = []
    unknown: str | None = None
    installer_config = bundle_config(bundle, config)
    with bundle.installer_lock(installer_config):
        # The ownership document is admitted only when this run will remove something: a walk that
        # removes nothing retires no rows, so a plane whose installer state is broken can still
        # have its all-preserved assessment sealed.
        ownership = admit_ownership_state(bundle, installer_config) if plan["remove"] else None
        journal.write("planned", before_any_effect=True)
        for row in plan["remove"]:
            outcome: dict[str, bool] = {"moved": False, "settled": False}
            retirement: RowRetirement | None = None
            if ownership is not None:
                record, preserved_row = matched_ownership_row(bundle, installer_config, ownership, row)
                if preserved_row is not None:
                    attention.append(preserved_row)
                    journal.document["attention"].append(
                        {"entry_name": row["entry_name"], "reason": preserved_row}
                    )
                if record is not None:
                    retirement = RowRetirement(installer_config, ownership, record, row["entry_name"])
            try:
                remove_one(
                    bundle,
                    config,
                    journal,
                    row,
                    outcome,
                    nothing_moved_yet=not ledger["moved"],
                    retirement=retirement,
                )
                if not outcome["settled"]:
                    # `remove_one` returns normally only after it records settlement (agentic-sdlc-
                    # 7c7d): a normal return that never flipped this flag is not a state this function
                    # currently produces, but trusting a bare return would let a future regression in
                    # `remove_one` report a removal as clean when its own bookkeeping never happened.
                    raise UnknownEffect(
                        f"the removal of {dar_escape(row['entry_name'])} returned without recording "
                        "settlement, so its effect is unknown"
                    )
                removed.add(row["entry_name"])
            except Refusal as exc:
                attention.append(str(exc))
                journal.document["attention"].append({"entry_name": row["entry_name"], "reason": str(exc)})
            except UnknownEffect as exc:
                unknown = str(exc)
                journal.document["attention"].append({"entry_name": row["entry_name"], "reason": str(exc)})
                if outcome["moved"]:
                    # The destination LEFT the plane. Reporting it as preserved would be a false
                    # statement about the plane; the doubt belongs in the effect state, which is
                    # `unknown`, and in the journal's outstanding quarantine.
                    removed.add(row["entry_name"])
                    outstanding.add(row["entry_name"])
                break
            finally:
                if outcome["moved"]:
                    ledger["moved"] = True
        journal.write(
            "unknown" if unknown is not None else "settled",
            before_any_effect=not ledger["moved"] and unknown is None,
        )

    journal_sha256 = journal.digest()
    if unknown is not None:
        effect_state, terminal_phase, exit_class, state = "unknown", "unknown", EXIT_UNKNOWN, "unknown"
        attention.append(unknown)
    elif len(removed) == len(observations):
        effect_state, terminal_phase, exit_class, state = "complete", "retired", EXIT_RETIRED, "retired"
    elif not removed:
        # No DESTINATION moved, and the receipt says so: `effect_state: none`. The exit class is still
        # 4, because this run is not a refusal. It ran the whole assessment and SEALED the terminal
        # receipt that consumes this activation's one retirement -- a second pass is refused by name
        # from here on -- while removing none of the entries the operator asked it to retire. Decision
        # 9's 3 is reserved for "clean refusal BEFORE effect", which every other exit-3 path here
        # satisfies by writing no receipt at all; reporting this outcome as 3 would tell a caller
        # nothing happened and it may retry, and the retry refuses. So the honest class is 4: the
        # effect on the request is admitted and partial, and the receipt names every preserved entry.
        effect_state, terminal_phase, exit_class, state = "none", "not-activated", EXIT_PARTIAL, "not-retired"
    else:
        # ``partial`` admits only ``unknown`` for an uninstall in the family's matrix.
        effect_state, terminal_phase, exit_class, state = "partial", "unknown", EXIT_PARTIAL, "partly-retired"

    # An inherited or fresh null digest is NAMED as an unknown by the family's producer, and the family
    # refuses `complete` beside any unknown -- correctly, because an effect whose own observations could
    # not all be made is not complete.  Consulting the RECORDED unknowns here rather than only the
    # removal count is what keeps this module from sealing a document its own family would refuse.
    if effect_state == "complete":
        for label, value in (("archive-digest", body["archive_sha256"]), ("journal-digest", journal_sha256)):
            if value is None:
                effect_state, terminal_phase, exit_class, state = "partial", "unknown", EXIT_PARTIAL, "partly-retired"
                attention.append(
                    f"every inventory entry was removed, but this retirement records {label} as unknown, "
                    "so its effect is partial rather than complete"
                )

    written: Path | None = None
    try:
        unsealed = build_receipt(
            dar,
            config,
            retired_payload(body),
            retired_id,
            observations,
            removed,
            plan_sha256,
            journal_sha256,
            effect_state,
            terminal_phase,
            # The retired receipt IS this retirement's prestate evidence, so the family requires
            # exactly one `derived-from` ancestor naming it -- which `build_receipt` writes from
            # `retired_id`.
            prestate_evidence="activation-receipt",
            receipt_id=receipt_id,
        )
        write_terminal_receipt(bundle, dar, receipt_path, seal_receipt(dar, unsealed))
        written = receipt_path
    except (UnknownEffect, Refusal, OSError) as exc:
        attention.append(f"the terminal receipt could not be recorded: {dar_escape(str(exc))}")
        if removed or unknown is not None:
            exit_class, state = EXIT_UNKNOWN, "unknown"

    return exit_class, render_report(
        state,
        retired_id,
        {
            "announcements": announcements,
            "host": config.host,
            "resolved_version": body["resolved_version"],
            "scope": scope_display(config),
            "unknowns": body.get("unknowns", []),
        },
        observations,
        removed,
        outstanding,
        written,
        journal_path,
        effect_state,
        terminal_phase,
        attention,
    )


def scope_display(config: Config) -> str:
    """One display string for this run's scope, DERIVED from the union and never stored beside it."""
    if config.scope_kind == SCOPE_PROJECT:
        return f"{SCOPE_PROJECT}:{config.boundary_home}"
    return SCOPE_USER


# ---- the ledger-directed path: a legacy-unreceipted plane, retired and then receipted --------------

#: The one line every ledger-directed run prints. It is an ANNOUNCEMENT, not a warning: the removal is
#: bounded by the same four controls the shipped ``bundle uninstall`` has always used, and the
#: difference an operator must know is which evidence authorised it.
LEDGER_ANNOUNCEMENT = "legacy-unreceipted uninstall (no activation receipt for {agent}/{scope})"

#: The classes a ledger row can take. Each maps onto the receipt inventory's own prestates through
#: ``CLASS_PRESTATE`` above, so the sealed evidence uses one vocabulary for both paths.
#: Which receipt prestate each ledger class maps onto. Separate from ``CLASS_PRESTATE`` because these
#: are a DIFFERENT classification -- the ownership row's own facts rather than a receipt inventory's --
#: and collapsing the two tables would let a class from one path be read through the other's rules.
LEDGER_CLASS_PRESTATE = {
    "owned-exact": "owned",
    "absent": "absent",
    "modified-content": "modified",
    "kept-adopted": "foreign",
    "unsafe-collection": "foreign",
}
LEDGER_CLASS_REASON = {
    "owned-exact": "the ownership row's recorded bytes are still the bytes on disk",
    "absent": "the ownership row records this destination and nothing is there",
    "modified-content": (
        "the bytes at this destination are no longer the bytes the ownership row records, so this "
        "lifecycle cannot prove it still owns them"
    ),
    "kept-adopted": (
        "the ownership row was adopted from a pre-existing entry and is marked unremovable, so the "
        "bytes are preserved exactly as the shipped uninstall preserves them"
    ),
    "unsafe-collection": (
        "the collection directory between the plane root and this destination is not one this "
        "lifecycle can prove it stays inside, so nothing here is touched"
    ),
}


def ledger_rows(bundle: ModuleType, config: Config, installer_config: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Select the ownership rows THIS scope's retirement may consider, and classify each one.

    THE FOUR CONTROLS ARE THE SHIPPED ONES, borrowed rather than restated: the row names this agent,
    its destination is the one THIS configured root would hold (``destination_is_configured``, which is
    what makes the scope's root the removal boundary), the live bytes still match the row
    (``entry_matches_record``, the whole ownership test), and an adopted unremovable row is kept. A row
    for another home or another agent is retained and left unselected, never reinterpreted.
    """
    rows: list[dict[str, Any]] = []
    for key in sorted(state["entries"]):
        record = state["entries"].get(key)
        if not isinstance(record, dict) or record.get("agent") != config.host:
            continue
        if not bundle.destination_is_configured(key, record, installer_config):
            continue
        destination = Path(key)
        name = ledger_entry_name(config, destination)
        if name is None:
            continue
        try:
            bundle.assert_safe_collection(bundle.record_entry(record, key), destination, installer_config)
        except Exception:  # noqa: BLE001 - an unprovable collection is preserved and named, never read
            rows.append(_ledger_row(name, destination, record, "unsafe-collection", None))
            continue
        if not bundle.path_present(destination):
            rows.append(_ledger_row(name, destination, record, "absent", None))
            continue
        if not bundle.entry_matches_record(destination, record):
            rows.append(_ledger_row(name, destination, record, "modified-content", safe_digest(bundle, destination)))
            continue
        if record.get("removable") is False:
            rows.append(_ledger_row(name, destination, record, "kept-adopted", safe_digest(bundle, destination)))
            continue
        rows.append(_ledger_row(name, destination, record, "owned-exact", safe_digest(bundle, destination)))
    return rows


def _ledger_row(
    name: str, destination: Path, record: dict[str, Any], classification: str, current: str | None
) -> dict[str, Any]:
    """One classified ledger row, in the same observation shape the receipt-directed path produces."""
    return {
        "class": classification,
        "current_sha256": current,
        "destination": destination,
        "entry_name": name,
        # The prestate this class maps onto, carried explicitly: this path's classification is its own,
        # and reading it through the receipt-directed table would apply another path's rules.
        "prestate": LEDGER_CLASS_PRESTATE[classification],
        # The row's OWN mode, which is the fact the receipt's per-row mode exists to carry: the shipped
        # `bundle install` publishes links on Unix, so a legacy plane's rows are honestly not copies.
        "mode": record.get("mode") if record.get("mode") in ("copy", "junction", "link") else None,
        "record": record,
    }


def ledger_entry_name(config: Config, destination: Path) -> str | None:
    """The receipt inventory's ``entry_name`` for one ledger destination, or None if it is not inside.

    A destination the plane root does not contain is not this scope's to name, and a name the receipt
    family would refuse is not one this run can record -- either way the row is left unselected rather
    than renamed into something the inventory will accept.
    """
    try:
        relative = destination.relative_to(config.plane_root).as_posix()
    except ValueError:
        return None
    if not relative or ".." in relative.split("/") or len(relative) > 256:
        return None
    if not all(character.isalnum() or character in "._/-" for character in relative):
        return None
    return relative


def observe_distribution(config: Config) -> tuple[str, dict[str, Any]]:
    """What this run can honestly say about the distribution a ledger retirement is running from.

    A ledger-directed retirement has NO acquisition receipt and no activation receipt to inherit a
    payload identity from, so the receipt it seals must answer those fields from what it can read here.
    Exactly one file answers the version -- ``.version-bump.json``'s own ``current``, the bump driver --
    and the checkout object answers the commit when git METADATA is readable, never by spawning git.

    ``dirty`` IS ALWAYS TRUE ON THIS PATH, and the reason is honesty rather than caution: the field
    means "this receipt does not assert the payload tree equals the commit it names", and nothing in
    this module compares a worktree against a commit, so it may not claim the tree was clean. A run
    that does prove it may record False.
    """
    root = config.scripts_dir.parent
    driver = root / VERSION_DRIVER_NAME
    try:
        raw = driver.read_bytes()[: _MAX_DRIVER_BYTES + 1]
    except OSError as exc:
        raise Refusal(
            f"the distribution root {str(root)!r} carries no readable {VERSION_DRIVER_NAME}, so a "
            f"retirement receipt could not name the version it retired: {exc}. Nothing was removed"
        ) from exc
    if len(raw) > _MAX_DRIVER_BYTES:
        raise Refusal(
            f"the version driver {str(driver)!r} is larger than {_MAX_DRIVER_BYTES} bytes, so it is "
            "not the document this plane reads. Nothing was removed"
        )
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Refusal(
            f"the version driver {str(driver)!r} is not one readable JSON object: {exc}. Nothing was "
            "removed"
        ) from exc
    current = document.get("current") if isinstance(document, dict) else None
    if not isinstance(current, str) or not current or len(current) > 64 or not _VERSION.match(current):
        raise Refusal(
            f"the version driver {str(driver)!r} states no admissible current version, so a retirement "
            "receipt could not name the version it retired. Nothing was removed"
        )
    return current, {"commit": observe_commit(root), "dirty": True}


def observe_commit(root: Path) -> str:
    """The distribution's own commit, read from git METADATA, or the explicit ``unknown``.

    No ``git`` process is spawned, ever: this is a lifecycle verb, and shelling out to resolve a commit
    would make an ambient executable part of what a receipt asserts. One level of loose-ref
    indirection is followed; a packed ref, an unreadable file, or any other shape answers ``unknown``,
    which is a statement the family admits rather than a plausible-looking value.
    """
    metadata = root / ".git"
    try:
        if metadata.is_file():
            line = metadata.read_bytes()[:_MAX_GIT_FILE_BYTES].decode("utf-8", "replace").strip()
            if not line.startswith("gitdir:"):
                return CHECKOUT_COMMIT_UNKNOWN
            target = Path(line.split(":", 1)[1].strip())
            metadata = target if target.is_absolute() else (root / target)
        if not metadata.is_dir():
            return CHECKOUT_COMMIT_UNKNOWN
        head = (metadata / "HEAD").read_bytes()[:_MAX_GIT_FILE_BYTES].decode("utf-8", "replace").strip()
        if _COMMIT.match(head):
            return head
        if not head.startswith("ref:"):
            return CHECKOUT_COMMIT_UNKNOWN
        reference = head.split(":", 1)[1].strip()
        if not reference or ".." in reference.split("/"):
            return CHECKOUT_COMMIT_UNKNOWN
        resolved = (metadata / reference).read_bytes()[:_MAX_GIT_FILE_BYTES].decode("utf-8", "replace").strip()
        return resolved if _COMMIT.match(resolved) else CHECKOUT_COMMIT_UNKNOWN
    except (OSError, ValueError):
        return CHECKOUT_COMMIT_UNKNOWN


def run_ledger_directed(
    bundle: ModuleType,
    dar: ModuleType,
    config: Config,
    ledger: dict[str, bool],
    announcements: list[str],
) -> tuple[int, list[str]]:
    """Retire a plane whose ownership rows exist and whose activation was never receipted.

    The candidate set is the ownership rows this scope's boundary selects, and the removal itself is
    the shipped ``transactional_delete`` -- not this module's copy-plane quarantine walk -- because a
    legacy plane's rows are honestly links on Unix and only the substrate's own primitive proves and
    removes all three publication modes. Every removal therefore retires its row in the same armed
    transition that moves the bytes, which is what keeps the ledger from outliving the plane.

    What this path does NOT do: it never adopts, repairs, or reinterprets a row, it removes nothing
    outside the selected root, and it seals its evidence as ``prestate_evidence: "ledger"`` with no
    ancestor -- because there is no receipt to derive from, and naming one would forge the very
    evidence this path exists to admit the absence of.
    """
    installer_config = bundle_config(bundle, config)
    # AN ABSENT OWNERSHIP DOCUMENT REFUSES BEFORE ANYTHING IS CREATED. Taking the lock would durably
    # create the state directory, and a run with no receipt and no rows must leave the state root
    # exactly as it found it -- the same "a refusal creates no directory" property the receipt-directed
    # path has. With no document there are no rows to select, so the check costs nothing and the
    # refusal is the honest one.
    if not bundle.path_present(installer_config.state_path):
        raise Refusal(
            f"ccodex sdlc uninstall found no activation receipt for {config.host}/{config.scope_kind}"
            f" at {str(config.active_receipt_path)!r} and no installer ownership document at"
            f" {str(installer_config.state_path)!r}; there is nothing to retire, and"
            " `ccodex sdlc install --host claude` is the front door for a first activation"
        )
    resolved_version, checkout = observe_distribution(config)
    announcement = LEDGER_ANNOUNCEMENT.format(agent=config.host, scope=config.scope_kind)

    removed: set[str] = set()
    outstanding: set[str] = set()
    attention: list[str] = []
    unknown: str | None = None

    with bundle.installer_lock(installer_config):
        state = admit_ownership_state(bundle, installer_config)
        rows = ledger_rows(bundle, config, installer_config, state)
        if not rows:
            raise Refusal(
                f"ccodex sdlc uninstall found no activation receipt for {config.host}/{config.scope_kind}"
                f" at {str(config.active_receipt_path)!r} and no ownership rows under"
                f" {str(config.plane_root)!r}; there is nothing to retire, and"
                " `ccodex sdlc install --host claude` is the front door for a first activation"
            )
        removable = [row for row in rows if row["class"] == "owned-exact"]
        plan = ledger_plan(config, rows, resolved_version)
        plan_sha256 = digest_bytes(dar.canonical_bytes(plan))
        receipt_id = ledger_receipt_id(config, plan_sha256)
        receipt_path = config.receipts_dir / f"{receipt_id}.json"
        journal_path = config.journals_dir / f"{receipt_id}.json"
        if bundle.path_present(receipt_path):
            raise Refusal(
                f"this legacy-unreceipted retirement already carries the terminal receipt"
                f" {str(receipt_path)!r}; a second retirement of one assessed plane is refused rather"
                " than repeated"
            )
        journal = Journal(
            bundle,
            journal_path,
            {
                "attention": [],
                "completed": [],
                "host": config.host,
                "pending": None,
                "phase": "planned",
                "plan": plan,
                "plan_sha256": plan_sha256,
                "plane_root": str(config.plane_root),
                "receipt_id": receipt_id,
                "retired_receipt_id": None,
                "schema_version": JOURNAL_SCHEMA,
            },
        )
        journal.write("planned", before_any_effect=True)
        for row in rows:
            if row["class"] == "absent":
                # The shipped uninstall drops an ownership row whose destination is already gone, and
                # leaving it would make the very next status report an owned-entry conflict.
                try:
                    bundle.persist_state(
                        installer_config, state, bundle.state_without_entry(state, str(row["destination"]))
                    )
                except Exception as exc:  # noqa: BLE001 - a row this run could not retire is named
                    attention.append(
                        f"the ownership row for {dar_escape(row['entry_name'])} names an absent "
                        f"destination and could not be retired: {exc!r}"
                    )
                continue
            if row["class"] != "owned-exact":
                # Named by the report's own preserved line, from the same reason table; appending it
                # here too would report one preservation twice.
                continue
            journal.document["pending"] = {
                "container": "",
                "destination": str(row["destination"]),
                "entry_name": row["entry_name"],
                "expected_sha256": row["current_sha256"],
                "payload": "",
            }
            journal.write("armed", before_any_effect=not ledger["moved"])
            try:
                bundle.transactional_delete(row["destination"], installer_config, state, row["record"])
            except BaseException as exc:  # noqa: BLE001 - the ONE fact that classifies is what moved
                gone = not bundle.path_present(row["destination"])
                journal.document["attention"].append(
                    {"entry_name": row["entry_name"], "reason": f"{exc!r}", "destination_absent": gone}
                )
                if gone:
                    # The destination LEFT the plane and this run cannot prove where it ended up. The
                    # installer's own armed slot is the recovery evidence; the doubt belongs in the
                    # effect state, never in a claim that the entry was preserved.
                    ledger["moved"] = True
                    removed.add(row["entry_name"])
                    outstanding.add(row["entry_name"])
                    unknown = (
                        f"the removal of {dar_escape(row['entry_name'])} left the plane before it "
                        f"settled, so its effect is unknown: {exc!r}"
                    )
                    journal.write("unknown")
                    break
                attention.append(
                    f"the entry {dar_escape(row['entry_name'])} could not be removed, so it was "
                    f"preserved untouched: {exc!r}"
                )
                journal.document["pending"] = None
                journal.write("planned", before_any_effect=not ledger["moved"])
                if not isinstance(exc, Exception):
                    raise
                continue
            ledger["moved"] = True
            removed.add(row["entry_name"])
            journal.document["pending"] = None
            journal.document["completed"].append(
                {
                    "destination": str(row["destination"]),
                    "entry_name": row["entry_name"],
                    "expected_sha256": row["current_sha256"],
                }
            )
            journal.write("settled")
        if unknown is None:
            journal.write("settled", before_any_effect=not ledger["moved"])

    journal_sha256 = journal.digest()
    inventory_rows = [row for row in rows if row["class"] != "absent"]
    if unknown is not None:
        effect_state, terminal_phase, exit_class, state_label = "unknown", "unknown", EXIT_UNKNOWN, "unknown"
        attention.append(unknown)
    elif removable and len(removed) == len(removable) and len(removed) == len(inventory_rows):
        effect_state, terminal_phase, exit_class, state_label = "complete", "retired", EXIT_RETIRED, "retired"
    elif not removed:
        effect_state, terminal_phase, exit_class, state_label = "none", "not-activated", EXIT_PARTIAL, "not-retired"
    else:
        effect_state, terminal_phase, exit_class, state_label = "partial", "unknown", EXIT_PARTIAL, "partly-retired"
    if effect_state == "complete" and journal_sha256 is None:
        effect_state, terminal_phase, exit_class, state_label = "partial", "unknown", EXIT_PARTIAL, "partly-retired"
        attention.append(
            "every selected ownership row was retired, but this retirement records journal-digest as "
            "unknown, so its effect is partial rather than complete"
        )

    observations = [
        {
            "class": row["class"],
            "current_sha256": row["current_sha256"],
            "destination": row["destination"],
            "entry_name": row["entry_name"],
            "mode": row["mode"],
            # Carried through, not re-derived: this path's classes are its own, and looking them up
            # in the receipt-directed table would read one path's classification by another's rules.
            "prestate": row["prestate"],
        }
        for row in inventory_rows
    ]
    written: Path | None = None
    try:
        unsealed = build_receipt(
            dar,
            config,
            {
                # A ledger retirement drew from no archive, so the digest is null and NOT-SUPPLIED:
                # the family names no unknown for it beside a checkout object, which is what lets a
                # clean retirement still record `complete`.
                "archive_sha256": None,
                "candidate_id": dar.checkout_candidate_id(retirement_inventory(dar, observations, removed)),
                "checkout": checkout,
                "resolved_version": resolved_version,
                "version_source": VERSION_SOURCE_CHECKOUT,
            },
            None,
            observations,
            removed,
            plan_sha256,
            journal_sha256,
            effect_state,
            terminal_phase,
            prestate_evidence="ledger",
            receipt_id=receipt_id,
        )
        write_terminal_receipt(bundle, dar, receipt_path, seal_receipt(dar, unsealed))
        written = receipt_path
    except (UnknownEffect, Refusal, OSError) as exc:
        attention.append(f"the terminal receipt could not be recorded: {dar_escape(str(exc))}")
        if removed or unknown is not None:
            exit_class, state_label = EXIT_UNKNOWN, "unknown"

    return exit_class, render_report(
        state_label,
        "none (the ownership rows are this retirement's prestate evidence)",
        {
            "announcements": [*announcements, announcement],
            "host": config.host,
            "resolved_version": resolved_version,
            "scope": scope_display(config),
            "unknowns": [],
        },
        observations,
        removed,
        outstanding,
        written,
        journal_path,
        effect_state,
        terminal_phase,
        attention,
    )


def ledger_plan(config: Config, rows: list[dict[str, Any]], resolved_version: str) -> dict[str, Any]:
    """The ledger-directed run's pre-effect intent, in the same closed plan shape."""
    remove: list[dict[str, Any]] = []
    preserve: list[dict[str, Any]] = []
    for row in rows:
        if row["class"] == "owned-exact":
            remove.append(
                {
                    "destination": str(row["destination"]),
                    "entry_name": row["entry_name"],
                    "expected_sha256": row["current_sha256"],
                }
            )
        else:
            preserve.append({"entry_name": row["entry_name"], "reason_code": row["class"]})
    remove.sort(key=lambda item: (item["entry_name"], item["destination"]))
    preserve.sort(key=lambda item: (item["entry_name"], item["reason_code"]))
    return {
        "candidate_id": None,
        "host": config.host,
        "plane_root": str(config.plane_root),
        "preserve": preserve,
        "prestate_evidence": "ledger",
        "remove": remove,
        "resolved_version": resolved_version,
        "retired_receipt_id": None,
        "schema_version": PLAN_SCHEMA,
        "scope": config.scope_object(),
    }


def ledger_receipt_id(config: Config, plan_sha256: str) -> str:
    """One lowercase token naming this retirement, derived from the plan it is about.

    There is no retired receipt id to compose from, so the identity comes from the assessment's own
    digest: two different assessed planes name two different receipts, and re-running the SAME
    assessment is refused by the create-only receipt rather than repeated.
    """
    candidate = f"uninstall-ledger-{config.host}-{config.scope_kind}-{plan_sha256[:16]}"
    if not _TOKEN.match(candidate):
        raise Refusal(f"the derived receipt identity {dar_escape(candidate)!r} is not a lowercase token")
    return candidate


def bundle_config(bundle: ModuleType, config: Config) -> Any:
    """The installer Config this module borrows for TWO purposes: the shared lifecycle lock, and
    the ownership rows the activation wrote.

    Both this plane and ``lifecycle:install`` write into the same Claude collections and the same
    ownership document, so they must serialize on the same lock file and retire rows through the
    same pending slot rather than through two private spellings (agentic-sdlc-42ec).
    """
    # THE SCOPE'S ROOT IS THE BOUNDARY, and it is the installer configuration that enforces it:
    # `destination_is_configured` compares each ownership row's destination against the root this
    # configured home implies for the SELECTED agent, so a project-scope run selects exactly the rows
    # under that project and a user-scope run selects exactly the rows under that agent's own root.
    # The two slots are asymmetric because the installer's own model is: Claude's configured root is
    # the home whose `.claude` holds its collections, while Codex's configured root IS its agent root.
    # Whichever slot the selected plane does not use is filled with this host's OTHER default, so a run
    # bounded by one plane cannot resolve a row under a root it never selected.
    claude_root = config.boundary_home if config.plane.collection is not None else config.home
    codex_root = config.boundary_home if config.plane.collection is None else config.codex_home
    return bundle.Config(
        config.scripts_dir.parent,
        claude_root,
        codex_root,
        "auto",
        False,
        config.host,
        config.state_root,
    )


def main(argv: list[str]) -> int:
    """The dispatcher's entry point. Returns an admitted exit class 0-4 and never raises."""
    global _ESCAPE
    try:
        refuse_read_only_guard()
        scripts_dir = Path(__file__).resolve().parent
        # THE SELECTED PLANE IS READ FROM THE VECTOR THE DISPATCHER FORWARDED and replaces the
        # configuration's default, so there is exactly one statement of which plane this run retires.
        # This module owns no grammar: any other vector is a pre-effect refusal, not a usage error,
        # because the dispatcher already owns usage and a second opinion would report one defect twice.
        planes = load_sibling(scripts_dir, "ccodex_sdlc_host_planes")
        if not (len(argv) == 2 and argv[0] == HOST_FLAG and argv[1] in planes.HOST_PLANES):
            raise Refusal(
                f"ccodex sdlc uninstall admits exactly [{HOST_FLAG!r}, "
                f"<{'|'.join(planes.AGENTS)}>]; this module received {argv!r}"
            )
        dar = load_sibling(scripts_dir, "distribution_activation_receipt")
        bundle = load_sibling(scripts_dir, "install_skill_bundle")
        _ESCAPE = dar.escape_display
        config = dataclasses.replace(default_config(bundle), host=argv[1])
    except Refusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - nothing has been touched yet, so this is a clean refusal
        print(f"error: ccodex sdlc uninstall refused before any effect: {exc!r}", file=sys.stderr)
        return EXIT_REFUSED
    return execute(bundle, dar, config)


def execute(bundle: ModuleType, dar: ModuleType, config: Config) -> int:
    """Run one retirement with the adapters and configuration already resolved.

    Every escape route is classified by ONE fact -- did anything leave the plane -- rather than by the
    exception's type, because a ``KeyboardInterrupt`` before the first rename and one after it are
    different outcomes that the same class would otherwise report identically.
    """
    global _ESCAPE
    _ESCAPE = dar.escape_display
    ledger: dict[str, bool] = {"moved": False}
    try:
        exit_class, lines = run(bundle, dar, config, ledger)
    except Refusal as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_UNKNOWN if ledger["moved"] else EXIT_REFUSED
    except UnknownEffect as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_UNKNOWN
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - includes the interrupt this walk must survive honestly
        print(
            f"error: ccodex sdlc uninstall stopped and "
            f"{'cannot prove what it moved' if ledger['moved'] else 'moved nothing'}: {exc!r}",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN if ledger["moved"] else EXIT_REFUSED
    sys.stdout.write("\n".join(lines) + "\n")
    return exit_class


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
