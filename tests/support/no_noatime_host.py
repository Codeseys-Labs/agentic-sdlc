#!/usr/bin/env python3
"""Run any test target on a host that cannot read a file without updating its access time.

WHY THIS FILE EXISTS
--------------------
`skills/agentic-sdlc/tools/git_project_detector.py` reads every byte of `.git` metadata through
`read_without_atime`, which requires `os.O_NOATIME` and raises `MetadataUnreadable(NO_ATIME)` rather
than retrying without it. That flag is LINUX-ONLY: `os` carries no `O_NOATIME` attribute on Darwin or
on native Windows. So on those two hosts the whole reader answers its documented fail-direction --
`admit` refuses every root as `invalid-git-metadata`, `observe_dirty` answers `True`, and
`observe_commit` answers `unknown` -- for a repository that is in perfect health.

That is the product's decision and this runner does not argue with it. What it fixes is that the
decision was UNREACHABLE from a Linux development host: the flag is always present here, so every
consumer took the admitting branch, no local run could see the refusing one, and the fail-direction
was defended only by prose. Fourteen of the seventeen macOS failures and two of the sixteen Windows
failures on main@818bf09 were one instance of that gap (seed context `ci-red-818bf09`): twelve
project-scope, doctor, and dirtiness tests asserted the admitting branch unconditionally, and a
six-minute cross-platform CI round trip was the only surface that ran the other one.

Forcing the flag away here reproduces those failures on Linux in seconds, and the same command
proves the skip predicates that now guard them: a test declared `skipUnless(hasattr(os, "O_NOATIME"))`
must actually skip under this runner, not pass.

ORDER MATTERS, AND IT IS THE OPPOSITE OF `coarse_birth_clock.py`'s. That runner loads the suite
BEFORE forcing its seam, because loading is what imports the module it patches. This one forces
BEFORE loading, because a `skipUnless(hasattr(os, "O_NOATIME"), ...)` decorator is evaluated when the
test module is imported -- force it afterwards and every such class runs anyway, which is the one
outcome this lever exists to rule out.

WHAT IT DOES NOT MODEL. Darwin and Windows differ from Linux in more than this flag: Windows has no
`O_NOFOLLOW` and needs `O_BINARY`, and its paths are not POSIX-absolute. This runner forces exactly
the one condition that fires FIRST on both of them, so a green run here is evidence about this class
and not a claim of cross-platform equivalence.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path
import sys
from typing import Callable, Iterator, TypeVar
import unittest

_T = TypeVar("_T")

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"

#: The attribute every `read_without_atime` consumer probes at CALL time. Named once so the runner
#: and its own test agree on the subject rather than on two spellings of it.
FLAG = "O_NOATIME"

#: Why a suite that needs the reader's ADMITTING branch cannot run where the flag is absent, and how
#: to reach the other branch here. Exported so every such guard under `tests/` names ONE fact instead
#: of paraphrasing it per module, and so the skip and the runner that proves the skip stay paired: a
#: reader who hits this reason has the command that reproduces what it is standing in for.
SKIP_REASON = (
    "the git-project ladder reads .git metadata through read_without_atime, which requires the "
    f"Linux-only os.{FLAG} and refuses rather than retrying without it, so on this host no root "
    "admits, every tree reads dirty, and every commit reads unknown; reproduce that branch on Linux "
    "with tests/support/no_noatime_host.py"
)


def requires_noatime() -> Callable[[_T], _T]:
    """Skip the decorated test or class unless this host can read without updating an access time.

    Evaluated when the decorated module is IMPORTED, which is why `no_noatime_host.py` forces the flag
    away before it loads a suite rather than after.
    """
    return unittest.skipUnless(hasattr(os, FLAG), SKIP_REASON)


@contextlib.contextmanager
def forced_no_noatime(*, require_flag: bool = True) -> Iterator[int | None]:
    """Remove `os.O_NOATIME` for the duration, then restore exactly what was there.

    `require_flag` refuses a host that never had the flag: forcing nothing and reporting a pass would
    be a run that proved nothing about the branch it names.
    """
    present = hasattr(os, FLAG)
    if not present:
        if require_flag:
            raise SystemExit(
                f"refused: this host already has no os.{FLAG}, so there is nothing to force and a "
                "green run here would be evidence about the wrong branch; pass --allow-unforced to "
                "run anyway"
            )
        yield None
        return
    original = getattr(os, FLAG)
    delattr(os, FLAG)
    try:
        yield original
    finally:
        setattr(os, FLAG, original)


def build_suite(targets: list[str]) -> unittest.TestSuite:
    """Load a suite from unittest names, or the whole `tests/` tree for `discover`.

    Loading happens AFTER the flag is forced -- see this module's docstring for why the ordering is
    load-bearing rather than incidental.
    """
    loader = unittest.TestLoader()
    if len(targets) == 1 and targets[0] == "discover":
        return loader.discover(str(TESTS_ROOT), top_level_dir=str(TESTS_ROOT))
    return loader.loadTestsFromNames(targets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="no_noatime_host.py",
        description=(
            "Run a test target with os.O_NOATIME forced absent, so the atime-free metadata reader's "
            "refusing branch -- the whole of it on Darwin and native Windows -- is reachable and "
            "provable from a Linux host."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="unittest names (tests.test_x.Class.test_y), or the single word 'discover'",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument(
        "-f", "--failfast", action="store_true", help="stop at the first failure"
    )
    parser.add_argument(
        "--allow-unforced",
        action="store_true",
        help="run on a host that already lacks the flag, forcing nothing",
    )
    arguments = parser.parse_args(argv)

    # BOTH spellings resolve: `tests.test_x` (the gate's own, via the repository root) and a bare
    # `test_x` (`coarse_birth_clock.py`'s, via the tests directory), so a target copied from either
    # surface loads here rather than failing as an unknown module.
    for entry in (REPO_ROOT, TESTS_ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    with forced_no_noatime(require_flag=not arguments.allow_unforced) as original:
        print(
            f"no-noatime-host: os.{FLAG} "
            + (f"forced absent (was {original})" if original is not None else "absent already"),
            file=sys.stderr,
        )
        sys.stderr.flush()
        suite = build_suite(arguments.targets)
        runner = unittest.TextTestRunner(
            verbosity=1 + arguments.verbose, failfast=arguments.failfast
        )
        result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
