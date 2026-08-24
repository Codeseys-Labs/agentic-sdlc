"""The routing reference and the skills tree must agree.

`skills/agentic-sdlc/references/routing.md` carries one moment→skill row per shipped skill
and doubles as the specification the descriptions express. A skill added, renamed, or
retired without its row — or a row naming a skill that does not exist — is exactly the
silent rot a prose table invites, so the agreement is executable rather than asserted.
The moment/symptom WORDING agreement with each description stays a review obligation;
only the row↔skill correspondence is cheap enough to pin.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "skills" / "agentic-sdlc" / "references" / "routing.md"


def _table_rows(text: str) -> list[str]:
    return re.findall(r"^\| `([a-z0-9-]+)` \|", text, re.MULTILINE)


class RoutingReferenceTests(unittest.TestCase):
    def test_every_shipped_skill_has_exactly_one_row_and_every_row_names_a_shipped_skill(self) -> None:
        self.assertTrue(ROUTING.is_file(), f"missing {ROUTING}")
        rows = _table_rows(ROUTING.read_text(encoding="utf-8"))
        self.assertTrue(rows, "routing table has no skill rows")
        self.assertEqual(len(rows), len(set(rows)), "duplicate routing rows")
        skills = sorted(
            path.name for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").is_file()
        )
        self.assertEqual(sorted(rows), skills)


if __name__ == "__main__":
    unittest.main()
