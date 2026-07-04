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

Generated agents should not pretend to select unavailable models. The default portable scaffold omits `model`, so subagents inherit the active/default Codex model selected by the host. It sets only `model_reasoning_effort` and `sandbox_mode`.

If a project intentionally pins models, use real Codex model ids only and run `make validate-agents`. The default allowlist is:

- `gpt-5.4`
- `gpt-5.5`
- `openai.gpt-5.4`
- `openai.gpt-5.5`

Override with `CODEX_RESEARCH_OS_ALLOWED_MODELS=model-a,model-b` when a host has a different verified model catalog.
