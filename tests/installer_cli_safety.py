"""The one seam every test that drives `install_skill_bundle.main` goes through.

WHY THIS IS A MODULE AND NOT A RULE IN A DOCSTRING (`agentic-sdlc-8dca`). During wave W1 a test
called `installer.main(["uninstall"])` with no isolated homes. It was safe only because the code under
test refused before any effect -- and that wave's MUTATION run removed exactly that refusal, driving a
real `uninstall` pass across the operator's own `~/.claude` and `~/.codex`. Nothing was destroyed
(the real 44-entry ownership document was never written, so the removals were limited to paths the run
itself had created), but the failure mode is structural rather than incidental: mutation testing
DELETES guards by design, so any test whose safety rests on the product refusing first is one mutation
away from mutating the machine it runs on. A prose rule cannot survive that, because the prose is not
what the mutation removes. This module is the surviving half -- the refusal lives OUTSIDE the code
under test, so removing the product's guard cannot remove this one.

WHAT IT REFUSES. `run_cli` never reaches `main` until the argv it was handed resolves, through the
PRODUCT'S OWN parser and path normalisation, to homes and a state root that are all outside the
operator's real ones. The subject is the RESOLVED path rather than the argv shape, so an omitted
`--claude-home` (which resolves to the operator's own home), a home that contains or is contained by
the real home, an ambient `CODEX_HOME` the test never redirected, or an unredirected state root each
fail the calling test by name -- while a test that isolated the run by patching `HOME` instead of
passing the flag is admitted, because it did isolate it. The verdict is a test failure, not a skip: a
test that cannot be run safely has not passed.

WHAT IT DOES NOT DO. It has no opinion about which exit code or message is correct -- that is the
caller's assertion, and keeping it there is what stops this guard from becoming a second copy of the
product's contract. In particular it knows nothing about
`install_skill_bundle.CLAUDE_HOME_INSIDE_PROJECT`: that refusal is the PRODUCT's, about a home inside a
git project, and a fixture home planted inside a fixture git repository is a legitimate thing to drive
through here. The two refusals are separate facts with separate names, and
`GUARD_REFUSAL` is deliberately unlike the product's token so a report can never confuse them.

WHERE THE REAL HOME COMES FROM. Snapshotted at IMPORT, before any test patches `HOME`, `CODEX_HOME`,
`XDG_STATE_HOME`, or `LOCALAPPDATA`. A guard that read those at call time would be told by the very
patch it exists to police that the operator's home is a fixture.
"""

from __future__ import annotations

import contextlib
import io
import os
import unittest
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The named reason this guard blocks a run. Distinct by construction from every refusal the product
#: declares -- `CLAUDE_HOME_INSIDE_PROJECT` above all -- because the two answer different questions:
#: this one is "the TEST did not isolate", that one is "the OPERATOR aimed the user plane at a repo".
GUARD_REFUSAL = "operator-home-not-isolated"

#: Snapshotted before any test can patch the environment. `os.path.expanduser` is the same resolution
#: `Path.home()` performs, and it is read exactly once, here.
REAL_HOME = Path(os.path.abspath(os.path.expanduser("~")))
_real_codex_home = os.environ.get("CODEX_HOME")
REAL_CODEX_HOME = Path(os.path.abspath(_real_codex_home)) if _real_codex_home else REAL_HOME / ".codex"
#: The roots a state document must not land in. `REAL_HOME` is always one of them, which covers every
#: home-derived default `state_directory` can pick on either platform without this module having to
#: restate that derivation; an explicitly SET `XDG_STATE_HOME` or `LOCALAPPDATA` is added because it
#: may point outside the home entirely. Both platform spellings are read on every platform, so a test
#: that redirects only the one this host consults does not look isolated here and unisolated elsewhere.
REAL_STATE_ROOTS: tuple[Path, ...] = (
    REAL_HOME,
    *(
        Path(os.path.abspath(value))
        for value in (os.environ.get("XDG_STATE_HOME"), os.environ.get("LOCALAPPDATA"))
        if value
    ),
)


@dataclass(frozen=True)
class CliRun:
    """One completed guarded CLI run: what it returned and what it said."""

    exit_code: int
    stdout: str
    stderr: str


def _overlaps(candidate: Path, protected: Path) -> bool:
    """Whether the two paths are the same tree or one encloses the other.

    BOTH directions, because both are unsafe for different reasons: a home INSIDE the operator's home
    is a run pointed at their real configuration, and a home CONTAINING it is a run whose removals
    would walk down into it. Lexical and case-normalised, matching how the product compares roots.
    """
    left = os.path.normcase(os.path.abspath(candidate))
    right = os.path.normcase(os.path.abspath(protected))
    if left == right:
        return True
    return left.startswith(right.rstrip(os.sep) + os.sep) or right.startswith(left.rstrip(os.sep) + os.sep)


def _codex_home_request(parsed: Any, home: Path) -> Path:
    """The Codex root `main` would select for this parse, before it judges the value.

    This mirrors `main`'s three branches on purpose, and the mirroring is the guard's job rather than a
    duplicated contract: predicting where the run WILL write is the only way to answer whether it is
    isolated, and a guard that predicted something else would either refuse safe runs or admit unsafe
    ones. The blank-`CODEX_HOME` branch matters most -- demanding an explicit `--codex-home` flag
    instead would make the product's own empty-value refusal impossible to drive from a test, so a
    blank value is followed to the same `<home>/.codex` fallback `main` reaches once that refusal is
    mutated away, which is precisely the state this guard must judge.
    """
    if parsed.codex_home is not None:
        return Path(parsed.codex_home)
    ambient = os.environ.get("CODEX_HOME")
    if ambient and ambient.strip():
        return Path(ambient)
    return home / ".codex"


def _refuse(test: unittest.TestCase, detail: str) -> None:
    test.fail(
        f"{GUARD_REFUSAL}: {detail}. A test that invokes the installer CLI must supply isolated"
        " --claude-home, --codex-home, and state roots, because the product's own refusal is what a"
        " mutation run deletes (agentic-sdlc-8dca)."
    )


def run_cli(
    test: unittest.TestCase,
    installer: Any,
    argv: Sequence[str],
    *,
    must_stay_empty: Path | None = None,
) -> CliRun:
    """Invoke `installer.main(argv)` only if this argv cannot reach the operator's own state.

    `must_stay_empty` is the independent positive control, and it is deliberately a SEPARATE assertion
    from whatever the caller checks about the exit code: "the run refused" and "the run touched
    nothing" are two claims, and a single combined assertion would let either one carry the other. The
    named root must hold no entries once the run returns -- so it is the sandbox the isolated homes are
    children of, passed only by callers whose run is supposed to have no effect at all.
    """
    arguments = list(argv)
    parsed = installer.parse_args(arguments)

    # The RESOLVED path is the subject, never the argv shape: an omitted `--claude-home` resolves to
    # the operator's own home and is caught below, while a test that redirected `HOME` to a fixture has
    # genuinely isolated the run and must not be refused for spelling it that way.
    home = installer.operational_path(parsed.claude_home)
    if _overlaps(home, REAL_HOME):
        _refuse(
            test,
            f"the resolved Claude home {home} overlaps the operator's real home {REAL_HOME}; argv was"
            f" {arguments}",
        )

    codex_home = installer.operational_path(_codex_home_request(parsed, home))
    if _overlaps(codex_home, REAL_HOME) or _overlaps(codex_home, REAL_CODEX_HOME):
        _refuse(
            test,
            f"the resolved Codex home {codex_home} overlaps the operator's real {REAL_CODEX_HOME};"
            f" argv was {arguments}",
        )

    # The product's own answer, so a redirection the test performed by any supported means counts and
    # this guard needs no second copy of the state-root rule.
    state_root = installer.state_directory()
    for protected in REAL_STATE_ROOTS:
        if _overlaps(state_root, protected):
            _refuse(
                test,
                f"the resolved state root {state_root} overlaps the operator's real {protected}, so the"
                " run would read or write their ownership document",
            )

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        exit_code = installer.main(arguments)
    run = CliRun(exit_code, out.getvalue(), err.getvalue())

    if must_stay_empty is not None:
        test.assertEqual(
            sorted(path.name for path in must_stay_empty.iterdir()),
            [],
            f"the guarded run created state under {must_stay_empty}",
        )
    return run
