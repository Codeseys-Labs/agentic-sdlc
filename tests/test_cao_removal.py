from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from shutil import ignore_patterns

ROOT = Path(__file__).parents[1]
SELF = Path(__file__).name  # "test_cao_removal.py"


def retype_directory_symlinks(root: Path) -> None:
    """Restore symlink types after a copytree on Windows (same helper as test_gate_graph).

    `shutil.copytree(symlinks=True)` recreates every symlink without `target_is_directory`, so
    on Windows a copied directory link lands as a FILE-type link and every later stat through it
    answers WinError 5. POSIX symlinks carry no type: no-op there. The tracked `plugin/*` links
    this was written for are gone (agentic-sdlc-d0ab), so it retypes nothing in a clean checkout
    and stays only for an untracked link in a copied working tree.
    """
    if os.name != "nt":
        return
    for directory, directories, filenames in os.walk(root):
        for name in (*directories, *filenames):
            link = Path(directory) / name
            if not link.is_symlink():
                continue
            target = os.readlink(str(link))
            if (Path(directory) / target).is_dir():
                link.unlink()
                link.symlink_to(target, target_is_directory=True)

# Categories from the removal contract: CAO-named path, INSTALL_CAO flag,
# executable reference, profile, install path, and runtime command. The private
# denylist below is the single source of truth for "what counts as a CAO
# surface"; the shipped tree must contain none of it.
CAO_COMMAND = re.compile(r"\b(?:cao|cao-server)\s+[a-z][a-z0-9_-]*\b")  # runtime command
CAO_TOKEN = re.compile(r"(?i)\bcao\b")  # profile / name / prose claim / bare token
INSTALL_FLAG = "INSTALL_CAO"  # flag (no allowlist now)
INSTALL_KIT = "install-cao-kit"  # executable / install-path reference


def scan_for_cao(root: Path) -> list[str]:
    """Return CAO-surface violations under ``root``.

    Skips ``.git``, ``__pycache__``, and the entire ``tests/`` tree: the private
    denylist itself (this file plus focused negative fixtures) must be free to
    name CAO to prevent regression. Paths are reported POSIX-style so the
    substrings are stable across platforms.
    """
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or "tests" in rel.parts:
            continue
        # Vendored/installed dependency trees and harness worktrees are not this commit's
        # shipped surface; scanning them reports other packages' or other commits' bytes.
        if "node_modules" in rel.parts or ".worktrees" in rel.parts or ".claude" in rel.parts:
            continue
        rel_posix = rel.as_posix()
        # (a) CAO-named path / profile dir / install path.
        if "cao" in path.name.lower() or "cao-profiles" in rel.parts:
            violations.append(f"cao-named path: {rel_posix}")
        # (b) content-based surfaces.
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if CAO_COMMAND.search(text):
            violations.append(f"cao runtime command: {rel_posix}")
        if INSTALL_FLAG in text:
            violations.append(f"INSTALL_CAO flag: {rel_posix}")
        if INSTALL_KIT in text:
            violations.append(f"install-cao-kit reference: {rel_posix}")
        if CAO_TOKEN.search(text):
            violations.append(f"cao token: {rel_posix}")
    return violations


class CaoRemovalContract(unittest.TestCase):
    """Negative removed-surface contract for CAO (replaces the tombstone tests).

    Positive: the shipped tree contains zero CAO surfaces. Negative: each
    forbidden surface class, planted into a throwaway copy, is rejected by the
    denylist scanner.
    """

    def plant_and_scan(
        self,
        rel_path: str,
        *,
        content: str | None = None,
        append: str | None = None,
    ) -> list[str]:
        """Copy ROOT to a temp dir, plant exactly one surface, return violations."""
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            shutil.copytree(
                ROOT, repo, symlinks=True, ignore=ignore_patterns(".git", "__pycache__")
            )
            retype_directory_symlinks(repo)
            target = repo / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if append is not None:
                existing = target.read_text(encoding="utf-8") if target.exists() else ""
                target.write_text(existing + append, encoding="utf-8")
            else:
                target.write_text(content if content is not None else "", encoding="utf-8")
            return scan_for_cao(repo)

    def test_shipped_tree_has_no_cao_surface(self) -> None:
        """RED until every CAO surface is deleted/rewritten; GREEN thereafter."""
        self.assertEqual(scan_for_cao(ROOT), [])

    def test_denylist_flags_cao_named_paths(self) -> None:
        cases = (
            # (rel_path, content, expected violation substring)
            ("scripts/cao-helper.sh", "#!/usr/bin/env bash\necho hi\n",
             "cao-named path: scripts/cao-helper.sh"),
            ("cao-profiles/codex-planner.md", "placeholder\n",
             "cao-named path: cao-profiles/codex-planner.md"),
            ("skills/agentic-sdlc/references/cao-operations.md", "placeholder\n",
             "cao-named path: skills/agentic-sdlc/references/cao-operations.md"),
        )
        for rel_path, content, expected in cases:
            with self.subTest(plant=rel_path):
                violations = self.plant_and_scan(rel_path, content=content)
                self.assertIn(expected, violations)

    def test_denylist_flags_install_cao_kit_recreation(self) -> None:
        # Recreating the executable itself trips the path detector on its name.
        # The distinct content-reference detector is proven separately by
        # test_denylist_flags_install_kit_reference.
        rel_path = "scripts/install-cao-kit.sh"
        violations = self.plant_and_scan(
            rel_path, content="#!/usr/bin/env bash\nexit 2\n"
        )
        self.assertIn(f"cao-named path: {rel_path}", violations)

    def test_denylist_flags_install_kit_reference(self) -> None:
        rel_path = "skills/agentic-sdlc/SKILL.md"
        violations = self.plant_and_scan(
            rel_path, append="\n- `<repo>/scripts/install-cao-kit.sh` (retained)\n"
        )
        self.assertIn(f"install-cao-kit reference: {rel_path}", violations)

    def test_denylist_flags_install_cao_flag(self) -> None:
        rel_path = "README.md"
        violations = self.plant_and_scan(
            rel_path, append="\nINSTALL_CAO=1 ./scripts/install-skill-bundle.sh\n"
        )
        self.assertIn(f"INSTALL_CAO flag: {rel_path}", violations)

    def test_denylist_flags_runtime_commands(self) -> None:
        # Case 6 plus the old test's mutation vectors, now asserting the scanner
        # reports a violation rather than the validator exiting 1.
        mutations = (
            ("README.md", "cao install arbitrary-profile"),
            ("mise.toml", "cao status"),
            ("lefthook.yml", "sudo cao doctor"),
            ("docs/guide.md", "$ cao status"),
            ("docs/guide.rst", "cao exec worker"),
            ("config/tool.ini", "command=cao-server start"),
            ("Makefile", "run:\n\tcao status"),
        )
        for rel_path, command in mutations:
            with self.subTest(plant=rel_path, command=command):
                violations = self.plant_and_scan(rel_path, append=f"\n{command}\n")
                self.assertIn(f"cao runtime command: {rel_path}", violations)

    def test_denylist_flags_bare_cao_token(self) -> None:
        rel_path = "docs/guide.md"
        violations = self.plant_and_scan(rel_path, append="\nCAO is back.\n")
        self.assertIn(f"cao token: {rel_path}", violations)

    def test_planting_does_not_touch_real_tree(self) -> None:
        """Every plant happens in a temp copy; the source tree is never mutated."""
        before = scan_for_cao(ROOT)
        self.plant_and_scan("scripts/cao-helper.sh", content="noop\n")
        self.plant_and_scan("README.md", append="\nINSTALL_CAO=1 x\n")
        self.plant_and_scan("mise.toml", append="\ncao status\n")
        after = scan_for_cao(ROOT)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
