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
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "agentic-sdlc/pass-budget-state@1"

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


def slugify(goal: str) -> str:
    slug = _SLUG_RUN.sub("-", goal.lower()).strip("-")[:48]
    return slug or "mission"


def mission_path(target: Path, slug: str) -> Path:
    return target / ".sdlc" / f"mission-{slug}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(target: Path, slug: str, goal: str) -> dict[str, Any]:
    path = mission_path(target, slug)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "schema": SCHEMA,
        "goal": goal,
        "slug": slug,
        "passes": {phase: 0 for phase in PASS_BUDGETS},
        "history": [],
        "stop_reason": "running",
    }


def _write_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def charge_pass(target: Path, state: dict[str, Any], phase: str) -> dict[str, Any]:
    """Increment ``phase`` and ``global``, persist, then report allow/refuse.

    The increment and the write happen unconditionally, before this function can
    tell the caller whether the pass is allowed — matching the ported source's
    "count-then-refuse" order: an exhausted budget is discovered only after the
    attempt has already been charged and saved, never pre-checked and skipped.
    """
    if phase not in PASS_BUDGETS or phase == "global":
        known = ", ".join(_KNOWN_PHASES)
        return {
            "allowed": False,
            "reason": f"unknown phase '{phase}'; known: {known}",
            "state": state,
        }
    next_state = {
        **state,
        "passes": dict(state.get("passes", {})),
        "history": list(state.get("history", [])),
    }
    next_state["passes"][phase] = next_state["passes"].get(phase, 0) + 1
    next_state["passes"]["global"] = next_state["passes"].get("global", 0) + 1
    phase_count = next_state["passes"][phase]
    global_count = next_state["passes"]["global"]
    next_state["history"].append({"at": _now(), "phase": phase, "count": phase_count})

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

    _write_atomic(mission_path(target, next_state["slug"]), next_state)
    return {"allowed": allowed, "reason": reason, "state": next_state}


def charge_command(target: Path, goal: str, phase: str) -> tuple[dict[str, Any], int]:
    slug = slugify(goal)
    state = load_state(target, slug, goal)
    result = charge_pass(target, state, phase)
    return result, (0 if result["allowed"] else 1)


def status_command(target: Path, goal: str) -> tuple[dict[str, Any], int]:
    slug = slugify(goal)
    state = load_state(target, slug, goal)
    return {
        "schema": SCHEMA,
        "goal": state.get("goal", goal),
        "slug": slug,
        "budgets": PASS_BUDGETS,
        "passes": state.get("passes", {}),
        "stop_reason": state.get("stop_reason", "running"),
    }, 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    charge = commands.add_parser("charge", help="charge one pass against a phase and the global budget")
    charge.add_argument("phase", help="phase name: " + ", ".join(_KNOWN_PHASES))
    charge.add_argument("--goal", required=True, help="mission goal text; identifies the ledger via its slug")
    charge.add_argument("--target", type=Path, required=True, help="target directory holding .sdlc/")

    status = commands.add_parser("status", help="print the current pass counts without charging one")
    status.add_argument("--goal", required=True)
    status.add_argument("--target", type=Path, required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "charge":
        result, code = charge_command(args.target, args.goal, args.phase)
        print(result["reason"])
    else:
        result, code = status_command(args.target, args.goal)
        print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
