"""Acceptance tests for the advisory usage reporter (seed agentic-sdlc-12b7).

Every fixture is synthetic and lives in a temporary directory: no test reads the real
``~/.opencodex`` or ``~/.claude``. The numbered design tests
(docs/plans/2026-08-24-usage-accounting-design.md section 7) are all present, including the
mutation-proven subscription-never-priced control.
"""

from __future__ import annotations

import builtins
import contextlib
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "usage_report.py"
SPEC = importlib.util.spec_from_file_location("usage_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
usage_report = importlib.util.module_from_spec(SPEC)
sys.modules["usage_report"] = usage_report  # dataclasses resolves annotations through here
SPEC.loader.exec_module(usage_report)

NOW = "2026-08-24T12:00:00+00:00"
GOLDEN_DIR = ROOT / "tests" / "fixtures" / "usage-report"


def epoch_ms(timestamp: str) -> int:
    """The real gateway logs epoch milliseconds; fixtures mirror that shape."""
    return int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000)


def gateway_row(
    timestamp: str = "2026-08-24T10:00:00Z",
    provider: str = "anthropic-native",
    status: str = "reported",
    total: int | None = None,
    input_tokens: int = 60,
    output_tokens: int = 40,
    surface: str | None = None,
    route_kind: str | None = None,
) -> dict:
    row = {
        "requestId": "req",
        "timestamp": epoch_ms(timestamp),
        "provider": provider,
        "model": "some-model",
        "admissionKind": "loopback",
        "status": 200,
        "usageStatus": status,
    }
    if status == "reported":
        usage: dict = {"inputTokens": input_tokens, "outputTokens": output_tokens}
        if total is not None:
            usage["totalTokens"] = total
        row["usage"] = usage
    if surface is not None:
        row["surface"] = surface
    if route_kind is not None:
        row["routeDecision"] = {"routeKind": route_kind}
    return row


def transcript_row(
    timestamp: str = "2026-08-24T10:00:00Z",
    model: str = "claude-fable-5",
    session: str = "session-a",
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_creation: int = 0,
    cache_read: int = 0,
    sidechain: bool = False,
    entrypoint: str = "cli",
    content: object | None = None,
) -> dict:
    row = {
        "type": "assistant",
        "timestamp": timestamp,
        "sessionId": session,
        "isSidechain": sidechain,
        "entrypoint": entrypoint,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        },
    }
    if content is not None:
        row["message"]["content"] = content
    return row


def write_homes(
    base: Path,
    gateway_rows: list[dict] | None = None,
    gateway_raw_lines: tuple[str, ...] = (),
    transcripts: dict[str, list[dict]] | None = None,
    stats: dict | None = None,
) -> tuple[Path, Path]:
    ocx = base / "opencodex"
    ocx.mkdir(parents=True, exist_ok=True)
    # Credential-adjacent neighbours the reporter must never touch (design test 9).
    (ocx / "admin-api-token").write_text("fixture-admin-token\n", encoding="utf-8")
    (ocx / "config.json").write_text("{}\n", encoding="utf-8")
    if gateway_rows is not None or gateway_raw_lines:
        lines = [json.dumps(row) for row in gateway_rows or []] + list(gateway_raw_lines)
        (ocx / "usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    claude = base / "claude"
    (claude / "projects").mkdir(parents=True, exist_ok=True)
    for name, rows in (transcripts or {}).items():
        file = claude / "projects" / "-home-user-project" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    if stats is not None:
        (claude / "stats-cache.json").write_text(json.dumps(stats), encoding="utf-8")
    return ocx, claude


def write_estimates_snapshot(base: Path, providers: object) -> Path:
    snapshot = base / "observe-usage-snapshot.json"
    snapshot.write_text(json.dumps({"providers": providers}), encoding="utf-8")
    return snapshot


def run_report(ocx: Path, claude: Path, *extra: str) -> tuple[int, str]:
    argv = ["--opencodex-home", str(ocx), "--claude-home", str(claude), "--now", NOW, *extra]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = usage_report.main(argv)
    return code, buffer.getvalue()


def report_json(ocx: Path, claude: Path, *extra: str) -> dict:
    code, output = run_report(ocx, claude, "--format", "json", *extra)
    assert code == 0, output
    return json.loads(output)


def lane_by_name(record: dict, name: str) -> dict:
    lanes = {lane["lane"]: lane for lane in record["stores"]["gateway"]["lanes"]}
    assert name in lanes, sorted(lanes)
    return lanes[name]


def all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys |= all_keys(child)
    elif isinstance(value, list):
        for child in value:
            keys |= all_keys(child)
    return keys


class SubscriptionNeverPricedTests(unittest.TestCase):
    """Design test 1, with the mutation control that proves the assertions bite."""

    def build(self, base: Path) -> tuple[Path, Path, Path]:
        ocx, claude = write_homes(
            base,
            gateway_rows=[
                gateway_row(provider="anthropic-native", total=1000),
                gateway_row(provider="anthropic-native", total=500),
                gateway_row(provider="openai", total=2000),
                gateway_row(provider="muse", total=300),
            ],
        )
        snapshot = write_estimates_snapshot(
            base,
            [
                {"provider": "anthropic-native", "estimatedCostUsd": 45.0},
                {"provider": "openai", "estimatedCostUsd": 3641.17},
                {"provider": "muse"},
            ],
        )
        return ocx, claude, snapshot

    BILLING = ("--billing", "openai=subscription", "--billing", "muse=api-key")

    def collect_outputs(self, ocx: Path, claude: Path, snapshot: Path) -> list[str]:
        outputs = []
        for fmt in ("text", "json"):
            for estimates in ((), ("--estimates", str(snapshot))):
                code, output = run_report(ocx, claude, "--format", fmt, *self.BILLING, *estimates)
                self.assertEqual(code, 0)
                outputs.append(output)
        return outputs

    def test_subscription_lanes_render_unpriced_and_dollar_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude, snapshot = self.build(Path(temp))
            record = report_json(ocx, claude, *self.BILLING)
            for lane_name in ("subscription:anthropic", "subscription:openai"):
                cost = lane_by_name(record, lane_name)["cost"]
                self.assertEqual(cost["label"], "unpriced")
                self.assertEqual(cost["statement"], "subscription marginal cost is unknown")
            self.assertEqual(lane_by_name(record, "api:muse")["cost"]["label"], "missing")
            for output in self.collect_outputs(ocx, claude, snapshot):
                self.assertNotIn("45.0", output)
                self.assertNotIn("3641.17", output)
                self.assertNotIn("$", output)
            _, advisory_text = run_report(
                ocx, claude, *self.BILLING, "--estimates", str(snapshot)
            )
            self.assertIn("anthropic-native: excluded - subscription", advisory_text)
            self.assertIn("openai: excluded - subscription", advisory_text)
            self.assertIn("carries no estimate", advisory_text)

    def test_mutation_control_pointing_classifier_at_api_key_is_caught(self) -> None:
        """Re-run the priced-lane probe with the built-in rule mutated: it must now fail."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude, snapshot = self.build(Path(temp))
            with mock.patch.dict(usage_report.BUILTIN_BILLING, {"anthropic-native": "api-key"}):
                record = report_json(
                    ocx, claude, *self.BILLING, "--estimates", str(snapshot)
                )
                code, text = run_report(
                    ocx, claude, *self.BILLING, "--estimates", str(snapshot)
                )
            self.assertEqual(code, 0)
            mutated_cost = lane_by_name(record, "api:anthropic-native")["cost"]
            self.assertNotEqual(mutated_cost["label"], "unpriced")
            # The gateway's 45.0 figure now leaks into both views — exactly what the
            # main test's assertions would catch, so they are proven load-bearing.
            self.assertIn("45.0", json.dumps(record))
            self.assertIn("45.0", text)

    def test_cli_cannot_redeclare_the_builtin_subscription_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude, _ = self.build(Path(temp))
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as ctx:
                    run_report(ocx, claude, "--billing", "anthropic-native=api-key")
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("story 88", stderr.getvalue())


class MeasurementLabelTests(unittest.TestCase):
    def test_unknown_is_never_zero(self) -> None:
        """Design test 2: unmeasured requests are named and counted, never rendered as 0."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[
                    gateway_row(total=100),
                    gateway_row(total=100),
                    gateway_row(status="unreported"),
                    gateway_row(status="unreported"),
                    gateway_row(status="mystery-future-status"),
                ],
            )
            record = report_json(ocx, claude, "--store", "gateway")
            tokens = lane_by_name(record, "subscription:anthropic")["tokens"]
            self.assertEqual(tokens["value"], 200)
            self.assertEqual(tokens["label"], "lower-bound")
            self.assertEqual(tokens["unmeasuredRequests"], 3)
            code, text = run_report(ocx, claude, "--store", "gateway")
            self.assertEqual(code, 0)
            self.assertIn(">= 200 tokens (3 requests unmeasured)", text)

    def test_fully_reported_window_is_exact(self) -> None:
        """Positive control for test 2: with nothing unmeasured the label is exact."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp), gateway_rows=[gateway_row(total=100), gateway_row(total=100)]
            )
            record = report_json(ocx, claude, "--store", "gateway")
            tokens = lane_by_name(record, "subscription:anthropic")["tokens"]
            self.assertEqual(tokens["label"], "exact")
            self.assertEqual(record["stores"]["gateway"]["evidence"]["windowLabel"], "exact")
            code, text = run_report(ocx, claude, "--store", "gateway")
            self.assertIn("200 tokens", text)
            self.assertNotIn(">=", text)

    def test_torn_line_is_survived_and_counted(self) -> None:
        """Design test 5: one malformed line -> badLines 1, window lower-bound, exit 0."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(total=100)],
                gateway_raw_lines=('{"torn": ',),
            )
            record = report_json(ocx, claude, "--store", "gateway")
            evidence = record["stores"]["gateway"]["evidence"]
            self.assertEqual(evidence["parsedRows"], 1)
            self.assertEqual(evidence["badLines"], 1)
            self.assertEqual(evidence["windowLabel"], "lower-bound")

    def test_stale_evidence_is_labeled_with_its_end_and_exits_zero(self) -> None:
        """Design test 6."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(timestamp="2026-08-20T10:00:00Z", total=100)],
                transcripts={"a.jsonl": [transcript_row(timestamp="2026-08-20T10:00:00Z")]},
            )
            record = report_json(ocx, claude, "--window", "24h")
            gateway_evidence = record["stores"]["gateway"]["evidence"]
            self.assertEqual(gateway_evidence["freshness"], "stale")
            self.assertEqual(gateway_evidence["windowEnd"], "2026-08-20T10:00:00+00:00")
            self.assertEqual(record["stores"]["gateway"]["lanes"], [])
            self.assertEqual(record["stores"]["claude"]["evidence"]["freshness"], "stale")
            code, text = run_report(ocx, claude, "--window", "24h")
            self.assertEqual(code, 0)
            self.assertIn("freshness: stale (evidence ends 2026-08-20T10:00:00+00:00)", text)

    def test_missing_dimensions_render_missing_and_exit_zero(self) -> None:
        """Design test 7: absent evidence and underivable ownership are missing, not guessed."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp), transcripts={"a.jsonl": [transcript_row()]}
            )
            record = report_json(ocx, claude)
            self.assertFalse(record["stores"]["gateway"]["evidence"]["present"])
            self.assertEqual(record["stores"]["gateway"]["evidence"]["label"], "missing")
            ownership = record["stores"]["claude"]["ownership"]
            for dimension in ("perWorkflow", "perTeammate"):
                self.assertEqual(ownership[dimension]["label"], "missing")
                self.assertIn("never guessed", ownership[dimension]["statement"])
            code, _ = run_report(ocx, claude)
            self.assertEqual(code, 0)


class StoreSeparationTests(unittest.TestCase):
    def test_no_cross_store_sum(self) -> None:
        """Design test 3: no key or line combines the stores; the overlap warning is present."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(total=1111, surface="claude")],
                transcripts={
                    "a.jsonl": [transcript_row(input_tokens=2000, output_tokens=222)]
                },
            )
            record = report_json(ocx, claude)
            code, text = run_report(ocx, claude)
            self.assertEqual(code, 0)
            for output in (json.dumps(record), text):
                self.assertNotIn("3333", output)  # 1111 + 2222 never appears
            self.assertIn("no combined", record["overlap"]["statement"])
            self.assertIn("overlap:", text)
            keys = {key.lower() for key in all_keys(record)}
            for forbidden in ("combined", "grandtotal", "crossstore"):
                self.assertFalse(
                    any(forbidden in key for key in keys), f"forbidden key shape: {forbidden}"
                )
            refusal_ids = [refusal["id"] for refusal in record["refusals"]]
            self.assertIn("no-cross-store-total", refusal_ids)

    def test_unit_honesty(self) -> None:
        """Design test 4: each store names its incompatible token convention."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(total=100)],
                transcripts={"a.jsonl": [transcript_row()]},
            )
            record = report_json(ocx, claude)
            gateway = record["stores"]["gateway"]
            self.assertEqual(gateway["unit"], "gateway-total (cache-inclusive)")
            self.assertEqual(
                gateway["lanes"][0]["tokens"]["unit"], "gateway-total (cache-inclusive)"
            )
            claude_store = record["stores"]["claude"]
            self.assertEqual(claude_store["unit"], "anthropic message.usage (cache-exclusive)")
            self.assertEqual(
                claude_store["byModel"][0]["unit"], "anthropic message.usage (cache-exclusive)"
            )
            _, text = run_report(ocx, claude)
            self.assertIn("gateway-total (cache-inclusive)", text)
            self.assertIn("anthropic message.usage (cache-exclusive)", text)

    def test_synthetic_rows_are_excluded_with_positive_control(self) -> None:
        """Design test 8."""
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                transcripts={
                    "a.jsonl": [
                        transcript_row(model="<synthetic>", input_tokens=999, output_tokens=999),
                        transcript_row(input_tokens=50, output_tokens=5),
                    ]
                },
            )
            record = report_json(ocx, claude, "--store", "claude")
            store = record["stores"]["claude"]
            self.assertEqual(store["syntheticRowsExcluded"], 1)
            models = [entry["model"] for entry in store["byModel"]]
            self.assertEqual(models, ["claude-fable-5"])  # positive control: real row included
            self.assertEqual(store["byModel"][0]["tokens"]["input_tokens"], 50)
            code, text = run_report(ocx, claude, "--store", "claude")
            self.assertNotIn("999", text)
            self.assertIn("in 50", text)

    def test_stats_cache_cross_check_never_reads_cost_usd(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                transcripts={"a.jsonl": [transcript_row()]},
                stats={
                    "lastComputedDate": "2026-08-24",
                    "modelUsage": {
                        "claude-fable-5": {
                            "inputTokens": 7,
                            "outputTokens": 3,
                            "costUSD": 12.34,
                            "contextWindow": 1000000,
                        }
                    },
                },
            )
            record = report_json(ocx, claude, "--store", "claude")
            cross = record["stores"]["claude"]["crossCheck"]
            self.assertEqual(cross["byModel"]["claude-fable-5"], {"inputTokens": 7, "outputTokens": 3})
            self.assertNotIn("12.34", json.dumps(record))
            code, text = run_report(ocx, claude, "--store", "claude")
            self.assertNotIn("12.34", text)
            self.assertIn("costUSD is a local list-rate computation", text)


class ReadAllowlistTests(unittest.TestCase):
    def test_reporter_opens_only_allowlisted_paths_and_never_writes(self) -> None:
        """Design test 9: every open recorded; admin-api-token untouched; no write modes."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ocx, claude = write_homes(
                base,
                gateway_rows=[gateway_row(total=100), gateway_row(provider="muse", total=50)],
                transcripts={"a.jsonl": [transcript_row()], "b.jsonl": [transcript_row()]},
                stats={"modelUsage": {}},
            )
            snapshot = write_estimates_snapshot(
                base, [{"provider": "muse", "estimatedCostUsd": 1.5}]
            )
            recorded: list[tuple[str, str]] = []
            real_open = builtins.open

            def recording_open(file, mode="r", *args, **kwargs):
                recorded.append((str(file), str(mode)))
                return real_open(file, mode, *args, **kwargs)

            with mock.patch("builtins.open", recording_open), mock.patch("io.open", recording_open):
                code, output = run_report(
                    ocx,
                    claude,
                    "--billing",
                    "muse=api-key",
                    "--estimates",
                    str(snapshot),
                    "--format",
                    "json",
                )
            self.assertEqual(code, 0)
            json.loads(output)
            allowed = {
                str(ocx / "usage.jsonl"),
                str(claude / "stats-cache.json"),
                str(snapshot),
                str(claude / "projects" / "-home-user-project" / "a.jsonl"),
                str(claude / "projects" / "-home-user-project" / "b.jsonl"),
            }
            inside = [(path, mode) for path, mode in recorded if path.startswith(str(base))]
            self.assertGreaterEqual(len(inside), 5)  # positive control: the recorder saw reads
            for path, mode in inside:
                self.assertIn(path, allowed)
                self.assertFalse(set(mode) & set("wax+"), f"write-shaped open of {path}: {mode}")
            opened = {path for path, _ in recorded}
            self.assertNotIn(str(ocx / "admin-api-token"), opened)
            self.assertNotIn(str(ocx / "config.json"), opened)

    def test_allowlist_refuses_paths_outside_its_three_patterns_by_name(self) -> None:
        home = Path("/fixture")
        allowlist = usage_report.ReadAllowlist(
            opencodex_usage=home / "opencodex" / "usage.jsonl",
            claude_projects_dir=home / "claude" / "projects",
            claude_stats_cache=home / "claude" / "stats-cache.json",
        )
        # Positive control: the three patterns admit.
        allowlist.admit(home / "opencodex" / "usage.jsonl")
        allowlist.admit(home / "claude" / "projects" / "proj" / "session.jsonl")
        allowlist.admit(home / "claude" / "stats-cache.json")
        for refused in (
            home / "opencodex" / "admin-api-token",
            home / "opencodex" / "config.json",
            home / "claude" / "projects" / "top-level.jsonl",
            home / "claude" / "projects" / "proj" / "nested" / "deep.jsonl",
            home / "claude" / "projects" / "proj" / "notes.txt",
            home / "claude" / "settings.json",
        ):
            with self.assertRaises(usage_report.ReadRefusal) as ctx:
                allowlist.admit(refused)
            message = str(ctx.exception)
            self.assertIn(str(refused), message)
            self.assertIn("closed read allowlist", message)
            self.assertIn(str(home / "opencodex" / "usage.jsonl"), message)


class PrivacyTests(unittest.TestCase):
    def test_content_bodies_and_credentials_never_reach_output(self) -> None:
        """Design test 10 plus hostile-identifier injection."""
        credential = "".join(("sk-", "ant-", "api03-")) + "A" * 24
        prompt_body = "SECRET PROMPT BODY do not leak"
        hostile_model = 'claude-x",\n  "injected": "boom'
        hostile_provider = 'evil\nprovider\t"lane'
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(provider=hostile_provider, total=100)],
                transcripts={
                    "a.jsonl": [
                        transcript_row(
                            model=hostile_model,
                            content=[{"type": "text", "text": f"{prompt_body} {credential}"}],
                        )
                    ]
                },
            )
            code, json_output = run_report(ocx, claude, "--format", "json")
            self.assertEqual(code, 0)
            code, text_output = run_report(ocx, claude)
            self.assertEqual(code, 0)
            for output in (json_output, text_output):
                self.assertNotIn(credential, output)
                self.assertNotIn(prompt_body, output)
            record = json.loads(json_output)  # hostile names never break JSON structure
            self.assertNotIn("injected", all_keys(record))
            self.assertEqual(
                record["stores"]["claude"]["byModel"][0]["model"], hostile_model
            )
            # Text view sanitizes control characters, so the newline injection cannot
            # open a new line; the sanitized identifiers still render (positive control).
            self.assertNotIn(hostile_model, text_output)
            self.assertNotIn(hostile_provider, text_output)
            self.assertIn('claude-x",?', text_output)
            self.assertIn("evil?provider", text_output)


class GoldenViewTests(unittest.TestCase):
    def test_text_and_json_views_render_one_record(self) -> None:
        """Design test 11: both goldens come from one fixture, so they cannot drift apart."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ocx, claude = write_homes(
                base,
                gateway_rows=[
                    gateway_row(total=1200, surface="claude"),
                    gateway_row(total=800),
                    gateway_row(status="unreported"),
                    gateway_row(provider="muse", total=500, route_kind="default-provider"),
                ],
                transcripts={
                    "a.jsonl": [
                        transcript_row(input_tokens=100, output_tokens=20, cache_read=7),
                        transcript_row(
                            session="session-b", sidechain=True, input_tokens=30, output_tokens=3
                        ),
                        transcript_row(model="<synthetic>", input_tokens=999),
                    ]
                },
                stats={
                    "lastComputedDate": "2026-08-24",
                    "modelUsage": {
                        "claude-fable-5": {"inputTokens": 130, "outputTokens": 23, "costUSD": 9.99}
                    },
                },
            )
            code, json_output = run_report(
                ocx, claude, "--billing", "muse=api-key", "--format", "json"
            )
            self.assertEqual(code, 0)
            code, text_output = run_report(ocx, claude, "--billing", "muse=api-key")
            self.assertEqual(code, 0)
            normalized_json = json_output.replace(str(base), "<fixture>")
            normalized_text = text_output.replace(str(base), "<fixture>")
            self.assertEqual(
                normalized_json, (GOLDEN_DIR / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                normalized_text, (GOLDEN_DIR / "report.txt").read_text(encoding="utf-8")
            )


class GateIndependenceTests(unittest.TestCase):
    def test_usage_report_is_never_a_gate_leaf(self) -> None:
        """Design test 12: asserted against parsed task/hook/CI definitions, not prose."""
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tasks = config["tasks"]
        self.assertIn("usage:report", tasks)  # positive control: the advisory task exists
        self.assertEqual(
            tasks["usage:report"]["run"],
            "uv run --python 3.12.11 --script scripts/usage_report.py",
        )
        self.assertEqual(tasks["check"]["depends"], ["validate", "test", "self-test", "secrets"])
        for name, task in tasks.items():
            if name == "usage:report":
                continue
            for reference in ("usage:report", "usage_report"):
                self.assertNotIn(
                    reference, json.dumps(task), f"task {name} must not reference the reporter"
                )
        lefthook = yaml.safe_load((ROOT / "lefthook.yml").read_text(encoding="utf-8"))
        for hook_name, hook in lefthook.items():
            for command_name, command in hook.get("commands", {}).items():
                for reference in ("usage:report", "usage_report", "usage"):
                    self.assertNotIn(
                        reference,
                        command.get("run", ""),
                        f"{hook_name}.{command_name} must not run the reporter",
                    )
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            self.assertNotIn("usage:report", workflow.read_text(encoding="utf-8"))


class EstimatesAdvisoryTests(unittest.TestCase):
    def test_estimates_quote_the_gateway_figure_verbatim_for_declared_api_key_lanes(self) -> None:
        """Design test 13."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ocx, claude = write_homes(
                base,
                gateway_rows=[
                    gateway_row(provider="muse", total=100),
                    gateway_row(provider="openrouter", total=100),
                    gateway_row(provider="anthropic-native", total=100),
                ],
            )
            snapshot = write_estimates_snapshot(
                base,
                [
                    {"provider": "muse", "estimatedCostUsd": 12.5},
                    {"provider": "openrouter", "estimatedCostUsd": 3.25},
                    {"provider": "anthropic-native", "estimatedCostUsd": 45.0},
                ],
            )
            record = report_json(
                ocx, claude, "--billing", "muse=api-key", "--estimates", str(snapshot)
            )
            advisories = {
                advisory.get("provider"): advisory for advisory in record["advisories"]
            }
            self.assertEqual(advisories["muse"]["disposition"], "quoted")
            self.assertEqual(advisories["muse"]["estimatedCostUsd"], 12.5)  # verbatim
            self.assertIn("list-rate estimate, not a bill", advisories["muse"]["statement"])
            self.assertEqual(advisories["openrouter"]["disposition"], "excluded-undeclared")
            self.assertIn("openrouter: excluded", advisories["openrouter"]["statement"])
            self.assertEqual(
                advisories["anthropic-native"]["disposition"], "excluded-subscription"
            )
            # The quoted advisory never becomes a lane value.
            self.assertEqual(lane_by_name(record, "api:muse")["cost"]["label"], "missing")
            self.assertNotIn("3.25", json.dumps(record))
            self.assertNotIn("45.0", json.dumps(record["stores"]) + json.dumps(record["advisories"]))
            code, text = run_report(
                ocx, claude, "--billing", "muse=api-key", "--estimates", str(snapshot)
            )
            self.assertIn("estimatedCostUsd 12.5 - list-rate estimate, not a bill", text)

    def test_without_the_flag_no_dollar_and_no_estimate_appears(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(provider="muse", total=100)],
                transcripts={"a.jsonl": [transcript_row()]},
            )
            record = report_json(ocx, claude, "--billing", "muse=api-key")
            self.assertNotIn("advisories", record)
            for fmt in ("text", "json"):
                code, output = run_report(ocx, claude, "--billing", "muse=api-key", "--format", fmt)
                self.assertEqual(code, 0)
                self.assertNotIn("$", output)
                self.assertNotIn("estimatedCostUsd", output)

    def test_missing_snapshot_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(Path(temp))
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    run_report(ocx, claude, "--estimates", str(Path(temp) / "absent.json"))
            self.assertEqual(ctx.exception.code, 2)


class TimestampToleranceTests(unittest.TestCase):
    def test_gateway_epoch_ms_and_transcript_iso_shapes_both_parse(self) -> None:
        """The real gateway logs epoch ms (measured row: 1786079166570); transcripts log ISO."""
        expected = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(usage_report.parse_timestamp(epoch_ms("2026-08-24T10:00:00Z")), expected)
        self.assertEqual(usage_report.parse_timestamp("2026-08-24T10:00:00Z"), expected)
        self.assertEqual(usage_report.parse_timestamp("2026-08-24T10:00:00"), expected)
        self.assertEqual(
            usage_report.parse_timestamp(int(expected.timestamp())), expected
        )  # plain epoch seconds
        for garbage in (True, None, "not-a-time", [1786079166570], float("inf")):
            self.assertIsNone(usage_report.parse_timestamp(garbage), garbage)


class CliContractTests(unittest.TestCase):
    def test_usage_errors_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(Path(temp))
            for argv in (
                ("--window", "13d"),
                ("--billing", "muse"),
                ("--billing", "muse=prepaid"),
                ("--now", "not-a-timestamp"),
            ):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as ctx:
                        run_report(ocx, claude, *argv)
                self.assertEqual(ctx.exception.code, 2, argv)

    def test_store_selection_reads_and_renders_only_the_selected_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ocx, claude = write_homes(
                Path(temp),
                gateway_rows=[gateway_row(total=100)],
                transcripts={"a.jsonl": [transcript_row()]},
            )
            record = report_json(ocx, claude, "--store", "gateway")
            self.assertEqual(sorted(record["stores"]), ["gateway"])
            self.assertNotIn("overlap", record)
            record = report_json(ocx, claude, "--store", "claude")
            self.assertEqual(sorted(record["stores"]), ["claude"])

    def test_entrypoint_smoke_run_with_absent_evidence_exits_zero(self) -> None:
        """Honest absence is a successful report, end to end through the real entrypoint."""
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "opencodex").mkdir()
            (base / "claude").mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--opencodex-home",
                    str(base / "opencodex"),
                    "--claude-home",
                    str(base / "claude"),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(completed.stdout)
            self.assertEqual(record["schema"], "agentic-sdlc/usage-report@1")
            self.assertFalse(record["stores"]["gateway"]["evidence"]["present"])
            refusal_ids = [refusal["id"] for refusal in record["refusals"]]
            self.assertEqual(len(refusal_ids), 7)


if __name__ == "__main__":
    unittest.main()
