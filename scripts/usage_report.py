#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Render the honest local usage report (advisory, read-only, never a gate leaf).

Implements docs/plans/2026-08-24-usage-accounting-design.md (seed agentic-sdlc-12b7): a
disposable projection over evidence stores that already exist. Every reported value carries
two orthogonal facts — a billing lane (where a turn's cost lands) and a measurement label
from the closed vocabulary {exact, lower-bound, unpriced, missing, stale}. Subscription
lanes are NEVER priced; an unknown or undeclared billing kind fails toward not-pricing; the
default output carries no dollar figure at all.

``--estimates <snapshot.json>`` quotes the gateway's OWN ``ocx observe usage --json``
figures verbatim for declared api-key lanes only, each labeled a list-rate estimate, not a
bill. The reporter itself never shells out and never touches the gateway (the report works
with the gateway down), so the snapshot is an operator-captured file passed in explicitly.

Reads are a closed allowlist — exactly three patterns plus that explicit snapshot:

1. ``<opencodex-home>/usage.jsonl`` — the ONLY file read in that credential-adjacent dir
2. ``<claude-home>/projects/*/*.jsonl`` — allowlisted fields only; content bodies never
   enter the report
3. ``<claude-home>/stats-cache.json`` — token fields only; its costUSD is never read out

Everything else is refused by name. The reporter writes nothing anywhere and performs no
network I/O. Exit 0 covers honest absence (missing/stale evidence is a successful report),
2 is a usage error, 1 an unexpected I/O failure.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

SCHEMA = "agentic-sdlc/usage-report@1"
GATEWAY_UNIT = "gateway-total (cache-inclusive)"
CLAUDE_UNIT = "anthropic message.usage (cache-exclusive)"
GATEWAY_SCHEMA_NOTE = "best-effort (opencodex private file)"
ESTIMATE_DISCLAIMER = "list-rate estimate, not a bill"
SYNTHETIC_MODEL = "<synthetic>"
WINDOWS: dict[str, timedelta | None] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}
BILLING_KINDS = ("subscription", "api-key")
# Story 88's built-in rule: the launch route only admits sk-ant-oat* logins, so
# anthropic-native traffic is subscription by construction. --billing may not redeclare it;
# only a source mutation can, and the test suite proves such a mutation is caught.
BUILTIN_BILLING = {"anthropic-native": "subscription"}
LANE_NAMES = {("anthropic-native", "subscription"): "subscription:anthropic"}
# Anthropic-convention transcript token fields (cache-exclusive input_tokens).
TRANSCRIPT_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
# stats-cache.json modelUsage fields admitted into the cross-check. costUSD is deliberately
# absent: it is a local list-rate computation, never a bill, and is never read into output.
STATS_CACHE_TOKEN_FIELDS = (
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "cacheCreationInputTokens",
)

OVERLAP_STATEMENT = (
    'gateway surface:"claude" rows and transcript rows describe overlapping turns with no '
    "provable join (a conversationId is not a sessionId) and incompatible input-token units "
    "(cache-inclusive vs cache-exclusive); the two stores render separately and no combined "
    "total exists in this report"
)

# Emitted verbatim in every report so absence is visible, not silent (design section 4).
# Deliberately free of currency symbols: the default output never carries one.
REFUSALS = (
    {
        "id": "no-cross-store-total",
        "statement": (
            "the gateway store and the transcript store describe overlapping turns with no "
            "provable join and incompatible input-token units; any combined number would "
            "double-count and mix units, so none exists anywhere in this report"
        ),
    },
    {
        "id": "no-per-turn-cost",
        "statement": (
            "no local surface carries a provider-metered cost for any single request, so "
            "per-turn cost attribution is not claimed"
        ),
    },
    {
        "id": "no-subscription-dollars",
        "statement": (
            "a subscription turn is never priced, not even as an estimate; the gateway's own "
            "list-rate figure over subscription lanes is a defect (seed agentic-sdlc-bf25), "
            "not a cost, and is never quoted here"
        ),
    },
    {
        "id": "no-per-workflow-or-teammate-ownership",
        "statement": (
            "transcripts carry no verified linkage from a spawned agent's session to its "
            "parent, so per-workflow and per-teammate ownership stay missing rather than "
            "heuristically split"
        ),
    },
    {
        "id": "no-session-conversation-join",
        "statement": (
            "gateway conversationId values and transcript sessionId values do not correlate "
            "by any verified rule; no join is attempted"
        ),
    },
    {
        "id": "no-completeness-claim",
        "statement": (
            "ambiguous account rows, surface-less rows, and unreported-usage rows are "
            "counted buckets, never redistributed into named lanes"
        ),
    },
    {
        "id": "no-budget-authority",
        "statement": "a usage report grants nothing and retroactively authorizes nothing",
    },
)


class ReadRefusal(Exception):
    """A path outside the reporter's closed read allowlist was about to be opened."""


@dataclass(frozen=True)
class ReadAllowlist:
    """The three admitted read patterns plus the explicit operator-supplied snapshot."""

    opencodex_usage: Path
    claude_projects_dir: Path
    claude_stats_cache: Path
    estimates_snapshot: Path | None = None

    def describe(self) -> str:
        patterns = [
            str(self.opencodex_usage),
            str(self.claude_projects_dir / "*" / "*.jsonl"),
            str(self.claude_stats_cache),
        ]
        if self.estimates_snapshot is not None:
            patterns.append(str(self.estimates_snapshot))
        return ", ".join(patterns)

    def admits(self, path: Path) -> bool:
        if path in (self.opencodex_usage, self.claude_stats_cache, self.estimates_snapshot):
            return True
        return path.suffix == ".jsonl" and path.parent.parent == self.claude_projects_dir

    def admit(self, path: Path) -> Path:
        if self.admits(path):
            return path
        raise ReadRefusal(
            f"refusing to read {path}: outside the closed read allowlist ({self.describe()})"
        )


def iter_admitted_lines(path: Path, allowlist: ReadAllowlist):
    with open(allowlist.admit(path), "r", encoding="utf-8", errors="replace") as handle:
        yield from handle


def read_admitted_json(path: Path, allowlist: ReadAllowlist) -> Any:
    with open(allowlist.admit(path), "r", encoding="utf-8", errors="replace") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class Window:
    requested: str
    start: datetime | None
    end: datetime

    def contains(self, moment: datetime | None) -> bool:
        if moment is None:
            return False
        return (self.start is None or moment >= self.start) and moment <= self.end


def parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # The gateway logs epoch milliseconds (measured 2026-08-24: 1786079166570), while
        # transcripts carry ISO-8601 strings; tolerate plain epoch seconds as well.
        seconds = value / 1000 if abs(value) >= 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def isoformat(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def counted_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def classify_lane(provider: str, declared: dict[str, str]) -> tuple[str, str]:
    """Return (lane name, billing kind); the built-in rule outranks every declaration."""
    kind = BUILTIN_BILLING.get(provider) or declared.get(provider, "undeclared")
    alias = LANE_NAMES.get((provider, kind))
    if alias is not None:
        return alias, kind
    prefix = {"subscription": "subscription", "api-key": "api", "undeclared": "undeclared"}[kind]
    return f"{prefix}:{provider}", kind


def lane_cost(kind: str) -> dict[str, str]:
    if kind == "api-key":
        return {
            "label": "missing",
            "statement": "metered on the provider's bill; no local evidence carries it",
        }
    if kind == "subscription":
        return {"label": "unpriced", "statement": "subscription marginal cost is unknown"}
    return {
        "label": "unpriced",
        "statement": (
            "billing kind undeclared - treated as subscription for pricing; "
            "marginal cost is unknown"
        ),
    }


def measured_total(row: dict[str, Any]) -> int | None:
    """Token total for a gateway row, or None when the row is unmeasured.

    Only usageStatus == "reported" counts as measured; every unknown status value is
    treated as unmeasured, so an unrecognized future schema fails toward lower-bound.
    """
    if row.get("usageStatus") != "reported":
        return None
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return None
    total = counted_int(usage.get("totalTokens"))
    if total is not None:
        return total
    input_tokens = counted_int(usage.get("inputTokens"))
    output_tokens = counted_int(usage.get("outputTokens"))
    if input_tokens is not None and output_tokens is not None:
        return input_tokens + output_tokens
    return None


def absent_evidence(path: Path, statement: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "present": False,
        "label": "missing",
        "statement": statement,
    }


def parse_gateway_store(
    allowlist: ReadAllowlist, window: Window, billing: dict[str, str]
) -> dict[str, Any]:
    path = allowlist.opencodex_usage
    if not path.is_file():
        return {
            "evidence": absent_evidence(
                path, "no gateway evidence at this path; honest absence is a successful report"
            ),
            "unit": GATEWAY_UNIT,
            "lanes": [],
        }
    parsed = bad = without_timestamp = misroutes = 0
    newest: datetime | None = None
    lanes: dict[str, dict[str, Any]] = {}
    surfaces = {"claude": 0, "unattributed": 0}
    for line in iter_admitted_lines(path, allowlist):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(row, dict):
            bad += 1
            continue
        parsed += 1
        moment = parse_timestamp(row.get("timestamp"))
        if moment is None:
            # Window membership is unknowable; the row is counted, never guessed into a lane.
            without_timestamp += 1
            continue
        if newest is None or moment > newest:
            newest = moment
        if not window.contains(moment):
            continue
        provider = row.get("provider")
        if not isinstance(provider, str) or not provider:
            provider = "(unknown-provider)"
        lane_name, kind = classify_lane(provider, billing)
        lane = lanes.setdefault(
            lane_name,
            {"provider": provider, "kind": kind, "requests": 0, "tokens": 0, "unmeasured": 0},
        )
        lane["requests"] += 1
        total = measured_total(row)
        if total is None:
            lane["unmeasured"] += 1
        else:
            lane["tokens"] += total
        surfaces["claude" if row.get("surface") == "claude" else "unattributed"] += 1
        route = row.get("routeDecision")
        if isinstance(route, dict) and route.get("routeKind") == "default-provider":
            misroutes += 1

    any_unmeasured = any(lane["unmeasured"] for lane in lanes.values())
    window_label = "lower-bound" if (bad or without_timestamp or any_unmeasured) else "exact"
    if newest is None:
        freshness = "missing"
    elif window.start is not None and newest < window.start:
        freshness = "stale"
    else:
        freshness = "exact"
    lane_records = []
    for name in sorted(lanes):
        lane = lanes[name]
        label = "lower-bound" if (lane["unmeasured"] or bad or without_timestamp) else "exact"
        lane_records.append(
            {
                "lane": name,
                "provider": lane["provider"],
                "billingKind": lane["kind"],
                "requests": {"value": lane["requests"], "label": "exact"},
                "tokens": {
                    "value": lane["tokens"],
                    "unit": GATEWAY_UNIT,
                    "label": label,
                    "unmeasuredRequests": lane["unmeasured"],
                },
                "cost": lane_cost(lane["kind"]),
            }
        )
    return {
        "evidence": {
            "path": str(path),
            "present": True,
            "parsedRows": parsed,
            "badLines": bad,
            "rowsWithoutTimestamp": without_timestamp,
            "windowLabel": window_label,
            "windowEnd": isoformat(newest),
            "freshness": freshness,
            "schemaNote": GATEWAY_SCHEMA_NOTE,
        },
        "unit": GATEWAY_UNIT,
        "lanes": lane_records,
        "surfaces": surfaces,
        "misroutes": {
            "defaultProviderRows": misroutes,
            "note": "routeKind default-provider is an alarm (seed agentic-sdlc-fa32)",
        },
    }


OWNERSHIP = {
    "perWorkflow": {
        "label": "missing",
        "statement": (
            "transcripts carry no verified linkage from a spawned agent's session to its "
            "parent; per-workflow ownership is missing, never guessed"
        ),
    },
    "perTeammate": {
        "label": "missing",
        "statement": (
            "transcripts carry no verified linkage from a spawned agent's session to its "
            "parent; per-teammate ownership is missing, never guessed"
        ),
    },
}


def parse_claude_store(allowlist: ReadAllowlist, window: Window) -> dict[str, Any]:
    projects = allowlist.claude_projects_dir
    files = sorted(p for p in projects.glob("*/*.jsonl") if p.is_file()) if projects.is_dir() else []
    if not files:
        return {
            "evidence": absent_evidence(
                projects / "*" / "*.jsonl",
                "no transcript evidence under this path; honest absence is a successful report",
            ),
            "unit": CLAUDE_UNIT,
            "byModel": [],
            "ownership": OWNERSHIP,
        }
    bad = records = synthetic = sidechain = attributed = without_timestamp = 0
    newest: datetime | None = None
    sessions: set[str] = set()
    by_model: dict[str, dict[str, int]] = {}
    by_entrypoint: dict[str, int] = {}
    for file in files:
        for line in iter_admitted_lines(file, allowlist):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(row, dict):
                bad += 1
                continue
            # Parse ONLY the allowlisted fields; message content never enters the report.
            message = row.get("message")
            usage = message.get("usage") if isinstance(message, dict) else None
            model = message.get("model") if isinstance(message, dict) else None
            if not isinstance(usage, dict) or not isinstance(model, str):
                continue
            moment = parse_timestamp(row.get("timestamp"))
            if moment is None:
                without_timestamp += 1
                continue
            if newest is None or moment > newest:
                newest = moment
            if not window.contains(moment):
                continue
            if model == SYNTHETIC_MODEL:
                synthetic += 1
                continue
            records += 1
            session = row.get("sessionId")
            if isinstance(session, str):
                sessions.add(session)
            if row.get("isSidechain") is True:
                sidechain += 1
            entrypoint = row.get("entrypoint")
            if isinstance(entrypoint, str):
                by_entrypoint[entrypoint] = by_entrypoint.get(entrypoint, 0) + 1
            if isinstance(row.get("attributionSkill"), str):
                attributed += 1
            slot = by_model.setdefault(
                model, {field: 0 for field in TRANSCRIPT_TOKEN_FIELDS} | {"records": 0}
            )
            slot["records"] += 1
            for field in TRANSCRIPT_TOKEN_FIELDS:
                value = counted_int(usage.get(field))
                if value is not None:
                    slot[field] += value

    label = "lower-bound" if (bad or without_timestamp) else "exact"
    if newest is None:
        freshness = "missing"
    elif window.start is not None and newest < window.start:
        freshness = "stale"
    else:
        freshness = "exact"
    model_records = [
        {
            "model": model,
            "records": by_model[model]["records"],
            "tokens": {field: by_model[model][field] for field in TRANSCRIPT_TOKEN_FIELDS},
            "unit": CLAUDE_UNIT,
            "label": label,
        }
        for model in sorted(by_model)
    ]
    store: dict[str, Any] = {
        "evidence": {
            "path": str(projects / "*" / "*.jsonl"),
            "present": True,
            "transcriptFiles": len(files),
            "usageRecords": records,
            "badLines": bad,
            "rowsWithoutTimestamp": without_timestamp,
            "windowLabel": label,
            "windowEnd": isoformat(newest),
            "freshness": freshness,
        },
        "unit": CLAUDE_UNIT,
        "sessions": {"count": len(sessions), "label": "exact"},
        "sidechainRecords": sidechain,
        "recordsWithAttributionSkill": attributed,
        "syntheticRowsExcluded": synthetic,
        "byEntrypoint": {name: by_entrypoint[name] for name in sorted(by_entrypoint)},
        "byModel": model_records,
        "ownership": OWNERSHIP,
    }
    cross_check = parse_stats_cache(allowlist, window)
    if cross_check is not None:
        store["crossCheck"] = cross_check
    return store


def parse_stats_cache(allowlist: ReadAllowlist, window: Window) -> dict[str, Any] | None:
    path = allowlist.claude_stats_cache
    if not path.is_file():
        return None
    try:
        document = read_admitted_json(path, allowlist)
    except (json.JSONDecodeError, UnicodeError):
        return {
            "path": str(path),
            "label": "missing",
            "statement": "stats-cache.json did not parse; the cross-check is unavailable",
        }
    if not isinstance(document, dict):
        return {
            "path": str(path),
            "label": "missing",
            "statement": "stats-cache.json did not parse; the cross-check is unavailable",
        }
    last_computed = document.get("lastComputedDate")
    computed_moment = parse_timestamp(last_computed)
    stale = (
        window.start is not None
        and computed_moment is not None
        and computed_moment < window.start
    )
    by_model: dict[str, dict[str, int]] = {}
    model_usage = document.get("modelUsage")
    if isinstance(model_usage, dict):
        for model in sorted(model_usage):
            entry = model_usage[model]
            if not isinstance(entry, dict):
                continue
            tokens = {}
            for field in STATS_CACHE_TOKEN_FIELDS:
                value = counted_int(entry.get(field))
                if value is not None:
                    tokens[field] = value
            by_model[str(model)] = tokens
    return {
        "path": str(path),
        "label": "stale" if stale else "exact",
        "lastComputedDate": last_computed if isinstance(last_computed, str) else None,
        "note": (
            "lifetime aggregate, not window-scoped; costUSD is a local list-rate "
            "computation and is never read into this report"
        ),
        "byModel": by_model,
    }


def load_estimates_snapshot(allowlist: ReadAllowlist) -> dict[str, Any]:
    """Per-provider estimatedCostUsd figures from an `ocx observe usage --json` capture."""
    document = read_admitted_json(allowlist.estimates_snapshot, allowlist)
    figures: dict[str, Any] = {}
    providers = document.get("providers") if isinstance(document, dict) else None
    entries: list[tuple[Any, Any]] = []
    if isinstance(providers, dict):
        entries = list(providers.items())
    elif isinstance(providers, list):
        entries = [
            (entry.get("provider") or entry.get("name"), entry)
            for entry in providers
            if isinstance(entry, dict)
        ]
    for name, entry in entries:
        if isinstance(name, str) and isinstance(entry, dict) and "estimatedCostUsd" in entry:
            figures[name] = entry["estimatedCostUsd"]
    return figures


def build_advisories(
    gateway: dict[str, Any] | None, figures: dict[str, Any], snapshot: Path
) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = [
        {
            "statement": (
                f"figures below are the gateway's own, quoted verbatim from the "
                f"operator-captured snapshot {snapshot}; each is a {ESTIMATE_DISCLAIMER}, "
                "and subscription lanes are never included"
            )
        }
    ]
    lanes = gateway.get("lanes", []) if gateway is not None else []
    for lane in lanes:
        provider = lane["provider"]
        kind = lane["billingKind"]
        if kind == "subscription":
            advisories.append(
                {
                    "provider": provider,
                    "disposition": "excluded-subscription",
                    "statement": f"{provider}: excluded - subscription, marginal cost unknown",
                }
            )
        elif kind == "undeclared":
            advisories.append(
                {
                    "provider": provider,
                    "disposition": "excluded-undeclared",
                    "statement": (
                        f"{provider}: excluded - billing kind undeclared; treated as "
                        f"subscription (declare --billing {provider}=api-key to include)"
                    ),
                }
            )
        elif provider in figures:
            advisories.append(
                {
                    "provider": provider,
                    "disposition": "quoted",
                    "estimatedCostUsd": figures[provider],
                    "statement": (
                        f"{lane['lane']}: gateway-reported estimatedCostUsd "
                        f"{figures[provider]} - {ESTIMATE_DISCLAIMER}"
                    ),
                }
            )
        else:
            advisories.append(
                {
                    "provider": provider,
                    "disposition": "no-estimate",
                    "statement": (
                        f"{lane['lane']}: the gateway snapshot carries no estimate for this "
                        "provider (its price table does not cover it)"
                    ),
                }
            )
    return advisories


def printable(value: Any) -> str:
    """Foreign identifiers (lane, provider, model names) never break text structure."""
    return "".join(ch if ch.isprintable() or ch == " " else "?" for ch in str(value))


def render_tokens(tokens: dict[str, Any]) -> str:
    if tokens["label"] != "lower-bound":
        return f"{tokens['value']} tokens"
    if not tokens["unmeasuredRequests"]:
        # Tainted by the store window (bad or untimestamped lines named in the evidence
        # line), not by this lane's own rows.
        return f">= {tokens['value']} tokens"
    plural = "" if tokens["unmeasuredRequests"] == 1 else "s"
    return f">= {tokens['value']} tokens ({tokens['unmeasuredRequests']} request{plural} unmeasured)"


def render_evidence(evidence: dict[str, Any], counts: str) -> list[str]:
    if not evidence.get("present"):
        return [f"evidence: {printable(evidence['path'])} | missing - {evidence['statement']}"]
    return [
        f"evidence: {printable(evidence['path'])} | {counts} | "
        f"window: {evidence['windowLabel']} | freshness: {evidence['freshness']}"
        + (f" (evidence ends {evidence['windowEnd']})" if evidence["freshness"] == "stale" else "")
    ]


def render_text(record: dict[str, Any]) -> str:
    window = record["window"]
    lines = [
        f"agentic-sdlc usage report ({record['schema']})",
        f"generated {record['generatedAt']} | window {window['requested']} "
        f"({window['from'] or 'beginning'} -> {window['to']})",
    ]
    gateway = record["stores"].get("gateway")
    if gateway is not None:
        lines += ["", "== gateway store =="]
        evidence = gateway["evidence"]
        if evidence.get("present"):
            counts = (
                f"parsed {evidence['parsedRows']} rows, {evidence['badLines']} bad lines, "
                f"{evidence['rowsWithoutTimestamp']} without timestamps"
            )
            lines += render_evidence(evidence, counts)
            lines.append(f"schema: {evidence['schemaNote']}")
            lines.append(f"unit: {gateway['unit']}")
            if gateway["lanes"]:
                for lane in gateway["lanes"]:
                    cost = lane["cost"]
                    lines.append(
                        f"  {printable(lane['lane']):<28} requests {lane['requests']['value']:>7}  "
                        f"{render_tokens(lane['tokens']):<48}  "
                        f"cost: {cost['label']} - {cost['statement']}"
                    )
            else:
                lines.append("  no requests in window")
            surfaces = gateway["surfaces"]
            lines.append(
                f"surfaces: claude {surfaces['claude']}, unattributed {surfaces['unattributed']}"
            )
            misroutes = gateway["misroutes"]
            lines.append(
                f"misroutes: {misroutes['defaultProviderRows']} default-provider rows "
                f"({misroutes['note']})"
            )
        else:
            lines += render_evidence(evidence, "")
    claude = record["stores"].get("claude")
    if claude is not None:
        lines += ["", "== claude store =="]
        evidence = claude["evidence"]
        if evidence.get("present"):
            counts = (
                f"{evidence['transcriptFiles']} files, {evidence['usageRecords']} usage "
                f"records, {evidence['badLines']} bad lines, "
                f"{evidence['rowsWithoutTimestamp']} without timestamps"
            )
            lines += render_evidence(evidence, counts)
            lines.append(f"unit: {claude['unit']}")
            lines.append(
                f"sessions: {claude['sessions']['count']} ({claude['sessions']['label']}) | "
                f"sidechain records: {claude['sidechainRecords']} | "
                f"synthetic rows excluded: {claude['syntheticRowsExcluded']} | "
                f"records with attributionSkill: {claude['recordsWithAttributionSkill']}"
            )
            if claude["byEntrypoint"]:
                pairs = ", ".join(
                    f"{printable(name)} {count}" for name, count in claude["byEntrypoint"].items()
                )
                lines.append(f"by entrypoint: {pairs}")
            for entry in claude["byModel"]:
                tokens = entry["tokens"]
                lines.append(
                    f"  {printable(entry['model']):<36} records {entry['records']:>6}  "
                    f"in {tokens['input_tokens']}  out {tokens['output_tokens']}  "
                    f"cacheCreate {tokens['cache_creation_input_tokens']}  "
                    f"cacheRead {tokens['cache_read_input_tokens']}  ({entry['label']})"
                )
        else:
            lines += render_evidence(evidence, "")
        ownership = claude["ownership"]
        lines.append(
            f"ownership: per-workflow {ownership['perWorkflow']['label']} - "
            f"{ownership['perWorkflow']['statement']}"
        )
        lines.append(
            f"ownership: per-teammate {ownership['perTeammate']['label']} - "
            f"{ownership['perTeammate']['statement']}"
        )
        cross = claude.get("crossCheck")
        if cross is not None:
            lines.append(f"cross-check (stats-cache.json): {cross['label']} - {cross['note']}"
                         if "note" in cross else
                         f"cross-check (stats-cache.json): {cross['label']} - {cross['statement']}")
    overlap = record.get("overlap")
    if overlap is not None:
        lines += ["", f"overlap: {overlap['statement']}"]
    lines += ["", "== refusals =="]
    for refusal in record["refusals"]:
        lines.append(f"- {refusal['id']}: {refusal['statement']}")
    advisories = record.get("advisories")
    if advisories is not None:
        lines += ["", "== advisories (--estimates) =="]
        for advisory in advisories:
            lines.append(f"- {printable(advisory['statement'])}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="usage_report.py",
        description=(
            "Advisory, read-only usage report over local evidence stores. Never a gate "
            "leaf; a report is evidence of nothing and authorizes nothing."
        ),
    )
    parser.add_argument("--window", choices=sorted(WINDOWS), default="7d")
    parser.add_argument("--store", choices=["gateway", "claude", "both"], default="both")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--estimates",
        metavar="SNAPSHOT_JSON",
        type=Path,
        help=(
            "path to an operator-captured `ocx observe usage --json` snapshot; its "
            "estimatedCostUsd figures are quoted verbatim for declared api-key lanes only, "
            "each labeled a list-rate estimate, not a bill (the reporter never runs ocx "
            "itself)"
        ),
    )
    parser.add_argument(
        "--billing",
        action="append",
        default=[],
        metavar="PROVIDER=subscription|api-key",
        help="declare a provider's billing kind; undeclared providers are never priced",
    )
    parser.add_argument("--opencodex-home", type=Path, default=Path.home() / ".opencodex")
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    parser.add_argument(
        "--now",
        metavar="ISO-8601",
        help="pin the report clock (reproducibility and tests); defaults to the current UTC time",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    billing: dict[str, str] = {}
    for declaration in args.billing:
        provider, separator, kind = declaration.partition("=")
        if not separator or not provider or kind not in BILLING_KINDS:
            parser.error(f"--billing expects PROVIDER=subscription|api-key, got {declaration!r}")
        if provider in BUILTIN_BILLING:
            parser.error(
                f"--billing may not redeclare {provider}: subscription by construction (story 88)"
            )
        billing[provider] = kind
    if args.now is not None:
        now = parse_timestamp(args.now)
        if now is None:
            parser.error(f"--now expects an ISO-8601 timestamp, got {args.now!r}")
    else:
        now = datetime.now(timezone.utc)
    span = WINDOWS[args.window]
    window = Window(args.window, None if span is None else now - span, now)
    claude_home = args.claude_home.expanduser()
    allowlist = ReadAllowlist(
        opencodex_usage=args.opencodex_home.expanduser() / "usage.jsonl",
        claude_projects_dir=claude_home / "projects",
        claude_stats_cache=claude_home / "stats-cache.json",
        estimates_snapshot=None if args.estimates is None else args.estimates.expanduser(),
    )

    stores: dict[str, Any] = {}
    try:
        if args.estimates is not None:
            if not allowlist.estimates_snapshot.is_file():
                parser.error(f"--estimates snapshot not found: {allowlist.estimates_snapshot}")
            try:
                figures = load_estimates_snapshot(allowlist)
            except (json.JSONDecodeError, UnicodeError):
                parser.error(
                    f"--estimates snapshot is not valid JSON: {allowlist.estimates_snapshot}"
                )
        if args.store in ("gateway", "both"):
            stores["gateway"] = parse_gateway_store(allowlist, window, billing)
        if args.store in ("claude", "both"):
            stores["claude"] = parse_claude_store(allowlist, window)
    except ReadRefusal as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 1
    except OSError as failure:
        print(f"error: unexpected I/O failure: {failure}", file=sys.stderr)
        return 1

    record: dict[str, Any] = {
        "schema": SCHEMA,
        "generatedAt": isoformat(now),
        "window": {
            "requested": args.window,
            "from": isoformat(window.start),
            "to": isoformat(window.end),
        },
        "stores": stores,
    }
    if len(stores) == 2:
        record["overlap"] = {"statement": OVERLAP_STATEMENT}
    record["refusals"] = [dict(refusal) for refusal in REFUSALS]
    if args.estimates is not None:
        record["advisories"] = build_advisories(
            stores.get("gateway"), figures, allowlist.estimates_snapshot
        )

    if args.format == "json":
        print(json.dumps(record, indent=2))
    else:
        print(render_text(record), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
