from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "model-tier-rightsizing" / "scripts" / "rightsize.py"
SPEC = importlib.util.spec_from_file_location("rightsize", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RIGHTSIZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RIGHTSIZE)
POLICY = RIGHTSIZE.load_json(RIGHTSIZE.POLICY_PATH)
TASK_POLICY = RIGHTSIZE.load_json(RIGHTSIZE.TASK_POLICY_PATH)
RUNTIME_POLICY = RIGHTSIZE.load_json(RIGHTSIZE.RUNTIME_POLICY_PATH)


CATALOG = {
    "data": [
        {"id": "gpt-5.6-luna"},
        {"id": "muse/muse-spark-1.2"},
    ]
}
LIVE_MODELS = [
    {
        "provider": "openai",
        "id": "gpt-5.6-luna",
        "namespaced": "gpt-5.6-luna",
        "disabled": False,
        "native": True,
        "reasoningEfforts": ["low", "medium", "high", "xhigh", "max"],
        "contextWindow": 372000,
    },
    {
        "provider": "muse",
        "id": "muse-spark-1.2",
        "namespaced": "muse/muse-spark-1.2",
        "disabled": False,
        "contextWindow": 1048576,
    },
]
AUTH = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "apiProvider": "firstParty",
    "email": "person@example.test",
    "orgId": "org-secret",
    "orgName": "Sensitive Org",
    "subscriptionType": "pro",
}
PROVIDERS = """Configured providers:

  openai (default)  adapter=openai-responses
  muse [custom]  adapter=openai-responses model=muse-spark-1.2

Available from registry (77):

  anthropic Anthropic Claude (oauth)
"""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def runner_for_discovery(repo: Path):
    def runner(argv, **_kwargs):
        joined = " ".join(argv)
        if "rev-parse --show-toplevel" in joined:
            return subprocess.CompletedProcess(argv, 0, str(repo) + "\n", "")
        if "rev-parse HEAD" in joined:
            return subprocess.CompletedProcess(argv, 0, "a" * 40 + "\n", "")
        if "config get port" in joined:
            return subprocess.CompletedProcess(argv, 0, "10100\n", "")
        if "models live --json" in joined:
            return subprocess.CompletedProcess(argv, 0, json.dumps(LIVE_MODELS), "")
        if "provider list" in joined:
            return subprocess.CompletedProcess(argv, 0, PROVIDERS, "")
        if "claude auth status --json" in joined:
            return subprocess.CompletedProcess(argv, 0, json.dumps(AUTH), "")
        raise AssertionError(argv)

    return runner


def discovery() -> dict:
    return {
        "schema_version": "rightsize-discovery/v1",
        "captured_at": "2026-08-12T00:00:00Z",
        "target_identity_sha256": "1" * 64,
        "gateway": {
            "endpoint": "http://127.0.0.1:10100/v1/models",
            "live": True,
            "catalog_sha256": "2" * 64,
            "catalog_ids": ["gpt-5.6-luna", "muse/muse-spark-1.2"],
        },
        "configured_providers": ["openai", "muse"],
        "registry_providers": ["anthropic"],
        "live_providers": ["muse", "openai"],
        "live_models": RIGHTSIZE.parse_live_models(json.dumps(LIVE_MODELS)),
        "claude_subscription": {
            "logged_in": True,
            "auth_method": "claude.ai",
            "api_provider": "firstParty",
            "subscription_type": "pro",
            "usable": True,
            "candidate_exact_model_ids": ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5"],
        },
    }


def route(
    model: str = "gpt-5.6-luna",
    *,
    provider: str = "openai",
    route_kind: str = "gateway-routed-provider",
    effort: str = "high",
    context: str = "base",
    billing: str = "api-token",
) -> dict:
    return {
        "transport_surface": "claude-code-gateway",
        "route_kind": route_kind,
        "provider": provider,
        "auth_basis": "operator-claude-login" if provider == "anthropic" else "provider-credential",
        "billing_basis": billing,
        "requested_model_id": model,
        "requested_effort": effort,
        "requested_context_form": context,
    }


def run_spec(pack: str = "builtin:harness-smoke-v1") -> dict:
    return {
        "schema_version": "rightsize-run-spec/v1",
        "routes": [route()],
        "task_classes": ["mechanical_redo", "deterministic_gated_change"],
        "task_pack": pack,
        "evaluation_depth": "pilot",
        "pareto_objective": "api-equivalent-cost",
        "attempts_per_task": 1,
        "budgets": {
            "max_calls": 10,
            "max_wall_seconds": 60,
            "max_api_equivalent_usd": 5,
        },
        "expected_peak_input_tokens": 100,
        "allow_usage_credits": False,
        "target_data_egress_acknowledged": False,
        "output": ".agentic-sdlc/rightsize/model-task-map.json",
        "regenerate": False,
        "force": False,
    }


def attempt(route_value: dict, task_id: str = "exact-output", accepted: bool = True, **overrides) -> dict:
    value = {
        "task_id": task_id,
        "task_class": "mechanical_redo",
        "critical": False,
        "route_id": RIGHTSIZE.digest(route_value),
        "accepted": accepted,
        "failure_class": None if accepted else "gate",
        "duration_ms": 100,
        "first_output_ms": 50,
        "tool_steps": 1,
        "request_injection_evidence": {},
        "identity_evidence": {"verified": True},
        "effort_readback": "unavailable",
        "context_readback": "unavailable",
        "output_sha256": "3" * 64,
        "usage": {
            "input_tokens": 10,
            "uncached_input_tokens": 5,
            "cache_read_tokens": 5,
            "cache_write_tokens": 0,
            "reasoning_tokens": 1,
            "visible_output_tokens": 2,
            "total_tokens": 12,
        },
        "cost": {
            "marginal_cost_usd": 0.1,
            "api_equivalent_cost_usd": 0.1,
            "cost_provenance": "gateway-modeled",
            "quota_consumption": "not-applicable",
            "usage_credits_possible": False,
        },
    }
    value.update(overrides)
    return value


class DiscoveryTests(unittest.TestCase):
    def test_discovery_strips_auth_pii_and_separates_live_from_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            result = RIGHTSIZE.discover(
                repo,
                runner=runner_for_discovery(repo),
                catalog_raw=canonical(CATALOG),
                captured_at="2026-08-12T00:00:00Z",
            )
        serialized = json.dumps(result)
        self.assertNotIn("person@example.test", serialized)
        self.assertNotIn("org-secret", serialized)
        self.assertNotIn("Sensitive Org", serialized)
        self.assertEqual(result["configured_providers"], ["openai", "muse"])
        self.assertEqual(result["registry_providers"], ["anthropic"])
        self.assertEqual(result["live_providers"], ["muse", "openai"])
        self.assertNotIn("anthropic", result["configured_providers"])
        self.assertTrue(result["claude_subscription"]["usable"])

    def test_discovery_reads_the_configured_gateway_port(self) -> None:
        calls: list[list[str]] = []
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            base_runner = runner_for_discovery(repo)

            def runner(argv, **kwargs):
                calls.append(argv)
                if "config" in argv and "get" in argv and "port" in argv:
                    return subprocess.CompletedProcess(argv, 0, "12042\n", "")
                return base_runner(argv, **kwargs)

            with mock.patch.object(RIGHTSIZE, "fetch_catalog", return_value=canonical(CATALOG)) as fetch:
                result = RIGHTSIZE.discover(
                    repo, runner=runner, captured_at="2026-08-12T00:00:00Z"
                )

        self.assertTrue(any("config" in argv and "port" in argv for argv in calls))
        fetch.assert_called_once_with("http://127.0.0.1:12042/v1/models")
        self.assertEqual(result["gateway"]["endpoint"], "http://127.0.0.1:12042/v1/models")

    def test_configured_gateway_port_rejects_non_ascii_digits(self) -> None:
        for value in ("²\n", "１２３\n"):
            with self.subTest(value=value):
                def runner(argv, **_kwargs):
                    return subprocess.CompletedProcess(argv, 0, value, "")

                with self.assertRaisesRegex(
                    RIGHTSIZE.RightsizeError, "ocx-configured-port-invalid"
                ):
                    RIGHTSIZE.configured_gateway_endpoint(runner)

    def test_duplicate_json_members_are_rejected(self) -> None:
        with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "duplicate-json-member:model"):
            RIGHTSIZE.parse_no_duplicate_members('{"model":"a","model":"b"}')


class SpecAndPlanTests(unittest.TestCase):
    def test_missing_required_answer_is_named(self) -> None:
        spec = run_spec()
        del spec["pareto_objective"]
        with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "question-required:spec.pareto_objective"):
            RIGHTSIZE.validate_spec(spec, POLICY)

    def test_unknown_free_text_model_is_blocked(self) -> None:
        spec = run_spec()
        spec["routes"] = [route("custom/not-live")]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "no-evaluation-eligible-route"):
                RIGHTSIZE.plan_run(spec, discovery(), Path(directory))

    def test_plan_is_deterministic_and_makes_no_live_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, _ = RIGHTSIZE.plan_run(run_spec(), discovery(), Path(directory))
            second, _ = RIGHTSIZE.plan_run(run_spec(), discovery(), Path(directory))
        self.assertEqual(RIGHTSIZE.canonical_bytes(first), RIGHTSIZE.canonical_bytes(second))
        self.assertFalse(first["live_calls_made"])
        self.assertFalse(first["files_written"])
        self.assertEqual(first["authorization"]["exact_model_calls"], 2)

    def test_usage_credit_routes_require_acknowledgement(self) -> None:
        spec = run_spec()
        spec["routes"] = [
            route(
                "claude-fable-5",
                provider="anthropic",
                route_kind="gateway-claude-subscription-passthrough",
                effort="max",
                billing="claude-subscription",
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "question-required:allow_usage_credits"):
                RIGHTSIZE.plan_run(spec, discovery(), Path(directory))

    def test_builtin_smoke_pack_cannot_qualify(self) -> None:
        spec = run_spec()
        spec["evaluation_depth"] = "qualification"
        spec["attempts_per_task"] = 3
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "target-representative"):
                RIGHTSIZE.plan_run(spec, discovery(), Path(directory))

    def test_context_fit_is_hard_filter_and_1m_is_not_inferred(self) -> None:
        state = RIGHTSIZE.route_discovery_state(route(), discovery(), RUNTIME_POLICY)
        context = RIGHTSIZE.context_state(route(), state, 371000, POLICY)
        self.assertFalse(context["fits"])
        self.assertEqual(context["capacity_source"], "ocx-live-models")
        extended = route(context="[1m]")
        extended_state = RIGHTSIZE.route_discovery_state(extended, discovery(), RUNTIME_POLICY)
        self.assertTrue(RIGHTSIZE.context_state(extended, extended_state, 371000, POLICY)["fits"])

    def test_fixture_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").write_text("safe", encoding="utf-8")
            (root / "link").symlink_to(root / "real")
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "fixture-symlink-forbidden"):
                RIGHTSIZE.validate_fixture(root)

    def test_fixture_is_allowed_and_bound_into_the_task_pack_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "input.txt").write_text("one", encoding="utf-8")
            pack = RIGHTSIZE.load_json(RIGHTSIZE.DEFAULT_PACK_PATH)
            pack["tasks"][0]["fixture"] = "fixture"
            first = RIGHTSIZE.validate_task_pack(pack, root / "pack.json", TASK_POLICY)
            (fixture / "input.txt").write_text("two", encoding="utf-8")
            second = RIGHTSIZE.validate_task_pack(pack, root / "pack.json", TASK_POLICY)
        self.assertNotEqual(first["tasks"][0]["fixture_sha256"], second["tasks"][0]["fixture_sha256"])
        self.assertNotEqual(RIGHTSIZE.digest(first), RIGHTSIZE.digest(second))

    def test_probe_plans_one_synthetic_canary_per_route(self) -> None:
        spec = run_spec()
        spec["evaluation_depth"] = "probe"
        spec["attempts_per_task"] = 7
        with tempfile.TemporaryDirectory() as directory:
            plan, execution = RIGHTSIZE.plan_run(spec, discovery(), Path(directory))
        self.assertEqual(plan["authorization"]["exact_model_calls"], 1)
        self.assertEqual(plan["authorization"]["attempts_per_task"], 1)
        self.assertEqual(plan["task_pack"]["id"], "route-probe-v1")
        self.assertEqual([task["id"] for task in execution["tasks"]], ["route-probe"])

    def test_claude_effort_vocabulary_is_not_reported_as_observed(self) -> None:
        claude = route(
            "claude-opus-4-8",
            provider="anthropic",
            route_kind="gateway-claude-subscription-passthrough",
            billing="claude-subscription",
        )
        state = RIGHTSIZE.route_discovery_state(claude, discovery(), RUNTIME_POLICY)
        self.assertEqual(state["effort_vocab"], [])
        self.assertEqual(state["effort_vocab_source"], "unavailable")
        self.assertTrue(state["requested_effort_policy_admitted"])

    def test_absolute_output_is_normalized_to_target_relative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = run_spec()
            spec["output"] = str(root / ".agentic-sdlc" / "map.json")
            plan, _ = RIGHTSIZE.plan_run(spec, discovery(), root)
        self.assertEqual(plan["run_spec"]["output"], ".agentic-sdlc/map.json")

    def test_invalid_verifier_is_rejected_before_evaluation(self) -> None:
        pack = RIGHTSIZE.load_json(RIGHTSIZE.DEFAULT_PACK_PATH)
        pack["tasks"][0]["verifier"] = {"type": "file-diff", "sha256": {"../outside": "0" * 64}}
        with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "invalid-verifier"):
            RIGHTSIZE.validate_task_pack(pack, RIGHTSIZE.DEFAULT_PACK_PATH, TASK_POLICY)

    def test_unknown_verifier_is_rejected_by_the_closed_vocabulary(self) -> None:
        pack = RIGHTSIZE.load_json(RIGHTSIZE.DEFAULT_PACK_PATH)
        pack["tasks"][0]["verifier"] = {"type": "external-command"}
        self.assertEqual(
            POLICY["verifier_types"],
            ["exact", "schema", "finding-coverage", "file-diff"],
        )
        with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "unsupported-verifier"):
            RIGHTSIZE.validate_task_pack(pack, RIGHTSIZE.DEFAULT_PACK_PATH, TASK_POLICY)

    def test_authority_qualification_requires_every_task_to_be_critical(self) -> None:
        pack = {
            "schema_version": "rightsize-task-pack/v1",
            "id": "authority-v1",
            "kind": "target-representative",
            "harness_profile": "claude-code-print-v1",
            "runtime_profile": "no-tools",
            "target_representative": True,
            "expected_results_hidden_or_immutable": True,
            "data_classification": "synthetic",
            "tasks": [
                {
                    **copy.deepcopy(RIGHTSIZE.PROBE_TASK),
                    "id": f"task-{index}",
                    "task_class": "authority_or_frontier",
                    "critical": index != 0,
                }
                for index in range(5)
            ],
        }
        spec = run_spec("authority.json")
        spec["task_classes"] = ["authority_or_frontier"]
        spec["evaluation_depth"] = "qualification"
        spec["attempts_per_task"] = 3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "authority.json").write_text(json.dumps(pack), encoding="utf-8")
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "must-be-critical"):
                RIGHTSIZE.plan_run(spec, discovery(), root)


class IdentityTests(unittest.TestCase):
    def test_gateway_identity_uses_attribution_and_rejects_default_provider(self) -> None:
        record = {
            "requestId": "request-1",
            "requestedModel": "gpt-5.6-luna",
            "resolvedModel": "gpt-5.6-luna",
            "provider": "openai",
            "status": 200,
            "inboundProtocol": "messages",
            "conversationId": "conversation-1",
            "routeDecision": {
                "routeKind": "native",
                "selected": {"provider": "openai", "model": "gpt-5.6-luna"},
            },
        }
        self.assertTrue(RIGHTSIZE.identity_evidence(route(), [record])["verified"])
        record["routeDecision"]["routeKind"] = "default-provider"
        self.assertEqual(RIGHTSIZE.identity_evidence(route(), [record])["failure"], "default-provider")

    def test_muse_prefix_and_provider_mismatch_fail_closed(self) -> None:
        muse_route = route("muse/muse-spark-1.2", provider="muse", effort="high")
        record = {
            "requestId": "request-2",
            "requestedModel": "muse/muse-spark-1.2",
            "resolvedModel": "muse-spark-1.2",
            "provider": "openai",
            "status": 200,
            "inboundProtocol": "messages",
            "conversationId": "conversation-2",
            "routeDecision": {
                "routeKind": "default-provider",
                "selected": {"provider": "openai", "model": "muse/muse-spark-1.2"},
            },
        }
        evidence = RIGHTSIZE.identity_evidence(muse_route, [record])
        self.assertFalse(evidence["verified"])

    def test_claude_passthrough_requires_anthropic_native_attribution(self) -> None:
        claude = route(
            "claude-opus-4-8",
            provider="anthropic",
            route_kind="gateway-claude-subscription-passthrough",
            billing="claude-subscription",
        )
        record = {
            "requestId": "request-3",
            "requestedModel": "claude-opus-4-8",
            "resolvedModel": None,
            "provider": "anthropic-native",
            "status": 200,
            "inboundProtocol": "messages",
            "conversationId": "conversation-3",
        }
        evidence = RIGHTSIZE.identity_evidence(claude, [record])
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["identity_basis"], "unambiguous_exact_id_mapping_with_provider_attribution")

    def test_ambiguous_conversation_groups_are_rejected(self) -> None:
        records = [
            {"requestId": "a", "conversationId": "one", "inboundProtocol": "messages"},
            {"requestId": "b", "conversationId": "two", "inboundProtocol": "messages"},
        ]
        self.assertEqual(RIGHTSIZE.identity_evidence(route(), records)["failure"], "ambiguous-attribution")

    def test_a_413_is_the_gateways_own_input_admission_refusal_not_a_transport_status(self) -> None:
        # opencodex answers 413 from its own input-admission preflight (estimated inbound tokens
        # over the route ceiling * 2.5) BEFORE any provider request exists, so the attempt carries
        # no provider evidence at all. It must not be reported as the same thing as an upstream
        # 5xx: the remedy is a smaller prompt or a larger window, not a retry.
        def record(status: object, request_id: str = "request-413") -> dict[str, object]:
            return {
                "requestId": request_id,
                "requestedModel": "gpt-5.6-luna",
                "resolvedModel": "gpt-5.6-luna",
                "provider": "openai",
                "status": status,
                "inboundProtocol": "messages",
                "conversationId": "conversation-413",
                "routeDecision": {
                    "routeKind": "native",
                    "selected": {"provider": "openai", "model": "gpt-5.6-luna"},
                },
            }

        # POSITIVE CONTROL: the same record shape at 200 verifies, so a failure below is the
        # status classification and not a broken fixture.
        self.assertTrue(RIGHTSIZE.identity_evidence(route(), [record(200)])["verified"])

        refused = RIGHTSIZE.identity_evidence(route(), [record(413)])
        self.assertFalse(refused["verified"])
        self.assertEqual(refused["failure"], "input_admission_refused")
        self.assertEqual(refused["observed_statuses"], [413])

        # An upstream failure keeps the generic name.
        self.assertEqual(
            RIGHTSIZE.identity_evidence(route(), [record(500)])["failure"], "transport-status"
        )
        # And a 413 sitting beside a 500 must NOT be renamed after the 413, which would hide the
        # 500 behind an admission verdict.
        mixed = RIGHTSIZE.identity_evidence(
            route(), [record(413, "request-a"), record(500, "request-b")]
        )
        self.assertEqual(mixed["failure"], "transport-status")
        # A supplied-but-unusable status is distinct from an admission refusal: neither the string
        # "413" nor an absent field is the gateway's 413.
        self.assertEqual(
            RIGHTSIZE.identity_evidence(route(), [record("413")])["failure"], "transport-status"
        )
        missing = record(200)
        del missing["status"]
        self.assertEqual(
            RIGHTSIZE.identity_evidence(route(), [missing])["failure"], "transport-status"
        )


class MetricsAndRenderTests(unittest.TestCase):
    def test_zero_success_cost_per_accepted_is_unavailable(self) -> None:
        value = RIGHTSIZE.summarize_route(
            route(),
            "mechanical_redo",
            [attempt(route(), accepted=False)],
            "qualification",
            {"target_representative": True},
            POLICY,
            True,
        )
        self.assertIsNone(value["observed_api_equivalent_cost_per_accepted"])
        self.assertEqual(value["qualification_state"], "route-probed")

    def test_pilot_never_promotes(self) -> None:
        attempts = [attempt(route(), task_id=f"task-{index}") for index in range(15)]
        summary = RIGHTSIZE.summarize_route(
            route(),
            "mechanical_redo",
            attempts,
            "pilot",
            {"target_representative": True},
            POLICY,
            True,
        )
        self.assertEqual(summary["qualification_state"], "route-probed")

    def test_qualification_requires_confidence_not_only_ninety_percent(self) -> None:
        ten = [attempt(route(), task_id=f"task-{index // 2}") for index in range(9)]
        ten.append(attempt(route(), task_id="task-4", accepted=False))
        summary = RIGHTSIZE.summarize_route(
            route(),
            "mechanical_redo",
            ten,
            "qualification",
            {"target_representative": True},
            POLICY,
            True,
        )
        self.assertEqual(summary["accepted_rate"], 0.9)
        self.assertLess(summary["wilson_95"]["lower"], 0.7)
        self.assertNotEqual(summary["qualification_state"], "role-qualified")

    def test_missing_efficiency_metric_does_not_establish_dominance(self) -> None:
        left = {
            "wilson_95": {"lower": 0.8},
            "transport_or_identity_failure_rate": 0.0,
            "observed_api_equivalent_cost_per_accepted": None,
        }
        right = {
            "wilson_95": {"lower": 0.7},
            "transport_or_identity_failure_rate": 0.0,
            "observed_api_equivalent_cost_per_accepted": 0.1,
        }
        self.assertFalse(RIGHTSIZE.dominates(left, right, "api-equivalent-cost"))
        self.assertTrue(RIGHTSIZE.dominates(left, right, "reliability"))

    def test_schema_integer_does_not_accept_boolean(self) -> None:
        verifier = {"type": "schema", "required": ["count"], "properties": {"count": "integer"}}
        self.assertFalse(RIGHTSIZE.verify_schema({"count": True}, verifier))
        self.assertTrue(RIGHTSIZE.verify_schema({"count": 1}, verifier))

    def test_subscription_cost_is_null_not_zero(self) -> None:
        claude = route(
            "claude-opus-4-8",
            provider="anthropic",
            route_kind="gateway-claude-subscription-passthrough",
            billing="claude-subscription",
        )
        cost = RIGHTSIZE.attempt_cost(claude, [], {"reported_total_cost_usd": 0.25})
        self.assertIsNone(cost["marginal_cost_usd"])
        self.assertEqual(cost["api_equivalent_cost_usd"], 0.25)
        self.assertNotEqual(cost["marginal_cost_usd"], 0)

    def test_dispatch_front_hard_filters_unqualified_routes(self) -> None:
        spec = run_spec()
        plan, execution = RIGHTSIZE.plan_run(spec, discovery(), ROOT)
        attempts = [attempt(route()), attempt(route(), task_id="structured-output", task_class="deterministic_gated_change")]
        evidence = RIGHTSIZE.build_evidence(plan, execution, attempts, "2026-08-12T00:00:00Z")
        self.assertEqual(evidence["measured_pareto_fronts"]["mechanical_redo"], [RIGHTSIZE.digest(route())])
        self.assertEqual(evidence["dispatch_pareto_fronts"]["mechanical_redo"], [])
        model_map = RIGHTSIZE.build_map(evidence)
        self.assertFalse(model_map["map"]["mechanical_redo"]["primary"]["dispatchable_recommendation"])
        self.assertEqual(
            model_map["map"]["mechanical_redo"]["status"],
            "blocked-not-role-qualified-or-runtime-admitted",
        )

    def test_dispatch_front_can_select_a_route_outside_the_measured_front(self) -> None:
        unqualified_route = route("gpt-5.6-terra")
        qualified_route = route("gpt-5.6-luna")
        unqualified = RIGHTSIZE.summarize_route(
            unqualified_route,
            "mechanical_redo",
            [attempt(unqualified_route)],
            "pilot",
            {"target_representative": False},
            POLICY,
            False,
        )
        qualified = copy.deepcopy(unqualified)
        qualified.update(
            {
                "route_id": RIGHTSIZE.digest(qualified_route),
                "route": qualified_route,
                "qualification_state": "role-qualified",
                "runtime_policy_admitted": True,
                "dispatchable_recommendation": True,
            }
        )
        evidence = {
            "summaries": [unqualified, qualified],
            "measured_pareto_fronts": {"mechanical_redo": [unqualified["route_id"]]},
            "dispatch_pareto_fronts": {"mechanical_redo": [qualified["route_id"]]},
            "target_identity_sha256": "1" * 64,
            "catalog_sha256": "2" * 64,
            "task_pack": {"task_pack_sha256": "3" * 64},
            "benchmark_snapshot_sha256": "4" * 64,
            "run_spec": run_spec(),
            "route_registry": [],
        }

        entry = RIGHTSIZE.build_map(evidence)["map"]["mechanical_redo"]

        self.assertEqual(entry["primary"]["route_id"], qualified["route_id"])
        self.assertTrue(entry["primary"]["dispatchable_recommendation"])
        self.assertEqual(entry["status"], "recommended")

    def test_route_probe_accepts_a_completed_response_that_fails_the_task_gate(self) -> None:
        spec = run_spec()
        plan, execution = RIGHTSIZE.plan_run(spec, discovery(), ROOT)
        rejected = attempt(route(), accepted=False)

        evidence = RIGHTSIZE.build_evidence(
            plan, execution, [rejected], "2026-08-12T00:00:00Z"
        )

        probe = next(
            item for item in evidence["route_probes"] if item["route_id"] == RIGHTSIZE.digest(route())
        )
        self.assertEqual(probe["qualification_state"], "route-probed")

    def test_capture_logs_skips_malformed_lines_and_reports_the_count(self) -> None:
        record = {"requestId": "request-1", "status": 200}

        def runner(argv, **_kwargs):
            return subprocess.CompletedProcess(
                argv, 0, f"{{partial\n{json.dumps(record)}\n", ""
            )

        captured = RIGHTSIZE.capture_logs(runner)

        self.assertEqual(captured["records"], [record])
        self.assertEqual(captured["skipped_lines"], 1)

    def test_attempt_rejects_equal_count_replaced_malformed_log_lines(self) -> None:
        task = copy.deepcopy(RIGHTSIZE.PROBE_TASK)
        record = {
            "requestId": "request-1",
            "requestedModel": "gpt-5.6-luna",
            "resolvedModel": "gpt-5.6-luna",
            "provider": "openai",
            "status": 200,
            "timestamp": 1,
            "inboundProtocol": "messages",
            "conversationId": "conversation-1",
            "routeDecision": {
                "routeKind": "native",
                "selected": {"provider": "openai", "model": "gpt-5.6-luna"},
            },
        }
        captures = iter(
            (
                "{old-partial\n",
                f"{{new-partial\n{json.dumps(record)}\n",
            )
        )

        def runner(argv, **_kwargs):
            if "observe" in argv:
                return subprocess.CompletedProcess(argv, 0, next(captures), "")
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"result": "RIGHTSIZE_ROUTE_OK"}), ""
            )

        with mock.patch.object(RIGHTSIZE.time, "time", side_effect=[0.001, 0.001]):
            result = RIGHTSIZE.run_attempt(
                route(), task, RIGHTSIZE.DEFAULT_PACK_PATH, 1.0, 10, runner=runner
            )

        self.assertEqual(result["attribution_log_skipped_lines"], 1)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["failure_class"], "identity")
        self.assertEqual(result["identity_evidence"]["failure"], "malformed-attribution-stream")

    def test_model_call_timeout_becomes_a_wall_time_refusal(self) -> None:
        task = copy.deepcopy(RIGHTSIZE.PROBE_TASK)
        calls = 0

        def runner(argv, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return subprocess.CompletedProcess(argv, 0, "", "")
            raise subprocess.TimeoutExpired(argv, 1)

        with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "wall-time-budget-exhausted"):
            RIGHTSIZE.run_attempt(route(), task, RIGHTSIZE.DEFAULT_PACK_PATH, 1.0, 1, runner=runner)

    def test_post_call_attribution_failure_names_the_completed_attempt(self) -> None:
        task = copy.deepcopy(RIGHTSIZE.PROBE_TASK)
        calls = 0

        def runner(argv, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if calls == 2:
                return subprocess.CompletedProcess(
                    argv, 0, json.dumps({"result": "RIGHTSIZE_ROUTE_OK"}), ""
                )
            return subprocess.CompletedProcess(argv, 1, "", "unavailable")

        with self.assertRaisesRegex(
            RIGHTSIZE.RightsizeError, "attempt-attribution-unavailable-after-model-call"
        ):
            RIGHTSIZE.run_attempt(
                route(), task, RIGHTSIZE.DEFAULT_PACK_PATH, 1.0, 10, runner=runner
            )

    def test_prompt_uses_stdin_not_process_arguments(self) -> None:
        calls: list[tuple[list[str], dict]] = []
        prompt = "TOP_SECRET_PROMPT"
        task = copy.deepcopy(RIGHTSIZE.PROBE_TASK)
        task["prompt"] = prompt
        logs = [
            [],
            [
                {
                    "requestId": "request-1",
                    "requestedModel": "gpt-5.6-luna",
                    "resolvedModel": "gpt-5.6-luna",
                    "provider": "openai",
                    "status": 200,
                    "timestamp": 1,
                    "inboundProtocol": "messages",
                    "conversationId": "conversation-1",
                    "routeDecision": {
                        "routeKind": "native",
                        "selected": {"provider": "openai", "model": "gpt-5.6-luna"},
                    },
                }
            ],
        ]

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            if "observe" in argv:
                records = logs.pop(0)
                return subprocess.CompletedProcess(argv, 0, "\n".join(json.dumps(item) for item in records), "")
            return subprocess.CompletedProcess(argv, 0, json.dumps({"result": "RIGHTSIZE_ROUTE_OK"}), "")

        with mock.patch.object(RIGHTSIZE.time, "time", side_effect=[0.001, 0.001]):
            RIGHTSIZE.run_attempt(route(), task, RIGHTSIZE.DEFAULT_PACK_PATH, 1.0, 10, runner=runner)
        model_argv, model_kwargs = next(call for call in calls if "--print" in call[0])
        self.assertNotIn(prompt, model_argv)
        self.assertEqual(model_kwargs["input"], prompt)
        self.assertEqual(model_kwargs["env"]["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", model_kwargs["env"])

    def test_render_is_byte_identical_and_contains_no_prompts(self) -> None:
        spec = run_spec()
        plan, execution = RIGHTSIZE.plan_run(spec, discovery(), ROOT)
        attempts = [attempt(route()), attempt(route(), task_id="structured-output", task_class="deterministic_gated_change")]
        evidence = RIGHTSIZE.build_evidence(plan, execution, attempts, "2026-08-12T00:00:00Z")
        first = RIGHTSIZE.render_bundle(evidence, ROOT, write=False)
        second = RIGHTSIZE.render_bundle(copy.deepcopy(evidence), ROOT, write=False)
        self.assertEqual(first["map"], second["map"])
        self.assertEqual(first["markdown"], second["markdown"])
        serialized = json.dumps(first)
        self.assertNotIn("Return exactly RIGHTSIZE_OK", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_partial_output_requires_regenerate_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "map.json"
            output.write_text("{}", encoding="utf-8")
            spec = run_spec()
            with self.assertRaisesRegex(RIGHTSIZE.RightsizeError, "partial-output-requires"):
                RIGHTSIZE.check_replacement((output, output.with_suffix(".md"), output.with_suffix(".evidence.json")), spec)

    def test_generated_digest_detects_user_edit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            artifact = RIGHTSIZE.with_payload_digest({"schema_version": "example/v1", "value": 1})
            path.write_text(RIGHTSIZE.pretty_json(artifact), encoding="utf-8")
            self.assertTrue(RIGHTSIZE.valid_json_artifact(path))
            artifact["value"] = 2
            path.write_text(RIGHTSIZE.pretty_json(artifact), encoding="utf-8")
            self.assertFalse(RIGHTSIZE.valid_json_artifact(path))

    def test_evaluation_environment_is_allowlisted_and_has_a_deterministic_path(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"AWS_SECRET_ACCESS_KEY": "secret", "ANTHROPIC_API_KEY": "secret"},
            clear=True,
        ):
            environment = RIGHTSIZE.evaluation_environment()

        self.assertNotIn("AWS_SECRET_ACCESS_KEY", environment)
        self.assertNotIn("ANTHROPIC_API_KEY", environment)
        self.assertEqual(environment["PATH"], os.defpath)
        self.assertEqual(environment["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")


if __name__ == "__main__":
    unittest.main()
