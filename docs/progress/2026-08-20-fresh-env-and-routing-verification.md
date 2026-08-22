# Fresh-environment install, Bedrock, and gateway routing: executed verification

2026-08-20

Three parallel test lanes answered one operator question by execution: can agentic-sdlc and
ccodex be installed in a fresh environment on top of a Claude Code installation, used,
customized, and extended with the external libraries — and does the routed-model plane work?
Every claim below was executed on this date; wall times and counts are point-in-time
observations of that run, not standing guarantees.

## Lane 1 — fresh container, no credentials (`asdlc-fresh`, ubuntu:24.04)

The documented first-use journey ran exactly as AGENTS.md describes, as an unprivileged user,
cloning from a read-only mount of the checkout at this commit:

- mise installed via its official installer; `mise trust ./mise.toml` explicit; then
  `mise --locked install` completed clean on the first attempt in 74 seconds.
- `bundle:install -- --agent claude` landed 24 entries, `-- --agent codex` 19 more;
  `bundle:status` closed with its terminal line `43 ok, 0 conflict, 0 absent`.
- `operator-tools:install`/`status` reported `2 ok`; the installer self-test passed;
  `mise run validate` finished in under two seconds.
- Customization boundary held: a hand-written operator skill created beside the installed
  plane stayed a plain file — not adopted, not overwritten, not reported as owned.
- One harness note for anyone repeating this: a read-only bind mount trips git's
  dubious-ownership guard until `safe.directory` covers it. A real operator cloning from a
  remote never sees this.

## Lane 2 — external libraries through their own front doors (same container)

- **ECC**: the surface-cost gate refused without its acknowledgement flag, the dry run
  planned without acting, the real run landed skills/agents/commands in the container home
  matching ECC's documented cost figures exactly, and an identical second run changed
  nothing — idempotent.
- **hyperresearch**: the front door installed only the CLI, exactly as the doctrine states;
  the CLI's own `install --global` verb then wrote the skill and agent files. Finding: this
  bundle's enumeration metadata trails upstream 0.10.0 by two agent files, so
  `libraries:status` under-reports the surface (seed `agentic-sdlc-927e`).
- **mattpocock/skills**: the documented one-line install fails on an unauthenticated
  Claude Code — no marketplaces are configured in a fresh, logged-out install, contradicting
  the upstream README's no-add-needed claim. The bundle's task failed honestly with the real
  exit code. The authenticated-session prerequisite needs recording (seed
  `agentic-sdlc-b3aa`).

## Lane 3 — Bedrock without ccodex (`asdlc-bedrock`)

Claude Code 2.1.238 installed fresh, configured for Bedrock via a bearer token passed only
through the container environment. The smoke ping answered through
`us.anthropic.claude-haiku-4-5-20251001-v1:0` in under five seconds. The whole mise/bundle
pipeline then ran identically to the credential-free lane — it never touches model routing —
and a Bedrock-routed `claude -p` listed all twelve bundle skills and five commands by name,
proving the installed plane is visible in-context under Bedrock. Methodology note: a
non-interactive `-p` file-path confirmation from an arbitrary directory answers from
convention, not disk, because the session sandbox scopes to the invocation directory; health
checks should ask for skill listings instead.

## Lane 4 — ccodex gateway on the operator host

The native half and every honesty control passed: launch refused at exit 3 on this
Bedrock-exporting host with a precise explanation; a clean-environment launch served the
native ping through the operator's own login; the catalog failed closed while the gateway was
down; `status` declined to assert liveness it could not verify; provider-add warned
unprompted about its own not-live misrouting window; key injection is stdin-only with an
explicit argv warning; `set-fast-model` cancelled without persisting.

The routed half is **confirmed working end to end** — with a lesson about verification. A
first pass concluded the routed request silently fell back to the native subscription; a
receipt-verified retest retracted that: both the friendly id and the cache id reached
provider `muse` with `status=200` receipts, the gateway normalizing away the
`claude-ocx-<provider>--` prefix and the `[1m]` marker. The false negative came from treating
`ocx observe logs --jsonl` as an append-only ledger when it is a bounded, non-deterministic
rolling window. Two findings stand: the cosmetic `unrecognized_model` diagnostic on every
routed launch reads as a failure and misleads (seed `agentic-sdlc-1565`, corrected in place),
and a Bedrock-shaped Anthropic model id in `ANTHROPIC_DEFAULT_*_MODEL` slips the launch
refusal set and 400s at the Codex upstream (seed `agentic-sdlc-41cb`). OpenRouter provider
onboarding stopped honestly at the `ocx sync` boundary: completing it rewrites the shared
`~/.codex` configuration, which needs its own operation-specific approval, and the account
subsystem cannot store a key for a provider that is not yet live. The provider add was fully
reverted.

## Verdict

A fresh-environment operator install of agentic-sdlc plus operator tools is real today, on
plain and Bedrock-configured Claude Code alike, and the ccodex gateway serves both catalogs
in one session with its refusal controls holding. The external-library story is real for ECC
and hyperresearch and blocked for mattpocock/skills only by the unauthenticated-marketplace
prerequisite. Both test containers were left running for iteration: `asdlc-fresh` and
`asdlc-bedrock`.
