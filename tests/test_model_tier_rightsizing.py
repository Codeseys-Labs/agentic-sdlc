from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTER = ROOT / "skills" / "model-tier-rightsizing" / "SKILL.md"
CALIBRATION = ROUTER.parent / "references" / "model-routing-calibration.md"
FLAGSHIP = ROOT / "skills" / "agentic-sdlc-orchestrator" / "references" / "tiered-orchestration.md"

DISPATCH_HEADER = (
    "Consequence lane",
    "Exact model ID",
    "Requested effort",
    "Complement",
    "Required gate or control",
)
DISPATCH_ROWS = (
    (
        "Derail / settled truth",
        "`gpt-5.6-sol`",
        "`high`, `xhigh`",
        "`claude-fable-5` at `max` searches a bounded assumptions packet",
        "Re-derivation; conductor adjudicates the advisory recommendation",
    ),
    (
        "Contained silent-degrade",
        "`gpt-5.6-terra`",
        "`xhigh`, `max`",
        "`claude-opus-4-8` at `high`, `xhigh` reviews an immutable semantic delta",
        "Explicit acceptance criteria and independent review",
    ),
    (
        "Deterministic-gated volume",
        "`gpt-5.6-luna`",
        "`high`, `xhigh`",
        "`claude-sonnet-5` at `high`, `xhigh` checks stable evidence",
        "Compiler, tests, schema, diff, or deterministic verifier",
    ),
    (
        "Bounded adversarial specialist",
        "`claude-fable-5`",
        "`max`",
        "`gpt-5.6-sol` at `xhigh` receives the counterexample artifact",
        "Bounded packet; advisory analysis only; conductor adjudicates",
    ),
    (
        "Semantic-review specialist",
        "`claude-opus-4-8`",
        "`high`, `xhigh`",
        "`gpt-5.6-terra` at `xhigh`, `max` reproduces the candidate",
        "Immutable candidate and named acceptance criteria",
    ),
    (
        "Gated-verification specialist",
        "`claude-sonnet-5`",
        "`high`, `xhigh`",
        "`gpt-5.6-luna` at `high`, `xhigh` produces deterministic receipts",
        "Same deterministic gate remains required",
    ),
)

ROADMAP_HEADER = (
    "Roadmap lane",
    "Primary exact model ID",
    "Requested effort and context",
    "Complementary assignment",
    "Gate or escalation",
)
ROADMAP_ROWS = (
    ("S1 Seeds toolchain retention", "`gpt-5.6-luna`", "`high`", "`claude-sonnet-5` at `high` checks evidence-to-claim coverage", "`gpt-5.6-terra` at `xhigh` analyzes semantic drift and recommends disposition"),
    ("S2 Seeds execution contract", "`gpt-5.6-terra`", "`xhigh`", "`gpt-5.6-sol` at `xhigh` analyzes queue evidence; `claude-opus-4-8` at `xhigh` reviews stable diff", "Null or mismatch fails closed; conductor adjudicates Seeds action"),
    ("Seeds fan-in", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-luna` at `high` re-gates exact ranges", "Authorized integrator only; `gpt-5.6-sol` at `xhigh` analyzes stop/go ambiguity for conductor adjudication"),
    ("Wave 1 CAO deletion", "`gpt-5.6-terra`", "`xhigh`", "`gpt-5.6-luna` at `high` inventories residues; `claude-opus-4-8` at `high` reviews removed surface", "Any shipped or runtime residue blocks"),
    ("Wave 2 state-v3 identity cutover", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes migration invariants; `gpt-5.6-luna` at `xhigh` runs crash matrix; `claude-opus-4-8` at `xhigh` reviews recovery", "Fail closed on foreign ownership; conductor adjudicates"),
    ("Claude marketplace/plugin plane", "`gpt-5.6-terra`", "`xhigh`", "`claude-opus-4-8` at `xhigh` checks supported-operation boundary", "Never edit opaque state"),
    ("Local checkout rename gate", "`gpt-5.6-sol`", "`xhigh`", "`gpt-5.6-luna` at `high` verifies pre/post receipts", "Human approval before mutation"),
    ("GitHub repository rename gate", "`gpt-5.6-sol`", "`xhigh`", "`claude-sonnet-5` at `high` inventories post-authorization evidence", "Human approval; model never authorizes"),
    ("A1 change-writing", "`gpt-5.6-terra`", "`xhigh`", "`claude-opus-4-8` at `high` reviews evidence and attribution; `gpt-5.6-luna` at `high` builds fixtures", "Output-only contract"),
    ("A2 Git-default sdlc-init", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes defaults and refusals; `claude-opus-4-8` at `xhigh` reviews safety; `gpt-5.6-luna` at `high` builds fixtures", "Dry-run and no-write cancellation"),
    ("A3 hierarchical instructions", "`gpt-5.6-terra`", "`xhigh`", "`claude-sonnet-5` at `high` checks conformance; `claude-opus-4-8` at `high` reviews markers and ownership", "Preserve foreign prose"),
    ("R1 shared role contracts", "`gpt-5.6-terra`", "`xhigh`", "`gpt-5.6-sol` at `xhigh` analyzes separation of powers; `claude-fable-5` at `max` attacks authority packet; `gpt-5.6-luna` at `high` projects fixtures", "All analysis advisory; conductor adjudicates"),
    ("R2 bounded Deep Work Loop", "`gpt-5.6-terra`", "`xhigh`", "`gpt-5.6-sol` at `xhigh` analyzes bounds and backflow; `claude-opus-4-8` at `xhigh` reviews recursion; `gpt-5.6-luna` at `high` tests", "No second queue or unbounded recursion"),
    ("R3 HyperResearch/Research OS", "`gpt-5.6-terra`", "`max`", "`claude-sonnet-5` extracts evidence; `claude-opus-4-8` reviews crash recovery; `gpt-5.6-sol` analyzes load-bearing unknowns", "Typed `SeedProposal`; conductor alone mutates Seeds"),
    ("G1 Git change-flow family", "`gpt-5.6-terra`", "`xhigh`", "`claude-opus-4-8` at `xhigh` reviews rebase, squash, and stack; `gpt-5.6-luna` at `high` builds fixtures", "Stable commit and merge-base evidence"),
    ("G2 toolchain/security", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes trust evidence; `claude-opus-4-8` reviews semantic security; `gpt-5.6-luna` tests falsifiability", "Exact gate argv, status, and log digest"),
    ("J1 jj certification", "`gpt-5.6-terra`", "`[1m]` at `xhigh`", "`gpt-5.6-sol` at `[1m]`, `xhigh` analyzes framing; `gpt-5.6-luna` at `high` builds fixture matrix; `claude-fable-5` at `max` attacks data-loss assumptions", "Official docs and immutable Git handoff; conductor adjudicates"),
    ("J2 jj implementation", "`gpt-5.6-terra`", "`max`", "`claude-opus-4-8` at `xhigh` reviews handoff and recovery; `gpt-5.6-luna` at `xhigh` builds fixtures", "Conflict-free exact Git OID"),
    ("A2j jj init amendment", "`gpt-5.6-terra`", "`xhigh`", "`claude-sonnet-5` at `high` checks explicit selection and receipt", "Only after J1/J2 certification"),
    ("M0a Mermaid browser ADR/spike", "`gpt-5.6-terra`", "`[1m]` at `xhigh`", "`gpt-5.6-sol` at `xhigh` analyzes dependency evidence; `claude-opus-4-8` reviews browser dependency; `gpt-5.6-luna` builds host/offline matrix", "Stop before M1 without portable provider; conductor adjudicates"),
    ("M0b Mermaid security foundation", "`gpt-5.6-terra`", "`max`", "`claude-opus-4-8` at `xhigh` reviews malicious SVG; `gpt-5.6-luna` builds parser/render matrix", "Strict allowlist and bounded resources"),
    ("M1 structural Mermaid skills", "`gpt-5.6-luna`", "`xhigh`", "`claude-sonnet-5` at `high` checks docs, citations, and fixtures", "One writer and pipeline reviewer"),
    ("M2 planning Mermaid skills", "`gpt-5.6-luna`", "`xhigh`", "`claude-sonnet-5` at `high` checks docs, citations, and fixtures", "One writer and pipeline reviewer"),
    ("M3 quantitative Mermaid skills", "`gpt-5.6-luna`", "`xhigh`", "`claude-sonnet-5` at `high` checks docs, citations, and fixtures", "One writer and pipeline reviewer"),
    ("M4 technical Mermaid skills", "`gpt-5.6-luna`", "`xhigh`", "`claude-sonnet-5` at `high` checks docs, citations, and fixtures", "One writer and pipeline reviewer"),
    ("M5 conceptual Mermaid skills", "`gpt-5.6-luna`", "`xhigh`", "`claude-sonnet-5` at `high` checks docs, citations, and fixtures", "One writer and pipeline reviewer"),
    ("M6 Mermaid router", "`gpt-5.6-terra`", "`xhigh`", "`claude-sonnet-5` at `high` inventories exact-one routing", "Reject unsupported or ambiguous requests"),
    ("M7 Mermaid conformance", "`gpt-5.6-luna`", "`xhigh`", "`claude-opus-4-8` reviews malicious output semantics; `gpt-5.6-sol` at `high` analyzes final evidence", "Exactly one router plus 30 skills; conductor adjudicates"),
    ("Release hardening", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-luna` builds cross-platform fixtures; `claude-opus-4-8` reviews semantics; `gpt-5.6-sol` recommends promotion", "Publication separately authorized by humans"),
    ("Evolutionary Core M2", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes kernel contracts; `gpt-5.6-luna` runs crash suite; `claude-opus-4-8` reviews immutable candidate", "Deterministic receipt and idempotent reconcile"),
    ("Claude Golden Wave M3", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes adapter and authority contract; `claude-opus-4-8` reviews semantics; `claude-sonnet-5` checks conformance; `claude-fable-5` attacks bounded assumptions", "Exact Claude ID, effort, and context readback"),
    ("Portability M4", "`gpt-5.6-terra`", "`max`", "`gpt-5.6-sol` at `xhigh` analyzes portability evidence; `gpt-5.6-luna` runs common fault suite; `claude-opus-4-8` reviews assumptions; `claude-sonnet-5` checks conformance", "No public ABI before three adapters"),
    ("CCP/ccodex certification", "`gpt-5.6-terra`", "`[1m]` at `max`", "`gpt-5.6-sol` at `xhigh` analyzes package evidence; `gpt-5.6-luna` checks lifecycle; `claude-fable-5` attacks credential assumptions; `claude-opus-4-8` reviews implementation", "Exact version, checksum, and readback"),
    ("Final family wiring", "`gpt-5.6-terra`", "`xhigh`", "`claude-sonnet-5` at `high` verifies cross-links and inventory", "No unrelated family co-mingling"),
)

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
        "## Exact dispatch and requested effort",
        "## Blast-radius production routing",
        "## Agentic SDLC phase routing",
        "## Approved roadmap family lanes",
    )
    return "\n".join(" | ".join(cell for row in (_table(text, heading)[1],) for cells in row for cell in cells) for heading in headings)


def _assert_authority(text: str) -> None:
    assert "The conductor alone\nadjudicates and mutates Seeds; only an authorized integrator performs an already-authorized\nfan-in; humans authorize outward actions." in text
    assert not re.search(
        r"(?i)(?:`)?(?:gpt-5\.6-(?:sol|terra|luna)|claude-(?:fable-5|opus-4-8|sonnet-5))(?:`)?\s+(?:owns?|decides?|authori[sz]\w*|mutat\w*)\s+(?:Seeds|the queue|fan-in|outward)",
        text,
    )
    assert not re.search(r"(?im)^\s*(?:edit|change|mutate|write)\s+(?:user )?(?:settings|trust)\b", text)


def _assert_calibration(text: str) -> None:
    assert _table(text, "## Exact dispatch and requested effort") == (DISPATCH_HEADER, DISPATCH_ROWS)
    assert _table(text, "## Approved roadmap family lanes") == (ROADMAP_HEADER, ROADMAP_ROWS)
    operational = _operational_cells(text)
    assert not re.search(r"(?i)\b(?:global|us|eu|ap)\.anthropic\.claude-[\w.-]+\b", operational)
    assert "same deterministic gate remains" in text.lower()
    assert "immutable candidate and explicit acceptance criteria" in text.lower()
    assert "If no certified route exists, fail closed" in text
    _assert_authority(text)


class ModelTierRightsizingTests(unittest.TestCase):
    def test_exact_structural_dispatch_and_roadmap_tuples(self) -> None:
        _assert_calibration(CALIBRATION.read_text(encoding="utf-8"))

    def test_router_and_flagship_are_single_authority_handoffs(self) -> None:
        router = ROUTER.read_text(encoding="utf-8")
        flagship = FLAGSHIP.read_text(encoding="utf-8")
        self.assertEqual(router.count("](references/model-routing-calibration.md)"), 1)
        self.assertIn("same class and\ncontrol predicate", router)
        self.assertIn("does not restate a routing matrix", flagship)
        self.assertNotRegex(flagship, r"(?i)\b(?:Fable|Opus|Sonnet|Sol|Terra|Luna)\b")

    def test_canonical_evidence_boundaries_and_historical_aliases_remain_explicit(self) -> None:
        text = CALIBRATION.read_text(encoding="utf-8")
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
        ):
            self.assertIn(value, text)
        for alias in (
            "`global.anthropic.claude-fable-5`",
            "`us.anthropic.claude-opus-4-8`",
            "`global.anthropic.claude-sonnet-5`",
        ):
            self.assertIn(alias, text)
        self.assertRegex(text, r"(?is)requested effort.{0,240}resolved effort")
        self.assertRegex(text, r"(?is)resolved effort.{0,100}(?:unknown|unavailable|not exposed)")
        self.assertRegex(text, r"(?is)\[1m\].{0,240}(?:does not|not).{0,100}(?:1M|context|intelligence)")

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
                if path != CALIBRATION:
                    self.assertNotRegex(text, r"(?i)\b(?:global|us|eu|ap)\.anthropic\.claude-[\w.-]+\b")
                self.assertNotRegex(
                    text,
                    r"(?i)(?:`)?(?:gpt-5\.6-(?:sol|terra|luna)|claude-(?:fable-5|opus-4-8|sonnet-5))(?:`)?\s+(?:owns?|decides?|authori[sz]\w*|mutat\w*)\s+(?:Seeds|the queue|fan-in|outward)",
                )
                self.assertNotRegex(text, r"(?im)^\s*(?:edit|change|mutate|write)\s+(?:user )?(?:settings|trust)\b")

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

    def test_mutations_fail_from_temporary_copies(self) -> None:
        original = CALIBRATION.read_text(encoding="utf-8")
        mutations = {
            "swapped dispatch rows": original.replace(
                "| Derail / settled truth | `gpt-5.6-sol`", "| TEMP | `gpt-5.6-sol`", 1
            ).replace(
                "| Contained silent-degrade | `gpt-5.6-terra`", "| Derail / settled truth | `gpt-5.6-terra`", 1
            ).replace("| TEMP | `gpt-5.6-sol`", "| Contained silent-degrade | `gpt-5.6-sol`", 1),
            "swapped roadmap rows": original.replace(
                "| S1 Seeds toolchain retention | `gpt-5.6-luna`", "| TEMP | `gpt-5.6-luna`", 1
            ).replace(
                "| S2 Seeds execution contract | `gpt-5.6-terra`", "| S1 Seeds toolchain retention | `gpt-5.6-terra`", 1
            ).replace("| TEMP | `gpt-5.6-luna`", "| S2 Seeds execution contract | `gpt-5.6-luna`", 1),
            "unsafe operational alias": original.replace("`gpt-5.6-sol`", "`global.anthropic.claude-fable-5`", 1),
            "malformed table": original.replace("| Derail / settled truth | `gpt-5.6-sol`", "| Derail / settled truth | `gpt-5.6-sol`", 1).replace("recommendation |\n", "recommendation \n", 1),
            "model-owned authority": original + "\n`gpt-5.6-sol` authorizes Seeds.\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / CALIBRATION.name
            for name, mutation in mutations.items():
                with self.subTest(mutation=name):
                    target.write_text(mutation, encoding="utf-8")
                    with self.assertRaises(AssertionError):
                        _assert_calibration(target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
