#!/usr/bin/env python3
"""``ccodex sdlc update``: refresh ONE activated distribution to ONE different acquired candidate.

WHAT LOADS THIS FILE, AND WHAT IT MAY RETURN.  ``scripts/ccodex_sdlc.py`` owns the closed grammar of
the three mutating lifecycle verbs.  It loads this file by absolute non-symlink path and calls
``main([])``; the integer returned is the exit class, and a raise that escapes reads as exit 4 there
because the module was already entered.  So every refusal here is a NAMED return, never an exception
escaping to the caller, and ``SystemExit`` is never raised for a verdict.

  * ``main`` returns an ``int`` in the exit class 0-4 and NEVER a ``bool``: ``dispatch_lifecycle``
    rejects ``bool`` explicitly, because ``True`` would otherwise read as exit 1.
  * Exit 0 means the refresh completed and the new receipt is sealed AND active.  Exit 3 is a clean
    refusal before any effect.  Exit 4 means an effect was admitted and its completion or its
    evidence cannot be claimed.  There is no partial-success class: a blocked entry is decided
    BEFORE anything moves, so this verb either refreshes the whole verified-unchanged footprint or
    refuses it.

THE TWO ADMISSIONS, BOTH REQUIRED, BOTH BEFORE ANY EFFECT.

  1. THE ACTIVE DISTRIBUTION-ACTIVATION RECEIPT.  ``activation/active-receipt.json`` is the only
     statement of what this plane owns.  It is validated through the sibling-loaded
     ``distribution_activation_receipt`` producer, and only a receipt that describes a LIVE
     activation of THIS host plane is updatable.  No active receipt is a named refusal: there is
     nothing to update over, and ``ccodex sdlc install --host claude`` is the front door.
  2. ONE EXACTLY ACQUIRED CANDIDATE PAYLOAD WHOSE IDENTITY DIFFERS.  Same admission posture as
     ``install``, re-expressed rather than imported: a sealed
     ``release-candidate-acquisition-receipt/v1`` under the acquisition layout, terminal phase
     ``installed-unselected``, ``selection`` and ``activation`` both ``absent`` INSIDE the seal, and
     the candidate root at the exact path that receipt records.  The acquisition receipt whose
     ``archive_sha256`` is the one the active receipt already activated is the ACTIVE payload's
     record, so it is excluded from selection and never re-activated; exactly one other admissible
     receipt must remain, and an ambiguous plane is refused rather than resolved.  A selection whose
     candidate identity equals the active receipt's is refused BY NAME -- there is nothing to
     update, and a re-activation of the same identity is never silent.

THE REFRESH FOOTPRINT IS CLASSIFIED, AND A BLOCKED ENTRY STOPS THE WHOLE RUN BEFORE IT STARTS.
For every entry the new payload would write, the current state is classified against the ACTIVE
receipt's own inventory.  An entry whose digest differs from the inventory's (``modified``) or which
is present but not in the inventory at all (``foreign``) is preserved, NAMED, and BLOCKS the refresh
as a pre-effect exit-3 refusal: modified or foreign entries are preserved and block refresh, so
there is no partial update past a blocked entry.  Only verified-unchanged owned entries are
changed, and a new-in-payload entry goes into an absent slot.

WHAT HAPPENS TO AN ENTRY THE NEW PAYLOAD NO LONGER CARRIES, AND WHY THIS IS NOT A REMOVAL.
It is PRESERVED and NAMED.  The receipt family's own matrix is exact:
``OPERATION_DISPOSITIONS['update']`` admits ``installed``, ``preserved``, and ``refreshed`` and NOT
``removed``, so an update receipt cannot record a removal at all.  Removing the entry and recording
it as ``preserved`` would be a false statement about the plane, and removing it while recording
nothing would drop it from the only inventory that names this plane.  Removal is
``ccodex sdlc uninstall``'s own verb, under its own receipt, and this module names the dropped entry
in its report, its journal, and its receipt inventory instead of quietly deleting it.

THE PRIOR RECEIPT REMAINS AVAILABLE UNTIL THE NEW ACTIVATION COMPLETES DURABLY.  In order: the
prior receipt is retained under its own id in the receipts directory (create-only, never
overwritten, and a different document already filed under that id is a named refusal), the new
receipt is sealed and written create-only and durably, and only THEN is the active pointer replaced
atomically.  A kill anywhere before that replace leaves the prior receipt as the active statement
plus a recoverable journal and an honest exit 4; a kill after it leaves the new receipt active and
durably filed.  Side-by-side identities never overwrite each other: both candidate roots stay where
their own acquisition recorded them, and both sealed acquisition receipts are READ and re-asserted
byte-identical after the whole run.

WHAT THIS MODULE DOES NOT DO.  No wildcard, no ``--all``, no purge, no presence-based overwrite or
delete, no adoption, no repository activation, no config trust, no OCX, no provider, no library, no
statusline, no Claude launch, and no gate-leaf wiring.  ``public_channel`` is null and
``release_claim`` is ``none`` in every document written here.  A completed update is EVIDENCE: it
authorizes no push, publication, PR mutation, merge, deployment, or any other outward effect.

REUSE, NOT REIMPLEMENTATION.  ``install_skill_bundle`` owns the transactional create/replace
protocol, the ownership records, the durability barriers, the state lock, and the digest primitives;
``distribution_activation_receipt`` owns the receipt body, its closed vocabularies, and its
cross-field matrices.  Both are loaded as exact physical siblings by absolute path, never through
ambient ``sys.path``, and their module constants are read at runtime instead of guessed.  No other
per-verb lifecycle module is imported: ``ccodex_sdlc_install`` and ``ccodex_sdlc_uninstall`` are
precedents that were RE-EXPRESSED here, because importing one ticket's module into another would
make either file's refusal the other's behaviour.

DEFECT CLASSES THIS FILE IS WRITTEN AGAINST, EACH ONE OBSERVED IN THIS PROJECT.

  * Character classes are written ``[0-9a-f]`` and never ``\\d``: ``\\d`` matches the Arabic-Indic
    ``٩``, so a digest or a version spelled in Unicode digits would read as equal and compare
    unequal.
  * A number that BECOMES non-finite while parsing (``1e400`` -> ``inf``) never reaches
    ``parse_constant``, so every parsed document is walked iteratively for non-finite floats.
  * Dict-literal evaluation order drops data: a comprehension inside a literal is evaluated after
    its sibling keys, so every list this module reports is built into a local FIRST.
  * Admission consults RECORDED UNKNOWNS, not only recorded facts: an observation nobody could make
    is not a fact and appears in no fact-only walk, so ``complete`` is derived from the unknowns as
    well as from the outcomes.
  * Control characters are escaped in every rendered line derived from an artifact or a filesystem
    name; the stored values are never mutated.
  * Supplied-but-missing is not not-supplied: every injected observation carries an explicit
    ``UNSUPPLIED`` sentinel, and a null digest recorded beside content that exists is NAMED as an
    unknown rather than left as a hole.

RESIDUALS, STATED EXACTLY.

  * Both seals are RE-DERIVATION.  They catch drift, a hand-edit, and a mismatched pair; they are
    not a boundary against a same-UID forger who rewrites a receipt and its payload together.
  * The digest re-proofs narrow a window; they are not a boundary against a same-UID racer mutating
    a destination between the proof and the rename.
  * The payload subset this refresh copies is verified against the new candidate manifest's own
    inventory rows.  The rest of the payload tree is not walked.
  * A validated receipt is a well-formed statement, not a true one: this module re-proves every
    digest on disk rather than trusting the inventory, but it cannot prove the plane's entries were
    ever what the receipt says they were.
  * ``stated_at`` is an OBSERVATION.  Nothing is admitted or refused by comparing instants, because
    this project's WSL2 host steps ``CLOCK_REALTIME`` backwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
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
from typing import Any, Callable

# ---- exit classes ---------------------------------------------------------------------------------

#: The refresh completed, the new receipt is sealed, and it is the plane's active statement.
EXIT_OK = 0
#: A clean refusal BEFORE any effect, named.
EXIT_REFUSED = 3
#: An effect was admitted and no absence of effect may be claimed.
EXIT_UNKNOWN = 4

HOST = "claude"
OPERATION = "update"
#: Claude's configured root is the selected home plus ``.claude``.
HOST_COLLECTION = ".claude"
#: The scope the shipped install receipt names for this plane. A receipt about another scope
#: describes a plane this module never observed, so it is refused rather than reinterpreted.
ACTIVATION_SCOPE = "claude-home"
ACTIVATION_MODE = "copy"
ENTRY_AGENT = "claude"
EMITTING_PLANE = "acquired-candidate"
#: The resolved version comes from the new payload's own manifest, never from a request.
VERSION_SOURCE = "archive-manifest"

#: The operations whose receipt describes a LIVE activation this verb can refresh. A receipt whose
#: own operation is ``uninstall`` records a retirement, and updating over it would refresh a plane
#: its own record says is gone.
UPDATABLE_OPERATIONS = ("install", "update")
#: The terminal phases of a live activation. ``not-activated`` moved nothing and ``unknown`` never
#: established its own effect, so neither is a plane whose entries can be proved unchanged.
UPDATABLE_PHASES = ("activated", "activated-partial")

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
#: That policy's ``constants`` for the same schema, plus its ``schema_version``. Verified INSIDE the
#: seal: an acquisition whose selection is not ``absent`` is a payload some other operation claimed.
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
ACQUISITION_RECEIPT_SEGMENTS = ("agentic-sdlc", "acquisition", "receipts")
ACQUISITION_CANDIDATE_SEGMENTS = ("agentic-sdlc", "acquisition", "candidates")
ACQUISITION_CANDIDATE_LEAF = "root"
ACTIVATION_SEGMENTS = ("agentic-sdlc", "activation")
ACTIVE_RECEIPT_NAME = "active-receipt.json"

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
RELEASE_CONTRACT_HOST = "claude-code"

PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-update-plan@1"
JOURNAL_SCHEMA = "agentic-sdlc/ccodex-sdlc-update-journal@1"

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

#: The one sentence this ticket's specification fixes for the blocked case, so the refusal a reader
#: greps for is the refusal the spec named.
BLOCK_SENTENCE = "Modified or foreign entries are preserved and block refresh"

#: The closed classification vocabulary for one entry the new payload would write. Exactly one
#: applies, each maps to one receipt prestate, and only the two admitted classes are ever written.
CLASS_ABSENT = "absent-slot"
CLASS_OWNED_EXACT = "owned-verified-unchanged"
CLASS_OWNED_CURRENT = "owned-already-this-payload"
CLASS_MODIFIED = "modified-content"
CLASS_FOREIGN = "foreign-unrecorded"
CLASS_FOREIGN_LINK = "foreign-symlink"
CLASS_FOREIGN_TYPE = "foreign-type"
CLASS_UNREADABLE = "foreign-unreadable"
CLASS_RETARGETED = "retargeted-parent"
CLASS_UNPROVABLE = "unprovable-inventory"
CLASS_NO_RECORD = "missing-ownership-record"
CLASS_RECORD_UNUSABLE = "ownership-record-unusable"
CLASS_AMBIGUOUS = "ambiguous-name"

#: The two classes a refresh may change. Everything else is preserved, NAMED, and blocks.
ADMITTED_CLASSES = (CLASS_ABSENT, CLASS_OWNED_EXACT, CLASS_OWNED_CURRENT)

CLASS_PRESTATE = {
    CLASS_ABSENT: PRESTATE_ABSENT,
    CLASS_OWNED_EXACT: PRESTATE_OWNED,
    CLASS_OWNED_CURRENT: PRESTATE_OWNED,
    CLASS_MODIFIED: PRESTATE_MODIFIED,
    CLASS_FOREIGN: PRESTATE_FOREIGN,
    CLASS_FOREIGN_LINK: PRESTATE_FOREIGN,
    CLASS_FOREIGN_TYPE: PRESTATE_FOREIGN,
    CLASS_UNREADABLE: PRESTATE_FOREIGN,
    CLASS_RETARGETED: PRESTATE_FOREIGN,
    CLASS_UNPROVABLE: PRESTATE_FOREIGN,
    CLASS_NO_RECORD: PRESTATE_FOREIGN,
    CLASS_RECORD_UNUSABLE: PRESTATE_FOREIGN,
    CLASS_AMBIGUOUS: PRESTATE_FOREIGN,
}

CLASS_REASON = {
    CLASS_ABSENT: (
        "nothing occupies the destination, so the new payload entry is copied into an absent slot"
    ),
    CLASS_OWNED_EXACT: (
        "the current content digest equals the digest the active receipt's inventory recorded, so"
        " this owned entry is verified unchanged and may be refreshed"
    ),
    CLASS_OWNED_CURRENT: (
        "the owned entry is already exactly this payload entry, so nothing is written to it"
    ),
    CLASS_MODIFIED: (
        "the current content digest differs from the digest the active receipt's inventory recorded,"
        " so this entry was modified outside this lifecycle"
    ),
    CLASS_FOREIGN: (
        "an entry stands at the destination that the active receipt's inventory does not record, so"
        " this lifecycle does not own it"
    ),
    CLASS_FOREIGN_LINK: (
        "a link stands where activated content belongs; this plane is copy-activated, and replacing a"
        " link whose target may lie outside the plane is not a refresh this receipt authorizes"
    ),
    CLASS_FOREIGN_TYPE: "the object at the destination is neither a file, a directory, nor a link",
    CLASS_UNREADABLE: (
        "the current content could not be digested, so unchanged ownership cannot be proved"
    ),
    CLASS_RETARGETED: (
        "a parent inside the plane is a link, so a write here could take effect outside the plane"
    ),
    CLASS_UNPROVABLE: (
        "the active receipt's inventory records no content digest for this entry, so there is nothing"
        " to prove unchanged ownership against"
    ),
    CLASS_NO_RECORD: (
        "the installer ownership state holds no record for this destination, so a transactional"
        " refresh could not prove what it replaces"
    ),
    CLASS_RECORD_UNUSABLE: (
        "the installer ownership record for this destination cannot authorize a refresh of it, so the"
        " entry is preserved exactly as it is"
    ),
    CLASS_AMBIGUOUS: "the recorded entry name does not resolve to one path inside the plane",
}

#: Every character class is written out. ``\\d`` and ``\\w`` admit Unicode, so an identity spelled in
#: Arabic-Indic digits would read as the same value while comparing unequal to it everywhere else.
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_OPERATION_ID = re.compile(r"op-[0-9a-f]{32}\Z")
_TOKEN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_VERSION = re.compile(r"[0-9A-Za-z]([0-9A-Za-z.+-]*[0-9A-Za-z])?\Z")
_UTC_INSTANT = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_ENTRY_NAME = re.compile(r"[A-Za-z0-9]([A-Za-z0-9._/-]*[A-Za-z0-9])?\Z")

_MAX_RECEIPT_BYTES = 1048576
_MAX_MANIFEST_BYTES = 8388608
_MAX_CONTRACT_BYTES = 1048576
#: One acquisition receipt is a few kilobytes. The bound means an unbounded directory cannot turn a
#: bounded selection into a scan, and an over-full plane is NAMED rather than partly read.
_MAX_ACQUISITION_RECEIPTS = 64
_MAX_DETAIL = 512
_INFINITY = float("inf")

_HOST_VERSION_COMMAND = ("claude", "--version")
_HOST_VERSION_TIMEOUT_SECONDS = 20


class Refusal(RuntimeError):
    """Declined BEFORE any effect could occur: exit class 3, always named."""


class UnknownEffect(RuntimeError):
    """An effect was admitted, so no absence of effect can be claimed: exit class 4."""


class _Unsupplied:
    """The third state of an injected observation: nobody supplied one at all.

    ``None`` is a VALUE here -- "I looked for the host version and could not see it" -- so a plain
    default of ``None`` would merge not-supplied with supplied-but-missing, and those two are
    different inputs with different named outcomes.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<unsupplied>"


UNSUPPLIED = _Unsupplied()

_ESCAPES = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def escape_display(value: str) -> str:
    """Escape every control character before an artifact-derived value reaches a rendered line.

    The same rule as the receipt producer's own ``escape_display``, pinned against it by the test
    module so a divergence is a failure rather than a silent second spelling.  DEL (0x7f) is included
    because a naive ``< 0x20`` test passes it.
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


def _absolute(path: Path) -> Path:
    """Absolute without resolving links, aliases, or 8.3 spellings: the installer's own rule."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def default_state_home() -> Path:
    """``XDG_STATE_HOME`` or its documented default, without creating anything."""
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


@dataclass(frozen=True)
class Config:
    """Every location and ambient observation this module depends on, in one injectable seam.

    The defaults are the ones the shipped scripts already use, so a test relocates all of them
    without this module inventing a second location convention and without touching the operator's
    real plane.
    """

    home: Path
    state_home: Path
    data_home: Path
    codex_home: Path
    #: ``None`` means "the installer's own default state root"; a path relocates the ownership state.
    installer_state_root: Path | None = None
    #: ``UNSUPPLIED`` observes the host itself; ``None`` is an observation that was made and failed.
    observed_host_version: str | None | _Unsupplied = UNSUPPLIED
    observed_system: str | _Unsupplied = UNSUPPLIED
    observed_machine: str | _Unsupplied = UNSUPPLIED
    observed_instant: str | None | _Unsupplied = UNSUPPLIED
    #: One test seam for interruption, called at each named transition. No production effect.
    checkpoint: Callable[[str], None] | None = None

    def __post_init__(self) -> None:
        for name in ("home", "state_home", "data_home", "codex_home"):
            object.__setattr__(self, name, _absolute(getattr(self, name)))
        if self.installer_state_root is not None:
            object.__setattr__(self, "installer_state_root", _absolute(self.installer_state_root))

    @property
    def plane_root(self) -> Path:
        return self.home / HOST_COLLECTION

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
        return self.activation_dir / ACTIVE_RECEIPT_NAME

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


def checkpoint(config: Config, point: str) -> None:
    """Call the injected interruption seam, if one was supplied. Never a production effect."""
    if config.checkpoint is not None:
        config.checkpoint(point)


# ---- sibling modules: exact physical files, never ambient sys.path --------------------------------


def load_sibling(stem: str) -> ModuleType:
    """Load one named sibling by absolute non-symlink path, the reader's own admission shape.

    The read-only guard is deliberately NOT installed here, because it exists to block the very
    primitives a lifecycle mutation needs; ``refuse_read_only_guard`` detects it instead.  No other
    per-verb lifecycle module is ever a sanctioned sibling: only the reused substrate is.
    """
    path = Path(__file__).with_name(f"{stem}.py")
    if path.is_symlink() or not path.is_file():
        raise Refusal(
            f"ccodex sdlc update requires the sibling module {show(str(path))}, which is absent or is"
            " a link"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_update_{stem}", path)
    if spec is None or spec.loader is None:
        raise Refusal(f"ccodex sdlc update cannot load the sibling module {show(str(path))}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an import failure here is still pre-effect
        raise Refusal(
            f"ccodex sdlc update cannot import the sibling module {show(str(path))}: {show(exc)}"
        ) from exc
    return module


def refuse_read_only_guard() -> None:
    """Refuse cleanly if this process already installed the reader's read-only guard.

    ``ccodex_sdlc_readonly.install`` patches ``builtins.open``, ``os``, ``shutil``, ``Path``, and
    ``fcntl`` process-globally, and ``block_lifecycle_mutators`` pins the very names this module
    reuses.  The shipped dispatcher hands off BEFORE it builds any read-only projection, so the guard
    is never installed on this path; if some other caller changes that, a lifecycle mutation must
    fail as a named refusal before any effect rather than as a traceback the dispatcher would have to
    classify as an unknown effect.
    """
    guard = sys.modules.get("_ccodex_sdlc_readonly_guard")
    if guard is not None and getattr(guard, "_INSTALLED", False):
        raise Refusal(
            "ccodex sdlc update refuses: this process already installed the read-only guard, whose"
            " stdlib mutation blocks would fail this operation partway through"
        )


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
    except FileNotFoundError as exc:
        raise Refusal(f"{subject} is absent at {show(str(path))}") from exc
    except OSError as exc:
        raise Refusal(f"{subject} is unavailable at {show(str(path))}: {show(exc)}") from exc
    if stat.S_ISLNK(item.st_mode):
        raise Refusal(
            f"{subject} at {show(str(path))} is a link; a lifecycle plane resolves a fixed path, and"
            " a redirection there is state nobody recorded"
        )
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
        value = json.loads(text, object_pairs_hook=_reject_duplicate, parse_constant=_reject_constant)
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


# ---- phase 0: platform and instant ----------------------------------------------------------------


def observe_platform(config: Config) -> tuple[str, str]:
    """Observe the operating system and architecture, or take the injected observation."""
    system = platform.system() if isinstance(config.observed_system, _Unsupplied) else config.observed_system
    machine = (
        platform.machine() if isinstance(config.observed_machine, _Unsupplied) else config.observed_machine
    )
    return str(system), str(machine)


def admit_platform(config: Config) -> tuple[str, str]:
    """Refuse an uncertified platform BY NAME rather than attempting a linux-x64 payload on it."""
    system, machine = observe_platform(config)
    if system != SUPPORTED_SYSTEM:
        raise Refusal(
            f"ccodex sdlc update refreshes a {CANDIDATE_PLATFORM} candidate and is certified only on"
            f" {SUPPORTED_SYSTEM}; the observed operating system is {show(system)}. Another platform"
            " is refused by name rather than attempted"
        )
    if machine.lower() not in SUPPORTED_MACHINES:
        raise Refusal(
            f"ccodex sdlc update refreshes a {CANDIDATE_PLATFORM} candidate; the observed"
            f" architecture is {show(machine)}, not one of {list(SUPPORTED_MACHINES)}"
        )
    return system, machine


def observe_instant(config: Config) -> str:
    """One UTC instant for ``stated_at``, observed and never compared.

    The receipt producer reads no clock at all and requires the caller to supply the instant, so it
    is observed HERE, checked against the envelope's own shape, and used only as a recorded fact.
    """
    if isinstance(config.observed_instant, _Unsupplied):
        observed: str | None = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    else:
        observed = config.observed_instant
    if observed is None:
        raise Refusal(
            "the supplied UTC instant observation is missing, so this update cannot state when it"
            " happened; the receipt envelope requires a YYYY-MM-DDTHH:MM:SSZ instant and this module"
            " never invents one"
        )
    if not isinstance(observed, str) or not _UTC_INSTANT.match(observed):
        raise Refusal(
            f"the observed UTC instant {show(observed)} is not a YYYY-MM-DDTHH:MM:SSZ value, so the"
            " receipt envelope would refuse it"
        )
    return observed


# ---- phase 1a: admit the ACTIVE distribution-activation receipt ------------------------------------


@dataclass(frozen=True)
class ActiveActivation:
    """The one statement of what this plane owns: its path, its bytes, its envelope, and its body."""

    path: Path
    raw: bytes
    receipt: dict[str, Any]
    body: dict[str, Any]
    receipt_id: str
    inventory: dict[str, dict[str, Any]]


def admit_active_receipt(dar: ModuleType, config: Config) -> ActiveActivation:
    """Read and validate the ACTIVE receipt, then admit only a LIVE activation of THIS host plane.

    An absent active receipt is the front-door refusal: there is nothing to update over, and
    reconstructing what this plane owns from directory contents is exactly the guess this module does
    not make.  Every reason is escaped before it reaches a line, because a receipt's own free text is
    observed in the field.
    """
    path = config.active_receipt_path
    try:
        raw = read_exact_file(path, _MAX_RECEIPT_BYTES, "the active distribution-activation receipt")
    except Refusal as exc:
        raise Refusal(
            f"ccodex sdlc update found no usable active distribution-activation receipt at"
            f" {show(str(path))}: {exc}. There is nothing to update over, and"
            " `ccodex sdlc install --host claude` is the front door for a first activation"
        ) from exc
    document = parse_json_object(raw, f"the active distribution-activation receipt {show(str(path))}")
    result = dar.derive("validate", document, f"the active receipt {path}")
    if result["verdict"] != dar.VERDICT_VALIDATED or not isinstance(result.get("receipt"), dict):
        reasons = "; ".join(escape_display(str(reason)) for reason in result.get("reasons", [])[:4])
        raise Refusal(
            f"ccodex sdlc update refuses: the active receipt {show(str(path))} does not validate as"
            f" {dar.BODY_SCHEMA}, so it cannot state what this plane owns or authorize a refresh of"
            f" it: {reasons or 'no reason was reported'}"
        )
    receipt = result["receipt"]
    body = receipt["body"]
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str) or not _TOKEN.match(receipt_id):
        raise Refusal(
            f"the active receipt {show(str(path))} carries the receipt_id {show(receipt_id)}, which is"
            " not a lowercase token this update could name as the record it supersedes"
        )
    admit_updatable(body, config, path)
    inventory = active_inventory(body, path)
    return ActiveActivation(
        path=path,
        raw=raw,
        receipt=receipt,
        body=body,
        receipt_id=receipt_id,
        inventory=inventory,
    )


def admit_updatable(body: dict[str, Any], config: Config, path: Path) -> None:
    """Admit only a validated receipt that describes a LIVE activation of THIS host plane and scope."""
    operation = body["operation"]
    if operation not in UPDATABLE_OPERATIONS:
        raise Refusal(
            f"the active receipt {show(str(path))} records operation {show(operation)}; only"
            f" {list(UPDATABLE_OPERATIONS)} describe a live activation, and refreshing over a"
            " retirement would write into a plane its own record says is gone"
        )
    if body["host"] != HOST:
        raise Refusal(
            f"the active receipt {show(str(path))} records host {show(body['host'])}, not"
            f" {show(HOST)}; a receipt names the one host plane it observed"
        )
    if body["activation_scope"] != ACTIVATION_SCOPE:
        raise Refusal(
            f"the active receipt {show(str(path))} records activation_scope"
            f" {show(body['activation_scope'])}, not {show(ACTIVATION_SCOPE)}; this update refreshes"
            " the Claude home plane it can observe and reinterprets no other scope"
        )
    phase = body["terminal_phase"]
    if phase not in UPDATABLE_PHASES:
        raise Refusal(
            f"the active receipt {show(str(path))} terminates {show(phase)}; only"
            f" {list(UPDATABLE_PHASES)} describe a plane with activated entries, and refreshing on the"
            " strength of an unestablished effect would turn an unknown into a write"
        )
    for key in ("candidate_id", "archive_sha256"):
        value = body[key]
        if not isinstance(value, str) or not _HEX64.match(value):
            raise Refusal(
                f"the active receipt {show(str(path))} records {key} {show(value)}, not 64 lowercase"
                " hexadecimal characters; without it the identity this update must differ from"
                " cannot be compared at all"
            )
    if not isinstance(body.get("entries"), list) or not body["entries"]:
        raise Refusal(
            f"the active receipt {show(str(path))} carries no entry inventory, and that inventory is"
            " the only statement a refresh can classify the current plane against"
        )
    # Recorded unknowns are an admission input, not a decoration: an entry whose content the active
    # receipt could not observe is named here, and the per-entry classification refuses it below.
    unknowns = body.get("unknowns")
    if not isinstance(unknowns, list):
        raise Refusal(
            f"the active receipt {show(str(path))} carries no unknowns list, so what it could not"
            " observe cannot be consulted"
        )


def active_inventory(body: dict[str, Any], path: Path) -> dict[str, dict[str, Any]]:
    """Index the active receipt's inventory by entry name. A row this module cannot read is refused."""
    index: dict[str, dict[str, Any]] = {}
    for ordinal, row in enumerate(body["entries"]):
        if not isinstance(row, dict):
            raise Refusal(
                f"the active receipt {show(str(path))} carries an inventory row {ordinal} that is not"
                " an entry record"
            )
        name = row.get("entry_name")
        if not isinstance(name, str) or not name:
            raise Refusal(
                f"the active receipt {show(str(path))} inventory row {ordinal} names the entry"
                f" {show(name)}, which is not a relative entry name"
            )
        if name in index:
            raise Refusal(
                f"the active receipt {show(str(path))} inventories {show(name)} twice, so which row"
                " describes it is unresolvable"
            )
        index[name] = row
    return index


# ---- phase 1b: admit ONE acquired candidate payload whose identity DIFFERS -------------------------


@dataclass(frozen=True)
class AdmittedPayload:
    """The one admitted new payload: its acquisition receipt, its root, and its manifest identity."""

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


@dataclass(frozen=True)
class Selection:
    """The admitted new payload plus the ACTIVE payload's acquisition receipt, when one is present.

    Both are held because both must be re-asserted byte-identical after the run: side-by-side
    identities never overwrite each other, and a sealed acquisition receipt is never mutated.
    """

    payload: AdmittedPayload
    active_receipt_path: Path | None
    active_receipt_bytes: bytes | None


def _require_physical_directory(path: Path, subject: str) -> None:
    """Refuse a link, a non-directory, or a link anywhere in the chain that reaches it."""
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
            " would move this update's payload outside the acquisition plane"
        )


def acquisition_record_digest(receipt: dict[str, Any]) -> str:
    """Re-derive the acquisition receipt's own seal: sha256 over its canonical bytes MINUS the seal."""
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
            f"{subject}'s operation_id is {show(operation_id)}, not the op-<32 lowercase hex> form the"
            " acquisition plane records; this update's receipt names it as its derived-from ancestor"
            " and correlation compares that value literally"
        )
    installed_at = receipt["installed_at"]
    if not isinstance(installed_at, str) or not _UTC_INSTANT.match(installed_at):
        raise Refusal(
            f"{subject}'s installed_at is {show(installed_at)}, not a YYYY-MM-DDTHH:MM:SSZ instant"
        )
    root_value = receipt["candidate_root_absolute_physical_path"]
    if not isinstance(root_value, str) or not root_value:
        raise Refusal(f"{subject}'s candidate_root_absolute_physical_path is {show(root_value)}")
    derived = acquisition_record_digest(receipt)
    if derived != receipt["record_sha256"]:
        raise Refusal(
            f"{subject} records record_sha256 {show(receipt['record_sha256'])} but its canonical bytes"
            f" minus that field seal to {show(derived)}; the receipt and its own seal are a mismatched"
            " pair, so this payload's provenance is not exact"
        )


def list_acquisition_receipts(config: Config) -> list[str]:
    """The acquisition plane's own receipt file names, bounded, in one stable order."""
    receipts_dir = config.acquisition_receipts_dir
    if not receipts_dir.is_dir() or receipts_dir.is_symlink():
        raise Refusal(
            f"no acquired candidate is available: the acquisition receipts directory"
            f" {show(str(receipts_dir))} is absent or is not an exact directory. Acquire the candidate"
            " this update should refresh to first; this operation never acquires one"
        )
    try:
        names = sorted(item.name for item in receipts_dir.iterdir())
    except OSError as exc:
        raise Refusal(
            f"the acquisition receipts directory {show(str(receipts_dir))} cannot be listed:"
            f" {show(exc)}"
        ) from exc
    filed = [name for name in names if name.endswith(".json") and _HEX64.match(name[: -len(".json")])]
    if len(filed) > _MAX_ACQUISITION_RECEIPTS:
        raise Refusal(
            f"the acquisition receipts directory {show(str(receipts_dir))} holds {len(filed)} filed"
            f" receipts, over the {_MAX_ACQUISITION_RECEIPTS}-document bound; an over-full plane is"
            " named rather than partly read"
        )
    return filed


def select_new_acquisition(
    config: Config, active: ActiveActivation
) -> tuple[Path, bytes, dict[str, Any], str, Path | None, bytes | None]:
    """Admit exactly ONE acquisition receipt whose archive is NOT the one already activated.

    Every filed receipt is validated, including the active payload's own: a plane holding a receipt
    this module cannot admit is ambiguous, and choosing among the rest while ignoring it would be a
    guess about which candidate the operator meant.  The active payload's receipt is then EXCLUDED by
    identity rather than by position, so a re-activation of the running identity is never reached.
    """
    filed = list_acquisition_receipts(config)
    receipts_dir = config.acquisition_receipts_dir
    active_archive = str(active.body["archive_sha256"])
    others: list[tuple[Path, bytes, dict[str, Any], str]] = []
    active_path: Path | None = None
    active_bytes: bytes | None = None
    for name in filed:
        path = receipts_dir / name
        raw = read_exact_file(path, _MAX_RECEIPT_BYTES, "the acquisition receipt")
        document = parse_json_object(raw, f"the acquisition receipt {show(str(path))}")
        archive = name[: -len(".json")]
        validate_acquisition_receipt(document, path, archive)
        if archive == active_archive:
            active_path, active_bytes = path, raw
            continue
        others.append((path, raw, document, archive))
    if not others:
        if active_path is not None:
            raise Refusal(
                f"ccodex sdlc update refuses: the only acquired candidate in"
                f" {show(str(receipts_dir))} is the one this plane already activated (archive"
                f" {show(active_archive[:12])}, candidate {show(str(active.body['candidate_id'])[:12])})."
                " There is nothing to update to, and a re-activation of the same identity is never"
                " silent"
            )
        raise Refusal(
            f"no acquired candidate is available: {show(str(receipts_dir))} holds no"
            " <archive-sha256>.json acquisition receipt other than the one this plane activated"
        )
    if len(others) > 1:
        listed = ", ".join(show(item[3] + ".json") for item in others)
        raise Refusal(
            f"{show(str(receipts_dir))} holds {len(others)} acquired candidates other than the active"
            f" one ({listed}); exactly one is admissible, and choosing between them would be a guess"
        )
    path, raw, document, archive = others[0]
    return path, raw, document, archive, active_path, active_bytes


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
    _require_physical_directory(config.data_home, "the configured XDG data home")
    for depth in range(len(ACQUISITION_CANDIDATE_SEGMENTS) + 2):
        component = expected
        for _ in range(depth):
            component = component.parent
        _require_physical_directory(component, "a component of the acquired candidate root")
    return expected


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
            f"{subject} claims public_channel {show(manifest.get('public_channel'))} and release_claim"
            f" {show(manifest.get('release_claim'))}; this plane activates only an unpublished"
            " candidate that claims no release"
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
            f"{subject}'s product_version is {show(version)}, which is not an ASCII version string of"
            " at most 64 characters; the resolved version is this receipt's whole subject"
        )
    return manifest, candidate_id, version


def manifest_inventory(manifest: dict[str, Any], candidate_root: Path) -> dict[str, dict[str, Any]]:
    """Index the manifest's inventory rows by relative path, refusing an unusable row by name."""
    rows = manifest.get("inventory")
    if not isinstance(rows, list) or not rows:
        raise Refusal(
            f"the candidate manifest at {show(str(candidate_root))} carries no usable inventory, so no"
            " payload entry could be verified against it"
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
                f"candidate manifest inventory row {ordinal} names {show(path_value)}, which carries a"
                " traversal segment"
            )
        if kind not in ("dir", "file", "symlink"):
            raise Refusal(
                f"candidate manifest inventory row {ordinal} declares the type {show(kind)}, not one"
                " of ['dir', 'file', 'symlink']"
            )
        if kind == "file" and (
            not isinstance(row.get("sha256"), str) or not _HEX64.match(str(row.get("sha256")))
        ):
            raise Refusal(
                f"candidate manifest inventory row {ordinal} for {show(path_value)} carries the sha256"
                f" {show(row.get('sha256'))}, not 64 lowercase hexadecimal characters"
            )
        if path_value in index:
            raise Refusal(
                f"the candidate manifest inventories {show(path_value)} twice, so which row describes"
                " it is unresolvable"
            )
        index[path_value] = row
    return index


def admit_new_payload(config: Config, active: ActiveActivation) -> Selection:
    """Phase 1b, whole: one exactly acquired candidate whose identity DIFFERS from the active one.

    The identity comparison is made on BOTH axes the plane records, because they can disagree: the
    archive digest selects the acquisition receipt, and the manifest's ``candidate_id`` is the payload
    identity the activation receipt carries.  Either one equal to the active receipt's is nothing to
    update, and a silent re-activation is exactly what this refusal exists to prevent.
    """
    receipt_path, raw, receipt, archive, active_path, active_bytes = select_new_acquisition(config, active)
    candidate_root = admit_candidate_root(config, receipt, archive)
    manifest, candidate_id, version = admit_candidate_manifest(candidate_root)
    if candidate_id == str(active.body["candidate_id"]):
        raise Refusal(
            f"ccodex sdlc update refuses: the acquired candidate {show(str(receipt_path))} carries the"
            f" candidate identity {show(candidate_id[:12])}, which is the identity this plane already"
            " activated. There is nothing to update, and a re-activation of the same identity is"
            " never silent"
        )
    inventory = manifest_inventory(manifest, candidate_root)
    payload = AdmittedPayload(
        receipt_path=receipt_path,
        receipt_bytes=raw,
        receipt=receipt,
        archive_sha256=archive,
        operation_id=str(receipt["operation_id"]),
        candidate_root=candidate_root,
        manifest=manifest,
        candidate_id=candidate_id,
        resolved_version=version,
        inventory=inventory,
    )
    return Selection(payload=payload, active_receipt_path=active_path, active_receipt_bytes=active_bytes)


def reassert_acquisition_receipts(selection: Selection, effect_started: bool) -> None:
    """Both sealed acquisition receipts must be BYTE-IDENTICAL after the whole run.

    They are this plane's provenance and this module never writes either one.  A change means a
    concurrent writer or a defect here, and either way the run's evidence is no longer exact: after an
    effect that is an unknown, before one it is a clean refusal.
    """
    pairs: list[tuple[Path, bytes]] = [(selection.payload.receipt_path, selection.payload.receipt_bytes)]
    if selection.active_receipt_path is not None and selection.active_receipt_bytes is not None:
        pairs.append((selection.active_receipt_path, selection.active_receipt_bytes))
    for path, admitted in pairs:
        try:
            current = path.read_bytes()
        except OSError as exc:
            message = (
                f"the acquisition receipt {show(str(path))} could not be re-read to prove it was not"
                f" written: {show(exc)}"
            )
            raise (UnknownEffect if effect_started else Refusal)(message) from exc
        if current != admitted:
            message = (
                f"the acquisition receipt {show(str(path))} changed during this run (admitted"
                f" {show(sha256_bytes(admitted))}, now {show(sha256_bytes(current))}); this operation"
                " never writes it, so its provenance is no longer exact"
            )
            raise (UnknownEffect if effect_started else Refusal)(message)


# ---- phase 2: the new payload's own release-contract compatibility claims --------------------------


def observe_host_version(config: Config) -> str | None:
    """Observe the Claude Code host version, or take the injected observation.

    The default observation runs the host's own ``--version`` once, with no shell, a bounded timeout,
    and an argument vector.  ``shutil.which`` is consulted rather than the ambient PATH being
    reshaped, because a test that strips PATH tests the developer's machine instead.  A host that
    cannot be observed yields ``None``, which is a DIFFERENT input from ``UNSUPPLIED``.
    """
    if not isinstance(config.observed_host_version, _Unsupplied):
        return config.observed_host_version
    executable = shutil.which(_HOST_VERSION_COMMAND[0])
    if executable is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, bounded
            [executable, *_HOST_VERSION_COMMAND[1:]],
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
            " this update cannot check the host it is about"
        )
    return contract


def _version_tuple(value: object, subject: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _SEMVER.match(value):
        raise Refusal(f"{subject} is {show(value)}, not a three-part SemVer of ASCII digits")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def check_compatibility(config: Config, payload: AdmittedPayload) -> str:
    """Refuse a DECLARED incompatibility by name; never substitute another version for the observed.

    Three separate refusals, because collapsing them hides which half of the question was
    unanswerable: the contract is about another host, the observed version is one the NEW payload
    declares incompatible, or the observed version is below the declared eligibility floor.  A host
    version that could not be observed is refused too: the activation receipt's closed unknowns
    vocabulary cannot say "the host version was unknown", so admitting one would seal a document that
    silently omits an admission input.
    """
    contract = load_release_contract(payload.candidate_root)
    compatibility = contract["compatibility"]
    core = compatibility.get("core")
    if not isinstance(core, dict):
        raise Refusal("the payload's release contract carries no compatibility.core row")
    declared_host = core.get("host")
    if declared_host != RELEASE_CONTRACT_HOST:
        raise Refusal(
            f"the payload's release contract states its core compatibility is about the host"
            f" {show(declared_host)}, not {show(RELEASE_CONTRACT_HOST)}; this update refreshes the"
            " Claude Code host plane and no other one"
        )
    known = compatibility.get("known_incompatible_host_versions")
    if not isinstance(known, list):
        raise Refusal(
            "the payload's release contract carries no"
            " compatibility.known_incompatible_host_versions list, so a declared incompatibility could"
            " not be read"
        )
    incompatible: dict[str, str] = {}
    for ordinal, record in enumerate(known):
        if not isinstance(record, dict) or set(record) != {"reason", "version"}:
            raise Refusal(
                f"compatibility.known_incompatible_host_versions[{ordinal}] is not a"
                " {reason, version} record"
            )
        version = record["version"]
        _version_tuple(version, f"compatibility.known_incompatible_host_versions[{ordinal}].version")
        reason = record["reason"]
        if not isinstance(reason, str) or not reason:
            raise Refusal(
                f"compatibility.known_incompatible_host_versions[{ordinal}].reason is {show(reason)},"
                " not a non-empty string"
            )
        incompatible[str(version)] = reason

    observed = observe_host_version(config)
    if observed is None:
        raise Refusal(
            "the Claude Code host version could not be observed, so the new payload's declared"
            " compatibility claims cannot be checked against this host. This operation refuses rather"
            " than assuming compatibility, and it never substitutes another version for the observed"
            " one"
        )
    if not isinstance(observed, str) or not _SEMVER.match(observed):
        raise Refusal(
            f"the observed Claude Code host version {show(observed)} is not a three-part SemVer, so it"
            " cannot be compared with the payload's declared claims"
        )
    if observed in incompatible:
        raise Refusal(
            f"the new payload DECLARES the observed Claude Code host version {show(observed)}"
            f" incompatible: {show(incompatible[observed])}. A declared incompatibility is refused by"
            " name, and no other host version is substituted for the observed one"
        )
    floor = _version_tuple(core.get("minimum_host_version"), "compatibility.core.minimum_host_version")
    if _version_tuple(observed, "the observed Claude Code host version") < floor:
        raise Refusal(
            f"the observed Claude Code host version {show(observed)} is below the new payload's"
            f" declared eligibility floor {show(core.get('minimum_host_version'))}; meeting that floor"
            " is eligibility only and falling below it is a declared incompatibility"
        )
    return observed


# ---- phase 3a: classify the refresh footprint BEFORE anything is written ---------------------------


@dataclass(frozen=True)
class PlannedEntry:
    """One entry this run manages, classified before any effect: what it is now and what happens.

    ``entry`` is the payload entry the refresh would write, or ``None`` for an entry the ACTIVE
    inventory records that the new payload no longer carries.  The second kind is never written and
    never removed; it is preserved and named, because an update receipt cannot record a removal in
    this family's closed disposition vocabulary.
    """

    entry: Any
    destination: Path | None
    name: str
    classification: str
    action: str
    record: dict[str, Any] | None
    recorded_sha256: str | None
    current_sha256: str | None
    detail: str
    dropped: bool = False

    @property
    def prestate(self) -> str:
        return CLASS_PRESTATE[self.classification]

    @property
    def blocks(self) -> bool:
        """Does this entry stop the whole refresh before it starts?

        Only an entry the new payload would WRITE can block: a dropped entry is not a destination this
        run touches, so a modified one there is preserved and named without stopping anything.
        """
        return not self.dropped and self.classification not in ADMITTED_CLASSES


@dataclass
class Run:
    """The one fact that decides an exit class: had an effect started when this failed?"""

    effect_started: bool = False
    completed_effects: int = 0
    failures: list[str] = dataclass_field(default_factory=list)
    pointer_replaced: bool = False


def safe_digest(bundle: ModuleType, path: Path) -> str | None:
    """The one reused digest definition, with an unreadable object reported as an honest unknown."""
    try:
        return bundle.digest(path)
    except (OSError, bundle.InstallerError, ValueError):
        return None


def entry_display_name(destination: Path, agent_root: Path) -> str:
    """The receipt's ``entry_name``: one relative ASCII name inside the activated scope."""
    try:
        relative = destination.relative_to(agent_root).as_posix()
    except ValueError as exc:
        raise Refusal(
            f"the destination {show(str(destination))} is not inside the activated Claude root"
            f" {show(str(agent_root))}"
        ) from exc
    if not _ENTRY_NAME.match(relative) or ".." in relative.split("/") or len(relative) > 256:
        raise Refusal(
            f"the entry name {show(relative)} is not a relative ASCII entry name the receipt inventory"
            " can carry"
        )
    return relative


def resolve_destination(config: Config, entry_name: Any) -> Path | None:
    """Resolve one INVENTORY entry name to one path inside the plane, or refuse to resolve it.

    The receipt family already refuses ``..`` in an entry name.  This is the second, independent check
    on the resolved path rather than on the spelling, because a receipt is evidence and never
    authorization: the value that decides where this run looks is re-derived here.
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
    """Is any directory between the plane root and this entry a link?

    A write reached through a link takes effect wherever the link points, which is outside what this
    receipt describes.  ``lstat`` on each component, never ``resolve``, so the question asked is "is
    this component a link" and not "where does it end up".
    """
    root = Path(os.path.normpath(str(config.plane_root)))
    current = destination.parent
    while True:
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except OSError:
            return False
        if current == root or current == current.parent:
            return False
        current = current.parent


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


def verify_entry_against_manifest(payload: AdmittedPayload, source: Path) -> None:
    """Verify the payload subset this refresh copies against the new manifest's own rows.

    Both directions, because each catches a different defect: an observed node with no row is content
    the manifest never inventoried, and a row with no observed node is a payload the manifest says is
    more complete than it is.
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
        name for name in payload.inventory if name == prefix or name.startswith(f"{prefix}/")
    }
    for name in sorted(set(observed) - inventoried):
        raise Refusal(
            f"the candidate payload carries {show(name)}, which its manifest does not inventory, so"
            " this refresh would copy content the payload's own identity does not cover"
        )
    for name in sorted(inventoried - set(observed)):
        raise Refusal(
            f"the candidate manifest inventories {show(name)}, which is absent from the payload, so the"
            " admitted candidate is not the payload its manifest describes"
        )
    for name in sorted(observed):
        path = observed[name]
        row = payload.inventory[name]
        kind = node_kind(path)
        if row.get("type") != kind:
            raise Refusal(
                f"the candidate payload node {show(name)} is a {kind} while its manifest row declares"
                f" {show(row.get('type'))}"
            )
        if kind == "file":
            digest = sha256_file(path)
            if digest != row.get("sha256"):
                raise Refusal(
                    f"the candidate payload file {show(name)} digests to {show(digest)} but its"
                    f" manifest row records {show(row.get('sha256'))}"
                )
        elif kind == "symlink":
            target = os.readlink(path)
            if target != row.get("target"):
                raise Refusal(
                    f"the candidate payload symlink {show(name)} points at {show(target)} but its"
                    f" manifest row records {show(row.get('target'))}"
                )


def classify_footprint(
    bundle: ModuleType,
    bundle_config: Any,
    config: Config,
    state: dict[str, Any],
    payload: AdmittedPayload,
    active: ActiveActivation,
) -> list[PlannedEntry]:
    """Classify every entry the new payload would write, against the ACTIVE receipt's inventory.

    The active inventory -- not a directory listing and not the installer state alone -- is the
    statement of what this plane owns, so ownership is proved against the digest IT recorded.  The
    installer ownership record is consulted as well, because the transactional refresh needs the
    record it replaces, and a refresh that could not prove what it replaces is not one this module
    performs.

    Every list is built into a local before it is returned: a comprehension inside the plan literal
    would be evaluated after its sibling keys and would drop exactly the observations this walk exists
    to make.
    """
    discovered = [
        entry for entry in bundle.discover_entries(payload.candidate_root) if entry.agent == ENTRY_AGENT
    ]
    if not discovered:
        raise Refusal(
            f"the admitted candidate payload at {show(str(payload.candidate_root))} carries no"
            " claude-host entries, so there is nothing this refresh could write"
        )
    outstanding = sorted(state.get("transactions", {}))
    if outstanding:
        raise Refusal(
            f"the installer ownership state holds {len(outstanding)} outstanding lifecycle"
            f" transaction(s), the first being {show(outstanding[0])}; recovery is a separate explicit"
            " operation and this update never resolves one"
        )
    planned: list[PlannedEntry] = []
    footprint: set[str] = set()
    for entry in discovered:
        verify_entry_against_manifest(payload, entry.source)
        try:
            destination = bundle.destination_for(entry, bundle_config)
            bundle.assert_safe_collection(entry, destination, bundle_config)
            agent_root = bundle.agent_root(entry, bundle_config)
        except bundle.InstallerError as exc:
            raise Refusal(f"the claude refresh destination is not admissible: {show(exc)}") from exc
        name = entry_display_name(destination, agent_root)
        if name in footprint:
            raise Refusal(
                f"the new payload would write {show(name)} twice, so which payload entry owns that"
                " destination is unresolvable"
            )
        footprint.add(name)
        planned.append(
            classify_one(bundle, bundle_config, config, state, payload, active, entry, destination, name)
        )
    for name in sorted(set(active.inventory) - footprint):
        planned.append(classify_dropped(bundle, config, active, name))
    planned.sort(key=lambda item: (item.dropped, item.name))
    return planned


def classify_one(
    bundle: ModuleType,
    bundle_config: Any,
    config: Config,
    state: dict[str, Any],
    payload: AdmittedPayload,
    active: ActiveActivation,
    entry: Any,
    destination: Path,
    name: str,
) -> PlannedEntry:
    """Classify ONE destination the new payload would write. Only two classes are ever changed."""
    row = active.inventory.get(name)
    recorded = row.get("content_sha256") if isinstance(row, dict) else None
    recorded_ok = isinstance(recorded, str) and bool(_HEX64.match(recorded))

    def planned(classification: str, current: str | None, detail: str, action: str) -> PlannedEntry:
        return PlannedEntry(
            entry=entry,
            destination=destination,
            name=name,
            classification=classification,
            action=action,
            record=state.get("entries", {}).get(str(destination)),
            recorded_sha256=recorded if recorded_ok else None,
            current_sha256=current,
            detail=detail,
        )

    if not bundle.path_present(destination):
        detail = CLASS_REASON[CLASS_ABSENT]
        if row is not None:
            detail = (
                f"{detail}; the active receipt's inventory records this entry as activated and nothing"
                " is there now, so the refresh writes into the empty slot rather than over content"
            )
        return planned(CLASS_ABSENT, None, detail, ACTION_INSTALL)
    if parent_is_retargeted(config, destination):
        return planned(CLASS_RETARGETED, None, CLASS_REASON[CLASS_RETARGETED], ACTION_PRESERVE)
    if destination.is_symlink() or bundle.is_junction(destination):
        return planned(
            CLASS_FOREIGN_LINK, safe_digest(bundle, destination), CLASS_REASON[CLASS_FOREIGN_LINK], ACTION_PRESERVE
        )
    if not destination.is_file() and not destination.is_dir():
        return planned(CLASS_FOREIGN_TYPE, None, CLASS_REASON[CLASS_FOREIGN_TYPE], ACTION_PRESERVE)
    current = safe_digest(bundle, destination)
    if current is None:
        return planned(CLASS_UNREADABLE, None, CLASS_REASON[CLASS_UNREADABLE], ACTION_PRESERVE)
    if row is None:
        return planned(CLASS_FOREIGN, current, CLASS_REASON[CLASS_FOREIGN], ACTION_PRESERVE)
    if not recorded_ok:
        return planned(CLASS_UNPROVABLE, current, CLASS_REASON[CLASS_UNPROVABLE], ACTION_PRESERVE)
    if current != recorded:
        return planned(CLASS_MODIFIED, current, CLASS_REASON[CLASS_MODIFIED], ACTION_PRESERVE)

    record = state.get("entries", {}).get(str(destination))
    if not isinstance(record, dict):
        return planned(CLASS_NO_RECORD, current, CLASS_REASON[CLASS_NO_RECORD], ACTION_PRESERVE)
    try:
        authority_matches = bundle.record_authority_matches(str(destination), record, bundle_config)
    except bundle.InstallerError as exc:
        return planned(
            CLASS_RECORD_UNUSABLE,
            current,
            "the recorded destination could not be re-checked, so it is preserved:"
            f" {escape_display(str(exc))}",
            ACTION_PRESERVE,
        )
    if not authority_matches:
        return planned(
            CLASS_RECORD_UNUSABLE,
            current,
            "the recorded configured root or collection identity no longer matches, so the ownership"
            " record is retargeted and is preserved rather than rewritten",
            ACTION_PRESERVE,
        )
    if record.get("mode") != ACTIVATION_MODE:
        return planned(
            CLASS_RECORD_UNUSABLE,
            current,
            f"the destination is owned in {show(record.get('mode'))} mode by another installation"
            " plane; this refresh copies and never converts an existing mode",
            ACTION_PRESERVE,
        )
    if record.get("removable", True) is False:
        return planned(
            CLASS_RECORD_UNUSABLE,
            current,
            "the destination is an adopted copy preserved on uninstall; it is left exactly as it is",
            ACTION_PRESERVE,
        )
    source_digest = safe_digest(bundle, entry.source)
    if source_digest is None:
        return planned(
            CLASS_RECORD_UNUSABLE,
            current,
            "the new payload entry could not be digested, so the owned entry is preserved rather than"
            " replaced by content this run cannot describe",
            ACTION_PRESERVE,
        )
    if record.get("source") == str(entry.source.resolve()) and record.get("digest") == source_digest:
        return planned(CLASS_OWNED_CURRENT, current, CLASS_REASON[CLASS_OWNED_CURRENT], ACTION_PRESERVE)
    return planned(
        CLASS_OWNED_EXACT,
        current,
        f"{CLASS_REASON[CLASS_OWNED_EXACT]}, and the new payload entry differs from it",
        ACTION_REFRESH,
    )


def classify_dropped(
    bundle: ModuleType, config: Config, active: ActiveActivation, name: str
) -> PlannedEntry:
    """Classify one entry the ACTIVE inventory records that the new payload no longer carries.

    It is never written and never removed.  ``OPERATION_DISPOSITIONS['update']`` admits no ``removed``
    disposition at all, so a removal here could not be recorded in the receipt that reports it, and
    removing while recording ``preserved`` would be a false statement about the plane.  Removal is
    ``ccodex sdlc uninstall``'s verb; this row exists so the entry is NAMED rather than dropped from
    the only inventory that describes this plane.
    """
    row = active.inventory[name]
    recorded = row.get("content_sha256")
    recorded_ok = isinstance(recorded, str) and bool(_HEX64.match(recorded))
    destination = resolve_destination(config, name)
    note = (
        "; it is carried by the retired payload and not by the new one, so it is preserved and named"
        " here rather than removed, because an update receipt cannot record a removal"
    )

    def dropped(classification: str, current: str | None) -> PlannedEntry:
        return PlannedEntry(
            entry=None,
            destination=destination,
            name=name,
            classification=classification,
            action=ACTION_PRESERVE,
            record=None,
            recorded_sha256=recorded if recorded_ok else None,
            current_sha256=current,
            detail=CLASS_REASON[classification] + note,
            dropped=True,
        )

    if destination is None:
        return dropped(CLASS_AMBIGUOUS, None)
    if not bundle.path_present(destination):
        return dropped(CLASS_ABSENT, None)
    if parent_is_retargeted(config, destination):
        return dropped(CLASS_RETARGETED, None)
    if destination.is_symlink() or bundle.is_junction(destination):
        return dropped(CLASS_FOREIGN_LINK, safe_digest(bundle, destination))
    if not destination.is_file() and not destination.is_dir():
        return dropped(CLASS_FOREIGN_TYPE, None)
    current = safe_digest(bundle, destination)
    if current is None:
        return dropped(CLASS_UNREADABLE, None)
    if not recorded_ok:
        return dropped(CLASS_UNPROVABLE, current)
    if current != recorded:
        return dropped(CLASS_MODIFIED, current)
    return dropped(CLASS_OWNED_CURRENT, current)


def refuse_blocked_entries(planned: list[PlannedEntry]) -> None:
    """Name every blocking entry and refuse the WHOLE refresh before anything moves.

    There is no partial update past a blocked entry: the refusal is decided here, before the first
    transaction is armed, so a blocked plane is exactly as it was when this command started.
    """
    blocked = [item for item in planned if item.blocks]
    if not blocked:
        return
    lines = [
        f"  {escape_display(item.name)} ({item.classification}: {escape_display(item.detail)})"
        for item in blocked
    ]
    raise Refusal(
        f"ccodex sdlc update refuses: {BLOCK_SENTENCE}. {len(blocked)} entr"
        f"{'y' if len(blocked) == 1 else 'ies'} the new payload would write cannot be proved unchanged"
        " against the active receipt's inventory, so the whole refresh stops before any effect and"
        " every one of them is preserved exactly as it is:\n" + "\n".join(lines)
    )


# ---- phase 3b: this module's own documents, written before any entry moves --------------------------


def canonical_document_bytes(dar: ModuleType, document: dict[str, Any], subject: str) -> bytes:
    """One canonical spelling for every document this module writes: the receipt producer's own."""
    try:
        return dar.canonical_bytes(document)
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
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".update-", delete=False) as handle:
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
        raise Refusal(f"{subject} cannot be prepared at {show(str(path.parent))}: {show(exc)}") from exc
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Refusal(
            f"{subject} already exists at {show(str(path))}; this operation never overwrites an existing"
            " receipt, because that document is the only evidence of the run that wrote it"
        ) from exc
    except OSError as exc:
        raise Refusal(f"{subject} cannot be created at {show(str(path))}: {show(exc)}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            bundle.flush_descriptor(handle.fileno(), full=True)
        bundle.fsync_directory(path.parent)
    except (OSError, bundle.DurabilityError) as exc:
        raise Refusal(f"{subject} cannot be written at {show(str(path))}: {show(exc)}") from exc


def build_plan_document(
    config: Config,
    payload: AdmittedPayload,
    active: ActiveActivation,
    planned: list[PlannedEntry],
    host_version: str,
    instant: str,
) -> dict[str, Any]:
    """The pre-effect intent, in one canonical document whose digest the receipt binds.

    Both lists are hoisted into locals ABOVE the returned literal.  Written the other way, Python
    would evaluate each comprehension after its sibling keys, and the plan the receipt's
    ``plan_sha256`` binds would be a plan assembled from values read before the walk that produced
    them -- the same evaluation-order defect that drops data.
    """
    refresh: list[dict[str, Any]] = []
    preserve: list[dict[str, Any]] = []
    for item in planned:
        row = {
            "action": item.action,
            "class": item.classification,
            "destination": str(item.destination) if item.destination is not None else None,
            "detail": item.detail,
            "dropped_by_new_payload": item.dropped,
            "entry_name": item.name,
            "prestate": item.prestate,
        }
        if item.action in (ACTION_INSTALL, ACTION_REFRESH):
            refresh.append(row)
        else:
            preserve.append(row)
    refresh.sort(key=lambda row: str(row["entry_name"]))
    preserve.sort(key=lambda row: str(row["entry_name"]))
    return {
        "activation_scope": ACTIVATION_SCOPE,
        "archive_sha256": payload.archive_sha256,
        "candidate_id": payload.candidate_id,
        "candidate_root": str(payload.candidate_root),
        "claude_root": str(config.plane_root),
        "host": HOST,
        "mode": ACTIVATION_MODE,
        "observed_host_version": host_version,
        "operation": OPERATION,
        "planned_at": instant,
        "preserve": preserve,
        "prior_archive_sha256": active.body["archive_sha256"],
        "prior_candidate_id": active.body["candidate_id"],
        "prior_receipt_id": active.receipt_id,
        "prior_resolved_version": active.body["resolved_version"],
        "public_channel": None,
        "refresh": refresh,
        "release_claim": "none",
        "resolved_version": payload.resolved_version,
        "schema_version": PLAN_SCHEMA,
        "version_source": VERSION_SOURCE,
    }


def build_journal_document(
    payload: AdmittedPayload,
    active: ActiveActivation,
    plan_sha256: str,
    installer_state_path: Path,
    receipt_id: str,
    receipt_path: Path,
    retained_prior_path: Path,
    active_pointer: Path,
    phase: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """The effect journal: what is intended, what moved, and where each receipt of this run lives.

    ``pointer_when_recorded`` is stated as of THIS write and is never rewritten afterwards, because
    the receipt binds these exact bytes as its ``journal_sha256``: a later rewrite would leave the
    receipt bound to a digest the file no longer has, which reads as tampering.  It is therefore the
    recoverable fact a killed run leaves behind -- the prior receipt was still the active statement
    when the effect was recorded -- and an operator compares the named pointer against the named
    receipt path to see which half of the transition completed.
    """
    rows = [dict(record) for record in records]
    return {
        "active_pointer": str(active_pointer),
        "candidate_id": payload.candidate_id,
        "entries": rows,
        "host": HOST,
        "installer_state_path": str(installer_state_path),
        "operation": OPERATION,
        "phase": phase,
        "plan_sha256": plan_sha256,
        "pointer_when_recorded": "prior-receipt",
        "prior_candidate_id": active.body["candidate_id"],
        "prior_receipt_id": active.receipt_id,
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "retained_prior_receipt": str(retained_prior_path),
        "schema_version": JOURNAL_SCHEMA,
    }


# ---- phase 3c: the transactional refresh -----------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One entry's observed outcome, with the content digest that lands in the receipt inventory."""

    name: str
    prestate: str
    disposition: str
    detail: str
    content_sha256: str | None
    unknown_detail: str | None


def observe_content(bundle: ModuleType, path: Path | None) -> tuple[str | None, str | None]:
    """Digest one entry that exists, or NAME why it could not be digested.

    A null digest under a content-bearing disposition is supplied-but-missing, so it must be named as
    an unknown rather than written as a hole; the receipt producer refuses the hole by name.
    """
    if path is None:
        return None, "the entry name did not resolve to one path inside the plane, so nothing was digested"
    try:
        return bundle.digest(path), None
    except (bundle.InstallerError, OSError) as exc:
        return None, f"the entry could not be digested: {escape_display(str(exc))}"


def _preserved_outcome(bundle: ModuleType, item: PlannedEntry, detail: str) -> Outcome:
    """One preserved entry, digested only when there is content a digest could be OF.

    ``absent`` plus ``preserved`` means nothing was there and nothing was written, so a digest would
    describe content that does not exist and the receipt producer refuses it by name.  That null is
    not-supplied and needs no unknown; a null under a content-bearing disposition is
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

    An inventory that dropped them would read as an update of fewer entries than this operation
    managed.  The body-level ``effect_state`` carries the uncertainty; no entry row claims an effect
    nobody observed.
    """
    outcomes: list[Outcome] = []
    for ordinal, item in enumerate(remaining):
        detail = (
            "this entry's transaction failed, so no effect on it is claimed; the installer's own journal"
            " is the recovery evidence"
            if ordinal == 0
            else "not attempted, because an earlier entry's transaction failed first"
        )
        outcomes.append(_preserved_outcome(bundle, item, detail))
    return outcomes


def refresh(
    bundle: ModuleType,
    bundle_config: Any,
    state: dict[str, Any],
    planned: list[PlannedEntry],
    run: Run,
) -> list[Outcome]:
    """Refresh every verified-unchanged owned entry and install every absent one, transactionally.

    Stopping at the first failure is deliberate: once one entry's transaction failed, the next would
    widen an already unknown effect, and a partial refresh with a named boundary is more recoverable
    than a half-finished sweep.  Every preserved entry -- including every entry the new payload no
    longer carries -- keeps its own named row.
    """
    outcomes: list[Outcome] = []
    for index, item in enumerate(planned):
        if item.action == ACTION_PRESERVE:
            outcomes.append(_preserved_outcome(bundle, item, item.detail))
            continue
        assert item.destination is not None  # only a payload footprint entry is ever written
        run.effect_started = True
        try:
            bundle.ensure_collection(item.entry, item.destination, bundle_config)
            if item.action == ACTION_INSTALL:
                root_token, collection_token = bundle.authority_tokens(
                    item.entry, item.destination, bundle_config
                )
                mode = bundle.transactional_create(
                    item.entry, item.destination, bundle_config, state, root_token, collection_token
                )
                disposition = DISPOSITION_INSTALLED
            else:
                assert item.record is not None  # classified owned, so an ownership record exists
                mode = bundle.transactional_replace(
                    item.entry,
                    item.destination,
                    bundle_config,
                    state,
                    item.record,
                    old_owned=True,
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
                f"{item.action} of {escape_display(item.name)} published {show(mode)} rather than a copy"
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
            )
        )
    return outcomes


# ---- phase 4: the sealed receipt and the active pointer --------------------------------------------


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
                "prestate": outcome.prestate,
            }
        )
        if outcome.content_sha256 is None and outcome.unknown_detail is not None:
            unknowns.append(
                {
                    "detail": outcome.unknown_detail[:_MAX_DETAIL],
                    "observation": "entry-content",
                    "subject": outcome.name,
                }
            )
    entries.sort(key=lambda row: str(row["entry_name"]))
    if journal_sha256 is None:
        unknowns.append(
            {
                "detail": (
                    "the update journal could not be digested, so the effect's own record is"
                    " unavailable"
                ),
                "observation": "journal-digest",
                "subject": "journal_sha256",
            }
        )
    unknowns.sort(key=lambda row: (str(row["observation"]), str(row["subject"])))
    return entries, unknowns


def derive_effect_state(
    dar: ModuleType, run: Run, journal_sha256: str | None, unknowns: list[dict[str, Any]]
) -> tuple[str, str]:
    """Effect state and terminal phase, taken from the receipt producer's OWN matrices.

    Reading the matrices instead of re-expressing them is what keeps this module and the checker from
    disagreeing exactly once, on the run nobody re-validated.  The RECORDED UNKNOWNS are an input, not
    a decoration: an effect whose own observations could not all be made is partial, never complete,
    and a derivation reading only the outcomes would have claimed complete precisely because an unmade
    observation is not one of them.
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
    admitted = dar.EFFECT_PHASES[state]
    phase = admitted[0]
    for preference in ("activated", "activated-partial", "unknown", "not-activated"):
        if preference in admitted and preference in dar.OPERATION_PHASES[OPERATION]:
            phase = preference
            break
    return state, phase


def build_receipt_body(
    dar: ModuleType,
    payload: AdmittedPayload,
    entries: list[dict[str, Any]],
    unknowns: list[dict[str, Any]],
    plan_sha256: str,
    journal_sha256: str | None,
    effect_state: str,
    terminal_phase: str,
) -> dict[str, Any]:
    """Write the closed ``distribution-activation-body@1`` observation from already-built locals.

    Both lists arrive complete, which is the whole point: nothing is discovered while this literal is
    evaluated, so nothing can be dropped by the order in which Python evaluates it.
    """
    return {
        "activation_scope": ACTIVATION_SCOPE,
        "archive_sha256": payload.archive_sha256,
        "candidate_id": payload.candidate_id,
        "effect_state": effect_state,
        "entries": entries,
        "host": HOST,
        "journal_sha256": journal_sha256,
        "operation": OPERATION,
        "plan_sha256": plan_sha256,
        "public_channel": None,
        # The explicit unsealed placeholder: seal WRITES this field, and an absent key would let the
        # producer fill a value the observation never asked it to.
        "record_sha256": dar.UNSEALED,
        "release_claim": "none",
        # A request is not a readback (Seed agentic-sdlc-0faa). This grammar carries no version request
        # at all, and null says so rather than leaving the key absent.
        "requested_version": None,
        "resolved_version": payload.resolved_version,
        "schema_version": dar.BODY_SCHEMA,
        "terminal_phase": terminal_phase,
        "unknowns": unknowns,
        "version_source": VERSION_SOURCE,
    }


def receipt_identity(payload: AdmittedPayload, instant: str) -> str:
    """One lowercase token identifying this receipt, derived from facts and never from a counter."""
    compact = instant.replace("-", "").replace(":", "").lower()
    token = f"{OPERATION}-{payload.operation_id}-{compact}"
    if not _TOKEN.match(token):
        raise Refusal(f"the derived receipt identity {show(token)} is not a lowercase ASCII token")
    return token


def seal_receipt(
    dar: ModuleType,
    body: dict[str, Any],
    payload: AdmittedPayload,
    active: ActiveActivation,
    receipt_id: str,
    instant: str,
) -> dict[str, Any]:
    """Derive the sealed receipt through the T1 producer, with BOTH ancestors this operation owes.

    Exactly one ``supersedes`` naming the receipt this update replaces -- the family admits that
    relation only for ``operation: update``, and requires exactly one of it -- and exactly one
    ``derived-from`` naming the NEW acquisition receipt this refresh drew its payload from.  Both
    reference a ``distribution-activation`` ``expected_kind``, because that kind names the lifecycle
    family rather than one operation.
    """
    document = {
        "ancestors": [
            {
                "expected_kind": dar.RECEIPT_KIND,
                "receipt_id": payload.operation_id,
                "relation": "derived-from",
            },
            {
                "expected_kind": dar.RECEIPT_KIND,
                "receipt_id": active.receipt_id,
                "relation": "supersedes",
            },
        ],
        "body": body,
        "content_digest": dar.UNSEALED,
        "emitting_plane": EMITTING_PLANE,
        "receipt_id": receipt_id,
        "receipt_kind": dar.RECEIPT_KIND,
        "schema": dar.ENVELOPE_SCHEMA,
        "stated_at": instant,
    }
    try:
        result = dar.derive("seal", document, "this update's observation")
    except dar.InputError as exc:
        raise UnknownEffect(
            f"this update's receipt could not be derived, so its effect has no sealed evidence:"
            f" {show(exc)}"
        ) from exc
    if result["verdict"] != dar.VERDICT_SEALED or not isinstance(result.get("receipt"), dict):
        reasons = "; ".join(escape_display(str(reason)) for reason in result.get("reasons", []))
        raise UnknownEffect(
            "this update's receipt was refused by its own producer, so its effect has no sealed"
            f" evidence: {reasons or 'no reason was reported'}"
        )
    return result["receipt"]


def retain_prior_receipt(bundle: ModuleType, dar: ModuleType, config: Config, active: ActiveActivation) -> Path:
    """Make sure the PRIOR receipt survives the pointer replacement, before any effect starts.

    The active pointer is a document, not a link, so replacing it would be the last write of the only
    copy unless the prior receipt is also filed under its own id.  This retains it create-only: an
    existing file whose canonical bytes match is already the retained copy, and a DIFFERENT document
    filed under the same receipt id is a named refusal rather than an overwrite, because two documents
    claiming one identity is exactly the ambiguity this plane must not resolve by guessing.
    """
    path = config.receipts_dir / f"{active.receipt_id}.json"
    expected = canonical_document_bytes(dar, active.receipt, "the prior receipt")
    if bundle.path_present(path):
        raw = read_exact_file(path, _MAX_RECEIPT_BYTES, "the retained prior receipt")
        if raw != expected:
            document = parse_json_object(raw, f"the retained prior receipt {show(str(path))}")
            if canonical_document_bytes(dar, document, "the retained prior receipt") != expected:
                raise Refusal(
                    f"the receipt id {show(active.receipt_id)} is already filed at {show(str(path))} as"
                    " a DIFFERENT document from the one this plane's active pointer carries; two"
                    " documents claiming one receipt identity is an ambiguity this update refuses"
                    " rather than resolves, and neither one is overwritten"
                )
        return path
    write_new_document(bundle, path, expected, "the retained prior receipt")
    return path


def replace_active_pointer(bundle: ModuleType, config: Config, raw: bytes) -> None:
    """Point the plane at the NEW receipt, atomically, only after it is durably filed.

    ``os.replace`` plus a parent fsync inside ``write_replaceable_document``: a kill before this call
    leaves the prior receipt as the plane's active statement, and a kill after it leaves the new
    receipt -- which is already durably filed under its own id.  There is no window in which the
    pointer names a receipt no directory holds.
    """
    try:
        write_replaceable_document(bundle, config.active_receipt_path, raw, "the active receipt pointer")
    except Refusal as exc:
        raise UnknownEffect(
            f"the refresh completed but the active pointer {show(str(config.active_receipt_path))} could"
            f" not be replaced, so the plane's active statement still names the prior receipt: {exc}"
        ) from exc


# ---- the report ------------------------------------------------------------------------------------


def report(
    config: Config,
    payload: AdmittedPayload,
    active: ActiveActivation,
    outcomes: list[Outcome],
    planned: list[PlannedEntry],
    effect_state: str,
    terminal_phase: str,
    receipt_path: Path,
    retained_prior: Path,
    journal_path: Path,
    run: Run,
) -> None:
    """One line per fact, every artifact-derived value escaped, and no claim beyond the evidence."""
    dropped = {item.name for item in planned if item.dropped}
    lines = [
        f"ccodex sdlc update: effect {escape_display(effect_state)}, terminal"
        f" {escape_display(terminal_phase)}",
        f"candidate {escape_display(str(active.body['candidate_id'])[:12])} ->"
        f" {escape_display(payload.candidate_id[:12])}: resolved"
        f" {escape_display(str(active.body['resolved_version']))} ->"
        f" {escape_display(payload.resolved_version)} via {VERSION_SOURCE}"
        " (requested: no version was requested)",
        f"claude root: {escape_display(str(config.plane_root))} (copies, never links)",
    ]
    for outcome in outcomes:
        suffix = " [not carried by the new payload]" if outcome.name in dropped else ""
        lines.append(
            f"entry {escape_display(outcome.name)}: {escape_display(outcome.prestate)} ->"
            f" {escape_display(outcome.disposition)}{suffix} -- {escape_display(outcome.detail)}"
        )
    for failure in run.failures:
        lines.append(f"failure: {escape_display(failure)}")
    for record in active.body.get("unknowns", []):
        if isinstance(record, dict):
            # `detail` is free text observed in the field, so it reaches this line ESCAPED: a bare
            # newline would forge a second line of this command's own output, a carriage return would
            # overwrite the line already printed, and an escape sequence would rewrite the terminal.
            lines.append(
                f"inherited unknown from the superseded receipt:"
                f" {escape_display(str(record.get('observation')))} about"
                f" {escape_display(str(record.get('subject')))}"
                f" ({escape_display(str(record.get('detail')))})"
            )
    lines.append(f"journal: {escape_display(str(journal_path))}")
    lines.append(
        f"superseded receipt {escape_display(active.receipt_id)} retained at"
        f" {escape_display(str(retained_prior))}"
    )
    lines.append(f"receipt: {escape_display(str(receipt_path))} (operation {OPERATION})")
    lines.append(
        f"active pointer {escape_display(str(config.active_receipt_path))} names "
        + (
            "this update's receipt"
            if run.pointer_replaced
            else f"the prior receipt {escape_display(active.receipt_id)}, which stays this plane's"
            " active statement"
        )
    )
    lines.append(
        "public_channel null and release_claim none: this update states no published release exists,"
        " and a completed update is evidence that authorizes no push, publication, PR mutation, merge,"
        " deployment, or any other outward effect"
    )
    sys.stdout.write("\n".join(lines) + "\n")


# ---- the run ---------------------------------------------------------------------------------------


def parse_argv(argv: list[str]) -> None:
    """This module owns no grammar; it admits exactly the empty vector its dispatcher forwards.

    A direct invocation with any other vector is a pre-effect refusal, not a usage error, because the
    dispatcher already owns usage and a second opinion here would report the same defect twice.
    """
    if argv:
        raise Refusal(
            f"ccodex sdlc update accepts no arguments; this module received"
            f" {[escape_display(item) for item in argv]}"
        )


def installer_config(bundle: ModuleType, config: Config, payload: AdmittedPayload) -> Any:
    """The installer Config this module borrows: the NEW payload root is the source of every copy.

    The same Config also carries the shared lifecycle lock, so this plane and ``bundle:install``
    serialize on one lock file rather than on two private ones.
    """
    return bundle.Config(
        payload.candidate_root,
        config.home,
        config.codex_home,
        ACTIVATION_MODE,
        False,
        HOST,
        config.installer_state_root,
    )


def run_update(config: Config, run: Run) -> int:
    """Admit both halves, plan, refresh, seal, then activate. Each phase refuses before the next."""
    admit_platform(config)
    instant = observe_instant(config)
    dar = load_sibling("distribution_activation_receipt")
    bundle = load_sibling("install_skill_bundle")

    active = admit_active_receipt(dar, config)
    selection = admit_new_payload(config, active)
    payload = selection.payload
    host_version = check_compatibility(config, payload)

    bconfig = installer_config(bundle, config, payload)
    if bundle.marketplace_overlap(config.home):
        raise Refusal(
            f"a Claude marketplace overlap is present under {show(str(config.plane_root))}; for Claude,"
            " use either direct installation or the marketplace, never both. The overlap blocks this"
            " Claude refresh and nothing was written"
        )

    receipt_id = receipt_identity(payload, instant)
    receipt_path = config.receipts_dir / f"{receipt_id}.json"
    journal_path = config.journals_dir / f"{OPERATION}-{payload.candidate_id}.json"

    with bundle.installer_lock(bconfig):
        try:
            state = bundle.load_config_state(bconfig)
        except bundle.InstallerError as exc:
            raise Refusal(f"the installer ownership state is not readable: {show(exc)}") from exc
        if state.get("version") == 1:
            raise Refusal(
                "the installer ownership state is still v1; explicit state migration is a separate"
                " operation and this update never performs one"
            )
        try:
            bundle.validate_state(bconfig, state)
        except bundle.InstallerError as exc:
            raise Refusal(f"the installer ownership state is not admissible: {show(exc)}") from exc

        planned = classify_footprint(bundle, bconfig, config, state, payload, active)
        refuse_blocked_entries(planned)

        plan_document = build_plan_document(config, payload, active, planned, host_version, instant)
        plan_raw = canonical_document_bytes(dar, plan_document, "the update plan")
        plan_sha256 = sha256_bytes(plan_raw)
        plan_path = config.plans_dir / f"{OPERATION}-{payload.candidate_id}-{plan_sha256[:12]}.json"
        write_replaceable_document(bundle, plan_path, plan_raw, "the update plan")

        if bundle.path_present(receipt_path):
            raise Refusal(
                f"this update's receipt {show(str(receipt_path))} already exists; a second run under"
                " one identity and instant is refused rather than repeated, and an outstanding unknown"
                " effect is an operator decision"
            )
        retained_prior = retain_prior_receipt(bundle, dar, config, active)

        def journal_bytes(phase: str, records: list[dict[str, Any]]) -> bytes:
            return canonical_document_bytes(
                dar,
                build_journal_document(
                    payload,
                    active,
                    plan_sha256,
                    bconfig.state_path,
                    receipt_id,
                    receipt_path,
                    retained_prior,
                    config.active_receipt_path,
                    phase,
                    records,
                ),
                "the update journal",
            )

        armed_records = [
            {
                "action": item.action,
                "class": item.classification,
                "dropped_by_new_payload": item.dropped,
                "entry_name": item.name,
                "phase": "armed",
                "prestate": item.prestate,
            }
            for item in planned
        ]
        write_replaceable_document(
            bundle, journal_path, journal_bytes("armed", armed_records), "the update journal"
        )
        checkpoint(config, "after-armed")

        # Everything above this line is a read or one of this module's own pre-effect documents. Below
        # it, the host plane can change.
        outcomes = refresh(bundle, bconfig, state, planned, run)
        checkpoint(config, "after-refresh")

        terminal_records = [
            {
                "action": ACTION_PRESERVE if outcome.disposition == DISPOSITION_PRESERVED else outcome.disposition,
                "detail": outcome.detail,
                "disposition": outcome.disposition,
                "entry_name": outcome.name,
                "phase": "recorded",
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
            raw = journal_bytes("effects-recorded", terminal_records)
            write_replaceable_document(bundle, journal_path, raw, "the update journal")
            journal_sha256 = sha256_bytes(raw)
        except Refusal as exc:
            # The effect already ran, so this is never a clean refusal: it is a missing binding, and
            # the receipt records the effect as unknown rather than complete.
            run.failures.append(f"the update journal could not be finalised: {escape_display(str(exc))}")
            journal_sha256 = None

        entries, unknowns = build_inventory(outcomes, journal_sha256)
        effect_state, terminal_phase = derive_effect_state(dar, run, journal_sha256, unknowns)
        body = build_receipt_body(
            dar, payload, entries, unknowns, plan_sha256, journal_sha256, effect_state, terminal_phase
        )
        receipt = seal_receipt(dar, body, payload, active, receipt_id, instant)
        receipt_raw = canonical_document_bytes(dar, receipt, "this update's receipt")
        write_new_document(bundle, receipt_path, receipt_raw, "this update's receipt")
        checkpoint(config, "after-receipt-sealed")

        # The prior receipt stays the plane's active statement until this update's own effect is
        # COMPLETE. A partial or unknown effect leaves the new receipt filed as evidence and the
        # pointer untouched, because a statement that claims an activation nobody completed is worse
        # than one an operator can still read.
        if not run.failures and effect_state == "complete":
            replace_active_pointer(bundle, config, receipt_raw)
            run.pointer_replaced = True
            checkpoint(config, "after-pointer-replaced")

    reassert_acquisition_receipts(selection, run.effect_started)
    report(
        config,
        payload,
        active,
        outcomes,
        planned,
        effect_state,
        terminal_phase,
        receipt_path,
        retained_prior,
        journal_path,
        run,
    )
    # Exit 0 requires all three halves: every claimed effect completed, the receipt sealed, and the
    # plane's active statement moved to it. An effect state the producer would not call complete is
    # exit 4 even with no failure recorded, because an observation nobody could make is not a
    # completion.
    if run.failures or effect_state != "complete" or not run.pointer_replaced:
        raise UnknownEffect(
            "this update did not complete every claimed effect and activate its own receipt: the"
            f" sealed receipt records effect_state {show(effect_state)} with terminal_phase"
            f" {show(terminal_phase)}, and the active pointer names"
            f" {'this update' if run.pointer_replaced else 'the prior receipt'}:"
            f" {'; '.join(run.failures) or 'an observation this run needed could not be made'}"
        )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """The dispatcher's entry point: always an ``int`` in the exit class 0-4, never a ``bool``."""
    selected = list(sys.argv[1:] if argv is None else argv)
    run = Run()
    try:
        parse_argv(selected)
        refuse_read_only_guard()
        return run_update(default_config(), run)
    except Refusal as exc:
        if run.effect_started:
            # A refusal raised after an effect started is not a clean refusal; reporting it as one
            # would claim an absence of effect nobody observed.
            print(f"error: ccodex sdlc update left an unknown effect: {escape_display(str(exc))}", file=sys.stderr)
            return EXIT_UNKNOWN
        print(
            f"error: ccodex sdlc update refused before any effect: {escape_display(str(exc))}",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    except UnknownEffect as exc:
        print(f"error: ccodex sdlc update left an unknown effect: {escape_display(str(exc))}", file=sys.stderr)
        return EXIT_UNKNOWN
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - includes the interrupt this walk must survive honestly
        if run.effect_started:
            print(
                f"error: ccodex sdlc update stopped after an effect started, so its effect is unknown:"
                f" {escape_display(repr(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(
            f"error: ccodex sdlc update stopped before any effect: {escape_display(repr(exc))}",
            file=sys.stderr,
        )
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
