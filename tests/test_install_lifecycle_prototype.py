"""The install-lifecycle prototype must model the installer's own preservation rules.

``docs/plans/claude-code-first-harness/prototypes/install-lifecycle/lifecycle_model.py`` ships
nothing, but it is executable and it is read as a description of the real lifecycle, so its
transitions are the claim under test. Two rules this repository states in prose have to hold in
them: a destination that drifted to ``modified/conflict`` is preserved rather than removed
(AGENTS.md — modified entries are "preserved untouched"), and provider-owned state survives a
distribution removal, which is what the prototype's own remove-route and remove-dist wording
promises.

Every refusal assertion here carries a positive control in the same test: a refusal proves nothing
unless the same harness is shown to let the unchanged case through.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]
PROTOTYPE = ROOT / "docs" / "plans" / "claude-code-first-harness" / "prototypes" / "install-lifecycle"
MODEL_SCRIPT = PROTOTYPE / "lifecycle_model.py"

_model_spec = importlib.util.spec_from_file_location("install_lifecycle_prototype_model", MODEL_SCRIPT)
assert _model_spec and _model_spec.loader
model = importlib.util.module_from_spec(_model_spec)
sys.modules[_model_spec.name] = model
_model_spec.loader.exec_module(model)

# The prototype's own walkthrough prefix that reaches an installed core plus routed profile.
TO_ROUTED_PROFILE = ("quick", "approve", "review", "doctor", "core", "approve", "route", "approve")


def apply(*actions: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reduce one action sequence. ``reduce`` copies, so a passed state is never mutated."""
    current = model.initial_state() if state is None else state
    for action in actions:
        current = model.reduce(current, action)
    return current


class StagedMutationRecheckTests(unittest.TestCase):
    def test_staged_core_removal_refuses_a_simulated_foreign_modification(self) -> None:
        installed = apply(*TO_ROUTED_PROFILE, "remove-route", "approve")
        self.assertEqual(installed["core"], "installed")

        applied = apply("remove-core", "approve", state=installed)
        self.assertEqual(applied["core"], "absent")
        self.assertEqual(applied["last_result"], "APPLIED: Remove Claude core")

        drifted = apply("remove-core", "conflict", "approve", state=installed)
        self.assertEqual(drifted["core"], "modified/conflict")
        self.assertTrue(drifted["last_result"].startswith("REFUSED: "), drifted["last_result"])
        self.assertIsNone(drifted["pending"])
        self.assertNotIn("approved: Remove Claude core", drifted["receipts"])

    def test_staged_route_removal_refuses_a_profile_that_drifted_while_pending(self) -> None:
        installed = apply(*TO_ROUTED_PROFILE)
        self.assertEqual(installed["routed_profile"], "installed")

        applied = apply("remove-route", "approve", state=installed)
        self.assertEqual(applied["routed_profile"], "absent")
        self.assertEqual(applied["last_result"], "APPLIED: Remove routed-model profile")

        # The `conflict` simulator marks only the first owned entry, which is the core while a
        # routed profile exists, so this drift is written directly.
        staged = apply("remove-route", state=installed)
        staged["routed_profile"] = "modified/conflict"
        drifted = model.reduce(staged, "approve")
        self.assertEqual(drifted["routed_profile"], "modified/conflict")
        self.assertTrue(drifted["last_result"].startswith("REFUSED: "), drifted["last_result"])
        self.assertIsNone(drifted["pending"])

    def test_recheck_leaves_the_prototype_walkthrough_applying(self) -> None:
        state = apply(
            *TO_ROUTED_PROFILE, "update", "approve", "review", "doctor", "refresh", "approve"
        )
        self.assertEqual(state["last_result"], "APPLIED: Refresh owned activations")
        self.assertEqual(state["core"], "installed")
        self.assertEqual(state["routed_profile"], "installed")
        self.assertEqual(state["core_version"], "1.1.0")


class ProviderOwnedStateTests(unittest.TestCase):
    def test_distribution_removal_preserves_the_configured_provider_surface(self) -> None:
        configured = apply(*TO_ROUTED_PROFILE, "provider", "approve")
        providers = configured["providers"]
        self.assertNotEqual(providers, "native-claude-only")

        removed = apply(
            "remove-route", "approve", "remove-core", "approve", "remove-dist", "approve",
            state=configured,
        )
        self.assertEqual(removed["providers"], providers)
        self.assertEqual(
            removed["last_result"],
            "Distribution removed; operator/provider-owned state was not touched.",
        )
        # Positive control: the same call really did reset the lifecycle-owned fields, so the
        # preserved provider surface is not just an unreached reset.
        self.assertEqual(removed["distribution"], "absent")
        self.assertIsNone(removed["distribution_version"])
        self.assertEqual(removed["core"], "absent")
        self.assertEqual(removed["receipts"], ["approved: remove selected distribution"])


if __name__ == "__main__":
    unittest.main()
