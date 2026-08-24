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
import gc
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings
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
        # The producer hashes the gate's raw emitted BYTES, and tests assert that digest over
        # exact LF content; a text-mode `sys.stdout.write` would let Windows translate \n to
        # \r\n in the pipe, changing the hashed subject, so the gate emits exact bytes.
        "sys.stdout.buffer.write(b'fake gate stdout\\n')",
        "sys.stdout.buffer.flush()",
        "sys.stderr.buffer.write(b'fake gate stderr\\n')",
        "sys.stderr.buffer.flush()",
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

    @unittest.skipUnless(POSIX, "SIGKILL and negative returncodes are POSIX signal semantics")
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
            status = real_wait(proc, *rest, **kwargs)  # type: ignore[arg-type]
            # Scoped to the GATE by exact argv: the producer's `head` stamp spawns `git rev-parse`
            # children too (agentic-sdlc-5ee7), and raising on the first of those would abort before
            # the gate ever ran — which is the opposite of the window this test is about.
            if list(proc.args) != argv:
                return status
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

    def test_a_mirror_write_failure_after_the_gate_ran_still_writes_the_receipt(self) -> None:
        """A mirror that genuinely fails costs the MIRROR, never the receipt of a gate that ran.

        This test previously asserted the opposite — 4, with no receipt — and that was the defect
        rather than the contract. `_stderr_mirror` states the rule it broke: the mirror is a
        convenience `--quiet` switches off, never the evidence. Under `EPIPE` the gate had still
        run, its bytes were still captured, and `log_digest` was still exact, so the only honest
        outcome is the receipt plus the gate's real verdict; escalating to 4 let an optional
        DISPLAY channel destroy a mandatory artifact and hand back a partial-effect code for a
        complete one. The exit-4 path stays reachable through the failures that genuinely leave the
        result unknown: `wait` raising inside the run window (above) and a destination created but
        not written (`_write_new_file`).
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
        # POSITIVE CONTROL on the injection: the mirror was REACHED and it DID fail. Without this
        # the assertions below would also pass on a run that never mirrored a byte.
        self.assertTrue(broken.buffer.write.called)
        self.assertIsInstance(broken.buffer.write.side_effect, OSError)
        self.assertTrue(marker.exists())  # the gate ran...
        self.assertEqual(code, gate_receipt.EXIT_OK, text)  # ...and its verdict is what came back
        self.assertNotEqual(code, gate_receipt.EXIT_PARTIAL)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        self.assertEqual(receipt["outcome"], "passed")
        # The mirror is display, so losing it changed nothing about what was hashed.
        self.assertEqual(receipt["log_digest"], _sha256_hex(b"fake gate stdout\nfake gate stderr\n"))
        self.assertNotIn("PARTIAL", text)  # nothing partial happened: the receipt is complete
        self.assertNotIn("BrokenPipeError", text)

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


# --------------------------------------------------------------------------------------------
# `baselined` = a receipt that carries the SET of named failing tests (operator decision,
# 2026-08-17). These tests exercise the identity extraction on GENUINE unittest output wherever
# possible: the "fake gate" is a real `python -m unittest` run over a generated module, so the
# parser is checked against the harness rather than against a hand-written imitation of it.
# --------------------------------------------------------------------------------------------


def _write_unittest_gate(directory: Path, module: str, source: str) -> list[str]:
    """A gate that IS a real unittest invocation. Returns the argv that runs it."""
    (directory / f"{module}.py").write_text(source, encoding="utf-8")
    # `-B` keeps a stale .pyc from a same-second rewrite out of the picture; `-m unittest`
    # puts the gate's cwd on sys.path, which is where the generated module lives.
    return [sys.executable, "-B", "-m", "unittest", module]


def _suite(failing: tuple[str, ...] = (), passing: tuple[str, ...] = ()) -> str:
    lines = ["import unittest", "", "", "class Suite(unittest.TestCase):"]
    for name in failing:
        lines += [f"    def {name}(self):", "        self.fail('injected')"]
    for name in passing:
        lines += [f"    def {name}(self):", "        pass"]
    return "\n".join(lines) + "\n"


def _write_canned_gate(directory: Path, *, text: str, exit_code: int, name: str) -> list[str]:
    """A gate that replays exact bytes, for harness shapes this Python cannot produce."""
    script = directory / name
    script.write_text(
        f"import sys\nsys.stdout.write({text!r})\nsys.exit({exit_code})\n", encoding="utf-8"
    )
    return [sys.executable, "-B", str(script)]


def _unittest_log(headers: tuple[str, ...], summary: str, *, ran: int = 3) -> str:
    """A unittest-shaped log with caller-chosen header lines and a caller-chosen tally line."""
    parts: list[str] = []
    for header in headers:
        parts += [
            "=" * 70,
            header,
            "-" * 70,
            "Traceback (most recent call last):",
            "AssertionError: injected",
            "",
        ]
    parts += ["-" * 70, f"Ran {ran} tests in 0.001s", "", summary, ""]
    return "\n".join(parts)


class FailureIdentityTests(_ProducerTestCase):
    """The receipt records WHICH tests failed, by a stable path-free identity, or says it cannot."""

    def _record(
        self, argv: list[str], *, out: Path, harness: str | None = "unittest"
    ) -> subprocess.CompletedProcess[str]:
        args = ["record", "--gate", "fake gate", "--out", str(out), "--lock", str(self.lock), "--quiet"]
        if harness is not None:
            args += ["--harness", harness]
        return self._run([*args, "--", *argv])

    def _receipt(self, out: Path) -> dict[str, object]:
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        return receipt

    def test_a_failing_run_records_the_named_failing_set(self) -> None:
        argv = _write_unittest_gate(
            self.tmp, "red_suite", _suite(failing=("test_alpha", "test_beta"), passing=("test_ok",))
        )
        out = self.tmp / "receipt.json"
        proc = self._record(argv, out=out)
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        receipt = self._receipt(out)
        self.assertEqual(receipt["outcome"], "failed")
        self.assertEqual(
            receipt["failures"],
            {
                "harness": "unittest",
                "state": "identified",
                # A method name alone is ambiguous across modules, so the identity is the
                # fully-qualified dotted test id: module, class, and method.
                "names": ["red_suite.Suite.test_alpha", "red_suite.Suite.test_beta"],
            },
        )

    def test_the_failing_set_is_covered_by_the_self_digest(self) -> None:
        argv = _write_unittest_gate(self.tmp, "sealed_suite", _suite(failing=("test_one",)))
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        receipt = self._receipt(out)  # positive control: it verifies as written
        edited = json.loads(json.dumps(receipt))
        edited["failures"]["names"] = []  # the whole point: dropping a failure must be detectable
        self.assertFalse(gate_receipt.verify_receipt(edited))
        renamed = json.loads(json.dumps(receipt))
        renamed["failures"]["names"] = ["sealed_suite.Suite.test_other"]
        self.assertFalse(gate_receipt.verify_receipt(renamed))
        rehashed = json.loads(json.dumps(receipt))
        del rehashed["failures"]  # removing the field wholesale is caught too
        self.assertFalse(gate_receipt.verify_receipt(rehashed))

    def test_the_identity_is_stable_across_runs_on_the_same_tree(self) -> None:
        argv = _write_unittest_gate(self.tmp, "stable_suite", _suite(failing=("test_x", "test_y")))
        first = self.tmp / "first.json"
        second = self.tmp / "second.json"
        self._record(argv, out=first)
        self._record(argv, out=second)
        one, two = self._receipt(first), self._receipt(second)
        self.assertEqual(one["failures"], two["failures"])
        self.assertEqual(one["failures"]["names"], ["stable_suite.Suite.test_x", "stable_suite.Suite.test_y"])
        # POSITIVE CONTROL: the field is not a constant that would match anything. Rewriting the
        # module so a DIFFERENT test fails changes the recorded identities, so the equality above is
        # stability across runs rather than a channel that never varies.
        moved = self.tmp / "moved.json"
        self._record(_write_unittest_gate(self.tmp, "stable_suite", _suite(failing=("test_z",))), out=moved)
        self.assertEqual(self._receipt(moved)["failures"]["names"], ["stable_suite.Suite.test_z"])

    def test_subtest_parameters_are_stripped_so_no_identity_embeds_a_mutable_path(self) -> None:
        """Real subtest headers carry their parameters — and those can contain absolute paths."""
        source = "\n".join(
            [
                "import unittest",
                "",
                "",
                "class Suite(unittest.TestCase):",
                "    def test_many(self):",
                "        for label in ('/tmp/moves/every/run', 'second'):",
                "            with self.subTest(label=label):",
                "                self.fail('injected')",
                "",
            ]
        )
        argv = _write_unittest_gate(self.tmp, "sub_suite", source)
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
                "--harness",
                "unittest",
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        receipt = self._receipt(out)
        # POSITIVE CONTROL for the observation channel: the harness really did print the path, so
        # its absence from the identity is the stripping at work and not an empty channel.
        self.assertIn(b"/tmp/moves/every/run", log.read_bytes())
        self.assertEqual(receipt["failures"]["names"], ["sub_suite.Suite.test_many"])
        for name in receipt["failures"]["names"]:
            self.assertNotIn("/", name)

    def test_a_class_fixture_error_is_named_by_the_fixture_it_ran_in(self) -> None:
        """`ERROR: setUpClass (mod.Cls)` names no method, so the identity has to be composed."""
        source = "\n".join(
            [
                "import unittest",
                "",
                "",
                "class Suite(unittest.TestCase):",
                "    @classmethod",
                "    def setUpClass(cls):",
                "        raise RuntimeError('injected')",
                "",
                "    def test_never_runs(self):",
                "        pass",
                "",
            ]
        )
        argv = _write_unittest_gate(self.tmp, "fixture_suite", source)
        out = self.tmp / "receipt.json"
        proc = self._record(argv, out=out)
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        self.assertEqual(
            self._receipt(out)["failures"]["names"], ["fixture_suite.Suite.setUpClass"]
        )

    def test_an_unexpected_success_is_a_named_non_pass_not_a_silent_one(self) -> None:
        """It turns the run red and unittest prints its name, so it belongs in the set."""
        source = "\n".join(
            [
                "import unittest",
                "",
                "",
                "class Suite(unittest.TestCase):",
                "    @unittest.expectedFailure",
                "    def test_should_have_failed(self):",
                "        pass",
                "",
            ]
        )
        argv = _write_unittest_gate(self.tmp, "unexpected_suite", source)
        out = self.tmp / "receipt.json"
        proc = self._record(argv, out=out)
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        receipt = self._receipt(out)
        self.assertEqual(receipt["failures"]["state"], "identified")
        self.assertEqual(
            receipt["failures"]["names"], ["unexpected_suite.Suite.test_should_have_failed"]
        )

    def test_a_green_run_records_an_empty_identified_set(self) -> None:
        """Skips and EXPECTED failures are not failures — and `expected failures=1` is not a tally."""
        source = "\n".join(
            [
                "import unittest",
                "",
                "",
                "class Suite(unittest.TestCase):",
                "    def test_ok(self):",
                "        pass",
                "",
                "    def test_skipped(self):",
                "        self.skipTest('injected')",
                "",
                "    @unittest.expectedFailure",
                "    def test_expected(self):",
                "        self.fail('injected')",
                "",
            ]
        )
        argv = _write_unittest_gate(self.tmp, "green_suite", source)
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
                "--harness",
                "unittest",
                "--quiet",
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_OK, proc.stderr)
        receipt = self._receipt(out)
        # POSITIVE CONTROL: the tally line really does say `expected failures=1`, so reading it as
        # one failure would be an observable defect rather than a hypothetical one.
        self.assertIn(b"expected failures=1", log.read_bytes())
        self.assertEqual(
            receipt["failures"], {"harness": "unittest", "state": "identified", "names": []}
        )

    def test_unparseable_harness_output_is_never_a_silently_empty_failure_set(self) -> None:
        """A red gate with no readable tally must SAY so; an empty set would read as clean."""
        argv = _write_canned_gate(
            self.tmp, text="make: *** [check] Error 2\n", exit_code=2, name="opaque.py"
        )
        out = self.tmp / "receipt.json"
        proc = self._record(argv, out=out)
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        receipt = self._receipt(out)
        self.assertEqual(
            receipt["failures"], {"harness": "unittest", "state": "unparsed", "names": []}
        )
        self.assertNotEqual(receipt["failures"]["state"], "identified")
        # The operator is told at record time, not left to discover it at comparison time.
        self.assertIn("no failing test could be identified", proc.stderr)
        # POSITIVE CONTROL: a real harness run through the identical invocation IS identified, so
        # `unparsed` above is about this gate's output and not about the option being inert.
        ok_out = self.tmp / "identified.json"
        self._record(_write_unittest_gate(self.tmp, "control_suite", _suite(failing=("test_a",))), out=ok_out)
        self.assertEqual(self._receipt(ok_out)["failures"]["state"], "identified")

    def test_a_tally_that_disagrees_with_the_named_headers_is_unparsed(self) -> None:
        """The harness's own count is the integrity check on the scrape: 2 declared, 1 named."""
        text = _unittest_log(("FAIL: test_a (mod.Suite.test_a)",), "FAILED (failures=2)")
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="mismatch.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        receipt = self._receipt(out)
        self.assertEqual(receipt["failures"]["state"], "unparsed")
        self.assertEqual(receipt["failures"]["names"], [])
        # POSITIVE CONTROL: the same log with an agreeing tally IS identified, so the rejection is
        # the cross-check and not a parser that cannot read this shape at all.
        agreeing = _unittest_log(("FAIL: test_a (mod.Suite.test_a)",), "FAILED (failures=1)")
        ok_out = self.tmp / "agree.json"
        self._record(
            _write_canned_gate(self.tmp, text=agreeing, exit_code=1, name="agree.py"), out=ok_out
        )
        self.assertEqual(self._receipt(ok_out)["failures"]["names"], ["mod.Suite.test_a"])

    def test_a_log_with_no_tally_line_at_all_is_unparsed(self) -> None:
        """Headers without a summary mean the harness never finished reporting."""
        text = "=" * 70 + "\nFAIL: test_a (mod.Suite.test_a)\n" + "-" * 70 + "\nkilled\n"
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="truncated.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        self.assertEqual(self._receipt(out)["failures"]["state"], "unparsed")

    def test_an_unknown_tally_key_is_unparsed_rather_than_guessed(self) -> None:
        text = _unittest_log(("FAIL: test_a (mod.Suite.test_a)",), "FAILED (failures=1, quarantined=4)")
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="unknown_key.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        self.assertEqual(self._receipt(out)["failures"]["state"], "unparsed")

    def test_a_tally_item_that_is_not_key_equals_count_is_unparsed_not_partly_read(self) -> None:
        """An unreadable tally ITEM voids the whole tally; the readable items are not summed alone.

        `quarantined=4` above is an unknown KEY that still has the `key=count` shape. This is the
        weaker case: an item that does not even have that shape, so nothing can be concluded about
        whether it declares non-passes. Summing only the items that happened to parse would produce
        a tally that agrees with the headers by accident and seal a failing set the harness never
        confirmed.
        """
        text = _unittest_log(("FAIL: test_a (mod.Suite.test_a)",), "FAILED (failures=1, bogus)")
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="bogus_item.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        receipt = self._receipt(out)
        self.assertEqual(receipt["failures"]["state"], "unparsed")
        self.assertEqual(receipt["failures"]["names"], [])
        # POSITIVE CONTROL: drop the unreadable item and the SAME log identifies the same one
        # failure, so the refusal is the unreadable item and not this log shape.
        readable = _unittest_log(("FAIL: test_a (mod.Suite.test_a)",), "FAILED (failures=1)")
        ok_out = self.tmp / "readable.json"
        self._record(
            _write_canned_gate(self.tmp, text=readable, exit_code=1, name="readable_item.py"),
            out=ok_out,
        )
        self.assertEqual(self._receipt(ok_out)["failures"]["state"], "identified")
        self.assertEqual(self._receipt(ok_out)["failures"]["names"], ["mod.Suite.test_a"])

    def test_one_runs_unreadable_tally_voids_the_whole_log_not_just_that_run(self) -> None:
        """A gate runs several suites; one unreadable tally makes the WHOLE failing set unknown.

        The dangerous shape is an unreadable tally on a run that reported no headers, beside a second
        run whose tally and headers agree. Skipping the unreadable run instead of voiding the log
        leaves a set that is internally consistent and SHORT — it silently omits whatever the first
        run failed — which is the under-reporting a later subset comparison cannot detect.
        """
        text = _unittest_log((), "FAILED (bogus)") + _unittest_log(
            ("FAIL: test_b (two.Suite.test_b)",), "FAILED (failures=1)"
        )
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="one_void_run.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        receipt = self._receipt(out)
        self.assertEqual(receipt["failures"]["state"], "unparsed")
        self.assertEqual(receipt["failures"]["names"], [])
        # POSITIVE CONTROL: make the first run's tally readable and the very same two-run log is
        # identified, naming the second run's failure. So the refusal is the unreadable tally, not
        # the multi-run shape and not the headerless first run.
        readable = _unittest_log((), "OK") + _unittest_log(
            ("FAIL: test_b (two.Suite.test_b)",), "FAILED (failures=1)"
        )
        ok_out = self.tmp / "both_readable.json"
        self._record(
            _write_canned_gate(self.tmp, text=readable, exit_code=1, name="both_readable.py"),
            out=ok_out,
        )
        self.assertEqual(self._receipt(ok_out)["failures"]["state"], "identified")
        self.assertEqual(self._receipt(ok_out)["failures"]["names"], ["two.Suite.test_b"])

    def test_a_header_shape_that_cannot_be_identified_forces_unparsed(self) -> None:
        """Counting a header we cannot name and then omitting it is the silent-loss defect."""
        text = _unittest_log(("FAIL: some description with no dotted id",), "FAILED (failures=1)")
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="unnamed.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        receipt = self._receipt(out)
        self.assertEqual(receipt["failures"]["state"], "unparsed")
        self.assertEqual(receipt["failures"]["names"], [])

    def test_an_older_harness_header_without_the_method_still_composes_an_identity(self) -> None:
        """Python <=3.10 printed `FAIL: test_a (mod.Suite)`; the method is the leading word."""
        text = _unittest_log(
            ("FAIL: test_a (mod.Suite)", "ERROR: test_b (mod.Suite)"), "FAILED (failures=1, errors=1)"
        )
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="legacy_shape.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        self.assertEqual(
            self._receipt(out)["failures"]["names"], ["mod.Suite.test_a", "mod.Suite.test_b"]
        )

    def test_a_single_segment_identity_is_refused_as_ambiguous(self) -> None:
        """A bare name is ambiguous across modules, which is why the identity is qualified."""
        text = _unittest_log(("FAIL: test_a (test_a)",), "FAILED (failures=1)")
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="bare.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        self.assertEqual(self._receipt(out)["failures"]["state"], "unparsed")

    def test_two_harness_runs_in_one_gate_are_summed(self) -> None:
        """`mise run check` runs several suites, so one gate log carries several tallies."""
        text = _unittest_log(("FAIL: test_a (one.Suite.test_a)",), "FAILED (failures=1)") + _unittest_log(
            ("ERROR: test_b (two.Suite.test_b)",), "FAILED (errors=1)"
        )
        argv = _write_canned_gate(self.tmp, text=text, exit_code=1, name="two_runs.py")
        out = self.tmp / "receipt.json"
        self._record(argv, out=out)
        self.assertEqual(
            self._receipt(out)["failures"]["names"], ["one.Suite.test_a", "two.Suite.test_b"]
        )

    def test_an_unobserved_gate_names_no_failures(self) -> None:
        """Nothing ran, so there is no failing set to name — and `unparsed` says exactly that."""
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
                "--harness",
                "unittest",
                "--unobserved",
                "--",
                *_write_unittest_gate(self.tmp, "never_suite", _suite(failing=("test_a",))),
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_UNOBSERVED, proc.stderr)
        receipt = self._receipt(out)
        self.assertIsNone(receipt["argv"])
        self.assertEqual(receipt["failures"], {"harness": "unittest", "state": "unparsed", "names": []})

    def test_without_the_harness_option_the_receipt_is_byte_identical_to_before(self) -> None:
        """Additive: an unrequested field is ABSENT, so the digest of an old-shaped receipt holds."""
        argv = _write_unittest_gate(self.tmp, "silent_suite", _suite(failing=("test_a",)))
        out = self.tmp / "receipt.json"
        self._record(argv, out=out, harness=None)
        receipt = self._receipt(out)
        self.assertNotIn("failures", receipt)
        explicit = self.tmp / "explicit-none.json"
        self._record(argv, out=explicit, harness="none")
        self.assertNotIn("failures", self._receipt(explicit))
        # The pre-change digest still re-derives over the same inputs.
        rebuilt = gate_receipt.build_receipt(
            gate=receipt["gate"],
            argv=receipt["argv"],
            status=receipt["status"],
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd=receipt["cwd"],
        )
        self.assertNotIn("failures", rebuilt)
        self.assertEqual(
            gate_receipt.canonical_digest({k: v for k, v in receipt.items() if k != "self_digest"}),
            receipt["self_digest"],
        )

    def test_pre_failures_receipts_keep_verifying(self) -> None:
        """A receipt written before this field existed carries no `failures` and still verifies."""
        legacy = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=1,
            log_bytes=b"FAILED (failures=1)\n",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
        )
        self.assertNotIn("failures", legacy)
        self.assertTrue(gate_receipt.verify_receipt(legacy))
        fresh = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=1,
            log_bytes=b"FAILED (failures=1)\n",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
            failures={"harness": "unittest", "state": "identified", "names": ["m.C.t"]},
        )
        self.assertTrue(gate_receipt.verify_receipt(fresh))
        self.assertNotEqual(fresh["self_digest"], legacy["self_digest"])
        # POSITIVE CONTROL: re-derivation still protects the legacy receipt from tampering.
        self.assertFalse(gate_receipt.verify_receipt(dict(legacy, status=0)))

    def test_the_producer_exit_space_is_unchanged_by_the_harness_option(self) -> None:
        """Recording failure identities is not a verdict: the seven codes keep their meanings."""
        cases = (
            (_suite(passing=("test_ok",)), gate_receipt.EXIT_OK, "pass_suite"),
            (_suite(failing=("test_bad",)), gate_receipt.EXIT_GATE_FAILED, "fail_suite"),
        )
        for source, expected, module in cases:
            with self.subTest(module=module):
                out = self.tmp / f"{module}.json"
                proc = self._record(_write_unittest_gate(self.tmp, module, source), out=out)
                self.assertEqual(proc.returncode, expected, proc.stderr)

    def test_an_unknown_harness_is_an_input_error_before_the_gate_runs(self) -> None:
        marker = self.tmp / "harness.marker"
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
                "--harness",
                "pytest",
                "--",
                *argv,
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE, proc.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse((self.tmp / "receipt.json").exists())


class FailureSetInvariantTests(unittest.TestCase):
    """A stored failing set must be well-formed, or it cannot be compared as a set at all."""

    def _sealed(self, failures: object, **overrides: object) -> dict[str, object]:
        body = {
            "gate": "mise run check",
            "argv": ["mise", "run", "check"],
            "status": 1,
            "signal": None,
            "outcome": gate_receipt.OUTCOME_FAILED,
            "log_digest": _sha256_hex(b""),
            "toolchain_digest": _sha256_hex(LOCK_BYTES),
            "cwd": "/tmp/fixture",
            "failures": failures,
        }
        body.update(overrides)
        return _reseal(body)

    def test_a_well_formed_failing_set_verifies(self) -> None:
        """POSITIVE CONTROL for every rejection below: this channel does accept a good record."""
        self.assertTrue(
            gate_receipt.verify_receipt(
                self._sealed({"harness": "unittest", "state": "identified", "names": ["m.C.t"]})
            )
        )

    def test_malformed_failing_sets_fail_verification(self) -> None:
        cases = {
            "not an object": ["m.C.t"],
            "a bare list of names": {"names": ["m.C.t"]},
            "an unknown state": {"harness": "unittest", "state": "guessed", "names": []},
            "an extra key": {
                "harness": "unittest",
                "state": "identified",
                "names": [],
                "reason": "why",
            },
            "a missing harness": {"state": "identified", "names": []},
            "an empty harness": {"harness": "", "state": "identified", "names": []},
            "names that are not a list": {"harness": "unittest", "state": "identified", "names": "m.C.t"},
            "names out of canonical order": {
                "harness": "unittest",
                "state": "identified",
                "names": ["m.C.z", "m.C.a"],
            },
            "duplicate names": {
                "harness": "unittest",
                "state": "identified",
                "names": ["m.C.a", "m.C.a"],
            },
            "a name that is not a string": {"harness": "unittest", "state": "identified", "names": [1]},
            "an empty name": {"harness": "unittest", "state": "identified", "names": [""]},
            "a name embedding an absolute path": {
                "harness": "unittest",
                "state": "identified",
                "names": ["/mnt/e/repo/tests/test_x.py::test_a"],
            },
            "a single-segment name": {"harness": "unittest", "state": "identified", "names": ["test_a"]},
            "a subtest-parameterised name": {
                "harness": "unittest",
                "state": "identified",
                "names": ["m.C.t (label='x')"],
            },
            "names beside an unparsed state": {
                "harness": "unittest",
                "state": "unparsed",
                "names": ["m.C.t"],
            },
            # JSON can carry this, and without the list check the per-name loop raises TypeError out
            # of verify_receipt instead of returning False — which a consumer reads as an internal
            # failure rather than as an unusable receipt.
            "names that are not iterable at all": {
                "harness": "unittest",
                "state": "identified",
                "names": 7,
            },
        }
        for label, failures in cases.items():
            with self.subTest(label=label):
                self.assertFalse(gate_receipt.verify_receipt(self._sealed(failures)), label)

    def test_nothing_executed_cannot_name_a_failing_test(self) -> None:
        """`argv: null` means nothing ran, so a named failure would have come from nowhere."""
        nothing_ran = self._sealed(
            {"harness": "unittest", "state": "identified", "names": ["m.C.t"]},
            argv=None,
            status=None,
            outcome=gate_receipt.OUTCOME_UNOBSERVED,
        )
        self.assertFalse(gate_receipt.verify_receipt(nothing_ran))
        # The two honest readings of that receipt both verify, so the rejection is about the
        # contradiction and not about `unobserved` or about an empty set per se.
        self.assertTrue(
            gate_receipt.verify_receipt(
                self._sealed(
                    {"harness": "unittest", "state": "unparsed", "names": []},
                    argv=None,
                    status=None,
                    outcome=gate_receipt.OUTCOME_UNOBSERVED,
                )
            )
        )
        self.assertTrue(
            gate_receipt.verify_receipt(
                self._sealed({"harness": "unittest", "state": "identified", "names": ["m.C.t"]})
            )
        )

    def test_build_receipt_normalizes_a_callers_unordered_names(self) -> None:
        """The `int()`-coercion precedent: never emit a receipt that fails its own verification."""
        receipt = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=1,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
            failures={
                "harness": "unittest",
                "state": "identified",
                "names": ["m.C.z", "m.C.a", "m.C.z"],
            },
        )
        self.assertEqual(receipt["failures"]["names"], ["m.C.a", "m.C.z"])
        self.assertTrue(gate_receipt.verify_receipt(receipt))

    def test_build_receipt_refuses_a_failing_set_it_could_not_seal_honestly(self) -> None:
        """Emitting an unverifiable receipt would be worse than raising on caller error."""
        cases = (
            ({"harness": "unittest", "state": "identified", "names": ["/abs/path.py::t"]}, ["x"]),
            ({"harness": "unittest", "state": "guessed", "names": []}, ["x"]),
            ({"harness": "unittest", "state": "unparsed", "names": ["m.C.t"]}, ["x"]),
            ({"state": "identified", "names": []}, ["x"]),
            ({"harness": "unittest", "state": "identified", "names": 7}, ["x"]),
            # Nothing executed, yet a failing test is named: the receipt would fail its own
            # verification, so raising is the only honest response.
            ({"harness": "unittest", "state": "identified", "names": ["m.C.t"]}, None),
        )
        for failures, argv in cases:
            with self.subTest(failures=failures, argv=argv):
                with self.assertRaises(ValueError):
                    gate_receipt.build_receipt(
                        gate="mise run check",
                        argv=argv,
                        status=1 if argv else None,
                        log_bytes=b"",
                        lock_bytes=LOCK_BYTES,
                        cwd="/tmp/fixture",
                        failures=failures,
                    )
        # POSITIVE CONTROL: the same names WITH something executed are sealed and verify, so the
        # last rejection is the argv cross-check and not the names themselves.
        sealed = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=1,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd="/tmp/fixture",
            failures={"harness": "unittest", "state": "identified", "names": ["m.C.t"]},
        )
        self.assertTrue(gate_receipt.verify_receipt(sealed))

    def test_extraction_of_a_captured_log_is_a_pure_function_of_its_bytes(self) -> None:
        red = gate_receipt.extract_unittest_failures(
            _unittest_log(("FAIL: test_a (m.C.test_a)",), "FAILED (failures=1)").encode("utf-8")
        )
        self.assertEqual(red, {"harness": "unittest", "state": "identified", "names": ["m.C.test_a"]})
        green = gate_receipt.extract_unittest_failures(b"Ran 1 test in 0.001s\n\nOK\n")
        self.assertEqual(green, {"harness": "unittest", "state": "identified", "names": []})
        blank = gate_receipt.extract_unittest_failures(b"")
        self.assertEqual(blank, {"harness": "unittest", "state": "unparsed", "names": []})
        # Undecodable bytes are replaced, never raised: a receipt is still owed for this run.
        self.assertEqual(
            gate_receipt.extract_unittest_failures(b"\xff\xfe\nOK\n"),
            {"harness": "unittest", "state": "identified", "names": []},
        )


DECLARED_EXITS = frozenset(
    {
        gate_receipt.EXIT_OK,
        gate_receipt.EXIT_INTERNAL,
        gate_receipt.EXIT_USAGE,
        gate_receipt.EXIT_REFUSED,
        gate_receipt.EXIT_PARTIAL,
        gate_receipt.EXIT_GATE_FAILED,
        gate_receipt.EXIT_UNOBSERVED,
    }
)


def _run_with_hostile_stderr(
    argv: list[str], *, mode: str, cwd: Path
) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Two shapes, kept separate because they produced DIFFERENT wrong exit codes and neither is
    exotic — a caller closing fd 2, and a reader that goes away mid-run:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError`, not `OSError`.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write
                raises `EPIPE` AND leaves bytes pending in the stream's buffer, which the
                interpreter flushes again while finalizing — replacing the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would give the child a writable stream and
    test nothing. `_stderr_is_really_hostile` proves each mode reaches the child.
    """
    if mode == "closed":
        # `exec 2>&-` in the shell, so the interpreter itself starts without fd 2. Spelled exactly
        # as the reproduction was, rather than through `preexec_fn`.
        proc = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
        )
        return proc.returncode, proc.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd))
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def _stderr_is_really_hostile(mode: str, cwd: Path) -> str:
    """What a canary child OBSERVES about its own stderr under `mode`, reported over stdout.

    Every negative assertion in this file's hostile-stderr tests needs this: `sh` failing with
    ENOENT, or a mode that quietly hands the child a working stream, would let each of them pass
    while proving nothing at all.
    """
    canary = (
        "import sys\n"
        "if sys.stderr is None:\n"
        "    print('none')\n"
        "else:\n"
        "    try:\n"
        "        sys.stderr.write('x')\n"
        "        sys.stderr.flush()\n"
        "        print('writable')\n"
        "    except OSError as exc:\n"
        "        print(type(exc).__name__)\n"
    )
    code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode=mode, cwd=cwd)
    return f"{code}:{out.decode('utf-8', 'replace').strip()}"


@unittest.skipUnless(POSIX, "fd-level stderr hostility is POSIX-only")
class HostileStderrTests(_ProducerTestCase):
    """A stderr that cannot be written is a DISPLAY failure, never an evidence or exit failure.

    Every case here was live on the branch. `record` against a red gate that had already run exited
    1 with no receipt under `2>&-` and 120 down a broken pipe, because the mirror raised inside the
    run window and `_report_failure` opened with another `sys.stderr.write`. The producer's exit
    space is closed (`DECLARED_EXITS`), so 120 must be unreachable rather than unlikely.
    """

    def _red_gate(self, marker: Path) -> list[str]:
        return _write_fake_gate(self.tmp, exit_code=7, marker=marker)

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every negative assertion below: the child really has no usable stderr.

        The canary's own exit codes are the second half of the control. Under `2>&-` it observes
        `sys.stderr is None` and exits cleanly, so `AttributeError` is what the producer had to
        survive there. Under a broken pipe it CATCHES the `BrokenPipeError` and still exits 120,
        because the bytes it left pending are flushed again while the interpreter finalizes — which
        is why swallowing the write is not on its own enough, and why the fix has to stop claiming
        the stream as well.
        """
        self.assertEqual(_stderr_is_really_hostile("closed", self.tmp), "0:none")
        self.assertEqual(_stderr_is_really_hostile("epipe", self.tmp), "120:BrokenPipeError")

    def test_a_hostile_stderr_cannot_cost_a_red_gate_its_receipt_or_its_verdict(self) -> None:
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                marker = self.tmp / f"ran-{mode}.marker"
                out = self.tmp / f"receipt-{mode}.json"
                code, stdout = _run_with_hostile_stderr(
                    [
                        sys.executable,
                        "-B",
                        str(SCRIPT),
                        "record",
                        "--gate",
                        "fake gate",
                        "--out",
                        str(out),
                        "--lock",
                        str(self.lock),
                        "--",  # NOT --quiet: the mirror must be live for this to mean anything
                        *self._red_gate(marker),
                    ],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertTrue(marker.exists())  # the gate ran, observed rather than assumed
                self.assertEqual(code, gate_receipt.EXIT_GATE_FAILED)
                self.assertIn(code, DECLARED_EXITS)  # 120 and 1 are both wrong answers here
                self.assertEqual(stdout, b"")  # the receipt went to --out, not onto stdout
                receipt = json.loads(out.read_text(encoding="utf-8"))
                self.assertTrue(gate_receipt.verify_receipt(receipt))
                self.assertEqual(receipt["status"], 7)
                self.assertEqual(receipt["outcome"], "failed")
                self.assertEqual(
                    receipt["log_digest"], _sha256_hex(b"fake gate stdout\nfake gate stderr\n")
                )
        # POSITIVE CONTROL: the identical command over a WORKING stderr returns the same code and a
        # receipt with the same digest, and it does write the mirrored gate output — so the runs
        # above lost the display channel and nothing else.
        marker = self.tmp / "ran-control.marker"
        out = self.tmp / "receipt-control.json"
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--",
                *self._red_gate(marker),
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_GATE_FAILED, proc.stderr)
        self.assertIn("fake gate stdout", proc.stderr)  # the channel the hostile runs lost
        self.assertEqual(
            json.loads(out.read_text(encoding="utf-8"))["log_digest"],
            _sha256_hex(b"fake gate stdout\nfake gate stderr\n"),
        )

    def test_a_hostile_stderr_cannot_cost_an_unobserved_receipt_that_quiet_never_silences(
        self,
    ) -> None:
        """`--quiet` silences the MIRROR; these notes are separate and were never suppressed.

        So this case isolates the advisory NOTE from the mirror: with `--quiet --unobserved` no gate
        runs and no byte is mirrored, and the single line at the top of `main` was still enough to
        lose the receipt entirely.
        """
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                out = self.tmp / f"unobserved-{mode}.json"
                code, _ = _run_with_hostile_stderr(
                    [
                        sys.executable,
                        "-B",
                        str(SCRIPT),
                        "record",
                        "--gate",
                        "fake gate",
                        "--out",
                        str(out),
                        "--lock",
                        str(self.lock),
                        "--quiet",
                        "--unobserved",
                        "--",
                        sys.executable,
                        "-c",
                        "raise SystemExit(0)",
                    ],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(code, gate_receipt.EXIT_UNOBSERVED)
                self.assertIn(code, DECLARED_EXITS)
                receipt = json.loads(out.read_text(encoding="utf-8"))
                self.assertTrue(gate_receipt.verify_receipt(receipt))
                self.assertIsNone(receipt["status"])
                self.assertIsNone(receipt["argv"])
        # POSITIVE CONTROL: the note IS written on this path under a working stderr, `--quiet` and
        # all — so the runs above suppressed a line that genuinely wanted writing.
        proc = self._run(
            [
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(self.tmp / "unobserved-control.json"),
                "--lock",
                str(self.lock),
                "--quiet",
                "--unobserved",
                "--",
                sys.executable,
                "-c",
                "raise SystemExit(0)",
            ]
        )
        self.assertEqual(proc.returncode, gate_receipt.EXIT_UNOBSERVED, proc.stderr)
        self.assertIn("recording an unobserved receipt", proc.stderr)

    def test_a_hostile_stderr_cannot_reclassify_a_clean_refusal(self) -> None:
        """A refusal BEFORE the gate ran must still read as 3, not as 1 and not as 120."""
        args = [
            "record",
            "--gate",
            "fake gate",
            "--out",
            str(self.tmp / "absent-dir" / "receipt.json"),
            "--lock",
            str(self.lock),
            "--quiet",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(0)",
        ]
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = _run_with_hostile_stderr(
                    [sys.executable, "-B", str(SCRIPT), *args], mode=mode, cwd=self.tmp
                )
                self.assertEqual(code, gate_receipt.EXIT_REFUSED)
                self.assertIn(code, DECLARED_EXITS)
        # POSITIVE CONTROL: the refusal is the named parent-directory one and it does report itself
        # on a working stderr, so the code above is that refusal rather than a crash that happens
        # to land on 3.
        proc = self._run(args)
        self.assertEqual(proc.returncode, gate_receipt.EXIT_REFUSED, proc.stderr)
        self.assertIn("does not exist", proc.stderr)

    def test_a_hostile_stderr_cannot_reclassify_a_usage_error(self) -> None:
        """The usage message and the usage CODE travel on different channels; only one may be lost."""
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, _ = _run_with_hostile_stderr(
                    [sys.executable, "-B", str(SCRIPT), "record", "--not-an-option"],
                    mode=mode,
                    cwd=self.tmp,
                )
                self.assertEqual(code, gate_receipt.EXIT_USAGE)
                self.assertIn(code, DECLARED_EXITS)
        # POSITIVE CONTROL: the same argv writes both usage lines to a working stderr.
        proc = self._run(["record", "--not-an-option"])
        self.assertEqual(proc.returncode, gate_receipt.EXIT_USAGE)
        self.assertIn("usage:", proc.stderr)
        self.assertIn("error:", proc.stderr)

    def test_a_broken_stdout_reports_partial_and_the_interpreter_cannot_overwrite_it(self) -> None:
        """The ARTIFACT channel's own failure: 4 is correct, and 120 used to replace it.

        `_report_failure` classified this one correctly all along and printed it; the interpreter
        then flushed the same broken stdout while finalizing and overwrote the exit code, so the
        caller was handed a code outside the contract for a failure the contract covers.
        """
        marker = self.tmp / "stdout-epipe.marker"
        argv = [
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
            *_write_fake_gate(self.tmp, exit_code=0, marker=marker),
        ]
        read_fd, write_fd = os.pipe()
        os.close(read_fd)  # nobody will ever read the receipt
        try:
            child = subprocess.Popen(argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(self.tmp))
        finally:
            os.close(write_fd)
        assert child.stderr is not None
        with child.stderr as stream:
            err = stream.read().decode("utf-8", "replace")
        code = child.wait()
        self.assertTrue(marker.exists())  # the gate ran, so this is a real partial result
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, err)
        self.assertIn(code, DECLARED_EXITS)
        self.assertNotEqual(code, 120)
        self.assertIn("already happened: the gate ran", err)
        # ...and the interpreter no longer complains about the stream it was left holding.
        self.assertNotIn("Exception ignored", err)
        # POSITIVE CONTROL: over a working stdout the same command emits one verifiable receipt and
        # returns the gate's verdict, so the 4 above is the broken pipe and not this argv.
        sink = self.tmp / "receipt-on-stdout.json"
        with sink.open("wb") as handle:
            ok = subprocess.run(argv, stdout=handle, stderr=subprocess.PIPE, cwd=str(self.tmp))
        self.assertEqual(ok.returncode, gate_receipt.EXIT_OK, ok.stderr)
        self.assertTrue(gate_receipt.verify_receipt(json.loads(sink.read_text(encoding="utf-8"))))


class AbandonBrokenStreamTests(unittest.TestCase):
    """The one shared primitive both entrypoints lean on to keep 120 out of their exit space."""

    def test_only_the_stream_that_failed_is_dropped(self) -> None:
        """`main` is importable, so the caller may have swapped the stream since the sink settled.

        Dropping unconditionally would take away a stream that never failed and that this module
        was not even writing to — the distinguishing case an unconditional `setattr` would break.
        """
        settled = io.StringIO()
        replacement = io.StringIO()
        with mock.patch.object(sys, "stderr", replacement):
            gate_receipt.abandon_broken_stream("stderr", settled)
            self.assertIs(sys.stderr, replacement)  # not ours to drop
            gate_receipt.abandon_broken_stream("stderr", replacement)
            self.assertIsNone(sys.stderr)  # this one failed, so it goes

    def test_a_settled_sink_stops_writing_after_its_first_failure(self) -> None:
        class _DiesOnSecondFlush:
            def __init__(self) -> None:
                self.written: list[str] = []

            def write(self, text: str) -> int:
                self.written.append(text)
                return len(text)

            def flush(self) -> None:
                if len(self.written) >= 2:
                    raise OSError(errno.EPIPE, "broken pipe")

        stream = _DiesOnSecondFlush()
        with mock.patch.object(sys, "stderr", stream):
            note = gate_receipt.advisory_stderr()
            note("first\n")
            note("second\n")  # this one fails...
            note("third\n")  # ...so this one is never attempted
            self.assertIsNone(sys.stderr)
        self.assertEqual(stream.written, ["first\n", "second\n"])

    def test_a_stderr_with_no_flush_still_gets_its_lines_and_keeps_its_receipt(self) -> None:
        """Guarding the channel must not make `flush` a new requirement on the caller's stream.

        A `write`-only object is a shape an importable `main` can be handed, and it worked before
        these lines were guarded. Requiring `flush` would have traded one display-channel defect for
        another: the sink would raise while being SETTLED, and the receipt would be lost again.
        """

        class _WriteOnly:
            def __init__(self) -> None:
                self.lines: list[str] = []

            def write(self, text: str) -> int:
                self.lines.append(text)
                return len(text)

        stream = _WriteOnly()
        with mock.patch.object(sys, "stderr", stream):
            note = gate_receipt.advisory_stderr()
            note("advisory line\n")
            gate_receipt._stderr_mirror(quiet=False)(b"mirrored bytes\n")
            self.assertIs(sys.stderr, stream)  # nothing failed, so nothing was dropped
        self.assertEqual(stream.lines, ["advisory line\n", "mirrored bytes\n"])

    def test_a_closed_fd_2_settles_to_a_sink_that_writes_nowhere(self) -> None:
        with mock.patch.object(sys, "stderr", None):
            note = gate_receipt.advisory_stderr()
            note("this cannot be written anywhere, and must not raise\n")
            mirror = gate_receipt._stderr_mirror(quiet=False)
            mirror(b"nor can this\n")
            self.assertIsNone(sys.stderr)


class AbandonedGateChildTests(_ProducerTestCase):
    """A gate child abandoned by an exception is reaped in BOUNDED time, changing no verdict.

    Before `_reap_abandoned_gate` existed, an exception between `Popen` and `wait` left the child
    behind: in-process that surfaced as `ResourceWarning: subprocess N is still running` from
    `__del__` — which no assertion can fail on — and for a child that had NOT yet exited it left a
    genuinely running process behind the returned exit code. Both are asserted here directly:
    the child's own reaped status, and the absence of the warning.
    """

    GRACE = 0.25  # the production ceiling is 15s of unwinding; these tests only need the shape

    # The flood is fixture MECHANICS, and each test below asserts exactly ONE way for its child to
    # end, so the flood must not be a second way. A pipe holds 64 KiB, `_run_gate` reads one 65536-
    # byte block and then abandons the child, closing the read end — which leaves the child's
    # residue unwritable. Through `sys.stdout` that residue sits in a buffer CPython flushes AGAIN
    # at shutdown, so the child raced its own `BrokenPipeError` against the reap and under CPU load
    # won: it exited 120, CPython's cannot-flush-std-streams code, before any signal arrived and
    # instead of its own clean exit. Writing straight to fd 1 and dropping the `EPIPE` leaves
    # `sys.stdout`'s buffer empty and nothing for shutdown to fail on, so the flood cannot end the
    # child at all. Dropping it is sound because the producer has its block by then, which is the
    # only thing the flood is for.
    _FLOOD = (
        "data = b'x' * 70000",
        "try:",
        "    while data:",
        "        data = data[os.write(1, data):]",
        "except OSError:",  # EPIPE: the read this fixture exists to feed has already happened
        "    pass",
    )

    def _write_blocking_gate(
        self, *, release: Path, name: str, ignore_sigterm: bool = False
    ) -> list[str]:
        """A gate that floods a first read and then WAITS, so it is alive when the mirror runs.

        `_run_gate` reads in 65536-byte blocks and a `read` returns only at that boundary or EOF, so
        a short gate is always finished before the mirror is reached — a gate that is still running
        has to write more than one block and then stay up. `release` is how a test lets it finish
        normally (its positive control); the deadline is a self-limit so no fixture can outlive the
        suite even if a test fails before its cleanup. Once the flood is out this child can only be
        ended by a signal or by `release`; see `_FLOOD`.
        """
        body = ["import os, sys, time"]
        if ignore_sigterm:
            body += ["import signal", "signal.signal(signal.SIGTERM, signal.SIG_IGN)"]
        body += [
            *self._FLOOD,
            "deadline = time.monotonic() + 30.0",
            f"while not os.path.exists({str(release)!r}) and time.monotonic() < deadline:",
            "    time.sleep(0.02)",
            "sys.exit(0)",
        ]
        script = self.tmp / name
        script.write_text("\n".join(body) + "\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def _write_self_finishing_gate(self, *, name: str, seconds: float) -> list[str]:
        """Alive when the mirror runs, then finished on its own a moment later — and ONLY so.

        The sleep is the whole point of this fixture, so the flood may not pre-empt it; see `_FLOOD`.
        """
        script = self.tmp / name
        script.write_text(
            "\n".join(
                [
                    "import os, sys, time",
                    *self._FLOOD,
                    f"time.sleep({seconds})",
                    "sys.exit(0)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return [sys.executable, str(script)]

    def _args(self, out: Path, argv: list[str]) -> list[str]:
        return [
            "record",
            "--gate",
            "blocking fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--",  # NOT --quiet: the mirror is the raise site these tests use
            *argv,
        ]

    @staticmethod
    def _raising_mirror(*, quiet: bool) -> object:
        """A raise inside the run window that the mirror's own guard cannot swallow.

        `MemoryError` from `chunks.append` is the realistic shape; `RuntimeError` is the same
        control flow without an unreproducible precondition. `_guarded_stderr_sink` catches only
        `OSError`/`ValueError`, so this escapes exactly as an unexpected failure would.
        """
        del quiet

        def mirror(chunk: bytes) -> None:
            raise RuntimeError("boom inside the run window, with the gate still running")

        return mirror

    @contextlib.contextmanager
    def _watch_children(self, argv: list[str]):
        """Record the GATE's children, named by their exact argv.

        `argv` is required rather than defaulted, because "every child this producer spawns" is not
        the same set as "the gate" and these tests are about the gate: the producer also reads the
        repository head for the receipt's `head` stamp (agentic-sdlc-5ee7), which spawns short-lived
        `git rev-parse` children that no reap rule here governs. Selecting by exact argv keeps each
        assertion below counting the one child it is about; matching loosely would let a future
        helper child silently satisfy `len(created) == 1` in place of the gate.
        """
        created: list[subprocess.Popen[bytes]] = []
        real_popen = subprocess.Popen

        def spy(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            if isinstance(proc.args, list) and list(proc.args) == argv:
                created.append(proc)
            return proc

        try:
            with mock.patch.object(gate_receipt.subprocess, "Popen", spy):
                yield created
        finally:
            for proc in created:  # no test may leave a gate behind, pass or fail
                if proc.returncode is None:
                    with contextlib.suppress(OSError):
                        proc.kill()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=10)

    @unittest.skipUnless(POSIX, "SIGKILL and negative returncodes are POSIX signal semantics")
    def test_the_recorded_resourcewarning_symptom_is_gone(self) -> None:
        """The symptom this finding was RECORDED as, asserted with its own positive control.

        `ResourceWarning: subprocess N is still running` comes from `Popen.__del__`, so it can only
        be observed by a test that holds NO reference to the child — which is also why nothing in
        this file could ever fail on it. Only pids are kept here, and the reap is disabled for the
        control run: that control is the whole point, because an assertion that no warning was
        raised passes just as well when the warning channel is dead.
        """
        release = self.tmp / "release-warning"
        argv = self._write_blocking_gate(release=release, name="warning_gate.py")
        args = self._args(self.tmp / "warned.json", argv)
        real_popen = subprocess.Popen

        def observe(reaping: bool) -> tuple[list[int], list[str]]:
            pids: list[int] = []

            def spy(*call_args: object, **kwargs: object) -> subprocess.Popen[bytes]:
                proc = real_popen(*call_args, **kwargs)  # type: ignore[arg-type]
                if list(proc.args) == argv:  # the GATE's child, not the `head` stamp's `git` reads
                    pids.append(proc.pid)  # the PID only: a strong reference suppresses `__del__`
                return proc

            reap = (
                gate_receipt._reap_abandoned_gate
                if reaping
                else (lambda *a, **k: None)  # the pre-fix behaviour, injected
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                with (
                    mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", self.GRACE),
                    mock.patch.object(gate_receipt, "_stderr_mirror", self._raising_mirror),
                    mock.patch.object(gate_receipt, "_reap_abandoned_gate", reap),
                    mock.patch.object(gate_receipt.subprocess, "Popen", spy),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    gate_receipt.main(args)
                gc.collect()  # `__del__` is what warns, so the frames holding the child must go
                messages = [f"{w.category.__name__}: {w.message}" for w in caught]
            for pid in pids:  # no test may leave a gate behind, pass or fail
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGKILL)
                with contextlib.suppress(OSError):
                    os.waitpid(pid, 0)
            return pids, messages

        reaped_pids, reaped_messages = observe(reaping=True)
        leaked_pids, leaked_messages = observe(reaping=False)
        self.assertEqual(len(reaped_pids), 1)
        self.assertEqual(len(leaked_pids), 1)
        # POSITIVE CONTROL: with the reap disabled the warning IS observed here, naming the leaked
        # child — so the empty list below is a reaped child and not a deaf warning channel.
        self.assertIn(
            f"ResourceWarning: subprocess {leaked_pids[0]} is still running", leaked_messages
        )
        self.assertEqual(reaped_messages, [])

    @unittest.skipUnless(POSIX, "SIGKILL and negative returncodes are POSIX signal semantics")
    def test_a_gate_still_running_when_the_producer_fails_is_ended_with_sigterm(self) -> None:
        release = self.tmp / "release-sigterm"
        argv = self._write_blocking_gate(release=release, name="blocking_gate.py")
        out = self.tmp / "receipt.json"
        args = self._args(out, argv)
        with (
            mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", self.GRACE),
            mock.patch.object(gate_receipt, "_stderr_mirror", self._raising_mirror),
            self._watch_children(argv) as created,
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            code = gate_receipt.main(args)
        text = err.getvalue()
        self.assertEqual(len(created), 1, text)
        child = created[0]
        # The child was ALIVE when the producer failed — otherwise the poll stage would have reaped
        # it with its own status — and it was reaped here, with the signal this producer sent.
        self.assertEqual(child.returncode, -signal.SIGTERM)
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertNotEqual(code, gate_receipt.EXIT_INTERNAL)
        self.assertNotEqual(code, gate_receipt.EXIT_REFUSED)
        self.assertFalse(out.exists())  # a killed gate has no verdict, so it gets no receipt
        self.assertIn("already happened: the gate ran", text)
        self.assertIn("it was ended with SIGTERM and its verdict was never observed", text)
        # POSITIVE CONTROL: the identical fixture, released and un-injected, runs to a verifiable
        # receipt — so the assertions above come from the injected raise, not from a broken gate,
        # and every channel they read (exit code, receipt, report text) does carry values.
        release.write_text("go\n", encoding="utf-8")
        with (
            self._watch_children(argv) as ok_created,
            contextlib.redirect_stderr(io.StringIO()) as ok_err,
        ):
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_OK, ok_err.getvalue())
        self.assertEqual(ok_created[0].returncode, 0)
        self.assertNotIn("SIGTERM", ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_a_gate_that_finishes_inside_the_grace_window_is_never_signalled(self) -> None:
        """The first stage's SUCCESS path: alive at abandonment, gone before the grace expired.

        Closing the pipe is usually enough to end a gate, so this is the ordinary case, and it must
        not be described as a kill: the child died of its own accord and its status was collected.
        An unconditional re-description would report a child "still running" that had just exited.
        """
        argv = self._write_self_finishing_gate(name="brief_gate.py", seconds=0.3)
        out = self.tmp / "receipt.json"
        args = self._args(out, argv)
        with (
            mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", 10.0),
            mock.patch.object(gate_receipt, "_stderr_mirror", self._raising_mirror),
            self._watch_children(argv) as created,
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            started = time.monotonic()
            code = gate_receipt.main(args)
            elapsed = time.monotonic() - started
        text = err.getvalue()
        # It was ALIVE when the producer failed (so the poll stage could not have reaped it) and it
        # exited on its own (so the status is its own, not a signal), well inside the grace window.
        self.assertEqual(created[0].returncode, 0)
        self.assertLess(elapsed, 10.0)
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertIn("already happened: the gate ran", text)
        self.assertNotIn("it was still running", text)  # nothing was killed, so nothing is claimed
        self.assertNotIn("SIGTERM", text)
        self.assertNotIn("SIGKILL", text)
        self.assertFalse(out.exists())
        # POSITIVE CONTROL: un-injected, the same gate records a verifiable receipt — so the report
        # text asserted against above is a live channel that simply has nothing extra to say.
        with contextlib.redirect_stderr(io.StringIO()) as ok_err:
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_OK, ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    @unittest.skipUnless(POSIX, "SIGKILL and negative returncodes are POSIX signal semantics")
    def test_a_gate_that_ignores_sigterm_is_killed_and_never_hangs_the_producer(self) -> None:
        """The reason the wait is bounded: an unbounded `finally` reap is a hang, not a leak.

        A gate that ignores `SIGTERM` and stays up is exactly the shape that would park the failure
        report for as long as the gate lives, and a hung producer is indistinguishable from a slow
        gate. So the producer is run on a thread and JOINED with a timeout: an unbounded wait leaves
        the thread alive and fails here, where the mutation is visible, instead of stalling the run.
        """
        release = self.tmp / "release-sigkill"
        argv = self._write_blocking_gate(
            release=release, name="deaf_gate.py", ignore_sigterm=True
        )
        out = self.tmp / "receipt.json"
        args = self._args(out, argv)
        captured: dict[str, object] = {}

        def run() -> None:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                captured["code"] = gate_receipt.main(args)
            captured["text"] = err.getvalue()

        with (
            mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", self.GRACE),
            mock.patch.object(gate_receipt, "_stderr_mirror", self._raising_mirror),
            self._watch_children(argv) as created,
        ):
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            worker.join(timeout=10.0)
            finished = not worker.is_alive()
            if not finished:  # unblock the mutant so the suite still terminates
                release.write_text("go\n", encoding="utf-8")
                worker.join(timeout=30.0)
        self.assertTrue(finished, "the producer did not return: the reap wait was not bounded")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].returncode, -signal.SIGKILL)  # SIGTERM was ignored, so escalate
        text = str(captured.get("text", ""))
        self.assertEqual(captured.get("code"), gate_receipt.EXIT_PARTIAL, text)
        self.assertIn("it was ended with SIGKILL and its verdict was never observed", text)
        self.assertFalse(out.exists())
        # POSITIVE CONTROL: the same deaf gate, released and un-injected, still records a receipt.
        release.write_text("go\n", encoding="utf-8")
        with (
            self._watch_children(argv) as ok_created,
            contextlib.redirect_stderr(io.StringIO()) as ok_err,
        ):
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_OK, ok_err.getvalue())
        self.assertEqual(ok_created[0].returncode, 0)
        self.assertNotIn("SIGKILL", ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_a_gate_that_already_exited_is_reaped_with_its_own_status_and_no_signal(self) -> None:
        """The common shape: `wait` itself raises, after the gate has already finished.

        Nothing here may be signalled — the child's own status is still there to be collected — and
        the admitted effect must stay exactly "the gate ran", because no new effect occurred.
        """
        marker = self.tmp / "exited.marker"
        argv = _write_fake_gate(self.tmp, exit_code=0, marker=marker)
        out = self.tmp / "receipt.json"
        args = [
            "record",
            "--gate",
            "short fake gate",
            "--out",
            str(out),
            "--lock",
            str(self.lock),
            "--quiet",  # quiet, so the raise below is unambiguously `wait`
            "--",
            *argv,
        ]
        real_wait = subprocess.Popen.wait
        raised: list[int] = []

        def raise_once_without_reaping(
            proc: subprocess.Popen[bytes], *rest: object, **kwargs: object
        ) -> int:
            # Scoped to the GATE's own wait by exact argv. The producer also spawns `git rev-parse`
            # children for the receipt's `head` stamp (agentic-sdlc-5ee7), and an unscoped injection
            # would fire on the first of those instead — before the gate had run at all, which is a
            # different failure from the one this test exists to describe.
            if not raised and list(proc.args) == argv:
                raised.append(proc.pid)
                raise RuntimeError("boom at wait, with the gate already exited")
            return real_wait(proc, *rest, **kwargs)  # type: ignore[arg-type]

        with (
            mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", 2.0),
            mock.patch.object(subprocess.Popen, "wait", raise_once_without_reaping),
            self._watch_children(argv) as created,
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            started = time.monotonic()
            code = gate_receipt.main(args)
            elapsed = time.monotonic() - started
        text = err.getvalue()
        self.assertEqual(raised and len(raised), 1, text)  # the injection was REACHED
        self.assertTrue(marker.exists())  # and the gate really ran
        self.assertEqual(created[0].returncode, 0)  # reaped, with the gate's OWN status
        self.assertEqual(code, gate_receipt.EXIT_PARTIAL, text)
        self.assertIn("already happened: the gate ran", text)
        self.assertNotIn("SIGTERM", text)  # nothing was signalled...
        self.assertNotIn("SIGKILL", text)
        self.assertNotIn("MAY STILL BE RUNNING", text)
        # ...and the effect was not re-described at all: an unconditional revision would report a
        # child that was still running, which this one provably was not.
        self.assertNotIn("it was still running", text)
        # ...which the clock corroborates: no bounded wait was needed for a child already gone.
        self.assertLess(elapsed, 2.0)
        # POSITIVE CONTROL: same args, real `wait`, verifiable receipt and a clean exit.
        with contextlib.redirect_stderr(io.StringIO()) as ok_err:
            ok_code = gate_receipt.main(args)
        self.assertEqual(ok_code, gate_receipt.EXIT_OK, ok_err.getvalue())
        self.assertTrue(gate_receipt.verify_receipt(json.loads(out.read_text(encoding="utf-8"))))

    def test_the_reap_grace_is_a_finite_positive_bound(self) -> None:
        """`None` here is the hang this design rejected: `wait(timeout=None)` blocks forever."""
        self.assertIsInstance(gate_receipt._REAP_GRACE_SECONDS, float)
        self.assertGreater(gate_receipt._REAP_GRACE_SECONDS, 0.0)
        self.assertLessEqual(gate_receipt._REAP_GRACE_SECONDS, 30.0)

    def test_reaping_never_replaces_the_failure_it_was_cleaning_up_after(self) -> None:
        """Cleanup that raises would rewrite the classification, so its own failures are swallowed."""
        effects = gate_receipt._Effects()
        token = effects.admit("the gate ran somewhere")
        exploding = mock.Mock()
        type(exploding).returncode = mock.PropertyMock(return_value=None)
        exploding.poll.side_effect = OSError(errno.ECHILD, "no child processes")
        gate_receipt._reap_abandoned_gate(
            exploding, ran="the gate ran somewhere", token=token, effects=effects
        )
        self.assertEqual(effects.admitted, ["the gate ran somewhere"])  # unchanged, and no raise
        # POSITIVE CONTROL: the same call on a process that survives SIGKILL DOES re-describe the
        # effect, so the observation channel asserted above is live rather than inert.
        stubborn = mock.Mock()
        type(stubborn).returncode = mock.PropertyMock(return_value=None)
        stubborn.poll.return_value = None
        stubborn.wait.side_effect = subprocess.TimeoutExpired("gate", 0.25)
        with mock.patch.object(gate_receipt, "_REAP_GRACE_SECONDS", 0.25):
            gate_receipt._reap_abandoned_gate(
                stubborn, ran="the gate ran somewhere", token=token, effects=effects
            )
        self.assertEqual(len(effects.admitted), 1)  # re-described, never a second admission
        self.assertIn("MAY STILL BE RUNNING", effects.admitted[0])


class RepositoryHeadStampTests(_ProducerTestCase):
    """agentic-sdlc-5ee7: every receipt names the repository head its `cwd` was sitting on.

    A receipt used to be anchored to a path and a toolchain but to no point in the repository's
    history, so nothing downstream could tell whether it and the artifacts beside it were derived
    against the same tree. These tests drive the real producer against real temporary repositories,
    so the stamp is checked against `git rev-parse`'s own answer rather than against a re-expression
    of it.
    """

    def _git(self, *arguments: str, cwd: Path | None = None) -> str:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }
        )
        done = subprocess.run(
            ["git", *arguments],
            cwd=str(cwd if cwd is not None else self.repository),
            capture_output=True,
            text=True,
            check=True,
            env=environment,
        )
        return done.stdout.strip()

    def setUp(self) -> None:
        super().setUp()
        if shutil.which("git") is None:  # pragma: no cover - environment-dependent
            self.skipTest("git is unavailable, so no head can be observed")
        self.repository = self.tmp / "repo"
        self.repository.mkdir()
        self._git("init", "-b", "main")
        self._git("commit", "--allow-empty", "-m", "first")

    def _record(self, out: Path, argv: list[str], *, cwd: Path, expect: int) -> dict[str, object]:
        done = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "record",
                "--gate",
                "fake gate",
                "--out",
                str(out),
                "--lock",
                str(self.lock),
                "--cwd",
                str(cwd),
                "--quiet",
                "--",
                *argv,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, expect, done.stderr)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_a_receipt_recorded_in_a_repository_stamps_that_repositorys_head(self) -> None:
        argv = _write_fake_gate(self.tmp, exit_code=0)
        receipt = self._record(self.tmp / "receipt.json", argv, cwd=self.repository, expect=0)
        commit = self._git("rev-parse", "HEAD")
        self.assertEqual(receipt["head"], {"commit": commit, "tree": self._git("rev-parse", f"{commit}^{{tree}}")})
        # The stamp is inside the seal like every other field, so it cannot be edited out afterwards.
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        tampered = dict(receipt)
        tampered["head"] = {"commit": "0" * 40, "tree": "1" * 40}
        self.assertFalse(gate_receipt.verify_receipt(tampered))

    def test_the_stamped_tree_belongs_to_the_stamped_commit(self) -> None:
        # The single-derivation rule, asserted against Git's own answer for the commit the receipt
        # names -- not for whatever HEAD happens to be at assertion time.
        # Real content, not a second empty commit: two empty commits share the one empty tree, so an
        # empty second commit would make the control below compare a value against itself.
        (self.repository / "content.txt").write_text("second\n", encoding="utf-8")
        self._git("add", "content.txt")
        self._git("commit", "-m", "second")
        argv = _write_fake_gate(self.tmp, exit_code=0)
        receipt = self._record(self.tmp / "second.json", argv, cwd=self.repository, expect=0)
        head = receipt["head"]
        assert isinstance(head, dict)
        self.assertEqual(head["tree"], self._git("rev-parse", f"{head['commit']}^{{tree}}"))
        # POSITIVE CONTROL: the repository really does have two commits with distinct trees to get
        # wrong, so the equality above is not vacuous.
        first = self._git("rev-parse", "HEAD~1")
        self.assertNotEqual(self._git("rev-parse", f"{first}^{{tree}}"), head["tree"])

    def test_a_non_repository_cwd_records_a_null_head_and_still_writes_the_receipt(self) -> None:
        # Null is a first-class answer, not a refusal: a gate that ran outside a repository is still
        # honest evidence about that gate.
        outside = self.tmp / "outside"
        outside.mkdir()
        argv = _write_fake_gate(self.tmp, exit_code=0)
        receipt = self._record(self.tmp / "outside.json", argv, cwd=outside, expect=0)
        self.assertIsNone(receipt["head"])
        self.assertEqual(receipt["outcome"], "passed")
        self.assertTrue(gate_receipt.verify_receipt(receipt))
        # POSITIVE CONTROL: the identical invocation inside the repository DOES stamp a head, so the
        # null above is the missing repository and not a producer that never stamps anything.
        inside = self._record(self.tmp / "inside.json", argv, cwd=self.repository, expect=0)
        self.assertIsNotNone(inside["head"])

    def test_a_head_that_moves_while_the_gate_runs_records_a_null_stamp(self) -> None:
        """A gate that commits underneath itself leaves no single head it was measured against.

        Recording the pre-gate head would claim the receipt describes a tree the gate did not finish
        on; recording the post-gate head would claim it describes one the gate did not start on. Both
        are lies a consumer cannot detect, so the producer records neither.
        """
        script = self.tmp / "committing_gate.py"
        script.write_text(
            "\n".join(
                [
                    "import subprocess, sys",
                    f"subprocess.run(['git', 'commit', '--allow-empty', '-m', 'moved'], cwd={str(self.repository)!r},",
                    "               check=True, capture_output=True,",
                    "               env={'PATH': __import__('os').environ['PATH'],",
                    "                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': __import__('os').devnull,",
                    "                    'GIT_AUTHOR_NAME': 'test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',",
                    "                    'GIT_COMMITTER_NAME': 'test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid'})",
                    "sys.exit(0)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        before = self._git("rev-parse", "HEAD")
        receipt = self._record(self.tmp / "moved.json", [sys.executable, str(script)], cwd=self.repository, expect=0)
        after = self._git("rev-parse", "HEAD")
        self.assertNotEqual(before, after, "the fixture gate did not actually move the head")
        self.assertIsNone(receipt["head"])
        # ...and the receipt is still written for the gate that really did pass.
        self.assertEqual(receipt["outcome"], "passed")
        # POSITIVE CONTROL: the same gate script re-run now that the head is where it will stay
        # stamps a head, so the null above is the movement and not this fixture being unstampable.
        settled = self._record(
            self.tmp / "settled.json", _write_fake_gate(self.tmp, exit_code=0), cwd=self.repository, expect=0
        )
        self.assertEqual(settled["head"], {"commit": after, "tree": self._git("rev-parse", f"{after}^{{tree}}")})

    def test_an_ambient_git_dir_cannot_re_point_the_observation(self) -> None:
        # `GIT_DIR` in the caller's environment would otherwise make `rev-parse` answer for ANOTHER
        # repository while the receipt went on naming this `cwd` -- a stamp that lies with nobody
        # editing it. The observation's environment is an allowlist, so the variable never arrives.
        other = self.tmp / "other"
        other.mkdir()
        self._git("init", "-b", "main", cwd=other)
        self._git("commit", "--allow-empty", "-m", "other repository", cwd=other)
        foreign = self._git("rev-parse", "HEAD", cwd=other)
        mine = self._git("rev-parse", "HEAD")
        self.assertNotEqual(foreign, mine)
        argv = _write_fake_gate(self.tmp, exit_code=0)
        out = self.tmp / "ambient.json"
        done = subprocess.run(
            [
                sys.executable, str(SCRIPT), "record", "--gate", "fake gate", "--out", str(out),
                "--lock", str(self.lock), "--cwd", str(self.repository), "--quiet", "--", *argv,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=dict(os.environ, GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other)),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = json.loads(out.read_text(encoding="utf-8"))
        head = receipt["head"]
        assert isinstance(head, dict)
        self.assertEqual(head["commit"], mine)
        self.assertNotEqual(head["commit"], foreign)

    def test_verify_receipt_rejects_a_malformed_head_stamp(self) -> None:
        # A consumer that refuses on DISAGREEMENT has to be able to rely on the shape it compares, or
        # a malformed stamp is reported as a head that moved.
        honest = gate_receipt.build_receipt(
            gate="mise run check",
            argv=["mise", "run", "check"],
            status=0,
            log_bytes=b"",
            lock_bytes=LOCK_BYTES,
            cwd=str(self.repository),
            head={"commit": "a" * 40, "tree": "b" * 40},
        )
        # POSITIVE CONTROL: the well-formed stamp verifies, so each rejection below is the shape.
        self.assertTrue(gate_receipt.verify_receipt(honest))
        self.assertTrue(gate_receipt.verify_receipt(_reseal({**honest, "head": None})))
        self.assertTrue(gate_receipt.verify_receipt(_reseal({**honest, "head": {"commit": "a" * 64, "tree": "b" * 64}})))
        for label, value in (
            ("missing tree", {"commit": "a" * 40}),
            ("extra key", {"commit": "a" * 40, "tree": "b" * 40, "branch": "main"}),
            ("not an object", "a" * 40),
            ("uppercase", {"commit": "A" * 40, "tree": "b" * 40}),
            ("abbreviated", {"commit": "a" * 12, "tree": "b" * 40}),
            ("non-hex", {"commit": "z" * 40, "tree": "b" * 40}),
            ("boolean", {"commit": True, "tree": "b" * 40}),
        ):
            with self.subTest(shape=label):
                self.assertFalse(gate_receipt.verify_receipt(_reseal({**honest, "head": value})))

    def test_a_receipt_written_before_the_stamp_existed_still_verifies(self) -> None:
        # The same additive rule `failures` follows: absence is a receipt from an older producer, not
        # a broken one. Refusing it HERE would make every consumer's named freshness refusal
        # unreachable, because the artifact would never get past verification to be refused by name.
        legacy = _reseal(
            {
                "gate": "mise run check",
                "argv": ["mise", "run", "check"],
                "status": 0,
                "signal": None,
                "outcome": "passed",
                "log_digest": _sha256_hex(b""),
                "toolchain_digest": _sha256_hex(LOCK_BYTES),
                "cwd": str(self.repository),
            }
        )
        self.assertNotIn("head", legacy)
        self.assertTrue(gate_receipt.verify_receipt(legacy))


if __name__ == "__main__":
    unittest.main()
