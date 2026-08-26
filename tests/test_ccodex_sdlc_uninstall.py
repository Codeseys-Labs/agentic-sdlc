"""Tests for ``scripts/ccodex_sdlc_uninstall.py``: retirement with ownership proof, on two rungs.

Nine kinds of test live here, and they check different things.

The END-TO-END tests plant a temporary home and state root, seal a real
``distribution-activation@2`` receipt over the planted entries with the family's own producer, run
the retirement, and then assert both halves: the owned entries are gone AND the terminal receipt the
run wrote validates through that same family checker.  The independent verifier is the point -- this
module composes a body rather than re-implementing one, so a test that only asked this module whether
its own output looked right would prove nothing about the receipt it claims to seal.

The KEYED-POINTER tests attack the admission authority itself.  The pointer is admitted by FILENAME,
so a pointer whose name disagrees with the scope inside the receipt it names must refuse rather than
redirect a removal, and each of the three axes -- kind, agent, root key -- is exercised with the
agreeing pointer as its positive control in the same test.  The pre-keyed name is covered on both
sides: alone it migrates and is announced, and beside the keyed one it is ``legacy-pointer-ambiguity``
with both paths named and nothing removed.

The LEGACY-UNRECEIPTED tests cover the second admission rung: a plane whose ownership rows exist and
whose activation was never receipted.  They assert the announcement, the retired rows, the sealed
``prestate_evidence: "ledger"`` receipt with no ancestor, the link-mode row the substrate's own
primitive removes, and the two preservation classes -- a row the operator edited and an adopted
unremovable one -- with the boundary control that another home's rows are left entirely alone.

The OWNERSHIP-PROOF tests plant a modified, a foreign-link, an absent, and an unprovable entry beside
owned ones and assert each is preserved, named with its own class, and left byte-identical.  Every one
carries a POSITIVE CONTROL in the same test: the owned entry in the same run IS removed, so a test
that stopped exercising the proof would also have to stop removing anything.

The BLAST-RADIUS test plants credentials, settings, plugins, a foreign skill library, a repository, a
Seeds queue, and an ADR, and asserts every one of them is byte-identical after a complete retirement.
The sealed acquisition receipt and the retired activation receipt are in that set: their bytes before
and after are compared directly.

The INTERRUPTION test raises from a checkpoint after the atomic quarantine rename and asserts three
things at once -- the journal ON DISK already named the container and the destination at that moment,
the run exits 4 rather than 0, and the terminal receipt records ``unknown`` rather than a clean
retirement.

The REFUSAL tests cover the pre-effect declines: no receipt, a tampered seal, a receipt of the wrong
operation or host or terminal phase, an off-Linux platform, a second retirement, and an argument
vector this verb does not accept.  Each asserts nothing was removed, and each is paired with the
control run that does remove.

The DISPATCH-CONTRACT tests load the module exactly as ``ccodex_sdlc.py`` does and assert
``main([])`` returns a real ``int`` in 0-4 that is not a ``bool`` -- the one return shape the
dispatcher classifies as an unknown effect if it drifts.

The RENDERING and DATA-LOSS tests attack this session's proven defect classes directly: a control
character in an entry name must not reach a rendered line, a ``1e400`` in the receipt must be refused
rather than overflowed into a seal, and a body assembled by this module must carry every entry the
walk observed rather than a list read before the walk filled it.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ccodex_sdlc_uninstall as target  # noqa: E402
from scripts import distribution_activation_receipt as dar  # noqa: E402
from scripts import install_skill_bundle as bundle  # noqa: E402

#: The ONE reader of `.git` metadata, loaded the way the product loads it (agentic-sdlc-7a2b, W4).
#: This module's own trio moved there, so the dirtiness tests below drive the shared reader directly
#: rather than a wrapper this suite would then be proving something about.
detector = bundle.load_git_project_detector(ROOT)

MODULE = ROOT / "scripts" / "ccodex_sdlc_uninstall.py"
READER = ROOT / "scripts" / "ccodex_sdlc.py"

RECEIPT_KIND = "distribution-activation"
BODY_SCHEMA = "agentic-sdlc/distribution-activation-body@2"
#: The read-only historical generation, admitted by `validate` and never sealed again.
BODY_SCHEMA_V1 = "agentic-sdlc/distribution-activation-body@1"
ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"

#: The exit classes, spelled out here rather than imported from the module under test, so a table this
#: module quietly renumbered would fail rather than agree with itself.
EXIT_RETIRED = 0
#: Spec Implementation Decision 9's class 4 -- "an admitted partial or unknown effect" -- which is what
#: a retirement that preserved or found-absent at least one inventory entry produces.  It was 1 for one
#: release; 1 is "unexpected internal failure" (agentic-sdlc-d7b3).
EXIT_PARTIAL = 4
EXIT_REFUSED = 3
EXIT_UNKNOWN = 4

INSTANT = "2026-08-20T12:00:00Z"


def hexof(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def unsealed_body(entries: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    """One unsealed activation body whose defaults seal clean, with every field overridable."""
    value: dict[str, Any] = {
        "archive_sha256": hexof("archive"),
        "candidate_id": hexof("candidate"),
        "effect_state": "complete",
        "entries": entries,
        "journal_sha256": hexof("journal"),
        "operation": "install",
        "plan_sha256": hexof("plan"),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": "0.7.3",
        "resolved_version": "0.7.3",
        "schema_version": BODY_SCHEMA,
        # The v2 scope union, with the EXACT key set a user scope admits.
        "scope": {"agent": "claude", "kind": "user"},
        "terminal_phase": "activated",
        "unknowns": [],
        "version_source": "archive-manifest",
    }
    value.update({key: item for key, item in overrides.items() if key != "receipt_id"})
    return value


def unsealed_document(entries: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return {
        "ancestors": [{"expected_kind": RECEIPT_KIND, "receipt_id": "acquisition-1", "relation": "derived-from"}],
        "body": unsealed_body(entries, **overrides),
        "content_digest": "",
        "emitting_plane": "ccodex-sdlc-install",
        "receipt_id": overrides.get("receipt_id", "activation-1"),
        "receipt_kind": RECEIPT_KIND,
        "schema": ENVELOPE_SCHEMA,
        "stated_at": INSTANT,
    }


class Plane:
    """One temporary operator plane: a home, a state root, and a sealed active receipt."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.state_root = root / "state"
        self.activation_root = self.state_root / "agentic-sdlc" / "activation"
        #: The Codex plane's configured root IS its agent root, which is why it is a sibling of the
        #: home rather than a collection inside it. Fixtures that never touch the codex plane still
        #: supply it, so no run can fall back to the operator's own `~/.codex`.
        self.codex_home = root / "codex-home"
        self.plane_root = self.home / ".claude"
        self.plane_root.mkdir(parents=True)
        self.activation_root.mkdir(parents=True)
        self.checkpoints: list[tuple[str, dict[str, Any]]] = []

    # ---- planting ------------------------------------------------------------------------------

    def write_file(self, relative: str, content: str) -> Path:
        path = self.plane_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_tree(self, relative: str, files: dict[str, str]) -> Path:
        root = self.plane_root / relative
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def entry_digest(self, relative: str) -> str:
        return bundle.digest(self.plane_root / relative)

    # ---- the active receipt --------------------------------------------------------------------

    def seal_active(self, entries: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
        result = dar.derive("seal", unsealed_document(entries, **overrides), "the observation")
        if result["verdict"] != "sealed":
            raise AssertionError(f"fixture did not seal: {result['reasons']}")
        receipt = result["receipt"]
        assert isinstance(receipt, dict)
        self.write_active(receipt)
        return receipt

    @property
    def pointer(self) -> Path:
        """This plane's ONE pointer, at the KEYED path the filename-as-authority rule fixes.

        Spelled out rather than read from the module under test: the filename IS the admission
        authority, so a test that asked the module where it looked would agree with any path it chose.
        """
        return self.activation_root / "active" / "claude" / "user.json"

    @property
    def legacy_pointer(self) -> Path:
        """Where the pre-keyed plane wrote its single pointer, for the migration cases."""
        return self.activation_root / "active-receipt.json"

    def write_active(self, receipt: dict[str, Any]) -> Path:
        path = self.pointer
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dar.canonical_bytes(receipt))
        return path

    def active_bytes(self) -> bytes:
        return self.pointer.read_bytes()

    # ---- running -------------------------------------------------------------------------------

    def config(self, **overrides: Any) -> target.Config:
        values: dict[str, Any] = {
            "scripts_dir": ROOT / "scripts",
            "home": self.home,
            "state_root": self.state_root,
            "activation_root": self.activation_root,
            # Isolated on BOTH planes (agentic-sdlc-8dca): a codex-scoped run resolves its boundary
            # from this root, so a fixture that left it unset would bound a removal at the operator's
            # own `~/.codex`.
            "codex_home": self.codex_home,
            "platform_system": "Linux",
            "stated_at": INSTANT,
            "checkpoint": self.record_checkpoint,
        }
        values.update(overrides)
        return target.Config(**values)

    def record_checkpoint(self, point: str, detail: dict[str, Any]) -> None:
        self.checkpoints.append((point, dict(detail)))

    def run(self, **overrides: Any) -> tuple[int, str]:
        config = self.config(**overrides)
        return run_capture(config)

    def terminal_receipt(self, receipt_id: str = "uninstall-activation-1") -> dict[str, Any]:
        path = self.activation_root / "receipts" / f"{receipt_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def journal(self, receipt_id: str = "uninstall-activation-1") -> dict[str, Any]:
        path = self.activation_root / "journals" / f"{receipt_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))


def capture(call: Any) -> tuple[int, str]:
    """Run one entry point with both streams captured, so a suite run stays quiet and readable."""
    import io

    out, err = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        code = call()
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return code, out.getvalue() + err.getvalue()


def run_capture(config: target.Config) -> tuple[int, str]:
    """Execute one retirement, capturing the report and the refusal channel as one text."""
    return capture(lambda: target.execute(bundle, dar, config))


def entry_record(
    name: str,
    digest_value: Any,
    *,
    prestate: str = "absent",
    disposition: str = "installed",
    mode: str | None = "copy",
) -> dict[str, Any]:
    """One v2 inventory row.  ``mode`` is required non-null wherever the disposition published bytes."""
    return {
        "content_sha256": digest_value,
        "disposition": disposition,
        "entry_name": name,
        "mode": mode,
        "prestate": prestate,
    }


def snapshot(paths: list[Path]) -> dict[str, bytes]:
    return {str(path): path.read_bytes() for path in paths}


class Harness(unittest.TestCase):
    """A temporary plane per test, with a standard two-entry owned activation."""

    def setUp(self) -> None:
        self.temp = Path(self.enterContext(_temporary_directory()))
        self.plane = Plane(self.temp)

    def plant_owned(self) -> list[dict[str, Any]]:
        self.plane.write_file("agents/sdlc-implementer.md", "# implementer\n")
        self.plane.write_tree("skills/agentic-sdlc", {"SKILL.md": "# skill\n", "references/a.md": "a\n"})
        return [
            entry_record("agents/sdlc-implementer.md", self.plane.entry_digest("agents/sdlc-implementer.md")),
            entry_record("skills/agentic-sdlc", self.plane.entry_digest("skills/agentic-sdlc")),
        ]


class _temporary_directory:
    """A context manager usable with ``enterContext`` on 3.12 without an extra dependency."""

    def __enter__(self) -> str:
        import tempfile

        self._name = tempfile.mkdtemp(prefix="ccodex-sdlc-uninstall-")
        return self._name

    def __exit__(self, *_exc: Any) -> None:
        shutil.rmtree(self._name, ignore_errors=True)


# ---- end to end ----------------------------------------------------------------------------------


class EndToEnd(Harness):
    def test_a_fully_owned_activation_is_retired_and_its_receipt_validates(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertFalse((self.plane.plane_root / "agents" / "sdlc-implementer.md").exists())
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())
        self.assertIn("removed: agents/sdlc-implementer.md", report)
        self.assertIn("removed: skills/agentic-sdlc", report)
        self.assertIn("ccodex sdlc uninstall: retired", report)

        receipt = self.plane.terminal_receipt()
        result = dar.derive("validate", receipt, "the terminal receipt")
        self.assertEqual(result["verdict"], "validated", result["reasons"])
        body = receipt["body"]
        self.assertEqual(body["operation"], "uninstall")
        self.assertEqual(body["terminal_phase"], "retired")
        self.assertEqual(body["effect_state"], "complete")
        self.assertEqual(body["public_channel"], None)
        self.assertEqual(body["release_claim"], "none")
        self.assertEqual(
            sorted((row["entry_name"], row["prestate"], row["disposition"], row["content_sha256"]) for row in body["entries"]),
            [
                ("agents/sdlc-implementer.md", "owned", "removed", None),
                ("skills/agentic-sdlc", "owned", "removed", None),
            ],
        )

    def test_the_terminal_receipt_names_the_retired_receipt_as_its_single_ancestor(self) -> None:
        self.plane.seal_active(self.plant_owned())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        receipt = self.plane.terminal_receipt()
        self.assertEqual(
            receipt["ancestors"],
            [{"expected_kind": RECEIPT_KIND, "receipt_id": "activation-1", "relation": "derived-from"}],
        )
        self.assertEqual(receipt["receipt_id"], "uninstall-activation-1")
        # The shipped family refuses `supersedes` on any operation but `update`, so the retirement
        # link is `derived-from`. This asserts the refusal is real rather than assumed.
        with_supersedes = json.loads(json.dumps(receipt))
        with_supersedes["ancestors"].append(
            {"expected_kind": RECEIPT_KIND, "receipt_id": "activation-1", "relation": "supersedes"}
        )
        refused = dar.derive("validate", with_supersedes, "the terminal receipt")
        self.assertEqual(refused["verdict"], "refused")
        self.assertIn("supersedes", "\n".join(refused["reasons"]))

    def test_the_journal_binds_the_plan_and_the_receipt_binds_the_journal(self) -> None:
        self.plane.seal_active(self.plant_owned())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        journal = self.plane.journal()
        receipt = self.plane.terminal_receipt()
        self.assertEqual(journal["phase"], "settled")
        self.assertEqual(journal["pending"], None)
        self.assertEqual(journal["plan_sha256"], receipt["body"]["plan_sha256"])
        self.assertEqual(
            receipt["body"]["journal_sha256"],
            hashlib.sha256((self.plane.activation_root / "journals" / "uninstall-activation-1.json").read_bytes()).hexdigest(),
        )
        self.assertEqual(
            sorted(row["entry_name"] for row in journal["completed"]),
            ["agents/sdlc-implementer.md", "skills/agentic-sdlc"],
        )

    def test_an_emptied_collection_directory_is_never_removed(self) -> None:
        """No purge: the collection the last owned entry lived in is left in place."""
        self.plane.seal_active(self.plant_owned())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertTrue((self.plane.plane_root / "agents").is_dir())
        self.assertTrue((self.plane.plane_root / "skills").is_dir())


# ---- ownership proof -----------------------------------------------------------------------------


class RecordedPrestateProof(Harness):
    """The record's own ownership statement is consulted BEFORE the digest (agentic-sdlc-9b9a).

    An activation that finds a destination occupied by an entry it does not own records
    ``prestate: foreign, disposition: preserved`` and -- honestly, because that is what it observed --
    stores THE OPERATOR'S OWN digest as that row's ``content_sha256``.  A retirement that proved
    removability from ``current == recorded`` alone therefore deleted exactly the file the activation
    refused to adopt, and it deleted it BECAUSE the record was accurate.  Every test here plants the
    digest-AGREEING case, which is the one a digest-only proof gets wrong.
    """

    def test_an_entry_the_activation_recorded_as_foreign_is_preserved_though_its_digest_agrees(self) -> None:
        entries = self.plant_owned()
        operator_own = self.plane.write_file("commands/sdlc-frame.md", "# the operator's own frame\n")
        recorded = self.plane.entry_digest("commands/sdlc-frame.md")
        entries.append(
            entry_record(
                "commands/sdlc-frame.md", recorded, prestate="foreign", disposition="preserved"
            )
        )
        self.plane.seal_active(entries)
        before = operator_own.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertEqual(operator_own.read_bytes(), before)
        self.assertIn("preserved: commands/sdlc-frame.md (recorded-foreign:", report)
        self.assertNotIn("removed: commands/sdlc-frame.md", report)
        # The hazard, pinned: the digest MATCHED, so a digest-only proof would have removed this file.
        self.assertEqual(recorded, bundle.digest(operator_own))
        # Positive control in the same run: the entries the activation really owned WERE removed, so
        # the preservation is a decision about one row and not a verb that retires nothing.
        self.assertIn("removed: agents/sdlc-implementer.md", report)
        self.assertFalse((self.plane.plane_root / "agents" / "sdlc-implementer.md").exists())
        rows = {row["entry_name"]: row for row in self.plane.terminal_receipt()["body"]["entries"]}
        self.assertEqual(rows["commands/sdlc-frame.md"]["prestate"], "foreign")
        self.assertEqual(rows["commands/sdlc-frame.md"]["disposition"], "preserved")
        self.assertEqual(
            dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated"
        )

    def test_an_entry_the_activation_recorded_as_modified_is_preserved_though_its_digest_agrees(self) -> None:
        entries = self.plant_owned()
        hand_edited = self.plane.write_file("agents/sdlc-critic.md", "# hand-edited by the operator\n")
        recorded = self.plane.entry_digest("agents/sdlc-critic.md")
        entries.append(
            entry_record(
                "agents/sdlc-critic.md", recorded, prestate="modified", disposition="preserved"
            )
        )
        self.plane.seal_active(entries)
        before = hand_edited.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertEqual(hand_edited.read_bytes(), before)
        self.assertIn("preserved: agents/sdlc-critic.md (recorded-modified:", report)
        self.assertNotIn("removed: agents/sdlc-critic.md", report)
        self.assertEqual(recorded, bundle.digest(hand_edited))
        self.assertIn("removed: skills/agentic-sdlc", report)
        self.assertEqual(
            dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated"
        )

    def test_an_activation_whose_only_entry_is_foreign_retires_nothing_and_still_seals(self) -> None:
        """The all-foreign plane: no destination moves, and the receipt still validates as ``none``."""
        operator_own = self.plane.write_file("commands/sdlc-frame.md", "# the operator's own frame\n")
        self.plane.seal_active(
            [
                entry_record(
                    "commands/sdlc-frame.md",
                    self.plane.entry_digest("commands/sdlc-frame.md"),
                    prestate="foreign",
                    disposition="preserved",
                )
            ]
        )
        before = operator_own.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertEqual(operator_own.read_bytes(), before)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "none")
        self.assertEqual(body["terminal_phase"], "not-activated")
        self.assertEqual(
            dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated"
        )
        # Positive control: the same harness reaches `retired` when the one entry is really owned.
        second = Plane(self.temp / "owned-instead")
        second.write_file("commands/sdlc-frame.md", "# an entry this lifecycle installed\n")
        second.seal_active(
            [entry_record("commands/sdlc-frame.md", second.entry_digest("commands/sdlc-frame.md"))]
        )
        code_two, report_two = second.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)

    def test_a_row_that_records_no_usable_prestate_is_never_removable(self) -> None:
        """The unknowns, at the classifier: the family validates these away, so they are proved here.

        A supplied-but-unusable prestate and a not-supplied one are DIFFERENT records and get different
        classes, because a consumer that collapsed them would report "the activation said nothing" for a
        row that said something this module could not read.
        """
        config = self.plane.config()
        planted = self.plane.write_file("agents/sdlc-planner.md", "# planner\n")
        digest_value = self.plane.entry_digest("agents/sdlc-planner.md")
        row = {
            "content_sha256": digest_value,
            "disposition": "installed",
            "entry_name": "agents/sdlc-planner.md",
            "mode": "copy",
            "prestate": "owned",
        }
        # POSITIVE CONTROL FIRST: this exact row, with a prestate that claims owned bytes, IS removable.
        self.assertEqual(
            ("owned-exact", planted, digest_value), target.classify_entry(bundle, config, row)
        )
        not_supplied = {key: value for key, value in row.items() if key != "prestate"}
        self.assertEqual(
            ("unrecorded-prestate", planted, None), target.classify_entry(bundle, config, not_supplied)
        )
        for unusable in (None, "", "owned-exact", "OWNED", 0, True, ["owned"], {"owned": True}):
            with self.subTest(prestate=repr(unusable)):
                self.assertEqual(
                    ("unrecognised-prestate", planted, None),
                    target.classify_entry(bundle, config, {**row, "prestate": unusable}),
                )
        # Neither class maps to `owned`, so neither can reach the plan's remove list.
        for name in ("unrecorded-prestate", "unrecognised-prestate", "recorded-foreign", "recorded-modified"):
            with self.subTest(classification=name):
                self.assertIn(name, target.CLASSES)
                self.assertNotEqual("owned", target.CLASS_PRESTATE[name])

    def test_a_recorded_foreign_row_is_not_even_stated_on_disk_before_it_is_preserved(self) -> None:
        """A row that can never be removed needs no disk fact, so none is read.

        The digest is reported as ``None`` deliberately: reading through a parent that may itself be a
        link would leave the plane this receipt describes, for an answer that cannot change the outcome.
        """
        config = self.plane.config()
        self.plane.write_file("commands/sdlc-frame.md", "# the operator's own frame\n")
        present = {
            "content_sha256": self.plane.entry_digest("commands/sdlc-frame.md"),
            "disposition": "preserved",
            "entry_name": "commands/sdlc-frame.md",
            "mode": None,
            "prestate": "foreign",
        }
        classification, destination, current = target.classify_entry(bundle, config, present)
        self.assertEqual("recorded-foreign", classification)
        self.assertEqual(self.plane.plane_root / "commands" / "sdlc-frame.md", destination)
        self.assertIsNone(current)
        # And an ABSENT foreign row gets the same class rather than being described as owned-and-gone.
        absent = {**present, "entry_name": "commands/never-planted.md"}
        self.assertEqual(
            ("recorded-foreign", self.plane.plane_root / "commands" / "never-planted.md", None),
            target.classify_entry(bundle, config, absent),
        )
        # Positive control: a name that resolves nowhere inside the plane still refuses on the NAME,
        # so the prestate consultation did not displace the path check that runs before it.
        self.assertEqual(
            ("ambiguous-name", None, None),
            target.classify_entry(bundle, config, {**present, "entry_name": "../outside.md"}),
        )


class OwnershipProof(Harness):
    def test_a_modified_entry_is_preserved_byte_for_byte_while_an_owned_one_is_removed(self) -> None:
        entries = self.plant_owned()
        modified = self.plane.write_file("agents/sdlc-reviewer.md", "# reviewer\n")
        entries.append(entry_record("agents/sdlc-reviewer.md", hexof("a digest nothing on disk has")))
        self.plane.seal_active(entries)
        before = modified.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertEqual(modified.read_bytes(), before)
        self.assertIn("preserved: agents/sdlc-reviewer.md (modified-content:", report)
        # Positive control in the same test: the owned entries in the same run WERE removed, so this
        # test cannot pass by refusing everything.
        self.assertIn("removed: agents/sdlc-implementer.md", report)
        self.assertFalse((self.plane.plane_root / "agents" / "sdlc-implementer.md").exists())
        body = self.plane.terminal_receipt()["body"]
        rows = {row["entry_name"]: row for row in body["entries"]}
        self.assertEqual(rows["agents/sdlc-reviewer.md"]["prestate"], "modified")
        self.assertEqual(rows["agents/sdlc-reviewer.md"]["disposition"], "preserved")
        self.assertEqual(rows["agents/sdlc-reviewer.md"]["content_sha256"], bundle.digest(modified))
        self.assertEqual(body["effect_state"], "partial")
        self.assertEqual(body["terminal_phase"], "unknown")
        self.assertEqual(dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated")

    def test_a_link_where_content_was_activated_is_preserved_and_its_target_untouched(self) -> None:
        entries = self.plant_owned()
        outside = self.temp / "outside.md"
        outside.write_text("# outside the plane\n", encoding="utf-8")
        link = self.plane.plane_root / "agents" / "sdlc-critic.md"
        link.symlink_to(outside)
        entries.append(entry_record("agents/sdlc-critic.md", bundle.digest(link)))
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertTrue(link.is_symlink())
        self.assertTrue(outside.is_file())
        self.assertEqual(outside.read_text(encoding="utf-8"), "# outside the plane\n")
        self.assertIn("preserved: agents/sdlc-critic.md (foreign-symlink:", report)
        # Positive control: the digest in the inventory MATCHED the link exactly, so the preservation
        # came from the symlink rule and not from a digest mismatch.
        self.assertEqual(bundle.digest(link), [row for row in entries if row["entry_name"] == "agents/sdlc-critic.md"][0]["content_sha256"])
        self.assertIn("removed: skills/agentic-sdlc", report)

    def test_an_entry_reached_through_a_linked_parent_is_preserved(self) -> None:
        entries = self.plant_owned()
        real = self.temp / "elsewhere"
        (real / "nested").mkdir(parents=True)
        (real / "nested" / "thing.md").write_text("# elsewhere\n", encoding="utf-8")
        (self.plane.plane_root / "commands").symlink_to(real)
        entries.append(entry_record("commands/nested/thing.md", bundle.digest(real / "nested" / "thing.md")))
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertTrue((real / "nested" / "thing.md").is_file())
        self.assertIn("preserved: commands/nested/thing.md (retargeted-parent:", report)
        self.assertIn("removed: agents/sdlc-implementer.md", report)

    def test_an_unlstatable_parent_is_treated_as_retargeted_never_as_clear(self) -> None:
        """A parent ``lstat`` that raises must read as retargeted, not as proven clear.

        The per-entry digest proof downstream never depended on this walk succeeding, so failing
        closed on an inspection error costs nothing but one extra "preserved" -- and reading the
        error as "not a link" would let an entry through the exact check that exists to stop it
        (agentic-sdlc-7c7d).
        """
        entries = self.plant_owned()
        self.plane.seal_active(entries)
        config = self.plane.config()
        destination = config.plane_root / "agents" / "sdlc-implementer.md"
        flaky_parent = config.plane_root / "agents"
        real_lstat = Path.lstat

        def flaky(path_self: Path, *args: Any, **kwargs: Any) -> Any:
            if path_self == flaky_parent:
                raise OSError("simulated: this component cannot be inspected")
            return real_lstat(path_self, *args, **kwargs)

        with mock.patch.object(Path, "lstat", flaky):
            self.assertTrue(target.parent_is_retargeted(config, destination))
        # Positive control: the identical destination, with no injected fault, is not retargeted.
        self.assertFalse(target.parent_is_retargeted(config, destination))

    def test_an_inventory_entry_with_no_digest_is_never_removed(self) -> None:
        entries = self.plant_owned()
        unprovable = self.plane.write_file("agents/sdlc-planner.md", "# planner\n")
        entries.append(
            entry_record("agents/sdlc-planner.md", None, prestate="owned", disposition="refreshed")
        )
        self.plane.seal_active(
            entries,
            unknowns=[
                {
                    "detail": "the digest could not be taken during activation",
                    "observation": "entry-content",
                    "subject": "agents/sdlc-planner.md",
                }
            ],
            effect_state="partial",
            terminal_phase="activated-partial",
        )
        before = unprovable.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertEqual(unprovable.read_bytes(), before)
        self.assertIn("preserved: agents/sdlc-planner.md (unprovable-inventory:", report)
        self.assertIn("inherited unknown: entry-content about agents/sdlc-planner.md", report)
        self.assertIn("removed: agents/sdlc-implementer.md", report)

    def test_an_absent_entry_is_noted_absent_and_the_run_does_not_claim_a_clean_retirement(self) -> None:
        entries = self.plant_owned()
        entries.append(entry_record("agents/sdlc-cartographer.md", hexof("never planted")))
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertIn("absent: agents/sdlc-cartographer.md (", report)
        body = self.plane.terminal_receipt()["body"]
        rows = {row["entry_name"]: row for row in body["entries"]}
        self.assertEqual(rows["agents/sdlc-cartographer.md"]["prestate"], "absent")
        self.assertEqual(rows["agents/sdlc-cartographer.md"]["disposition"], "preserved")
        self.assertEqual(rows["agents/sdlc-cartographer.md"]["content_sha256"], None)
        self.assertNotEqual(body["terminal_phase"], "retired")

    def test_an_activation_whose_entries_are_all_gone_records_no_effect(self) -> None:
        entries = [entry_record("agents/one.md", hexof("one")), entry_record("agents/two.md", hexof("two"))]
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "none")
        self.assertEqual(body["terminal_phase"], "not-activated")
        self.assertEqual(dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated")
        # Positive control: the same harness reaches `retired` once the entries are really there.
        second = Plane(self.temp / "second")
        second.write_file("agents/one.md", "# one\n")
        second.seal_active([entry_record("agents/one.md", second.entry_digest("agents/one.md"))])
        code_two, report_two = second.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)

    def test_a_name_that_would_escape_the_plane_resolves_to_nothing(self) -> None:
        """Two independent refusals of the same name, and the second is the one that decides a path.

        The family's inventory check refuses ``..`` and an absolute name by its own name regex, so a
        VALIDATED receipt cannot carry one -- that is the first control, asserted here directly. This
        module still re-derives the destination rather than trusting the spelling, because a receipt is
        evidence and never authorization for where a deletion lands.
        """
        config = self.plane.config()
        for hostile in ("/etc/hosts", "../../etc/hosts", "a/../../../etc/hosts", "", "..", "/"):
            with self.subTest(name=hostile):
                self.assertIsNone(target.resolve_destination(config, hostile))
                # First control: the family refuses the same name in an inventory row.
                refused = dar.derive("seal", unsealed_document([entry_record(hostile, hexof("hostile"))]), "the observation")
                self.assertEqual(refused["verdict"], "refused")
                self.assertIn("entry_name", "\n".join(refused["reasons"]))
        # Third control: the same document shape seals once the name is ordinary, so the refusals
        # above came from the names and not from the surrounding fixture.
        self.assertEqual(
            dar.derive("seal", unsealed_document([entry_record("agents/ok.md", hexof("ok"))]), "the observation")["verdict"],
            "sealed",
        )
        # Second control: an ordinary name DOES resolve, so the assertions above are about the names.
        resolved = target.resolve_destination(config, "skills/agentic-sdlc")
        self.assertEqual(resolved, self.plane.plane_root / "skills" / "agentic-sdlc")


# ---- blast radius --------------------------------------------------------------------------------


class BlastRadius(Harness):
    def test_nothing_outside_the_inventory_is_touched_by_a_complete_retirement(self) -> None:
        entries = self.plant_owned()
        bystanders = [
            self.plane.write_file(".credentials.json", '{"claudeAiOauth":{"accessToken":"sk-ant-oat-EXAMPLE"}}\n'),
            self.plane.write_file("settings.json", '{"statusLine":{"type":"command"}}\n'),
            self.plane.write_file("plugins/config.json", "{}\n"),
            self.plane.write_file("skills/foreign-library/SKILL.md", "# not ours\n"),
            self.plane.write_file("projects/session.jsonl", '{"turn":1}\n'),
            self.plane.write_file("agents/operator-authored.md", "# the operator's own\n"),
        ]
        repository = self.temp / "repo"
        (repository / ".seeds").mkdir(parents=True)
        (repository / ".seeds" / "issues.jsonl").write_text('{"id":"x"}\n', encoding="utf-8")
        (repository / "docs").mkdir()
        (repository / "docs" / "0001-adr.md").write_text("# ADR\n", encoding="utf-8")
        acquisition = self.plane.state_root / "agentic-sdlc" / "acquisition" / "receipts" / "sealed.json"
        acquisition.parent.mkdir(parents=True)
        acquisition.write_bytes(dar.canonical_bytes({"body": {"selection": "absent"}, "record_sha256": hexof("seal")}))
        bystanders.extend(
            [
                repository / ".seeds" / "issues.jsonl",
                repository / "docs" / "0001-adr.md",
                acquisition,
            ]
        )
        self.plane.seal_active(entries)
        before = snapshot(bystanders)
        active_before = self.plane.active_bytes()
        acquisition_stat = acquisition.lstat()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertEqual(snapshot(bystanders), before)
        # The two sealed receipts are read, never written, moved, or re-sealed.
        self.assertEqual(self.plane.active_bytes(), active_before)
        self.assertEqual(acquisition.lstat().st_mtime_ns, acquisition_stat.st_mtime_ns)
        self.assertEqual(acquisition.lstat().st_ino, acquisition_stat.st_ino)
        # No credential value reaches the report.
        self.assertNotIn("sk-ant-oat", report)

    def test_the_plane_keeps_every_unrecorded_sibling_inside_an_owned_collection(self) -> None:
        entries = self.plant_owned()
        sibling = self.plane.write_file("skills/another-skill/SKILL.md", "# another\n")
        self.plane.seal_active(entries)
        before = sibling.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertEqual(sibling.read_bytes(), before)
        self.assertNotIn("another-skill", report)


# ---- interruption --------------------------------------------------------------------------------


class Interruption(Harness):
    def test_an_interruption_after_the_quarantine_exits_unknown_over_a_recoverable_journal(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(entries)
        journal_path = self.plane.activation_root / "journals" / "uninstall-activation-1.json"
        observed: dict[str, Any] = {}

        def interrupt(point: str, detail: dict[str, Any]) -> None:
            if point != "after-quarantined":
                return
            # The journal must ALREADY be on disk naming the container and the destination: that is
            # the crash-consistency claim, and reading it here is what proves it.
            observed["journal"] = json.loads(journal_path.read_text(encoding="utf-8"))
            observed["detail"] = dict(detail)
            raise KeyboardInterrupt("simulated interruption")

        code, report = self.plane.run(checkpoint=interrupt)

        self.assertEqual(code, EXIT_UNKNOWN, report)
        pending = observed["journal"]["pending"]
        self.assertEqual(observed["journal"]["phase"], "quarantined")
        self.assertEqual(pending["destination"], observed["detail"]["destination"])
        self.assertTrue(Path(pending["container"]).is_dir())
        self.assertTrue(Path(pending["payload"]).exists())
        self.assertFalse(Path(pending["destination"]).exists())
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "unknown")
        self.assertEqual(body["terminal_phase"], "unknown")
        self.assertEqual(dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated")
        self.assertIn("failed after it was quarantined, so its effect is unknown", report)
        # The entry that LEFT the plane is never reported as preserved: the doubt lives in the effect
        # state and in the journal's outstanding container, not in a false statement about the plane.
        self.assertIn("removed with an outstanding quarantine: agents/sdlc-implementer.md", report)
        self.assertNotIn("preserved: agents/sdlc-implementer.md", report)
        rows = {row["entry_name"]: row for row in body["entries"]}
        self.assertEqual(rows["agents/sdlc-implementer.md"]["disposition"], "removed")
        self.assertEqual(rows["agents/sdlc-implementer.md"]["content_sha256"], None)
        # The entry the walk never reached is still preserved and named.
        self.assertEqual(rows["skills/agentic-sdlc"]["disposition"], "preserved")
        self.assertTrue((self.plane.plane_root / "skills" / "agentic-sdlc").is_dir())
        # The journal on disk after the run still names the outstanding container, so recovery has a
        # record rather than a clean-looking half-state.
        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["phase"], "unknown")

    def test_content_that_changes_after_the_transaction_is_armed_is_re_proved_and_preserved(self) -> None:
        """The second proof, taken between arming and the rename, is the one a racer would defeat."""
        entries = self.plant_owned()
        self.plane.seal_active(entries)
        victim = self.plane.plane_root / "agents" / "sdlc-implementer.md"

        def mutate(point: str, detail: dict[str, Any]) -> None:
            if point == "after-armed" and detail["entry_name"] == "agents/sdlc-implementer.md":
                victim.write_text("# rewritten between the proof and the rename\n", encoding="utf-8")

        code, report = self.plane.run(checkpoint=mutate)

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertTrue(victim.is_file())
        self.assertEqual(victim.read_text(encoding="utf-8"), "# rewritten between the proof and the rename\n")
        self.assertIn("changed after its transaction was armed", report)
        # Positive control: the entry nobody touched in the same run WAS removed.
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())
        # The abandoned quarantine container is cleaned up rather than left behind.
        self.assertEqual([child.name for child in (self.plane.plane_root / "agents").iterdir()], ["sdlc-implementer.md"])

    def test_an_interruption_before_the_quarantine_preserves_the_entry_and_does_not_claim_unknown(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(entries)

        def interrupt(point: str, detail: dict[str, Any]) -> None:
            if point == "after-armed" and detail["entry_name"] == "agents/sdlc-implementer.md":
                raise RuntimeError("simulated failure before the rename")

        code, report = self.plane.run(checkpoint=interrupt)

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())
        self.assertIn("could not be quarantined, so it was preserved untouched", report)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "partial")

    def test_a_normal_return_that_never_recorded_settlement_is_reported_unknown(self) -> None:
        """``outcome['settled']`` is consulted, not just written (agentic-sdlc-7c7d).

        Nothing in this module today returns from ``remove_one`` without having set it, so this
        stands in for a future regression: a wrapper that runs the real removal but then clears the
        flag the way a broken early-return would.
        """
        entries = self.plant_owned()
        self.plane.seal_active(entries)
        real_remove_one = target.remove_one

        def forgets_to_settle(bundle: Any, config: Any, journal: Any, row: Any, outcome: Any, **kwargs: Any) -> None:
            real_remove_one(bundle, config, journal, row, outcome, **kwargs)
            outcome["settled"] = False

        with mock.patch.object(target, "remove_one", forgets_to_settle):
            code, report = self.plane.run()

        self.assertEqual(code, EXIT_UNKNOWN, report)
        self.assertIn("returned without recording settlement", report)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "unknown")
        # Positive control: the identical harness, with the real function alone, retires cleanly.
        second = Plane(self.temp / "second-normal-settle")
        second.write_file("agents/sdlc-implementer.md", "# implementer\n")
        second.seal_active(
            [entry_record("agents/sdlc-implementer.md", second.entry_digest("agents/sdlc-implementer.md"))]
        )
        code_two, report_two = second.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)


# ---- the installer ownership rows ------------------------------------------------------------------


def installer_write_config(plane: Plane, payload_root: Path) -> Any:
    """A copy-mode installer Config over this plane: the shape the install verb activates with."""
    return bundle.Config(
        payload_root, plane.home, plane.home / ".codex", "copy", False, "claude", plane.state_root
    )


def installer_read_config(plane: Plane, payload_root: Path) -> Any:
    """The read-only Config the reader's projection uses over the same shared state document."""
    return bundle.Config(
        payload_root, plane.home, plane.home / ".codex", "auto", True, "all", plane.state_root
    )


def owned_entry_conflicts(plane: Plane, payload_root: Path) -> list[dict[str, str]]:
    projection = bundle.readonly_projection(installer_read_config(plane, payload_root))
    return [finding for finding in projection["findings"] if finding["code"] == "owned-entry-conflict"]


def activate_with_ownership_rows(plane: Plane, payload_root: Path) -> list[dict[str, Any]]:
    """Publish the standard two entries exactly as ``ccodex sdlc install`` does.

    The rows land in the shared installer state through the installer's own
    ``transactional_create`` -- the machinery the install verb reuses -- so what these tests
    exercise is the real correlation: rows keyed by ``destination_for`` spellings against a
    retirement that resolves the receipt's entry names back to the same destinations.
    """
    (payload_root / "agents").mkdir(parents=True, exist_ok=True)
    (payload_root / "agents" / "sdlc-implementer.md").write_text("# implementer\n", encoding="utf-8")
    skill = payload_root / "skills" / "agentic-sdlc"
    (skill / "references").mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (skill / "references" / "a.md").write_text("a\n", encoding="utf-8")
    config = installer_write_config(plane, payload_root)
    state = bundle.load_config_state(config)
    for entry in (
        bundle.Entry("claude", "agent", "sdlc-implementer.md", payload_root / "agents" / "sdlc-implementer.md"),
        bundle.Entry("claude", "skill", "agentic-sdlc", skill),
    ):
        destination = bundle.destination_for(entry, config)
        bundle.ensure_collection(entry, destination, config)
        bundle.transactional_create(entry, destination, config, state)
    return [
        entry_record("agents/sdlc-implementer.md", plane.entry_digest("agents/sdlc-implementer.md")),
        entry_record("skills/agentic-sdlc", plane.entry_digest("skills/agentic-sdlc")),
    ]


class OwnershipRows(Harness):
    """The rows the activation wrote are retired with the bytes (agentic-sdlc-42ec).

    Wave f194-w1's FINDING-1: after a complete receipted uninstall, ``ccodex sdlc status`` reported
    ``bundle.state degraded`` with one ``owned-entry-conflict`` per removed entry, because the
    install verb writes ownership rows into the shared installer state and the retirement removed
    only the bytes.  These tests pin the symmetric half: a retirement retires the rows it proved,
    through the installer's own pending slot, and every window crash-resolves per that doctrine.
    """

    def state_path(self, plane: Plane | None = None) -> Path:
        return (plane or self.plane).state_root / "agentic-sdlc-installer" / "state.json"

    def state_document(self, plane: Plane | None = None) -> dict[str, Any]:
        return json.loads(self.state_path(plane).read_text(encoding="utf-8"))

    def test_a_complete_retirement_leaves_zero_owned_entry_conflicts(self) -> None:
        """The missing post-uninstall status proof: install rows, uninstall, projection clean."""
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)
        before = self.state_document()
        self.assertEqual(len(before["entries"]), 2, before)
        # Control half one: with rows and bytes both present, the projection is already clean, so a
        # clean projection after the run is not a vacuous truth about a plane that never had rows.
        self.assertEqual(owned_entry_conflicts(self.plane, payload), [])

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        after = self.state_document()
        self.assertEqual(after["entries"], {})
        self.assertIsNone(after["pending"])
        projection = bundle.readonly_projection(installer_read_config(self.plane, payload))
        self.assertEqual(
            [finding for finding in projection["findings"] if finding["code"] == "owned-entry-conflict"],
            [],
            projection,
        )
        self.assertNotEqual(projection["state"], "degraded", projection)

    def test_the_conflict_detector_bites_on_bytes_removed_with_rows_left(self) -> None:
        """POSITIVE CONTROL for the projection assertion above.

        The exact pre-fix end state -- bytes gone, rows left -- must read as
        ``owned-entry-conflict``/``degraded``.  Without this, a projection that stopped detecting
        absence would make the zero-conflict assertion vacuous.
        """
        payload = self.plane.root / "payload"
        activate_with_ownership_rows(self.plane, payload)
        (self.plane.plane_root / "agents" / "sdlc-implementer.md").unlink()
        shutil.rmtree(self.plane.plane_root / "skills" / "agentic-sdlc")

        projection = bundle.readonly_projection(installer_read_config(self.plane, payload))

        conflicts = [
            finding for finding in projection["findings"] if finding["code"] == "owned-entry-conflict"
        ]
        self.assertEqual(len(conflicts), 2, projection)
        self.assertTrue(all(finding["message"] == "owned bundle entry is absent" for finding in conflicts))
        self.assertEqual(projection["state"], "degraded")

    def test_the_row_retirement_mechanism_is_what_produces_the_clean_status(self) -> None:
        """The executable form of 'revert the fix and the test fails'.

        With the matching seam disabled the run still retires every byte at exit 0 -- the pre-fix
        behaviour exactly -- and the stale rows then read as conflicts, so the clean projection in
        the first test is produced by the retirement mechanism and by nothing else.
        """
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)

        with mock.patch.object(target, "matched_ownership_row", lambda *args: (None, None)):
            code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertEqual(len(self.state_document()["entries"]), 2)
        conflicts = owned_entry_conflicts(self.plane, payload)
        self.assertEqual(len(conflicts), 2, conflicts)
        self.assertEqual(
            bundle.readonly_projection(installer_read_config(self.plane, payload))["state"], "degraded"
        )

    def test_an_interruption_between_byte_removal_and_row_retirement_recovers_per_the_pending_slot(self) -> None:
        """The chosen path's crash case: killed after the rename, before the row commit.

        The armed slot must survive the crash, be NAMED by the projection as pending recovery, and
        resolve through ``recover_pending`` from the live bytes: the destination is absent, so the
        armed ``uninstall`` transition COMMITS and the row retires.
        """
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)
        victim = str(self.plane.plane_root / "agents" / "sdlc-implementer.md")

        def interrupt(point: str, detail: dict[str, Any]) -> None:
            if point == "after-quarantined" and detail["destination"] == victim:
                raise KeyboardInterrupt("simulated crash between the rename and the row commit")

        code, report = self.plane.run(checkpoint=interrupt)

        self.assertEqual(code, EXIT_UNKNOWN, report)
        state = self.state_document()
        pending = state["pending"]
        self.assertIsNotNone(pending, state)
        self.assertEqual(pending["operation"], "uninstall")
        self.assertEqual(pending["path"], victim)
        self.assertIsNone(pending["after"])
        self.assertEqual(state["entries"][victim], pending["before"])
        self.assertFalse(Path(victim).exists())
        # The projection names the interrupted transition rather than reporting a clean plane.
        projection = bundle.readonly_projection(installer_read_config(self.plane, payload))
        self.assertEqual(
            [finding["code"] for finding in projection["findings"] if finding["code"] == "pending-recovery"],
            ["pending-recovery"],
            projection,
        )
        self.assertEqual(projection["state"], "blocked")
        # Recovery resolves the slot from the live bytes, through the installer's own resolver. The
        # read-only form proposes the same outcome first, without writing it.
        write_config = installer_write_config(self.plane, payload)
        dry_state = bundle.load_config_state(write_config)
        proposals, unresolved = bundle.recover_pending(write_config, dry_state, read_only=True)
        self.assertTrue(any(line.startswith("would recover commit") for line in proposals), proposals)
        self.assertTrue(unresolved)
        live_state = bundle.load_config_state(write_config)
        messages, unresolved = bundle.recover_pending(write_config, live_state, read_only=False)
        self.assertTrue(any(line.startswith("recovered commit") for line in messages), messages)
        self.assertFalse(unresolved)
        final = self.state_document()
        self.assertIsNone(final["pending"])
        self.assertNotIn(victim, final["entries"])

    def test_a_rename_failure_after_arming_rolls_the_armed_row_back(self) -> None:
        """The other half of the window: armed but nothing moved resolves as an abort in-run."""
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)
        victim = self.plane.plane_root / "agents" / "sdlc-implementer.md"
        real_rename = bundle.rename_absent

        def failing(source: Path, destination: Path) -> None:
            if source == victim:
                raise OSError("simulated rename failure")
            real_rename(source, destination)

        with mock.patch.object(bundle, "rename_absent", failing):
            code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        state = self.state_document()
        self.assertIsNone(state["pending"])
        self.assertIn(str(victim), state["entries"])
        self.assertTrue(victim.is_file())
        # Positive control in the same run: the untouched entry WAS removed and its row retired.
        self.assertNotIn(str(self.plane.plane_root / "skills" / "agentic-sdlc"), state["entries"])
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())

    def test_a_row_recording_other_bytes_is_preserved_and_named(self) -> None:
        """Preservation is not weakened: a row that records other bytes is never guessed retired."""
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        victim = str(self.plane.plane_root / "agents" / "sdlc-implementer.md")
        state = self.state_document()
        state["entries"][victim]["digest"] = hexof("some other bytes entirely")
        self.state_path().write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertIn("does not record the bytes this retirement proved", report)
        final = self.state_document()
        self.assertIn(victim, final["entries"])
        self.assertNotIn(str(self.plane.plane_root / "skills" / "agentic-sdlc"), final["entries"])

    def test_an_outstanding_installer_transition_refuses_before_any_effect(self) -> None:
        """An armed slot someone else owns is never overwritten: recovery is a separate operation."""
        payload = self.plane.root / "payload"
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)
        victim = str(self.plane.plane_root / "agents" / "sdlc-implementer.md")
        state = self.state_document()
        state["pending"] = {
            "operation": "uninstall",
            "path": victim,
            "before": state["entries"][victim],
            "after": None,
        }
        self.state_path().write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("outstanding lifecycle transition", report)
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        self.assertTrue((self.plane.plane_root / "skills" / "agentic-sdlc").is_dir())
        self.assertFalse((self.plane.activation_root / "receipts").exists())


# ---- the keyed pointer plane ----------------------------------------------------------------------


class KeyedPointerPlane(Harness):
    """The pointer FILENAME is the admission authority, and the pre-keyed name migrates once."""

    def test_this_module_derives_the_same_pointer_paths_the_family_does(self) -> None:
        """The re-expression's whole cost is drift, and this is where it is paid."""
        activation = Path("/state/agentic-sdlc/activation")
        for kind, root in (("user", None), ("project", "/srv/repo")):
            with self.subTest(kind=kind):
                self.assertEqual(
                    dar.pointer_path(activation, "claude", kind, root),
                    target._pointer_path(activation, "claude", kind, root),
                )
        self.assertEqual(dar.LEGACY_ACTIVE_POINTER_NAME, target.LEGACY_ACTIVE_POINTER_NAME)
        self.assertEqual(dar.ACTIVE_DIRECTORY, target.ACTIVE_DIRECTORY)
        self.assertEqual(dar.USER_POINTER_NAME, target.USER_POINTER_NAME)
        self.assertEqual(dar.ROOT_KEY_CHARACTERS, target.ROOT_KEY_CHARACTERS)
        # POSITIVE CONTROL: the comparison detects a divergence, so the equalities are not vacuous.
        self.assertNotEqual(
            dar.pointer_path(activation, "claude", "user"),
            target._pointer_path(activation, "codex", "user"),
        )

    def test_the_retirement_admits_the_keyed_pointer_and_not_the_legacy_name(self) -> None:
        entries = self.plant_owned()
        receipt = self.plane.seal_active(entries)  # writes the KEYED path
        self.assertTrue(self.plane.pointer.is_file())
        self.assertFalse(self.plane.legacy_pointer.exists())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertEqual("uninstall", self.plane.terminal_receipt()["body"]["operation"])
        self.assertEqual({"agent": "claude", "kind": "user"}, self.plane.terminal_receipt()["body"]["scope"])
        self.assertEqual(receipt["receipt_id"], "activation-1")

    def test_a_legacy_pointer_alone_is_migrated_announced_and_removed(self) -> None:
        entries = self.plant_owned()
        receipt = self.plane.seal_active(entries)
        # Move it back to the pre-keyed spelling: the state a host activated before the keyed plane.
        self.plane.legacy_pointer.write_bytes(dar.canonical_bytes(receipt))
        self.plane.pointer.unlink()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertIn("migrated the legacy active pointer", report)
        self.assertIn(str(self.plane.legacy_pointer), report)
        self.assertIn(str(self.plane.pointer), report)
        self.assertFalse(self.plane.legacy_pointer.exists(), "the migration removes the old file")
        self.assertTrue(self.plane.pointer.is_file())

    def test_both_pointers_present_is_refused_naming_both_paths(self) -> None:
        entries = self.plant_owned()
        receipt = self.plane.seal_active(entries)
        self.plane.legacy_pointer.write_bytes(dar.canonical_bytes(receipt))
        before = snapshot(
            [self.plane.plane_root / "agents" / "sdlc-implementer.md", self.plane.legacy_pointer, self.plane.pointer]
        )

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("legacy-pointer-ambiguity", report)
        self.assertIn(str(self.plane.legacy_pointer), report)
        self.assertIn(str(self.plane.pointer), report)
        self.assertIn("remove the one that is not current", report)
        self.assertEqual(
            before,
            snapshot(
                [
                    self.plane.plane_root / "agents" / "sdlc-implementer.md",
                    self.plane.legacy_pointer,
                    self.plane.pointer,
                ]
            ),
        )
        # POSITIVE CONTROL: removing either one lets the same plane retire.
        self.plane.legacy_pointer.unlink()
        code_two, report_two = self.plane.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)

    def test_a_pointer_whose_receipt_names_another_scope_refuses_on_the_kind_axis(self) -> None:
        """A hand-edited pointer must not redirect a removal at a plane it does not describe."""
        entries = self.plant_owned()
        project = self.plane.seal_active(
            entries, scope={"agent": "claude", "kind": "project", "root": str(self.plane.home / "repo")}
        )
        self.assertEqual("project", project["body"]["scope"]["kind"])
        before = snapshot([self.plane.plane_root / "agents" / "sdlc-implementer.md"])

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("pointer-receipt-disagreement", report)
        self.assertIn("is a user-scope pointer while the receipt it names records scope.kind", report)
        self.assertEqual(before, snapshot([self.plane.plane_root / "agents" / "sdlc-implementer.md"]))
        # POSITIVE CONTROL: the same receipt at the pointer its own scope names is admitted.
        project_root = self.plane.home / "repo"
        keyed = dar.pointer_path(self.plane.activation_root, "claude", "project", str(project_root))
        keyed.parent.mkdir(parents=True, exist_ok=True)
        keyed.write_bytes(dar.canonical_bytes(project))
        self.plane.pointer.unlink()
        (project_root / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        for relative in ("agents/sdlc-implementer.md",):
            (project_root / ".claude" / relative).write_text("# implementer\n", encoding="utf-8")
        code_two, report_two = self.plane.run(scope_kind="project", project_root=project_root)
        self.assertNotIn("pointer-receipt-disagreement", report_two)
        self.assertIn("project:", report_two)
        self.assertNotEqual(EXIT_REFUSED, code_two, report_two)

    def test_a_pointer_moved_to_another_root_s_key_refuses_on_the_root_axis(self) -> None:
        entries = self.plant_owned()
        project_root = self.plane.home / "repo"
        receipt = self.plane.seal_active(
            entries, scope={"agent": "claude", "kind": "project", "root": str(project_root)}
        )
        self.plane.pointer.unlink()
        wrong = dar.pointer_path(self.plane.activation_root, "claude", "project", str(self.plane.home / "other"))
        wrong.parent.mkdir(parents=True, exist_ok=True)
        wrong.write_bytes(dar.canonical_bytes(receipt))

        code, report = self.plane.run(scope_kind="project", project_root=self.plane.home / "other")

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("pointer-receipt-disagreement", report)


# ---- the legacy-unreceipted retirement ------------------------------------------------------------


class LedgerFixtures:
    """The fixtures the three ledger-rung suites share. A MIXIN, deliberately not a ``TestCase``.

    Two of these classes used to subclass a third to borrow ``payload`` and ``distribution``, which
    also inherited its ten tests -- so every one of them ran three times and one defect was reported
    under three class names. Helpers live here; tests live in the suites.
    """

    def payload(self, name: str = "payload") -> Path:
        root = self.temp / name
        root.mkdir(parents=True, exist_ok=True)
        return root

    def distribution(self, name: str, *, git: bool = False) -> Path:
        """One fabricated distribution root: a scripts/ this module can load, plus a bump driver.

        SELF-CONTAINED BY CONSTRUCTION, because the alternative reads the developer's machine. The
        ledger rung observes ``config.scripts_dir.parent``, so a fixture that passed this suite's own
        ``ROOT / "scripts"`` would make the product compute the dirtiness of the REPOSITORY -- which
        answers False on a clean checkout and True mid-wave, and a test asserting either is asserting
        the state of whoever ran it. ``git=False`` leaves the root with no git metadata at all, which
        is the one input whose answer is fixed on every host.
        """
        root = self.temp / name
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        for module in (
            "distribution_activation_receipt.py",
            "install_skill_bundle.py",
            "ccodex_sdlc_host_planes.py",
        ):
            shutil.copy2(ROOT / "scripts" / module, scripts / module)
        # The shared `.git` reader travels too, and it has to: modules are loaded from
        # `scripts_dir.parent`, and a fabricated distribution that carried the scripts but not the
        # reader would be a shape no real distribution has (agentic-sdlc-7a2b, W4).
        reader = root / bundle.GIT_DETECTOR_RELATIVE
        reader.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / bundle.GIT_DETECTOR_RELATIVE, reader)
        (root / target.VERSION_DRIVER_NAME).write_text(
            json.dumps({"current": "0.7.5"}), encoding="utf-8"
        )
        (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        if git:
            self.commit_tree(root)
        return root

    @staticmethod
    def commit_tree(root: Path) -> str:
        """Make the fabricated root a real single-commit git repository, and return its commit.

        The TEST spawns git; the product never does. That asymmetry is the point: what is under test is
        a reader of ``.git`` metadata, so the fixture has to be metadata a real git wrote rather than
        bytes this file invented.
        """
        environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        for arguments in (
            ("init", "-q", "--initial-branch=main", "."),
            ("add", "-A"),
            ("commit", "-q", "-m", "fixture"),
        ):
            subprocess.run(
                ["git", *arguments], cwd=root, env=environment, check=True, capture_output=True
            )
        resolved = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        return resolved.stdout.strip()


class LegacyUnreceipted(LedgerFixtures, Harness):
    """A plane with ownership rows and no receipt: the FINDING-1 defect class, given a verb.

    ``bundle install`` wrote rows for years without sealing anything, and a repository root could be
    handed to it as a configured home, so those rows would otherwise be selected by NO verb. Every
    test here asserts the announcement as well as the effect, because the operator's question is which
    evidence authorised the removal.
    """

    def test_ownership_rows_with_no_receipt_are_retired_and_receipted(self) -> None:
        payload = self.payload()
        # THE DISTRIBUTION ROOT IS FABRICATED, and it has to be: this rung's receipt records what it can
        # read about the distribution it ran from, and `checkout.dirty` is now COMPUTED from that root's
        # git metadata. Handing it this suite's own `ROOT / "scripts"` made the product compute the
        # dirtiness of the REPOSITORY -- False on a clean checkout, True mid-wave -- so the assertion
        # below silently asserted the state of whoever ran it, and it passed for a whole wave only
        # because a gate runs before a commit. A git-less root is the input whose answer is fixed.
        distribution = self.distribution("legacy-distribution")
        activate_with_ownership_rows(self.plane, payload)
        self.assertFalse(self.plane.pointer.exists())
        implementer = self.plane.plane_root / "agents" / "sdlc-implementer.md"
        self.assertTrue(implementer.is_file())

        code, report = self.plane.run(scripts_dir=distribution / "scripts")

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertIn("legacy-unreceipted uninstall (no activation receipt for claude/user)", report)
        self.assertFalse(implementer.exists(), "the bytes left the plane")
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())
        # The ownership rows left with the bytes: the very next status must not read a conflict.
        self.assertEqual([], owned_entry_conflicts(self.plane, payload))
        state = bundle.load_config_state(installer_read_config(self.plane, payload))
        self.assertEqual({}, state["entries"])
        # And the retirement is EVIDENCE: one sealed receipt whose prestate evidence is the ledger.
        receipts = sorted((self.plane.activation_root / "receipts").glob("*.json"))
        self.assertEqual(1, len(receipts), receipts)
        document = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual("ledger", document["body"]["prestate_evidence"])
        self.assertEqual([], document["ancestors"], "ledger evidence names no ancestor")
        self.assertEqual("uninstall", document["body"]["operation"])
        self.assertEqual("retired", document["body"]["terminal_phase"])
        self.assertEqual("complete", document["body"]["effect_state"])
        self.assertEqual({"agent": "claude", "kind": "user"}, document["body"]["scope"])
        self.assertIsNone(document["body"]["archive_sha256"])
        self.assertEqual("checkout-tree", document["body"]["version_source"])
        self.assertIn("checkout", document["body"])
        # A root with no git metadata cannot be compared with any commit, so the flag fails toward
        # NOT-ASSERTED and the report says which observation was unavailable. The computed `False`
        # direction is proven on a real single-commit fixture in `CheckoutDirtiness`.
        self.assertIs(True, document["body"]["checkout"]["dirty"])
        self.assertEqual("unknown", document["body"]["checkout"]["commit"])
        self.assertIn("dirty=true", report)
        self.assertIn("no readable git metadata", report)
        self.assertEqual([], document["body"]["unknowns"], "no archive existed, so none is unknown")
        # The sealed document validates through the family's own checker, not just this module's eye.
        self.assertEqual("validated", dar.derive("validate", document, "the retirement")["verdict"])

    def test_a_link_published_row_is_retired_too_because_the_substrate_primitive_proves_it(self) -> None:
        """The shipped ``bundle install`` publishes links on Unix, so a legacy plane's rows are links."""
        payload = self.payload("link-payload")
        (payload / "agents").mkdir(parents=True)
        source = payload / "agents" / "sdlc-implementer.md"
        source.write_text("# implementer\n", encoding="utf-8")
        config = bundle.Config(payload, self.plane.home, self.plane.home / ".codex", "link", False, "claude", self.plane.state_root)
        state = bundle.load_config_state(config)
        entry = bundle.Entry("claude", "agent", "sdlc-implementer.md", source)
        destination = bundle.destination_for(entry, config)
        bundle.ensure_collection(entry, destination, config)
        mode = bundle.transactional_create(entry, destination, config, state)
        self.assertEqual("link", mode)
        self.assertTrue(destination.is_symlink())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertFalse(destination.exists() or destination.is_symlink())
        document = json.loads(
            sorted((self.plane.activation_root / "receipts").glob("*.json"))[0].read_text(encoding="utf-8")
        )
        row = document["body"]["entries"][0]
        self.assertEqual("removed", row["disposition"])
        # The row's OWN mode is what the receipt records: this is the fact per-row mode exists for.
        self.assertEqual("link", row["mode"])

    def test_a_modified_row_and_an_adopted_row_are_preserved_and_named(self) -> None:
        payload = self.payload("preserve-payload")
        activate_with_ownership_rows(self.plane, payload)
        implementer = self.plane.plane_root / "agents" / "sdlc-implementer.md"
        implementer.write_text("# the operator's own edit\n", encoding="utf-8")
        config = installer_write_config(self.plane, payload)
        state = bundle.load_config_state(config)
        skill_key = str(self.plane.plane_root / "skills" / "agentic-sdlc")
        adopted = dict(state["entries"][skill_key])
        adopted["removable"] = False
        candidate = json.loads(json.dumps(state))
        candidate["entries"][skill_key] = adopted
        bundle.persist_state(config, state, candidate)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertIn("modified-content", report)
        self.assertIn("kept-adopted", report)
        self.assertTrue(implementer.is_file(), "an operator's edit is preserved untouched")
        self.assertEqual(
            "# the operator's own edit\n", implementer.read_text(encoding="utf-8")
        )
        self.assertTrue((self.plane.plane_root / "skills" / "agentic-sdlc").is_dir())
        document = json.loads(
            sorted((self.plane.activation_root / "receipts").glob("*.json"))[0].read_text(encoding="utf-8")
        )
        self.assertEqual("none", document["body"]["effect_state"])
        self.assertEqual("not-activated", document["body"]["terminal_phase"])
        self.assertEqual(
            {"modified", "foreign"},
            {row["prestate"] for row in document["body"]["entries"]},
        )
        self.assertEqual({"preserved"}, {row["disposition"] for row in document["body"]["entries"]})

    def test_rows_under_another_configured_home_are_left_unselected(self) -> None:
        payload = self.payload("other-home-payload")
        other = Plane(self.temp / "other-operator")
        activate_with_ownership_rows(other, payload)
        # One shared state document, two homes: this run's boundary is its own home alone.
        shared = bundle.load_config_state(installer_read_config(other, payload))
        self.assertTrue(shared["entries"])
        code, report = self.plane.run(state_root=other.state_root)

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("no ownership rows under", report)
        after = bundle.load_config_state(installer_read_config(other, payload))
        self.assertEqual(shared["entries"], after["entries"], "another home's rows are retained")
        self.assertTrue((other.plane_root / "agents" / "sdlc-implementer.md").is_file())

    def test_a_project_root_s_rows_are_retired_at_project_scope(self) -> None:
        """The W-f half: ``--claude-home <repo>`` wrote unreceipted rows under a repository root."""
        payload = self.payload("project-payload")
        project = Plane(self.temp / "project-checkout")
        activate_with_ownership_rows(project, payload)
        # The rows are keyed under the project root, and the state root stays the operator's own.
        rows = bundle.load_config_state(installer_read_config(project, payload))["entries"]
        self.assertTrue(rows)

        code, report = self.plane.run(
            state_root=project.state_root,
            activation_root=project.state_root / "agentic-sdlc" / "activation",
            scope_kind="project",
            project_root=project.home,
        )

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertIn("legacy-unreceipted uninstall (no activation receipt for claude/project)", report)
        self.assertIn(f"project:{project.home}", report)
        self.assertFalse((project.plane_root / "agents" / "sdlc-implementer.md").exists())
        document = json.loads(
            sorted((project.state_root / "agentic-sdlc" / "activation" / "receipts").glob("*.json"))[0].read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            {"agent": "claude", "kind": "project", "root": str(project.home)}, document["body"]["scope"]
        )
        self.assertEqual("ledger", document["body"]["prestate_evidence"])
        self.assertEqual("validated", dar.derive("validate", document, "the retirement")["verdict"])

    def test_no_receipt_and_no_ownership_document_refuses_without_creating_anything(self) -> None:
        untouched = self.temp / "never-created"
        code, report = self.plane.run(
            state_root=untouched, activation_root=untouched / "agentic-sdlc" / "activation"
        )
        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("no installer ownership document", report)
        self.assertFalse(untouched.exists())

    def test_an_ownership_document_with_no_rows_for_this_scope_refuses_by_name(self) -> None:
        payload = self.payload("empty-rows")
        config = installer_write_config(self.plane, payload)
        bundle.persist_state(config, bundle.load_config_state(config), bundle.empty_state())
        self.assertTrue(config.state_path.is_file())

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("no ownership rows under", report)
        self.assertIn("is the front door", report)

    def test_a_second_ledger_retirement_of_one_assessment_is_refused_rather_than_repeated(self) -> None:
        payload = self.payload("second-pass")
        activate_with_ownership_rows(self.plane, payload)
        first_code, first_report = self.plane.run()
        self.assertEqual(first_code, EXIT_RETIRED, first_report)

        second_code, second_report = self.plane.run()

        # The rows are gone with the bytes, so the second pass has nothing to select and says so.
        self.assertEqual(second_code, EXIT_REFUSED, second_report)
        self.assertIn("no ownership rows under", second_report)

    def test_the_pointer_directed_path_wins_when_a_receipt_exists(self) -> None:
        """The ladder is ordered: a receipted plane never takes the announced legacy path."""
        payload = self.payload("both-paths")
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        self.assertNotIn("legacy-unreceipted uninstall", report)
        self.assertEqual(
            "activation-receipt", self.plane.terminal_receipt()["body"]["prestate_evidence"]
        )

    def test_the_distribution_version_is_read_from_one_file_and_a_missing_one_refuses(self) -> None:
        payload = self.payload("version-driver")
        activate_with_ownership_rows(self.plane, payload)
        scripts = self.temp / "no-driver" / "scripts"
        scripts.mkdir(parents=True)
        for name in (
            "distribution_activation_receipt.py",
            "install_skill_bundle.py",
            "ccodex_sdlc_host_planes.py",
        ):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        reader = scripts.parent / bundle.GIT_DETECTOR_RELATIVE
        reader.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / bundle.GIT_DETECTOR_RELATIVE, reader)

        code, report = self.plane.run(scripts_dir=scripts)

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn(target.VERSION_DRIVER_NAME, report)
        self.assertIn("could not name the version it retired", report)
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        # POSITIVE CONTROL: with the driver in place the same plane retires.
        driver = scripts.parent / target.VERSION_DRIVER_NAME
        driver.write_text(json.dumps({"current": "0.7.5"}), encoding="utf-8")
        code_two, report_two = self.plane.run(scripts_dir=scripts)
        self.assertEqual(code_two, EXIT_RETIRED, report_two)
        document = json.loads(
            sorted((self.plane.activation_root / "receipts").glob("*.json"))[0].read_text(encoding="utf-8")
        )
        self.assertEqual("0.7.5", document["body"]["resolved_version"])
        # No git metadata beside that driver, so the commit is the explicit unknown.
        self.assertEqual("unknown", document["body"]["checkout"]["commit"])
        # ... and dirty is TRUE for the same reason: with nothing to compare against, this flag fails
        # toward "not asserted", and the report names the missing observation rather than leaving the
        # boolean unattributable. `CheckoutDirtiness` proves the computed direction both ways.
        self.assertTrue(document["body"]["checkout"]["dirty"])
        self.assertIn("no readable git metadata", report_two)


class CheckoutDirtiness(LedgerFixtures, Harness):
    """``checkout.dirty`` is COMPUTED, and both directions are proven on one fixture.

    It was unconditionally ``true`` for one wave. What makes the ``false`` direction admissible is that
    it is a comparison rather than an assumption, so this class runs the same plane twice: once on a
    genuinely clean single-commit tree, and once after planting one modified byte in a tracked file.
    """

    def seal_from(self, distribution: Path, payload: Path) -> dict[str, Any]:
        code, report = self.plane.run(scripts_dir=distribution / "scripts")
        self.assertEqual(code, EXIT_RETIRED, report)
        document = json.loads(
            sorted((self.plane.activation_root / "receipts").glob("*.json"))[0].read_text(
                encoding="utf-8"
            )
        )
        self.report = report
        return document

    def test_a_clean_tree_seals_dirty_false_and_one_modified_file_seals_true(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("this host has no git to build a real metadata fixture with")
        distribution = self.distribution("clean-distribution")
        commit = self.commit_tree(distribution)

        payload = self.payload("dirty-clean")
        activate_with_ownership_rows(self.plane, payload)
        clean = self.seal_from(distribution, payload)

        self.assertEqual(commit, clean["body"]["checkout"]["commit"])
        self.assertFalse(clean["body"]["checkout"]["dirty"], "a clean tree may be asserted clean")
        self.assertIn("dirty=false", self.report)
        self.assertIn("the git index tracks matches the worktree", self.report)
        # The receipt is still a checkout body: null archive digest, checkout-tree version source.
        self.assertIsNone(clean["body"]["archive_sha256"])
        self.assertEqual("checkout-tree", clean["body"]["version_source"])

        # THE OTHER DIRECTION, on the same fixture: one tracked file's content moves.
        # The sealed receipt is removed first because a ledger retirement's id is derived from its plan
        # digest, and the plan for the re-planted rows is byte-identical -- so the second run would be
        # refused as "a second retirement of one assessed plane", which is a DIFFERENT control (proven
        # in its own test). Resetting it here keeps this test about the dirty computation.
        for sealed in sorted((self.plane.activation_root / "receipts").glob("*.json")):
            sealed.unlink()
        (distribution / "tracked.txt").write_text("planted\n", encoding="utf-8")
        second_payload = self.payload("dirty-modified")
        activate_with_ownership_rows(self.plane, second_payload)
        modified = self.seal_from(distribution, second_payload)

        self.assertEqual(commit, modified["body"]["checkout"]["commit"], "the commit did not move")
        self.assertTrue(modified["body"]["checkout"]["dirty"], "a modified tracked path is dirty")
        self.assertIn("dirty=true", self.report)
        self.assertIn("'tracked.txt' differs in content from the index", self.report)

    def test_the_detector_answers_dirty_for_every_shape_it_cannot_compare(self) -> None:
        """A staged change, an unparseable index, and absent metadata each fail toward NOT-asserted.

        The staged case is the one that matters most: the worktree and the index agree with each other
        while both differ from the commit, so a detector that compared only those two would call it
        clean. The cache-tree root is what catches it, and this is where that claim is checked.
        """
        if shutil.which("git") is None:
            self.skipTest("this host has no git to build a real metadata fixture with")
        distribution = self.distribution("shapes")
        self.commit_tree(distribution)
        clean, reason = detector.observe_dirty(distribution)
        self.assertFalse(clean, reason)

        # A rewrite that changes only mtime is NOT dirty: content is hashed, never stat data.
        (distribution / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        os.utime(distribution / "tracked.txt", (0, 0))
        unchanged, reason = detector.observe_dirty(distribution)
        self.assertFalse(unchanged, reason)

        (distribution / "tracked.txt").write_text("staged\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "tracked.txt"],
            cwd=distribution,
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
            check=True,
            capture_output=True,
        )
        staged, reason = detector.observe_dirty(distribution)
        self.assertTrue(staged, "a staged-but-uncommitted change may not be asserted clean")
        self.assertIn("cache-tree root", reason)

        index = distribution / ".git" / "index"
        index.write_bytes(b"NOTDIRC" + index.read_bytes()[7:])
        unparseable, reason = detector.observe_dirty(distribution)
        self.assertTrue(unparseable)
        self.assertIn("not a shape this reader parses", reason)

        shutil.rmtree(distribution / ".git")
        absent, reason = detector.observe_dirty(distribution)
        self.assertTrue(absent)
        self.assertIn("no readable git metadata", reason)


class LedgerPreview(LedgerFixtures, Harness):
    """``--dry-run`` on both admission rungs: the plan is rendered and nothing is touched."""

    def test_a_preview_renders_the_plan_and_removes_nothing_on_either_rung(self) -> None:
        payload = self.payload("preview")
        entries = activate_with_ownership_rows(self.plane, payload)
        implementer = self.plane.plane_root / "agents" / "sdlc-implementer.md"
        before = implementer.read_bytes()

        code, report = self.plane.run(dry_run=True)

        self.assertEqual(code, target.EXIT_PREVIEWED, report)
        self.assertIn("--dry-run: nothing was removed", report)
        self.assertIn("admission: ledger", report)
        self.assertIn("would remove 'agents/sdlc-implementer.md'", report)
        self.assertEqual(before, implementer.read_bytes(), "the preview touched no byte")
        self.assertFalse((self.plane.activation_root / "receipts").exists())
        self.assertFalse((self.plane.activation_root / "journals").exists())
        # The ownership rows survive a preview, which is what makes the real run below possible.
        state = bundle.load_config_state(installer_read_config(self.plane, payload))
        self.assertNotEqual({}, state["entries"])

        # The receipt-directed rung previews too, and names the pointer that admitted it.
        self.plane.seal_active(entries)
        receipted_code, receipted_report = self.plane.run(dry_run=True)
        self.assertEqual(receipted_code, target.EXIT_PREVIEWED, receipted_report)
        self.assertIn("admission: activation-receipt", receipted_report)
        self.assertIn(str(self.plane.pointer), receipted_report)
        self.assertTrue(implementer.is_file())
        self.assertFalse((self.plane.activation_root / "receipts").exists())

        # POSITIVE CONTROL: the same plane, run for real, does every one of those things.
        real_code, real_report = self.plane.run()
        self.assertEqual(real_code, EXIT_RETIRED, real_report)
        self.assertFalse(implementer.exists())
        self.assertEqual(
            "activation-receipt", self.plane.terminal_receipt()["body"]["prestate_evidence"]
        )

    def test_a_preview_leaves_the_legacy_pointer_where_it_found_it(self) -> None:
        """The migration is a write, so a preview reports it as pending instead of performing it."""
        payload = self.payload("preview-legacy")
        entries = activate_with_ownership_rows(self.plane, payload)
        self.plane.seal_active(entries)
        legacy = self.plane.legacy_pointer
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_bytes(self.plane.active_bytes())
        self.plane.pointer.unlink()

        code, report = self.plane.run(dry_run=True)

        self.assertEqual(code, target.EXIT_PREVIEWED, report)
        self.assertIn("would be re-filed at", report)
        self.assertTrue(legacy.is_file(), "the preview left the legacy pointer alone")
        self.assertFalse(self.plane.pointer.exists(), "and wrote no keyed pointer")
        # POSITIVE CONTROL: the real run performs the migration the preview only described.
        real_code, real_report = self.plane.run()
        self.assertEqual(real_code, EXIT_RETIRED, real_report)
        self.assertFalse(legacy.exists())


# ---- refusals ------------------------------------------------------------------------------------


class Refusals(Harness):
    def assert_nothing_removed(self) -> None:
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        self.assertTrue((self.plane.plane_root / "skills" / "agentic-sdlc").is_dir())
        self.assertFalse((self.plane.activation_root / "receipts").exists())
        self.assertFalse((self.plane.activation_root / "journals").exists())

    def test_an_absent_receipt_refuses_by_name_rather_than_guessing_from_the_directory(self) -> None:
        """No pointer AND no ownership document: the ladder runs out of rungs and says which ones.

        The refusal names the pointer it looked for, the ownership document it looked for, and the
        front door -- rather than reconstructing a candidate set from directory contents, which is the
        guess this verb does not make.  A plane with ownership rows but no receipt is a DIFFERENT
        state: it takes the announced legacy-unreceipted path, which `LegacyUnreceipted` covers.
        """
        self.plant_owned()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("found no activation receipt for claude/user", report)
        self.assertIn("no installer ownership document", report)
        self.assertIn("is the front door", report)
        self.assert_nothing_removed()

    def test_a_refusal_creates_no_directory_at_all_under_the_state_root(self) -> None:
        """The dispatcher's own grammar test asserts a refused mutating verb writes no state."""
        self.plane.seal_active(self.plant_owned())
        untouched = self.temp / "never-created"

        code, report = self.plane.run(state_root=untouched, activation_root=untouched / "agentic-sdlc" / "activation")

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertFalse(untouched.exists())
        # Positive control: the same run DOES create the receipt and journal directories once it is
        # admitted, so the absence above is the refusal and not an inert code path.
        code_two, report_two = self.plane.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)
        self.assertTrue((self.plane.activation_root / "receipts").is_dir())
        self.assertTrue((self.plane.activation_root / "journals").is_dir())

    def test_a_tampered_seal_refuses_and_removes_nothing(self) -> None:
        receipt = self.plane.seal_active(self.plant_owned())
        tampered = json.loads(json.dumps(receipt))
        tampered["body"]["resolved_version"] = "9.9.9"
        self.plane.write_active(tampered)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("does not validate as", report)
        self.assert_nothing_removed()
        # Positive control: the untampered bytes DO retire, so the refusal came from the tamper.
        self.plane.write_active(receipt)
        code_two, report_two = self.plane.run()
        self.assertEqual(code_two, EXIT_RETIRED, report_two)

    def test_a_receipt_that_already_records_a_retirement_is_refused(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(
            [entry_record(row["entry_name"], None, prestate="owned", disposition="removed") for row in entries],
            operation="uninstall",
            # A v2 retirement body carries the closed prestate-evidence discriminator; this one names
            # the receipt it retired, which the fixture's single `derived-from` ancestor supplies.
            prestate_evidence="activation-receipt",
            terminal_phase="retired",
        )

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("only ['install', 'update'] describe a live activation", report)
        self.assert_nothing_removed()

    def test_a_receipt_that_never_activated_is_refused(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(
            [entry_record(row["entry_name"], row["content_sha256"], prestate="owned", disposition="preserved") for row in entries],
            effect_state="none",
            terminal_phase="not-activated",
        )

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("terminates 'not-activated'", report)
        self.assert_nothing_removed()

    def test_an_already_retired_activation_refuses_a_second_pass(self) -> None:
        entries = self.plant_owned()
        receipt = self.plane.seal_active(entries)
        first, first_report = self.plane.run()
        self.assertEqual(first, EXIT_RETIRED, first_report)
        # Replant the entries so a second pass would have something to delete if it ran at all.
        self.plant_owned()
        self.plane.write_active(receipt)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("already carries the terminal receipt", report)
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())

    def test_off_linux_refuses_by_name_before_reading_anything(self) -> None:
        self.plane.seal_active(self.plant_owned())

        for system in ("Darwin", "Windows"):
            with self.subTest(system=system):
                code, report = self.plane.run(platform_system=system)
                self.assertEqual(code, EXIT_REFUSED, report)
                self.assertIn("certified on Linux only", report)
                self.assertIn(system, report)
                self.assert_nothing_removed()
        # Positive control: the identical plane retires on the supported platform.
        code, report = self.plane.run(platform_system="Linux")
        self.assertEqual(code, EXIT_RETIRED, report)

    def test_a_linked_active_receipt_is_refused(self) -> None:
        receipt = self.plane.seal_active(self.plant_owned())
        real = self.temp / "elsewhere-receipt.json"
        real.write_bytes(dar.canonical_bytes(receipt))
        active = self.plane.pointer
        active.unlink()
        active.symlink_to(real)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("is a link", report)
        self.assert_nothing_removed()

    def test_a_non_finite_number_in_the_receipt_is_refused_rather_than_overflowed(self) -> None:
        self.plant_owned()
        active = self.plane.pointer
        active.parent.mkdir(parents=True, exist_ok=True)
        # `1e400` never reaches `parse_constant`: json overflows it to inf inside the float parser.
        active.write_text('{"body": {"plan_sha256": 1e400}}', encoding="utf-8")

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("non-finite number", report)
        self.assert_nothing_removed()
        # Finite control: the same surrounding document shape refuses for a DIFFERENT named reason,
        # so the exit above came from the overflow and not from the shape.
        active.write_text('{"body": {"plan_sha256": 1e30}}', encoding="utf-8")
        code_two, report_two = self.plane.run()
        self.assertEqual(code_two, EXIT_REFUSED, report_two)
        self.assertNotIn("non-finite number", report_two)

    def test_a_repeated_json_key_in_the_receipt_is_refused(self) -> None:
        self.plant_owned()
        active = self.plane.activation_root / "active-receipt.json"
        active.write_text('{"receipt_id": "a", "receipt_id": "b"}', encoding="utf-8")

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("repeats the JSON key", report)
        self.assert_nothing_removed()

    def test_an_argument_vector_this_verb_does_not_accept_is_refused_before_any_effect(self) -> None:
        self.plane.seal_active(self.plant_owned())

        # Every vector the dispatcher would never forward, refused BEFORE this module resolves any
        # configuration -- which is also what keeps this test off the operator's real home, since
        # `default_config` is never reached (agentic-sdlc-8dca).
        for vector in (
            ["--all"],
            ["uninstall"],
            [""],
            [],
            ["--host"],
            ["--host", "gemini"],
            ["--host", "claude", "extra"],
            ["--host=claude"],
        ):
            with self.subTest(vector=vector):
                code, report = capture(lambda: target.main(list(vector)))
                self.assertEqual(code, EXIT_REFUSED, report)
                self.assertIn("admits exactly ['--host', <claude|codex>]", report)
        self.assert_nothing_removed()

    def test_a_read_only_guarded_process_refuses_before_any_effect(self) -> None:
        self.plane.seal_active(self.plant_owned())

        class FakeGuard:
            _INSTALLED = True

        saved = sys.modules.get("_ccodex_sdlc_readonly_guard")
        sys.modules["_ccodex_sdlc_readonly_guard"] = FakeGuard  # type: ignore[assignment]
        try:
            code, report = capture(lambda: target.main(["--host", "claude"]))
            self.assertIn("already installed the read-only guard", report)
        finally:
            if saved is None:
                del sys.modules["_ccodex_sdlc_readonly_guard"]
            else:
                sys.modules["_ccodex_sdlc_readonly_guard"] = saved
        self.assertEqual(code, EXIT_REFUSED)
        self.assert_nothing_removed()


# ---- rendering and data loss ---------------------------------------------------------------------


class RenderingAndDataLoss(Harness):
    def test_a_control_character_in_an_inherited_detail_never_reaches_a_rendered_line(self) -> None:
        """The family admits any text in a `detail`; a terminal is not a receipt.

        The entry NAME cannot carry a control character through a validated receipt -- the family's own
        name class refuses one, asserted here as the control -- so the artifact-derived string that can
        reach a line is the free-text detail of a recorded unknown.
        """
        entries = self.plant_owned()
        hostile = "planted\r\x1b[2Jcleared\nforged: line"
        self.plane.seal_active(
            entries,
            effect_state="partial",
            terminal_phase="activated-partial",
            unknowns=[{"detail": hostile, "observation": "archive-digest", "subject": "archive_sha256"}],
            archive_sha256=None,
        )

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        for raw in ("\r", "\x1b"):
            self.assertNotIn(raw, report)
        self.assertIn("planted\\r\\x1b[2Jcleared\\nforged: line", report)
        # The terminal receipt names the same gap in the producer's own words rather than copying the
        # observed text, and the STORED source keeps every character verbatim.
        self.assertEqual(
            [(row["observation"], row["subject"]) for row in self.plane.terminal_receipt()["body"]["unknowns"]],
            [("archive-digest", "archive_sha256")],
        )
        self.assertEqual(
            json.loads(self.plane.pointer.read_text(encoding="utf-8"))["body"]["unknowns"][0]["detail"],
            hostile,
        )
        # Control: the family refuses the same characters in an entry NAME, so the line above is the
        # only artifact channel that needed escaping.
        refused = dar.derive("seal", unsealed_document([entry_record("agents/forged\rline.md", hexof("x"))]), "obs")
        self.assertEqual(refused["verdict"], "refused")

    def test_the_receipt_inventory_carries_every_entry_the_walk_observed(self) -> None:
        """The dict-literal evaluation-order defect: an inventory assembled before the walk is empty."""
        entries = self.plant_owned()
        for index in range(4):
            name = f"agents/extra-{index}.md"
            self.plane.write_file(name, f"# extra {index}\n")
            entries.append(entry_record(name, self.plane.entry_digest(name)))
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_RETIRED, report)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(len(body["entries"]), len(entries))
        self.assertEqual(
            sorted(row["entry_name"] for row in body["entries"]),
            sorted(row["entry_name"] for row in entries),
        )
        self.assertTrue(all(row["disposition"] == "removed" for row in body["entries"]))

    def test_a_receipt_whose_own_archive_digest_is_unknown_cannot_report_a_complete_retirement(self) -> None:
        entries = self.plant_owned()
        self.plane.seal_active(
            entries,
            archive_sha256=None,
            # The family refuses `complete` beside any unknown, so an activation with an unobserved
            # archive digest is itself partial: this fixture is the shape that actually exists.
            effect_state="partial",
            terminal_phase="activated-partial",
            unknowns=[
                {
                    "detail": "the archive digest could not be taken during activation",
                    "observation": "archive-digest",
                    "subject": "archive_sha256",
                }
            ],
        )

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_PARTIAL, report)
        self.assertFalse((self.plane.plane_root / "agents" / "sdlc-implementer.md").exists())
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "partial")
        self.assertEqual(body["terminal_phase"], "unknown")
        self.assertEqual(dar.derive("validate", self.plane.terminal_receipt(), "receipt")["verdict"], "validated")
        self.assertIn("records archive-digest as unknown", report)


# ---- the dispatcher's contract -------------------------------------------------------------------


class DispatchContract(unittest.TestCase):
    def load_as_the_dispatcher_does(self) -> Any:
        spec = importlib.util.spec_from_file_location("_ccodex_sdlc_lifecycle_uninstall", MODULE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_the_module_is_a_physical_non_symlink_sibling_of_the_reader(self) -> None:
        self.assertTrue(MODULE.is_file())
        self.assertFalse(MODULE.is_symlink())
        self.assertEqual(MODULE.parent, READER.parent)

    def test_main_is_callable_and_returns_an_admitted_exit_class_that_is_not_a_bool(self) -> None:
        module = self.load_as_the_dispatcher_does()
        self.assertTrue(callable(module.main))
        with _temporary_directory() as temp:
            plane = Plane(Path(temp))
            plane.seal_active([entry_record("agents/one.md", hexof("one"))])
            result, _report = capture(lambda: module.execute(bundle, dar, plane.config()))
        self.assertIsInstance(result, int)
        self.assertNotIsInstance(result, bool)
        self.assertTrue(0 <= result <= 4)

    def test_the_reader_dispatches_this_verb_to_this_module(self) -> None:
        from scripts import ccodex_sdlc as reader

        self.assertEqual(reader.LIFECYCLE_VERBS["uninstall"], "ccodex_sdlc_uninstall")
        self.assertEqual(reader.lifecycle_module_path("uninstall"), MODULE)

    def test_the_exit_table_is_the_closed_set_the_dispatcher_admits(self) -> None:
        module = self.load_as_the_dispatcher_does()
        table = [module.EXIT_RETIRED, module.EXIT_PARTIAL, module.EXIT_REFUSED, module.EXIT_UNKNOWN]
        self.assertEqual(table, [EXIT_RETIRED, EXIT_PARTIAL, EXIT_REFUSED, EXIT_UNKNOWN])
        # Decision 9 has ONE class for both admitted-effect states, so 4 appears twice; the one
        # class it must NEVER carry is 1, and no name on this module resolves to it.
        self.assertNotIn(1, table)
        self.assertFalse(hasattr(module, "EXIT_ATTENTION"))
        for value in table:
            self.assertIsInstance(value, int)
            self.assertNotIsInstance(value, bool)

    def test_the_module_runs_under_the_bound_interpreter_without_writing_bytecode(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(MODULE), "--help"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, EXIT_REFUSED, completed.stderr)
        self.assertIn("admits exactly ['--host', <claude|codex>]", completed.stderr)
        self.assertEqual(completed.stdout, "")


# ---- the boundary this module must not cross -----------------------------------------------------


def executable_source(path: Path) -> str:
    """The module's CODE with every docstring removed.

    A prose scan is not a code scan: this module's own documentation says the words ``--all`` and
    ``purge`` in order to state that it has neither, and a grep over the raw bytes would read that
    sentence as the surface it forbids. Stripping docstrings keeps the assertion about behaviour.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                body[0] = ast.Expr(value=ast.Constant(value=None))
    return ast.unparse(ast.fix_missing_locations(tree))


class Boundary(unittest.TestCase):
    def test_the_module_declares_no_wildcard_purge_or_all_surface(self) -> None:
        code = executable_source(MODULE)
        for forbidden in ("--all", "purge", "rmtree", "glob(", "iterdir", "os.walk"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        # Positive control: the docstring-stripping did not empty the source it scanned.
        self.assertIn("def remove_one", code)
        self.assertIn("rename_absent", code)

    def test_the_module_never_reads_a_credential_or_settings_path(self) -> None:
        code = executable_source(MODULE)
        for forbidden in (".credentials.json", "settings.json", "apiKeyHelper", "ANTHROPIC", "sk-ant"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_the_module_states_no_release_claim(self) -> None:
        code = executable_source(MODULE)
        self.assertIn("'public_channel': None", code)
        self.assertIn("'release_claim': 'none'", code)

    def test_the_reused_names_are_exactly_the_ones_the_installer_exports(self) -> None:
        for name in (
            "digest",
            "path_present",
            "is_junction",
            "remove_path",
            "rename_absent",
            "reserve_private_artifact",
            "fsync_directory",
            "durable_mkdir",
            "flush_descriptor",
            "write_state",
            "installer_lock",
            "state_directory",
            "Config",
            "InstallerError",
            # The ownership-row retirement (agentic-sdlc-42ec) reuses the installer's own state
            # machinery rather than a private spelling of it.
            "load_config_state",
            "validate_state",
            "destination_is_configured",
            "entry_matches_record",
            "arm_pending",
            "commit_pending",
            "resolved_pending_state",
            "persist_state",
            "recover_pending",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(bundle, name), f"install_skill_bundle exports no {name}")

    def test_the_read_only_guards_pinned_mutator_set_still_covers_the_reused_writers(self) -> None:
        """The guard pins anticipated mutator names; the two this module reuses must stay in it."""
        source = (ROOT / "scripts" / "ccodex_sdlc_readonly.py").read_text(encoding="utf-8")
        for name in ('"write_state"', '"persist_state"', '"installer_lock"'):
            with self.subTest(name=name):
                self.assertIn(name, source)


class PlatformFloor(unittest.TestCase):
    def test_the_supported_platform_is_the_one_this_host_reports(self) -> None:
        if platform.system() != "Linux":
            self.skipTest("this suite exercises the Linux-only lifecycle floor")
        self.assertEqual(target.SUPPORTED_PLATFORM, platform.system())

    def test_every_class_maps_to_one_prestate_and_one_reason(self) -> None:
        self.assertEqual(sorted(target.CLASSES), sorted(target.CLASS_PRESTATE))
        self.assertEqual(sorted(target.CLASSES), sorted(target.CLASS_REASON))
        self.assertEqual(
            sorted(set(target.CLASS_PRESTATE.values())), sorted({"absent", "foreign", "modified", "owned"})
        )
        for value in target.CLASS_PRESTATE.values():
            self.assertIn(value, dar.PRESTATES)
        # `owned-exact` is the ONLY class that maps to `owned`, so no other class can be removed.
        owned = [name for name, prestate in target.CLASS_PRESTATE.items() if prestate == "owned"]
        self.assertEqual(owned, ["owned-exact"])

    def test_the_terminal_phases_this_module_uses_are_admitted_for_uninstall(self) -> None:
        for phase in ("retired", "not-activated", "unknown"):
            self.assertIn(phase, dar.OPERATION_PHASES["uninstall"])
        self.assertNotIn("activated", dar.OPERATION_PHASES["uninstall"])
        self.assertEqual(dar.OPERATION_DISPOSITIONS["uninstall"], ("preserved", "removed"))
        self.assertEqual(dar.EFFECT_PHASES["complete"], ("activated", "retired"))
        self.assertEqual(dar.EFFECT_PHASES["partial"], ("activated-partial", "unknown"))
        self.assertEqual(dar.EFFECT_PHASES["none"], ("not-activated",))
        self.assertEqual(dar.EFFECT_PHASES["unknown"], ("unknown",))


if __name__ == "__main__":
    unittest.main()
