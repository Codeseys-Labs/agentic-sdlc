"""Pin the per-model context-window table against the numbers and doctrine it claims.

The table in the calibration is the sole owner of the per-model windows (ADR-0012 Decision
item 4), so nothing in the repository can be diffed against it to prove it correct. What CAN
be pinned mechanically is that the table does not contradict itself, does not contradict the
conservative default it recommends, and keeps the requested-versus-readback boundary that the
rest of the calibration already enforces for effort.

The load-bearing checks here are the ones that would catch a plausible future edit:

- a window silently inferred for a model the research recorded as unknown;
- the shared-pool model losing its shared marking, which is the one hazard a single number
  per model cannot express;
- the conservative default drifting above the smallest window it must protect (ADR-0012
  Decision item 2), which is the failure direction that puts the compaction net behind a real
  limit; and
- the requested context form being upgraded into proof of a served window.

The published-window numbers themselves are provider facts and are not asserted here beyond
internal consistency: asserting them would pin this suite to a vendor catalog that moves.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CALIBRATION = ROOT / "skills" / "model-tier-rightsizing" / "references" / "model-routing-calibration.md"
FLAGSHIP = ROOT / "skills" / "agentic-sdlc" / "references" / "tiered-orchestration.md"
ROUTER = ROOT / "skills" / "model-tier-rightsizing" / "SKILL.md"
RESEARCH = ROOT / "docs" / "research" / "2026-08-07-context-window-accommodation.md"
ADR = ROOT / "docs" / "adr" / "0012-context-window-accommodation.md"
MUSE_RESEARCH = ROOT / "docs" / "research" / "2026-08-07-muse-spark-qualification.md"

WINDOWS_HEADING = "### Per-model windows and their shared-versus-separate shape"

# The measured shared pool, from the muse qualification memo section 5.8. Exactly 2**20.
MEASURED_SHARED_WINDOW = 1_048_576

# Models the research recorded as having NO gateway-computed window. A future edit that
# invents one of these numbers is the specific regression this guards.
GATEWAY_UNKNOWN = ("gpt-5.4-mini", "muse-spark-1.2", "muse-spark-1.2-contributor", "muse-spark-1.1")

# Models whose provider window is a single shared input+output pool rather than separate
# reservations. Losing this marking is a silent correctness loss.
SHARED_POOL = ("muse-spark-1.2", "muse-spark-1.2-contributor")

# The smallest gateway-computed window in the served catalog. The conservative default must
# never be documented as protecting a model below the client's own clamp floor.
SMALLEST_GATEWAY_WINDOW = 100_000
CLIENT_CLAMP_FLOOR = 100_000

# The adopted session floor (ADR-0012 Decision item 2). The number is derived from the smallest
# real window among the operator's SELECTED models, so it is pinned here together with that
# smallest window: the floor may never exceed the window it claims to protect.
ADOPTED_FLOOR = 272_000
SMALLEST_SELECTED_REAL_WINDOW = 272_000

# The gateway's compiled window for the 5.6 family, rejected as the floor because it sits above
# the provider-served ceiling. Pinned so a future edit cannot quietly adopt it.
REJECTED_FLOOR = 372_000

# Deferred pending measurement (ADR-0012 Decision item 4).
DEFERRED_KNOB = "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"

# Default output ceiling for model IDs the client does not recognize (every gateway-served name).
UNRECOGNIZED_OUTPUT_DEFAULT = 32_000


def _table(text: str, heading: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Parse the pipe table immediately below a heading.

    Mirrors the parser in test_model_tier_rightsizing so a malformed table fails here the
    same way it would there.
    """
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
    assert len(lines) >= 3, f"missing table below {heading}"

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


def _rows_by_model(text: str) -> dict[str, dict[str, str]]:
    header, rows = _table(text, WINDOWS_HEADING)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        model = row[0].strip().strip("`")
        assert model, f"empty model cell in row: {row}"
        assert model not in out, f"duplicate row for {model}"
        out[model] = dict(zip(header, row))
    return out


class ContextWindowTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calibration = CALIBRATION.read_text(encoding="utf-8")
        self.rows = _rows_by_model(self.calibration)

    def test_table_carries_a_gateway_column_a_provider_column_and_a_shape_column(self) -> None:
        header, _ = _table(self.calibration, WINDOWS_HEADING)
        joined = " | ".join(header).lower()
        # A single window column per model cannot express the shared-pool hazard, which is
        # the whole reason the shape column exists.
        self.assertIn("gateway", joined)
        self.assertIn("provider", joined)
        self.assertIn("shape", joined)
        self.assertIn("source status", joined)

    def test_every_model_the_research_recorded_as_unknown_stays_unknown(self) -> None:
        for model in GATEWAY_UNKNOWN:
            self.assertIn(model, self.rows, f"{model} missing from the window table")
            gateway_cell = next(
                value for key, value in self.rows[model].items() if "gateway" in key.lower()
            )
            self.assertEqual(
                gateway_cell.lower(),
                "unknown",
                f"{model} gained a gateway window; the research recorded none. "
                "A window may not be inferred from a sibling model (ADR-0012 Decision item 6).",
            )

    def test_shared_pool_models_are_marked_shared_and_others_are_not(self) -> None:
        for model, row in self.rows.items():
            shape = next(value for key, value in row.items() if "shape" in key.lower()).lower()
            if model in SHARED_POOL:
                self.assertIn(
                    "shared",
                    shape,
                    f"{model} lost its shared input/output marking; input and output compete "
                    "there and a single number cannot express that",
                )
                self.assertNotIn("separate:", shape, f"{model} marked both shared and separate")
            elif model.startswith("gpt-") and "separate:" in shape:
                # Where a GPT row publishes both halves the arithmetic must close exactly;
                # that exactness is what proves the window is a sum, not a shared pool.
                published = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", shape)]
                self.assertEqual(len(published), 2, f"{model} separate shape needs two numbers")
                provider_cell = next(
                    value for key, value in row.items() if "provider-documented" in key.lower()
                )
                totals = {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", provider_cell)}
                self.assertIn(
                    sum(published),
                    totals,
                    f"{model}: input+output {published} does not sum to any published total "
                    f"in {provider_cell!r}",
                )

    def test_measured_shared_window_matches_the_muse_memo_exactly(self) -> None:
        # The measurement is exactly 2**20 with zero remainder; a rounded 1000000 would be a
        # different, wrong number and would also change the marking predicate's outcome.
        self.assertEqual(MEASURED_SHARED_WINDOW, 2**20)
        for model in SHARED_POOL:
            provider_cell = next(
                value for key, value in self.rows[model].items() if "provider-documented" in key.lower()
            )
            self.assertIn(str(MEASURED_SHARED_WINDOW), provider_cell, model)
            self.assertIn("measured", provider_cell.lower(), model)
        muse = MUSE_RESEARCH.read_text(encoding="utf-8")
        self.assertIn(
            str(MEASURED_SHARED_WINDOW),
            muse,
            "the calibration cites a measured window the source memo does not contain",
        )

    def test_the_conservative_default_never_claims_to_protect_below_the_clamp_floor(self) -> None:
        # ADR-0012 Decision item 2: the floor must suit the SMALLEST reachable model, and a
        # window at or below the client's clamp floor cannot be protected by it at all.
        self.assertLessEqual(SMALLEST_GATEWAY_WINDOW, CLIENT_CLAMP_FLOOR)
        for text, name in ((self.calibration, "calibration"), (RESEARCH.read_text(encoding="utf-8"), "research")):
            self.assertRegex(
                text,
                r"(?is)\bat or below\b.{0,120}\b(?:minimum\s+)?floor\b.{0,200}\bcannot be (?:matched|protected)\b",
                f"{name} lost the statement that a sub-floor window is unprotectable",
            )
            self.assertRegex(
                text,
                r"(?is)\bsmallest\b.{0,120}\bnever the largest\b",
                f"{name} lost the smallest-not-largest floor rule",
            )

    def test_adopted_floor_never_exceeds_the_smallest_window_it_protects(self) -> None:
        # The whole point of the floor is that the compaction net sits INSIDE the real ceiling.
        # A floor above the smallest selected window puts it behind that ceiling, which converts
        # a clean local compaction into provider-side truncation.
        self.assertLessEqual(
            ADOPTED_FLOOR,
            SMALLEST_SELECTED_REAL_WINDOW,
            "the floor must not exceed the smallest real window among the selected models",
        )
        self.assertLess(
            ADOPTED_FLOOR,
            REJECTED_FLOOR,
            "the rejected gateway-compiled value must remain above the adopted floor",
        )
        self.assertIn(str(ADOPTED_FLOOR), self.calibration)
        self.assertNotRegex(
            self.calibration,
            rf"(?is)adopted session floor is\D{{0,40}}{REJECTED_FLOOR}",
            "the rejected value must never become the adopted floor",
        )

    def test_calibration_records_the_derivation_rule_not_only_the_number(self) -> None:
        # The number expires when the selected model set changes; the rule is what survives.
        self.assertRegex(
            self.calibration,
            r"(?is)\bsmallest real window\b.{0,120}\bmodels\b.{0,80}\b(?:actually\s+)?selects?\b",
            "the derivation rule must be stated, or the number rots silently",
        )
        self.assertRegex(
            self.calibration,
            r"(?is)\bre-derive\b",
            "a reader must be told to re-derive when the selected set changes",
        )
        # A reader who adds a smaller model must be told to LOWER the floor.
        self.assertRegex(
            self.calibration,
            rf"(?is)\b{SMALLEST_GATEWAY_WINDOW}\b.{{0,120}}\blower\b|\blower\b.{{0,120}}\b{SMALLEST_GATEWAY_WINDOW}\b",
            "the lower-it-if-you-add-a-smaller-model obligation must be explicit",
        )

    def test_under_use_of_the_large_models_is_documented_as_deliberate(self) -> None:
        # Silence here would read as an oversight and invite someone to "fix" it by raising the
        # floor globally, which is the exact error the floor prevents.
        self.assertRegex(
            self.calibration,
            r"(?is)\bunder-uses?\b.{0,200}\bby design\b",
            "the accepted cost must be labelled deliberate",
        )
        self.assertRegex(
            self.calibration,
            r"(?is)\bsingle-model\b.{0,160}\b(?:opt-in|raise)\b",
            "the single-model opt-in is the pressure valve and must be named",
        )

    def test_opinionated_pct_default_is_85_and_remains_one_directional(self) -> None:
        # ADR-0012 Decision item 4 amended 2026-08-08: opinionated 85, safe because one-directional.
        # Before measurement the knob was deliberately left unset; now 85 ships as a safety margin.
        for text, name in ((self.calibration, "calibration"), (ADR.read_text(encoding="utf-8"), "adr")):
            self.assertIn("85", text, f"{name} must record the opinionated 85")
            self.assertRegex(text, r"(?is)\bopinionated\b", f"{name} must label 85 as opinionated")
            self.assertRegex(text, r"(?is)\bone-directional\b", f"{name} must keep the one-directional reason")
        self.assertIn("231200", self.calibration, "effective 0.85*272000 trigger must be stated")
        self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85", self.calibration)
        self.assertRegex(self.calibration, r"(?is)amended 2026-08-08", "amendment date must travel")
        self.assertRegex(
            self.calibration,
            r"(?is)only when the operator has not already set it",
            "installer-override-wins must be explicit",
        )
        adr = ADR.read_text(encoding="utf-8")
        self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85", adr)
        # The only concrete shipped assignment may be 85; any other concrete percentage would be
        # a different default. The placeholder <1-100> for installer tuning is not a concrete value.
        for text, name in ((self.calibration, "calibration"), (adr, "adr")):
            assignments = re.findall(rf"{DEFERRED_KNOB}\s*[=:]\s*(\d+)", text)
            for value in assignments:
                self.assertEqual(value, "85", f"{name} prescribes {value} instead of opinionated 85")
            self.assertNotRegex(
                text,
                r"(?is)85\s+is\s+(?:a\s+)?measured\s+optimum",
                f"{name} must not claim 85 is a measured optimum",
            )
        research = RESEARCH.read_text(encoding="utf-8")
        self.assertIn("claude_code.compaction", research)
        self.assertIn("pre_tokens", research)
        self.assertRegex(research, r"(?is)\bPreCompact\b", "measurement procedure must name boundary hook")
        self.assertRegex(research, r"(?is)\bA/B\b|\bidentical run\b", "A/B must remain decisive")
        self.assertIn("85", research)
        self.assertRegex(research, r"(?is)\bopinionated\b", "research table must label 85 opinionated")

    def test_shared_pool_output_budget_interaction_is_stated_where_routing_is_read(self) -> None:
        self.assertIn(str(UNRECOGNIZED_OUTPUT_DEFAULT), self.calibration)
        self.assertRegex(
            self.calibration,
            r"(?is)\breduces the context available\b|\breduces the effective context\b",
            "the output-vs-input coupling must be stated, not implied",
        )
        self.assertRegex(
            self.calibration,
            r"(?is)\bshared\b.{0,200}\barithmetic\b|\barithmetic\b.{0,200}\bshared\b",
            "on a shared pool the trade is exact, not approximate",
        )
        # The recorded per-model map must use the measured value, never the rounded one.
        self.assertIn('"muse-spark-1.2": 1048576', self.calibration)
        self.assertRegex(
            self.calibration,
            r"(?is)\bnot a rounded 1000000\b",
            "the rounded value changes the marking predicate and must be warned against",
        )

    def test_live_config_is_documented_as_untouched_rather_than_applied(self) -> None:
        research = RESEARCH.read_text(encoding="utf-8")
        self.assertRegex(
            research,
            r"(?is)\blive config\b.{0,120}\buntouched\b",
            "a recipe must not read as a description of current state",
        )
        self.assertRegex(
            research,
            r"(?is)\babsent\b",
            "the verification that the map is absent must be recorded",
        )
        for text, name in ((research, "research"), (ADR.read_text(encoding="utf-8"), "adr")):
            self.assertRegex(
                text,
                r"(?is)\b(?:operator's own|operation-specific)\b.{0,60}\bauthoriz",
                f"{name} must route the mutation through the operator's own authorization",
            )

    def test_calibration_keeps_context_as_request_never_proof_of_served_window(self) -> None:
        self.assertRegex(
            self.calibration,
            r"(?is)requested_context_form.{0,200}\brequest\b.{0,200}\bnever proves?\b.{0,60}\bserved window\b",
        )
        self.assertIn("context_readback_status: unavailable", self.calibration)
        # The inverse claim must never appear: a requested form is not evidence of a window.
        self.assertNotRegex(
            self.calibration,
            r"(?is)\brequested\s+context\s+form\s+(?:equals?|is|proves?|guarantees?|confirms?)\s+"
            r"(?:the\s+)?(?:served|effective|resolved)\s+(?:context\s+)?window\b",
        )
        self.assertNotRegex(
            self.calibration,
            r"(?is)\[1m\].{0,160}\b(?:proves?|guarantees?|confirms?)\b.{0,80}\bcontext window\b",
        )

    def test_layer_ownership_rule_is_stated_in_the_calibration(self) -> None:
        self.assertRegex(
            self.calibration,
            r"(?is)configure the gateway,? not the session",
            "the layer-ownership rule is the decision; it must be stated where routing is read",
        )
        self.assertRegex(
            self.calibration,
            r"(?is)\bper session\b.{0,80}\bprocess-wide\b",
            "the per-session constraint is what forces the conservative floor",
        )

    def test_flagship_points_at_the_table_and_restates_no_window_number(self) -> None:
        flagship = FLAGSHIP.read_text(encoding="utf-8")
        self.assertIn("Context windows section", flagship)
        self.assertIn("model-routing-calibration.md", flagship)
        self.assertRegex(
            flagship,
            r"(?is)\bsole owner\b.{0,120}\bper-model numbers\b",
            "one owner per fact: the flagship must defer, not restate",
        )
        # No per-model window number may appear outside its owner.
        for number in ("372000", "272000", "1050000", "1048576", "100000", "350000"):
            self.assertNotIn(
                number,
                flagship,
                f"{number} restated in the flagship; the calibration owns the numbers",
            )

    def test_router_advertises_the_window_material_without_carrying_it(self) -> None:
        router = ROUTER.read_text(encoding="utf-8")
        self.assertIn("per-model context windows", router)
        self.assertIn("shared-versus-separate", router)
        for number in ("372000", "1048576", "350000"):
            self.assertNotIn(number, router, f"{number} restated in the router")

    def test_research_and_adr_exist_dated_and_authorize_nothing(self) -> None:
        research = RESEARCH.read_text(encoding="utf-8")
        adr = ADR.read_text(encoding="utf-8")
        self.assertIn("2026-08-07", research)
        self.assertIn("**Status:** accepted", adr)
        self.assertIn("**Date:** 2026-08-07", adr)
        for text, name in ((research, "research"), (adr, "adr")):
            self.assertRegex(
                text,
                r"(?is)authorizes? no(?:thing|\s+\w)",
                f"{name} must close by authorizing nothing",
            )
        # The ADR must keep a reversal condition for each layer that could change.
        self.assertRegex(adr, r"(?is)## Reversal conditions")
        self.assertRegex(
            adr,
            r"(?is)\bper-model windows\b.{0,200}\bdiscovery catalog\b",
            "reversal condition 1: a gateway release advertising per-model windows",
        )
        self.assertRegex(
            adr,
            r"(?is)\bclient release with per-model context limits\b",
            "reversal condition 2: a client release with per-model limits",
        )

    def test_no_credential_or_private_path_leaked_into_installed_doctrine(self) -> None:
        # The calibration is installed content; the research and ADR are not, but neither
        # may carry a key or an operator-specific home.
        for path in (CALIBRATION, RESEARCH, ADR):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?i)\bsk-[A-Za-z0-9_-]{16,}", str(path))
            self.assertNotRegex(text, r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,}", str(path))
        self.assertNotIn("/home/", CALIBRATION.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
