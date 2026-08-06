from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).parents[1]
GIT_DIR = ROOT / ".git"
RECORD = ROOT / "docs" / "progress" / "2026-07-21-prime-candidate-custody.json"
SELF = "tests/test_prime_candidate_custody.py"
ASSESSED_HEAD_COMMIT = "ada5ecd1ad3e2c9d6318cb869eeba045376d32bf"
ASSESSED_HEAD_TREE = "783eecb964cd3ce923ed2623ec956d26c7b490f5"
ASSESSED_RELEASE_BRANCH = "release/offline-observer-rc"
REQUIRED_CANDIDATE_COMMITS = {
    "73db932d4ea2d86eb39ff0712102466f3a090519": {
        "tree": "310311925d45cb67c766d80c9b8b79e0508e0e27",
        "role": "prime activation and instruction-generation candidate origin",
    },
    "de39b9e4c6479f4b9ea95eb0d98b9feed387a79e": {
        "tree": "bbc7d612a57ce57ddb1935f492b212b6ae11b62d",
        "role": "prime activation gate-proof and atomicity hardening",
    },
    "7c22893de63a213e3704c08f2246443a5d0ebe14": {
        "tree": "f4d72bce1cb1b9339776b069dd3ec324c4cba4da",
        "role": "integrated A2/A3 activation and instruction candidate",
    },
}
REQUIRED_FROZEN_REFS = {
    "blocker/prime-readiness-v7": {
        "commit": "6fa3c01b3d7146bbfc0a07c503dfe48ec57dcc60",
        "tree": "cf5ae280c3488d41f5c6bfac95224d6d1fae784d",
    },
    "blocker/seeds-worktrees-v7": {
        "commit": "6fa3c01b3d7146bbfc0a07c503dfe48ec57dcc60",
        "tree": "cf5ae280c3488d41f5c6bfac95224d6d1fae784d",
    },
    "integration/blocker-closure-v7": {
        "commit": "6fa3c01b3d7146bbfc0a07c503dfe48ec57dcc60",
        "tree": "cf5ae280c3488d41f5c6bfac95224d6d1fae784d",
    },
    "blocker/contracts-v7": {
        "commit": "6fa3c01b3d7146bbfc0a07c503dfe48ec57dcc60",
        "tree": "cf5ae280c3488d41f5c6bfac95224d6d1fae784d",
    },
    "blocker/overlay-v7": {
        "commit": "6fa3c01b3d7146bbfc0a07c503dfe48ec57dcc60",
        "tree": "cf5ae280c3488d41f5c6bfac95224d6d1fae784d",
    },
}
REQUIRED_RELEVANT_PATHS = [
    "commands/sdlc-init.md",
    "scripts/activation_planner.py",
    "scripts/instruction_generator.py",
    "tests/test_activation_planner.py",
    "tests/test_instruction_generator.py",
]
REQUIRED_CANDIDATE_BYTES = {
    "commands/sdlc-init.md": "7c22893de63a213e3704c08f2246443a5d0ebe14",
    "scripts/activation_planner.py": "de39b9e4c6479f4b9ea95eb0d98b9feed387a79e",
    "scripts/instruction_generator.py": "7c22893de63a213e3704c08f2246443a5d0ebe14",
    "tests/test_activation_planner.py": "de39b9e4c6479f4b9ea95eb0d98b9feed387a79e",
    "tests/test_instruction_generator.py": "7c22893de63a213e3704c08f2246443a5d0ebe14",
}
REQUIRED_TEST_LOCATORS = {
    ("tests/test_activation_planner.py", "tracked-at-assessed-head"),
    ("tests/test_instruction_generator.py", "tracked-at-assessed-head"),
    (SELF, "new-uncommitted-working-tree-verifier"),
}
REQUIRED_DEFERRED = ["archive", "V7", "gateway", "DRIVE", "unknown", "dirty", "unreviewable-bytes"]
REQUIRED_FORBIDDEN_EFFECTS = [
    "integration",
    "activation",
    "trust/config mutation",
    "inference",
    "push",
    "PR mutation",
    "release",
    "deployment",
]
TOP_LEVEL_KEYS = {
    "record",
    "candidate_commits",
    "frozen_refs",
    "candidate_bytes",
    "relevant_paths",
    "tests",
    "disposition",
    "deferred",
    "authority_boundaries",
}
RECORD_KEYS = {"kind", "date", "tranche_id", "status", "release_branch", "assessed_head"}
ASSESSED_HEAD_KEYS = {"commit", "tree"}
CANDIDATE_COMMIT_KEYS = {"commit", "tree", "role"}
FROZEN_REF_KEYS = {"ref", "commit", "tree"}
CANDIDATE_BYTES_KEYS = {"path", "source_commit", "source_blob", "head_blob"}
TEST_KEYS = {"path", "classification"}
DISPOSITION_KEYS = {
    "promotion_required",
    "candidate_activation_bytes_already_present",
    "frozen_refs_contribute_no_relevant_delta",
    "summary",
}
AUTHORITY_BOUNDARY_KEYS = {"status", "forbidden_effects", "blocked_follow_on"}


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def git(*args: str, expect_failure: bool = False) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "--git-dir",
            str(GIT_DIR),
            "--work-tree",
            str(ROOT),
            *args,
        ],
        cwd=ROOT,
        env=env,
        check=not expect_failure,
        capture_output=True,
        text=True,
    )
    if expect_failure:
        if result.returncode == 0:
            raise AssertionError(f"expected git failure for {args!r}")
        return result.stdout.strip()
    return result.stdout.strip()


def assert_exact_keys(test: unittest.TestCase, value: object, expected: set[str]) -> None:
    test.assertIsInstance(value, dict)
    test.assertEqual(set(value), expected)


def valid_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        return False
    if ":" in value or value.startswith("-") or any(char in value for char in "*?[]!^"):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def _custody_objects_present() -> bool:
    """Whether this checkout holds the local-only objects the attestation names.

    The assessed commit, the candidate commits, and the five frozen `*-v7` refs were never
    pushed (`git ls-remote --heads origin` lists none of them), so a fresh clone and CI cannot
    see them. Verifying custody there is impossible, not failing — so those checks skip rather
    than error. The record's shape, its internal consistency, and its authority boundaries are
    still verified everywhere, because those are properties of the file, not of the object store.
    """
    if not GIT_DIR.is_dir() or GIT_DIR.is_symlink():
        return False
    refs = [f"refs/heads/{ref}" for ref in REQUIRED_FROZEN_REFS]
    for name in (ASSESSED_HEAD_COMMIT, f"refs/heads/{ASSESSED_RELEASE_BRANCH}", *refs):
        try:
            git("rev-parse", "--verify", name)
        except subprocess.CalledProcessError:
            return False
    return True


CUSTODY_OBJECTS_PRESENT = _custody_objects_present()
CUSTODY_SKIP_REASON = (
    "custody objects are local-only (assessed commit, candidate commits, and the frozen *-v7 "
    "refs were never pushed), so this checkout cannot verify them"
)


class PrimeCandidateCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(
            RECORD.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
        cls.head = cls.record["record"]["assessed_head"]

    def test_record_shape_and_immutable_objects(self) -> None:
        assert_exact_keys(self, self.record, TOP_LEVEL_KEYS)
        record = self.record["record"]
        assert_exact_keys(self, record, RECORD_KEYS)
        assert_exact_keys(self, record["assessed_head"], ASSESSED_HEAD_KEYS)
        self.assertEqual(record["kind"], "prime-candidate-custody")
        self.assertEqual(record["release_branch"], ASSESSED_RELEASE_BRANCH)
        self.assertEqual(record["tranche_id"], "agentic-sdlc-p1")
        self.assertEqual(record["date"], "2026-07-21")
        self.assertEqual(record["status"], "non-authorizing")
        self.assertEqual(record["assessed_head"]["commit"], ASSESSED_HEAD_COMMIT)
        self.assertEqual(record["assessed_head"]["tree"], ASSESSED_HEAD_TREE)

    @unittest.skipUnless(CUSTODY_OBJECTS_PRESENT, CUSTODY_SKIP_REASON)
    def test_assessed_objects_are_immutable_and_still_reachable(self) -> None:
        # The record is a dated attestation about one commit, so it is verified against that
        # commit by name. Asserting HEAD still equals it would make the record expire on the
        # next commit, which is not what custody means.
        self.assertEqual(git("cat-file", "-t", ASSESSED_HEAD_COMMIT), "commit")
        self.assertEqual(git("rev-parse", f"{ASSESSED_HEAD_COMMIT}^{{tree}}"), ASSESSED_HEAD_TREE)
        release_ref = f"refs/heads/{ASSESSED_RELEASE_BRANCH}"
        git("symbolic-ref", "--quiet", release_ref, expect_failure=True)
        self.assertEqual(git("cat-file", "-t", release_ref), "commit")
        # The durable safety property: the assessed custody point is still contained in the
        # release line rather than orphaned by a reset or a force-push.
        git("merge-base", "--is-ancestor", ASSESSED_HEAD_COMMIT, release_ref)

        candidate_items = self.record["candidate_commits"]
        self.assertIsInstance(candidate_items, list)
        candidate_commits = [item["commit"] for item in candidate_items]
        self.assertEqual(len(candidate_commits), len(set(candidate_commits)))
        self.assertEqual(set(candidate_commits), set(REQUIRED_CANDIDATE_COMMITS))
        for item in candidate_items:
            assert_exact_keys(self, item, CANDIDATE_COMMIT_KEYS)
            expected = REQUIRED_CANDIDATE_COMMITS[item["commit"]]
            self.assertEqual(item["tree"], expected["tree"])
            self.assertEqual(item["role"], expected["role"])
            self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(item["tree"], r"^[0-9a-f]{40}$")
            self.assertEqual(git("cat-file", "-t", item["commit"]), "commit")
            self.assertEqual(git("rev-parse", f"{item['commit']}^{{commit}}"), item["commit"])
            self.assertEqual(git("rev-parse", f"{item['commit']}^{{tree}}"), item["tree"])
            git("merge-base", "--is-ancestor", item["commit"], ASSESSED_HEAD_COMMIT)

        frozen_items = self.record["frozen_refs"]
        self.assertIsInstance(frozen_items, list)
        frozen_refs = [item["ref"] for item in frozen_items]
        self.assertEqual(len(frozen_refs), len(set(frozen_refs)))
        self.assertEqual(set(frozen_refs), set(REQUIRED_FROZEN_REFS))
        for item in frozen_items:
            assert_exact_keys(self, item, FROZEN_REF_KEYS)
            expected = REQUIRED_FROZEN_REFS[item["ref"]]
            self.assertEqual(item["commit"], expected["commit"])
            self.assertEqual(item["tree"], expected["tree"])
            self.assertTrue(valid_path(item["ref"]))
            direct_ref = f"refs/heads/{item['ref']}"
            git("symbolic-ref", "--quiet", direct_ref, expect_failure=True)
            self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(git("rev-parse", "--verify", direct_ref), item["commit"])
            self.assertEqual(git("cat-file", "-t", direct_ref), "commit")
            self.assertEqual(git("rev-parse", "--verify", f"{direct_ref}^{{commit}}"), item["commit"])
            self.assertEqual(git("rev-parse", "--verify", f"{direct_ref}^{{tree}}"), item["tree"])

    @unittest.skipUnless(CUSTODY_OBJECTS_PRESENT, CUSTODY_SKIP_REASON)
    def test_candidate_blobs_are_present_at_head(self) -> None:
        items = self.record["candidate_bytes"]
        self.assertIsInstance(items, list)
        paths = [item["path"] for item in items]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(set(paths), set(REQUIRED_CANDIDATE_BYTES))
        for item in items:
            assert_exact_keys(self, item, CANDIDATE_BYTES_KEYS)
            self.assertEqual(item["source_commit"], REQUIRED_CANDIDATE_BYTES[item["path"]])
            self.assertTrue(valid_path(item["path"]))
            self.assertEqual(
                git("rev-parse", f"{item['source_commit']}:{item['path']}"), item["source_blob"]
            )
            self.assertEqual(git("rev-parse", f"{ASSESSED_HEAD_COMMIT}:{item['path']}"), item["head_blob"])
            self.assertEqual(item["source_blob"], item["head_blob"])

    @unittest.skipUnless(CUSTODY_OBJECTS_PRESENT, CUSTODY_SKIP_REASON)
    def test_frozen_refs_have_no_relevant_delta(self) -> None:
        paths = self.record["relevant_paths"]
        self.assertIsInstance(paths, list)
        self.assertEqual(paths, REQUIRED_RELEVANT_PATHS)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(paths)
        self.assertTrue(all(valid_path(path) for path in paths))
        for item in self.record["frozen_refs"]:
            direct_ref = f"refs/heads/{item['ref']}"
            git("symbolic-ref", "--quiet", direct_ref, expect_failure=True)
            self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(git("rev-parse", "--verify", direct_ref), item["commit"])
            self.assertEqual(git("cat-file", "-t", direct_ref), "commit")
            git("--literal-pathspecs", "diff", "--quiet", "--exit-code", direct_ref, ASSESSED_HEAD_COMMIT, "--", *paths)

    def test_test_locators_and_disposition_boundaries(self) -> None:
        self.assertIsInstance(self.record["tests"], list)
        locators = [(item["path"], item["classification"]) for item in self.record["tests"]]
        self.assertEqual(len(locators), len(set(locators)))
        self.assertEqual(set(locators), REQUIRED_TEST_LOCATORS)
        self.assertEqual(len(locators), len(REQUIRED_TEST_LOCATORS))
        for item in self.record["tests"]:
            assert_exact_keys(self, item, TEST_KEYS)
            self.assertTrue(valid_path(item["path"]))
            if not CUSTODY_OBJECTS_PRESENT:
                continue
            if item["path"] == SELF:
                self.assertEqual(item["classification"], "new-uncommitted-working-tree-verifier")
                self.assertTrue((ROOT / item["path"]).is_file())
                with self.assertRaises(subprocess.CalledProcessError):
                    git("cat-file", "-e", f"{ASSESSED_HEAD_COMMIT}:{item['path']}")
            else:
                self.assertEqual(item["classification"], "tracked-at-assessed-head")
                git("cat-file", "-e", f"{ASSESSED_HEAD_COMMIT}:{item['path']}")

        disposition = self.record["disposition"]
        assert_exact_keys(self, disposition, DISPOSITION_KEYS)
        self.assertIs(type(disposition["promotion_required"]), bool)
        self.assertIs(disposition["promotion_required"], False)
        self.assertIs(type(disposition["candidate_activation_bytes_already_present"]), bool)
        self.assertIs(disposition["candidate_activation_bytes_already_present"], True)
        self.assertIs(type(disposition["frozen_refs_contribute_no_relevant_delta"]), bool)
        self.assertIs(disposition["frozen_refs_contribute_no_relevant_delta"], True)
        self.assertEqual(disposition["summary"], "No promotion required; candidate activation bytes already present; frozen refs contribute no relevant delta.")
        self.assertEqual(self.record["deferred"], REQUIRED_DEFERRED)
        boundaries = self.record["authority_boundaries"]
        assert_exact_keys(self, boundaries, AUTHORITY_BOUNDARY_KEYS)
        self.assertEqual(boundaries["status"], "custody/review/gates/Seeds are evidence only and non-authorizing")
        self.assertEqual(boundaries["forbidden_effects"], REQUIRED_FORBIDDEN_EFFECTS)
        self.assertEqual(boundaries["blocked_follow_on"], "P2/P3 stay blocked pending P1 acceptance/reconciliation")


if __name__ == "__main__":
    unittest.main()
