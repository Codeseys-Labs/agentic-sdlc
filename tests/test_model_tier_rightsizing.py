from __future__ import annotations

import re
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTER = ROOT / "skills" / "model-tier-rightsizing" / "SKILL.md"
CALIBRATION = ROUTER.parent / "references" / "model-routing-calibration.md"
FLAGSHIP = ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "tiered-orchestration.md"

CONSUMERS = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "commands" / "sdlc-frame.md",
    ROOT / "commands" / "sdlc-mission.md",
    ROOT / "commands" / "sdlc-wave.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "delegation-planes.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "sdlc-loop.md",
    FLAGSHIP,
)
POLICY_SURFACES = CONSUMERS + (ROUTER, CALIBRATION)

RUNTIME_ASSIGNMENT_FIELDS = (
    "requested_model_id",
    "requested_effort",
    "requested_context_form",
    "request_injection_status",
    "request_injection_source",
    "request_injection_evidence",
    "resolution_state",
    "resolved_provider",
    "resolved_model_id",
    "model_readback_status",
    "model_identity_basis",
    "model_readback_source",
    "model_readback_evidence",
    "effort_readback_status",
    "effort_readback_source",
    "effort_readback_evidence",
    "context_readback_status",
    "context_readback_source",
    "context_readback_evidence",
)

GLOBAL_RUNTIME_ASSIGNMENT_FIELDS = (
    "requested_model_id",
    "requested_effort",
    "requested_context_form",
    "request_injection_status",
    "request_injection_source",
    "request_injection_evidence",
    "resolution_state",
    "resolved_provider",
    "resolved_model_id",
    "model_readback_status",
    "model_readback_source",
    "model_readback_evidence",
    "effort_readback_status",
    "effort_readback_source",
    "effort_readback_evidence",
    "context_readback_status",
    "context_readback_source",
    "context_readback_evidence",
)

GLOBAL_ROLE_SURFACES = tuple(sorted((ROOT / "agents" / "claude").glob("sdlc-*.md"))) + tuple(
    sorted((ROOT / "agents" / "codex").glob("sdlc-*.toml"))
)

GLOBAL_RUNTIME_CONSUMERS = (
    ROOT / "commands" / "sdlc-wave.md",
    FLAGSHIP,
    ROUTER,
)

ALLOWED_EXACT_MODEL_IDS = frozenset(
    (
        "gpt-5.6-sol",
        "claude-fable-5",
        "gpt-5.6-terra",
        "claude-opus-4-8",
        "gpt-5.6-luna",
        "claude-sonnet-5",
    )
)

RESEARCH_CONSUMERS = (
    ROOT / "README.md",
    ROOT / "agents" / "codex" / "research" / "README.md",
    ROOT / "skills" / "codex-research-os" / "SKILL.md",
    ROOT / "skills" / "codex-research-os" / "references" / "operating-model.md",
    ROOT / "skills" / "codex-research-os" / "references" / "agent-roster.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "research-team.md",
    ROOT / "commands" / "sdlc-wave.md",
    FLAGSHIP,
)

PRIMARY_PAIRS = {
    "frontier": ("gpt-5.6-sol", "claude-fable-5"),
    "judgment": ("gpt-5.6-terra", "claude-opus-4-8"),
    "volume": ("gpt-5.6-luna", "claude-sonnet-5"),
}

ROUTE_MATRICES = {
    "## Exact dispatch and requested effort": {
        "row_header": "Consequence lane",
        "rows": {
            "Derail / settled truth": "frontier",
            "Contained silent-degrade": "judgment",
            "Deterministic-gated volume": "volume",
            "Cheap fully checked redo": "volume",
        },
    },
    "## Blast-radius production routing": {
        "row_header": "Wrong-output consequence",
        "rows": {
            "Cheap deterministic retry": "volume",
            "Visible compiler/test/gate failure": "volume",
            "Silent candidate degradation": "judgment",
            "Run derailment or settled truth": "frontier",
            "Trust, credentials, authority, or data-loss boundary": "frontier",
        },
    },
    "## Agentic SDLC phase routing": {
        "row_header": "Phase",
        "rows": {
            "Frame": "frontier",
            "Discover": "judgment",
            "Research": "judgment",
            "Plan": "frontier",
            "Act, contained": "judgment",
            "Act, deterministic-gated": "volume",
            "Review, semantic": "judgment",
            "Review, trust or authority": "frontier",
            "Reconcile": "judgment",
            "Integrate": "judgment",
            "Ship recommendation": "frontier",
        },
    },
    "## Approved roadmap family lanes": {
        "row_header": "Roadmap lane",
        "rows": {
            "S1 Seeds toolchain retention": "volume",
            "S2 Seeds execution contract": "judgment",
            "Seeds fan-in": "judgment",
            "Wave 1 CAO deletion": "judgment",
            "Wave 2 state-v3 identity cutover": "judgment",
            "Claude marketplace/plugin plane": "judgment",
            "Local checkout rename gate": "frontier",
            "GitHub repository rename gate": "frontier",
            "A1 change-writing": "judgment",
            "A2 Git-default sdlc-init": "judgment",
            "A3 hierarchical instructions": "judgment",
            "R1 shared role contracts": "judgment",
            "R2 bounded Deep Work Loop": "judgment",
            "R3 HyperResearch/Research OS": "judgment",
            "G1 Git change-flow family": "judgment",
            "G2 toolchain/security": "judgment",
            "J1 jj certification": "judgment",
            "J2 jj implementation": "judgment",
            "A2j jj init amendment": "judgment",
            "M0a Mermaid browser ADR/spike": "judgment",
            "M0b Mermaid security foundation": "judgment",
            "M1 structural Mermaid skills": "volume",
            "M2 planning Mermaid skills": "volume",
            "M3 quantitative Mermaid skills": "volume",
            "M4 technical Mermaid skills": "volume",
            "M5 conceptual Mermaid skills": "volume",
            "M6 Mermaid router": "judgment",
            "M7 Mermaid conformance": "volume",
            "Release hardening": "judgment",
            "Evolutionary Core M2": "judgment",
            "Claude Golden Wave M3": "judgment",
            "Portability M4": "judgment",
            "CCP/ccodex certification": "judgment",
            "Final family wiring": "judgment",
        },
    },
}

FABLE_BOUNDARY = (
    "Fable is eligible only for a certified, bounded frontier/adversarial packet; "
    "it never settles truth or replaces the Sol peer."
)
FABLE_NO_PEER = "Settled-truth work stops or reduces scope if no certified peer is available."


def _table(text: str, heading: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    marker = f"{heading}\n"
    assert marker in text, f"missing heading: {heading}"
    lines: list[str] = []
    started = False
    for line in text.split(marker, 1)[1].splitlines():
        if line.startswith("|"):
            started = True
            lines.append(line)
        elif started:
            break
    assert len(lines) >= 2, f"missing table below {heading}"

    def cells(line: str) -> tuple[str, ...]:
        assert line.endswith("|"), f"unterminated table row: {line}"
        return tuple(cell.strip() for cell in line[1:-1].split("|"))

    header = cells(lines[0])
    separator = cells(lines[1])
    assert len(header) == len(separator), f"separator width differs below {heading}"
    assert all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator), f"invalid separator below {heading}"
    rows = tuple(cells(line) for line in lines[2:])
    assert all(len(row) == len(header) for row in rows), f"malformed columns below {heading}"
    return header, rows


def _operational_cells(text: str) -> str:
    headings = (
        "## Four semantic tiers and eligible pairs",
        *ROUTE_MATRICES,
    )
    return "\n".join(
        " | ".join(cell for row in _table(text, heading)[1] for cell in row)
        for heading in headings
    )


def _expected_pair_cell(pair: str) -> str:
    left, right = PRIMARY_PAIRS[pair]
    return f"`{left}` or `{right}`"


def _assert_conditionally_eligible_pair(selection: str) -> None:
    assert not re.search(
        r"(?is)\b(?:choose|select|route|dispatch)\s+(?:gpt|claude)\b.{0,100}\b(?:every|all)\s+(?:dispatch|route|task|case)s?\b",
        selection,
    ), selection
    assert not re.search(
        r"(?is)\b(?:gpt|claude)\b.{0,120}\b(?:documentary\s+only|never\s+(?:selected|chosen|eligible)|not\s+eligible)\b",
        selection,
    ), selection


def _assert_frontier_selection_boundary(selection: str) -> None:
    if re.search(r"(?i)\bfable\b", selection):
        assert re.search(r"(?i)\bcertified\b", selection), selection
        assert re.search(r"(?i)\bbounded\b", selection), selection
        assert re.search(r"(?i)\b(?:adversarial|attack|counterexample)\w*\b", selection), selection
        assert not re.search(r"(?is)\bfable\b.{0,100}\b(?:settle|form|derive)\w*.{0,40}\btruth\b", selection), selection
    assert not re.search(r"(?is)\b(?:sol|peer)\b.{0,100}\boptional\b", selection), selection


def _assert_no_context_window_expansion_claim(text: str) -> None:
    qualifier = r"(?:larger|effective|one[-\s]million[-\s]token|1,000,000[-\s]token|1m(?:[-\s]token)?)"
    window = r"(?:upstream\s+)?context\s+window"
    assert not re.search(
        rf"(?is)\[1m\].{{0,160}}\b(?:provides|expands|increases)\b.{{0,160}}(?:\b{qualifier}\b.{{0,80}}\b{window}\b|\b{window}\b.{{0,80}}\b{qualifier}\b)",
        text,
    )


def _assert_effort_resolution_boundary(text: str) -> None:
    assert not re.search(
        r"(?is)\brequested\s+effort\s+(?:equals?|is|guarantees?|proves?)\s+(?:the\s+)?(?:resolved|effective\s+upstream)\s+effort\b.{0,100}\b(?:after|upon|on|with)\b.{0,50}\b(?:success|successful)\w*",
        text,
    )


def _assert_primary_route_allocation(text: str) -> None:
    for heading, matrix in ROUTE_MATRICES.items():
        header, rows = _table(text, heading)
        assert matrix["row_header"] in header, f"missing row key in {heading}"
        assert "Eligible primary exact IDs" in header, f"missing pair allocation in {heading}"
        assert "Selection condition" in header, f"missing selection condition in {heading}"
        row_index = header.index(matrix["row_header"])
        primary_index = header.index("Eligible primary exact IDs")
        selection_index = header.index("Selection condition")
        by_name = {row[row_index]: row for row in rows}
        assert set(by_name) == set(matrix["rows"]), f"unexpected routing rows in {heading}"
        for name, pair in matrix["rows"].items():
            row = by_name[name]
            allocation = row[primary_index]
            selection = row[selection_index]
            assert allocation == _expected_pair_cell(pair), (heading, name, allocation)
            assert re.search(r"(?i)\bchoose\b", selection), (heading, name, selection)
            assert len(selection.split()) >= 8, (heading, name, selection)
            _assert_conditionally_eligible_pair(selection)
            if pair == "frontier":
                _assert_frontier_selection_boundary(selection)


def _assert_tier_pair_allocation(text: str) -> None:
    header, rows = _table(text, "## Four semantic tiers and eligible pairs")
    assert header == (
        "Semantic tier",
        "Wrong-output consequence",
        "Eligible exact pair",
        "Requested effort",
        "Required gate or control",
    )
    by_tier = {row[0]: row for row in rows}
    assert by_tier["Frontier"][2] == _expected_pair_cell("frontier")
    assert by_tier["Judgment workhorse"][2] == _expected_pair_cell("judgment")
    assert by_tier["Capable volume"][2] == _expected_pair_cell("volume")
    assert by_tier["Mechanical floor"][2] == (
        "Cheapest certified route from `gpt-5.6-luna` or `claude-sonnet-5`"
    )


def _assert_fable_boundary(text: str) -> None:
    assert FABLE_BOUNDARY in text
    assert FABLE_NO_PEER in text
    assert "and remains advisory to the conductor." in text
    assert "retention" in text.lower()
    assert "refusal" in text.lower()
    assert re.search(r"(?is)(?:new[- ]model|day[- ]one).{0,100}(?:503|capacity)", text)


def _assert_no_unsafe_executable_aliases(text: str) -> None:
    bare = r"(?:fable|opus|sonnet|haiku)"
    key = r"['\"`]?model['\"`]?"
    assert not re.search(
        rf"(?ix)\b{key}\s*(?::|=|\s)\s*['\"`]?{bare}['\"`]?\b",
        text,
    )
    assert not re.search(
        rf"(?ix)\b{key}\s*(?::|=|\s)\s*['\"`]?(?:global|us|eu|ap)\.anthropic\.claude-[\w.-]+['\"`]?\b",
        text,
    )


def _assert_authority(text: str) -> None:
    assert "The conductor alone\nadjudicates and mutates Seeds; only an authorized integrator performs an already-authorized\nfan-in; humans authorize outward actions." in text
    assert not re.search(
        r"(?i)(?:`)?(?:gpt-5\.6-(?:sol|terra|luna)|claude-(?:fable-5|opus-4-8|sonnet-5))(?:`)?\s+(?:owns?|decides?|authori[sz]\w*|mutat\w*)\s+(?:Seeds|the queue|fan-in|outward)",
        text,
    )
    assert not re.search(r"(?im)^\s*(?:edit|change|mutate|write)\s+(?:user )?(?:settings|trust)\b", text)


def _assert_calibration(text: str) -> None:
    _assert_tier_pair_allocation(text)
    _assert_primary_route_allocation(text)
    operational = _operational_cells(text)
    for family in (*PRIMARY_PAIRS["frontier"], *PRIMARY_PAIRS["judgment"], *PRIMARY_PAIRS["volume"]):
        assert family in operational, f"missing primary model family: {family}"
    assert "Mechanical floor" in operational
    assert "same deterministic gate remains" in text.lower()
    assert "immutable candidate and explicit acceptance criteria" in text.lower()
    assert "If no certified route exists, fail closed" in text
    _assert_no_unsafe_executable_aliases(operational)
    _assert_fable_boundary(text)
    _assert_authority(text)


def _assert_no_unsafe_operational_prose(text: str) -> None:
    assert not re.search(r"(?i)\b(?:global|us|eu|ap)\.anthropic\.claude-[\w.-]+\b", text)
    _assert_no_unsafe_executable_aliases(text)
    assert not re.search(r"(?i)\b(?:use|set|route|dispatch|select)\b.{0,80}\b(?:fable|opus|sonnet|haiku)\b\s*(?:alias|by default)", text)
    assert not re.search(r"(?i)\b(?:host|provider)\s+default\b.{0,100}\b(?:model|selection|dispatch)", text)


def _assert_context_claims(text: str) -> None:
    _assert_no_context_window_expansion_claim(text)
    assert not re.search(
        r"(?i)\[1m\].{0,100}(?:more intelligent|higher intelligence|proves? (?:a )?1m|guarantees? (?:a )?1m|upstream capacity|effective capacity)",
        text,
    )


def _claude_frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "missing Claude YAML frontmatter"
    raw = text.split("---\n", 2)[1]
    parsed: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.fullmatch(r"([A-Za-z_][\w-]*):\s*(.*)", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _assert_no_static_model_selection(text: str) -> None:
    if text.startswith("---\n"):
        metadata = _claude_frontmatter(text)
    else:
        metadata = tomllib.loads(text)
    assert "model" not in metadata, "provider-neutral role must not pin model"
    assert "model_reasoning_effort" not in metadata, "provider-neutral role must not pin effort"


def _assert_global_runtime_role_contract(text: str) -> None:
    if text.lstrip().startswith(("name =", "name=")):
        match = re.search(r'developer_instructions\s*=\s*"""(.*?)"""', text, re.DOTALL)
        contract = match.group(1) if match else text
    else:
        contract = text
    for field in GLOBAL_RUNTIME_ASSIGNMENT_FIELDS:
        assert field in contract, f"missing runtime assignment field: {field}"
    assert "conductor-supplied certified `RuntimeAssignment`" in contract
    assert re.search(r"(?is)resolution_state.{0,80}(?:must equal|must be).{0,30}resolved", contract)
    assert re.search(r"(?is)Requested, inherited, or unresolved.{0,180}SeedProposal", contract)
    assert re.search(r"(?is)unverified model identity.{0,180}SeedProposal", contract)
    assert re.search(r"(?m)^(?:- )?`?resolved_provider`?: [^\n]*non-unknown[^\n]+unknown is forbidden[^\n]*$", contract)
    assert re.search(r"(?m)^(?:- )?`?resolved_model_id`?: [^\n]*non-unknown[^\n]*$", contract)
    assert re.search(r"(?m)^(?:- )?`?request_injection_status`?: [^\n]*verified[^\n]*$", contract)
    assert re.search(r"(?m)^(?:- )?`?model_readback_status`?: [^\n]*verified[^\n]*$", contract)
    assert re.search(r"(?m)^(?:- )?`?effort_readback_status`?: [^\n]*verified[^\n]*unavailable[^\n]*$", contract)
    assert re.search(r"(?m)^(?:- )?`?context_readback_status`?: [^\n]*verified[^\n]*unavailable[^\n]*$", contract)
    assert "stop before spawn" in contract
    assert "inject the exact requested model and effort" in contract
    assert re.search(r"(?is)request injection.{0,100}(?:immutable|verified)", contract)
    assert re.search(r"(?is)effective effort.{0,120}(?:unavailable|not exposed)", contract)
    assert re.search(r"(?is)effective context.{0,120}(?:unavailable|not exposed)", contract)
    assert re.search(r"(?is)never copy requested.{0,100}(?:resolved|readback)", contract)
    _assert_effort_resolution_boundary(contract)
    _assert_no_static_model_selection(text)
    assert not re.search(r"(?i)host (?:configuration|default).{0,80}(?:choose|select|supply).{0,40}model", contract)
    assert not re.search(r"(?is)prompt prose.{0,80}(?:enforces|guarantees|sets).{0,40}(?:model|effort)", contract)


def _assert_global_runtime_consumer_contract(text: str) -> None:
    for field in (
        "RuntimeAssignment",
        "request_injection_status",
        "request_injection_source",
        "request_injection_evidence",
        "resolved_provider",
        "resolved_model_id",
        "model_readback_status",
        "model_readback_source",
        "model_readback_evidence",
        "effort_readback_status",
        "context_readback_status",
    ):
        assert field in text, f"missing global runtime consumer field: {field}"
    assert re.search(r"(?is)requested.{0,80}inherited.{0,80}unresolved.{0,180}stop", text)
    assert re.search(r"(?is)unverified model[- ]identity.{0,180}stop", text)
    assert re.search(r"(?is)effort_readback_status.{0,100}(?:verified|unavailable)", text)
    assert re.search(r"(?is)context_readback_status.{0,100}(?:verified|unavailable)", text)
    assert re.search(r"(?is)never copy requested.{0,120}(?:resolved|readback)", text)
    assert not re.search(
        r"(?is)(?:resolved_effort|resolved_context_form|provider_readback_source|provider_readback_evidence).{0,160}must (?:all )?be non-unknown",
        text,
    )


def _assert_research_runtime_role_contract(text: str) -> None:
    if text.lstrip().startswith(("name =", "name=")):
        match = re.search(r'developer_instructions\s*=\s*"""(.*?)"""', text, re.DOTALL)
        contract = match.group(1) if match else text
    else:
        contract = text
    for field in RUNTIME_ASSIGNMENT_FIELDS:
        assert field in contract, f"missing runtime assignment field: {field}"
    assert "conductor-supplied certified `RuntimeAssignment`" in contract
    assert re.search(r"(?is)resolution_state.{0,80}(?:must equal|must be).{0,30}resolved", contract)
    assert re.search(r"(?is)Exact model and effort request injection is mandatory.{0,80}immutable", contract)
    assert re.search(r"(?is)(?:may honestly be unavailable only when the exact ID maps unambiguously|source may be unavailable only when an\s+unambiguous exact-ID mapping)", contract)
    assert re.search(r"(?is)(?:Effective effort or context may honestly be unavailable|effort and context may be honestly unavailable)", contract)
    assert re.search(r"(?is)(?:never become resolved or readback evidence|requested values never become readback)", contract)
    assert "stop before spawn" in contract
    assert re.search(r"(?is)inject.{0,80}exact (?:requested|resolved) model and effort", contract)
    _assert_effort_resolution_boundary(contract)
    assert not re.search(r"(?m)^\s*model\s*=", text)
    assert not re.search(r"(?m)^\s*model_reasoning_effort\s*=", text)


def _assert_research_dispatch_boundary(text: str) -> None:
    assert "conductor-supplied certified" in text
    assert "RuntimeAssignment" in text
    assert re.search(r"(?is)resolution_state.{0,80}(?:must (?:equal|be)|only).{0,20}`?resolved`?", text)
    assert re.search(r"(?is)(?:requested|inherited|unresolved).{0,240}(?:stop|SeedProposal)", text)
    assert re.search(r"(?is)(?:inject|injected).{0,160}(?:model|effort)", text)
    assert re.search(r"(?is)(?:immutable|unavailable|readback).{0,240}(?:provider|model|effort|context)", text)
    assert not re.search(r"(?is)prompt prose.{0,80}(?:enforces|guarantees|sets).{0,40}(?:model|effort)", text)


def _assert_research_director_authority(text: str) -> None:
    assert "Research Director is Seeds-read-only" in text
    assert "Do not create, claim, update, close, sync, or disposition Seeds" in text
    assert text.count("SeedProposal {") == 1
    assert not re.search(r"(?is)Research Director.{0,120}(?:may|can|must|should).{0,80}(?:create|claim|update|close|sync|disposition).{0,80}Seeds?", text)


def _assert_persistent_mutation_guard(text: str) -> None:
    for match in re.finditer(
        r"(?im)^.*(?:mise\s+trust|~[/\\]\.codex[/\\]config\.toml|settings\.json|shell\s+alias|credential(?:s)?\s+(?:write|store|mutation|change)).*$",
        text,
    ):
        line = match.group(0)
        window = text[max(0, match.start() - 280) : match.end() + 280]
        if "mise --no-config" in line or re.search(r"(?i)mise trust\s+is\s+not", line):
            continue
        assert re.search(r"(?i)(?:explicit|operation-specific).{0,80}(?:approval|authorization)", window), line


def _assert_historical_evidence(text: str) -> None:
    for value in (
        "80 task-local passes",
        "10 harness-inconclusive cells",
        "0 observed task-local model failures",
        "not a total ranking",
        "not production proof",
        "provisional and requested-only",
        "does not prove compaction or context handling occurred",
        "Exact Claude `[1m]` forms\nwere not separately certified",
        "2026-07-05",
        "account-, region-,\nprovider-, and date-specific",
        "`gpt-5.6-sol` → `gpt-5.5` → `gpt-5.4`",
        "`gpt-5.6-terra` → `gpt-5.5` → `gpt-5.4`",
        "`gpt-5.6-luna` → `gpt-5.4-mini` → `gpt-5.3-codex-spark`",
        "61 agents / 9.05M subagent tokens / 2h12m",
        "wf_497ea95a-e7f",
        "dcperf-automation",
        "6-dimension review + adversarial verification",
        "Historical rejected alias evidence",
    ):
        assert value in text, value
    quota_header, quota_rows = _table(text, "## Quota and concurrency evidence")
    assert quota_header == (
        "Historical Claude lane",
        "Cross-region TPM",
        "Global cross-region TPM",
        "Global CRIS tokens/day",
        "Invocation tokens/day",
        "RPM",
        "Historical fully-gated concurrency",
    )
    quota_by_name = {row[0]: row for row in quota_rows}
    assert "Haiku 4.5" in quota_by_name
    assert quota_by_name["Haiku 4.5"] == (
        "Haiku 4.5",
        "5M",
        "5M",
        "7.2B",
        "3.6B",
        "10K",
        "~20–50 heavy agents",
    )
    assert quota_by_name["Fable 5"][-1] == "1, maybe 2 bounded agents"
    assert "mandatory provider_data_share retention" in text
    assert "stricter refusal/safety behavior" in text
    assert "day-one capacity can flap independently of quota" in text or re.search(
        r"(?is)day-one\s+capacity.{0,80}independently of quota", text
    )
    assert "not deterministic receipts" in text
    for alias in (
        "`global.anthropic.claude-fable-5`",
        "`us.anthropic.claude-opus-4-8`",
        "`global.anthropic.claude-sonnet-5`",
    ):
        assert alias in text
    assert re.search(r"(?is)requested.{0,240}(?:resolved|effective) effort", text)
    assert re.search(r"(?is)(?:resolved|effective) effort.{0,100}(?:unknown|unavailable|not exposed)", text)
    assert re.search(r"(?is)\[1m\].{0,240}(?:does not|not).{0,100}(?:1M|context|intelligence)", text)


class ModelTierRightsizingTests(unittest.TestCase):
    def test_canonical_operational_matrices_allocate_pairs_with_selection_conditions(self) -> None:
        _assert_calibration(CALIBRATION.read_text(encoding="utf-8"))

    def test_router_and_flagship_are_single_authority_handoffs(self) -> None:
        router = ROUTER.read_text(encoding="utf-8")
        flagship = FLAGSHIP.read_text(encoding="utf-8")
        self.assertEqual(router.count("](references/model-routing-calibration.md)"), 1)
        self.assertIn("same class and\ncontrol predicate", router)
        self.assertIn("does not restate a routing matrix", flagship)
        self.assertIn("Sol/Fable, Terra/Opus, and Luna/Sonnet", flagship)
        self.assertNotIn("| Consequence lane | Exact model ID |", flagship)
        self.assertIn("certified bounded frontier/adversarial", router)
        self.assertIn("stops or reduces scope", router)
        _assert_no_unsafe_operational_prose(router)

    def test_canonical_evidence_boundaries_historical_aliases_and_quota_history_remain_explicit(self) -> None:
        _assert_historical_evidence(CALIBRATION.read_text(encoding="utf-8"))

    def test_dispatching_consumers_require_injected_certified_ids(self) -> None:
        for path in CONSUMERS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(consumer=path):
                self.assertRegex(text, r"(?is)certified\s+exact\s+model\s+ID")
                self.assertRegex(text, r"(?is)stop.{0,100}(?:dispatch|delegat)")
        self.assertIn("model-tier-rightsizing", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("model-routing", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_policy_surfaces_reject_unsafe_operational_aliases_and_authority_grants(self) -> None:
        for path in POLICY_SURFACES:
            text = path.read_text(encoding="utf-8")
            with self.subTest(surface=path):
                if path == CALIBRATION:
                    _assert_no_unsafe_executable_aliases(_operational_cells(text))
                else:
                    _assert_no_unsafe_operational_prose(text)
                _assert_context_claims(text)
                _assert_effort_resolution_boundary(text)
                self.assertNotRegex(
                    text,
                    r"(?i)(?:`)?(?:gpt-5\.6-(?:sol|terra|luna)|claude-(?:fable-5|opus-4-8|sonnet-5))(?:`)?\s+(?:owns?|decides?|authori[sz]\w*|mutat\w*)\s+(?:Seeds|the queue|fan-in|outward)",
                )
                self.assertNotRegex(text, r"(?im)^\s*(?:edit|change|mutate|write)\s+(?:user )?(?:settings|trust)\b")

    def test_all_global_role_manifests_require_one_runtime_assignment_contract(self) -> None:
        self.assertEqual(len(GLOBAL_ROLE_SURFACES), 14)
        for path in GLOBAL_ROLE_SURFACES:
            with self.subTest(role_surface=path):
                _assert_global_runtime_role_contract(path.read_text(encoding="utf-8"))

    def test_global_runtime_consumers_share_role_evidence_semantics(self) -> None:
        for path in GLOBAL_RUNTIME_CONSUMERS:
            with self.subTest(consumer=path):
                _assert_global_runtime_consumer_contract(path.read_text(encoding="utf-8"))

    def test_global_role_manifest_model_and_effort_mutants_fail(self) -> None:
        claude = (ROOT / "agents" / "claude" / "sdlc-reviewer.md").read_text(encoding="utf-8")
        codex = (ROOT / "agents" / "codex" / "sdlc-reviewer.toml").read_text(encoding="utf-8")
        mutants = {
            "valid quoted Claude YAML model": claude.replace(
                "name: sdlc-reviewer", 'name: sdlc-reviewer\nmodel: "claude-sonnet-5"', 1
            ),
            "Codex TOML model": codex.replace('sandbox_mode = "', 'model = "gpt-5.6-luna"\nsandbox_mode = "', 1),
            "Codex TOML effort": codex.replace(
                'sandbox_mode = "', 'model_reasoning_effort = "high"\nsandbox_mode = "', 1
            ),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                with self.assertRaises(AssertionError):
                    _assert_global_runtime_role_contract(mutant)

    def test_runtime_assignment_allows_unavailable_effort_and_context_readback_without_overclaim(self) -> None:
        role = (ROOT / "agents" / "codex" / "sdlc-reviewer.toml").read_text(encoding="utf-8")
        _assert_global_runtime_role_contract(role)
        self.assertIn("effort_readback_status: verified or unavailable", role)
        self.assertIn("context_readback_status: verified or unavailable", role)
        self.assertNotRegex(role, r"(?is)requested_effort.{0,160}resolved_effort")
        self.assertNotRegex(role, r"(?is)requested_context_form.{0,160}resolved_context_form")

    def test_runtime_contract_preserves_all_six_exact_bare_ids_and_four_tiers(self) -> None:
        calibration = CALIBRATION.read_text(encoding="utf-8")
        operational = _operational_cells(calibration)
        observed = set(re.findall(r"`((?:gpt|claude)-[^`]+)`", operational))
        self.assertEqual(observed & ALLOWED_EXACT_MODEL_IDS, ALLOWED_EXACT_MODEL_IDS)
        for tier in ("Frontier", "Judgment workhorse", "Capable volume", "Mechanical floor"):
            self.assertIn(tier, operational)

    def test_all_research_role_manifests_and_generator_require_runtime_assignment(self) -> None:
        role_surfaces = tuple(sorted((ROOT / "agents" / "codex" / "research").glob("*.toml")))
        generator = ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
        operating_model = ROOT / "skills" / "codex-research-os" / "references" / "operating-model.md"
        self.assertEqual(len(role_surfaces), 17)
        for path in role_surfaces + (generator, operating_model):
            with self.subTest(role_surface=path):
                _assert_research_runtime_role_contract(path.read_text(encoding="utf-8"))

    def test_research_consumers_define_certified_spawn_boundary(self) -> None:
        for path in RESEARCH_CONSUMERS:
            with self.subTest(consumer=path):
                _assert_research_dispatch_boundary(path.read_text(encoding="utf-8"))

    def test_research_director_is_seeds_read_only_and_emits_one_typed_proposal(self) -> None:
        director = ROOT / "agents" / "codex" / "research" / "research_director.toml"
        generator = ROOT / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
        for path in (director, generator):
            text = path.read_text(encoding="utf-8")
            with self.subTest(surface=path):
                self.assertIn("Research Director is Seeds-read-only", text)
                self.assertIn("Seeds(<target>, prime)", text)
                self.assertIn("Seeds(<target>, ready --format json)", text)
                self.assertIn("Seeds(<target>, blocked --format json)", text)
                self.assertIn("MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec", text)
                self.assertIn("node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sd <args>", text)
                self.assertIn("Do not create, claim, update, close, sync, or disposition Seeds", text)
                self.assertIn("exactly one typed `SeedProposal {", text)
                for forbidden in (
                    "sd create",
                    "sd update",
                    "sd close",
                    "sd sync",
                    "Seeds(<target>, create",
                    "Seeds(<target>, update",
                    "Seeds(<target>, close",
                    "Seeds(<target>, sync",
                ):
                    self.assertNotIn(forbidden, text)
                if path == director:
                    _assert_research_director_authority(text)

    def test_runtime_assignment_and_director_authority_mutants_fail(self) -> None:
        role = (ROOT / "agents" / "codex" / "research" / "experimentalist.toml").read_text(encoding="utf-8")
        director = (ROOT / "agents" / "codex" / "research" / "research_director.toml").read_text(encoding="utf-8")
        runtime_mutations = {
            "provider removal": role.replace("- resolved_provider:", "- omitted_provider:", 1),
            "requested dispatch": role.replace("resolution_state must equal resolved", "resolution_state may equal requested", 1),
            "immutable injection removal": role.replace("Exact model and effort request injection is mandatory and immutable", "Request injection is optional", 1),
            "static model": role.replace('sandbox_mode = "', 'model = "gpt-5.6-terra"\nsandbox_mode = "', 1),
            "static effort": role.replace('sandbox_mode = "', 'model_reasoning_effort = "high"\nsandbox_mode = "', 1),
        }
        for name, mutation in runtime_mutations.items():
            with self.subTest(runtime_mutation=name):
                with self.assertRaises(AssertionError):
                    _assert_research_runtime_role_contract(mutation)

        authority_mutations = {
            "create grant": director + "\nThe Research Director may create Seeds.\n",
            "claim grant": director + "\nThe Research Director may claim Seeds.\n",
            "update grant": director + "\nThe Research Director may update Seeds.\n",
            "close grant": director + "\nThe Research Director may close Seeds.\n",
            "sync grant": director + "\nThe Research Director may sync Seeds.\n",
            "disposition grant": director + "\nThe Research Director may disposition Seeds.\n",
        }
        for name, mutation in authority_mutations.items():
            with self.subTest(authority_mutation=name):
                with self.assertRaises(AssertionError):
                    _assert_research_director_authority(mutation)

    def test_persistent_trust_config_alias_and_credentials_require_operation_specific_approval(self) -> None:
        guidance = (
            ROOT / "README.md",
            ROOT / "commands" / "sdlc-init.md",
            ROOT / "commands" / "sdlc-wave.md",
            ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "seeds-worktrees.md",
        )
        for path in guidance:
            with self.subTest(guidance=path):
                _assert_persistent_mutation_guard(path.read_text(encoding="utf-8"))

    def test_process_scoped_no_config_gate_remains_allowed(self) -> None:
        _assert_persistent_mutation_guard(
            "For a process-scoped test run, use `mise --no-config --cd <target> exec ...`; "
            "this does not persist trust."
        )

    def test_canonical_links_resolve_and_no_second_active_matrix_exists(self) -> None:
        for source in (ROUTER, FLAGSHIP):
            text = source.read_text(encoding="utf-8")
            links = re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]*)?\)", text)
            self.assertTrue(links, source)
            for target in links:
                with self.subTest(source=source, target=target):
                    self.assertTrue((source.parent / target).resolve().is_file())
        for path in ROOT.rglob("*.md"):
            if path == CALIBRATION:
                continue
            with self.subTest(path=path):
                self.assertNotIn("| Consequence lane | Exact model ID |", path.read_text(encoding="utf-8"))

    def test_mutations_fail_for_primary_allocation_fable_constraints_and_history(self) -> None:
        original = CALIBRATION.read_text(encoding="utf-8")
        mutations = {
            "GPT-primary monoculture": original.replace(
                "`gpt-5.6-sol` or `claude-fable-5`", "`gpt-5.6-sol`", 1
            ),
            "provider family removal": original.replace(
                "`gpt-5.6-terra` or `claude-opus-4-8`", "`gpt-5.6-terra`", 1
            ),
            "row swap": original.replace(
                "| Derail / settled truth | `gpt-5.6-sol` or `claude-fable-5`",
                "| TEMP | `gpt-5.6-sol` or `claude-fable-5`",
                1,
            ).replace(
                "| Contained silent-degrade | `gpt-5.6-terra` or `claude-opus-4-8`",
                "| Derail / settled truth | `gpt-5.6-terra` or `claude-opus-4-8`",
                1,
            ).replace(
                "| TEMP | `gpt-5.6-sol` or `claude-fable-5`",
                "| Contained silent-degrade | `gpt-5.6-sol` or `claude-fable-5`",
                1,
            ),
            "Fable settles truth": original.replace(
                FABLE_BOUNDARY,
                "Fable may settle truth without a certified peer.",
                1,
            ),
            "Haiku quota history deletion": original.replace(
                "| Haiku 4.5 | 5M | 5M | 7.2B | 3.6B | 10K | ~20–50 heavy agents |\n", "", 1
            ),
            "legacy receipt identity deletion": original.replace("wf_497ea95a-e7f", "redacted", 1),
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / CALIBRATION.name
            for name, mutation in mutations.items():
                with self.subTest(mutation=name):
                    target.write_text(mutation, encoding="utf-8")
                    with self.assertRaises(AssertionError):
                        if name in {"Haiku quota history deletion", "legacy receipt identity deletion"}:
                            _assert_historical_evidence(target.read_text(encoding="utf-8"))
                        else:
                            _assert_calibration(target.read_text(encoding="utf-8"))

    def test_semantic_mutants_fail_for_pair_choice_frontier_and_telemetry_claims(self) -> None:
        original = CALIBRATION.read_text(encoding="utf-8")
        frontier_choice = (
            "Choose Sol when it must form the advisory frame or settled-truth derivation; "
            "choose Fable only when it is the certified bounded adversarial packet and Sol remains the peer."
        )
        runtime_contract = "\n".join(
            f"{field}: unknown" for field in RUNTIME_ASSIGNMENT_FIELDS
        ) + "\ninherited\nunresolved\n"
        mutations = {
            "GPT-only selection condition": (
                _assert_calibration,
                original.replace(
                    frontier_choice,
                    "Choose GPT for every dispatch; Claude is documentary only and is never selected.",
                    1,
                ),
            ),
            "Fable settles truth and makes Sol optional": (
                _assert_calibration,
                original.replace(
                    "it never settles truth or replaces the Sol peer.",
                    "it may settle truth and makes Sol optional after success.",
                    1,
                ),
            ),
            "[1m] expands the upstream context window": (
                _assert_context_claims,
                "[1m] expands a larger upstream context window after dispatch.",
            ),
            "requested effort becomes upstream effort": (
                _assert_research_runtime_role_contract,
                runtime_contract
                + "Requested effort guarantees resolved effort after successful dispatch.",
            ),
        }
        for name, (assertion, text) in mutations.items():
            with self.subTest(mutation=name):
                with self.assertRaises(AssertionError):
                    assertion(text)

    def test_all_executable_alias_forms_fail_while_historical_rejection_examples_remain_allowed(self) -> None:
        for alias in ("fable", "opus", "sonnet", "haiku"):
            for expression in (
                f"model: '{alias}'",
                f'model = "{alias}"',
                f"model {alias}",
                f'{{"model":"{alias}"}}',
                f"{{'model':'{alias}'}}",
            ):
                with self.subTest(expression=expression):
                    with self.assertRaises(AssertionError):
                        _assert_no_unsafe_executable_aliases(expression)
        for expression in (
            "model: 'global.anthropic.claude-fable-5'",
            'model = "us.anthropic.claude-opus-4-8"',
            "model global.anthropic.claude-sonnet-5",
            "model: 'ap.anthropic.claude-haiku-4-5'",
            '{"model":"global.anthropic.claude-fable-5"}',
            "{'model':'us.anthropic.claude-opus-4-8'}",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(AssertionError):
                    _assert_no_unsafe_executable_aliases(expression)
        text = CALIBRATION.read_text(encoding="utf-8")
        self.assertIn("### Historical rejected alias evidence", text)
        self.assertIn("`global.anthropic.claude-fable-5`", text)
        _assert_no_unsafe_executable_aliases(_operational_cells(text))

    def test_policy_mutation_helpers_reject_new_loopholes(self) -> None:
        mutations = {
            "host default policy": (
                _assert_no_unsafe_operational_prose,
                "Let the host default model selection decide each worker.",
            ),
            "static effort pin": (
                _assert_research_runtime_role_contract,
                "\n".join(f"{field}: unknown" for field in RUNTIME_ASSIGNMENT_FIELDS)
                + "\nresolution_state: inherited|unresolved\nmodel_reasoning_effort = 'high'\n",
            ),
            "context intelligence overclaim": (
                _assert_context_claims,
                "Use [1m] because it guarantees a 1M upstream capacity and more intelligence.",
            ),
            "persistent trust without approval": (
                _assert_persistent_mutation_guard,
                "Run mise trust /repo/mise.toml before dispatch.",
            ),
            "persistent config without approval": (
                _assert_persistent_mutation_guard,
                "Add the repository to ~/.codex/config.toml before dispatch.",
            ),
        }
        for name, (assertion, text) in mutations.items():
            with self.subTest(mutation=name):
                with self.assertRaises(AssertionError):
                    assertion(text)


if __name__ == "__main__":
    unittest.main()
