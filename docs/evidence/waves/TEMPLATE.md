# Wave `<wave-id>` — evidence

Copy to `docs/evidence/waves/<wave-id>.md`. Fill every field from a command's output, never from a
worker summary; write `unknown` rather than a guess.

## Nodes

| node | role | model_id | disposition | commit | reviewed-by |
|---|---|---|---|---|---|
| `ws-<slug>-<n>` | implementer | `<resolved exact model id>` | accepted \| approved-skip \| blocked | `<40-hex>` | `ws-<slug>-<m>` |
| `ws-<slug>-<m>` | reviewer | `<resolved exact model id>` | accepted \| approved-skip \| blocked | — | — |

`model_id` is the id read back from the adapter, not the requested tier. `reviewed-by` names a
different node than its own row; a row reviewed by its author is unreviewed.

The disposition column is node-plane vocabulary, closed at those three values and distinct from
the wave-level outcome below: `accepted` means the reviewing node accepted the workstream —
including after findings were fixed and re-reviewed; `approved-skip` names the approval that
skipped the node; `blocked` states its reasons. Wave words (`remediation-progress`,
`unknown-effect`, ...) never appear in this column.

## Outcome

- `outcome`: `<accepted | remediation-progress | blocked | aborted | failed | unknown-effect>`
- `reasons`: `<named reasons, for every outcome other than accepted>`

Exactly one of those six values (product spec Implementation Decision 61) — free text is not an
outcome. The first three state what the recorded evidence shows; the last three state how the
execution ended, which only the conductor's own record carries. `unknown-effect` dominates: no
other record or artifact talks it down, and recovery follows it. An ended state overrides
completion evidence — a wave whose gate passed is still `failed` if its execution ended failed.
A blank or unfillable `outcome` is a named gap that fails closed: no reader (including a Release
Validity derivation) ever reads an absent outcome as `accepted`.

## Operator approval

> `<the operator's verbatim approval, quoted exactly as written, including its date>`

The quoted date must precede the committer date below. An approval recorded after the effect it
authorizes is not an approval.

## Integration

- Integration commit: `<40-hex>` — base `<base-ref>`, branch `<work/<seed-id>-<slug>>`
- Committer date: `<git show -s --format=%cI <integration-commit>>`

## Gate receipt

Recorded on the MERGED head with
`python scripts/gate_receipt.py record --gate "mise run check" --out <path> -- mise run check`. A
worktree-head receipt is not evidence about the merged tree.

- `self_digest`: `<from that receipt>`
- `outcome`: `<passed | failed | unobserved — the receipt's field, never an exit code>`
- `head.commit`: `<40-hex — must equal the integration commit above>`

Everything above is evidence. None of it authorizes push, publication, PR mutation, merge,
deployment, or any other outward effect; each needs explicit operation-specific authorization.
