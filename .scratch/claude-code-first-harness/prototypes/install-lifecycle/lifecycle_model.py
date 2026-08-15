"""PROTOTYPE: pure installation-lifecycle state machine; performs no I/O."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


State = dict[str, Any]


def initial_state() -> State:
    return {
        "distribution": "absent",
        "distribution_version": None,
        "previous_version": None,
        "source_reviewed": False,
        "mise_trusted": False,
        "toolchain_ready": False,
        "doctor": "not-run",
        "core": "absent",
        "core_version": None,
        "routed_profile": "absent",
        "providers": "native-claude-only",
        "optional_profile": "absent",
        "pending": None,
        "last_result": "Choose an acquisition path.",
        "receipts": [],
    }


MUTATIONS = {
    "quick": (
        "Acquire versioned release",
        "Install and globally activate the ccodex operator CLI through mise; no Claude, OCX, or provider state changes.",
    ),
    "checkout": (
        "Acquire managed checkout",
        "Clone the distribution into its managed data directory; trust, tools, and host activation remain separate.",
    ),
    "trust": (
        "Trust reviewed checkout config",
        "Persist mise trust for this exact reviewed mise.toml path.",
    ),
    "tools": (
        "Resolve checkout toolchain",
        "Download and install the locked contributor toolchain for the managed checkout.",
    ),
    "core": (
        "Activate Claude core",
        "Install receipt-owned Agentic SDLC plugin entries for ordinary Claude Code.",
    ),
    "route": (
        "Activate routed-model profile",
        "Admit ccodex launch and its pinned OCX runtime; provider credentials are unchanged.",
    ),
    "provider": (
        "Configure one OCX provider",
        "Enter the provider's own login flow; credentials remain operator-owned.",
    ),
    "profile": (
        "Activate optional first-party profile",
        "Install one receipt-owned optional profile without changing the core or companion libraries.",
    ),
    "update": (
        "Acquire next distribution version",
        "Install version 1.1.0 beside 1.0.0; activated host entries remain on their recorded version until refresh.",
    ),
    "refresh": (
        "Refresh owned activations",
        "Replace only verified unchanged owned core/profile entries with the selected distribution version.",
    ),
    "rollback": (
        "Observe mise selecting the previous version",
        "Model an external mise version selection; ccodex does not update itself and activations remain unchanged until refresh.",
    ),
    "remove-route": (
        "Remove routed-model profile",
        "Remove only unchanged receipt-owned ccodex/OCX entries; provider-owned credentials remain.",
    ),
    "remove-core": (
        "Remove Claude core",
        "Remove only unchanged receipt-owned Agentic SDLC Claude entries; distribution remains installed.",
    ),
    "remove-dist": (
        "Remove selected distribution",
        "Remove the selected mise release or managed checkout only after owned activations are absent.",
    ),
}


def _receipt(state: State, event: str) -> None:
    state["receipts"].append(event)
    state["receipts"] = state["receipts"][-5:]


def _stage(state: State, action: str) -> State:
    if state["pending"]:
        state["last_result"] = "Resolve the current approval before requesting another mutation."
        return state
    allowed, reason = _allowed(state, action)
    if not allowed:
        state["last_result"] = f"REFUSED: {reason}"
        return state
    title, effect = MUTATIONS[action]
    state["pending"] = {"action": action, "title": title, "effect": effect}
    state["last_result"] = "Approval required for the exact effect shown."
    return state


def _allowed(state: State, action: str) -> tuple[bool, str]:
    distribution = state["distribution"]
    if action in {"quick", "checkout"}:
        return (distribution == "absent", "a distribution is already selected")
    if action == "trust":
        return (
            distribution == "managed-checkout" and state["source_reviewed"] and not state["mise_trusted"],
            "managed checkout must exist, be reviewed, and remain untrusted",
        )
    if action == "tools":
        return (
            distribution == "managed-checkout" and state["mise_trusted"] and not state["toolchain_ready"],
            "the exact checkout config must be trusted first",
        )
    if action == "core":
        return (
            distribution != "absent" and state["doctor"] == "ready" and state["core"] == "absent",
            "run a successful doctor and resolve any existing core state first",
        )
    if action == "route":
        return (
            state["core"] == "installed" and state["routed_profile"] == "absent",
            "the Claude core must be installed and the profile absent",
        )
    if action == "provider":
        return (
            state["routed_profile"] == "installed" and state["providers"] == "native-claude-only",
            "the routed profile must be installed and no OCX provider configured",
        )
    if action == "profile":
        return (
            state["core"] == "installed" and state["optional_profile"] == "absent",
            "the core must be installed and the optional profile absent",
        )
    if action == "update":
        return (
            distribution != "absent" and state["distribution_version"] == "1.0.0",
            "version 1.0.0 must be selected",
        )
    if action == "refresh":
        stale = any(
            value == "stale" for value in (state["core"], state["routed_profile"], state["optional_profile"])
        )
        return (
            stale and state["source_reviewed"] and state["doctor"] == "ready",
            "a stale activation, review of the selected version, and a ready doctor are required",
        )
    if action == "rollback":
        return (state["previous_version"] is not None, "no previous version is available")
    if action == "remove-route":
        return (state["routed_profile"] == "installed", "routed profile is not safely removable")
    if action == "remove-core":
        profiles_absent = state["routed_profile"] == "absent" and state["optional_profile"] == "absent"
        return (
            state["core"] == "installed" and profiles_absent,
            "remove owned profiles first or resolve modified/conflicting state",
        )
    if action == "remove-dist":
        activations_absent = all(
            state[name] == "absent" for name in ("core", "routed_profile", "optional_profile")
        )
        return (distribution != "absent" and activations_absent, "remove owned activations first")
    return (False, "unknown mutation")


def _approve(state: State) -> State:
    pending = state["pending"]
    if not pending:
        state["last_result"] = "Nothing is awaiting approval."
        return state
    action = pending["action"]
    if action == "quick":
        state.update(
            distribution="versioned-release",
            distribution_version="1.0.0",
            toolchain_ready=True,
        )
    elif action == "checkout":
        state.update(distribution="managed-checkout", distribution_version="1.0.0")
    elif action == "trust":
        state["mise_trusted"] = True
    elif action == "tools":
        state["toolchain_ready"] = True
    elif action == "core":
        state.update(core="installed", core_version=state["distribution_version"])
    elif action == "route":
        state["routed_profile"] = "installed"
    elif action == "provider":
        state["providers"] = "native-Claude + one qualified OCX provider"
    elif action == "profile":
        state["optional_profile"] = "installed"
    elif action == "update":
        state["previous_version"] = state["distribution_version"]
        state["distribution_version"] = "1.1.0"
        state["source_reviewed"] = False
        for name in ("core", "routed_profile", "optional_profile"):
            if state[name] == "installed":
                state[name] = "stale"
    elif action == "refresh":
        for name in ("core", "routed_profile", "optional_profile"):
            if state[name] == "stale":
                state[name] = "installed"
        if state["core"] == "installed":
            state["core_version"] = state["distribution_version"]
    elif action == "rollback":
        current = state["distribution_version"]
        state["distribution_version"] = state["previous_version"]
        state["previous_version"] = current
        state["source_reviewed"] = False
        for name in ("core", "routed_profile", "optional_profile"):
            if state[name] == "installed":
                state[name] = "stale"
    elif action == "remove-route":
        state["routed_profile"] = "absent"
    elif action == "remove-core":
        state.update(core="absent", core_version=None)
    elif action == "remove-dist":
        state = initial_state()
        state["last_result"] = "Distribution removed; operator/provider-owned state was not touched."
        _receipt(state, "approved: remove selected distribution")
        return state
    _receipt(state, f"approved: {pending['title']}")
    state["pending"] = None
    state["doctor"] = "not-run" if action in {"quick", "checkout", "update", "rollback"} else state["doctor"]
    state["last_result"] = f"APPLIED: {pending['title']}"
    return state


def reduce(state: State, action: str) -> State:
    """Return the next lifecycle state for one named prototype action."""
    state = deepcopy(state)
    if action in MUTATIONS:
        return _stage(state, action)
    if action == "approve":
        return _approve(state)
    if action == "reject":
        if state["pending"]:
            state["last_result"] = f"REJECTED: {state['pending']['title']}"
            state["pending"] = None
        else:
            state["last_result"] = "Nothing is awaiting approval."
        return state
    if action == "review":
        if state["distribution"] == "absent":
            state["last_result"] = "BLOCKED: acquire a distribution before reviewing it."
        elif state["distribution"] == "managed-checkout":
            state["source_reviewed"] = True
            state["last_result"] = "READ-ONLY: mise.toml, lock, source, and resolved commit reviewed."
        else:
            state["source_reviewed"] = True
            state["last_result"] = "READ-ONLY: release manifest, checksums, attestation, and version reviewed."
        return state
    if action == "doctor":
        if state["distribution"] == "absent":
            state.update(doctor="blocked", last_result="BLOCKED: acquire a distribution first.")
        elif not state["source_reviewed"]:
            state.update(doctor="blocked", last_result="BLOCKED: review this exact distribution version first.")
        elif state["distribution"] == "managed-checkout" and not state["toolchain_ready"]:
            state.update(doctor="blocked", last_result="BLOCKED: checkout trust/toolchain is incomplete.")
        else:
            state.update(doctor="ready", last_result="READY: host, distribution, receipts, and collisions inspected offline.")
        return state
    if action == "status":
        state["last_result"] = "READ-ONLY: status derived from local receipts; no network or repair attempted."
        return state
    if action == "conflict":
        target = next((name for name in ("core", "routed_profile", "optional_profile") if state[name] in {"installed", "stale"}), None)
        if target:
            state[target] = "modified/conflict"
            state["last_result"] = f"SIMULATED: foreign modification detected in {target}; update/removal will preserve it."
        else:
            state["last_result"] = "Install an owned activation before simulating drift."
        return state
    state["last_result"] = "Unknown action."
    return state
