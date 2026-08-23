# Wave `<wave-id>` — evidence

Copy to `docs/evidence/waves/<wave-id>.md`. Fill every field from a command's output, never from a
worker summary; write `unknown` rather than a guess.

## Nodes

| node | role | model_id | disposition | commit | reviewed-by |
|---|---|---|---|---|---|
| `ws-<slug>-<n>` | implementer | `<resolved exact model id>` | accepted \| remediated \| blocked | `<40-hex>` | `ws-<slug>-<m>` |
| `ws-<slug>-<m>` | reviewer | `<resolved exact model id>` | accepted \| remediated \| blocked | — | — |

`model_id` is the id read back from the adapter, not the requested tier. `reviewed-by` names a
different node than its own row; a row reviewed by its author is unreviewed.

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
