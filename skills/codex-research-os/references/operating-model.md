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

Run `make validate-agents` before trusting a generated research team. The gate checks that
`.codex/agents/*.toml` contains only known top-level keys and that names match filenames.
Provider-neutral role files intentionally omit both static `model` and
`model_reasoning_effort`; the runtime assignment—not a host default or prompt prose—selects
the route. Roles consume the assignment and never dispatch themselves.

Before spawn, the conductor provides the assignment outside the static role manifest. It is a
conductor-supplied certified `RuntimeAssignment`:

```yaml
requested_model_id: <certified exact ID>
requested_effort: low|medium|high|xhigh|max
requested_context_form: base|<transport-certified exact [1m] form>
request_injection_status: verified
request_injection_source: <non-unknown immutable launcher/adapter request source>
request_injection_evidence: <non-unknown immutable exact model/effort request receipt>
resolution_state: requested|resolved|inherited|unresolved
resolved_provider: <independent observation or unique exact-ID mapping>
resolved_model_id: <exact ID verified by independent readback or mapping>
model_readback_status: verified
model_identity_basis: independent_readback|unambiguous_exact_id_mapping
model_readback_source: <independent source or unavailable_in_transport for mapping>
model_readback_evidence: <immutable receipt or immutable policy mapping reference>
effort_readback_status: verified|unavailable
effort_readback_source: <independent source or unavailable_in_transport>
effort_readback_evidence: <immutable receipt or unavailable_in_transport>
context_readback_status: verified|unavailable
context_readback_source: <independent source or unavailable_in_transport>
context_readback_evidence: <immutable receipt or unavailable_in_transport>
```

`resolution_state` must equal `resolved`. Exact model and effort request injection is mandatory
and immutable. An independently observed provider/model source may be unavailable only when an
unambiguous exact-ID mapping plus immutable request/model evidence verifies identity. Effective
effort and context may be honestly unavailable; requested values never become readback. Requested,
inherited, or unresolved assignments stop before spawn and return one `SeedProposal` to the
conductor. The selected host or launcher must inject the exact requested model and effort before
spawn. If it cannot inject both, it does not dispatch and returns one `SeedProposal`; prompt prose
does not enforce a Codex model or effort. `[1m]` readback does not establish intelligence,
upstream context capacity, compaction, or effort compliance.
