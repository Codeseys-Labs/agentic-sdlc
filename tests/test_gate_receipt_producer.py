"""Producer-side tests for gate receipts.

These cover the piece scripts/gate_receipt.py lacked: a caller that actually invokes a gate,
captures its combined output, and emits a receipt through build_receipt. Every gate here is an
INJECTED fake (a few lines of Python written into a temp dir), never `mise run check` — the
authoritative gate takes minutes and would make these tests neither fast nor hermetic.

The receipt is tamper detection by re-derivation, not a security boundary against the same OS
user, and no receipt these tests produce authorizes any outward effect.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import gate_receipt


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "gate_receipt.py"
LOCK_BYTES = b'[tools.fake]\nversion = "1.2.3"\n'
NOT_ROOT = os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0
POSIX = os.name == "posix"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reseal(body: dict[str, object]) -> dict[str, object]:
    """A receipt whose self_digest is internally consistent — so only the invariants can reject it."""
    sealed = {k: v for k, v in body.items() if k != "self_digest"}
    receipt = dict(sealed)
    receipt["self_digest"] = gate_receipt.canonical_digest(sealed)
    return receipt


def _write_fake_gate(
    directory: Path, *, exit_code: int, marker: Path | None = None, name: str | None = None
) -> list[str]:
    """An injected stand-in for the authoritative gate. Returns the argv that runs it."""
    body = [
        "import sys",
        "sys.stdout.write('fake gate stdout\\n')",
        "sys.stdout.flush()",
        "sys.stderr.write('fake gate stderr\\n')",
        "sys.stderr.flush()",
    ]
    if marker is not None:
        body.append(f"open({str(marker)!r}, 'w').write('ran')")
    body.append(f"sys.exit({exit_code})")
    script = directory / (name or f"fake_gate_{exit_code}.py")
    script.write_text("\n".join(body) + "\n", encoding="utf-8")
    return [sys.executable, str(script)]


class _ProducerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.lock = self.tmp / "mise.lock"
        self.lock.write_bytes(LOCK_BYTES)

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
        )


class GateReceiptProducerCliTests(_ProducerTestCase):
    """The producer surface: run a gate, capture it, emit a receipt to an explicit destination."""

    def test_producer_records_passing_gate_with_verifiable_receipt(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        out = self.tmp / "receipt.json"
        log = self.tmp / "gate.log"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--log",
                str(log),
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        # The receipt verifies through the EXISTING re-derivation contract.
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["gate"], "fake gate")
        self.assertEqual(receipt["argv"], argv)
        self.assertEqual(receipt["status"], 0)
        self.assertIsNone(receipt["signal"])
        self.assertEqual(receipt["outcome"], "passed")
        self.assertEqual(receipt["cwd"], str(self.tmp.resolve()))
        # The log digest is over the bytes actually captured, and the persisted log matches it.
        log_bytes = log.read_bytes()
        self.assertEqual(receipt["log_digest"], _sha256_hex(log_bytes))
        self.assertIn(b"fake gate stdout", log_bytes)
        self.assertIn(b"fake gate stderr", log_bytes)  # stderr is merged into the same capture
        self.assertTrue(gate_receipt.verify_toolchain_binding(receipt, LOCK_BYTES))

    def test_failing_gate_never_exits_green_and_its_exact_code_is_in_the_receipt(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=7)
        out = self.tmp / "receipt.json"
        proc = self._run(
            ["record", "--gate", "fake gate", "--out", str(out), "--lock", str(self.lock), "--", *argv]
        )
        # A red gate must never surface as a green producer exit...
        self.assertNotEqual(proc.returncode, 0)
        # ...and the producer reports ITSELF, so the gate's own code is not passed through.
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["status"], 7)  # the exact code survives, in the receipt
        self.assertEqual(receipt["outcome"], "failed")

    def test_unobserved_gate_is_distinct_from_a_failing_gate(self) -> None:
        out_unobserved = self.tmp / "unobserved.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out_unobserved),
                "--lock",
                str(self.lock),
                "--unobserved",
                "--",
                *_write_fake_gate(self.tmp, exit_code=0, marker=self.tmp / "never.marker"),
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_UNOBSERVED, proc.stderr)
        self.assertNotEqual(proc.returncode, 0)  # never 0: unobserved is not a pass
        unobserved = json.loads(out_unobserved.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(unobserved))
        self.assertEqual(unobserved["outcome"], "unobserved")
        self.assertIsNone(unobserved["status"])
        # Nothing ran, so the receipt names no executed command — while `gate` still says which
        # gate it is about, so the record is not anonymous.
        self.assertIsNone(unobserved["argv"])
        self.assertEqual(unobserved["gate"], "fake gate")
        # POSITIVE CONTROL for the "gate did not run" claim: the same fake gate, actually run,
        # DOES create its marker, so the marker's absence above is an observation, not a blind spot.
        self.assertFalse((self.tmp / "never.marker").exists())
        out_ran = self.tmp / "ran.json"
        ran_argv = _write_fake_gate(self.tmp, exit_code=0, marker=self.tmp / "did.marker")
        ran = self._run(
            ["record", "--gate", "fake gate", "--out", str(out_ran), "--lock", str(self.lock), "--", *ran_argv]
        )
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertTrue((self.tmp / "did.marker").exists())
        # POSITIVE CONTROL for the field channel: the same keys carry a real run too.
        observed = json.loads(out_ran.read_text(encoding="utf-8"))
        self.assertEqual(observed["outcome"], "passed")
        self.assertEqual(observed["status"], 0)
        self.assertEqual(observed["argv"], ran_argv)

    def test_producer_refuses_to_clobber_an_existing_receipt(self) -> None:
        out = self.tmp / "receipt.json"
        out.write_text("{\"existing\": true}\n", encoding="utf-8")
        marker = self.tmp / "clobber.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        proc = self._run(
            ["record", "--gate", "fake gate", "--out", str(out), "--lock", str(self.lock), "--", *argv]
        )
        self.assertNotEqual(proc.returncode, 0)
        # Nothing happened, so this is a CLEAN refusal, never a partial result.
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), "{\"existing\": true}\n")
        # POSITIVE CONTROL: the refusal happens before the gate runs, and this same fake gate
        # provably creates its marker when it is allowed to run (next two assertions).
        self.assertFalse(marker.exists())
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "fresh.json"),
                "--lock",
                str(self.lock),
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(marker.exists())

    def test_producer_refuses_to_clobber_an_existing_log(self) -> None:
        """The log destination is guarded exactly like the receipt destination, and just as early."""
        log = self.tmp / "gate.log"
        log.write_bytes(b"earlier evidence\n")
        marker = self.tmp / "log-clobber.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "receipt.json"),
                "--lock",
                str(self.lock),
                "--log",
                str(log),
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertEqual(log.read_bytes(), b"earlier evidence\n")
        self.assertFalse((self.tmp / "receipt.json").exists())
        self.assertFalse(marker.exists())  # refused before the gate ran
        # POSITIVE CONTROL: a free log path lets the same invocation through.
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "receipt.json"),
                "--lock",
                str(self.lock),
                "--log",
                str(self.tmp / "fresh.log"),
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(marker.exists())

    def test_one_path_cannot_hold_both_the_receipt_and_the_log(self) -> None:
        """`--out X --log X` refuses BEFORE the gate, so no raw log lands at a receipt path."""
        both = self.tmp / "both.json"
        marker = self.tmp / "collision.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(both),
                "--lock",
                str(self.lock),
                "--log",
                str(both),
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertFalse(marker.exists())  # a clean refusal: the gate never ran
        self.assertFalse(both.exists())  # and no half-written artifact was left behind
        # The refusal must not claim pre-existing evidence that never existed.
        self.assertNotIn("refusing to overwrite existing evidence", proc.stderr)
        self.assertIn("--out and --log both resolve to", proc.stderr)

    def test_a_symlinked_log_aliasing_the_receipt_is_refused_too(self) -> None:
        """Two different spellings of one file are still one file."""
        out = self.tmp / "receipt.json"
        alias = self.tmp / "alias.log"
        alias.symlink_to(out)  # dangling: neither path exists yet
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--log",
                str(alias),
                "--",
                *_write_fake_gate(self.tmp, exit_code=0),
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertFalse(out.exists())

    def test_a_dangling_symlink_at_a_destination_is_occupied_too(self) -> None:
        """A symlink IS the occupant, dangling or not — and `O_EXCL` would refuse it anyway.

        Testing `exists()` instead of `lexists()` looks equivalent and is not: the pre-flight would
        pass, the gate would run in full, and only the write would fail on `EEXIST`, turning a clean
        pre-run refusal into a lost receipt for work that already happened.
        """
        for label, name in (("receipt", "receipt.json"), ("log", "gate.log")):
            with self.subTest(destination=label):
                link = self.tmp / f"dangling-{name}"
                link.symlink_to(self.tmp / f"nowhere-{name}")  # the target does not exist
                self.assertFalse(link.exists())  # ...so exists() cannot see the occupant...
                self.assertTrue(link.is_symlink())  # ...but the link is unmistakably there
                marker = self.tmp / f"symlink-{label}.marker"
                argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker, name=f"g-{label}.py")
                extra = (
                    ["--out", str(link)]
                    if label == "receipt"
                    else ["--out", str(self.tmp / f"receipt-{label}.json"), "--log", str(link)]
                )
                proc = self._run(
                    ["record", "--gate", "fake gate", "--lock", str(self.lock), *extra, "--", *argv]
                )
                self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
                self.assertIn("refusing to overwrite existing evidence", proc.stderr)
                # The decisive observation: a clean refusal, so the gate never ran at all.
                self.assertFalse(marker.exists())
                self.assertFalse((self.tmp / f"nowhere-{name}").exists())  # nor was it followed
                # POSITIVE CONTROL: the same invocation at a free path runs the gate and succeeds.
                free = ["--out", str(self.tmp / f"free-{label}.json")]
                if label == "log":
                    free += ["--log", str(self.tmp / f"free-{label}.log")]
                ok = self._run(
                    ["record", "--gate", "fake gate", "--lock", str(self.lock), *free, "--quiet", "--", *argv]
                )
                self.assertEqual(ok.returncode, 0, ok.stderr)
                self.assertTrue(marker.exists())

    @unittest.skipUnless(NOT_ROOT, "directory permissions do not restrain root")
    def test_an_unwritable_parent_directory_refuses_before_the_gate_runs(self) -> None:
        """The other half of the pre-flight: the parent exists but cannot be written."""
        readonly = self.tmp / "readonly"
        readonly.mkdir()
        readonly.chmod(0o555)
        self.addCleanup(lambda: readonly.chmod(0o755))
        marker = self.tmp / "readonly.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(readonly / "receipt.json"),
                "--lock",
                str(self.lock),
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertIn("not writable", proc.stderr)
        # A full gate run whose receipt cannot land is the waste this pre-flight exists to avoid,
        # so the observation that matters is that the gate did not run.
        self.assertFalse(marker.exists())
        self.assertFalse((readonly / "receipt.json").exists())
        # POSITIVE CONTROL: made writable, the identical invocation runs the gate and lands.
        readonly.chmod(0o755)
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(readonly / "receipt.json"),
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(marker.exists())
        self.assertTrue((readonly / "receipt.json").exists())

    def test_a_stdout_receipt_does_not_collide_with_a_log_file_named_dash(self) -> None:
        """`--out -` is a stream, so it cannot collide with any path — not even `./-`.

        `os.path.realpath("-")` is `<cwd>/-`, so without the `--out -` exemption this invocation
        would be refused for a path collision that does not exist, and no receipt would be produced.
        """
        argv = _write_fake_gate(self.tmp, exit_code=0)
        log = self.tmp / "-"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                "-",
                "--lock",
                str(self.lock),
                "--log",
                str(log),
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("one path cannot hold both", proc.stderr)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(proc.stdout)))
        self.assertIn(b"fake gate stdout", log.read_bytes())  # the log went to the file `./-`
        # And now that `./-` exists in the gate's cwd, `--out -` must STILL mean stdout: the
        # occupancy check exempts the stream, or an unrelated file named `-` would refuse it.
        again = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                "-",
                "--lock",
                str(self.lock),
                "--log",
                str(self.tmp / "second.log"),
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotIn("refusing to overwrite existing evidence", again.stderr)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(again.stdout)))

    @unittest.skipUnless(NOT_ROOT, "directory permissions do not restrain root")
    def test_a_stdout_receipt_is_unaffected_by_an_unwritable_current_directory(self) -> None:
        """`--out -` needs no writable directory at all, so the pre-flight must skip the stream.

        `Path("-").parent` is `.`, so a creatability check applied to `-` asks whether the CURRENT
        directory is writable — a question stdout does not depend on. In a read-only cwd that turns
        a perfectly good stdout receipt into a refusal.
        """
        readonly = self.tmp / "readonly-cwd"
        readonly.mkdir()
        argv = _write_fake_gate(self.tmp, exit_code=0)
        readonly.chmod(0o555)
        self.addCleanup(lambda: readonly.chmod(0o755))
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "record",
                "--gate",
                "fake gate",
                "--out",
                "-",
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *argv,
            ],
            capture_output=True,
            text=True,
            cwd=str(readonly),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("not writable", proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["cwd"], str(readonly.resolve()))
        # POSITIVE CONTROL: a FILE destination in that same read-only directory IS refused, so the
        # directory really is unwritable and the success above is the stream exemption at work.
        refused = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "record",
                "--gate",
                "fake gate",
                "--out",
                "receipt.json",
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *argv,
            ],
            capture_output=True,
            text=True,
            cwd=str(readonly),
            check=False,
        )
        self.assertEqual(refused.returncode, gate_receipt.EXIT_REFUSED, refused.stderr)
        self.assertIn("not writable", refused.stderr)

    def test_the_gate_argv_keeps_its_own_dash_dash(self) -> None:
        """The split takes the FIRST bare `--`; later ones belong to the gate, e.g. `mise run x --`."""
        script = self.tmp / "echo_args.py"
        script.write_text("import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n", encoding="utf-8")
        out = self.tmp / "receipt.json"
        gate_argv = [sys.executable, str(script), "--", "--gate", "not-an-option"]
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *gate_argv,
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(receipt["argv"], gate_argv)  # nothing was consumed by the producer
        self.assertEqual(receipt["gate"], "fake gate")  # and the label was NOT taken from the gate
        # The gate really received the trailing arguments: its own echo is what was hashed.
        self.assertEqual(
            receipt["log_digest"], _sha256_hex(" ".join(gate_argv[2:]).encode("utf-8"))
        )

    def test_log_dash_is_rejected_instead_of_silently_discarded(self) -> None:
        """`--log -` used to return 0 having written no log at all."""
        marker = self.tmp / "logdash.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--log",
                "-",
                "--",
                *argv,
            ]
        )
        self.assertNotEqual(proc.returncode, 0)  # never a silent success
        self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE, proc.stderr)
        self.assertIn("--log", proc.stderr)
        self.assertFalse(marker.exists())  # rejected before the gate ran
        self.assertFalse(out.exists())
        self.assertFalse((self.tmp / "-").exists())  # and no file literally named `-`
        # POSITIVE CONTROL: a real path is accepted and the log is actually persisted.
        log = self.tmp / "gate.log"
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--log",
                str(log),
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn(b"fake gate stdout", log.read_bytes())

    def test_gate_that_cannot_be_started_is_unobserved_not_failed(self) -> None:
        out = self.tmp / "receipt.json"
        missing = self.tmp / "no-such-gate"
        proc = self._run(
            ["record", "--gate", "fake gate", "--out", str(out), "--lock", str(self.lock), "--", str(missing)]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_UNOBSERVED, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        # A spawn failure must not be laundered into a 127-style "ran and failed" verdict.
        self.assertEqual(receipt["outcome"], "unobserved")
        self.assertIsNone(receipt["status"])
        self.assertIsNone(receipt["argv"])  # nothing executed, so nothing is claimed as executed
        # POSITIVE CONTROL: an existing gate at a path in the same temp dir does reach "passed",
        # so the unobserved result above is about the missing gate, not about the fixture.
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "ok.json"),
                "--lock",
                str(self.lock),
                "--",
                *_write_fake_gate(self.tmp, exit_code=0),
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads((self.tmp / "ok.json").read_text(encoding="utf-8"))["outcome"], "passed")

    def test_signal_killed_gate_records_no_verdict_and_no_negative_status(self) -> None:
        """A killed gate RAN but returned no exit code; -9 is not an exit code."""
        script = self.tmp / "suicide.py"
        script.write_text(
            "import os, signal, sys\n"
            "sys.stdout.write('about to die\\n')\n"
            "sys.stdout.flush()\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n",
            encoding="utf-8",
        )
        argv = [sys.executable, str(script)]
        out = self.tmp / "receipt.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *argv,
            ]
        )
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertIsNone(receipt["status"])  # never -9: status is an exit code or null
        self.assertEqual(receipt["signal"], 9)
        self.assertEqual(receipt["outcome"], "unobserved")  # no verdict was produced
        self.assertNotEqual(receipt["outcome"], "failed")
        self.assertEqual(receipt["argv"], argv)  # it DID run, unlike a never-run gate
        # The producer's own exit agrees with the receipt instead of asserting a 137 verdict.
        self.assertEqual(proc.returncode, gate_receipt.EXIT_UNOBSERVED, proc.stderr)
        self.assertIn("killed by signal 9", proc.stderr)
        # The captured bytes before the kill are still hashed as evidence.
        self.assertEqual(receipt["log_digest"], _sha256_hex(b"about to die\n"))

    def test_destination_is_required_and_has_no_default(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        proc = self._run(["record", "--gate", "fake gate", "--lock", str(self.lock), "--", *argv])
        self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE)
        self.assertIn("--out", proc.stderr)
        # POSITIVE CONTROL: the only thing missing was the destination — the same invocation
        # succeeds once --out is supplied, so this is not a generic usage failure.
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "receipt.json"),
                "--lock",
                str(self.lock),
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_receipt_can_go_to_stdout_without_touching_the_filesystem(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        proc = self._run(
            ["record", "--gate", "fake gate", "--out", "-", "--lock", str(self.lock), "--quiet", "--", *argv]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["outcome"], "passed")
        self.assertFalse((self.tmp / "-").exists())  # `-` is a stream, never a file named `-`

    def test_captured_output_is_mirrored_unless_quiet(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        loud = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "loud.json"),
                "--lock",
                str(self.lock),
                "--",
                *argv,
            ]
        )
        self.assertEqual(loud.returncode, 0, loud.stderr)
        self.assertIn("fake gate stdout", loud.stderr)
        quiet = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "quiet.json"),
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(quiet.returncode, 0, quiet.stderr)
        self.assertNotIn("fake gate stdout", quiet.stderr)
        # Suppressing the mirror must not change what is hashed.
        self.assertEqual(
            json.loads((self.tmp / "loud.json").read_text(encoding="utf-8"))["log_digest"],
            json.loads((self.tmp / "quiet.json").read_text(encoding="utf-8"))["log_digest"],
        )

    def test_lock_defaults_to_the_gate_cwds_mise_lock(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        out = self.tmp / "receipt.json"
        proc = self._run(["record", "--gate", "fake gate", "--out", str(out), "--quiet", "--", *argv])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        # The default binds the lock of the directory the gate ran in, not some ambient lock.
        self.assertTrue(gate_receipt.verify_toolchain_binding(receipt, LOCK_BYTES))

    def test_unreadable_lock_refuses_before_the_gate_runs(self) -> None:
        marker = self.tmp / "lock.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.tmp / "absent.lock"),
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertFalse(marker.exists())  # an unbindable receipt is refused, not written unbound
        self.assertFalse(out.exists())

    def test_gate_runs_in_the_requested_cwd(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "mise.lock").write_bytes(LOCK_BYTES)
        script = elsewhere / "pwd_gate.py"
        script.write_text("import os, sys\nsys.stdout.write(os.getcwd())\n", encoding="utf-8")
        out = self.tmp / "receipt.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--cwd",
                str(elsewhere),
                "--quiet",
                "--",
                sys.executable,
                str(script),
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        resolved = str(elsewhere.resolve())
        self.assertEqual(receipt["cwd"], resolved)
        # The gate really ran there: its own getcwd() is what was captured and hashed.
        self.assertEqual(receipt["log_digest"], _sha256_hex(resolved.encode("utf-8")))

    def test_nonexistent_gate_cwd_is_an_input_error(self) -> None:
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "receipt.json"),
                "--lock",
                str(self.lock),
                "--cwd",
                str(self.tmp / "no-such-dir"),
                "--",
                "true",
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE, proc.stderr)
        self.assertFalse((self.tmp / "receipt.json").exists())

    def test_missing_gate_argv_is_an_input_error(self) -> None:
        for tail in ([], ["--"]):
            with self.subTest(tail=tail):
                proc = self._run(
                    [
                        "record",
                        "--gate",
                        "fake gate",
                        "--out",
                        str(self.tmp / "receipt.json"),
                        "--lock",
                        str(self.lock),
                        *tail,
                    ]
                )
                self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE, proc.stderr)
                self.assertFalse((self.tmp / "receipt.json").exists())


class EffectAwareExitTests(_ProducerTestCase):
    """Decision 9: a clean pre-effect refusal (3) and a post-effect partial (4) are distinct."""

    def test_uncreatable_destination_refuses_before_the_gate_instead_of_losing_its_receipt(self) -> None:
        marker = self.tmp / "preflight.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        missing = self.tmp / "no-such-dir"
        # Both artifacts are pre-flighted: a lost log after a real gate run is orphan evidence
        # exactly as a lost receipt is.
        for label, extra in (
            ("out", ["--out", str(missing / "receipt.json")]),
            ("log", ["--out", str(self.tmp / "receipt-log.json"), "--log", str(missing / "gate.log")]),
        ):
            with self.subTest(destination=label):
                marker.unlink(missing_ok=True)
                proc = self._run(
                    ["record", "--gate", "fake gate", "--lock", str(self.lock), *extra, "--", *argv]
                )
                self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
                # The decisive observation: the gate did NOT run, so nothing was lost for real work.
                self.assertFalse(marker.exists())
                self.assertFalse((self.tmp / "receipt-log.json").exists())
        # POSITIVE CONTROL: the same destinations inside an existing directory are accepted.
        missing.mkdir()
        ok = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(missing / "receipt.json"),
                "--lock",
                str(self.lock),
                "--log",
                str(missing / "gate.log"),
                "--",
                *argv,
            ]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(marker.exists())
        self.assertTrue((missing / "gate.log").exists())

    @unittest.skipUnless(NOT_ROOT, "directory permissions do not restrain root")
    def test_a_failure_after_the_gate_ran_is_partial_never_a_clean_refusal(self) -> None:
        """The gate's side effects exist and the receipt is gone: that is 4, not 3 and not 1."""
        evidence = self.tmp / "evidence"
        evidence.mkdir()
        marker = self.tmp / "post-effect.marker"
        script = self.tmp / "sabotage.py"
        script.write_text(
            "import os, sys\n"
            f"open({str(marker)!r}, 'w').write('ran')\n"
            f"os.chmod({str(evidence)!r}, 0o555)\n",
            encoding="utf-8",
        )
        self.addCleanup(lambda: evidence.chmod(0o755))
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(evidence / "receipt.json"),
                "--lock",
                str(self.lock),
                "--quiet",
                "--",
                sys.executable,
                str(script),
            ]
        )
        self.assertTrue(marker.exists())  # the gate's effect is real and still on disk
        self.assertFalse((evidence / "receipt.json").exists())  # the receipt was lost
        self.assertEqual(proc.returncode, gate_receipt.EXIT_PARTIAL, proc.stderr)
        self.assertNotEqual(proc.returncode, gate_receipt.EXIT_REFUSED)
        self.assertNotEqual(proc.returncode, gate_receipt.EXIT_INTERNAL)
        # And it says so, naming what already happened rather than implying nothing did.
        self.assertIn("PARTIAL", proc.stderr)
        self.assertIn("already happened: the gate ran", proc.stderr)

    @unittest.skipUnless(NOT_ROOT, "directory permissions do not restrain root")
    def test_an_orphaned_log_is_reported_as_an_admitted_effect(self) -> None:
        """Log written, receipt lost: the orphan evidence must be named, not silently left."""
        evidence = self.tmp / "evidence"
        evidence.mkdir()
        log = self.tmp / "gate.log"
        script = self.tmp / "sabotage.py"
        script.write_text(
            "import os, sys\nsys.stdout.write('work\\n')\n" f"os.chmod({str(evidence)!r}, 0o555)\n",
            encoding="utf-8",
        )
        self.addCleanup(lambda: evidence.chmod(0o755))
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(evidence / "receipt.json"),
                "--lock",
                str(self.lock),
                "--log",
                str(log),
                "--quiet",
                "--",
                sys.executable,
                str(script),
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_PARTIAL, proc.stderr)
        self.assertTrue(log.exists())  # the orphan is preserved, never deleted...
        self.assertIn(f"already happened: the captured gate log was written to {log}", proc.stderr)

    def test_an_unexpected_failure_before_any_effect_is_internal_not_partial(self) -> None:
        """EXIT_INTERNAL is reachable: an unforeseen error with nothing done yet."""
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=self.tmp / "internal.marker")
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(self.tmp / "receipt.json"),
            "--lock",
            str(self.lock),
            "--quiet",
            "--",
            *argv,
        ]
        with mock.patch.object(gate_receipt, "_read_lock", side_effect=RuntimeError("boom")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_receipt.main(args)
        self.assertEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertIn("unexpected RuntimeError", err.getvalue())
        self.assertFalse((self.tmp / "internal.marker").exists())
        self.assertFalse((self.tmp / "receipt.json").exists())

    def test_an_unexpected_failure_after_the_gate_ran_escalates_to_partial(self) -> None:
        """The same unforeseen error class, once an effect exists, must report 4 instead of 1."""
        marker = self.tmp / "escalate.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(self.tmp / "receipt.json"),
            "--lock",
            str(self.lock),
            "--quiet",
            "--",
            *argv,
        ]
        with mock.patch.object(gate_receipt, "build_receipt", side_effect=RuntimeError("boom")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_receipt.main(args)
        self.assertTrue(marker.exists())
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL)
        self.assertIn("already happened: the gate ran", err.getvalue())

    def test_a_text_mode_stderr_keeps_the_receipt_of_a_gate_that_ran(self) -> None:
        """`main` is importable, so a TEXT `sys.stderr` is an ordinary caller, not an exotic one.

        `unittest --buffer` and `contextlib.redirect_stderr(io.StringIO())` each install one, and a
        text stream has no `.buffer`. Reaching for `.buffer` mid-run therefore raised
        `AttributeError` AFTER the gate had run: exit 1 — "nothing happened" — over a marker on disk
        and no receipt at all. Mirroring is a convenience `--quiet` switches off, so it must never
        be able to cost a completed gate its evidence.
        """
        marker = self.tmp / "text-stderr.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--",  # deliberately NOT --quiet: the mirror is the whole point of this test
            *argv,
        ]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertEqual(code, gate_receipt.EXIT_OK, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertTrue(marker.exists())  # the gate ran — this test's premise, observed not assumed
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["outcome"], "passed")
        # The mirror rendered to the text stream instead of being silently dropped...
        self.assertIn("fake gate stdout", text)
        self.assertIn("fake gate stderr", text)
        # ...and it changed nothing about what was hashed: the digest is over the raw bytes.
        self.assertEqual(receipt["log_digest"], _sha256_hex(b"fake gate stdout\nfake gate stderr\n"))

    def test_a_failure_inside_the_run_window_is_partial_before_run_gate_ever_returns(self) -> None:
        """The gate is "ran" from `Popen`, not from `wait`, so the window between them must count.

        This is the test that goes red if the admission moves back to the caller. `wait` is reaped
        and THEN raises, so `_run_gate` never returns while the gate's marker is already on disk: an
        admission made after the call leaves `effects` empty and reports 1 — "nothing happened" —
        for work that provably happened. Guarding individual raise sites does not fix this; there
        are three inside the window and the next one added would restore the defect.
        """
        marker = self.tmp / "window.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--quiet",  # quiet, so the raise below is unambiguously `wait` and not the mirror
            "--",
            *argv,
        ]
        real_wait = subprocess.Popen.wait

        def reap_then_raise(proc: subprocess.Popen[bytes], *rest: object, **kwargs: object) -> int:
            # Reap first: an unwaited child would leave a ResourceWarning, not a cleaner test.
            real_wait(proc, *rest, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("boom before _run_gate could return")

        with mock.patch.object(subprocess.Popen, "wait", reap_then_raise):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertTrue(marker.exists())  # it ran...
        self.assertFalse(out.exists())  # ...and its receipt is gone, so the result is partial
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertNotEqual(code, gate_receipt.EXIT_REFUSED)
        self.assertIn("PARTIAL", text)
        self.assertIn("already happened: the gate ran", text)
        # POSITIVE CONTROL: the identical call with the real `wait` writes a verifiable receipt, so
        # the escalation above is the injected failure and not the fixture.
        with contextlib.redirect_stderr(io.StringIO()) as ok_err:
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_OK, ok_err.getvalue())
        self.assertNotIn("PARTIAL", ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_a_mirror_write_failure_after_the_gate_ran_is_partial_not_effect_free(self) -> None:
        """Tolerating a text stream must not SILENCE a mirror that genuinely fails.

        The stream's shape can no longer strand a receipt, but a real write failure still can, and
        it lands in the same window: `EPIPE` on a byte-capable stderr must report 4, never 1. This
        keeps the exit-4 path reachable for a raise site other than `wait`.
        """
        marker = self.tmp / "mirror.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--",  # not --quiet: the mirror has to be reached for its failure to matter
            *argv,
        ]

        class _BrokenMirror:
            """Byte-capable stderr whose `.buffer` fails, while its own text writes still work."""

            def __init__(self) -> None:
                self.text = io.StringIO()
                self.buffer = mock.Mock()
                self.buffer.write.side_effect = OSError(errno.EPIPE, "broken pipe")

            def write(self, data: str) -> int:
                return self.text.write(data)

            def flush(self) -> None:
                return None

        broken = _BrokenMirror()
        with mock.patch.object(sys, "stderr", broken):
            code = gate_receipt.main(args)
        text = broken.text.getvalue()
        self.assertTrue(marker.exists())
        self.assertFalse(out.exists())
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertIn("unexpected BrokenPipeError", text)  # not laundered into an unobserved gate
        self.assertIn("already happened: the gate ran", text)

    def test_producer_exit_codes_never_replay_the_gates_own_code(self) -> None:
        """A gate exiting 3 must not read as the producer's clean refusal (and 3 is common here)."""
        reserved = {
            gate_receipt.EXIT_INTERNAL,
            gate_receipt.EXIT_USAGE,
            gate_receipt.EXIT_REFUSED,
            gate_receipt.EXIT_PARTIAL,
        }
        for gate_code in (1, 2, 3, 4, 74, 127):
            with self.subTest(gate_code=gate_code):
                out = self.tmp / f"receipt-{gate_code}.json"
                proc = self._run(
                    [
                        "record",
                        "--gate",
                        "fake gate",
                        "--out",
                        str(out),
                        "--lock",
                        str(self.lock),
                        "--quiet",
                        "--",
                        *_write_fake_gate(self.tmp, exit_code=gate_code),
                    ]
                )
                self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
                self.assertNotIn(proc.returncode, reserved)
                receipt = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(receipt["status"], gate_code)  # the exact code is not lost
                self.assertEqual(receipt["outcome"], "failed")

    def test_the_reserved_exit_codes_are_pairwise_distinct(self) -> None:
        """Every producer state has its own code; the whole point is that none collide."""
        codes = [
            gate_receipt.EXIT_OK,
            gate_receipt.EXIT_INTERNAL,
            gate_receipt.EXIT_USAGE,
            gate_receipt.EXIT_REFUSED,
            gate_receipt.EXIT_PARTIAL,
            gate_receipt.EXIT_GATE_FAILED,
            gate_receipt.EXIT_UNOBSERVED,
        ]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(codes[:5], [0, 1, 2, 3, 4])  # the effect-aware contract, verbatim
        self.assertNotIn(gate_receipt.EXIT_UNOBSERVED, {0, 1, 2, 3, 4})
        self.assertNotIn(gate_receipt.EXIT_GATE_FAILED, {0, 1, 2, 3, 4})

    def test_write_new_file_preserves_an_existing_path(self) -> None:
        """The exclusive-create guard, exercised directly: the only caller reaches it by a race."""
        effects = gate_receipt._Effects()
        target = self.tmp / "occupied"
        target.write_bytes(b"earlier\n")
        with self.assertRaises(gate_receipt._ProducerError) as raised:
            gate_receipt._write_new_file(str(target), b"replacement\n", effects=effects, what="receipt")
        self.assertEqual(raised.exception.code, gate_receipt.EXIT_INTERNAL)
        self.assertEqual(target.read_bytes(), b"earlier\n")
        # Preserving somebody else's file is NOT an effect of ours, so nothing may be admitted:
        # otherwise this clean refusal would escalate to a partial result it never caused.
        self.assertFalse(effects.any())
        self.assertEqual(effects.admitted, [])
        # POSITIVE CONTROL: a free path is written, so the refusal is about the occupancy.
        free = self.tmp / "free"
        gate_receipt._write_new_file(str(free), b"replacement\n", effects=effects, what="receipt")
        self.assertEqual(free.read_bytes(), b"replacement\n")
        self.assertEqual(effects.admitted, [f"the receipt was written to {free}"])

    @unittest.skipUnless(POSIX, "RLIMIT_FSIZE and preexec_fn are POSIX-only")
    def test_a_kernel_truncated_receipt_write_is_partial_and_leaves_no_blocking_stray(self) -> None:
        """N1: the destination EXISTS from `os.open` on, so a failed write is 4 — never 1.

        `--unobserved` runs no gate, so the ONLY possible admitted effect is the creation itself:
        if creation is admitted where it happens, this is a partial result; if it is admitted only
        after the write returns, the producer exits 1 ("nothing happened") on top of a truncated
        non-receipt that then blocks its own exclusive-create destination forever.
        """
        import resource  # noqa: PLC0415 - POSIX-only, imported inside the POSIX-only test
        import signal  # noqa: PLC0415

        def _cap_file_size() -> None:  # pragma: no cover - runs in the forked child
            # Ignore SIGXFSZ so the oversized write returns EFBIG instead of killing the producer;
            # a signal death would prove nothing about how the producer classifies its own failure.
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (64, 64))

        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--unobserved",
            "--",
            "true",
        ]
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(self.tmp),
            check=False,
            preexec_fn=_cap_file_size,
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_PARTIAL, proc.stderr)
        self.assertNotEqual(proc.returncode, gate_receipt.EXIT_INTERNAL)
        self.assertNotEqual(proc.returncode, gate_receipt.EXIT_REFUSED)
        self.assertIn("PARTIAL", proc.stderr)
        self.assertIn(f"already happened: {out} was created", proc.stderr)
        # The stray truncated non-receipt is gone, so it can neither be read as evidence nor
        # block its own destination; and the reason says which disposition happened.
        self.assertFalse(out.exists(), f"a truncated non-receipt was left at {out}")
        self.assertIn("the incomplete file was removed", proc.stderr)
        # POSITIVE CONTROL: without the file-size cap the identical invocation writes a real,
        # verifiable receipt, so the failure above is the write limit and not the fixture.
        ok_out = self.tmp / "ok.json"
        ok = self._run([*args[:4], str(ok_out), *args[5:]])
        self.assertEqual(ok.returncode, gate_receipt.EXIT_UNOBSERVED, ok.stderr)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(ok_out.read_text(encoding="utf-8"))))
        # And the retry that the removal makes possible: the same destination is usable again.
        retry = self._run(args)
        self.assertEqual(retry.returncode, gate_receipt.EXIT_UNOBSERVED, retry.stderr)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_a_receipt_write_failure_admits_the_creation_it_already_performed(self) -> None:
        """The same defect through a durability failure, in-process: fsync fails after creation."""
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--unobserved",
            "--",
            "true",
        ]
        with mock.patch("os.fsync", side_effect=OSError(errno.EIO, "input/output error")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertIn("PARTIAL", text)
        self.assertIn(f"already happened: {out} was created", text)
        self.assertFalse(out.exists())
        # POSITIVE CONTROL: the identical call with a working fsync writes the receipt and never
        # reports a partial result, so the escalation above is caused by the write failure.
        with contextlib.redirect_stderr(io.StringIO()) as ok_err:
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_UNOBSERVED, ok_err.getvalue())
        self.assertNotIn("PARTIAL", ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_a_partial_file_that_cannot_be_removed_is_named_rather_than_hidden(self) -> None:
        """If the cleanup itself fails, the surviving file must be named — silence is the defect."""
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--unobserved",
            "--",
            "true",
        ]
        with mock.patch("os.fsync", side_effect=OSError(errno.EIO, "input/output error")):
            with mock.patch("os.unlink", side_effect=OSError(errno.EPERM, "not permitted")):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertTrue(out.exists())  # it really is still there...
        self.assertIn(f"an INCOMPLETE file REMAINS at {out}", text)  # ...and it is reported
        self.assertNotIn("the incomplete file was removed", text)  # never claimed falsely

    def test_a_failed_stdout_receipt_write_is_partial_not_a_clean_internal_failure(self) -> None:
        """`--out -` puts bytes on somebody else's stream: a failed flush is an unknown effect."""
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            "-",
            "--lock",
            str(self.lock),
            "--unobserved",
            "--",
            "true",
        ]
        broken = mock.Mock()
        broken.write.side_effect = OSError(errno.EPIPE, "broken pipe")
        with mock.patch.object(sys, "stdout", mock.Mock(buffer=broken)):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertIn("stdout", text)
        self.assertIn("already happened", text)
        # POSITIVE CONTROL: the same call over a working stream emits one verifiable receipt.
        with contextlib.redirect_stderr(io.StringIO()):
            buffer = io.BytesIO()
            with mock.patch.object(sys, "stdout", mock.Mock(buffer=buffer)):
                ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_UNOBSERVED)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(buffer.getvalue())))


class UnobservedOutcomeTests(unittest.TestCase):
    """`status` alone cannot separate "never ran" from "ran and failed"; `outcome` must."""

    def test_no_exit_code_can_mean_unobserved(self) -> None:
        for status in (0, 1, 2, 7, 127, 255):
            with self.subTest(status=status):
                receipt = gate_receipt.build_receipt(
                    gate="fake gate",
                    argv=["fake"],
                    status=status,
                    log_bytes=b"",
                    lock_bytes=LOCK_BYTES,
                    cwd="/tmp/fixture",
                )
                self.assertNotEqual(receipt["outcome"], gate_receipt.OUTCOME_UNOBSERVED)
                self.assertEqual(
                    receipt["outcome"],
                    gate_receipt.OUTCOME_PASSED if status == 0 else gate_receipt.OUTCOME_FAILED,
                )
        # POSITIVE CONTROL: the unobserved value is reachable at all — through status=None only.
        unobserved = gate_receipt.build_receipt(
            gate="fake gate",
            argv=None,
            status=None,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
        )
        self.assertEqual(unobserved["outcome"], gate_receipt.OUTCOME_UNOBSERVED)
        self.assertIsNone(unobserved["status"])
        self.assertTrue(gate_receipt.verify_receipt(unobserved))

    def test_build_receipt_never_emits_a_receipt_that_fails_its_own_verification(self) -> None:
        """`status` is coerced with `int()` for storage, so the outcome must be derived the same way.

        Derive it from the RAW argument instead and a coerced status disagrees with its own outcome —
        a receipt that verifies nowhere, produced by the honest path. A float or stringly-typed
        status is caller error, but emitting an unverifiable receipt in response is a defect.
        """
        for status, expected in ((0.5, gate_receipt.OUTCOME_PASSED), ("0", gate_receipt.OUTCOME_PASSED)):
            with self.subTest(status=status):
                receipt = gate_receipt.build_receipt(
                    gate="fake gate",
                    argv=["fake"],
                    status=status,  # type: ignore[arg-type]
                    log_bytes=b"",
                    lock_bytes=LOCK_BYTES,
                    cwd="/tmp/fixture",
                )
                self.assertEqual(receipt["status"], 0)  # coerced on the way in...
                self.assertEqual(receipt["outcome"], expected)  # ...and the outcome agrees with it
                self.assertTrue(gate_receipt.verify_receipt(receipt))

    def test_outcome_inconsistent_with_status_fails_verification(self) -> None:
        forged = {
            "gate": "fake gate",
            "argv": ["fake"],
            "status": 1,
            "signal": None,
            "outcome": gate_receipt.OUTCOME_PASSED,  # a lie the self_digest alone cannot catch
            "log_digest": _sha256_hex(b""),
            "toolchain_digest": _sha256_hex(LOCK_BYTES),
            "cwd": "/tmp/fixture",
        }
        forged = _reseal(forged)
        # The digest itself is internally consistent (positive control on the channel)...
        self.assertEqual(
            gate_receipt.canonical_digest({k: v for k, v in forged.items() if k != "self_digest"}),
            forged["self_digest"],
        )
        # ...yet the receipt is rejected, because outcome must agree with status.
        self.assertFalse(gate_receipt.verify_receipt(forged))
        self.assertTrue(gate_receipt.verify_receipt(_reseal(dict(forged, outcome=gate_receipt.OUTCOME_FAILED))))

    def test_a_receipt_cannot_name_an_executed_command_and_report_nothing_observed(self) -> None:
        """The F2 state: status null, outcome unobserved, argv still populated."""
        contradictory = _reseal(
            {
                "gate": "mise run check",
                "argv": ["mise", "run", "check"],  # claims this ran...
                "status": None,  # ...while claiming nothing was observed
                "signal": None,
                "outcome": gate_receipt.OUTCOME_UNOBSERVED,
                "log_digest": _sha256_hex(b""),
                "toolchain_digest": _sha256_hex(LOCK_BYTES),
                "cwd": "/tmp/fixture",
            }
        )
        self.assertFalse(gate_receipt.verify_receipt(contradictory))
        # The two honest readings of that state both verify, so the rejection is about the
        # contradiction and not about `unobserved` or about a populated argv per se.
        nothing_ran = _reseal(dict(contradictory, argv=None))
        self.assertTrue(gate_receipt.verify_receipt(nothing_ran))
        ran_and_was_killed = _reseal(dict(contradictory, signal=9))
        self.assertTrue(gate_receipt.verify_receipt(ran_and_was_killed))

    def test_dishonest_argv_status_and_signal_combinations_fail_verification(self) -> None:
        honest = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=0,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
        )
        self.assertTrue(gate_receipt.verify_receipt(honest))  # positive control on the channel
        for label, patch in (
            ("a verdict with nothing executed", {"argv": None}),
            ("killed yet still returning an exit code", {"signal": 9}),
            ("killed with nothing executed", {"argv": None, "status": None, "signal": 9}),
            ("a negative status posing as an exit code", {"status": -9}),
            ("argv as a string instead of a list", {"argv": "mise run check"}),
            # A list of non-strings is not an argv either: `all(isinstance(a, str))` is what
            # rejects it, and the string case above cannot observe that clause (every character
            # of a string IS a string, so it passes the element test and fails the list test).
            ("argv holding values that are not strings", {"argv": [123]}),
            ("argv mixing a string with a non-string", {"argv": ["mise", None]}),
            ("a boolean status", {"status": False}),
            # `status` must be an int or null. A stringly-typed or float status would otherwise
            # survive, because derive_outcome coerces it and then agrees with itself.
            ("a stringly-typed status", {"status": "0"}),
            ("a float status", {"status": 0.0}),
            # `signal: 0` beside a POPULATED argv is the only shape that reaches the `signal > 0`
            # clause. With `argv: null` it is rejected earlier, for being killed with nothing
            # executed — so that spelling names this guard without observing it.
            ("a signal of zero", {"argv": None, "status": None, "signal": 0}),
            ("a signal of zero beside a command that ran", {"status": None, "signal": 0}),
            ("a boolean signal", {"status": None, "signal": True}),
        ):
            with self.subTest(label=label):
                forged = _reseal(dict(honest, **patch))
                forged = _reseal(dict(forged, outcome=gate_receipt.derive_outcome(forged.get("status"))))
                self.assertFalse(gate_receipt.verify_receipt(forged), label)

    def test_verification_requires_a_real_string_digest(self) -> None:
        """`self_digest` must be a string, not an object that merely claims to compare equal."""

        class AlwaysEqual:
            """A non-JSON value a Python caller could pass in; JSON parsing cannot produce it."""

            def __eq__(self, other: object) -> bool:
                return True

            def __ne__(self, other: object) -> bool:
                return False

        body = {
            "gate": "mise run check",
            "argv": ["mise", "run", "check"],
            "status": 0,
            "signal": None,
            "outcome": gate_receipt.OUTCOME_PASSED,
            "log_digest": _sha256_hex(b""),
            "toolchain_digest": _sha256_hex(LOCK_BYTES),
            "cwd": "/tmp/fixture",
        }
        self.assertFalse(gate_receipt.verify_receipt(dict(body, self_digest=AlwaysEqual())))
        # A missing digest is refused for the same reason: there is nothing to re-derive against.
        self.assertFalse(gate_receipt.verify_receipt(dict(body)))
        # POSITIVE CONTROL: the real digest over the same body verifies, so the rejections above
        # are about the digest's type and not about the body.
        self.assertTrue(gate_receipt.verify_receipt(_reseal(body)))

    def test_pre_outcome_receipts_are_exempt_from_the_state_invariants(self) -> None:
        """The four honest states bind receipts that CARRY `outcome`; older ones predate them.

        Applying the invariants to a pre-`outcome` receipt would retroactively invalidate evidence
        that was honest under the contract it was written to, so the exemption is the compatibility
        promise itself — and it is exactly as narrow as "no `outcome` field".
        """
        # `argv: null` beside `status: 0` is one of the states `_states_are_consistent` rejects.
        self.assertFalse(gate_receipt._states_are_consistent({"argv": None, "status": 0, "signal": None}))
        legacy_body = {
            "gate": "mise run check",
            "argv": None,
            "status": 0,
            "log_digest": _sha256_hex(b""),
            "toolchain_digest": _sha256_hex(LOCK_BYTES),
            "cwd": "/tmp/fixture",
        }
        legacy = dict(legacy_body)
        legacy["self_digest"] = gate_receipt.canonical_digest(legacy_body)
        self.assertNotIn("outcome", legacy)
        self.assertTrue(gate_receipt.verify_receipt(legacy))
        # The moment the same shape claims an `outcome`, the invariants apply and reject it.
        self.assertFalse(gate_receipt.verify_receipt(_reseal(dict(legacy_body, outcome="passed"))))
        # POSITIVE CONTROL: re-derivation still protects the exempt receipt from tampering.
        self.assertFalse(gate_receipt.verify_receipt(dict(legacy, cwd="/tmp/elsewhere")))

    def test_pre_outcome_receipts_remain_verifiable(self) -> None:
        """Adding a field changes the digest of NEW receipts only."""
        legacy_body = {
            "gate": "mise run check",
            "argv": ["mise", "run", "check"],
            "status": 0,
            "log_digest": _sha256_hex(b"legacy log\n"),
            "toolchain_digest": _sha256_hex(LOCK_BYTES),
            "cwd": "/tmp/fixture",
        }
        legacy = dict(legacy_body)
        legacy["self_digest"] = gate_receipt.canonical_digest(legacy_body)
        self.assertNotIn("outcome", legacy)
        self.assertNotIn("signal", legacy)
        self.assertTrue(gate_receipt.verify_receipt(legacy))
        # POSITIVE CONTROL: this verification channel does reject a mutated legacy receipt.
        self.assertFalse(gate_receipt.verify_receipt(dict(legacy, status=1)))
        # A newly built receipt over the same inputs carries outcome and so digests differently.
        fresh = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=0,
            log_bytes=b"legacy log\n",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
        )
        self.assertIn("outcome", fresh)
        self.assertIn("signal", fresh)
        self.assertNotEqual(fresh["self_digest"], legacy["self_digest"])
        self.assertTrue(gate_receipt.verify_receipt(fresh))


if __name__ == "__main__":
    unittest.main()
