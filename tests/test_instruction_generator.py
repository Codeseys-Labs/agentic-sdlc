from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import instruction_generator as gen


MARKER = {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"}

#: The canonical tool, invoked as a subprocess so a CLI-level test observes the real process
#: exit code, stdout, and stderr rather than an in-process exception.
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "instruction-generator.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def manifest() -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@2",
        "marker": MARKER,
        "doctrine_pointer": "literal text; this is never opened",
        "outputs": [{
            "path": "AGENTS.md",
            "kind": "root_agents",
            "prefix": "# Local policy\n\n",
            "sections": [{"key": "intent", "body": "Keep this local."}],
        }],
    }


class InstructionGeneratorTests(unittest.TestCase):
    def test_render_selected_is_pure_and_does_not_dereference_pointer(self) -> None:
        calls: list[str] = []

        def reader(path: str):
            calls.append(path)
            self.assertEqual(path, "AGENTS.md")
            return {"kind": "absent", "identity": None}, None

        rendered = gen.render_selected(manifest(), "AGENTS.md", reader)
        self.assertEqual(calls, ["AGENTS.md"])
        self.assertEqual(rendered["action"], "create")
        self.assertIn("literal text; this is never opened", rendered["content"].decode())
        self.assertIn(MARKER["start"], rendered["content"].decode())

    def test_replace_preserves_foreign_text_and_exact_output_is_noop(self) -> None:
        old = b"# Foreign\n\n"

        def reader(_: str):
            return {"kind": "regular", "identity": {"placeholder": True}}, old

        first = gen.render_selected(manifest(), "AGENTS.md", reader)
        self.assertEqual(first["action"], "replace")

        def rendered_reader(_: str):
            return {"kind": "regular", "identity": {"placeholder": True}}, first["content"]

        second = gen.render_selected(manifest(), "AGENTS.md", rendered_reader)
        self.assertEqual(second["action"], "no-op")
        self.assertEqual(second["content"], first["content"])

    def test_closed_manifest_rejects_unknown_duplicate_and_bad_paths(self) -> None:
        bad = manifest()
        bad["unexpected"] = True
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)
        bad = manifest()
        bad["outputs"].append(dict(bad["outputs"][0]))
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)
        bad = manifest()
        bad["outputs"][0]["path"] = "../escape"
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)

    def test_locate_marked_block_rejects_malformed_markers(self) -> None:
        with self.assertRaises(gen.GeneratorError):
            gen.render_selected(
                manifest(), "AGENTS.md", lambda _: ({"kind": "regular", "identity": {}}, b"<!-- agentic-sdlc:start -->\n")
            )

    def test_missing_manifest_refuses_at_exit_2_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.json"
            self.assertFalse(missing.exists())
            result = _run_cli(["plan", "--manifest", str(missing), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_INPUT)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(missing), result.stderr)

    def test_malformed_manifest_still_refuses_at_exit_2(self) -> None:
        """Positive control: the pre-existing refusal path for a bad manifest stays intact."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "manifest.json"
            bad.write_text("not json", encoding="utf-8")
            result = _run_cli(["plan", "--manifest", str(bad), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_INPUT)
            self.assertEqual(result.stdout, "")
            self.assertIn("invalid canonical manifest", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_plan_cli_happy_path_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_bytes(gen._canonical(manifest()))
            result = _run_cli(["plan", "--manifest", str(manifest_path), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_OK)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema"], "agentic-sdlc/instruction-render@2")
            self.assertEqual(payload["path"], "AGENTS.md")
            self.assertEqual(payload["action"], "create")


if __name__ == "__main__":
    unittest.main()
