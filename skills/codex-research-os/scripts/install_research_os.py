#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import ctypes
import datetime as dt
import hashlib
import json
import os
import platform
import re
import secrets
import stat
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Iterator


COMMON_AGENT_RULES = """
Read repository instructions before acting. Preserve existing project conventions. Keep work to one smallest useful research unit unless the director assigns more. Write durable findings to the research OS ledgers. Do not promote claims without matching evidence and review. If the repo has an issue tracker, propose tracked work to the conductor before substantive changes. If the repo has an expertise/memory system, record non-obvious findings before finishing.
"""

POLICY_DIR = Path(__file__).parents[1] / "policy"
POLICY_PATH = POLICY_DIR / "runtime-assignment-receipt-v1.json"
NORMATIVE_CONTRACT_PATH = POLICY_DIR / "runtime-assignment-normative-contract-v1.json"
RUNTIME_FIELDS = (
    "schema_version",
    "requested_model_id",
    "requested_effort",
    "requested_context_form",
    "request_injection_status",
    "request_injection_evidence",
    "resolution_state",
    "resolved_provider",
    "resolved_model_id",
    "model_identity_basis",
    "model_readback_status",
    "model_readback_evidence",
    "effort_readback_status",
    "effort_readback_evidence",
    "effort_effective_divergence",
    "context_readback_status",
    "context_readback_evidence",
    "context_effective_divergence",
)
ONE_MILLION_CONTEXT_SEMANTICS = "A `[1m]` request or base-ID readback proves neither intelligence, upstream context capacity, compaction, nor effort compliance."
VALIDATION_ONLY_SEMANTICS = "The receipt is validated only for canonical internal consistency. It does not authenticate an issuer or prove external request injection, readback, spawn identity, or admission. The external authenticated harness is the sole spawn and admission authority."
SEEDS_READ_ONLY_SEMANTICS = "Every managed role is Seeds-read-only. No runtime, authority, or other protected block is excluded: managed roles must not create, claim, update, close, sync, disposition, label, delete, archive, or otherwise mutate Seeds. They may inspect through the accepted launcher and return advisory SeedProposal values to the conductor."
RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256 = "675c8799587b9b7151fd7f98f3424e5e9783986d2db9dc5488bb2a1a704b7794"
RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256 = "22c165551389b844fc46b8fcae2e7cd750254181ad2096b6884b0ee8f25b801c"
SOURCE_PINNED_REVIEWER_INSTRUCTIONS_SHA256 = {
    "adversarial_reviewer": "72c99c20fb4c96df000a0bd4cf3e06a665fba444fd2d3bd292e542805cd111fe",
    "replication_reviewer": "81e0c077a3a88e6ba21f74cee539120266a323f2f5362b7783a3089e272335de",
    "safety_reviewer": "dedc346315dd9cac63ed9d85576e6db6c6e4a85f0de9a53b7465c8452d962b5d",
}
RESEARCH_ROLE_IDS = frozenset(
    {
        "ablationist",
        "adversarial_reviewer",
        "benchmark_engineer",
        "counterexample_hunter",
        "data_engineer",
        "experimentalist",
        "formalizer",
        "knowledge_librarian",
        "literature_scout",
        "novelty_auditor",
        "replication_reviewer",
        "repo_cartographer",
        "research_director",
        "safety_reviewer",
        "synthesis_writer",
        "systems_engineer",
        "theorist",
    }
)
REVIEWER_OUTWARD_AUTHORITY_PATTERN = re.compile(
    r"(?i)\b(?:may|can|is\s+authorized\s+to|are\s+authorized\s+to|is\s+permitted\s+to|are\s+permitted\s+to)\b"
    r".{0,100}\b(?:push|publish(?:ing|ation)?|outward(?:\s+effect)?|merge|deploy(?:ment)?)\b"
)
SEEDS_MUTATION_AUTHORITY_PATTERN = re.compile(
    r"(?i)\b(?:may|can|should|will|is\s+authorized\s+to)\s+"
    r"(?:create|claim|update|close|sync|disposition|label|delete|archive|mutate)\b.{0,80}\b(?:Seeds?|SeedProposal)\b"
)
CANONICAL_RUNTIME_CONTRACT_SHA256 = "9399a0d9ebed19cefd020ac190ac772641e804e9f8a1632fb2b01059c94ba420"
EXACT_MODEL_PROVIDER_MAP = {
    "claude-fable-5": "anthropic",
    "claude-opus-4-8": "anthropic",
    "claude-sonnet-5": "anthropic",
    "gpt-5.6-luna": "openai",
    "gpt-5.6-sol": "openai",
    "gpt-5.6-terra": "openai",
}
EXACT_MODEL_PAIRS = {
    "frontier": ["gpt-5.6-sol", "claude-fable-5"],
    "judgment": ["gpt-5.6-terra", "claude-opus-4-8"],
    "volume": ["gpt-5.6-luna", "claude-sonnet-5"],
}
ALLOWED_EFFORTS = ["low", "medium", "high", "xhigh", "max"]
ALLOWED_CONTEXT_FORMS = ["base", "[1m]"]
ALLOWED_EVIDENCE = {
    "request_injection": {
        "source_kinds": ["immutable_request_receipt"],
        "statuses": ["verified"],
        "schemas": ["launcher-request-evidence/v1"],
    },
    "model_mapping": {
        "source_kinds": ["policy_exact_id_mapping"],
        "statuses": ["unavailable"],
        "schemas": ["runtime-assignment-policy-v1"],
    },
    "transport_readback": {
        "source_kinds": ["transport_readback"],
        "statuses": ["verified", "unavailable"],
        "schemas": ["runtime-assignment-readback/v1"],
    },
}
CERTIFIED_MODEL_ORDER = [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
]
CERTIFIED_CONTEXT_FORMS_BY_MODEL = {
    "claude-fable-5": ["base"],
    "claude-opus-4-8": ["base"],
    "claude-sonnet-5": ["base"],
    "gpt-5.6-luna": ["base", "[1m]"],
    "gpt-5.6-sol": ["base", "[1m]"],
    "gpt-5.6-terra": ["base", "[1m]"],
}
PRODUCTION_EFFORTS_BY_MODEL = {
    "claude-fable-5": ["xhigh", "max"],
    "claude-opus-4-8": ["high", "xhigh"],
    "claude-sonnet-5": ["high", "xhigh"],
    "gpt-5.6-luna": ["high", "xhigh"],
    "gpt-5.6-sol": ["high", "xhigh"],
    "gpt-5.6-terra": ["xhigh", "max"],
}


def certified_request_tuples() -> list[list[str]]:
    return [
        [model, effort, context]
        for model in CERTIFIED_MODEL_ORDER
        for context in CERTIFIED_CONTEXT_FORMS_BY_MODEL[model]
        for effort in ALLOWED_EFFORTS
    ]


def load_policy(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        content = path.read_bytes()
        policy = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(policy, dict):
        raise ValueError(f"{label} must be a JSON object")
    return policy, content


def runtime_policies() -> tuple[dict[str, object], dict[str, object]]:
    receipt, receipt_bytes = load_policy(POLICY_PATH, "runtime receipt policy")
    normative, _ = load_policy(NORMATIVE_CONTRACT_PATH, "normative runtime contract")
    contract = receipt.get("canonical_runtime_contract")
    if not isinstance(contract, str) or not contract:
        raise ValueError("runtime receipt policy must define a canonical runtime contract")
    if normative.get("canonical_receipt_policy_sha256") != hashlib.sha256(receipt_bytes).hexdigest():
        raise ValueError("normative runtime contract does not bind the packaged receipt policy")
    if normative.get("canonical_runtime_contract_sha256") != hashlib.sha256(contract.encode("utf-8")).hexdigest():
        raise ValueError("normative runtime contract does not bind the packaged runtime block")
    if normative.get("canonical_runtime_contract_sha256") != CANONICAL_RUNTIME_CONTRACT_SHA256:
        raise ValueError("normative runtime contract does not match the source-pinned canonical runtime authority contract")
    if normative.get("canonical_receipt_fields") != receipt.get("canonical_receipt_fields"):
        raise ValueError("packaged normative and receipt field contracts differ")
    if receipt.get("canonical_receipt_fields") != list(RUNTIME_FIELDS):
        raise ValueError("packaged receipt policy differs from the source-pinned canonical field order")
    if receipt.get("allowed_evidence") != ALLOWED_EVIDENCE:
        raise ValueError("packaged receipt policy allowed_evidence vocabulary differs from the source-pinned contract")
    if normative.get("allowed_evidence") != ALLOWED_EVIDENCE:
        raise ValueError("packaged normative contract allowed_evidence vocabulary differs from the source-pinned contract")
    if normative.get("exact_model_provider_map") != receipt.get("allowed_exact_model_ids"):
        raise ValueError("packaged normative and receipt model contracts differ")
    if normative.get("allowed_efforts") != receipt.get("allowed_efforts"):
        raise ValueError("packaged normative and receipt effort contracts differ")
    if normative.get("allowed_context_forms") != receipt.get("allowed_context_forms"):
        raise ValueError("packaged normative and receipt context contracts differ")
    if normative.get("certified_request_tuples") != receipt.get("certified_request_tuples"):
        raise ValueError("packaged normative and receipt tuple contracts differ")
    source_pins = {
        "exact_model_provider_map": EXACT_MODEL_PROVIDER_MAP,
        "exact_model_pairs": EXACT_MODEL_PAIRS,
        "allowed_efforts": ALLOWED_EFFORTS,
        "allowed_context_forms": ALLOWED_CONTEXT_FORMS,
        "allowed_evidence": ALLOWED_EVIDENCE,
        "certified_context_forms_by_model": CERTIFIED_CONTEXT_FORMS_BY_MODEL,
        "certified_request_tuples": certified_request_tuples(),
        "production_efforts_by_model": PRODUCTION_EFFORTS_BY_MODEL,
        "validation_only_semantics": VALIDATION_ONLY_SEMANTICS,
        "one_million_context_semantics": ONE_MILLION_CONTEXT_SEMANTICS,
        "seeds_read_only_semantics": SEEDS_READ_ONLY_SEMANTICS,
        "research_director_seeds_contract_sha256": RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256,
    }
    for field, expected in source_pins.items():
        if normative.get(field) != expected:
            raise ValueError(f"packaged normative contract {field} differs from the source-pinned contract")
    return receipt, normative


RECEIPT_POLICY, NORMATIVE_CONTRACT = runtime_policies()


def canonical_runtime_model_assignment() -> str:
    contract = RECEIPT_POLICY["canonical_runtime_contract"]
    assert isinstance(contract, str)
    return contract


RUNTIME_MODEL_ASSIGNMENT = canonical_runtime_model_assignment()
# Canonical content is policy-owned at runtime; this phrase preserves the source-level role contract.
RUNTIME_MODEL_ASSIGNMENT_SOURCE = "conductor-supplied certified `RuntimeAssignment`"
RUNTIME_MODEL_ASSIGNMENT_INJECTION = "Exact model and effort request injection is mandatory and immutable"
RUNTIME_MODEL_ASSIGNMENT_READBACK = "Effective effort and context may honestly be unavailable"
RUNTIME_MODEL_ASSIGNMENT_BOUNDARY = "stop before spawn"
RUNTIME_MODEL_ASSIGNMENT_NO_COPIED_READBACK = "Prompt echoes and copied requested values never become resolution or readback evidence"

RESEARCH_DIRECTOR_SEEDS_AUTHORITY = """Seeds authority:
- Research Director is Seeds-read-only.
- Use only the exact accepted Seeds inspection contract:
  `Seeds(<target>, <args...>)` = `MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec node@22.23.2 bun@1.4.0 npm:@os-eco/seeds-cli@0.5.15 -- sd <args>`.
- Inspect `Seeds(<target>, prime)`, `Seeds(<target>, ready --format json)`, and `Seeds(<target>, blocked --format json)` before substantive orchestration when Seeds is available.
- Do not create, claim, update, close, sync, or disposition Seeds.
- For work that outlives the session, emit exactly one typed `SeedProposal { title: str, summary: str, acceptance_criteria: list[str], priority: str, blocking: bool, scope: list[str], evidence: list[str], dependencies: list[str], recommended_owner: str }` for conductor triage.
"""


def validate_source_pinned_role_authority() -> None:
    instructions_by_role = developer_instructions_by_role()
    director = instructions_by_role["research_director"]
    if hashlib.sha256(director.encode("utf-8")).hexdigest() != RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256:
        raise ValueError("source-pinned protected role authority content differs for Research Director")
    protected_director = clean(RESEARCH_DIRECTOR_SEEDS_AUTHORITY)
    if director.count(protected_director) != 1:
        raise ValueError("source-pinned protected role authority requires the exact Research Director Seeds block once")
    if SEEDS_MUTATION_AUTHORITY_PATTERN.search(director.replace(protected_director, "", 1)):
        raise ValueError("source-pinned protected role authority forbids Research Director Seeds mutation authority")
    for role, expected_digest in SOURCE_PINNED_REVIEWER_INSTRUCTIONS_SHA256.items():
        instructions = instructions_by_role[role]
        if hashlib.sha256(instructions.encode("utf-8")).hexdigest() != expected_digest:
            raise ValueError(f"source-pinned protected role authority content differs for {role}")
        if REVIEWER_OUTWARD_AUTHORITY_PATTERN.search(instructions):
            raise ValueError(f"source-pinned protected role authority forbids outward reviewer authority for {role}")


AGENTS = {
    "research_director": (
        "Coordinates the research team, selects next actions, assigns specialists, and enforces claim discipline.",
        "workspace-write",
        """
You are the research director for this repository. Begin by reading AGENTS.md, research/README.md, research/charter.md, research/problem_statement.md, research/status.md, research/state/current_focus.md, research/state/next_action.md, research/state/resume_context.md, research/claims/claims.yaml, research/research_journal.md, research/memory/best.md, and research/memory/failed_attempts.md.

Classify work as greenfield, brownfield, or hybrid. Identify the highest-leverage uncertainty. Select exactly one smallest useful unit of work. Assign the right specialist while keeping shared files lead-owned. Validate specialist outputs against schemas and review gates. Update status, next_action, resume_context, claims, and memory. Prevent overclaiming: evidence before synthesis and review before promotion.
"""
        + RESEARCH_DIRECTOR_SEEDS_AUTHORITY
        + """
End with current state, strongest evidence, weakest assumption, exact next action, and recommended next agent.
""",
    ),
    "repo_cartographer": (
        "Maps an existing codebase, architecture, entrypoints, tests, data flow, docs, and research extension points.",
        "workspace-write",
        """
You are the repository cartographer. Use this role for brownfield mapping. Read AGENTS.md first. Map repository structure, core modules, entrypoints, build/test commands, data flow, experiment harnesses, current docs, TODOs, blockers, and research-relevant extension points. Write findings incrementally to research/memory/repo_map.md and setup blockers to research/state/blockers.md. Do not modify code or infer unsupported claims. Record non-obvious repository facts before finishing.
""",
    ),
    "literature_scout": (
        "Finds, reads, and summarizes prior work, papers, benchmarks, and related systems.",
        "workspace-write",
        """
You are the literature scout. Map prior art rather than solving the project or declaring novelty. Read AGENTS.md and research/workflows/literature_discovery.md. Prefer primary sources and the repository's research workflow when doing live research. For each source extract citation, contribution, method, assumptions, results, benchmarks, limitations, relevance, follow-up sources, and warnings. Write paper notes under research/literature/paper_notes/ and update literature_map.md, prior_art_matrix.md, and reading_queue.yaml. Mark uncertain citations and record non-obvious source relationships.
""",
    ),
    "novelty_auditor": (
        "Evaluates whether an idea, claim, method, or result is novel relative to prior work.",
        "workspace-write",
        """
You are the novelty auditor. Assume every idea may already exist. Search prior art, identify nearest neighbors, compare mechanisms rather than wording, separate a new combination from a new principle, and classify novelty as none, incremental, new application, new combination, new mechanism, or new theorem/result. Write to research/reviews/novelty_reviews.md, research/literature/prior_art_matrix.md, and claim downgrades in research/claims/claims.yaml. Default status is unknown_novelty; never mark an idea novel without evidence.
""",
    ),
    "theorist": (
        "Generates hypotheses, mechanisms, proof strategies, reductions, invariants, and conceptual models.",
        "workspace-write",
        """
You are the theorist. Generate candidate explanations and strategies. For each candidate include a hypothesis or theorem statement, mechanism, why it might be true, required assumptions, consequences, falsifier, minimal validation step, and related prior work if known. Propose at least five independent strategies before converging, including one long-shot approach. Do not polish conclusions or promote claims. Write candidates as untested unless validated, and update research/ideas/idea_bank.yaml, research/claims/claims.yaml, and research/proofs/theorem_statements.md when applicable.
""",
    ),
    "counterexample_hunter": (
        "Searches for counterexamples, edge cases, failures, and minimal falsifying examples.",
        "workspace-write",
        """
You are the counterexample hunter. Try to falsify claims. For mathematical claims, formalize the predicate, enumerate small cases, search random larger and adversarial cases, and minimize any counterexample. For empirical or system claims, test edge workloads, degenerate inputs, assumptions, and regressions. Write coverage and failures under research/experiments/counterexamples/, research/reviews/adversarial_reviews.md, and research/claims/claims.yaml. Never claim no counterexample exists; state only the search space covered.
""",
    ),
    "formalizer": (
        "Turns claims, theorems, specs, and proof sketches into formal statements or machine-checkable artifacts.",
        "workspace-write",
        """
You are the formalizer. Preserve exact meaning while making claims checkable. Extract the exact statement, define terms, list assumptions, choose Lean, Coq, SMT, an executable property test, or a type/spec contract, encode it, attempt a proof or partial proof, and record blockers. Write to research/proofs/formal/, research/claims/proof_gaps.yaml, and research/proofs/proof_reviews.md. Do not silently strengthen or weaken statements; stop and mark ambiguity when needed.
""",
    ),
    "experimentalist": (
        "Designs and runs experiments, logs metrics, and validates hypotheses with executable evidence.",
        "workspace-write",
        """
You are the experimentalist. Before running, state the hypothesis, baseline, metrics, success criteria, failure criteria, and cheapest decisive experiment. During the run, log commands, configs, metrics, outputs, and failures. Afterwards, compare with the baseline, update the registry and claims, and recommend the next step. Write to research/experiments/registry.yaml, research/experiments/runs/{run_id}/, research/experiments/results/, and research/research_journal.md. No improvement claim is valid until a baseline is reproduced or explicitly defined.
""",
    ),
    "benchmark_engineer": (
        "Builds benchmark harnesses, baselines, evaluation scripts, and comparison matrices.",
        "workspace-write",
        """
You are the benchmark engineer. Make evaluation fair and repeatable. Create or improve benchmark harnesses, baseline commands, metric definitions, dataset splits, reproducible configs, comparison tables, and regression tests. Write to research/benchmarks/benchmark_plan.md, research/benchmarks/baseline_results.yaml, research/benchmarks/comparison_matrix.md, and project-native test locations when directed. Do not optimize the method; optimize evaluation reliability.
""",
    ),
    "data_engineer": (
        "Audits datasets, preprocessing, data lineage, leakage risk, and dataset validity.",
        "workspace-write",
        """
You are the data engineer. Audit data sources, visible licensing, splits, preprocessing, leakage risk, distribution shift, missing values, label quality, reproducibility, and storage layout. Write to research/data/data_inventory.md, research/data/data_lineage.yaml, research/data/preprocessing.md, and research/data/validation_report.md. If data is not trustworthy, block empirical claims.
""",
    ),
    "systems_engineer": (
        "Improves infrastructure, runtime, performance, reliability, and developer ergonomics.",
        "workspace-write",
        """
You are the systems engineer. Focus on reproducible environment, build/test reliability, runtime performance, logging, experiment execution, CI hooks, resource usage, and failure recovery. Write to scripts/, Makefile, research/state/blockers.md, and research/benchmarks/comparison_matrix.md when performance changes. Do not change research claims; provide infrastructure evidence only.
""",
    ),
    "ablationist": (
        "Runs systematic ablations to determine which components are load-bearing.",
        "workspace-write",
        """
You are the ablationist. Read the current best result. Identify every non-default or nontrivial component: architecture choice, optimizer, scheduler, data augmentation, prompt or retrieval component, proof lemma, system optimization, or heuristic. Define one ablated version at a time, keep comparisons fair, and log metric deltas. Record the component, original and ablated settings, interpretation, and whether it is load-bearing in research/experiments/templates/ablation_plan.md, research/experiments/results/ablation_{timestamp}.md, and research/claims/claims.yaml. Neutral ablations should downgrade mechanism claims.
""",
    ),
    "replication_reviewer": (
        "Checks whether experiments and results are reproducible.",
        "workspace-write",
        """
You are the replication reviewer. Assess whether a result can be reproduced. Check code version, command, config, dataset, environment, hardware, random seed, metrics, logs, and baseline comparison. Verdicts are reproducible, probably reproducible, under-specified, not reproducible, or invalid. Write to research/reviews/replication_reviews.md, research/experiments/registry.yaml, and claim downgrades in research/claims/claims.yaml. Do not approve your own experiments.
""",
    ),
    "adversarial_reviewer": (
        "Strictly attacks claims, proofs, experiments, novelty, and conclusions.",
        "workspace-write",
        """
You are the adversarial reviewer. Be strict and prevent false progress. Attack main claims, assumptions, methodology, baselines, proof gaps, experimental design, metrics, novelty, reproducibility, safety, and unsupported conclusions. Verdicts are accept, weak_accept, needs_repair, reject, or falsified. Write to research/reviews/adversarial_reviews.md, research/reviews/review_queue.yaml, and claim downgrades in research/claims/claims.yaml. Do not be polite at the cost of accuracy.
""",
    ),
    "synthesis_writer": (
        "Writes grounded summaries, technical reports, papers, and final recommendations from validated evidence.",
        "workspace-write",
        """
You are the synthesis writer. Synthesize only from research/claims/claims.yaml, the experiment registry, literature notes, review files, proof files, benchmark results, and research journal. Do not invent claims, hide negative results, or overstate novelty. Write to research/reports/technical_report.md, research/reports/paper_draft.md, research/reports/final_recommendation.md, and research/status.md. Include what was attempted, what worked, what failed, what is supported, what remains uncertain, and next steps. Run review gates before final claims.
""",
    ),
    "knowledge_librarian": (
        "Maintains memory, research journal, lessons learned, failed attempts, and open questions.",
        "workspace-write",
        """
You are the knowledge librarian. Maintain research/research_journal.md, research/memory/best.md, observations.md, lessons_learned.md, failed_attempts.md, useful_patterns.md, open_questions.md, and research/state/resume_context.md. Preserve negative results, deduplicate stale notes, keep summaries short but specific, and link observations to evidence files. Never change claim status without evidence.
""",
    ),
    "safety_reviewer": (
        "Reviews security, privacy, destructive action risk, compliance, and operational safety.",
        "workspace-write",
        """
You are the safety reviewer. Review destructive file operations, credential exposure, unsafe shell commands, data privacy, license risk, unbounded spend, network access, production impact, model/tool misuse, and hidden-state reproducibility risk. Write to research/reviews/safety_reviews.md and research/state/blockers.md. Block actions that risk data loss, credential leakage, or uncontrolled spend.
""",
    ),
}


def validate_packaged_managed_roles() -> None:
    validate_source_pinned_role_authority()
    try:
        roles = NORMATIVE_CONTRACT["managed_roles"]["research"]["roles"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid packaged managed role contract: {exc}") from exc
    if not isinstance(roles, dict) or set(roles) != RESEARCH_ROLE_IDS or set(AGENTS) != RESEARCH_ROLE_IDS:
        raise ValueError("packaged managed role roster differs from the source-pinned 17 Research OS roles")
    for role, (description, sandbox, _) in AGENTS.items():
        spec = roles.get(role)
        if not isinstance(spec, dict):
            raise ValueError(f"invalid packaged managed role contract for {role}")
        instructions = developer_instructions_by_role()[role]
        manifest = agent_toml(role, description, sandbox, AGENTS[role][2])
        expected = {
            "path": f"agents/codex/research/{role}.toml",
            "sandbox_mode": sandbox,
            "description_sha256": hashlib.sha256(description.encode("utf-8")).hexdigest(),
            "developer_instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
        }
        if spec != expected:
            raise ValueError(f"packaged managed role contract differs from generator role {role}")


WORKFLOWS = {
    "research_loop.md": """
# Research Loop

1. Read current state: status, current_focus, next_action, claims, journal, best memory, and failed attempts.
2. Identify the highest-leverage uncertainty.
3. Choose exactly one primary action: read one paper, run one experiment, formalize one claim, search counterexamples, review, reproduce baseline, update benchmark, or synthesize.
4. Invoke the relevant specialist.
5. Validate output.
6. Update claims, journal, status, next_action, and memory.
7. End with what changed, what is supported, what is falsified, what is uncertain, and exact next action.
""",
    "greenfield_loop.md": """
# Greenfield Research Loop

Use when starting from a broad domain.

1. Define research area.
2. Generate candidate ideas.
3. Score novelty, feasibility, falsifiability, impact, compute cost, and literature risk.
4. Run literature scout on top candidates.
5. Run novelty auditor.
6. Select one candidate.
7. Define cheapest decisive experiment or proof check.
8. Run experiment or formalization.
9. Run adversarial review.
10. Kill, iterate, pivot, or promote.

Never call an idea novel until novelty audit passes.
""",
    "brownfield_loop.md": """
# Brownfield Research Loop

Use when the repo, paper, benchmark, or codebase already exists.

1. Run repo cartographer.
2. Identify build, test, and benchmark commands.
3. Find or define baseline.
4. Reproduce baseline when feasible.
5. Read existing docs and prior work.
6. Inventory claims conservatively.
7. Identify gaps or extension points.
8. Run cheapest decisive experiment.
9. Compare to baseline.
10. Run replication and adversarial review.
11. Update claims, status, next_action, and memory.
""",
    "literature_discovery.md": """
# Literature Discovery

Read literature map and queue. Pick one source. Extract citation, contribution, method, assumptions, results, limitations, relevance, and follow-up sources. Update paper notes, prior-art matrix, and queue. Add claims only as literature_supported or unknown_novelty.
""",
    "paper_reproduction.md": """
# Paper Reproduction

Read target paper. Extract method, data, metrics, hyperparameters, and hardware. Identify minimal reproducible result. Implement or locate baseline. Run smallest reproduction. Compare to paper. Log deviations. Run replication review. Update claims.
""",
    "experiment_execution.md": """
# Experiment Execution

State hypothesis, linked claims, baseline, metrics, success criteria, and failure criteria. Create a run directory. Save config, logs, metrics, and outputs. Compare to baseline. Update registry and claims.
""",
    "counterexample_search.md": """
# Counterexample Search

Select target claim, formalize predicate, enumerate small cases, test edge/random cases, minimize failures, save counterexamples, downgrade or falsify claim, and record search coverage.
""",
    "formalization.md": """
# Formalization

Select claim, rewrite precise statement, list definitions and assumptions, choose formal target, encode statement, attempt proof/checker, record proof gaps, and update claim status.
""",
    "ablation.md": """
# Ablation

Read target result, identify one component, define original and ablated settings, keep comparison fair, run or plan ablation, log metric delta, decide load-bearing status, and update claims.
""",
    "strict_review.md": """
# Strict Review

Attack claim validity, assumptions, baselines, metrics, proof gaps, novelty, reproducibility, safety, hidden dependencies, and unsupported conclusions. Return verdict and required repairs.
""",
    "synthesis.md": """
# Synthesis

Read validated evidence, run review gates, summarize only supported claims, preserve negative results, list uncertainty, and end with next actions.
""",
    "next_action_selection.md": """
# Next Action Selection

Ask: What is the research question? What counts as progress? What cheapest test could falsify the hypothesis? What is known? What is the dangerous assumption? Which specialist should run? What evidence would change our mind?
""",
}


SCHEMAS = {
    "claim.schema.yaml": """
name: claim
required: [id, claim, claim_type, status, evidence, counterevidence, assumptions, validation_required, last_updated, owner_agent]
claim_type: [theorem, conjecture, empirical, implementation, literature, benchmark, safety, novelty]
status: [untested, unknown_novelty, literature_supported, small_case_supported, experimentally_supported, falsified, informally_proved, reviewed, formally_specified, formally_proved]
""",
    "experiment.schema.yaml": """
name: experiment
required: [id, title, hypothesis, claim_ids, baseline, method, success_criteria, failure_criteria, command, config_path, metrics_path, artifact_paths, status, result_summary, review_status]
status: [planned, running, failed, completed, invalid, superseded]
review_status: [unreviewed, replication_reviewed, adversarially_reviewed, rejected]
""",
    "idea.schema.yaml": """
name: idea
required: [id, title, description, source, novelty_score, feasibility_score, falsifiability_score, impact_score, compute_cost, literature_risk, nearest_prior_work, cheapest_decisive_experiment, status]
compute_cost: [low, medium, high]
literature_risk: [low, medium, high, unknown]
status: [proposed, rejected, needs_literature_review, ready_for_experiment, under_experiment, promoted_to_project, falsified]
""",
    "literature_note.schema.yaml": """
name: literature_note
required: [id, citation, source_url, contribution, method, assumptions, reported_results, limitations, relevance, follow_up_sources]
""",
    "review.schema.yaml": """
name: review
required: [id, review_type, target, target_claim_ids, verdict, severity, findings, required_repairs, claim_status_changes, reviewer_agent, date]
review_type: [adversarial, replication, novelty, safety, proof]
verdict: [accept, weak_accept, needs_repair, reject, falsified]
severity: [low, medium, high, critical]
""",
    "decision.schema.yaml": """
name: decision
required: [id, date, title, decision, rationale, alternatives_considered, evidence, owner_agent, status]
status: [proposed, accepted, superseded, rejected]
""",
}


def clean(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def agent_toml(name: str, description: str, sandbox: str, body: str) -> str:
    instructions = clean(RUNTIME_MODEL_ASSIGNMENT + "\n" + body + "\n" + COMMON_AGENT_RULES).replace('"""', '\\"\\"\\"')
    return (
        f'name = "{name}"\n'
        f'description = "{description}"\n'
        f'sandbox_mode = "{sandbox}"\n\n'
        'developer_instructions = """\n'
        f'{instructions}'
        '"""\n'
    )


def developer_instructions_by_role() -> dict[str, str]:
    return {
        name: clean(RUNTIME_MODEL_ASSIGNMENT + "\n" + body + "\n" + COMMON_AGENT_RULES)
        for name, (_, _, body) in AGENTS.items()
    }


def script_files() -> dict[str, str]:
    lib = r'''
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_PATH = ROOT / "research" / "claims" / "claims.yaml"
EXPERIMENTS_PATH = ROOT / "research" / "experiments" / "registry.yaml"

def read_text(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default

def load_structured(path: Path, default: Any) -> Any:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        data = yaml.safe_load(text)
        return default if data is None else data
    except ModuleNotFoundError:
        if text.strip().endswith(": []"):
            return {text.split(":", 1)[0].strip(): []}
        return json.loads(text)

def as_records(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list")
        return [x for x in value if isinstance(x, dict)]
    return []

def count_by(records: list[dict[str, Any]], field: str) -> Counter:
    return Counter(str(record.get(field, "missing")) for record in records)

def evidence_text(record: dict[str, Any]) -> str:
    chunks = []
    for key in ("evidence", "review_evidence", "counterevidence", "artifact_paths"):
        value = record.get(key, [])
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        elif value:
            chunks.append(str(value))
    return " ".join(chunks).lower()
'''
    status = r'''
#!/usr/bin/env python3
from research_os_lib import CLAIMS_PATH, EXPERIMENTS_PATH, ROOT, as_records, count_by, load_structured, read_text

def first(path):
    text = read_text(path).strip()
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            return line.strip()
    return text.splitlines()[0] if text else "(empty)"

claims = as_records(load_structured(CLAIMS_PATH, {"claims": []}), "claims")
experiments = as_records(load_structured(EXPERIMENTS_PATH, {"experiments": []}), "experiments")
print("# Research OS Status\n")
print("Current focus:", first(ROOT / "research/state/current_focus.md"))
print("Next action:", first(ROOT / "research/state/next_action.md"))
print("\nClaims by status:")
for key, value in sorted(count_by(claims, "status").items()):
    print(f"  {key}: {value}")
if not claims:
    print("  none")
print("\nExperiments by status:")
for key, value in sorted(count_by(experiments, "status").items()):
    print(f"  {key}: {value}")
if not experiments:
    print("  none")
'''
    validate_agents = r'''
#!/usr/bin/env python3
import hashlib, re, tomllib
from research_os_lib import ROOT

agents_dir = ROOT / ".codex" / "agents"
allowed_keys = {"name", "description", "sandbox_mode", "developer_instructions"}
runtime_fields = __RUNTIME_FIELDS__
expected_roles = __MANAGED_ROLE_CONTRACTS__
source_pinned_reviewer_instructions = __SOURCE_PINNED_REVIEWER_INSTRUCTIONS__
protected_runtime = __RUNTIME_CONTRACT__
protected_director = __DIRECTOR_CONTRACT__
contradictory_runtime = re.compile(r"(?i)\b(?:RuntimeAssignment|request_injection|resolved_(?:provider|model_id)|model_readback|effort_readback|context_readback|provider[- ]default|host[- ]default|caller[- ]override|requested(?:_model_id|_effort|_context_form)?.{0,80}(?:resolved|readback)|(?:resolved|readback).{0,80}requested(?:_model_id|_effort|_context_form)?)")
contradictory_authority = re.compile(r"(?i)\b(?:repository|role|agent|worker|receipt|local\s+validation|local\s+status|passing\s+(?:local\s+)?gate)\b.{0,80}\b(?:may|can|is\s+authorized\s+to|authori[sz](?:e|es|ed)?|grant(?:s|ed)?)\b.{0,80}\b(?:external\s+)?(?:spawn|admission|readback)\b")
contradictory_capacity = re.compile(r"(?i)\[1m\].{0,100}\bproves?\b.{0,100}\b(?:capacity|intelligence|compaction|effort)\b")
contradictory_seeds = re.compile(r"(?i)\b(?:may|can|should|will|is\s+authorized\s+to)\s+(?:create|claim|update|close|sync|disposition|label|delete|archive|mutate)\b.{0,80}\b(?:Seeds?|SeedProposal)\b")
contradictory_publication = re.compile(r"(?i)\b(?:local\s+validation|passing\s+(?:local\s+)?gate|local\s+status)\b.{0,80}\b(?:sufficient|authori[sz](?:e|es|ed)?|grant(?:s|ed)?|permit(?:s|ted)?)\b.{0,80}\b(?:push|publish(?:ing|ation)?|merge|deploy(?:ment)?|outward)\b")
forbidden_seed_authority_addition = re.compile(r"(?i)\b(?:seeds?|seedproposal|sd)\b")
errors = []
files = sorted(agents_dir.glob("*.toml")) if agents_dir.exists() else []
actual_roles = {path.stem for path in files}
if actual_roles != set(expected_roles):
    errors.append(
        "managed role roster mismatch: expected "
        + ", ".join(sorted(expected_roles))
        + "; got "
        + ", ".join(sorted(actual_roles))
    )
for path in files:
    label = path.relative_to(ROOT)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"{label}: invalid TOML: {exc}")
        continue
    unknown = sorted(set(data) - allowed_keys)
    if unknown:
        errors.append(f"{label}: unknown top-level keys that Codex may ignore: {', '.join(unknown)}")
    for required in ("name", "description", "developer_instructions"):
        if not data.get(required):
            errors.append(f"{label}: missing required field {required}")
    if data.get("name") != path.stem:
        errors.append(f"{label}: name {data.get('name')!r} does not match filename stem {path.stem!r}")
    instructions = data.get("developer_instructions", "")
    expected = expected_roles.get(path.stem)
    if expected is None:
        errors.append(f"{label}: not in the managed role roster")
    else:
        description = data.get("description")
        if not isinstance(description, str) or hashlib.sha256(description.encode("utf-8")).hexdigest() != expected["description_sha256"]:
            errors.append(f"{label}: description differs from generation-time canonical content")
        if not isinstance(instructions, str) or hashlib.sha256(instructions.encode("utf-8")).hexdigest() != expected["developer_instructions_sha256"]:
            errors.append(f"{label}: developer instructions differ from generation-time canonical content")
        if data.get("sandbox_mode") != expected["sandbox_mode"]:
            errors.append(f"{label}: sandbox_mode differs from the managed role contract")
    if path.stem in source_pinned_reviewer_instructions and (
        not isinstance(instructions, str)
        or hashlib.sha256(instructions.encode("utf-8")).hexdigest() != source_pinned_reviewer_instructions[path.stem]
    ):
        errors.append(f"{label}: protected reviewer authority content differs from source-pinned canonical content")
    missing_runtime = sorted(field for field in runtime_fields if field not in instructions)
    if missing_runtime:
        errors.append(f"{label}: runtime model assignment contract missing {', '.join(missing_runtime)}")
    outside_runtime = instructions
    if instructions.count(protected_runtime) != 1:
        errors.append(f"{label}: protected runtime block must occur exactly once")
    else:
        outside_runtime = instructions.replace(protected_runtime, "", 1)
        if contradictory_runtime.search(outside_runtime):
            errors.append(f"{label}: additive runtime restatement or requested-to-readback/host-default mutation is forbidden")
        authority_text = outside_runtime.replace(protected_runtime, "", 1)
        if any(
            pattern.search(authority_text)
            for pattern in (
                contradictory_authority,
                contradictory_capacity,
                contradictory_seeds,
                contradictory_publication,
            )
        ):
            errors.append(f"{label}: contradictory runtime authority language is forbidden")
    if "model" in data:
        errors.append(f"{label}: static model is forbidden; the conductor must inject the exact requested model at spawn")
    if "model_reasoning_effort" in data:
        errors.append(f"{label}: static model_reasoning_effort is forbidden; the conductor must inject requested_effort at spawn")
    sandbox = data.get("sandbox_mode")
    if sandbox is not None and not isinstance(sandbox, str):
        errors.append(f"{label}: unsupported sandbox_mode {sandbox!r}")
    if path.stem == "research_director":
        director_count = instructions.count(protected_director)
        if director_count != 1:
            errors.append(f"{label}: protected Seeds authority block must occur exactly once")
            director_outside = outside_runtime
        else:
            director_outside = outside_runtime.replace(protected_director, "", 1)
        if forbidden_seed_authority_addition.search(director_outside):
            errors.append(f"{label}: additive Seeds or SeedProposal authority language is forbidden")
print(f"Validated {len(files)} agent config(s).")
for error in errors:
    print("ERROR:", error)
raise SystemExit(1 if errors else 0)
'''.replace("__RUNTIME_FIELDS__", repr(tuple(RECEIPT_POLICY["canonical_receipt_fields"]))).replace(
    "__MANAGED_ROLE_CONTRACTS__",
    repr({
        role: {
            "sandbox_mode": spec[1],
            "description_sha256": hashlib.sha256(spec[0].encode("utf-8")).hexdigest(),
            "developer_instructions_sha256": hashlib.sha256(
                developer_instructions_by_role()[role].encode("utf-8")
            ).hexdigest(),
        }
        for role, spec in AGENTS.items()
    }),
).replace(
    "__SOURCE_PINNED_REVIEWER_INSTRUCTIONS__", repr(SOURCE_PINNED_REVIEWER_INSTRUCTIONS_SHA256)
).replace("__RUNTIME_CONTRACT__", repr(clean(RUNTIME_MODEL_ASSIGNMENT))).replace("__DIRECTOR_CONTRACT__", repr(clean(RESEARCH_DIRECTOR_SEEDS_AUTHORITY)))
    validate_claims = r'''
#!/usr/bin/env python3
from research_os_lib import CLAIMS_PATH, as_records, load_structured

required = {"id","claim","claim_type","status","evidence","counterevidence","assumptions","validation_required","last_updated","owner_agent"}
promoted = {"literature_supported","small_case_supported","experimentally_supported","informally_proved","reviewed","formally_specified","formally_proved"}
claims = as_records(load_structured(CLAIMS_PATH, {"claims": []}), "claims")
errors = []
seen = set()
for i, claim in enumerate(claims, 1):
    label = claim.get("id") or f"claim[{i}]"
    missing = sorted(required - set(claim))
    if missing:
        errors.append(f"{label}: missing {', '.join(missing)}")
    if claim.get("id") in seen:
        errors.append(f"{label}: duplicate id")
    seen.add(claim.get("id"))
    if claim.get("status") in promoted and not claim.get("evidence"):
        errors.append(f"{label}: promoted status requires evidence")
print(f"Validated {len(claims)} claim(s).")
for error in errors:
    print("ERROR:", error)
raise SystemExit(1 if errors else 0)
'''
    validate_experiments = r'''
#!/usr/bin/env python3
from pathlib import Path
from research_os_lib import EXPERIMENTS_PATH, ROOT, as_records, load_structured

required = {"id","title","hypothesis","claim_ids","baseline","method","success_criteria","failure_criteria","command","config_path","metrics_path","artifact_paths","status","result_summary","review_status"}
experiments = as_records(load_structured(EXPERIMENTS_PATH, {"experiments": []}), "experiments")
errors = []
seen = set()
for i, exp in enumerate(experiments, 1):
    label = exp.get("id") or f"experiment[{i}]"
    missing = sorted(required - set(exp))
    if missing:
        errors.append(f"{label}: missing {', '.join(missing)}")
    if exp.get("id") in seen:
        errors.append(f"{label}: duplicate id")
    seen.add(exp.get("id"))
    if exp.get("status") == "completed":
        for field in ("command", "config_path", "metrics_path", "result_summary"):
            if not exp.get(field):
                errors.append(f"{label}: completed experiment requires {field}")
        for field in ("config_path", "metrics_path"):
            value = exp.get(field)
            if value:
                path = Path(value)
                if not path.is_absolute():
                    path = ROOT / path
                if not path.exists():
                    errors.append(f"{label}: {field} not found: {value}")
print(f"Validated {len(experiments)} experiment(s).")
for error in errors:
    print("ERROR:", error)
raise SystemExit(1 if errors else 0)
'''
    review_gates = r'''
#!/usr/bin/env python3
from research_os_lib import CLAIMS_PATH, as_records, evidence_text, load_structured

claims = as_records(load_structured(CLAIMS_PATH, {"claims": []}), "claims")
errors = []
for claim in claims:
    cid = claim.get("id", "missing-id")
    status = claim.get("status")
    ctype = claim.get("claim_type")
    text = (claim.get("claim") or "").lower()
    important = claim.get("importance") in {"high", "critical"} or status in {"experimentally_supported","informally_proved","reviewed","formally_specified","formally_proved"}
    if not important:
        continue
    ev = evidence_text(claim)
    if ctype in {"empirical", "benchmark"} and status in {"experimentally_supported", "reviewed"} and "replication" not in ev:
        errors.append(f"{cid}: empirical/benchmark claim needs replication review evidence")
    if ctype in {"theorem", "conjecture"} and status in {"informally_proved", "reviewed", "formally_specified", "formally_proved"} and not any(x in ev for x in ("proof", "formal", "lean", "coq", "smt")):
        errors.append(f"{cid}: proof-like claim needs proof/formalization evidence")
    if (ctype == "novelty" or "novel" in text) and status != "unknown_novelty" and not any(x in ev for x in ("novelty", "prior art", "prior_art")):
        errors.append(f"{cid}: novelty-like claim needs novelty review evidence")
    if important and status not in {"untested", "unknown_novelty", "falsified"} and not any(x in ev for x in ("adversarial", "review")):
        errors.append(f"{cid}: important promoted claim needs adversarial review evidence")
if errors:
    print("Review gates failed:")
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)
print(f"Review gates passed for {len(claims)} claim(s).")
'''
    create_experiment = r'''
#!/usr/bin/env python3
import argparse, datetime as dt, json, re
from pathlib import Path
from research_os_lib import EXPERIMENTS_PATH, ROOT, as_records, load_structured

def slug(text):
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")[:60] or "experiment"

parser = argparse.ArgumentParser()
parser.add_argument("--title", default="untitled experiment")
args = parser.parse_args()
stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
run_id = f"{stamp}-{slug(args.title)}"
rel = Path("research/experiments/runs") / run_id
path = ROOT / rel
path.mkdir(parents=True, exist_ok=False)
(path / "config.yaml").write_text(f"id: {json.dumps(run_id)}\ntitle: {json.dumps(args.title)}\n", encoding="utf-8")
(path / "metrics.jsonl").write_text("", encoding="utf-8")
(path / "experiment_card.md").write_text("# Experiment Card\n\n## Hypothesis\n\n## Baseline\n\n## Metrics\n\n## Results\n", encoding="utf-8")
records = as_records(load_structured(EXPERIMENTS_PATH, {"experiments": []}), "experiments")
records.append({"id": run_id, "title": args.title, "hypothesis": "", "claim_ids": [], "baseline": "", "method": "", "success_criteria": "", "failure_criteria": "", "command": "", "config_path": str(rel / "config.yaml"), "metrics_path": str(rel / "metrics.jsonl"), "artifact_paths": [str(rel / "experiment_card.md")], "status": "planned", "result_summary": "", "review_status": "unreviewed"})
lines = ["experiments:"]
for r in records:
    lines.append(f"  - id: {json.dumps(r['id'])}")
    for key, value in r.items():
        if key != "id":
            lines.append(f"    {key}: {json.dumps(value)}")
EXPERIMENTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(path)
'''
    compare_runs = r'''
#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def load(run):
    run = Path(run)
    out = {}
    if (run / "metrics.json").exists():
        data = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        out.update({k: float(v) for k, v in data.items() if isinstance(v, (int, float))})
    if (run / "metrics.jsonl").exists():
        for line in (run / "metrics.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if isinstance(row.get("value"), (int, float)):
                    out[str(row.get("metric") or row.get("name"))] = float(row["value"])
    return out

parser = argparse.ArgumentParser()
parser.add_argument("run_a", nargs="?")
parser.add_argument("run_b", nargs="?")
args = parser.parse_args()
if not args.run_a or not args.run_b:
    parser.print_help()
    raise SystemExit(0)
a, b = load(args.run_a), load(args.run_b)
print("| metric | run_a | run_b | delta |")
print("| --- | ---: | ---: | ---: |")
for key in sorted(set(a) | set(b)):
    av, bv = a.get(key), b.get(key)
    delta = "" if av is None or bv is None else f"{bv-av:.6g}"
    print(f"| {key} | {'' if av is None else f'{av:.6g}'} | {'' if bv is None else f'{bv:.6g}'} | {delta} |")
'''
    scaffold_check = r'''
#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
expected = [".codex/config.toml", ".codex/agents/research_director.toml", "research/README.md", "research/claims/claims.yaml", "research/state/next_action.md", "research/workflows/greenfield_loop.md", "research/workflows/brownfield_loop.md", "scripts/validate_agent_configs.py", "scripts/research_status.py", "Makefile"]
missing = []
for rel in expected:
    if (root / rel).exists():
        print("OK     ", rel)
    else:
        print("MISSING", rel)
        missing.append(rel)
raise SystemExit(1 if missing else 0)
'''
    return {
        "scripts/research_os_lib.py": clean(lib),
        "scripts/research_status.py": clean(status),
        "scripts/validate_agent_configs.py": clean(validate_agents),
        "scripts/validate_claims.py": clean(validate_claims),
        "scripts/validate_experiments.py": clean(validate_experiments),
        "scripts/check_review_gates.py": clean(review_gates),
        "scripts/create_experiment.py": clean(create_experiment),
        "scripts/compare_runs.py": clean(compare_runs),
        "scripts/scaffold_research_os.py": clean(scaffold_check),
    }


def core_files(project_name: str) -> dict[str, str]:
    today = dt.date.today().isoformat()
    return {
        ".codex/config.toml": clean(
            """
            [agents]
            max_threads = 8
            max_depth = 1
            job_max_runtime_seconds = 7200

            [research_os]
            state_dir = "research/state"
            claim_ledger = "research/claims/claims.yaml"
            experiment_registry = "research/experiments/registry.yaml"
            review_queue = "research/reviews/review_queue.yaml"
            """
        ),
        "research/README.md": clean(
            f"""
            # Codex Research OS

            This directory is the persistent operating system for Codex-native research in `{project_name}`.

            Start with the research director. Use `research/workflows/greenfield_loop.md` for broad new directions and `research/workflows/brownfield_loop.md` for existing code, papers, benchmarks, or datasets.

            Daily commands:

            ```bash
            make status
            make validate-agents
            make validate-claims
            make validate-experiments
            make review-gates
            ```

            Evidence rules:
            - meaningful claims live in `research/claims/claims.yaml`;
            - experiments live in `research/experiments/registry.yaml` and `research/experiments/runs/`;
            - reviews live in `research/reviews/`;
            - continuation state lives in `research/state/`;
            - final synthesis must pass review gates.
            - agent TOML must pass `make validate-agents`; provider-neutral role definitions
              omit static model and effort pins and never dispatch. Before spawn, the conductor
              supplies a certified v1 `RuntimeAssignment`; `resolution_state` must equal `resolved`,
              `resolved_provider` and `resolved_model_id` need verified model identity, and effective
              effort/context may be `unavailable` only with their structured unavailable evidence.
              Request-injection evidence binds canonical requested model/effort/context bytes, adapter
              ID/version/config digest, and request-byte digest; requested values never become readback.
              The external harness calls admission immediately before spawn and remains responsible for
              injection, no-bypass, and spawned-worker identity; this generated scaffold has no host
              launcher. If the assignment is requested, inherited, unresolved, incomplete, or denied,
              stop and return one `SeedProposal` instead of dispatching. Prompt prose does not enforce a
              Codex model or effort.
            """
        ),
        "research/charter.md": clean(
            """
            # Research Charter

            This research OS exists to make Codex behave like a disciplined research organization: director, specialists, persistent memory, conservative claims, review gates, and reproducible experiment records.

            Principles: no untracked claims; evidence before synthesis; one unit per loop; small cases before generalization; baselines before improvements; adversarial review before promotion; negative results stay visible; novelty is uncertain until checked; every run ends with a concrete next action.
            """
        ),
        "research/problem_statement.md": clean(
            """
            # Problem Statement

            Write the concrete research question here before a focused run.

            Current mode: unset. The research director should classify each run as greenfield, brownfield, or hybrid.
            """
        ),
        "research/research_journal.md": f"# Research Journal\n\n## {today} - Research OS initialized\n\nInstalled Codex-native research OS scaffold.\n",
        "research/decision_log.md": f"# Decision Log\n\n## {today} - Install Codex Research OS\n\nDecision: use a repo-native file-based research operating system with specialist agents and review gates.\n",
        "research/status.md": "# Research Status\n\nStatus: initialized\n\nCurrent focus: choose the first research loop.\n\nNext action: read `research/state/next_action.md`.\n",
        "research/state/current_focus.md": "# Current Focus\n\nChoose the first concrete research target.\n",
        "research/state/next_action.md": "# Next Action\n\nRun the research director on either `research/workflows/greenfield_loop.md` or `research/workflows/brownfield_loop.md`.\n",
        "research/state/resume_context.md": "# Resume Context\n\nRead repository instructions, then research/README.md, research/status.md, and research/state/next_action.md.\n",
        "research/state/blockers.md": "# Blockers\n\nNone recorded yet.\n",
        "research/claims/claims.yaml": "claims: []\n",
        "research/claims/assumptions.yaml": "assumptions: []\n",
        "research/claims/proof_gaps.yaml": "proof_gaps: []\n",
        "research/claims/claim_schema.md": "# Claim Ledger Schema\n\nUse `research/schemas/claim.schema.yaml`. Promote claims slowly and attach evidence.\n",
        "research/ideas/idea_bank.yaml": "ideas: []\n",
        "research/ideas/idea_scores.yaml": "idea_scores: []\n",
        "research/ideas/rejected_ideas.md": "# Rejected Ideas\n\nRecord killed ideas and evidence.\n",
        "research/ideas/greenfield_map.md": "# Greenfield Map\n\nMap domains, candidates, prior work, decisive tests, and decisions.\n",
        "research/literature/sources.bib": "% Bibliography entries.\n",
        "research/literature/reading_queue.yaml": "queue: []\n",
        "research/literature/literature_map.md": "# Literature Map\n\nSummarize source relationships to active questions.\n",
        "research/literature/prior_art_matrix.md": "# Prior Art Matrix\n\n| Idea or claim | Nearest prior work | Same mechanism? | Difference | Novelty risk | Evidence |\n| --- | --- | --- | --- | --- | --- |\n",
        "research/literature/paper_notes/.gitkeep": "",
        "research/experiments/registry.yaml": "experiments: []\n",
        "research/experiments/templates/experiment_card.md": "# Experiment Card\n\n## Hypothesis\n\n## Baseline\n\n## Metrics\n\n## Results\n\n## Review\n",
        "research/experiments/templates/metric_log_format.md": "# Metric Log Format\n\nUse `metrics.jsonl` rows like `{\"metric\":\"loss\",\"value\":0.0,\"step\":0}`.\n",
        "research/experiments/templates/ablation_plan.md": "# Ablation Plan\n\n| Component | Original | Ablated | Metric | Delta | Load-bearing? |\n| --- | --- | --- | --- | --- | --- |\n",
        "research/proofs/theorem_statements.md": "# Theorem Statements\n",
        "research/proofs/informal_proofs.md": "# Informal Proofs\n",
        "research/proofs/proof_reviews.md": "# Proof Reviews\n",
        "research/proofs/formal/lean/.gitkeep": "",
        "research/proofs/formal/coq/.gitkeep": "",
        "research/proofs/formal/smt/.gitkeep": "",
        "research/benchmarks/benchmark_plan.md": "# Benchmark Plan\n\nDefine baseline, datasets, metrics, budgets, and comparison rules.\n",
        "research/benchmarks/baseline_results.yaml": "baselines: []\n",
        "research/benchmarks/comparison_matrix.md": "# Comparison Matrix\n\n| Method | Baseline? | Dataset | Metric | Result | Command | Review |\n| --- | --- | --- | --- | --- | --- | --- |\n",
        "research/benchmarks/harness/.gitkeep": "",
        "research/data/data_inventory.md": "# Data Inventory\n",
        "research/data/data_lineage.yaml": "datasets: []\n",
        "research/data/preprocessing.md": "# Preprocessing\n",
        "research/data/validation_report.md": "# Data Validation Report\n",
        "research/reviews/adversarial_reviews.md": "# Adversarial Reviews\n",
        "research/reviews/replication_reviews.md": "# Replication Reviews\n",
        "research/reviews/novelty_reviews.md": "# Novelty Reviews\n",
        "research/reviews/safety_reviews.md": "# Safety Reviews\n",
        "research/reviews/review_queue.yaml": "reviews: []\n",
        "research/reports/weekly_summary.md": "# Weekly Summary\n\n## Supported\n\n## Falsified\n\n## Uncertain\n\n## Next Actions\n",
        "research/reports/technical_report.md": "# Technical Report\n\nDraft only from validated claims and reviewed evidence.\n",
        "research/reports/paper_draft.md": "# Paper Draft\n\nDo not treat as final until review gates pass.\n",
        "research/reports/final_recommendation.md": "# Final Recommendation\n",
        "research/memory/best.md": "# Best Current Understanding\n\nNo settled project-specific conclusions recorded yet.\n",
        "research/memory/observations.md": "# Observations\n",
        "research/memory/lessons_learned.md": "# Lessons Learned\n",
        "research/memory/failed_attempts.md": "# Failed Attempts\n",
        "research/memory/useful_patterns.md": "# Useful Patterns\n",
        "research/memory/open_questions.md": "# Open Questions\n",
        "research/memory/repo_map.md": "# Repository Map\n",
        "Makefile": clean(
            """
            PYTHON := mise x uv@0.11.17 -- uv run --python 3.12.11 python
            TITLE ?= untitled experiment

            .PHONY: status validate-agents validate-claims validate-experiments review-gates new-experiment compare-runs scaffold-check research-check

            status:
            \t$(PYTHON) scripts/research_status.py

            validate-agents:
            \t$(PYTHON) scripts/validate_agent_configs.py

            validate-claims:
            \t$(PYTHON) scripts/validate_claims.py

            validate-experiments:
            \t$(PYTHON) scripts/validate_experiments.py

            review-gates:
            \t$(PYTHON) scripts/check_review_gates.py

            new-experiment:
            \t$(PYTHON) scripts/create_experiment.py --title "$(TITLE)"

            compare-runs:
            \t$(PYTHON) scripts/compare_runs.py $(RUN_A) $(RUN_B)

            scaffold-check:
            \t$(PYTHON) scripts/scaffold_research_os.py

            research-check: validate-agents validate-claims validate-experiments review-gates
            """
        ),
    }


def build_files(project_name: str) -> dict[str, str]:
    validate_packaged_managed_roles()
    files = core_files(project_name)
    for name, (description, sandbox, body) in AGENTS.items():
        files[f".codex/agents/{name}.toml"] = agent_toml(name, description, sandbox, body)
    for name, content in WORKFLOWS.items():
        files[f"research/workflows/{name}"] = clean(content)
    for name, content in SCHEMAS.items():
        files[f"research/schemas/{name}"] = clean(content)
    files.update(script_files())
    return files


# Generator-owned lifecycle. External state is the sole ownership authority; the
# target-local manifest is only an atomically published view of exact active records.
MANIFEST_REL = ".codex/research-os-manifest.json"
MANIFEST_SCHEMA = "research-os-ownership-manifest/v1"
STATE_VERSION = 1
IDENTITY_VERSION = "stat-v2"
_STATE_NAMESPACE = "agentic-sdlc-research-os"
_MANIFEST_TRANSACTION_KEY = "@manifest"
_PRIVATE_PREFIX = ".research-os-"


class ResearchOSError(RuntimeError):
    """An unsafe or ambiguous lifecycle state that must fail closed."""


class RecoveryConflict(ResearchOSError):
    """An interrupted transaction no longer has one exact safe interpretation."""


class TargetRootError(ResearchOSError):
    """The caller's `--target` does not resolve to a safe, existing directory this process may
    open: supplied but missing, supplied but not a directory, or supplied but unsafe to follow.
    """


# EXITS, as one derivation point (product-spec Implementation Decision 9). `main`'s only
# currently-classified refusal is an unusable `--target`; every other `ResearchOSError` this
# module raises describes a state this survey has not mapped yet and stays an unexpected
# internal failure (1) until a later change gives it its own class.
#: `main` completed: the scaffold ran (or a dry run reported what it would do) and no
#: `TargetRootError` was raised.
EXIT_OK = 0
#: A `TargetRootError` was raised: the supplied `--target` could not be opened as a safe
#: existing directory. Nothing was opened; nothing was written.
EXIT_INPUT = 2


class _LinuxStatxTimestamp(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_int64),
        ("tv_nsec", ctypes.c_uint32),
        ("__reserved", ctypes.c_int32),
    ]


class _LinuxStatx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint32),
        ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64),
        ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32),
        ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16),
        ("__spare0", ctypes.c_uint16),
        ("stx_ino", ctypes.c_uint64),
        ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64),
        ("stx_attributes_mask", ctypes.c_uint64),
        ("stx_atime", _LinuxStatxTimestamp),
        ("stx_btime", _LinuxStatxTimestamp),
        ("stx_ctime", _LinuxStatxTimestamp),
        ("stx_mtime", _LinuxStatxTimestamp),
        ("stx_rdev_major", ctypes.c_uint32),
        ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32),
        ("stx_dev_minor", ctypes.c_uint32),
        ("stx_mnt_id", ctypes.c_uint64),
        ("stx_dio_mem_align", ctypes.c_uint32),
        ("stx_dio_offset_align", ctypes.c_uint32),
        ("__spare3", ctypes.c_uint64 * 12),
    ]


class _WindowsFileId128(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16)]


class _WindowsFileIdInformation(ctypes.Structure):
    _fields_ = [
        ("volume_serial", ctypes.c_uint64),
        ("file_id", _WindowsFileId128),
    ]


class ObservedLeaf:
    __slots__ = ("state", "identity", "digest", "mode", "ancestors")

    def __init__(
        self,
        state: str,
        identity: str | None = None,
        digest: str | None = None,
        mode: int | None = None,
        ancestors: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.state = state
        self.identity = identity
        self.digest = digest
        self.mode = mode
        self.ancestors = ancestors


class PrivateArtifact:
    __slots__ = ("container", "payload", "witness", "identity")

    def __init__(self, container: Path, payload: Path, witness: Path, identity: str) -> None:
        self.container = container
        self.payload = payload
        self.witness = witness
        self.identity = identity


class StagedFile:
    __slots__ = ("artifact", "record")

    def __init__(self, artifact: PrivateArtifact, record: dict[str, Any]) -> None:
        self.artifact = artifact
        self.record = record


def content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bytes_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_digest(path: Path) -> str | None:
    try:
        return _bytes_digest(path.read_bytes())
    except OSError:
        return None


def _is_executable_rel(rel: str) -> bool:
    return rel.startswith("scripts/") and rel.endswith(".py")


def _normalise_relative_path(rel: str, *, allow_manifest: bool = False) -> tuple[str, ...]:
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise ValueError(f"invalid generated path: {rel!r}")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise ValueError(f"generated path must be relative: {rel!r}")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts) or "/".join(parts) != rel:
        raise ValueError(f"invalid generated path: {rel!r}")
    if rel == MANIFEST_REL and not allow_manifest:
        raise ValueError("generated paths must not include the manifest")
    return tuple(parts)


def _validated_files(files: dict[str, str]) -> dict[str, tuple[str, ...]]:
    if not isinstance(files, dict):
        raise ValueError("generated files must be a dictionary")
    normalised: dict[str, tuple[str, ...]] = {}
    for rel, content in files.items():
        if not isinstance(content, str):
            raise ValueError(f"generated content must be text: {rel!r}")
        normalised[rel] = _normalise_relative_path(rel)
    return normalised


def _platform_system() -> str:
    return platform.system()


def _identity_token_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split(":")
    return bool(
        len(parts) == 4
        and parts[0] == IDENTITY_VERSION
        and all(part.isdigit() for part in parts[1:3])
        and parts[3].replace(".", "", 1).isdigit()
    )


def _linux_statx(path: bytes, *, descriptor: int = -100, flags: int = 0) -> _LinuxStatx | None:
    statx = getattr(ctypes.CDLL(None, use_errno=True), "statx", None)
    if statx is None:
        return None
    statx.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_LinuxStatx),
    ]
    statx.restype = ctypes.c_int
    metadata = _LinuxStatx()
    statx_btime = 0x00000800
    if statx(descriptor, path, flags, statx_btime, ctypes.byref(metadata)) != 0:
        return None
    if not metadata.stx_mask & statx_btime:
        return None
    return metadata


def _windows_file_identity(path: Path, *, follow_symlinks: bool = True) -> tuple[int, int, int] | None:
    if os.name != "nt":
        return None
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandleEx
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    handle = create_file(
        str(path),
        0x00000080,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000 | (0 if follow_symlinks else 0x00200000),
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        return None
    try:
        information = _WindowsFileIdInformation()
        if not get_information(handle, 18, ctypes.byref(information), ctypes.sizeof(information)):
            return None
        file_id = int.from_bytes(bytes(information.file_id.identifier), "little")
        return information.volume_serial, file_id, 0
    finally:
        close_handle(handle)


def _path_identity(path: Path, *, follow_symlinks: bool = True) -> str:
    if _platform_system() == "Windows":
        identity = _windows_file_identity(path, follow_symlinks=follow_symlinks)
        if identity is not None:
            volume, file_index, creation = identity
            return f"{IDENTITY_VERSION}:{volume}:{file_index}:{creation}"
    metadata = os.stat(path, follow_symlinks=follow_symlinks)
    generation: str | None = None
    if _platform_system() == "Darwin":
        birth_ns = getattr(metadata, "st_birthtime_ns", None)
        birth = getattr(metadata, "st_birthtime", None)
        generation = str(birth_ns if birth_ns is not None else birth) if birth is not None or birth_ns is not None else None
    elif _platform_system() == "Windows":
        generation = str(metadata.st_ctime_ns)
    elif _platform_system() == "Linux":
        result = _linux_statx(
            os.fsencode(path),
            flags=0 if follow_symlinks else 0x00000100,
        )
        if result is not None:
            generation = f"{result.stx_btime.tv_sec}.{result.stx_btime.tv_nsec}"
    if generation is None:
        raise ResearchOSError(f"filesystem does not expose stable object identity for {path}")
    return f"{IDENTITY_VERSION}:{metadata.st_dev}:{metadata.st_ino}:{generation}"


def _fd_identity(fd: int) -> str:
    metadata = os.fstat(fd)
    generation: str | None = None
    if _platform_system() == "Darwin":
        birth_ns = getattr(metadata, "st_birthtime_ns", None)
        birth = getattr(metadata, "st_birthtime", None)
        generation = str(birth_ns if birth_ns is not None else birth) if birth is not None or birth_ns is not None else None
    elif _platform_system() == "Linux":
        result = _linux_statx(b"", descriptor=fd, flags=0x00001000)
        if result is not None:
            generation = f"{result.stx_btime.tv_sec}.{result.stx_btime.tv_nsec}"
    if generation is None:
        raise ResearchOSError("filesystem does not expose stable descriptor identity")
    return f"{IDENTITY_VERSION}:{metadata.st_dev}:{metadata.st_ino}:{generation}"


def _identity_matches(path: Path, expected: Any, *, follow_symlinks: bool = True) -> bool:
    if not _identity_token_valid(expected):
        return False
    try:
        return _path_identity(path, follow_symlinks=follow_symlinks) == expected
    except (OSError, ResearchOSError):
        return False


def _physical_target(root: Path) -> str:
    try:
        return os.path.normcase(str(root.resolve(strict=True)))
    except OSError as exc:
        raise TargetRootError(f"cannot resolve target root {root}: {exc}") from exc


def _state_root() -> Path:
    if _platform_system() == "Windows":
        value = os.environ.get("LOCALAPPDATA")
        return Path(value) if value else Path.home() / "AppData" / "Local"
    value = os.environ.get("XDG_STATE_HOME")
    return Path(value) if value else Path.home() / ".local" / "state"


def _state_path(root: Path) -> Path:
    key = hashlib.sha256(os.fsencode(_physical_target(root))).hexdigest()
    return _state_root() / _STATE_NAMESPACE / key / "state.json"


def _safe_open_flags(*, write: bool = False) -> int:
    flags = os.O_WRONLY if write else os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    return flags


def _open_root(root: Path) -> int | None:
    if os.name == "nt":
        try:
            metadata = os.lstat(root)
        except OSError as exc:
            raise TargetRootError(f"cannot open target root {root}: {exc}") from exc
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_file_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise TargetRootError("target root is not a safe directory")
        return None
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required):
        raise TargetRootError("safe no-follow directory primitives are unavailable")
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise TargetRootError(f"cannot open target root {root}: {exc}") from exc
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise TargetRootError("target root is not a directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_parent(root_fd: int, parts: tuple[str, ...], *, create: bool) -> tuple[int | None, tuple[tuple[str, str], ...]]:
    current_fd = os.dup(root_fd)
    ancestors: list[tuple[str, str]] = []
    current_parts: list[str] = []
    try:
        for component in parts[:-1]:
            current_parts.append(component)
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                if not create:
                    os.close(current_fd)
                    return None, tuple(ancestors)
                try:
                    os.mkdir(component, 0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=current_fd,
                )
            if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                os.close(next_fd)
                raise ResearchOSError(f"unsafe generated ancestor: {'/'.join(current_parts)}")
            ancestors.append(("/".join(current_parts), _fd_identity(next_fd)))
            os.close(current_fd)
            current_fd = next_fd
        return current_fd, tuple(ancestors)
    except BaseException:
        try:
            os.close(current_fd)
        except OSError:
            pass
        raise


def _windows_parent(root: Path, parts: tuple[str, ...], *, create: bool) -> tuple[Path | None, tuple[tuple[str, str], ...]]:
    current = root
    ancestors: list[tuple[str, str]] = []
    current_parts: list[str] = []
    for component in parts[:-1]:
        current_parts.append(component)
        current = current / component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if not create:
                return None, tuple(ancestors)
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
            metadata = os.lstat(current)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_file_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise ResearchOSError(f"unsafe generated ancestor: {'/'.join(current_parts)}")
        ancestors.append(("/".join(current_parts), _path_identity(current, follow_symlinks=False)))
    return current, tuple(ancestors)


def _read_fd_bytes(fd: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError as exc:
            raise ResearchOSError("generated leaf cannot be read without blocking") from exc
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _inspect_leaf(root: Path, root_fd: int | None, parts: tuple[str, ...]) -> ObservedLeaf:
    if root_fd is None:
        parent, ancestors = _windows_parent(root, parts, create=False)
        if parent is None:
            return ObservedLeaf("missing", ancestors=ancestors)
        path = parent / parts[-1]
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            return ObservedLeaf("missing", ancestors=ancestors)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_file_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            return ObservedLeaf("non-regular", ancestors=ancestors)
        identity = _path_identity(path, follow_symlinks=False)
        try:
            fd = os.open(path, _safe_open_flags())
        except (OSError, PermissionError):
            return ObservedLeaf("regular-unreadable", identity=identity, mode=stat.S_IMODE(metadata.st_mode), ancestors=ancestors)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode):
                return ObservedLeaf("non-regular", ancestors=ancestors)
            data = _read_fd_bytes(fd)
            if not _identity_matches(path, identity, follow_symlinks=False):
                return ObservedLeaf("unsafe-ancestor", ancestors=ancestors)
            return ObservedLeaf("regular-readable", identity, _bytes_digest(data), stat.S_IMODE(opened.st_mode), ancestors)
        finally:
            os.close(fd)

    parent_fd, ancestors = _open_parent(root_fd, parts, create=False)
    if parent_fd is None:
        return ObservedLeaf("missing", ancestors=ancestors)
    try:
        try:
            leaf_fd = os.open(parts[-1], _safe_open_flags(), dir_fd=parent_fd)
        except FileNotFoundError:
            return ObservedLeaf("missing", ancestors=ancestors)
        except OSError as exc:
            try:
                metadata = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return ObservedLeaf("missing", ancestors=ancestors)
            if not stat.S_ISREG(metadata.st_mode):
                return ObservedLeaf("non-regular", ancestors=ancestors)
            try:
                identity = _path_identity(root.joinpath(*parts), follow_symlinks=False)
            except (OSError, ResearchOSError):
                identity = None
            return ObservedLeaf("regular-unreadable", identity=identity, mode=stat.S_IMODE(metadata.st_mode), ancestors=ancestors)
        try:
            metadata = os.fstat(leaf_fd)
            if not stat.S_ISREG(metadata.st_mode):
                return ObservedLeaf("non-regular", ancestors=ancestors)
            identity = _fd_identity(leaf_fd)
            data = _read_fd_bytes(leaf_fd)
            current = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                return ObservedLeaf("unsafe-ancestor", ancestors=ancestors)
            return ObservedLeaf("regular-readable", identity, _bytes_digest(data), stat.S_IMODE(metadata.st_mode), ancestors)
        finally:
            os.close(leaf_fd)
    finally:
        os.close(parent_fd)


def _ensure_parent(root: Path, root_fd: int | None, parts: tuple[str, ...]) -> tuple[Path, str, tuple[tuple[str, str], ...]]:
    if root_fd is None:
        parent, ancestors = _windows_parent(root, parts, create=True)
        assert parent is not None
        return parent, _path_identity(parent, follow_symlinks=False), ancestors
    parent_fd, ancestors = _open_parent(root_fd, parts, create=True)
    assert parent_fd is not None
    try:
        parent = root.joinpath(*parts[:-1]) if parts[:-1] else root
        return parent, _fd_identity(parent_fd), ancestors
    finally:
        os.close(parent_fd)


def _ancestor_records(ancestors: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"path": path, "identity": identity} for path, identity in ancestors]


def _record_from_observation(observed: ObservedLeaf) -> dict[str, Any]:
    if observed.state != "regular-readable" or observed.identity is None or observed.digest is None or observed.mode is None:
        raise ResearchOSError("cannot record a non-exact generated leaf")
    return {
        "destination_identity": observed.identity,
        "destination_type": "file",
        "digest": observed.digest,
        "mode": observed.mode,
        "ancestors": _ancestor_records(observed.ancestors),
    }


def _record_structure_valid(record: Any) -> bool:
    if not isinstance(record, dict) or set(record) != {
        "destination_identity",
        "destination_type",
        "digest",
        "mode",
        "ancestors",
    }:
        return False
    ancestors = record.get("ancestors")
    return bool(
        _identity_token_valid(record.get("destination_identity"))
        and record.get("destination_type") == "file"
        and isinstance(record.get("digest"), str)
        and re.fullmatch(r"[0-9a-f]{64}", record["digest"])
        and isinstance(record.get("mode"), int)
        and 0 <= record["mode"] <= 0o7777
        and isinstance(ancestors, list)
        and all(
            isinstance(item, dict)
            and set(item) == {"path", "identity"}
            and isinstance(item["path"], str)
            and _identity_token_valid(item["identity"])
            for item in ancestors
        )
    )


def _authority_matches(observed: ObservedLeaf, record: dict[str, Any]) -> bool:
    return bool(
        observed.state == "regular-readable"
        and observed.identity == record["destination_identity"]
        and _ancestor_records(observed.ancestors) == record["ancestors"]
    )


def _exact_matches(observed: ObservedLeaf, record: dict[str, Any]) -> bool:
    mode_matches = _platform_system() == "Windows" or observed.mode == record["mode"]
    return _authority_matches(observed, record) and observed.digest == record["digest"] and mode_matches


def _empty_state(root: Path, root_identity: str) -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "target": {"path": _physical_target(root), "identity": root_identity},
        "entries": {},
        "manifest": None,
        "transactions": {},
        "conflicts": {},
    }


def _artifact_state(artifact: PrivateArtifact) -> dict[str, str]:
    return {
        "container": str(artifact.container),
        "payload": str(artifact.payload),
        "witness": str(artifact.witness),
        "identity": artifact.identity,
    }


def _artifact_state_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"container", "payload", "witness", "identity"}:
        return False
    try:
        container = Path(value["container"])
        payload = Path(value["payload"])
        witness = Path(value["witness"])
    except TypeError:
        return False
    return bool(
        container.is_absolute()
        and container.name.startswith(_PRIVATE_PREFIX)
        and payload == container / "payload"
        and witness == container / "witness"
        and _identity_token_valid(value.get("identity"))
    )


def _transaction_valid(key: str, tx: Any) -> bool:
    if not isinstance(tx, dict) or set(tx) != {
        "operation",
        "phase",
        "rel",
        "authority_record",
        "old_record",
        "new_record",
        "stage",
        "backup",
    }:
        return False
    operation = tx.get("operation")
    if operation not in {"create", "replace", "delete"} or tx.get("phase") not in {"armed", "committed"} or tx.get("rel") != key:
        return False
    if key != _MANIFEST_TRANSACTION_KEY:
        try:
            _normalise_relative_path(key)
        except ValueError:
            return False
    for field in ("authority_record", "old_record", "new_record"):
        if tx[field] is not None and not _record_structure_valid(tx[field]):
            return False
    if operation == "create":
        return bool(
            tx["authority_record"] is None
            and tx["old_record"] is None
            and tx["new_record"] is not None
            and _artifact_state_valid(tx["stage"])
            and tx["backup"] is None
        )
    if operation == "replace":
        return bool(
            tx["authority_record"] is not None
            and tx["old_record"] is not None
            and tx["new_record"] is not None
            and _artifact_state_valid(tx["stage"])
            and _artifact_state_valid(tx["backup"])
        )
    return bool(
        tx["authority_record"] is not None
        and tx["old_record"] is not None
        and tx["new_record"] is None
        and tx["stage"] is None
        and _artifact_state_valid(tx["backup"])
    )


def _validate_state(state: Any, root: Path, root_identity: str) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != {
        "version",
        "target",
        "entries",
        "manifest",
        "transactions",
        "conflicts",
    }:
        raise ResearchOSError("invalid Research OS ownership state")
    version = state.get("version")
    if isinstance(version, int) and version > STATE_VERSION:
        raise ResearchOSError(f"Research OS state was written by a newer installer (version {version})")
    target = state.get("target")
    if (
        version != STATE_VERSION
        or not isinstance(target, dict)
        or set(target) != {"path", "identity"}
        or target.get("path") != _physical_target(root)
        or target.get("identity") != root_identity
    ):
        raise ResearchOSError("Research OS target identity changed or state is invalid")
    entries = state.get("entries")
    transactions = state.get("transactions")
    conflicts = state.get("conflicts")
    if not isinstance(entries, dict) or not isinstance(transactions, dict) or not isinstance(conflicts, dict):
        raise ResearchOSError("invalid Research OS ownership state")
    for rel, record in entries.items():
        try:
            _normalise_relative_path(rel)
        except (TypeError, ValueError) as exc:
            raise ResearchOSError(f"invalid Research OS ownership record: {rel!r}") from exc
        if not _record_structure_valid(record):
            raise ResearchOSError(f"invalid Research OS ownership record: {rel}")
    if state["manifest"] is not None and not _record_structure_valid(state["manifest"]):
        raise ResearchOSError("invalid Research OS manifest ownership record")
    if any(not isinstance(key, str) or not _transaction_valid(key, tx) for key, tx in transactions.items()):
        raise ResearchOSError("invalid Research OS transaction record")
    for key, conflict in conflicts.items():
        if (
            not isinstance(key, str)
            or not isinstance(conflict, dict)
            or set(conflict) != {"action", "reason"}
            or not all(isinstance(value, str) for value in conflict.values())
        ):
            raise ResearchOSError("invalid Research OS conflict record")
    return state


def _load_state(path: Path, root: Path, root_identity: str) -> tuple[dict[str, Any], bool]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return _empty_state(root, root_identity), False
    except OSError as exc:
        raise ResearchOSError(f"cannot inspect Research OS state {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ResearchOSError(f"Research OS state is not a regular file: {path}")
    try:
        descriptor = os.open(path, _safe_open_flags())
    except OSError as exc:
        raise ResearchOSError(f"cannot read Research OS state {path}: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ResearchOSError(f"Research OS state is not a regular file: {path}")
        data = _read_fd_bytes(descriptor)
        current = os.lstat(path)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ResearchOSError(f"Research OS state changed while reading: {path}")
    except OSError as exc:
        raise ResearchOSError(f"cannot read Research OS state {path}: {exc}") from exc
    finally:
        os.close(descriptor)
    try:
        state = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResearchOSError(f"cannot read Research OS state {path}: {exc}") from exc
    return _validate_state(state, root, root_identity), True


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_state(path: Path, state: dict[str, Any], root: Path, root_identity: str) -> None:
    _validate_state(state, root, root_identity)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write((json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _persist_candidate(path: Path, state: dict[str, Any], candidate: dict[str, Any], root: Path, root_identity: str) -> None:
    _write_state(path, candidate, root, root_identity)
    state.clear()
    state.update(candidate)


@contextmanager
def _state_lock(state_path: Path) -> Iterator[None]:
    state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_path.with_name("installer.lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            try:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\0")
                    os.fsync(fd)
                    os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ResearchOSError("another Research OS install is active") from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ResearchOSError("another Research OS install is active") from exc
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _open_verified_directory(path: Path, expected_identity: str | None) -> int:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        if expected_identity is not None and _fd_identity(descriptor) != expected_identity:
            raise RecoveryConflict(f"directory identity changed: {path}")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _windows_rename_noreplace(source: Path, destination: Path, source_parent_identity: str | None, destination_parent_identity: str | None) -> None:
    if os.name != "nt":
        os.rename(source, destination)
        return
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    invalid = wintypes.HANDLE(-1).value
    share_all = 0x00000001 | 0x00000002 | 0x00000004

    def open_handle(path: Path, access: int, share: int = share_all) -> int:
        handle = create_file(str(path), access, share, None, 3, 0x02000000 | 0x00200000, None)
        if handle == invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    source_handle = open_handle(source, 0x00010000 | 0x00000080)
    destination_parent_handle = open_handle(destination.parent, 0x00000080, 0x00000001 | 0x00000002)
    try:
        if source_parent_identity is not None and not _identity_matches(source.parent, source_parent_identity, follow_symlinks=False):
            raise RecoveryConflict(f"directory identity changed: {source.parent}")
        if destination_parent_identity is not None and not _identity_matches(destination.parent, destination_parent_identity, follow_symlinks=False):
            raise RecoveryConflict(f"directory identity changed: {destination.parent}")
        destination_name = str(destination)
        destination_bytes = destination_name.encode("utf-16-le")

        class FileRenameInfoEx(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD),
                ("FileName", wintypes.WCHAR * (len(destination_name) + 1)),
            ]

        information = FileRenameInfoEx(0, None, len(destination_bytes), destination_name)
        information_size = FileRenameInfoEx.FileName.offset + len(destination_bytes) + 2
        if not set_information(source_handle, 22, ctypes.byref(information), information_size):
            error = ctypes.get_last_error()
            if error in {80, 183}:
                raise FileExistsError(error, os.strerror(error), str(destination))
            raise ctypes.WinError(error)
    finally:
        close_handle(destination_parent_handle)
        close_handle(source_handle)


def _rename_noreplace(
    source: Path,
    destination: Path,
    *,
    source_parent_identity: str | None = None,
    destination_parent_identity: str | None = None,
) -> None:
    system = _platform_system()
    if system == "Windows":
        _windows_rename_noreplace(source, destination, source_parent_identity, destination_parent_identity)
        return
    source_fd = _open_verified_directory(source.parent, source_parent_identity)
    destination_fd = _open_verified_directory(destination.parent, destination_parent_identity)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if system == "Darwin":
            rename = getattr(libc, "renameatx_np", None)
            if rename is None:
                raise ResearchOSError("atomic no-replace rename is unavailable")
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            result = rename(source_fd, os.fsencode(source.name), destination_fd, os.fsencode(destination.name), 0x00000004)
        elif system == "Linux":
            rename = getattr(libc, "renameat2", None)
            if rename is None:
                raise ResearchOSError("atomic no-replace rename requires glibc 2.28 or newer")
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            result = rename(source_fd, os.fsencode(source.name), destination_fd, os.fsencode(destination.name), 1)
        else:
            raise ResearchOSError("atomic no-replace rename is unavailable")
        if result != 0:
            error = ctypes.get_errno()
            if error == getattr(os, "EEXIST", 17):
                raise FileExistsError(error, os.strerror(error), str(destination))
            raise OSError(error, os.strerror(error), str(destination))
        os.fsync(source_fd)
        if destination_fd != source_fd:
            os.fsync(destination_fd)
    finally:
        os.close(destination_fd)
        os.close(source_fd)


def _reserve_artifact(parent: Path, role: str) -> PrivateArtifact:
    for _ in range(32):
        container = parent / f"{_PRIVATE_PREFIX}{role}-{secrets.token_hex(16)}"
        try:
            container.mkdir(mode=0o700)
        except FileExistsError:
            continue
        identity = _path_identity(container, follow_symlinks=False)
        _fsync_directory(parent)
        return PrivateArtifact(container, container / "payload", container / "witness", identity)
    raise ResearchOSError(f"cannot reserve private {role} artifact in {parent}")


def _artifact_from_state(value: dict[str, str]) -> PrivateArtifact:
    return PrivateArtifact(Path(value["container"]), Path(value["payload"]), Path(value["witness"]), value["identity"])


def _link_fd(fd: int, directory_fd: int, name: str) -> None:
    linkat = getattr(ctypes.CDLL(None, use_errno=True), "linkat", None)
    if linkat is None:
        raise ResearchOSError("exact-descriptor staged publication is unavailable")
    linkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    linkat.restype = ctypes.c_int
    if linkat(fd, b"", directory_fd, os.fsencode(name), 0x00001000) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)


def _inspect_absolute(path: Path) -> ObservedLeaf:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return ObservedLeaf("missing")
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        return ObservedLeaf("non-regular")
    try:
        fd = os.open(path, _safe_open_flags())
    except OSError:
        return ObservedLeaf("regular-unreadable")
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            return ObservedLeaf("non-regular")
        identity = _fd_identity(fd) if os.name != "nt" else _path_identity(path, follow_symlinks=False)
        data = _read_fd_bytes(fd)
        if not _identity_matches(path, identity, follow_symlinks=False):
            return ObservedLeaf("unsafe-ancestor")
        return ObservedLeaf("regular-readable", identity, _bytes_digest(data), stat.S_IMODE(opened.st_mode))
    finally:
        os.close(fd)


def _artifact_container_exact(artifact: PrivateArtifact) -> bool:
    return _identity_matches(artifact.container, artifact.identity, follow_symlinks=False)


def _artifact_links(artifact: PrivateArtifact, record: dict[str, Any]) -> tuple[ObservedLeaf, ObservedLeaf]:
    return _inspect_absolute(artifact.payload), _inspect_absolute(artifact.witness)


def _stage_exact(stage: StagedFile) -> bool:
    if not _artifact_container_exact(stage.artifact):
        return False
    payload, witness = _artifact_links(stage.artifact, stage.record)
    expected = {**stage.record, "ancestors": []}
    return _exact_matches(payload, expected) and _exact_matches(witness, expected)


def _stage_published(stage: StagedFile) -> bool:
    if not _artifact_container_exact(stage.artifact):
        return False
    payload, witness = _artifact_links(stage.artifact, stage.record)
    expected = {**stage.record, "ancestors": []}
    return payload.state == "missing" and _exact_matches(witness, expected)


def _backup_exact(artifact: PrivateArtifact, record: dict[str, Any]) -> bool:
    if not _artifact_container_exact(artifact):
        return False
    payload, witness = _artifact_links(artifact, record)
    expected = {**record, "ancestors": []}
    return _exact_matches(payload, expected) and _exact_matches(witness, expected)


def _artifact_empty(artifact: PrivateArtifact) -> bool:
    if not artifact.container.exists():
        return True
    if not _artifact_container_exact(artifact):
        return False
    try:
        return not any(artifact.container.iterdir())
    except OSError:
        return False


def _cleanup_artifact_windows(
    artifact: PrivateArtifact,
    observations: dict[Path, ObservedLeaf],
    record: dict[str, Any],
) -> None:
    for child, observed in observations.items():
        quarantine = artifact.container / f"retired-{child.name}-{secrets.token_hex(16)}"
        try:
            _rename_noreplace(
                child,
                quarantine,
                source_parent_identity=artifact.identity,
                destination_parent_identity=artifact.identity,
            )
        except BaseException as exc:
            raise RecoveryConflict(f"private payload changed during cleanup: {child}") from exc
        moved = _inspect_absolute(quarantine)
        expected = {**record, "ancestors": []}
        if not _exact_matches(moved, expected):
            raise RecoveryConflict(f"private payload changed during cleanup: {child}")
        try:
            quarantine.unlink()
        except OSError as exc:
            raise RecoveryConflict(f"cannot retire private payload: {quarantine}") from exc
    try:
        artifact.container.rmdir()
    except OSError as exc:
        raise RecoveryConflict(f"private container is not empty: {artifact.container}") from exc


def _cleanup_artifact(artifact: PrivateArtifact, record: dict[str, Any] | None) -> None:
    if not artifact.container.exists():
        return
    if not _artifact_container_exact(artifact):
        raise RecoveryConflict(f"private container identity changed: {artifact.container}")
    children = list(artifact.container.iterdir())
    if any(child.name not in {"payload", "witness"} for child in children):
        raise RecoveryConflict(f"foreign content in private container: {artifact.container}")
    observations = {child: _inspect_absolute(child) for child in children}
    if record is None and children:
        raise RecoveryConflict(f"unexpected private payload: {artifact.container}")
    if record is not None:
        expected = {**record, "ancestors": []}
        if any(not _exact_matches(observed, expected) for observed in observations.values()):
            raise RecoveryConflict(f"private payload changed: {artifact.container}")
    assert record is not None
    if _platform_system() == "Windows":
        _cleanup_artifact_windows(artifact, observations, record)
        return
    container_fd = _open_verified_directory(artifact.container, artifact.identity)
    quarantine: list[str] = []
    try:
        for child in children:
            observed = observations[child]
            quarantine_name = f"retired-{child.name}-{secrets.token_hex(16)}"
            try:
                _rename_noreplace(
                    child,
                    artifact.container / quarantine_name,
                    source_parent_identity=artifact.identity,
                    destination_parent_identity=artifact.identity,
                )
            except BaseException as exc:
                raise RecoveryConflict(f"private payload changed during cleanup: {child}") from exc
            moved = _inspect_absolute(artifact.container / quarantine_name)
            expected = {**record, "ancestors": []} if record is not None else None
            if expected is None or not _exact_matches(moved, expected):
                raise RecoveryConflict(f"private payload changed during cleanup: {child}")
            quarantine.append(quarantine_name)
        os.fsync(container_fd)
        for name in quarantine:
            os.unlink(name, dir_fd=container_fd)
        os.fsync(container_fd)
    finally:
        os.close(container_fd)
    artifact.container.rmdir()
    _fsync_directory(artifact.container.parent)


def _set_staged_mode(file_fd: int, path: Path, mode: int) -> None:
    if _platform_system() == "Windows":
        os.chmod(path, mode)
    else:
        os.fchmod(file_fd, mode)


def _stage_file(parent: Path, data: bytes, mode: int, ancestors: tuple[tuple[str, str], ...]) -> StagedFile:
    artifact = _reserve_artifact(parent, "stage")
    container_fd: int | None = None
    file_fd: int | None = None
    named = False
    try:
        if os.name != "nt":
            container_fd = os.open(artifact.container, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                file_fd = os.open(".", os.O_RDWR | os.O_TMPFILE | getattr(os, "O_CLOEXEC", 0), mode, dir_fd=container_fd)
            except (AttributeError, OSError):
                file_fd = os.open("payload", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=container_fd)
                named = True
        else:
            file_fd = os.open(artifact.payload, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), mode)
            named = True
        written = 0
        while written < len(data):
            count = os.write(file_fd, data[written:])
            if count <= 0:
                raise OSError("short write staging generated file")
            written += count
        _set_staged_mode(file_fd, artifact.payload, mode)
        os.fsync(file_fd)
        identity = _fd_identity(file_fd) if os.name != "nt" else _path_identity(artifact.payload, follow_symlinks=False)
        if not named:
            assert container_fd is not None
            _link_fd(file_fd, container_fd, "payload")
        if os.name == "nt":
            os.link(artifact.payload, artifact.witness)
        else:
            assert container_fd is not None
            os.link("payload", "witness", src_dir_fd=container_fd, dst_dir_fd=container_fd, follow_symlinks=False)
        if container_fd is not None:
            os.fsync(container_fd)
        record = {
            "destination_identity": identity,
            "destination_type": "file",
            "digest": _bytes_digest(data),
            "mode": mode,
            "ancestors": _ancestor_records(ancestors),
        }
        stage = StagedFile(artifact, record)
        if not _stage_exact(stage):
            raise RecoveryConflict(f"staged payload changed: {artifact.container}")
        return stage
    except BaseException:
        if file_fd is not None:
            os.close(file_fd)
            file_fd = None
        if container_fd is not None:
            os.close(container_fd)
            container_fd = None
        try:
            children = list(artifact.container.iterdir()) if _artifact_container_exact(artifact) else []
            for child in children:
                child.unlink()
            if _artifact_container_exact(artifact):
                artifact.container.rmdir()
                _fsync_directory(parent)
        except OSError:
            pass
        raise
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if container_fd is not None:
            os.close(container_fd)


def _publish_staged_file(stage: StagedFile, destination: Path, new_record: dict[str, Any], destination_parent_identity: str) -> None:
    if not _stage_exact(stage) or stage.record != new_record:
        raise RecoveryConflict(f"staged payload changed: {stage.artifact.payload}")
    if _inspect_absolute(destination).state != "missing":
        raise RecoveryConflict(f"publish destination is no longer absent: {destination}")
    try:
        _rename_noreplace(
            stage.artifact.payload,
            destination,
            source_parent_identity=stage.artifact.identity,
            destination_parent_identity=destination_parent_identity,
        )
    except FileExistsError as exc:
        raise RecoveryConflict(f"publish destination is no longer absent: {destination}") from exc
    observed = _inspect_absolute(destination)
    expected = {**new_record, "ancestors": []}
    if not _exact_matches(observed, expected) or not _stage_published(stage):
        raise RecoveryConflict(f"published destination changed: {destination}")


def _move_exact_to_backup(
    destination: Path,
    expected_record: dict[str, Any],
    backup: PrivateArtifact,
    destination_parent_identity: str,
) -> None:
    if not _artifact_empty(backup):
        raise RecoveryConflict(f"backup is not empty: {backup.container}")
    exact_fd: int | None = None
    try:
        if os.name != "nt":
            exact_fd = os.open(destination, _safe_open_flags())
            opened = os.fstat(exact_fd)
            opened_identity = _fd_identity(exact_fd)
            opened_digest = _bytes_digest(_read_fd_bytes(exact_fd))
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened_identity != expected_record["destination_identity"]
                or opened_digest != expected_record["digest"]
                or stat.S_IMODE(opened.st_mode) != expected_record["mode"]
            ):
                raise RecoveryConflict(f"destination changed before retirement: {destination}")
        try:
            _rename_noreplace(
                destination,
                backup.payload,
                source_parent_identity=destination_parent_identity,
                destination_parent_identity=backup.identity,
            )
        except FileExistsError as exc:
            raise RecoveryConflict(f"backup destination changed: {backup.payload}") from exc
        moved = _inspect_absolute(backup.payload)
        expected_private = {**expected_record, "ancestors": []}
        if not _exact_matches(moved, expected_private):
            if exact_fd is not None:
                backup_fd = _open_verified_directory(backup.container, backup.identity)
                try:
                    _link_fd(exact_fd, backup_fd, "witness")
                    os.fsync(backup_fd)
                finally:
                    os.close(backup_fd)
            if _inspect_absolute(destination).state == "missing":
                try:
                    _rename_noreplace(
                        backup.payload,
                        destination,
                        source_parent_identity=backup.identity,
                        destination_parent_identity=destination_parent_identity,
                    )
                except BaseException:
                    pass
            raise RecoveryConflict(f"destination identity changed during retirement: {destination}")
        try:
            os.link(backup.payload, backup.witness, follow_symlinks=False)
        except BaseException:
            if _inspect_absolute(destination).state == "missing":
                _rename_noreplace(
                    backup.payload,
                    destination,
                    source_parent_identity=backup.identity,
                    destination_parent_identity=destination_parent_identity,
                )
            raise
        if not _backup_exact(backup, expected_record):
            raise RecoveryConflict(f"backup changed: {backup.container}")
    finally:
        if exact_fd is not None:
            os.close(exact_fd)


def _transaction(
    operation: str,
    rel: str,
    *,
    authority_record: dict[str, Any] | None,
    old_record: dict[str, Any] | None,
    new_record: dict[str, Any] | None,
    stage: PrivateArtifact | None,
    backup: PrivateArtifact | None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "phase": "armed",
        "rel": rel,
        "authority_record": copy.deepcopy(authority_record),
        "old_record": copy.deepcopy(old_record),
        "new_record": copy.deepcopy(new_record),
        "stage": _artifact_state(stage) if stage else None,
        "backup": _artifact_state(backup) if backup else None,
    }


def _transaction_destination(root: Path, key: str) -> tuple[str, tuple[str, ...], Path]:
    rel = MANIFEST_REL if key == _MANIFEST_TRANSACTION_KEY else key
    parts = _normalise_relative_path(rel, allow_manifest=key == _MANIFEST_TRANSACTION_KEY)
    return rel, parts, root.joinpath(*parts)


def _set_active(candidate: dict[str, Any], key: str, record: dict[str, Any] | None) -> None:
    if key == _MANIFEST_TRANSACTION_KEY:
        candidate["manifest"] = copy.deepcopy(record)
    elif record is None:
        candidate["entries"].pop(key, None)
    else:
        candidate["entries"][key] = copy.deepcopy(record)


def _commit_transaction(
    state_path: Path,
    state: dict[str, Any],
    key: str,
    active_record: dict[str, Any] | None,
    root: Path,
    root_identity: str,
) -> None:
    candidate = copy.deepcopy(state)
    candidate["transactions"][key]["phase"] = "committed"
    _set_active(candidate, key, active_record)
    _persist_candidate(state_path, state, candidate, root, root_identity)


def _finish_transaction(
    state_path: Path,
    state: dict[str, Any],
    key: str,
    root: Path,
    root_identity: str,
) -> None:
    candidate = copy.deepcopy(state)
    candidate["transactions"].pop(key, None)
    _persist_candidate(state_path, state, candidate, root, root_identity)


def _execute_create(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
    key: str,
    data: bytes,
    mode: int,
) -> dict[str, Any]:
    _, parts, destination = _transaction_destination(root, key)
    parent, parent_identity, ancestors = _ensure_parent(root, root_fd, parts)
    if _inspect_leaf(root, root_fd, parts).state != "missing":
        raise RecoveryConflict(f"create destination appeared: {destination}")
    stage = _stage_file(parent, data, mode, ancestors)
    tx = _transaction("create", key, authority_record=None, old_record=None, new_record=stage.record, stage=stage.artifact, backup=None)
    candidate = copy.deepcopy(state)
    candidate["transactions"][key] = tx
    try:
        _persist_candidate(state_path, state, candidate, root, root_identity)
    except BaseException:
        _cleanup_artifact(stage.artifact, stage.record)
        raise
    _publish_staged_file(stage, destination, stage.record, parent_identity)
    _commit_transaction(state_path, state, key, stage.record, root, root_identity)
    _cleanup_artifact(stage.artifact, stage.record)
    _finish_transaction(state_path, state, key, root, root_identity)
    return stage.record


def _execute_replace(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
    key: str,
    authority_record: dict[str, Any],
    data: bytes,
    mode: int,
) -> dict[str, Any]:
    _, parts, destination = _transaction_destination(root, key)
    observed = _inspect_leaf(root, root_fd, parts)
    if not _authority_matches(observed, authority_record):
        raise RecoveryConflict(f"owned destination identity changed: {destination}")
    old_record = _record_from_observation(observed)
    parent = destination.parent
    parent_identity = root_identity if not parts[:-1] else observed.ancestors[-1][1]
    stage = _stage_file(parent, data, mode, observed.ancestors)
    backup = _reserve_artifact(parent, "backup")
    tx = _transaction("replace", key, authority_record=authority_record, old_record=old_record, new_record=stage.record, stage=stage.artifact, backup=backup)
    candidate = copy.deepcopy(state)
    candidate["transactions"][key] = tx
    try:
        _persist_candidate(state_path, state, candidate, root, root_identity)
    except BaseException:
        _cleanup_artifact(stage.artifact, stage.record)
        _cleanup_artifact(backup, None)
        raise
    _move_exact_to_backup(destination, old_record, backup, parent_identity)
    _publish_staged_file(stage, destination, stage.record, parent_identity)
    _commit_transaction(state_path, state, key, stage.record, root, root_identity)
    _cleanup_artifact(stage.artifact, stage.record)
    _cleanup_artifact(backup, old_record)
    _finish_transaction(state_path, state, key, root, root_identity)
    return stage.record


def _execute_delete(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
    key: str,
    authority_record: dict[str, Any],
) -> None:
    _, parts, destination = _transaction_destination(root, key)
    observed = _inspect_leaf(root, root_fd, parts)
    if not _exact_matches(observed, authority_record):
        raise RecoveryConflict(f"owned destination changed before removal: {destination}")
    old_record = _record_from_observation(observed)
    parent_identity = root_identity if not parts[:-1] else observed.ancestors[-1][1]
    backup = _reserve_artifact(destination.parent, "backup")
    tx = _transaction("delete", key, authority_record=authority_record, old_record=old_record, new_record=None, stage=None, backup=backup)
    candidate = copy.deepcopy(state)
    candidate["transactions"][key] = tx
    try:
        _persist_candidate(state_path, state, candidate, root, root_identity)
    except BaseException:
        _cleanup_artifact(backup, None)
        raise
    _move_exact_to_backup(destination, old_record, backup, parent_identity)
    _commit_transaction(state_path, state, key, None, root, root_identity)
    _cleanup_artifact(backup, old_record)
    _finish_transaction(state_path, state, key, root, root_identity)


def _transaction_artifacts(tx: dict[str, Any]) -> tuple[StagedFile | None, PrivateArtifact | None]:
    stage = None
    if tx["stage"] is not None:
        artifact = _artifact_from_state(tx["stage"])
        assert tx["new_record"] is not None
        stage = StagedFile(artifact, tx["new_record"])
    backup = _artifact_from_state(tx["backup"]) if tx["backup"] is not None else None
    return stage, backup


def _validate_transaction_artifact_location(root: Path, key: str, tx: dict[str, Any]) -> None:
    _, _, destination = _transaction_destination(root, key)
    for field in ("stage", "backup"):
        value = tx[field]
        if value is None:
            continue
        artifact = _artifact_from_state(value)
        if artifact.container.parent != destination.parent:
            raise RecoveryConflict(f"transaction artifact escaped destination parent: {artifact.container}")


def _recover_one(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
    key: str,
) -> None:
    tx = state["transactions"][key]
    _validate_transaction_artifact_location(root, key, tx)
    _, parts, destination = _transaction_destination(root, key)
    live = _inspect_leaf(root, root_fd, parts)
    stage, backup = _transaction_artifacts(tx)
    operation = tx["operation"]
    old_record = tx["old_record"]
    new_record = tx["new_record"]

    if tx["phase"] == "committed":
        active = state["manifest"] if key == _MANIFEST_TRANSACTION_KEY else state["entries"].get(key)
        if active is None:
            if live.state != "missing":
                raise RecoveryConflict(f"committed delete destination changed: {destination}")
        elif not _exact_matches(live, active):
            raise RecoveryConflict(f"committed destination changed: {destination}")
        if stage is not None:
            if not (_stage_published(stage) or _artifact_empty(stage.artifact)):
                raise RecoveryConflict(f"committed stage changed: {stage.artifact.container}")
            _cleanup_artifact(stage.artifact, stage.record)
        if backup is not None:
            assert old_record is not None
            if not (_backup_exact(backup, old_record) or _artifact_empty(backup)):
                raise RecoveryConflict(f"committed backup changed: {backup.container}")
            _cleanup_artifact(backup, old_record)
        _finish_transaction(state_path, state, key, root, root_identity)
        return

    if operation == "create":
        assert stage is not None and new_record is not None
        if _exact_matches(live, new_record) and _stage_published(stage):
            _commit_transaction(state_path, state, key, new_record, root, root_identity)
            _recover_one(root, root_fd, state_path, state, root_identity, key)
            return
        if live.state == "missing" and _stage_exact(stage):
            _cleanup_artifact(stage.artifact, stage.record)
            _finish_transaction(state_path, state, key, root, root_identity)
            return
        raise RecoveryConflict(f"interrupted create conflict: {destination}")

    assert old_record is not None and backup is not None
    if operation == "replace":
        assert stage is not None and new_record is not None
        if _exact_matches(live, new_record) and _stage_published(stage) and _backup_exact(backup, old_record):
            _commit_transaction(state_path, state, key, new_record, root, root_identity)
            _recover_one(root, root_fd, state_path, state, root_identity, key)
            return
        if live.state == "missing" and _stage_exact(stage) and _backup_exact(backup, old_record):
            parent_identity = root_identity if not parts[:-1] else old_record["ancestors"][-1]["identity"]
            _rename_noreplace(backup.payload, destination, source_parent_identity=backup.identity, destination_parent_identity=parent_identity)
            try:
                backup.witness.unlink()
            except FileNotFoundError:
                pass
            _cleanup_artifact(stage.artifact, stage.record)
            _cleanup_artifact(backup, None)
            _finish_transaction(state_path, state, key, root, root_identity)
            return
        authority = tx["authority_record"]
        if authority is not None and _authority_matches(live, authority) and _stage_exact(stage) and _artifact_empty(backup):
            _cleanup_artifact(stage.artifact, stage.record)
            _cleanup_artifact(backup, None)
            _finish_transaction(state_path, state, key, root, root_identity)
            return
        raise RecoveryConflict(f"interrupted replace conflict: {destination}")

    if live.state == "missing" and _backup_exact(backup, old_record):
        _commit_transaction(state_path, state, key, None, root, root_identity)
        _recover_one(root, root_fd, state_path, state, root_identity, key)
        return
    authority = tx["authority_record"]
    if authority is not None and _exact_matches(live, authority) and _artifact_empty(backup):
        _cleanup_artifact(backup, None)
        _finish_transaction(state_path, state, key, root, root_identity)
        return
    raise RecoveryConflict(f"interrupted delete conflict: {destination}")


def _recover_transactions(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
    *,
    read_only: bool,
) -> None:
    if read_only and state["transactions"]:
        for key, tx in state["transactions"].items():
            _validate_transaction_artifact_location(root, key, tx)
        return
    for key in sorted(list(state["transactions"])):
        _recover_one(root, root_fd, state_path, state, root_identity, key)


def _plan_install(
    root: Path,
    root_fd: int | None,
    files: dict[str, str],
    normalised: dict[str, tuple[str, ...]],
    state: dict[str, Any],
    *,
    force: bool,
) -> dict[str, str]:
    actions: dict[str, str] = {}
    for rel in sorted(files):
        observed = _inspect_leaf(root, root_fd, normalised[rel])
        record = state["entries"].get(rel)
        canonical = content_digest(files[rel])
        if record is None:
            actions[rel] = "created" if observed.state == "missing" else "skipped-foreign"
            continue
        if observed.state != "regular-readable" or not _authority_matches(observed, record):
            actions[rel] = "skipped-foreign"
        elif observed.digest != record["digest"]:
            actions[rel] = "restored" if force else "skipped-modified"
        elif observed.mode != record["mode"] and _platform_system() != "Windows":
            actions[rel] = "skipped-modified"
        elif observed.digest == canonical:
            actions[rel] = "unchanged"
        else:
            actions[rel] = "updated"
    for rel, record in sorted(state["entries"].items()):
        if rel in files:
            continue
        observed = _inspect_leaf(root, root_fd, _normalise_relative_path(rel))
        actions[rel] = "removed" if _exact_matches(observed, record) else "skipped-remove-modified"
    return actions


def _preflight_manifest(root: Path, root_fd: int | None, state: dict[str, Any]) -> None:
    parts = _normalise_relative_path(MANIFEST_REL, allow_manifest=True)
    observed = _inspect_leaf(root, root_fd, parts)
    record = state["manifest"]
    if record is None:
        if observed.state != "missing":
            raise ResearchOSError("pre-existing Research OS manifest is foreign")
        return
    if not _exact_matches(observed, record):
        raise ResearchOSError("Research OS manifest identity or content changed")


def _active_records(root: Path, root_fd: int | None, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for rel, record in sorted(state["entries"].items()):
        if rel in state["conflicts"]:
            continue
        observed = _inspect_leaf(root, root_fd, _normalise_relative_path(rel))
        if not _exact_matches(observed, record):
            raise RecoveryConflict(f"owned leaf changed before manifest publication: {rel}")
        active[rel] = record
    return active


def _manifest_bytes(root: Path, root_identity: str, active: dict[str, dict[str, Any]]) -> bytes:
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "state": "complete",
        "target": {
            "path_sha256": hashlib.sha256(os.fsencode(_physical_target(root))).hexdigest(),
            "identity": root_identity,
        },
        "files": {rel: record["digest"] for rel, record in sorted(active.items())},
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publish_manifest(
    root: Path,
    root_fd: int | None,
    state_path: Path,
    state: dict[str, Any],
    root_identity: str,
) -> None:
    active = _active_records(root, root_fd, state)
    if not active and state["manifest"] is None:
        return
    data = _manifest_bytes(root, root_identity, active)
    parts = _normalise_relative_path(MANIFEST_REL, allow_manifest=True)
    observed = _inspect_leaf(root, root_fd, parts)
    record = state["manifest"]
    if record is None:
        if observed.state != "missing":
            raise RecoveryConflict("foreign manifest appeared before publication")
        _execute_create(root, root_fd, state_path, state, root_identity, _MANIFEST_TRANSACTION_KEY, data, 0o600)
    else:
        if not _exact_matches(observed, record):
            raise RecoveryConflict("owned manifest changed before publication")
        if observed.digest != _bytes_digest(data):
            _execute_replace(root, root_fd, state_path, state, root_identity, _MANIFEST_TRANSACTION_KEY, record, data, 0o600)
    active_after = _active_records(root, root_fd, state)
    manifest_observed = _inspect_leaf(root, root_fd, parts)
    if not _exact_matches(manifest_observed, state["manifest"]):
        raise RecoveryConflict("manifest changed after publication")
    if _manifest_bytes(root, root_identity, active_after) != data:
        raise RecoveryConflict("owned tree changed during manifest publication")


def _record_conflicts(state: dict[str, Any], actions: dict[str, str]) -> bool:
    changed = False
    conflict_actions = {"skipped-foreign", "skipped-modified", "skipped-remove-modified"}
    for rel, action in actions.items():
        if action in conflict_actions and rel in state["entries"]:
            value = {"action": action, "reason": "ownership identity, content, mode, or readability did not match"}
            if state["conflicts"].get(rel) != value:
                state["conflicts"][rel] = value
                changed = True
        elif action not in conflict_actions and rel in state["conflicts"]:
            state["conflicts"].pop(rel)
            changed = True
    return changed


def _apply_locked(
    root: Path,
    files: dict[str, str],
    normalised: dict[str, tuple[str, ...]],
    *,
    force: bool,
    dry_run: bool,
) -> dict[str, str]:
    root_fd = _open_root(root)
    try:
        root_identity = _path_identity(root)
        if root_fd is not None and _fd_identity(root_fd) != root_identity:
            raise ResearchOSError("target root changed while opening")
        state_path = _state_path(root)
        state, state_exists = _load_state(state_path, root, root_identity)
        _recover_transactions(root, root_fd, state_path, state, root_identity, read_only=dry_run)
        if state["transactions"]:
            if not dry_run:
                raise RecoveryConflict("interrupted Research OS transaction remains unresolved")
            return _plan_install(root, root_fd, files, normalised, state, force=force)
        _preflight_manifest(root, root_fd, state)
        actions = _plan_install(root, root_fd, files, normalised, state, force=force)
        if dry_run:
            return actions

        for rel in sorted(files):
            action = actions[rel]
            data = files[rel].encode("utf-8")
            mode = 0o700 if _is_executable_rel(rel) else 0o600
            if action == "created":
                _execute_create(root, root_fd, state_path, state, root_identity, rel, data, mode)
                state_exists = True
            elif action in {"updated", "restored"}:
                record = state["entries"][rel]
                _execute_replace(root, root_fd, state_path, state, root_identity, rel, record, data, mode)
        for rel in sorted(set(state["entries"]) - set(files)):
            if actions[rel] == "removed":
                _execute_delete(root, root_fd, state_path, state, root_identity, rel, state["entries"][rel])

        conflicts_changed = _record_conflicts(state, actions)
        if conflicts_changed and (state_exists or state["entries"] or state["manifest"] is not None):
            _write_state(state_path, state, root, root_identity)
            state_exists = True
        _publish_manifest(root, root_fd, state_path, state, root_identity)
        return actions
    finally:
        if root_fd is not None:
            os.close(root_fd)


def apply_install(
    root: Path,
    *,
    files: dict[str, str],
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, str]:
    root = Path(root)
    normalised = _validated_files(files)
    if dry_run:
        return _apply_locked(root, files, normalised, force=force, dry_run=True)
    state_path = _state_path(root)
    with _state_lock(state_path):
        return _apply_locked(root, files, normalised, force=force, dry_run=False)



def main() -> int:
    parser = argparse.ArgumentParser(description="Install a Codex-native research OS scaffold into a repository.")
    # Required, never defaulted to the current directory: a no-argument run once scaffolded the
    # whole research OS into the invoking repository. The target root is an explicit operator
    # choice, so the missing argument fails before any path is resolved.
    parser.add_argument("--target", required=True, help="Target repository root (required).")
    parser.add_argument("--project-name", default=None, help="Human-readable project name.")
    parser.add_argument("--force", action="store_true", help="Re-copy owned but modified files back to canonical.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()

    root = Path(args.target).expanduser().resolve()
    project_name = args.project_name or root.name
    files = build_files(project_name)

    try:
        actions = apply_install(root, files=files, force=args.force, dry_run=args.dry_run)
    except TargetRootError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INPUT

    counts: dict[str, int] = {}
    for rel in sorted(actions):
        state = actions[rel]
        counts[state] = counts.get(state, 0) + 1
        print(f"{state:>22} {rel}")

    print("\nResearch OS setup summary")
    print(json.dumps(counts, indent=2, sort_keys=True))
    if args.dry_run:
        print("\n(dry run: no files written)")
    print("\nNext:")
    print("  make status")
    print("  make validate-claims")
    print("  make validate-experiments")
    print("  make review-gates")
    partial_actions = {"skipped-foreign", "skipped-modified", "skipped-remove-modified"}
    return 1 if any(action in partial_actions for action in actions.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
