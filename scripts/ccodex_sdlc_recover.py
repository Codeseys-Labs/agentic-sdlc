#!/usr/bin/env python3
"""``ccodex sdlc recover --apply <plan-sha256>``: the one mutating form of the recover verb.

THE APPROVAL IS THE DIGEST.  ``recover --dry-run`` derives a canonical, digest-bound recovery plan
from the same journal and receipt evidence this module reads, renders that digest to the operator,
and changes nothing.  Applying is a separate act: the operator hands back the exact digest they
approved, this module RE-DERIVES the plan from verified state at apply time, and refuses by name
when the re-derived digest differs -- state moved, or the approved plan is stale.  A digest is
therefore an approval of one exact plan, never a standing permission to recover whatever is found.

The plan derivation in this file is the ONE derivation both sides use: the reader loads this module
as an optional sibling and calls ``derive_plan`` to render the digest, so there is no second
spelling of the plan that could disagree with the one an ``--apply`` re-derives.  Deriving is pure
observation -- it reads, classifies, and digests, and it writes nothing -- which is why the reader
may call it while its process-wide read-only guard is installed.

Resume and roll back happen ONLY through the reused substrate's own machinery
(``install_skill_bundle.classify_recovery`` / ``execute_recovery`` / ``recover_transactions`` for the
bundle journal, ``install_operator_tools.recover_pending`` for the operator-tools journal).  This
module classifies, admits, and reports; it invents no repair of its own.  Foreign, modified,
ambiguous, and unknown-effect state is preserved and NAMED rather than overwritten or deleted.

A completed recovery is evidence, never authorization: no push, publication, PR mutation, merge, or
deployment follows from it.  ``public_channel`` stays null and the release claim stays ``none``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import stat
import sys
from types import ModuleType
from typing import Any


# ---- exit classes ---------------------------------------------------------------------------------

#: Every selected transition reached a durable terminal state and nothing was preserved unhandled.
EXIT_RECOVERED = 0
#: A clean refusal BEFORE any effect, named.
EXIT_REFUSED = 3
#: An ADMITTED PARTIAL EFFECT: recovery ran, and something the operator must look at was preserved and
#: named, so not every selected transition reached a durable terminal state.  Spec Implementation
#: Decision 9 assigns 4 to "an admitted partial or unknown effect" and 1 to "unexpected internal
#: failure"; a named preservation is neither unexpected nor internal, so the value is 4, spelled with
#: this repository's own name for that class (``gate_baseline``/``gate_receipt`` both use
#: ``EXIT_PARTIAL = 4``).  It was 1 for one release (agentic-sdlc-d7b3).
EXIT_PARTIAL = 4
#: An effect was admitted and its completion cannot be claimed.  It shares exit 4 with
#: ``EXIT_PARTIAL`` because Decision 9 has ONE class for both admitted-effect states; the two
#: constants stay distinct because the reported lines distinguish them.
EXIT_UNKNOWN = 4

HOST = "claude"
OPERATION = "recover"
APPLY_FLAG = "--apply"

#: The plan's own schema. The reader re-expresses this string and declines the digest dimension when
#: the two disagree, so a drifted plan shape is NAMED rather than silently digested as if unchanged.
PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-recovery-plan@1"

#: Recovery moves an activated linux-x64 plane. Another platform refuses BY NAME (ADR/0cce), because
#: an uncertified attempt at a half-finished transition is exactly the state nobody can undo.
SUPPORTED_SYSTEM = "Linux"
SUPPORTED_MACHINES = ("x86_64", "amd64")

#: The activation receipts this host recorded, under the operator's own XDG state root: the same
#: plane the reader observes, resolved from the same two segments.
STATE_PLANE_DIRECTORY = "agentic-sdlc"
ACTIVATION_RECEIPTS = ("activation", "receipts")

#: A journal is kilobytes and a receipt is smaller. The ceilings mean an oversized or truncated
#: document is NAMED instead of being read into this process, and the document bound means an
#: unbounded directory cannot turn a bounded read into a scan.
MAX_JOURNAL_BYTES = 4194304
MAX_RECEIPT_BYTES = 65536
MAX_RECEIPT_DOCUMENTS = 64

#: Written out rather than spelled with a regex digit class: ``\d`` admits the Arabic-Indic ``٩``, so
#: a digest spelled in it would read as the same value while comparing unequal to it.
_HEX_CHARACTERS = "0123456789abcdef"
_DIGIT_CHARACTERS = "0123456789"
_TOKEN_CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789"

#: The activation-receipt filename grammar THIS PLANE'S OWN lifecycle verbs derive.
#: ``ccodex_sdlc_install`` and ``ccodex_sdlc_update`` file ``<verb>-<operation-id>-<compact
#: instant>.json``, each validated as one lowercase ASCII token by the module that writes it, and
#: ``ccodex_sdlc_uninstall`` files ``uninstall-<the receipt id it retired>.json``.  Recognising exactly
#: this shape is recognising this host's own evidence; it is NOT a general "looks like a filename"
#: test.  The anchors are what keep it narrow: an operator's own neighbour in the plane
#: (``operator-notes.json``, or a name that happens to carry a credential-shaped string) matches no
#: verb prefix and no trailing instant, stays unrecognised, and is refused without its name being
#: echoed (agentic-sdlc-3bb8).
LIFECYCLE_RECEIPT_VERBS = ("install", "update")
RETIREMENT_RECEIPT_PREFIX = "uninstall-"
_ESCAPES = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}

#: Journal document states. ``absent`` is a state, not a defect: a host that never installed has no
#: journal. Everything else that is not ``present`` is state this module refuses to act through.
JOURNAL_PRESENT = "present"
JOURNAL_ABSENT = "absent"
JOURNAL_BLOCKING_STATES = ("irregular", "oversized", "symlinked", "unreadable")

#: Item actions. ``preserve`` is a first-class outcome, not a failure to act.
ACTION_RESUME_TRANSACTION = "resume-transaction"
ACTION_RESUME_PENDING = "resume-pending"

CONFLICT = "conflict"


class Refusal(RuntimeError):
    """Declined BEFORE any effect could occur: exit class 3, always named."""


class UnknownEffect(RuntimeError):
    """An effect was admitted, so no absence of effect can be claimed: exit class 4."""


class PlanUnavailable(RuntimeError):
    """The plan could not be derived, so no digest may be rendered or compared."""


# ---- rendering -------------------------------------------------------------------------------------


def escape_display(value: str) -> str:
    """Escape every control character before an artifact- or filesystem-derived value is rendered.

    Re-expressed from the receipt family's own rule rather than imported, because this module must
    still name a refusal when the sibling that owns that rule is absent.  DEL (0x7f) is included
    because a naive ``< 0x20`` test passes it, and a bare ``\\r`` would overwrite the line already
    printed rather than adding one.
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


# ---- canonical serialization ------------------------------------------------------------------------


def canonical_document(value: object) -> str:
    """This repository's one canonical JSON spelling, trailing newline included.

    ``allow_nan=False`` is load-bearing: a plan that carried ``Infinity`` would serialize to a token
    no strict reader admits, so the digest would pin a document nobody could read back.
    """
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan_digest(plan: dict[str, Any]) -> str:
    """The sha256 over the plan's canonical bytes: the operator's approval token."""
    return sha256_bytes(canonical_document(plan).encode("utf-8"))


def is_plan_digest(value: object) -> bool:
    """Exactly 64 lowercase hexadecimal characters, tested by membership and never by ``\\d``."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX_CHARACTERS for character in value)
    )


def is_compact_instant(value: str) -> bool:
    """``YYYYMMDDThhmmssZ`` lowercased: the exact trailing token the lifecycle verbs derive.

    ``receipt_identity`` in both writing modules builds it as the receipt's stated instant with the
    separators stripped and the whole token lowercased.  Tested by digit MEMBERSHIP rather than with
    ``[0-9]`` inside a ``\\d`` class, so a name spelled with the Arabic-Indic ``٩`` is not admitted as
    the same shape while comparing unequal to it.
    """
    if len(value) != 16 or value[8] != "t" or value[15] != "z":
        return False
    return all(character in _DIGIT_CHARACTERS for character in value[:8] + value[9:15])


def is_operation_token(value: str) -> bool:
    """One lowercase ASCII token -- ``[a-z0-9]([a-z0-9-]*[a-z0-9])?`` -- spelled by membership.

    This is the operation-id shape the writing modules validate before they name a receipt.  A leading
    or trailing ``-`` is refused, and ``.`` and every separator are outside the admitted set, so a
    recognised stem can never traverse out of the directory it was listed from.
    """
    if not value or value[0] not in _TOKEN_CHARACTERS or value[-1] not in _TOKEN_CHARACTERS:
        return False
    return all(character in _TOKEN_CHARACTERS or character == "-" for character in value)


def is_lifecycle_receipt_stem(value: str) -> bool:
    """Is this stem a name this plane's OWN lifecycle verbs derive for an activation receipt?

    ``install-<operation-id>-<compact instant>``, ``update-<operation-id>-<compact instant>``, and
    ``uninstall-`` prefixed onto either of those.  Anchored at BOTH ends on purpose: an unanchored
    "lowercase token" test would admit any hyphenated neighbour an operator dropped in the plane, and
    naming such a document would both echo a name that is not ours to echo and read foreign content as
    this host's evidence.
    """
    if value.startswith(RETIREMENT_RECEIPT_PREFIX):
        value = value[len(RETIREMENT_RECEIPT_PREFIX) :]
    for verb in LIFECYCLE_RECEIPT_VERBS:
        if not value.startswith(f"{verb}-"):
            continue
        remainder = value[len(verb) + 1 :]
        operation, separator, instant = remainder.rpartition("-")
        return bool(separator) and is_operation_token(operation) and is_compact_instant(instant)
    return False


def plane_locator(prefix: str, name: str) -> str:
    """One deterministic locator for a plane document, opaque when the NAME is not ours to echo.

    Two name shapes carry no operator content and are therefore kept verbatim: ``<64 lowercase
    hex>.json``, and the activation-receipt grammar the lifecycle verbs themselves derive
    (``is_lifecycle_receipt_stem``).  Keeping the second is the fix for agentic-sdlc-3bb8: those are
    the receipts THIS host filed, so treating them as unnameable made every real activation's plane
    unverifiable and left an interrupted transaction with no executable recovery.  Anything else is
    named by a digest of itself, which stays stable across runs and distinguishes two unrecognised
    neighbours without republishing either name.
    """
    stem = name[:-5] if name.endswith(".json") else ""
    if is_plan_digest(stem) or is_lifecycle_receipt_stem(stem):
        return f"{prefix}://{stem}"
    digest = hashlib.sha256(name.encode("utf-8", "surrogatepass")).hexdigest()
    return f"{prefix}://unrecognised-{digest[:16]}"


# ---- bounded, link-refusing document reads ----------------------------------------------------------


def read_bounded_document(path: Path, limit: int) -> tuple[bytes | None, str]:
    """Read one document read-only, or NAME the state that stopped the read. Never follows a link.

    ``lstat`` before the open is load-bearing twice: a symlink is a redirected state surface this
    module reports instead of following, and opening a FIFO would block until a writer that may never
    arrive.  The size is bounded before and after the read, so a document that grows between the two
    is named rather than read.
    """
    try:
        item = path.lstat()
    except FileNotFoundError:
        return None, JOURNAL_ABSENT
    except OSError:
        return None, "unreadable"
    if stat.S_ISLNK(item.st_mode):
        return None, "symlinked"
    if not stat.S_ISREG(item.st_mode):
        return None, "irregular"
    if item.st_size > limit:
        return None, "oversized"
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError:
        return None, "unreadable"
    if len(raw) > limit:
        return None, "oversized"
    return raw, JOURNAL_PRESENT


def observe_journal(component: str, slug: str, path: Path) -> dict[str, Any]:
    """One journal document observed as a state plus, when present, the digest of its exact bytes.

    The digest is what makes an approval SPECIFIC.  An opaque locator alone would survive a phase
    advancing from ``armed`` to ``cleanup``; the bytes do not, so a plan approved against one
    journal cannot be applied against another.
    """
    raw, state = read_bounded_document(path, MAX_JOURNAL_BYTES)
    return {
        "component": component,
        "digest": sha256_bytes(raw) if raw is not None else None,
        "locator": f"journal://{slug}",
        "state": state,
    }


def receipt_names(directory: Path) -> tuple[list[str], str]:
    """List the activation receipts plane's candidate documents, bounded and sorted, or name why not."""
    try:
        item = directory.lstat()
    except FileNotFoundError:
        return [], JOURNAL_ABSENT
    except OSError:
        return [], "unreadable"
    if stat.S_ISLNK(item.st_mode):
        return [], "symlinked"
    if not stat.S_ISDIR(item.st_mode):
        return [], "irregular"
    try:
        names = sorted(entry.name for entry in os.scandir(directory) if entry.name.endswith(".json"))
    except OSError:
        return [], "unreadable"
    if len(names) > MAX_RECEIPT_DOCUMENTS:
        return names[:MAX_RECEIPT_DOCUMENTS], "overfull"
    return names, "observed"


def observe_receipts(directory: Path) -> dict[str, Any]:
    """Observe the activation receipts plane: bounded, sorted, opaque, and by exact bytes.

    Only the plane's identity is taken here.  Whether a receipt's SEAL validates is a separate
    question, asked once at apply time through the family's own validator, because a digest over
    bytes must not depend on an optional sibling being present.
    """
    names, state = receipt_names(directory)
    if state in (JOURNAL_ABSENT, "unreadable", "symlinked", "irregular"):
        return {"documents": [], "state": state}
    documents: list[dict[str, Any]] = []
    for name in names:
        raw, document_state = read_bounded_document(directory / name, MAX_RECEIPT_BYTES)
        documents.append(
            {
                "digest": sha256_bytes(raw) if raw is not None else None,
                "locator": plane_locator("activation-receipt", name),
                "state": document_state,
            }
        )
    if not documents and state == "observed":
        state = JOURNAL_ABSENT
    return {"documents": documents, "state": state}


# ---- the ONE plan derivation ------------------------------------------------------------------------


def bundle_items(bundle: ModuleType, bundle_config: Any, journal: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify each interrupted bundle transaction that selects this configured home.

    The locator is the reused installer's OWN read-only locator, so a plan item names exactly the
    proposal the operator already saw in ``recover --dry-run`` rather than a second numbering.  The
    classification is ``classify_recovery``'s own verdict, so a layout whose witnesses are no longer
    exact appears here as ``conflict`` -- preserved and named, never acted through.
    """
    if journal["state"] != JOURNAL_PRESENT:
        return []
    raw, _state = read_bounded_document(Path(journal["path"]), MAX_JOURNAL_BYTES)
    if raw is None:
        raise PlanUnavailable("the bundle journal became unreadable while the plan was being derived")
    try:
        state = bundle._readonly_json_document(raw, Path(journal["path"]))
    except Exception as exc:  # noqa: BLE001 - a malformed journal states no plan, it is not a crash
        raise PlanUnavailable(f"the bundle journal is not one strict JSON object ({show(exc)})") from exc
    if set(state) != {"version", "entries", "transactions"} or state.get("version") != bundle.STATE_VERSION:
        raise PlanUnavailable("the bundle journal is not one readable current-version document")
    try:
        bundle.validate_state(bundle_config, state)
    except Exception as exc:  # noqa: BLE001 - the substrate's own verdict on its own journal
        raise PlanUnavailable(f"the bundle journal does not validate ({show(exc)})") from exc
    transactions = state["transactions"]
    selected: list[dict[str, Any]] = []
    for key in sorted(transactions):
        transaction = transactions[key]
        records = bundle.transaction_configured_records(transaction, bundle_config)
        if not records:
            continue
        selected.append({"record": records[0], "transaction": transaction})
    items: list[dict[str, Any]] = []
    for ordinal, entry in enumerate(selected, start=1):
        items.append(
            {
                "action": ACTION_RESUME_TRANSACTION,
                "classification": bundle.classify_recovery(entry["transaction"], bundle_config),
                "component": "bundle",
                "path": bundle._readonly_locator("transaction", entry["record"], ordinal),
            }
        )
    return items


def operator_tools_items(
    operator_tools: ModuleType, operator_config: Any, journal: dict[str, Any]
) -> list[dict[str, Any]]:
    """Observe the operator-tools pending transition without deciding its outcome here.

    ``recover_pending`` owns the decision and it fsyncs the containing directory on the way in, which
    the reader's read-only guard would block, so this derivation records only what is OBSERVABLE: the
    recorded operation and which of the two recorded contents the live file matches.  That is enough
    to make the digest move when the file moves, and it leaves the verdict with the substrate.
    """
    if journal["state"] != JOURNAL_PRESENT:
        return []
    raw, _state = read_bounded_document(Path(journal["path"]), MAX_JOURNAL_BYTES)
    if raw is None:
        raise PlanUnavailable("the operator-tools journal became unreadable while the plan was derived")
    try:
        state = operator_tools._readonly_json_document(raw, Path(journal["path"]))
    except Exception as exc:  # noqa: BLE001 - a malformed journal states no plan
        raise PlanUnavailable(
            f"the operator-tools journal is not one strict JSON object ({show(exc)})"
        ) from exc
    if set(state) != {"version", "entries", "pending"} or state.get("version") != operator_tools.STATE_VERSION:
        raise PlanUnavailable("the operator-tools journal is not one readable current-version document")
    pending = state["pending"]
    if pending is None:
        return []
    try:
        operator_tools.validate_pending(operator_config, state)
    except Exception as exc:  # noqa: BLE001 - the substrate's own verdict on its own journal
        raise PlanUnavailable(f"the operator-tools pending transition is malformed ({show(exc)})") from exc
    path = operator_config.bin_dir / Path(str(pending["path"])).name
    observed = "live-other"
    if not path.exists() and not path.is_symlink():
        observed = "live-absent"
    else:
        for role in ("before", "after"):
            record = pending.get(role)
            if isinstance(record, dict) and operator_tools.live_matches(path, record):
                observed = f"live-{role}"
                break
    return [
        {
            "action": ACTION_RESUME_PENDING,
            "classification": f"{pending['operation']}/{observed}",
            "component": "operator-tools",
            "path": str(path),
        }
    ]


def derive_plan(
    *,
    operator_tools: ModuleType,
    operator_config: Any,
    bundle: ModuleType,
    bundle_config: Any,
    activation_receipts: Path,
) -> tuple[dict[str, Any], str]:
    """Derive ONE canonical recovery plan and its digest from journal and receipt state.

    Pure observation: every path here is read, never opened for writing, never repaired, and no lock
    is taken, which is what lets the read-only reader call this to render a digest.  The returned
    plan is exactly what an ``--apply`` re-derives, so a digest computed here and a digest computed
    there differ only when the state itself moved.
    """
    journals = [
        {**observe_journal("operator-tools", "operator-tools/state", operator_config.state_path),
         "path": str(operator_config.state_path)},
    ]
    bundle_journals = []
    seen: set[str] = set()
    for slug, path in (
        ("bundle/state", bundle_config.state_path),
        ("bundle/legacy-state", bundle_config.legacy_state_path),
    ):
        if str(path) in seen:
            continue
        seen.add(str(path))
        bundle_journals.append({**observe_journal("bundle", slug, path), "path": str(path)})
    journals.extend(bundle_journals)

    present = [journal for journal in bundle_journals if journal["state"] == JOURNAL_PRESENT]
    if len(present) > 1:
        # Two journals is ambiguity, and selecting one would be the migration nobody approved.
        raise PlanUnavailable(
            "more than one bundle journal document is present; recovery selects and migrates neither"
        )
    items = operator_tools_items(operator_tools, operator_config, journals[0])
    if present:
        items.extend(bundle_items(bundle, bundle_config, present[0]))
    items.sort(key=lambda item: (item["component"], item["path"], item["action"]))
    conflicts = sum(1 for item in items if item["classification"] == CONFLICT)
    plan = {
        "counts": {
            "conflicts": conflicts,
            "items": len(items),
            "recoverable": len(items) - conflicts,
        },
        "host": HOST,
        "items": items,
        # ``path`` is the local read key, never part of the digested plan: an operator's absolute
        # paths are not this plan's to publish, and the opaque locator plus the byte digest already
        # identify the document exactly.
        "journal": sorted(
            [{key: value for key, value in journal.items() if key != "path"} for journal in journals],
            key=lambda journal: journal["locator"],
        ),
        "operation": OPERATION,
        "receipts": observe_receipts(activation_receipts),
        "schema": PLAN_SCHEMA,
    }
    return plan, plan_digest(plan)


# ---- apply: admission ------------------------------------------------------------------------------


def _absolute(path: Path) -> Path:
    """Absolute without resolving links, aliases, or 8.3 spellings: the installer's own rule."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def parse_argv(argv: list[str]) -> str:
    """Admit exactly the vector the dispatcher forwards, and return the approved plan digest.

    The dispatcher owns the usage surface, so a direct invocation with another vector is a pre-effect
    refusal rather than a second usage opinion.  Not-supplied and supplied-but-unusable stay distinct
    refusals, because collapsing them hides which half of the invocation was wrong.
    """
    if not argv:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} admits exactly [{APPLY_FLAG!r}, '<plan-sha256>'];"
            " this module received no argument at all"
        )
    if argv[0] != APPLY_FLAG:
        raise Refusal(
            f"ccodex sdlc recover admits exactly {APPLY_FLAG} as its first argument; this module"
            f" received {show(argv[0])}"
        )
    if len(argv) == 1:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} was supplied without the plan digest it approves"
        )
    if len(argv) > 2:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} admits exactly one plan digest; this module also"
            f" received {show(argv[2])}"
        )
    if not is_plan_digest(argv[1]):
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} requires one 64-character lowercase hexadecimal plan"
            f" digest; this module received {show(argv[1])}"
        )
    return argv[1]


def refuse_read_only_guard() -> None:
    """Refuse cleanly if this process already installed the reader's read-only guard.

    The guard patches ``builtins.open``, ``os``, ``shutil``, ``Path``, and ``fcntl`` process-globally
    and pins the very names this module reuses.  The shipped dispatcher hands off BEFORE it builds
    any read-only projection, so the guard is never installed on this path; if some other caller
    changes that, a recovery must fail as a NAMED refusal before any effect rather than as a
    ``ReadOnlyViolation`` traceback the dispatcher would classify as an unknown effect.
    """
    guard = sys.modules.get("_ccodex_sdlc_readonly_guard")
    if guard is not None and getattr(guard, "_INSTALLED", False):
        raise Refusal(
            "ccodex sdlc recover --apply refuses: this process already installed the read-only guard,"
            " whose stdlib mutation blocks would fail this operation partway through"
        )


def admit_platform(system: str | None = None, machine: str | None = None) -> None:
    """Refuse an uncertified platform BY NAME rather than resuming a transition on it."""
    observed_system = platform.system() if system is None else system
    observed_machine = platform.machine() if machine is None else machine
    if observed_system != SUPPORTED_SYSTEM:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} resumes an activated {SUPPORTED_SYSTEM} plane and is"
            f" certified only there; the observed operating system is {show(observed_system)}."
            " Another platform is refused rather than attempted"
        )
    if observed_machine.lower() not in SUPPORTED_MACHINES:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} resumes a linux-x64 plane; the observed architecture"
            f" is {show(observed_machine)}, not one of {list(SUPPORTED_MACHINES)}"
        )


def load_sibling(stem: str) -> ModuleType:
    """Load one named sibling by absolute non-symlink path, the reader's own admission shape."""
    path = Path(__file__).with_name(f"{stem}.py")
    if path.is_symlink() or not path.is_file():
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} requires the sibling module {show(str(path))}, which"
            " is absent or is a link"
        )
    spec = importlib.util.spec_from_file_location(f"_ccodex_sdlc_recover_{stem}", path)
    if spec is None or spec.loader is None:
        raise Refusal(f"ccodex sdlc recover {APPLY_FLAG} cannot load {show(str(path))}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an import failure here is still pre-effect
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} cannot import {show(str(path))}: {show(exc)}"
        ) from exc
    return module


def verify_receipt_evidence(dar: ModuleType, receipts: dict[str, Any], directory: Path) -> list[str]:
    """Admit the activation plane's recorded evidence, or refuse by name. Never repair a receipt.

    A sealed acquisition or activation receipt is never mutated here (agentic-sdlc-0cce); it is READ
    for what it already states.  A document the family's own validator will not validate is not
    evidence, and resuming a half-finished transition on the strength of it would be acting on state
    this host cannot verify.

    The bytes are re-digested against the plan's own record, so a receipt rewritten between the
    derivation and this check is NAMED as movement rather than validated as if it were the approved
    one.  A neighbour whose name this plane cannot recognise is ambiguous evidence and refuses:
    guessing which file an opaque locator meant is exactly the guess that must not happen here.

    RECOGNISED means named, validated, and LEFT IN PLACE -- never rewritten, moved, or repaired.  The
    recognised set is this plane's own two grammars (``is_plan_digest`` and
    ``is_lifecycle_receipt_stem``); before agentic-sdlc-3bb8 it was the digest grammar alone, which no
    lifecycle verb has ever used to name a receipt, so every host that had completed one install or
    update refused its own evidence here and had no executable recovery for an interrupted
    transaction.  A genuinely alien filename still refuses, by the same line, without echoing itself.
    """
    if receipts["state"] in JOURNAL_BLOCKING_STATES:
        raise Refusal(
            f"the activation receipts plane {show(str(directory))} is {receipts['state']}, so the"
            " recorded evidence for this host cannot be verified"
        )
    if receipts["state"] == "overfull":
        raise Refusal(
            f"the activation receipts plane {show(str(directory))} holds more than"
            f" {MAX_RECEIPT_DOCUMENTS} documents, so which evidence describes this host is ambiguous"
        )
    verified: list[str] = []
    for document in receipts["documents"]:
        locator = document["locator"]
        if document["state"] != JOURNAL_PRESENT:
            raise Refusal(
                f"the recorded activation receipt {locator} is {document['state']}, so this host's"
                " evidence cannot be verified"
            )
        stem = locator.split("://", 1)[-1]
        if not (is_plan_digest(stem) or is_lifecycle_receipt_stem(stem)):
            raise Refusal(
                f"the activation receipts plane holds {locator}, a document this plane cannot name;"
                " unrecognised evidence is preserved and refused rather than interpreted"
            )
        path = directory / f"{stem}.json"
        raw, state = read_bounded_document(path, MAX_RECEIPT_BYTES)
        if raw is None or sha256_bytes(raw) != document["digest"]:
            raise Refusal(
                f"the recorded activation receipt {locator} is no longer the document this plan was"
                f" derived from (now {state}): the state moved and nothing was touched"
            )
        try:
            parsed = dar.load_document(str(path), locator)
        except Exception as exc:  # noqa: BLE001 - an unusable receipt is a named refusal
            raise Refusal(
                f"the recorded activation receipt {locator} is unusable: {show(exc)}"
            ) from exc
        result = dar.derive("validate", parsed, locator)
        if result["verdict"] != dar.VERDICT_VALIDATED:
            reasons = "; ".join(escape_display(str(reason)) for reason in result["reasons"][:4])
            raise Refusal(
                f"the recorded activation receipt {locator} does not validate as {dar.BODY_SCHEMA},"
                f" so it cannot be treated as this host's evidence: {reasons}"
            )
        verified.append(locator)
    return verified


# ---- apply: configuration ---------------------------------------------------------------------------


def build_configs(
    operator_tools: ModuleType, bundle: ModuleType, *, home: Path | None = None
) -> tuple[Any, Any, Path]:
    """Build the two substrate configurations the reader builds, with writing enabled.

    Identity fields are resolved exactly as ``ccodex_sdlc.recovery_configs`` resolves them, because a
    plan derived against one selection and applied against another would compare two different
    hosts.  ``dry_run`` is the only difference, and it participates in no classification.
    """
    resolved_home = operator_tools.absolute(Path.home() if home is None else home)
    state_root = operator_tools.state_root_for(resolved_home)
    root = _absolute(Path(__file__).parent.parent)
    operator_config = operator_tools.Config(
        root, resolved_home, operator_tools.default_bin_dir(resolved_home), state_root, False, False
    )
    codex_home_value = os.environ.get("CODEX_HOME")
    codex_home = (
        Path(codex_home_value) if codex_home_value and codex_home_value.strip() else resolved_home / ".codex"
    )
    bundle_config = bundle.Config(root, resolved_home, codex_home, "auto", False, "all", state_root)
    activation = state_root / STATE_PLANE_DIRECTORY
    return operator_config, bundle_config, activation.joinpath(*ACTIVATION_RECEIPTS)


# ---- apply: execution --------------------------------------------------------------------------------


def admit_journals(plan: dict[str, Any]) -> None:
    """Refuse a journal this module must not act through, naming the state that stopped it."""
    for journal in plan["journal"]:
        if journal["state"] in JOURNAL_BLOCKING_STATES:
            raise Refusal(
                f"the {journal['component']} journal {journal['locator']} is {journal['state']}, so"
                " recovery cannot verify what it would resume; it is preserved untouched"
            )


def resume_operator_tools(
    operator_tools: ModuleType, operator_config: Any, plan: dict[str, Any], ledger: dict[str, bool]
) -> tuple[list[str], bool]:
    """Resume or roll back the operator-tools pending transition through its own machinery.

    The journal's exact bytes are re-checked UNDER the lifecycle lock against the digest the approved
    plan recorded, mirroring ``resume_bundle``'s own pattern: a plan verified before the lock and
    executed after it would otherwise have admitted whatever moved in between.
    """
    if not any(item["component"] == "operator-tools" for item in plan["items"]):
        return [], False
    recorded = {
        journal["locator"]: journal["digest"]
        for journal in plan["journal"]
        if journal["component"] == "operator-tools" and journal["state"] == JOURNAL_PRESENT
    }
    moved_before = ledger["moved"]
    with operator_tools.lifecycle_lock(operator_config):
        locator = "journal://operator-tools/state"
        if locator in recorded:
            raw, state_name = read_bounded_document(operator_config.state_path, MAX_JOURNAL_BYTES)
            if raw is None or sha256_bytes(raw) != recorded[locator]:
                raise Refusal(
                    f"the operator-tools journal {locator} changed between the approval and the lock"
                    f" (now {state_name}): the state moved and nothing was touched"
                )
        state = operator_tools.load_state(operator_config.state_path, operator_config)
        try:
            # Pessimistic on purpose: the flag is raised BEFORE the call, because the write happens
            # inside it and a flag raised afterwards would claim an absence of effect nobody saw.
            ledger["moved"] = True
            message = operator_tools.recover_pending(operator_config, state, read_only=False)
        except operator_tools.OperatorToolsError as exc:
            # ``recover_pending`` refuses a conflicting live file BEFORE it writes anything, which is
            # why the flag may be lowered here and only here: the transition is preserved exactly as
            # found and named for the operator.
            ledger["moved"] = moved_before
            return [f"operator-tools: preserved conflict: {escape_display(str(exc))}"], True
    if message is None:
        ledger["moved"] = moved_before
        return ["operator-tools: nothing pending remained to recover"], True
    return [f"operator-tools: {escape_display(message)}"], False


def resume_bundle(
    bundle: ModuleType,
    bundle_config: Any,
    plan: dict[str, Any],
    ledger: dict[str, bool],
) -> tuple[list[str], bool]:
    """Resume or roll back the bundle journal's transactions through the substrate's own machinery.

    The journal's exact bytes are re-checked UNDER the installer lock against the digest the approved
    plan recorded: a plan verified before the lock and executed after it would otherwise have
    admitted whatever moved in between.
    """
    if not any(item["component"] == "bundle" for item in plan["items"]):
        return [], False
    recorded = {
        journal["locator"]: journal["digest"]
        for journal in plan["journal"]
        if journal["component"] == "bundle" and journal["state"] == JOURNAL_PRESENT
    }
    with bundle.installer_lock(bundle_config):
        for locator, path in (
            ("journal://bundle/state", bundle_config.state_path),
            ("journal://bundle/legacy-state", bundle_config.legacy_state_path),
        ):
            if locator not in recorded:
                continue
            raw, state = read_bounded_document(path, MAX_JOURNAL_BYTES)
            if raw is None or sha256_bytes(raw) != recorded[locator]:
                raise Refusal(
                    f"the bundle journal {locator} changed between the approval and the lock (now"
                    f" {state}): the state moved and nothing was touched"
                )
        state_document = bundle.load_config_state(bundle_config)
        bundle.validate_state(bundle_config, state_document)
        ledger["moved"] = True
        messages, partial = bundle.recover_transactions(bundle_config, state_document, read_only=False)
    return [f"bundle: {escape_display(message)}" for message in messages], partial


def run(argv: list[str], ledger: dict[str, bool], *, home: Path | None = None) -> tuple[int, list[str]]:
    """One recovery: admit, re-derive, compare digests, then resume through reused machinery."""
    approved = parse_argv(argv)
    refuse_read_only_guard()
    admit_platform()
    dar = load_sibling("distribution_activation_receipt")
    bundle = load_sibling("install_skill_bundle")
    operator_tools = load_sibling("install_operator_tools")
    operator_config, bundle_config, receipts_dir = build_configs(operator_tools, bundle, home=home)

    try:
        plan, digest = derive_plan(
            operator_tools=operator_tools,
            operator_config=operator_config,
            bundle=bundle,
            bundle_config=bundle_config,
            activation_receipts=receipts_dir,
        )
    except PlanUnavailable as exc:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} cannot re-derive a plan from this host's state:"
            f" {escape_display(str(exc))}. Nothing was touched"
        ) from exc
    admit_journals(plan)
    verify_receipt_evidence(dar, plan["receipts"], receipts_dir)

    if plan["counts"]["items"] == 0:
        raise Refusal(
            f"ccodex sdlc recover {APPLY_FLAG} found nothing to recover on this host, so there is no"
            " plan to apply and nothing was touched"
        )
    if digest != approved:
        raise Refusal(
            f"the approved plan {show(approved)} is not the plan this host's state derives"
            f" ({show(digest)}): the state moved after the approval, or the approval is stale."
            " Re-run `ccodex sdlc recover --dry-run`, review the new plan, and approve that digest."
            " Nothing was touched"
        )

    lines = [
        f"ccodex sdlc recover {APPLY_FLAG} {escape_display(approved[:12])}: plan re-derived from"
        f" verified journal and receipt state ({plan['counts']['items']} item(s),"
        f" {plan['counts']['conflicts']} classified conflict(s))",
    ]
    operator_lines, operator_partial = resume_operator_tools(
        operator_tools, operator_config, plan, ledger
    )
    bundle_lines, bundle_partial = resume_bundle(bundle, bundle_config, plan, ledger)
    lines.extend(operator_lines)
    lines.extend(bundle_lines)
    partial = operator_partial or bundle_partial or bool(plan["counts"]["conflicts"])
    lines.append(
        "preserved state is never overwritten or deleted: foreign, modified, retargeted, and"
        " ambiguous entries are reported by name and left exactly as found"
    )
    lines.append(
        "public_channel null and release_claim none: this recovery states no published release"
        " exists, and it authorizes no push, publication, merge, or deployment"
    )
    return (EXIT_PARTIAL if partial else EXIT_RECOVERED), lines


def main(argv: list[str] | None = None) -> int:
    """The dispatcher's entry point: always an ``int`` in the exit class 0-4, never a ``bool``.

    Every escape route is classified by ONE fact -- did anything move -- rather than by the
    exception's type, because an interrupt before the first recovery step and one after it are
    different outcomes that the same class would otherwise report identically.
    """
    selected = list(sys.argv[1:] if argv is None else argv)
    ledger: dict[str, bool] = {"moved": False}
    try:
        exit_class, lines = run(selected, ledger)
    except Refusal as exc:
        if ledger["moved"]:
            print(
                f"error: ccodex sdlc recover {APPLY_FLAG} left an unknown effect:"
                f" {escape_display(str(exc))}",
                file=sys.stderr,
            )
            return EXIT_UNKNOWN
        print(
            f"error: ccodex sdlc recover {APPLY_FLAG} refused before any effect:"
            f" {escape_display(str(exc))}",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    except UnknownEffect as exc:
        print(
            f"error: ccodex sdlc recover {APPLY_FLAG} left an unknown effect:"
            f" {escape_display(str(exc))}",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - includes the interrupt this walk must survive
        moved = ledger["moved"]
        print(
            f"error: ccodex sdlc recover {APPLY_FLAG} stopped and"
            f" {'cannot prove what it recovered' if moved else 'moved nothing'}:"
            f" {escape_display(repr(exc))}",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN if moved else EXIT_REFUSED
    sys.stdout.write("\n".join(lines) + "\n")
    return exit_class


if __name__ == "__main__":
    raise SystemExit(main())
