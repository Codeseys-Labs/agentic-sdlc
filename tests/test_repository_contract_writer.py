from __future__ import annotations

import builtins
import errno
import hashlib
import importlib.util
import io
import json
import os
import resource
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import activation_planner as ap

WRITER = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-contract-writer.py"
READER = ROOT / "skills" / "agentic-sdlc" / "tools" / "repository-contract.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rc = _load("_agentic_sdlc_repository_contract", READER)
rw = _load("_agentic_sdlc_repository_contract_writer", WRITER)

INTENT = {
    "canonical_guidance": "AGENTS.md",
    "queue_adapter": "seeds",
    "adr_location": "docs/adr",
    "glossary_location": "CONTEXT.md",
    "authoritative_gate": "mise run check",
    "worktree_policy": "one writer per worktree",
    "integration_policy": "authorized serial fan-in",
    "ci_expectation": "calls the same pinned authoritative gate",
    "writing_profile": "evidence-preserving",
}


def fields(**overrides: str) -> dict[str, str]:
    value = {"schema": rc.MANIFEST_SCHEMA, **INTENT}
    value.update(overrides)
    return value


# Spelled out here rather than imported from the module under test. Importing `rw.HEADER` and
# `rw.ORDERED_FIELDS` would make every byte assertion below agree with any mutation of them,
# which is precisely how a claim injected into the header survived the whole suite once.
EXPECTED_HEADER = (
    b"# RepositoryContractManifest -- portable repository intent (ADR-0022 decision 2).\n"
    b"# Tracked on purpose. Every value is an explicit operator statement, never a detected fact.\n"
    b"# Not proof of ownership, tool identity, trust, route, or readiness: those live in the\n"
    b"# machine-local receipt plane, and readiness is a separate assessment.\n"
)
EXPECTED_ORDER = (
    "schema",
    "canonical_guidance",
    "queue_adapter",
    "adr_location",
    "glossary_location",
    "authoritative_gate",
    "worktree_policy",
    "integration_policy",
    "ci_expectation",
    "writing_profile",
)


def expected_manifest_bytes(**overrides: str) -> bytes:
    """The exact bytes a correct writer emits for `fields(**overrides)`."""
    value = fields(**overrides)
    body = "".join(f'{name} = "{value[name]}"\n' for name in EXPECTED_ORDER)
    return EXPECTED_HEADER + b"\n" + body.encode("utf-8")


# Content for a file OUTSIDE the repository, used by the symlink-containment tests. Asserting
# these exact bytes back is the positive control that the refusal had no effect out there.
OUTSIDE_CONTENT = b"PRECIOUS CONTENT OUTSIDE THE REPOSITORY\n"

ACL_UNDEFINED_ID = 0xFFFFFFFF
_ACL_USER_OBJ, _ACL_USER, _ACL_GROUP_OBJ, _ACL_MASK, _ACL_OTHER = 0x01, 0x02, 0x04, 0x10, 0x20


def acl_bytes(owner: int, named: int) -> bytes:
    """A minimal valid POSIX.1e ACL granting one NAMED user, in `system.posix_acl_*` form.

    Hand-built rather than shelled out to `setfacl`, so the test observes the kernel rather
    than the developer's PATH. The named entry is what makes the ACL *extended*, which is the
    state the writer refuses; entries must be in tag order for the kernel to accept them.
    """
    entries = (
        (_ACL_USER_OBJ, owner, ACL_UNDEFINED_ID),
        (_ACL_USER, named, 0),
        (_ACL_GROUP_OBJ, named, ACL_UNDEFINED_ID),
        (_ACL_MASK, owner, ACL_UNDEFINED_ID),
        (_ACL_OTHER, named, ACL_UNDEFINED_ID),
    )
    return struct.pack("<I", 2) + b"".join(struct.pack("<HHI", tag, perm, ident) for tag, perm, ident in entries)


def try_set_acl(path: Path, attribute: str, owner: int, named: int) -> bool:
    """Set an extended ACL, reporting False when this filesystem cannot carry one."""
    try:
        os.setxattr(path, attribute, acl_bytes(owner, named))
    except OSError as exc:
        if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM, errno.EINVAL):
            return False
        raise
    return True


def bind_mount_is_available() -> bool:
    """Whether an unprivileged mount namespace can be entered, for the real bind-mount test.

    A skip guard, never an assertion: the mocked mount-identity tests carry the mutation
    coverage on every host, and this one adds the proof that a REAL bind mount is what the
    mount id sees.
    """
    if shutil.which("unshare") is None:
        return False
    return subprocess.run(["unshare", "-Urm", "true"], capture_output=True).returncode == 0


def argv_for(target: Path, *extra: str, **overrides: str) -> list[str]:
    args = ["write", "--target", str(target), *extra]
    for name, content in fields(**overrides).items():
        args += [f"--{name.replace('_', '-')}", content]
    return args


class WriterBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        self.state = self.target / ".agentic-sdlc"
        self.path = self.state / "repo.toml"

    def write(self, *, force: bool = False, **overrides: str) -> tuple[dict, int]:
        return rw.write_command(self.target, fields(**overrides), force=force)

    def assertRefused(self, result: dict, code: int, expected_code: int, fragment: str) -> None:
        """Assert WHICH check fired. Every refusal is otherwise an identical
        (refused, code) pair and no test can tell one from another."""
        self.assertEqual(result["status"], "refused", result)
        self.assertEqual(code, expected_code, result)
        self.assertTrue(
            any(fragment in reason for reason in result["reasons"]),
            f"expected a reason containing {fragment!r}, got {result['reasons']}",
        )
        self.assertEqual(result["effect"], "none", result)


class ReaderAgreementTests(WriterBase):
    def test_written_manifest_is_valid_to_the_reader(self) -> None:
        result, code = self.write()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["effect"], "manifest-written")

        read, read_code = rc.inspect_command(self.target)
        self.assertEqual(read_code, 0, read)
        self.assertEqual(read["status"], "valid", read)
        self.assertEqual(read["contract"], fields())

    def test_field_set_matches_the_readers_closed_schema(self) -> None:
        """The reader's REQUIRED_FIELDS is the single definition of the key set. A
        writer with its own copy would silently omit a field added there."""
        self.assertEqual(set(rw.ORDERED_FIELDS), set(rc.REQUIRED_FIELDS))
        self.write()
        emitted = rw.tomllib.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(set(emitted), set(rc.REQUIRED_FIELDS))

    def test_values_needing_escaping_round_trip_through_the_reader(self) -> None:
        awkward = 'gate "quoted" \\ and\ttab'
        result, code = self.write(authoritative_gate=awkward)

        self.assertEqual(code, 0, result)
        read, read_code = rc.inspect_command(self.target)
        self.assertEqual(read_code, 0, read)
        self.assertEqual(read["contract"]["authoritative_gate"], awkward)


class EngineAdmissionTests(WriterBase):
    def admit(self) -> None:
        ap._validate_private_state(self.target, ap.bind_target(self.target))

    def test_written_manifest_is_admitted_by_the_activation_engine(self) -> None:
        result, code = self.write()
        self.assertEqual(code, 0, result)

        self.admit()

    def test_engine_admission_observation_channel_actually_refuses(self) -> None:
        """POSITIVE CONTROL for every `self.admit()` above: an admission call that
        cannot fail proves nothing. Make the engine refuse the same file."""
        self.write()
        os.chmod(self.path, 0o646)

        with self.assertRaises(ap.ActivationError) as caught:
            self.admit()
        self.assertEqual(caught.exception.status, "foreign-state")

    def test_clone_shaped_modes_are_admitted_at_umask_022_and_002(self) -> None:
        """The engine had a real defect that appeared only at umask 002, and Git
        records no mode, so both shapes must be produced and admitted."""
        for mask, file_mode, dir_mode in ((0o022, 0o644, 0o755), (0o002, 0o664, 0o775)):
            with self.subTest(umask=oct(mask)):
                fresh = Path(self.tmp.name) / f"repo-{mask:04o}"
                fresh.mkdir()
                previous = os.umask(mask)
                try:
                    result, code = rw.write_command(fresh, fields(), force=False)
                finally:
                    os.umask(previous)
                self.assertEqual(code, 0, result)
                manifest = fresh / ".agentic-sdlc" / "repo.toml"
                self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), file_mode)
                self.assertEqual(stat.S_IMODE(manifest.parent.stat().st_mode), dir_mode)
                ap._validate_private_state(fresh, ap.bind_target(fresh))

    def test_mode_is_an_ordinary_files_mode_never_a_private_one(self) -> None:
        """ADR-0022 admits this path under a cloneable-mode predicate because the file is
        meant to be committed, so the writer must impose no mode of its own. Compared
        against a reference ordinary file created under the SAME umask rather than against
        a literal, because at umask 077 an ordinary tracked file is 0600 too and pinning
        0644 there would make this writer LESS restrictive than a checkout."""
        for mask in (0o022, 0o002, 0o077):
            with self.subTest(umask=oct(mask)):
                fresh = Path(self.tmp.name) / f"ordinary-{mask:04o}"
                fresh.mkdir()
                previous = os.umask(mask)
                try:
                    result, code = rw.write_command(fresh, fields(), force=False)
                    reference = fresh / "ordinary.txt"
                    reference.write_text("reference\n")
                finally:
                    os.umask(previous)
                self.assertEqual(code, 0, result)
                manifest = fresh / ".agentic-sdlc" / "repo.toml"
                self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), stat.S_IMODE(reference.stat().st_mode))

    def test_world_writable_umask_cannot_produce_an_unadmittable_manifest(self) -> None:
        previous = os.umask(0o000)
        try:
            result, code = self.write()
        finally:
            os.umask(previous)
        self.assertEqual(code, 0, result)
        self.assertFalse(stat.S_IMODE(self.path.stat().st_mode) & 0o002)
        self.assertFalse(stat.S_IMODE(self.state.stat().st_mode) & 0o002)
        self.admit()


class OverwriteRefusalTests(WriterBase):
    def test_existing_manifest_is_not_overwritten_without_force(self) -> None:
        self.write()
        before = self.path.read_bytes()

        result, code = self.write(queue_adapter="replaced")

        self.assertRefused(result, code, 3, "already exists")
        self.assertEqual(self.path.read_bytes(), before)

    def test_force_replaces_an_existing_manifest(self) -> None:
        self.write()
        before = self.path.read_bytes()

        result, code = self.write(queue_adapter="replaced", force=True)

        self.assertEqual(code, 0, result)
        self.assertNotEqual(self.path.read_bytes(), before)
        read, _ = rc.inspect_command(self.target)
        self.assertEqual(read["contract"]["queue_adapter"], "replaced")

    def test_hardlinked_manifest_is_refused_even_with_force(self) -> None:
        """st_nlink != 1 is refused by both the reader and the engine, so replacing
        the content through a second name must not be possible either."""
        self.write()
        os.link(self.path, Path(self.tmp.name) / "outside.toml")
        before = self.path.read_bytes()

        result, code = self.write(queue_adapter="replaced", force=True)

        self.assertRefused(result, code, 3, "unsafe")
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_shorter_replacement_leaves_no_bytes_of_the_previous_manifest(self) -> None:
        """`--force` replaces content IN PLACE through the already-verified descriptor -- no
        temporary sibling, no rename -- which the module docstring records as a deliberate
        decision. The one guard that makes it safe is the `ftruncate`, and it had no coverage
        because the only `--force` test in this suite replaced "seeds" with the LONGER
        "replaced", so truncation was never needed. With the truncate removed this fixture exits
        0 `written` over a 920-byte file holding a 721-byte payload: a `manifest_sha256` that
        does not match the bytes on disk, and a manifest the reader refuses as malformed."""
        self.write(queue_adapter="q" * 200)
        long_size = self.path.stat().st_size

        result, code = self.write(queue_adapter="x", force=True)

        self.assertEqual(code, 0, result)
        expected = expected_manifest_bytes(queue_adapter="x")
        self.assertLess(len(expected), long_size, "the fixture must actually shrink the manifest")
        # The BYTES, not the parse: a tail left behind by a missing truncate is a fragment of the
        # previous manifest appended after the new one, and the size is what exposes it.
        self.assertEqual(self.path.read_bytes(), expected)
        self.assertEqual(self.path.stat().st_size, len(expected))
        # The reported digest must be the digest of what is actually on disk, which is the
        # channel a downstream consumer would key on.
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        read, read_code = rc.inspect_command(self.target)
        self.assertEqual((read_code, read["status"]), (0, "valid"), read)

    def test_other_writable_existing_manifest_is_refused_even_with_force(self) -> None:
        """The engine refuses an other-writable manifest as `foreign-state`, so replacing one
        would produce a file the engine will not admit -- and the writer never re-modes an
        existing node, because silently relaxing the mode of tracked repository policy is its own
        version of a silent overwrite. There was a directory analogue of this test but no
        manifest one, so the check had no coverage."""
        self.write()
        before = self.path.read_bytes()
        os.chmod(self.path, 0o646)  # open(mode=) is masked by the umask; chmod is not

        result, code = self.write(queue_adapter="replaced", force=True)

        self.assertRefused(result, code, 3, "repo.toml")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o646, "the mode was quietly relaxed")

    def test_foreign_owned_existing_manifest_is_refused_even_with_force(self) -> None:
        """A manifest owned by another user is refused rather than rewritten, and that check had
        no coverage either. `os.geteuid` is patched because a test cannot chown; the state root
        is checked first and consults it exactly once, so the SECOND value is the manifest's own
        check and the ordering is what makes this test attributable."""
        self.write()
        before = self.path.read_bytes()
        real = os.geteuid()

        with mock.patch.object(os, "geteuid", mock.Mock(side_effect=[real, real + 1])):
            result, code = self.write(queue_adapter="replaced", force=True)

        self.assertRefused(result, code, 3, "repo.toml")
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_manifest_ownership_control_our_own_uid_is_replaced(self) -> None:
        """POSITIVE CONTROL: the identical patched sequence reporting our real uid both times
        replaces the manifest, so the refusal above is the ownership check and not the patch."""
        self.write()
        real = os.geteuid()

        with mock.patch.object(os, "geteuid", mock.Mock(side_effect=[real, real])):
            result, code = self.write(queue_adapter="replaced", force=True)

        self.assertEqual(code, 0, result)
        self.assertEqual(self.path.read_bytes(), expected_manifest_bytes(queue_adapter="replaced"))


class ProhibitedClaimTests(WriterBase):
    def test_writer_refuses_a_prohibited_claim_field(self) -> None:
        result, code = rw.write_command(self.target, fields(readiness="ready"), force=False)

        self.assertRefused(result, code, 2, "must not claim readiness")
        self.assertFalse(self.path.exists())

    def test_prohibited_claim_control_the_same_call_succeeds_without_it(self) -> None:
        """POSITIVE CONTROL for the refusal above and for the absence assertions
        below: the only difference is the prohibited field."""
        result, code = rw.write_command(self.target, fields(), force=False)

        self.assertEqual(code, 0, result)
        self.assertTrue(self.path.exists())

    def test_emitted_field_names_carry_no_prohibited_claim_token(self) -> None:
        """Named for the channel it actually observes: parsed KEYS. Comments are invisible to
        TOML, so this says nothing about the header -- `EmittedByteTests` covers that."""
        self.write()
        emitted = rw.tomllib.loads(self.path.read_text(encoding="utf-8"))

        flagged = [name for name in emitted if any(token in name for token in rc.PROHIBITED_CLAIM_TOKENS)]
        self.assertEqual(flagged, [])
        # POSITIVE CONTROL: the same scan over the same channel must flag a planted key,
        # otherwise `flagged == []` would also hold for a scan that can never fire.
        planted = dict(emitted, readiness="ready")
        self.assertEqual([name for name in planted if any(token in name for token in rc.PROHIBITED_CLAIM_TOKENS)], ["readiness"])

    def test_field_values_are_deliberately_not_token_screened(self) -> None:
        """DECIDED, not overlooked. Only field NAMES are screened, so a value CAN assert what
        Implementation Decision 10 forbids, and the module docstring says so. A value screen
        would refuse true statements -- an `authoritative_gate` of `mise trust ./mise.toml &&
        mise run check` contains "trust", a `ci_expectation` naming a pinned toolchain contains
        "tool" -- while a determined author just spells the claim another way; the reader makes
        the same trade for the same reason when it screens only unrecognized names. Pinned here
        so the decision cannot be reversed silently and the docstring's residual stays true."""
        claim = "this manifest PROVES readiness, ownership, trust, tool identity and route"

        result, code = self.write(writing_profile=claim)

        self.assertEqual(code, 0, result)
        read, read_code = rc.inspect_command(self.target)
        self.assertEqual((read_code, read["status"]), (0, "valid"), read)
        self.assertEqual(read["contract"]["writing_profile"], claim)
        # The mitigation that DOES hold: the disclaimer is emitted above the values.
        self.assertIn(b"# Not proof of ownership, tool identity, trust, route, or readiness", self.path.read_bytes())

    def test_a_value_cannot_smuggle_a_prohibited_claim_into_a_FIELD_NAME(self) -> None:
        """The line the previous test draws is between NAMES and VALUES: a claim in a value is
        accepted and a claim in a name is refused. That line only holds if a value cannot BECOME
        a name, which is what a TOML injection would do -- close the string, open a new key. The
        escape is what contains it, so this is the security half of a guard whose other half
        (`escaping round-trips`) was already covered: the emitted key set must stay exactly the
        reader's ten fields no matter what a value contains."""
        for label, payload in (
            ("closes the string and opens a key", '"\nreadiness = "ready'),
            ("bare newline", 'a\nownership = "proven"'),
            ("carriage return", 'a\rtrust = "established"'),
            ("comment then key", 'a" # x\nroute = "bound'),
        ):
            with self.subTest(injection=label):
                fresh = Path(self.tmp.name) / f"inject-{abs(hash(label))}"
                fresh.mkdir()

                result, code = rw.write_command(fresh, fields(writing_profile=payload), force=False)

                self.assertEqual(code, 0, result)
                emitted = rw.tomllib.loads((fresh / rc.MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
                # The injected name is not a key, and no key beyond the closed set appeared.
                self.assertEqual(set(emitted), set(rc.REQUIRED_FIELDS), label)
                self.assertEqual([n for n in emitted if any(t in n for t in rc.PROHIBITED_CLAIM_TOKENS)], [], label)
                # It survives as the VALUE it was, which is the accepted half of the trade.
                self.assertEqual(emitted["writing_profile"], payload, label)

    def test_cli_has_no_option_for_a_prohibited_claim(self) -> None:
        rejected = self.cli(argv_for(self.target, "--readiness", "ready"))
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("--readiness", rejected.stderr)
        # POSITIVE CONTROL: an otherwise identical argv without the option is accepted,
        # so the exit 2 above is the unknown option and not a broken invocation.
        accepted = self.cli(argv_for(self.target))
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def cli(self, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(WRITER), *argv], capture_output=True, text=True)


class EmittedByteTests(WriterBase):
    def test_emitted_bytes_are_exactly_the_manifest_including_the_disclaimer(self) -> None:
        """Observe the BYTES. The predecessor of this test was named for the emitted bytes and
        observed `tomllib.loads(...)` keys instead, so the header -- the only place the file
        disclaims being proof of ownership, tool identity, trust, route, or readiness -- was
        unguarded against deletion or inversion: mutations injecting "This manifest is
        AUTHORIZATION to push, merge and deploy" and "proof of readiness, ownership, trust and
        route" into it both passed all 26 tests. TOML cannot see a comment, so an exact byte
        comparison against a literal spelled out in this file is the only channel that can."""
        self.write()

        self.assertEqual(self.path.read_bytes(), expected_manifest_bytes())

    def test_a_claim_injected_into_the_header_is_caught_by_the_byte_comparison(self) -> None:
        """POSITIVE CONTROL for the assertion above, driven the way the surviving mutations
        were -- change the module's header and re-emit -- rather than by editing a string the
        test already holds. The last assertion is why the key-scanning predecessor could never
        have caught this: over its channel, the injected claim is not there at all."""
        fresh = Path(self.tmp.name) / "mutated"
        fresh.mkdir()
        injected = "# This manifest is AUTHORIZATION to push, merge and deploy.\n"

        with mock.patch.object(rw, "HEADER", rw.HEADER + injected):
            result, code = rw.write_command(fresh, fields(), force=False)

        self.assertEqual(code, 0, result)
        emitted = (fresh / ".agentic-sdlc" / "repo.toml").read_bytes()
        self.assertIn(b"AUTHORIZATION", emitted)
        self.assertNotEqual(emitted, expected_manifest_bytes())
        self.assertEqual([name for name in rw.tomllib.loads(emitted.decode("utf-8")) if any(token in name for token in rc.PROHIBITED_CLAIM_TOKENS)], [])


class RenderNetTests(WriterBase):
    """`render_manifest` parses its own output back through the READER and compares the result
    before a byte reaches the filesystem. That net is what the module docstring's claim that this
    module "cannot emit something the reader refuses" rests on, and it had zero coverage: both
    skipping the reparse and dropping the equality check survived every test -- an unguarded
    claim of exactly the shape that produced an earlier finding.

    Both stops are internal failures BEFORE any effect, so they are the reachable sites for
    Decision 9's code 1, which had no assertion anywhere in the suite: `INTERNAL_CODE = 1`
    could be changed to 3 or 0 and stay green, leaving one of the five codes unguarded against
    precisely the misclassification that produced the earlier effect-code findings."""

    def test_a_render_the_reader_rejects_is_an_internal_failure_before_any_effect(self) -> None:
        """The reparse leg. The reader instance the WRITER holds is patched, so the raised class
        is `rw._reader.ContractError` -- the test's own `rc` is a separately loaded module whose
        exception class the writer's `except` would not catch."""
        def rejecting(payload: bytes) -> dict:
            raise rw._reader.ContractError("refused", "planted parse failure")

        with mock.patch.object(rw._reader, "parse_contract", rejecting):
            result, code = self.write()

        self.assertEqual(result["status"], "failed", result)
        # Decision 9's code 1, pinned as a LITERAL and not as `rw.INTERNAL_CODE`, which would
        # agree with any mutation of the constant.
        self.assertEqual(code, 1, result)
        self.assertEqual(result["exit_code"], 1, result)
        self.assertIn("not readable", result["reasons"][0])
        # 1 means "before any effect", so nothing may exist -- not even the state root.
        self.assertEqual(result["effect"], "none", result)
        self.assertFalse(self.state.exists(), "the render net must stop before any effect")

    def test_a_render_that_does_not_round_trip_is_an_internal_failure(self) -> None:
        """The comparison leg. A reparse that SUCCEEDS but disagrees with the contract is the
        case the equality check exists for, and dropping that check let it through."""
        real_parse = rw._reader.parse_contract

        def drifting(payload: bytes) -> dict:
            return dict(real_parse(payload), queue_adapter="a value the operator never supplied")

        with mock.patch.object(rw._reader, "parse_contract", drifting):
            result, code = self.write()

        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["exit_code"], 1, result)
        self.assertIn("round-trip", result["reasons"][0])
        self.assertEqual(result["effect"], "none", result)
        self.assertFalse(self.state.exists())

    def test_render_net_control_the_unpatched_render_reparses_and_agrees(self) -> None:
        """POSITIVE CONTROL for both legs: the real reparse runs, agrees, and writes. So the two
        failures above are the planted disagreement and not a broken fixture."""
        observed: list[bytes] = []
        real_parse = rw._reader.parse_contract

        def recording(payload: bytes) -> dict:
            observed.append(payload)
            return real_parse(payload)

        with mock.patch.object(rw._reader, "parse_contract", recording):
            result, code = self.write()

        self.assertEqual(code, 0, result)
        # The reparse is fed the bytes that are then written -- not a re-render of them.
        self.assertEqual(observed, [self.path.read_bytes()])

    def test_a_control_character_in_a_value_is_escaped_and_round_trips(self) -> None:
        """A raw control character is a parse error inside a TOML basic string, and values reach
        this module straight from argv, which can carry any byte. The escape is what keeps such a
        value writable at all; without it the render net above turns the same input into a code-1
        internal failure.

        This branch also subsumes part of the named-escape table above it, which is worth
        recording so a future reader does not chase an equivalent mutant: `\\n`, `\\r`, `\\t`,
        `\\b` and `\\f` are all below 0x20, so deleting any of them from that table changes
        nothing observable -- this fallback emits `\\uXXXX` for them instead. Only the `"` and
        `\\` entries are load-bearing there, because those two are the printable characters that
        can close or reopen the string, and both are covered."""
        awkward = "gate\x01and\x7fdelete"

        result, code = self.write(authoritative_gate=awkward)

        self.assertEqual(code, 0, result)
        emitted = self.path.read_bytes()
        self.assertNotIn(b"\x01", emitted)
        self.assertNotIn(b"\x7f", emitted)
        self.assertIn(b"\\u0001", emitted)
        self.assertIn(b"\\u007F", emitted)
        read, read_code = rc.inspect_command(self.target)
        self.assertEqual((read_code, read["status"]), (0, "valid"), read)
        self.assertEqual(read["contract"]["authoritative_gate"], awkward)

    def test_a_value_that_cannot_be_encoded_is_a_schema_refusal_not_a_crash(self) -> None:
        """Exactly what a non-UTF-8 argv byte becomes: Python decodes argv with
        `surrogateescape`, so a stray `0xFF` arrives as a lone surrogate that `encode("utf-8")`
        cannot render. Without the encode check the failure lands later at the payload encode as
        an uncaught `UnicodeEncodeError` -- no result document and no Decision 9 exit code at
        all."""
        result, code = self.write(writing_profile="profile\udcff")

        self.assertRefused(result, code, 2, "invalid writing_profile")
        self.assertFalse(self.state.exists())

    def test_a_non_utf8_argv_byte_actually_reaches_that_refusal(self) -> None:
        """The channel the test above stands in for, end to end and out of process, so the lone
        surrogate is not just a hand-built Python value."""
        completed = subprocess.run(
            [sys.executable, str(WRITER), *argv_for(self.target, writing_profile="profile\udcff")],
            capture_output=True,
        )

        self.assertEqual(completed.returncode, 2, completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["status"], "refused", completed.stdout)
        self.assertFalse(self.state.exists())


class SchemaAgreementAtImportTests(WriterBase):
    """`ORDERED_FIELDS` fixes the emission ORDER only; the reader's `REQUIRED_FIELDS` stays the
    authority on WHICH fields exist. The import-time raise is what turns a disagreement into a
    loud failure rather than a manifest silently missing a field the reader requires -- the
    docstring's claim that "a field added there cannot be silently omitted here". Removing the
    raise survived every test, because with the two in agreement it never fires, so the only way
    to observe it is to import a copy that disagrees."""

    def _import_copy(self, source: str, name: str):
        """Import a writer copy from a scratch directory with the REAL reader beside it.

        `_load_reader` resolves the reader as a sibling of the writer's own resolved path, so the
        copy needs one; a symlink supplies it without duplicating the reader's bytes.
        """
        scratch = Path(self.tmp.name) / name
        scratch.mkdir()
        copy = scratch / WRITER.name
        copy.write_text(source, encoding="utf-8")
        (scratch / READER.name).symlink_to(READER)
        return _load(f"_writer_copy_{name}", copy)

    def test_a_writer_missing_a_field_the_reader_requires_fails_at_import(self) -> None:
        source = WRITER.read_text(encoding="utf-8")
        dropped = source.replace('    "writing_profile",\n)', ")", 1)
        self.assertNotEqual(dropped, source, "the fixture did not drop a field")

        with self.assertRaises(RuntimeError) as caught:
            self._import_copy(dropped, "dropped")

        self.assertIn("disagrees", str(caught.exception))

    def test_import_guard_control_the_unmodified_source_imports(self) -> None:
        """POSITIVE CONTROL: the same scratch-directory machinery imports the real source
        cleanly, so the raise above is the field disagreement and not the copy."""
        module = self._import_copy(WRITER.read_text(encoding="utf-8"), "clean")

        self.assertEqual(set(module.ORDERED_FIELDS), set(rc.REQUIRED_FIELDS))


class PersistenceTests(WriterBase):
    """Both `fsync` calls sit AFTER the manifest exists, so each failure is an admitted UNKNOWN
    effect under Decision 9 and never a clean refusal. Neither branch had coverage, so removing
    either call survived every test -- and with a call removed, its failure branch is simply
    gone."""

    def test_a_failed_manifest_fsync_is_an_admitted_unknown_effect(self) -> None:
        with mock.patch.object(os, "fsync", mock.Mock(side_effect=OSError(errno.EIO, "io error"))):
            result, code = self.write()

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "manifest-unknown", result)
        self.assertIn("cannot write", result["reasons"][0])
        self.assertTrue(self.path.exists(), "the effect is real, which is why it cannot be 1 or 3")

    def test_a_failed_state_root_fsync_is_an_admitted_unknown_effect(self) -> None:
        """The second call, which persists the state root's own directory entry. The manifest's
        fsync is allowed through so this drives the one after it, and the call count is asserted
        so a removed call cannot masquerade as a passing test."""
        calls: list[int] = []
        real_fsync = os.fsync

        def failing(fd: int) -> None:
            calls.append(fd)
            if len(calls) == 1:
                real_fsync(fd)
                return
            raise OSError(errno.EIO, "io error")

        with mock.patch.object(os, "fsync", failing):
            result, code = self.write()

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "manifest-unknown", result)
        self.assertIn("cannot persist", result["reasons"][0])
        self.assertEqual(len(calls), 2, "the state root's own fsync was never reached")
        # The manifest's bytes are complete; it is the DIRECTORY entry that is unknown.
        self.assertEqual(self.path.read_bytes(), expected_manifest_bytes())


class EffectContractTests(WriterBase):
    """Implementation Decision 9's boundary: 1 and 3 both mean "before any effect"."""

    def test_short_write_is_an_admitted_unknown_effect_not_an_internal_failure(self) -> None:
        """A short write leaves a truncated manifest on disk, so it is 4, not the 1 this module
        reported while admitting `manifest-unknown` in the same document. `RLIMIT_FSIZE` with
        `SIGXFSZ` ignored is a real short write: the kernel takes one byte and stops."""
        previous_handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1, hard))
        try:
            result, code = self.write()
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
            signal.signal(signal.SIGXFSZ, previous_handler)

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "manifest-unknown", result)
        # The effect is REAL, which is the entire reason the code can be neither 1 nor 3.
        self.assertEqual(self.path.read_bytes(), b"#")
        read, read_code = rc.inspect_command(self.target)
        self.assertEqual(read["status"], "refused", read)
        self.assertEqual(read_code, 2, read)

    def test_failing_to_mode_a_created_manifest_is_an_admitted_effect(self) -> None:
        """The created manifest EXISTS and is empty by then, which the reader refuses as
        malformed. An unhandled `OSError` here would leave that behind while producing no
        result document and no Decision 9 exit code at all. The state root is pre-created so
        this drives the manifest's `fchmod`, and umask 000 is what makes it happen."""
        self.state.mkdir()
        previous = os.umask(0o000)
        try:
            with mock.patch.object(os, "fchmod", mock.Mock(side_effect=OSError(errno.EPERM, "denied"))):
                result, code = self.write()
        finally:
            os.umask(previous)

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "manifest-unknown", result)
        self.assertEqual(self.path.read_bytes(), b"")
        read, _ = rc.inspect_command(self.target)
        self.assertEqual(read["status"], "refused", read)

    def test_failing_to_mode_a_created_state_root_is_an_admitted_effect(self) -> None:
        """The same escape one level up: at umask 000 the writer clears the other-write bit
        from the state root it just created, and that `fchmod` is the reachable failure."""
        previous = os.umask(0o000)
        try:
            with mock.patch.object(os, "fchmod", mock.Mock(side_effect=OSError(errno.EPERM, "denied"))):
                result, code = self.write()
        finally:
            os.umask(previous)

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "state-root-created", result)
        self.assertTrue(self.state.is_dir())
        self.assertFalse(self.path.exists())

    def test_an_inherited_acl_is_pre_flighted_so_creating_the_state_root_costs_nothing(self) -> None:
        """A default ACL on the repository root -- shared NFS, a setgid project directory -- is
        inherited by the state root this module creates, which the engine then refuses. Checked
        before `mkdir`, so it is a clean refusal that leaves nothing behind."""
        if not try_set_acl(self.target, "system.posix_acl_default", 0o7, 0o5):
            self.skipTest("filesystem cannot carry a POSIX default ACL")

        result, code = self.write()

        self.assertRefused(result, code, 3, "inheritable ACL state")  # also asserts effect none
        self.assertFalse(self.state.exists(), "an ACL-poisoned state root was left behind")

    def test_a_stop_after_the_state_root_exists_admits_the_effect(self) -> None:
        """POSITIVE CONTROL for the pre-flight above AND the code-4 half of Decision 9: with
        only the pre-flight disabled, the same fixture reaches the post-`mkdir` ACL refusal,
        which is the reachable combination that used to return 3 while reporting an effect."""
        if not try_set_acl(self.target, "system.posix_acl_default", 0o7, 0o5):
            self.skipTest("filesystem cannot carry a POSIX default ACL")

        with mock.patch.object(rw, "_assert_no_inheritable_acl", lambda target_fd: None):
            result, code = self.write()

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "state-root-created", result)
        self.assertTrue(self.state.is_dir())
        self.assertFalse(self.path.exists())


class MountIdentityTests(WriterBase):
    """The engine also requires the bound `(st_dev, mount id)`; the writer must too, or it
    writes a manifest the engine refuses as `foreign-state` and leaves it there."""

    def test_state_root_on_another_mount_is_refused(self) -> None:
        """Mocked at `_mount_id` so it runs on every host and every filesystem. The bind-mount
        test below proves the real probe reports different ids for a real bind mount."""
        self.state.mkdir()
        observed = iter((11, 22))  # target directory, then the state root

        with mock.patch.object(rw, "_mount_id", lambda fd: next(observed, 22)):
            result, code = self.write()

        self.assertRefused(result, code, 3, ".agentic-sdlc")
        self.assertFalse(self.path.exists())

    def test_mount_identity_control_one_mount_is_written(self) -> None:
        """POSITIVE CONTROL: the same patched probe, one id, writes normally."""
        self.state.mkdir()

        with mock.patch.object(rw, "_mount_id", lambda fd: 11):
            result, code = self.write()

        self.assertEqual(code, 0, result)

    def test_existing_manifest_on_another_mount_is_refused_even_with_force(self) -> None:
        """A bind mount can be planted over the manifest itself, and `--force` would then
        replace the contents of a file outside the repository."""
        self.write()
        observed = iter((11, 11, 22))  # target, state root, then the manifest

        with mock.patch.object(rw, "_mount_id", lambda fd: next(observed, 22)):
            result, code = self.write(queue_adapter="replaced", force=True)

        self.assertRefused(result, code, 3, "repo.toml")
        self.assertEqual(self.path.read_bytes(), expected_manifest_bytes())

    def test_the_probe_reads_the_mount_of_the_descriptor_it_is_given(self) -> None:
        """The probe itself, unmocked: two descriptors on one mount agree, and the value is an
        integer rather than a silent None on a platform that has mount ids."""
        self.state.mkdir()
        target_fd = os.open(self.target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, target_fd)
        state_fd = os.open(self.state, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, state_fd)

        if sys.platform != "linux":
            self.assertIsNone(rw._mount_id(target_fd))
            return
        self.assertIsInstance(rw._mount_id(target_fd), int)
        self.assertEqual(rw._mount_id(target_fd), rw._mount_id(state_fd))

    def test_the_probe_reports_the_filesystem_of_the_descriptor_not_a_constant(self) -> None:
        """`st_dev` is the other half of the identity pair, and on a platform without mount ids
        it is the ONLY half, so a constant there would make the whole comparison vacuous. Two
        descriptors on genuinely different filesystems must report different values."""
        here = os.open(self.target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, here)
        if sys.platform != "linux":
            self.skipTest("no second filesystem is guaranteed off Linux")
        other = os.open("/proc", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, other)

        self.assertEqual(rw._node_identity(here)[0], os.fstat(here).st_dev)
        self.assertNotEqual(rw._node_identity(here)[0], rw._node_identity(other)[0])

    @unittest.skipUnless(sys.platform == "linux", "mount ids are a Linux facility")
    def test_an_unreadable_mount_identity_is_refused_rather_than_assumed_equal(self) -> None:
        """On Linux the mount id is not optional. Returning None when `fdinfo` cannot be read
        would put None on BOTH sides of the comparison, so every foreign mount would compare
        equal and the refusal this check exists for would silently stop happening."""
        self.state.mkdir()
        real_open = builtins.open

        def blocked(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith("/proc/self/fdinfo"):
                raise OSError(errno.EACCES, "denied")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(builtins, "open", blocked):
            result, code = self.write()

        self.assertRefused(result, code, 3, "cannot read mount identity")
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(sys.platform == "linux", "mount ids are a Linux facility")
    def test_an_fdinfo_without_a_mount_id_is_refused(self) -> None:
        """An identity this module cannot find is one it cannot compare, so absence refuses
        rather than defaulting."""
        self.state.mkdir()

        with mock.patch.object(builtins, "open", self._fdinfo_returning(b"pos:\t0\nflags:\t0100000\n")):
            result, code = self.write()

        self.assertRefused(result, code, 3, "mount identity is unavailable")
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(sys.platform == "linux", "mount ids are a Linux facility")
    def test_an_unparseable_mount_id_is_refused(self) -> None:
        self.state.mkdir()

        with mock.patch.object(builtins, "open", self._fdinfo_returning(b"mnt_id:\tnot-a-number\n")):
            result, code = self.write()

        self.assertRefused(result, code, 3, "unreadable mount identity")
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(sys.platform == "linux", "mount ids are a Linux facility")
    def test_fdinfo_control_a_well_formed_substitute_is_accepted(self) -> None:
        """POSITIVE CONTROL for the three refusals above: the same substituted `fdinfo`, this
        time well formed, writes -- so those refusals are what each fixture says they are and not
        the substitution itself."""
        self.state.mkdir()

        with mock.patch.object(builtins, "open", self._fdinfo_returning(b"pos:\t0\nmnt_id:\t4242\n")):
            result, code = self.write()

        self.assertEqual(code, 0, result)

    def _fdinfo_returning(self, content: bytes):
        """Substitute only `/proc/self/fdinfo/<fd>` reads; every other `open` is the real one."""
        real_open = builtins.open

        def substituted(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith("/proc/self/fdinfo"):
                return io.BytesIO(content)
            return real_open(path, *args, **kwargs)

        return substituted

    def test_a_refusal_inside_the_manifest_open_inherits_the_state_root_effect(self) -> None:
        """Decision 9's derived-code invariant one level down. Refusals raised inside
        `_open_manifest`'s custody block by SHARED helpers -- the ACL predicate, the mount probe
        -- carry no effect of their own, so the caller's effect has to be attached or a stop that
        already created the state root reports a clean `refused`/3 while a directory sits on disk.
        Reaching that combination for real needs the state root created while a manifest already
        exists below it, which only a concurrent actor produces, so the create is reported
        directly here: the invariant is what is under test, not the race that reaches it. The
        analogous line one level up is covered by a real fixture, so leaving this one unguarded
        was the asymmetry."""
        self.write()
        before = self.path.read_bytes()
        real_open_state_root = rw._open_state_root

        def reports_a_create(target_fd, root):
            state_fd, _ = real_open_state_root(target_fd, root)
            return state_fd, "state-root-created"

        observed = iter((11, 11, 22))  # target, state root, then the manifest
        with mock.patch.object(rw, "_open_state_root", reports_a_create), mock.patch.object(rw, "_mount_id", lambda fd: next(observed, 22)):
            result, code = self.write(queue_adapter="replaced", force=True)

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "partial", result)
        self.assertEqual(result["effect"], "state-root-created", result)
        self.assertEqual(self.path.read_bytes(), before)

    @unittest.skipUnless(bind_mount_is_available(), "unprivileged mount namespaces are unavailable")
    def test_a_real_bind_mounted_state_root_is_refused(self) -> None:
        """The mechanism end to end. A bind mount from the same filesystem shares `st_dev` with
        the repository, so the mount id is the only check that sees it."""
        repo = Path(self.tmp.name) / "bound"
        (repo / ".agentic-sdlc").mkdir(parents=True)
        foreign = Path(self.tmp.name) / "foreign"
        foreign.mkdir()
        script = (
            "import json, subprocess, sys\n"
            f"subprocess.run(['mount', '--bind', {str(foreign)!r}, {str(repo / '.agentic-sdlc')!r}], check=True)\n"
            f"done = subprocess.run([sys.executable, {str(WRITER)!r}, *{argv_for(repo)!r}], capture_output=True, text=True)\n"
            "print(json.dumps({'code': done.returncode, 'out': done.stdout}))\n"
        )

        completed = subprocess.run(["unshare", "-Urm", sys.executable, "-c", script], capture_output=True, text=True, timeout=120)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        observed = json.loads(completed.stdout)
        self.assertEqual(observed["code"], 3, observed)
        self.assertEqual(json.loads(observed["out"])["effect"], "none", observed)
        self.assertFalse((foreign / "repo.toml").exists(), "wrote into the foreign mount")
        # POSITIVE CONTROL: the bind mount existed only in that namespace, so the identical
        # argv against the identical fixture writes here -- the refusal was the mount, not
        # anything else about the fixture.
        accepted = subprocess.run([sys.executable, str(WRITER), *argv_for(repo)], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stdout)
        self.assertTrue((repo / ".agentic-sdlc" / "repo.toml").exists())


class ExtendedAclTests(WriterBase):
    """`_has_extended_acl` is the fail-closed half of permitting group-write, and it had zero
    coverage: a mutation making it return immediately survived all 26 tests."""

    def test_extended_acl_on_the_state_root_is_refused(self) -> None:
        self.state.mkdir()
        if not try_set_acl(self.state, "system.posix_acl_access", 0o7, 0o5):
            self.skipTest("filesystem cannot carry a POSIX ACL")

        result, code = self.write()

        self.assertRefused(result, code, 3, "unsafe ACL state")
        self.assertFalse(self.path.exists())

    def test_extended_acl_on_an_existing_manifest_is_refused_even_with_force(self) -> None:
        self.write()
        before = self.path.read_bytes()
        if not try_set_acl(self.path, "system.posix_acl_access", 0o6, 0o4):
            self.skipTest("filesystem cannot carry a POSIX ACL")

        result, code = self.write(queue_adapter="replaced", force=True)

        self.assertRefused(result, code, 3, "unsafe ACL state")
        self.assertEqual(self.path.read_bytes(), before)

    def test_the_refusal_is_driven_by_what_listxattr_reports(self) -> None:
        """Runs on every filesystem, including one that cannot carry an ACL, so the guard has
        coverage even where the fixtures above skip."""
        self.state.mkdir()

        with mock.patch.object(os, "listxattr", lambda fd: ["system.posix_acl_access"]):
            result, code = self.write()

        self.assertRefused(result, code, 3, "unsafe ACL state")
        self.assertFalse(self.path.exists())

    def test_a_filesystem_that_cannot_carry_an_acl_is_tolerated(self) -> None:
        """POSITIVE CONTROL for the two assertions above: only ENOTSUP is tolerated, and the
        same call succeeds through it, so their refusals are the ACL and not the fixture."""
        self.state.mkdir()

        def unsupported(fd: int) -> list[str]:
            raise OSError(errno.ENOTSUP, "not supported")

        with mock.patch.object(os, "listxattr", unsupported):
            result, code = self.write()

        self.assertEqual(code, 0, result)

    def test_an_unreadable_acl_state_is_refused_rather_than_assumed_absent(self) -> None:
        self.state.mkdir()

        def denied(fd: int) -> list[str]:
            raise OSError(errno.EACCES, "denied")

        with mock.patch.object(os, "listxattr", denied):
            result, code = self.write()

        self.assertRefused(result, code, 3, "cannot read ACL state")


class NonRegularManifestTests(WriterBase):
    """A FIFO is the one non-regular node an unprivileged actor can plant at the manifest path,
    and `O_WRONLY` without `O_NONBLOCK` blocked this module in `open(2)` forever on it."""

    def test_a_fifo_at_the_manifest_path_does_not_block_the_writer(self) -> None:
        """Out of process with a TIMEOUT on purpose: the defect is an unbounded `open(2)`, so an
        in-process assertion would hang the whole suite instead of failing it."""
        self.state.mkdir()
        os.mkfifo(self.path)

        try:
            completed = subprocess.run([sys.executable, str(WRITER), *argv_for(self.target, "--force")], capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            self.fail("the writer blocked in open(2) on a FIFO planted at the manifest path")

        self.assertEqual(completed.returncode, 3, completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["effect"], "none", completed.stdout)

    def test_a_fifo_with_a_reader_attached_reaches_the_regular_file_guard(self) -> None:
        """The other half. With a reader attached the open SUCCEEDS, so the regular-file check
        is what has to refuse -- and before `O_NONBLOCK` that check was unreachable for a FIFO,
        because the open never returned at all."""
        self.state.mkdir()
        os.mkfifo(self.path)
        reader_fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        self.addCleanup(os.close, reader_fd)

        result, code = self.write(force=True)

        self.assertRefused(result, code, 3, "unsafe")
        try:
            drained = os.read(reader_fd, 65536)
        except BlockingIOError:
            drained = b""
        self.assertEqual(drained, b"", "manifest bytes were written into a planted FIFO")


class SchemaRefusalTests(WriterBase):
    def test_missing_field_is_a_schema_refusal(self) -> None:
        incomplete = fields()
        del incomplete["ci_expectation"]

        result, code = rw.write_command(self.target, incomplete, force=False)

        self.assertRefused(result, code, 2, "ci_expectation")
        self.assertFalse(self.path.exists())

    def test_blank_value_is_a_schema_refusal(self) -> None:
        result, code = self.write(queue_adapter="   ")

        self.assertRefused(result, code, 2, "queue_adapter")
        self.assertFalse(self.path.exists())

    def test_wrong_schema_value_is_a_schema_refusal(self) -> None:
        result, code = self.write(schema="agentic-sdlc/repository-contract@99")

        self.assertRefused(result, code, 2, "schema")
        self.assertFalse(self.path.exists())


class CustodyRefusalTests(WriterBase):
    def test_relative_target_is_a_clean_refusal(self) -> None:
        result, code = rw.write_command(Path("repo"), fields(), force=False)

        self.assertRefused(result, code, 3, "absolute")

    def test_missing_target_is_a_clean_refusal(self) -> None:
        result, code = rw.write_command(self.target / "absent", fields(), force=False)

        self.assertRefused(result, code, 3, "target")

    def test_symlinked_state_root_is_a_clean_refusal(self) -> None:
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        self.state.symlink_to(outside)

        result, code = self.write()

        self.assertRefused(result, code, 3, ".agentic-sdlc")
        self.assertFalse((outside / "repo.toml").exists())

    def test_symlinked_manifest_is_a_clean_refusal(self) -> None:
        """`O_NOFOLLOW` on the manifest open is the ONLY thing between `--force` and writing
        tracked repository policy to an arbitrary path, and the predecessor of this test could
        not observe it: it symlinked the manifest to a `decoy` it never created, so the refusal
        it saw was ENOENT on a dangling link -- which happens with or without `O_NOFOLLOW`.
        Driven against a REAL file outside the state root, the mutation removing `O_NOFOLLOW`
        returns exit 0 `written` and lands the entire manifest on that file with all 46 tests
        green. The link target is deliberately admissible to every OTHER custody predicate --
        regular, single-linked, caller-owned, not other-writable, same filesystem and mount --
        which is what makes the refusal attributable to the traversal and nothing else, and the
        control below PROVES that admissibility instead of asserting it."""
        outside = Path(self.tmp.name) / "outside.toml"
        outside.write_bytes(OUTSIDE_CONTENT)
        self.state.mkdir()
        self.path.symlink_to(outside)
        observed: list[int] = []
        real_open = os.open

        def recording_open(path, flags, *args, **kwargs):
            try:
                return real_open(path, flags, *args, **kwargs)
            except OSError as exc:
                if path == rc.REPO_MANIFEST_NAME:
                    observed.append(exc.errno)
                raise

        with mock.patch.object(os, "open", recording_open):
            result, code = self.write(force=True)

        self.assertRefused(result, code, 3, "repo.toml")
        # ATTRIBUTION. ELOOP on the manifest's own open is what `O_NOFOLLOW` and nothing else
        # produces. The dangling-decoy fixture this replaced yields ENOENT here instead, which
        # is exactly why it passed against a writer that follows the link.
        self.assertIn(errno.ELOOP, observed, f"the refusal was not O_NOFOLLOW; errnos were {observed}")
        # POSITIVE CONTROL on the effect: the file outside the repository is untouched.
        self.assertEqual(outside.read_bytes(), OUTSIDE_CONTENT)

    def test_symlink_control_the_identical_file_reached_directly_is_replaced(self) -> None:
        """POSITIVE CONTROL for the refusal above. A file with the same content, owner, mode,
        link count, filesystem and mount IS replaced by `--force` when it is the manifest itself
        rather than a symlink target, so that refusal is the traversal and not some other
        custody predicate the fixture happened to trip."""
        self.state.mkdir()
        self.path.write_bytes(OUTSIDE_CONTENT)

        result, code = self.write(force=True)

        self.assertEqual(code, 0, result)
        self.assertEqual(self.path.read_bytes(), expected_manifest_bytes())

    def test_a_regular_file_target_is_refused_at_the_target_itself(self) -> None:
        """`O_DIRECTORY` on the target is what makes this the TARGET's refusal. Without it the
        open succeeds and the stop moves down to the state root, blaming `.agentic-sdlc` for a
        target that was never a directory; this suite's standing rule is that a refusal has to
        say which check fired."""
        afile = Path(self.tmp.name) / "afile"
        afile.write_text("not a repository\n")

        result, code = rw.write_command(afile, fields(), force=False)

        self.assertRefused(result, code, 3, "cannot open target")

    def test_a_regular_file_at_the_state_root_path_is_a_clean_refusal(self) -> None:
        """`O_DIRECTORY` refuses this at the open with ENOTDIR. That is also why the `S_ISDIR`
        half of the state root's own fstat check is unreachable in production: the descriptor
        cannot be a non-directory, so dropping that half is an equivalent mutant while the
        `st_uid` half beside it is not."""
        self.state.write_text("not a directory\n")

        result, code = self.write()

        self.assertRefused(result, code, 3, ".agentic-sdlc")
        self.assertEqual(self.state.read_text(), "not a directory\n")

    def test_a_fifo_at_the_state_root_path_does_not_block_the_writer(self) -> None:
        """`O_DIRECTORY` is also what makes the state root's open unable to hang on a FIFO --
        ENOTDIR comes back before any rendezvous -- so `O_NONBLOCK` there is the reader parity
        the docstring calls it, and removing it changes nothing. Out of process with a timeout,
        because if that reasoning were wrong the failure mode would be a hung suite rather than
        a red test."""
        os.mkfifo(self.state)

        try:
            completed = subprocess.run([sys.executable, str(WRITER), *argv_for(self.target)], capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            self.fail("the writer blocked in open(2) on a FIFO planted at the state root path")

        self.assertEqual(completed.returncode, 3, completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["effect"], "none", completed.stdout)

    def test_o_directory_makes_the_state_roots_isdir_half_unreachable(self) -> None:
        """EQUIVALENCE PROOF, not a behavioural guard, and labelled as one so it is not mistaken
        for coverage. The state root's fstat check reads `not S_ISDIR(...) or st_uid !=
        geteuid()`. The `st_uid` half has a real fixture below, but the `S_ISDIR` half can never
        be true, because every open of that path carries `O_DIRECTORY` and the kernel rejects
        each non-directory AT THE OPEN -- so the descriptor that reaches `fstat` is always a
        directory and dropping that half changes nothing observable.

        Three legs, because the claim rests on all three: the premise is read out of the writer's
        own source rather than assumed, so removing `O_DIRECTORY` there fails this test instead of
        silently invalidating the equivalence; the kernel is then observed rejecting every node
        type an unprivileged actor can plant; and the writer is observed refusing each one
        cleanly, which is the behaviour that actually matters."""
        # LEG 1: the premise, read from `_open_state_root` itself.
        body = WRITER.read_text(encoding="utf-8").split("def _open_state_root(", 1)[1]
        flags_line = next(line for line in body.splitlines() if line.strip().startswith("flags ="))
        self.assertIn("os.O_DIRECTORY", flags_line, "this equivalence proof rests on O_DIRECTORY")

        planted = Path(self.tmp.name) / "planted"
        planted.mkdir()
        makers = {
            "regular-file": lambda p: p.write_bytes(b"x"),
            "fifo": os.mkfifo,
            "symlink-to-a-directory": lambda p: p.symlink_to(planted),
            "dangling-symlink": lambda p: p.symlink_to(planted / "absent"),
        }
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        for label, make in makers.items():
            with self.subTest(node=label):
                # LEG 2: the kernel refuses the open, so `fstat` never sees this node.
                make(planted / label)
                with self.assertRaises(OSError) as caught:
                    os.close(os.open(planted / label, flags))
                self.assertIn(caught.exception.errno, (errno.ENOTDIR, errno.ELOOP), label)

                # LEG 3: the writer's own behaviour for the same node planted at the state root.
                repo = Path(self.tmp.name) / f"repo-{label}"
                repo.mkdir()
                make(repo / rc.STATE_DIRECTORY_NAME)
                result, code = rw.write_command(repo, fields(), force=True)
                self.assertRefused(result, code, 3, rc.STATE_DIRECTORY_NAME)
                self.assertFalse((repo / rc.MANIFEST_RELATIVE_PATH).exists(), label)
        # POSITIVE CONTROL for leg 2: the identical flags DO open a real directory, so those
        # failures are the node type and not an unusable flag set.
        os.close(os.open(planted, flags))

    def test_foreign_owned_state_root_is_a_clean_refusal(self) -> None:
        """The state root's `st_uid` check had no coverage at all: with it off this module
        creates the manifest inside a directory owned by another user, which the engine then
        refuses as `foreign-state`. A test cannot chown, so `os.geteuid` is patched -- the
        technique this suite already uses for `os.fchmod` and `os.listxattr`. Only ONE value is
        supplied on purpose: the create path consults it exactly once, so a second call would
        raise `StopIteration` rather than pass silently."""
        self.state.mkdir()

        with mock.patch.object(os, "geteuid", mock.Mock(side_effect=[os.geteuid() + 1])):
            result, code = self.write()

        self.assertRefused(result, code, 3, f"unsafe {rc.STATE_DIRECTORY_NAME}")
        self.assertNotIn("repo.toml", result["reasons"][0], "this must be the state root's check")
        self.assertFalse(self.path.exists())

    def test_state_root_ownership_control_our_own_uid_is_written(self) -> None:
        """POSITIVE CONTROL: the identical patched probe reporting our real uid writes."""
        self.state.mkdir()

        with mock.patch.object(os, "geteuid", mock.Mock(side_effect=[os.geteuid()])):
            result, code = self.write()

        self.assertEqual(code, 0, result)

    def test_other_writable_state_root_is_a_clean_refusal(self) -> None:
        self.state.mkdir()
        os.chmod(self.state, 0o757)  # mkdir(mode=) is masked by the umask; chmod is not

        result, code = self.write()

        self.assertRefused(result, code, 3, "unsafe")
        self.assertFalse(self.path.exists())

    def test_manifest_directory_is_a_clean_refusal(self) -> None:
        self.state.mkdir()
        self.path.mkdir()

        result, code = self.write(force=True)

        self.assertRefused(result, code, 3, "unsafe")


class CommandLineTests(WriterBase):
    def cli(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(WRITER), *argv], capture_output=True)

    def test_cli_writes_and_prints_exactly_one_canonical_object(self) -> None:
        completed = self.cli(*argv_for(self.target))

        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertEqual(completed.stdout, rc.canonical_bytes(json.loads(completed.stdout)))
        self.assertEqual(json.loads(completed.stdout)["status"], "written")
        read, _ = rc.inspect_command(self.target)
        self.assertEqual(read["status"], "valid", read)

    def test_cli_refusal_exit_code_is_three_not_one(self) -> None:
        """Implementation Decision 9. `activation-planner.py` maps refusals to 1; the
        reader is the contract this writer follows."""
        self.cli(*argv_for(self.target))

        completed = self.cli(*argv_for(self.target))

        self.assertEqual(completed.returncode, 3, completed.stdout.decode())
        self.assertEqual(json.loads(completed.stdout)["exit_code"], 3)


if __name__ == "__main__":
    unittest.main()
