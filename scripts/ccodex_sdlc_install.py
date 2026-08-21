#!/usr/bin/env python3
"""``ccodex sdlc install --host claude``: copy-activate ONE acquired candidate, then seal ONE receipt.

WHAT LOADS THIS FILE, AND WHAT IT MAY RETURN. ``scripts/ccodex_sdlc.py`` parses the closed
lifecycle grammar, refuses it, or loads this file by absolute non-symlink path and calls
``main(["--host", "claude"])``.  That reader owns no writer authority and this module owns no
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

  1. ADMIT ONE EXACT ACQUIRED CANDIDATE PAYLOAD.  The only admissible payload root today is the
     exactly acquired local candidate (Seed agentic-sdlc-0cce): one sealed
     ``release-candidate-acquisition-receipt/v1`` under the acquisition layout, terminal phase
     ``installed-unselected``, ``selection`` and ``activation`` both ``absent`` INSIDE the seal, and
     the candidate root at the exact path that receipt records.  There is no checkout payload, no
     archive payload, no ``--from`` and no discovery: an ambiguous receipts directory is refused
     rather than resolved.  The sealed acquisition receipt is READ and never written: its bytes are
     digested at admission and re-digested after the whole run, and a change is an unknown effect
     rather than a success.
  2. CHECK THE PAYLOAD'S OWN COMPATIBILITY CLAIMS.  ``policy/release-contract.v1.json`` inside the
     admitted payload declares the host it is about, an eligibility floor, and
     ``known_incompatible_host_versions``.  A DECLARED incompatibility with the observed host is
     refused BY NAME.  No other version is ever substituted for the observed one (Seed
     agentic-sdlc-0faa: a requested or nominated identity never becomes a readback), and an
     unobservable host version is refused rather than assumed compatible -- the receipt's closed
     ``unknowns`` vocabulary cannot even express "the host version was unknown", so admitting one
     would produce a document that silently omits an admission input it could not make.
  3. COPY-ACTIVATE THE CLAUDE-HOST ENTRIES TRANSACTIONALLY.  Copies, never links.  Every entry is
     classified ``absent``/``owned``/``foreign``/``modified`` BEFORE anything is written, and a
     ``foreign`` or ``modified`` entry is PRESERVED and NAMED in both the journal and the receipt
     inventory rather than adopted, replaced, or dropped.  There is no wildcard, no ``--all``, no
     purge, and no presence-based overwrite or delete.  The per-entry effect runs through the
     shipped installer's crash-consistent transactions, so an interruption leaves a recoverable
     journal plus an outstanding transaction record, never a half-state reported complete.
  4. SEAL ONE ``distribution-activation@1`` RECEIPT.  The sibling T1 producer derives both seals
     over the observation this module made: operation ``install``, the exact resolved candidate
     identity, the per-entry inventory with digests and prestates, the effect state and terminal
     phase taken from that module's OWN matrices, ``public_channel`` null, ``release_claim``
     ``none``, and exactly one ``derived-from`` ancestor naming the acquisition receipt's
     ``operation_id``.  An install carries NO ``supersedes`` ancestor: only an update replaces an
     earlier receipt.
  5. POINT THE PLANE AT THAT RECEIPT.  ``activation/active-receipt.json`` is the only statement of
     what this plane owns, and it is the admission every later verb reads: ``ccodex sdlc update``
     and ``ccodex sdlc uninstall`` admit that pointer and nothing else, so an install that sealed a
     receipt without writing it left a plane no later verb could act on.  The order is fixed and is
     the same order ``ccodex sdlc update`` uses: the receipt is written create-only and DURABLY
     first, and only then is the pointer replaced atomically, so there is no window in which the
     pointer names a receipt no directory holds.  A partial or unknown effect files the receipt as
     evidence and leaves the pointer ALONE -- a pointer that claims an activation nobody completed
     is worse than an absent one -- and exit 0 therefore requires all three halves: every claimed
     effect complete, the receipt sealed, and the pointer naming it.

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
from typing import Any

# ---- exit classes ---------------------------------------------------------------------------------

#: The receipt sealed and every claimed effect completed durably.
EXIT_OK = 0
#: A clean refusal BEFORE any effect, named.
EXIT_REFUSED = 3
#: An effect was admitted and its completion or its evidence cannot be claimed.
EXIT_UNKNOWN = 4

HOST = "claude"
HOST_ARGV = ("--host", HOST)
OPERATION = "install"
#: One lowercase token naming the part of the host plane this operation touches. Wildcards are
#: refused by the receipt producer BY NAME, and nothing here would ever construct one.
ACTIVATION_SCOPE = "claude-home"
EMITTING_PLANE = "acquired-candidate"
ENTRY_AGENT = "claude"
#: Copies, never links: the activation plane must not depend on a checkout that can move or vanish.
ACTIVATION_MODE = "copy"
#: The version this activation resolved was READ from the candidate manifest, not from an adapter
#: readback and never from a request.
VERSION_SOURCE = "archive-manifest"

# ---- re-expressed contracts, each pinned by a test against the shipped artifact -------------------

#: The acquisition receipt's closed key set, re-expressed from
#: policy/release-candidate-acquisition.v1.json -> records.schemas.immutable_receipt.required_keys.
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
ACQUISITION_POLICY_NAME = "release-candidate-acquisition.v1.json"
#: The acquisition layout, re-expressed from that policy's ``filesystem.layout``.
ACQUISITION_RECEIPT_SEGMENTS = ("agentic-sdlc", "acquisition", "receipts")
ACQUISITION_CANDIDATE_SEGMENTS = ("agentic-sdlc", "acquisition", "candidates")
ACQUISITION_CANDIDATE_LEAF = "root"
#: This module's own artifacts live beside the acquisition plane's, under the same state home.
ACTIVATION_SEGMENTS = ("agentic-sdlc", "activation")
#: The plane's ONE active statement, re-expressed from the same name ``ccodex sdlc update`` and
#: ``ccodex sdlc uninstall`` admit. Those verbs admit this document and nothing else, so this is the
#: name an install must land for the plane to have a front door at all.
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
#: The host the contract's core compatibility row is ABOUT. ``--host claude`` selects the Claude
#: Code host plane, and the contract spells that host ``claude-code``.
RELEASE_CONTRACT_HOST = "claude-code"

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
            f"ccodex sdlc install requires the sibling module {show(str(path))}, which is absent or"
            " is a link"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_install_{stem}", path)
    if spec is None or spec.loader is None:
        raise Refusal(f"ccodex sdlc install cannot load the sibling module {show(str(path))}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an import failure here is still pre-effect
        raise Refusal(
            f"ccodex sdlc install cannot import the sibling module {show(str(path))}: {show(exc)}"
        ) from exc
    return module


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
    """Refuse an uncertified platform BY NAME rather than attempting a linux-x64 payload on it."""
    system, machine = observe_platform(config)
    if system != SUPPORTED_SYSTEM:
        raise Refusal(
            f"ccodex sdlc install --host claude activates a {CANDIDATE_PLATFORM} candidate and is"
            f" certified only on {SUPPORTED_SYSTEM}; the observed operating system is"
            f" {show(system)}. Another platform is refused rather than attempted"
        )
    if machine.lower() not in SUPPORTED_MACHINES:
        raise Refusal(
            f"ccodex sdlc install --host claude activates a {CANDIDATE_PLATFORM} candidate; the"
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


def admit_acquisition_receipt(config: Config) -> tuple[Path, bytes, dict[str, Any], str]:
    """Admit exactly ONE sealed acquisition receipt, or refuse the ambiguity by name."""
    receipts_dir = config.acquisition_receipts_dir
    if not receipts_dir.is_dir() or receipts_dir.is_symlink():
        raise Refusal(
            f"no acquired candidate is available: the acquisition receipts directory"
            f" {show(str(receipts_dir))} is absent or is not an exact directory. Acquire a"
            " candidate first; this operation never acquires one"
        )
    try:
        names = sorted(item.name for item in receipts_dir.iterdir())
    except OSError as exc:
        raise Refusal(
            f"the acquisition receipts directory {show(str(receipts_dir))} cannot be listed:"
            f" {show(exc)}"
        ) from exc
    candidates = [name for name in names if name.endswith(".json") and _HEX64.match(name[: -len(".json")])]
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


def admit_payload(config: Config) -> AdmittedPayload:
    """Phase 1, whole: exactly one acquired candidate, its exact root, and its manifest identity."""
    receipt_path, raw, receipt, archive_sha256 = admit_acquisition_receipt(config)
    candidate_root = admit_candidate_root(config, receipt, archive_sha256)
    manifest, candidate_id, version = admit_candidate_manifest(candidate_root)
    inventory = manifest_inventory(manifest, candidate_root)
    return AdmittedPayload(
        receipt_path=receipt_path,
        receipt_bytes=raw,
        receipt=receipt,
        archive_sha256=archive_sha256,
        operation_id=str(receipt["operation_id"]),
        candidate_root=candidate_root,
        manifest=manifest,
        candidate_id=candidate_id,
        resolved_version=version,
        inventory=inventory,
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
    """Observe the Claude Code host version, or take the injected observation.

    The default observation runs the host's own ``--version`` once, with no shell, a bounded
    timeout, and an argument vector.  ``shutil.which`` is consulted rather than the ambient PATH
    being reshaped, because a test that strips PATH tests the developer's machine instead.  A host
    that cannot be observed yields ``None``, which is a DIFFERENT input from ``UNSUPPLIED``.
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
            " this activation cannot check the host it is about"
        )
    return contract


def _version_tuple(value: object, subject: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _SEMVER.match(value):
        raise Refusal(f"{subject} is {show(value)}, not a three-part SemVer of ASCII digits")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def check_compatibility(config: Config, payload: AdmittedPayload) -> str:
    """Refuse a DECLARED incompatibility by name; never substitute another version for the observed.

    Three separate refusals, because collapsing them hides which half of the question was
    unanswerable: the contract is about another host, the observed version is a version the payload
    DECLARES incompatible, or the observed version is below the declared eligibility floor.  A host
    version that could not be observed is refused too: the activation receipt's closed unknowns
    vocabulary has no way to say "the host version was unknown", so admitting one would seal a
    document that silently omits an admission input.
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
            f" {show(declared_host)}, not {show(RELEASE_CONTRACT_HOST)}; --host claude selects the"
            " Claude Code host plane and this operation activates no other one"
        )
    known = compatibility.get("known_incompatible_host_versions")
    if not isinstance(known, list):
        raise Refusal(
            "the payload's release contract carries no compatibility."
            "known_incompatible_host_versions list, so a declared incompatibility could not be read"
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
                f"compatibility.known_incompatible_host_versions[{ordinal}].reason is"
                f" {show(reason)}, not a non-empty string"
            )
        incompatible[str(version)] = reason

    observed = observe_host_version(config)
    if observed is None:
        raise Refusal(
            "the Claude Code host version could not be observed, so the payload's declared"
            " compatibility claims cannot be checked against this host. This operation refuses"
            " rather than assuming compatibility, and it never substitutes another version for the"
            " observed one"
        )
    if not isinstance(observed, str) or not _SEMVER.match(observed):
        raise Refusal(
            f"the observed Claude Code host version {show(observed)} is not a three-part SemVer, so"
            " it cannot be compared with the payload's declared claims"
        )
    if observed in incompatible:
        raise Refusal(
            f"the payload DECLARES the observed Claude Code host version {show(observed)}"
            f" incompatible: {show(incompatible[observed])}. A declared incompatibility is refused"
            " by name, and no other host version is substituted for the observed one"
        )
    floor = _version_tuple(core.get("minimum_host_version"), "compatibility.core.minimum_host_version")
    if _version_tuple(observed, "the observed Claude Code host version") < floor:
        raise Refusal(
            f"the observed Claude Code host version {show(observed)} is below the payload's"
            f" declared eligibility floor {show(core.get('minimum_host_version'))}; meeting that"
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
    #: Whether ``activation/active-receipt.json`` now names THIS run's receipt. False is the honest
    #: default: an unreplaced pointer is never reported as an activation, and exit 0 requires it.
    pointer_replaced: bool = False


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


def verify_entry_against_manifest(payload: AdmittedPayload, source: Path) -> None:
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
            f"the candidate payload carries {show(name)}, which its manifest does not inventory, so"
            " this activation would copy content the payload's own identity does not cover"
        )
    for name in sorted(inventoried - set(observed)):
        raise Refusal(
            f"the candidate manifest inventories {show(name)}, which is absent from the payload, so"
            " the admitted candidate is not the payload its manifest describes"
        )
    for name in sorted(observed):
        path = observed[name]
        row = payload.inventory[name]
        kind = node_kind(path)
        if row.get("type") != kind:
            raise Refusal(
                f"the candidate payload node {show(name)} is a {kind} while its manifest row"
                f" declares {show(row.get('type'))}"
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


def classify_entries(
    bundle: ModuleType,
    bundle_config: Any,
    state: dict[str, Any],
    payload: AdmittedPayload,
) -> list[PlannedEntry]:
    """Per-entry prestate classification, entirely before any write.

    ``foreign`` and ``modified`` are PRESERVED and NAMED here, never adopted, replaced, or dropped:
    an inventory that omitted them would read as a clean activation of a collided plane.  There is
    no wildcard, no presence-based overwrite, and no delete anywhere in this function.
    """
    discovered = [
        entry
        for entry in bundle.discover_entries(payload.candidate_root)
        if entry.agent == ENTRY_AGENT
    ]
    if not discovered:
        raise Refusal(
            f"the admitted candidate payload at {show(str(payload.candidate_root))} carries no"
            " claude-host entries, so there is nothing this activation could copy"
        )
    outstanding = sorted(state.get("transactions", {}))
    if outstanding:
        raise Refusal(
            "the installer ownership state holds"
            f" {len(outstanding)} outstanding lifecycle transaction(s), the first being"
            f" {show(outstanding[0])}; recovery is a separate explicit operation and this activation"
            " never resolves one"
        )
    planned: list[PlannedEntry] = []
    for entry in discovered:
        verify_entry_against_manifest(payload, entry.source)
        try:
            destination = bundle.destination_for(entry, bundle_config)
            bundle.assert_safe_collection(entry, destination, bundle_config)
            agent_root = bundle.agent_root(entry, bundle_config)
        except bundle.InstallerError as exc:
            raise Refusal(f"the claude activation destination is not admissible: {show(exc)}") from exc
        name = entry_display_name(destination, agent_root)
        key = str(destination)
        record = state.get("entries", {}).get(key)
        if isinstance(record, dict):
            planned.append(_classify_owned(bundle, bundle_config, entry, destination, name, key, record))
            continue
        if bundle.path_present(destination):
            planned.append(
                PlannedEntry(
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
        "activation_scope": ACTIVATION_SCOPE,
        "archive_sha256": payload.archive_sha256,
        "candidate_id": payload.candidate_id,
        "candidate_root": str(payload.candidate_root),
        "claude_root": str(config.home / ".claude"),
        "entries": rows,
        "host": HOST,
        "mode": ACTIVATION_MODE,
        "observed_host_version": host_version,
        "operation": OPERATION,
        "planned_at": instant,
        "public_channel": None,
        "release_claim": "none",
        "resolved_version": payload.resolved_version,
        "schema_version": PLAN_SCHEMA,
        "version_source": VERSION_SOURCE,
    }


def build_journal_document(
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
        "host": HOST,
        "installer_state_path": str(installer_state_path),
        "operation": OPERATION,
        "phase": phase,
        "plan_sha256": plan_sha256,
        "schema_version": JOURNAL_SCHEMA,
    }


# ---- phase 3c: the transactional copy-activation ---------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """One entry's observed outcome, with the content digest that lands in the receipt inventory."""

    name: str
    prestate: str
    disposition: str
    detail: str
    content_sha256: str | None
    unknown_detail: str | None


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
        run.effect_started = True
        try:
            bundle.ensure_collection(item.entry, item.destination, bundle_config)
            root_token, collection_token = bundle.authority_tokens(
                item.entry, item.destination, bundle_config
            )
            if item.action == ACTION_INSTALL:
                mode = bundle.transactional_create(
                    item.entry, item.destination, bundle_config, state, root_token, collection_token
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
    payload: AdmittedPayload,
    entries: list[dict[str, Any]],
    unknowns: list[dict[str, Any]],
    plan_sha256: str,
    journal_sha256: str | None,
    effect_state: str,
    terminal_phase: str,
) -> dict[str, Any]:
    """Write the closed ``distribution-activation-body@1`` observation from already-built locals.

    Both lists arrive complete from ``build_inventory``, which is the whole point: nothing is
    discovered while this literal is being evaluated, so nothing can be dropped by the order in which
    Python evaluates it.
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
        "record_sha256": "",
        "release_claim": "none",
        # A request is not a readback (Seed agentic-sdlc-0faa). This grammar carries no version
        # request at all, and null says so rather than leaving the key absent.
        "requested_version": None,
        "resolved_version": payload.resolved_version,
        "schema_version": receipts.BODY_SCHEMA,
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


def receipt_identity(payload: AdmittedPayload, instant: str) -> str:
    """One lowercase token identifying this receipt, derived from facts and never from a counter."""
    compact = instant.replace("-", "").replace(":", "").lower()
    token = f"{OPERATION}-{payload.operation_id}-{compact}"
    if not re.match(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z", token):
        raise Refusal(f"the derived receipt identity {show(token)} is not a lowercase ASCII token")
    return token


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


def parse_argv(argv: list[str]) -> None:
    """This module owns no grammar; it admits exactly the vector its dispatcher forwards.

    A direct invocation with any other vector is a pre-effect refusal, not a usage error, because
    the dispatcher already owns usage and a second opinion here would report the same defect twice.
    """
    if tuple(argv) != HOST_ARGV:
        raise Refusal(
            f"ccodex sdlc install admits exactly {list(HOST_ARGV)}; this module received"
            f" {[escape_display(item) for item in argv]}"
        )


def run_install(config: Config, run: Run) -> int:
    """The four phases, in order, each refusing by name before the next could move anything."""
    parsed_host = HOST
    admit_platform(config)
    instant = observe_instant(config)
    receipts = load_sibling("distribution_activation_receipt")
    bundle = load_sibling("install_skill_bundle")

    payload = admit_payload(config)
    host_version = check_compatibility(config, payload)

    bundle_config = bundle.Config(
        payload.candidate_root,
        config.home,
        config.codex_home,
        ACTIVATION_MODE,
        False,
        parsed_host,
        config.installer_state_root,
    )
    if bundle.marketplace_overlap(config.home):
        raise Refusal(
            f"a Claude marketplace overlap is present under {show(str(config.home / '.claude'))};"
            " for Claude, use either direct installation or the marketplace, never both. The"
            " overlap blocks this Claude activation and nothing was written"
        )

    with bundle.installer_lock(bundle_config):
        try:
            state = bundle.load_config_state(bundle_config)
        except bundle.InstallerError as exc:
            raise Refusal(f"the installer ownership state is not readable: {show(exc)}") from exc
        if state.get("version") == 1:
            raise Refusal(
                "the installer ownership state is still v1; explicit state migration is a separate"
                " operation and this activation never performs one"
            )
        try:
            bundle.validate_state(bundle_config, state)
        except bundle.InstallerError as exc:
            raise Refusal(f"the installer ownership state is not admissible: {show(exc)}") from exc

        planned = classify_entries(bundle, bundle_config, state, payload)
        plan_document = build_plan_document(config, payload, planned, host_version, instant)
        plan_raw = canonical_document_bytes(receipts, plan_document, "the activation plan")
        plan_sha256 = sha256_bytes(plan_raw)
        plan_path = config.plans_dir / f"{OPERATION}-{payload.candidate_id}-{plan_sha256[:12]}.json"
        write_replaceable_document(bundle, plan_path, plan_raw, "the activation plan")

        journal_path = config.journals_dir / f"{OPERATION}-{payload.candidate_id}.json"
        armed_records = [
            {"action": item.action, "entry_name": item.name, "phase": "armed", "prestate": item.prestate}
            for item in planned
        ]
        armed_raw = canonical_document_bytes(
            receipts,
            build_journal_document(
                payload, plan_sha256, bundle_config.state_path, "armed", armed_records
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
                    payload, plan_sha256, bundle_config.state_path, "terminal", terminal_records
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
            payload,
            entries,
            unknowns,
            plan_sha256,
            journal_sha256,
            effect_state,
            terminal_phase,
        )
        receipt_id = receipt_identity(payload, instant)
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
    report(config, payload, outcomes, effect_state, terminal_phase, receipt_path, run)
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


def report(
    config: Config,
    payload: AdmittedPayload,
    outcomes: list[Outcome],
    effect_state: str,
    terminal_phase: str,
    receipt_path: Path,
    run: Run,
) -> None:
    """One line per fact, every artifact-derived value escaped, and no claim beyond the evidence."""
    lines = [
        f"ccodex sdlc install --host {HOST}: effect {escape_display(effect_state)},"
        f" terminal {escape_display(terminal_phase)}",
        f"candidate {escape_display(payload.candidate_id[:12])} resolved"
        f" {escape_display(payload.resolved_version)} via {VERSION_SOURCE}"
        f" (requested: no version was requested)",
        f"claude root: {escape_display(str(config.home / '.claude'))} (copies, never links)",
    ]
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


def main(argv: list[str] | None = None) -> int:
    """The dispatcher's entry point: always an ``int`` in the exit class 0-4, never a ``bool``."""
    selected = list(sys.argv[1:] if argv is None else argv)
    run = Run()
    try:
        parse_argv(selected)
        return run_install(default_config(), run)
    except Refusal as exc:
        if run.effect_started:
            # A refusal raised after an effect started is not a clean refusal; reporting it as one
            # would claim an absence of effect nobody observed.
            print(
                f"error: ccodex sdlc install left an unknown effect: {escape_display(str(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(f"error: ccodex sdlc install refused before any effect: {escape_display(str(exc))}", file=sys.stderr)
        return EXIT_REFUSED
    except UnknownEffect as exc:
        print(f"error: ccodex sdlc install left an unknown effect: {escape_display(str(exc))}", file=sys.stderr)
        return EXIT_UNKNOWN
    except Exception as exc:  # noqa: BLE001 - classified against the one fact that decides the class
        if run.effect_started:
            print(
                f"error: ccodex sdlc install failed after an effect started, so its effect is"
                f" unknown: {escape_display(repr(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(
            f"error: ccodex sdlc install failed before any effect: {escape_display(repr(exc))}",
            file=sys.stderr,
        )
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
