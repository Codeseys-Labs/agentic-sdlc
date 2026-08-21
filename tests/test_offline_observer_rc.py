from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "scripts" / "install_skill_bundle.py"
OBSERVER = ROOT / "skills" / "agentic-sdlc" / "tools" / "offline-inspect.py"
GIT = Path(subprocess.check_output(["sh", "-c", "command -v git"], text=True).strip()) if os.name != "nt" else None

# The observer's exit classes, RE-EXPRESSED from product-spec Implementation Decision 9 rather than
# imported from the module under test, so a table the observer quietly renumbers fails here instead
# of agreeing with itself.
#: Reserved by Decision 9; 3 and 4 are unreachable for an effect-free command but stay reserved.
RESERVED_EXIT_BLOCK = (0, 1, 2, 3, 4)
#: Every item was adoptable, mergeable, or skippable.
EXIT_READY = 0
#: An unexpected internal failure. A DERIVED verdict may never land here.
EXIT_INTERNAL = 1
#: The target or the command line is unusable, so no inspection happened.
EXIT_INPUT = 2
#: The inspection RAN and named a refusal (agentic-sdlc-4253). Nonzero so a shell caller still sees a
#: signal, and outside the reserved block so it cannot be confused with a crash or a bad argument.
EXIT_NOT_READY = 5
MARKER_START = "<!-- agentic-sdlc:start -->"
MARKER_END = "<!-- agentic-sdlc:end -->"
CANONICAL_AGENTS_BODY = """## intent
Project intent for the wave.

## gate
Run `mise run check` before any commit.

## substrate
Git-worktree waves only.

## seeds
Seeds(<target>, prime|ready|blocked).

## doctrine
See skills/agentic-sdlc/SKILL.md for the doctrine."""
CANONICAL_CLAUDE_BODY = """## Claude command routing
- /sdlc-init
- /sdlc-frame
- /sdlc-wave
- /sdlc-mission"""
EXCLUDED_SURFACES = [
    "PRIME apply",
    "workflow overlay",
    "gateway",
    "routing",
    "Seeds",
    "archives",
    "V7",
    "config",
    "queue mutation",
]


def read_bytes_without_atime(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOATIME"):
        flags |= os.O_NOATIME
    descriptor = os.open(path, flags)
    try:
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def snapshot_tree(root: Path, *, include_atime: bool = False) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}

    def visit(path: Path, relative: str) -> None:
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        record: dict[str, object] = {
            "mode": mode,
            "mtime_ns": metadata.st_mtime_ns,
        }
        if include_atime and not stat.S_ISDIR(metadata.st_mode):
            record["atime_ns"] = metadata.st_atime_ns
        if stat.S_ISDIR(metadata.st_mode):
            record["type"] = "directory"
        elif stat.S_ISREG(metadata.st_mode):
            record["type"] = "file"
            record["sha256"] = hashlib.sha256(read_bytes_without_atime(path)).hexdigest()
        elif stat.S_ISLNK(metadata.st_mode):
            record["type"] = "symlink"
            record["link_text"] = os.readlink(path)
        else:
            record["type"] = "special"
        snapshot[relative] = record
        if record["type"] == "directory":
            with os.scandir(path) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
            for child in children:
                child_relative = child.name if relative == "." else f"{relative}/{child.name}"
                visit(Path(child.path), child_relative)

    visit(root, ".")
    return snapshot


def path_present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def marked_content(body: str, *, preamble: str = "") -> str:
    return f"{preamble}{MARKER_START}\n{body}\n{MARKER_END}\n"


def observe(observer: Path, target: Path, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-B", str(observer), "--target", str(target)],
        cwd=cwd,
        env={"HOME": str(cwd), "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        check=False,
    )


def item(plan: dict[str, object], item_id: str) -> dict[str, object]:
    return next(candidate for candidate in plan["items"] if candidate["id"] == item_id)


@unittest.skipIf(GIT is None, "Git is required for observer regression fixtures")
class OfflineObserverRegressionTests(unittest.TestCase):
    def test_refuses_gitfile_whose_gitdir_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-gitfile-") as temporary:
            target = Path(temporary)
            (target / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

            result = observe(OBSERVER, target, target)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, EXIT_NOT_READY, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(
                item(plan, "git-baseline"),
                {"id": "git-baseline", "action": "refuse", "reason": "invalid-git-metadata"},
            )
            self.assertEqual(
                plan["preview_readiness"],
                {"state": "NOT_READY", "reason": "git-baseline/invalid-git-metadata"},
            )

    def test_refuses_git_directory_without_minimum_structure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-gitdir-") as temporary:
            target = Path(temporary)
            (target / ".git").mkdir()

            result = observe(OBSERVER, target, target)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, EXIT_NOT_READY, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(
                item(plan, "git-baseline"),
                {"id": "git-baseline", "action": "refuse", "reason": "invalid-git-metadata"},
            )

    def test_refuses_git_directory_with_empty_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-git-head-") as temporary:
            target = Path(temporary)
            metadata = target / ".git"
            (metadata / "objects").mkdir(parents=True)
            (metadata / "refs").mkdir()
            (metadata / "HEAD").write_text("", encoding="utf-8")
            (metadata / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")

            result = observe(OBSERVER, target, target)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, EXIT_NOT_READY, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(
                item(plan, "git-baseline"),
                {"id": "git-baseline", "action": "refuse", "reason": "invalid-git-metadata"},
            )

    def test_adopts_valid_linked_worktree_gitfile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-worktree-") as temporary:
            root = Path(temporary)
            repository = root / "repository"
            linked = root / "linked"
            repository.mkdir()
            initialized = subprocess.run(
                [str(GIT), "-C", str(repository), "init", "--quiet"],
                env={"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(root), "PATH": os.defpath},
                capture_output=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr.decode("utf-8", "replace"))
            created = subprocess.run(
                [str(GIT), "-C", str(repository), "worktree", "add", "--quiet", "--orphan", str(linked)],
                env={"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(root), "PATH": os.defpath},
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr.decode("utf-8", "replace"))

            result = observe(OBSERVER, linked, root)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(item(plan, "git-baseline")["action"], "adopt")

    def test_adopts_only_canonical_instruction_content_and_claude_preamble(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-instructions-") as temporary:
            target = Path(temporary)
            (target / "AGENTS.md").write_text(marked_content(CANONICAL_AGENTS_BODY), encoding="utf-8")
            (target / "CLAUDE.md").write_text(
                marked_content(CANONICAL_CLAUDE_BODY, preamble="@AGENTS.md\n\n"), encoding="utf-8"
            )

            result = observe(OBSERVER, target, target)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(item(plan, "instructions:AGENTS.md")["action"], "adopt")
            self.assertEqual(item(plan, "instructions:CLAUDE.md")["action"], "adopt")

    def test_marks_stale_bodies_and_wrong_claude_preamble_for_merge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-stale-") as temporary:
            target = Path(temporary)
            (target / "AGENTS.md").write_text(marked_content("stale"), encoding="utf-8")
            (target / "CLAUDE.md").write_text(
                marked_content("stale", preamble="@WRONG.md\n\n"), encoding="utf-8"
            )

            result = observe(OBSERVER, target, target)
            plan = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(item(plan, "instructions:AGENTS.md")["action"], "merge")
            self.assertEqual(item(plan, "instructions:CLAUDE.md")["action"], "merge")

    @unittest.skipUnless(hasattr(os, "O_NOATIME"), "O_NOATIME is required for zero-atime proof")
    def test_instruction_reads_preserve_access_times(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-atime-") as temporary:
            target = Path(temporary)
            agents = target / "AGENTS.md"
            claude = target / "CLAUDE.md"
            agents.write_text(marked_content(CANONICAL_AGENTS_BODY), encoding="utf-8")
            claude.write_text(
                marked_content(CANONICAL_CLAUDE_BODY, preamble="@AGENTS.md\n\n"), encoding="utf-8"
            )
            old_atime_ns = 946684800_000_000_000
            for path in (agents, claude):
                os.utime(path, ns=(old_atime_ns, path.stat().st_mtime_ns))
            before = snapshot_tree(target, include_atime=True)

            result = observe(OBSERVER, target, target)
            after = snapshot_tree(target, include_atime=True)

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(after, before)


@unittest.skipIf(GIT is None, "Git is required for the brownfield acceptance fixture")
class OfflineObserverReleaseCandidateTests(unittest.TestCase):
    def test_copy_install_status_observe_and_uninstall_is_deterministic_and_read_only(self) -> None:
        self.assertTrue(Path(sys.executable).is_absolute())
        with tempfile.TemporaryDirectory(prefix="offline-observer-rc-") as temporary:
            root = Path(temporary)
            home = root / "home"
            codex_home = root / "codex-home"
            state_home = root / "state"
            foreign = {
                home / ".claude" / "settings.json": b'{"foreign":true}\n',
                home / ".claude" / "skills" / "foreign" / "SKILL.md": b"foreign claude skill\n",
                home / ".claude" / "agents" / "foreign.md": b"foreign claude agent\n",
                home / ".claude" / "commands" / "foreign.md": b"foreign claude command\n",
                codex_home / "config.toml": b"foreign = true\n",
                codex_home / "skills" / "foreign" / "SKILL.md": b"foreign codex skill\n",
                codex_home / "agents" / "foreign.toml": b"foreign = true\n",
                codex_home / "commands" / "foreign.md": b"foreign codex command\n",
            }
            for path, content in foreign.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            lifecycle_environment = {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home),
                "XDG_STATE_HOME": str(state_home),
                "LOCALAPPDATA": str(state_home),
                "PATH": "",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            def lifecycle(command: str) -> subprocess.CompletedProcess[bytes]:
                return subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(INSTALLER),
                        command,
                        "--mode",
                        "copy",
                        "--home",
                        str(home),
                        "--codex-home",
                        str(codex_home),
                    ],
                    cwd=ROOT,
                    env=lifecycle_environment,
                    capture_output=True,
                    check=False,
                )

            installed = lifecycle("install")
            self.assertEqual(installed.returncode, 0, installed.stderr.decode("utf-8", "replace"))
            claude_observer = home / ".claude" / "skills" / "agentic-sdlc" / "tools" / "offline-inspect.py"
            codex_observer = codex_home / "skills" / "agentic-sdlc" / "tools" / "offline-inspect.py"
            self.assertTrue(claude_observer.is_file())
            self.assertEqual(claude_observer.read_bytes(), codex_observer.read_bytes())

            state_file = state_home / "agentic-sdlc-installer" / "state.json"
            installed_state = json.loads(state_file.read_text(encoding="utf-8"))
            managed_paths = [
                Path(destination)
                for destination, record in installed_state["entries"].items()
                if record["removable"]
            ]
            before_status = snapshot_tree(root)
            checked = lifecycle("status")
            after_status = snapshot_tree(root)
            self.assertEqual(checked.returncode, 0, checked.stderr.decode("utf-8", "replace"))
            self.assertEqual(after_status, before_status)

            greenfield = root / "greenfield"
            greenfield.mkdir()
            brownfield = root / "brownfield"
            brownfield.mkdir()
            (brownfield / "AGENTS.md").write_text("Foreign project guidance.\n", encoding="utf-8")
            (brownfield / "CLAUDE.md").write_text(
                f"{MARKER_START}\nmissing closing marker\n", encoding="utf-8"
            )
            (brownfield / "config").mkdir()
            (brownfield / "config" / "app.json").write_bytes(b'{"mode":"foreign"}\n')
            (brownfield / ".seeds").mkdir()
            (brownfield / ".seeds" / "state.json").write_bytes(b'{"state":"foreign"}\n')
            (brownfield / "queue").mkdir()
            (brownfield / "queue" / "pending.json").write_bytes(b'{"queue":"foreign"}\n')

            git_environment = {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(home),
                "LC_ALL": "C",
                "PATH": os.defpath,
            }

            def git(*arguments: str) -> bytes:
                result = subprocess.run(
                    [str(GIT), "-C", str(brownfield), *arguments],
                    env=git_environment,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                return result.stdout

            git("init", "--quiet")
            git("config", "user.name", "Offline Observer Fixture")
            git("config", "user.email", "offline-observer@example.invalid")
            git("config", "observer.fixture", "true")
            git("add", "--all")
            git("commit", "--quiet", "-m", "brownfield fixture")

            git_state_before = {
                "head": git("rev-parse", "HEAD"),
                "status": git("status", "--porcelain=v1", "--untracked-files=all"),
                "config": git("config", "--local", "--list", "--null"),
            }
            target_before = {
                "greenfield": snapshot_tree(greenfield, include_atime=True),
                "brownfield": snapshot_tree(brownfield, include_atime=True),
            }
            observer_environment = {
                "HOME": str(home),
                "PATH": "",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            def observe(target: Path) -> subprocess.CompletedProcess[bytes]:
                return subprocess.run(
                    [sys.executable, "-B", str(claude_observer), "--target", str(target)],
                    cwd=root,
                    env=observer_environment,
                    capture_output=True,
                    check=False,
                )

            green_first = observe(greenfield)
            green_second = observe(greenfield)
            brown_first = observe(brownfield)
            brown_second = observe(brownfield)
            self.assertEqual(green_first.stdout, green_second.stdout)
            self.assertEqual(green_first.stderr, green_second.stderr)
            self.assertEqual(brown_first.stdout, brown_second.stdout)
            self.assertEqual(brown_first.stderr, brown_second.stderr)
            self.assertEqual(green_first.returncode, EXIT_READY, green_first.stderr.decode("utf-8", "replace"))
            self.assertEqual(brown_first.returncode, EXIT_NOT_READY, brown_first.stderr.decode("utf-8", "replace"))
            self.assertEqual(green_first.stderr, b"")
            self.assertEqual(brown_first.stderr, b"")

            green_plan = json.loads(green_first.stdout)
            brown_plan = json.loads(brown_first.stdout)
            self.assertEqual(green_plan["schema"], "agentic-sdlc/offline-inspect@1")
            self.assertEqual(brown_plan["schema"], "agentic-sdlc/offline-inspect@1")
            self.assertEqual(
                [(item["id"], item["action"]) for item in green_plan["items"]],
                [
                    ("git-baseline", "create"),
                    ("instructions:AGENTS.md", "create"),
                    ("instructions:CLAUDE.md", "create"),
                    ("excluded-surfaces", "skip"),
                ],
            )
            self.assertEqual(
                [(item["id"], item["action"]) for item in brown_plan["items"]],
                [
                    ("git-baseline", "adopt"),
                    ("instructions:AGENTS.md", "merge"),
                    ("instructions:CLAUDE.md", "refuse"),
                    ("excluded-surfaces", "skip"),
                ],
            )
            self.assertEqual(
                green_plan["preview_readiness"],
                {"state": "READY", "reason": "no_refusals"},
            )
            self.assertEqual(
                brown_plan["preview_readiness"],
                {
                    "state": "NOT_READY",
                    "reason": "instructions:CLAUDE.md/malformed-marker",
                },
            )
            self.assertEqual(
                green_plan["items"][-1],
                {"id": "excluded-surfaces", "action": "skip", "scope": EXCLUDED_SURFACES},
            )
            self.assertEqual(brown_plan["items"][-1], green_plan["items"][-1])

            target_after = {
                "greenfield": snapshot_tree(greenfield, include_atime=True),
                "brownfield": snapshot_tree(brownfield, include_atime=True),
            }
            git_state_after = {
                "head": git("rev-parse", "HEAD"),
                "status": git("status", "--porcelain=v1", "--untracked-files=all"),
                "config": git("config", "--local", "--list", "--null"),
            }
            self.assertEqual(target_after, target_before)
            self.assertEqual(git_state_after, git_state_before)

            removed = lifecycle("uninstall")
            self.assertEqual(removed.returncode, 0, removed.stderr.decode("utf-8", "replace"))
            for managed_path in managed_paths:
                self.assertFalse(path_present(managed_path), str(managed_path))
            for path, content in foreign.items():
                self.assertEqual(path.read_bytes(), content, str(path))


@unittest.skipIf(GIT is None, "Git is required for observer regression fixtures")
class OfflineObserverExitClassTests(unittest.TestCase):
    """The observer's exit classes must be DISTINGUISHABLE, not merely individually asserted.

    Seed agentic-sdlc-4253. Before this, a derived `NOT_READY` verdict and an unexpected internal
    failure both exited 1, so a caller reading only `$?` could not tell "I inspected the target and
    it is not ready" from "I crashed". Each check below pairs its claim with a POSITIVE CONTROL run
    through the same comparison, so none of them can pass by the comparison being vacuous.
    """

    def test_not_ready_verdict_is_outside_the_reserved_block(self) -> None:
        # Binds this module's re-expressed constants to each other only; a production renumber is
        # caught by the exit-value tests above, which drive the tool and read $? directly.
        self.assertNotIn(EXIT_NOT_READY, RESERVED_EXIT_BLOCK)
        # Positive control for that claim: the codes the observer DOES take from the reserved block
        # are found there by the same membership test, so `assertNotIn` is not vacuously true.
        for reserved in (EXIT_READY, EXIT_INTERNAL, EXIT_INPUT):
            self.assertIn(reserved, RESERVED_EXIT_BLOCK)

    def test_three_reachable_classes_are_three_distinct_codes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-classes-") as temporary:
            root = Path(temporary)

            ready = root / "ready"
            ready.mkdir()
            (ready / "AGENTS.md").write_text(marked_content(CANONICAL_AGENTS_BODY), encoding="utf-8")
            (ready / "CLAUDE.md").write_text(
                marked_content(CANONICAL_CLAUDE_BODY, preamble="@AGENTS.md\n"), encoding="utf-8"
            )

            not_ready = root / "not-ready"
            not_ready.mkdir()
            (not_ready / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

            absent = root / "absent"

            observed = {
                "ready": observe(OBSERVER, ready, root),
                "not-ready": observe(OBSERVER, not_ready, root),
                "absent": observe(OBSERVER, absent, root),
            }
            codes = {name: result.returncode for name, result in observed.items()}

            self.assertEqual(
                codes,
                {"ready": EXIT_READY, "not-ready": EXIT_NOT_READY, "absent": EXIT_INPUT},
                {name: result.stderr.decode("utf-8", "replace") for name, result in observed.items()},
            )
            # The three codes must be three, not one repeated: this is the property the seed found
            # broken, and it fails if any future edit collapses two classes onto one code.
            self.assertEqual(len(set(codes.values())), 3, codes)
            # A DERIVED verdict may never occupy the unexpected-internal-failure code.
            self.assertNotIn(EXIT_INTERNAL, set(codes.values()))
            # Positive control: the verdicts themselves still differ, so the exit codes are reporting
            # two genuinely different inspections rather than one duplicated run.
            self.assertEqual(
                json.loads(observed["ready"].stdout)["preview_readiness"],
                {"state": "READY", "reason": "no_refusals"},
            )
            self.assertEqual(
                json.loads(observed["not-ready"].stdout)["preview_readiness"],
                {"state": "NOT_READY", "reason": "git-baseline/invalid-git-metadata"},
            )
            # An input error emits NO document at all, which is what separates 2 from 5: 5 always
            # carries the one result document, and the control above shows this check can see one.
            self.assertEqual(observed["absent"].stdout, b"")
            self.assertNotEqual(observed["not-ready"].stdout, b"")

    def test_a_not_ready_verdict_still_writes_nothing_to_the_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="offline-observer-inert-") as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            (target / ".git").write_text("gitdir: /definitely/missing\n", encoding="utf-8")

            before = snapshot_tree(target, include_atime=True)
            result = observe(OBSERVER, target, root)
            after = snapshot_tree(target, include_atime=True)

            self.assertEqual(result.returncode, EXIT_NOT_READY, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(after, before)
            # Positive control for the "nothing moved" comparison: the same comparison DOES see a
            # change when one is made, so the equality above is not vacuous.
            (target / "sentinel").write_text("x", encoding="utf-8")
            self.assertNotEqual(snapshot_tree(target, include_atime=True), before)


if __name__ == "__main__":
    unittest.main()
