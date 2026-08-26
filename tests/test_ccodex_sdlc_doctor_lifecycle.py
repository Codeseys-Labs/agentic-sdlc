"""The host-level lifecycle readiness that ``ccodex doctor`` and ``ccodex status`` now READ.

Four dimensions are under test: the selected payload against the activated version, the
distribution-activation receipt's presence and seal validity, an interrupted transition, and the
release contract's declared incompatibility against the observed host.  Every one of them is an
observation: nothing here may repair, network, execute a host, resolve a version, or write.

Three properties this module holds harder than the rest.

READ-ONLY IS MEASURED, NOT ASSERTED.  The end-to-end tests hash every file under the injected home
and state root before and after the run and require the two inventories to be identical, so a
future reader that "just" refreshed a receipt fails here.  The sealed acquisition receipt gets its
own byte-identity assertion, because agentic-sdlc-0cce decided that document is never mutated.

ABSENT IS NAMED, NOT INVENTED.  A host that never activated anything has no plane.  That reads as
absent with a reason and leaves the exit class exactly where today's contract put it; it does not
become a defect, and it does not become a guessed success either.  The same rule covers a validator
that is not in this distribution and a host version a read-only command cannot observe.

EVERY NEGATIVE ASSERTION CARRIES A POSITIVE CONTROL.  An absence proves nothing unless the same
harness is shown to detect the presence, so each test that asserts "no finding" also shows the
finding the identical harness produces once the condition it names is real.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]
READER_SCRIPT = ROOT / "scripts" / "ccodex_sdlc.py"
GUARD_SCRIPT = ROOT / "scripts" / "ccodex_sdlc_readonly.py"
VALIDATOR_SCRIPT = ROOT / "scripts" / "distribution_activation_receipt.py"
CONTRACT_PATH = ROOT / "policy" / "release-contract.v1.json"
POLICY_PATH = ROOT / "policy" / "ccodex-sdlc-read-report.v1.json"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The reader is loaded for its PURE observers only. `load_read_only_adapters`,
# `observe_projections`, and `observe_host_readiness` install the process-wide read-only guard, so
# calling one of them in this process would block the test harness's own writes; the end-to-end
# coverage runs the reader as a subprocess instead.
reader = _load("doctor_lifecycle_reader", READER_SCRIPT)
guard = _load("doctor_lifecycle_guard", GUARD_SCRIPT)
receipts = _load("doctor_lifecycle_receipts", VALIDATOR_SCRIPT)
#: The ownership substrate, loaded for FIXTURE CONSTRUCTION only: `write_bundle_pending`
#: builds an armed `pending` slot with the installer's own constructors so the planted
#: document is its shape rather than a second hand-typed spelling of it.
bundle = _load("doctor_lifecycle_bundle", ROOT / "scripts" / "install_skill_bundle.py")

BODY_SCHEMA = "agentic-sdlc/distribution-activation-body@2"
#: The read-only historical generation: admitted by `validate`, never sealed again.
BODY_SCHEMA_V1 = "agentic-sdlc/distribution-activation-body@1"
ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"
RECEIPT_KIND = "distribution-activation"
ACQUISITION_SCHEMA = "release-candidate-acquisition-receipt/v1"
# The one relation that retires a receipt, and the one file that names the current one. Both are
# spelled out here and pinned against the reader's and the family's own constants below, so a rename
# in either place fails as a named disagreement instead of silently making these fixtures fictional.
SUPERSEDES_RELATION = "supersedes"
#: The KEYED pointer this reader resolves for (claude, user), and the pre-keyed name it still reports
#: as its own state.  Both are spelled out here and pinned against the reader's own constants below.
ACTIVE_POINTER_SEGMENTS = ("active", "claude", "user.json")
LEGACY_ACTIVE_POINTER_NAME = "active-receipt.json"
# The SIX reader usage lines and the reader forms, pinned as literals: this ticket touches the
# projection and must leave the ratified front-door grammar byte-for-byte alone. The surface itself
# MOVED with agentic-sdlc-7a2b W3a -- `ccodex sdlc <verb>` is retired at the dispatcher and all six
# verbs are top-level -- so what is pinned here is the new surface, and the pin is what makes a later
# drift in it a named failure rather than a silent widening. `inspect` is gone: `status` reads one
# selected plane and `doctor` reads the whole box, so a fourth spelling of a read had nothing left to
# say.
READER_USAGE_LINES = (
    "usage: ccodex install   --scope user|project --agent claude|codex [--project PATH]"
    " [--mode auto|link|copy] [--dry-run]",
    "       ccodex status    --scope user|project --agent claude|codex [--project PATH] [--json]",
    "       ccodex update    --scope user|project --agent claude|codex [--project PATH]",
    "       ccodex uninstall --scope user|project --agent claude|codex [--project PATH] [--dry-run]",
    "       ccodex doctor    [--json]",
    "       ccodex recover   --dry-run [--json] | --apply <plan-sha256>",
)
PLAN_DIGEST = "5" * 64
#: The two selectors EVERY selector verb requires, spelled once so a vector here cannot drift from the
#: grammar it drives. There is no default and no wildcard for either, so nothing below omits one.
SELECTED = ("--scope", "user", "--agent", "claude")
# Each admitted form beside the whole ``Invocation`` it parses to. The expected side is a SIX-field
# tuple now rather than four: the invocation carries the parsed `scope` and `agent` as well, so a
# parser that silently dropped a selector would compare unequal here instead of passing on a
# shortened tuple. THE FORWARDED VALUE IS STILL THE AGENT, and for `install`/`update`/`uninstall` it
# is what `main` wraps in the modules' own `['--host', <agent>]` ABI -- one operator spelling
# (`--agent`) and one module ABI (`--host`), which is why the operator flag below is `--agent` while
# the module-facing assertions further down still read `--host`.
#: The two finding codes W4 added, spelled once so a test cannot assert one and forget the other.
ORPHAN_CODES = ("orphaned-root", "pointer-outlived-root")

READER_FORMS = (
    (("status", *SELECTED), ("status", False, False, None, "user", "claude", None, None)),
    (("status", *SELECTED, "--json"), ("status", False, True, None, "user", "claude", None, None)),
    (
        ("status", "--scope", "user", "--agent", "codex"),
        ("status", False, False, None, "user", "codex", None, None),
    ),
    (("doctor",), ("doctor", False, False, None, None, None, None, None)),
    (("doctor", "--json"), ("doctor", False, True, None, None, None, None, None)),
    (("recover", "--dry-run"), ("recover", True, False, None, None, None, None, None)),
    (("recover", "--apply", PLAN_DIGEST), ("recover", False, False, PLAN_DIGEST, None, None, None, None)),
    (("install", *SELECTED), ("install", False, False, "claude", "user", "claude", None, None)),
    (
        ("install", "--scope", "user", "--agent", "codex"),
        ("install", False, False, "codex", "user", "codex", None, None),
    ),
    (("update", *SELECTED), ("update", False, False, "claude", "user", "claude", None, None)),
    (
        ("update", "--scope", "user", "--agent", "codex"),
        ("update", False, False, "codex", "user", "codex", None, None),
    ),
    (("uninstall", *SELECTED), ("uninstall", False, False, "claude", "user", "claude", None, None)),
    (
        ("uninstall", "--scope", "user", "--agent", "codex"),
        ("uninstall", False, False, "codex", "user", "codex", None, None),
    ),
)
#: The three reader verbs and the argument tail each one needs. `status` carries the two required
#: selectors, `doctor` and `recover` take neither -- `doctor` is the whole-box read and `recover`
#: resumes the one pending slot the substrate can carry, which is not a scoped object.
READER_VERBS = (("status", SELECTED), ("doctor", ()), ("recover", ("--dry-run",)))


def hexof(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def activation_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "archive_sha256": hexof("archive"),
        "candidate_id": hexof("candidate"),
        "effect_state": "complete",
        "entries": [
            {
                "content_sha256": hexof("entry"),
                "disposition": "installed",
                "entry_name": "skills/agentic-sdlc",
                "mode": "copy",
                "prestate": "absent",
            }
        ],
        "journal_sha256": hexof("journal"),
        "operation": "install",
        "plan_sha256": hexof("plan"),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": "0.7.3",
        "resolved_version": "0.7.3",
        "schema_version": BODY_SCHEMA,
        "scope": {"agent": "claude", "kind": "user"},
        "terminal_phase": "activated",
        "unknowns": [],
        "version_source": "adapter-readback",
    }
    body.update(overrides)
    return body


def superseding_ancestors(replaced: str, acquisition: str = "acquisition-2") -> list[dict[str, str]]:
    """The two typed ancestors an ``operation: update`` receipt carries, in the family's own shape.

    The family admits ``supersedes`` ONLY for ``operation: update`` and requires exactly one of it,
    so a fixture that supersedes anything is an update fixture.  The ``derived-from`` reference names
    the acquisition the refresh drew its payload from and must never read as a supersession.
    """
    return [
        {"expected_kind": RECEIPT_KIND, "receipt_id": acquisition, "relation": "derived-from"},
        {"expected_kind": RECEIPT_KIND, "receipt_id": replaced, "relation": SUPERSEDES_RELATION},
    ]


def sealed_activation_receipt(
    *,
    receipt_id: str = "activation-1",
    ancestors: list[dict[str, str]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """One receipt sealed by the family's OWN producer, so the fixture is never a hand-built seal."""
    document = {
        "ancestors": ancestors
        if ancestors is not None
        else [
            {"expected_kind": RECEIPT_KIND, "receipt_id": "acquisition-1", "relation": "derived-from"}
        ],
        "body": activation_body(**overrides),
        "content_digest": "",
        "emitting_plane": "repository-gate",
        "receipt_id": receipt_id,
        "receipt_kind": RECEIPT_KIND,
        "schema": ENVELOPE_SCHEMA,
        "stated_at": "2026-08-20T12:00:00Z",
    }
    result = receipts.derive("seal", document, "the observation")
    if result["verdict"] != receipts.VERDICT_SEALED:
        raise AssertionError(f"fixture did not seal: {result['reasons']}")
    receipt = result["receipt"]
    assert isinstance(receipt, dict)
    return receipt


def acquisition_receipt(candidate_root: Path, **overrides: Any) -> dict[str, Any]:
    """The acquisition plane's own terminal record, in the shape its producer writes it."""
    document: dict[str, Any] = {
        "activation": "absent",
        "archive_sha256": hexof("archive"),
        "candidate_root_absolute_physical_path": str(candidate_root),
        "effect_state": "complete",
        "installed_at": "2026-08-20T11:00:00Z",
        "journal_sha256": hexof("journal"),
        "operation_id": "acquire",
        "plan_sha256": hexof("plan"),
        "public_channel": None,
        "record_sha256": hexof("acquisition-record"),
        "release_claim": "none",
        "schema_version": ACQUISITION_SCHEMA,
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    document.update(overrides)
    return document


def inventory(*roots: Path) -> dict[str, str]:
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


WINDOWS_SKIP = unittest.skipIf(
    os.name == "nt",
    "this suite observes the acquisition/activation planes only the POSIX-only "
    "durable-write ccodex lifecycle produces; native Windows fails closed by name "
    "at the CLI, so no such plane exists there",
)


#: HOW EACH PER-VERB MODULE NAMES ITSELF, which is NOT one string across the family: `install` names
#: the surviving top-level invocation (renamed in W3b of agentic-sdlc-7a2b, seed agentic-sdlc-67c9) and
#: the other two still name the retired `ccodex sdlc <verb>` spelling because they are other waves'
#: files. A shared f-string here asserted one spelling for all three and would have passed while
#: proving the wrong thing about two of them.
MODULE_OWN_PREFIX = {
    "install": "error: ccodex install ",
    "update": "error: ccodex sdlc update ",
    "uninstall": "error: ccodex sdlc uninstall ",
}

class ReadinessHarness(unittest.TestCase):
    """One injected host: an acquisition plane, an activation plane, and an acquired candidate."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.state = self.root / "state"
        self.acquisition = self.state / "agentic-sdlc" / "acquisition" / "receipts"
        self.activation = self.state / "agentic-sdlc" / "activation" / "receipts"
        self.candidate = self.root / "data" / "candidates" / hexof("archive") / "root"
        self.home.mkdir()
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    # ---- fixture writers ---------------------------------------------------------------------

    def write_candidate(self, version: str = "0.7.3") -> None:
        self.candidate.mkdir(parents=True, exist_ok=True)
        (self.candidate / "manifest.json").write_text(
            json.dumps({"candidate_id": hexof("candidate"), "product_version": version}),
            encoding="utf-8",
        )

    def write_acquisition(self, **overrides: Any) -> Path:
        self.acquisition.mkdir(parents=True, exist_ok=True)
        document = acquisition_receipt(self.candidate, **overrides)
        path = self.acquisition / f"{document['archive_sha256']}.json"
        path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
        return path

    def write_activation(self, name: str | None = None, **overrides: Any) -> Path:
        self.activation.mkdir(parents=True, exist_ok=True)
        receipt = sealed_activation_receipt(**overrides)
        path = self.activation / (name or f"{hexof('activation')}.json")
        path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
        return path

    def write_raw_activation(self, name: str, content: bytes) -> Path:
        self.activation.mkdir(parents=True, exist_ok=True)
        path = self.activation / name
        path.write_bytes(content)
        return path

    @property
    def pointer(self) -> Path:
        """The plane's active statement, at the KEYED layout position the shipped writers use."""
        return self.state.joinpath("agentic-sdlc", "activation", *ACTIVE_POINTER_SEGMENTS)

    @property
    def legacy_pointer(self) -> Path:
        """The pre-keyed spelling, which a read verb still reports and a mutating verb migrates."""
        return self.state / "agentic-sdlc" / "activation" / LEGACY_ACTIVE_POINTER_NAME

    def write_pointer(self, receipt: dict[str, Any]) -> Path:
        """Write the pointer exactly as ``ccodex install``/``update`` do: the receipt's own bytes."""
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_bytes(receipts.canonical_bytes(receipt))
        return self.pointer

    def file_activation(self, receipt: dict[str, Any], name: str | None = None) -> Path:
        """File one ALREADY sealed receipt under a name derived from the identity it claims."""
        self.activation.mkdir(parents=True, exist_ok=True)
        path = self.activation / (name or f"{hexof(receipt['receipt_id'])}.json")
        path.write_bytes(receipts.canonical_bytes(receipt))
        return path

    def write_payload(self, archive: str, version: str) -> Path:
        """One more acquired candidate root plus its acquisition receipt, keyed by its own digest."""
        root = self.root / "data" / "candidates" / archive / "root"
        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.json").write_text(
            json.dumps({"candidate_id": hexof(f"candidate-{archive}"), "product_version": version}),
            encoding="utf-8",
        )
        self.acquisition.mkdir(parents=True, exist_ok=True)
        document = acquisition_receipt(root, archive_sha256=archive)
        (self.acquisition / f"{archive}.json").write_text(
            json.dumps(document, sort_keys=True), encoding="utf-8"
        )
        return root

    def write_updated_plane(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """The plane a HEALTHY ``ccodex update`` leaves behind, in the shape it really leaves it.

        Two acquired payloads, the prior receipt RETAINED under its own id, the new receipt filed
        under its own id with one ``supersedes`` ancestor naming the prior one, and the pointer
        carrying the new receipt's exact bytes.  Nothing here is a mock: both receipts are sealed by
        the family's own producer, and the pointer is written the way the update verb writes it.
        """
        self.write_candidate()
        self.write_acquisition()
        new_archive = hexof("archive-b")
        self.write_payload(new_archive, "0.7.4")
        prior = sealed_activation_receipt(receipt_id="activation-1")
        current = sealed_activation_receipt(
            receipt_id="activation-2",
            ancestors=superseding_ancestors("activation-1"),
            operation="update",
            archive_sha256=new_archive,
            candidate_id=hexof(f"candidate-{new_archive}"),
            requested_version="0.7.4",
            resolved_version="0.7.4",
        )
        self.file_activation(prior)
        self.file_activation(current)
        self.write_pointer(current)
        return prior, current

    def receipt_for(self, activation: dict[str, Any], receipt_id: str) -> dict[str, Any]:
        """The ONE observation whose locator is the filed name of this receipt identity."""
        locator = f"activation-receipt://{hexof(receipt_id)}"
        matches = [item for item in activation["receipts"] if item["locator"] == locator]
        assert len(matches) == 1, (locator, [item["locator"] for item in activation["receipts"]])
        return matches[0]

    # ---- observation --------------------------------------------------------------------------

    def observe(
        self,
        *,
        validator: Any = receipts,
        validator_reason: str | None = None,
        observed_host_version: str | None = None,
        contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return reader.observe_readiness(
            self.contract if contract is None else contract,
            acquisition_receipts=self.acquisition,
            activation_receipts=self.activation,
            validator=validator,
            validator_reason=validator_reason,
            observed_host_version=observed_host_version,
        )

    def findings(self, **kwargs: Any) -> list[dict[str, str]]:
        return reader.readiness_findings(self.observe(**kwargs))

    def codes(self, findings: list[dict[str, str]]) -> set[str]:
        return {finding["code"] for finding in findings}

    # ---- subprocess ---------------------------------------------------------------------------

    def write_bundle_pending(self) -> Path:
        """Arm the ownership plane's own `pending` slot, through the installer's own helpers.

        Built with `install_skill_bundle`'s constructors rather than hand-typed JSON: the document has
        to satisfy `validate_state` and `pending_selects_config`, and a hand-typed copy would pass this
        fixture's eye while failing the reader's, or drift silently when the schema moves.
        """
        config = bundle.Config(ROOT, self.home, self.home / ".codex", "auto", True, "all", self.state)
        source = self.root / "bundle-source" / "doctor-pending-fixture"
        source.mkdir(parents=True, exist_ok=True)
        (source / "SKILL.md").write_text("---\nname: doctor-pending-fixture\n---\n", encoding="utf-8")
        entry = bundle.Entry("claude", "skill", "doctor-pending-fixture", source)
        destination = bundle.destination_for(entry, config)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copytree(source, destination)
        record = bundle.entry_record(entry, "copy", installed_digest=bundle.digest(destination))
        document = config.state_path
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(
            json.dumps(
                {
                    "version": bundle.STATE_VERSION,
                    "entries": {},
                    "pending": bundle.pending_slot("install", str(destination), None, record),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return document

    def run_reader(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "-B", str(READER_SCRIPT), *arguments],
            env={
                "HOME": str(self.home),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "",
                "XDG_STATE_HOME": str(self.state),
                "XDG_BIN_HOME": str(self.root / "bin"),
                "CODEX_HOME": str(self.home / ".codex"),
            },
            capture_output=True,
            text=True,
            check=False,
        )


@WINDOWS_SKIP
class DoctorLifecycleReadinessTests(ReadinessHarness):
    # ---- absence -------------------------------------------------------------------------------

    def test_an_absent_activation_plane_is_named_absent_and_leaves_the_exit_class_alone(self) -> None:
        readiness = self.observe()

        self.assertEqual(readiness["activation"]["state"], "absent")
        self.assertEqual(readiness["activation"]["listing_reason"], "absent")
        self.assertEqual(readiness["activation"]["activated_versions"], [])
        self.assertEqual(readiness["reconciliation"]["activated_versions"], [])
        self.assertEqual(readiness["selection"]["state"], "absent")
        self.assertEqual(readiness["reconciliation"]["version_delta"], "unknown")
        self.assertEqual(reader.readiness_findings(readiness), [])
        for verb, suffix in READER_VERBS:
            with self.subTest(verb=verb):
                completed = self.run_reader(verb, *suffix, "--json")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                report = json.loads(completed.stdout)
                self.assertEqual(report["overall"]["exit_class"], "ok")
                self.assertEqual(
                    [finding for finding in report["findings"] if finding["component"] == "checkout"], []
                )
        # Positive control: the identical harness DOES surface a checkout finding once the plane
        # holds something it can name, so the empty lists above are absence and not a dead reader.
        self.write_raw_activation("not-a-receipt.json", b"{}")
        control = self.run_reader("doctor", "--json")
        self.assertEqual(control.returncode, 0, control.stderr)
        control_report = json.loads(control.stdout)
        self.assertTrue(
            [finding for finding in control_report["findings"] if finding["component"] == "checkout"]
        )

    # ---- a valid receipt ------------------------------------------------------------------------

    def test_a_valid_receipt_reports_both_versions_and_a_true_seal_without_a_finding(self) -> None:
        self.write_candidate("0.7.3")
        self.write_acquisition()
        self.write_activation()

        readiness = self.observe()

        receipt = readiness["activation"]["receipts"][0]
        self.assertTrue(receipt["seal_valid"])
        self.assertEqual(receipt["state"], "validated")
        self.assertEqual(receipt["terminal_phase"], "activated")
        self.assertEqual(receipt["activated_version"], "0.7.3")
        self.assertEqual(readiness["activation"]["state"], "observed")
        self.assertEqual(readiness["activation"]["activated_versions"], ["0.7.3"])
        self.assertEqual(readiness["selection"]["versions"], ["0.7.3"])
        self.assertTrue(readiness["selection"]["payloads"][0]["acquired"])
        self.assertEqual(readiness["reconciliation"]["version_delta"], "same")
        self.assertEqual(readiness["reconciliation"]["matched"], [receipt["locator"]])
        self.assertEqual(readiness["reconciliation"]["unmatched"], [])
        self.assertEqual(reader.readiness_findings(readiness), [])
        # Positive control for the true seal: the same reader reports False, with a reason, for the
        # same document once one sealed byte no longer agrees with the body.
        tampered = json.loads((self.activation / f"{hexof('activation')}.json").read_text())
        tampered["body"]["resolved_version"] = "9.9.9"
        self.write_raw_activation(f"{hexof('activation')}.json", json.dumps(tampered).encode("utf-8"))
        after = self.observe()
        self.assertFalse(after["activation"]["receipts"][0]["seal_valid"])

    def test_a_selected_payload_and_a_different_activated_version_are_both_reported(self) -> None:
        self.write_candidate("0.7.3")
        self.write_acquisition()
        self.write_activation(requested_version="0.6.3", resolved_version="0.6.3")

        readiness = self.observe()

        self.assertEqual(readiness["selection"]["versions"], ["0.7.3"])
        self.assertEqual(readiness["activation"]["activated_versions"], ["0.6.3"])
        self.assertEqual(readiness["reconciliation"]["version_delta"], "different")
        # A version delta is a dimension VALUE, not a defect: the closed v1 finding vocabulary has
        # no code for it, and this reader does not borrow a defect code to state one.
        self.assertEqual(reader.readiness_findings(readiness), [])
        # Positive control: the identical delta beside an activation that matches no acquired
        # payload IS nameable, and the same harness names it.
        self.write_activation(
            name=f"{hexof('other')}.json", archive_sha256=hexof("another-archive")
        )
        self.assertIn("state-ambiguous", self.codes(reader.readiness_findings(self.observe())))

    def test_a_requested_version_never_becomes_an_activated_version(self) -> None:
        # The family refuses `version_source: request` outright, so this is proven against a stub
        # validator: what is under test is that THIS reader reads back only a proven source.
        body = activation_body(
            version_source="request", requested_version="9.9.9", resolved_version="9.9.9"
        )
        stub = SimpleNamespace(
            VERDICT_VALIDATED="validated",
            derive=lambda command, document, subject: {"verdict": "validated", "reasons": []},
        )
        observation = reader.observe_activation_receipt({"body": body}, stub, "activation-receipt://x")

        self.assertTrue(observation["seal_valid"])
        self.assertIsNone(observation["activated_version"])
        self.assertEqual(observation["requested_version"], "9.9.9")
        # Positive control: the same stub, the same body, one proven source, and the version lands.
        proven = reader.observe_activation_receipt(
            {"body": activation_body(version_source="adapter-readback", resolved_version="9.9.9")},
            stub,
            "activation-receipt://x",
        )
        self.assertEqual(proven["activated_version"], "9.9.9")

    def test_an_activation_whose_version_has_no_proven_source_is_named_ambiguous(self) -> None:
        stub = SimpleNamespace(
            VERDICT_VALIDATED="validated",
            derive=lambda command, document, subject: {"verdict": "validated", "reasons": []},
        )
        self.write_raw_activation(
            f"{hexof('activation')}.json",
            json.dumps({"body": activation_body(version_source="request")}).encode("utf-8"),
        )

        findings = self.findings(validator=stub)

        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(any("read it back" in finding["message"] for finding in findings))
        # Positive control: the proven source, same harness, no such finding.
        self.write_raw_activation(
            f"{hexof('activation')}.json",
            json.dumps({"body": activation_body()}).encode("utf-8"),
        )
        self.assertFalse(
            any("read it back" in finding["message"] for finding in self.findings(validator=stub))
        )

    # ---- a tampered receipt ---------------------------------------------------------------------

    def test_a_tampered_receipt_is_named_malformed_rather_than_crashing_the_reader(self) -> None:
        path = self.write_activation()
        clean = json.loads(path.read_text(encoding="utf-8"))
        # Positive control FIRST: these exact bytes validate, so every refusal below is the edit.
        self.assertTrue(self.observe()["activation"]["receipts"][0]["seal_valid"])

        for label, mutate in (
            ("body-field", lambda doc: doc["body"].update({"terminal_phase": "retired"})),
            ("record-seal", lambda doc: doc["body"].update({"record_sha256": "0" * 64})),
            ("content-digest", lambda doc: doc.update({"content_digest": "0" * 64})),
            ("receipt-kind", lambda doc: doc.update({"receipt_kind": "incident-recovery"})),
        ):
            with self.subTest(label=label):
                document = copy.deepcopy(clean)
                mutate(document)
                path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")

                readiness = self.observe()
                findings = reader.readiness_findings(readiness)

                self.assertFalse(readiness["activation"]["receipts"][0]["seal_valid"])
                self.assertEqual(readiness["activation"]["receipts"][0]["state"], "invalid")
                self.assertEqual(readiness["activation"]["state"], "unreadable")
                self.assertIn("state-malformed", self.codes(findings))
                self.assertTrue(readiness["activation"]["receipts"][0]["reason"])
                # Nothing is read out of a document that did not validate.
                self.assertIsNone(readiness["activation"]["receipts"][0]["activated_version"])
                self.assertEqual(readiness["activation"]["activated_versions"], [])

        completed = self.run_reader("doctor", "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        report = json.loads(completed.stdout)
        self.assertIn(
            "state-malformed",
            {finding["code"] for finding in report["findings"] if finding["component"] == "checkout"},
        )

    def test_an_unreadable_or_symlinked_plane_document_is_named_and_never_followed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        self.write_activation()
        # Positive control: the harness reaches `validated` for a physical document.
        self.assertEqual(self.observe()["activation"]["receipts"][0]["state"], "validated")

        elsewhere = self.root / "elsewhere.json"
        elsewhere.write_text(
            (self.activation / f"{hexof('activation')}.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        linked = self.activation / f"{hexof('linked')}.json"
        linked.symlink_to(elsewhere)

        findings = self.findings()

        self.assertIn("state-symlinked", self.codes(findings))
        self.assertTrue(any("instead of following" in finding["message"] for finding in findings))
        linked.unlink()

        for label, content in (
            ("not-utf8", b'{"body": "\xff\xfe"}'),
            ("duplicate-key", b'{"body":{},"body":{}}'),
            ("non-finite", b'{"body": {"resolved_version": 1e400}}'),
            ("not-an-object", b"[]"),
            ("oversize", b'{"padding": "' + b"a" * (reader.MAX_PLANE_DOCUMENT_BYTES + 8) + b'"}'),
        ):
            with self.subTest(label=label):
                path = self.write_raw_activation(f"{hexof(label)}.json", content)

                findings = self.findings()

                self.assertIn("state-unreadable", self.codes(findings))
                self.assertTrue(readable_reason(findings), findings)
                path.unlink()
        # Positive control after the loop: with only the physical receipt left, neither code fires.
        final = self.codes(self.findings())
        self.assertNotIn("state-unreadable", final)
        self.assertNotIn("state-symlinked", final)

    # ---- interrupted transitions ------------------------------------------------------------------

    def test_an_interrupted_transition_is_visible_beside_the_ownership_planes_own_pending_work(
        self,
    ) -> None:
        self.write_candidate()
        self.write_acquisition()
        self.write_activation(effect_state="partial", terminal_phase="activated-partial")

        readiness = self.observe()
        findings = reader.readiness_findings(readiness)

        self.assertTrue(readiness["activation"]["receipts"][0]["interrupted"])
        self.assertEqual(len(readiness["activation"]["interrupted"]), 1)
        self.assertIn("pending-recovery", self.codes(findings))
        self.assertTrue(any("did not complete" in finding["message"] for finding in findings))

        # The OWNERSHIP plane keeps its own outstanding transition, and the two are reported side by
        # side rather than one dimension shadowing the other. That second plane used to be
        # operator-tools; gh #10 phase 4 deleted it, and the bundle journal is now the one substrate
        # that can carry an armed slot, so the claim is unchanged and its subject moved.
        self.write_bundle_pending()
        completed = self.run_reader("doctor", "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        components = {
            (finding["component"], finding["code"])
            for finding in report["findings"]
            if finding["code"] == "pending-recovery"
        }
        self.assertIn(("checkout", "pending-recovery"), components)
        self.assertIn(("bundle", "pending-recovery"), components)
        # And a leftover store from the DELETED plane is a third, independent dimension: it is named
        # rather than resumed, so it must appear beside both of the above without shadowing either and
        # without borrowing `pending-recovery` for something nothing can recover.
        (self.state / reader.RETIRED_OPERATOR_TOOLS_STORE).mkdir(parents=True, exist_ok=True)
        retired = json.loads(self.run_reader("doctor", "--json").stdout)["findings"]
        retired_pairs = {(finding["component"], finding["code"]) for finding in retired}
        self.assertIn(("operator-tools", "foreign-state"), retired_pairs)
        self.assertIn(("checkout", "pending-recovery"), retired_pairs)
        self.assertIn(("bundle", "pending-recovery"), retired_pairs)
        self.assertNotIn(("operator-tools", "pending-recovery"), retired_pairs)
        # And a FOURTH dimension, from the other deleted plane (agentic-sdlc-7a2b, W5): the per-file
        # workflows enabler's receipt store. It is named under its own component beside the first
        # three, so a host carrying both leftovers reads two remedies rather than one.
        self.assertNotIn(("claude-workflows", "foreign-state"), retired_pairs)
        (self.state / reader.ORPHANED_WORKFLOW_RECEIPTS_STORE).mkdir(parents=True, exist_ok=True)
        orphaned = json.loads(self.run_reader("doctor", "--json").stdout)["findings"]
        orphaned_pairs = {(finding["component"], finding["code"]) for finding in orphaned}
        self.assertIn(("claude-workflows", "foreign-state"), orphaned_pairs)
        self.assertIn(("operator-tools", "foreign-state"), orphaned_pairs)
        self.assertNotIn(("claude-workflows", "pending-recovery"), orphaned_pairs)
        # Positive control: a completed transition in the same plane produces no checkout pending
        # finding, so the assertion above is the recorded effect state and not a constant.
        self.write_activation(effect_state="complete", terminal_phase="activated")
        self.assertNotIn("pending-recovery", self.codes(reader.readiness_findings(self.observe())))

    def test_more_than_one_activated_version_is_named_ambiguous(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        self.write_activation()
        self.write_activation(
            name=f"{hexof('second')}.json", requested_version="0.6.3", resolved_version="0.6.3"
        )

        readiness = self.observe()
        findings = reader.readiness_findings(readiness)

        self.assertEqual(readiness["activation"]["activated_versions"], ["0.6.3", "0.7.3"])
        self.assertEqual(readiness["activation"]["state"], "ambiguous")
        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(any("more than one activated version" in item["message"] for item in findings))
        # Positive control: one receipt, one version, no ambiguity from the same harness.
        (self.activation / f"{hexof('second')}.json").unlink()
        self.assertNotIn(
            "state-ambiguous", self.codes(reader.readiness_findings(self.observe()))
        )

    def test_a_recorded_unknown_is_consulted_instead_of_the_recorded_fact(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        # A stub validator, because the family itself refuses a fact and an unknown about the same
        # observation. What is under test is that this reader consults the recorded UNKNOWN and does
        # not reconcile a digest the receipt already said it never observed.
        stub = SimpleNamespace(
            VERDICT_VALIDATED="validated",
            derive=lambda command, document, subject: {"verdict": "validated", "reasons": []},
        )
        unknown_body = activation_body(
            unknowns=[
                {
                    "detail": "the archive was gone before it could be digested",
                    "observation": "archive-digest",
                    "subject": "archive_sha256",
                }
            ]
        )
        self.write_raw_activation(
            f"{hexof('activation')}.json", json.dumps({"body": unknown_body}).encode("utf-8")
        )

        readiness = self.observe(validator=stub)
        findings = reader.readiness_findings(readiness)

        self.assertEqual(readiness["activation"]["receipts"][0]["unknown_subjects"], ["archive_sha256"])
        self.assertEqual(len(readiness["reconciliation"]["unknown"]), 1)
        self.assertEqual(readiness["reconciliation"]["matched"], [])
        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(any("no observed payload digest" in item["message"] for item in findings))
        # Positive control: the identical digest with no recorded unknown DOES reconcile, so the
        # refusal above is the unknown and not the digest.
        self.write_raw_activation(
            f"{hexof('activation')}.json", json.dumps({"body": activation_body()}).encode("utf-8")
        )
        control = self.observe(validator=stub)
        self.assertEqual(len(control["reconciliation"]["matched"]), 1)
        self.assertEqual(control["reconciliation"]["unknown"], [])

    def test_an_unacquired_or_unreadable_payload_never_becomes_a_selected_version(self) -> None:
        self.write_candidate()
        # An acquisition record whose terminal phase never reached the acquired form.
        self.write_acquisition(terminal_phase="published")

        readiness = self.observe()

        self.assertFalse(readiness["selection"]["payloads"][0]["acquired"])
        self.assertEqual(readiness["selection"]["payloads"][0]["payload_version"], "0.7.3")
        self.assertEqual(readiness["reconciliation"]["matched"], [])
        # Positive control: the acquired terminal phase reconciles in the same harness.
        self.write_acquisition()
        self.write_activation()
        self.assertEqual(len(self.observe()["reconciliation"]["matched"]), 1)

    def test_a_missing_candidate_manifest_is_a_named_unknown_rather_than_a_guessed_version(self) -> None:
        self.write_acquisition()  # no candidate root written at all

        readiness = self.observe()
        payload = readiness["selection"]["payloads"][0]

        self.assertIsNone(payload["payload_version"])
        self.assertIn("candidate manifest", payload["payload_version_reason"] or "")
        self.assertEqual(readiness["selection"]["versions"], [])
        self.assertEqual(reader.readiness_findings(readiness), [])
        # Positive control: with the manifest present the same harness reads the version.
        self.write_candidate("0.7.3")
        self.assertEqual(self.observe()["selection"]["versions"], ["0.7.3"])

    # ---- declared incompatibility ------------------------------------------------------------------

    def test_a_declared_incompatible_host_version_surfaces_as_an_unsupported_finding(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["compatibility"]["known_incompatible_host_versions"] = [
            incompatible_record("2.1.199"),
            incompatible_record("2.1.200"),
        ]

        findings = self.findings(contract=contract, observed_host_version="2.1.199")
        readiness = self.observe(contract=contract, observed_host_version="2.1.199")

        self.assertEqual(readiness["compatibility"]["state"], "declared-incompatible")
        self.assertEqual(readiness["compatibility"]["host"], "claude-code")
        self.assertEqual(readiness["compatibility"]["minimum_host_version"], "2.1.154")
        self.assertEqual(readiness["compatibility"]["declared_incompatible"], ["2.1.199", "2.1.200"])
        self.assertIn("state-unsupported", self.codes(findings))
        self.assertTrue(any("2.1.199" in finding["message"] for finding in findings))
        # Positive control: a host version that is not on the declared list, same contract, same
        # harness, no finding -- so the finding above is the declaration and not the presence of a
        # version.
        clean = self.observe(contract=contract, observed_host_version="2.1.233")
        self.assertEqual(clean["compatibility"]["state"], "not-declared-incompatible")
        self.assertEqual(reader.readiness_findings(clean), [])

    def test_an_incompatibility_declared_about_another_host_never_refuses_this_one(self) -> None:
        """The per-plane half of the fix, and the direction that made it necessary.

        Two hosts' version spaces are unrelated, and the mutating verbs already filter a declared
        incompatibility by the host it names. This reader reports the CORE row, so a record about
        `codex-cli` must leave it `not-declared-incompatible` even when the observed version string is
        character-for-character the declared one. Before the filter existed the whole verdict was
        unreachable, so this direction could not have been observed either way.
        """
        foreign = incompatible_contract(self.contract, host="codex-cli")
        observed = self.observe(contract=foreign, observed_host_version="2.1.199")

        self.assertEqual(observed["compatibility"]["state"], "not-declared-incompatible")
        self.assertEqual(observed["compatibility"]["declared_incompatible"], [])
        self.assertEqual(reader.readiness_findings(observed), [])
        # Positive control: the SAME version, the SAME harness, the record re-declared about the core
        # host -- so the pass above is the host axis and not a fixture that declares nothing.
        native = self.observe(contract=incompatible_contract(self.contract), observed_host_version="2.1.199")
        self.assertEqual(native["compatibility"]["state"], "declared-incompatible")
        self.assertEqual(native["compatibility"]["declared_incompatible"], ["2.1.199"])

    def test_a_malformed_declared_incompatibility_is_skipped_rather_than_guessed_at(self) -> None:
        """A record the contract's own validators refuse is not evidence for a reader verdict either.

        The mutating verbs refuse a non-`{host, reason, version}` entry BY NAME at their own boundary.
        A read-only verb has no such boundary to refuse from, so it reports what the contract
        DECLARED, which for an unreadable entry is nothing -- reclassifying it would state a verdict
        the contract never made.
        """
        malformed = copy.deepcopy(self.contract)
        malformed["compatibility"]["known_incompatible_host_versions"] = [
            "2.1.199",
            {"version": "2.1.199"},
            {"host": "claude-code", "reason": "no version key", "extra": "2.1.199"},
        ]
        observed = self.observe(contract=malformed, observed_host_version="2.1.199")

        self.assertEqual(observed["compatibility"]["state"], "not-declared-incompatible")
        self.assertEqual(observed["compatibility"]["declared_incompatible"], [])
        # Positive control: one well-formed record among the malformed ones IS read, so the empty
        # list above is the shape filter and not a reader that stopped looking.
        mixed = copy.deepcopy(malformed)
        mixed["compatibility"]["known_incompatible_host_versions"].append(incompatible_record("2.1.199"))
        self.assertEqual(
            self.observe(contract=mixed, observed_host_version="2.1.199")["compatibility"]["state"],
            "declared-incompatible",
        )

    def test_an_unobservable_host_version_is_unknown_with_a_reason_and_not_a_failure(self) -> None:
        readiness = self.observe()

        self.assertEqual(readiness["compatibility"]["state"], "unknown")
        self.assertIsNone(readiness["compatibility"]["observed_host_version"])
        self.assertIn("executing the host", readiness["compatibility"]["reason"])
        self.assertEqual(readiness["compatibility"]["declared_incompatible"], [])
        self.assertEqual(reader.readiness_findings(readiness), [])
        # A supplied-but-unusable value is a DIFFERENT state from a value never supplied.
        supplied = self.observe(observed_host_version="2.1.\x00154")
        self.assertEqual(supplied["compatibility"]["state"], "unknown")
        self.assertIn("not an admissible version string", supplied["compatibility"]["reason"])
        self.assertNotEqual(supplied["compatibility"]["reason"], readiness["compatibility"]["reason"])
        # Positive control: an admissible value reaches a decided state.
        self.assertEqual(
            self.observe(observed_host_version="2.1.233")["compatibility"]["state"],
            "not-declared-incompatible",
        )

    def test_a_contract_without_a_compatibility_surface_is_unknown_rather_than_admitted(self) -> None:
        stripped = copy.deepcopy(self.contract)
        stripped.pop("compatibility")

        readiness = self.observe(contract=stripped, observed_host_version="2.1.199")

        self.assertEqual(readiness["compatibility"]["state"], "unknown")
        self.assertIn("no compatibility surface", readiness["compatibility"]["reason"])
        self.assertEqual(reader.readiness_findings(readiness), [])
        # Positive control: the tracked contract does declare one, so the branch above is the edit.
        self.assertNotEqual(
            self.observe(observed_host_version="2.1.199")["compatibility"]["state"], "unknown"
        )

    # ---- the validator is optional -----------------------------------------------------------------

    def test_an_absent_or_drifted_seal_validator_declines_instead_of_guessing_validity(self) -> None:
        self.write_activation()
        with tempfile.TemporaryDirectory() as temp:
            scripts = Path(temp) / "scripts"
            scripts.mkdir()
            reader_copy = scripts / "ccodex_sdlc.py"
            reader_copy.write_text("# stub\n", encoding="utf-8")
            (scripts / "ccodex_sdlc_readonly.py").write_text(
                GUARD_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
            )

            absent, absent_reason = reader.load_activation_validator(reader_copy, guard)
            self.assertIsNone(absent)
            self.assertIn("absent from this distribution", absent_reason or "")

            drifted = scripts / "distribution_activation_receipt.py"
            source = VALIDATOR_SCRIPT.read_text(encoding="utf-8")
            drifted.write_text(
                source.replace(
                    'EFFECT_STATES = ("complete", "none", "partial", "unknown")',
                    'EFFECT_STATES = ("complete", "none", "partial", "unknown", "widened")',
                ),
                encoding="utf-8",
            )
            module, reason = reader.load_activation_validator(reader_copy, guard)
            self.assertIsNone(module)
            self.assertIn("EFFECT_STATES vocabulary drifted", reason or "")

            # Positive control: the unmodified module at the same path loads and reports no reason.
            drifted.write_text(source, encoding="utf-8")
            loaded, no_reason = reader.load_activation_validator(reader_copy, guard)
            self.assertIsNotNone(loaded)
            self.assertIsNone(no_reason)

        unassessed = self.observe(
            validator=None, validator_reason="the seal validator is absent from this distribution"
        )
        findings = reader.readiness_findings(unassessed)
        self.assertEqual(unassessed["activation"]["receipts"][0]["state"], "unassessed")
        self.assertIsNone(unassessed["activation"]["receipts"][0]["seal_valid"])
        self.assertEqual(unassessed["activation"]["activated_versions"], [])
        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(any("was not assessed" in finding["message"] for finding in findings))

    def test_a_validator_that_raises_is_an_unassessed_receipt_rather_than_an_exit_one(self) -> None:
        def explode(command: str, document: dict[str, Any], subject: str) -> dict[str, Any]:
            raise RuntimeError("validator blew up")

        stub = SimpleNamespace(VERDICT_VALIDATED="validated", derive=explode)
        self.write_activation()

        readiness = self.observe(validator=stub)

        self.assertEqual(readiness["activation"]["receipts"][0]["state"], "unassessed")
        self.assertIn("validator blew up", readiness["activation"]["receipts"][0]["reason"] or "")
        self.assertIn("state-ambiguous", self.codes(reader.readiness_findings(readiness)))
        # Positive control: the real validator over the same document reaches a verdict.
        self.assertEqual(self.observe()["activation"]["receipts"][0]["state"], "validated")

    # ---- rendering safety ---------------------------------------------------------------------------

    def test_no_artifact_string_can_forge_a_line_of_this_commands_output(self) -> None:
        forged = "\nfinding [checkout] ccodex sdlc activation completed\n"
        # A sealed receipt whose scope was then edited to carry the injection: the validator refuses
        # the scope BY NAME, which is the path on which an artifact string reaches a rendered line.
        tampered = sealed_activation_receipt()
        tampered["body"]["scope"] = {"agent": f"claude{forged}", "kind": "user"}
        self.write_raw_activation(
            f"{hexof('activation')}.json", json.dumps(tampered, sort_keys=True).encode("utf-8")
        )
        # And a plane document whose NAME carries the same injection; `/` is left out of the name
        # only because it would name a directory rather than a file.
        self.write_raw_activation(f"receipt{forged}.json", b"{}")

        findings = self.findings()
        self.assertTrue(findings)
        for finding in findings:
            with self.subTest(path=finding["path"]):
                self.assertNotIn("\n", finding["message"])
                self.assertNotIn("\r", finding["message"])
                self.assertNotIn("\n", finding["path"])
                self.assertLessEqual(len(finding["message"]), reader.MAX_FINDING_MESSAGE_CHARS + 12)
        completed = self.run_reader("doctor")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(forged, completed.stdout)
        for line in completed.stdout.splitlines():
            self.assertFalse(
                line.startswith("finding [checkout] ccodex sdlc activation completed"),
                f"an artifact string forged an output line: {line!r}",
            )
        # The reason that WOULD have carried the injection is length-bounded, and the bound says so
        # rather than dropping the tail silently.
        self.assertTrue(any("(truncated)" in finding["message"] for finding in findings))
        # Positive control: the escaping is escaping, not a refusal to render. The same renderer
        # keeps the injected text INSIDE one escaped token, so its escaped form survives and its raw
        # form never appears.
        rendered = reader.bounded_message(f"scope {forged}")
        self.assertIn("ccodex sdlc activation completed", rendered)
        self.assertIn("\\n", rendered)
        self.assertNotIn("\n", rendered)

    def test_escape_display_agrees_with_the_receipt_familys_own_rendering_rule(self) -> None:
        for value in (
            "ordinary text",
            "0.7.3",
            "line\nbreak",
            "carriage\rreturn",
            "tab\tstop",
            "back\\slash",
            "null\x00byte",
            "escape\x1b[2Jclear",
            "delete\x7fchar",
            "wide é中",
        ):
            with self.subTest(value=value):
                self.assertEqual(reader.escape_display(value), receipts.escape_display(value))
        # Positive control: the comparison can fail, so the equalities above are agreement and not
        # two functions that both return their input.
        self.assertNotEqual(reader.escape_display("a\nb"), "a\nb")
        self.assertEqual(reader.escape_display("plain"), "plain")

    def test_an_unrecognised_document_name_is_located_by_digest_and_never_echoed(self) -> None:
        secret = "sk" + "-ant-api-plane-name-canary"
        self.write_raw_activation(f"{secret}.json", b"{}")

        findings = self.findings()

        self.assertTrue(findings)
        for finding in findings:
            self.assertNotIn(secret, finding["path"])
            self.assertNotIn(secret, finding["message"])
        self.assertTrue(findings[0]["path"].startswith("activation-receipt://unrecognised-"))
        completed = self.run_reader("doctor", "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(secret, completed.stdout)
        # Positive control: a well-formed name IS carried, so the digest form above is the name
        # shape and not a blanket refusal to locate anything.
        self.assertEqual(
            reader.plane_locator("activation-receipt", f"{hexof('activation')}.json"),
            f"activation-receipt://{hexof('activation')}",
        )

    # ---- the report stays inside its pinned policy ---------------------------------------------------

    def test_every_readiness_finding_stays_inside_the_pinned_v1_report_vocabulary(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        codes = set(policy["vocabularies"]["finding_codes"])
        components = set(policy["vocabularies"]["finding_components"])
        self.write_candidate()
        self.write_acquisition()
        self.write_activation(effect_state="partial", terminal_phase="activated-partial")
        self.write_raw_activation(f"{hexof('broken')}.json", b"{}")

        findings = self.findings(
            contract=incompatible_contract(self.contract), observed_host_version="2.1.199"
        )

        self.assertTrue(len(findings) >= 3, findings)
        for finding in findings:
            with self.subTest(code=finding["code"]):
                self.assertEqual(set(finding), set(policy["field_vocabularies"]["finding"]))
                self.assertIn(finding["code"], codes)
                self.assertIn(finding["component"], components)
                reader.validate_finding(
                    finding, policy["field_vocabularies"], policy["vocabularies"]
                )
        # Positive control: the same checker rejects a code outside the vocabulary, so the loop
        # above is a check and not a no-op.
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_finding(
                {**findings[0], "code": "activation-version-delta"},
                policy["field_vocabularies"],
                policy["vocabularies"],
            )

    def test_the_human_render_carries_every_readiness_finding_the_json_report_carries(self) -> None:
        self.write_activation(effect_state="partial", terminal_phase="activated-partial")

        machine = self.run_reader("doctor", "--json")
        human = self.run_reader("doctor")

        self.assertEqual(machine.returncode, 0, machine.stderr)
        self.assertEqual(human.returncode, 0, human.stderr)
        report = json.loads(machine.stdout)
        checkout_findings = [
            finding for finding in report["findings"] if finding["component"] == "checkout"
        ]
        self.assertTrue(checkout_findings)
        for finding in checkout_findings:
            self.assertIn(finding["message"], human.stdout)
            self.assertIn(finding["path"], human.stdout)

    # ---- read-only ------------------------------------------------------------------------------------

    def test_the_whole_run_touches_nothing_under_the_injected_home_or_state_root(self) -> None:
        self.write_candidate()
        acquisition = self.write_acquisition()
        self.write_activation(effect_state="partial", terminal_phase="activated-partial")
        self.write_raw_activation(f"{hexof('broken')}.json", b"{}")
        sealed_before = acquisition.read_bytes()
        before = inventory(self.home, self.state, self.candidate.parent)

        for verb, suffix in READER_VERBS:
            for extra in ((), ("--json",)):
                completed = self.run_reader(verb, *suffix, *extra)
                self.assertEqual(completed.returncode, 0, completed.stderr)

        after = inventory(self.home, self.state, self.candidate.parent)
        self.assertEqual(before, after)
        # The sealed acquisition receipt is never mutated (agentic-sdlc-0cce), byte for byte.
        self.assertEqual(acquisition.read_bytes(), sealed_before)
        self.assertFalse((self.state / "agentic-sdlc" / "activation" / "lock").exists())
        # Positive control: the same inventory function DOES notice a change, so the equality above
        # is a measurement and not a comparison of two empty dictionaries.
        self.assertTrue(before)
        (self.state / "agentic-sdlc" / "activation" / "receipts" / f"{hexof('probe')}.json").write_bytes(b"{}")
        self.assertNotEqual(before, inventory(self.home, self.state, self.candidate.parent))

    # ---- the front-door grammar pins -------------------------------------------------------------------

    def test_the_reader_grammar_and_usage_surface_are_pinned_byte_for_byte(self) -> None:
        """The reader's whole operator surface, held as literals rather than described.

        RE-ANCHORED, not weakened, by agentic-sdlc-7a2b W3a: the pin used to hold the f894 `ccodex
        sdlc <verb>` surface, and the ratified front door moved every verb to the top level. The
        SUBJECT is unchanged -- one byte-for-byte pin of `usage()` plus the whole admitted/refused
        grammar -- so what moved is the pinned text and the shape of an `Invocation`, and the assertions
        stayed exact.
        """
        rendered = reader.usage()
        self.assertEqual(rendered.splitlines()[: len(READER_USAGE_LINES)], list(READER_USAGE_LINES))
        self.assertEqual(rendered, EXPECTED_USAGE)
        for arguments, expected in READER_FORMS:
            with self.subTest(arguments=arguments):
                self.assertEqual(reader.parse_command(list(arguments)), expected)
        for invalid in (
            # A RETIRED verb is not a verb: `inspect` is gone from `READER_VERBS`, so the reader itself
            # no longer knows the name and the dispatcher refuses the old `ccodex sdlc inspect` spelling
            # with both replacements named.
            ("inspect",),
            ("inspect", "--dry-run"),
            ("doctor", "--dry-run"),
            ("recover",),
            # Each selector verb needs BOTH selectors: neither has a default and neither has a
            # wildcard, so a bare verb, a lone `--scope`, and a lone `--agent` are three refusals.
            ("install",),
            ("status",),
            ("update",),
            ("uninstall",),
            ("install", "--scope", "user"),
            ("install", "--agent", "claude"),
            ("update", "--json"),
            # `--host` is GONE from the operator grammar -- it survives only as the per-verb modules'
            # own ABI, which no operator types -- and an unadmitted agent is refused by name.
            ("install", "--host", "claude"),
            ("install", "--scope", "user", "--agent", "gemini"),
            ("install", "--scope", "everywhere", "--agent", "claude"),
            # A value flag spelled with `=` is one argument where the grammar takes two.
            ("install", "--scope=user", "--agent", "claude"),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(reader.UsageError):
                    reader.parse_command(list(invalid))
        self.assertEqual(sorted(reader.LIFECYCLE_VERBS), ["install", "uninstall", "update"])
        self.assertEqual(reader.READER_VERBS, ("status", "doctor", "recover"))
        self.assertEqual(reader.SELECTOR_VERBS, ("install", "status", "update", "uninstall"))
        self.assertEqual(reader.LIFECYCLE_AGENTS, ("claude", "codex"))
        self.assertEqual(reader.LIFECYCLE_SCOPES, ("user", "project"))
        # The one asymmetry this file must NOT "fix": the operator flag and the module ABI are
        # different strings on purpose, and both are pinned so neither can drift into the other.
        self.assertEqual(reader.AGENT_FLAG, "--agent")
        self.assertEqual(reader.FORWARDED_AGENT_FLAG, "--host")

    def test_a_mutating_verb_still_refuses_by_name_with_a_readiness_plane_present(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        self.write_activation()
        before = inventory(self.home, self.state)

        for vector in (
            ("install", "--scope", "user", "--agent", "claude"),
            ("install", "--scope", "user", "--agent", "codex"),
            ("update", "--scope", "user", "--agent", "claude"),
            ("update", "--scope", "user", "--agent", "codex"),
            ("uninstall", "--scope", "user", "--agent", "claude"),
            ("uninstall", "--scope", "user", "--agent", "codex"),
        ):
            with self.subTest(verb=vector[0], agent=vector[4]):
                completed = self.run_reader(*vector)
                self.assertEqual(completed.returncode, 3, completed.stderr)
                # All three per-verb modules ship, so each refuses pre-effect in its OWN name; the
                # loader's absence message appearing here would mean dispatch never reached one.
                # THE PREFIX IS THE MODULE'S OWN AND THE FAMILY IS SPLIT: `install` was renamed to
                # the surviving top-level invocation in W3b, while `update` and `uninstall` still print
                # `ccodex sdlc <verb>` because they are other waves' files. The map is what proves the
                # MODULE answered rather than the reader -- neither reader refusal carries a prefix
                # with a trailing verb -- and a rename lands here as one line.
                self.assertIn(MODULE_OWN_PREFIX[vector[0]], completed.stderr)
                self.assertNotIn("is unavailable in this distribution", completed.stderr)
                self.assertEqual(completed.stdout, "")
                self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(before, inventory(self.home, self.state))
        # Positive control: a reader verb over the same planes succeeds, so the exit-3s above are
        # the mutating verbs' own refusals and not a broken invocation.
        control = self.run_reader("doctor", "--json")
        self.assertEqual(control.returncode, 0, control.stderr)


@WINDOWS_SKIP
@WINDOWS_SKIP
class ProjectPointerRootTest(ReadinessHarness):
    """The two states a project pointer's ROOT can be in, and the rows a reader owes for each.

    A pointer for a vanished repository is the ADR-0022 pathology this program exists to delete -- an
    evidence record with no reader is a write-only artifact -- so `doctor` naming it is half of the exit
    (§2.2 items 6-7); the records-only uninstall is the other half and lives in its own suite.

    THE JUDGE IS INJECTED, and every test here supplies the real one built over the shipped substrate,
    because a stub would prove this suite's idea of a git project rather than the product's. One test
    supplies none, which is the honest third state: a reader that could not look reports `unassessed` and
    emits no finding at all.
    """

    def project_pointer(self, root: Path, *, agent: str = "claude", **overrides: Any) -> Path:
        """One project pointer at the keyed path the shipped writers derive, holding a sealed receipt.

        The filename's key is `sha256(root)[:16]`, spelled out here rather than read back from the
        writer: the filename IS the admission authority, so a fixture that asked the writer where it
        wrote would agree with any path it chose.
        """
        key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        directory = self.state / "agentic-sdlc" / "activation" / "active" / agent
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"project-{key}.json"
        receipt = sealed_activation_receipt(
            receipt_id=overrides.pop("receipt_id", f"activation-project-{key[:8]}"),
            scope={"agent": agent, "kind": "project", "root": str(root)},
            **overrides,
        )
        path.write_bytes(receipts.canonical_bytes(receipt))
        return path

    def judge(self) -> Any:
        """The product's own root-state predicate, over the product's own shared `.git` reader."""
        return reader.project_root_judge(bundle)

    def rows(self, **kwargs: Any) -> list[dict[str, Any]]:
        return reader.observe_activation(
            self.activation, receipts, None, project_root_state=kwargs.pop("root_state", self.judge())
        )["project_pointers"]

    def findings_for(self, root_state: Any) -> list[dict[str, str]]:
        observation = reader.observe_readiness(
            self.contract,
            acquisition_receipts=self.acquisition,
            activation_receipts=self.activation,
            validator=receipts,
            validator_reason=None,
            project_root_state=root_state,
        )
        return reader.readiness_findings(observation)

    def live_repository(self, name: str) -> Path:
        """A root the shared reader admits: one regular one-line HEAD plus `objects/` and `refs/`."""
        root = self.root / name
        (root / ".git" / "objects").mkdir(parents=True)
        (root / ".git" / "refs").mkdir()
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        return root

    def test_a_live_project_root_is_observed_and_says_nothing(self) -> None:
        root = self.live_repository("live-project")
        self.project_pointer(root)

        rows = self.rows()

        self.assertEqual(1, len(rows), rows)
        self.assertEqual(reader.ROOT_LIVE, rows[0]["state"])
        self.assertEqual(str(root), rows[0]["root"])
        # A healthy plane produces NO row in the report: a finding for it would make every activated
        # repository read as a defect.
        self.assertEqual([], [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES])

    def test_a_pointer_whose_root_no_longer_exists_is_reported_as_an_orphaned_root(self) -> None:
        root = self.live_repository("moved-away")
        self.project_pointer(root)
        shutil.move(str(root), str(self.root / "somewhere-else"))

        rows = self.rows()
        findings = [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES]

        self.assertEqual(reader.ROOT_ABSENT, rows[0]["state"])
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("orphaned-root", findings[0]["code"])
        self.assertIn("no longer exists", findings[0]["message"])
        # The remedy is the records-only retirement, named in the finding an operator will read.
        self.assertIn("uninstall --scope project", findings[0]["message"])
        # POSITIVE CONTROL: moving it back makes the same reader say nothing.
        shutil.move(str(self.root / "somewhere-else"), str(root))
        self.assertEqual([], [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES])

    def test_a_pointer_whose_root_stopped_being_a_git_project_is_reported_as_outliving_it(self) -> None:
        root = self.live_repository("de-gitted")
        self.project_pointer(root)
        shutil.rmtree(root / ".git")

        rows = self.rows()
        findings = [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES]

        self.assertEqual(reader.ROOT_NOT_A_PROJECT, rows[0]["state"])
        self.assertEqual(1, len(findings), findings)
        self.assertEqual("pointer-outlived-root", findings[0]["code"])
        self.assertIn("outlived its repository", findings[0]["message"])
        # BOTH REMEDIES, because this verb refuses to choose between them.
        self.assertIn("restore", findings[0]["message"])
        self.assertIn("remove the directory entirely", findings[0]["message"])
        # POSITIVE CONTROL: the two states are DISTINCT, not one refusal wearing two names -- the same
        # fixture with the root deleted outright reports the other code.
        shutil.rmtree(root)
        recoded = [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES]
        self.assertEqual(["orphaned-root"], [f["code"] for f in recoded])

    def test_two_orphaned_roots_carry_distinct_locators_so_neither_report_row_hides_the_other(self) -> None:
        """`make_report` sorts findings by (component, path, code, message): one shared locator would
        order two orphans by their prose, and the pointer's own key is what keeps them apart."""
        for name in ("first", "second"):
            root = self.live_repository(name)
            self.project_pointer(root)
            shutil.rmtree(root)

        findings = [f for f in self.findings_for(self.judge()) if f["code"] == "orphaned-root"]

        self.assertEqual(2, len(findings), findings)
        self.assertEqual(2, len({f["path"] for f in findings}), findings)
        for finding in findings:
            self.assertTrue(finding["path"].startswith("activation-plane://project-pointer"), finding)

    def test_a_reader_with_no_judge_reports_unassessed_and_emits_no_finding(self) -> None:
        """The honest third state: what could not be looked at is not reported as broken."""
        root = self.live_repository("unjudged")
        self.project_pointer(root)
        shutil.rmtree(root)

        rows = self.rows(root_state=None)

        self.assertEqual(reader.ROOT_UNASSESSED, rows[0]["state"])
        self.assertEqual([], [f for f in self.findings_for(None) if f["code"] in ORPHAN_CODES])
        # POSITIVE CONTROL: the same plane WITH a judge reports the orphan, so the silence above is the
        # absent judge and not an enumeration that found nothing.
        self.assertEqual(
            ["orphaned-root"],
            [f["code"] for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES],
        )

    def test_a_pointer_that_states_no_absolute_root_is_named_rather_than_guessed_at(self) -> None:
        root = self.live_repository("relative")
        path = self.project_pointer(root)
        document = json.loads(path.read_text(encoding="utf-8"))
        document["body"]["scope"]["root"] = "relative/path"
        path.write_text(json.dumps(document), encoding="utf-8")

        rows = self.rows()

        self.assertEqual(reader.ROOT_UNASSESSED, rows[0]["state"])
        self.assertIn("no absolute project root", rows[0]["reason"])
        self.assertEqual([], [f for f in self.findings_for(self.judge()) if f["code"] in ORPHAN_CODES])

    def test_the_user_pointer_is_not_a_project_pointer_and_is_never_enumerated_here(self) -> None:
        """The two pointer kinds are read by two observers, and the filename is what separates them."""
        self.write_pointer(sealed_activation_receipt())

        self.assertEqual([], self.rows())

    def test_both_new_codes_are_members_of_the_pinned_v1_report_vocabulary(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

        for code in ORPHAN_CODES:
            with self.subTest(code=code):
                self.assertIn(code, policy["vocabularies"]["finding_codes"])
        # Positive control: the same membership test rejects a code the policy does not carry, so the
        # loop above is a check rather than a no-op.
        self.assertNotIn("project-pointer-stranded", policy["vocabularies"]["finding_codes"])


class SupersededActivationHistoryTest(ReadinessHarness):
    """A RETAINED prior receipt is history, not an ambiguity (agentic-sdlc-7b2e).

    ``ccodex update`` retains the receipt it replaced under its own id on purpose: a kill between
    the two writes must leave a readable prior statement.  So a healthy updated plane holds two filed
    activation receipts, and a reader that counted every filed receipt as a current activation
    reported that retention as ``state-ambiguous`` naming both versions -- a defect this reader
    invented about a plane in its correct state.

    Two independent facts resolve it and NEITHER is guessed here: the pointer the writers maintain
    names the current receipt, and an update's own ``supersedes`` ancestor names the receipt it
    replaced.  Genuine ambiguity -- no usable pointer AND more than one non-superseded activation --
    still produces the finding, and every negative assertion below carries that positive control in
    the same test.
    """

    def test_the_relation_and_pointer_name_this_module_pins_are_the_shipped_ones(self) -> None:
        self.assertEqual(SUPERSEDES_RELATION, reader.SUPERSEDES_RELATION)
        self.assertEqual(
            ACTIVE_POINTER_SEGMENTS,
            (reader.ACTIVE_DIRECTORY, reader.DEFAULT_POINTER_AGENT, reader.USER_POINTER_NAME),
        )
        self.assertEqual(LEGACY_ACTIVE_POINTER_NAME, reader.LEGACY_ACTIVE_POINTER_NAME)
        self.assertIn(SUPERSEDES_RELATION, receipts.FAMILY_RELATIONS)
        # Positive control: the same comparison detects a rename, so the equalities are not vacuous.
        self.assertNotEqual(SUPERSEDES_RELATION, "replaces")

    def test_a_healthy_updated_plane_produces_no_ambiguity_finding(self) -> None:
        self.write_updated_plane()

        readiness = self.observe()
        activation = readiness["activation"]
        findings = reader.readiness_findings(readiness)

        self.assertEqual(["0.7.4"], activation["activated_versions"])
        self.assertEqual("observed", activation["state"])
        self.assertEqual("observed", activation["active_pointer"]["state"])
        self.assertEqual("matched", activation["active_pointer"]["correlation"])
        # Both documents are still READ -- retention is preserved evidence, not a hidden file.
        self.assertEqual(2, len(activation["receipts"]))
        self.assertTrue(self.receipt_for(activation, "activation-1")["superseded"])
        self.assertFalse(self.receipt_for(activation, "activation-1")["active"])
        self.assertFalse(self.receipt_for(activation, "activation-2")["superseded"])
        self.assertTrue(self.receipt_for(activation, "activation-2")["active"])
        self.assertEqual(
            [f"activation-receipt://{hexof('activation-1')}"], activation["superseded_activations"]
        )
        self.assertEqual(
            [f"activation-receipt://{hexof('activation-2')}"], activation["active_activations"]
        )
        self.assertNotIn("state-ambiguous", self.codes(findings))
        self.assertEqual([], findings)

        # POSITIVE CONTROL: the identical harness with two NON-superseded receipts and no pointer
        # still names the ambiguity, so the absence above is the supersession and not a dropped check.
        self.pointer.unlink()
        for path in sorted(self.activation.glob("*.json")):
            path.unlink()
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))
        self.file_activation(
            sealed_activation_receipt(
                receipt_id="activation-2", requested_version="0.6.3", resolved_version="0.6.3"
            )
        )
        control = reader.readiness_findings(self.observe())
        self.assertIn("state-ambiguous", self.codes(control))
        self.assertTrue(any("more than one activated version" in item["message"] for item in control))

    def test_the_pointer_alone_resolves_receipts_that_supersede_nothing(self) -> None:
        """The pointer is PREFERRED: it decides even where no ancestor says anything."""
        self.write_candidate()
        self.write_acquisition()
        new_archive = hexof("archive-b")
        self.write_payload(new_archive, "0.7.4")
        first = sealed_activation_receipt(receipt_id="activation-1")
        second = sealed_activation_receipt(
            receipt_id="activation-2",
            archive_sha256=new_archive,
            candidate_id=hexof(f"candidate-{new_archive}"),
            requested_version="0.7.4",
            resolved_version="0.7.4",
        )
        self.file_activation(first)
        self.file_activation(second)

        # POSITIVE CONTROL FIRST: with no pointer and no supersession this plane IS ambiguous.
        without = self.observe()
        self.assertEqual(["0.7.3", "0.7.4"], without["activation"]["activated_versions"])
        self.assertIn("state-ambiguous", self.codes(reader.readiness_findings(without)))

        self.write_pointer(second)
        readiness = self.observe()
        activation = readiness["activation"]

        self.assertEqual(["0.7.4"], activation["activated_versions"])
        self.assertEqual("matched", activation["active_pointer"]["correlation"])
        # Neither receipt is superseded: no ancestor says so, and the reader states only what it read.
        self.assertEqual([], activation["superseded_activations"])
        self.assertEqual(
            [f"activation-receipt://{hexof('activation-2')}"], activation["active_activations"]
        )
        self.assertNotIn("state-ambiguous", self.codes(reader.readiness_findings(readiness)))

    def test_only_a_validated_neighbour_can_retire_a_receipt(self) -> None:
        """An unvalidated document's ancestors are unchecked text and retire nothing."""
        self.write_candidate()
        self.write_acquisition()
        new_archive = hexof("archive-b")
        self.write_payload(new_archive, "0.7.4")
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))
        current = sealed_activation_receipt(
            receipt_id="activation-2",
            ancestors=superseding_ancestors("activation-1"),
            operation="update",
            archive_sha256=new_archive,
            candidate_id=hexof(f"candidate-{new_archive}"),
            requested_version="0.7.4",
            resolved_version="0.7.4",
        )
        current_path = self.file_activation(current)

        # POSITIVE CONTROL FIRST: while its seal holds, this neighbour DOES retire the prior receipt.
        sealed = self.observe()["activation"]
        self.assertTrue(self.receipt_for(sealed, "activation-1")["superseded"])

        tampered = copy.deepcopy(current)
        tampered["body"]["resolved_version"] = "9.9.9"
        current_path.write_bytes(receipts.canonical_bytes(tampered))
        # The pointer is not in play here: the supersession walk itself is what is under test.
        self.assertFalse(self.pointer.exists())

        readiness = self.observe()
        activation = readiness["activation"]
        findings = reader.readiness_findings(readiness)

        self.assertEqual("invalid", self.receipt_for(activation, "activation-2")["state"])
        self.assertEqual([], self.receipt_for(activation, "activation-2")["supersedes"])
        self.assertFalse(self.receipt_for(activation, "activation-1")["superseded"])
        self.assertEqual([], activation["superseded_activations"])
        self.assertIn("state-malformed", self.codes(findings))
        # The one surviving activation is the prior receipt, and nothing was read out of the broken
        # document -- not its version, and not the retirement it claimed.
        self.assertEqual(["0.7.3"], activation["activated_versions"])

    def test_the_pointer_wins_over_an_ancestor_that_claims_to_have_replaced_it(self) -> None:
        """The state a kill between the two writes leaves: a sealed successor the plane never activated.

        ``update`` files its receipt durably BEFORE it replaces the pointer, so an interruption in that
        window leaves a receipt whose ``supersedes`` ancestor names the receipt the plane still points
        at.  The pointer is the plane's own statement of what it owns, so it decides; the successor's
        claim stays visible rather than becoming a version this plane never activated.
        """
        self.write_candidate()
        self.write_acquisition()
        new_archive = hexof("archive-b")
        self.write_payload(new_archive, "0.7.4")
        prior = sealed_activation_receipt(receipt_id="activation-1")
        self.file_activation(prior)
        self.file_activation(
            sealed_activation_receipt(
                receipt_id="activation-2",
                ancestors=superseding_ancestors("activation-1"),
                operation="update",
                archive_sha256=new_archive,
                candidate_id=hexof(f"candidate-{new_archive}"),
                requested_version="0.7.4",
                resolved_version="0.7.4",
            )
        )
        # The pointer was never replaced, so it still carries the PRIOR receipt's bytes.
        self.write_pointer(prior)

        readiness = self.observe()
        activation = readiness["activation"]

        self.assertEqual(["0.7.3"], activation["activated_versions"])
        self.assertEqual("matched", activation["active_pointer"]["correlation"])
        self.assertTrue(self.receipt_for(activation, "activation-1")["active"])
        # Both facts are kept: another receipt DOES claim to have replaced this one.
        self.assertTrue(self.receipt_for(activation, "activation-1")["superseded"])
        self.assertFalse(self.receipt_for(activation, "activation-2")["active"])
        self.assertNotIn("state-ambiguous", self.codes(reader.readiness_findings(readiness)))
        # Positive control: replacing the pointer with the successor's bytes -- the write the killed
        # update never reached -- moves the plane's statement to it, so the pointer is what decided.
        self.write_pointer(
            json.loads((self.activation / f"{hexof('activation-2')}.json").read_text(encoding="utf-8"))
        )
        moved = self.observe()["activation"]
        self.assertEqual(["0.7.4"], moved["activated_versions"])
        self.assertTrue(self.receipt_for(moved, "activation-2")["active"])

    def test_a_pointer_that_names_no_filed_receipt_is_named_ambiguous(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))
        elsewhere = sealed_activation_receipt(receipt_id="activation-2")
        self.write_pointer(elsewhere)

        readiness = self.observe()
        findings = reader.readiness_findings(readiness)

        self.assertEqual("observed", readiness["activation"]["active_pointer"]["state"])
        self.assertEqual(
            "names-no-filed-activation", readiness["activation"]["active_pointer"]["correlation"]
        )
        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(
            any("names no validated activation receipt" in item["message"] for item in findings)
        )
        self.assertTrue(
            any(item["path"] == reader.ACTIVE_POINTER_LOCATOR for item in findings)
        )
        # Positive control: filing the receipt the pointer names correlates it and clears the finding.
        self.file_activation(elsewhere)
        cleared = self.observe()
        self.assertEqual("matched", cleared["activation"]["active_pointer"]["correlation"])
        self.assertNotIn("state-ambiguous", self.codes(reader.readiness_findings(cleared)))

    def test_a_pointer_naming_an_identity_two_documents_claim_is_not_resolved(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        current = sealed_activation_receipt(receipt_id="activation-1")
        self.file_activation(current, name=f"{hexof('first-copy')}.json")
        self.file_activation(current, name=f"{hexof('second-copy')}.json")
        self.write_pointer(current)

        readiness = self.observe()
        findings = reader.readiness_findings(readiness)

        self.assertEqual(
            "names-more-than-one-filed-document",
            readiness["activation"]["active_pointer"]["correlation"],
        )
        self.assertIn("state-ambiguous", self.codes(findings))
        self.assertTrue(any("more than one filed document" in item["message"] for item in findings))
        # Positive control: one copy, one identity, and the same harness correlates it cleanly.
        (self.activation / f"{hexof('second-copy')}.json").unlink()
        resolved = self.observe()
        self.assertEqual("matched", resolved["activation"]["active_pointer"]["correlation"])
        self.assertNotIn("state-ambiguous", self.codes(reader.readiness_findings(resolved)))

    def test_an_unusable_pointer_is_named_and_never_followed(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        self.write_candidate()
        self.write_acquisition()
        new_archive = hexof("archive-b")
        self.write_payload(new_archive, "0.7.4")
        first = sealed_activation_receipt(receipt_id="activation-1")
        second = sealed_activation_receipt(
            receipt_id="activation-2",
            archive_sha256=new_archive,
            candidate_id=hexof(f"candidate-{new_archive}"),
            requested_version="0.7.4",
            resolved_version="0.7.4",
        )
        self.file_activation(first)
        self.file_activation(second)
        # POSITIVE CONTROL FIRST: as a physical readable file, this pointer resolves the plane.
        self.write_pointer(second)
        self.assertNotIn("state-ambiguous", self.codes(self.findings()))
        pointer_bytes = self.pointer.read_bytes()

        elsewhere = self.root / "elsewhere-pointer.json"
        elsewhere.write_bytes(pointer_bytes)
        broken_seal = copy.deepcopy(second)
        broken_seal["body"]["resolved_version"] = "9.9.9"
        cases = (
            ("symlink", None, "state-symlinked", "instead of following"),
            ("not-json", b"{", "state-unreadable", "is not one strict JSON object"),
            ("broken-seal", receipts.canonical_bytes(broken_seal), "state-malformed", "did not validate"),
        )
        for label, content, code, fragment in cases:
            with self.subTest(label=label):
                self.pointer.unlink()
                if content is None:
                    self.pointer.symlink_to(elsewhere)
                else:
                    self.pointer.write_bytes(content)

                readiness = self.observe()
                findings = reader.readiness_findings(readiness)

                self.assertIn(code, self.codes(findings))
                self.assertTrue(any(fragment in item["message"] for item in findings), findings)
                self.assertTrue(
                    any(item["path"] == reader.ACTIVE_POINTER_LOCATOR for item in findings)
                )
                # NEVER FOLLOWED, and never trusted: the document behind each of these WOULD have
                # resolved the plane, so the surviving ambiguity is the proof that it was not used.
                self.assertEqual(["0.7.3", "0.7.4"], readiness["activation"]["activated_versions"])
                self.assertIn("state-ambiguous", self.codes(findings))
        # Positive control: restoring the exact readable bytes resolves the plane again.
        self.pointer.unlink()
        self.pointer.write_bytes(pointer_bytes)
        self.assertNotIn("state-ambiguous", self.codes(self.findings()))

    def test_a_supplied_absent_pointer_is_not_the_same_input_as_an_unsupplied_one(self) -> None:
        self.write_candidate()
        self.write_acquisition()
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))

        derived = reader.observe_activation(self.activation, receipts, None)["active_pointer"]
        named_none = reader.observe_activation(
            self.activation, receipts, None, active_pointer=None
        )["active_pointer"]
        named_missing = reader.observe_activation(
            self.activation, receipts, None, active_pointer=self.root / "nowhere.json"
        )["active_pointer"]

        self.assertEqual("absent", derived["state"])
        self.assertFalse(derived["location_supplied"])
        self.assertEqual("unnamed", named_none["state"])
        self.assertTrue(named_none["location_supplied"])
        self.assertEqual("absent", named_missing["state"])
        self.assertTrue(named_missing["location_supplied"])
        self.assertNotEqual(derived, named_none)
        self.assertNotEqual(derived, named_missing)
        # Positive control: the DERIVED location is the layout's own, so the absence above is the
        # missing file and not a location this reader never looked at.
        current = sealed_activation_receipt(receipt_id="activation-1")
        self.write_pointer(current)
        found = reader.observe_activation(self.activation, receipts, None)["active_pointer"]
        self.assertEqual("observed", found["state"])
        self.assertEqual("activation-1", found["receipt_id"])
        self.assertEqual(self.pointer, self.activation.parent.joinpath(*ACTIVE_POINTER_SEGMENTS))

    def test_an_inadmissible_receipt_id_correlates_with_nothing(self) -> None:
        """A correlated identity is admitted only in the family's bounded token shape."""
        for value in ("Activation-1", "activation_1", "-activation", "activation-", "٩", "a" * 129, ""):
            with self.subTest(value=value):
                self.assertIsNone(reader.safe_receipt_id(value))
        for value in (None, 1, 1.5, ["activation-1"]):
            with self.subTest(value=value):
                self.assertIsNone(reader.safe_receipt_id(value))
        # Positive control: the admissible spellings this plane really writes DO pass.
        for value in ("activation-1", "install-op-" + "0" * 32 + "-20260820t121314z"):
            with self.subTest(value=value):
                self.assertEqual(value, reader.safe_receipt_id(value))

    def test_the_updated_plane_is_read_without_touching_it(self) -> None:
        self.write_updated_plane()
        pointer_bytes = self.pointer.read_bytes()
        before = inventory(self.home, self.state, self.root / "data")

        for verb, suffix in READER_VERBS:
            for extra in ((), ("--json",)):
                completed = self.run_reader(verb, *suffix, *extra)
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

        after = inventory(self.home, self.state, self.root / "data")
        self.assertEqual(before, after)
        self.assertEqual(pointer_bytes, self.pointer.read_bytes())
        report = json.loads(self.run_reader("doctor", "--json").stdout)
        checkout = {
            finding["code"] for finding in report["findings"] if finding["component"] == "checkout"
        }
        self.assertNotIn("state-ambiguous", checkout)
        # Positive control: the same inventory function DOES notice a change, so the equality above
        # is a measurement rather than a comparison of two empty dictionaries.
        self.assertTrue(before)
        (self.activation / f"{hexof('probe')}.json").write_bytes(b"{}")
        self.assertNotEqual(before, inventory(self.home, self.state, self.root / "data"))

    def test_every_pointer_finding_stays_inside_the_pinned_v1_report_vocabulary(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        codes = set(policy["vocabularies"]["finding_codes"])
        components = set(policy["vocabularies"]["finding_components"])
        self.write_candidate()
        self.write_acquisition()
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))
        self.write_pointer(sealed_activation_receipt(receipt_id="activation-2"))

        findings = reader.readiness_findings(self.observe())

        self.assertTrue(findings)
        for finding in findings:
            with self.subTest(code=finding["code"]):
                self.assertEqual(set(finding), set(policy["field_vocabularies"]["finding"]))
                self.assertIn(finding["code"], codes)
                self.assertIn(finding["component"], components)
                reader.validate_finding(finding, policy["field_vocabularies"], policy["vocabularies"])
        # Positive control: the same checker rejects a code outside the vocabulary.
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_finding(
                {**findings[0], "code": "activation-pointer-missing"},
                policy["field_vocabularies"],
                policy["vocabularies"],
            )

    def test_no_pointer_derived_value_can_forge_a_line_of_this_commands_output(self) -> None:
        """A reason line derived from the filesystem is ESCAPED before it is rendered."""
        self.write_candidate()
        self.write_acquisition()
        self.file_activation(sealed_activation_receipt(receipt_id="activation-1"))
        # A DIRECTORY where the pointer should be. The reason text reaches the rendered finding
        # message through the same escape every other filesystem-derived reason goes through.
        self.pointer.mkdir(parents=True)

        findings = reader.readiness_findings(self.observe())

        self.assertIn("state-unreadable", self.codes(findings))
        for finding in findings:
            for character in ("\n", "\r", "\x1b", "\x7f"):
                self.assertNotIn(character, finding["message"], finding)
                self.assertNotIn(character, finding["path"], finding)
        # Positive control: the escape is not the identity function.
        self.assertEqual("a\\nb", reader.escape_display("a\nb"))


def readable_reason(findings: list[dict[str, str]]) -> bool:
    return any(
        finding["code"] == "state-unreadable" and len(finding["message"]) > 20 for finding in findings
    )


#: One declared incompatibility in the shape the CONTRACT actually carries. It used to be built here
#: as a bare string, which no reader could ever match: `ccodex_sdlc_install` and `ccodex_sdlc_update`
#: both validate every entry as exactly `{host, reason, version}` and refuse anything else, and the
#: reader's own `isinstance(value, str)` filter therefore selected nothing at all -- so the
#: `declared-incompatible` verdict was unreachable and this fixture was asserting against a shape the
#: product never sees. The reader's filter is now per-host, so the `host` field is load-bearing: the
#: value below names the CORE host because that is the row `observe_host_compatibility` reports about.
def incompatible_record(version: str, host: str = "claude-code") -> dict[str, str]:
    return {"host": host, "reason": f"{host} {version} is declared incompatible", "version": version}


def incompatible_contract(contract: dict[str, Any], *, host: str = "claude-code") -> dict[str, Any]:
    changed = copy.deepcopy(contract)
    changed["compatibility"]["known_incompatible_host_versions"] = [incompatible_record("2.1.199", host)]
    return changed


#: ``reader.usage()`` byte for byte. Held as literals rather than assembled from the reader's own
#: constants on purpose: a pin built out of the values it is pinning would follow every rename it is
#: supposed to catch. So every word of the paragraph below is transcribed from
#: ``scripts/ccodex_sdlc.py``, including the line breaks, and a reflow there fails here by design.
EXPECTED_USAGE = (
    "usage: ccodex install   --scope user|project --agent claude|codex [--project PATH]"
    " [--mode auto|link|copy] [--dry-run]\n"
    "       ccodex status    --scope user|project --agent claude|codex [--project PATH] [--json]\n"
    "       ccodex update    --scope user|project --agent claude|codex [--project PATH]\n"
    "       ccodex uninstall --scope user|project --agent claude|codex [--project PATH] [--dry-run]\n"
    "       ccodex doctor    [--json]\n"
    "       ccodex recover   --dry-run [--json] | --apply <plan-sha256>\n\n"
    "status, doctor, and recover --dry-run read checkout-development ownership and recovery\n"
    "evidence without installing, updating, uninstalling, following, or changing state.\n"
    "`recover --dry-run` is proposal-only, requires the literal --dry-run safeguard, and renders\n"
    "the sha256 of the exact plan it derived. `recover --apply <plan-sha256>` is the one mutating\n"
    "recover form: the approval IS the digest, so it re-derives that plan from verified journal\n"
    "and receipt state and refuses by name when the re-derived digest differs, when the evidence\n"
    "does not verify, or when there is nothing to recover.\n\n"
    "install, update, and uninstall are the mutating lifecycle verbs. This reader performs no\n"
    "lifecycle mutation itself: it parses the closed grammar above and hands an admitted vector\n"
    "to one named per-verb module, refusing by name before any effect when that module is not\n"
    "present in this distribution.\n\n"
    "install, status, update, and uninstall each take an explicit --scope and\n"
    "--agent; there is no default and no wildcard for either, so one agent's removal can\n"
    "never reach another agent's bytes. doctor and recover take neither: doctor is the whole-box\n"
    "read, and recover resumes the one pending slot the substrate can carry, which is not a\n"
    "scoped object. --scope project resolves ONE repository root -- --project PATH, or a\n"
    "walk up from the working directory -- and its plane is keyed by that root, so two worktrees of\n"
    "one repository are two independent planes. Project scope is copy-only.\n"
)


if __name__ == "__main__":
    unittest.main()
