"""Cover the durable RouteQualification layer and its pre-dispatch admission.

Every refusal here carries a positive control: the same document, mutated only in the one field the
refusal is about, must reach `admit-dispatch`. Without that pairing a refusal test passes whenever
the tool refuses for ANY reason, including a reason the test does not name, so it would keep
passing after the check it claims to cover was deleted.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "model-tier-rightsizing" / "scripts"


def load(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUALIFICATION = load("route_qualification", SCRIPTS / "route_qualification.py")
RIGHTSIZE = load("rightsize", SCRIPTS / "rightsize.py")
POLICY = QUALIFICATION.load_policy()
EVALUATION_POLICY = json.loads((SCRIPTS.parent / "policy" / "rightsize-evaluation-v1.json").read_text())
FLOOR = EVALUATION_POLICY["qualification"]

ROUTE = {
    "transport_surface": "claude-code-gateway",
    "route_kind": "gateway-routed-provider",
    "provider": "openai",
    "auth_basis": "provider-credential",
    "billing_basis": "api-token",
    "requested_model_id": "gpt-5.6-luna",
    "requested_effort": "high",
    "requested_context_form": "base",
}
ROUTE_ID = QUALIFICATION.sha256_json(ROUTE)
CLASS = "semantic_implementation"
SIBLING_CLASS = "semantic_review"

OTHER_ROUTE = {**ROUTE, "requested_effort": "xhigh"}
OTHER_ROUTE_ID = QUALIFICATION.sha256_json(OTHER_ROUTE)


def attribution(provider: str = "openai", model: str = "gpt-5.6-luna", route_kind: str = "model-alias") -> dict:
    return {
        "request_id": "req-1",
        "requested_model": model,
        "resolved_model": model,
        "provider": provider,
        "status": 200,
        "route_kind": route_kind,
        "selected_provider": provider,
        "selected_model": model,
    }


def attempt(
    task_id: str,
    accepted: bool,
    *,
    task_class: str = CLASS,
    route_id: str = ROUTE_ID,
    critical: bool = False,
    failure_class: str | None = None,
    identity: dict | None = None,
) -> dict:
    return {
        "task_id": task_id,
        "task_class": task_class,
        "critical": critical,
        "route_id": route_id,
        "accepted": accepted,
        "failure_class": failure_class if failure_class is not None else (None if accepted else "gate"),
        "duration_ms": 1200,
        "first_output_ms": 90,
        "tool_steps": 2,
        "request_injection_evidence": {"schema_version": "rightsize-request-injection/v1"},
        "identity_evidence": identity
        if identity is not None
        else {"verified": True, "identity_basis": "gateway_attribution_log", "records": [attribution()]},
        "attribution_log_skipped_lines": 0,
        "effort_readback": "unavailable",
        "context_readback": "unavailable",
        "output_sha256": None,
        "usage": {"total_tokens": 400},
        "cost": {"api_equivalent_cost_usd": 0.02},
    }


def attempts_for(
    accepted: int,
    *,
    tasks: int = 5,
    per_task: int = 3,
    task_class: str = CLASS,
    route_id: str = ROUTE_ID,
    critical: bool = False,
) -> list[dict]:
    """Build `tasks * per_task` attempts of which exactly `accepted` were accepted."""
    records: list[dict] = []
    for index in range(tasks * per_task):
        records.append(
            attempt(
                f"task-{index // per_task}",
                index < accepted,
                task_class=task_class,
                route_id=route_id,
                critical=critical,
            )
        )
    return records


def evidence_for(
    records: list[dict],
    *,
    depth: str = "qualification",
    target_representative: bool = True,
    provenance: str = "observed",
    task_class: str = CLASS,
    routes: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "rightsize-evidence/v1",
        "evaluator_version": RIGHTSIZE.EVALUATOR_VERSION,
        "evaluator_sha256": "0" * 64,
        "evaluation_policy_sha256": "1" * 64,
        "task_pack_policy_sha256": "2" * 64,
        "runtime_policy_sha256": "3" * 64,
        "launcher_sha256": "4" * 64,
        "captured_at": "2026-08-20T10:00:00Z",
        "authorization_digest": "5" * 64,
        "target_identity_sha256": "6" * 64,
        "catalog_sha256": "7" * 64,
        "benchmark_snapshot_sha256": "8" * 64,
        "run_spec": {"evaluation_depth": depth, "task_classes": [task_class]},
        "task_pack": {"id": "pack", "target_representative": target_representative},
        "route_registry": [
            {
                "route": route,
                "discovery_state": {},
                "context_state": {},
                "evaluation_eligible": True,
                "blockers": [],
            }
            for route in (routes if routes is not None else [ROUTE])
        ],
        "attempts": records,
        "summaries": [{"route_id": ROUTE_ID, "task_class": task_class, "provenance": provenance}],
        "route_probes": [],
        "measured_pareto_fronts": {},
        "dispatch_pareto_fronts": {},
        "limitations": [],
    }


class Harness(unittest.TestCase):
    """Run the command line in process so exit codes and emitted documents are both asserted."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name: str, document: object) -> str:
        path = self.root / name
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return str(path)

    def run_command(self, argv: list[str]) -> tuple[int, object, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = QUALIFICATION.main(argv)
        stdout = out.getvalue()
        return code, (json.loads(stdout) if stdout.strip() else None), err.getvalue()

    def issue(self, evidence: dict, *, task_class: str = CLASS, issued_at: str = "2026-08-20T12:00:00Z") -> dict:
        path = self.write(f"evidence-{hashlib.sha256(issued_at.encode()).hexdigest()[:8]}.json", evidence)
        code, document, stderr = self.run_command(
            ["issue", "--evidence", path, "--route-id", ROUTE_ID, "--task-class", task_class, "--issued-at", issued_at]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(document, dict)
        return document

    def issue_refusal(self, evidence: dict, **kwargs: str) -> str:
        path = self.write("evidence-refused.json", evidence)
        argv = [
            "issue",
            "--evidence",
            path,
            "--route-id",
            kwargs.get("route_id", ROUTE_ID),
            "--task-class",
            kwargs.get("task_class", CLASS),
            "--issued-at",
            kwargs.get("issued_at", "2026-08-20T12:00:00Z"),
        ]
        code, document, stderr = self.run_command(argv)
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIsNone(document)
        return json.loads(stderr)["reason"]

    def store(self, generations: list[dict], quarantines: list[dict] | None = None, recoveries: list[dict] | None = None) -> dict:
        return {
            "schema_version": POLICY["verdict_schema_versions"]["store"],
            "generations": generations,
            "quarantines": quarantines or [],
            "recoveries": recoveries or [],
        }

    def admit(
        self,
        store: dict,
        *,
        task_class: str = CLASS,
        route_id: str = ROUTE_ID,
        at: str = "2026-08-25T00:00:00Z",
        provider: str | None = "openai",
        model: str | None = "gpt-5.6-luna",
        route_kind: str | None = None,
        name: str = "store.json",
    ) -> dict:
        path = self.write(name, store)
        argv = ["admit", "--store", path, "--route-id", route_id, "--task-class", task_class, "--at", at]
        if provider is not None:
            argv += ["--observed-provider", provider]
        if model is not None:
            argv += ["--observed-model-id", model]
        if route_kind is not None:
            argv += ["--observed-route-kind", route_kind]
        code, document, stderr = self.run_command(argv)
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(document, dict)
        return document

    def qualified_generation(self, **kwargs: str) -> dict:
        """One current qualified generation for the standard cell, at the floor's minimum sample."""
        return self.issue(evidence_for(attempts_for(14)), **kwargs)


class FloorBoundaryTests(Harness):
    """The promotion floor at its exact edge, in both directions.

    The samples are chosen so each requirement can be seen doing its own work: 14/15 clears both
    the accepted-rate and the Wilson bound by the narrowest margin, while 18/20 meets the 90%
    accepted rate EXACTLY and still fails, because at twenty attempts the interval is wider than
    the bound allows. 27/30 is the same 90% rate at a sample large enough to pass.
    """

    def test_the_minimum_qualifying_sample_qualifies(self) -> None:
        generation = self.issue(evidence_for(attempts_for(14)))
        self.assertEqual(generation["verdict"], "qualified")
        self.assertEqual(generation["unmet_requirements"], [])
        measured = generation["measured"]
        self.assertEqual((measured["accepted"], measured["attempts"]), (14, 15))
        self.assertEqual(measured["distinct_tasks"], FLOOR["minimum_distinct_tasks"])
        self.assertEqual(measured["minimum_attempts_per_task_observed"], FLOOR["minimum_attempts_per_task"])
        self.assertGreaterEqual(measured["wilson_95"]["lower"], FLOOR["minimum_wilson_lower_bound"])
        # The margin is genuinely narrow: this is the boundary, not a comfortable pass.
        self.assertLess(measured["wilson_95"]["lower"], FLOOR["minimum_wilson_lower_bound"] + 0.01)

    def test_one_fewer_accepted_attempt_fails_the_floor(self) -> None:
        generation = self.issue(evidence_for(attempts_for(13)))
        self.assertEqual(generation["verdict"], "unqualified")
        self.assertEqual(
            generation["unmet_requirements"],
            ["accepted-rate-below-floor", "wilson-lower-bound-below-floor"],
        )
        self.assertLess(generation["measured"]["accepted_rate"], FLOOR["minimum_accepted_rate"])

    def test_exactly_ninety_percent_still_fails_when_the_sample_is_too_small(self) -> None:
        generation = self.issue(evidence_for(attempts_for(18, per_task=4)))
        self.assertEqual(generation["measured"]["accepted_rate"], FLOOR["minimum_accepted_rate"])
        self.assertEqual(generation["verdict"], "unqualified")
        self.assertEqual(generation["unmet_requirements"], ["wilson-lower-bound-below-floor"])

    def test_the_same_rate_qualifies_once_the_sample_is_large_enough(self) -> None:
        generation = self.issue(evidence_for(attempts_for(27, per_task=6)))
        self.assertEqual(generation["measured"]["accepted_rate"], FLOOR["minimum_accepted_rate"])
        self.assertEqual(generation["verdict"], "qualified")

    def test_every_other_floor_requirement_is_named_and_each_has_a_control(self) -> None:
        control = self.issue(evidence_for(attempts_for(15)))
        self.assertEqual(control["verdict"], "qualified")

        cases = {
            "fewer-than-minimum-distinct-tasks": evidence_for(attempts_for(12, tasks=4, per_task=3)),
            "fewer-than-minimum-attempts-per-task": evidence_for(attempts_for(10, tasks=5, per_task=2)),
            "evaluation-depth-is-not-qualification": evidence_for(attempts_for(15), depth="pilot"),
            "task-pack-is-not-target-representative": evidence_for(
                attempts_for(15), target_representative=False
            ),
        }
        for requirement, evidence in cases.items():
            with self.subTest(requirement=requirement):
                generation = self.issue(evidence)
                self.assertEqual(generation["verdict"], "unqualified")
                self.assertIn(requirement, generation["unmet_requirements"])

    def test_a_route_or_identity_failure_blocks_an_otherwise_passing_sample(self) -> None:
        records = attempts_for(15)
        control = self.issue(evidence_for(copy.deepcopy(records)))
        self.assertEqual(control["verdict"], "qualified")

        records[0] = attempt(
            "task-0",
            False,
            failure_class="identity",
            identity={"verified": True, "identity_basis": "gateway_attribution_log", "records": [attribution()]},
        )
        generation = self.issue(evidence_for(records))
        self.assertEqual(generation["verdict"], "unqualified")
        self.assertIn("route-or-identity-failure-present", generation["unmet_requirements"])

    def test_a_failed_critical_task_blocks_an_otherwise_passing_sample(self) -> None:
        records = attempts_for(14, critical=True)
        generation = self.issue(evidence_for(records))
        self.assertEqual(generation["verdict"], "unqualified")
        self.assertIn("critical-task-failure-present", generation["unmet_requirements"])
        # Control: the same critical marking with every attempt accepted qualifies.
        clean = self.issue(evidence_for(attempts_for(15, critical=True)))
        self.assertEqual(clean["verdict"], "qualified")

    def test_authority_or_frontier_requires_every_task_marked_critical(self) -> None:
        noncritical = self.issue(
            evidence_for(attempts_for(15, task_class="authority_or_frontier"), task_class="authority_or_frontier"),
            task_class="authority_or_frontier",
        )
        self.assertEqual(noncritical["verdict"], "unqualified")
        self.assertEqual(
            noncritical["unmet_requirements"], ["authority-or-frontier-task-not-marked-critical"]
        )
        critical = self.issue(
            evidence_for(
                attempts_for(15, task_class="authority_or_frontier", critical=True),
                task_class="authority_or_frontier",
            ),
            task_class="authority_or_frontier",
        )
        self.assertEqual(critical["verdict"], "qualified")


class SingleFloorImplementationTests(Harness):
    """Decision 49's "one rightsizing evaluator" has to be literally one implementation."""

    def test_the_qualification_policy_states_no_threshold_of_its_own(self) -> None:
        """A second copy of any threshold could disagree with the evaluator that measures it.

        Asserted as the absence of any number at all outside the freshness horizons, rather than as
        the absence of each floor value: the floor's `0` and `3` occur as substrings of unrelated
        prose, so a text search would fail on "Decision 30" while missing a genuine `0.7` added as
        a new key later.
        """

        def numbers(value: object) -> list[float]:
            if isinstance(value, bool):
                return []
            if isinstance(value, (int, float)):
                return [float(value)]
            if isinstance(value, dict):
                return [found for item in value.values() for found in numbers(item)]
            if isinstance(value, list):
                return [found for item in value for found in numbers(item)]
            return []

        without_freshness = {key: value for key, value in POLICY.items() if key != "freshness"}
        self.assertEqual(numbers(without_freshness), [])
        self.assertEqual(sorted(numbers(POLICY["freshness"])), [30.0, 90.0])
        self.assertEqual(POLICY["floor_policy_reference"], "rightsize-evaluation-v1.json#/qualification")

    def test_the_evaluator_summary_and_the_issued_generation_agree_on_every_sample(self) -> None:
        """`summarize_route` and `issue` must reach the same verdict, or the floor forked."""
        for accepted, per_task in ((13, 3), (14, 3), (15, 3), (18, 4), (27, 6)):
            with self.subTest(accepted=accepted, per_task=per_task):
                records = attempts_for(accepted, per_task=per_task)
                summary = RIGHTSIZE.summarize_route(
                    ROUTE,
                    CLASS,
                    records,
                    "qualification",
                    {"target_representative": True},
                    EVALUATION_POLICY,
                    True,
                )
                generation = self.issue(evidence_for(records))
                self.assertEqual(
                    summary["qualification_state"] == "role-qualified",
                    generation["verdict"] == "qualified",
                )
                self.assertEqual(summary["wilson_95"], generation["measured"]["wilson_95"])


class IssuanceRefusalTests(Harness):
    def test_mined_evidence_cannot_issue_a_qualification(self) -> None:
        reason = self.issue_refusal(evidence_for(attempts_for(15), provenance="mined"))
        self.assertIn("cannot issue a qualification", reason)
        # Control: the identical sample labelled observed issues a qualified generation.
        self.assertEqual(self.issue(evidence_for(attempts_for(15)))["verdict"], "qualified")

    def test_a_benchmark_document_is_refused_by_schema(self) -> None:
        document = evidence_for(attempts_for(15))
        document["schema_version"] = "model-benchmark-evidence/v1"
        self.assertIn("rightsize-evidence/v1", self.issue_refusal(document))

    def test_attempts_whose_attribution_names_another_provider_cannot_qualify_the_route(self) -> None:
        records = attempts_for(15)
        records[0]["identity_evidence"]["records"] = [attribution(provider="anthropic", model="claude-sonnet-5")]
        reason = self.issue_refusal(evidence_for(records))
        self.assertIn("do not correlate to the route being qualified", reason)
        self.assertIn("anthropic", reason)

    def test_a_default_provider_fallthrough_in_the_evidence_cannot_qualify(self) -> None:
        records = attempts_for(15)
        records[3]["identity_evidence"]["records"] = [attribution(route_kind="default-provider")]
        self.assertIn("default-provider fallthrough", self.issue_refusal(evidence_for(records)))

    def test_an_unverified_identity_flag_cannot_qualify(self) -> None:
        records = attempts_for(15)
        records[2]["identity_evidence"] = {"verified": False, "failure": "provider-mismatch"}
        self.assertIn("is not verified", self.issue_refusal(evidence_for(records)))

    def test_a_passthrough_routes_provider_is_re_derived_rather_than_taken_on_the_flag(self) -> None:
        """The passthrough route's attribution names a fixed upstream, not the route's provider."""
        passthrough = {
            **ROUTE,
            "route_kind": "gateway-claude-subscription-passthrough",
            "provider": "anthropic",
            "auth_basis": "operator-claude-login",
            "billing_basis": "claude-subscription",
            "requested_model_id": "claude-opus-4-8",
        }
        passthrough_id = QUALIFICATION.sha256_json(passthrough)

        def evidence(provider: str) -> dict:
            records = attempts_for(15, route_id=passthrough_id)
            for record in records:
                record["identity_evidence"]["records"] = [
                    attribution(provider=provider, model="claude-opus-4-8")
                ]
            document = evidence_for(records, routes=[passthrough])
            document["summaries"] = [
                {"route_id": passthrough_id, "task_class": CLASS, "provenance": "observed"}
            ]
            return document

        path = self.write("passthrough-good.json", evidence("anthropic-native"))
        code, document, stderr = self.run_command(
            [
                "issue",
                "--evidence",
                path,
                "--route-id",
                passthrough_id,
                "--task-class",
                CLASS,
                "--issued-at",
                "2026-08-20T12:00:00Z",
            ]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(document, dict)
        self.assertEqual(document["verdict"], "qualified")

        path = self.write("passthrough-bad.json", evidence("openai"))
        code, _, stderr = self.run_command(
            [
                "issue",
                "--evidence",
                path,
                "--route-id",
                passthrough_id,
                "--task-class",
                CLASS,
                "--issued-at",
                "2026-08-20T12:00:00Z",
            ]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("expects anthropic-native", json.loads(stderr)["reason"])

    def test_an_uncharacterized_route_kind_is_refused_rather_than_treated_as_passthrough(self) -> None:
        invented = {**ROUTE, "route_kind": "direct-vendor-sdk"}
        invented_id = QUALIFICATION.sha256_json(invented)
        records = attempts_for(15, route_id=invented_id)
        document = evidence_for(records, routes=[invented])
        document["summaries"] = [{"route_id": invented_id, "task_class": CLASS, "provenance": "observed"}]
        path = self.write("invented.json", document)
        code, _, stderr = self.run_command(
            [
                "issue",
                "--evidence",
                path,
                "--route-id",
                invented_id,
                "--task-class",
                CLASS,
                "--issued-at",
                "2026-08-20T12:00:00Z",
            ]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("is uncharacterized", json.loads(stderr)["reason"])
        # Control: both declared route kinds are accepted.
        self.assertEqual(
            set(EVALUATION_POLICY["route_kinds"]),
            {"gateway-routed-provider", "gateway-claude-subscription-passthrough"},
        )
        self.assertEqual(self.issue(evidence_for(attempts_for(15)))["verdict"], "qualified")

    def test_a_route_absent_from_the_evidence_registry_cannot_be_qualified(self) -> None:
        document = evidence_for(attempts_for(15), routes=[OTHER_ROUTE])
        self.assertIn("no route in the evidence registry digests", self.issue_refusal(document))

    def test_a_cell_with_no_recorded_attempt_is_refused_rather_than_declared_unqualified(self) -> None:
        reason = self.issue_refusal(evidence_for(attempts_for(15)), task_class=SIBLING_CLASS)
        self.assertIn("records no attempt", reason)

    def test_an_unrecognized_task_class_is_refused(self) -> None:
        self.assertIn(
            "not one of the eight task classes",
            self.issue_refusal(evidence_for(attempts_for(15)), task_class="freestyle"),
        )

    def test_only_one_timestamp_spelling_is_admitted(self) -> None:
        for spelling in ("2026-08-20T12:00:00+00:00", "2026-08-20", "2026-08-20T12:00:00.500Z"):
            with self.subTest(spelling=spelling):
                self.assertIn(
                    "is not a %Y-%m-%dT%H:%M:%SZ timestamp",
                    self.issue_refusal(evidence_for(attempts_for(15)), issued_at=spelling),
                )
        self.assertEqual(
            self.issue(evidence_for(attempts_for(15)), issued_at="2026-08-20T12:00:00Z")["verdict"],
            "qualified",
        )


class GenerationImmutabilityTests(Harness):
    def test_a_generation_names_itself_by_digest(self) -> None:
        generation = self.qualified_generation()
        body = {key: value for key, value in generation.items() if key != "generation_id"}
        self.assertEqual(generation["generation_id"], QUALIFICATION.sha256_json(body))

    def test_an_edited_generation_stops_naming_itself_and_the_store_is_refused(self) -> None:
        generation = self.qualified_generation()
        control = self.write("control.json", self.store([generation]))
        code, document, _ = self.run_command(["validate", "--store", control])
        self.assertEqual((code, document["status"]), (QUALIFICATION.EXIT_OK, "valid"))

        tampered = copy.deepcopy(generation)
        tampered["verdict"] = "qualified"
        tampered["measured"]["accepted"] = 15
        path = self.write("tampered.json", self.store([tampered]))
        code, document, _ = self.run_command(["validate", "--store", path])
        self.assertEqual(document["status"], "invalid")
        self.assertIn("generation_id does not digest its own content", " ".join(document["errors"]))

    def test_a_generation_promoted_by_hand_is_refused_by_its_own_unmet_requirements(self) -> None:
        """Flipping only the verdict leaves the record contradicting itself, and re-digesting it
        still leaves the unmet requirements it was issued with."""
        unqualified = self.issue(evidence_for(attempts_for(13)))
        forged = copy.deepcopy(unqualified)
        forged["verdict"] = "qualified"
        forged = QUALIFICATION.finalize_generation(forged, POLICY)
        path = self.write("forged.json", self.store([forged]))
        code, document, _ = self.run_command(["validate", "--store", path])
        self.assertEqual(document["status"], "invalid")
        self.assertIn("verdict contradicts its own unmet_requirements", " ".join(document["errors"]))

    def test_a_repeated_generation_id_is_refused(self) -> None:
        generation = self.qualified_generation()
        path = self.write("duplicate.json", self.store([generation, copy.deepcopy(generation)]))
        code, document, _ = self.run_command(["validate", "--store", path])
        self.assertEqual(document["status"], "invalid")
        self.assertIn("repeats generation_id", " ".join(document["errors"]))

    def test_a_route_id_that_does_not_digest_its_route_is_refused(self) -> None:
        generation = copy.deepcopy(self.qualified_generation())
        generation["route"] = OTHER_ROUTE
        generation = QUALIFICATION.finalize_generation(generation, POLICY)
        path = self.write("mismatched.json", self.store([generation]))
        _, document, _ = self.run_command(["validate", "--store", path])
        self.assertIn("route_id does not digest its own route tuple", " ".join(document["errors"]))

    def test_a_store_carrying_an_unexpected_field_is_refused(self) -> None:
        store = self.store([self.qualified_generation()])
        store["dispatch_authorized"] = True
        path = self.write("extra.json", store)
        _, document, _ = self.run_command(["validate", "--store", path])
        self.assertIn("unexpected fields: dispatch_authorized", " ".join(document["errors"]))


class AdmissionTests(Harness):
    def test_a_current_qualified_correlated_cell_admits(self) -> None:
        verdict = self.admit(self.store([self.qualified_generation()]))
        self.assertEqual(verdict["verdict"], "admit-dispatch")
        self.assertIsNone(verdict["reason"])
        self.assertFalse(verdict["quarantine_required"])
        self.assertEqual(verdict["expires_at"], "2026-09-19T12:00:00Z")
        # Admission is qualification evidence and says so; it is not dispatch authorization.
        self.assertIn("separate", verdict["authority_boundary"])

    def test_admission_never_writes_to_the_store(self) -> None:
        path = Path(self.write("readonly.json", self.store([self.qualified_generation()])))
        before = path.read_bytes()
        self.run_command(
            [
                "admit",
                "--store",
                str(path),
                "--route-id",
                ROUTE_ID,
                "--task-class",
                CLASS,
                "--at",
                "2026-08-25T00:00:00Z",
                "--observed-provider",
                "openai",
                "--observed-model-id",
                "gpt-5.6-luna",
            ]
        )
        self.assertEqual(path.read_bytes(), before)

    def test_an_unmeasured_cell_refuses_without_claiming_it_failed(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, task_class=SIBLING_CLASS)
        self.assertEqual(verdict["reason"], "no-generation-for-cell")
        self.assertFalse(verdict["quarantine_required"])
        # Control: the measured cell in the same store admits.
        self.assertEqual(self.admit(store)["verdict"], "admit-dispatch")

    def test_an_unqualified_current_generation_refuses_and_names_what_it_missed(self) -> None:
        store = self.store([self.issue(evidence_for(attempts_for(13)))])
        verdict = self.admit(store)
        self.assertEqual(verdict["reason"], "generation-unqualified")
        self.assertIn("accepted-rate-below-floor", verdict["detail"])
        # Control: the same cell measured one attempt better admits.
        self.assertEqual(self.admit(self.store([self.qualified_generation()]))["verdict"], "admit-dispatch")

    def test_a_newer_unqualified_generation_supersedes_an_older_qualified_one(self) -> None:
        """A cell that regressed must not stay dispatchable on the strength of old evidence."""
        older = self.qualified_generation(issued_at="2026-08-20T12:00:00Z")
        newer = self.issue(evidence_for(attempts_for(13)), issued_at="2026-08-22T12:00:00Z")
        verdict = self.admit(self.store([older, newer]))
        self.assertEqual(verdict["reason"], "generation-unqualified")
        self.assertEqual(verdict["selected_generation_id"], newer["generation_id"])
        # Control: with the order of events reversed, the newer qualified generation admits.
        recovered = self.qualified_generation(issued_at="2026-08-23T12:00:00Z")
        self.assertEqual(
            self.admit(self.store([older, newer, recovered]))["selected_generation_id"],
            recovered["generation_id"],
        )


class FreshnessTests(Harness):
    """Decision 41's 30-day horizon, at the day either side of it."""

    def test_the_last_in_window_instant_admits_and_the_next_second_does_not(self) -> None:
        store = self.store([self.qualified_generation()])
        inside = self.admit(store, at="2026-09-19T12:00:00Z")
        self.assertEqual(inside["verdict"], "admit-dispatch")
        outside = self.admit(store, at="2026-09-19T12:00:01Z")
        self.assertEqual(outside["reason"], "qualification-expired")
        self.assertIn("only a qualification refresh renews it", outside["detail"])

    def test_the_horizon_is_the_policys_own_number(self) -> None:
        days = POLICY["freshness"]["route_class_qualification_max_age_days"]
        self.assertEqual(days, 30)
        generation = self.qualified_generation()
        issued = QUALIFICATION.parse_timestamp(generation["issued_at"], "issued_at", POLICY)
        expires = QUALIFICATION.parse_timestamp(generation["expires_at"], "expires_at", POLICY)
        self.assertEqual((expires - issued).days, days)

    def test_mined_evidence_carries_a_separate_horizon_that_cannot_promote(self) -> None:
        self.assertEqual(POLICY["freshness"]["mined_evidence_max_age_days"], 90)
        self.assertEqual(POLICY["evidence_provenance_admissible_for_issue"], ["observed"])
        self.assertFalse(EVALUATION_POLICY["promotion"]["mined_evidence_may_promote"])

    def test_a_stale_generation_cannot_be_renewed_by_a_second_probe(self) -> None:
        """Decision 50: one lifecycle layer never renews another. The surface exposes no verb that
        could refresh freshness without re-issuing from evidence."""
        verbs = set(QUALIFICATION.COMMANDS)
        self.assertEqual(verbs, {"issue", "validate", "admit", "quarantine", "recover"})
        for forbidden in ("probe", "refresh", "configure", "credential", "disable", "dispatch"):
            self.assertNotIn(forbidden, verbs)


class FloorDriftTests(Harness):
    def test_a_generation_issued_under_a_different_floor_is_refused(self) -> None:
        generation = copy.deepcopy(self.qualified_generation())
        control = self.admit(self.store([generation]), name="control.json")
        self.assertEqual(control["verdict"], "admit-dispatch")

        generation["floor_policy_sha256"] = "f" * 64
        drifted = QUALIFICATION.finalize_generation(generation, POLICY)
        verdict = self.admit(self.store([drifted]), name="drifted.json")
        self.assertEqual(verdict["reason"], "floor-policy-drift")
        self.assertIn("never measured against the floor in force now", verdict["detail"])

    def test_the_recorded_floor_digest_binds_the_qualification_block_alone(self) -> None:
        """A budget edit must not expire every generation; a threshold edit must."""
        self.assertEqual(
            self.qualified_generation()["floor_policy_sha256"],
            QUALIFICATION.sha256_json(FLOOR),
        )
        unrelated = copy.deepcopy(EVALUATION_POLICY)
        unrelated["budget_limits"]["max_calls"] = 999
        self.assertEqual(
            QUALIFICATION.sha256_json(unrelated["qualification"]), QUALIFICATION.sha256_json(FLOOR)
        )
        threshold = copy.deepcopy(EVALUATION_POLICY)
        threshold["qualification"]["minimum_wilson_lower_bound"] = 0.6
        self.assertNotEqual(
            QUALIFICATION.sha256_json(threshold["qualification"]), QUALIFICATION.sha256_json(FLOOR)
        )


class AmbiguousSelectionTests(Harness):
    def test_two_distinct_generations_at_the_same_instant_refuse_rather_than_pick_one(self) -> None:
        first = self.qualified_generation()
        second = self.issue(evidence_for(attempts_for(15)))
        self.assertNotEqual(first["generation_id"], second["generation_id"])
        self.assertEqual(first["issued_at"], second["issued_at"])
        verdict = self.admit(self.store([first, second]))
        self.assertEqual(verdict["reason"], "ambiguous-current-generation")
        self.assertIn("no single current generation", verdict["detail"])

    def test_list_order_does_not_decide_the_ambiguous_case(self) -> None:
        first = self.qualified_generation()
        second = self.issue(evidence_for(attempts_for(15)))
        for order in ([first, second], [second, first]):
            with self.subTest(order=[generation["generation_id"][:8] for generation in order]):
                self.assertEqual(
                    self.admit(self.store(order), name="ordered.json")["reason"],
                    "ambiguous-current-generation",
                )
        # Control: one of the two alone admits, so the refusal is about the pair.
        self.assertEqual(self.admit(self.store([first]), name="single.json")["verdict"], "admit-dispatch")


class IdentityCorrelationTests(Harness):
    def test_an_uncorrelated_identity_refuses_and_names_an_identity_mismatch_quarantine(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, provider="anthropic", model="claude-sonnet-5")
        self.assertEqual(verdict["reason"], "route-identity-uncorrelated")
        self.assertTrue(verdict["quarantine_required"])
        self.assertEqual(verdict["quarantine_cause"], "identity-mismatch")
        # Control: the correlated identity over the same store admits.
        self.assertEqual(self.admit(store)["verdict"], "admit-dispatch")

    def test_a_matching_model_on_the_wrong_provider_is_still_uncorrelated(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, provider="openrouter", model="gpt-5.6-luna")
        self.assertEqual(verdict["reason"], "route-identity-uncorrelated")

    def test_a_matching_provider_serving_another_model_is_still_uncorrelated(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, provider="openai", model="gpt-5.6-sol")
        self.assertEqual(verdict["reason"], "route-identity-uncorrelated")

    def test_missing_identity_evidence_refuses_rather_than_assuming_the_route(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, provider=None, model=None)
        self.assertEqual(verdict["reason"], "identity-evidence-missing")
        self.assertFalse(verdict["quarantine_required"])
        self.assertEqual(self.admit(store)["verdict"], "admit-dispatch")

    def test_a_default_provider_route_decision_is_a_quarantine_event(self) -> None:
        store = self.store([self.qualified_generation()])
        verdict = self.admit(store, route_kind="default-provider")
        self.assertEqual(verdict["reason"], "default-provider-fallthrough")
        self.assertEqual(verdict["quarantine_cause"], "default-provider-fallthrough")
        # Control: any other route decision with the same identity admits.
        self.assertEqual(self.admit(store, route_kind="model-alias")["verdict"], "admit-dispatch")

    def test_a_namespaced_route_correlates_against_the_upstreams_bare_id(self) -> None:
        namespaced = {**ROUTE, "provider": "muse", "requested_model_id": "muse/muse-spark-1.2"}
        generation = copy.deepcopy(self.qualified_generation())
        generation["route"] = namespaced
        generation["route_id"] = QUALIFICATION.sha256_json(namespaced)
        generation = QUALIFICATION.finalize_generation(generation, POLICY)
        store = self.store([generation])
        admitted = self.admit(
            store, route_id=generation["route_id"], provider="muse", model="muse-spark-1.2"
        )
        self.assertEqual(admitted["verdict"], "admit-dispatch")
        # The provider prefix is never dropped from the provider comparison itself.
        refused = self.admit(
            store, route_id=generation["route_id"], provider="openai", model="muse-spark-1.2"
        )
        self.assertEqual(refused["reason"], "route-identity-uncorrelated")

    def test_the_provider_comparison_is_exact_and_strips_no_prefix(self) -> None:
        """The model comparison tolerates a namespace; the provider comparison must not.

        Without this control the tolerance could be widened to the provider field without any test
        noticing, and a provider string that merely ENDS in the qualified provider's name would
        correlate — which is the one field a default-provider fallthrough gets wrong.
        """
        store = self.store([self.qualified_generation()])
        for spelling in ("gateway/openai", "not-openai/openai", "openai/openai"):
            with self.subTest(provider=spelling):
                verdict = self.admit(store, provider=spelling, model="gpt-5.6-luna", name="p.json")
                self.assertEqual(verdict["reason"], "route-identity-uncorrelated")
        self.assertEqual(self.admit(store, provider="openai")["verdict"], "admit-dispatch")


class QuarantineTests(Harness):
    def quarantine(self, store: dict, **kwargs: str) -> tuple[int, object, str]:
        path = self.write("to-quarantine.json", store)
        argv = [
            "quarantine",
            "--store",
            path,
            "--route-id",
            kwargs.get("route_id", ROUTE_ID),
            "--task-class",
            kwargs.get("task_class", CLASS),
            "--cause",
            kwargs.get("cause", "identity-mismatch"),
            "--at",
            kwargs.get("at", "2026-08-25T01:00:00Z"),
        ]
        return self.run_command(argv)

    def two_class_store(self) -> dict:
        primary = self.qualified_generation()
        sibling = self.issue(
            evidence_for(attempts_for(15, task_class=SIBLING_CLASS), task_class=SIBLING_CLASS),
            task_class=SIBLING_CLASS,
        )
        return self.store([primary, sibling])

    def test_a_quarantine_blocks_the_cell_and_preserves_the_last_good_generation(self) -> None:
        store = self.store([self.qualified_generation()])
        self.assertEqual(self.admit(store, name="before.json")["verdict"], "admit-dispatch")

        code, quarantined, stderr = self.quarantine(store)
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(quarantined, dict)
        self.assertEqual(quarantined["generations"], store["generations"])
        self.assertEqual(len(quarantined["quarantines"]), 1)

        verdict = self.admit(quarantined, at="2026-08-26T00:00:00Z", name="after.json")
        self.assertEqual(verdict["reason"], "cell-quarantined")
        self.assertIn("re-qualify the cell", verdict["detail"])

    def test_a_quarantine_scopes_to_the_exact_cell_and_not_its_siblings(self) -> None:
        store = self.two_class_store()
        code, quarantined, stderr = self.quarantine(store)
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(quarantined, dict)
        self.assertEqual(
            self.admit(quarantined, at="2026-08-26T00:00:00Z", name="q.json")["reason"],
            "cell-quarantined",
        )
        sibling = self.admit(
            quarantined, task_class=SIBLING_CLASS, at="2026-08-26T00:00:00Z", name="s.json"
        )
        self.assertEqual(sibling["verdict"], "admit-dispatch")

    def test_a_quarantine_on_one_route_leaves_another_route_in_the_same_class_admissible(self) -> None:
        generation = self.qualified_generation()
        other = copy.deepcopy(generation)
        other["route"] = OTHER_ROUTE
        other["route_id"] = OTHER_ROUTE_ID
        other = QUALIFICATION.finalize_generation(other, POLICY)
        code, quarantined, _ = self.quarantine(self.store([generation, other]))
        assert isinstance(quarantined, dict)
        self.assertEqual(
            self.admit(quarantined, at="2026-08-26T00:00:00Z", name="q.json")["reason"],
            "cell-quarantined",
        )
        self.assertEqual(
            self.admit(
                quarantined,
                route_id=OTHER_ROUTE_ID,
                at="2026-08-26T00:00:00Z",
                name="o.json",
            )["verdict"],
            "admit-dispatch",
        )

    def test_only_the_declared_quarantine_causes_are_accepted(self) -> None:
        for cause in POLICY["quarantine_causes"]:
            with self.subTest(cause=cause):
                code, document, _ = self.quarantine(self.store([self.qualified_generation()]), cause=cause)
                self.assertEqual(code, QUALIFICATION.EXIT_OK)
                assert isinstance(document, dict)
                self.assertEqual(document["quarantines"][0]["cause"], cause)
        code, document, stderr = self.quarantine(
            self.store([self.qualified_generation()]), cause="operator-hunch"
        )
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("is not a quarantine cause", json.loads(stderr)["reason"])

    def test_two_quarantines_for_one_cell_at_one_instant_are_refused(self) -> None:
        code, first, _ = self.quarantine(self.store([self.qualified_generation()]))
        assert isinstance(first, dict)
        code, _, stderr = self.quarantine(first)
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("already recorded", json.loads(stderr)["reason"])
        # Control: a second quarantine at a different instant is recorded.
        code, second, _ = self.quarantine(first, at="2026-08-25T02:00:00Z")
        self.assertEqual(code, QUALIFICATION.EXIT_OK)
        assert isinstance(second, dict)
        self.assertEqual(len(second["quarantines"]), 2)

    def test_quarantine_does_not_write_the_input_store(self) -> None:
        path = Path(self.write("to-quarantine.json", self.store([self.qualified_generation()])))
        before = path.read_bytes()
        self.quarantine(json.loads(before))
        self.assertEqual(path.read_bytes(), before)


class RecoveryTests(Harness):
    def recover(self, store: dict, generation_id: str, **kwargs: str) -> tuple[int, object, str]:
        path = self.write("to-recover.json", store)
        argv = [
            "recover",
            "--store",
            path,
            "--route-id",
            kwargs.get("route_id", ROUTE_ID),
            "--task-class",
            kwargs.get("task_class", CLASS),
            "--acknowledged-cause",
            kwargs.get("acknowledged_cause", "identity-mismatch"),
            "--recovery-generation-id",
            generation_id,
            "--at",
            kwargs.get("at", "2026-08-28T00:00:00Z"),
        ]
        return self.run_command(argv)

    def quarantined_store(self) -> dict:
        store = self.store([self.qualified_generation()])
        path = self.write("pre.json", store)
        code, quarantined, stderr = self.run_command(
            [
                "quarantine",
                "--store",
                path,
                "--route-id",
                ROUTE_ID,
                "--task-class",
                CLASS,
                "--cause",
                "identity-mismatch",
                "--at",
                "2026-08-25T01:00:00Z",
            ]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(quarantined, dict)
        return quarantined

    def test_re_qualification_after_the_failure_clears_the_quarantine(self) -> None:
        store = self.quarantined_store()
        fresh = self.qualified_generation(issued_at="2026-08-26T12:00:00Z")
        store["generations"] = [*store["generations"], fresh]

        code, recovered, stderr = self.recover(store, fresh["generation_id"])
        self.assertEqual(code, QUALIFICATION.EXIT_OK, stderr)
        assert isinstance(recovered, dict)
        # The quarantine is resolved, not erased: the history stays reviewable.
        self.assertEqual(len(recovered["quarantines"]), 1)
        self.assertEqual(len(recovered["recoveries"]), 1)
        self.assertEqual(recovered["recoveries"][0]["resolves_quarantined_at"], "2026-08-25T01:00:00Z")

        verdict = self.admit(recovered, at="2026-08-29T00:00:00Z", name="post.json")
        self.assertEqual(verdict["verdict"], "admit-dispatch")
        self.assertEqual(verdict["selected_generation_id"], fresh["generation_id"])

    def test_evidence_predating_the_quarantine_cannot_clear_it(self) -> None:
        store = self.quarantined_store()
        stale = store["generations"][0]
        code, _, stderr = self.recover(store, stale["generation_id"])
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("not after the quarantine", json.loads(stderr)["reason"])
        # Control: the same store with a later generation recovers.
        fresh = self.qualified_generation(issued_at="2026-08-26T12:00:00Z")
        store["generations"] = [*store["generations"], fresh]
        self.assertEqual(self.recover(store, fresh["generation_id"])[0], QUALIFICATION.EXIT_OK)

    def test_an_unqualified_re_measurement_leaves_the_cell_out_of_service(self) -> None:
        store = self.quarantined_store()
        failed = self.issue(evidence_for(attempts_for(13)), issued_at="2026-08-26T12:00:00Z")
        store["generations"] = [*store["generations"], failed]
        code, _, stderr = self.recover(store, failed["generation_id"])
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("re-qualification is the only exit", json.loads(stderr)["reason"])

    def test_recovery_requires_acknowledging_the_quarantines_own_cause(self) -> None:
        store = self.quarantined_store()
        fresh = self.qualified_generation(issued_at="2026-08-26T12:00:00Z")
        store["generations"] = [*store["generations"], fresh]
        code, _, stderr = self.recover(
            store, fresh["generation_id"], acknowledged_cause="default-provider-fallthrough"
        )
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("does not name this quarantine's own cause", json.loads(stderr)["reason"])
        self.assertEqual(self.recover(store, fresh["generation_id"])[0], QUALIFICATION.EXIT_OK)

    def test_recovering_an_unquarantined_cell_is_refused(self) -> None:
        generation = self.qualified_generation()
        code, _, stderr = self.recover(self.store([generation]), generation["generation_id"])
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("no unresolved quarantine exists", json.loads(stderr)["reason"])

    def test_a_recovery_citing_a_generation_the_store_does_not_hold_is_refused(self) -> None:
        store = self.quarantined_store()
        code, _, stderr = self.recover(store, "a" * 64)
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("holds no generation", json.loads(stderr)["reason"])

    def test_a_second_quarantine_after_recovery_blocks_the_cell_again(self) -> None:
        store = self.quarantined_store()
        fresh = self.qualified_generation(issued_at="2026-08-26T12:00:00Z")
        store["generations"] = [*store["generations"], fresh]
        _, recovered, _ = self.recover(store, fresh["generation_id"])
        assert isinstance(recovered, dict)
        path = self.write("again.json", recovered)
        _, requarantined, _ = self.run_command(
            [
                "quarantine",
                "--store",
                path,
                "--route-id",
                ROUTE_ID,
                "--task-class",
                CLASS,
                "--cause",
                "default-provider-fallthrough",
                "--at",
                "2026-08-30T00:00:00Z",
            ]
        )
        assert isinstance(requarantined, dict)
        verdict = self.admit(requarantined, at="2026-08-31T00:00:00Z", name="blocked.json")
        self.assertEqual(verdict["reason"], "cell-quarantined")
        self.assertIn("default-provider-fallthrough", verdict["detail"])


class ContractTests(Harness):
    def test_every_refusal_reason_the_policy_declares_is_reachable(self) -> None:
        """A declared reason no code path emits is documentation, not a control."""
        emitted = set()
        generation = self.qualified_generation()
        store = self.store([generation])
        emitted.add(self.admit(store, task_class=SIBLING_CLASS)["reason"])
        emitted.add(self.admit(self.store([self.issue(evidence_for(attempts_for(13)))]))["reason"])
        emitted.add(
            self.admit(self.store([generation, self.issue(evidence_for(attempts_for(15)))]))["reason"]
        )
        emitted.add(self.admit(store, at="2026-10-01T00:00:00Z")["reason"])
        drifted = copy.deepcopy(generation)
        drifted["floor_policy_sha256"] = "f" * 64
        emitted.add(self.admit(self.store([QUALIFICATION.finalize_generation(drifted, POLICY)]))["reason"])
        emitted.add(self.admit(store, provider="anthropic", model="claude-sonnet-5")["reason"])
        emitted.add(self.admit(store, route_kind="default-provider")["reason"])
        emitted.add(self.admit(store, provider=None, model=None)["reason"])
        path = self.write("q.json", store)
        _, quarantined, _ = self.run_command(
            [
                "quarantine",
                "--store",
                path,
                "--route-id",
                ROUTE_ID,
                "--task-class",
                CLASS,
                "--cause",
                "identity-mismatch",
                "--at",
                "2026-08-25T01:00:00Z",
            ]
        )
        assert isinstance(quarantined, dict)
        emitted.add(self.admit(quarantined, at="2026-08-26T00:00:00Z", name="qq.json")["reason"])
        self.assertEqual(emitted, set(POLICY["refusal_reasons"]))

    def test_an_undeclared_refusal_reason_cannot_be_emitted(self) -> None:
        with self.assertRaises(QUALIFICATION.InputError):
            QUALIFICATION.refusal(POLICY, ROUTE_ID, CLASS, "vibes", "no")

    def test_the_generation_carries_exactly_the_canonical_fields(self) -> None:
        self.assertEqual(
            sorted(self.qualified_generation()), sorted(POLICY["canonical_generation_fields"])
        )

    def test_the_admission_verdict_never_claims_dispatch_authority(self) -> None:
        verdict = self.admit(self.store([self.qualified_generation()]))
        self.assertIn("not authorization to dispatch", verdict["authority_boundary"])
        for forbidden in ("authorized", "approved", "dispatched", "spawn"):
            self.assertNotIn(forbidden, verdict["verdict"])

    def test_no_verb_can_reach_a_network_a_subprocess_or_a_model(self) -> None:
        """Checked against the import surface, not the prose.

        A substring search would pass only until someone wrote the word `subprocess` in a comment,
        and would keep passing if the module imported it under an alias. The imports are what
        decide whether this surface can spend a token, so those are what the test reads.
        """
        tree = ast.parse((SCRIPTS / "route_qualification.py").read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(
            imported,
            {"__future__", "argparse", "datetime", "hashlib", "importlib", "json", "pathlib", "sys", "typing"},
        )
        for forbidden in ("subprocess", "socket", "urllib", "http", "requests", "os"):
            self.assertNotIn(forbidden, imported)

    def test_help_prepares_nothing_and_exits_zero(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(io.StringIO()):
                QUALIFICATION.main(["--help"])
        self.assertEqual(raised.exception.code, 0)

    def test_an_unusable_store_is_an_input_refusal_not_a_verdict(self) -> None:
        path = self.write("broken.json", {"schema_version": "route-qualification-store/v1"})
        code, document, stderr = self.run_command(
            [
                "admit",
                "--store",
                path,
                "--route-id",
                ROUTE_ID,
                "--task-class",
                CLASS,
                "--at",
                "2026-08-25T00:00:00Z",
                "--observed-provider",
                "openai",
                "--observed-model-id",
                "gpt-5.6-luna",
            ]
        )
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIsNone(document)
        self.assertIn("not usable", json.loads(stderr)["reason"])

    def test_a_duplicate_json_member_is_refused(self) -> None:
        path = self.root / "duplicate-member.json"
        path.write_text('{"schema_version": "a", "schema_version": "b"}', encoding="utf-8")
        code, _, stderr = self.run_command(["validate", "--store", str(path)])
        self.assertEqual(code, QUALIFICATION.EXIT_INPUT)
        self.assertIn("duplicate JSON member", json.loads(stderr)["reason"])


if __name__ == "__main__":
    unittest.main()
