#!/usr/bin/env python3
"""``ccodex sdlc uninstall``: receipt-directed retirement of one distribution activation.

WHAT THIS MODULE IS
-------------------
``scripts/ccodex_sdlc.py`` owns the closed grammar of the three mutating lifecycle verbs.  It loads
this file by absolute non-symlink path and enters ``main([])``; the integer this returns is the exit
class, and a raise after import reads as exit 4 there because the module was already entered.  So
every refusal here is a NAMED return, never an exception escaping to the caller.

THE ONE SOURCE OF TRUTH
-----------------------
The ACTIVE ``distribution-activation@1`` receipt is the only statement of what this plane owns.  It
is validated through the sibling-loaded ``distribution_activation_receipt.py`` before a single path
is stat'ed, and its entry inventory is the ONLY candidate set for removal.  There is no wildcard, no
``--all``, no purge, and no directory listing: a file this plane never recorded is not a candidate,
and an absent or unsealed receipt is a named refusal rather than a guess reconstructed from
directory contents.

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
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import re
import stat
import sys
import time
from dataclasses import dataclass
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

#: The host plane this verb retires.  Closed and single-valued, matching the dispatcher's own
#: ``LIFECYCLE_HOSTS``: a wildcard host binds nothing.
HOST = "claude"
#: Claude's configured root is the selected home plus ``.claude``.
HOST_COLLECTION = ".claude"

SUPPORTED_PLATFORM = "Linux"

#: Every character class is written out.  ``\\d`` and ``\\w`` admit Unicode, so an identity spelled
#: with the Arabic-Indic ``٩`` would read as the same token while comparing unequal to it.
_TOKEN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
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
    host: str = HOST
    platform_system: str = SUPPORTED_PLATFORM
    stated_at: str | None = None
    emitting_plane: str = "ccodex-sdlc-uninstall"
    checkpoint: Callable[[str, dict[str, Any]], None] | None = None

    @property
    def plane_root(self) -> Path:
        return self.home / HOST_COLLECTION

    @property
    def active_receipt_path(self) -> Path:
        return self.activation_root / "active-receipt.json"

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
    return Config(
        scripts_dir=Path(__file__).resolve().parent,
        home=absolute(Path.home()),
        state_root=state_root,
        activation_root=state_root / "agentic-sdlc" / "activation",
        platform_system=platform.system(),
    )


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
    if body["host"] != config.host:
        raise Refusal(
            f"the active receipt {str(path)!r} records host {dar.escape_display(str(body['host']))!r}, "
            f"not {config.host!r}; a receipt names the one host plane it observed"
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
        "activation_scope": body["activation_scope"],
        "candidate_id": body["candidate_id"],
        "host": body["host"],
        "plane_root": str(config.plane_root),
        "preserve": preserve,
        "remove": remove,
        "resolved_version": body["resolved_version"],
        "retired_receipt_id": None,
        "schema_version": PLAN_SCHEMA,
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


def build_receipt(
    dar: ModuleType,
    config: Config,
    body: dict[str, Any],
    retired_id: str,
    observations: list[dict[str, Any]],
    removed: set[str],
    plan_sha256: str,
    journal_sha256: str | None,
    effect_state: str,
    terminal_phase: str,
) -> dict[str, Any]:
    """Assemble the one unsealed terminal observation. Every list is built ABOVE the literal.

    A dict literal that read ``entries`` before the loop that fills it would seal a receipt whose
    inventory is empty and whose own checks would then pass, because the check reads the list that
    lost the records.
    """
    entries: list[dict[str, Any]] = []
    for item in observations:
        name = item["entry_name"]
        if name in removed:
            # ``removed`` leaves nothing to digest, and the family refuses a digest beside it.
            entries.append(
                {
                    "content_sha256": None,
                    "disposition": "removed",
                    "entry_name": name,
                    "prestate": "owned",
                }
            )
            continue
        prestate = CLASS_PRESTATE[item["class"]]
        content = item["current_sha256"] if dar.content_bearing(prestate, "preserved") else None
        entries.append(
            {
                "content_sha256": content,
                "disposition": "preserved",
                "entry_name": name,
                "prestate": prestate,
            }
        )
    entries.sort(key=lambda row: str(row["entry_name"]))
    observation = {
        "activation_scope": body["activation_scope"],
        "archive_sha256": body["archive_sha256"],
        "candidate_id": body["candidate_id"],
        "effect_state": effect_state,
        "entries": entries,
        "host": body["host"],
        "journal_sha256": journal_sha256,
        "operation": "uninstall",
        "plan_sha256": plan_sha256,
        "public_channel": None,
        "record_sha256": dar.UNSEALED,
        "release_claim": "none",
        # An uninstall requests no version. Null is the statement "no version was requested", which is
        # not the "unknown" a null digest means.
        "requested_version": None,
        "resolved_version": body["resolved_version"],
        "schema_version": dar.BODY_SCHEMA,
        "terminal_phase": terminal_phase,
        "unknowns": [],
        "version_source": body["version_source"],
    }
    return {
        "ancestors": [
            {
                "expected_kind": dar.RECEIPT_KIND,
                "receipt_id": retired_id,
                "relation": "derived-from",
            }
        ],
        "body": observation,
        "content_digest": dar.UNSEALED,
        "emitting_plane": config.emitting_plane,
        "receipt_id": terminal_receipt_id(retired_id),
        "receipt_kind": dar.RECEIPT_KIND,
        "schema": dar.ENVELOPE_SCHEMA,
        "stated_at": resolved_instant(config),
    }


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
    retired_id: str,
    body: dict[str, Any],
    observations: list[dict[str, Any]],
    removed: set[str],
    outstanding: set[str],
    receipt_path: Path | None,
    journal_path: Path,
    effect_state: str,
    terminal_phase: str,
    attention: list[str],
) -> list[str]:
    """One offline report: removed, preserved, attention. Every artifact-derived value is escaped."""
    lines = [
        f"ccodex sdlc uninstall: {state}",
        f"retired activation: {dar_escape(retired_id)} (host {dar_escape(body['host'])},"
        f" scope {dar_escape(body['activation_scope'])}, resolved {dar_escape(body['resolved_version'])})",
    ]
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
            lines.append(f"preserved: {name} ({item['class']}: {CLASS_REASON[item['class']]})")
    for note in attention:
        lines.append(f"attention: {note}")
    for record in body.get("unknowns", []):
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

    ``ledger['moved']`` is set the instant the first destination leaves the plane, so a caller that
    catches an interrupt escaping this function can classify it honestly instead of guessing.
    """
    if config.platform_system != SUPPORTED_PLATFORM:
        raise Refusal(
            f"ccodex sdlc uninstall is certified on {SUPPORTED_PLATFORM} only and refuses on "
            f"{dar_escape(config.platform_system)}; the candidate plane it retires is Linux x64 only"
        )

    receipt_document = read_receipt_document(dar, config.active_receipt_path, "distribution-activation receipt")
    validated = admit_active_receipt(dar, receipt_document, config.active_receipt_path)
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
            body,
            retired_id,
            observations,
            removed,
            plan_sha256,
            journal_sha256,
            effect_state,
            terminal_phase,
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
        body,
        observations,
        removed,
        outstanding,
        written,
        journal_path,
        effect_state,
        terminal_phase,
        attention,
    )


def bundle_config(bundle: ModuleType, config: Config) -> Any:
    """The installer Config this module borrows for TWO purposes: the shared lifecycle lock, and
    the ownership rows the activation wrote.

    Both this plane and ``bundle:install`` write into the same Claude collections and the same
    ownership document, so they must serialize on the same lock file and retire rows through the
    same pending slot rather than through two private spellings (agentic-sdlc-42ec).
    """
    return bundle.Config(
        config.scripts_dir.parent,
        config.home,
        config.home / ".codex",
        "auto",
        False,
        config.host,
        config.state_root,
    )


def main(argv: list[str]) -> int:
    """The dispatcher's entry point. Returns an admitted exit class 0-4 and never raises."""
    global _ESCAPE
    try:
        if argv:
            raise Refusal(f"ccodex sdlc uninstall accepts no arguments: {argv[0]!r}")
        refuse_read_only_guard()
        scripts_dir = Path(__file__).resolve().parent
        dar = load_sibling(scripts_dir, "distribution_activation_receipt")
        bundle = load_sibling(scripts_dir, "install_skill_bundle")
        _ESCAPE = dar.escape_display
        config = default_config(bundle)
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
