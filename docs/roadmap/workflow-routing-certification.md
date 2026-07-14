# Workflow routing certification

**Seed:** `agentic-sdlc-orchestrator-wt-roadmap-docs-addd` — closed.

## Result

All 12 requested calls succeeded. The routing evidence exposed a resolved base model ID for every successful call. It did **not** expose a resolved effort value or a distinct resolved `[1m]` context signal. Those fields remain **unverified**; downstream work therefore uses bounded decomposition rather than assuming the requested effort or context suffix took effect.

| Requested call | Success token | Visible resolved base model | Resolved effort | Distinct resolved `[1m]` context signal |
|---|---|---|---|---|
| Sol `high` | `ROUTE_OK:sol-high` | `gpt-5.6-sol` | unverified | not applicable/requested without suffix |
| Sol `xhigh` | `ROUTE_OK:sol-xhigh` | `gpt-5.6-sol` | unverified | not applicable/requested without suffix |
| Sol `[1m] high` | `ROUTE_OK:sol-1m-high` | `gpt-5.6-sol` | unverified | unverified |
| Sol `[1m] xhigh` | `ROUTE_OK:sol-1m-xhigh` | `gpt-5.6-sol` | unverified | unverified |
| Terra `xhigh` | `ROUTE_OK:terra-xhigh` | `gpt-5.6-terra` | unverified | not applicable/requested without suffix |
| Terra `max` | `ROUTE_OK:terra-max` | `gpt-5.6-terra` | unverified | not applicable/requested without suffix |
| Terra `[1m] xhigh` | `ROUTE_OK:terra-1m-xhigh` | `gpt-5.6-terra` | unverified | unverified |
| Terra `[1m] max` | `ROUTE_OK:terra-1m-max` | `gpt-5.6-terra` | unverified | unverified |
| Luna `high` | `ROUTE_OK:luna-high` | `gpt-5.6-luna` | unverified | not applicable/requested without suffix |
| Luna `xhigh` | `ROUTE_OK:luna-xhigh` | `gpt-5.6-luna` | unverified | not applicable/requested without suffix |
| Luna `[1m] high` | `ROUTE_OK:luna-1m-high` | `gpt-5.6-luna` | unverified | unverified |
| Luna `[1m] xhigh` | `ROUTE_OK:luna-1m-xhigh` | `gpt-5.6-luna` | unverified | unverified |

## Evidence and limitation

The durable workflow journal contains twelve success results, one per requested shape. Minimal response records show the base model IDs above. The available records do not contain a provider readback field for resolved effort or a distinct context-resolution field for `[1m]`; requested labels and echoed success tokens do not prove either field resolved.

This certification therefore verifies dispatch success and base-model resolution only. It does not certify effective effort, extended-context behavior, or capacity. Work that would rely on those unexposed fields must be split into bounded artifacts with explicit stop conditions and independently verifiable outputs.
