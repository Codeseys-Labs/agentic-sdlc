"""The receipt shim's seal, its re-hash obligation, and the real consumer's admission of its output.

The last class is the point of the module: ``ccodex_sdlc_install``'s OWN ``admit_payload`` is run
against a root and a receipt this shim produced, so the producer/consumer contract is proven by the
consumer's code rather than by two hand-written constant tables agreeing with each other.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "write_acquisition_receipt.py"
INSTALL_PATH = ROOT / "scripts" / "ccodex_sdlc_install.py"
RELEASE_CONTRACT_PATH = ROOT / "policy" / "release-contract.v1.json"
INSTANT = "2026-08-20T12:13:14Z"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


shim = _load(MODULE_PATH, "write_acquisition_receipt_under_test")
install = _load(INSTALL_PATH, "write_acquisition_receipt_consumer")

PAYLOAD = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha\n",
    "skills/alpha-skill/references/notes.md": "notes\n",
    "agents/claude/cartographer.md": "cartographer\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame\n",
}


def inventory_for_tree(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        item = path.lstat()
        if path.is_symlink():
            target = os.readlink(path)
            rows.append(
                {"mode": 0o777, "path": relative, "size": len(target.encode()), "target": target, "type": "symlink"}
            )
        elif path.is_dir():
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


class ShimFixture(unittest.TestCase):
    """One acquisition layout: a candidate root at the layout path plus a separate state home."""

    ARCHIVE_BYTES = b"fabricated-archive-bytes"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Resolved so the layout the consumer derives from this data home matches the physical
        # candidate-root path the producer records: on macOS the unresolved `/var/folders/...`
        # spelling differs from the recorded `/private/var/...` one and `admit_candidate_root`
        # refuses the pair as an out-of-layout payload.
        base = Path(self.temporary.name).resolve()
        self.state_home = base / "state"
        self.data_home = base / "data"
        self.home = base / "operator-home"
        self.installer_state_root = base / "installer-state"
        for directory in (self.state_home, self.data_home, self.home, self.installer_state_root):
            directory.mkdir()
        self.archive = base / "agentic-sdlc-0.7.3.tar.gz"
        self.archive.write_bytes(self.ARCHIVE_BYTES)
        self.archive_sha256 = hashlib.sha256(self.ARCHIVE_BYTES).hexdigest()
        self.candidate_root = self.data_home.joinpath(
            *shim.CANDIDATE_SEGMENTS, self.archive_sha256, shim.CANDIDATE_LEAF
        )
        self.candidate_root.mkdir(parents=True)
        for relative, text in PAYLOAD.items():
            path = self.candidate_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        contract_path = self.candidate_root / "policy" / "release-contract.v1.json"
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_bytes(
            shim.canonical(json.loads(RELEASE_CONTRACT_PATH.read_text(encoding="utf-8")))
        )
        self.write_manifest()

    def write_manifest(self, **overrides: object) -> dict[str, object]:
        manifest: dict[str, object] = {
            "archive_root": "agentic-sdlc-0.7.3",
            "artifact_kind": "unpublished-candidate",
            "candidate_id": hashlib.sha256(b"fabricated-candidate").hexdigest(),
            "inventory": inventory_for_tree(self.candidate_root),
            "platform": "linux-x64",
            "product_version": "0.7.3",
            "public_channel": None,
            "release_claim": "none",
            "schema_version": "release-candidate/v1",
            "support_tier": "unsupported",
        }
        manifest.update(overrides)
        (self.candidate_root / "manifest.json").write_bytes(shim.canonical(manifest))
        return manifest

    def seal(self, **overrides: object) -> Path:
        arguments: dict[str, object] = {
            "root": self.candidate_root,
            "state_home": self.state_home,
            "archive": self.archive,
            "archive_sha256": None,
            "operation_id": None,
            "installed_at": INSTANT,
        }
        arguments.update(overrides)
        return shim.write_receipt(**arguments)  # type: ignore[arg-type]

    def receipt(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding="utf-8"))


class SealTest(ShimFixture):
    def test_the_receipt_lands_at_the_layout_path_and_reseals_to_its_own_digest(self) -> None:
        path = self.seal()
        self.assertEqual(
            path, self.state_home.joinpath(*shim.RECEIPT_SEGMENTS, f"{self.archive_sha256}.json")
        )
        receipt = self.receipt(path)
        self.assertEqual(tuple(sorted(receipt)), tuple(sorted(shim.RECEIPT_KEYS)))
        for key, value in shim.RECEIPT_CONSTANTS.items():
            self.assertEqual(receipt[key], value)
        body = {key: value for key, value in receipt.items() if key != "record_sha256"}
        self.assertEqual(
            receipt["record_sha256"], hashlib.sha256(shim.canonical(body)).hexdigest()
        )
        # Positive control: the seal is over the body, so a changed field breaks the same derivation.
        body["installed_at"] = "2026-08-20T12:13:15Z"
        self.assertNotEqual(
            receipt["record_sha256"], hashlib.sha256(shim.canonical(body)).hexdigest()
        )

    def test_the_derived_digests_are_re_derivable_from_the_root(self) -> None:
        receipt = self.receipt(self.seal())
        manifest_bytes = (self.candidate_root / "manifest.json").read_bytes()
        self.assertEqual(receipt["plan_sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        digests = {
            row["path"]: row["sha256"]
            for row in json.loads(manifest_bytes.decode("utf-8"))["inventory"]
            if row["type"] == "file"
        }
        self.assertEqual(
            receipt["journal_sha256"],
            hashlib.sha256(shim.canonical({"verified": digests})).hexdigest(),
        )
        self.assertEqual(receipt["archive_sha256"], self.archive_sha256)
        self.assertEqual(
            receipt["candidate_root_absolute_physical_path"],
            os.path.realpath(self.candidate_root),
        )

    def test_the_same_root_seals_identically_twice(self) -> None:
        path = self.seal()
        first = self.receipt(path)
        path.unlink()
        second = self.receipt(self.seal())
        self.assertEqual(first, second)

    def test_a_sealed_receipt_is_never_replaced(self) -> None:
        self.seal()
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("already exists", str(raised.exception))

    def test_an_explicit_digest_and_an_archive_are_mutually_exclusive(self) -> None:
        for overrides in (
            {"archive": None, "archive_sha256": None},
            {"archive_sha256": self.archive_sha256},
        ):
            with self.subTest(overrides=sorted(overrides)), self.assertRaises(shim.Refusal) as raised:
                self.seal(**overrides)
            self.assertIn("exactly one of --archive or --archive-sha256", str(raised.exception))

    def test_a_supplied_digest_alone_seals_the_same_document(self) -> None:
        receipt = self.receipt(self.seal(archive=None, archive_sha256=self.archive_sha256))
        self.assertEqual(receipt["archive_sha256"], self.archive_sha256)

    def test_a_root_outside_the_acquisition_layout_is_refused(self) -> None:
        stray = Path(self.temporary.name) / "stray-root"
        stray.mkdir()
        (stray / "manifest.json").write_bytes(shim.canonical({"schema_version": "release-candidate/v1"}))
        with self.assertRaises(shim.Refusal) as raised:
            self.seal(root=stray)
        self.assertIn("$XDG_DATA_HOME", str(raised.exception))

    def test_a_malformed_instant_is_refused(self) -> None:
        with self.assertRaises(shim.Refusal) as raised:
            self.seal(installed_at="2026-08-20 12:13:14")
        self.assertIn("installed-at", str(raised.exception).replace("--installed-at", "installed-at"))


class RehashObligationTest(ShimFixture):
    """No receipt is sealed over bytes this producer has not digested."""

    def test_a_modified_payload_file_is_refused_by_name(self) -> None:
        target = self.candidate_root / "commands" / "sdlc-frame.md"
        target.write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("commands/sdlc-frame.md", str(raised.exception))
        self.assertIn("digests to", str(raised.exception))
        self.assertFalse(self.state_home.joinpath(*shim.RECEIPT_SEGMENTS).exists())

    def test_a_same_length_replacement_is_refused(self) -> None:
        """The c5ea877 case: identical length, so only the digest can see it."""
        target = self.candidate_root / "commands" / "sdlc-frame.md"
        original = target.read_text(encoding="utf-8")
        target.write_text("XXXXX" + original[5:], encoding="utf-8")
        self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))
        with self.assertRaises(shim.Refusal):
            self.seal()

    def test_an_uninventoried_file_is_refused(self) -> None:
        (self.candidate_root / "commands" / "extra.md").write_text("extra\n", encoding="utf-8")
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("does not inventory", str(raised.exception))

    def test_a_missing_inventoried_file_is_refused(self) -> None:
        (self.candidate_root / "commands" / "sdlc-frame.md").unlink()
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("absent from the root", str(raised.exception))

    def test_a_retargeted_symlink_is_refused(self) -> None:
        link = self.candidate_root / "plugin-skills"
        os.symlink("skills", link)
        self.write_manifest()
        link.unlink()
        os.symlink("agents", link)
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("points at", str(raised.exception))

    def test_a_node_whose_type_changed_is_refused(self) -> None:
        target = self.candidate_root / "commands" / "sdlc-frame.md"
        target.unlink()
        target.mkdir()
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("declares", str(raised.exception))

    def test_an_intact_root_seals_so_the_refusals_are_not_vacuous(self) -> None:
        self.assertTrue(self.seal().is_file())

    def test_a_manifest_without_an_inventory_is_refused(self) -> None:
        self.write_manifest(inventory=[])
        with self.assertRaises(shim.Refusal) as raised:
            self.seal()
        self.assertIn("no inventory", str(raised.exception))


class ReadbackTest(ShimFixture):
    """Seed agentic-sdlc-ba1a's remedy: the sealed bytes are read back before success is reported."""

    def test_a_receipt_rewritten_between_the_write_and_the_readback_is_exit_four(self) -> None:
        """The write completes, a same-UID writer replaces it, and the readback is the only witness."""
        path = self.state_home.joinpath(*shim.RECEIPT_SEGMENTS, f"{self.archive_sha256}.json")
        original_fsync = os.fsync
        forged = shim.canonical({"forged": True})

        def fsync_then_replace(descriptor: int) -> None:
            original_fsync(descriptor)
            path.write_bytes(forged)

        os.fsync = fsync_then_replace  # type: ignore[assignment]
        try:
            with self.assertRaises(shim.UnknownEffect) as raised:
                self.seal()
        finally:
            os.fsync = original_fsync  # type: ignore[assignment]
        self.assertIn("rather than the sealed", str(raised.exception))
        self.assertEqual(path.read_bytes(), forged)
        self.assertEqual(shim.EXIT_UNKNOWN, 4)

    def test_an_untouched_write_reads_back_equal(self) -> None:
        path = self.seal()
        self.assertEqual(path.read_bytes(), shim.canonical(self.receipt(path)))


@unittest.skipUnless(
    hasattr(os, "O_NOFOLLOW"),
    "the simulation removes os.O_NOFOLLOW, which this platform already lacks",
)
class NoFollowFallbackTest(ShimFixture):
    """``O_NOFOLLOW`` is reinforcement where the platform defines it, not the control: with
    ``O_CREAT | O_EXCL`` the open already fails ``EEXIST`` when the path names a symlink, even a
    dangling one, and the receipt's documented threat model is drift detection, not a same-UID
    TOCTOU racer. These two tests pin both halves of that sentence on a platform without the
    flag, simulated by removing it."""

    def without_nofollow(self):
        saved = os.O_NOFOLLOW

        class _Restore:
            def __enter__(self_inner) -> None:
                delattr(os, "O_NOFOLLOW")

            def __exit__(self_inner, *exc_info: object) -> None:
                os.O_NOFOLLOW = saved  # ALWAYS restore.

        return _Restore()

    def test_a_normal_seal_still_succeeds_without_the_flag(self) -> None:
        with self.without_nofollow():
            path = self.seal()
        self.assertTrue(path.is_file())
        self.assertEqual(self.receipt(path)["archive_sha256"], self.archive_sha256)

    def test_a_planted_symlink_is_still_refused_without_the_flag(self) -> None:
        # POSITIVE CONTROL: the refusal that O_NOFOLLOW reinforced must survive the fallback.
        directory = self.state_home.joinpath(*shim.RECEIPT_SEGMENTS)
        directory.mkdir(parents=True)
        elsewhere = Path(self.temporary.name) / "redirect-target.json"
        planted = directory / f"{self.archive_sha256}.json"
        planted.symlink_to(elsewhere)
        with self.without_nofollow():
            with self.assertRaises(shim.Refusal) as raised:
                self.seal()
        self.assertIn("already exists", str(raised.exception))
        self.assertTrue(planted.is_symlink())
        self.assertFalse(elsewhere.exists(), "the write must never follow the planted link")


class RealAdmissionTest(ShimFixture):
    """``ccodex install``'s own admission code, run against a shim-produced receipt.

    Both directions of the W3b library boundary live here: the consumer ADMITS a receipt this module's
    CLI produced, and the consumer's own auto-seal produces bytes identical to that CLI's for the same
    root. A drift in either direction is a drift between the schema owner and its one caller.
    """

    def config(self) -> object:
        return install.Config(
            home=self.home,
            state_home=self.state_home,
            data_home=self.data_home,
            codex_home=Path(self.temporary.name) / "codex-home",
            installer_state_root=self.installer_state_root,
            observed_host_version="2.1.233",
            observed_instant=INSTANT,
            observed_system="Linux",
            observed_machine="x86_64",
        )

    def admitted(self) -> object:
        """The consumer's whole admission, in the two steps it now takes.

        W3b split it: ``classify_payload`` resolves the root and says whether a ticket is already filed,
        and ``admit_payload`` holds one -- sealing it through THIS module when there is none. Both are
        driven here, with this test file's own shim module passed as the producer, so what is exercised
        is the real seam between the consumer and the schema owner rather than a stand-in.
        """
        config = self.config()
        candidate = install.classify_payload(config, shim)
        return install.admit_payload(config, candidate, shim, INSTANT)

    def test_the_consumer_admits_a_shim_receipt_and_its_root(self) -> None:
        self.seal()
        payload = self.admitted()
        self.assertEqual(payload.archive_sha256, self.archive_sha256)
        self.assertEqual(payload.candidate_root, self.candidate_root)
        self.assertEqual(payload.resolved_version, "0.7.3")
        self.assertIn("commands/sdlc-frame.md", payload.inventory)
        install.verify_entry_against_manifest(payload, self.candidate_root / "commands" / "sdlc-frame.md")

    def test_the_consumer_re_derives_the_shim_seal(self) -> None:
        path = self.seal()
        receipt = self.receipt(path)
        self.assertEqual(install.acquisition_record_digest(receipt), receipt["record_sha256"])
        # Positive control: the consumer's own re-derivation refuses a hand-edited receipt.
        tampered = dict(receipt)
        tampered["installed_at"] = "2026-08-20T12:13:15Z"
        path.write_bytes(shim.canonical(tampered))
        with self.assertRaises(install.Refusal):
            self.admitted()

    def test_the_cli_produces_a_receipt_the_consumer_admits(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--root",
                str(self.candidate_root),
                "--state-home",
                str(self.state_home),
                "--archive",
                str(self.archive),
                "--installed-at",
                INSTANT,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, shim.EXIT_OK, completed.stdout + completed.stderr)
        self.assertIn(f"{self.archive_sha256}.json", completed.stdout)
        payload = self.admitted()
        self.assertEqual(payload.archive_sha256, self.archive_sha256)
        self.assertEqual("reused", payload.acquisition, "a filed ticket is reused, never re-sealed")

    def test_the_consumer_seals_the_same_bytes_this_modules_cli_would(self) -> None:
        """W3b's library boundary, checked from the schema owner's own suite.

        ``ccodex install`` auto-seals by CALLING ``write_receipt``. If that ever became a second
        implementation, the two documents would drift -- so this seals the same root twice, once through
        the consumer's admission and once through this module's CLI into a separate state home, and
        requires the bytes to be equal. The control changes one input and requires them to differ.
        """
        payload = self.admitted()
        self.assertEqual("sealed", payload.acquisition, "no ticket was filed, so the consumer sealed one")
        consumer_bytes = payload.receipt_path.read_bytes()

        elsewhere = Path(self.temporary.name) / "cli-state"
        elsewhere.mkdir()
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--root",
                str(self.candidate_root),
                "--state-home",
                str(elsewhere),
                "--archive",
                str(self.archive),
                "--installed-at",
                INSTANT,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, shim.EXIT_OK, completed.stdout + completed.stderr)
        produced = elsewhere.joinpath(*shim.RECEIPT_SEGMENTS) / f"{self.archive_sha256}.json"
        self.assertEqual(consumer_bytes, produced.read_bytes())
        # CONTROL: a different instant is different bytes, so the equality above has content.
        other = Path(self.temporary.name) / "cli-state-later"
        other.mkdir()
        later = shim.write_receipt(
            root=self.candidate_root,
            state_home=other,
            archive=self.archive,
            archive_sha256=None,
            operation_id=None,
            installed_at="2026-08-20T12:15:00Z",
        )
        self.assertNotEqual(consumer_bytes, later.read_bytes())

    def test_the_cli_refuses_a_tampered_root_at_exit_three(self) -> None:
        (self.candidate_root / "commands" / "sdlc-frame.md").write_text("tampered\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--root",
                str(self.candidate_root),
                "--state-home",
                str(self.state_home),
                "--archive",
                str(self.archive),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, shim.EXIT_REFUSED, completed.stdout + completed.stderr)
        self.assertIn("refused:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
