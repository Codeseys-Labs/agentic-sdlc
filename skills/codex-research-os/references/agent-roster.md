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

Generated roles are provider-neutral and do not select models or pin static effort. Before
any dispatch, the caller loads `model-tier-rightsizing`, chooses inside the appropriate exact
six-model pair, and supplies a runtime assignment with these fields:

- `requested_model_id`
- `requested_effort`
- `requested_context_form`
- `resolution_state` (`requested`, `resolved`, `inherited`, or `unresolved`)
- `resolved_model_id`
- `resolved_effort`
- `resolved_context_form`

The caller records adapter readback and stops when the route is inherited or unresolved.
Never use an unverified alias or host-default model selection for an operational dispatch.
A project may maintain a local exact-ID allowlist for static validation, but allowlisting does
not certify a live transport. `[1m]` request/base-ID readback is not evidence of intelligence,
upstream capacity, compaction, or effort compliance.
