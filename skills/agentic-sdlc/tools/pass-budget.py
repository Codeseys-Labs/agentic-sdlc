#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Conductor-owned mission pass-budget ledger.

The module deliberately does NOT enforce anything on a host, a worker, or a loop
runner: nothing here can stop a subagent from being dispatched, block a tool call,
or gate a merge. It is the conductor's own bookkeeping — a counted, persisted
ledger of how many times each mission phase (and the mission overall) has been
charged a pass, checked against the fixed budgets below. `charge` increments the
phase counter and the global counter and persists the result BEFORE returning, so
the write survives even when the returned answer is a refusal: the count-then-
refuse order matches the source doctrine this ports (a refused pass still spent
budget, because the attempt happened). A refusal returned by this tool is advice
the conductor must obey by choosing not to delegate further into that phase; it
is not a lock, a hook, and not something that can reach outside this process to
prevent a delegation that the conductor makes anyway.

Budgets (mirrors commands/sdlc-mission.md and pi-lab's sdlc-mission.ts
PASS_BUDGETS exactly): global 6; frame 1; discover 2; research 2; plan 2; act 3.

State lives at ``.sdlc/mission-<slug>.json`` under the target directory, one file
per mission goal. The slug is derived from the goal text (lowercase, non-alnum
runs collapsed to a single hyphen, trimmed, capped at 48 characters, falling back
to "mission" if that yields nothing) so repeated invocations for the same goal
share one ledger. Persistence is atomic: a temp file is written in the same
directory and then swapped into place with ``os.replace``, so a crash mid-write
cannot leave a torn or half-written ledger behind.

EVERY CHARGE IS KEYED, and that is what makes a retry safe. The count-then-refuse
order above means a caller that retried an ambiguous `charge` used to spend a
SECOND pass for one logical attempt, against both the phase budget and the global
budget — state corruption, not a misreport. So `charge` requires
``--attempt-id``: an id the caller chooses for the attempt it is charging for,
recorded in the ledger's ``charges`` map inside the same atomic write as the
increment it paid for. A charge whose id is already recorded writes NOTHING and
returns the recorded verdict verbatim, so a retry converges instead of
accumulating. A charge with an unrecorded id charges normally, so two genuinely
different attempts still cost two passes.

AN UNKEYED CHARGE IS REFUSED rather than accepted for compatibility. There is no
honest way to make one idempotent: with no id there is nothing for a retry to
match against, so accepting one would preserve the original defect for every
caller that did not opt in, and this ledger's only value is that its count is
true. Missing ``--attempt-id`` is therefore a grammar error (exit 2).

THE ORDER OF THE THREE STEPS IS THE SAFETY PROPERTY. The increment is
unconditional, the verdict is derived from the already-incremented counts, and
increment plus verdict plus attempt id land in ONE atomic write before the caller
is told anything. Nothing is pre-checked and skipped, so a crash between the
durable write and the caller seeing the answer still costs the pass — while the
retry that follows that crash converges on the recorded verdict, because the id
was written with the increment.

SCHEMA. This tool writes ``agentic-sdlc/pass-budget-state@2`` (the @1 shape plus
``charges``) and reads @1 as well, carrying its counts forward and keying every
later charge. Any other schema, and any ledger that is not readable JSON, is a
clean refusal: this tool never guesses at a document it does not recognise.

EXITS (Implementation Decision 9): 0 for a valid query or closed requested
result, 1 for an unexpected internal failure before any effect, 2 for a
grammar/schema/input error, 3 for a clean refusal before any effect, and 4 after
an admitted partial or unknown effect. Two consequences are worth spelling out.

First, a budget-exhausted verdict is exit 0. It is not a clean refusal (3),
because the doctrine above requires the increment to have landed first; it is not
a partial or unknown effect (4), because the charge completed exactly as asked.
It is the closed result of a completed operation, so the refusal rides in the
result — the ``REFUSED`` line on stdout, ``stop_reason`` in the ledger, and an
advisory line on stderr — and not in the exit code.

Second, effects are admitted where they HAPPEN, inside the writing primitive: the
temp file exists from its ``open`` onward, and the ledger has moved from the
instant ``os.replace`` returns. `_report_failure` is the one place any refusal's
code is settled, by reading that ledger, and no raise site may state an effect —
`BudgetError` has no effect parameter. So a raise asking for 3 after the write
still comes out 4.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "agentic-sdlc/pass-budget-state@2"
# @1 is the pre-idempotency shape: the same counters with no `charges` map.
READABLE_SCHEMAS = (SCHEMA, "agentic-sdlc/pass-budget-state@1")

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
EXIT_REFUSED = 3
EXIT_PARTIAL = 4

EFFECT_NONE = "none"
EFFECT_UNKNOWN = "effect_unknown"

PASS_BUDGETS: dict[str, int] = {
    "global": 6,
    "frame": 1,
    "discover": 2,
    "research": 2,
    "plan": 2,
    "act": 3,
}

_KNOWN_PHASES = [key for key in PASS_BUDGETS if key != "global"]
_SLUG_RUN = re.compile(r"[^a-z0-9]+")
# Same shape as the wave journal's ids: something a caller can put in a filename, a log line, and
# a shell argument without quoting, bounded so one cannot bloat the ledger by itself.
_ATTEMPT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

# One bounded test seam. It can only make this tool FAIL at a named point; it cannot skip a check,
# widen authority, or write anything the ordinary path would not have written. It exists because
# the effect-admission rule is worth nothing unless a failure AFTER the durable write can actually
# be driven, and no mock reaches a subprocess.
FAULT_ENV = "AGENTIC_SDLC_PASS_BUDGET_FAULT"
FAULT_POINTS = ("before-write", "after-write")


class BudgetError(Exception):
    """A refusal or failure of this tool. `code` is required; the effect is NEVER a parameter.

    A raise site states what went wrong and how severe the CAUSE is. What it may not state is what
    already happened on disk, because that is what the site cannot know. `_report_failure` derives
    the effect from the ledger instead.
    """

    def __init__(self, status: str, reason: str, code: int) -> None:
        super().__init__(reason)
        self.status, self.reason, self.code = status, reason, code


class _Effects:
    """What THIS invocation has already done, so no refusal can be reported as no effect.

    Decision 9 separates "I refused before touching anything" (3) from "something happened and the
    result is partial or unknown" (4). Those are indistinguishable to an operator unless the tool
    tracks its own effects, so it records each one and escalates any later refusal.
    """

    def __init__(self) -> None:
        self.admitted: list[str] = []

    def admit(self, effect: str) -> int:
        """Record an effect at the moment it happens; the token allows only re-describing it."""
        self.admitted.append(effect)
        return len(self.admitted) - 1

    def revise(self, token: int, effect: str) -> None:
        """Sharpen an admitted effect's description. It can be re-described, never withdrawn."""
        self.admitted[token] = effect

    def any(self) -> bool:
        return bool(self.admitted)


_EFFECTS = _Effects()


@contextlib.contextmanager
def _effect_ledger() -> Iterator[_Effects]:
    """Install one fresh ledger for one command invocation, then restore the previous one.

    Module-scoped rather than threaded through every helper, because the effects are admitted
    frames below the handler that classifies them, and a parameter is exactly the bookkeeping a
    future helper forgets. Restoring rather than clearing keeps a test that drives two commands in
    one process from erasing the outer command's admitted effects.
    """
    global _EFFECTS
    previous = _EFFECTS
    _EFFECTS = _Effects()
    try:
        yield _EFFECTS
    finally:
        _EFFECTS = previous


def _admit(effect: str) -> int:
    return _EFFECTS.admit(effect)


def _revise(token: int, effect: str) -> None:
    _EFFECTS.revise(token, effect)


def _fault_request() -> tuple[str, int] | None:
    """Parse and validate the seam once, so an unrecognised request refuses instead of hiding."""
    raw = os.environ.get(FAULT_ENV)
    if not raw:
        return None
    name, _, requested = raw.partition(":")
    if name not in FAULT_POINTS:
        raise BudgetError("invalid", f"unknown fault point {name!r}; known: {', '.join(FAULT_POINTS)}", EXIT_INPUT)
    if not requested:
        return name, EXIT_INTERNAL
    if requested not in {"0", "1", "2", "3", "4"}:
        raise BudgetError("invalid", f"fault code {requested!r} is outside this tool's exit set 0-4", EXIT_INPUT)
    return name, int(requested)


def _fault(point: str) -> None:
    """Fail at `point` when the environment names it, as `<point>` or `<point>:<code>`.

    The requested code is what proves the escalation is real: a site asking for 3 (a clean refusal)
    after the durable write must still come out as 4, and the same request before it must come out
    unchanged. One mechanism, both directions.
    """
    request = _fault_request()
    if request is None:
        return
    name, code = request
    if name != point:
        return
    raise BudgetError("injected-fault", f"injected fault at {point}", code)


def slugify(goal: str) -> str:
    slug = _SLUG_RUN.sub("-", goal.lower()).strip("-")[:48]
    return slug or "mission"


def mission_path(target: Path, slug: str) -> Path:
    return target / ".sdlc" / f"mission-{slug}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(target: Path, slug: str, goal: str) -> dict[str, Any]:
    """Read the ledger, or return a fresh one. An unrecognised document is a clean refusal."""
    path = mission_path(target, slug)
    if not path.exists():
        return {
            "schema": SCHEMA,
            "goal": goal,
            "slug": slug,
            "passes": {phase: 0 for phase in PASS_BUDGETS},
            "charges": {},
            "history": [],
            "stop_reason": "running",
        }
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BudgetError("refused", f"cannot read the ledger at {path}: {exc}", EXIT_REFUSED) from exc
    try:
        state = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BudgetError("refused", f"the ledger at {path} is not readable JSON: {exc}", EXIT_REFUSED) from exc
    if not isinstance(state, dict):
        raise BudgetError("refused", f"the ledger at {path} is not a JSON object", EXIT_REFUSED)
    schema = state.get("schema")
    if schema not in READABLE_SCHEMAS:
        raise BudgetError(
            "refused",
            f"the ledger at {path} carries schema {schema!r}; this tool reads {' and '.join(READABLE_SCHEMAS)}",
            EXIT_REFUSED,
        )
    if not isinstance(state.get("passes"), dict):
        raise BudgetError("refused", f"the ledger at {path} has no readable `passes` map", EXIT_REFUSED)
    charges = state.setdefault("charges", {})
    if not isinstance(charges, dict):
        raise BudgetError("refused", f"the ledger at {path} has an unreadable `charges` map", EXIT_REFUSED)
    # In memory only: nothing is written here, so a read never rewrites a caller's file. The @2
    # schema string reaches disk on the next charge, together with that charge's own record.
    state["schema"] = SCHEMA
    return state


def _write_atomic(path: Path, state: dict[str, Any]) -> None:
    """Swap the ledger into place, admitting each effect at the instant it happens.

    The temp file exists from its `open` onward, so admitting it after the write completes would
    classify the created-but-unwritten case as though nothing had happened. The ledger has moved
    from the instant `os.replace` returns, so the admission is revised there and not later.
    """
    parent = path.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BudgetError("refused", f"cannot create the ledger directory {parent}: {exc}", EXIT_REFUSED) from exc
        _admit(f"created the ledger directory {parent}")
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        handle = temp.open("w", encoding="utf-8")
    except OSError as exc:
        raise BudgetError("refused", f"cannot open a temp ledger beside {path}: {exc}", EXIT_REFUSED) from exc
    token = _admit(f"a partial ledger file exists at {temp} and is not the ledger")
    try:
        with handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        raise BudgetError("refused", f"cannot write the ledger at {path}: {exc}", EXIT_REFUSED) from exc
    _revise(token, f"the ledger at {path} now carries this charge")


def _check_attempt_id(attempt_id: Any) -> str:
    if not isinstance(attempt_id, str) or not _ATTEMPT_ID.match(attempt_id):
        raise BudgetError(
            "invalid",
            f"attempt id {attempt_id!r} must match {_ATTEMPT_ID.pattern}: it names one logical attempt, "
            "and a retry carrying the same id converges on that attempt's recorded charge",
            EXIT_INPUT,
        )
    return attempt_id


def _recorded(state: dict[str, Any], attempt_id: str, phase: str) -> dict[str, Any] | None:
    """The prior charge for `attempt_id`, or None. A conflicting reuse refuses before any effect."""
    prior = state.get("charges", {}).get(attempt_id)
    if prior is None:
        return None
    if not isinstance(prior, dict) or not isinstance(prior.get("reason"), str) or "allowed" not in prior:
        raise BudgetError(
            "refused",
            f"the recorded charge for attempt id '{attempt_id}' is unreadable, so this retry cannot converge on it",
            EXIT_REFUSED,
        )
    if prior.get("phase") != phase:
        raise BudgetError(
            "refused",
            f"attempt id '{attempt_id}' already charged phase '{prior.get('phase')}' and may not be reused for "
            f"'{phase}': one id names one attempt, and reusing it would either hide a charge or invent one",
            EXIT_REFUSED,
        )
    return prior


def charge_pass(target: Path, state: dict[str, Any], phase: str, attempt_id: str) -> dict[str, Any]:
    """Increment ``phase`` and ``global``, persist with the attempt id, then report allow/refuse.

    The increment and the write happen unconditionally, before this function can tell the caller
    whether the pass is allowed — matching the ported source's "count-then-refuse" order: an
    exhausted budget is discovered only after the attempt has already been charged and saved, never
    pre-checked and skipped.

    What is NOT unconditional is charging the same attempt twice. `attempt_id` is written into the
    ledger inside the same atomic write as the increment it paid for, so a retry carrying that id
    finds the recorded verdict and returns it with no write at all.
    """
    _check_attempt_id(attempt_id)
    if phase not in PASS_BUDGETS or phase == "global":
        known = ", ".join(_KNOWN_PHASES)
        raise BudgetError("invalid", f"unknown phase '{phase}'; known: {known}", EXIT_INPUT)
    prior = _recorded(state, attempt_id, phase)
    if prior is not None:
        return {
            "allowed": bool(prior["allowed"]),
            "reason": prior["reason"],
            "state": state,
            "converged": True,
        }

    next_state = {
        **state,
        "passes": dict(state.get("passes", {})),
        "charges": dict(state.get("charges", {})),
        "history": list(state.get("history", [])),
    }
    next_state["passes"][phase] = next_state["passes"].get(phase, 0) + 1
    next_state["passes"]["global"] = next_state["passes"].get("global", 0) + 1
    phase_count = next_state["passes"][phase]
    global_count = next_state["passes"]["global"]
    at = _now()
    next_state["history"].append({"at": at, "phase": phase, "count": phase_count, "attempt_id": attempt_id})

    allowed = True
    reason = f"pass {phase_count}/{PASS_BUDGETS[phase]} for {phase}; global {global_count}/{PASS_BUDGETS['global']}"
    if phase_count > PASS_BUDGETS[phase]:
        allowed = False
        next_state["stop_reason"] = "bound-tripped"
        reason = (
            f"REFUSED: {phase} budget {PASS_BUDGETS[phase]} exhausted (this would be pass "
            f"{phase_count}). This is a refusal, not a completion. Resume by raising the "
            "budget deliberately or closing blockers."
        )
    elif global_count > PASS_BUDGETS["global"]:
        allowed = False
        next_state["stop_reason"] = "bound-tripped"
        reason = f"REFUSED: global budget {PASS_BUDGETS['global']} exhausted. Name the blockers; do not claim done."

    # The verdict is recorded with the charge it belongs to. A retry must converge on the SAME
    # answer, and an answer derived again later could differ from the one this caller lost.
    next_state["charges"][attempt_id] = {
        "at": at,
        "phase": phase,
        "allowed": allowed,
        "reason": reason,
        "phase_count": phase_count,
        "global_count": global_count,
    }

    _fault("before-write")
    _write_atomic(mission_path(target, next_state["slug"]), next_state)
    _fault("after-write")
    return {"allowed": allowed, "reason": reason, "state": next_state, "converged": False}


def charge_command(target: Path, goal: str, phase: str, attempt_id: str) -> tuple[dict[str, Any], int]:
    """Charge one pass. The exit code reports the OPERATION; the verdict rides in the result.

    A budget-exhausted charge completed exactly what was asked of it, so it is exit 0 with
    ``allowed`` false — never a clean pre-effect refusal, which is what an increment already on
    disk would make a lie.
    """
    slug = slugify(goal)
    state = load_state(target, slug, goal)
    return charge_pass(target, state, phase, attempt_id), EXIT_OK


def status_command(target: Path, goal: str) -> tuple[dict[str, Any], int]:
    slug = slugify(goal)
    state = load_state(target, slug, goal)
    return {
        "schema": SCHEMA,
        "goal": state.get("goal", goal),
        "slug": slug,
        "budgets": PASS_BUDGETS,
        "passes": state.get("passes", {}),
        "charges": len(state.get("charges", {})),
        "stop_reason": state.get("stop_reason", "running"),
    }, EXIT_OK


def _report_failure(exc: BudgetError) -> tuple[str, str, int]:
    """THE single choke point: every refusal's code is DERIVED here, from the effect ledger.

    1. THE LEDGER IS THE FLOOR. Once this invocation has admitted any effect, no refusal may exit
       as a clean pre-effect refusal (3), a pre-effect internal failure (1), or an input verdict
       (2), because on disk the result is partial or unknown. 4 is the only honest answer.
    2. A RAISE SITE MAY ONLY ESCALATE. A site asking for 4 reports an unknown effect this
       invocation merely observed; what it cannot do is claim `none` over something that happened,
       and that direction is unreachable because the effect is not a parameter of any raise.
    """
    status, code, effect = exc.status, exc.code, EFFECT_NONE
    if _EFFECTS.any():
        status, code, effect = "effect-unknown", EXIT_PARTIAL, EFFECT_UNKNOWN
    elif code == EXIT_PARTIAL:
        effect = EFFECT_UNKNOWN
    return status, effect, code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Conductor-owned mission pass-budget ledger.")
    commands = parser.add_subparsers(dest="command", required=True)

    charge = commands.add_parser("charge", help="charge one pass against a phase and the global budget")
    charge.add_argument("phase", help="phase name: " + ", ".join(_KNOWN_PHASES))
    charge.add_argument("--goal", required=True, help="mission goal text; identifies the ledger via its slug")
    charge.add_argument("--target", type=Path, required=True, help="target directory holding .sdlc/")
    charge.add_argument(
        "--attempt-id",
        required=True,
        help="id of the logical attempt being charged; a retry carrying the same id converges on "
        "its recorded charge instead of spending a second pass",
    )

    status = commands.add_parser("status", help="print the current pass counts without charging one")
    status.add_argument("--goal", required=True)
    status.add_argument("--target", type=Path, required=True)

    return parser.parse_args(argv)


def _note(line: str) -> None:
    """Write one advisory line to stderr. Display only: losing it changes no verdict."""
    stream = sys.stderr
    if stream is None:
        return
    with contextlib.suppress(OSError, ValueError):
        stream.write(line)
        stream.flush()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    with _effect_ledger():
        try:
            _fault_request()  # validate the seam for every verb, before anything can happen
            if args.command == "charge":
                result, code = charge_command(args.target, args.goal, args.phase, args.attempt_id)
                print(result["reason"])
                if result["converged"]:
                    _note(f"pass-budget.py: converged on the charge already recorded for attempt '{args.attempt_id}'\n")
                if not result["allowed"]:
                    # Exit 0 carries a completed charge, so the refusal has to be loud somewhere
                    # a human looks. It is advice either way: this tool stops nothing.
                    _note(f"pass-budget.py: {result['reason']}\n")
            else:
                result, code = status_command(args.target, args.goal)
                print(json.dumps(result, indent=2, sort_keys=True))
            return code
        except BudgetError as exc:
            status, _effect, code = _report_failure(exc)
            reason = exc.reason
        except Exception as exc:  # an unexpected failure must still classify its own effects
            status, _effect, code = _report_failure(
                BudgetError("internal", f"unexpected {type(exc).__name__}: {exc}", EXIT_INTERNAL)
            )
            reason = f"unexpected {type(exc).__name__}: {exc}"
        _note(f"pass-budget.py: {status}: {reason}\n")
        if _EFFECTS.any():
            _note("pass-budget.py: this is a PARTIAL result, not a clean refusal:\n")
            for effect in _EFFECTS.admitted:
                _note(f"pass-budget.py:   already happened: {effect}\n")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
