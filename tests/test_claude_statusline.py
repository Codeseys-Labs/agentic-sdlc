from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "assets" / "claude" / "statusline-command.sh"
BASH = shutil.which("bash")

# Every other test here reads only the script's own rendered text, so the shell it runs under is
# the only thing that has to work. This one is the exception: it asserts that a directory the
# SHELL created under a Windows-form `XDG_CACHE_HOME` is visible again at a Python-computed path,
# so a `C:\...` path has to survive a round trip through a POSIX shell asset. Measured on
# windows-2025 (CI run 32774680436, agentic-sdlc-5ce7) the agent segment never rendered at all:
# `'agents' not found in '...C:UsersRUNNER~1AppDataLocalTemptmp1d1i4opr...'`. Which step of that
# round trip breaks is not decidable without a Windows shell, and native Windows statusline
# activation is uncertified per AGENTS.md, so this claim is not gated on that host.
SHELL_PATH_ROUNDTRIP_SKIP_REASON = (
    "this claim needs a Windows-form path to round-trip from Python through the POSIX statusline "
    "asset and back; native Windows statusline activation is uncertified (AGENTS.md) and the "
    "failing step is not decidable without a Windows shell (agentic-sdlc-5ce7)"
)


@unittest.skipUnless(BASH and shutil.which("jq"), "bash and jq are required")
class ClaudeStatuslineTests(unittest.TestCase):
    def render(self, payload: object, *, cwd: Path, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = {
            "HOME": str(cwd / "home"),
            "PATH": os.environ.get("PATH", ""),
            "XDG_CACHE_HOME": str(cwd / "cache"),
        }
        env.update(environment or {})
        return subprocess.run(
            [BASH, str(SCRIPT)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env,
            check=False,
        )

    def test_sparse_input_renders_without_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.render({"cwd": temp}, cwd=Path(temp))

        self.assertEqual(result.returncode, 0)
        self.assertIn("in", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_complete_input_preserves_major_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = {
                "workspace": {"project_dir": temp},
                "model": {"id": "global.anthropic.claude-opus-5[1m]"},
                "effort": {"level": "xhigh"},
                "context_window": {
                    "total_input_tokens": 12345,
                    "total_output_tokens": 2345,
                    "used_percentage": 75,
                    "context_window_size": 1_000_000,
                    "current_usage": {
                        "input_tokens": 1000,
                        "cache_creation_input_tokens": 50,
                        "cache_read_input_tokens": 9000,
                    },
                },
                "cost": {"total_cost_usd": 1.25, "total_duration_ms": 72000},
                "rate_limits": {
                    "five_hour": {"used_percentage": 40},
                    "seven_day": {"used_percentage": 80},
                },
                "output_style": {"name": "bluf"},
            }
            result = self.render(payload, cwd=root)

        for text in ("opus", "xhigh", "75%", "12.3k", "cache", "$1.25", "1m", "5h", "7d", "[bluf]"):
            self.assertIn(text, result.stdout)
        self.assertEqual(result.stderr, "")

    def test_malformed_input_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = subprocess.run(
                [BASH, str(SCRIPT)],
                input="not-json",
                text=True,
                capture_output=True,
                cwd=root,
                env={"HOME": str(root / "home"), "PATH": os.environ.get("PATH", "")},
                check=False,
            )

        self.assertEqual(result.stdout, "claude\n")
        self.assertEqual(result.stderr, "")

    def test_terminal_control_text_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = {
                "cwd": temp,
                "model": {"id": "model\\033[31m]0;owned"},
                "output_style": {"name": "style\\n[2J"},
            }
            result = self.render(payload, cwd=Path(temp))

        self.assertNotIn("\\033", result.stdout)
        self.assertNotIn("\x1b]0;owned", result.stdout)
        self.assertNotIn("\x1b[2J", result.stdout)
        self.assertEqual(result.stderr, "")

    @unittest.skipIf(os.name == "nt", SHELL_PATH_ROUNDTRIP_SKIP_REASON)
    def test_subagent_cost_cache_stays_below_xdg_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transcript = root / "session.jsonl"
            agent_dir = root / "session" / "subagents" / "worker"
            agent_dir.mkdir(parents=True)
            transcript.write_text("")
            (agent_dir / "agent-1.jsonl").write_text(
                json.dumps(
                    {
                        "message": {
                            "id": "m1",
                            "model": "claude-opus-5",
                            "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
                        }
                    }
                )
                + "\n"
            )
            legacy_tmp_before = {
                path: path.stat().st_mtime_ns
                for path in Path("/tmp").glob("statusline-agentcost-*")
            }
            result = self.render(
                {"cwd": temp, "transcript_path": str(transcript)}, cwd=root
            )

            cache_root = root / "cache" / "agentic-sdlc" / "statusline"
            self.assertIn("agents", result.stdout)
            self.assertTrue(any(cache_root.iterdir()))
            self.assertEqual(
                {
                    path: path.stat().st_mtime_ns
                    for path in Path("/tmp").glob("statusline-agentcost-*")
                },
                legacy_tmp_before,
            )


if __name__ == "__main__":
    unittest.main()
