# Codex Research OS Operating Model

## Structure

Install the following repo-native layer:

```text
.codex/
  config.toml
  agents/*.toml
research/
  README.md
  charter.md
  problem_statement.md
  research_journal.md
  decision_log.md
  status.md
  state/
  claims/
  ideas/
  literature/
  experiments/
  proofs/
  benchmarks/
  data/
  reviews/
  reports/
  memory/
  workflows/
  schemas/
scripts/
Makefile
```

## Evidence Ladder

```text
idea -> conjecture -> small-case support -> experiment support -> replication support -> adversarially reviewed -> formally specified -> formally proved / robustly reproduced
```

Move claims upward slowly. Downgrade quickly when assumptions, baselines, reproducibility, or novelty fail.

## Greenfield Loop

Use for a broad research ambition:
1. Define area.
2. Generate ideas.
3. Score novelty, feasibility, falsifiability, impact, cost, and literature risk.
4. Scout literature.
5. Audit novelty.
6. Pick one candidate.
7. Run the cheapest decisive experiment or proof check.
8. Review.
9. Kill, iterate, pivot, or promote.

## Brownfield Loop

Use for existing code, papers, benchmarks, or dossiers:
1. Map repo.
2. Identify build/test/benchmark commands.
3. Reproduce or define baseline.
4. Inventory claims conservatively.
5. Find gaps.
6. Run cheapest decisive test.
7. Compare to baseline.
8. Run replication and adversarial review.
9. Update ledgers and next action.

## Review Gates

Treat `make review-gates` as the minimum final-synthesis guard. It should flag:
- promoted empirical/benchmark claims without replication review;
- proof-like claims without proof/formalization evidence;
- novelty-like claims without novelty review evidence;
- important promoted claims without adversarial review evidence.

The gate is intentionally conservative; project-specific gates may be stricter.

## Agent Config Gate

Run `make validate-agents` before trusting a generated research team. The gate checks that `.codex/agents/*.toml` contains only known top-level keys, that agent names match filenames, that reasoning efforts are known values, and that any explicit `model` pins are allowlisted.

Absent `model` fields are intentional: they avoid fake model claims and let the host Codex configuration choose the actual model.
