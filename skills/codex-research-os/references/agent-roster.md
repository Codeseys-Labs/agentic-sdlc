# Agent Roster

Use these agents as narrow roles, not as personas that can approve their own work.

| Agent | Purpose | Primary Outputs |
| --- | --- | --- |
| research_director | Coordinate loops and enforce discipline | status, next_action, assignments |
| repo_cartographer | Map existing repo/artifacts | memory/repo_map, blockers |
| literature_scout | Map prior art | literature map, paper notes |
| novelty_auditor | Check occupancy/novelty | novelty reviews, prior-art matrix |
| theorist | Generate hypotheses and mechanisms | ideas, claims, theorem statements |
| counterexample_hunter | Falsify claims | counterexamples, adversarial notes |
| formalizer | Make statements checkable | formal specs, proof gaps |
| experimentalist | Design/run experiments | registry, runs, results |
| benchmark_engineer | Build fair evaluation | benchmark plan, comparisons |
| data_engineer | Audit data and leakage | data inventory, validation report |
| systems_engineer | Improve infrastructure | scripts, Makefile, blockers |
| ablationist | Test load-bearing components | ablation plans/results |
| replication_reviewer | Check reproducibility | replication reviews |
| adversarial_reviewer | Attack conclusions | adversarial reviews |
| synthesis_writer | Write grounded reports | reports, status |
| knowledge_librarian | Maintain memory | journal, lessons, resume context |
| safety_reviewer | Block unsafe operations | safety reviews, blockers |

Model tiering, external tools, seeds, or project-specific issue systems are optional project policy. The portable OS only requires files, scripts, and conservative review gates.

## Model Config Policy

Generated roles are provider-neutral, do not dispatch, and contain no static `model` or
`model_reasoning_effort` pin. Before spawn, the conductor loads `model-tier-rightsizing`,
chooses inside the appropriate exact six-model pair, and supplies a conductor-supplied certified
`RuntimeAssignment` with a certified exact model ID and these fields:

- `schema_version`
- `requested_model_id`, `requested_effort`, and `requested_context_form`
- `request_injection_status` and `request_injection_evidence`
- `resolution_state`, `resolved_provider`, `resolved_model_id`, and `model_identity_basis`
- `model_readback_status` and `model_readback_evidence`
- `effort_readback_status` and `effort_readback_evidence`
- `context_readback_status` and `context_readback_evidence`

This is the exact 16-field canonical receipt shape; it has no `*_source` projections. Its
closed evidence binds embedded model/provider/effort/context values and digests to receipt
fields. Validation proves only canonical internal consistency; the external authenticated
harness alone admits and spawns. `resolution_state` must be `resolved`. Exact model/effort
request injection is mandatory and immutable. Effective effort and context may be honestly
unavailable; requested values never become readback. Requested, inherited, unresolved, or
incomplete assignments stop before spawn and return one `SeedProposal` to the conductor. The
selected host or launcher must inject the exact resolved
model and effort. If it cannot inject both, it does not dispatch and returns one `SeedProposal`.
Prompt prose does not enforce a Codex model or effort. Never use an unverified alias or
host-default model selection. An allowlist does not certify a live transport, and `[1m]`
request/base-ID readback is not evidence of intelligence, upstream capacity, compaction, or
effort compliance.
