# role-manifest conformance fixtures

Static fixtures consumed by `tests/test_role_manifest.py`. Most RED cases are built
in-test by mutating the golden `policy/role-manifest.v1.json`; this directory holds the
fixtures whose exact bytes are load-bearing.

- `coordinated-repin-authority-grab.json` — the CRITICAL anti-bypass fixture. It grants
  the Research Director Seeds-mutation (`queue_authority=mutate`) and strips the
  advisory-only boundary from the reviewer and critic, while leaving
  `generated_from.normative_contract_sha256` bound to the real pinned contract and every
  projection `content_digest` correctly repinned. Validation must STILL fail, because the
  manifest's authority fields are cross-checked against the source-pinned contract and the
  role identity — never trusted as their own source of truth. This proves the manifest is
  not a mutable channel that can widen authority around the `0750cbc` digest pins.
