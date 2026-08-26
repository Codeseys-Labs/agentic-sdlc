"""``ccodex update --scope user --agent <agent>``: dual admission, a blocked refresh, one refresh, one seal.

THE OPERATOR SPELLING AND THIS MODULE'S ABI ARE TWO DIFFERENT FACTS, and neither is a mistake.
``ccodex sdlc update`` is retired at exit 2 and the front door is the top-level ``update`` with
``--scope``/``--agent``; this module is unchanged and still admits exactly ``['--host', <agent>]``,
still naming itself ``ccodex sdlc update`` in its own stdout and refusals, because the reader builds
that one vector in one place (``ccodex_sdlc.main``) and renaming the ABI would reach files this wave
does not own. So the in-process tests below drive ``--host`` and the subprocess test that goes through
the shipped reader drives ``--scope user --agent claude``; every message assertion quotes whichever of
the two actually emitted it.

WHAT THIS MODULE PROVES, AND HOW IT AVOIDS PROVING NOTHING.  Every negative assertion here carries a
POSITIVE CONTROL in the same test: an absence proves nothing unless the same harness is shown to
detect the presence.  A refusal test therefore always runs the same fixture twice -- once with the
defect and once without -- and every "nothing was written" assertion is paired with a run that does
write.

THE FIXTURE IS A FABRICATED PLANE, NOT A MOCK.  Each test builds TWO real candidate payload trees
under a real ``XDG_DATA_HOME``, two real sealed ``release-candidate-acquisition-receipt/v1``
documents under a real ``XDG_STATE_HOME``, and a real activated Claude home -- activated by driving
the SHIPPED installer's own ``transactional_create``, so the ownership records the refresh replaces
are the records production would hold.  The active ``distribution-activation@1`` receipt is sealed by
the family's OWN producer over the digests of the files that were really written, so a change to
either algorithm surfaces here rather than in production.

The end-to-end path is additionally driven through ``scripts/ccodex_sdlc.py`` in a subprocess under
the isolated ``-I -B`` Python 3.12.11 the dispatcher requires, because the in-process tests can
prove behaviour but not that the real dispatcher's contract is met.
"""

from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ccodex_sdlc_update.py"
RECEIPT_PRODUCER_PATH = ROOT / "scripts" / "distribution_activation_receipt.py"
INSTALLER_PATH = ROOT / "scripts" / "install_skill_bundle.py"
READER_PATH = ROOT / "scripts" / "ccodex_sdlc.py"
ENVELOPE_TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "receipt-envelope.py"
RECEIPT_PRODUCER_SHIM_PATH = ROOT / "scripts" / "write_acquisition_receipt.py"
RELEASE_CONTRACT_PATH = ROOT / "policy" / "release-contract.v1.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


update = _load(MODULE_PATH, "ccodex_sdlc_update_under_test")
receipts = _load(RECEIPT_PRODUCER_PATH, "ccodex_sdlc_update_receipt_producer")
bundle = _load(INSTALLER_PATH, "ccodex_sdlc_update_installer")
# The closed per-agent host-plane table, loaded directly for the pins that compare it against the
# shipped contract and against the module under test.
planes = _load(ROOT / "scripts" / "ccodex_sdlc_host_planes.py", "ccodex_sdlc_update_host_planes")
reader = _load(READER_PATH, "ccodex_sdlc_update_reader")
# The acquisition receipt's producer, pinned in place of the deleted acquisition policy's schema
# table: the contract this module re-expresses is now owned by the module that writes the document.
shim = _load(RECEIPT_PRODUCER_SHIM_PATH, "ccodex_sdlc_update_acquisition_shim")

PRIOR_INSTANT = "2026-08-19T09:10:11Z"
INSTANT = "2026-08-20T12:13:14Z"
LATER_INSTANT = "2026-08-20T12:45:00Z"
HOST_VERSION = "2.1.233"

ARCHIVE_A = hashlib.sha256(b"fabricated-archive-a").hexdigest()
ARCHIVE_B = hashlib.sha256(b"fabricated-archive-b").hexdigest()
CANDIDATE_A = hashlib.sha256(b"fabricated-candidate-a").hexdigest()
CANDIDATE_B = hashlib.sha256(b"fabricated-candidate-b").hexdigest()
OPERATION_A = "op-" + hashlib.sha256(b"fabricated-operation-a").hexdigest()[:32]
OPERATION_B = "op-" + hashlib.sha256(b"fabricated-operation-b").hexdigest()[:32]
VERSION_A = "0.7.3"
VERSION_B = "0.7.4"

#: The payload subset each fixture carries. One skill DIRECTORY with a nested file, one Claude agent,
#: one command, and one CODEX agent that a claude-host refresh must never touch.
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
CLAUDE_DESTINATIONS = ("skills/alpha-skill", "agents/cartographer.md", "commands/sdlc-frame.md")
CODEX_DESTINATION = "agents/cartographer.toml"


def executable_source(path: Path) -> str:
    """Re-render one module from its syntax tree with every docstring and comment removed.

    ``ast.unparse`` drops comments, and every module/class/function docstring is popped, so a
    forbidden-vocabulary scan reads what the module DOES rather than what its prose names.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if len(body) > 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                body.pop(0)
    return ast.unparse(tree)


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
    contract: dict[str, Any] | None = None,
    manifest_overrides: dict[str, Any] | None = None,
) -> Path:
    """One acquired candidate payload tree with its own manifest identity."""
    candidate_root = data_home / "agentic-sdlc" / "acquisition" / "candidates" / archive / "root"
    candidate_root.mkdir(parents=True)
    for relative, text in payload.items():
        target = candidate_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    contract_document = (
        contract if contract is not None else json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    )
    contract_path = candidate_root / "policy" / "release-contract.v1.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_bytes(canonical(contract_document))
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


def activate_with_the_shipped_installer(
    candidate_root: Path, home: Path, codex_home: Path, state_root: Path
) -> list[tuple[str, Path]]:
    """Copy-activate one candidate's claude entries through the SHIPPED installer's own transactions.

    The prestate this ticket refreshes is therefore the prestate production holds -- real copies plus
    real ownership records -- rather than a hand-written state file that could agree with a defect.
    """
    config = bundle.Config(candidate_root, home, codex_home, "copy", False, "claude", state_root)
    written: list[tuple[str, Path]] = []
    with bundle.installer_lock(config):
        state = bundle.load_config_state(config)
        for entry in bundle.discover_entries(candidate_root):
            if entry.agent != "claude":
                continue
            destination = bundle.destination_for(entry, config)
            bundle.ensure_collection(entry, destination, config)
            mode = bundle.transactional_create(entry, destination, config, state)
            assert mode == "copy", mode
            written.append(
                (destination.relative_to(bundle.agent_root(entry, config)).as_posix(), destination)
            )
    written.sort(key=lambda row: row[0])
    return written


def sealed_prior_receipt(
    entries: list[tuple[str, Path]],
    *,
    candidate_id: str = CANDIDATE_A,
    archive: str = ARCHIVE_A,
    version: str = VERSION_A,
    operation_id: str = OPERATION_A,
    instant: str = PRIOR_INSTANT,
    receipt_id: str | None = None,
    body_overrides: dict[str, Any] | None = None,
    entry_digest: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The ACTIVE receipt, sealed by the family's own producer over the digests really on disk."""
    rows: list[dict[str, Any]] = []
    for name, destination in entries:
        digest = (entry_digest or {}).get(name, bundle.digest(destination))
        rows.append(
            {
                "content_sha256": digest,
                "disposition": "installed",
                "entry_name": name,
                "mode": "copy",
                "prestate": "absent",
            }
        )
    rows.sort(key=lambda row: str(row["entry_name"]))
    body = {
        "archive_sha256": archive,
        "candidate_id": candidate_id,
        "effect_state": "complete",
        "entries": rows,
        "journal_sha256": hashlib.sha256(b"prior-journal").hexdigest(),
        "operation": "install",
        "plan_sha256": hashlib.sha256(b"prior-plan").hexdigest(),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": None,
        "resolved_version": version,
        "schema_version": receipts.BODY_SCHEMA,
        "scope": {"agent": "claude", "kind": "user"},
        "terminal_phase": "activated",
        "unknowns": [],
        "version_source": "archive-manifest",
    }
    body.update(body_overrides or {})
    compact = instant.replace("-", "").replace(":", "").lower()
    document = {
        "ancestors": [
            {
                "expected_kind": receipts.RECEIPT_KIND,
                "receipt_id": operation_id,
                "relation": "derived-from",
            }
        ],
        "body": body,
        "content_digest": "",
        "emitting_plane": "acquired-candidate",
        "receipt_id": receipt_id or f"install-{operation_id}-{compact}",
        "receipt_kind": receipts.RECEIPT_KIND,
        "schema": receipts.ENVELOPE_SCHEMA,
        "stated_at": instant,
    }
    result = receipts.derive("seal", document, "the prior activation")
    if result["verdict"] != receipts.VERDICT_SEALED:
        raise AssertionError(f"fixture did not seal: {result['reasons']}")
    sealed = result["receipt"]
    assert isinstance(sealed, dict)
    return sealed


@dataclass
class Fixture:
    root: Path
    home: Path
    state_home: Path
    data_home: Path
    codex_home: Path
    candidate_a: Path
    candidate_b: Path | None
    acquisition_a: Path
    acquisition_b: Path | None
    activated: list[tuple[str, Path]]
    prior_receipt: dict[str, Any]
    config: Any

    @property
    def claude_root(self) -> Path:
        return self.home / ".claude"

    @property
    def activation_dir(self) -> Path:
        return self.state_home / "agentic-sdlc" / "activation"

    @property
    def pointer(self) -> Path:
        """This plane's ONE pointer, at the KEYED path the filename-as-authority rule fixes.

        Spelled out rather than read from the module under test: the filename IS the admission
        authority, so a test that asked the writer where it wrote would agree with any path it chose.
        """
        return self.activation_dir / "active" / "claude" / "user.json"

    @property
    def legacy_pointer(self) -> Path:
        """Where the pre-keyed plane wrote its single pointer, for the migration cases."""
        return self.activation_dir / "active-receipt.json"

    def destination(self, relative: str) -> Path:
        return self.claude_root / relative

    def receipt_paths(self) -> list[Path]:
        directory = self.activation_dir / "receipts"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def journals(self) -> list[Path]:
        directory = self.activation_dir / "journals"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def plans(self) -> list[Path]:
        directory = self.activation_dir / "plans"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def journal(self) -> dict[str, Any]:
        paths = self.journals()
        assert len(paths) == 1, paths
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def new_receipt(self) -> dict[str, Any]:
        prior_name = f"{self.prior_receipt['receipt_id']}.json"
        fresh = [path for path in self.receipt_paths() if path.name != prior_name]
        assert len(fresh) == 1, fresh
        return json.loads(fresh[0].read_text(encoding="utf-8"))

    def config_at(self, instant: str = INSTANT, **overrides: Any) -> Any:
        """The plane's Config, with the certified platform injected by default.

        ``observed_system``/``observed_machine`` default to ``Linux``/``x86_64`` so every fixture
        is host-independent: without an explicit override, ``admit_platform`` sees the certified
        platform regardless of which real host runs this suite.  ``test_off_linux_refuses_by_name``
        overrides them to exercise the refusal itself (agentic-sdlc-e8a9).
        """
        values: dict[str, Any] = {
            "home": self.home,
            "state_home": self.state_home,
            "data_home": self.data_home,
            "codex_home": self.codex_home,
            "installer_state_root": self.state_home,
            "observed_host_version": HOST_VERSION,
            "observed_instant": instant,
            "observed_system": "Linux",
            "observed_machine": "x86_64",
        }
        values.update(overrides)
        return update.Config(**values)


def build_fixture(
    root: Path,
    *,
    payload_a: dict[str, str] | None = None,
    payload_b: dict[str, str] | None = None,
    version_b: str = VERSION_B,
    candidate_b_id: str = CANDIDATE_B,
    include_b: bool = True,
    contract_b: dict[str, Any] | None = None,
    manifest_overrides_b: dict[str, Any] | None = None,
    write_pointer: bool = True,
    retain_prior: bool = False,
    prior_body_overrides: dict[str, Any] | None = None,
    prior_entry_digest: dict[str, str] | None = None,
    drop_inventory_entries: tuple[str, ...] = (),
) -> Fixture:
    """Fabricate one ACTIVATED plane plus one different acquired candidate, ready to update."""
    home = root / "operator-home"
    state_home = root / "state"
    data_home = root / "data"
    codex_home = root / "codex-home"
    for directory in (home, state_home, data_home):
        directory.mkdir(parents=True, exist_ok=True)

    candidate_a = write_candidate(
        data_home, ARCHIVE_A, CANDIDATE_A, VERSION_A, payload_a or PAYLOAD_A
    )
    acquisition_a = write_acquisition_receipt(
        state_home, ARCHIVE_A, candidate_a, OPERATION_A, "2026-08-19T08:00:00Z"
    )
    candidate_b: Path | None = None
    acquisition_b: Path | None = None
    if include_b:
        candidate_b = write_candidate(
            data_home,
            ARCHIVE_B,
            candidate_b_id,
            version_b,
            payload_b or PAYLOAD_B,
            contract=contract_b,
            manifest_overrides=manifest_overrides_b,
        )
        acquisition_b = write_acquisition_receipt(
            state_home, ARCHIVE_B, candidate_b, OPERATION_B, "2026-08-20T08:00:00Z"
        )

    activated = activate_with_the_shipped_installer(candidate_a, home, codex_home, state_home)
    inventory = [row for row in activated if row[0] not in drop_inventory_entries]
    prior = sealed_prior_receipt(
        inventory, body_overrides=prior_body_overrides, entry_digest=prior_entry_digest
    )
    activation_dir = state_home / "agentic-sdlc" / "activation"
    (activation_dir / "receipts").mkdir(parents=True, exist_ok=True)
    if write_pointer:
        keyed = activation_dir / "active" / "claude" / "user.json"
        keyed.parent.mkdir(parents=True, exist_ok=True)
        keyed.write_bytes(receipts.canonical_bytes(prior))
    if retain_prior:
        (activation_dir / "receipts" / f"{prior['receipt_id']}.json").write_bytes(
            receipts.canonical_bytes(prior)
        )

    fixture = Fixture(
        root=root,
        home=home,
        state_home=state_home,
        data_home=data_home,
        codex_home=codex_home,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        acquisition_a=acquisition_a,
        acquisition_b=acquisition_b,
        activated=activated,
        prior_receipt=prior,
        config=None,
    )
    fixture.config = fixture.config_at()
    return fixture


@dataclass
class Outcome:
    code: int
    stdout: str
    stderr: str


#: The phrases this module's OWN platform refusal carries, one per observed axis.  Re-expressed rather
#: than imported, so a refusal that stopped naming its observation stops matching here.
PLATFORM_REFUSAL_FRAGMENTS = ("the observed operating system is", "the observed architecture is")


def skip_when_a_child_refused_this_host(
    case: unittest.TestCase, completed: subprocess.CompletedProcess[str]
) -> None:
    """Skip BY NAME when a child that observed the REAL platform refused this host, else return.

    The end-to-end check below runs the shipped reader in a child under ``-I``, which is the ONE place
    in this suite where ``Config.observed_system``/``observed_machine`` cannot reach: the child builds
    its configuration from the module's own ``default_config()``, and ``-I`` closes every environment
    and ``sitecustomize`` route an injected observation could have taken.  Off the certified linux-x64
    platform that child therefore refuses at exit 3 before any effect -- the product being correct --
    so the claim "the real dispatcher runs update end to end" is reported as a named skip instead of a
    failed exit-0 assertion (agentic-sdlc-e8a9).

    Positive control: the refusal must name THIS host's own observation, taken from the same
    ``platform`` module the shipped module reads.  A refusal about a platform this host is not buys no
    skip and stays a failure.  On the certified host no fragment matches at all, so nothing here can
    fire on the linux-x64 runner.
    """
    if completed.returncode != 3:
        return
    axes = (
        (PLATFORM_REFUSAL_FRAGMENTS[0], update.platform.system(), update.SUPPORTED_SYSTEM),
        (PLATFORM_REFUSAL_FRAGMENTS[1], update.platform.machine(), update.SUPPORTED_MACHINES),
    )
    for fragment, observed, certified in axes:
        if fragment not in completed.stderr:
            continue
        case.assertIn(f"{fragment} '{observed}'", completed.stderr, completed.stderr)
        case.skipTest(
            f"a child of this test observes the real platform, and the shipped module refused it by"
            f" name: {fragment} {observed!r}, not the certified {certified!r}"
        )


def call_main(
    fixture: Fixture,
    *,
    argv: list[str] | None = None,
    config: Any | None = None,
    fail_refresh_after: int | None = None,
    fail_observe_content_at: int | None = None,
) -> Outcome:
    """Drive ``main(["--host", <agent>])`` exactly as the dispatcher does, optionally injecting a fault.

    The default vector selects the Claude plane, which is what every fixture below builds; a codex-plane
    run passes its own ``argv`` and its own configuration.

    ``fail_refresh_after`` is injected at the seam a real interruption would hit: the shipped
    installer's ``transactional_replace``, on the sibling instance this run loads.  Patching the file
    would not work, because every run loads its own module object by absolute path.

    ``fail_observe_content_at`` is a DIFFERENT seam: the ONE-INDEXED call to this module's own
    ``observe_content`` that returns an unknown instead of a digest, leaving every other call --
    including the write each call follows -- to run for real.  Unlike a transaction fault, an
    observation fault never stops the refresh loop; it is recorded as an unknown and the walk
    continues, which is why this is a call COUNT rather than a permanent failure from that call on.
    """
    real_loader = update.load_sibling

    def loader(stem: str) -> ModuleType:
        module = real_loader(stem)
        if stem == "install_skill_bundle" and fail_refresh_after is not None:
            original = module.transactional_replace
            calls: list[int] = []

            def failing(*args: Any, **kwargs: Any) -> Any:
                calls.append(1)
                if len(calls) > fail_refresh_after:
                    raise module.InstallerError("fault-injected transaction failure")
                return original(*args, **kwargs)

            module.transactional_replace = failing
        return module

    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(update, "default_config", lambda: config or fixture.config))
        stack.enter_context(mock.patch.object(update, "load_sibling", loader))
        if fail_observe_content_at is not None:
            real_observe_content = update.observe_content
            observations: list[int] = []

            def failing_observe_content(
                bundle_module: ModuleType, path: Path | None
            ) -> tuple[str | None, str | None]:
                observations.append(1)
                if len(observations) == fail_observe_content_at:
                    return (
                        None,
                        "fault-injected observation failure: the digest could not be trusted",
                    )
                return real_observe_content(bundle_module, path)

            stack.enter_context(
                mock.patch.object(update, "observe_content", failing_observe_content)
            )
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        code = update.main(["--host", "claude"] if argv is None else argv)
    assert isinstance(code, int) and not isinstance(code, bool), repr(code)
    assert 0 <= code <= 4, code
    return Outcome(code, out.getvalue(), err.getvalue())


def plane_inventory(*roots: Path) -> dict[str, str]:
    """Every file under each root by path, with its digest, symlink target, and size."""
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


# Applied to every suite below whose fixtures publish through the shipped durable-write
# plane. ReExpressedContractsTest stays undecorated: it compares constants and shipped
# artifacts without touching that plane.
WINDOWS_SKIP = unittest.skipIf(
    os.name == "nt",
    "the ccodex lifecycle writes through the POSIX-only durable-write plane "
    "(os.open O_DIRECTORY fsync barriers) and pins exact path identity that Windows 8.3 "
    "short-name roots break; native Windows fails closed by name at the CLI",
)


class TemporaryRoot(unittest.TestCase):
    """One temporary directory per test, so no test can observe another's plane."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        # Resolved because the product admits only a fully PHYSICAL data home: on macOS `$TMPDIR`
        # lives under `/var/folders/...` and `/var` is a symlink to `/private/var`, so the
        # unresolved spelling trips the redirected-component refusal on every fixture. Fixtures
        # that plant their own symlinks do so UNDER this resolved root.
        self.root = Path(self._temp.name).resolve()

    def fixture(self, **kwargs: Any) -> Fixture:
        directory = Path(tempfile.mkdtemp(dir=self.root))
        return build_fixture(directory, **kwargs)

    def repoint(self, fixture: Fixture, **kwargs: Any) -> dict[str, Any]:
        """Re-seal this plane's ACTIVE receipt with overrides and rewrite the pointer."""
        prior = sealed_prior_receipt(fixture.activated, **kwargs)
        fixture.prior_receipt = prior
        fixture.pointer.write_bytes(receipts.canonical_bytes(prior))
        return prior


class ReExpressedContractsTest(TemporaryRoot):
    """The constants and decisions this module re-expresses must still agree with the shipped tree."""

    def test_acquisition_receipt_contract_matches_its_producer(self) -> None:
        self.assertEqual(
            tuple(sorted(shim.RECEIPT_KEYS)), tuple(sorted(update.ACQUISITION_RECEIPT_KEYS))
        )
        self.assertEqual(shim.RECEIPT_CONSTANTS, update.ACQUISITION_RECEIPT_CONSTANTS)
        self.assertEqual(
            "$XDG_STATE_HOME/" + "/".join(update.ACQUISITION_RECEIPT_SEGMENTS) + "/<archive-sha256>.json",
            shim.RECEIPT_LAYOUT,
        )
        self.assertEqual(
            "$XDG_DATA_HOME/"
            + "/".join(update.ACQUISITION_CANDIDATE_SEGMENTS)
            + f"/<archive-sha256>/{update.ACQUISITION_CANDIDATE_LEAF}",
            shim.CANDIDATE_ROOT_LAYOUT,
        )
        # Positive control: the same lookups do detect a disagreement.
        self.assertNotEqual(
            shim.RECEIPT_CONSTANTS, {**shim.RECEIPT_CONSTANTS, "selection": "chosen"}
        )

    def test_escape_display_agrees_with_the_receipt_producer(self) -> None:
        for sample in ("plain", "a\nb", "a\rb", "a\tb", "a\\b", "\x1b[2J", "\x7f", "٩"):
            with self.subTest(sample=sample):
                self.assertEqual(receipts.escape_display(sample), update.escape_display(sample))
        # Positive control: the escape is not the identity, so the agreement above is not vacuous.
        self.assertNotEqual("a\nb", update.escape_display("a\nb"))
        self.assertEqual("a\\nb", update.escape_display("a\nb"))

    def test_every_host_plane_has_the_shipped_contract_row_it_will_be_checked_against(self) -> None:
        """A plane in the closed table and not in the contract is the defect this equality catches."""
        contract = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        compatibility = contract["compatibility"]
        self.assertEqual(planes.AGENTS, ("claude", "codex"))
        self.assertEqual(update.CONTRACT_SECTION_CORE, planes.CONTRACT_SECTION_CORE)
        for agent in planes.AGENTS:
            plane = planes.plane_for(agent)
            with self.subTest(agent=agent):
                if plane.contract_section == planes.CONTRACT_SECTION_CORE:
                    row = compatibility[plane.contract_section]
                else:
                    row = compatibility[plane.contract_section][agent]
                self.assertEqual(row["host"], plane.contract_host)
        self.assertEqual([], compatibility["known_incompatible_host_versions"])

    def test_the_family_admits_no_removal_for_an_update_so_a_dropped_entry_is_preserved(self) -> None:
        """The recorded reason this module preserves rather than removes a dropped entry.

        If the family ever admitted ``removed`` for an update, this test fails and the preserve-only
        decision must be revisited deliberately instead of surviving as a stale comment.
        """
        self.assertNotIn("removed", receipts.OPERATION_DISPOSITIONS["update"])
        self.assertEqual(("installed", "preserved", "refreshed"), receipts.OPERATION_DISPOSITIONS["update"])
        # Positive control: the same lookup does report a removal for the operation that owns removal.
        self.assertIn("removed", receipts.OPERATION_DISPOSITIONS["uninstall"])
        self.assertIn("activated", receipts.OPERATION_PHASES["update"])
        # An update replaces exactly one earlier receipt, which is why this module seals two ancestors.
        self.assertIn("supersedes", receipts.FAMILY_RELATIONS)

    def test_module_carries_no_wildcard_purge_or_delete_vocabulary(self) -> None:
        """The MUST-NOTs are pinned in the CODE, with every docstring and comment stripped first.

        A naive line filter would read the prose that NAMES the forbidden vocabulary as a use of it,
        which is why the module is re-rendered from its own syntax tree instead.
        """
        code = executable_source(MODULE_PATH)
        for forbidden in (
            "--all",
            "purge",
            "rmtree",
            "transactional_delete",
            "remove_path",
            "durable_unlink",
            "ccodex_sdlc_install",
            "ccodex_sdlc_uninstall",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        # Positive control: the same search does find the tokens the module really uses.
        self.assertIn("transactional_replace", code)
        self.assertIn("transactional_create", code)

    def test_every_class_maps_to_one_prestate_and_only_the_admitted_classes_are_written(self) -> None:
        self.assertEqual(sorted(update.CLASS_PRESTATE), sorted(update.CLASS_REASON))
        for classification, prestate in update.CLASS_PRESTATE.items():
            with self.subTest(classification=classification):
                self.assertIn(prestate, receipts.PRESTATES)
        self.assertEqual(
            (update.CLASS_ABSENT, update.CLASS_OWNED_EXACT, update.CLASS_OWNED_CURRENT),
            update.ADMITTED_CLASSES,
        )
        # Positive control: a class outside the admitted tuple really is a blocking one.
        blocking = [name for name in update.CLASS_PRESTATE if name not in update.ADMITTED_CLASSES]
        self.assertIn(update.CLASS_MODIFIED, blocking)
        self.assertIn(update.CLASS_FOREIGN, blocking)


@WINDOWS_SKIP
class EndToEndUpdateTest(TemporaryRoot):
    def test_update_refreshes_owned_entries_and_seals_one_receipt_with_both_ancestors(self) -> None:
        fixture = self.fixture()
        prior_pointer = fixture.pointer.read_bytes()
        acquisitions = {
            path: path.read_bytes() for path in (fixture.acquisition_a, fixture.acquisition_b) if path
        }

        outcome = call_main(fixture)
        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertEqual("", outcome.stderr)

        # Every claude destination now holds the NEW payload's content, still as a copy.
        self.assertEqual("cartographer two\n", fixture.destination("agents/cartographer.md").read_text())
        self.assertEqual("frame two\n", fixture.destination("commands/sdlc-frame.md").read_text())
        self.assertEqual(
            "notes two\n", fixture.destination("skills/alpha-skill/references/notes.md").read_text()
        )
        for relative in CLAUDE_DESTINATIONS:
            with self.subTest(relative=relative):
                self.assertFalse(fixture.destination(relative).is_symlink())
        # A claude-host refresh never touches the codex plane, and there is no wildcard host.
        self.assertFalse((fixture.home / ".codex" / CODEX_DESTINATION).exists())
        self.assertFalse((fixture.codex_home / CODEX_DESTINATION).exists())

        receipt = fixture.new_receipt()
        body = receipt["body"]
        self.assertEqual("update", body["operation"])
        self.assertEqual(CANDIDATE_B, body["candidate_id"])
        self.assertEqual(ARCHIVE_B, body["archive_sha256"])
        self.assertEqual(VERSION_B, body["resolved_version"])
        self.assertIsNone(body["requested_version"])
        self.assertEqual("archive-manifest", body["version_source"])
        self.assertEqual("complete", body["effect_state"])
        self.assertEqual("activated", body["terminal_phase"])
        self.assertIsNone(body["public_channel"])
        self.assertEqual("none", body["release_claim"])
        self.assertEqual([], body["unknowns"])
        self.assertEqual(
            {("refreshed", "owned")}, {(row["disposition"], row["prestate"]) for row in body["entries"]}
        )
        self.assertEqual(
            [
                {"expected_kind": receipts.RECEIPT_KIND, "receipt_id": OPERATION_B, "relation": "derived-from"},
                {
                    "expected_kind": receipts.RECEIPT_KIND,
                    "receipt_id": fixture.prior_receipt["receipt_id"],
                    "relation": "supersedes",
                },
            ],
            receipt["ancestors"],
        )
        # Each inventory digest is the digest really on disk now, not the one the prior receipt held.
        for row in body["entries"]:
            with self.subTest(entry=row["entry_name"]):
                self.assertEqual(
                    bundle.digest(fixture.destination(str(row["entry_name"]))), row["content_sha256"]
                )

        # The pointer moved to THIS receipt, and the prior one is still readable under its own id.
        self.assertEqual(receipts.canonical_bytes(receipt), fixture.pointer.read_bytes())
        retained = fixture.activation_dir / "receipts" / f"{fixture.prior_receipt['receipt_id']}.json"
        self.assertEqual(prior_pointer, retained.read_bytes())
        # Both sealed acquisition receipts are byte-identical, and both payload roots survive.
        for path, before in acquisitions.items():
            with self.subTest(path=path.name):
                self.assertEqual(before, path.read_bytes())
        self.assertTrue((fixture.candidate_a / "manifest.json").is_file())
        assert fixture.candidate_b is not None
        self.assertTrue((fixture.candidate_b / "manifest.json").is_file())

    def test_the_new_receipt_validates_through_the_family_and_the_skills_plane_envelope(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        receipt = fixture.new_receipt()

        result = receipts.derive("validate", receipt, "the sealed update receipt")
        self.assertEqual(receipts.VERDICT_VALIDATED, result["verdict"], result["reasons"])

        path = fixture.root / "receipt-for-the-envelope.json"
        path.write_bytes(receipts.canonical_bytes(receipt))
        proof = subprocess.run(
            [sys.executable, str(ENVELOPE_TOOL), "verify", "--receipt", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, proof.returncode, proof.stderr)
        report = json.loads(proof.stdout)
        self.assertEqual("verified", report["verdict"], proof.stdout)
        self.assertEqual(
            {"derived-from", "supersedes"},
            {reference["relation"] for reference in receipt["ancestors"]},
        )
        # Positive control for the ENVELOPE checker: it refuses a body edit, because its content digest
        # seals the body. Its own residuals say the digest does NOT bind the ancestor list, which is
        # why the ancestor half is proved through the family's checker below instead.
        edited = json.loads(json.dumps(receipt))
        edited["body"]["resolved_version"] = "9.9.9"
        broken = fixture.root / "tampered.json"
        broken.write_bytes(receipts.canonical_bytes(edited))
        refusal = subprocess.run(
            [sys.executable, str(ENVELOPE_TOOL), "verify", "--receipt", str(broken)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual("verified", json.loads(refusal.stdout)["verdict"], refusal.stdout)
        # Positive control for the FAMILY checker's ancestor rule: an update with no supersedes is
        # refused, so the two ancestors above are a requirement this receipt met and not decoration.
        without = json.loads(json.dumps(receipt))
        without["ancestors"] = [
            reference for reference in without["ancestors"] if reference["relation"] != "supersedes"
        ]
        stripped = receipts.derive("validate", without, "an update with no supersedes")
        self.assertEqual(receipts.VERDICT_REFUSED, stripped["verdict"])
        self.assertIn("supersedes", " ".join(str(reason) for reason in stripped["reasons"]))

    def test_an_already_retained_prior_receipt_is_reused_and_a_different_one_refuses(self) -> None:
        reused = self.fixture(retain_prior=True)
        self.assertEqual(0, call_main(reused).code, "a byte-identical retained copy is the retained copy")

        conflicting = self.fixture()
        path = conflicting.activation_dir / "receipts" / f"{conflicting.prior_receipt['receipt_id']}.json"
        other = sealed_prior_receipt(conflicting.activated, version="0.7.2")
        path.write_bytes(receipts.canonical_bytes(other))
        before = plane_inventory(conflicting.claude_root)

        outcome = call_main(conflicting)
        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("error: ccodex sdlc update ", outcome.stderr)
        self.assertIn("as a DIFFERENT document", outcome.stderr)
        # Neither document was overwritten and no entry moved.
        self.assertEqual(receipts.canonical_bytes(other), path.read_bytes())
        self.assertEqual(before, plane_inventory(conflicting.claude_root))

    #: The reader's OPERATOR grammar for this verb: top-level, both selectors required, no default and
    #: no wildcard. What the reader then forwards to this module is `['--host', 'claude']`, which is
    #: why the in-process tests spell it that way and why the stdout assertion below still reads
    #: `ccodex sdlc update --host claude` -- that line is the MODULE's, not the reader's.
    READER_ARGV = ["update", "--scope", "user", "--agent", "claude"]

    def test_the_real_dispatcher_runs_update_end_to_end(self) -> None:
        """The shipped reader loads this module by absolute path and honours its integer exit class."""
        fixture = self.fixture()
        binary = fixture.root / "bin"
        binary.mkdir()
        stub = binary / "claude"
        stub.write_text(f"#!/bin/sh\necho '{HOST_VERSION} (Claude Code)'\n", encoding="utf-8")
        stub.chmod(0o755)
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(READER_PATH), *self.READER_ARGV],
            env={
                "HOME": str(fixture.home),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": str(binary),
                "XDG_STATE_HOME": str(fixture.state_home),
                "XDG_DATA_HOME": str(fixture.data_home),
                "CODEX_HOME": str(fixture.codex_home),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        skip_when_a_child_refused_this_host(self, completed)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn(
            "ccodex sdlc update --host claude: effect complete, terminal activated", completed.stdout
        )
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual("cartographer two\n", fixture.destination("agents/cartographer.md").read_text())
        receipt = fixture.new_receipt()
        self.assertEqual("update", receipt["body"]["operation"])
        self.assertEqual(receipts.canonical_bytes(receipt), fixture.pointer.read_bytes())
        self.assertEqual(
            receipts.VERDICT_VALIDATED,
            receipts.derive("validate", receipt, "the dispatched receipt")["verdict"],
        )
        # Positive control: the same dispatcher refuses the same plane once the pointer is gone.
        fixture.pointer.unlink()
        again = subprocess.run(
            [sys.executable, "-I", "-B", str(READER_PATH), *self.READER_ARGV],
            env={
                "HOME": str(fixture.home),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": str(binary),
                "XDG_STATE_HOME": str(fixture.state_home),
                "XDG_DATA_HOME": str(fixture.data_home),
                "CODEX_HOME": str(fixture.codex_home),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(3, again.returncode, again.stderr)
        self.assertIn("error: ccodex sdlc update ", again.stderr)
        self.assertNotIn("is unavailable in this distribution", again.stderr)
        self.assertEqual("", again.stdout)

    def test_an_entry_the_new_payload_no_longer_carries_is_preserved_and_named(self) -> None:
        payload = {name: text for name, text in PAYLOAD_B.items() if name != "commands/sdlc-frame.md"}
        fixture = self.fixture(payload_b=payload)
        outcome = call_main(fixture)
        self.assertEqual(0, outcome.code, outcome.stderr)

        dropped = fixture.destination("commands/sdlc-frame.md")
        # Preserved, not removed: the retired payload's content is still exactly there.
        self.assertEqual("frame one\n", dropped.read_text())
        self.assertIn("[not carried by the new payload]", outcome.stdout)
        rows = {row["entry_name"]: row for row in fixture.new_receipt()["body"]["entries"]}
        self.assertEqual("preserved", rows["commands/sdlc-frame.md"]["disposition"])
        self.assertEqual("owned", rows["commands/sdlc-frame.md"]["prestate"])
        self.assertEqual(bundle.digest(dropped), rows["commands/sdlc-frame.md"]["content_sha256"])
        # Positive control: the entries the new payload DOES carry were refreshed in the same run.
        self.assertEqual("refreshed", rows["agents/cartographer.md"]["disposition"])
        self.assertEqual("cartographer two\n", fixture.destination("agents/cartographer.md").read_text())

    def test_an_acquisition_receipt_written_during_the_run_is_an_unknown_effect(self) -> None:
        """The sealed acquisition receipt is this update's provenance and this module never writes it.

        A concurrent writer is simulated at the ONE point where the run has already had an effect, so
        the honest outcome is an unknown rather than a success with drifted provenance.
        """
        fixture = self.fixture()
        assert fixture.acquisition_b is not None

        def toucher(point: str) -> None:
            if point == "after-refresh":
                document = json.loads(fixture.acquisition_b.read_text(encoding="utf-8"))
                document["installed_at"] = "2026-08-20T08:00:02Z"
                fixture.acquisition_b.write_bytes(seal_acquisition(document))

        outcome = call_main(fixture, config=fixture.config_at(checkpoint=toucher))
        self.assertEqual(4, outcome.code, outcome.stderr)
        self.assertIn("changed during this run", outcome.stderr)
        self.assertIn("its provenance is no longer exact", outcome.stderr)
        # Positive control: with no concurrent writer the same plane completes and both sealed
        # acquisition receipts are byte-identical afterwards.
        clean = self.fixture()
        assert clean.acquisition_b is not None
        before = (clean.acquisition_a.read_bytes(), clean.acquisition_b.read_bytes())
        self.assertEqual(0, call_main(clean).code)
        self.assertEqual(before, (clean.acquisition_a.read_bytes(), clean.acquisition_b.read_bytes()))

    def test_an_absent_recorded_destination_is_installed_rather_than_blocked(self) -> None:
        fixture = self.fixture()
        victim = fixture.destination("agents/cartographer.md")
        victim.unlink()
        outcome = call_main(fixture)
        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertEqual("cartographer two\n", victim.read_text())
        rows = {row["entry_name"]: row for row in fixture.new_receipt()["body"]["entries"]}
        self.assertEqual("installed", rows["agents/cartographer.md"]["disposition"])
        self.assertEqual("absent", rows["agents/cartographer.md"]["prestate"])
        # Positive control: an entry that was present is recorded as a refresh in the same receipt.
        self.assertEqual("refreshed", rows["commands/sdlc-frame.md"]["disposition"])


@WINDOWS_SKIP
def sealed_v1_prior_receipt(entries: list[tuple[str, Path]]) -> dict[str, Any]:
    """One PRE-KEYED active receipt, in the read-only v1 generation, sealed WITHOUT the producer.

    ``seal`` refuses a v1 body by name -- history is never authored -- so this fixture derives the two
    digests directly, which is exactly what the v1 producer did. That is the only way to build the
    prestate a host activated before the scope union existed, and it is the prestate this update must
    admit exactly once as the outgoing document a v2 seal supersedes.
    """
    rows = [
        {
            "content_sha256": bundle.digest(destination),
            "disposition": "installed",
            "entry_name": name,
            "prestate": "absent",
        }
        for name, destination in entries
    ]
    rows.sort(key=lambda row: str(row["entry_name"]))
    body = {
        "activation_scope": "claude-home",
        "archive_sha256": ARCHIVE_A,
        "candidate_id": CANDIDATE_A,
        "effect_state": "complete",
        "entries": rows,
        "host": "claude",
        "journal_sha256": hashlib.sha256(b"v1-journal").hexdigest(),
        "operation": "install",
        "plan_sha256": hashlib.sha256(b"v1-plan").hexdigest(),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": None,
        "resolved_version": VERSION_A,
        "schema_version": receipts.BODY_SCHEMA_V1,
        "terminal_phase": "activated",
        "unknowns": [],
        "version_source": "archive-manifest",
    }
    sealed_body = receipts.seal_body(body)
    return {
        "ancestors": [
            {
                "expected_kind": receipts.RECEIPT_KIND,
                "receipt_id": OPERATION_A,
                "relation": "derived-from",
            }
        ],
        "body": sealed_body,
        "content_digest": receipts.envelope_content_digest(sealed_body, "the v1 prior activation"),
        "emitting_plane": "acquired-candidate",
        "receipt_id": "install-v1-activation",
        "receipt_kind": receipts.RECEIPT_KIND,
        "schema": receipts.ENVELOPE_SCHEMA,
        "stated_at": PRIOR_INSTANT,
    }


class GenerationMigrationTest(TemporaryRoot):
    """A v1-activated plane is updated ONCE, and the receipt this run seals is v2."""

    def test_a_v1_active_receipt_is_admitted_as_the_outgoing_document(self) -> None:
        fixture = self.fixture()
        prior = sealed_v1_prior_receipt(fixture.activated)
        self.assertEqual("validated", receipts.derive("validate", prior, "the v1 prior")["verdict"])
        fixture.pointer.write_bytes(receipts.canonical_bytes(prior))

        outcome = call_main(fixture)

        self.assertEqual(0, outcome.code, outcome.stderr)
        sealed = json.loads(fixture.pointer.read_text(encoding="utf-8"))
        self.assertEqual(receipts.BODY_SCHEMA, sealed["body"]["schema_version"])
        self.assertEqual({"agent": "claude", "kind": "user"}, sealed["body"]["scope"])
        self.assertNotIn("activation_scope", sealed["body"])
        self.assertEqual(
            [prior["receipt_id"]],
            [row["receipt_id"] for row in sealed["ancestors"] if row["relation"] == "supersedes"],
        )
        # The v1 document is RETAINED under its own id: history is kept, never rewritten.
        retained = fixture.activation_dir / "receipts" / f"{prior['receipt_id']}.json"
        self.assertEqual(receipts.canonical_bytes(prior), retained.read_bytes())

    def test_a_v1_receipt_about_another_scope_is_refused_rather_than_reinterpreted(self) -> None:
        fixture = self.fixture()
        prior = sealed_v1_prior_receipt(fixture.activated)
        body = dict(prior["body"])
        body["activation_scope"] = "some-other-plane"
        body["record_sha256"] = ""
        sealed_body = receipts.seal_body(body)
        fixture.pointer.write_bytes(
            receipts.canonical_bytes(
                {
                    **prior,
                    "body": sealed_body,
                    "content_digest": receipts.envelope_content_digest(sealed_body, "the v1 prior"),
                }
            )
        )

        outcome = call_main(fixture)

        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("states neither this verb's scope union", outcome.stderr)

    def test_a_legacy_pointer_alone_is_migrated_and_announced(self) -> None:
        fixture = self.fixture(write_pointer=False)
        fixture.legacy_pointer.write_bytes(receipts.canonical_bytes(fixture.prior_receipt))

        outcome = call_main(fixture)

        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertIn("migrated the legacy active pointer", outcome.stdout)
        self.assertFalse(fixture.legacy_pointer.exists())
        self.assertTrue(fixture.pointer.is_file())

    def test_both_pointers_present_refuses_naming_both_paths(self) -> None:
        fixture = self.fixture()
        fixture.legacy_pointer.write_bytes(fixture.pointer.read_bytes())
        before = {path: path.read_bytes() for path in (fixture.pointer, fixture.legacy_pointer)}

        outcome = call_main(fixture)

        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("legacy-pointer-ambiguity", outcome.stderr)
        self.assertIn(str(fixture.legacy_pointer), outcome.stderr)
        self.assertIn(str(fixture.pointer), outcome.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        # Positive control: with the ambiguity resolved the identical plane refreshes.
        fixture.legacy_pointer.unlink()
        self.assertEqual(0, call_main(fixture).code)

    def test_a_pointer_whose_receipt_names_another_scope_refuses_on_the_pointer_axis(self) -> None:
        fixture = self.fixture()
        self.repoint(
            fixture,
            body_overrides={"scope": {"agent": "claude", "kind": "project", "root": str(fixture.root / "repo")}},
        )

        outcome = call_main(fixture)

        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("pointer-receipt-disagreement", outcome.stderr)
        self.assertIn("is a user-scope pointer while the receipt it names records scope.kind", outcome.stderr)


class AdmissionRefusalTest(TemporaryRoot):
    """Both admissions refuse BY NAME before any effect, and each refusal has a positive control."""

    def assert_clean_refusal(self, fixture: Fixture, outcome: Outcome, *fragments: str) -> None:
        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertEqual("", outcome.stdout)
        self.assertIn("error: ccodex sdlc update ", outcome.stderr)
        self.assertNotIn("Traceback", outcome.stderr)
        for fragment in fragments:
            self.assertIn(fragment, outcome.stderr)
        self.assertEqual([], fixture.plans())
        self.assertEqual([], fixture.journals())

    def test_no_active_receipt_refuses_by_name(self) -> None:
        fixture = self.fixture(write_pointer=False)
        before = plane_inventory(fixture.claude_root)
        outcome = call_main(fixture)
        self.assert_clean_refusal(
            fixture,
            outcome,
            "found no usable active distribution-activation receipt",
            "install --host claude` is the front door",
        )
        self.assertEqual(before, plane_inventory(fixture.claude_root))
        # Positive control: the identical fixture with the pointer written completes.
        fixture.pointer.parent.mkdir(parents=True, exist_ok=True)
        fixture.pointer.write_bytes(receipts.canonical_bytes(fixture.prior_receipt))
        self.assertEqual(0, call_main(fixture).code)

    def test_an_unsealed_or_tampered_active_receipt_refuses(self) -> None:
        fixture = self.fixture()
        tampered = json.loads(json.dumps(fixture.prior_receipt))
        tampered["body"]["resolved_version"] = "9.9.9"
        fixture.pointer.write_bytes(receipts.canonical_bytes(tampered))
        outcome = call_main(fixture)
        self.assert_clean_refusal(fixture, outcome, "does not validate as", receipts.BODY_SCHEMA)
        # Positive control: restoring the sealed bytes admits the same plane.
        fixture.pointer.write_bytes(receipts.canonical_bytes(fixture.prior_receipt))
        self.assertEqual(0, call_main(fixture).code)

    def test_an_active_receipt_that_is_a_link_refuses_rather_than_being_followed(self) -> None:
        fixture = self.fixture()
        elsewhere = fixture.root / "elsewhere.json"
        elsewhere.write_bytes(receipts.canonical_bytes(fixture.prior_receipt))
        fixture.pointer.unlink()
        fixture.pointer.symlink_to(elsewhere)
        outcome = call_main(fixture)
        self.assert_clean_refusal(fixture, outcome, "is a link")
        # Positive control: the same bytes as a regular file at the same path are admitted.
        fixture.pointer.unlink()
        fixture.pointer.write_bytes(elsewhere.read_bytes())
        self.assertEqual(0, call_main(fixture).code)

    def test_a_retired_active_receipt_refuses_because_there_is_nothing_to_update_over(self) -> None:
        fixture = self.fixture()
        retired_rows = [
            {
                "content_sha256": None,
                "disposition": "removed",
                "entry_name": name,
                "mode": "copy",
                "prestate": "owned",
            }
            for name, _ in fixture.activated
        ]
        self.repoint(
            fixture,
            body_overrides={
                "entries": sorted(retired_rows, key=lambda row: str(row["entry_name"])),
                "operation": "uninstall",
                # A v2 retirement body carries the closed prestate-evidence discriminator, and this
                # one derives from the receipt it retires -- so exactly one `derived-from` ancestor,
                # which the fixture already writes.
                "prestate_evidence": "activation-receipt",
                "terminal_phase": "retired",
            },
        )
        outcome = call_main(fixture)
        self.assert_clean_refusal(fixture, outcome, "records operation 'uninstall'")
        # Positive control: the live activation the same harness seals is admitted.
        self.repoint(fixture)
        self.assertEqual(0, call_main(fixture).code)

    def test_an_activated_partial_plane_is_updatable_but_a_not_activated_one_is_not(self) -> None:
        refused = self.fixture()
        self.repoint(
            refused,
            body_overrides={"effect_state": "none", "terminal_phase": "not-activated", "entries": []},
        )
        outcome = call_main(refused)
        self.assert_clean_refusal(refused, outcome, "terminates 'not-activated'")
        # Positive control: `activated-partial` is a live plane and the same harness updates it.
        admitted = self.fixture()
        self.repoint(
            admitted,
            body_overrides={"effect_state": "partial", "terminal_phase": "activated-partial"},
        )
        self.assertEqual(0, call_main(admitted).code)

    def test_the_same_identity_selection_refuses_on_both_axes(self) -> None:
        only_active = self.fixture(include_b=False)
        outcome = call_main(only_active)
        self.assert_clean_refusal(
            only_active,
            outcome,
            "is the one this plane already activated",
            "a re-activation of the same identity is never silent",
        )

        same_candidate = self.fixture(candidate_b_id=CANDIDATE_A)
        second = call_main(same_candidate)
        self.assert_clean_refusal(
            same_candidate,
            second,
            "which is the identity this plane already activated",
            "There is nothing to update",
        )
        # Positive control: a DIFFERENT identity through the identical harness completes.
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_two_other_acquired_candidates_are_an_ambiguity_this_update_refuses(self) -> None:
        fixture = self.fixture()
        third_archive = hashlib.sha256(b"fabricated-archive-c").hexdigest()
        third_root = write_candidate(
            fixture.data_home,
            third_archive,
            hashlib.sha256(b"fabricated-candidate-c").hexdigest(),
            "0.7.5",
            PAYLOAD_B,
        )
        write_acquisition_receipt(
            fixture.state_home,
            third_archive,
            third_root,
            "op-" + hashlib.sha256(b"fabricated-operation-c").hexdigest()[:32],
            "2026-08-20T09:00:00Z",
        )
        outcome = call_main(fixture)
        self.assert_clean_refusal(
            fixture, outcome, "acquired candidates other than the active one", "would be a guess"
        )
        # Positive control: removing the ambiguity leaves exactly one admissible candidate.
        (fixture.state_home / "agentic-sdlc" / "acquisition" / "receipts" / f"{third_archive}.json").unlink()
        self.assertEqual(0, call_main(fixture).code)

    def test_a_tampered_acquisition_seal_refuses_before_the_candidate_is_read(self) -> None:
        fixture = self.fixture()
        assert fixture.acquisition_b is not None
        document = json.loads(fixture.acquisition_b.read_text(encoding="utf-8"))
        document["installed_at"] = "2026-08-20T08:00:01Z"
        fixture.acquisition_b.write_bytes(canonical(document))
        outcome = call_main(fixture)
        self.assert_clean_refusal(fixture, outcome, "mismatched pair")
        # Positive control: the resealed receipt for the same values is admitted.
        fixture.acquisition_b.write_bytes(seal_acquisition(document))
        self.assertEqual(0, call_main(fixture).code)

    def test_off_linux_refuses_by_name(self) -> None:
        fixture = self.fixture()
        outcome = call_main(fixture, config=fixture.config_at(observed_system="Darwin"))
        self.assert_clean_refusal(
            fixture, outcome, "certified only on Linux", "the observed operating system is 'Darwin'"
        )
        machine = call_main(fixture, config=fixture.config_at(observed_machine="aarch64"))
        self.assert_clean_refusal(fixture, machine, "the observed architecture is 'aarch64'")
        # Positive control: the same plane on the certified platform completes.
        self.assertEqual(0, call_main(fixture).code)

    def test_the_real_host_is_refused_or_admitted_by_name_with_no_observation_supplied(self) -> None:
        """The ``UNSUPPLIED`` fallback: nothing is injected, so ``observe_platform`` reads the host.

        ``config_at`` injects the certified pair by default, which is what makes the check above
        host-independent -- and it also means nothing else in this module exercises
        ``observe_platform``'s own ``platform.system``/``platform.machine`` fallback in-process any
        more (agentic-sdlc-e8a9).  This drives ``main`` with the sentinel LEFT IN PLACE and admits
        EITHER outcome, each named rather than assumed: a host the product certifies completes at exit
        0 with the observation the fallback actually made, and any other host gets the product's own
        refusal naming what it observed, with no plan and no journal.  Nothing here asserts which host
        that is, so it states no claim about the runner.
        """
        fixture = self.fixture()
        unsupplied = fixture.config_at(
            observed_system=update.UNSUPPLIED, observed_machine=update.UNSUPPLIED
        )
        try:
            admitted = update.admit_platform(unsupplied)
        except update.Refusal as refusal:
            expected: str | None = str(refusal)
        else:
            expected = None

        outcome = call_main(fixture, config=unsupplied)
        if expected is None:
            self.assertEqual(0, outcome.code, outcome.stderr)
            # The fallback read the host itself rather than an injected pair.
            self.assertEqual((update.platform.system(), update.platform.machine()), admitted)
        else:
            self.assert_clean_refusal(fixture, outcome, update.escape_display(expected))

    def test_a_declared_incompatibility_and_an_unobservable_host_version_both_refuse(self) -> None:
        contract = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        contract["compatibility"]["known_incompatible_host_versions"] = [
            {
                "host": "claude-code",
                "reason": "the fabricated payload declares this host broken",
                "version": HOST_VERSION,
            }
        ]
        declared = self.fixture(contract_b=contract)
        outcome = call_main(declared)
        self.assert_clean_refusal(
            declared, outcome, "DECLARES the observed Claude Code host version", "refused by name"
        )

        # The same declaration filed for the OTHER host admits this plane: two hosts' version spaces
        # are unrelated, so an exclusion is scoped to the host its record names. The refusal above is
        # this assertion's positive control -- the only difference between them is that one field.
        other_host = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        other_host["compatibility"]["known_incompatible_host_versions"] = [
            {
                "host": "codex-cli",
                "reason": "the fabricated payload declares this host broken",
                "version": HOST_VERSION,
            }
        ]
        elsewhere = self.fixture(contract_b=other_host)
        admitted = call_main(elsewhere)
        self.assertEqual(0, admitted.code, admitted.stderr)

        blind = self.fixture()
        second = call_main(blind, config=blind.config_at(observed_host_version=None))
        self.assert_clean_refusal(
            blind,
            second,
            "the Claude Code host version could not be observed",
            "never substitutes another version for the observed one",
        )
        # Positive control: the observed version the contract admits completes the same update.
        self.assertEqual(0, call_main(blind).code)

    def test_a_non_finite_number_and_a_duplicate_key_are_refused_in_a_read_document(self) -> None:
        """``1e400`` never reaches ``parse_constant``, so the iterative walk is what catches it."""
        with self.assertRaises(update.Refusal):
            update.parse_json_object(b'{"n": 1e400}', "a fabricated document")
        with self.assertRaises(update.Refusal):
            update.parse_json_object(b'{"a": 1, "a": 2}', "a fabricated document")
        with self.assertRaises(update.Refusal):
            update.parse_json_object(b'{"n": NaN}', "a fabricated document")
        # Positive control: the same reader accepts an ordinary document with a finite number.
        self.assertEqual({"n": 1.5}, update.parse_json_object(b'{"n": 1.5}', "a fabricated document"))

    def test_the_module_admits_only_the_forwarded_host_vector_and_returns_an_exit_class(self) -> None:
        fixture = self.fixture()
        for rejected in ([], ["--host"], ["--host", "gemini"], ["--host", "claude", "extra"]):
            with self.subTest(argv=rejected):
                outcome = call_main(fixture, argv=rejected)
                self.assertEqual(3, outcome.code)
                self.assertIn("admits exactly ['--host', <claude|codex>]", outcome.stderr)
                self.assertEqual([], fixture.journals())
        # Positive control: the vector the dispatcher forwards is admitted.
        clean = call_main(fixture)
        self.assertEqual(0, clean.code, clean.stderr)
        self.assertIsInstance(clean.code, int)
        self.assertNotIsInstance(clean.code, bool)


@WINDOWS_SKIP
class BlockedRefreshTest(TemporaryRoot):
    """A modified or foreign entry is preserved, NAMED, and blocks the whole refresh pre-effect."""

    def assert_blocked(self, fixture: Fixture, outcome: Outcome, name: str, classification: str) -> None:
        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertEqual("", outcome.stdout)
        self.assertIn(update.BLOCK_SENTENCE, outcome.stderr)
        self.assertIn(name, outcome.stderr)
        self.assertIn(classification, outcome.stderr)
        # No partial update past a blocked entry: no receipt, no journal, and the pointer is untouched.
        self.assertEqual(
            [fixture.activation_dir / "receipts" / f"{fixture.prior_receipt['receipt_id']}.json"]
            if (fixture.activation_dir / "receipts" / f"{fixture.prior_receipt['receipt_id']}.json").exists()
            else [],
            fixture.receipt_paths(),
        )
        self.assertEqual([], fixture.journals())
        self.assertEqual(receipts.canonical_bytes(fixture.prior_receipt), fixture.pointer.read_bytes())

    def test_a_modified_entry_blocks_and_the_whole_plane_is_left_untouched(self) -> None:
        fixture = self.fixture()
        victim = fixture.destination("agents/cartographer.md")
        victim.write_text("hand-edited by the operator\n", encoding="utf-8")
        before = plane_inventory(fixture.claude_root)

        outcome = call_main(fixture)
        self.assert_blocked(fixture, outcome, "agents/cartographer.md", update.CLASS_MODIFIED)
        # The modified entry is preserved byte-for-byte AND no other entry was refreshed past it.
        self.assertEqual("hand-edited by the operator\n", victim.read_text())
        self.assertEqual("frame one\n", fixture.destination("commands/sdlc-frame.md").read_text())
        self.assertEqual(before, plane_inventory(fixture.claude_root))
        # Positive control: restoring the recorded content lets the identical fixture refresh.
        victim.write_text(PAYLOAD_A["agents/claude/cartographer.md"], encoding="utf-8")
        self.assertEqual(0, call_main(fixture).code)
        self.assertEqual("cartographer two\n", victim.read_text())

    def test_a_foreign_entry_blocks_and_is_preserved_never_adopted(self) -> None:
        payload = dict(PAYLOAD_B)
        payload["commands/sdlc-extra.md"] = "extra two\n"
        fixture = self.fixture(payload_b=payload)
        foreign = fixture.destination("commands/sdlc-extra.md")
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("the operator's own command\n", encoding="utf-8")
        before = plane_inventory(fixture.claude_root)

        outcome = call_main(fixture)
        self.assert_blocked(fixture, outcome, "commands/sdlc-extra.md", update.CLASS_FOREIGN)
        self.assertEqual("the operator's own command\n", foreign.read_text())
        self.assertEqual(before, plane_inventory(fixture.claude_root))
        # Positive control: with the destination free, the same payload entry installs into the slot.
        foreign.unlink()
        self.assertEqual(0, call_main(fixture).code)
        self.assertEqual("extra two\n", foreign.read_text())

    def test_a_symlinked_destination_blocks_rather_than_being_replaced_through_the_link(self) -> None:
        fixture = self.fixture()
        outside = fixture.root / "outside.md"
        outside.write_text("content outside the plane\n", encoding="utf-8")
        victim = fixture.destination("agents/cartographer.md")
        victim.unlink()
        victim.symlink_to(outside)

        outcome = call_main(fixture)
        self.assert_blocked(fixture, outcome, "agents/cartographer.md", update.CLASS_FOREIGN_LINK)
        self.assertTrue(victim.is_symlink())
        self.assertEqual("content outside the plane\n", outside.read_text())

    def test_an_inventory_row_with_no_digest_blocks_because_nothing_proves_ownership(self) -> None:
        fixture = self.fixture()
        self.repoint(
            fixture,
            entry_digest={"agents/cartographer.md": None},
            body_overrides={
                "effect_state": "partial",
                "terminal_phase": "activated-partial",
                "unknowns": [
                    {
                        "detail": "the entry could not be digested when it was activated",
                        "observation": "entry-content",
                        "subject": "agents/cartographer.md",
                    }
                ],
            },
        )
        outcome = call_main(fixture)
        self.assert_blocked(fixture, outcome, "agents/cartographer.md", update.CLASS_UNPROVABLE)
        self.assertEqual("cartographer one\n", fixture.destination("agents/cartographer.md").read_text())
        # Positive control: the same plane with a recorded digest for that entry refreshes.
        self.repoint(fixture, body_overrides={"effect_state": "partial", "terminal_phase": "activated-partial"})
        self.assertEqual(0, call_main(fixture).code)

    def test_a_missing_ownership_record_blocks_because_a_refresh_must_prove_what_it_replaces(self) -> None:
        fixture = self.fixture()
        state_path = fixture.state_home / "agentic-sdlc-installer" / "state.json"
        self.assertTrue(state_path.is_file())
        kept = state_path.read_bytes()
        state_path.unlink()

        outcome = call_main(fixture)
        self.assert_blocked(fixture, outcome, "agents/cartographer.md", update.CLASS_NO_RECORD)
        self.assertEqual("cartographer one\n", fixture.destination("agents/cartographer.md").read_text())
        # Positive control: the restored ownership state admits the identical refresh.
        state_path.write_bytes(kept)
        self.assertEqual(0, call_main(fixture).code)

    def test_an_outstanding_installer_transition_refuses_rather_than_being_resolved(self) -> None:
        """The outstanding transition is armed with the installer's OWN primitives, not hand-written.

        A hand-written slot is refused by ``validate_state`` first, which would prove only that an
        invalid state is invalid; this one is a transition the shipped installer itself would
        recognise as recoverable, so the refusal under test is the "recovery is a separate operation"
        one.
        """
        fixture = self.fixture()
        state_path = fixture.state_home / "agentic-sdlc-installer" / "state.json"
        config = bundle.Config(
            fixture.candidate_a, fixture.home, fixture.codex_home, "copy", False, "claude", fixture.state_home
        )
        state = bundle.load_config_state(config)
        key = sorted(state["entries"])[0]
        record = state["entries"][key]
        state["pending"] = bundle.pending_slot("uninstall", key, record, None)
        bundle.write_state(state_path, state, False)
        bundle.validate_state(config, bundle.load_config_state(config))  # positive control: it is valid

        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("outstanding lifecycle", outcome.stderr)
        self.assertIn("recovery is a separate explicit operation", outcome.stderr)
        self.assertEqual([], fixture.journals())
        self.assertEqual("cartographer one\n", fixture.destination("agents/cartographer.md").read_text())


@WINDOWS_SKIP
class InterruptionTest(TemporaryRoot):
    """A kill mid-flight leaves the PRIOR receipt active, a recoverable journal, and an honest 4."""

    def test_a_kill_after_the_seal_leaves_the_prior_receipt_as_the_active_statement(self) -> None:
        fixture = self.fixture()
        prior_pointer = fixture.pointer.read_bytes()

        def killer(point: str) -> None:
            if point == "after-receipt-sealed":
                raise KeyboardInterrupt("the operator killed this run")

        outcome = call_main(fixture, config=fixture.config_at(checkpoint=killer))
        self.assertEqual(4, outcome.code, outcome.stderr)
        self.assertIn("so its effect is unknown", outcome.stderr)
        # The prior receipt is STILL this plane's active statement, and it is readable under its own id.
        self.assertEqual(prior_pointer, fixture.pointer.read_bytes())
        retained = fixture.activation_dir / "receipts" / f"{fixture.prior_receipt['receipt_id']}.json"
        self.assertEqual(prior_pointer, retained.read_bytes())
        # The journal is recoverable and names both receipts of the transition it stopped inside.
        journal = fixture.journal()
        self.assertEqual("prior-receipt", journal["pointer_when_recorded"])
        self.assertEqual("effects-recorded", journal["phase"])
        self.assertEqual(fixture.prior_receipt["receipt_id"], journal["prior_receipt_id"])
        self.assertEqual(str(fixture.pointer), journal["active_pointer"])
        self.assertTrue(Path(journal["receipt_path"]).is_file())
        # The effect really did happen, which is why this is an unknown rather than a refusal.
        self.assertEqual("cartographer two\n", fixture.destination("agents/cartographer.md").read_text())
        # Positive control: the same fixture without the kill reaches exit 0 and moves the pointer.
        clean = self.fixture()
        self.assertEqual(0, call_main(clean).code)
        self.assertNotEqual(
            receipts.canonical_bytes(clean.prior_receipt), clean.pointer.read_bytes()
        )

    def test_a_failed_transaction_leaves_the_prior_receipt_active_and_records_a_partial_effect(self) -> None:
        fixture = self.fixture()
        prior_pointer = fixture.pointer.read_bytes()
        outcome = call_main(fixture, fail_refresh_after=1)
        self.assertEqual(4, outcome.code, outcome.stderr)
        self.assertIn("fault-injected transaction failure", outcome.stderr)
        self.assertEqual(prior_pointer, fixture.pointer.read_bytes())
        body = fixture.new_receipt()["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        self.assertEqual(
            receipts.VERDICT_VALIDATED,
            receipts.derive("validate", fixture.new_receipt(), "the partial receipt")["verdict"],
        )
        self.assertIn("active pointer", outcome.stdout)
        self.assertIn("stays this plane's active statement", outcome.stdout)
        # Positive control: without the fault the same plane completes and activates its own receipt.
        clean = self.fixture()
        self.assertEqual(0, call_main(clean).code)
        self.assertEqual("complete", clean.new_receipt()["body"]["effect_state"])

    def test_a_digest_failure_after_a_successful_write_is_a_partial_effect_never_a_false_complete(
        self,
    ) -> None:
        """V5 (agentic-sdlc-cd9f): no earlier test exercised a recorded unknown with no failure.

        ``derive_effect_state``'s ``elif unknowns:`` branch is what turns an observation nobody could
        make into ``partial`` rather than a false ``complete``.  Before this test, flipping that
        branch to ``complete`` passed every test in this module: no run here had reached the seal with
        unknowns recorded and ``run.failures`` empty.  The write for the first entry this run touches
        REALLY SUCCEEDS -- its new content lands on disk -- and only the digest observed right after
        it fails, which is supplied-but-missing rather than not-supplied.
        """
        fixture = self.fixture()
        prior_pointer = fixture.pointer.read_bytes()

        outcome = call_main(fixture, fail_observe_content_at=1)

        self.assertEqual(4, outcome.code, outcome.stderr)
        self.assertIn("this update did not complete every claimed effect", outcome.stderr)
        self.assertIn("effect_state 'partial'", outcome.stderr)
        # The active pointer never moved: the prior receipt is still this plane's active statement.
        self.assertEqual(prior_pointer, fixture.pointer.read_bytes())
        self.assertIn("stays this plane's active statement", outcome.stdout)

        receipt = fixture.new_receipt()
        body = receipt["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        content_unknowns = [row for row in body["unknowns"] if row["observation"] == "entry-content"]
        self.assertEqual(1, len(content_unknowns), body["unknowns"])
        failed_name = content_unknowns[0]["subject"]
        self.assertIn(failed_name, CLAUDE_DESTINATIONS)
        self.assertIn("fault-injected observation failure", content_unknowns[0]["detail"])

        entries_by_name = {row["entry_name"]: row for row in body["entries"]}
        self.assertEqual(set(CLAUDE_DESTINATIONS), set(entries_by_name))
        self.assertIsNone(entries_by_name[failed_name]["content_sha256"])
        old_digest_by_name = {
            row["entry_name"]: row["content_sha256"] for row in fixture.prior_receipt["body"]["entries"]
        }
        for name in CLAUDE_DESTINATIONS:
            with self.subTest(name=name):
                self.assertEqual("refreshed", entries_by_name[name]["disposition"])
                self.assertEqual("owned", entries_by_name[name]["prestate"])
                if name == failed_name:
                    # The write for this entry really happened -- its digest changed from the prior
                    # receipt's own record -- even though this run never observed the new one.
                    self.assertNotEqual(
                        old_digest_by_name[name], bundle.digest(fixture.destination(name))
                    )
                else:
                    self.assertEqual(
                        bundle.digest(fixture.destination(name)), entries_by_name[name]["content_sha256"]
                    )

        # The receipt is sealed by the family's own producer and validates, even though its own
        # effect is partial: a sealed-but-not-yet-activated receipt is still evidence.
        self.assertEqual(
            receipts.VERDICT_VALIDATED,
            receipts.derive("validate", receipt, "the partial receipt")["verdict"],
        )

        # Positive control: the SAME fixture with no injected observation fault reaches exit 0,
        # records no unknowns at all, and moves the pointer -- so the partial result above is this
        # one fault, not a broken harness.
        clean = self.fixture()
        clean_outcome = call_main(clean)
        self.assertEqual(0, clean_outcome.code, clean_outcome.stderr)
        self.assertEqual([], clean.new_receipt()["body"]["unknowns"])
        self.assertEqual("complete", clean.new_receipt()["body"]["effect_state"])
        self.assertNotEqual(receipts.canonical_bytes(clean.prior_receipt), clean.pointer.read_bytes())

    def test_an_existing_receipt_for_this_identity_and_instant_refuses_rather_than_repeating(self) -> None:
        fixture = self.fixture()
        receipt_id = f"update-claude-{OPERATION_B}-20260820t121314z"
        occupied = fixture.activation_dir / "receipts" / f"{receipt_id}.json"
        occupied.write_bytes(b"{}\n")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code, outcome.stdout)
        self.assertIn("already exists", outcome.stderr)
        self.assertEqual(b"{}\n", occupied.read_bytes())
        self.assertEqual("cartographer one\n", fixture.destination("agents/cartographer.md").read_text())
        # Positive control: the same run at a different instant writes its own receipt.
        self.assertEqual(0, call_main(fixture, config=fixture.config_at(LATER_INSTANT)).code)


@WINDOWS_SKIP
class ReportTest(TemporaryRoot):
    """Every rendered line derived from an artifact is escaped, and the report claims no authority."""

    def test_control_characters_from_the_superseded_receipt_are_escaped_in_the_report(self) -> None:
        hostile = "cleared\x1b[2J and\na second line\r"
        active = update.ActiveActivation(
            path=self.root / "active-receipt.json",
            raw=b"{}",
            receipt={"receipt_id": "install-prior"},
            body={
                "candidate_id": "a" * 64,
                "resolved_version": "0.7.3",
                "unknowns": [
                    {"detail": hostile, "observation": "entry-content", "subject": "agents/x.md"}
                ],
            },
            receipt_id="install-prior",
            inventory={},
        )
        payload = update.AdmittedPayload(
            receipt_path=self.root / "acquisition.json",
            receipt_bytes=b"{}",
            receipt={},
            archive_sha256="b" * 64,
            operation_id=OPERATION_B,
            candidate_root=self.root / "candidate",
            manifest={},
            candidate_id="c" * 64,
            resolved_version="0.7.4",
            inventory={},
        )
        outcome = update.Outcome(
            name="agents/x.md",
            prestate="owned",
            disposition="refreshed",
            detail="a detail with\na forged line",
            content_sha256="d" * 64,
            unknown_detail=None,
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            update.report(
                update.Config(
                    home=self.root / "home",
                    state_home=self.root / "state",
                    data_home=self.root / "data",
                    codex_home=self.root / "codex",
                ),
                payload,
                active,
                [outcome],
                [],
                "complete",
                "activated",
                self.root / "receipt.json",
                self.root / "retained.json",
                self.root / "journal.json",
                update.Run(pointer_replaced=True),
            )
        rendered = out.getvalue()
        self.assertIn("\\x1b[2J", rendered)
        self.assertIn("\\n", rendered)
        self.assertIn("\\r", rendered)
        self.assertNotIn("\x1b", rendered)
        # One line per fact: the two forged newlines never become lines of this command's own output.
        # Ten facts: three header lines, one entry, one inherited unknown, the journal, the retained
        # prior receipt, this run's receipt, the pointer, and the no-authority statement.
        self.assertEqual(10, len(rendered.splitlines()), rendered)
        self.assertIn("authorizes no push, publication, PR mutation, merge, deployment", rendered)
        # Positive control: the same renderer does emit the hostile text, escaped rather than dropped.
        self.assertIn("cleared", rendered)

    def test_the_plan_and_the_journal_record_the_identity_transition(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        plans = fixture.plans()
        self.assertEqual(1, len(plans), plans)
        plan = json.loads(plans[0].read_text(encoding="utf-8"))
        self.assertEqual(update.PLAN_SCHEMA, plan["schema_version"])
        self.assertEqual(CANDIDATE_A, plan["prior_candidate_id"])
        self.assertEqual(CANDIDATE_B, plan["candidate_id"])
        self.assertEqual(fixture.prior_receipt["receipt_id"], plan["prior_receipt_id"])
        self.assertEqual(
            sorted(name for name, _ in fixture.activated),
            sorted(str(row["entry_name"]) for row in plan["refresh"]),
        )
        self.assertEqual([], plan["preserve"])
        self.assertIsNone(plan["public_channel"])
        self.assertEqual("none", plan["release_claim"])

        journal_paths = fixture.journals()
        self.assertEqual(1, len(journal_paths), journal_paths)
        journal = fixture.journal()
        self.assertEqual(update.JOURNAL_SCHEMA, journal["schema_version"])
        self.assertEqual("effects-recorded", journal["phase"])
        self.assertEqual("prior-receipt", journal["pointer_when_recorded"])
        self.assertEqual(str(fixture.pointer), journal["active_pointer"])
        body = fixture.new_receipt()["body"]
        # The receipt binds the plan and the journal by the digest of the bytes still on disk: a
        # journal rewritten after the seal would leave the receipt bound to a digest the file no
        # longer has, which is indistinguishable from tampering.
        self.assertEqual(hashlib.sha256(plans[0].read_bytes()).hexdigest(), body["plan_sha256"])
        self.assertEqual(hashlib.sha256(journal_paths[0].read_bytes()).hexdigest(), body["journal_sha256"])
        # Positive control: those two digests are different values, so neither assertion is vacuous.
        self.assertNotEqual(body["plan_sha256"], body["journal_sha256"])


if __name__ == "__main__":
    unittest.main()
