"""Tests for the pre-spawn RuntimeAssignment admission and the substitution classification.

Three kinds of test live here and they check different things.

The UNIT cases construct artifacts, because that is the only way to reach a combination no honest
producer would emit on demand -- a receipt whose readback fields hold its own requested values, a
host that cannot inject effort, an envelope entry that authorizes a swap while naming no authority.
They compute the receipt-side canonical form the same way the tool re-expresses it, so a shared
misreading of that form would pass both sides.

The CROSS-CHECK case closes that hole: it feeds the happy-path embedded assignment to the real
`skills/model-tier-rightsizing/scripts/receipt_admission.py` over its real command line and requires
`validated`. That producer-side validator owns the canonical form, the closed field sets, the
certified tuples, and every evidence digest, so if this module's `receipt_json` re-expression or any
constructed digest were wrong, the cross-check would fail rather than pass silently. Its own positive
control is in the same test: a mutated receipt must come back `invalid`, so the channel is shown to
discriminate.

The HOSTILE-FD cases run the tool with a stderr it cannot write to, because a diagnostic channel must
cost the display line and never the classified exit code.

Every negative assertion below carries a positive control in the same test: the unmutated artifact is
asserted to reach the good verdict first, so a test that stopped exercising its guard would also have
to stop reaching that verdict.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "runtime-assignment.py"
POLICY = ROOT / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
RECEIPT_ADMISSION = ROOT / "skills" / "model-tier-rightsizing" / "scripts" / "receipt_admission.py"

ADMISSION_SCHEMA = "agentic-sdlc/runtime-assignment-admission@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/runtime-substitution-classification@1"
REQUEST_SCHEMA = "agentic-sdlc/runtime-admission-request@1"
SERVED_SCHEMA = "agentic-sdlc/runtime-served-record@1"
RECEIPT_SCHEMA_VERSION = "runtime-assignment-receipt/v1"

ADMIT = "admit-dispatch"
REFUSE = "refuse-dispatch"
SEED = "seed-proposal"
EXACT = "exact-match"
EXPLAINED = "explained-substitution"
UNEXPLAINED = "unexplained-substitution"

EXIT_OK = 0
#: The undelivered-result code. A verdict this tool derived but could not put on stdout is neither a
#: success nor an input error, and 120 is not in the module's exit space at all.
EXIT_INTERNAL = 1
EXIT_INPUT = 2

MODEL = "claude-sonnet-5"
PROVIDER = "anthropic"
EFFORT = "high"
CONTEXT = "base"
TIER = "capable-volume"

SEED_PROPOSAL_FIELDS = (
    "title",
    "summary",
    "acceptance_criteria",
    "priority",
    "blocking",
    "scope",
    "evidence",
    "dependencies",
    "recommended_owner",
)

POSIX = os.name == "posix"


def receipt_json(value: Any) -> str:
    """`receipt_admission.canonical_json`, re-expressed: tight, sorted, ensure_ascii=False, no newline.

    The cross-check test is what keeps this honest -- it drives the real validator, which recomputes
    every digest through its own copy of this form.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_receipt_json(value: Any) -> str:
    return hashlib.sha256(receipt_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_tool_module() -> Any:
    """Import the hyphen-named tool by path, for the few unit-level predicates worth calling directly."""
    spec = importlib.util.spec_from_file_location("runtime_assignment_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assignment_binding(*, model_id: str = MODEL, provider: str = PROVIDER, effort: str = EFFORT, context: str = CONTEXT) -> dict[str, str]:
    return {"context_form": context, "effort": effort, "model_id": model_id, "provider": provider}


def build_assignment(
    *,
    requested_model_id: str = MODEL,
    resolved_model_id: str | None = None,
    provider: str = PROVIDER,
    effort: str = EFFORT,
    context: str = CONTEXT,
    resolution_state: str = "resolved",
    request_injection_status: str = "verified",
    identity_basis: str = "independent_readback",
    identity_source: str = "adapter_response_readback",
    model_readback_status: str = "verified",
    effort_readback: dict[str, Any] | None = None,
    context_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One canonical `runtime-assignment-receipt/v1` assignment, in the policy's field order.

    The default is the shape the contract calls fully admissible: resolved, injection evidenced,
    identity independently observed, and both effective readbacks HONESTLY UNAVAILABLE.
    """
    resolved = requested_model_id if resolved_model_id is None else resolved_model_id
    binding = sha256_receipt_json(
        assignment_binding(model_id=resolved, provider=provider, effort=effort, context=context)
    )
    if identity_basis == "unambiguous_exact_id_mapping":
        model_evidence: dict[str, Any] = {
            "source_kind": "policy_exact_id_mapping",
            "status": "unavailable",
            "schema": "runtime-assignment-policy-v1",
            "reference": "model-provider-map",
            "mapped_provider": provider,
            "mapped_model_id": resolved,
            "assignment_binding_sha256": binding,
        }
    else:
        model_evidence = {
            "source_kind": "transport_readback",
            "status": "verified",
            "schema": "runtime-assignment-readback/v1",
            "observed_provider": provider,
            "observed_model_id": resolved,
            "observed_identity_source": identity_source,
            "readback_bytes_sha256": sha256_receipt_json({"model_id": resolved, "provider": provider}),
            "assignment_binding_sha256": binding,
        }
    effort_block = effort_readback or unavailable_readback(binding)
    context_block = context_readback or unavailable_readback(binding)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "requested_model_id": requested_model_id,
        "requested_effort": effort,
        "requested_context_form": context,
        "request_injection_status": request_injection_status,
        "request_injection_evidence": {
            "source_kind": "immutable_request_receipt",
            "status": "verified",
            "schema": "launcher-request-evidence/v1",
            "adapter_id": "workflow-agent-call",
            "adapter_version": "1",
            "adapter_config_sha256": sha256_receipt_json({"injects": ["model", "effort"]}),
            "request_bytes_sha256": sha256_receipt_json(
                {"context_form": context, "effort": effort, "model_id": requested_model_id}
            ),
        },
        "resolution_state": resolution_state,
        "resolved_provider": provider,
        "resolved_model_id": resolved,
        "model_identity_basis": identity_basis,
        "model_readback_status": model_readback_status,
        "model_readback_evidence": model_evidence,
        "effort_readback_status": effort_block["status"],
        "effort_readback_evidence": effort_block["evidence"],
        "effort_effective_divergence": effort_block["divergence"],
        "context_readback_status": context_block["status"],
        "context_readback_evidence": context_block["evidence"],
        "context_effective_divergence": context_block["divergence"],
    }


def unavailable_readback(binding: str) -> dict[str, Any]:
    """An honestly unavailable effective readback: no value, and divergence unavailable."""
    return {
        "status": "unavailable",
        "divergence": "unavailable",
        "evidence": {
            "source_kind": "transport_readback",
            "status": "unavailable",
            "schema": "runtime-assignment-readback/v1",
            "assignment_binding_sha256": binding,
        },
    }


def verified_readback(
    axis: str,
    observed: str,
    *,
    requested: str,
    binding: str,
    response_bytes: str | None = None,
    pointer: str = "/effective/value",
    divergence: str | None = None,
    digest: str | None = None,
    drop: tuple[str, ...] = (),
) -> dict[str, Any]:
    """A verified effective readback bound to transport bytes at a named position."""
    body = response_bytes if response_bytes is not None else json.dumps({"effective": {"value": observed}})
    value_key = "observed_effort" if axis == "effort" else "observed_context_form"
    state = "matches_requested" if observed == requested else "diverges_from_requested"
    evidence: dict[str, Any] = {
        "source_kind": "transport_readback",
        "status": "verified",
        "schema": "runtime-assignment-readback/v1",
        value_key: observed,
        "response_bytes": body,
        "observed_value_pointer": pointer,
        "readback_bytes_sha256": digest if digest is not None else sha256_text(body),
        "effective_value_state": state,
        "assignment_binding_sha256": binding,
    }
    for key in drop:
        evidence.pop(key, None)
    return {
        "status": "verified",
        "divergence": state if divergence is None else divergence,
        "evidence": evidence,
    }


def build_request(
    *,
    node: str = "implementer-a",
    tier: Any = TIER,
    injects_model: Any = True,
    injects_effort: Any = True,
    host_injection: Any = None,
    assignment: dict[str, Any] | None = None,
    drop_tier: bool = False,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "node": node,
        "requested_tier": tier,
        "host_injection": {
            "host": "claude-code",
            "surface": "workflow_agent_call",
            "injects_model": injects_model,
            "injects_effort": injects_effort,
        }
        if host_injection is None
        else host_injection,
        "assignment": assignment if assignment is not None else build_assignment(),
    }
    if drop_tier:
        del request["requested_tier"]
    if host_injection == "absent":
        del request["host_injection"]
    return request


def build_served(
    *,
    node: str = "implementer-a",
    requested_model: str = MODEL,
    requested_effort: str = EFFORT,
    requested_context: str = CONTEXT,
    served_model: Any = MODEL,
    served_provider: Any = PROVIDER,
    identity_status: str = "verified",
    identity_source: Any = "adapter_response_readback",
    identity_basis: Any = "independent_readback",
    request_injection_status: str = "verified",
    effort_status: str = "unavailable",
    served_effort: Any = None,
    context_status: str = "unavailable",
    served_context: Any = None,
    envelope: Any = None,
    drop_served: tuple[str, ...] = (),
) -> dict[str, Any]:
    served: dict[str, Any] = {
        "identity_status": identity_status,
        "identity_source": identity_source,
        "identity_basis": identity_basis,
        "request_injection_status": request_injection_status,
        "provider": served_provider,
        "model_id": served_model,
        "effort_readback_status": effort_status,
        "context_readback_status": context_status,
    }
    if served_effort is not None:
        served["effort"] = served_effort
    if served_context is not None:
        served["context_form"] = served_context
    # ABSENT is not the same document as null, and the identity-honesty rule has to admit both, so
    # the absent shape needs its own construction rather than a `None` that writes the key anyway.
    for key in drop_served:
        served.pop(key, None)
    record: dict[str, Any] = {
        "schema": SERVED_SCHEMA,
        "node": node,
        "requested": {
            "model_id": requested_model,
            "effort": requested_effort,
            "context_form": requested_context,
        },
        "served": served,
    }
    if envelope is not None:
        record["authorized_substitutions"] = envelope
    return record


def authorization(
    *,
    axis: str,
    from_value: Any,
    to_value: Any,
    to_provider: Any = None,
    authorized_by: Any = "the approved wave plan's predeclared fallback",
    approved_in: Any = "wave-2026-08-19/plan.md#routes",
) -> dict[str, Any]:
    return {
        "axis": axis,
        "from": from_value,
        "to": to_value,
        "to_provider": to_provider,
        "authorized_by": authorized_by,
        "approved_in": approved_in,
    }


def _run_with_hostile_stderr(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stderr this process CANNOT write to. Returns (exit code, stdout bytes).

    Re-expressed from the fixture `tests.test_activation_result` uses for the identical rule, not
    imported across test modules. Two shapes, kept separate because they produce DIFFERENT wrong exit
    codes and neither is exotic:

        closed  `2>&-`. CPython then starts with `sys.stderr is None`, so the FIRST
                `sys.stderr.write` raises `AttributeError` and exit 2 becomes exit 1.
        epipe   fd 2 is the write end of a pipe whose reader is already closed, so every write raises
                `EPIPE` and leaves bytes pending that CPython flushes again while finalizing, which
                replaces the exit code with 120.

    Stderr is deliberately NOT captured: capturing it would hand the child a writable stream and test
    nothing.
    """
    if mode == "closed":
        proc = subprocess.run(
            ["sh", "-c", 'exec 2>&-; exec "$@"', "sh", *argv],
            stdout=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
        )
        return proc.returncode, proc.stdout
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stderr mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=write_fd, cwd=str(cwd))
    finally:
        os.close(write_fd)
    assert child.stdout is not None
    with child.stdout as stream:
        out = stream.read()
    return child.wait(), out


def _run_with_hostile_stdout(argv: list[str], *, mode: str, cwd: Path) -> tuple[int, bytes]:
    """Run argv with a stdout this process CANNOT write to. Returns (exit code, stderr bytes).

    The mirror of `_run_with_hostile_stderr`, and a DIFFERENT contract: stdout carries the one result
    document, so the tool may not deliver it and may not pretend it did. The two modes fail
    differently for the same reasons as on stderr -- `1>&-` leaves `sys.stdout is None`, and a pipe
    whose reader is gone makes every write `EPIPE` and leaves bytes for the shutdown flush to turn
    into 120.

    Stdout is deliberately NOT captured: capturing it would hand the child a writable stream.
    """
    if mode == "closed":
        proc = subprocess.run(
            ["sh", "-c", 'exec 1>&-; exec "$@"', "sh", *argv],
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            check=False,
        )
        return proc.returncode, proc.stderr
    if mode != "epipe":
        raise AssertionError(f"unknown hostile stdout mode: {mode}")
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # the reader is gone BEFORE the child starts, so no write can succeed
    try:
        child = subprocess.Popen(argv, stdout=write_fd, stderr=subprocess.PIPE, cwd=str(cwd))
    finally:
        os.close(write_fd)
    assert child.stderr is not None
    with child.stderr as stream:
        err = stream.read()
    return child.wait(), err


class ToolCase(unittest.TestCase):
    """Shared plumbing: write an artifact into a private temp dir and run the tool over it."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def store(self, name: str, value: Any) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        return path

    def run_tool(self, *argv: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", str(TOOL), *argv], capture_output=True, cwd=str(self.root), check=False
        )

    def admit(self, request: dict[str, Any], *, policy: Path | str = POLICY, name: str = "request") -> dict[str, Any]:
        path = self.store(name, request)
        done = self.run_tool("admit", "--request", str(path), "--policy", str(policy))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        result = json.loads(done.stdout)
        self.assertEqual(result["schema"], ADMISSION_SCHEMA)
        return result

    def classify(self, record: dict[str, Any], *, name: str = "served") -> dict[str, Any]:
        path = self.store(name, record)
        done = self.run_tool("classify", "--served", str(path), "--policy", str(POLICY))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        result = json.loads(done.stdout)
        self.assertEqual(result["schema"], CLASSIFICATION_SCHEMA)
        return result

    def joined(self, result: dict[str, Any]) -> str:
        return " || ".join(result["reasons"] + result.get("injection_gaps", []))


class AdmissionTests(ToolCase):
    """Job 1: admit or refuse one RuntimeAssignment BEFORE spawn."""

    def test_a_resolved_injected_and_read_back_assignment_is_admitted(self) -> None:
        result = self.admit(build_request())
        self.assertEqual(result["verdict"], ADMIT)
        self.assertTrue(result["may_spawn"])
        self.assertEqual(result["reasons"], [])
        self.assertIsNone(result["seed_proposal"])
        self.assertEqual(result["evidence"]["requested"]["model_id"], MODEL)
        self.assertEqual(result["evidence"]["resolved"]["provider"], PROVIDER)
        self.assertEqual(result["evidence"]["requested_tier"], TIER)

    def test_an_inherited_resolution_state_refuses_by_name(self) -> None:
        # POSITIVE CONTROL: the same request with resolution_state resolved is admitted, so this
        # test cannot pass by failing to reach a verdict at all.
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)
        result = self.admit(build_request(assignment=build_assignment(resolution_state="inherited")))
        self.assertEqual(result["verdict"], REFUSE)
        self.assertFalse(result["may_spawn"])
        self.assertIn("inherited", self.joined(result))
        self.assertIn("never proof", self.joined(result))
        self.assertIn("stops before dispatch", self.joined(result))

    def test_an_unresolved_resolution_state_refuses_by_name(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(assignment=build_assignment(resolution_state="unresolved")))
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("unresolved", self.joined(result))
        self.assertIn("before spawn", self.joined(result))

    def test_a_requested_or_unknown_resolution_state_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for state in ("requested", "pending", ""):
            with self.subTest(state=state):
                result = self.admit(
                    build_request(assignment=build_assignment(resolution_state=state)), name=f"request-{state or 'empty'}"
                )
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("resolution_state", self.joined(result))

    def test_requested_values_presented_as_readback_refuse(self) -> None:
        """THE conflation the contract forbids, in every shape a request holder could write.

        This input is the most dangerous in the space: every status says verified and no field is
        absent, so it reads as a fully resolved assignment.

        The fixtures come in two halves on purpose, because the guard has two halves. The canonical
        bodies are caught by comparing the stripped BYTES against the echo forms. The reformatted and
        key-reordered bodies can only be caught after parsing, and each of them names a pointer that
        RESOLVES to the observed value -- so with the post-parse comparison gone they are admitted
        with the requested effort recorded as the effective one. Without them the module's claim that
        "whitespace, quoting, and key order normalize away" was prose no test could contradict.
        """
        binding = sha256_receipt_json(assignment_binding())
        # POSITIVE CONTROL: genuine transport bytes at a named position are admitted, so the guard is
        # refusing the ECHO and not merely refusing every verified readback.
        genuine = verified_readback("effort", "low", requested=EFFORT, binding=binding)
        self.assertEqual(
            self.admit(build_request(assignment=build_assignment(effort_readback=genuine)), name="genuine")["verdict"],
            ADMIT,
        )
        echoes = {
            # Canonical-form bodies: their exact stripped bytes are one of the echo forms.
            "bare-requested-value": (json.dumps(EFFORT), ""),
            "effort-object": (receipt_json({"effort": EFFORT}), ""),
            "request-triple": (receipt_json({"context_form": CONTEXT, "effort": EFFORT, "model_id": MODEL}), ""),
            "assignment-binding": (receipt_json(assignment_binding()), ""),
            # Bodies no byte comparison can catch, each bound to a pointer that resolves.
            "reformatted-effort-object": (json.dumps({"effort": EFFORT}, indent=4), "/effort"),
            "key-reordered-request-triple": (
                json.dumps({"model_id": MODEL, "effort": EFFORT, "context_form": CONTEXT}, indent=2),
                "/effort",
            ),
        }
        for label, (body, pointer) in echoes.items():
            with self.subTest(echo=label):
                echoed = verified_readback(
                    "effort", EFFORT, requested=EFFORT, binding=binding, response_bytes=body, pointer=pointer
                )
                result = self.admit(
                    build_request(assignment=build_assignment(effort_readback=echoed)), name=f"echo-{label}"
                )
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("request echo", self.joined(result))
                self.assertIn("requested values never become readback", self.joined(result))

    def test_a_verified_readback_that_names_no_observation_refuses(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        full = verified_readback("effort", "low", requested=EFFORT, binding=binding)
        self.assertEqual(
            self.admit(build_request(assignment=build_assignment(effort_readback=full)), name="full")["verdict"], ADMIT
        )  # POSITIVE CONTROL
        stripped = verified_readback(
            "effort", EFFORT, requested=EFFORT, binding=binding, drop=("response_bytes", "observed_value_pointer")
        )
        result = self.admit(build_request(assignment=build_assignment(effort_readback=stripped)), name="stripped")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("names no observation", self.joined(result))

    def test_an_unavailable_readback_carrying_a_value_refuses(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        honest = unavailable_readback(binding)
        self.assertEqual(
            self.admit(build_request(assignment=build_assignment(effort_readback=honest)), name="honest")["verdict"],
            ADMIT,
        )  # POSITIVE CONTROL
        masked = {
            "status": "unavailable",
            "divergence": "unavailable",
            "evidence": {**honest["evidence"], "observed_effort": EFFORT},
        }
        result = self.admit(build_request(assignment=build_assignment(effort_readback=masked)), name="masked")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("never carries a value", self.joined(result))

    def test_an_unavailable_readback_declaring_a_divergence_refuses(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        lying = {**unavailable_readback(binding), "divergence": "matches_requested"}
        result = self.admit(build_request(assignment=build_assignment(context_readback=lying)), name="lying")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("divergence is declared that was never observed", self.joined(result))

    def test_an_honestly_unavailable_readback_is_admitted_and_recorded_as_unavailable(self) -> None:
        """The effective value must be recorded as unavailable, NEVER as the requested value."""
        result = self.admit(build_request())
        self.assertEqual(result["verdict"], ADMIT)
        effective = result["evidence"]["effective"]
        self.assertEqual(effective["effort_readback_status"], "unavailable")
        self.assertEqual(effective["context_readback_status"], "unavailable")
        self.assertIsNone(effective["effort"])
        self.assertIsNone(effective["context_form"])
        self.assertNotEqual(effective["effort"], EFFORT)
        self.assertNotEqual(effective["context_form"], CONTEXT)
        # POSITIVE CONTROL: the same output channel DOES carry an effective value when one was
        # genuinely observed, so the two `None`s above are a recording and not a dead field.
        binding = sha256_receipt_json(assignment_binding())
        observed = self.admit(
            build_request(
                assignment=build_assignment(
                    effort_readback=verified_readback("effort", "low", requested=EFFORT, binding=binding)
                )
            ),
            name="observed",
        )
        self.assertEqual(observed["verdict"], ADMIT)
        self.assertEqual(observed["evidence"]["effective"]["effort"], "low")
        self.assertNotEqual(observed["evidence"]["effective"]["effort"], EFFORT)

    def test_a_host_that_cannot_inject_effort_returns_one_seed_proposal_not_a_dispatch(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(injects_effort=False), name="no-effort")
        self.assertEqual(result["verdict"], SEED)
        self.assertFalse(result["may_spawn"])
        proposal = result["seed_proposal"]
        self.assertIsNotNone(proposal)
        # The emitted document is canonical (sorted keys), so the typed ORDER cannot survive
        # serialization; the tool asserts that order internally and this asserts the exact field set.
        self.assertEqual(sorted(proposal), sorted(SEED_PROPOSAL_FIELDS))
        self.assertTrue(proposal["blocking"])
        self.assertIn("effort", " ".join(result["injection_gaps"]))
        self.assertIn("SeedProposal", result["consequence"])

    def test_a_host_that_cannot_inject_the_model_also_returns_one_seed_proposal(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for label, pieces in (
            ("model", {"injects_model": False}),
            ("both", {"injects_model": False, "injects_effort": False}),
        ):
            with self.subTest(missing=label):
                result = self.admit(build_request(**pieces), name=f"no-{label}")
                self.assertEqual(result["verdict"], SEED)
                self.assertIsNotNone(result["seed_proposal"])
                self.assertEqual(len(result["injection_gaps"]), 2 if label == "both" else 1)

    def test_a_non_boolean_injection_capability_refuses_rather_than_reading_as_truthy(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for value in ("false", 0, None):
            with self.subTest(value=value):
                result = self.admit(build_request(injects_effort=value), name=f"nonbool-{value}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIsNone(result["seed_proposal"])
                self.assertIn("not a boolean", self.joined(result))

    def test_an_absent_or_unclosed_host_injection_declaration_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for label, host_injection in (
            ("absent", "absent"),
            ("not-an-object", ["claude-code"]),
            ("missing-field", {"host": "claude-code", "injects_model": True, "injects_effort": True}),
            (
                "extra-field",
                {
                    "host": "claude-code",
                    "surface": "workflow_agent_call",
                    "injects_model": True,
                    "injects_effort": True,
                    "injects_context": True,
                },
            ),
        ):
            with self.subTest(shape=label):
                result = self.admit(build_request(host_injection=host_injection), name=f"host-{label}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("host_injection", self.joined(result))

    def test_an_unavailable_independent_observation_is_admitted_with_an_unambiguous_mapping(self) -> None:
        result = self.admit(
            build_request(assignment=build_assignment(identity_basis="unambiguous_exact_id_mapping")),
            name="mapping",
        )
        self.assertEqual(result["verdict"], ADMIT)
        self.assertEqual(result["evidence"]["resolved"]["identity_basis"], "unambiguous_exact_id_mapping")
        self.assertEqual(result["evidence"]["resolved"]["provider"], PROVIDER)

    def test_the_same_mapping_without_immutable_request_evidence_refuses(self) -> None:
        mapped = build_assignment(identity_basis="unambiguous_exact_id_mapping")
        self.assertEqual(self.admit(build_request(assignment=mapped), name="mapping")["verdict"], ADMIT)  # CONTROL
        unbacked = build_assignment(
            identity_basis="unambiguous_exact_id_mapping", request_injection_status="unavailable"
        )
        result = self.admit(build_request(assignment=unbacked), name="unbacked")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("immutable request", self.joined(result))

    def test_a_mapping_evidence_object_bound_to_another_assignment_refuses(self) -> None:
        mapped = build_assignment(identity_basis="unambiguous_exact_id_mapping")
        self.assertEqual(self.admit(build_request(assignment=mapped), name="mapping")["verdict"], ADMIT)  # CONTROL
        transplanted = build_assignment(identity_basis="unambiguous_exact_id_mapping")
        transplanted["model_readback_evidence"]["assignment_binding_sha256"] = sha256_receipt_json(
            assignment_binding(model_id="claude-opus-4-8")
        )
        result = self.admit(build_request(assignment=transplanted), name="transplanted")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("captured for a different one", self.joined(result))

    def test_a_mapping_for_an_id_the_policy_does_not_map_refuses(self) -> None:
        mapped = build_assignment(identity_basis="unambiguous_exact_id_mapping")
        self.assertEqual(self.admit(build_request(assignment=mapped), name="mapping")["verdict"], ADMIT)  # CONTROL
        unknown = build_assignment(
            requested_model_id="gpt-9.9-unlisted", identity_basis="unambiguous_exact_id_mapping"
        )
        result = self.admit(build_request(assignment=unknown), name="unknown-id")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("not unambiguous", self.joined(result))

    def test_an_exact_id_the_policy_does_not_map_refuses_even_with_an_observed_readback(self) -> None:
        """The clause-level mapping check: identity is verified AGAINST the versioned policy."""
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(
            build_request(assignment=build_assignment(requested_model_id="gpt-9.9-unlisted")), name="unmapped"
        )
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("not an exact model ID the policy maps", self.joined(result))

    def test_a_requested_effort_or_context_outside_the_policy_vocabulary_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for label, pieces in (("effort", {"effort": "ultra"}), ("context", {"context": "2m"})):
            with self.subTest(axis=label):
                result = self.admit(
                    build_request(assignment=build_assignment(**pieces)), name=f"vocabulary-{label}"
                )
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("vocabulary", self.joined(result))

    def test_mapping_evidence_must_be_the_versioned_mapping_and_bind_the_resolved_pair(self) -> None:
        mapped = build_assignment(identity_basis="unambiguous_exact_id_mapping")
        self.assertEqual(self.admit(build_request(assignment=mapped), name="mapping")["verdict"], ADMIT)  # CONTROL
        for label, mutation, fragment in (
            ("reference", {"reference": "a-note-somewhere"}, "not the policy mapping reference"),
            ("mapped-model", {"mapped_model_id": "claude-opus-4-8"}, "does not bind the mapped provider"),
            ("mapped-provider", {"mapped_provider": "openai"}, "does not bind the mapped provider"),
            ("no-binding-digest", {"assignment_binding_sha256": "nope"}, "carries no lowercase SHA-256"),
        ):
            with self.subTest(evidence=label):
                assignment = build_assignment(identity_basis="unambiguous_exact_id_mapping")
                assignment["model_readback_evidence"].update(mutation)
                result = self.admit(build_request(assignment=assignment), name=f"mapping-{label}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn(fragment, self.joined(result))

    def test_a_verified_readback_must_bind_its_own_transport_bytes_and_position(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        good = verified_readback("effort", "low", requested=EFFORT, binding=binding)
        self.assertEqual(
            self.admit(build_request(assignment=build_assignment(effort_readback=good)), name="good")["verdict"],
            ADMIT,
        )  # POSITIVE CONTROL
        cases = {
            "broken-digest": (
                verified_readback("effort", "low", requested=EFFORT, binding=binding, digest="0" * 64),
                "does not bind the transport response bytes",
            ),
            "pointer-elsewhere": (
                verified_readback("effort", "low", requested=EFFORT, binding=binding, pointer="/effective/other"),
                "not the value the transport reported",
            ),
            "freeform-bytes": (
                verified_readback(
                    "effort", "low", requested=EFFORT, binding=binding, response_bytes="effort was low, honestly"
                ),
                "do not parse as JSON",
            ),
            "out-of-vocabulary": (
                verified_readback(
                    "effort",
                    "ultra",
                    requested=EFFORT,
                    binding=binding,
                    response_bytes=json.dumps({"effective": {"value": "ultra"}}),
                ),
                "outside the policy allowed_efforts vocabulary",
            ),
            "divergence-denied": (
                verified_readback(
                    "effort", "low", requested=EFFORT, binding=binding, divergence="matches_requested"
                ),
                "effort_effective_divergence is 'matches_requested'",
            ),
        }
        for label, (readback, fragment) in cases.items():
            with self.subTest(case=label):
                result = self.admit(
                    build_request(assignment=build_assignment(effort_readback=readback)), name=f"readback-{label}"
                )
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn(fragment, self.joined(result))

    def test_an_unknown_effective_readback_status_refuses(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        odd = {**unavailable_readback(binding), "status": "probably"}
        result = self.admit(build_request(assignment=build_assignment(effort_readback=odd)), name="odd-status")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("effort_readback_status is 'probably'", self.joined(result))

    def test_the_tier_field_may_not_carry_a_model_id(self) -> None:
        """Direction A of the tier/identity separation: a route in the tier field."""
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for label, tier in (("exact-model-id", MODEL), ("pair-label", "Terra/Opus"), ("null", None)):
            with self.subTest(tier=label):
                result = self.admit(build_request(tier=tier), name=f"tier-{label}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("requested_tier", self.joined(result))

    def test_a_resolved_identity_field_may_not_carry_a_tier(self) -> None:
        """Direction B of the tier/identity separation: a tier in a route field."""
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for field, value in (("resolved_model_id", "capable-volume"), ("resolved_provider", "frontier")):
            with self.subTest(field=field):
                assignment = build_assignment()
                assignment[field] = value
                result = self.admit(build_request(assignment=assignment), name=f"tier-in-{field}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn("separate facts", self.joined(result))
                self.assertIn("semantic tier and not a resolved route", self.joined(result))

    def test_an_absent_requested_tier_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(drop_tier=True), name="no-tier")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("records no requested_tier", self.joined(result))

    def test_an_incomplete_assignment_refuses_and_names_every_missing_field(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        assignment = build_assignment()
        del assignment["resolution_state"]
        del assignment["effort_readback_status"]
        result = self.admit(build_request(assignment=assignment), name="incomplete")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("incomplete", self.joined(result))
        self.assertIn("resolution_state", self.joined(result))
        self.assertIn("effort_readback_status", self.joined(result))

    def test_a_gateway_response_body_identity_source_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(
            build_request(assignment=build_assignment(identity_source="gateway_response_body")), name="body"
        )
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("echoes the caller's requested model string", self.joined(result))

    def test_an_unnamed_identity_source_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(assignment=build_assignment(identity_source="trust_me")), name="unnamed")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("admissible provenance", self.joined(result))

    def test_independent_identity_evidence_must_be_verified_and_about_this_route(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        for label, mutation, fragment in (
            ("unverified-evidence", {"status": "unavailable"}, "independent identity readback must be"),
            ("empty-observation", {"observed_model_id": ""}, "so nothing was independently observed"),
            ("other-route", {"observed_model_id": "claude-opus-4-8"}, "is about a different route"),
            ("other-provider", {"observed_provider": "openai"}, "is about a different route"),
        ):
            with self.subTest(evidence=label):
                assignment = build_assignment()
                assignment["model_readback_evidence"].update(mutation)
                result = self.admit(build_request(assignment=assignment), name=f"identity-{label}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn(fragment, self.joined(result))

    def test_a_pre_spawn_model_substitution_refuses_as_a_mutable_request(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        swapped = build_assignment(requested_model_id=MODEL, resolved_model_id="claude-opus-4-8")
        result = self.admit(build_request(assignment=swapped), name="swapped")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("immutable", self.joined(result))

    def test_request_injection_evidence_must_bind_the_requested_bytes(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        # Each shape asserts its OWN reason, because "no digest at all" and "a digest of the wrong
        # tuple" are different facts and a human fixes them differently.
        for label, digest, fragment in (
            (
                "wrong-tuple",
                sha256_receipt_json({"context_form": CONTEXT, "effort": "low", "model_id": MODEL}),
                "does not bind the requested model",
            ),
            ("not-a-digest", "nope", "carries no lowercase SHA-256"),
            ("null", None, "carries no lowercase SHA-256"),
        ):
            with self.subTest(digest=label):
                assignment = build_assignment()
                assignment["request_injection_evidence"]["request_bytes_sha256"] = digest
                result = self.admit(build_request(assignment=assignment), name=f"digest-{label}")
                self.assertEqual(result["verdict"], REFUSE)
                self.assertIn(fragment, self.joined(result))

    def test_an_unverified_request_injection_status_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(
            build_request(assignment=build_assignment(request_injection_status="unavailable")), name="uninjected"
        )
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("mandatory and immutable", self.joined(result))

    def test_an_unverified_model_readback_status_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(
            build_request(assignment=build_assignment(model_readback_status="unavailable")), name="unread"
        )
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("verified model identity", self.joined(result))

    def test_a_provider_that_is_not_the_policy_mapped_one_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(assignment=build_assignment(provider="openai")), name="wrong-provider")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("policy-mapped provider", self.joined(result))

    def test_an_unknown_identity_basis_refuses(self) -> None:
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(build_request(assignment=build_assignment(identity_basis="vibes")), name="vibes")
        self.assertEqual(result["verdict"], REFUSE)
        self.assertIn("basis for the resolved identity is unnamed", self.joined(result))

    def test_the_seed_proposal_verdict_outranks_a_refusal_and_hides_no_reason(self) -> None:
        """Both outcomes stop before spawn; the ordering must not swallow the other reasons."""
        self.assertEqual(self.admit(build_request())["verdict"], ADMIT)  # POSITIVE CONTROL
        result = self.admit(
            build_request(injects_effort=False, assignment=build_assignment(resolution_state="inherited")),
            name="both",
        )
        self.assertEqual(result["verdict"], SEED)
        self.assertTrue(result["reasons"], "the refusal reasons must still be listed")
        self.assertIn("inherited", self.joined(result))
        self.assertIn("effort", " ".join(result["injection_gaps"]))

    def test_the_default_policy_path_resolves_without_an_explicit_argument(self) -> None:
        """The default is derived from the tool's own location, never from cwd, HOME, or argv."""
        path = self.store("request", build_request())
        done = self.run_tool("admit", "--request", str(path))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        result = json.loads(done.stdout)
        self.assertEqual(result["verdict"], ADMIT)
        self.assertEqual(Path(result["evidence"]["policy_path"]).resolve(), POLICY.resolve())


class ClassificationTests(ToolCase):
    """Job 2: classify what a receipt actually served against what was requested."""

    def test_a_receipt_that_served_the_requested_route_is_an_exact_match(self) -> None:
        result = self.classify(build_served())
        self.assertEqual(result["verdict"], EXACT)
        self.assertFalse(result["blocks_wave_completion"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual([axis["axis"] for axis in result["axes"]], ["context", "effort", "model"])

    def test_a_documented_fallback_inside_the_envelope_is_an_explained_substitution(self) -> None:
        envelope = [
            authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)
        ]
        record = build_served(served_model="claude-opus-4-8", envelope=envelope)
        result = self.classify(record)
        self.assertEqual(result["verdict"], EXPLAINED)
        self.assertFalse(result["blocks_wave_completion"])
        self.assertIn("the approved wave plan's predeclared fallback", " ".join(result["explanations"]))
        # POSITIVE CONTROL: the identical served record WITHOUT the envelope is unexplained, so the
        # explained verdict came from the authorization and not from the substitution being benign.
        bare = self.classify(build_served(served_model="claude-opus-4-8"), name="bare")
        self.assertEqual(bare["verdict"], UNEXPLAINED)
        self.assertTrue(bare["blocks_wave_completion"])

    def test_an_unauthorized_substitution_is_unexplained_and_blocks_wave_completion(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        result = self.classify(build_served(served_model="claude-opus-4-8"), name="swap")
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertTrue(result["blocks_wave_completion"])
        self.assertIn("UNEXPLAINED", " ".join(result["reasons"]))
        self.assertIn("no unexplained substitution", result["consequence"])

    def test_an_envelope_entry_that_names_no_authorization_does_not_explain(self) -> None:
        named = [authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)]
        self.assertEqual(
            self.classify(build_served(served_model="claude-opus-4-8", envelope=named), name="named")["verdict"],
            EXPLAINED,
        )  # POSITIVE CONTROL
        for label, pieces in (
            ("no-authorized-by", {"authorized_by": ""}),
            ("null-approved-in", {"approved_in": None}),
        ):
            with self.subTest(entry=label):
                envelope = [
                    authorization(
                        axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER, **pieces
                    )
                ]
                result = self.classify(
                    build_served(served_model="claude-opus-4-8", envelope=envelope), name=f"unnamed-{label}"
                )
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("unnamed authority", " ".join(result["reasons"]))

    def test_an_envelope_entry_for_a_different_swap_does_not_explain_this_one(self) -> None:
        matching = [authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)]
        self.assertEqual(
            self.classify(build_served(served_model="claude-opus-4-8", envelope=matching), name="match")["verdict"],
            EXPLAINED,
        )  # POSITIVE CONTROL
        for label, entry in (
            ("wrong-target", authorization(axis="model", from_value=MODEL, to_value="claude-fable-5", to_provider=PROVIDER)),
            ("wrong-provider", authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider="openai")),
            ("wrong-axis", authorization(axis="effort", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)),
        ):
            with self.subTest(entry=label):
                result = self.classify(
                    build_served(served_model="claude-opus-4-8", envelope=[entry]), name=f"other-{label}"
                )
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("no entry", " ".join(result["reasons"]))

    def test_two_entries_authorizing_the_same_swap_are_ambiguous_and_do_not_explain(self) -> None:
        entry = authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)
        self.assertEqual(
            self.classify(build_served(served_model="claude-opus-4-8", envelope=[entry]), name="one")["verdict"],
            EXPLAINED,
        )  # POSITIVE CONTROL
        second = {**entry, "authorized_by": "an operator note"}
        result = self.classify(
            build_served(served_model="claude-opus-4-8", envelope=[entry, second]), name="two"
        )
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertIn("ambiguous", " ".join(result["reasons"]))

    def test_an_unclosed_envelope_entry_does_not_explain(self) -> None:
        entry = authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)
        self.assertEqual(
            self.classify(build_served(served_model="claude-opus-4-8", envelope=[entry]), name="closed")["verdict"],
            EXPLAINED,
        )  # POSITIVE CONTROL
        for label, bad in (("not-an-object", "authorized"), ("extra-field", {**entry, "note": "fine"})):
            with self.subTest(entry=label):
                result = self.classify(
                    build_served(served_model="claude-opus-4-8", envelope=[bad]), name=f"unclosed-{label}"
                )
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("closed envelope shape", " ".join(result["reasons"]))

    def test_an_unavailable_identity_needs_the_exact_id_mapping_carve_out(self) -> None:
        # POSITIVE CONTROL: with the carve-out satisfied the same unavailable identity is an exact
        # match, so the refusals below are about the MISSING evidence and not about unavailability.
        allowed = self.classify(
            build_served(identity_status="unavailable", identity_basis="unambiguous_exact_id_mapping"),
            name="mapped",
        )
        self.assertEqual(allowed["verdict"], EXACT)
        model_axis = next(axis for axis in allowed["axes"] if axis["axis"] == "model")
        self.assertEqual(model_axis["disposition"], "matches-by-exact-id-mapping")
        for label, pieces in (
            ("no-mapping-basis", {"identity_basis": "independent_readback"}),
            ("unverified-injection", {"identity_basis": "unambiguous_exact_id_mapping", "request_injection_status": "unavailable"}),
            ("unmapped-id", {"identity_basis": "unambiguous_exact_id_mapping", "requested_model": "gpt-9.9-unlisted", "served_model": "gpt-9.9-unlisted"}),
        ):
            with self.subTest(case=label):
                result = self.classify(
                    build_served(identity_status="unavailable", **pieces), name=f"unavailable-{label}"
                )
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertTrue(result["blocks_wave_completion"])

    def test_an_unavailable_identity_may_state_only_the_route_the_mapping_derives(self) -> None:
        """The masked model substitution: an honest `unavailable` beside an unverified fallback hint.

        The realistic producer is a gateway that falls back silently while the harness records the
        hint as `model_id` next to a truthful `unavailable` status. Without this guard the carve-out
        called that an exact match, wave completion was unblocked, and the emitted document
        contradicted its own verdict on its face -- requested sonnet, served opus, `exact-match`.

        The rule is not "carry nothing": `admit`'s half of the same carve-out REQUIRES the resolved
        pair to be populated and to equal the mapping's output, so demanding null here would make the
        two halves of one contract disagree. What an unobserved record may state is exactly the one
        route the mapping derives.
        """
        carve_out = {"identity_status": "unavailable", "identity_basis": "unambiguous_exact_id_mapping"}
        # POSITIVE CONTROLS: all three HONEST shapes of the same carve-out still reach exact-match, so
        # the refusals below are about the STATED route and not about unavailability itself.
        for label, pieces in (
            ("the-mappings-own-output", {}),
            ("null-fields", {"served_model": None, "served_provider": None}),
            ("absent-fields", {"drop_served": ("model_id", "provider")}),
        ):
            with self.subTest(honest=label):
                allowed = self.classify(build_served(**carve_out, **pieces), name=f"honest-{label}")
                self.assertEqual(allowed["verdict"], EXACT)
                self.assertFalse(allowed["blocks_wave_completion"])
                model_axis = next(axis for axis in allowed["axes"] if axis["axis"] == "model")
                self.assertEqual(model_axis["disposition"], "matches-by-exact-id-mapping")
        for label, pieces in (
            ("model-and-provider", {"served_model": "claude-opus-4-8", "served_provider": "openai"}),
            ("model-only", {"served_model": "claude-opus-4-8"}),
            ("provider-only", {"served_provider": "openai"}),
        ):
            with self.subTest(masked=label):
                result = self.classify(build_served(**carve_out, **pieces), name=f"masked-{label}")
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertTrue(result["blocks_wave_completion"])
                self.assertIn("never carries a value it did not derive", " ".join(result["reasons"]))
                model_axis = next(axis for axis in result["axes"] if axis["axis"] == "model")
                self.assertNotEqual(model_axis["disposition"], "matches-by-exact-id-mapping")

    def test_an_envelope_cannot_authorize_a_provider_the_policy_does_not_map(self) -> None:
        """A jointly impossible route, predeclared: opus served by openai while the policy maps opus
        to anthropic.

        The provider cross-check used to run only where the served model EQUALLED the request, so the
        substituted path was never checked and an envelope entry could carry an impossible route into
        `explained-substitution`. An authorization names an authority for a difference; it cannot make
        a route the versioned policy does not map possible.
        """
        possible = [authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider=PROVIDER)]
        # POSITIVE CONTROL: the same substitution to the POLICY-MAPPED provider is still explained, so
        # this refuses the impossible provider rather than every authorized model substitution.
        self.assertEqual(
            self.classify(build_served(served_model="claude-opus-4-8", envelope=possible), name="possible")["verdict"],
            EXPLAINED,
        )
        impossible = [authorization(axis="model", from_value=MODEL, to_value="claude-opus-4-8", to_provider="openai")]
        result = self.classify(
            build_served(served_model="claude-opus-4-8", served_provider="openai", envelope=impossible),
            name="impossible",
        )
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertTrue(result["blocks_wave_completion"])
        self.assertEqual(result["explanations"], [])
        self.assertIn("jointly impossible", " ".join(result["reasons"]))
        self.assertIn("policy-mapped 'anthropic'", " ".join(result["reasons"]))

    def test_an_unmapped_served_model_is_not_a_clean_exact_match(self) -> None:
        """Decided, fail-closed: an ID the versioned policy does not map cannot be an exact match.

        Equality with the request proves only that the record repeats itself. `mapped_provider`
        returns None for an out-of-vocabulary ID, so nothing constrained the served provider and
        `evil-corp` passed; and `admit` already refuses the same ID before spawn, so admitting it
        here would have the two halves of one contract disagree about whether a route is knowable.
        """
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        for label, provider in (("hostile", "evil-corp"), ("plausible", "openai")):
            with self.subTest(provider=label):
                result = self.classify(
                    build_served(
                        requested_model="gpt-9.9-unlisted",
                        served_model="gpt-9.9-unlisted",
                        served_provider=provider,
                    ),
                    name=f"unmapped-{label}",
                )
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertTrue(result["blocks_wave_completion"])
                self.assertIn("not an exact model ID the versioned policy maps", " ".join(result["reasons"]))
        # The other half of the same contract, executed rather than asserted in prose: `admit`
        # refuses that exact ID before spawn, so neither half calls this route knowable.
        refused = self.admit(
            build_request(assignment=build_assignment(requested_model_id="gpt-9.9-unlisted")), name="unmapped-admit"
        )
        self.assertEqual(refused["verdict"], REFUSE)

    def test_a_gateway_response_body_cannot_establish_what_served(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        result = self.classify(build_served(identity_source="gateway_response_body"), name="body")
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertIn("echoes the caller's own", " ".join(result["reasons"]))

    def test_an_identity_source_outside_the_admissible_set_cannot_establish_what_served(self) -> None:
        """Distinct from the response-body case: an unknown source is refused for lacking provenance,
        not for echoing the request, and the two reasons send a human to different fixes."""
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        for source in ("trust_me", "", None):
            with self.subTest(source=source):
                result = self.classify(build_served(identity_source=source), name=f"source-{source}")
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("admissible provenance", " ".join(result["reasons"]))

    def test_a_tier_name_is_not_a_served_model_identity(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        for label, pieces in (
            ("model", {"served_model": "capable-volume"}),
            ("provider", {"served_provider": "frontier"}),
        ):
            with self.subTest(field=label):
                result = self.classify(build_served(**pieces), name=f"tier-{label}")
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("semantic tier", " ".join(result["reasons"]))

    def test_an_absent_served_route_identity_is_unexplained(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        for label, pieces in (("model", {"served_model": None}), ("provider", {"served_provider": ""})):
            with self.subTest(field=label):
                result = self.classify(build_served(**pieces), name=f"absent-{label}")
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("no served route identity was recorded", " ".join(result["reasons"]))

    def test_a_served_effort_that_diverges_needs_its_own_authorization(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        unauthorized = self.classify(
            build_served(effort_status="verified", served_effort="low"), name="effort-swap"
        )
        self.assertEqual(unauthorized["verdict"], UNEXPLAINED)
        authorized = self.classify(
            build_served(
                effort_status="verified",
                served_effort="low",
                envelope=[authorization(axis="effort", from_value=EFFORT, to_value="low")],
            ),
            name="effort-authorized",
        )
        self.assertEqual(authorized["verdict"], EXPLAINED)

    def test_a_served_context_form_that_diverges_needs_its_own_authorization(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        unauthorized = self.classify(
            build_served(context_status="verified", served_context="[1m]"), name="context-swap"
        )
        self.assertEqual(unauthorized["verdict"], UNEXPLAINED)
        authorized = self.classify(
            build_served(
                context_status="verified",
                served_context="[1m]",
                envelope=[authorization(axis="context", from_value=CONTEXT, to_value="[1m]")],
            ),
            name="context-authorized",
        )
        self.assertEqual(authorized["verdict"], EXPLAINED)

    def test_a_verified_effective_value_equal_to_the_request_is_still_an_exact_match(self) -> None:
        result = self.classify(build_served(effort_status="verified", served_effort=EFFORT), name="same-effort")
        self.assertEqual(result["verdict"], EXACT)
        effort_axis = next(axis for axis in result["axes"] if axis["axis"] == "effort")
        self.assertEqual(effort_axis["served"], EFFORT)
        self.assertEqual(effort_axis["readback_status"], "verified")

    def test_an_honestly_unavailable_effective_value_is_not_a_substitution(self) -> None:
        result = self.classify(build_served())
        self.assertEqual(result["verdict"], EXACT)
        for axis in result["axes"]:
            if axis["axis"] in {"effort", "context"}:
                self.assertEqual(axis["disposition"], "unavailable")
                self.assertIsNone(axis["served"])
        # POSITIVE CONTROL: the same field carries a value when one was verified, so `None` above is
        # a recording of unavailability rather than an unpopulated field.
        observed = self.classify(build_served(effort_status="verified", served_effort="low"), name="observed")
        effort_axis = next(axis for axis in observed["axes"] if axis["axis"] == "effort")
        self.assertEqual(effort_axis["served"], "low")

    def test_an_unavailable_readback_carrying_a_value_is_the_forbidden_conflation(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        result = self.classify(build_served(effort_status="unavailable", served_effort=EFFORT), name="masked")
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertIn("never carries a value", " ".join(result["reasons"]))
        self.assertIn("conflation", " ".join(result["reasons"]))

    def test_an_out_of_vocabulary_effective_value_is_not_a_verified_readback(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        result = self.classify(build_served(effort_status="verified", served_effort="ultra"), name="ooo")
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertIn("vocabulary", " ".join(result["reasons"]))

    def test_an_unknown_readback_status_is_unexplained_rather_than_assumed_matching(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        for label, pieces in (
            ("identity", {"identity_status": "probably"}),
            ("effort", {"effort_status": "probably"}),
            ("context", {"context_status": "probably"}),
        ):
            with self.subTest(axis=label):
                result = self.classify(build_served(**pieces), name=f"status-{label}")
                self.assertEqual(result["verdict"], UNEXPLAINED)
                self.assertIn("unestablished", " ".join(result["reasons"]))

    def test_a_matching_model_served_by_another_provider_is_a_route_substitution(self) -> None:
        self.assertEqual(self.classify(build_served())["verdict"], EXACT)  # POSITIVE CONTROL
        result = self.classify(build_served(served_provider="openai"), name="cross-provider")
        self.assertEqual(result["verdict"], UNEXPLAINED)
        self.assertIn("route substitution", " ".join(result["reasons"]))


class InputErrorTests(ToolCase):
    """Exit 2 is for a question that could not be asked, and it never emits a result document."""

    def assert_input_error(self, argv: list[str], fragment: str) -> None:
        done = self.run_tool(*argv)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"", "an input error must emit no result document")
        self.assertIn(fragment, done.stderr.decode("utf-8", "replace"))

    def test_a_good_run_exits_zero(self) -> None:
        """POSITIVE CONTROL for every exit-2 assertion in this class."""
        path = self.store("request", build_request())
        done = self.run_tool("admit", "--request", str(path), "--policy", str(POLICY))
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(json.loads(done.stdout)["verdict"], ADMIT)

    def test_an_unreadable_artifact_is_an_input_error(self) -> None:
        self.assert_input_error(
            ["admit", "--request", str(self.root / "absent.json"), "--policy", str(POLICY)], "cannot read"
        )

    def test_a_directory_is_not_a_regular_file(self) -> None:
        (self.root / "dir.json").mkdir()
        self.assert_input_error(
            ["admit", "--request", str(self.root / "dir.json"), "--policy", str(POLICY)], "not a regular file"
        )

    def test_non_json_and_non_object_artifacts_are_input_errors(self) -> None:
        broken = self.root / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        self.assert_input_error(["admit", "--request", str(broken), "--policy", str(POLICY)], "is not JSON")
        listy = self.root / "list.json"
        listy.write_text("[]", encoding="utf-8")
        self.assert_input_error(["admit", "--request", str(listy), "--policy", str(POLICY)], "not a JSON object")

    def test_a_duplicate_json_member_is_an_input_error(self) -> None:
        path = self.root / "dupe.json"
        path.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
        self.assert_input_error(["admit", "--request", str(path), "--policy", str(POLICY)], "duplicate JSON member")

    def test_a_wrong_schema_tag_is_an_input_error_not_a_refusal(self) -> None:
        wrong = build_request()
        wrong["schema"] = "agentic-sdlc/runtime-admission-request@0"
        self.assert_input_error(
            ["admit", "--request", str(self.store("wrong", wrong)), "--policy", str(POLICY)], REQUEST_SCHEMA
        )

    def test_a_wrong_embedded_assignment_schema_is_an_input_error(self) -> None:
        request = build_request()
        request["assignment"]["schema_version"] = "runtime-assignment-receipt/v0"
        self.assert_input_error(
            ["admit", "--request", str(self.store("v0", request)), "--policy", str(POLICY)], RECEIPT_SCHEMA_VERSION
        )

    def test_an_absent_assignment_object_is_an_input_error(self) -> None:
        request = build_request()
        request["assignment"] = "runtime-assignment-receipt/v1"
        self.assert_input_error(
            ["admit", "--request", str(self.store("noassign", request)), "--policy", str(POLICY)],
            "carries no assignment object",
        )

    def test_a_served_record_without_both_halves_is_an_input_error(self) -> None:
        record = build_served()
        del record["served"]
        self.assert_input_error(
            ["classify", "--served", str(self.store("half", record)), "--policy", str(POLICY)],
            "requested and a served object",
        )

    def test_a_non_list_envelope_is_an_input_error(self) -> None:
        record = build_served(envelope={"axis": "model"})
        self.assert_input_error(
            ["classify", "--served", str(self.store("envelope", record)), "--policy", str(POLICY)],
            "authorized_substitutions value that is not a",
        )

    def test_a_non_finite_json_constant_is_an_input_error(self) -> None:
        path = self.root / "nan.json"
        path.write_text('{"schema": "x", "n": NaN}', encoding="utf-8")
        self.assert_input_error(["admit", "--request", str(path), "--policy", str(POLICY)], "non-finite JSON constant")

    def test_an_unusable_policy_is_an_input_error(self) -> None:
        path = self.root / "policy.json"
        path.write_text(json.dumps({"schema_version": RECEIPT_SCHEMA_VERSION}), encoding="utf-8")
        self.assert_input_error(
            ["admit", "--request", str(self.store("request", build_request())), "--policy", str(path)],
            "no exact model ID to provider map",
        )


class CrossCheckTests(ToolCase):
    """The constructed happy-path assignment must be a REAL canonical receipt, not a local shape."""

    @unittest.skipUnless(RECEIPT_ADMISSION.is_file(), "the producer-side validator is not present")
    def test_the_embedded_assignment_validates_under_the_real_receipt_validator(self) -> None:
        assignment = build_assignment()
        done = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION)],
            input=json.dumps(assignment).encode("utf-8"),
            capture_output=True,
            check=False,
        )
        report = json.loads(done.stdout)
        self.assertEqual(report.get("status"), "validated", done.stdout.decode("utf-8", "replace"))
        self.assertEqual(done.returncode, 0)
        # POSITIVE CONTROL: the channel discriminates. A one-field mutation must come back invalid,
        # so `validated` above is a verdict about these bytes and not an unconditional answer.
        mutated = build_assignment()
        mutated["resolved_provider"] = "openai"
        broken = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION)],
            input=json.dumps(mutated).encode("utf-8"),
            capture_output=True,
            check=False,
        )
        self.assertEqual(json.loads(broken.stdout).get("status"), "invalid")

    @unittest.skipUnless(RECEIPT_ADMISSION.is_file(), "the producer-side validator is not present")
    def test_a_verified_readback_assignment_also_validates_under_the_real_validator(self) -> None:
        binding = sha256_receipt_json(assignment_binding())
        assignment = build_assignment(
            effort_readback=verified_readback("effort", "low", requested=EFFORT, binding=binding)
        )
        done = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION)],
            input=json.dumps(assignment).encode("utf-8"),
            capture_output=True,
            check=False,
        )
        self.assertEqual(json.loads(done.stdout).get("status"), "validated", done.stdout.decode("utf-8", "replace"))
        # POSITIVE CONTROL: the same receipt with the readback digest broken is invalid there too.
        broken_assignment = build_assignment(
            effort_readback=verified_readback(
                "effort", "low", requested=EFFORT, binding=binding, digest="0" * 64
            )
        )
        broken = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION)],
            input=json.dumps(broken_assignment).encode("utf-8"),
            capture_output=True,
            check=False,
        )
        self.assertEqual(json.loads(broken.stdout).get("status"), "invalid")

    @unittest.skipUnless(RECEIPT_ADMISSION.is_file(), "the producer-side validator is not present")
    def test_help_exits_zero_without_reading_stdin(self) -> None:
        """SP-11: `--help` is a 0-class query that never touches the stdin-document channel.

        Stdin below carries bytes that cannot parse as JSON. If `--help` fell through to the
        pre-fix default action (read stdin unconditionally) before returning, it would report
        `{"errors": [...], "status": "invalid"}` at exit 2 instead of printing usage at exit 0.
        """
        done = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION), "--help"],
            input=b"not json and would not parse",
            capture_output=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        self.assertIn(b"usage:", done.stdout)
        self.assertNotIn(b"status", done.stdout)
        self.assertEqual(done.stderr, b"")

    @unittest.skipUnless(RECEIPT_ADMISSION.is_file(), "the producer-side validator is not present")
    def test_unknown_flag_exits_two_with_usage_on_stderr(self) -> None:
        """SP-11: an unrecognized argument is the grammar class (2), with usage on stderr, not
        the stdin-document error shape (which prints its own JSON error to stdout at the same
        code)."""
        done = subprocess.run(
            [sys.executable, "-B", str(RECEIPT_ADMISSION), "--zzz-not-a-flag"],
            input=b"",
            capture_output=True,
            check=False,
        )
        self.assertEqual(done.returncode, 2, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout, b"")
        self.assertIn(b"usage:", done.stderr)
        # POSITIVE CONTROL for the byte-identical default action: no arguments at all still
        # reads stdin and admits a valid document exactly as before this front door existed --
        # covered by test_the_embedded_assignment_validates_under_the_real_receipt_validator
        # and test_a_verified_readback_assignment_also_validates_under_the_real_validator above,
        # both invoked with the identical bare `[sys.executable, "-B", str(RECEIPT_ADMISSION)]`
        # argv this front door must leave unchanged.


class PartitionTests(ToolCase):
    """The verdict selections themselves: one partition, one verdict, never none and never two."""

    def setUp(self) -> None:
        super().setUp()
        self.module = load_tool_module()

    def test_an_unevaluated_admission_clause_refuses_rather_than_admitting(self) -> None:
        admission = self.module.Admission("policy")
        admission.evaluated = set(self.module.ADMISSION_CLAUSES)
        self.assertEqual(admission.verdict(), ADMIT)  # POSITIVE CONTROL: the full set admits
        for clause in sorted(self.module.ADMISSION_CLAUSES):
            with self.subTest(dropped=clause):
                partial = self.module.Admission("policy")
                partial.evaluated = set(self.module.ADMISSION_CLAUSES) - {clause}
                self.assertEqual(partial.verdict(), REFUSE)
                self.assertIn(clause, " ".join(partial.reasons))

    def test_an_unclassified_axis_is_unexplained_rather_than_matching(self) -> None:
        full = self.module.Classification("policy")
        for axis in sorted(self.module.CLASSIFICATION_AXES):
            full.record(axis, disposition="matches")
        self.assertEqual(full.verdict(), EXACT)  # POSITIVE CONTROL: all three axes give exact-match
        for axis in sorted(self.module.CLASSIFICATION_AXES):
            with self.subTest(dropped=axis):
                partial = self.module.Classification("policy")
                for other in sorted(self.module.CLASSIFICATION_AXES - {axis}):
                    partial.record(other, disposition="matches")
                self.assertEqual(partial.verdict(), UNEXPLAINED)
                self.assertIn(axis, " ".join(partial.unexplained))

    def test_every_verdict_carries_a_consequence_and_no_verdict_is_unnamed(self) -> None:
        self.assertEqual(
            set(self.module.ADMISSION_CONSEQUENCE), {ADMIT, REFUSE, SEED}, "one consequence per admission verdict"
        )
        self.assertEqual(
            set(self.module.CLASSIFICATION_CONSEQUENCE),
            {EXACT, EXPLAINED, UNEXPLAINED},
            "one consequence per classification verdict",
        )
        for text in list(self.module.ADMISSION_CONSEQUENCE.values()) + list(
            self.module.CLASSIFICATION_CONSEQUENCE.values()
        ):
            self.assertNotIn("cannot determine", text)

    def test_the_seed_proposal_shape_is_the_repositorys_typed_one_and_not_an_invention(self) -> None:
        """The emitted proposal must be the queue's own typed shape, in its documented order."""
        source = (
            ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
        ).read_text(encoding="utf-8")
        marker = "SeedProposal { "
        self.assertIn(marker, source)  # POSITIVE CONTROL: the documented shape was actually found
        body = source.split(marker, 1)[1].split("}", 1)[0]
        documented = tuple(part.split(":", 1)[0].strip() for part in body.split(","))
        self.assertEqual(len(documented), 9)
        self.assertEqual(self.module.SEED_PROPOSAL_FIELDS, documented)

    def test_the_typed_order_invariant_is_live_and_not_decoration(self) -> None:
        """No runtime input can break the constructed order, so the guard is proven by substitution.

        Reordering the constant while the constructor keeps its literal order is exactly the future
        edit the invariant exists to catch, and it must raise rather than emit a mis-shaped proposal.
        """
        admission = self.module.Admission("policy")
        admission.gap("the host cannot inject the exact effort")
        request = build_request(injects_effort=False)
        proposal = self.module.seed_proposal_for(admission, request)
        self.assertEqual(tuple(proposal), self.module.SEED_PROPOSAL_FIELDS)  # POSITIVE CONTROL
        original = self.module.SEED_PROPOSAL_FIELDS
        self.addCleanup(setattr, self.module, "SEED_PROPOSAL_FIELDS", original)
        self.module.SEED_PROPOSAL_FIELDS = tuple(reversed(original))
        with self.assertRaises(self.module.InputError):
            self.module.seed_proposal_for(admission, request)

    def test_a_tier_token_is_recognized_however_it_is_spelled(self) -> None:
        for value in ("capable-volume", "Capable_Volume", " FRONTIER ", "judgment-workhorse"):
            with self.subTest(value=value):
                self.assertTrue(self.module.is_tier_token(value))
        # POSITIVE CONTROL: exact model IDs and near-misses are NOT tiers, so the predicate
        # discriminates rather than answering true for every string.
        for value in (MODEL, "gpt-5.6-terra", "capable", None, ["frontier"]):
            with self.subTest(value=value):
                self.assertFalse(self.module.is_tier_token(value))


class DocstringTests(unittest.TestCase):
    """Prose the exit contract depends on. A reserved code a tool cannot reach is a false promise."""

    def test_the_module_states_why_decision_nine_reserves_neither_three_nor_four(self) -> None:
        squeezed = " ".join(TOOL.read_text(encoding="utf-8").split('"""')[1].split())
        self.assertIn("exit space is 0, 2, and 1", squeezed)
        self.assertIn("can cause no effect can neither refuse before one nor admit one", squeezed)
        self.assertIn("4 is unreachable rather than merely unused", squeezed)

    def test_the_module_states_the_two_stream_rules_its_exit_codes_rest_on(self) -> None:
        """The two streams are not the same kind of thing, and the difference decides an exit code."""
        squeezed = " ".join(TOOL.read_text(encoding="utf-8").split('"""')[1].split())
        self.assertIn("Stderr is display only", squeezed)
        self.assertIn("stdout that cannot receive the result document is exit 1", squeezed)
        self.assertIn("replace this module's exit code with 120", squeezed)
        # POSITIVE CONTROL: the extraction really reached the module docstring, so the three
        # assertions above are about prose that was read and not about an empty string.
        self.assertIn("Admit or refuse a `RuntimeAssignment` before spawn", squeezed)

    def test_the_module_states_the_contract_tension_it_cannot_resolve(self) -> None:
        squeezed = " ".join(TOOL.read_text(encoding="utf-8").split('"""')[1].split())
        self.assertIn("resolved` is recorded only after adapter readback", squeezed)
        self.assertIn("before spawn", squeezed)


@unittest.skipUnless(POSIX, "fd-level stderr hostility is POSIX-only")
class HostileStderrTests(ToolCase):
    """A stderr this process cannot write to must cost the display line, never the exit code."""

    def test_the_hostile_stderr_fixture_is_actually_hostile(self) -> None:
        """The control for every assertion below: the child really has no usable stderr."""
        canary = (
            "import sys\n"
            "if sys.stderr is None:\n"
            "    print('none')\n"
            "else:\n"
            "    try:\n"
            "        sys.stderr.write('x')\n"
            "        sys.stderr.flush()\n"
            "        print('writable')\n"
            "    except OSError as exc:\n"
            "        print(type(exc).__name__)\n"
        )
        code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode="closed", cwd=self.root)
        self.assertEqual(f"{code}:{out.decode('utf-8', 'replace').strip()}", "0:none")
        code, out = _run_with_hostile_stderr([sys.executable, "-B", "-c", canary], mode="epipe", cwd=self.root)
        self.assertEqual(f"{code}:{out.decode('utf-8', 'replace').strip()}", "120:BrokenPipeError")

    def test_a_hostile_stderr_cannot_reclassify_a_well_classified_input_error(self) -> None:
        argv = [
            sys.executable,
            "-B",
            str(TOOL),
            "admit",
            "--request",
            str(self.root / "absent.json"),
            "--policy",
            str(POLICY),
        ]
        for mode in ("closed", "epipe"):
            with self.subTest(mode=mode):
                code, out = _run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_INPUT)
                self.assertNotIn(code, (1, 120))  # 1-for-2 and 120 are both wrong answers here
                self.assertEqual(out, b"", "an input error must emit no result document")
        # POSITIVE CONTROL: the identical argv over a WORKING stderr still exits 2 and carries the
        # diagnostic line the hostile runs necessarily lost, so those runs lost the display channel
        # and nothing else.
        done = subprocess.run(argv, capture_output=True, cwd=str(self.root), check=False)
        self.assertEqual(done.returncode, EXIT_INPUT, done.stderr)
        self.assertIn(b"cannot read", done.stderr)

    def test_the_grammar_path_keeps_exit_two_and_writes_no_result_document(self) -> None:
        """argparse is a SECOND stream surface, and both of its defects hide behind good descriptors.

        `ArgumentParser.error` writes usage through `print_usage`, which falls back to STDOUT when
        `sys.stderr is None`, so under `2>&-` a grammar error kept exit 2 while putting bytes on the
        one channel a result document lives on. And argparse swallows a failed write while leaving its
        bytes pending, which was enough for the shutdown flush to replace exit 2 with 120.
        """
        arms = {
            "missing-required-option": ["admit"],
            "unknown-subcommand": ["not-a-command"],
            "no-arguments": [],
            "unknown-flag": ["--not-a-flag"],
        }
        for label, pieces in arms.items():
            argv = [sys.executable, "-B", str(TOOL), *pieces]
            # POSITIVE CONTROL: over a WORKING stderr the same argv exits 2, carries its usage on
            # stderr, and writes nothing to stdout, so the hostile runs lost the display and nothing
            # else -- and the arm is a real grammar error rather than a typo that parses.
            done = subprocess.run(argv, capture_output=True, cwd=str(self.root), check=False)
            with self.subTest(arm=label, stderr="working"):
                self.assertEqual(done.returncode, EXIT_INPUT, done.stderr.decode("utf-8", "replace"))
                self.assertEqual(done.stdout, b"")
                self.assertIn(b"usage:", done.stderr)
            for mode in ("closed", "epipe"):
                with self.subTest(arm=label, stderr=mode):
                    code, out = _run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                    self.assertEqual(code, EXIT_INPUT)
                    self.assertNotIn(code, (1, 120))  # 1-for-2 and 120 are both wrong answers here
                    self.assertEqual(out, b"", "usage may never fall back onto the result channel")

    def test_a_hostile_stderr_cannot_cost_a_derived_verdict_its_exit_code(self) -> None:
        for label, pieces in (
            (ADMIT, ["admit", "--request", str(self.store("request", build_request()))]),
            (SEED, ["admit", "--request", str(self.store("seed", build_request(injects_effort=False)))]),
            (
                UNEXPLAINED,
                ["classify", "--served", str(self.store("served", build_served(served_model="claude-opus-4-8")))],
            ),
        ):
            argv = [sys.executable, "-B", str(TOOL), *pieces, "--policy", str(POLICY)]
            for mode in ("closed", "epipe"):
                with self.subTest(verdict=label, mode=mode):
                    code, out = _run_with_hostile_stderr(argv, mode=mode, cwd=self.root)
                    self.assertEqual(code, EXIT_OK)
                    self.assertNotIn(code, (1, 120))
                    self.assertEqual(json.loads(out)["verdict"], label)


@unittest.skipUnless(POSIX, "fd-level stdout hostility is POSIX-only")
class HostileStdoutTests(ToolCase):
    """Stdout carries the EVIDENCE, so failing to deliver it must be classified, never inherited."""

    def test_the_hostile_stdout_fixture_is_actually_hostile(self) -> None:
        """The control for the assertion below: the child really has no usable stdout.

        The canary reports on stderr, because the channel under test is the one it cannot use. Its
        epipe exit of 120 is the whole reason this fixture exists: that is what an unguarded write
        costs, and it is outside the tool's declared exit set.
        """
        canary = (
            "import sys\n"
            "if sys.stdout is None:\n"
            "    sys.stderr.write('none')\n"
            "else:\n"
            "    try:\n"
            "        sys.stdout.write('x')\n"
            "        sys.stdout.flush()\n"
            "        sys.stderr.write('writable')\n"
            "    except OSError as exc:\n"
            "        sys.stderr.write(type(exc).__name__)\n"
        )
        code, err = _run_with_hostile_stdout([sys.executable, "-B", "-c", canary], mode="closed", cwd=self.root)
        self.assertEqual(f"{code}:{err.decode('utf-8', 'replace').strip()}", "0:none")
        code, err = _run_with_hostile_stdout([sys.executable, "-B", "-c", canary], mode="epipe", cwd=self.root)
        text = err.decode("utf-8", "replace").strip()
        self.assertEqual(code, 120, text)
        # The canary reports the caught error and then CPython's finalizer trails its own "Exception
        # ignored" over the same broken stream -- which is exactly the retry the tool has to prevent.
        self.assertTrue(text.startswith("BrokenPipeError"), text)
        self.assertIn("Exception ignored", text)

    def test_help_over_a_hostile_stdout_still_exits_zero_and_prepares_nothing(self) -> None:
        """`--help` is the other line argparse writes to STDOUT, and it is display only.

        Help text is not a result document, so an unwritable stdout must cost the text and nothing
        else. Unguarded, argparse's own write raised straight through and turned `--help` into an exit
        1 traceback on a broken reader.
        """
        argv = [sys.executable, "-B", str(TOOL), "--help"]
        # POSITIVE CONTROL: over a working stdout the same argv exits 0 and DOES print usage, so the
        # runs below lost the text rather than never having any.
        done = subprocess.run(argv, capture_output=True, cwd=str(self.root), check=False)
        self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
        self.assertIn(b"usage:", done.stdout)
        for mode in ("closed", "epipe"):
            with self.subTest(stdout=mode):
                code, err = _run_with_hostile_stdout(argv, mode=mode, cwd=self.root)
                self.assertEqual(code, EXIT_OK, err.decode("utf-8", "replace"))
                self.assertNotIn(code, (1, 120))
                self.assertNotIn("Traceback", err.decode("utf-8", "replace"))

    def test_an_undeliverable_result_document_is_a_named_exit_one_and_never_120(self) -> None:
        """A derived verdict that did not reach its caller is not a success and not an input error.

        Both hostile shapes used to answer with a code the module does not define: `1>&-` reached
        `sys.stdout.buffer` on None and exited 1 through an unhandled traceback, and a broken reader
        exited 120. The diagnostic has to name the undelivered document, because exit 1 alone does not
        tell a human that the verdict itself was derived.
        """
        for label, pieces in (
            (ADMIT, ["admit", "--request", str(self.store("request", build_request()))]),
            (
                UNEXPLAINED,
                ["classify", "--served", str(self.store("served", build_served(served_model="claude-opus-4-8")))],
            ),
        ):
            argv = [sys.executable, "-B", str(TOOL), *pieces, "--policy", str(POLICY)]
            # POSITIVE CONTROL: over a WORKING stdout the same argv exits 0 and delivers the document,
            # so the runs below lost the delivery and not the derivation.
            done = subprocess.run(argv, capture_output=True, cwd=str(self.root), check=False)
            with self.subTest(verdict=label, stdout="working"):
                self.assertEqual(done.returncode, EXIT_OK, done.stderr.decode("utf-8", "replace"))
                self.assertEqual(json.loads(done.stdout)["verdict"], label)
            for mode in ("closed", "epipe"):
                with self.subTest(verdict=label, stdout=mode):
                    code, err = _run_with_hostile_stdout(argv, mode=mode, cwd=self.root)
                    self.assertEqual(code, EXIT_INTERNAL)
                    self.assertNotIn(code, (0, 2, 120))
                    text = err.decode("utf-8", "replace")
                    self.assertIn("runtime-assignment.py:", text)
                    self.assertIn("deliver", text)
                    self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()
