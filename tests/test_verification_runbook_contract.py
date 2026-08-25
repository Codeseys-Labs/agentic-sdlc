from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "verification.md"
VALIDATE_BUNDLE_PY = ROOT / "scripts" / "validate_bundle.py"
OPENCODEX_CLAUDE_SH = ROOT / "scripts" / "opencodex-claude.sh"
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
# lines"), the route-reachability sentence; scripts/opencodex-claude.sh cmd_status's five
# route-reachability printf lines.
CLAIM_OPENCODEX_ROUTE_TOKENS = (
    "a route-reachability line that is `ok`, `BYPASSED` (something in the environment or"
    " settings would route around the gateway even if it were up), `MISROUTED` (a model slot"
    " exported in this shell — `ANTHROPIC_MODEL`, an `ANTHROPIC_DEFAULT_*_MODEL` tier slot, or"
    " `ANTHROPIC_SMALL_FAST_MODEL` — holds a cloud-provider-shaped id, so that family would be"
    " served by the DEFAULT provider instead of Anthropic), `MISBILLED` (an"
    " `sk-ant-api*` Console key would take the native branch but bill API credits), or"
    " `UNKNOWN` (a settings document it could not read)",
    (
        r'''printf '  ok      : nothing exported in this shell, and no key in the documents below, outranks\n' ''',
        r'''printf '  BYPASSED: %s is exported; a launch would reach a cloud provider, not this gateway\n' "$blocker"''',
        r'''printf '  MISROUTED: %s is exported as %s, a cloud-provider model id; a launch refuses --\n' "$blocker" "$slot_value"''',
        r'''printf '  MISBILLED: %s holds an sk-ant-api* Console key; native turns would bill credits\n' "$blocker"''',
        r'''printf '  UNKNOWN : %s could not be checked (%s); a launch refuses rather than assume it is clean\n' "$document" "${blocker#unreadable:}"''',
    ),
)

# TOKEN EXHAUSTIVENESS for the same claim, added because assert_claim above only checks PRESENCE:
# the runbook could state a subset of what cmd_status's route-reachability block actually prints,
# or a superset, and assert_claim would still pass either way. This pair of helpers extracts each
# side of the SAME comparison independently of CLAIM_OPENCODEX_ROUTE_TOKENS, straight from the
# runbook's own sentence and the script's own printf lines, so the exhaustiveness check in
# test_opencodex_route_reachability_tokens_are_exhaustive below does not just re-derive from the
# constant its sibling test already checked -- that would let the two sides of the SAME drift move
# together silently. Adding a sixth outcome to cmd_status without documenting it in the runbook
# sentence -- or documenting one there that the live block no longer prints -- fails this test.
_ROUTE_LABEL_PATTERN = re.compile(r"printf '  ([A-Za-z][A-Za-z-]*)\s*:")


def _live_route_reachability_labels() -> frozenset[str]:
    source = OPENCODEX_CLAUDE_SH.read_text(encoding="utf-8")
    start = source.index("== gateway route reachability ==")
    end = source.index("== attribution log stream ==", start)
    return frozenset(_ROUTE_LABEL_PATTERN.findall(source[start:end]))


def _documented_route_reachability_labels() -> frozenset[str]:
    """The runbook's own top-level backtick tokens for this sentence, PAREN DEPTH aware.

    `MISBILLED`'s own parenthetical names `` `sk-ant-api*` `` as part of its explanation, so a
    naive "every backtick span in the sentence" extraction would return that shape fragment as a
    sixth route label. Tracking paren depth and only collecting a backtick span at depth 0 is what
    keeps that nested example out of the documented SET without hand-listing which spans to skip.
    """
    text = _normalize(RUNBOOK.read_text(encoding="utf-8"))
    start = text.index("a route-reachability line that is")
    end = text.index("; the separate supervision line", start)
    sentence = text[start:end]
    tokens: list[str] = []
    depth = 0
    index = 0
    while index < len(sentence):
        character = sentence[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "`" and depth == 0:
            close = sentence.index("`", index + 1)
            tokens.append(sentence[index + 1 : close])
            index = close
        index += 1
    return frozenset(tokens)


# Same runbook sentence, its supervision-line half; cmd_status's three `state` printf lines.
CLAIM_OPENCODEX_SUPERVISION_TOKENS = (
    "the separate supervision line above it is `healthy`, `HALF-UP`, or `DOWN`",
    (
        r'''printf '  state   : healthy\n' ''',
        r'''printf '  state   : HALF-UP (something is bound or a pid is alive, but no healthy identity probe)\n' ''',
        r'''printf '  state   : DOWN\n' ''',
    ),
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

# SNAPSHOT taken here, after every CLAIM_* constant above and before the class body, so it can
# never see a name a test method or helper defines later. This is the coverage guard's other half
# (see test_every_claim_constant_is_exercised_by_exactly_one_test_method): deleting one CLAIM_*
# constant and its one test method together leaves every REMAINING per-claim check green, because
# the deleted claim simply is not iterated any more. A per-name check alone cannot see a claim that
# no longer exists, so the total COUNT is pinned as a literal a silent deletion has to walk through
# rather than being caught in passing. Adding or removing a claim means updating this number in the
# same change -- which is the point: the update itself is the record that the change was deliberate.
_CLAIM_NAMES = tuple(sorted(name for name in globals() if name.startswith("CLAIM_")))


def _assert_claim_call_sites() -> dict[str, list[str]]:
    """Map each name in _CLAIM_NAMES to the test methods whose body calls
    `self.assert_claim(<that name>, ...)` with it as the literal first argument.

    AST-based rather than a source-text/regex search: a test that merely READS a CLAIM_* constant
    for some other purpose (as test_opencodex_route_reachability_tokens_are_exhaustive would, had
    it reused CLAIM_OPENCODEX_ROUTE_TOKENS instead of re-deriving both of its sides independently)
    must not count as "exercising" it here -- only an actual assert_claim call does, which is the
    one place a claim's fragment-and-pattern pair is genuinely checked.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=str(Path(__file__)))
    (class_def,) = (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "VerificationRunbookContractTests"
    )
    call_sites: dict[str, list[str]] = {name: [] for name in _CLAIM_NAMES}
    for member in class_def.body:
        if not (isinstance(member, ast.FunctionDef) and member.name.startswith("test_")):
            continue
        for node in ast.walk(member):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "assert_claim"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in call_sites
            ):
                call_sites[node.args[0].id].append(member.name)
    return call_sites


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

    def test_opencodex_route_reachability_tokens_are_exhaustive(self) -> None:
        # The presence check above passes on a documented SUBSET or SUPERSET of what cmd_status
        # actually prints; this requires the two SETS to be equal. Both sides are derived
        # independently of CLAIM_OPENCODEX_ROUTE_TOKENS and of each other -- see the two helpers'
        # own docstrings -- so a real drift in either the runbook sentence or the script's printf
        # lines fails here even if nobody remembered to touch the pattern tuple above.
        documented = _documented_route_reachability_labels()
        live = _live_route_reachability_labels()
        # POSITIVE CONTROL: both extractions must find SOMETHING, or an anchor silently stopped
        # matching (a renamed section heading, a reworded sentence) and an empty-vs-empty
        # comparison would pass for the wrong reason.
        self.assertTrue(documented, "no backtick route-reachability tokens found in the runbook")
        self.assertTrue(live, "no printf route-reachability labels found in cmd_status")
        self.assertEqual(
            documented,
            live,
            "docs/runbooks/verification.md's route-reachability sentence and cmd_status's "
            "route-reachability printf block name different outcome sets",
        )

    def test_opencodex_supervision_tokens(self) -> None:
        self.assert_claim(CLAIM_OPENCODEX_SUPERVISION_TOKENS, OPENCODEX_CLAUDE_SH)

    def test_bundle_status_no_owned_entries_line(self) -> None:
        self.assert_claim(CLAIM_BUNDLE_STATUS_NO_OWNED_ENTRIES, INSTALL_SKILL_BUNDLE_PY)

    def test_bundle_status_ok_conflict_absent_line(self) -> None:
        self.assert_claim(CLAIM_BUNDLE_STATUS_OK_CONFLICT_ABSENT, INSTALL_SKILL_BUNDLE_PY)

    def test_every_claim_constant_is_exercised_by_exactly_one_test_method(self) -> None:
        # Deleting one CLAIM_* constant AND its one test method together leaves every REMAINING
        # per-claim test green -- "Ran 6" instead of "Ran 7", with no failure naming what shrank.
        # The pinned count below is what makes that shrink loud: it has to be bumped in the SAME
        # change that adds or removes a claim, and bumping it is the record that the change was
        # deliberate rather than an accident this suite stayed silent about.
        self.assertEqual(
            len(_CLAIM_NAMES),
            6,
            "a CLAIM_* constant was added or removed without updating this pinned count "
            f"(current constants: {list(_CLAIM_NAMES)!r})",
        )
        # The complementary half: an EXISTING claim that lost its one assert_claim call (or picked
        # up a second, redundant one) without the constant itself disappearing, which the count
        # above cannot see because the name is still there.
        call_sites = _assert_claim_call_sites()
        for claim_name in _CLAIM_NAMES:
            with self.subTest(claim=claim_name):
                methods = call_sites[claim_name]
                self.assertEqual(
                    len(methods),
                    1,
                    f"{claim_name} must be checked by exactly one assert_claim call, found in: "
                    f"{methods!r}",
                )


if __name__ == "__main__":
    unittest.main()
