from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import instruction_generator as gen


MARKER = {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"}


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


if __name__ == "__main__":
    unittest.main()
