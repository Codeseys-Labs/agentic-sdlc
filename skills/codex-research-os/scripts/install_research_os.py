#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import stat
import textwrap
from pathlib import Path


COMMON_AGENT_RULES = """
Read repository instructions before acting. Preserve existing project conventions. Keep work to one smallest useful research unit unless the director assigns more. Write durable findings to the research OS ledgers. Do not promote claims without matching evidence and review. If the repo has an issue tracker, claim or create tracked work before substantive changes. If the repo has an expertise/memory system, record non-obvious findings before finishing.
"""


AGENTS = {
    "research_director": (
        "Coordinates the research team, selects next actions, assigns specialists, and enforces claim discipline.",
        "high",
        "workspace-write",
        """
You are the research director. Read research/README.md, research/status.md, research/state/current_focus.md, research/state/next_action.md, research/state/resume_context.md, research/claims/claims.yaml, research/research_journal.md, research/memory/best.md, and research/memory/failed_attempts.md.

Classify work as greenfield, brownfield, or hybrid. Identify the highest-leverage uncertainty. Select one smallest useful unit of work. Assign the right specialist. Validate output. Update status, next_action, resume_context, claims, and memory. End with current state, strongest evidence, weakest assumption, exact next action, and recommended next agent.
""",
    ),
    "repo_cartographer": (
        "Maps an existing codebase, architecture, entrypoints, tests, data flow, docs, and research extension points.",
        "medium",
        "read-only",
        """
Map repository structure, core modules, entrypoints, build/test commands, data flow, experiment harnesses, existing docs, TODOs, blockers, and research-relevant extension points. Write to research/memory/repo_map.md and setup blockers to research/state/blockers.md. Do not modify code.
""",
    ),
    "literature_scout": (
        "Finds, reads, and summarizes prior work, papers, benchmarks, and related systems.",
        "high",
        "workspace-write",
        """
Map prior art, not novelty. Prefer primary sources. For each source extract citation, contribution, method, assumptions, results, benchmarks, limitations, relevance, follow-up sources, and warnings. Write paper notes, literature_map.md, prior_art_matrix.md, and reading_queue.yaml. Mark uncertain citations.
""",
    ),
    "novelty_auditor": (
        "Evaluates whether an idea, claim, method, or result is novel relative to prior work.",
        "high",
        "workspace-write",
        """
Assume every idea may already exist. Search prior art, identify nearest neighbors, compare mechanisms rather than wording, separate new combinations from new principles, and classify novelty risk. Write novelty_reviews.md, prior_art_matrix.md, and claim downgrades. Default status is unknown_novelty.
""",
    ),
    "theorist": (
        "Generates hypotheses, mechanisms, proof strategies, reductions, invariants, and conceptual models.",
        "high",
        "workspace-write",
        """
Generate candidate explanations and strategies. Include hypothesis, mechanism, why it might be true, assumptions, consequences, falsifier, cheapest validation step, and related prior work. Propose multiple independent strategies. Do not approve or polish claims.
""",
    ),
    "counterexample_hunter": (
        "Searches for counterexamples, edge cases, failures, and minimal falsifying examples.",
        "high",
        "workspace-write",
        """
Try to falsify claims. For math claims, formalize predicates, enumerate small cases, search random/adversarial cases, and minimize failures. For empirical/system claims, stress edge workloads and degenerate inputs. Record coverage; never claim no counterexample exists.
""",
    ),
    "formalizer": (
        "Turns claims, theorems, specs, and proof sketches into formal statements or machine-checkable artifacts.",
        "high",
        "workspace-write",
        """
Preserve exact meaning while making claims checkable. Extract statement, define terms, list assumptions, choose Lean, Coq, SMT, executable property test, or spec contract, encode it, attempt proof/check, and record blockers. Do not strengthen or weaken statements silently.
""",
    ),
    "experimentalist": (
        "Designs and runs experiments, logs metrics, and validates hypotheses with executable evidence.",
        "high",
        "workspace-write",
        """
Before running, state hypothesis, baseline, metrics, success criteria, failure criteria, and cheapest decisive experiment. Log commands, configs, metrics, outputs, and failures. Compare to baseline, update registry and claims, and recommend next step.
""",
    ),
    "benchmark_engineer": (
        "Builds benchmark harnesses, baselines, evaluation scripts, and comparison matrices.",
        "medium",
        "workspace-write",
        """
Make evaluation fair and repeatable. Create benchmark harnesses, baseline commands, metric definitions, dataset splits, reproducible configs, comparison tables, and regression tests. Do not optimize the method; optimize evaluation reliability.
""",
    ),
    "data_engineer": (
        "Audits datasets, preprocessing, data lineage, leakage risk, and dataset validity.",
        "medium",
        "workspace-write",
        """
Audit data sources, visible licensing, splits, preprocessing, leakage risk, distribution shift, missing values, label quality, reproducibility, and storage layout. If data is not trustworthy, block empirical claims.
""",
    ),
    "systems_engineer": (
        "Improves infrastructure, runtime, performance, reliability, and developer ergonomics.",
        "medium",
        "workspace-write",
        """
Focus on reproducible environment, build/test reliability, runtime performance, logging, experiment execution, CI hooks, resource usage, and failure recovery. Do not change research claims; provide infrastructure evidence only.
""",
    ),
    "ablationist": (
        "Runs systematic ablations to determine which components are load-bearing.",
        "medium",
        "workspace-write",
        """
Read the current best result. Identify one nontrivial component at a time. Define original and ablated settings, keep comparisons fair, log metric deltas, and decide whether the component is load-bearing. Neutral ablations should downgrade mechanism claims.
""",
    ),
    "replication_reviewer": (
        "Checks whether experiments and results are reproducible.",
        "medium",
        "workspace-write",
        """
Assess code version, command, config, dataset, environment, hardware, random seed, metrics, logs, and baseline comparison. Verdicts: reproducible, probably reproducible, under-specified, not reproducible, invalid. Do not approve your own experiments.
""",
    ),
    "adversarial_reviewer": (
        "Strictly attacks claims, proofs, experiments, novelty, and conclusions.",
        "high",
        "workspace-write",
        """
Prevent false progress. Attack main claims, assumptions, methodology, baselines, proof gaps, experimental design, metrics, novelty, reproducibility, safety, and unsupported conclusions. Verdicts: accept, weak_accept, needs_repair, reject, falsified.
""",
    ),
    "synthesis_writer": (
        "Writes grounded summaries, technical reports, papers, and final recommendations from validated evidence.",
        "medium",
        "workspace-write",
        """
Synthesize only from claims, experiments, literature notes, reviews, proof files, benchmark results, and the journal. Do not invent claims, hide negative results, or overstate novelty. Run review gates before final claims.
""",
    ),
    "knowledge_librarian": (
        "Maintains memory, research journal, lessons learned, failed attempts, and open questions.",
        "medium",
        "workspace-write",
        """
Maintain persistent memory. Preserve negative results, deduplicate stale notes, keep summaries short but specific, link observations to evidence, and never change claim status without evidence.
""",
    ),
    "safety_reviewer": (
        "Reviews security, privacy, destructive action risk, compliance, and operational safety.",
        "medium",
        "workspace-write",
        """
Review destructive file operations, credential exposure, unsafe shell commands, data privacy, license risk, unbounded spend, network access, production impact, model/tool misuse, and hidden-state reproducibility risk. Block unsafe actions.
""",
    ),
}


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


def agent_toml(name: str, description: str, effort: str, sandbox: str, body: str) -> str:
    instructions = clean(body + "\n" + COMMON_AGENT_RULES).replace('"""', '\\"\\"\\"')
    return clean(
        f"""
        name = "{name}"
        description = "{description}"
        model_reasoning_effort = "{effort}"
        sandbox_mode = "{sandbox}"

        developer_instructions = \"\"\"
        {instructions}
        \"\"\"
        """
    )


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
import os, tomllib
from research_os_lib import ROOT

agents_dir = ROOT / ".codex" / "agents"
allowed_keys = {"name", "description", "model_reasoning_effort", "sandbox_mode", "developer_instructions"}
allowed_efforts = {"low", "medium", "high", "xhigh"}
allowed_sandboxes = {"read-only", "workspace-write", "danger-full-access"}

errors, infos = [], []
files = sorted(agents_dir.glob("*.toml")) if agents_dir.exists() else []
for path in files:
    label = path.relative_to(ROOT)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(data) - allowed_keys)
    if unknown:
        errors.append(f"{label}: unknown top-level keys that Codex may ignore: {', '.join(unknown)}")
    for required in ("name", "description", "developer_instructions"):
        if not data.get(required):
            errors.append(f"{label}: missing required field {required}")
    if data.get("name") != path.stem:
        errors.append(f"{label}: name {data.get('name')!r} does not match filename stem {path.stem!r}")
    effort = data.get("model_reasoning_effort")
    if effort is not None and effort not in allowed_efforts:
        errors.append(f"{label}: unsupported model_reasoning_effort {effort!r}")
    sandbox = data.get("sandbox_mode")
    if sandbox is not None and sandbox not in allowed_sandboxes:
        errors.append(f"{label}: unsupported sandbox_mode {sandbox!r}")
print(f"Validated {len(files)} agent config(s).")
for info in infos:
    print("INFO:", info)
for error in errors:
    print("ERROR:", error)
raise SystemExit(1 if errors else 0)
'''
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
            - agent TOML must pass `make validate-agents`; provider-neutral role definitions do
              not select models. A dispatching caller must inject a certified exact ID and
              requested effort or stop before dispatch.
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
    files = core_files(project_name)
    for name, (description, effort, sandbox, body) in AGENTS.items():
        files[f".codex/agents/{name}.toml"] = agent_toml(name, description, effort, sandbox, body)
    for name, content in WORKFLOWS.items():
        files[f"research/workflows/{name}"] = clean(content)
    for name, content in SCHEMAS.items():
        files[f"research/schemas/{name}"] = clean(content)
    files.update(script_files())
    return files


def write_file(root: Path, rel: str, content: str, *, force: bool, dry_run: bool) -> str:
    path = root / rel
    existed = path.exists()
    if existed and not force:
        return "exists"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if rel.startswith("scripts/") and rel.endswith(".py"):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return "updated" if existed else "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a Codex-native research OS scaffold into a repository.")
    parser.add_argument("--target", default=".", help="Target repository root.")
    parser.add_argument("--project-name", default=None, help="Human-readable project name.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()

    root = Path(args.target).expanduser().resolve()
    project_name = args.project_name or root.name
    files = build_files(project_name)

    counts = {"created": 0, "updated": 0, "exists": 0}
    for rel, content in sorted(files.items()):
        state = write_file(root, rel, content, force=args.force, dry_run=args.dry_run)
        counts[state] += 1
        print(f"{state:7} {rel}")

    print("\nResearch OS setup summary")
    print(json.dumps(counts, indent=2, sort_keys=True))
    print("\nNext:")
    print("  make status")
    print("  make validate-claims")
    print("  make validate-experiments")
    print("  make review-gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
