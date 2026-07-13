# Research role TOMLs (repo-scoped — NOT globally installed)

The 17-role research team from `skills/codex-research-os/`, shipped here as reference
copies so the roster is inspectable and reusable without running the scaffolder.

**These are deliberately NOT symlinked into `$CODEX_HOME/agents/` by the bundle
installer.** They are repo-scoped by design: each role reads/writes a target repo's
`research/` ledgers (claims.yaml, reviews, journal), so a global install would put 17
context-costing roles in every codex session with dangling ledger paths.

Install into a specific research repo either way:

```bash
# preferred — from the bundle root; scaffolds roles, ledgers, workflows, and gates:
mise run research-os:install -- --target /path/to/repo --project-name "Name"

# or copy just the roles into a repo that already has the research/ layer:
cp <bundle>/agents/codex/research/*.toml /path/to/repo/.codex/agents/
```

Roster: research_director, repo_cartographer, literature_scout, novelty_auditor,
theorist, counterexample_hunter, formalizer, experimentalist, benchmark_engineer,
data_engineer, systems_engineer, ablationist, replication_reviewer,
adversarial_reviewer, synthesis_writer, knowledge_librarian, safety_reviewer.
Principles: `skills/agentic-sdlc-orchestrator/references/research-team.md`.
No `model` pins (inherit the host default — see the no-decorative-pins policy).
