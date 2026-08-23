#!/usr/bin/env python3
"""Run any test target with the installers' birth-timestamp clock FORCED COARSE.

WHY THIS FILE EXISTS
--------------------
Both lifecycle installers name a filesystem object by `stat-v2:<dev>:<ino>:<btime>`. Inodes are
reused, so the birth timestamp is the entire discriminator, and every filesystem quantizes it:
objects created inside one quantum are stamped identically. `scripts/install_skill_bundle.py` and
`skills/codex-research-os/scripts/install_research_os.py` therefore try to prove a recorded witness
SETTLED (its birth quantum provably closed) with one probe, and DEFER what the probe cannot prove:
the record is persisted carrying `witness_settled: false` and one bounded wait is paid at the end
of the command.

That deferral-and-marker path is invisible to this repository's own gate. A development host with
fine-grained btime (microsecond deltas between back-to-back creates) settles on the FIRST probe
every single time, so nothing is ever deferred, no marker is ever written, and no consumer of a
marker ever runs -- the whole path executes zero times in a full green local suite. A CI runner
whose btime is coarse (one distinct value measured across 40 creates inside a 787 microsecond
window) runs it for real, on every transaction. A gate that cannot reach a path cannot defend it,
and a six-minute CI round trip is not an iteration surface.

This module closes that hole. It forces the birth clock coarse at the two seams the product
actually consults, then hands the test target to `unittest`, so the coarse-clock path is
reproducible and provable on any host, forever.

USAGE
-----
    uv run --python 3.12.11 python -B tests/support/coarse_birth_clock.py \
        test_research_os_lifecycle.TransactionSafetyTests -v

    # whole suite, cheaper quantum (every deferred wait costs up to one quantum of wall clock)
    uv run --python 3.12.11 --with pyyaml==6.0.3 python -B \
        tests/support/coarse_birth_clock.py --quantum 0.25 discover

Any `unittest` name works: `module`, `module.Class`, `module.Class.method`, several at once, or the
literal `discover` for the whole `tests/` tree. Add `--with pyyaml==6.0.3` to the `uv` invocation
whenever a selected module imports `yaml`.

WHAT THE QUANTUM COSTS
----------------------
Every deferred witness makes its command pay a real bounded wait, so the quantum is a wall-clock
multiplier, not a free knob. Measured here: `test_research_os_lifecycle` (45 tests) took 85s at
`--quantum 1.0`; `test_install_skill_bundle` (107 tests) did not finish inside 500s at 1.0 but took
15s at `--quantum 0.05`, finding the identical failure set. So use 1.0 on a focused target where
one-second fidelity is the point, and 0.05 for a module or the whole suite. A quantum only has to
outlast the gap between two back-to-back creations to collapse them, and 50ms outlasts it by
three orders of magnitude.

WHY THIS ANCHORS ON AN OBSERVED BIRTH VALUE (measured, not assumed)
------------------------------------------------------------------
HISTORICAL NOTE, kept because the measurement is the argument: the repo's own two per-test
`simulated_birth_clock` helpers USED to anchor on `origin = time.time_ns()` and floor with Python's
`//`, which rounds toward negative infinity. A btime BELOW that origin lands in bucket -1 and is
reported one whole quantum early -- that is what failed the settlement suite's own positive control
on CI run 32565128438. Seed `agentic-sdlc-249d-recovery` re-anchored BOTH helpers on an observed
birth value with the same upward clamp used here, so they no longer carry the defect; grep
`anchor: int | None = None` in either test module to confirm rather than trusting this sentence.
Measured on this host, which is NOT a coarse-btime host:

  * btime here is fine-grained: 200 creates in 8.6ms produced 200/200 distinct witnesses, minimum
    delta 12,580ns, and the nsec fields are not multiples of any 4ms tick.
  * Even so, a btime read back is consistently slightly BEHIND a `time.time_ns()` sampled
    immediately before the create -- 40/40 negative, -0.023ms to -0.924ms. That small offset is
    all the bucket -1 bug needs.
  * The mechanism of that offset is NOT established here. `clock_getres(CLOCK_REALTIME_COARSE)` is
    4ms on this kernel, but a 4ms-quantized source cannot produce witnesses 12us apart, so the
    coarse clock is ruled OUT as this host's btime source. Do not repeat that explanation; it was
    asserted and then falsified during this investigation.
  * Against ONE fixed origin -- what the helpers actually do -- only the FIRST create falls below
    it: 1/400, crossing at create #1, 5 trials of 5.

So a wall-clock-anchored grid can place the first observation one quantum before every later one,
and the first observation is normally the RECORDED object -- the direction the failure signatures
show. Anchoring on an observed birth value cannot do this: the anchor is itself a btime, so no
btime can precede it, and anything below the anchor is clamped up rather than floored down.

The CI runner is a genuinely coarse-btime host and this one is not, which is the whole reason this
lever exists. `BirthWitnessSettlementTests` in the research-os module records the measurement: run
32554149554 (kernel 6.6.141, ext4) saw ONE distinct btime across 40 back-to-back creates and
repeated an identical (inode, btime) pair in 20 of 20 delete-recreate trials. Keep the two
phenomena apart -- coarse btime on CI is what drives the PRODUCT's settlement-deferral failures,
while the small negative offset above is what makes the HARNESS's bucket -1 bug flake even on a
fine-grained host.

One caveat before trusting a green quantum'd run. With `quantum=0.000000001` the helpers'
`max(1, int(q * 10**9))` yields `quantum_ns == 1`, and `anchor + max(0, (v-anchor)//1)*1` is an
exact identity for every value at or above the anchor -- so that arm returns the host's real btime
untouched apart from clamping a below-anchor value up to the anchor.
That is BY DESIGN: the tests using it are named `..._under_coarse_and_native_birth_clocks`, and
1ns is their NATIVE arm. What is false is the blanket claim in the research-os class docstring that
granularity is "forced through the `_linux_statx` seam in every test here, never inherited from
this host" -- in the 1ns arm it is inherited exactly. Separately, at 0.5s a bucket -1 shifts a
recorded witness ~500ms EARLIER, which pushes an "older than any later replacement" assertion
toward passing rather than failing, so a green result there is weak evidence.

It is also importable, for a test that wants the forced clock in-process. This repository loads
single-file modules by path, so use the same idiom:

    spec = importlib.util.spec_from_file_location("coarse_birth_clock", <this file>)
    ...
    with coarse_birth_clock.forced_coarse_birth_clock(1.0):
        ...

It is deliberately NOT a `mise` task and NOT a leaf of `mise run check`. It forces a host property
to a value the host does not have, so its verdict is a reproduction, not a gate.

HOW THE QUANTUM GRID IS ANCHORED
--------------------------------
Every witness the seam returns is truncated onto a grid of `--quantum` seconds. The grid is
anchored to the FIRST REAL BIRTH VALUE observed after each anchor reset, never to wall-clock time,
and a value below the anchor is clamped up to it. Both rules are load-bearing:

* Anchoring to an observed birth value means the grid boundary can never fall INSIDE one of the
  host filesystem's own quanta. A wall-clock anchor can, and then two objects the host stamped
  identically get different forced witnesses -- a phantom discrimination the host never had. That
  is not hypothetical: the existing per-test helpers in `tests/test_research_os_lifecycle.py` and
  `tests/test_install_skill_bundle.py` anchor on `time.time_ns()`, and on the coarse CI runner
  that produced witnesses exactly one 3600s quantum apart for two files created microseconds
  apart, failing `test_same_quantum_witness_cannot_discriminate_a_reused_inode` on its own
  positive control.
* Clamping up, rather than letting a pre-existing object fall into an earlier bucket, keeps the
  forced clock from GRANTING discrimination. A target that looks older than a probe settles; the
  whole point of this lever is to withhold settlement, so every rounding choice here rounds toward
  "cannot discriminate".

The anchor is reset before every test when run through this module's runner, so a test cannot pass
or fail by where in the quantum it happened to start: whatever that test creates first defines its
own grid, and everything it creates within one quantum of that collapses onto one witness.

`--anchor epoch` opts out of that determinism ON PURPOSE, and is the one mode that models a
filesystem stamping on an absolute clock tick. Only an absolute grid can return a birth value
EARLIER than a wall-clock reading taken before the object was created, which is the mechanism that
makes a wall-clock-anchored simulated clock split a real quantum. It reproduces
`test_same_quantum_witness_cannot_discriminate_a_reused_inode` (measured: 7 of 8 runs at
`--anchor epoch --quantum 0.05`, each with the same one-quantum split CI showed), and it is
intermittent by construction, so it is a diagnostic and never a gate.

WHAT THIS DOES NOT SIMULATE
---------------------------
It fakes a clock. It does not fake a kernel, a filesystem, or an allocator.

* Only IN-PROCESS calls are forced. A test that invokes an installer as a SUBPROCESS
  (`uv run --script`, the bash wrapper, `sys.executable <script>`) gets the host's real clock in
  that child. Such a run is a mix of forced and native, and any result from it must say so.
* It cannot make a clock FINER than the host's, only coarser. That is the only direction that
  matters here, because coarseness is the defect.
* It does not cause inode reuse. The collision CI measured 20 times out of 20 -- a delete and
  recreate landing on the same inode -- is modelled by the tests themselves
  (`reused_inode_witness`), not raced here.
* Real time still passes. A quantum boundary is crossed by the wall clock, so the product's
  bounded wait terminates after at most one quantum instead of hitting its cap. This models a
  coarse host, not a host whose birth clock never advances at all; for that pathological host use
  the existing per-test `simulated_birth_clock(None)` freeze.
* Only the birth timestamp is forced. `st_ctime`, `st_mtime`, `st_atime` and every other stat
  field stay real, because the ownership witness consults none of them.
* The `install_skill_bundle` seam is its whole birth-identity FUNCTION, so its Darwin and Windows
  branches are forced too. The `install_research_os` seam is its Linux `statx` wrapper, so on
  Darwin or Windows that installer reads the host clock unforced.
* A forced witness never reaches disk as a claim about the host: it is a return value inside one
  process. Ownership state written during a forced run is a fixture, not a receipt.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
# The two product seams. Each is matched by the module's resolved `__file__`, not by the name a
# test happened to register in `sys.modules`, because every test module here loads these installers
# by path under a name of its own choosing.
BUNDLE_INSTALLER = REPO_ROOT / "scripts" / "install_skill_bundle.py"
BUNDLE_SEAM = "stat_birth_identity"
RESEARCH_OS_INSTALLER = (
    REPO_ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
)
RESEARCH_OS_SEAM = "_linux_statx"
DEFAULT_QUANTUM_SECONDS = 1.0
OBSERVED_ANCHOR = "observed"
EPOCH_ANCHOR = "epoch"
ANCHORS = (OBSERVED_ANCHOR, EPOCH_ANCHOR)


class QuantumGrid:
    """A birth-timestamp grid, anchored either to an observed value or to the epoch.

    One grid is shared by every patched seam in a run, so two installers exercised by the same
    test agree about what "the same quantum" means.

    `observed` (the default) anchors to the first real value seen since the last reset, which is
    what makes a reproduction deterministic: the boundary is a real birth value, so it cannot fall
    inside one of the host's own quanta, and a test shorter than the quantum observes exactly one
    bucket however the host's clock happened to be sitting.

    `epoch` floors to an absolute grid, which is what a real filesystem does when it stamps on a
    clock tick, and is therefore the only mode that can return a birth value EARLIER than a
    wall-clock reading taken before the object was created. That asymmetry is not academic: it is
    the whole mechanism by which a wall-clock-anchored simulated clock (`origin = time.time_ns()`,
    floor toward the epoch -- the shape of the per-test helpers in
    `tests/test_research_os_lifecycle.py` and `tests/test_install_skill_bundle.py`) drops one
    object into the bucket BELOW its own origin and reports it a full quantum older than a sibling
    the filesystem stamped identically. Reproducing that needs this mode, and this mode is
    deliberately NOT the default, because whether the split lands depends on where in the quantum
    the run started. It is the nondeterminism, modelled faithfully -- so expect it to reproduce
    intermittently, and never build a gate on it.
    """

    def __init__(self, quantum_ns: int, *, anchor: str = OBSERVED_ANCHOR) -> None:
        if quantum_ns < 1:
            raise ValueError("a birth quantum must be at least one nanosecond")
        if anchor not in ANCHORS:
            raise ValueError(f"anchor must be one of {ANCHORS}, got {anchor!r}")
        self.quantum_ns = quantum_ns
        self.anchor = anchor
        self.anchor_ns: int | None = None
        self.observations = 0
        self.anchor_resets = 0

    def reset(self) -> None:
        """Drop the anchor so the next observed birth value defines a fresh grid."""
        self.anchor_ns = None
        self.anchor_resets += 1

    def coarsen(self, value_ns: int) -> int:
        self.observations += 1
        if self.anchor == EPOCH_ANCHOR:
            return (value_ns // self.quantum_ns) * self.quantum_ns
        if self.anchor_ns is None:
            self.anchor_ns = value_ns
        offset = value_ns - self.anchor_ns
        if offset < 0:
            # Clamp up. Rounding an older object DOWN would make it look strictly older than a
            # probe taken now, which is exactly the proof of settlement this lever exists to
            # withhold.
            return self.anchor_ns
        return self.anchor_ns + (offset // self.quantum_ns) * self.quantum_ns


def _coarse_birth_identity(real: Callable[..., Any], grid: QuantumGrid) -> Callable[..., Any]:
    """Force `install_skill_bundle.stat_birth_identity`, preserving its platform spelling.

    Linux spells the witness `<tv_sec>.<tv_nsec>`; the Darwin and Windows branches spell it as an
    integer nanosecond count. Both are kept exactly as the real seam produces them (unpadded, the
    way the product formats them), because the product compares whole witness strings.
    """

    @functools.wraps(real)
    def forced(path: Path, *, follow_symlinks: bool = True) -> str | None:
        value = real(path, follow_symlinks=follow_symlinks)
        if value is None:
            return None
        seconds, separator, fraction = value.partition(".")
        try:
            total = int(seconds) * 10**9 + int(fraction or 0) if separator else int(seconds)
        except ValueError:
            # A spelling this lever does not understand is passed through untouched rather than
            # silently replaced with a fabricated one.
            return value
        coarse = grid.coarsen(total)
        if separator:
            return f"{coarse // 10**9}.{coarse % 10**9}"
        return str(coarse)

    return forced


class _ForcedBtime:
    def __init__(self, seconds: int, nanoseconds: int) -> None:
        self.tv_sec = seconds
        self.tv_nsec = nanoseconds


class _ForcedStatx:
    """A `statx` result with a forced `stx_btime`; every other field is the real one."""

    def __init__(self, source: Any, btime: _ForcedBtime) -> None:
        self._source = source
        self.stx_btime = btime

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)


def _coarse_linux_statx(real: Callable[..., Any], grid: QuantumGrid) -> Callable[..., Any]:
    """Force `install_research_os._linux_statx`, which is that installer's only btime source."""

    @functools.wraps(real)
    def forced(path: bytes, *, descriptor: int = -100, flags: int = 0) -> Any:
        result = real(path, descriptor=descriptor, flags=flags)
        if result is None:
            return None
        total = result.stx_btime.tv_sec * 10**9 + result.stx_btime.tv_nsec
        coarse = grid.coarsen(total)
        return _ForcedStatx(result, _ForcedBtime(coarse // 10**9, coarse % 10**9))

    return forced


_SEAMS: tuple[tuple[Path, str, Callable[..., Any]], ...] = (
    (BUNDLE_INSTALLER, BUNDLE_SEAM, _coarse_birth_identity),
    (RESEARCH_OS_INSTALLER, RESEARCH_OS_SEAM, _coarse_linux_statx),
)


def loaded_seams() -> list[tuple[Any, str, Callable[..., Any]]]:
    """Every already-imported copy of a product module that owns a birth-timestamp seam."""
    found: dict[int, tuple[Any, str, Callable[..., Any]]] = {}
    for module in list(sys.modules.values()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        try:
            resolved = Path(origin).resolve()
        except OSError:
            continue
        for script, attribute, factory in _SEAMS:
            if resolved == script and hasattr(module, attribute):
                found[id(module)] = (module, attribute, factory)
    return list(found.values())


def _prove_collapse(module: Any, attribute: str, *, attempts: int = 1) -> str:
    """Positive control: two objects created back to back must now share one witness.

    A lever that silently does nothing is the same failure mode that let this class of defect
    ship, so the forced clock proves itself through the patched seam before any test runs.

    `attempts` exists for the `epoch` anchor only, where two probes microseconds apart can
    legitimately straddle an absolute grid line. Retrying the PROBE is honest; a retry that never
    collapses still refuses.
    """
    last: RuntimeError | None = None
    for _ in range(max(1, attempts)):
        try:
            return _probe_collapse_once(module, attribute)
        except RuntimeError as error:
            last = error
    assert last is not None
    raise last


def _probe_collapse_once(module: Any, attribute: str) -> str:
    with tempfile.TemporaryDirectory(prefix="coarse-birth-probe-") as directory:
        root = Path(directory)
        first = root / "first"
        second = root / "second"
        first.write_bytes(b"")
        second.write_bytes(b"")
        seam = getattr(module, attribute)
        if attribute == BUNDLE_SEAM:
            witnesses = (seam(first), seam(second))
        else:
            results = (seam(os.fsencode(first)), seam(os.fsencode(second)))
            if any(result is None for result in results):
                raise RuntimeError(
                    f"{module.__name__}.{attribute} reported no birth timestamp for a file it "
                    "just created; this host cannot host a birth-witness reproduction"
                )
            witnesses = tuple(
                f"{result.stx_btime.tv_sec}.{result.stx_btime.tv_nsec}" for result in results
            )
        if witnesses[0] is None or witnesses[0] != witnesses[1]:
            raise RuntimeError(
                f"forced coarse clock did not collapse two back-to-back creates through "
                f"{module.__name__}.{attribute}: {witnesses[0]!r} != {witnesses[1]!r}"
            )
        return str(witnesses[0])


class ForcedClock:
    """What one forced-clock scope actually patched, for reporting and for anchor resets."""

    def __init__(self, quantum_seconds: float, grid: QuantumGrid, seams: list[str]) -> None:
        self.quantum_seconds = quantum_seconds
        self.grid = grid
        self.seams = seams
        self.proofs: dict[str, str] = {}


@contextlib.contextmanager
def forced_coarse_birth_clock(
    quantum_seconds: float = DEFAULT_QUANTUM_SECONDS,
    *,
    require_seam: bool = True,
    anchor: str = OBSERVED_ANCHOR,
) -> Iterator[ForcedClock]:
    """Force every already-loaded installer's birth clock onto a `quantum_seconds` grid.

    The seam is patched on the module object the test already imported, so this must be entered
    AFTER the test modules are loaded. `require_seam=False` allows a target that imports neither
    installer -- useful for asking whether an unrelated failure is clock-sensitive at all.
    `anchor` selects the grid origin; see `QuantumGrid` for why `observed` is the default and
    `epoch` is the deliberately intermittent one.
    """
    grid = QuantumGrid(max(1, int(quantum_seconds * 10**9)), anchor=anchor)
    with contextlib.ExitStack() as stack:
        seams = loaded_seams()
        names = [f"{module.__name__}.{attribute}" for module, attribute, _ in seams]
        if not seams and require_seam:
            raise RuntimeError(
                "no birth-timestamp seam is loaded, so this run would force nothing. Load a test "
                f"module that imports {BUNDLE_INSTALLER.name} or {RESEARCH_OS_INSTALLER.name}, or "
                "pass --allow-unpatched to run an unrelated target under a clock that is not "
                "actually forced."
            )
        for module, attribute, factory in seams:
            stack.enter_context(
                mock.patch.object(module, attribute, factory(getattr(module, attribute), grid))
            )
        clock = ForcedClock(quantum_seconds, grid, names)
        attempts = 5 if grid.anchor == EPOCH_ANCHOR else 1
        for module, attribute, _ in seams:
            clock.proofs[f"{module.__name__}.{attribute}"] = _prove_collapse(
                module, attribute, attempts=attempts
            )
        grid.reset()
        yield clock


class _ReAnchoringResult(unittest.TextTestResult):
    """Re-anchor the quantum grid before each test, so no test inherits another's grid."""

    def __init__(self, *args: Any, grid: QuantumGrid, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._grid = grid

    def startTest(self, test: unittest.TestCase) -> None:
        self._grid.reset()
        super().startTest(test)


def build_suite(targets: list[str]) -> unittest.TestSuite:
    """Load a suite from unittest names, or the whole `tests/` tree for `discover`.

    Loading happens BEFORE the clock is forced, which is required: loading is what imports the
    installers whose seams are then patched.
    """
    loader = unittest.TestLoader()
    if len(targets) == 1 and targets[0] == "discover":
        return loader.discover(str(TESTS_ROOT), top_level_dir=str(TESTS_ROOT))
    return loader.loadTestsFromNames(targets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coarse_birth_clock.py",
        description=(
            "Run a test target with the installers' birth-timestamp clock forced coarse, so the "
            "settlement deferral path a fine-grained development host never reaches is exercised "
            "and provable here."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="TARGET",
        help="unittest names (module, module.Class, module.Class.method), or 'discover'",
    )
    parser.add_argument(
        "--quantum",
        type=float,
        default=DEFAULT_QUANTUM_SECONDS,
        metavar="SECONDS",
        help=(
            "forced birth-timestamp granularity (default: %(default)s). Coarser collapses more "
            "witnesses but every deferred wait then costs up to one quantum of wall clock."
        ),
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument(
        "--anchor",
        choices=ANCHORS,
        default=OBSERVED_ANCHOR,
        help=(
            "grid origin (default: %(default)s). 'observed' anchors to a real birth value and is "
            "deterministic. 'epoch' floors to an absolute grid, the way a filesystem stamping on a "
            "clock tick does, which is the only mode that can report a birth value earlier than a "
            "wall-clock reading taken before the object existed -- and is therefore intermittent "
            "by construction. Use it to expose wall-clock-anchored harness code, never as a gate."
        ),
    )
    parser.add_argument(
        "--allow-unpatched",
        action="store_true",
        help="run even when the target imports neither installer, forcing nothing",
    )
    parser.add_argument(
        "-f", "--failfast", action="store_true", help="stop at the first failure"
    )
    arguments = parser.parse_args(argv)
    if arguments.quantum <= 0:
        parser.error("--quantum must be positive")

    if str(TESTS_ROOT) not in sys.path:
        sys.path.insert(0, str(TESTS_ROOT))
    suite = build_suite(arguments.targets)
    with forced_coarse_birth_clock(
        arguments.quantum,
        require_seam=not arguments.allow_unpatched,
        anchor=arguments.anchor,
    ) as clock:
        print(
            f"coarse-birth-clock: quantum={clock.quantum_seconds:g}s "
            f"anchor={clock.grid.anchor} "
            f"seams={', '.join(clock.seams) or 'NONE (unforced)'}",
            file=sys.stderr,
        )
        for name, witness in clock.proofs.items():
            print(
                f"coarse-birth-clock: collapse proved through {name} at witness {witness}",
                file=sys.stderr,
            )
        sys.stderr.flush()
        runner = unittest.TextTestRunner(
            verbosity=1 + arguments.verbose,
            failfast=arguments.failfast,
            resultclass=functools.partial(_ReAnchoringResult, grid=clock.grid),
        )
        result = runner.run(suite)
        print(
            f"coarse-birth-clock: {clock.grid.observations} forced witnesses across "
            f"{clock.grid.anchor_resets} anchors",
            file=sys.stderr,
        )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
