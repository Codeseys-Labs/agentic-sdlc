from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "verification.md"
VALIDATE_BUNDLE_PY = ROOT / "scripts" / "validate_bundle.py"
OPENCODEX_CLAUDE_SH = ROOT / "scripts" / "opencodex-claude.sh"
INSTALL_OPERATOR_TOOLS_PY = ROOT / "scripts" / "install_operator_tools.py"
INSTALL_SKILL_BUNDLE_PY = ROOT / "scripts" / "install_skill_bundle.py"


def _normalize(text: str) -> str:
    """Collapse all whitespace, including the runbook's own line-wrap width, before comparing.

    A claim's tokens and punctuation still have to match exactly; only how the prose or the
    source happens to be wrapped or indented is treated as irrelevant to the contract.
    """
    return " ".join(text.split())


# Each constant below is a (runbook_fragment, source_pattern) PAIR extracted ONCE from a
# load-bearing tool-contract claim in docs/runbooks/verification.md, paired with the literal
# source text that backs it. Every fragment is taken from the runbook's own SHAPE-claim prose --
# never from one of its "Observed verbatim"/"Captured ... today" EXAMPLE TRANSCRIPT blocks, which
# are point-in-time by the runbook's own stated rule and stay exempt from this contract by
# construction, because no fragment below is drawn from one. A `source_pattern` is either a
# single literal string or a tuple of them when one runbook sentence names several tokens that
# each have their own line in the source. The test method named after each constant is the one
# place that claim can fail, so a drift on either side names itself instead of rotting quietly.

# docs/runbooks/verification.md, section 1 step 9 (shape claim, not the numeric example below it)
CLAIM_VALIDATE_BUNDLE_SUMMARY_FORMAT = (
    "Success shape: exit 0 with a line of the form `validate-bundle: 0 error(s), 0 warning(s)`.",
    r'''print(f"\nvalidate-bundle: {len(result.errors)} error(s), {len(result.warnings)} warning(s)")''',
)

# Same runbook sentence, its errors-only-exit half; scripts/validate_bundle.py, main()'s return.
CLAIM_VALIDATE_BUNDLE_ERRORS_ONLY_EXIT = (
    "A nonzero error count exits 1; warnings exit 0",
    "return 1 if result.errors else 0",
)

# docs/runbooks/verification.md, section 3 ("`ccodex status`'s provider table and its honesty
# lines"), the route-reachability sentence; scripts/opencodex-claude.sh cmd_status's four
# route-reachability printf lines.
CLAIM_OPENCODEX_ROUTE_TOKENS = (
    "a route-reachability line that is `ok`, `BYPASSED` (something in the environment or"
    " settings would route around the gateway even if it were up), `MISBILLED` (an"
    " `sk-ant-api*` Console key would take the native branch but bill API credits), or"
    " `UNKNOWN` (a settings document it could not read)",
    (
        r'''printf '  ok      : nothing exported in this shell, and no key in the documents below, outranks\n' ''',
        r'''printf '  BYPASSED: %s is exported; a launch would reach a cloud provider, not this gateway\n' "$blocker"''',
        r'''printf '  MISBILLED: %s holds an sk-ant-api* Console key; native turns would bill credits\n' "$blocker"''',
        r'''printf '  UNKNOWN : %s could not be checked (%s); a launch refuses rather than assume it is clean\n' "$document" "${blocker#unreadable:}"''',
    ),
)

# Same runbook sentence, its supervision-line half; cmd_status's three `state` printf lines.
CLAIM_OPENCODEX_SUPERVISION_TOKENS = (
    "the separate supervision line above it is `healthy`, `HALF-UP`, or `DOWN`",
    (
        r'''printf '  state   : healthy\n' ''',
        r'''printf '  state   : HALF-UP (something is bound or a pid is alive, but no healthy identity probe)\n' ''',
        r'''printf '  state   : DOWN\n' ''',
    ),
)

# docs/runbooks/verification.md, section 1 step 7; scripts/install_operator_tools.py's status
# branch of the shared lifecycle-summary renderer.
CLAIM_OPERATOR_TOOLS_STATUS_SUMMARY_FORMAT = (
    "`status` prints one `ok`/`absent`/`unmanaged` line per desired command plus a closing"
    " summary line in the shape `X ok, Y conflict, Z absent, W pending`.",
    r'''return f"status summary: {ok} ok, {unmanaged + conflicts} conflict, {absent} absent, {pending} pending"''',
)

# docs/runbooks/verification.md, section 1 step 6, the "no owned entries" half of the guaranteed
# two-shape terminal line; scripts/install_skill_bundle.py's status_summary().
CLAIM_BUNDLE_STATUS_NO_OWNED_ENTRIES = (
    "`no owned entries for this host`",
    r'''return "no owned entries for this host (run: mise run bundle:install)"''',
)

# Same runbook sentence, its "N ok, M conflict, K absent" half; status_summary()'s other branch.
CLAIM_BUNDLE_STATUS_OK_CONFLICT_ABSENT = (
    "`N ok, M conflict, K absent`",
    r'''return f"{counts['ok']} ok, {counts['conflict']} conflict, {counts['absent']} absent"''',
)


class VerificationRunbookContractTests(unittest.TestCase):
    """Each test owns exactly one load-bearing claim from docs/runbooks/verification.md.

    A claim is checked on both sides: the runbook still states the fragment, and the named
    source file still contains the literal pattern that backs it. Either side drifting away from
    the recorded pair fails the one test that names the claim, instead of the claim rotting
    silently the way plain prose does. This never touches the runbook's own numeric example
    transcripts -- those stay exempt by construction, because no constant above is drawn from
    one.
    """

    def assert_claim(self, claim: tuple, source_file: Path) -> None:
        fragment, pattern = claim
        runbook_text = _normalize(RUNBOOK.read_text(encoding="utf-8"))
        source_text = _normalize(source_file.read_text(encoding="utf-8"))
        # assertTrue, not assertIn: assertIn appends the whole normalized file as the
        # haystack, turning one drift into a ~105 KB failure message.
        self.assertTrue(
            _normalize(fragment) in runbook_text,
            f"docs/runbooks/verification.md no longer states this claim: {fragment!r}",
        )
        patterns = pattern if isinstance(pattern, tuple) else (pattern,)
        for one in patterns:
            self.assertTrue(
                _normalize(one) in source_text,
                f"{source_file.relative_to(ROOT)} no longer contains: {one!r}",
            )

    def test_validate_bundle_summary_format(self) -> None:
        self.assert_claim(CLAIM_VALIDATE_BUNDLE_SUMMARY_FORMAT, VALIDATE_BUNDLE_PY)

    def test_validate_bundle_errors_only_exit_rule(self) -> None:
        self.assert_claim(CLAIM_VALIDATE_BUNDLE_ERRORS_ONLY_EXIT, VALIDATE_BUNDLE_PY)

    def test_opencodex_route_reachability_tokens(self) -> None:
        self.assert_claim(CLAIM_OPENCODEX_ROUTE_TOKENS, OPENCODEX_CLAUDE_SH)

    def test_opencodex_supervision_tokens(self) -> None:
        self.assert_claim(CLAIM_OPENCODEX_SUPERVISION_TOKENS, OPENCODEX_CLAUDE_SH)

    def test_operator_tools_status_summary_format(self) -> None:
        self.assert_claim(
            CLAIM_OPERATOR_TOOLS_STATUS_SUMMARY_FORMAT, INSTALL_OPERATOR_TOOLS_PY
        )

    def test_bundle_status_no_owned_entries_line(self) -> None:
        self.assert_claim(CLAIM_BUNDLE_STATUS_NO_OWNED_ENTRIES, INSTALL_SKILL_BUNDLE_PY)

    def test_bundle_status_ok_conflict_absent_line(self) -> None:
        self.assert_claim(CLAIM_BUNDLE_STATUS_OK_CONFLICT_ABSENT, INSTALL_SKILL_BUNDLE_PY)


if __name__ == "__main__":
    unittest.main()
