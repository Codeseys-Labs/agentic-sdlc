"""Tests for ``scripts/ccodex_sdlc_uninstall.py``: receipt-directed retirement with ownership proof.

Seven kinds of test live here, and they check different things.

The END-TO-END tests plant a temporary home and state root, seal a real
``distribution-activation@1`` receipt over the planted entries with the family's own producer, run
the retirement, and then assert both halves: the owned entries are gone AND the terminal receipt the
run wrote validates through that same family checker.  The independent verifier is the point -- this
module composes a body rather than re-implementing one, so a test that only asked this module whether
its own output looked right would prove nothing about the receipt it claims to seal.

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
import platform
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ccodex_sdlc_uninstall as target  # noqa: E402
from scripts import distribution_activation_receipt as dar  # noqa: E402
from scripts import install_skill_bundle as bundle  # noqa: E402

MODULE = ROOT / "scripts" / "ccodex_sdlc_uninstall.py"
READER = ROOT / "scripts" / "ccodex_sdlc.py"

RECEIPT_KIND = "distribution-activation"
BODY_SCHEMA = "agentic-sdlc/distribution-activation-body@1"
ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"

#: The exit classes, spelled out here rather than imported from the module under test, so a table this
#: module quietly renumbered would fail rather than agree with itself.
EXIT_RETIRED = 0
EXIT_ATTENTION = 1
EXIT_REFUSED = 3
EXIT_UNKNOWN = 4

INSTANT = "2026-08-20T12:00:00Z"


def hexof(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def unsealed_body(entries: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    """One unsealed activation body whose defaults seal clean, with every field overridable."""
    value: dict[str, Any] = {
        "activation_scope": "user-plane",
        "archive_sha256": hexof("archive"),
        "candidate_id": hexof("candidate"),
        "effect_state": "complete",
        "entries": entries,
        "host": "claude",
        "journal_sha256": hexof("journal"),
        "operation": "install",
        "plan_sha256": hexof("plan"),
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "requested_version": "0.7.3",
        "resolved_version": "0.7.3",
        "schema_version": BODY_SCHEMA,
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

    def write_active(self, receipt: dict[str, Any]) -> Path:
        path = self.activation_root / "active-receipt.json"
        path.write_bytes(dar.canonical_bytes(receipt))
        return path

    def active_bytes(self) -> bytes:
        return (self.activation_root / "active-receipt.json").read_bytes()

    # ---- running -------------------------------------------------------------------------------

    def config(self, **overrides: Any) -> target.Config:
        values: dict[str, Any] = {
            "scripts_dir": ROOT / "scripts",
            "home": self.home,
            "state_root": self.state_root,
            "activation_root": self.activation_root,
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


def entry_record(name: str, digest_value: Any, *, prestate: str = "absent", disposition: str = "installed") -> dict[str, Any]:
    return {
        "content_sha256": digest_value,
        "disposition": disposition,
        "entry_name": name,
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


class OwnershipProof(Harness):
    def test_a_modified_entry_is_preserved_byte_for_byte_while_an_owned_one_is_removed(self) -> None:
        entries = self.plant_owned()
        modified = self.plane.write_file("agents/sdlc-reviewer.md", "# reviewer\n")
        entries.append(entry_record("agents/sdlc-reviewer.md", hexof("a digest nothing on disk has")))
        self.plane.seal_active(entries)
        before = modified.read_bytes()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_ATTENTION, report)
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

        self.assertEqual(code, EXIT_ATTENTION, report)
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

        self.assertEqual(code, EXIT_ATTENTION, report)
        self.assertTrue((real / "nested" / "thing.md").is_file())
        self.assertIn("preserved: commands/nested/thing.md (retargeted-parent:", report)
        self.assertIn("removed: agents/sdlc-implementer.md", report)

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

        self.assertEqual(code, EXIT_ATTENTION, report)
        self.assertEqual(unprovable.read_bytes(), before)
        self.assertIn("preserved: agents/sdlc-planner.md (unprovable-inventory:", report)
        self.assertIn("inherited unknown: entry-content about agents/sdlc-planner.md", report)
        self.assertIn("removed: agents/sdlc-implementer.md", report)

    def test_an_absent_entry_is_noted_absent_and_the_run_does_not_claim_a_clean_retirement(self) -> None:
        entries = self.plant_owned()
        entries.append(entry_record("agents/sdlc-cartographer.md", hexof("never planted")))
        self.plane.seal_active(entries)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_ATTENTION, report)
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

        self.assertEqual(code, EXIT_ATTENTION, report)
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

        self.assertEqual(code, EXIT_ATTENTION, report)
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

        self.assertEqual(code, EXIT_ATTENTION, report)
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        self.assertFalse((self.plane.plane_root / "skills" / "agentic-sdlc").exists())
        self.assertIn("could not be quarantined, so it was preserved untouched", report)
        body = self.plane.terminal_receipt()["body"]
        self.assertEqual(body["effect_state"], "partial")


# ---- refusals ------------------------------------------------------------------------------------


class Refusals(Harness):
    def assert_nothing_removed(self) -> None:
        self.assertTrue((self.plane.plane_root / "agents" / "sdlc-implementer.md").is_file())
        self.assertTrue((self.plane.plane_root / "skills" / "agentic-sdlc").is_dir())
        self.assertFalse((self.plane.activation_root / "receipts").exists())
        self.assertFalse((self.plane.activation_root / "journals").exists())

    def test_an_absent_receipt_refuses_by_name_rather_than_guessing_from_the_directory(self) -> None:
        self.plant_owned()

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("found no active distribution-activation receipt", report)
        self.assertIn("nothing to reconstruct it from", report)
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
        active = self.plane.activation_root / "active-receipt.json"
        active.unlink()
        active.symlink_to(real)

        code, report = self.plane.run()

        self.assertEqual(code, EXIT_REFUSED, report)
        self.assertIn("is a link", report)
        self.assert_nothing_removed()

    def test_a_non_finite_number_in_the_receipt_is_refused_rather_than_overflowed(self) -> None:
        self.plant_owned()
        active = self.plane.activation_root / "active-receipt.json"
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

        for vector in (["--all"], ["--host", "claude"], ["uninstall"], [""]):
            with self.subTest(vector=vector):
                code, report = capture(lambda: target.main(list(vector)))
                self.assertEqual(code, EXIT_REFUSED, report)
                self.assertIn("accepts no arguments", report)
        self.assert_nothing_removed()

    def test_a_read_only_guarded_process_refuses_before_any_effect(self) -> None:
        self.plane.seal_active(self.plant_owned())

        class FakeGuard:
            _INSTALLED = True

        saved = sys.modules.get("_ccodex_sdlc_readonly_guard")
        sys.modules["_ccodex_sdlc_readonly_guard"] = FakeGuard  # type: ignore[assignment]
        try:
            code, report = capture(lambda: target.main([]))
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

        self.assertEqual(code, EXIT_ATTENTION, report)
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
            json.loads((self.plane.activation_root / "active-receipt.json").read_text(encoding="utf-8"))["body"][
                "unknowns"
            ][0]["detail"],
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

        self.assertEqual(code, EXIT_ATTENTION, report)
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
        table = [module.EXIT_RETIRED, module.EXIT_ATTENTION, module.EXIT_REFUSED, module.EXIT_UNKNOWN]
        self.assertEqual(table, [EXIT_RETIRED, EXIT_ATTENTION, EXIT_REFUSED, EXIT_UNKNOWN])
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
        self.assertIn("accepts no arguments", completed.stderr)
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
