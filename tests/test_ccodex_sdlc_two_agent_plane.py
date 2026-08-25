"""Two receipted planes on one host: two pointers, and neither verb reaches the other's bytes.

WHY THIS FILE IS SEPARATE FROM THE PER-VERB SUITES. Its subject is not one module's behaviour; it is
what the three modules leave behind when they are run in sequence against ONE operator plane. The
critique-a §2.3 defect this exists to kill is only reachable across that sequence: with ``--agent``
required and no wildcard, a pointer keyed by scope ALONE would let a codex activation overwrite a
claude one, and the next ``uninstall --host claude`` would then remove codex bytes on the strength of
it. Neither module alone can be wrong about that; the pair can.

WHAT EACH CHECK PROVES, AND WHAT WOULD MAKE IT GO RED.

  * Two installs from ONE acquired payload leave TWO pointer files, TWO receipts, and TWO disjoint
    sets of destinations. Regress the pointer path to a per-scope name and the second install
    overwrites the first pointer; regress the receipt identity to drop the agent and the second
    install refuses against the first's create-only receipt; regress the journal name the same way and
    the first plane's receipt ends up naming a ``journal_sha256`` no file carries.
  * ``uninstall --host claude`` leaves every codex destination BYTE-IDENTICAL (sha256 before and
    after), leaves the codex pointer untouched, and leaves the codex ownership rows in the shared
    ledger. Regress the entry filter, the ledger row filter, or the boundary root to a claude constant
    and codex bytes leave with the claude retirement.
  * The reverse direction is asserted too, in the same test, because "A does not touch B" and "B does
    not touch A" are two facts and a single-direction check would pass on a plane that only ever
    protected one of them.

EVERY CLI RUN HERE IS ISOLATED (seed agentic-sdlc-8dca). Both homes, the state root, the data root,
and the installer's ownership document live under one temporary directory per test, and every
configuration is injected rather than read from the operator's environment -- including the codex
home, which a fixture that left it unset would resolve to the operator's own ``~/.codex``.
"""

from __future__ import annotations

import contextlib
from dataclasses import replace as dataclass_replace
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import Any
import unittest


ROOT = Path(__file__).parents[1]


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


install = _load(ROOT / "scripts" / "ccodex_sdlc_install.py", "two_agent_install")
uninstall = _load(ROOT / "scripts" / "ccodex_sdlc_uninstall.py", "two_agent_uninstall")
bundle = _load(ROOT / "scripts" / "install_skill_bundle.py", "two_agent_bundle")
receipts = _load(ROOT / "scripts" / "distribution_activation_receipt.py", "two_agent_receipts")
planes = _load(ROOT / "scripts" / "ccodex_sdlc_host_planes.py", "two_agent_host_planes")
# The install suite owns the acquisition fixture: one real candidate payload tree, one real manifest,
# and one really sealed acquisition receipt. Reusing it is the point -- a second fabricator here could
# drift from the shape the product admits and this file would then prove something about the copy.
install_suite = _load(ROOT / "tests" / "test_ccodex_sdlc_install.py", "two_agent_install_suite")

WINDOWS_SKIP = unittest.skipIf(
    os.name == "nt",
    "the ccodex sdlc lifecycle writes through the POSIX-only durable-write plane; native Windows"
    " fails closed by name at the CLI",
)

#: The payload subset, carrying entries for BOTH planes. A payload with claude entries only could not
#: distinguish "the codex plane was left alone" from "there was nothing there to touch".
PAYLOAD_FILES = {
    "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha\n",
    "skills/alpha-skill/references/notes.md": "notes\n",
    "agents/claude/cartographer.md": "cartographer\n",
    "agents/codex/cartographer.toml": 'name = "cartographer"\n',
    "commands/sdlc-frame.md": "frame\n",
}
#: What each plane owns after its own install, spelled out rather than read back from the writer: a
#: test that asked the installer where it wrote would agree with any destination it chose.
CLAUDE_ENTRIES = ("skills/alpha-skill", "agents/cartographer.md", "commands/sdlc-frame.md")
CODEX_ENTRIES = ("skills/alpha-skill", "agents/cartographer.toml")


def digest_tree(root: Path) -> dict[str, str]:
    """Every regular file under one root, keyed by relative path, digested.

    Directories and links are recorded by kind rather than content, so a destination that changed NODE
    TYPE -- a directory replaced by a link to elsewhere -- is a difference this comparison sees.
    """
    inventory: dict[str, str] = {}
    if not root.exists():
        return inventory
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            inventory[relative] = f"symlink:{os.readlink(path)}"
        elif path.is_dir():
            inventory[relative] = "dir"
        else:
            inventory[relative] = f"file:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    return inventory


@WINDOWS_SKIP
class TwoAgentPlaneTest(unittest.TestCase):
    """One host, one payload, two receipted planes."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name).resolve()
        self.fixture = install_suite.build_fixture(
            Path(tempfile.mkdtemp(dir=self.root)), payload=dict(PAYLOAD_FILES)
        )
        self.activation = self.fixture.state_home / "agentic-sdlc" / "activation"

    # ---- driving the shipped modules ----------------------------------------------------------

    def install_plane(self, agent: str, instant: str) -> tuple[int, str, str]:
        """Run the shipped install module for ONE agent, exactly as the dispatcher does."""
        config = dataclass_replace(self.fixture.config, agent=agent, observed_instant=instant)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(install, "default_config", lambda: config)
            )
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = install.main(["--host", agent])
        return code, out.getvalue(), err.getvalue()

    def retire_plane(self, agent: str, instant: str) -> tuple[int, str]:
        """Run the shipped uninstall module for ONE agent, through its own ``execute`` entry."""
        config = uninstall.Config(
            scripts_dir=ROOT / "scripts",
            home=self.fixture.home,
            state_root=self.fixture.installer_state_root,
            activation_root=self.activation,
            codex_home=self.fixture.config.codex_home,
            host=agent,
            platform_system="Linux",
            stated_at=instant,
        )
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = uninstall.execute(bundle, receipts, config)
        return code, out.getvalue() + err.getvalue()

    # ---- the plane's own paths, spelled here ---------------------------------------------------

    def pointer(self, agent: str) -> Path:
        return self.activation / "active" / agent / "user.json"

    def plane_root(self, agent: str) -> Path:
        return self.fixture.home / ".claude" if agent == "claude" else self.fixture.config.codex_home

    def ledger_agents(self) -> dict[str, int]:
        state = json.loads(self.fixture.installer_state_root.joinpath("agentic-sdlc-installer", "state.json").read_text())
        counts: dict[str, int] = {}
        for record in state["entries"].values():
            counts[record["agent"]] = counts.get(record["agent"], 0) + 1
        return counts

    # ---- the checks ----------------------------------------------------------------------------

    def test_installing_both_planes_leaves_two_pointers_and_two_receipts(self) -> None:
        """The keyed pointer plane, proven across the sequence rather than per verb.

        The two runs share ONE acquisition receipt and ONE injected instant, which is deliberate: that
        is the exact input under which a receipt identity or a journal name without the agent collides,
        and create-only files turn a collision into either a refusal or a destroyed binding.
        """
        claude_code, claude_out, claude_err = self.install_plane("claude", install_suite.INSTANT)
        self.assertEqual(0, claude_code, claude_err)
        codex_code, codex_out, codex_err = self.install_plane("codex", install_suite.INSTANT)
        self.assertEqual(0, codex_code, codex_err)

        # TWO pointer files, at the two keyed paths, each naming its own receipt.
        self.assertTrue(self.pointer("claude").is_file(), sorted(self.activation.rglob("*")))
        self.assertTrue(self.pointer("codex").is_file(), sorted(self.activation.rglob("*")))
        self.assertNotEqual(self.pointer("claude").read_bytes(), self.pointer("codex").read_bytes())
        self.assertEqual(
            {"claude", "codex"},
            {path.parent.name for path in (self.activation / "active").rglob("user.json")},
        )
        # And no pre-keyed pointer was created by either run.
        self.assertFalse((self.activation / "active-receipt.json").exists())

        # TWO receipts, each stating its own plane in the ONE field that states it.
        filed = sorted((self.activation / "receipts").glob("*.json"))
        self.assertEqual(2, len(filed), [path.name for path in filed])
        by_agent = {}
        for path in filed:
            body = json.loads(path.read_text())["body"]
            self.assertNotIn("host", body, "v2 states the plane once, as scope.agent")
            by_agent[body["scope"]["agent"]] = (path, body)
        self.assertEqual({"claude", "codex"}, set(by_agent))
        for agent, (path, body) in by_agent.items():
            with self.subTest(agent=agent):
                self.assertEqual({"agent": agent, "kind": "user"}, body["scope"])
                self.assertEqual("complete", body["effect_state"])
                self.assertEqual("activated", body["terminal_phase"])
                self.assertIn(f"install-{agent}-", path.name)
                self.assertEqual(
                    json.loads(self.pointer(agent).read_text())["body"]["scope"]["agent"], agent
                )

        # TWO journals, so neither receipt's `journal_sha256` names a file the other run overwrote.
        journals = sorted((self.activation / "journals").glob("*.json"))
        self.assertEqual(2, len(journals), [path.name for path in journals])
        for agent, (_path, body) in by_agent.items():
            with self.subTest(agent=agent):
                named = [
                    path
                    for path in journals
                    if hashlib.sha256(path.read_bytes()).hexdigest() == body["journal_sha256"]
                ]
                self.assertEqual(1, len(named), f"{agent}'s receipt names no journal on disk")
                self.assertIn(f"install-{agent}-", named[0].name)

        # The two destination sets are disjoint and each is complete.
        for relative in CLAUDE_ENTRIES:
            self.assertTrue((self.plane_root("claude") / relative).exists(), relative)
        for relative in CODEX_ENTRIES:
            self.assertTrue((self.plane_root("codex") / relative).exists(), relative)
        # Claude-only kinds have no codex destination at all: the installer refuses one, so their
        # absence here is the payload model rather than a partial install.
        self.assertFalse((self.plane_root("codex") / "commands").exists())
        self.assertFalse((self.plane_root("codex") / "agents" / "cartographer.md").exists())

        # ONE shared ownership ledger, with rows for both agents.
        self.assertEqual({"claude": 3, "codex": 2}, self.ledger_agents())

        # EACH RUN NAMES THE ROOT IT ACTUALLY WROTE INTO, in its report and in the plan document whose
        # digest its receipt binds. Asserting the prefix alone would pass on a codex run that reported
        # the Claude collection, which is exactly what a plane-root derivation regressed to a constant
        # would print -- the bytes would still land correctly, because destinations come from the
        # installer, and only these two statements would be wrong.
        plans = {}
        for path in sorted((self.activation / "plans").glob("*.json")):
            document = json.loads(path.read_text())
            plans[document["host"]] = document
        self.assertEqual({"claude", "codex"}, set(plans))
        for agent, output in (("claude", claude_out), ("codex", codex_out)):
            with self.subTest(agent=agent):
                expected = str(self.plane_root(agent))
                self.assertIn(f"{agent} root: {expected} (copies, never links)", output)
                self.assertEqual(expected, plans[agent]["plane_root"])
                self.assertNotIn("claude_root", plans[agent])
                for row in plans[agent]["entries"]:
                    self.assertTrue(
                        row["destination"].startswith(expected + "/"),
                        f"{agent}'s plan names a destination outside its own root: {row}",
                    )

    def test_retiring_one_plane_leaves_every_byte_of_the_other_identical(self) -> None:
        """The critique-a §2.3 cross-agent defect, proven dead in BOTH directions.

        A single-direction check would pass on a plane that protected codex from claude and not the
        reverse, so each half of this test retires one agent on its own freshly built pair and asserts
        the other's bytes, pointer, receipt, and ledger rows are untouched. The positive control is in
        the same assertions: the RETIRED plane's bytes really did leave, so "unchanged" is a comparison
        that can distinguish the two outcomes rather than a walk that found nothing either time.
        """
        for retired, survivor in (("claude", "codex"), ("codex", "claude")):
            with self.subTest(retired=retired, survivor=survivor):
                self.setUp()
                self.assertEqual(0, self.install_plane("claude", install_suite.INSTANT)[0])
                self.assertEqual(0, self.install_plane("codex", install_suite.INSTANT)[0])

                before = digest_tree(self.plane_root(survivor))
                self.assertTrue(before, f"the {survivor} plane is empty, so nothing could be compared")
                survivor_pointer = self.pointer(survivor).read_bytes()
                retired_before = digest_tree(self.plane_root(retired))

                code, report = self.retire_plane(retired, install_suite.LATER_INSTANT)
                self.assertEqual(0, code, report)

                # THE SURVIVOR IS BYTE-IDENTICAL: same paths, same node kinds, same digests.
                self.assertEqual(before, digest_tree(self.plane_root(survivor)))
                self.assertEqual(survivor_pointer, self.pointer(survivor).read_bytes())
                self.assertTrue(self.pointer(survivor).is_file())
                # Its ledger rows survive too, so a later verb can still select them.
                self.assertEqual(
                    {"claude": 3, "codex": 2}[survivor], self.ledger_agents().get(survivor)
                )

                # POSITIVE CONTROL: the retired plane's own entries really did leave, so the equality
                # above is a comparison between two different outcomes.
                after_retired = digest_tree(self.plane_root(retired))
                self.assertNotEqual(retired_before, after_retired)
                for relative in CLAUDE_ENTRIES if retired == "claude" else CODEX_ENTRIES:
                    self.assertFalse((self.plane_root(retired) / relative).exists(), relative)
                # WHAT THE SHIPPED RETIREMENT DOES AND DOES NOT DO TO THE POINTER, asserted as observed
                # rather than as hoped: the ledger rows for this agent are gone, and the keyed pointer
                # is LEFT IN PLACE still naming the install receipt it was pointing at. A second
                # retirement of the same activation is refused by the create-only retirement receipt
                # rather than by an absent pointer. That is pre-WX behaviour, identical on both planes,
                # and it is pinned here so a later wave that changes it does so deliberately -- and so
                # that the survivor assertions above are not read as covering it.
                self.assertNotIn(retired, self.ledger_agents())
                retired_pointer = json.loads(self.pointer(retired).read_text())
                self.assertEqual("install", retired_pointer["body"]["operation"])
                self.assertEqual({"agent": retired, "kind": "user"}, retired_pointer["body"]["scope"])
                repeat, repeat_report = self.retire_plane(retired, install_suite.LATER_INSTANT)
                self.assertEqual(3, repeat, repeat_report)
                self.assertEqual(before, digest_tree(self.plane_root(survivor)))

                # The retirement receipt states the plane it retired, and only that one.
                retirements = [
                    json.loads(path.read_text())["body"]
                    for path in sorted((self.activation / "receipts").glob("*.json"))
                    if json.loads(path.read_text())["body"]["operation"] == "uninstall"
                ]
                self.assertEqual(1, len(retirements), retirements)
                self.assertEqual({"agent": retired, "kind": "user"}, retirements[0]["scope"])

    def test_a_hand_moved_pointer_cannot_redirect_one_planes_removal_at_the_other(self) -> None:
        """The filename is the admission authority, so a swapped pointer refuses rather than acting.

        This is the axis the keyed plane exists for: copying the codex pointer over the claude one
        makes the claude verb's own pointer name a receipt whose ``scope.agent`` is codex, and the
        disagreement is refused BY NAME before a path is stat'ed. Without the agent axis the removal
        would proceed with codex's inventory under the claude key.
        """
        self.assertEqual(0, self.install_plane("claude", install_suite.INSTANT)[0])
        self.assertEqual(0, self.install_plane("codex", install_suite.INSTANT)[0])
        codex_before = digest_tree(self.plane_root("codex"))

        self.pointer("claude").write_bytes(self.pointer("codex").read_bytes())
        code, report = self.retire_plane("claude", install_suite.LATER_INSTANT)

        self.assertEqual(3, code, report)
        self.assertIn("pointer-receipt-disagreement", report)
        self.assertEqual(codex_before, digest_tree(self.plane_root("codex")))
        for relative in CLAUDE_ENTRIES:
            self.assertTrue((self.plane_root("claude") / relative).exists(), relative)
        # Positive control: with its own pointer restored, the same run retires normally.
        self.assertEqual(0, self.install_plane("claude", install_suite.LATER_INSTANT)[0])
        restored, restored_report = self.retire_plane("claude", "2026-08-20T12:20:00Z")
        self.assertEqual(0, restored, restored_report)
        self.assertEqual(codex_before, digest_tree(self.plane_root("codex")))


@WINDOWS_SKIP
class ContractRowAdmissionTest(unittest.TestCase):
    """A plane whose compatibility row the payload does not declare is refused, never borrowed."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name).resolve()

    def build(self, contract: dict[str, Any] | None = None) -> Any:
        return install_suite.build_fixture(
            Path(tempfile.mkdtemp(dir=self.root)), payload=dict(PAYLOAD_FILES), contract=contract
        )

    def run_install(self, fixture: Any, agent: str) -> tuple[int, str]:
        config = dataclass_replace(fixture.config, agent=agent)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch.object(install, "default_config", lambda: config)
            )
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = install.main(["--host", agent])
        return code, out.getvalue() + err.getvalue()

    def test_a_payload_with_no_codex_row_refuses_the_codex_plane_and_admits_claude(self) -> None:
        """The mutation this wave owes: delete the codex contract row and the codex install refuses.

        The claude half is the positive control, in the same test and against the same payload: it
        stays green under the mutation, which is what makes the refusal attributable to the missing row
        rather than to a payload the whole lifecycle stopped admitting.
        """
        contract = json.loads(
            (ROOT / "policy" / "release-contract.v1.json").read_text(encoding="utf-8")
        )
        contract["compatibility"]["companion_hosts"].pop("codex")
        without = self.build(contract=contract)
        code, report = self.run_install(without, "codex")
        self.assertEqual(3, code, report)
        self.assertIn("declares no compatibility.companion_hosts.codex row", report)
        self.assertIn("borrowing another host's compatibility claims", report)
        self.assertEqual([], without.activation_receipts())
        self.assertFalse((without.config.codex_home / "agents").exists())

        claude_only = self.build(contract=contract)
        claude_code, claude_report = self.run_install(claude_only, "claude")
        self.assertEqual(0, claude_code, claude_report)

        # And with the shipped contract the same codex install completes.
        shipped = self.build()
        codex_code, codex_report = self.run_install(shipped, "codex")
        self.assertEqual(0, codex_code, codex_report)

    def test_a_codex_row_about_another_host_is_refused_rather_than_accepted(self) -> None:
        contract = json.loads(
            (ROOT / "policy" / "release-contract.v1.json").read_text(encoding="utf-8")
        )
        contract["compatibility"]["companion_hosts"]["codex"]["host"] = "claude-code"
        fixture = self.build(contract=contract)
        code, report = self.run_install(fixture, "codex")
        self.assertEqual(3, code, report)
        self.assertIn("compatibility is about the host 'claude-code'", report)
        self.assertIn("'codex-cli'", report)
        self.assertEqual([], fixture.activation_receipts())

    def test_the_codex_floor_is_compared_against_the_codex_hosts_own_observed_version(self) -> None:
        """The floor is real on this plane, and it is the CODEX row's floor rather than Core's.

        Claude's Core minimum is 2.1.154 and codex's is 0.148.0; a plane that read Core's row would
        refuse every codex host, and one that skipped the comparison would admit any. Both directions
        are asserted here against the same shipped contract.
        """
        row = json.loads((ROOT / "policy" / "release-contract.v1.json").read_text())
        minimum = row["compatibility"]["companion_hosts"]["codex"]["minimum_host_version"]
        self.assertEqual("0.148.0", minimum)

        at_floor = self.build()
        code, report = self.run_install(
            dataclass_replace(at_floor, config=dataclass_replace(at_floor.config, observed_host_version=minimum)),
            "codex",
        )
        self.assertEqual(0, code, report)

        below = self.build()
        code, report = self.run_install(
            dataclass_replace(below, config=dataclass_replace(below.config, observed_host_version="0.147.9")),
            "codex",
        )
        self.assertEqual(3, code, report)
        self.assertIn("eligibility floor", report)
        self.assertIn("Codex CLI", report)
        self.assertEqual([], below.activation_receipts())

    def test_an_unobservable_codex_version_refuses_rather_than_assuming_compatibility(self) -> None:
        fixture = self.build()
        code, report = self.run_install(
            dataclass_replace(fixture, config=dataclass_replace(fixture.config, observed_host_version=None)),
            "codex",
        )
        self.assertEqual(3, code, report)
        self.assertIn("Codex CLI host version could not be observed", report)
        self.assertEqual([], fixture.activation_receipts())
        # Positive control: the same fixture with an observable version activates.
        control = self.build()
        self.assertEqual(0, self.run_install(control, "codex")[0])


class ClosedTableTest(unittest.TestCase):
    """The table is the ONE place a plane is widened, and every consumer reads that one place."""

    def test_the_table_is_closed_and_every_row_is_complete(self) -> None:
        self.assertEqual(("claude", "codex"), planes.AGENTS)
        self.assertEqual(set(planes.AGENTS), set(planes.HOST_PLANES))
        for agent in planes.AGENTS:
            plane = planes.plane_for(agent)
            with self.subTest(agent=agent):
                self.assertEqual(agent, plane.agent)
                self.assertTrue(plane.contract_host)
                self.assertNotEqual(plane.contract_host, plane.agent)
                self.assertIn(
                    plane.contract_section,
                    (planes.CONTRACT_SECTION_CORE, planes.CONTRACT_SECTION_COMPANION),
                )
                self.assertIsInstance(plane.checks_marketplace_overlap, bool)
                self.assertIsInstance(plane.owns_legacy_pointer, bool)
                self.assertTrue(plane.display)
        with self.assertRaises(KeyError):
            planes.plane_for("gemini")
        with self.assertRaises(KeyError):
            planes.plane_for(None)

    def test_exactly_one_plane_owns_the_pre_keyed_pointer_and_the_marketplace_gate(self) -> None:
        """Both are properties of ONE plane, and a second owner would be a defect not a widening.

        The pre-keyed pointer could only ever have been written by the plane whose writers spelled
        ``activation_scope: claude-home``, and the marketplace channel that can publish these entries
        is Claude's alone. A table that answered True twice would let a codex run claim a claude
        statement or block on a collision it cannot have.
        """
        owners = [a for a in planes.AGENTS if planes.plane_for(a).owns_legacy_pointer]
        gated = [a for a in planes.AGENTS if planes.plane_for(a).checks_marketplace_overlap]
        self.assertEqual(["claude"], owners)
        self.assertEqual(["claude"], gated)

    def test_the_agent_root_derivation_matches_the_installers_own_model(self) -> None:
        """One model, not two: the table's derivation is checked against the shipped installer's.

        This is what makes ``collection`` a re-expression rather than a second opinion -- the installer
        decides where an agent's entries live, and a table that disagreed would bound a removal at a
        root the ownership rows are not under.
        """
        home = Path("/fixture/home")
        codex_home = Path("/fixture/codex")
        config = bundle.Config(ROOT, home, codex_home, "copy", False, "claude", None)
        for agent, configured in (("claude", home), ("codex", codex_home)):
            with self.subTest(agent=agent):
                entry = bundle.Entry(agent, "skill", "alpha", ROOT / "skills")
                self.assertEqual(
                    bundle.agent_root(entry, config),
                    planes.plane_for(agent).agent_root(configured),
                )
                self.assertEqual(bundle.configured_root(entry, config), configured)

    def test_the_receipt_family_admits_exactly_the_tables_agents(self) -> None:
        self.assertEqual(tuple(sorted(receipts.HOSTS)), planes.AGENTS)
        self.assertEqual(("claude",), receipts.HOSTS_V1)


if __name__ == "__main__":
    unittest.main()
