#!/usr/bin/env python3
"""PROTOTYPE TUI for the Agentic SDLC installation lifecycle."""

from __future__ import annotations

import os
import sys

from lifecycle_model import initial_state, reduce


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

ACTIONS = {
    "g": "quick",
    "c": "checkout",
    "v": "review",
    "t": "trust",
    "k": "tools",
    "d": "doctor",
    "i": "core",
    "r": "route",
    "p": "provider",
    "f": "profile",
    "u": "update",
    "h": "refresh",
    "b": "rollback",
    "x": "conflict",
    "1": "remove-route",
    "2": "remove-core",
    "3": "remove-dist",
    "s": "status",
    "a": "approve",
    "j": "reject",
}


def render(state: dict, *, clear_screen: bool = True) -> None:
    if clear_screen:
        os.system("clear" if os.name != "nt" else "cls")
    print(f"{BOLD}PROTOTYPE — ccodex sdlc lifecycle{RESET}")
    print(f"{DIM}No command changes the machine. Approval is simulated.{RESET}\n")
    fields = (
        ("distribution", f"{state['distribution']} {state['distribution_version'] or ''}".strip()),
        ("previous version", state["previous_version"] or "none"),
        ("reviewed / trusted", f"{state['source_reviewed']} / {state['mise_trusted']}"),
        ("toolchain / doctor", f"{state['toolchain_ready']} / {state['doctor']}"),
        ("Claude core", f"{state['core']} {state['core_version'] or ''}".strip()),
        ("ccodex routed profile", state["routed_profile"]),
        ("provider surface", state["providers"]),
        ("optional profile", state["optional_profile"]),
    )
    for name, value in fields:
        print(f"{BOLD}{name:24}{RESET} {value}")
    pending = state["pending"]
    print(f"\n{BOLD}pending approval{RESET}")
    if pending:
        print(f"  {pending['title']}\n  {DIM}{pending['effect']}{RESET}")
    else:
        print("  none")
    print(f"\n{BOLD}last result{RESET}\n  {state['last_result']}")
    print(f"\n{BOLD}recent receipts{RESET}")
    print("  " + ("\n  ".join(state["receipts"]) if state["receipts"] else "none"))
    print(f"\n{BOLD}Actions{RESET}")
    print("[g] release  [c] checkout  [v] review  [t] trust  [k] tools  [d] doctor")
    print("[i] core     [r] ccodex    [p] provider [f] profile [u] update [h] refresh")
    print("[b] rollback [x] conflict  [1] rm route [2] rm core [3] rm dist [s] status")
    print("[a] approve  [j] reject    [q] quit")


def demo() -> None:
    state = initial_state()
    steps = (
        ("request release acquisition", "quick"),
        ("approve acquisition", "approve"),
        ("review exact release evidence", "review"),
        ("run offline doctor", "doctor"),
        ("request native-Claude core", "core"),
        ("approve core activation", "approve"),
        ("request optional ccodex profile", "route"),
        ("approve routed profile", "approve"),
        ("request version update", "update"),
        ("approve side-by-side update", "approve"),
        ("review updated release evidence", "review"),
        ("rerun offline doctor", "doctor"),
        ("refresh owned activations", "refresh"),
        ("approve activation refresh", "approve"),
        ("inspect offline status", "status"),
    )
    print("PROTOTYPE — non-interactive ccodex sdlc walkthrough")
    print("No command changes the machine.\n")
    for number, (label, action) in enumerate(steps, start=1):
        state = reduce(state, action)
        print(
            f"{number:02}. {label:34} -> {state['last_result']} "
            f"[dist={state['distribution_version'] or '-'}, core={state['core']}, "
            f"ccodex={state['routed_profile']}]"
        )
    print("\nFinal state\n")
    render(state, clear_screen=False)


def main() -> None:
    if not sys.stdin.isatty():
        demo()
        return
    state = initial_state()
    while True:
        render(state)
        try:
            choice = input("\nchoice> ").strip().lower()
        except EOFError:
            print("\nInput closed; prototype exited without changing the machine.")
            return
        if choice == "q":
            return
        state = reduce(state, ACTIONS.get(choice, choice))


if __name__ == "__main__":
    main()
