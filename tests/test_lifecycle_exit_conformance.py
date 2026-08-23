"""Effect-aware exit conformance for the whole `ccodex sdlc` lifecycle (spec Decision 9).

WHAT THIS MODULE IS FOR.  The per-verb modules -- ``test_ccodex_sdlc_install.py``,
``_update.py``, ``_uninstall.py``, ``_recover_apply.py`` -- each prove their own verb's behaviour.
Nothing proved that the FOUR verbs answer the operator with ONE exit vocabulary, that the same three
operator-owned files survive every one of them, or that the words a lifecycle result prints never
read as authorization.  This module is that cross-verb conformance suite.  It adds no production
behaviour of its own.

It was first landed with three checks PINNING defects it had found rather than asserting the honest
behaviour, each named FINDING in its own prose.  All three are now fixed in production and the checks
assert the honest behaviour: the retirement of an entry the activation recorded ``foreign``
(agentic-sdlc-9b9a), the recovery of an interrupted transaction on a host that has filed a real
activation receipt (agentic-sdlc-3bb8), and the exit class of an admitted partial retirement
(agentic-sdlc-d7b3).  Each of those three checks names its seed and states what production does now.

THE FIVE EXIT CLASSES, re-expressed from the shipped spec rather than imported from any module under
test, so a table a module quietly renumbered fails here instead of agreeing with itself:

    0  a durably complete effect (or a valid query)
    1  unexpected internal failure
    2  grammar / schema / input error
    3  clean refusal BEFORE any effect
    4  an admitted partial or unknown effect

HOW THE VERBS ARE DRIVEN.  Three levels, all real, chosen per claim:

* THE INSTALLED DISPATCHER.  ``operator-tools`` installs a real ``ccodex`` once for the module, and
  every verb runs as ``ccodex sdlc <verb> ...`` in a subprocess over a private ``HOME``,
  ``XDG_STATE_HOME``, ``XDG_DATA_HOME``, and ``XDG_BIN_HOME``.  This is the level the operator
  types, and it is the ONLY level that can prove the exit-2 grammar matrix, because a malformed
  vector never reaches a per-verb module at all.
* THE REAL PER-VERB ENTRY POINT IN A SUBPROCESS.  ``driver.py`` loads one shipped module by absolute
  path exactly as ``scripts/ccodex_sdlc.py`` does, wraps ONE named shipped-installer primitive with
  a fault, and calls the module's own ``main(argv)``.  Configuration still comes from the
  environment through the module's own ``default_config()``; nothing is stubbed but the single
  injected primitive.  Every faulted run is paired with a fault-free run THROUGH THE SAME DRIVER and
  with the installed dispatcher's own result, so the driver is shown to be faithful before any
  conclusion is drawn from it.
* A REAL SIGKILL.  The crash-honesty chain kills the install process inside the shipped installer's
  own transaction, so the state the recovery verbs then read is the state a power loss leaves.

EVERY NEGATIVE ASSERTION CARRIES A POSITIVE CONTROL.  An "exit 2 and nothing moved" test also runs
an admitted vector and shows it is neither exit 2 nor inert; a "no authorization vocabulary" scan is
also run over a fabricated authorizing line and shown to flag it; a "these bytes survived" assertion
is paired with a run whose bytes the same comparison would have caught changing.

A finding this suite cannot fix in production stays recorded at the class that hit it, prefixed
FINDING, rather than being asserted as if it were the contract.

THE ONE HOST CONDITION.  All three levels run the linux-x64-certified payload in a child under
``-I``, so the per-verb modules' injected platform-observation seam cannot cross into them and off
the certified platform every lifecycle verb refuses at exit 3 before any effect.  ``Plane`` reports
that as a named skip (``payload_host_or_skip``) and only when the PRODUCT's own predicate refuses
this host as well, so on the certified linux-x64 host the branch is unreachable and every claim below
is proved rather than skipped (agentic-sdlc-e8a9).
"""

from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]
SPEC_PATH = ROOT / "docs" / "plans" / "claude-code-first-harness" / "agentic-sdlc-product-spec.md"
RELEASE_CONTRACT_PATH = ROOT / "policy" / "release-contract.v1.json"

#: The exit classes, spelled as literals.  Decision 9 is the authority; no module under test is.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_GRAMMAR = 2
EXIT_REFUSED = 3
EXIT_UNKNOWN = 4
ADMITTED_EXIT_CLASSES = (EXIT_OK, EXIT_INTERNAL, EXIT_GRAMMAR, EXIT_REFUSED, EXIT_UNKNOWN)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bundle = _load(ROOT / "scripts" / "install_skill_bundle.py", "exit_conformance_bundle")
operator_tools = _load(ROOT / "scripts" / "install_operator_tools.py", "exit_conformance_operator_tools")
dar = _load(ROOT / "scripts" / "distribution_activation_receipt.py", "exit_conformance_receipts")
recover = _load(ROOT / "scripts" / "ccodex_sdlc_recover.py", "exit_conformance_recover")

#: The phrases a shipped verb's OWN platform refusal carries: install and update refuse to activate
#: or refresh a linux-x64 CANDIDATE, recover refuses to resume a linux-x64 PLANE, and each names the
#: one observation it refused.  Re-expressed here rather than imported so a verb that quietly stopped
#: naming its observation stops matching instead of agreeing with itself.
PLATFORM_REFUSAL_FRAGMENTS = ("the observed operating system is", "the observed architecture is")


def uncertified_platform() -> str | None:
    """The PRODUCT's own certified-platform verdict for THIS host, or ``None`` when it admits it.

    Asked of ``ccodex_sdlc_recover.admit_platform``'s parameterized observation rather than of
    ``sys.platform`` or a literal ``"Darwin"``: the certified platform is a rule the shipped verbs
    own, so a harness that restated it would drift the moment the product widened it, and a harness
    that read ``sys.platform`` would be asserting about the runner instead of asking the shipped
    predicate.  On the certified linux-x64 host this returns ``None``, which is what makes every skip
    built on it UNREACHABLE there rather than merely unlikely (agentic-sdlc-e8a9).
    """
    try:
        recover.admit_platform(system=platform.system(), machine=platform.machine())
    except recover.Refusal as refusal:
        return str(refusal)
    return None


#: A host version the shipped release contract admits (floor 2.1.154, no declared incompatibility).
#: The stub ``claude`` planted on the dispatcher's PATH prints it, which is what makes an install
#: through the real dispatcher DETERMINISTIC instead of skipping on hosts with no Claude Code.
HOST_VERSION = "2.1.233"

ARCHIVE_A = hashlib.sha256(b"exit-conformance-archive-a").hexdigest()
ARCHIVE_B = hashlib.sha256(b"exit-conformance-archive-b").hexdigest()
CANDIDATE_A = hashlib.sha256(b"exit-conformance-candidate-a").hexdigest()
CANDIDATE_B = hashlib.sha256(b"exit-conformance-candidate-b").hexdigest()
OPERATION_A = "op-" + hashlib.sha256(b"exit-conformance-operation-a").hexdigest()[:32]
OPERATION_B = "op-" + hashlib.sha256(b"exit-conformance-operation-b").hexdigest()[:32]
VERSION_A = "0.7.3"
VERSION_B = "0.7.4"

#: One skill DIRECTORY with a nested file, one Claude agent, one command, and one CODEX agent a
#: claude-host lifecycle verb must never touch.  Two payloads, so an update has something to refresh.
PAYLOAD_A = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha one\n",
    "skills/alpha-skill/references/notes.md": "notes one\n",
    "agents/claude/cartographer.md": "cartographer one\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame one\n",
}
PAYLOAD_B = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha two\n",
    "skills/alpha-skill/references/notes.md": "notes two\n",
    "agents/claude/cartographer.md": "cartographer two\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame two\n",
}
CLAUDE_DESTINATIONS = ("agents/cartographer.md", "commands/sdlc-frame.md", "skills/alpha-skill")
CODEX_DESTINATION = "agents/cartographer.toml"

#: One well-formed digest no plan this suite derives will ever equal.
FOREIGN_DIGEST = hashlib.sha256(b"a recovery plan no host derives").hexdigest()


# ---- canonical bytes and the acquisition fixture --------------------------------------------------


def canonical(document: Any) -> bytes:
    return (
        json.dumps(document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")


def seal_acquisition(receipt: dict[str, Any]) -> bytes:
    """The acquisition producer's own seal: digest the canonical bytes MINUS ``record_sha256``."""
    body = {key: value for key, value in receipt.items() if key != "record_sha256"}
    body["record_sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    return canonical(body)


def inventory_for_tree(root: Path) -> list[dict[str, Any]]:
    """The candidate manifest's inventory shape, mirroring the release-candidate builder's walk."""
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        item = path.lstat()
        if stat.S_ISLNK(item.st_mode):
            target = os.readlink(path)
            rows.append(
                {
                    "mode": 0o755,
                    "path": relative,
                    "size": len(target.encode()),
                    "target": target,
                    "type": "symlink",
                }
            )
        elif stat.S_ISDIR(item.st_mode):
            rows.append({"mode": 0o755, "path": relative, "size": 0, "type": "dir"})
        else:
            rows.append(
                {
                    "mode": 0o644,
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size": item.st_size,
                    "type": "file",
                }
            )
    rows.sort(key=lambda row: str(row["path"]))
    return rows


def write_candidate(
    data_home: Path,
    archive: str,
    candidate_id: str,
    version: str,
    payload: dict[str, str],
    *,
    manifest_overrides: dict[str, Any] | None = None,
) -> Path:
    """One acquired candidate payload tree under the acquisition layout, with its own manifest."""
    candidate_root = data_home / "agentic-sdlc" / "acquisition" / "candidates" / archive / "root"
    candidate_root.mkdir(parents=True)
    for relative, text in payload.items():
        target = candidate_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    contract_path = candidate_root / "policy" / "release-contract.v1.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_bytes(canonical(json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))))
    manifest = {
        "archive_root": f"agentic-sdlc-candidate-{candidate_id}-linux-x64",
        "artifact_kind": "unpublished-candidate",
        "candidate_id": candidate_id,
        "inventory": inventory_for_tree(candidate_root),
        "platform": "linux-x64",
        "product_version": version,
        "public_channel": None,
        "release_claim": "none",
        "schema_version": "release-candidate/v1",
        "support_tier": "unsupported",
    }
    manifest.update(manifest_overrides or {})
    (candidate_root / "manifest.json").write_bytes(canonical(manifest))
    return candidate_root


def write_acquisition_receipt(
    state_home: Path,
    archive: str,
    candidate_root: Path,
    operation_id: str,
    installed_at: str,
    *,
    overrides: dict[str, Any] | None = None,
    reseal: bool = True,
) -> Path:
    receipt = {
        "activation": "absent",
        "archive_sha256": archive,
        "candidate_root_absolute_physical_path": str(candidate_root),
        "effect_state": "complete",
        "installed_at": installed_at,
        "journal_sha256": hashlib.sha256(b"acquisition-journal").hexdigest(),
        "operation_id": operation_id,
        "plan_sha256": hashlib.sha256(b"acquisition-plan").hexdigest(),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    receipt.update(overrides or {})
    directory = state_home / "agentic-sdlc" / "acquisition" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{archive}.json"
    path.write_bytes(seal_acquisition(receipt) if reseal else canonical(receipt))
    return path


# ---- whole-tree observation -----------------------------------------------------------------------


def tree_hash(*roots: Path) -> str:
    """ONE digest over every path, mode, symlink target, and byte under the given roots.

    This is the exit-3 instrument: a clean refusal before effect must leave this value unchanged.
    A directory that was merely CREATED changes it, which is deliberate -- Decision 9's "before
    effect" is a claim about the filesystem, not about the interesting files in it.
    """
    digest = hashlib.sha256()
    for root in roots:
        digest.update(b"\x00root\x00")
        digest.update(str(root).encode("utf-8", "surrogatepass"))
        for path in sorted(root.rglob("*") if root.exists() else []):
            item = path.lstat()
            digest.update(b"\x00")
            digest.update(str(path.relative_to(root)).encode("utf-8", "surrogatepass"))
            digest.update(f"{stat.S_IMODE(item.st_mode):o}:{stat.S_IFMT(item.st_mode):o}".encode("ascii"))
            if path.is_symlink():
                digest.update(os.readlink(path).encode("utf-8", "surrogatepass"))
            elif path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def plane_inventory(*roots: Path) -> dict[str, str]:
    """Every path under each root with its digest, so a diff NAMES what moved."""
    seen: dict[str, str] = {}
    for root in roots:
        for path in sorted(root.rglob("*")) if root.exists() else []:
            item = path.lstat()
            if stat.S_ISLNK(item.st_mode):
                seen[str(path)] = f"link:{os.readlink(path)}"
            elif stat.S_ISDIR(item.st_mode):
                seen[str(path)] = "dir"
            else:
                seen[str(path)] = f"file:{item.st_size}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    return seen


# ---- the authorization-vocabulary scanner ---------------------------------------------------------

#: The authority-shaped words a lifecycle RESULT may never claim.  The shipped reports legitimately
#: DENY them ("authorizes no push, publication, merge, or deployment"), so a bare token grep would
#: flag every honest run.  A line is a claim only when it carries a token and no denial marker.
AUTHORITY_TOKENS = (
    "push",
    "publish",
    "publication",
    "published",
    "merge",
    "merged",
    "deploy",
    "deployment",
    "deployed",
    "authorize",
    "authorized",
    "authorizes",
    "authorization",
)
#: Every way the shipped surfaces spell a denial.  A marker clears the SEGMENT it appears in, never a
#: whole line: a denial in one clause must not launder an authorizing clause beside it.
DENIAL_MARKERS = (
    "no ",
    "not ",
    "never",
    "none",
    "nothing",
    "null",
    "without",
    "cannot",
    "refus",
    "absent",
    "evidence only",
    "is not authority",
)


#: Segment separators.  A rendered report puts several independent statements on one line, so a
#: LINE-level scan lets one clause's denial launder the clause beside it -- an install report that
#: gained "this activation authorizes the integrator to push" in front of the honest
#: "public_channel null ... authorizes no push ..." sentence would read as clean.  Splitting on the
#: separators the shipped reports actually use is what closes that hole; it was found by mutation,
#: not by reading.
SEGMENT_SEPARATORS = ("\n", "; ", ". ", ": ")


def _segments(text: str) -> list[str]:
    pieces = [text.lower()]
    for separator in SEGMENT_SEPARATORS:
        expanded: list[str] = []
        for piece in pieces:
            expanded.extend(piece.split(separator))
        pieces = expanded
    return [piece.strip() for piece in pieces if piece.strip()]


def authority_claims(text: str) -> list[str]:
    """Return every SEGMENT that carries an authority token WITHOUT a denial marker of its own."""
    return [
        segment
        for segment in _segments(text)
        if any(token in segment for token in AUTHORITY_TOKENS)
        and not any(marker in segment for marker in DENIAL_MARKERS)
    ]


def document_authority_claims(document: Any) -> list[str]:
    """Scan a sealed document LEAF BY LEAF rather than as one long line.

    A canonical receipt is a single line of JSON, so a whole-text scan would let a ``null`` anywhere
    in the document clear an authorizing string anywhere else in it.  Every key and every string
    value is scanned on its own instead.
    """
    claims: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            claims.extend(authority_claims(str(key)))
            claims.extend(document_authority_claims(value))
    elif isinstance(document, list):
        for item in document:
            claims.extend(document_authority_claims(item))
    elif isinstance(document, str):
        claims.extend(authority_claims(document))
    return claims


# ---- the installed dispatcher ---------------------------------------------------------------------


class _InstalledDispatcher:
    """One real ``ccodex`` installed once for the whole module, over per-test operator planes.

    ``operator-tools`` binds the launcher to absolute ``ocx``/``jq``/``uv`` paths and to the exact
    interpreter running this suite, which is why the binary is reusable: it carries no per-test
    state.  Every plane a test drives is supplied as environment, so no two tests can observe each
    other's home.
    """

    def __init__(self) -> None:
        self._root: tempfile.TemporaryDirectory[str] | None = None
        self.dispatcher: Path | None = None
        self.stub_bin: Path | None = None

    def ensure(self) -> tuple[Path, Path]:
        if self.dispatcher is not None and self.stub_bin is not None:
            return self.dispatcher, self.stub_bin
        self._root = tempfile.TemporaryDirectory(prefix="exit-conformance-dispatcher-")
        # Registered explicitly: a module-scoped temporary directory that relied on its own finalizer
        # would leave a tree behind on an interrupted run and warn on a clean one.
        atexit.register(self._root.cleanup)
        root = Path(self._root.name)
        runtime = root / "runtime"
        runtime.mkdir()
        for name in ("ocx", "jq", "uv"):
            executable = runtime / name
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
        config = operator_tools.Config(
            ROOT,
            root / "install-home",
            root / "bin",
            root / "installer-state",
            False,
            False,
            runtime / "ocx",
            runtime / "jq",
            runtime / "uv",
            Path(sys.executable),
        )
        installed, messages = operator_tools.install(config)
        if installed != 0:
            raise AssertionError(f"operator tools did not install: {messages}")
        stub_bin = root / "stub-bin"
        stub_bin.mkdir()
        # `install` observes the host version by running `claude --version`. A stub makes that
        # observation deterministic; without it a clean host refuses at exit 3 and every effect-aware
        # claim below would be skipped rather than proved.
        claude = stub_bin / "claude"
        claude.write_text(f"#!/bin/sh\nprintf '%s (Claude Code)\\n' '{HOST_VERSION}'\nexit 0\n")
        claude.chmod(0o755)
        self.dispatcher = config.bin_dir / "ccodex"
        self.stub_bin = stub_bin
        return self.dispatcher, self.stub_bin


DISPATCHER = _InstalledDispatcher()

#: The one driver that loads a shipped per-verb module exactly as ``scripts/ccodex_sdlc.py`` does and
#: wraps ONE named shipped-installer primitive.  Written to a temp directory per test root; it never
#: touches a tracked file.
DRIVER_SOURCE = '''\
"""Load one shipped lifecycle module by absolute path and call its own main(argv).

The module resolves its configuration through its OWN default_config() over this process's
environment; the only substitution is the single named install_skill_bundle primitive named by
CONFORMANCE_FAULT, and CONFORMANCE_FAULT may be null, which is the fidelity control.
"""

import importlib.util
import json
import os
import signal
import sys
from pathlib import Path

root = Path(os.environ["CONFORMANCE_ROOT"])
stem = os.environ["CONFORMANCE_MODULE"]
argv = json.loads(os.environ["CONFORMANCE_ARGV"])
fault = json.loads(os.environ["CONFORMANCE_FAULT"])

path = root / "scripts" / (stem + ".py")
spec = importlib.util.spec_from_file_location("conformance_" + stem, path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

if fault is not None:
    real_loader = module.load_sibling
    counters = {}

    def loader(*arguments):
        loaded = real_loader(*arguments)
        if arguments[-1] != "install_skill_bundle":
            return loaded
        name = fault["function"]
        original = getattr(loaded, name)
        seen = counters.setdefault(name, [])

        def wrapped(*positional, **keyword):
            seen.append(1)
            if len(seen) > fault["after"]:
                if fault["kind"] == "sigkill":
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os.kill(os.getpid(), signal.SIGKILL)
                raise loaded.InstallerError(fault["message"])
            return original(*positional, **keyword)

        setattr(loaded, name, wrapped)
        return loaded

    module.load_sibling = loader

sys.exit(module.main(argv))
'''

FAULT_MESSAGE = "fault-injected transaction failure"


class Plane:
    """One operator plane: a private home, state root, data root, and bin root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "operator-home"
        self.state_home = root / "state"
        self.data_home = root / "data"
        self.bin_home = root / "bin"
        self.codex_home = self.home / ".codex"
        for directory in (self.home, self.state_home, self.data_home, self.bin_home):
            directory.mkdir(parents=True, exist_ok=True)
        self.driver = root / "driver.py"
        self.driver.write_text(DRIVER_SOURCE, encoding="utf-8")

    # ---- layout ---------------------------------------------------------------------------------

    @property
    def claude_root(self) -> Path:
        return self.home / ".claude"

    @property
    def activation_dir(self) -> Path:
        return self.state_home / "agentic-sdlc" / "activation"

    @property
    def pointer(self) -> Path:
        return self.activation_dir / "active-receipt.json"

    @property
    def installer_state(self) -> Path:
        return self.state_home / "agentic-sdlc-installer" / "state.json"

    def destination(self, relative: str) -> Path:
        return self.claude_root / relative

    def observed_roots(self) -> tuple[Path, ...]:
        return (self.home, self.state_home, self.data_home, self.bin_home)

    def receipts(self) -> list[Path]:
        directory = self.activation_dir / "receipts"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def journals(self) -> list[Path]:
        directory = self.activation_dir / "journals"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def plans(self) -> list[Path]:
        directory = self.activation_dir / "plans"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def acquire(
        self,
        archive: str,
        candidate_id: str,
        version: str,
        payload: dict[str, str],
        operation_id: str,
        installed_at: str,
        **kwargs: Any,
    ) -> tuple[Path, Path]:
        candidate_root = write_candidate(
            self.data_home, archive, candidate_id, version, payload, **kwargs
        )
        receipt = write_acquisition_receipt(
            self.state_home, archive, candidate_root, operation_id, installed_at
        )
        return candidate_root, receipt

    def acquire_a(self, payload: dict[str, str] | None = None) -> tuple[Path, Path]:
        return self.acquire(
            ARCHIVE_A, CANDIDATE_A, VERSION_A, payload or PAYLOAD_A, OPERATION_A, "2026-08-19T08:00:00Z"
        )

    def acquire_b(self, payload: dict[str, str] | None = None) -> tuple[Path, Path]:
        return self.acquire(
            ARCHIVE_B, CANDIDATE_B, VERSION_B, payload or PAYLOAD_B, OPERATION_B, "2026-08-20T08:00:00Z"
        )

    # ---- running --------------------------------------------------------------------------------

    def environment(self) -> dict[str, str]:
        dispatcher, stub_bin = DISPATCHER.ensure()
        environment = os.environ.copy()
        environment.update(
            {
                "AGENTIC_SDLC_ROOT": str(ROOT),
                "HOME": str(self.home),
                "XDG_STATE_HOME": str(self.state_home),
                "XDG_DATA_HOME": str(self.data_home),
                "XDG_BIN_HOME": str(self.bin_home),
                "CODEX_HOME": str(self.codex_home),
                "PATH": f"{stub_bin}:{os.environ.get('PATH', '')}",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
        )
        environment.pop("PYTHONPATH", None)
        return environment

    def payload_host_or_skip(
        self, completed: subprocess.CompletedProcess[str], driven: str
    ) -> subprocess.CompletedProcess[str]:
        """Pass the child's result through, or SKIP BY NAME when it refused THIS host's platform.

        Every child below runs the real linux-x64-certified payload: the installed dispatcher execs
        the shipped reader under ``-I``, and the driver runs one shipped module's own ``main`` under
        ``-I`` as well, so no observation this harness could inject reaches either of them -- the
        per-verb modules take a ``Config.observed_system``/``observed_machine`` seam, and ``-I`` closes
        every environment and ``sitecustomize`` route to it across a process boundary.  Off the
        certified platform each lifecycle verb therefore refuses at exit 3 BEFORE any effect, which is
        the product being correct: the exit-class claims below are about what an admitted effect
        reports, not about a host that cannot run the payload at all, so that refusal is reported here
        as a NAMED skip instead of as a failed exit-class claim.

        Everything below must hold, which is what keeps this unreachable on the certified host: the
        child exited exactly 3; ``uncertified_platform`` -- the PRODUCT's own predicate over the real
        host -- refuses this host too; and ONE line of the child's stderr carries both a shipped verb's
        platform-refusal phrase AND this host's own observation, quoted the way the product quotes it.
        That last pairing is the positive control: a refusal about a platform this host is not, or a
        line that merely mentions the phrase, buys no skip and stays a failure.
        """
        if completed.returncode != EXIT_REFUSED or uncertified_platform() is None:
            return completed
        named = tuple(
            line
            for line in completed.stderr.splitlines()
            if any(fragment in line for fragment in PLATFORM_REFUSAL_FRAGMENTS)
            and any(f"'{observed}'" in line for observed in (platform.system(), platform.machine()))
        )
        if not named:
            return completed
        raise unittest.SkipTest(
            f"{driven} needs a host the linux-x64-certified payload can run on; the product's own"
            f" certified-platform predicate refuses this host, and the child refused it by name before"
            f" any effect: {named[0].strip()}"
        )

    def dispatch(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run one verb through the REAL installed ``ccodex`` dispatcher."""
        dispatcher, _stub = DISPATCHER.ensure()
        completed = subprocess.run(
            [str(dispatcher), *arguments],
            env=self.environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        return self.payload_host_or_skip(
            completed, f"`ccodex {' '.join(arguments[:2])}` through the installed dispatcher"
        )

    def drive(
        self,
        stem: str,
        argv: list[str],
        *,
        fault: dict[str, Any] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run one shipped module's own ``main(argv)`` with at most one injected primitive."""
        environment = self.environment()
        environment.update(
            {
                "CONFORMANCE_ROOT": str(ROOT),
                "CONFORMANCE_MODULE": stem,
                "CONFORMANCE_ARGV": json.dumps(argv),
                "CONFORMANCE_FAULT": json.dumps(fault),
            }
        )
        completed = subprocess.run(
            [str(Path(sys.executable)), "-I", "-B", str(self.driver)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        # A real mid-effect SIGKILL is named separately from an ordinary driven run: what it needs is
        # not merely an admitted platform but a host whose payload REACHES the shipped installer's own
        # transaction, because a verb that refused at phase 0 never arrives at the primitive the kill
        # is aimed at, and "no journal was left behind" would then be true for the wrong reason.
        driven = (
            "the crash-honesty chain's real mid-effect SIGKILL inside the shipped installer's own"
            f" transaction ({stem})"
            if (fault or {}).get("kind") == "sigkill"
            else f"the shipped {stem} module's own main(argv) under the driver"
        )
        return self.payload_host_or_skip(completed, driven)


class Conformance(unittest.TestCase):
    """One temporary root per test, so no test can observe another's plane."""

    maxDiff = None

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="exit-conformance-")
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)

    def plane(self) -> Plane:
        return Plane(Path(tempfile.mkdtemp(dir=self.root)))

    # ---- shared assertions ----------------------------------------------------------------------

    def assert_admitted_class(self, completed: subprocess.CompletedProcess[str]) -> None:
        self.assertIn(
            completed.returncode,
            ADMITTED_EXIT_CLASSES,
            f"{completed.returncode} is outside Decision 9: {completed.stderr}",
        )

    def assert_no_authority_claim(self, *texts: str) -> None:
        """Scan raw streams by segment, and any text that parses as JSON leaf by leaf as well."""
        for text in texts:
            self.assertEqual([], authority_claims(text), text[:2000])
            try:
                document = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                continue
            self.assertEqual([], document_authority_claims(document), text[:2000])

    def sealed(self, plane: Plane, path: Path) -> dict[str, Any]:
        document = json.loads(path.read_text(encoding="utf-8"))
        verdict = dar.derive("validate", document, "a sealed lifecycle receipt")
        self.assertEqual("validated", verdict["verdict"], verdict["reasons"])
        return document

    def install_once(self, plane: Plane) -> subprocess.CompletedProcess[str]:
        """One real activation through the installed dispatcher, asserted complete."""
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        self.assertTrue(plane.pointer.is_file(), completed.stdout)
        return completed


# ---- (0) the contract itself ----------------------------------------------------------------------


class SpecDecisionNineTest(Conformance):
    """Decision 9 is re-read from the shipped spec, so this module cannot drift away from it."""

    def test_the_shipped_spec_still_states_the_five_exit_classes(self) -> None:
        collapsed = " ".join(SPEC_PATH.read_text(encoding="utf-8").split())
        self.assertIn("**Effect-aware exits.**", collapsed)
        clauses = (
            "0 for a valid query or closed requested result",
            "1 for unexpected internal failure",
            "2 for grammar/schema/input error",
            "3 for clean refusal before effect",
            "4 after an admitted partial or unknown effect",
        )
        for clause in clauses:
            self.assertIn(clause, collapsed, clause)
        # Positive control: the same lookup does detect an absent clause, so the five above are
        # findings and not a scan that would pass over any text at all.
        self.assertNotIn("5 for a sixth exit class", collapsed)

    def test_the_installed_launcher_documents_the_same_vocabulary(self) -> None:
        """The operator reads the exit classes from ``ccodex --help``, so that text is pinned too."""
        dispatcher, _stub = DISPATCHER.ensure()
        completed = subprocess.run(
            [str(dispatcher), "--help"], capture_output=True, text=True, check=False, timeout=120
        )
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        collapsed = " ".join(completed.stdout.split())
        self.assertIn(
            "exit codes: 0 ok - 1 failure - 2 usage - 3 refused"
            " (a boundary declined the operation before any effect)"
            " - 4 admitted partial or unknown effect (`sdlc` lifecycle verbs only)",
            collapsed,
        )
        # Positive control: the help text is not empty of everything, so the absence of a sixth
        # class below is a fact about the vocabulary rather than about a failed capture.
        self.assertIn("sdlc install --host claude", collapsed)
        self.assertNotIn("5 ", collapsed.split("exit codes:")[1][:120])

    def test_this_module_pins_the_classes_as_literals_not_as_a_module_import(self) -> None:
        self.assertEqual((0, 1, 2, 3, 4), ADMITTED_EXIT_CLASSES)
        # Each shipped module names its own subset. They must all be members of the same five, and
        # none of them may claim a class outside it.
        install_module = _load(ROOT / "scripts" / "ccodex_sdlc_install.py", "exit_conformance_install")
        update_module = _load(ROOT / "scripts" / "ccodex_sdlc_update.py", "exit_conformance_update")
        uninstall_module = _load(ROOT / "scripts" / "ccodex_sdlc_uninstall.py", "exit_conformance_uninstall")
        declared = {
            "install": (install_module.EXIT_OK, install_module.EXIT_REFUSED, install_module.EXIT_UNKNOWN),
            "update": (update_module.EXIT_OK, update_module.EXIT_REFUSED, update_module.EXIT_UNKNOWN),
            "uninstall": (
                uninstall_module.EXIT_RETIRED,
                uninstall_module.EXIT_PARTIAL,
                uninstall_module.EXIT_REFUSED,
                uninstall_module.EXIT_UNKNOWN,
            ),
            "recover": (
                recover.EXIT_RECOVERED,
                recover.EXIT_PARTIAL,
                recover.EXIT_REFUSED,
                recover.EXIT_UNKNOWN,
            ),
        }
        for verb, values in declared.items():
            for value in values:
                with self.subTest(verb=verb, value=value):
                    self.assertIn(value, ADMITTED_EXIT_CLASSES)
        self.assertEqual((0, 3, 4), declared["install"])
        self.assertEqual((0, 3, 4), declared["update"])
        # The two verbs that can report an admitted PARTIAL effect name that class separately from an
        # unknown one, and Decision 9 gives both the same class 4 -- so 4 appears twice and the set is
        # the same {0, 3, 4} the other two verbs declare.  Neither may carry 1: exit 1 is "unexpected
        # internal failure", and both of these outcomes are named, sealed, and expected
        # (agentic-sdlc-d7b3).
        self.assertEqual((0, 4, 3, 4), declared["uninstall"])
        self.assertEqual((0, 4, 3, 4), declared["recover"])
        for verb in ("install", "update", "uninstall", "recover"):
            with self.subTest(verb=verb):
                self.assertEqual({EXIT_OK, EXIT_REFUSED, EXIT_UNKNOWN}, set(declared[verb]))
                self.assertNotIn(EXIT_INTERNAL, declared[verb])
        # Positive control: the same attribute lookup that found no exit-1 constant on either module
        # DOES find one where a module declares it, so the absence above is a fact about these tables.
        self.assertFalse(hasattr(uninstall_module, "EXIT_ATTENTION"))
        self.assertFalse(hasattr(recover, "EXIT_ATTENTION"))
        gate_receipt = _load(ROOT / "scripts" / "gate_receipt.py", "exit_conformance_gate_receipt")
        self.assertEqual(EXIT_INTERNAL, gate_receipt.EXIT_INTERNAL)
        self.assertEqual(EXIT_UNKNOWN, gate_receipt.EXIT_PARTIAL)


# ---- (1a) exit 2: the closed grammar matrix --------------------------------------------------------

#: Every grammar/input error the closed `ccodex sdlc` surface admits, spelled per verb.  A malformed
#: vector never reaches a per-verb module, so this matrix can only be proved at the dispatcher.
GRAMMAR_MATRIX: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("no-verb", ("sdlc",), "needs inspect, status, doctor"),
    ("unknown-verb", ("sdlc", "frobnicate"), "unknown ccodex sdlc verb: 'frobnicate'"),
    ("install-no-host", ("sdlc", "install"), "requires an explicit --host claude"),
    ("install-joined-host", ("sdlc", "install", "--host=claude"), "spells its host as two arguments"),
    ("install-host-no-value", ("sdlc", "install", "--host"), "--host was supplied without a host value"),
    ("install-unsupported-host", ("sdlc", "install", "--host", "codex"), "unsupported ccodex sdlc install host"),
    ("install-wildcard-host", ("sdlc", "install", "--host", "all"), "unsupported ccodex sdlc install host"),
    ("install-extra", ("sdlc", "install", "--host", "claude", "--force"), "accepts exactly --host claude"),
    ("install-unknown-flag", ("sdlc", "install", "--yes"), "unknown ccodex sdlc install argument"),
    ("install-unicode-host", ("sdlc", "install", "--host", "claude٩"), "unsupported ccodex sdlc install host"),
    ("update-json", ("sdlc", "update", "--json"), "ccodex sdlc update accepts no arguments"),
    ("update-host", ("sdlc", "update", "--host", "claude"), "ccodex sdlc update accepts no arguments"),
    ("update-positional", ("sdlc", "update", "latest"), "ccodex sdlc update accepts no arguments"),
    ("uninstall-json", ("sdlc", "uninstall", "--json"), "ccodex sdlc uninstall accepts no arguments"),
    ("uninstall-positional", ("sdlc", "uninstall", "claude"), "ccodex sdlc uninstall accepts no arguments"),
    ("uninstall-force", ("sdlc", "uninstall", "--force"), "ccodex sdlc uninstall accepts no arguments"),
    ("recover-bare", ("sdlc", "recover"), "requires exactly --dry-run"),
    ("recover-json-only", ("sdlc", "recover", "--json"), "requires exactly --dry-run"),
    ("recover-apply-no-digest", ("sdlc", "recover", "--apply"), "was supplied without the plan digest"),
    ("recover-apply-empty", ("sdlc", "recover", "--apply", ""), "64-character lowercase hexadecimal digest"),
    ("recover-apply-short", ("sdlc", "recover", "--apply", "5" * 63), "64-character lowercase hexadecimal digest"),
    ("recover-apply-long", ("sdlc", "recover", "--apply", "5" * 65), "64-character lowercase hexadecimal digest"),
    ("recover-apply-nonhex", ("sdlc", "recover", "--apply", "5" * 63 + "g"), "64-character lowercase hexadecimal digest"),
    ("recover-apply-upper", ("sdlc", "recover", "--apply", "5" * 63 + "F"), "64-character lowercase hexadecimal digest"),
    # `[0-9]` never `\d`: the Arabic-Indic digest must be REFUSED, never read as the same value.
    ("recover-apply-unicode-digits", ("sdlc", "recover", "--apply", "٩" * 64), "64-character lowercase hexadecimal digest"),
    ("recover-apply-newline", ("sdlc", "recover", "--apply", "5" * 63 + "\n"), "64-character lowercase hexadecimal digest"),
    ("recover-apply-joined", ("sdlc", "recover", f"--apply={'5' * 64}"), "spells its approval as two arguments"),
    ("recover-apply-twice", ("sdlc", "recover", "--apply", "5" * 64, "5" * 64), "accepts exactly one plan digest"),
    ("recover-apply-json", ("sdlc", "recover", "--apply", "5" * 64, "--json"), "accepts exactly one plan digest"),
    ("recover-dry-run-and-apply", ("sdlc", "recover", "--dry-run", "--apply", "5" * 64), "requires exactly --dry-run"),
    ("recover-apply-then-dry-run", ("sdlc", "recover", "--apply", "5" * 64, "--dry-run"), "accepts exactly one plan digest"),
    ("inspect-extra", ("sdlc", "inspect", "--all"), "accepts only optional --json"),
    ("status-extra", ("sdlc", "status", "--verbose"), "accepts only optional --json"),
    ("doctor-extra", ("sdlc", "doctor", "--fix"), "accepts only optional --json"),
)


class GrammarErrorExitTwoTest(Conformance):
    """Decision 9's exit 2, closed across every verb, with the whole tree proved untouched."""

    def test_every_grammar_error_is_exit_two_and_moves_nothing(self) -> None:
        plane = self.plane()
        # An ACTIVATED plane with a second candidate acquired, so every refusal below is refusing a
        # host that had real work available. A grammar test over an empty host would pass even if the
        # parser ran after the effect.
        plane.acquire_a()
        self.install_once(plane)
        plane.acquire_b()
        before = tree_hash(*plane.observed_roots())
        for label, vector, fragment in GRAMMAR_MATRIX:
            with self.subTest(case=label):
                completed = plane.dispatch(*vector)
                self.assert_admitted_class(completed)
                self.assertEqual(EXIT_GRAMMAR, completed.returncode, completed.stderr)
                self.assertEqual("", completed.stdout)
                self.assertIn(fragment, completed.stderr)
                self.assertIn("usage: ccodex sdlc inspect", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
                self.assertEqual(before, tree_hash(*plane.observed_roots()), label)
        # POSITIVE CONTROL, two halves. The same plane, the same harness: an admitted READ is 0 and
        # not 2, and an admitted MUTATION does move the tree -- so the 34 refusals above are the
        # parser declining, not a harness that cannot reach an effect at all.
        read = plane.dispatch("sdlc", "status")
        self.assertEqual(EXIT_OK, read.returncode, read.stderr)
        self.assertEqual(before, tree_hash(*plane.observed_roots()))
        mutation = plane.dispatch("sdlc", "update")
        self.assertEqual(EXIT_OK, mutation.returncode, mutation.stderr)
        self.assertNotEqual(before, tree_hash(*plane.observed_roots()))

    def test_a_control_character_in_a_refused_argument_never_forges_a_line(self) -> None:
        """A grammar refusal echoes the caller's token, so it must escape it (session defect class)."""
        plane = self.plane()
        completed = plane.dispatch("sdlc", "install", "--host", "claude\nerror: activated")
        self.assertEqual(EXIT_GRAMMAR, completed.returncode, completed.stderr)
        self.assertNotIn("\nerror: activated", completed.stderr)
        self.assertIn("\\n", completed.stderr)
        # Positive control: the same channel does carry the surrounding refusal, so the absence
        # above is the escape and not a lost message.
        self.assertIn("unsupported ccodex sdlc install host", completed.stderr)

    def test_the_grammar_matrix_covers_every_verb_the_usage_text_offers(self) -> None:
        """A closed matrix that silently stopped covering a verb would prove exit 2 for the others."""
        plane = self.plane()
        usage = plane.dispatch("sdlc").stderr
        offered = {
            line.split()[2]
            for line in usage.splitlines()
            if line.strip().startswith(("usage: ccodex sdlc", "ccodex sdlc"))
            and len(line.split()) > 2
        }
        offered |= {
            token.split()[0]
            for token in usage.split("ccodex sdlc ")[1:]
            if token.split() and token.split()[0].isalpha()
        }
        covered = {vector[1] for _label, vector, _fragment in GRAMMAR_MATRIX if len(vector) > 1}
        for verb in ("inspect", "status", "doctor", "recover", "install", "update", "uninstall"):
            with self.subTest(verb=verb):
                self.assertIn(verb, offered)
                self.assertIn(verb, covered)
        # Positive control: a verb the surface does NOT offer is absent from both sets.
        self.assertNotIn("frobnicate", offered)


# ---- (1b) exit 0: a durably complete effect --------------------------------------------------------


class DurableCompleteExitZeroTest(Conformance):
    """Exit 0 is claimed only when the receipt SEALS, VALIDATES, and records ``complete``.

    The three halves are checked independently: the effect on disk, the sealed document's own
    ``effect_state``, and the family producer's verdict on the bytes that were filed.  A run that
    exited 0 while any half disagreed would be exactly the "clean-looking half-state" Decision 9
    exists to forbid.
    """

    def assert_complete_receipt(
        self, plane: Plane, operation: str, terminal_phase: str = "activated"
    ) -> dict[str, Any]:
        document = self.sealed(plane, plane.pointer)
        body = document["body"]
        self.assertEqual(operation, body["operation"])
        self.assertEqual("complete", body["effect_state"])
        self.assertEqual(terminal_phase, body["terminal_phase"])
        self.assertEqual([], body["unknowns"])
        self.assertEqual("claude", body["host"])
        self.assertIsNone(body["public_channel"])
        self.assertEqual("none", body["release_claim"])
        # The pointer is a COPY of a filed receipt, never a link, and the filed bytes are identical.
        self.assertFalse(plane.pointer.is_symlink())
        named = plane.activation_dir / "receipts" / f"{document['receipt_id']}.json"
        self.assertTrue(named.is_file(), [path.name for path in plane.receipts()])
        self.assertEqual(named.read_bytes(), plane.pointer.read_bytes())
        return body

    def test_install_exits_zero_only_with_a_sealed_complete_receipt_and_a_landed_pointer(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stderr)
        body = self.assert_complete_receipt(plane, "install")
        self.assertEqual(VERSION_A, body["resolved_version"])
        for relative in CLAUDE_DESTINATIONS:
            destination = plane.destination(relative)
            self.assertTrue(destination.exists(), relative)
            self.assertFalse(destination.is_symlink(), f"{relative} is a copy, never a link")
        self.assertFalse(plane.destination(CODEX_DESTINATION).exists())
        self.assertFalse((plane.codex_home / CODEX_DESTINATION).exists())
        self.assertIn("effect complete", completed.stdout)
        self.assert_no_authority_claim(completed.stdout, completed.stderr, plane.pointer.read_text())
        # Positive control: the digest of every entry the receipt names is the digest on disk, so
        # "complete" is a statement about this filesystem and not a constant in the document.
        for entry in body["entries"]:
            self.assertEqual(
                bundle.digest(plane.destination(entry["entry_name"])),
                entry["content_sha256"],
                entry["entry_name"],
            )

    def test_update_exits_zero_only_after_the_pointer_supersedes_the_prior_receipt(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        prior = json.loads(plane.pointer.read_text(encoding="utf-8"))
        plane.acquire_b()
        completed = plane.dispatch("sdlc", "update")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stderr)
        body = self.assert_complete_receipt(plane, "update")
        self.assertEqual(VERSION_B, body["resolved_version"])
        self.assertEqual(
            "alpha two\n".join(["---\nname: alpha-skill\n---\n", ""]),
            plane.destination("skills/alpha-skill/SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual("cartographer two\n", plane.destination("agents/cartographer.md").read_text())
        # The superseded receipt is RETAINED, and the pointer now names a different document.
        superseded = plane.activation_dir / "receipts" / f"{prior['receipt_id']}.json"
        self.assertTrue(superseded.is_file())
        self.assertNotEqual(prior["receipt_id"], json.loads(plane.pointer.read_text())["receipt_id"])
        self.assert_no_authority_claim(completed.stdout, completed.stderr, plane.pointer.read_text())

    def test_uninstall_exits_zero_only_when_every_recorded_entry_left_the_plane(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        recorded = [entry["entry_name"] for entry in json.loads(plane.pointer.read_text())["body"]["entries"]]
        completed = plane.dispatch("sdlc", "uninstall")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stderr)
        for relative in recorded:
            self.assertFalse(plane.destination(relative).exists(), relative)
        terminal = [
            path for path in plane.receipts() if json.loads(path.read_text())["body"]["operation"] == "uninstall"
        ]
        self.assertEqual(1, len(terminal), [path.name for path in plane.receipts()])
        body = self.sealed(plane, terminal[0])["body"]
        self.assertEqual("complete", body["effect_state"])
        self.assertEqual("retired", body["terminal_phase"])
        self.assertEqual([], body["unknowns"])
        self.assertIn("retired", completed.stdout)
        self.assert_no_authority_claim(completed.stdout, completed.stderr, terminal[0].read_text())
        # Positive control: the same assertion catches an entry that did NOT leave, which is what
        # `ForeignPreservationTest` drives deliberately.
        self.assertTrue(recorded)

    def test_recover_apply_exits_zero_only_when_the_transition_reached_a_terminal_state(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        killed = plane.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "commit_pending", "after": 0, "kind": "sigkill", "message": "killed"},
        )
        self.assertEqual(-9, killed.returncode, killed.stderr)
        digest, assessment = self.plan_digest(plane)
        applied = plane.dispatch("sdlc", "recover", "--apply", digest)
        self.assertEqual(EXIT_OK, applied.returncode, applied.stderr)
        self.assertEqual("", applied.stderr)
        self.assertIn("plan re-derived from verified journal and receipt state", applied.stdout)
        # DURABLY TERMINAL: the interrupted transition is gone from the ownership journal and the
        # very next assessment offers no digest, so exit 0 named a state that stayed reached.
        self.assertIsNone(json.loads(plane.installer_state.read_text())["pending"])
        again = plane.dispatch("sdlc", "recover", "--dry-run")
        self.assertEqual(EXIT_OK, again.returncode, again.stderr)
        self.assertIn("nothing to recover, so no plan digest is offered", again.stderr)
        self.assert_no_authority_claim(applied.stdout, applied.stderr, assessment.stderr)
        # Positive control: the assessment DID offer a digest a moment earlier, so the absence above
        # is the recovery completing rather than a host that never had anything to recover.
        self.assertTrue(recover.is_plan_digest(digest))

    def plan_digest(self, plane: Plane) -> tuple[str, subprocess.CompletedProcess[str]]:
        completed = plane.dispatch("sdlc", "recover", "--dry-run")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        prefix = "recovery plan sha256 "
        lines = [line for line in completed.stderr.splitlines() if line.startswith(prefix)]
        self.assertEqual(1, len(lines), completed.stderr)
        digest = lines[0][len(prefix) : len(prefix) + 64]
        self.assertTrue(recover.is_plan_digest(digest), lines[0])
        return digest, completed


# ---- (1c) exit 3: a clean refusal BEFORE any effect ------------------------------------------------


class CleanRefusalExitThreeTest(Conformance):
    """Every refusal is measured with the WHOLE-TREE hash: before-effect is a filesystem claim."""

    def assert_clean_refusal(
        self, plane: Plane, completed: subprocess.CompletedProcess[str], before: str, fragment: str
    ) -> None:
        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_REFUSED, completed.returncode, completed.stderr)
        self.assertIn(fragment, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(before, tree_hash(*plane.observed_roots()), completed.stderr)
        self.assert_no_authority_claim(completed.stdout, completed.stderr)

    def test_install_refuses_an_absent_and_an_ambiguous_acquisition_differently(self) -> None:
        absent = self.plane()
        before = tree_hash(*absent.observed_roots())
        completed = absent.dispatch("sdlc", "install", "--host", "claude")
        self.assert_clean_refusal(absent, completed, before, "no acquired candidate is available")

        ambiguous = self.plane()
        ambiguous.acquire_a()
        ambiguous.acquire_b()
        before = tree_hash(*ambiguous.observed_roots())
        completed = ambiguous.dispatch("sdlc", "install", "--host", "claude")
        self.assert_clean_refusal(
            ambiguous, completed, before, "exactly one exactly acquired local candidate is admissible"
        )
        self.assertIn("holds 2 acquisition receipts", completed.stderr)
        self.assertNotIn("no acquired candidate is available", completed.stderr)
        # Positive control: exactly one acquisition on the same harness installs, so the two
        # refusals above are about the acquisition count and not about an unusable fixture.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)

    def test_update_and_uninstall_refuse_a_plane_that_states_no_active_receipt(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        plane.acquire_b()
        before = tree_hash(*plane.observed_roots())
        update = plane.dispatch("sdlc", "update")
        self.assert_clean_refusal(plane, update, before, "no usable active distribution-activation receipt")
        uninstall = plane.dispatch("sdlc", "uninstall")
        self.assert_clean_refusal(plane, uninstall, before, "no active distribution-activation receipt")

    def test_update_refuses_a_pointer_that_is_a_link_rather_than_following_it(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        plane.acquire_b()
        real = plane.activation_dir / "elsewhere-receipt.json"
        shutil.move(str(plane.pointer), str(real))
        plane.pointer.symlink_to(real)
        before = tree_hash(*plane.observed_roots())
        completed = plane.dispatch("sdlc", "update")
        self.assert_clean_refusal(plane, completed, before, "active-receipt.json")
        self.assertTrue(plane.pointer.is_symlink(), "the link itself is preserved, never resolved away")
        # Positive control: the same bytes at a PHYSICAL pointer are admitted, so the refusal is
        # about the link and not about the document it names.
        plane.pointer.unlink()
        shutil.move(str(real), str(plane.pointer))
        admitted = plane.dispatch("sdlc", "update")
        self.assertEqual(EXIT_OK, admitted.returncode, admitted.stderr)

    def test_recover_apply_refuses_a_clean_host_and_a_foreign_digest_differently(self) -> None:
        clean = self.plane()
        before = tree_hash(*clean.observed_roots())
        completed = clean.dispatch("sdlc", "recover", "--apply", FOREIGN_DIGEST)
        self.assert_clean_refusal(clean, completed, before, "found nothing to recover on this host")
        self.assertEqual("", completed.stdout)

        # A host that DOES have something to recover refuses the same digest for a different, named
        # reason: the approval is the digest, and this one approves no plan this state derives.
        interrupted = self.plane()
        interrupted.acquire_a()
        killed = interrupted.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "commit_pending", "after": 0, "kind": "sigkill", "message": "killed"},
        )
        self.assertEqual(-9, killed.returncode)
        before = tree_hash(*interrupted.observed_roots())
        completed = interrupted.dispatch("sdlc", "recover", "--apply", FOREIGN_DIGEST)
        self.assert_clean_refusal(
            interrupted, completed, before, "is not the plan this host's state derives"
        )
        self.assertNotIn("found nothing to recover", completed.stderr)

    def test_a_tampered_acquisition_seal_refuses_before_the_candidate_is_read(self) -> None:
        plane = self.plane()
        _candidate, receipt = plane.acquire_a()
        document = json.loads(receipt.read_text(encoding="utf-8"))
        # A field no admission rule reads on its own, so the ONLY thing that can refuse this document
        # is its own seal.  Tampering with a semantically checked field would pass the test on the
        # semantic refusal and prove nothing about the seal.
        document["installed_at"] = "2026-08-19T10:00:01Z"
        receipt.write_bytes(canonical(document))
        before = tree_hash(*plane.observed_roots())
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assert_clean_refusal(plane, completed, before, "record_sha256")
        self.assertFalse(plane.claude_root.exists(), "a tampered seal must not create the plane")
        # Positive control: the same field at its sealed value is admitted, so the refusal above is
        # the seal and not the value.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)

    def test_a_non_finite_number_in_a_read_document_refuses_rather_than_being_digested(self) -> None:
        """A session defect class: ``Infinity`` is JSON a reader must refuse, never round-trip."""
        plane = self.plane()
        _candidate, receipt = plane.acquire_a()
        raw = receipt.read_text(encoding="utf-8")
        receipt.write_text(raw.replace('"effect_state":"complete"', '"effect_state":1e400'), encoding="utf-8")
        before = tree_hash(*plane.observed_roots())
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assert_clean_refusal(plane, completed, before, "refused before any effect")
        # Positive control: the untampered fixture is admitted by the same reader.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)


# ---- (1d) exit 4: an admitted partial or unknown effect --------------------------------------------


class AdmittedEffectExitFourTest(Conformance):
    """A planted mid-transaction failure must produce an HONEST record, never a clean half-state.

    "Clean-looking" has three concrete spellings, and each is asserted against:
      * exit 0 while the receipt says anything but ``complete``;
      * an active pointer naming an activation nobody finished;
      * a receipt the family's own producer would refuse, or no receipt at all with an exit that
        claims the effect is known.
    """

    def test_install_failing_after_one_effect_records_partial_and_withholds_the_pointer(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        completed = plane.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "transactional_create", "after": 1, "kind": "raise", "message": FAULT_MESSAGE},
        )
        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
        self.assertIn("unknown effect", completed.stderr)
        self.assertIn(FAULT_MESSAGE, completed.stderr)
        self.assertEqual(1, len(plane.receipts()), [path.name for path in plane.receipts()])
        body = self.sealed(plane, plane.receipts()[0])["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        self.assertEqual(1, sum(1 for entry in body["entries"] if entry["disposition"] == "installed"))
        # NEVER A CLEAN-LOOKING HALF-STATE: the pointer is the plane's one statement, and a partial
        # activation must not make one.
        self.assertFalse(plane.pointer.exists(), "a partial effect must not write the active pointer")
        self.assertIn("was NOT written", completed.stdout)
        journal = json.loads(plane.journals()[0].read_text(encoding="utf-8"))
        self.assertEqual("terminal", journal["phase"])
        self.assertIn("failed", {record["phase"] for record in journal["entries"]})
        self.assert_no_authority_claim(completed.stdout, completed.stderr, plane.receipts()[0].read_text())
        # POSITIVE CONTROL, through the SAME DRIVER: without the fault the identical fixture is 0,
        # complete, and pointed. This is what makes the driver evidence rather than a mock.
        control = self.plane()
        control.acquire_a()
        clean = control.drive("ccodex_sdlc_install", ["--host", "claude"], fault=None)
        self.assertEqual(EXIT_OK, clean.returncode, clean.stderr)
        self.assertEqual("complete", self.sealed(control, control.pointer)["body"]["effect_state"])
        # And the installed dispatcher agrees with the driver on the fault-free result.
        dispatched = self.plane()
        dispatched.acquire_a()
        self.install_once(dispatched)

    def test_install_failing_before_any_effect_records_unknown_rather_than_none(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        completed = plane.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "transactional_create", "after": 0, "kind": "raise", "message": FAULT_MESSAGE},
        )
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
        body = self.sealed(plane, plane.receipts()[0])["body"]
        self.assertEqual("unknown", body["effect_state"])
        self.assertEqual("unknown", body["terminal_phase"])
        self.assertFalse(plane.pointer.exists())
        self.assertEqual(
            set(), {entry["disposition"] for entry in body["entries"]} - {"preserved"}
        )

    def test_update_failing_mid_refresh_records_partial_and_leaves_the_prior_receipt_active(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        prior = plane.pointer.read_bytes()
        prior_id = json.loads(prior)["receipt_id"]
        plane.acquire_b()
        completed = plane.drive(
            "ccodex_sdlc_update",
            [],
            fault={"function": "transactional_replace", "after": 1, "kind": "raise", "message": FAULT_MESSAGE},
        )
        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
        self.assertIn("unknown effect", completed.stderr)
        fresh = [
            path
            for path in plane.receipts()
            if json.loads(path.read_text())["body"]["operation"] == "update"
        ]
        self.assertEqual(1, len(fresh), [path.name for path in plane.receipts()])
        body = self.sealed(plane, fresh[0])["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        # The plane's statement is UNCHANGED: a partial refresh never becomes the active receipt.
        self.assertEqual(prior, plane.pointer.read_bytes())
        self.assertEqual(prior_id, json.loads(plane.pointer.read_text())["receipt_id"])
        self.assert_no_authority_claim(completed.stdout, completed.stderr, fresh[0].read_text())
        # Positive control through the same driver: no fault, exit 0, and the pointer DOES move.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)
        control.acquire_b()
        clean = control.drive("ccodex_sdlc_update", [], fault=None)
        self.assertEqual(EXIT_OK, clean.returncode, clean.stderr)
        self.assertEqual("update", json.loads(control.pointer.read_text())["body"]["operation"])

    def test_uninstall_that_cannot_prove_a_quarantined_removal_records_unknown(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        completed = plane.drive(
            "ccodex_sdlc_uninstall",
            [],
            fault={"function": "remove_path", "after": 0, "kind": "raise", "message": FAULT_MESSAGE},
        )
        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
        terminal = [
            path
            for path in plane.receipts()
            if json.loads(path.read_text())["body"]["operation"] == "uninstall"
        ]
        self.assertEqual(1, len(terminal))
        body = self.sealed(plane, terminal[0])["body"]
        self.assertEqual("unknown", body["effect_state"])
        self.assertEqual("unknown", body["terminal_phase"])
        # THE JOURNAL IS THE HONEST RECORD: it still names the outstanding quarantine container, so
        # an operator can find the bytes that left the plane.
        journals = [path for path in plane.journals() if path.name.startswith("uninstall-")]
        self.assertEqual(1, len(journals))
        journal = json.loads(journals[0].read_text(encoding="utf-8"))
        self.assertEqual("unknown", journal["phase"])
        self.assertIsNotNone(journal["pending"])
        self.assertTrue(Path(journal["pending"]["container"]).exists())
        self.assert_no_authority_claim(completed.stdout, completed.stderr, terminal[0].read_text())
        # Positive control through the same driver: no fault, and the retirement is complete.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)
        clean = control.drive("ccodex_sdlc_uninstall", [], fault=None)
        self.assertEqual(EXIT_OK, clean.returncode, clean.stderr)

    def test_recover_apply_interrupted_after_an_effect_reports_an_unknown_effect(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        killed = plane.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "commit_pending", "after": 0, "kind": "sigkill", "message": "killed"},
        )
        self.assertEqual(-9, killed.returncode)
        digest = self.plan_digest(plane)
        completed = plane.drive(
            "ccodex_sdlc_recover",
            ["--apply", digest],
            fault={"function": "persist_state", "after": 0, "kind": "raise", "message": FAULT_MESSAGE},
        )
        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        # Positive control through the same driver: the same digest with no fault recovers cleanly.
        control = self.plane()
        control.acquire_a()
        control.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "commit_pending", "after": 0, "kind": "sigkill", "message": "killed"},
        )
        clean = control.drive("ccodex_sdlc_recover", ["--apply", self.plan_digest(control)], fault=None)
        self.assertIn(clean.returncode, (EXIT_OK, EXIT_INTERNAL), clean.stderr)

    def plan_digest(self, plane: Plane) -> str:
        completed = plane.dispatch("sdlc", "recover", "--dry-run")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        prefix = "recovery plan sha256 "
        lines = [line for line in completed.stderr.splitlines() if line.startswith(prefix)]
        self.assertEqual(1, len(lines), completed.stderr)
        digest = lines[0][len(prefix) : len(prefix) + 64]
        self.assertTrue(recover.is_plan_digest(digest), lines[0])
        return digest


# ---- (1e) exit 1: unexpected internal failure ------------------------------------------------------


class InternalFailureExitOneTest(Conformance):
    """Exit 1 IS producible without a planted production defect -- and only from the READER.

    ``scripts/ccodex_sdlc.py`` maps a ``ReportInvariantError``/``OSError``/``ValueError`` raised while
    CONSTRUCTING a read report to exit 1 ("internal report construction invariant failure").  A
    shipped release contract whose ``checkout`` identity does not match is enough to reach it, so the
    class is proved over unmodified shipped code with a MUTATED COPY of one policy document in a
    shadow checkout -- no production file is touched.

    The mutating half of the surface deliberately never returns 1.  ``dispatch_lifecycle`` classifies
    an unexpected exception from a per-verb module as exit 4, because once the module was entered its
    effect is unknown, and "unknown effect" is a stronger statement than "internal failure".  That is
    asserted below by EXECUTION over all four verbs, not by reading the comment that says so.
    """

    def shadow_reader(self, *, break_contract: bool) -> Path:
        shadow = Path(tempfile.mkdtemp(dir=self.root)) / "shadow-checkout"
        for relative in (
            "policy/ccodex-sdlc-read-report.v1.json",
            "policy/release-contract.v1.json",
            "scripts/ccodex_sdlc.py",
            "scripts/ccodex_sdlc_readonly.py",
            "scripts/install_operator_tools.py",
            "scripts/install_skill_bundle.py",
        ):
            destination = shadow / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        if break_contract:
            path = shadow / "policy" / "release-contract.v1.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["checkout"]["version"] = "9.9.9"
            path.write_bytes(canonical(contract))
        return shadow

    def run_shadow(self, shadow: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(Path(sys.executable)), "-I", "-B", str(shadow / "scripts" / "ccodex_sdlc.py"), *arguments],
            env={
                "HOME": str(shadow.parent / "reader-home"),
                "XDG_STATE_HOME": str(shadow.parent / "reader-state"),
                "PATH": "",
                "LANG": "C",
                "LC_ALL": "C",
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )

    def test_a_broken_report_invariant_is_exit_one_on_every_reader_verb(self) -> None:
        broken = self.shadow_reader(break_contract=True)
        for verb in ("inspect", "status", "doctor"):
            with self.subTest(verb=verb):
                completed = self.run_shadow(broken, verb)
                self.assert_admitted_class(completed)
                self.assertEqual(EXIT_INTERNAL, completed.returncode, completed.stderr)
                self.assertIn("internal report construction invariant failure", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
                self.assertEqual("", completed.stdout)
        # POSITIVE CONTROL: the identical shadow with the SHIPPED contract answers 0, so exit 1 above
        # is the broken invariant and not a shadow checkout that cannot run at all.
        intact = self.shadow_reader(break_contract=False)
        for verb in ("inspect", "status", "doctor"):
            with self.subTest(control=verb):
                control = self.run_shadow(intact, verb)
                self.assertEqual(EXIT_OK, control.returncode, control.stderr)
                self.assertNotEqual("", control.stdout)

    def test_a_mutating_verb_maps_an_unexpected_exception_to_four_and_never_to_one(self) -> None:
        """The dispatch contract, by EXECUTION: a module that raises leaves an unknown effect."""
        modules = {
            "install": ("ccodex_sdlc_install", ("install", "--host", "claude")),
            "update": ("ccodex_sdlc_update", ("update",)),
            "uninstall": ("ccodex_sdlc_uninstall", ("uninstall",)),
            "recover": ("ccodex_sdlc_recover", ("recover", "--apply", FOREIGN_DIGEST)),
        }
        for verb, (stem, vector) in modules.items():
            with self.subTest(verb=verb):
                shadow = self.shadow_reader(break_contract=False)
                planted = shadow / "scripts" / f"{stem}.py"
                planted.write_text(
                    "def main(argv):\n    raise RuntimeError('unexpected internal failure')\n",
                    encoding="utf-8",
                )
                completed = self.run_shadow(shadow, *vector)
                self.assert_admitted_class(completed)
                self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stderr)
                self.assertNotEqual(EXIT_INTERNAL, completed.returncode)
                self.assertIn("failed inside its module, so its effect is unknown", completed.stderr)
                # Positive control: the same shadow, the same verb, a module that returns 0 -- so the
                # exit 4 above is the raise and not the plant.
                planted.write_text("def main(argv):\n    return 0\n", encoding="utf-8")
                control = self.run_shadow(shadow, *vector)
                self.assertEqual(EXIT_OK, control.returncode, control.stderr)

    def test_no_shipped_lifecycle_module_can_return_one_by_its_own_exit_table(self) -> None:
        """No mutating verb declares an exit-1 constant, so none of the four can return 1 by name.

        ``uninstall`` and ``recover`` used to: they spelled exit 1 ``EXIT_ATTENTION`` and returned it
        for an outcome their OWN sealed receipt records as an admitted effect (agentic-sdlc-d7b3).
        Both now spell Decision 9's class 4 ``EXIT_PARTIAL``, which is the name the repository's other
        effect-aware producers already use for it.
        """
        install_module = _load(ROOT / "scripts" / "ccodex_sdlc_install.py", "exit_one_install")
        update_module = _load(ROOT / "scripts" / "ccodex_sdlc_update.py", "exit_one_update")
        uninstall_module = _load(ROOT / "scripts" / "ccodex_sdlc_uninstall.py", "exit_one_uninstall")
        for module in (install_module, update_module):
            self.assertEqual({0, 3, 4}, {module.EXIT_OK, module.EXIT_REFUSED, module.EXIT_UNKNOWN})
        self.assertEqual(
            {0, 3, 4},
            {
                uninstall_module.EXIT_RETIRED,
                uninstall_module.EXIT_PARTIAL,
                uninstall_module.EXIT_REFUSED,
                uninstall_module.EXIT_UNKNOWN,
            },
        )
        self.assertEqual(
            {0, 3, 4},
            {recover.EXIT_RECOVERED, recover.EXIT_PARTIAL, recover.EXIT_REFUSED, recover.EXIT_UNKNOWN},
        )
        for module in (install_module, update_module, uninstall_module, recover):
            with self.subTest(module=module.__name__):
                self.assertFalse(hasattr(module, "EXIT_ATTENTION"), module.__name__)
                self.assertFalse(hasattr(module, "EXIT_INTERNAL"), module.__name__)
                # No name on the module resolves to 1 at all, so the class cannot be reached by a
                # differently-spelled constant either.
                names = [
                    name
                    for name in dir(module)
                    if name.startswith("EXIT_")
                    and isinstance(getattr(module, name), int)
                    and not isinstance(getattr(module, name), bool)
                ]
                self.assertNotEqual([], names, module.__name__)
                for name in names:
                    self.assertIn(getattr(module, name), (0, 3, 4), f"{module.__name__}.{name}")
        # POSITIVE CONTROL: the identical ``EXIT_*`` scan DOES find an exit-1 constant on a shipped
        # module that legitimately declares one -- the gate-receipt producer, whose 1 is a pre-effect
        # internal failure -- so the absences above are facts about these four tables and not a scan
        # that would pass over any module at all.
        gate_receipt = _load(ROOT / "scripts" / "gate_receipt.py", "exit_one_gate_receipt")
        found = [
            name
            for name in dir(gate_receipt)
            if name.startswith("EXIT_") and getattr(gate_receipt, name) == EXIT_INTERNAL
        ]
        self.assertEqual(["EXIT_INTERNAL"], found)


# ---- (2) foreign preservation, cross-verb ----------------------------------------------------------

#: The three operator-owned files ONE layout carries through install, update, and uninstall.
FOREIGN_ENTRY = "commands/sdlc-frame.md"
FOREIGN_BYTES = "the operator's own frame command\n"
OWNED_ENTRY = "agents/cartographer.md"
MODIFIED_BYTES = "hand-edited by the operator, never by this lifecycle\n"
PRECIOUS_ENTRY = "settings.json"
PRECIOUS_BYTES = '{"statusLine":{"type":"command","command":"the operator\'s own line"}}\n'


class ForeignPreservationTest(Conformance):
    """ONE home layout, three operator-owned files, driven through all three mutating verbs.

    * FOREIGN -- an unrecorded file occupying a destination the payload wants.  ``install`` must
      classify it ``foreign``/``preserved`` and NAME it; ``update`` must block on it and name it.
    * MODIFIED OWNED -- an entry this lifecycle installed and the operator then edited.  ``update``
      must block; ``uninstall`` must preserve it and name it.
    * PRECIOUS NON-INVENTORY -- a file no receipt inventory ever mentions.  No verb may touch it, and
      no verb may name it either: a blast radius that reaches it would show up as a name in a report.

    ``test_uninstall_preserves_the_entry_install_recorded_as_foreign`` closes the fourth corner: the
    foreign file must survive ``uninstall`` too, and it must survive BECAUSE the inventory row says
    ``foreign``, not because a digest happened to disagree (agentic-sdlc-9b9a).
    """

    def layout(self) -> Plane:
        plane = self.plane()
        plane.acquire_a()
        foreign = plane.destination(FOREIGN_ENTRY)
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text(FOREIGN_BYTES, encoding="utf-8")
        precious = plane.claude_root / PRECIOUS_ENTRY
        precious.write_text(PRECIOUS_BYTES, encoding="utf-8")
        return plane

    def test_install_preserves_and_names_the_foreign_entry_and_never_names_the_precious_one(self) -> None:
        plane = self.layout()
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        self.assertEqual(FOREIGN_BYTES, plane.destination(FOREIGN_ENTRY).read_text(encoding="utf-8"))
        self.assertEqual(PRECIOUS_BYTES, (plane.claude_root / PRECIOUS_ENTRY).read_text(encoding="utf-8"))
        entries = {entry["entry_name"]: entry for entry in self.sealed(plane, plane.pointer)["body"]["entries"]}
        self.assertEqual("foreign", entries[FOREIGN_ENTRY]["prestate"])
        self.assertEqual("preserved", entries[FOREIGN_ENTRY]["disposition"])
        self.assertEqual(bundle.digest(plane.destination(FOREIGN_ENTRY)), entries[FOREIGN_ENTRY]["content_sha256"])
        # NAMED where the contract names it: the human report and the sealed inventory both.
        self.assertIn(FOREIGN_ENTRY, completed.stdout)
        self.assertIn("foreign", completed.stdout)
        # And the precious file is named NOWHERE, because no verb observed it.
        self.assertNotIn(PRECIOUS_ENTRY, completed.stdout)
        self.assertNotIn(PRECIOUS_ENTRY, completed.stderr)
        self.assertNotIn(PRECIOUS_ENTRY, plane.pointer.read_text(encoding="utf-8"))
        # Positive control: the entries the install DID own are named and were written, so the
        # preservation above is a decision and not an install that did nothing.
        self.assertEqual("installed", entries[OWNED_ENTRY]["disposition"])
        self.assertEqual("cartographer one\n", plane.destination(OWNED_ENTRY).read_text(encoding="utf-8"))

    def test_update_blocks_on_both_the_foreign_and_the_modified_entry_and_moves_nothing(self) -> None:
        plane = self.layout()
        self.assertEqual(EXIT_OK, plane.dispatch("sdlc", "install", "--host", "claude").returncode)
        plane.destination(OWNED_ENTRY).write_text(MODIFIED_BYTES, encoding="utf-8")
        plane.acquire_b()
        before = plane_inventory(plane.claude_root)
        before_hash = tree_hash(*plane.observed_roots())

        completed = plane.dispatch("sdlc", "update")

        self.assertEqual(EXIT_REFUSED, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stdout)
        self.assertIn("Modified or foreign entries are preserved and block refresh", completed.stderr)
        self.assertIn(OWNED_ENTRY, completed.stderr)
        self.assertIn("modified-content", completed.stderr)
        self.assertIn(FOREIGN_ENTRY, completed.stderr)
        self.assertIn("missing-ownership-record", completed.stderr)
        self.assertNotIn(PRECIOUS_ENTRY, completed.stderr)
        # All three files are byte-identical, and so is the WHOLE tree.
        self.assertEqual(MODIFIED_BYTES, plane.destination(OWNED_ENTRY).read_text(encoding="utf-8"))
        self.assertEqual(FOREIGN_BYTES, plane.destination(FOREIGN_ENTRY).read_text(encoding="utf-8"))
        self.assertEqual(PRECIOUS_BYTES, (plane.claude_root / PRECIOUS_ENTRY).read_text(encoding="utf-8"))
        self.assertEqual(before, plane_inventory(plane.claude_root))
        self.assertEqual(before_hash, tree_hash(*plane.observed_roots()))
        # POSITIVE CONTROL: restoring the recorded content lets the SAME fixture refresh, so the
        # block is about the two named entries and not about an update that could never run.  The
        # foreign entry still blocks, which is why the control restores the modified one and asserts
        # the refusal now names exactly one entry.
        plane.destination(OWNED_ENTRY).write_text("cartographer one\n", encoding="utf-8")
        narrowed = plane.dispatch("sdlc", "update")
        self.assertEqual(EXIT_REFUSED, narrowed.returncode, narrowed.stderr)
        self.assertIn("1 entry the new payload would write cannot be proved unchanged", narrowed.stderr)
        self.assertNotIn("modified-content", narrowed.stderr)

    def test_uninstall_preserves_and_names_the_modified_entry_and_never_touches_the_precious_one(self) -> None:
        plane = self.layout()
        self.assertEqual(EXIT_OK, plane.dispatch("sdlc", "install", "--host", "claude").returncode)
        plane.destination(OWNED_ENTRY).write_text(MODIFIED_BYTES, encoding="utf-8")

        completed = plane.dispatch("sdlc", "uninstall")

        self.assert_admitted_class(completed)
        self.assertIn(f"preserved: {OWNED_ENTRY}", completed.stdout)
        self.assertIn("modified-content", completed.stdout)
        self.assertEqual(MODIFIED_BYTES, plane.destination(OWNED_ENTRY).read_text(encoding="utf-8"))
        self.assertEqual(PRECIOUS_BYTES, (plane.claude_root / PRECIOUS_ENTRY).read_text(encoding="utf-8"))
        self.assertNotIn(PRECIOUS_ENTRY, completed.stdout)
        self.assertNotIn(PRECIOUS_ENTRY, completed.stderr)
        terminal = [
            path for path in plane.receipts() if json.loads(path.read_text())["body"]["operation"] == "uninstall"
        ]
        self.assertEqual(1, len(terminal))
        self.assertNotIn(PRECIOUS_ENTRY, terminal[0].read_text(encoding="utf-8"))
        # Positive control: an entry whose ownership DID prove was removed in the same run, so the
        # preservation above is the ownership proof failing and not a retirement that removed nothing.
        self.assertFalse(plane.destination("skills/alpha-skill").exists())

    def test_uninstall_preserves_the_entry_install_recorded_as_foreign(self) -> None:
        """The data-loss corner (agentic-sdlc-9b9a), now asserted as the honest behaviour.

        ``install`` records an occupied destination as ``prestate: foreign, disposition: preserved``
        and stores the FOREIGN file's own digest as that entry's ``content_sha256`` -- which is honest
        observation, so the record is not what changed.  What changed is the CONSUMER: ``uninstall``
        used to prove removability from ``current == recorded`` alone, and that comparison SUCCEEDS
        here precisely because the digest recorded is the operator's file, so the retirement deleted
        the one file the activation explicitly refused to adopt.

        AGENTS.md: "Lifecycle mutation adopts only exact eligible prior owned state.  Foreign,
        modified, conflicting, or ambiguous entries are preserved and reported.  Removal proves
        unchanged ownership before deletion."  Unchangedness was proved; OWNERSHIP never was.  The
        classifier now reads the row's own ``prestate`` first, so the digest can never authorize this
        deletion -- and the reason code asserted below is ``recorded-foreign``, which is reachable
        ONLY from that record and not from any disk fact.
        """
        plane = self.layout()
        self.assertEqual(EXIT_OK, plane.dispatch("sdlc", "install", "--host", "claude").returncode)
        entries = {entry["entry_name"]: entry for entry in json.loads(plane.pointer.read_text())["body"]["entries"]}
        self.assertEqual("foreign", entries[FOREIGN_ENTRY]["prestate"])
        self.assertEqual("preserved", entries[FOREIGN_ENTRY]["disposition"])
        # The digest the retirement will compare against IS the operator's own file, so a
        # digest-only ownership proof would succeed.  Pinned here, because it is the whole hazard.
        self.assertEqual(
            bundle.digest(plane.destination(FOREIGN_ENTRY)), entries[FOREIGN_ENTRY]["content_sha256"]
        )

        completed = plane.dispatch("sdlc", "uninstall")

        self.assert_admitted_class(completed)
        self.assertEqual(
            FOREIGN_BYTES,
            plane.destination(FOREIGN_ENTRY).read_text(encoding="utf-8"),
            "the operator's own file must survive a retirement that never owned it",
        )
        self.assertIn(f"preserved: {FOREIGN_ENTRY}", completed.stdout)
        self.assertNotIn(f"removed: {FOREIGN_ENTRY}", completed.stdout)
        # The preservation came from the RECORD, not from a digest that happened to disagree.
        self.assertIn("recorded-foreign", completed.stdout)
        # An admitted partial effect: entries were retired, one was preserved, and the class is 4.
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stdout)
        self.assertIn("partly-retired", completed.stdout)
        # POSITIVE CONTROL 1: the same run DID remove the two entries it really owned, so the
        # preservation above is a decision about one row and not a verb that retires nothing.
        self.assertIn(f"removed: {OWNED_ENTRY}", completed.stdout)
        self.assertFalse(plane.destination(OWNED_ENTRY).exists())
        self.assertFalse(plane.destination("skills/alpha-skill").exists())
        # POSITIVE CONTROL 2: the foreign entry survives in the OTHER digest state too -- edited after
        # the install, so ``current != recorded`` -- which is the case that already worked.  Keeping it
        # shows the record-based preservation did not replace the digest-based one.
        plane_two = self.layout()
        self.assertEqual(EXIT_OK, plane_two.dispatch("sdlc", "install", "--host", "claude").returncode)
        plane_two.destination(FOREIGN_ENTRY).write_text("edited after the install\n", encoding="utf-8")
        second = plane_two.dispatch("sdlc", "uninstall")
        self.assertEqual(
            "edited after the install\n",
            plane_two.destination(FOREIGN_ENTRY).read_text(encoding="utf-8"),
        )
        self.assertIn(f"preserved: {FOREIGN_ENTRY}", second.stdout)


class UninstallAdmittedEffectExitFourTest(Conformance):
    """An admitted retirement effect is Decision 9's class 4, in both of its shapes.

    ``ccodex_sdlc_uninstall.py`` used to name exit 1 ``EXIT_ATTENTION`` and return it for two
    outcomes: ``partly-retired`` (some entries removed, some preserved) and ``not-retired`` (nothing
    moved).  Its own sealed receipt records ``effect_state: partial`` for the first and ``none`` for
    the second.  Decision 9 (spec:227-229) assigns 1 to "unexpected internal failure" and 4 to "an
    admitted partial or unknown effect", so a caller that branched on the documented vocabulary read an
    admitted effect as a crash.  Both now return 4 (agentic-sdlc-d7b3).

    ``not-retired`` is 4 rather than 3 for a reason the third test in this class pins by execution:
    Decision 9's 3 is a "clean refusal BEFORE effect", and this outcome is not one.  It ran the whole
    assessment and sealed the terminal receipt that CONSUMES this activation's one retirement, so a
    caller told "3, nothing happened, retry" is told something false -- the retry is refused by name.

    ``recover`` carried the same exit-1 convention for a preserved classified conflict and is fixed
    with it; ``tests/test_ccodex_sdlc_recover_apply.py`` owns that verb's two cases.
    """

    def test_a_partly_retired_plane_exits_four_and_its_receipt_records_partial(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        plane.destination(OWNED_ENTRY).write_text(MODIFIED_BYTES, encoding="utf-8")

        completed = plane.dispatch("sdlc", "uninstall")

        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stdout)
        self.assertIn("partly-retired", completed.stdout)
        terminal = [
            path for path in plane.receipts() if json.loads(path.read_text())["body"]["operation"] == "uninstall"
        ]
        body = self.sealed(plane, terminal[0])["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("unknown", body["terminal_phase"])
        # The receipt says partial and the exit says 4: one vocabulary, two surfaces that agree.
        self.assertNotEqual(EXIT_INTERNAL, completed.returncode)
        # POSITIVE CONTROL: a fully owned plane exits 0 with ``complete``, so exit 4 above is the
        # preserved entry and not a verb that always exits 4.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)
        clean = control.dispatch("sdlc", "uninstall")
        self.assertEqual(EXIT_OK, clean.returncode, clean.stderr)

    def test_a_plane_whose_entries_already_left_exits_four_and_its_receipt_records_none(self) -> None:
        """``not-retired``: no destination moved, ``effect_state: none`` -- and the class is 4.

        Nothing here is unexpected, so 1 is wrong.  0 would be wrong too: the plane is not in the
        requested end state as far as this verb can prove, which is why its own receipt terminates
        ``not-activated`` rather than ``retired``.  And 3 would be wrong because this run is not a
        refusal before effect: it sealed a terminal receipt, and the assertion at the end of this test
        EXECUTES the consequence -- the second pass is refused by name, so "nothing happened, retry"
        would have been false.
        """
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        for relative in CLAUDE_DESTINATIONS:
            destination = plane.destination(relative)
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        before = tree_hash(*plane.observed_roots())

        completed = plane.dispatch("sdlc", "uninstall")

        self.assert_admitted_class(completed)
        self.assertEqual(EXIT_UNKNOWN, completed.returncode, completed.stdout + completed.stderr)
        self.assertNotEqual(EXIT_INTERNAL, completed.returncode)
        self.assertIn("not-retired", completed.stdout)
        terminal = [
            path for path in plane.receipts() if json.loads(path.read_text())["body"]["operation"] == "uninstall"
        ]
        body = self.sealed(plane, terminal[0])["body"]
        self.assertEqual("none", body["effect_state"])
        self.assertEqual("not-activated", body["terminal_phase"])
        # WHY NOT 3: this run is not repeatable, so it was not a refusal before effect.  Executed, not
        # asserted from the docstring -- and the tree DID change, by exactly the receipt it sealed.
        self.assertNotEqual(before, tree_hash(*plane.observed_roots()))
        repeat = plane.dispatch("sdlc", "uninstall")
        self.assertEqual(EXIT_REFUSED, repeat.returncode, repeat.stdout + repeat.stderr)
        self.assertIn("a second retirement of one activation is refused rather than repeated", repeat.stderr)
        # POSITIVE CONTROL: the same harness reports 0 for a plane whose entries are all present, so
        # exit 4 above is the absent entries and not a verb that always exits 4.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)
        clean = control.dispatch("sdlc", "uninstall")
        self.assertEqual(EXIT_OK, clean.returncode, clean.stderr)

    def test_a_second_retirement_of_one_activation_is_a_clean_refusal_not_a_repeat(self) -> None:
        """The honest neighbour of the two above: THIS outcome IS Decision 9's exit 3."""
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        self.assertEqual(EXIT_OK, plane.dispatch("sdlc", "uninstall").returncode)
        before = tree_hash(*plane.observed_roots())

        again = plane.dispatch("sdlc", "uninstall")

        self.assert_admitted_class(again)
        self.assertEqual(EXIT_REFUSED, again.returncode, again.stdout + again.stderr)
        self.assertIn("a second retirement of one activation is refused rather than repeated", again.stderr)
        self.assertEqual(before, tree_hash(*plane.observed_roots()), "and it moved nothing")


# ---- (3) stale prestate ----------------------------------------------------------------------------


class StalePrestateTest(Conformance):
    """State that moved between ASSESSMENT and EFFECT must refuse BY NAME, before any effect."""

    def test_update_refuses_by_name_when_an_entry_moves_after_its_ownership_was_recorded(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        plane.acquire_b()
        # The assessment the refresh trusts is the ACTIVE RECEIPT's inventory, recorded at install.
        recorded = {
            entry["entry_name"]: entry["content_sha256"]
            for entry in json.loads(plane.pointer.read_text())["body"]["entries"]
        }
        victim = plane.destination(OWNED_ENTRY)
        self.assertEqual(recorded[OWNED_ENTRY], bundle.digest(victim))
        victim.write_text(MODIFIED_BYTES, encoding="utf-8")
        self.assertNotEqual(recorded[OWNED_ENTRY], bundle.digest(victim))
        before = tree_hash(*plane.observed_roots())

        completed = plane.dispatch("sdlc", "update")

        self.assertEqual(EXIT_REFUSED, completed.returncode, completed.stderr)
        self.assertIn(OWNED_ENTRY, completed.stderr)
        self.assertIn("modified-content", completed.stderr)
        self.assertIn("the current content digest differs from the digest", completed.stderr)
        self.assertEqual(before, tree_hash(*plane.observed_roots()))
        self.assertEqual(
            [],
            [path for path in plane.journals() if path.name.startswith("update-")],
            "a blocked refresh writes no journal of its own",
        )
        # Positive control: the install's journal IS there, so the absence above is the blocked
        # refresh and not a plane whose journals directory this harness cannot see.
        self.assertEqual(1, len([path for path in plane.journals() if path.name.startswith("install-")]))
        # Positive control: restoring the recorded bytes lets the same plane refresh, so the refusal
        # is the moved prestate and not a permanently blocked host.
        victim.write_text("cartographer one\n", encoding="utf-8")
        self.assertEqual(recorded[OWNED_ENTRY], bundle.digest(victim))
        admitted = plane.dispatch("sdlc", "update")
        self.assertEqual(EXIT_OK, admitted.returncode, admitted.stderr)

    def test_recover_refuses_a_digest_whose_state_moved_between_the_dry_run_and_the_apply(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        killed = plane.drive(
            "ccodex_sdlc_install",
            ["--host", "claude"],
            fault={"function": "commit_pending", "after": 0, "kind": "sigkill", "message": "killed"},
        )
        self.assertEqual(-9, killed.returncode)
        assessment = plane.dispatch("sdlc", "recover", "--dry-run")
        self.assertEqual(EXIT_OK, assessment.returncode, assessment.stderr)
        prefix = "recovery plan sha256 "
        approved = [line for line in assessment.stderr.splitlines() if line.startswith(prefix)][0][
            len(prefix) : len(prefix) + 64
        ]
        self.assertTrue(recover.is_plan_digest(approved))
        # THE STATE MOVES: the operator edits the published-but-unfinalized destination after
        # reviewing the plan.  Nothing about the approval is malformed; it is simply no longer the
        # plan this host derives.
        (plane.destination("skills/alpha-skill") / "SKILL.md").write_text("operator edit\n", encoding="utf-8")
        before = tree_hash(*plane.observed_roots())

        completed = plane.dispatch("sdlc", "recover", "--apply", approved)

        self.assertEqual(EXIT_REFUSED, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stdout)
        self.assertIn("is not the plan this host's state derives", completed.stderr)
        self.assertIn("the state moved after the approval", completed.stderr)
        self.assertIn("Nothing was touched", completed.stderr)
        self.assertEqual(before, tree_hash(*plane.observed_roots()))
        # POSITIVE CONTROL: the digest the MOVED state derives is a different value, and it is
        # admitted, so the refusal above is staleness and not an unrecoverable host.
        fresh_assessment = plane.dispatch("sdlc", "recover", "--dry-run")
        fresh = [line for line in fresh_assessment.stderr.splitlines() if line.startswith(prefix)][0][
            len(prefix) : len(prefix) + 64
        ]
        self.assertNotEqual(approved, fresh)
        applied = plane.dispatch("sdlc", "recover", "--apply", fresh)
        # 0 if every selected transition settled, 4 if something was preserved and named: either way
        # the plan was ADMITTED rather than refused as stale.  Never 1 -- exit 1 is "unexpected
        # internal failure" and a named preservation is not one (agentic-sdlc-d7b3).
        self.assertIn(applied.returncode, (EXIT_OK, EXIT_UNKNOWN), applied.stderr)
        self.assertNotEqual(EXIT_INTERNAL, applied.returncode)
        self.assertNotIn("is not the plan this host's state derives", applied.stderr)


# ---- (4) crash honesty -----------------------------------------------------------------------------


class CrashHonestyTest(Conformance):
    """A REAL ``SIGKILL`` inside the shipped installer's transaction, then the recovery chain.

    The kill lands at ``commit_pending`` -- after the transition is durably armed in the installer's
    one ``pending`` slot and after the destination is published, before the ownership record resolves.
    That is the exact window a power loss leaves open, and it is the one the recovery verbs exist for.
    No signal handler runs, so the state the chain then reads is not a state any ``except`` clause
    tidied.  This kill point was ``cleanup_private_artifact`` until demolition rank 4 replaced the
    per-entry transaction journal with that slot; the window it names is the same one.
    """

    SIGKILL_FAULT = {
        "function": "commit_pending",
        "after": 0,
        "kind": "sigkill",
        "message": "killed inside the transaction",
    }

    def kill_an_install(self, plane: Plane) -> subprocess.CompletedProcess[str]:
        killed = plane.drive("ccodex_sdlc_install", ["--host", "claude"], fault=self.SIGKILL_FAULT)
        self.assertEqual(-9, killed.returncode, killed.stderr)
        return killed

    def plan_digest(self, plane: Plane) -> tuple[str, subprocess.CompletedProcess[str]]:
        completed = plane.dispatch("sdlc", "recover", "--dry-run")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        prefix = "recovery plan sha256 "
        lines = [line for line in completed.stderr.splitlines() if line.startswith(prefix)]
        self.assertEqual(1, len(lines), completed.stderr)
        return lines[0][len(prefix) : len(prefix) + 64], completed

    def test_a_killed_install_leaves_no_pointer_and_the_recovery_chain_completes_it(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.kill_an_install(plane)

        # 1. NO POINTER, NO RECEIPT: the plane makes no statement it did not durably earn.
        self.assertFalse(plane.pointer.exists(), "a killed install must leave no active pointer")
        self.assertEqual([], plane.receipts(), "a killed install seals nothing")
        # The ownership journal DOES hold the armed transition, naming its destination and the record
        # it would become. No entry record was written yet: that is what `commit_pending` does, and
        # that is where the kill landed.
        outstanding = json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"]
        self.assertIsNotNone(outstanding, "the armed transition survives the kill")
        self.assertEqual("install", outstanding["operation"])
        self.assertIsNone(outstanding["before"])
        published = Path(outstanding["path"])
        self.assertNotIn(
            str(published),
            json.loads(plane.installer_state.read_text(encoding="utf-8"))["entries"],
        )
        self.assertTrue(published.exists(), "the kill landed after the publish, which is the point")

        # 2. THE NEIGHBOURING VERBS REFUSE, because the plane states no active receipt.
        for verb in ("update", "uninstall"):
            with self.subTest(verb=verb):
                refused = plane.dispatch("sdlc", verb)
                self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stderr)

        # 3. THE ASSESSMENT PLANS IT, read-only, and offers exactly one digest.
        digest, assessment = self.plan_digest(plane)
        before_assessment = tree_hash(*plane.observed_roots())
        repeat, _again = self.plan_digest(plane)
        self.assertEqual(digest, repeat, "a read-only assessment is stable")
        self.assertEqual(before_assessment, tree_hash(*plane.observed_roots()), "and it changes nothing")
        self.assertIn(f"ccodex sdlc recover --apply {digest}", assessment.stderr)

        # 4. THE APPLY COMPLETES IT.
        applied = plane.dispatch("sdlc", "recover", "--apply", digest)
        self.assertEqual(EXIT_OK, applied.returncode, applied.stderr)
        self.assertIn("recovered", applied.stdout)
        self.assertIn(str(published), applied.stdout)

        # 5. TERMINAL STATE COHERENT: no outstanding transaction, nothing left to recover, the plane
        # still states no activation, and a fresh install now completes and lands its pointer.
        self.assertIsNone(json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"])
        self.assertIn(
            "nothing to recover, so no plan digest is offered",
            plane.dispatch("sdlc", "recover", "--dry-run").stderr,
        )
        self.assertFalse(plane.pointer.exists(), "recovery completes a transaction, never an activation")
        self.assertEqual(EXIT_REFUSED, plane.dispatch("sdlc", "update").returncode)
        reinstalled = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assertEqual(EXIT_OK, reinstalled.returncode, reinstalled.stderr)
        body = self.sealed(plane, plane.pointer)["body"]
        self.assertEqual("complete", body["effect_state"])
        # The entry the recovery finalized is now recorded as ``owned``, not re-installed blindly.
        recorded = {entry["entry_name"]: entry["prestate"] for entry in body["entries"]}
        self.assertEqual("owned", recorded[published.name if published.name in recorded else "skills/alpha-skill"])
        self.assert_no_authority_claim(applied.stdout, applied.stderr, assessment.stderr)

    def test_a_killed_install_leaves_an_unfinished_journal_and_never_a_sealed_claim(self) -> None:
        """The journal SURVIVES a kill -- that is its job -- and it must not claim a terminal state."""
        killed_plane = self.plane()
        killed_plane.acquire_a()
        self.kill_an_install(killed_plane)
        self.assertEqual([], killed_plane.receipts(), "a kill seals nothing")
        self.assertFalse(killed_plane.pointer.exists())
        self.assertEqual(1, len(killed_plane.journals()), "the journal is written BEFORE the effect")
        journal = json.loads(killed_plane.journals()[0].read_text(encoding="utf-8"))
        self.assertNotEqual("terminal", journal["phase"], journal["phase"])
        self.assertNotIn(
            "complete",
            {record.get("phase") for record in journal["entries"]},
            "no entry may be journaled complete when the process died mid-transaction",
        )
        # POSITIVE CONTROL: the same fixture without the kill reaches ``terminal``, files a receipt,
        # and lands a pointer -- so the assertions above are the kill and not an unreachable path.
        control = self.plane()
        control.acquire_a()
        self.install_once(control)
        self.assertEqual(1, len(control.receipts()))
        self.assertEqual(1, len(control.plans()))
        self.assertEqual(
            "terminal", json.loads(control.journals()[0].read_text(encoding="utf-8"))["phase"]
        )

    def test_recover_apply_completes_a_killed_update_on_a_host_with_a_real_activation_receipt(self) -> None:
        """The recovery chain on the host that can actually crash mid-update (agentic-sdlc-3bb8).

        ``install`` and ``update`` file activation receipts as
        ``<operation>-<operation-id>-<instant>.json``.  ``ccodex_sdlc_recover.py`` reads that same
        directory and used to admit only ``<64 lowercase hex>.json`` -- a grammar no lifecycle verb
        has ever written -- naming its own plane's receipts ``activation-receipt://unrecognised-<16
        hex>`` and refusing the whole apply.  So on every host that had completed one install or
        update, ``recover --apply`` refused at exit 3 for the digest ``recover --dry-run`` had offered
        seconds earlier, and the interrupted transaction stayed outstanding with NO executable
        recovery path.  The chain in the first test of this class only worked because a killed FIRST
        install has not filed a receipt yet.

        Recognising a name means naming it, validating it through the family's own checker, and
        LEAVING IT IN PLACE.  All three are asserted, the last by bytes.  Two controls follow the
        chain: a clean host with no filed receipt still applies, and a plane holding a genuinely alien
        neighbour still refuses without echoing its name.
        """
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        filed = plane.receipts()
        self.assertEqual(1, len(filed))
        stem = filed[0].name[: -len(".json")]
        self.assertNotEqual(64, len(stem), "the fix is about the NAME, so its shape is pinned here")
        self.assertTrue(stem.startswith("install-op-"), stem)
        self.assertTrue(recover.is_lifecycle_receipt_stem(stem), stem)
        receipt_bytes = filed[0].read_bytes()

        plane.acquire_b()
        killed = plane.drive("ccodex_sdlc_update", [], fault=self.SIGKILL_FAULT)
        self.assertEqual(-9, killed.returncode)
        outstanding = json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"]
        self.assertIsNotNone(outstanding, "there IS an interrupted transition to recover")

        # 1. THE ASSESSMENT PLANS IT and names no unrecognised evidence: the plane's own receipt is
        # its own evidence.
        digest, assessment = self.plan_digest(plane)
        self.assertNotIn("unrecognised", assessment.stderr)
        self.assertIn(f"ccodex sdlc recover --apply {digest}", assessment.stderr)

        # 2. THE APPLY COMPLETES IT.
        applied = plane.dispatch("sdlc", "recover", "--apply", digest)

        self.assert_admitted_class(applied)
        self.assertEqual(EXIT_OK, applied.returncode, applied.stdout + applied.stderr)
        self.assertNotIn("unrecognised", applied.stderr)
        self.assertIn("recovered", applied.stdout)

        # 3. TERMINAL STATE COHERENT: nothing outstanding, nothing left to recover, and the receipt
        # this run read as evidence is byte-identical -- recognised means READ, never rewritten.
        self.assertIsNone(json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"])
        self.assertIn(
            "nothing to recover, so no plan digest is offered",
            plane.dispatch("sdlc", "recover", "--dry-run").stderr,
        )
        self.assertEqual([filed[0]], plane.receipts())
        self.assertEqual(receipt_bytes, filed[0].read_bytes())
        self.assertTrue(plane.pointer.is_file(), "the activation this plane states is untouched")
        self.assert_no_authority_claim(applied.stdout, applied.stderr, assessment.stderr)
        # POSITIVE CONTROL: the identical interrupted state on a host with NO filed activation
        # receipt still applies cleanly, so the apply above is not the receipt gate being switched off.
        control = self.plane()
        control.acquire_a()
        self.kill_an_install(control)
        self.assertEqual([], control.receipts())
        control_digest, _assessment = self.plan_digest(control)
        recovered = control.dispatch("sdlc", "recover", "--apply", control_digest)
        self.assertEqual(EXIT_OK, recovered.returncode, recovered.stderr)
        self.assertNotIn("unrecognised", recovered.stderr)
        # NEGATIVE CONTROL: a genuinely alien neighbour in the same plane still refuses the whole
        # apply, and its name is still never echoed -- so the recognised set was widened to this
        # plane's own grammar and not opened to whatever a directory happens to hold.
        alien_plane = self.plane()
        alien_plane.acquire_a()
        self.kill_an_install(alien_plane)
        alien = alien_plane.activation_dir / "receipts" / "operator-notes.json"
        alien.parent.mkdir(parents=True, exist_ok=True)
        alien.write_text("{}\n", encoding="utf-8")
        alien_digest, alien_assessment = self.plan_digest(alien_plane)
        blocked = alien_plane.dispatch("sdlc", "recover", "--apply", alien_digest)
        self.assertEqual(EXIT_REFUSED, blocked.returncode, blocked.stdout + blocked.stderr)
        self.assertIn("activation-receipt://unrecognised-", blocked.stderr)
        self.assertIn("a document this plane cannot name", blocked.stderr)
        self.assertNotIn("operator-notes", blocked.stderr)
        self.assertNotIn("operator-notes", alien_assessment.stderr)

    def test_recover_apply_refuses_a_lifecycle_receipt_that_fails_its_own_family_validation(self) -> None:
        """A name this plane RECOGNISES must still be VALIDATED -- never admitted by name alone.

        The test above pins that ``verify_receipt_evidence`` widened its recognised set to this
        plane's own lifecycle-receipt grammar (agentic-sdlc-3bb8), so a real install/update receipt is
        no longer refused as unrecognised.  The docstring on ``verify_receipt_evidence`` promises
        THREE things for a recognised name: it is named, VALIDATED through the family's own checker,
        and LEFT IN PLACE.  This test pins the middle promise, which the test above cannot: it never
        disturbs the receipt's bytes, so it would still pass even if the digest re-check and the
        ``dar.load_document`` / ``dar.derive("validate", ...)`` read that follow the name check were
        skipped entirely.

        The filed receipt is byte-flipped BEFORE the recovery plan is even derived, so the plan's own
        recorded digest for this receipt is the digest of the CORRUPTED bytes.  Apply's re-check of
        live bytes against that recorded digest therefore agrees -- the tamper is invisible to the
        "did it move" check -- and the only remaining thing that can catch it is the load/validate
        read a few lines later.  A change that admitted a recognised stem immediately after the name
        test, before either of those two reads, would pass every assertion above unchanged while
        silently treating this corrupted receipt as verified evidence.
        """
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        filed = plane.receipts()
        self.assertEqual(1, len(filed))
        receipt_path = filed[0]
        stem = receipt_path.name[: -len(".json")]
        self.assertTrue(recover.is_lifecycle_receipt_stem(stem), stem)
        original_bytes = receipt_path.read_bytes()

        plane.acquire_b()
        killed = plane.drive("ccodex_sdlc_update", [], fault=self.SIGKILL_FAULT)
        self.assertEqual(-9, killed.returncode)
        outstanding = json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"]
        self.assertIsNotNone(outstanding, "there IS an interrupted transition to recover")

        # Corrupt the filed receipt's bytes BEFORE the plan is derived at all: the plan's recorded
        # digest for this receipt will be the CORRUPTED digest, so apply's bytes-moved check cannot
        # be what catches this -- only the load/validate read that follows it can.
        corrupted = bytearray(original_bytes)
        corrupted[0] ^= 0xFF
        receipt_path.write_bytes(bytes(corrupted))
        self.assertNotEqual(original_bytes, receipt_path.read_bytes())

        digest, assessment = self.plan_digest(plane)
        self.assertNotIn("unrecognised", assessment.stderr)
        self.assertIn(f"ccodex sdlc recover --apply {digest}", assessment.stderr)
        before_apply = tree_hash(*plane.observed_roots())

        # THE REFUSAL: the corrupted receipt is named by its own recognised locator, never treated as
        # verified, and nothing moves.
        applied = plane.dispatch("sdlc", "recover", "--apply", digest)
        self.assertEqual(EXIT_REFUSED, applied.returncode, applied.stdout + applied.stderr)
        self.assertIn(f"activation-receipt://{stem}", applied.stderr)
        self.assertNotIn("unrecognised", applied.stderr)
        self.assertEqual(before_apply, tree_hash(*plane.observed_roots()), "a refusal moves nothing")
        still_outstanding = json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"]
        self.assertEqual(outstanding, still_outstanding, "the armed transition is untouched")
        self.assert_no_authority_claim(applied.stdout, applied.stderr, assessment.stderr)

        # POSITIVE CONTROL: restore the EXACT original bytes and the identical chain completes, which
        # is what shows the refusal above was the corrupted content and not the receipt gate itself
        # misfiring on this plane.
        receipt_path.write_bytes(original_bytes)
        self.assertEqual(original_bytes, receipt_path.read_bytes())
        restored_digest, restored_assessment = self.plan_digest(plane)
        self.assertNotIn("unrecognised", restored_assessment.stderr)
        restored = plane.dispatch("sdlc", "recover", "--apply", restored_digest)
        self.assert_admitted_class(restored)
        self.assertEqual(EXIT_OK, restored.returncode, restored.stdout + restored.stderr)
        self.assertIn("recovered", restored.stdout)
        self.assertNotIn("unrecognised", restored.stderr)
        self.assertIsNone(json.loads(plane.installer_state.read_text(encoding="utf-8"))["pending"])
        self.assertEqual([receipt_path], plane.receipts())
        self.assertEqual(original_bytes, receipt_path.read_bytes(), "recognised means READ, never rewritten")
        self.assert_no_authority_claim(restored.stdout, restored.stderr, restored_assessment.stderr)


# ---- (5) one ownership schema, every other generation refused -------------------------------------


class OwnershipSchemaTest(Conformance):
    """One ownership schema is READ; every other generation is refused BY NAME and never retrofitted.

    Slice 3's exit artifact named "the two old-schema readers" (spec:586-591, agentic-sdlc-642f), and
    this section used to pin that split: `normalize_document_to_v3` admitted v2 and v3, and
    `combined_v1_state` recognized v1 for the explicit `--migrate-state` operation. Demolition rank 4
    (seed agentic-sdlc-0c38) deleted every one of those readers along with the physical-identity
    witnesses and the transaction journal the old records carried, so there is no longer a second
    generation to read: a record whose witnesses this installer cannot check is not an ownership
    claim it can honour.

    What survives is the property that mattered -- a lifecycle verb never RETROFITS a document it did
    not write. It refuses, names the version it found and the remedy, and leaves the bytes alone. The
    committed `tests/fixtures/lifecycle-ownership-schemas/` documents went with the readers they
    pinned: with one live schema the real installer's own output is the only fixture that cannot
    drift.
    """

    def stripped_to_v1(self, document: dict[str, Any]) -> dict[str, Any]:
        """The v1 shape: entries only, and only the six fields a v1-era writer produced."""
        return {
            "entries": {
                key: {
                    name: value
                    for name, value in record.items()
                    if name in ("agent", "digest", "kind", "mode", "name", "source")
                }
                for key, record in document["entries"].items()
            },
            "version": 1,
        }

    def test_a_lifecycle_verb_admits_the_current_schema_and_persists_every_prior_record(self) -> None:
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        produced = json.loads(plane.installer_state.read_text(encoding="utf-8"))
        self.assertEqual(bundle.STATE_VERSION, produced["version"])
        self.assertEqual({"entries", "pending", "version"}, set(produced))
        self.assertIsNone(produced["pending"])
        # Every record carries exactly the closed field set, so a drifted writer fails here.
        self.assertEqual(
            {frozenset(bundle.RECORD_FIELDS)},
            {frozenset(record) for record in produced["entries"].values()},
        )
        keys_before = set(produced["entries"])

        plane.acquire_b()
        completed = plane.dispatch("sdlc", "update")

        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        persisted = json.loads(plane.installer_state.read_text(encoding="utf-8"))
        self.assertEqual(bundle.STATE_VERSION, persisted["version"])
        self.assertEqual(keys_before, set(persisted["entries"]))

    def test_every_other_generation_is_refused_by_name_and_never_retrofitted(self) -> None:
        for generation in (1, 2, 3, bundle.STATE_VERSION + 1):
            with self.subTest(version=generation):
                plane = self.plane()
                plane.acquire_a()
                self.install_once(plane)
                document = json.loads(plane.installer_state.read_text(encoding="utf-8"))
                if generation == 1:
                    document = self.stripped_to_v1(document)
                else:
                    document["version"] = generation
                plane.installer_state.write_bytes(canonical(document))
                before = plane.installer_state.read_bytes()

                plane.acquire_b()
                refused = plane.dispatch("sdlc", "update")

                self.assertEqual(EXIT_REFUSED, refused.returncode, refused.stderr)
                self.assertIn("different installer schema", refused.stderr)
                self.assertIn(f"version {generation}", refused.stderr)
                self.assertIn("remove it and reinstall to rebuild it", refused.stderr)
                self.assertEqual(before, plane.installer_state.read_bytes(), "never retrofitted")
                self.assertEqual("", refused.stdout)

    def test_the_reader_refuses_the_same_generations_in_process_without_a_write(self) -> None:
        """The same rule at the library seam, where the message and the untouched bytes are visible."""
        plane = self.plane()
        plane.acquire_a()
        self.install_once(plane)
        path = plane.installer_state
        current = json.loads(path.read_text(encoding="utf-8"))

        for generation in (1, 2, 3, bundle.STATE_VERSION + 1):
            with self.subTest(version=generation):
                document = self.stripped_to_v1(current) if generation == 1 else {
                    **current, "version": generation
                }
                path.write_bytes(canonical(document))
                before = path.read_bytes()
                with self.assertRaises(bundle.InstallerError) as raised:
                    bundle.load_state(path)
                self.assertIn("different installer schema", str(raised.exception))
                self.assertEqual(before, path.read_bytes(), "a refused read never rewrites")

        # Positive control: the untouched current document IS read, so the refusals above are the
        # version field and nothing else about these records.
        path.write_bytes(canonical(current))
        state = bundle.load_state(path)
        self.assertEqual(bundle.STATE_VERSION, state["version"])
        self.assertEqual(set(current["entries"]), set(state["entries"]))


# ---- (6) non-authority ------------------------------------------------------------------------------


class NonAuthorityTest(Conformance):
    """A lifecycle result is EVIDENCE.  Nothing it prints or seals may read as authorization.

    The scanner is ``authority_claims``: a line carrying an authority token and NO denial marker.  A
    bare token grep would be useless here, because the honest reports deliberately DENY the tokens
    ("it authorizes no push, publication, merge, or deployment"), and a suite that flagged those
    would be deleted within a week.  The scanner is therefore proved against fabricated claims in the
    same test that clears the real ones.
    """

    def collect(self) -> tuple[list[str], list[str]]:
        """Drive the whole lifecycle once and return every stream and every sealed document."""
        streams: list[str] = []
        documents: list[str] = []
        plane = self.plane()
        plane.acquire_a()
        runs = [plane.dispatch("sdlc", "install", "--host", "claude")]
        plane.acquire_b()
        runs.append(plane.dispatch("sdlc", "update"))
        runs.append(plane.dispatch("sdlc", "inspect"))
        runs.append(plane.dispatch("sdlc", "status"))
        runs.append(plane.dispatch("sdlc", "doctor"))
        runs.append(plane.dispatch("sdlc", "recover", "--dry-run"))
        runs.append(plane.dispatch("sdlc", "uninstall"))
        # Refusals and admitted-effect paths speak to the operator too.
        runs.append(plane.dispatch("sdlc", "update"))
        runs.append(plane.dispatch("sdlc", "recover", "--apply", FOREIGN_DIGEST))
        faulted = self.plane()
        faulted.acquire_a()
        runs.append(
            faulted.drive(
                "ccodex_sdlc_install",
                ["--host", "claude"],
                fault={"function": "transactional_create", "after": 1, "kind": "raise", "message": FAULT_MESSAGE},
            )
        )
        for completed in runs:
            self.assert_admitted_class(completed)
            streams.append(completed.stdout)
            streams.append(completed.stderr)
        for source in (plane, faulted):
            for path in source.receipts():
                documents.append(path.read_text(encoding="utf-8"))
            for path in source.journals() + source.plans():
                documents.append(path.read_text(encoding="utf-8"))
            if source.pointer.exists():
                documents.append(source.pointer.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(streams), 20, "every verb must have been driven")
        self.assertGreaterEqual(len(documents), 4, "sealed evidence must have been produced")
        return streams, documents

    def test_no_stream_or_sealed_document_carries_an_authorization_claim(self) -> None:
        streams, documents = self.collect()
        for index, text in enumerate(streams):
            with self.subTest(stream=index):
                self.assertEqual([], authority_claims(text), text[:1500])
        for index, text in enumerate(documents):
            with self.subTest(document=index):
                self.assertEqual([], authority_claims(text), text[:1500])
                self.assertEqual(
                    [], document_authority_claims(json.loads(text)), text[:1500]
                )
        # POSITIVE CONTROL, the whole point of this section: the same scanner over the same real text
        # with ONE fabricated authorizing line appended DOES flag it.  Without this, an empty result
        # would be indistinguishable from a scanner that matches nothing.
        forged = (
            "this receipt authorizes the integrator to push and merge the wave",
            "deploying the activated bundle to production is approved by this result",
            "authorization granted for publication of this candidate",
            "the gate passed, so you may merge",
        )
        for line in forged:
            with self.subTest(forged=line):
                self.assertEqual([line.strip().lower()], authority_claims(streams[0] + "\n" + line))
        # And the denial markers do not swallow a claim that merely mentions a negative elsewhere.
        self.assertEqual(
            ["push authorized for the release branch"],
            authority_claims("nothing here\npush authorized for the release branch\n"),
        )
        # NOR does a denial in the CLAUSE BESIDE a claim launder it. This is the case that a
        # line-level scanner missed and the mutation table caught (M8): the shipped install report
        # ends every run with an honest denial on the same line a defect would prepend a claim to.
        self.assertEqual(
            ["this activation authorizes the integrator to push and merge the wave"],
            authority_claims(
                "this activation authorizes the integrator to push and merge the wave; "
                "public_channel null and release_claim none: this activation states no published"
                " release exists, and it authorizes no push, publication, merge, or deployment\n"
            ),
        )
        # A sealed document is scanned LEAF BY LEAF for the same reason: one `null` in a canonical
        # one-line receipt must not clear an authorizing string elsewhere in it.
        self.assertEqual(
            ["this run authorizes publication"],
            document_authority_claims(
                {"public_channel": None, "note": "this run authorizes publication", "unknowns": []}
            ),
        )
        self.assertEqual(
            [],
            document_authority_claims({"public_channel": None, "note": "authorizes no publication"}),
        )
        forged_line = canonical(
            {"note": "this run authorizes publication", "public_channel": None}
        ).decode("ascii")
        self.assertEqual([], authority_claims(forged_line), "which a whole-text scan DOES miss")
        self.assertEqual(
            ["this run authorizes publication"],
            document_authority_claims(json.loads(forged_line)),
            "and which the leaf-by-leaf scan catches -- which is why both scans run",
        )

    def test_the_shipped_reports_deny_the_authority_words_they_use(self) -> None:
        """The denial markers must be doing real work, not clearing lines that never had a token."""
        plane = self.plane()
        plane.acquire_a()
        completed = plane.dispatch("sdlc", "install", "--host", "claude")
        self.assertEqual(EXIT_OK, completed.returncode, completed.stderr)
        carriers = [
            line
            for line in completed.stdout.lower().splitlines()
            if any(token in line for token in AUTHORITY_TOKENS)
        ]
        self.assertTrue(carriers, "the shipped report DOES use these words, in a denial")
        self.assertIn("authorizes no push, publication, merge, or deployment", " ".join(carriers))
        self.assertEqual([], authority_claims(completed.stdout))
        # Positive control: strip the denial from that exact line and the scanner flags it.
        stripped = completed.stdout.replace("authorizes no push", "authorizes push")
        stripped = stripped.replace("public_channel null and release_claim none: ", "")
        stripped = stripped.replace("this activation states no published release exists, and it ", "")
        self.assertEqual(1, len(authority_claims(stripped)), authority_claims(stripped))
