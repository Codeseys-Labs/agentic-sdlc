"""``ccodex sdlc install --host claude``: admission, compatibility, copy-activation, and one seal.

WHAT THIS MODULE PROVES, AND HOW IT AVOIDS PROVING NOTHING. Every negative assertion here carries a
POSITIVE CONTROL in the same test: an absence proves nothing unless the same harness is shown to
detect the presence. A refusal test therefore always runs the same fixture twice -- once with the
defect and once without -- and a "no receipt was written" assertion is always paired with a run that
does write one.

THE FIXTURE IS A FABRICATED ACQUISITION, NOT A MOCK. Each test builds a real candidate payload tree
under a real ``XDG_DATA_HOME``, a real sealed ``release-candidate-acquisition-receipt/v1`` under a
real ``XDG_STATE_HOME``, and a real Claude home, then drives ``main(["--host", "claude"])`` exactly
as the dispatcher does. The acquisition receipt is sealed with the acquisition producer's OWN
algorithm (canonical bytes minus ``record_sha256``), so a change to that algorithm surfaces here
rather than in production.

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
import shutil
import stat
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "ccodex_sdlc_install.py"
RECEIPT_PRODUCER_PATH = ROOT / "scripts" / "distribution_activation_receipt.py"
INSTALLER_PATH = ROOT / "scripts" / "install_skill_bundle.py"
GUARD_PATH = ROOT / "scripts" / "ccodex_sdlc_readonly.py"
READER_PATH = ROOT / "scripts" / "ccodex_sdlc.py"
RECEIPT_PRODUCER_SHIM_PATH = ROOT / "scripts" / "write_acquisition_receipt.py"
RELEASE_CONTRACT_PATH = ROOT / "policy" / "release-contract.v1.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


install = _load(MODULE_PATH, "ccodex_sdlc_install_under_test")
receipts = _load(RECEIPT_PRODUCER_PATH, "ccodex_sdlc_install_receipt_producer")
bundle = _load(INSTALLER_PATH, "ccodex_sdlc_install_installer")
guard = _load(GUARD_PATH, "ccodex_sdlc_install_guard")
# The neighbouring verb and the reader's projection, loaded for the ONE document all three share:
# `activation/active-receipt.json`. The update module is DRIVEN here rather than imitated, because
# what this ticket must prove is that a real install produces a plane the real update admits; the
# reader is loaded for its pure observers only, never for a guard-installing entrypoint.
update = _load(ROOT / "scripts" / "ccodex_sdlc_update.py", "ccodex_sdlc_install_then_update")
reader = _load(READER_PATH, "ccodex_sdlc_install_reader")
# The acquisition receipt's producer. It replaced the deleted acquisition engine and its policy
# document, so the closed key set, the constants, and the two layout strings are pinned against the
# module that actually writes them rather than against a schema table with no producer.
shim = _load(RECEIPT_PRODUCER_SHIM_PATH, "ccodex_sdlc_install_acquisition_shim")

INSTANT = "2026-08-20T12:13:14Z"
LATER_INSTANT = "2026-08-20T12:15:00Z"
HOST_VERSION = "2.1.233"
ARCHIVE_SHA = hashlib.sha256(b"fabricated-archive").hexdigest()
CANDIDATE_ID = hashlib.sha256(b"fabricated-candidate").hexdigest()
OPERATION_ID = "op-" + hashlib.sha256(b"fabricated-operation").hexdigest()[:32]
PRODUCT_VERSION = "0.7.3"

#: The payload subset every fixture carries. One skill DIRECTORY with a nested file, one Claude
#: agent, one command, and one CODEX agent that must never be activated by a Claude-host install.
PAYLOAD_FILES = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha\n",
    "skills/alpha-skill/references/notes.md": "notes\n",
    "agents/claude/cartographer.md": "cartographer\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame\n",
}
CLAUDE_DESTINATIONS = (
    "skills/alpha-skill",
    "agents/cartographer.md",
    "commands/sdlc-frame.md",
)
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
        json.dumps(
            document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
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
                {"mode": 0o755, "path": relative, "size": len(target.encode()), "target": target, "type": "symlink"}
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


@dataclass
class Fixture:
    root: Path
    home: Path
    state_home: Path
    data_home: Path
    installer_state_root: Path
    candidate_root: Path
    acquisition_receipt: Path
    config: Any

    @property
    def claude_root(self) -> Path:
        return self.home / ".claude"

    def destination(self, relative: str) -> Path:
        return self.claude_root / relative

    def activation_receipts(self) -> list[Path]:
        directory = self.state_home / "agentic-sdlc" / "activation" / "receipts"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def journal(self) -> dict[str, Any]:
        directory = self.state_home / "agentic-sdlc" / "activation" / "journals"
        paths = sorted(directory.glob("*.json"))
        assert len(paths) == 1, paths
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def journal_bytes(self) -> bytes:
        directory = self.state_home / "agentic-sdlc" / "activation" / "journals"
        paths = sorted(directory.glob("*.json"))
        assert len(paths) == 1, paths
        return paths[0].read_bytes()

    def plans(self) -> list[Path]:
        directory = self.state_home / "agentic-sdlc" / "activation" / "plans"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    @property
    def pointer(self) -> Path:
        """The plane's ONE active statement -- the only document ``update`` and ``uninstall`` admit."""
        return self.state_home / "agentic-sdlc" / "activation" / "active-receipt.json"


def build_fixture(
    root: Path,
    *,
    contract: dict[str, Any] | None = None,
    host_version: str | None | Any = HOST_VERSION,
    instant: str = INSTANT,
    payload: dict[str, str] | None = None,
    receipt_overrides: dict[str, Any] | None = None,
    reseal: bool = True,
    manifest_overrides: dict[str, Any] | None = None,
    observed_system: str = "Linux",
    observed_machine: str = "x86_64",
) -> Fixture:
    """Fabricate one complete acquisition: payload tree, manifest, sealed receipt, and Config.

    ``observed_system``/``observed_machine`` default to the certified ``Linux``/``x86_64`` pair so
    every fixture is host-independent: without an explicit override, ``admit_platform`` sees the
    certified platform regardless of which real host runs this suite.  ``PlatformTest`` overrides
    them to exercise the refusal itself.
    """
    home = root / "operator-home"
    state_home = root / "state"
    data_home = root / "data"
    installer_state_root = root / "installer-state"
    for directory in (home, state_home, data_home, installer_state_root):
        directory.mkdir(parents=True, exist_ok=True)

    candidate_root = data_home / "agentic-sdlc" / "acquisition" / "candidates" / ARCHIVE_SHA / "root"
    candidate_root.mkdir(parents=True)
    for relative, text in (payload or PAYLOAD_FILES).items():
        target = candidate_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    contract_document = contract if contract is not None else json.loads(
        RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract_path = candidate_root / "policy" / "release-contract.v1.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_bytes(canonical(contract_document))

    manifest = {
        "archive_root": f"agentic-sdlc-candidate-{CANDIDATE_ID}-linux-x64",
        "artifact_kind": "unpublished-candidate",
        "candidate_id": CANDIDATE_ID,
        "inventory": inventory_for_tree(candidate_root),
        "platform": "linux-x64",
        "product_version": PRODUCT_VERSION,
        "public_channel": None,
        "release_claim": "none",
        "schema_version": "release-candidate/v1",
        "support_tier": "unsupported",
    }
    manifest.update(manifest_overrides or {})
    (candidate_root / "manifest.json").write_bytes(canonical(manifest))

    receipt = {
        "activation": "absent",
        "archive_sha256": ARCHIVE_SHA,
        "candidate_root_absolute_physical_path": str(candidate_root),
        "effect_state": "complete",
        "installed_at": "2026-08-19T10:00:00Z",
        "journal_sha256": hashlib.sha256(b"journal").hexdigest(),
        "operation_id": OPERATION_ID,
        "plan_sha256": hashlib.sha256(b"plan").hexdigest(),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    receipt.update(receipt_overrides or {})
    receipt_dir = state_home / "agentic-sdlc" / "acquisition" / "receipts"
    receipt_dir.mkdir(parents=True)
    receipt_path = receipt_dir / f"{ARCHIVE_SHA}.json"
    receipt_path.write_bytes(seal_acquisition(receipt) if reseal else canonical(receipt))

    config = install.Config(
        home=home,
        state_home=state_home,
        data_home=data_home,
        codex_home=root / "codex-home",
        installer_state_root=installer_state_root,
        observed_host_version=host_version,
        observed_instant=instant,
        observed_system=observed_system,
        observed_machine=observed_machine,
    )
    return Fixture(
        root=root,
        home=home,
        state_home=state_home,
        data_home=data_home,
        installer_state_root=installer_state_root,
        candidate_root=candidate_root,
        acquisition_receipt=receipt_path,
        config=config,
    )


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

    The end-to-end checks below run the shipped module in a child under ``-I``, which is the ONE place
    in this suite where ``Config.observed_system``/``observed_machine`` cannot reach: the child builds
    its configuration from its own ``default_config()``, and ``-I`` closes every environment and
    ``sitecustomize`` route an injected observation could have taken.  Off the certified linux-x64
    platform that child therefore refuses at exit 3 before any effect -- the product being correct --
    so the claim "this reader dispatches this module end to end" is reported as a named skip instead of
    a failed exit-0 assertion (agentic-sdlc-e8a9).

    Positive control: the refusal must name THIS host's own observation, taken from the same
    ``platform`` module the shipped module reads.  A refusal about a platform this host is not buys no
    skip and stays a failure.  On the certified host no fragment matches at all, so nothing here can
    fire on the linux-x64 runner.
    """
    if completed.returncode != 3:
        return
    axes = (
        (PLATFORM_REFUSAL_FRAGMENTS[0], install.platform.system(), install.SUPPORTED_SYSTEM),
        (PLATFORM_REFUSAL_FRAGMENTS[1], install.platform.machine(), install.SUPPORTED_MACHINES),
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
    fail_transaction_after: int | None = None,
    config: Any | None = None,
) -> Outcome:
    """Drive ``main`` exactly as the dispatcher does, optionally injecting one transaction fault.

    The fault is injected at the ONE seam a real interruption would hit: the shipped installer's
    ``transactional_create``, on the sibling instance this run loads.  Patching the file would not
    work, because every run loads its own module object by absolute path.
    """
    selected = ["--host", "claude"] if argv is None else argv
    real_loader = install.load_sibling

    def loader(stem: str) -> ModuleType:
        module = real_loader(stem)
        if stem == "install_skill_bundle" and fail_transaction_after is not None:
            original = module.transactional_create
            calls: list[int] = []

            def failing(*args: Any, **kwargs: Any) -> Any:
                calls.append(1)
                if len(calls) > fail_transaction_after:
                    raise module.InstallerError("fault-injected transaction failure")
                return original(*args, **kwargs)

            module.transactional_create = failing
        return module

    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(install, "default_config", lambda: config or fixture.config))
        stack.enter_context(mock.patch.object(install, "load_sibling", loader))
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        code = install.main(selected)
    assert isinstance(code, int) and not isinstance(code, bool), repr(code)
    assert 0 <= code <= 4, code
    return Outcome(code, out.getvalue(), err.getvalue())


def sealed_receipt(fixture: Fixture) -> dict[str, Any]:
    paths = fixture.activation_receipts()
    assert len(paths) == 1, paths
    return json.loads(paths[0].read_text(encoding="utf-8"))


class TemporaryRoot(unittest.TestCase):
    """One temporary directory per test, so no test can observe another's plane."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)

    def fixture(self, **kwargs: Any) -> Fixture:
        directory = Path(tempfile.mkdtemp(dir=self.root))
        return build_fixture(directory, **kwargs)

    def later_config(self, fixture: Fixture, instant: str = LATER_INSTANT) -> Any:
        """The same plane observed at a later instant, which is what makes a second run's receipt new."""
        return install.Config(
            home=fixture.home,
            state_home=fixture.state_home,
            data_home=fixture.data_home,
            codex_home=fixture.config.codex_home,
            installer_state_root=fixture.installer_state_root,
            observed_host_version=HOST_VERSION,
            observed_instant=instant,
            observed_system=fixture.config.observed_system,
            observed_machine=fixture.config.observed_machine,
        )


class ReExpressedContractsTest(TemporaryRoot):
    """The constants this module re-expresses must still agree with the shipped artifacts."""

    def test_acquisition_receipt_contract_matches_its_producer(self) -> None:
        self.assertEqual(tuple(sorted(shim.RECEIPT_KEYS)), tuple(sorted(install.ACQUISITION_RECEIPT_KEYS)))
        self.assertEqual(shim.RECEIPT_CONSTANTS, install.ACQUISITION_RECEIPT_CONSTANTS)
        self.assertEqual(
            "$XDG_STATE_HOME/" + "/".join(install.ACQUISITION_RECEIPT_SEGMENTS) + "/<archive-sha256>.json",
            shim.RECEIPT_LAYOUT,
        )
        self.assertEqual(
            "$XDG_DATA_HOME/"
            + "/".join(install.ACQUISITION_CANDIDATE_SEGMENTS)
            + f"/<archive-sha256>/{install.ACQUISITION_CANDIDATE_LEAF}",
            shim.CANDIDATE_ROOT_LAYOUT,
        )
        # Positive control: the same lookups do detect a disagreement.
        self.assertNotEqual(
            shim.RECEIPT_CONSTANTS, {**shim.RECEIPT_CONSTANTS, "selection": "chosen"}
        )

    def test_escape_display_agrees_with_the_receipt_producer(self) -> None:
        samples = ("plain", "a\nb", "a\rb", "a\tb", "a\\b", "\x1b[2J", "\x7f", "٩")
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(receipts.escape_display(sample), install.escape_display(sample))
        # Positive control: the escape is not the identity, so the agreement above is not vacuous.
        self.assertNotEqual("a\nb", install.escape_display("a\nb"))
        self.assertEqual("a\\nb", install.escape_display("a\nb"))

    def test_release_contract_fixture_is_the_shipped_one(self) -> None:
        contract = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(install.RELEASE_CONTRACT_HOST, contract["compatibility"]["core"]["host"])
        self.assertEqual([], contract["compatibility"]["known_incompatible_host_versions"])

    def test_module_carries_no_wildcard_purge_or_delete_vocabulary(self) -> None:
        """The MUST-NOTs are pinned in the CODE, with every docstring and comment stripped first.

        A naive line filter would read the prose that NAMES the forbidden vocabulary as a use of it,
        which is why the module is re-rendered from its own syntax tree instead.
        """
        code = executable_source(MODULE_PATH)
        for forbidden in ("--all", "purge", "rmtree", "transactional_delete", "remove_path", "uninstall("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        # Positive control: the same search does find a token the module really uses.
        self.assertIn("transactional_create", code)


class EndToEndInstallTest(TemporaryRoot):
    def test_install_copies_claude_entries_and_seals_one_receipt(self) -> None:
        fixture = self.fixture()
        before = fixture.acquisition_receipt.read_bytes()
        outcome = call_main(fixture)
        self.assertEqual(0, outcome.code, outcome.stderr)

        for relative in CLAUDE_DESTINATIONS:
            destination = fixture.destination(relative)
            self.assertTrue(destination.exists(), relative)
            self.assertFalse(destination.is_symlink(), f"{relative} must be a copy, never a link")
        nested = fixture.destination("skills/alpha-skill/references/notes.md")
        self.assertEqual("notes\n", nested.read_text(encoding="utf-8"))
        # A claude-host activation never touches the codex plane, and there is no wildcard host.
        self.assertFalse((fixture.config.codex_home / CODEX_DESTINATION).exists())
        self.assertFalse(fixture.destination(CODEX_DESTINATION).exists())

        document = sealed_receipt(fixture)
        body = document["body"]
        self.assertEqual("install", body["operation"])
        self.assertEqual("claude", body["host"])
        self.assertEqual("claude-home", body["activation_scope"])
        self.assertEqual("complete", body["effect_state"])
        self.assertEqual("activated", body["terminal_phase"])
        self.assertIsNone(body["public_channel"])
        self.assertEqual("none", body["release_claim"])
        self.assertIsNone(body["requested_version"])
        self.assertEqual(PRODUCT_VERSION, body["resolved_version"])
        self.assertEqual("archive-manifest", body["version_source"])
        self.assertEqual(CANDIDATE_ID, body["candidate_id"])
        self.assertEqual(ARCHIVE_SHA, body["archive_sha256"])
        self.assertEqual([], body["unknowns"])
        self.assertEqual(
            {"expected_kind": "distribution-activation", "receipt_id": OPERATION_ID, "relation": "derived-from"},
            document["ancestors"][0],
        )
        self.assertEqual(1, len(document["ancestors"]))
        self.assertEqual(INSTANT, document["stated_at"])

        names = {entry["entry_name"]: entry for entry in body["entries"]}
        self.assertEqual(set(CLAUDE_DESTINATIONS), set(names))
        for name, entry in names.items():
            self.assertEqual("absent", entry["prestate"], name)
            self.assertEqual("installed", entry["disposition"], name)
            self.assertEqual(
                bundle.digest(fixture.destination(name)), entry["content_sha256"], name
            )

        # The producer itself is the authority on the seal: re-validating must agree.
        result = receipts.derive("validate", document, "the sealed activation receipt")
        self.assertEqual("validated", result["verdict"], result["reasons"])

        journal = fixture.journal()
        self.assertEqual("terminal", journal["phase"])
        self.assertEqual(
            hashlib.sha256(fixture.journal_bytes()).hexdigest(), body["journal_sha256"]
        )
        self.assertEqual(1, len(fixture.plans()))
        plan_bytes = fixture.plans()[0].read_bytes()
        self.assertEqual(hashlib.sha256(plan_bytes).hexdigest(), body["plan_sha256"])
        self.assertEqual(before, fixture.acquisition_receipt.read_bytes())

        # THE ACTIVE POINTER IS THE PLANE'S FRONT DOOR. `update` and `uninstall` admit this document
        # and nothing else, so an install that sealed a receipt without landing it left a plane no
        # later verb could act on (agentic-sdlc-7b2e).
        self.assertTrue(fixture.pointer.exists(), "the active pointer must exist after install")
        self.assertFalse(fixture.pointer.is_symlink(), "the pointer is a document, never a link")
        receipt_path = fixture.activation_receipts()[0]
        self.assertEqual(receipt_path.read_bytes(), fixture.pointer.read_bytes())
        pointed = json.loads(fixture.pointer.read_text(encoding="utf-8"))
        self.assertEqual(document, pointed)
        self.assertEqual(f"{pointed['receipt_id']}.json", receipt_path.name)
        # The pointer's own bytes validate through the family's producer, not merely the file it copies.
        self.assertEqual(
            "validated",
            receipts.derive("validate", pointed, "the active pointer")["verdict"],
        )
        self.assertIn(f"active pointer {fixture.pointer}", outcome.stdout)
        self.assertIn("names this activation's receipt", outcome.stdout)

    def test_second_install_of_the_same_payload_writes_nothing_new(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        first = {path: path.read_bytes() for path in fixture.activation_receipts()}
        digests = {
            relative: bundle.digest(fixture.destination(relative)) for relative in CLAUDE_DESTINATIONS
        }
        later = self.later_config(fixture)
        outcome = call_main(fixture, config=later)
        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertEqual(2, len(fixture.activation_receipts()))
        for path, raw in first.items():
            self.assertEqual(raw, path.read_bytes(), "an earlier receipt is never rewritten")
        for relative, digest in digests.items():
            self.assertEqual(digest, bundle.digest(fixture.destination(relative)))
        second = json.loads(
            [path for path in fixture.activation_receipts() if path not in first][0].read_text(
                encoding="utf-8"
            )
        )
        dispositions = {entry["disposition"] for entry in second["body"]["entries"]}
        self.assertEqual({"preserved"}, dispositions)
        self.assertEqual({"owned"}, {entry["prestate"] for entry in second["body"]["entries"]})
        self.assertEqual("complete", second["body"]["effect_state"])

    def test_a_receipt_is_never_overwritten(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        existing = fixture.activation_receipts()[0]
        raw = existing.read_bytes()
        # The same instant derives the same receipt identity, so the second run would collide.
        outcome = call_main(fixture)
        self.assertEqual(4, outcome.code)
        self.assertIn("never overwrites", outcome.stderr)
        self.assertEqual(raw, existing.read_bytes())
        self.assertEqual(1, len(fixture.activation_receipts()))


class PreservationTest(TemporaryRoot):
    def test_foreign_entry_is_preserved_and_named(self) -> None:
        fixture = self.fixture()
        occupied = fixture.destination("commands/sdlc-frame.md")
        occupied.parent.mkdir(parents=True)
        occupied.write_text("operator's own command\n", encoding="utf-8")
        outcome = call_main(fixture)
        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertEqual("operator's own command\n", occupied.read_text(encoding="utf-8"))
        body = sealed_receipt(fixture)["body"]
        entries = {entry["entry_name"]: entry for entry in body["entries"]}
        self.assertEqual("foreign", entries["commands/sdlc-frame.md"]["prestate"])
        self.assertEqual("preserved", entries["commands/sdlc-frame.md"]["disposition"])
        self.assertEqual(
            bundle.digest(occupied), entries["commands/sdlc-frame.md"]["content_sha256"]
        )
        self.assertIn("commands/sdlc-frame.md", outcome.stdout)
        self.assertIn("preserved", outcome.stdout)
        # Positive control: the same run still installed the entries that were absent.
        self.assertEqual("installed", entries["skills/alpha-skill"]["disposition"])
        self.assertTrue(fixture.destination("skills/alpha-skill").is_dir())

    def test_modified_owned_entry_is_preserved_and_named(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        owned = fixture.destination("agents/cartographer.md")
        owned.write_text("edited outside this lifecycle\n", encoding="utf-8")
        later = self.later_config(fixture)
        outcome = call_main(fixture, config=later)
        self.assertEqual(0, outcome.code, outcome.stderr)
        self.assertEqual("edited outside this lifecycle\n", owned.read_text(encoding="utf-8"))
        second = [path for path in fixture.activation_receipts() if LATER_INSTANT.replace("-", "").replace(":", "").lower() in path.name]
        self.assertEqual(1, len(second))
        body = json.loads(second[0].read_text(encoding="utf-8"))["body"]
        entries = {entry["entry_name"]: entry for entry in body["entries"]}
        self.assertEqual("modified", entries["agents/cartographer.md"]["prestate"])
        self.assertEqual("preserved", entries["agents/cartographer.md"]["disposition"])
        # Positive control: an untouched owned entry in the same run is not called modified.
        self.assertEqual("owned", entries["skills/alpha-skill"]["prestate"])

    def test_outstanding_transaction_refuses_before_any_effect(self) -> None:
        """Recovery is a separate explicit operation, so an outstanding transaction stops this one.

        The transaction record is built from a REAL owned record and a real private stage container,
        because a hand-written one is refused earlier as malformed and would prove a different rule.
        """
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        self.assertEqual(1, len(fixture.activation_receipts()))
        state_path = fixture.installer_state_root / "agentic-sdlc-installer" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        key = str(fixture.destination("agents/cartographer.md"))
        record = state["entries"].pop(key)
        artifact = bundle.reserve_private_artifact(Path(key), "stage")
        state["transactions"][key] = bundle.transaction_record(
            "create", key, old_record=None, old_owned=False, new_record=record, stage=artifact, backup=None
        )
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        later = self.later_config(fixture)
        outcome = call_main(fixture, config=later)
        self.assertEqual(3, outcome.code)
        self.assertIn("outstanding lifecycle transaction", outcome.stderr)
        self.assertEqual(1, len(fixture.activation_receipts()))
        # Positive control: restoring the resolved state admits the very same run.
        state["transactions"].pop(key)
        state["entries"][key] = record
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(0, call_main(fixture, config=later).code)
        self.assertEqual(2, len(fixture.activation_receipts()))

    def test_marketplace_overlap_blocks_the_claude_plane(self) -> None:
        fixture = self.fixture()
        marketplace = fixture.claude_root / "plugins" / "marketplaces" / "agentic-sdlc"
        marketplace.mkdir(parents=True)
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("marketplace overlap", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertFalse(fixture.destination("skills/alpha-skill").exists())
        # Positive control: removing the overlap admits the same run.
        marketplace.rmdir()
        self.assertEqual(0, call_main(fixture).code)


class CompatibilityTest(TemporaryRoot):
    def contract_with_incompatible(self, version: str) -> dict[str, Any]:
        contract = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        contract["compatibility"]["known_incompatible_host_versions"] = [
            {"reason": "dynamic workflows regress on this host build", "version": version}
        ]
        return contract

    def test_declared_incompatibility_refuses_by_name(self) -> None:
        fixture = self.fixture(contract=self.contract_with_incompatible(HOST_VERSION))
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn(HOST_VERSION, outcome.stderr)
        self.assertIn("dynamic workflows regress on this host build", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual([], fixture.plans())
        self.assertFalse(fixture.destination("skills/alpha-skill").exists())
        # Positive control: the SAME declaration about another version admits this host.
        other = self.fixture(contract=self.contract_with_incompatible("2.1.154"))
        self.assertEqual(0, call_main(other).code)

    def test_host_version_below_the_declared_floor_refuses(self) -> None:
        fixture = self.fixture(host_version="2.1.153")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("eligibility floor", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        # Positive control: the floor itself is admitted.
        self.assertEqual(0, call_main(self.fixture(host_version="2.1.154")).code)

    def test_contract_about_another_host_refuses(self) -> None:
        contract = json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8"))
        contract["compatibility"]["core"]["host"] = "some-other-host"
        fixture = self.fixture(contract=contract)
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("some-other-host", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_unobservable_host_version_refuses_rather_than_assuming(self) -> None:
        fixture = self.fixture(host_version=None)
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("could not be observed", outcome.stderr)
        self.assertIn("never substitutes another version", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        # Positive control: a supplied observation admits the same fixture.
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_supplied_missing_and_not_supplied_are_different_inputs(self) -> None:
        """``None`` never consults the host; ``UNSUPPLIED`` observes it, and both are named."""
        supplied_missing = self.fixture(host_version=None)

        def forbidden(_name: str) -> str:
            raise AssertionError("a supplied observation must not consult the host")

        with mock.patch.object(install.shutil, "which", forbidden):
            self.assertEqual(3, call_main(supplied_missing).code)

        not_supplied = self.fixture(host_version=install.UNSUPPLIED)
        with mock.patch.object(install.shutil, "which", lambda _name: None):
            outcome = call_main(not_supplied)
        self.assertEqual(3, outcome.code)
        self.assertIn("could not be observed", outcome.stderr)

        observed = self.fixture(host_version=install.UNSUPPLIED)
        completed = subprocess.CompletedProcess(["claude"], 0, "2.1.200 (Claude Code)\n", "")
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(install.shutil, "which", lambda _name: "/usr/bin/claude"))
            stack.enter_context(mock.patch.object(install.subprocess, "run", lambda *a, **k: completed))
            result = call_main(observed)
        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual(
            "2.1.200",
            json.loads(observed.plans()[0].read_text(encoding="utf-8"))["observed_host_version"],
        )

    def test_unicode_digits_never_pass_as_a_version(self) -> None:
        fixture = self.fixture(host_version="2.1.٩")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("three-part SemVer", outcome.stderr)
        # Positive control: the ASCII spelling of a version at or above the floor is admitted, so
        # the refusal above is about the Unicode digit and not about the version being rejected.
        self.assertEqual(0, call_main(self.fixture(host_version="2.1.200")).code)


class PlatformTest(TemporaryRoot):
    """Drives ``admit_platform`` through the injected ``Config.observed_system``/``observed_machine``
    seam rather than mocking ``platform.system``/``platform.machine``, so the refusal is exercised
    identically on every host this suite runs on -- including a host that IS the certified platform,
    where mocking the real stdlib function would leave the "positive control" unable to state
    anything about the actual host without hardcoding an assumption about it (agentic-sdlc-e8a9).

    The last check is the other half of that trade: injecting both axes everywhere would leave
    ``observe_platform``'s ``UNSUPPLIED`` fallback -- the branch that reads the real host -- uncovered
    in-process, so that one supplies NEITHER observation and names both admissible outcomes instead of
    asserting which host this is.
    """

    def test_off_linux_refuses_by_name(self) -> None:
        fixture = self.fixture(observed_system="Darwin")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("Darwin", outcome.stderr)
        self.assertIn("certified only on Linux", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertFalse(fixture.destination("skills/alpha-skill").exists())
        # Positive control: the SAME fixture with the certified observation injected admits the run,
        # regardless of what the real host this suite executes on happens to be.
        self.assertEqual(0, call_main(self.fixture(observed_system="Linux")).code)

    def test_unsupported_architecture_refuses_by_name(self) -> None:
        fixture = self.fixture(observed_machine="aarch64")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("aarch64", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        # Positive control: the SAME fixture with the certified architecture injected admits the run.
        self.assertEqual(0, call_main(self.fixture(observed_machine="x86_64")).code)

    def test_the_real_host_is_refused_or_admitted_by_name_with_no_observation_supplied(self) -> None:
        """The ``UNSUPPLIED`` fallback: nothing is injected, so ``observe_platform`` reads the host.

        The two checks above inject both axes, which is exactly what makes them host-independent -- and
        it also means neither of them exercises ``observe_platform``'s own
        ``platform.system``/``platform.machine`` fallback in-process any more, leaving that branch
        covered only by the subprocess end-to-end check, the one place off-Linux cannot reach
        (agentic-sdlc-e8a9).  This drives ``main`` with the sentinel LEFT IN PLACE and admits EITHER
        outcome, each named rather than assumed:

        * a host the product certifies -- the fallback observed it, the run completes at exit 0, and one
          activation receipt is sealed;
        * any other host -- the product refuses at exit 3 with its OWN message about the observation it
          actually made, and no receipt and no destination exist.

        Nothing here asserts which host that is, so it states no claim about the runner; a third
        outcome (another exit class, a refusal on a host the predicate admits, or a completed run on one
        it refuses) fails.
        """
        fixture = self.fixture()
        unsupplied = install.Config(
            home=fixture.home,
            state_home=fixture.state_home,
            data_home=fixture.data_home,
            codex_home=fixture.config.codex_home,
            installer_state_root=fixture.installer_state_root,
            observed_host_version=HOST_VERSION,
            observed_instant=INSTANT,
            # observed_system/observed_machine are deliberately NOT supplied: they keep the shipped
            # ``UNSUPPLIED`` default, which is the branch under test.
        )
        self.assertIs(install.UNSUPPLIED, unsupplied.observed_system)
        self.assertIs(install.UNSUPPLIED, unsupplied.observed_machine)
        try:
            admitted = install.admit_platform(unsupplied)
        except install.Refusal as refusal:
            expected: str | None = str(refusal)
        else:
            expected = None

        outcome = call_main(fixture, config=unsupplied)
        if expected is None:
            self.assertEqual(0, outcome.code, outcome.stderr)
            # The fallback read the host itself rather than an injected pair.
            self.assertEqual((install.platform.system(), install.platform.machine()), admitted)
            self.assertEqual(1, len(fixture.activation_receipts()))
        else:
            self.assertEqual(3, outcome.code, outcome.stderr)
            # The product's OWN refusal text, which necessarily quotes the observation it made on
            # whichever axis refused -- so this names the real host without restating any rule.
            self.assertIn(install.escape_display(expected), outcome.stderr)
            self.assertIn("refused before any effect", outcome.stderr)
            self.assertEqual([], fixture.activation_receipts())
            self.assertFalse(fixture.destination("skills/alpha-skill").exists())


class AdmissionTest(TemporaryRoot):
    def test_absent_and_ambiguous_acquisition_are_different_refusals(self) -> None:
        fixture = self.fixture()
        fixture.acquisition_receipt.unlink()
        absent = call_main(fixture)
        self.assertEqual(3, absent.code)
        self.assertIn("no <archive-sha256>.json acquisition receipt", absent.stderr)

        second = fixture.acquisition_receipt.with_name(f"{'b' * 64}.json")
        fixture.acquisition_receipt.write_bytes(
            seal_acquisition(
                {
                    "activation": "absent",
                    "archive_sha256": ARCHIVE_SHA,
                    "candidate_root_absolute_physical_path": str(fixture.candidate_root),
                    "effect_state": "complete",
                    "installed_at": "2026-08-19T10:00:00Z",
                    "journal_sha256": hashlib.sha256(b"journal").hexdigest(),
                    "operation_id": OPERATION_ID,
                    "plan_sha256": hashlib.sha256(b"plan").hexdigest(),
                    "public_channel": None,
                    "record_sha256": "",
                    "release_claim": "none",
                    "schema_version": "release-candidate-acquisition-receipt/v1",
                    "selection": "absent",
                    "support": "unsupported",
                    "terminal_phase": "installed-unselected",
                }
            )
        )
        second.write_bytes(fixture.acquisition_receipt.read_bytes())
        ambiguous = call_main(fixture)
        self.assertEqual(3, ambiguous.code)
        self.assertIn("exactly one exactly acquired local candidate", ambiguous.stderr)
        # Positive control: exactly one admits.
        second.unlink()
        self.assertEqual(0, call_main(fixture).code)

    def test_selection_or_phase_other_than_terminal_unselected_refuses(self) -> None:
        for overrides, needle in (
            ({"selection": "chosen"}, "selection"),
            ({"terminal_phase": "published"}, "terminal_phase"),
            ({"activation": "present"}, "activation"),
            ({"effect_state": "partial"}, "effect_state"),
        ):
            with self.subTest(overrides=overrides):
                fixture = self.fixture(receipt_overrides=overrides)
                outcome = call_main(fixture)
                self.assertEqual(3, outcome.code)
                self.assertIn(needle, outcome.stderr)
                self.assertEqual([], fixture.activation_receipts())
        # Positive control: the unmodified receipt admits.
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_broken_seal_refuses_as_a_mismatched_pair(self) -> None:
        fixture = self.fixture()
        document = json.loads(fixture.acquisition_receipt.read_text(encoding="utf-8"))
        document["installed_at"] = "2026-08-19T11:00:00Z"
        fixture.acquisition_receipt.write_bytes(canonical(document))
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("mismatched pair", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        # Positive control: resealing the same edit admits it.
        fixture.acquisition_receipt.write_bytes(seal_acquisition(document))
        self.assertEqual(0, call_main(fixture).code)

    def test_nonfinite_number_and_duplicate_key_are_refused(self) -> None:
        fixture = self.fixture()
        raw = fixture.acquisition_receipt.read_text(encoding="utf-8")
        fixture.acquisition_receipt.write_text(raw.replace('"support":"unsupported"', '"support":1e400'), encoding="utf-8")
        nonfinite = call_main(fixture)
        self.assertEqual(3, nonfinite.code)
        self.assertIn("non-finite", nonfinite.stderr)

        fixture.acquisition_receipt.write_text(
            raw.replace('"support":"unsupported"', '"support":"unsupported","support":"unsupported"'),
            encoding="utf-8",
        )
        duplicate = call_main(fixture)
        self.assertEqual(3, duplicate.code)
        self.assertIn("two meanings", duplicate.stderr)
        # Positive control: the untouched document admits.
        fixture.acquisition_receipt.write_text(raw, encoding="utf-8")
        self.assertEqual(0, call_main(fixture).code)

    def test_candidate_root_outside_the_acquisition_layout_refuses(self) -> None:
        fixture = self.fixture()
        elsewhere = fixture.root / "elsewhere"
        shutil.copytree(fixture.candidate_root, elsewhere)
        document = json.loads(fixture.acquisition_receipt.read_text(encoding="utf-8"))
        document["candidate_root_absolute_physical_path"] = str(elsewhere)
        fixture.acquisition_receipt.write_bytes(seal_acquisition(document))
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("acquisition layout", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_payload_that_disagrees_with_its_manifest_refuses(self) -> None:
        fixture = self.fixture()
        (fixture.candidate_root / "skills" / "alpha-skill" / "SKILL.md").write_text(
            "tampered\n", encoding="utf-8"
        )
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("manifest row records", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertFalse(fixture.destination("skills/alpha-skill").exists())
        # Positive control: an untampered payload admits.
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_uninventoried_payload_content_refuses(self) -> None:
        fixture = self.fixture()
        (fixture.candidate_root / "skills" / "alpha-skill" / "extra.md").write_text("extra\n", encoding="utf-8")
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("does not inventory", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_manifest_claiming_a_release_refuses(self) -> None:
        fixture = self.fixture(manifest_overrides={"release_claim": "stable"})
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("release_claim", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual(0, call_main(self.fixture()).code)

    def test_payload_with_no_claude_entries_refuses(self) -> None:
        fixture = self.fixture(payload={"agents/codex/cartographer.toml": 'name = "x"\n'})
        outcome = call_main(fixture)
        self.assertEqual(3, outcome.code)
        self.assertIn("no claude-host entries", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertEqual(0, call_main(self.fixture()).code)


class InterruptedTransactionTest(TemporaryRoot):
    def test_failure_after_one_effect_reports_partial_never_complete(self) -> None:
        fixture = self.fixture()
        before = fixture.acquisition_receipt.read_bytes()
        outcome = call_main(fixture, fail_transaction_after=1)
        self.assertEqual(4, outcome.code)
        self.assertIn("unknown effect", outcome.stderr)
        body = sealed_receipt(fixture)["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        self.assertEqual(
            1, sum(1 for entry in body["entries"] if entry["disposition"] == "installed")
        )
        journal = fixture.journal()
        self.assertEqual("terminal", journal["phase"])
        self.assertIn("failed", {record["phase"] for record in journal["entries"]})
        self.assertIn(
            "fault-injected transaction failure",
            " ".join(str(record.get("detail", "")) for record in journal["entries"]),
        )
        result = receipts.derive("validate", sealed_receipt(fixture), "the partial receipt")
        self.assertEqual("validated", result["verdict"], result["reasons"])
        self.assertEqual(before, fixture.acquisition_receipt.read_bytes())
        # A PARTIAL EFFECT FILES THE RECEIPT AS EVIDENCE AND LEAVES THE POINTER ALONE. A pointer that
        # claimed an activation nobody completed is worse than an absent one, and it would be the one
        # document `update` and `uninstall` admit (agentic-sdlc-7b2e).
        self.assertFalse(fixture.pointer.exists(), "a partial effect must not write the pointer")
        self.assertIn("was NOT written", outcome.stdout)
        self.assertIn("active pointer", outcome.stderr)
        # Positive control: the same fixture without the fault reports complete AND lands the pointer.
        clean = self.fixture()
        self.assertEqual(0, call_main(clean).code)
        self.assertEqual("complete", sealed_receipt(clean)["body"]["effect_state"])
        self.assertTrue(clean.pointer.exists())
        self.assertEqual(clean.activation_receipts()[0].read_bytes(), clean.pointer.read_bytes())

    def test_a_receipt_that_cannot_be_filed_never_becomes_the_plane_s_statement(self) -> None:
        """The ORDER is load-bearing: the receipt is durably filed BEFORE the pointer names it.

        A pointer written first would survive a kill that stopped the receipt write, and the plane
        would then name a receipt no directory holds -- which is the one state the later verbs cannot
        act on and cannot diagnose.  The fault is injected at the receipt write itself, so what is
        under test is the sequence and not the gate above it.
        """
        fixture = self.fixture()
        with mock.patch.object(
            install,
            "write_new_document",
            side_effect=install.UnknownEffect("fault-injected receipt filing failure"),
        ):
            outcome = call_main(fixture)

        self.assertEqual(4, outcome.code)
        self.assertIn("fault-injected receipt filing failure", outcome.stderr)
        self.assertEqual([], fixture.activation_receipts())
        self.assertFalse(
            fixture.pointer.exists(),
            "the pointer must never name a receipt that was not filed",
        )
        # Positive control: the same fixture without the fault files the receipt AND lands the pointer,
        # so the absence above is the injected failure and not a run that never got that far.
        clean = self.fixture()
        self.assertEqual(0, call_main(clean).code)
        self.assertEqual(1, len(clean.activation_receipts()))
        self.assertTrue(clean.pointer.exists())
        self.assertEqual(clean.activation_receipts()[0].read_bytes(), clean.pointer.read_bytes())

    def test_failure_before_any_effect_completed_reports_unknown(self) -> None:
        fixture = self.fixture()
        outcome = call_main(fixture, fail_transaction_after=0)
        self.assertEqual(4, outcome.code)
        body = sealed_receipt(fixture)["body"]
        self.assertEqual("unknown", body["effect_state"])
        self.assertEqual("unknown", body["terminal_phase"])
        self.assertEqual(
            set(), {entry["disposition"] for entry in body["entries"]} - {"preserved"}
        )
        result = receipts.derive("validate", sealed_receipt(fixture), "the unknown receipt")
        self.assertEqual("validated", result["verdict"], result["reasons"])
        # An UNKNOWN effect is not an activation either: the receipt is filed, the pointer is not.
        self.assertFalse(fixture.pointer.exists(), "an unknown effect must not write the pointer")
        # Positive control: the fault is what caused it, and the clean run does land the pointer.
        control = self.fixture()
        self.assertEqual(0, call_main(control).code)
        self.assertTrue(control.pointer.exists())


class RecordedUnknownsTest(TemporaryRoot):
    def test_an_undigestable_entry_is_named_and_never_reported_complete(self) -> None:
        """An observation that could not be made is not a completion, and it is NAMED, not dropped."""
        fixture = self.fixture()
        with mock.patch.object(
            install, "observe_content", lambda _bundle, _path: (None, "fault-injected digest failure")
        ):
            outcome = call_main(fixture)
        self.assertEqual(4, outcome.code)
        body = sealed_receipt(fixture)["body"]
        self.assertEqual("partial", body["effect_state"])
        self.assertEqual("activated-partial", body["terminal_phase"])
        self.assertEqual(
            sorted(CLAUDE_DESTINATIONS),
            sorted(record["subject"] for record in body["unknowns"]),
        )
        self.assertEqual({"entry-content"}, {record["observation"] for record in body["unknowns"]})
        for entry in body["entries"]:
            self.assertIsNone(entry["content_sha256"], entry["entry_name"])
        result = receipts.derive("validate", sealed_receipt(fixture), "the partial receipt")
        self.assertEqual("validated", result["verdict"], result["reasons"])
        # The gate consults the RECORDED UNKNOWNS, not only the outcomes: every entry moved, and the
        # pointer still stays put, because an observation nobody could make is not a completion.
        self.assertFalse(fixture.pointer.exists(), "a recorded unknown must not activate the plane")
        # Positive control: without the injected failure the same run digests and reports complete.
        clean = self.fixture()
        self.assertEqual(0, call_main(clean).code)
        self.assertEqual("complete", sealed_receipt(clean)["body"]["effect_state"])
        self.assertEqual([], sealed_receipt(clean)["body"]["unknowns"])
        self.assertTrue(clean.pointer.exists())


SECOND_ARCHIVE_SHA = hashlib.sha256(b"fabricated-archive-two").hexdigest()
SECOND_CANDIDATE_ID = hashlib.sha256(b"fabricated-candidate-two").hexdigest()
SECOND_OPERATION_ID = "op-" + hashlib.sha256(b"fabricated-operation-two").hexdigest()[:32]
SECOND_PRODUCT_VERSION = "0.7.4"
#: The same entry names with different content, so every entry the refresh touches is an OWNED
#: verified-unchanged slot rather than a blocked one.
SECOND_PAYLOAD_FILES = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha two\n",
    "skills/alpha-skill/references/notes.md": "notes two\n",
    "agents/claude/cartographer.md": "cartographer two\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame two\n",
}


def acquire_second_candidate(fixture: Fixture) -> Path:
    """Fabricate ONE more acquired candidate on the same host: a different identity and version.

    The same fabrication `build_fixture` performs, re-expressed for a second archive digest so the
    update verb has exactly one admissible candidate that is not the one the install activated.
    """
    candidate_root = (
        fixture.data_home / "agentic-sdlc" / "acquisition" / "candidates" / SECOND_ARCHIVE_SHA / "root"
    )
    candidate_root.mkdir(parents=True)
    for relative, text in SECOND_PAYLOAD_FILES.items():
        target = candidate_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    contract_path = candidate_root / "policy" / "release-contract.v1.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_bytes(RELEASE_CONTRACT_PATH.read_bytes())
    manifest = {
        "archive_root": f"agentic-sdlc-candidate-{SECOND_CANDIDATE_ID}-linux-x64",
        "artifact_kind": "unpublished-candidate",
        "candidate_id": SECOND_CANDIDATE_ID,
        "inventory": inventory_for_tree(candidate_root),
        "platform": "linux-x64",
        "product_version": SECOND_PRODUCT_VERSION,
        "public_channel": None,
        "release_claim": "none",
        "schema_version": "release-candidate/v1",
        "support_tier": "unsupported",
    }
    (candidate_root / "manifest.json").write_bytes(canonical(manifest))
    receipt = {
        "activation": "absent",
        "archive_sha256": SECOND_ARCHIVE_SHA,
        "candidate_root_absolute_physical_path": str(candidate_root),
        "effect_state": "complete",
        "installed_at": "2026-08-20T10:00:00Z",
        "journal_sha256": hashlib.sha256(b"journal-two").hexdigest(),
        "operation_id": SECOND_OPERATION_ID,
        "plan_sha256": hashlib.sha256(b"plan-two").hexdigest(),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    directory = fixture.state_home / "agentic-sdlc" / "acquisition" / "receipts"
    (directory / f"{SECOND_ARCHIVE_SHA}.json").write_bytes(seal_acquisition(receipt))
    return candidate_root


class InstallThenUpdateTest(TemporaryRoot):
    """The two verbs meet at ONE document, and this test drives both of them for real.

    ``ccodex sdlc update`` admits ``activation/active-receipt.json`` and nothing else.  Before
    agentic-sdlc-7b2e this module never wrote it, so a real install at exit 0 followed by a real
    update refused at exit 3 with no usable active receipt: the front door of the plane the install
    had just built did not exist.  Nothing here is a fixture receipt -- the install writes the
    pointer, and the update reads the document the install actually wrote.
    """

    def update_config(self, fixture: Fixture, instant: str = LATER_INSTANT) -> Any:
        return update.Config(
            home=fixture.home,
            state_home=fixture.state_home,
            data_home=fixture.data_home,
            codex_home=fixture.config.codex_home,
            installer_state_root=fixture.installer_state_root,
            observed_host_version=HOST_VERSION,
            observed_instant=instant,
            observed_system=fixture.config.observed_system,
            observed_machine=fixture.config.observed_machine,
        )

    def call_update(self, fixture: Fixture, instant: str = LATER_INSTANT) -> Outcome:
        out, err = io.StringIO(), io.StringIO()
        config = self.update_config(fixture, instant)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(update, "default_config", lambda: config))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = update.main([])
        assert isinstance(code, int) and not isinstance(code, bool), repr(code)
        return Outcome(code, out.getvalue(), err.getvalue())

    def test_a_real_install_is_updatable_and_the_update_supersedes_its_pointer(self) -> None:
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        installed = json.loads(fixture.pointer.read_text(encoding="utf-8"))
        install_receipt_id = installed["receipt_id"]
        self.assertEqual("install", installed["body"]["operation"])
        self.assertEqual(PRODUCT_VERSION, installed["body"]["resolved_version"])

        acquire_second_candidate(fixture)
        outcome = self.call_update(fixture)

        self.assertEqual(0, outcome.code, outcome.stderr)
        current = json.loads(fixture.pointer.read_text(encoding="utf-8"))
        self.assertEqual("update", current["body"]["operation"])
        self.assertEqual(SECOND_PRODUCT_VERSION, current["body"]["resolved_version"])
        self.assertEqual(SECOND_ARCHIVE_SHA, current["body"]["archive_sha256"])
        self.assertEqual(
            "validated", receipts.derive("validate", current, "the updated pointer")["verdict"]
        )
        # The update SUPERSEDES exactly the receipt the install's pointer named.
        superseded = [
            reference["receipt_id"]
            for reference in current["ancestors"]
            if reference["relation"] == "supersedes"
        ]
        self.assertEqual([install_receipt_id], superseded)
        # Both receipts are filed, and the prior one is retained byte-identically under its own id.
        filed = {path.name: path for path in fixture.activation_receipts()}
        self.assertEqual(
            {f"{install_receipt_id}.json", f"{current['receipt_id']}.json"}, set(filed)
        )
        self.assertEqual(installed, json.loads(filed[f"{install_receipt_id}.json"].read_text()))
        self.assertEqual(
            filed[f"{current['receipt_id']}.json"].read_bytes(), fixture.pointer.read_bytes()
        )
        # The refresh really replaced the content on disk, so this is one activation, not two planes.
        self.assertEqual(
            "cartographer two\n",
            fixture.destination("agents/cartographer.md").read_text(encoding="utf-8"),
        )
        self.assertIn("names this update's receipt", outcome.stdout)

    def test_the_plane_the_two_verbs_leave_is_not_ambiguous_to_the_shipped_reader(self) -> None:
        """The projection reads the plane these two verbs really built, not a fabricated one."""
        fixture = self.fixture()
        self.assertEqual(0, call_main(fixture).code)
        acquire_second_candidate(fixture)
        self.assertEqual(0, self.call_update(fixture).code)

        readiness = reader.observe_readiness(
            json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")),
            acquisition_receipts=fixture.state_home / "agentic-sdlc" / "acquisition" / "receipts",
            activation_receipts=fixture.state_home / "agentic-sdlc" / "activation" / "receipts",
            validator=receipts,
            validator_reason=None,
        )
        findings = reader.readiness_findings(readiness)

        self.assertEqual(2, len(readiness["activation"]["receipts"]))
        self.assertEqual([SECOND_PRODUCT_VERSION], readiness["activation"]["activated_versions"])
        self.assertEqual("matched", readiness["activation"]["active_pointer"]["correlation"])
        self.assertEqual(1, len(readiness["activation"]["superseded_activations"]))
        self.assertEqual([], findings)
        # POSITIVE CONTROL: remove the pointer, and re-seal the second receipt as an INSTALL -- which
        # the family forbids from carrying a supersedes ancestor at all -- and the identical projection
        # over two activated receipts DOES name the ambiguity. The seal is re-derived by the family's
        # own producer, so the control is two VALID receipts and not two broken ones.
        fixture.pointer.unlink()
        for path in fixture.activation_receipts():
            document = json.loads(path.read_text(encoding="utf-8"))
            if document["body"]["operation"] != "update":
                continue
            document["body"]["operation"] = "install"
            document["body"]["record_sha256"] = ""
            document["content_digest"] = receipts.UNSEALED
            document["ancestors"] = [
                reference
                for reference in document["ancestors"]
                if reference["relation"] != "supersedes"
            ]
            resealed = receipts.derive("seal", document, "the control receipt")
            self.assertEqual(receipts.VERDICT_SEALED, resealed["verdict"], resealed["reasons"])
            path.write_bytes(receipts.canonical_bytes(resealed["receipt"]))
        control = reader.observe_readiness(
            json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")),
            acquisition_receipts=fixture.state_home / "agentic-sdlc" / "acquisition" / "receipts",
            activation_receipts=fixture.state_home / "agentic-sdlc" / "activation" / "receipts",
            validator=receipts,
            validator_reason=None,
        )
        codes = {finding["code"] for finding in reader.readiness_findings(control)}
        self.assertIn("state-ambiguous", codes)


class DispatchContractTest(TemporaryRoot):
    def test_main_returns_int_exit_classes_and_never_bool(self) -> None:
        cases = (
            (["--host", "claude"], 0, None),
            (["--host", "codex"], 3, None),
            ([], 3, None),
            (["--host=claude"], 3, None),
            (["--host", "claude", "--extra"], 3, None),
        )
        for argv, expected, fault in cases:
            with self.subTest(argv=argv):
                fixture = self.fixture()
                outcome = call_main(fixture, argv=argv, fail_transaction_after=fault)
                self.assertEqual(expected, outcome.code)
        faulted = self.fixture()
        self.assertEqual(4, call_main(faulted, fail_transaction_after=0).code)

    def test_the_shipped_reader_dispatches_this_module(self) -> None:
        if sys.version_info[:3] != (3, 12, 11):
            self.skipTest("the dispatcher admits only its bound isolated Python 3.12.11")
        shadow = self.root / "shadow"
        (shadow / "scripts").mkdir(parents=True)
        (shadow / "policy").mkdir(parents=True)
        for relative in (
            "policy/ccodex-sdlc-read-report.v1.json",
            "policy/release-contract.v1.json",
            "scripts/ccodex_sdlc.py",
            "scripts/ccodex_sdlc_readonly.py",
            "scripts/ccodex_sdlc_install.py",
            "scripts/install_operator_tools.py",
            "scripts/install_skill_bundle.py",
            "scripts/distribution_activation_receipt.py",
        ):
            shutil.copy2(ROOT / relative, shadow / relative)
        fixture = self.fixture()
        completed = subprocess.run(
            [str(Path(sys.executable)), "-I", "-B", str(shadow / "scripts" / "ccodex_sdlc.py"), "install", "--host", "claude"],
            capture_output=True,
            text=True,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": str(fixture.home),
                "XDG_STATE_HOME": str(fixture.state_home),
                "XDG_DATA_HOME": str(fixture.data_home),
                "CODEX_HOME": str(fixture.config.codex_home),
                "CLAUDE_HOST_VERSION_UNUSED": "1",
            },
            check=False,
            timeout=600,
        )
        if completed.returncode == 3 and "host version could not be observed" in completed.stderr:
            self.skipTest("this host has no observable Claude Code version")
        skip_when_a_child_refused_this_host(self, completed)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("effect complete", completed.stdout)
        for relative in CLAUDE_DESTINATIONS:
            self.assertTrue((fixture.home / ".claude" / relative).exists(), relative)
        receipt_dir = fixture.state_home / "agentic-sdlc" / "activation" / "receipts"
        self.assertEqual(1, len(sorted(receipt_dir.glob("*.json"))))
        # Positive control: the same shadow refuses the codex host at exit 3 without a receipt.
        refused = subprocess.run(
            [str(Path(sys.executable)), "-I", "-B", str(shadow / "scripts" / "ccodex_sdlc.py"), "install", "--host", "codex"],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        self.assertEqual(2, refused.returncode)


class GuardInteractionTest(unittest.TestCase):
    def test_the_read_only_guard_blocks_the_primitives_this_activation_needs(self) -> None:
        """The reader cannot borrow this module's authority, and this module never runs guarded."""
        adapter = _load(INSTALLER_PATH, "ccodex_sdlc_install_guard_probe")
        needed = (
            "write_state",
            "persist_state",
            "installer_lock",
            "durable_mkdir",
            # Landed after the guard's pinned name set was first written (agentic-sdlc-7c7d): these
            # arm, commit, retire, and rename an entry's own transaction and must be closed into the
            # same set rather than left reachable by a future reader that loads this module for more
            # than `readonly_projection`.
            "transactional_create",
            "transactional_delete",
            "transactional_rename",
            "transactional_replace",
        )
        for name in needed:
            self.assertTrue(callable(getattr(adapter, name)), name)
        guard.block_lifecycle_mutators(adapter)
        for name in needed:
            with self.subTest(name=name):
                with self.assertRaises(guard.ReadOnlyViolation):
                    getattr(adapter, name)()
        # Positive control: a name the guard does not pin is still the real function (calling it
        # with no arguments dies on its own signature, not on ReadOnlyViolation), which is why this
        # module is never loaded into a guarded reader process in the first place.
        with self.assertRaises(TypeError):
            adapter.readonly_projection()


class ConfigSeamTest(unittest.TestCase):
    def test_default_config_reads_the_documented_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment = {
                "XDG_STATE_HOME": str(root / "state"),
                "XDG_DATA_HOME": str(root / "data"),
                "CODEX_HOME": str(root / "codex"),
                "HOME": str(root / "home"),
            }
            with mock.patch.dict(os.environ, environment, clear=False):
                with mock.patch.object(install.Path, "home", classmethod(lambda _cls: root / "home")):
                    config = install.default_config()
            self.assertEqual(root / "state", config.state_home)
            self.assertEqual(root / "data", config.data_home)
            self.assertEqual(root / "codex", config.codex_home)
            self.assertEqual(root / "home", config.home)
            self.assertEqual(
                root / "state" / "agentic-sdlc" / "acquisition" / "receipts",
                config.acquisition_receipts_dir,
            )
            self.assertEqual(
                root / "data" / "agentic-sdlc" / "acquisition" / "candidates",
                config.acquisition_candidates_dir,
            )
            # Positive control: an empty variable falls back rather than yielding an empty path.
            with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "  "}, clear=False):
                with mock.patch.object(install.Path, "home", classmethod(lambda _cls: root / "home")):
                    fallback = install.default_config()
            self.assertEqual(root / "home" / ".local" / "state", fallback.state_home)

    def test_unsupplied_is_not_none(self) -> None:
        self.assertIsNot(install.UNSUPPLIED, None)
        self.assertFalse(isinstance(None, install._Unsupplied))
        self.assertTrue(isinstance(install.UNSUPPLIED, install._Unsupplied))


if __name__ == "__main__":  # pragma: no cover - direct execution convenience
    unittest.main()
