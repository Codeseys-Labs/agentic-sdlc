# dd04 — Honest usage accounting (V41): design note

- **Seed:** `agentic-sdlc-dd04` — "design honest usage accounting (V41): exact/lower-bound/unpriced lanes" (open, priority 3)
- **Spec anchors:** ID59 (spec:391-393), stories 87-89 (spec:177-179); spec test 24 (accounting), test 23 (golden human/JSON views), test 26 (privacy)
- **Anti-pattern to avoid:** ADR-0030 records that `sdlc-observability-projection.py` (1,928 source lines, 3,657 test lines) **never produced output** — no document carrying its schema exists anywhere. The failure mode was building a projection stack nothing consumed. This design starts from evidence that already exists and a reader that already wants it.
- **Date / method:** 2026-08-24. Every schema below was read from the live host (read-only); doc claims were fetched from code.claude.com the same day. No gateway state was mutated; no repo file was edited.

## 1. Evidence-source inventory (verified)

### A. `~/.opencodex/usage.jsonl` — the gateway's per-request log (primary store)

47.5 MB, 36,702 lines, **1 unparseable line** (a torn write; the reporter must survive and count it). One JSON object per request. Fields verified by full-file aggregation:

| Field | Coverage | Values seen |
|---|---|---|
| `requestId`, `timestamp`, `provider`, `model`, `admissionKind`, `status`, `durationMs`, `usageStatus` | 36,701 (all parsed) | providers: `openai` 34,096, `anthropic-native` 1,540, `muse` 1,055, `openrouter` 10; `admissionKind` all `loopback` |
| `usageStatus` | all | `reported` 35,534, `unreported` 1,167 — the log itself distinguishes measured from unmeasured |
| `usage` object | 35,534 | `inputTokens`, `outputTokens`, `totalTokens`, `cachedInputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `reasoningOutputTokens` |
| `requestedModel` / `resolvedModel` | 36,402 / 34,630 | `requestedEffort` on 32,301 |
| `surface` | 11,507 | only value: `"claude"` (Claude Code turns); **absent on 25,194 rows** (Codex-CLI and other loopback clients) |
| `conversationId` | 36,347 | 32-hex hash — **not** a Claude Code sessionId; no provable join |
| `routeDecision.routeKind` | 34,862 | `native` 33,708, `explicit-provider` 1,066, **`default-provider` 88** (the fa32 misroute alarm), absent 1,839 |
| `attempts[]` | 33,139 | per-attempt provider/model/adapter/status/usage — retries carry usage per attempt |
| error fields | `errorCode`/`closeReason` 868, `upstreamError` 244 | HTTP: 200×35,833, 499×441 (client closed — tokens may have burned upstream unreported), 429×93, 502×154, 400×127, 401×49 |

**No dollar field exists anywhere in this log.** Token counts only.

**Token convention (load-bearing):** gateway `inputTokens` is **cache-inclusive** (verified: anthropic-native row `inputTokens: 49215, cacheCreationInputTokens: 49057, outputTokens: 7, totalTokens: 49222`). Claude transcripts use the Anthropic convention where `input_tokens` is **cache-exclusive** (verified row: `input_tokens: 2, cache_creation_input_tokens: 52347`). Summing across the two stores is therefore dishonest twice over: overlapping turns AND incompatible units.

Caution for implementers: `usage.jsonl` sits beside `admin-api-token` and `config.json` in `~/.opencodex/`. The reporter's file allowlist is exactly one file in that directory.

### B. `ocx observe usage [--json]` — the gateway's own aggregation

Read via the sanctioned `mise exec -- ocx observe` route (opencodex 2.28.0). Emits: `summary` (requests, attemptCount, measured/reported/unreported/unsupported/estimated request counts, token sums, `coverageRatio` 0.968 on this host, `estimatedCostUsd`, `pricedRequests`/`unpricedRequests`/`unmeteredRequests`), plus `days`, `models`, `providers`, `accounts` breakdowns and honesty fields (`historyTruncated`, `truncatedPrefixBytes`, `entriesTruncated`, `entriesDropped`, `snapshotWindowStart/End`).

**The central defect this design exists to not repeat:** `estimatedCostUsd` prices **subscription lanes at API list rates**. Verified on this host:

- `anthropic-native` (turns riding the operator's `sk-ant-oat*` subscription login through the gateway): `estimatedCostUsd: 45.00`. Spec story 88 says exactly this number must never be presented as a cost.
- `openai`: `estimatedCostUsd: 3641.17` — but `ccodex ocx configure account list` shows the openai account is `TYPE codex, PLAN pro, ID main`: a **ChatGPT subscription**, not a metered key. $3641 is a counterfactual, not a bill.
- `muse` (an `api-key` account): **no** `estimatedCostUsd` at all — the gateway's price table doesn't cover it, so even the metered lanes are only partially priced.
- `accounts` attribution is honest about its own limits: 34,001 of 36,701 requests fall under `accountLogLabel: "legacy-ambiguous", ambiguous: true`.

Conclusion: `ocx observe usage` is a good **token** witness and a bad **cost** witness. The reporter may quote its estimate only as a named advisory, never as a lane value.

### C. `ocx observe logs --jsonl` — same records, streamed

Same per-request schema as (A) with richer terminal fields (`terminalStatus`, `tierOutcome`, per-attempt `displayMetrics`). `ccodex status` itself prints this as the attribution stream; it is the one upstream-plane command an agent may run unaided (ccodex-ocx-configuration.md). Requires a running gateway; (A) does not.

### D. `ccodex ocx configure account list` — the billing-kind witness

Sanctioned read-only route. `TYPE` column distinguishes `codex` (subscription; PLAN `pro`) from `api-key` (metered: muse, openrouter). This is the only local surface that states which lane a provider's spend actually lands in. It prints fingerprint labels, never key values.

### E. Claude Code transcripts — `~/.claude/projects/<project-slug>/<session-id>.jsonl`

Native, no Admin API. Every assistant record carries `message.model` and `message.usage`:
`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens_details.thinking_tokens`, `service_tier`, `cache_creation.{ephemeral_1h,ephemeral_5m}_input_tokens`, `server_tool_use.{web_search,web_fetch}_requests`. Top-level: `sessionId`, `uuid`, `parentUuid`, `timestamp`, `version`, `type`, `isSidechain`, `entrypoint` (`cli` / `sdk-py`), `effort`, and on some records `attributionSkill`.

Verified limits: `<synthetic>` model rows exist with all-zero usage (error placeholders — exclude); in the 3 most recent sessions scanned, `isSidechain` was only ever `false` and **no workflow/teammate/agent-name field exists** — session files of spawned teammates carry no verified link to their parent. Per-workflow and per-teammate attribution is therefore `missing`, not derivable.

Note for this host: `CLAUDE_CODE_USE_BEDROCK` is exported (ccodex status: "BYPASSED"), so native sessions here bill to AWS Bedrock — an API-metered lane whose dollars are a fact **only in the AWS bill**, absent from every local surface.

### F. Statusline stdin JSON — session-scoped, already consumed in-repo

`assets/claude/statusline-command.sh` (the packaged `agentic-sdlc-statusline`) reads `.model.id`, `.effort.level`, `.context_window.*`, `.cost.total_cost_usd`, `.cost.total_duration_ms`, `.rate_limits.five_hour.used_percentage`, `.rate_limits.seven_day.used_percentage`, `.transcript_path`. Ephemeral (exists only during a session), and the docs state the dollar figure is computed **locally from token counts priced at standard list rates** — for subscribers "the session cost figure isn't relevant for billing purposes" (code.claude.com/docs/en/costs, fetched 2026-08-24). The rate-limit percentages are the honest subscription-lane display: share-of-window is a fact; dollars are not.

### G. `~/.claude/stats-cache.json` — native local aggregate

Verified shape: `dailyActivity[]`, `dailyModelTokens[]` (`tokensByModel`), `modelUsage.<model>.{inputTokens,outputTokens,cacheReadInputTokens,cacheCreationInputTokens,webSearchRequests,costUSD,contextWindow}`. Same caveat: `costUSD` is a local list-rate computation, not a bill. Useful as a cross-check on transcript sums; never a cost source.

### H. Excluded surfaces

OpenTelemetry export (docs: "the only option that streams per-user token and cost metrics") is **egress** — excluded by the no-telemetry vision (spec:82-83, V44). The Admin/Analytics APIs are org-plane and out of scope by the seed's own framing. `/usage` and `/insights` are interactive-only surfaces, not files; their documented semantics are cited above but they are not reporter inputs.

## 2. Lane semantics

Two orthogonal axes. Every reported value carries both.

### Billing lanes (where a turn's cost lands)

| Lane | Membership rule (verified witness) | Marginal cost |
|---|---|---|
| `subscription:anthropic` | gateway rows `provider: anthropic-native` (the launch route only admits `sk-ant-oat*` logins — AGENTS.md `ocx:launch`) | **unknown by design — never priced** |
| `subscription:codex` | gateway rows for a provider whose account TYPE is `codex` (witness D) | **unknown by design — never priced** |
| `api:<provider>` | gateway rows for a provider whose account TYPE is `api-key` (muse, openrouter) | a fact on the provider's bill; locally `missing` unless provider-metered evidence exists (none does today) |
| `cloud:<provider>` | native transcripts produced under a provider-routing switch (e.g. Bedrock) | a fact in the cloud bill; locally `missing` |
| `native:claude` | transcripts with no gateway/cloud routing in effect | subscription or Console depending on login; default **unpriced** |

Unknown or undeclarable billing kind fails **toward not-pricing**: a lane the reporter cannot classify is treated as subscription for pricing purposes.

### Measurement labels — the closed vocabulary (spec story 87)

Applied per value, to usage and to cost independently:

- **`exact`** — provider-reported numbers covering the whole queried window: token sums over rows with `usageStatus: "reported"` when the window has no incompleteness marker. Token counts are provider-metered (they return in API responses); they are the only values that can ever be `exact` today.
- **`lower-bound`** — a sum known to be incomplete, with the incompleteness *named and counted*: any window containing `unreported` rows, the unparseable line, `historyTruncated`/`entriesDropped` ≠ 0, or 499-closed requests whose usage never came back. Rendered as "≥ N tokens (M requests unmeasured)". Unknown never appears as zero.
- **`unpriced`** — the quantity is measured but a marginal price is **not a fact for this lane**: every subscription lane's cost. A subscription turn is never priced as if API-billed, full stop.
- **`missing`** — the dimension is a fact somewhere but no local evidence carries it: api/cloud-lane dollars, per-workflow ownership, per-teammate ownership, cross-store turn identity.
- **`stale`** — evidence exists but its window ends before the queried window: gateway down and `usage.jsonl` unwritten since `snapshotWindowEnd`; `stats-cache.json` `lastComputedDate` older than the query. Rendered with the evidence timestamp, never silently reused.

Distinction worth keeping sharp: `unpriced` = pricing the value would invent a fact (subscription); `missing` = the fact exists but not here (OpenRouter's bill, AWS's bill).

### Ownership separation (spec story 89)

Within what the evidence supports, no further:

- Gateway store: by `surface` (`claude` vs unattributed), `provider`/`resolvedModel`, `conversationId`, `accountLogLabel` (with `legacy-ambiguous` reported as its own bucket, never redistributed).
- Transcript store: by `sessionId`, `isSidechain`, `entrypoint`, `message.model`; `attributionSkill` where present.
- **No cross-store grand total exists in the output.** Gateway `surface:"claude"` rows and transcript rows describe overlapping turns with no provable join (`conversationId` ≠ `sessionId`) and incompatible input-token conventions. The two stores render as two sections with a named overlap warning. This is how nested activity is not double counted: by refusing the sum, not by guessing the join.

## 3. The reporter

### Surface

- **One script:** `scripts/usage_report.py` (mise-managed uv Python 3.12, stdlib only).
- **One mise task:** `usage:report` — advisory, **never** referenced by `check`, `lefthook.yml`, or CI (same posture as `mermaid:*`).
- **Not** a ccodex verb in v1: mounting `ccodex sdlc usage` requires wrapper changes plus an operator-tools reinstall; it is the natural v2 home beside `sdlc status` (spec ID58 already classes these as disposable read-only projections) once the script exists to mount.

```
mise run usage:report -- [--window 24h|7d|30d|all] [--store gateway|claude|both]
                         [--format text|json] [--estimates]
                         [--billing <provider>=subscription|api-key ...]
```

- Default: `--window 7d --store both --format text`, **no dollar figures anywhere**.
- `--estimates`: adds an `advisories` section quoting the gateway's own `estimatedCostUsd` per api-key lane verbatim, each line carrying "list-rate estimate, not a bill", with subscription lanes excluded **by name** ("anthropic-native: excluded — subscription, marginal cost unknown"). Without `--billing` declarations beyond the built-in `anthropic-native → subscription` rule, undeclared providers are excluded from estimates too.
- Exit codes: 0 including when every value is `missing`/`stale` (honest absence is a successful report); 2 usage error; 1 unexpected I/O failure. Never nonzero for absent evidence.

### Reads (closed allowlist — everything else is out of bounds)

1. `~/.opencodex/usage.jsonl` — only this file in that credential-adjacent directory; tolerant parse (bad line → counted, window → `lower-bound`); unknown `usageStatus` values → treated as unmeasured.
2. `~/.claude/projects/*/*.jsonl` — parse **only** `type`, `timestamp`, `sessionId`, `isSidechain`, `entrypoint`, `attributionSkill`, `message.model`, `message.usage`. Prompt/content bodies are never read into the report (spec test 26); `<synthetic>` rows excluded from sums.
3. `~/.claude/stats-cache.json` — optional cross-check of transcript token sums; its `costUSD` is never read into output.

No shell-outs in v1 (no `ocx`, no `ccodex`): the report works with the gateway down, and adds no dependency on gateway liveness. Residual accepted and stated: direct `usage.jsonl` parsing couples to an opencodex-2.28.0-era private schema; the reporter pins the fields above, classifies unrecognized shapes as unmeasured, and prints the gateway version it cannot verify as `schema: best-effort (opencodex private file)`.

### Output shape

One semantic JSON record; the text view renders from the same record (spec test 23). Sketch:

```json
{
  "schema": "agentic-sdlc/usage-report@1",
  "generatedAt": "...", "window": {"from": "...", "to": "...", "requested": "7d"},
  "stores": {
    "gateway": {
      "evidence": {"path": "~/.opencodex/usage.jsonl", "parsedRows": 36701, "badLines": 1,
                   "windowEnd": "...", "freshness": "exact|stale"},
      "lanes": [
        {"lane": "subscription:anthropic", "provider": "anthropic-native",
         "requests": {"value": 1540, "label": "exact"},
         "tokens": {"value": 108880898, "unit": "gateway-total (cache-inclusive)",
                    "label": "lower-bound", "unmeasuredRequests": 95},
         "cost": {"label": "unpriced", "statement": "subscription marginal cost is unknown"}},
        {"lane": "api:muse", "cost": {"label": "missing",
         "statement": "metered on the provider's bill; no local evidence carries it"}}
      ],
      "misroutes": {"defaultProviderRows": 88, "note": "routeKind default-provider is an alarm (seed fa32)"}
    },
    "claude": {"unit": "anthropic message.usage (cache-exclusive)", "sessions": [...], "byModel": [...]}
  },
  "refusals": [ ... see §4 ... ],
  "advisories": [ ... only with --estimates ... ]
}
```

Closed enums: `label ∈ {exact, lower-bound, unpriced, missing, stale}`; lane kinds as in §2; every token value names its unit convention.

## 4. What the reporter refuses to claim

Emitted verbatim in the `refusals` array so absence is visible, not silent:

1. **No cross-store total.** Gateway and transcript stores overlap unprovably and count input tokens differently; any combined number would double-count and mix units.
2. **No per-turn cost attribution.** No local surface carries a provider-metered dollar for any single request.
3. **No subscription dollars, ever** — not even "estimated": story 88 verbatim. The gateway's $45.00/$3641.17 figures for the two subscription lanes are reported only as the defect they are.
4. **No per-workflow / per-teammate ownership.** Transcripts carry no verified linkage from a spawned agent's session to its parent; the label is `missing`, not a heuristic split.
5. **No session→conversation join.** `conversationId` (32-hex) and `sessionId` (UUID) do not correlate by any verified rule.
6. **No completeness claim.** `legacy-ambiguous` account rows (34,001 of 36,701), surface-less rows (25,194), and unreported-usage rows (1,167) are counted buckets, never redistributed into named lanes.
7. **No budget authority.** A usage report grants nothing and retroactively authorizes nothing (spec test 24: "no retroactive budget authority").

## 5. Non-goals

- **No telemetry, no egress, no network I/O at all.** Local files in, stdout out.
- **Never a gate leaf.** Not in `check`, hooks, or CI; a beautiful report is evidence of nothing.
- **No daemon, warehouse, or dashboard** (spec ID58). Disposable projection over canonical local artifacts — the ADR-0030 lesson applied: the canonical artifacts already exist and are not ours.
- **No writes**: no cache, no state file, no receipt. Rerunning is the refresh.
- **No price-table maintenance.** Prices rot; the reporter carries none. Dollar strings enter only as the gateway's own quoted estimate under `--estimates`.
- **No gateway interaction**, mutation or read; no dependency on gateway liveness.

## 6. Build estimate

- `scripts/usage_report.py`: ~350-450 lines (two parsers, lane classifier, label logic, JSON+text renderers).
- Tests `tests/test_usage_report.py`: ~500-700 lines against synthetic fixtures (spec test 19 pattern: offline, synthetic usage) — no test reads the real `~/.opencodex` or `~/.claude`.
- `mise.toml` task stanza + AGENTS.md task-list line (the inventory paragraph demands re-diffing) + a short `docs/` note or ADR-worthy paragraph recording the subscription-never-priced rule.
- One implementer worktree wave, one reviewer; roughly 1-2 sessions of work. No new tools, no new dependencies.
- Follow-up seeds to file (not this seed's scope): (a) upstream/wrapper: `ocx observe usage` prices subscription lanes at list rates — at minimum document, ideally propose an upstream `billingKind` field; (b) v2 mount as `ccodex sdlc usage`; (c) transcript teammate-linkage investigation if per-agent ownership is ever wanted.

## 7. Acceptance tests

1. **Subscription-never-priced:** fixture with `anthropic-native` and codex-account rows → no dollar value appears in any subscription lane in either format, with and without `--estimates`; cost renders `unpriced` + the unknown statement. Mutation control: point the classifier at api-key and assert the test fails.
2. **Unknown-never-zero:** fixture with `unreported` rows → token label `lower-bound`, unmeasured count named; totals never render the unmeasured as 0.
3. **No cross-store sum:** fixture with overlapping gateway/transcript activity → assert no key or line combines the stores; the overlap warning is present.
4. **Unit honesty:** gateway section says cache-inclusive, transcript section says cache-exclusive; both unit strings asserted.
5. **Torn line:** fixture with one malformed line → parse succeeds, `badLines: 1`, window labeled `lower-bound`.
6. **Stale:** fixture whose last timestamp predates `--window 24h` → `freshness: stale` with the evidence timestamp; exit 0.
7. **Missing dimensions:** per-workflow query surface renders `missing` (never a guess); exit 0.
8. **Synthetic exclusion:** `<synthetic>` transcript rows excluded from all sums (positive control: a real row is included).
9. **Read-only + allowlist:** reporter opens no path outside the three allowlisted patterns and opens nothing for write — asserted by monkeypatched `open`/`Path.open` recording every access; a fixture `admin-api-token` beside the fixture `usage.jsonl` is never touched.
10. **Privacy:** transcript fixture with a credential-shaped string and a prompt body in message content → neither appears in any output (spec test 26 pattern).
11. **Golden views:** text output is derived from the JSON record; golden pair kept in sync by rendering both from one fixture.
12. **Gate independence:** `usage:report` absent from `check` dependencies and `lefthook.yml` (asserted against the parsed task/hook definitions, not by prose).
13. **Estimates advisory:** with `--estimates`, api-key lanes quote the gateway figure verbatim with "not a bill"; undeclared and subscription providers are excluded by name; without the flag, the string `$` does not occur in output.
