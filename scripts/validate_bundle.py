#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Validate Agentic SDLC bundle metadata and the repository's trust-boundary pins.

Scope rule, after the 2026-08-22 shrink (seed agentic-sdlc-ab6a, epic agentic-sdlc-3c90): a
check earns its place here only if it guards the DELIVERED PAYLOAD or a TRUST BOUNDARY, and only
if no runtime consumer already fails on the same input. The three payload guards are
`validate_skills` (name==dirname, the Codex 1024-char description cap, and every
`references/*.md` a skill instructs an agent to read — the installer symlinks skill directories
without parsing a byte of frontmatter, so nothing else checks these), `bash -n` over the shipped
shell CLI, and `compile()` over the shipped Python. The trust boundaries are the
protected-role authority pins over shipped `agents/` bytes, the authority-projection scan and
closed roster over all 33 of those role files, the Mermaid supply-chain digests
(ADR-0006: that component downloads and executes a browser), the secrets-gate config,
the release-candidate honesty disclosures, and the gate graph's own shape.

What was deleted, and why it needed no replacement: nine policy documents were re-derived
structurally here while their runtime consumers parsed the same files anyway and four of them
were ALSO digest-pinned inside the very same function, so the digest strictly dominated the
structure. `mise.toml` was re-stated as a Python dict; `mise.lock` — which carries the resolved
version, backend, and per-platform checksum of every pin — is the integrity control, so only its
bytes and the gate's own four leaf commands are pinned now. `policy/role-manifest.v1.json`
existed only to be validated: `agents/` is the source of truth, its roster is closed here, and
every one of its 33 files is digest-pinned by the normative runtime contract and scanned for
authority-granting prose. The measured evidence for that class of deletion: setting
`counts.delivery_roles = 99` in the role manifest failed the gate loudly while
`mise run bundle:status` still reported `43 ok` — no operator-visible failure existed to prevent.

Two things this file is not. It is not a review substitute: a policy bump that loses an encoded
checklist is caught by reading the diff. And a passing run is evidence only — it authorizes no
push, publication, merge, or deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import yaml


SECRET_PATTERN = re.compile(
    r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY|amazon\.com/[a-z]|\.a2z\.com|aws\.dev/"
)
# `.js` is here because the workflow overlay payload ships in that suffix; without it a workflow
# document would be the one authored tree the secret-shaped-string scan below never reads.
TEXT_SUFFIXES = {".md", ".mjs", ".js", ".sh", ".ps1", ".toml", ".json", ".yml", ".yaml", ".py"}
# The workflow overlay's authored shape. A workflow's installed name is its identity — it becomes
# the namespaced command a host exposes — so the stem stays a portable lowercase slug and the file
# restates it in a required header line, which is what keeps the declared name and the stem from
# drifting. This is a bundle-local authoring convention, not a claim about a host's file schema.
WORKFLOW_STEM_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
WORKFLOW_HEADER_PREFIX = "// workflow: "
# The host's workflow loader admits a script only when its FIRST STATEMENT is
# `export const meta = {...}` as a PURE literal — no variables, calls, spreads, or
# interpolation — declaring `name` and `description` (`phases` optional), with nothing before it
# but comments and blank lines; the live host refused the shipped scout at load for exactly this
# (agentic-sdlc-60f0). The rules here mirror that contract as a closed grammar: leading
# commentary is `//` line comments only (the required header line already is one), values are
# single-line string literals, and `phases` is an array of them. Stricter than the host refuses
# closed rather than open.
WORKFLOW_META_OPEN_PATTERN = re.compile(r"export[ \t]+const[ \t]+meta[ \t]*=[ \t]*\{")
WORKFLOW_META_KEYS = ("name", "description", "phases")
WORKFLOW_META_KEY_PATTERN = re.compile(r"([A-Za-z_$][A-Za-z0-9_$]*)[ \t\r\n]*:")
WORKFLOW_META_STRING_PATTERN = re.compile(r"'(?:[^'\\\n]|\\[^\n])*'|\"(?:[^\"\\\n]|\\[^\n])*\"")
WORKFLOW_META_FIRST_STATEMENT_ERROR = (
    "the first statement must be an 'export const meta = {...}' literal"
    " (only '//' comments and blank lines may precede it)"
)
WORKFLOW_META_PURE_LITERAL_ERROR = (
    "meta must be a pure object literal (no variables, calls, spreads, or interpolation)"
)
# A workflow script cannot load modules in its documented runtime, so shipping one that tries is
# shipping a document that cannot run.
WORKFLOW_MODULE_LOAD_PATTERN = re.compile(r"\brequire\s*\(|\bimport\s*\(|^[ \t]*import[ \t]", re.MULTILINE)
# A provider-neutral role carries no static model or effort pin; the conductor injects the exact
# requested values at dispatch. A quoted literal in either slot is that forbidden pin.
WORKFLOW_ROUTE_PIN_PATTERN = re.compile(r"\b(?:model|effort)[ \t]*:[ \t]*['\"`]")
# A user-specific home root is host-specific state, never distributable payload. `~` and `$HOME`
# stay legal because they name whichever user runs the host rather than one named account.
WORKFLOW_USER_PATH_PATTERN = re.compile(
    r"/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/|[A-Za-z]:\\+Users\\+"
)
# Compile-only parse probe. A workflow document is an async function body — the documented shape
# uses top-level `await` and a terminal `return`, neither of which parses as a standalone script —
# so it is compiled through the AsyncFunction constructor and never called.
WORKFLOW_PARSE_PROBE = (
    "const fs = require('fs');"
    "const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;"
    # `export` is a module-only keyword that cannot appear in a function body, and the host
    # extracts the required meta statement before it wraps the body. The probe mirrors that by
    # demoting the first `export const meta` to a plain `const` (a non-global regex substitutes
    # once). The pattern is anchored at line start because a `//` comment may quote the phrase
    # without being the statement; it tolerates the same whitespace WORKFLOW_META_OPEN_PATTERN
    # does.
    "const body = fs.readFileSync(process.argv[1], 'utf8')"
    ".replace(/^([ \\t]*)export(?=[ \\t]+const[ \\t]+meta\\b)/m, '$1');"
    "try { new AsyncFunction(body); }"
    "catch (error) { process.stderr.write(String((error && error.message) || error)); process.exit(1); }"
)
# The agent-hook script's authored shape mirrors the workflow header pairing, shifted one line
# down because line 1 of a shell script is its shebang. Lines 3 and 4 declare the settings stanza
# the separately authorized activator builds — a CLOSED event/matcher vocabulary, so shipping a
# hook this bundle's activator cannot wire is a gate failure, not a runtime surprise.
HOOK_SHEBANG = "#!/bin/sh"
HOOK_HEADER_PREFIX = "# hook: "
HOOK_EVENT_PREFIX = "# hook-event: "
HOOK_MATCHER_PREFIX = "# hook-matcher: "
HOOK_EVENT_MATCHERS = {
    "SessionStart": frozenset({"startup", "resume", "clear", "compact", "fork"}),
}
# Self-imposed context-injection budget: the platform documents no size limit for SessionStart
# stdout, so the bundle imposes one on the whole file. A hook that wants to emit more must
# justify raising this cap in review.
HOOK_MAX_BYTES = 4096
REQUIRED_TASKS = {
    "bundle:install",
    "bundle:status",
    "bundle:uninstall",
    "bundle:install:claude",
    "bundle:install:codex",
    "bundle:install:all-hosts",
    "bundle:status:all-hosts",
    "release:build",
    "research-os:install",
    "operator-tools:install",
    "operator-tools:status",
    "operator-tools:retire-aliases",
    "operator-tools:uninstall",
    "operator-tools:self-test",
    "claude:statusline:status",
    "claude:statusline:activate",
    "claude:statusline:deactivate",
    "claude:hooks:status",
    "claude:hooks:activate",
    "claude:hooks:deactivate",
    "claude:workflows:status",
    "claude:workflows:activate",
    "claude:workflows:deactivate",
    "libraries:list",
    "libraries:install",
    "libraries:status",
    "libraries:migrate",
    "ocx:launch",
    "ocx:ultracode",
    "ocx:status",
    "ocx:restart",
    "ocx:configure",
    "mermaid:provision",
    "mermaid:linux-test",
    "test",
    "self-test",
    "secrets",
    "check",
    "hooks:install",
    "contributor:setup",
    "setup",
}
MIN_MISE_VERSION = "2026.4.27"
PYTHON_VERSION = "3.12.11"
NODE_VERSION = "22.23.2"
# The renderer's mmdc version. It is pinned by package-lock.json digest below, NOT by a mise
# [tools] entry: that entry was removed 2026-08-07 (docs/adr/0002 amendment) because puppeteer's
# postinstall came with it and needed a zip archiver mise does not install, failing the whole
# `mise --locked install`. Nothing resolves mmdc through mise, so there is no lock/tool pin here.
MERMAID_VERSION = "11.16.0"
# node 22.23.2 bundles npm 10.9.8, so the M0b renderer's npm identity is pinned in package.json
# as its own `packageManager` value. Provisioning is an explicit operator step and no gate leaf
# invokes it, so this pin never becomes a bootstrap prerequisite.
MERMAID_NPM_VERSION = "10.8.1"
# The renderer supply chain is pinned by exact digest, not by version range: the lock bytes and
# the policy bytes are both hashed, so a dependency edit or a policy loosening fails the gate.
MERMAID_PACKAGE_LOCK_SHA256 = "45d2b754f3b9ad65dd9b88aab2803912db32315eacf71cbd7635d28b088a892e"
MERMAID_POLICY_SHA256 = "ebb2b9d60e06236233e548ccaad6d201097851f0581889f34028c813e9dd850c"
MERMAID_POLICY_SCHEMA = "mermaid-renderer-linux/v1"
MERMAID_PACKAGE_PINS = {
    "@mermaid-js/mermaid-cli": MERMAID_VERSION,
    "@puppeteer/browsers": "3.0.6",
    "mermaid": "11.16.0",
    "puppeteer": "25.3.0",
}
MERMAID_LOCK_RESOLUTIONS = {
    "node_modules/@mermaid-js/mermaid-cli": MERMAID_VERSION,
    "node_modules/@mermaid-js/parser": "1.2.0",
    "node_modules/@puppeteer/browsers": "3.0.6",
    "node_modules/mermaid": "11.16.0",
    "node_modules/puppeteer": "25.3.0",
}
MERMAID_BROWSER_IDENTITY = {
    "build_id": "150.0.7871.24",
    "executable_sha256": "db4fe5b63d1b56729feb1eeebc82967768e66ef823ba942b2d4e506a34dc4a78",
    "cache_tree_sha256": "3afbf64662eb240f67e98b7f352532de67e09dc9dabfd5390172c0c630b7ecfa",
}
# The shipped CLI's shell payload. `bash -n` over these is a payload guard, not machinery
# bookkeeping: a stray `fi` here kills `ccodex launch` on first invocation. They live under
# assets/ or bin/ or are sourced fragments, so the scripts/*.sh glob in validate_scripts misses
# them. `bin/ccodex` is the release tree's self-locating dispatcher; the entry doubles as an
# existence pin, because `bash -n` on a missing path exits nonzero and names it.
SHELL_SYNTAX_PATHS = (
    "assets/claude/statusline-command.sh",
    "assets/claude/session-inheritance.sh",
    "assets/launchers/ccodex.in",
    "bin/ccodex",
    "scripts/opencodex-claude.sh",
)
MERMAID_REQUIRED_ARTIFACTS = frozenset(
    {
        "scripts/provision_mermaid_linux.py",
        "scripts/render_mermaid_linux.py",
        "scripts/sanitize_mermaid_svg.mjs",
        "tests/test_mermaid_renderer.py",
        "tests/test_mermaid_renderer_gate.py",
        "tests_linux/test_mermaid_renderer_e2e.py",
        "tests/fixtures/mermaid-renderer/corpus.json",
    }
)
# Generated trees that are provisioned, not reviewed. Walking them would make the secret scan
# and the gate-graph copy depend on whether a host has run provisioning.
UNREVIEWED_TREES = frozenset({".git", "node_modules", ".mermaid-runtime", "__pycache__"})
# The reviewed lock IS the toolchain integrity control: it carries the resolved version, the
# backend, and a per-platform checksum for every pin, and `settings.locked` makes mise honor it.
# Re-transcribing those 12 rows into Python said the same thing a second time in a weaker
# language, so only the lock's own bytes are pinned here — an edit to a version, a backend, or a
# checksum changes them.
MISE_LOCK_SHA256 = "31ed02eb15e425253e90b3f3b4d117f0b5c3876fa9351e27b6b6375fd47d5b1c"
# The reviewed allowlist for the npm backend. A pin here resolves an arbitrary dependency tree
# whose postinstall scripts run during `mise --locked install`, so each name is screened per
# docs/adr/0002's 2026-08-07 amendment: a pin may not require a tool mise itself does not install.
# Reviewed 2026-08-07 — Seeds runs no install script; opencodex runs one (transitive bun) that
# extracts with Node's built-in zlib; bare npm is npm itself. This catches an UNREVIEWED pin being
# added; it cannot detect that a listed pin's upstream added a hostile postinstall.
NPM_BACKED_TOOLS = frozenset({"npm", "npm:@os-eco/seeds-cli", "npm:@bitkyc08/opencodex"})
# Only the gate's OWN leaves are pinned by exact command. `[tasks.validate] run = "true"` would
# hollow every check in this file, and the same edit to test/self-test/secrets hollows the other
# three leaves, so the four commands `check` depends on are part of the contract. The other ~25
# task rows are convenience wiring: a wrong one is visible the first time an operator runs it.
GATE_LEAF_COMMANDS = {
    "validate": "--script scripts/validate_bundle.py",
    "test": "--with pyyaml==6.0.3 python -m unittest discover -s tests",
    "self-test": "--script scripts/install_skill_bundle.py self-test",
}
# The secrets task runs one stdlib wrapper through the pinned Python. It asks Git for exactly
# tracked + nonignored-untracked files, so ignored operator runtime state is absent without hiding
# a force-tracked file beneath an ignored prefix. The wrapper supplies this explicit tracked config
# to every scanner batch; history scanning remains a separate consent-requiring operation.
SECRETS_CONFIG_PATH = ".config/betterleaks.toml"
SECRETS_SCRIPT_PATH = "scripts/secrets_scan.py"
SECRETS_COMMAND = f"uv run --python {PYTHON_VERSION} --script {SECRETS_SCRIPT_PATH}"
SECRETS_COMMAND_WINDOWS = f"uv.exe run --python {PYTHON_VERSION} --script {SECRETS_SCRIPT_PATH}"
RELEASE_CONTRACT_RELATIVE_PATH = Path("policy") / "release-contract.v1.json"
RELEASE_CANDIDATE_POLICY_RELATIVE_PATH = Path("policy") / "release-candidate.v1.json"
NORMATIVE_CONTRACT_RELATIVE_PATH = Path("policy") / "runtime-assignment-normative-contract-v1.json"
RECEIPT_POLICY_RELATIVE_PATH = (
    Path("skills") / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
)
RELEASE_CANDIDATE_POLICY_SCHEMA = "release-candidate-policy/v1"
# The two ccodex report descriptors are pinned by digest only. Their runtime consumer
# (scripts/ccodex_sdlc.py) parses them on every invocation and must fail on malformed input
# there, so a second structural re-derivation in a pre-commit linter proved nothing the digest
# does not already prove — and the v2 pass measured that itself, running its structural lines and
# then comparing the same bytes against a pin that strictly dominated them.
CCODEX_SDLC_REPORT_POLICY_SHA256 = {
    "policy/ccodex-sdlc-read-report.v1.json": "eadce0fd12af79be3727c1fdb8505a291805741d951e67baa35162dc4d18b7dd",
    "policy/ccodex-sdlc-read-report.v2.json": "0667ab351d7ab755f94f4ca74be1d3a6510c0cf7ea30f35ff9a0821e732108d9",
}
RELEASE_CONTRACT_TOP_LEVEL_KEYS = (
    "schema_version",
    "checkout",
    "compatibility",
    "channels",
    "claim_lint",
)
RELEASE_CHECKOUT_KEYS = frozenset(
    {
        "certification_claim",
        "plane",
        "public_channel",
        "release_topology_adr_status",
        "version",
    }
)
RELEASE_COMPATIBILITY_KEYS = frozenset(
    {
        "core",
        "dated_references",
        "known_incompatible_host_versions",
        "optional_profile_floors",
        "support_rows",
        "support_tiers",
        "tuple_dimensions",
    }
)
RELEASE_CORE_KEYS = frozenset(
    {
        "certification_requires_current_capability_evidence",
        "host",
        "minimum_host_version",
        "minimum_is_eligibility_only",
        "required_capabilities",
        "surface",
    }
)
RELEASE_SUPPORT_TIERS = (
    "certified",
    "capability-qualified",
    "experimental",
    "unsupported",
)
RELEASE_TUPLE_DIMENSIONS = (
    "product_release",
    "surface",
    "host",
    "host_version",
    "operating_system",
    "architecture",
    "runtime_boundary",
    "installation_plane",
    "capability_evidence",
    "optional_profile_versions",
    "dependency_versions",
)
RELEASE_SUPPORT_ROW_KEYS = frozenset((*RELEASE_TUPLE_DIMENSIONS, "tier"))
RELEASE_CHANNELS_KEYS = frozenset({"preview", "public_channel_names", "stable"})
RELEASE_STABLE_CHANNEL_KEYS = frozenset(
    {
        "allows_experimental_profiles",
        "default_permission_bypass",
        "requires_complete_core_release_gate",
        "requires_current_certified_core",
        "requires_migration_and_recovery",
        "selection",
    }
)
RELEASE_PREVIEW_CHANNEL_KEYS = frozenset(
    {"inherits_stable_state", "install_mode", "may_overwrite_stable", "selection"}
)
RELEASE_CLAIM_LINT_KEYS = frozenset(
    {"allowed_extensions", "fixture_root", "forbidden_claims"}
)
RELEASE_CLAIM_CATEGORIES = frozenset(
    {
        "asd_conformance",
        "blanket_cross_platform_latest",
        "bundled_companion",
        "model_wide",
        "official_product",
        "provider_neutral_equal_parity",
        "provider_wide",
        "replacement",
        "security_completeness",
        "universal_gateway",
        "unsupported_renderer",
    }
)
RESEARCH_DIRECTOR_SEEDS_AUTHORITY = """Seeds authority:
- Research Director is Seeds-read-only.
- Use only the exact accepted Seeds inspection contract:
  `Seeds(<target>, <args...>)` = `MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec node@22.23.2 bun@1.4.0 npm:@os-eco/seeds-cli@0.5.15 -- sd <args>`.
- Inspect `Seeds(<target>, prime)`, `Seeds(<target>, ready --format json)`, and `Seeds(<target>, blocked --format json)` before substantive orchestration when Seeds is available.
- Do not create, claim, update, close, sync, or disposition Seeds.
- For work that outlives the session, emit exactly one typed `SeedProposal { title: str, summary: str, acceptance_criteria: list[str], priority: str, blocking: bool, scope: list[str], evidence: list[str], dependencies: list[str], recommended_owner: str }` for conductor triage.
"""
PROTECTED_REVIEWER_PATHS = frozenset(
    {
        "agents/claude/sdlc-reviewer.md",
        "agents/codex/sdlc-reviewer.toml",
        "agents/codex/research/adversarial_reviewer.toml",
        "agents/codex/research/replication_reviewer.toml",
        "agents/codex/research/safety_reviewer.toml",
    }
)
# The closed role roster. `install_skill_bundle.discover_entries` globs `agents/claude/*.md` and
# `agents/codex/*.toml` without reading a byte of their content, so anything dropped in either
# directory installs into the operator's home as a role — which is why the roster is a source
# constant here and not derived from the tree it is meant to bound.
GLOBAL_ROLE_STEMS = (
    "cartographer",
    "critic",
    "documentarian",
    "implementer",
    "integrator",
    "planner",
    "researcher",
    "reviewer",
)
SOURCE_PINNED_GLOBAL_PATHS = frozenset(
    {f"agents/claude/sdlc-{stem}.md" for stem in GLOBAL_ROLE_STEMS}
    | {f"agents/codex/sdlc-{stem}.toml" for stem in GLOBAL_ROLE_STEMS}
)
RESEARCH_ROLE_IDS = frozenset(
    {
        "ablationist",
        "adversarial_reviewer",
        "benchmark_engineer",
        "counterexample_hunter",
        "data_engineer",
        "experimentalist",
        "formalizer",
        "knowledge_librarian",
        "literature_scout",
        "novelty_auditor",
        "replication_reviewer",
        "repo_cartographer",
        "research_director",
        "safety_reviewer",
        "synthesis_writer",
        "systems_engineer",
        "theorist",
    }
)
SOURCE_PINNED_RESEARCH_PATHS = frozenset(
    f"agents/codex/research/{role}.toml" for role in RESEARCH_ROLE_IDS
)
REVIEWER_NO_OUTWARD_AUTHORITY = "You never decide release status, authorize a mutation, merge, push, or edit code."
REVIEWER_OUTWARD_AUTHORITY_PATTERN = re.compile(
    r"(?i)\b(?:may|can|is\s+authorized\s+to|are\s+authorized\s+to|is\s+permitted\s+to|are\s+permitted\s+to)\b"
    r".{0,100}\b(?:push|publish(?:ing|ation)?|outward(?:\s+effect)?|merge|deploy(?:ment)?)\b"
)
SEEDS_MUTATION_AUTHORITY_PATTERN = re.compile(
    r"(?i)\b(?:may|can|should|will|is\s+authorized\s+to|has\s+permission\s+to"
    r"|is\s+allowed\s+to|are\s+allowed\s+to|is\s+permitted\s+to|are\s+permitted\s+to)\s+"
    r"(?:create|claim|update|close|sync|disposition|label|delete|archive|mutate)\b.{0,80}\b(?:Seeds?|SeedProposal)\b"
)
# Authority-granting prose the 33 shipped role projections must never carry: spawn/admission
# authority claimed for a repository, role, receipt or local gate; `[1m]` used as proof of
# capacity; Seeds mutation; a local gate substituting for outward authorization. The five run
# against every role file, not only the digest-pinned reviewers, because the fourteen
# non-protected projections ship to the operator's home with no digest over them.
FORBIDDEN_PROJECTION_AUTHORITY_PATTERNS = (
    re.compile(
        r"(?i)\b(?:repository|role|agent|worker|receipt|local\s+validation|local\s+status|passing\s+(?:local\s+)?gate)\b"
        r".{0,80}\b(?:may|can|is\s+authorized\s+to|is\s+the\s+sole|authori[sz](?:e|es|ed)?|grant(?:s|ed)?)\b"
        r".{0,80}\b(?:external\s+)?(?:spawn|admission|readback)\b"
    ),
    re.compile(
        r"(?i)\b(?:external\s+)?(?:spawn|admission|readback)\b.{0,80}\b(?:authority|authorized|authori[sz](?:e|es|ed)?)\b"
    ),
    re.compile(
        r"(?i)\[1m\].{0,100}\bproves?\b.{0,100}\b(?:capacity|intelligence|compaction|effort)\b"
    ),
    re.compile(
        r"(?i)\b(?:may|can|should|will|is\s+authorized\s+to)\s+"
        r"(?:create|claim|update|close|sync|disposition|label|delete|archive|mutate)\b.{0,80}\b(?:Seeds?|SeedProposal)\b"
    ),
    re.compile(
        r"(?i)\b(?:local\s+validation|passing\s+(?:local\s+)?gate|local\s+status)\b.{0,80}\b"
        r"(?:sufficient|authori[sz](?:e|es|ed)?|grant(?:s|ed)?|permit(?:s|ted)?)\b.{0,80}\b"
        r"(?:push|publish(?:ing|ation)?|merge|deploy(?:ment)?|outward)\b"
    ),
)
RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256 = "22c165551389b844fc46b8fcae2e7cd750254181ad2096b6884b0ee8f25b801c"
SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256 = {
    "agents/claude/sdlc-reviewer.md": "fe2297470d4c0cc8fce37fbc8f2b4b24c117ba808cf5ddd199f5a2c7c699f860",
    "agents/codex/sdlc-reviewer.toml": "816f52d896821f4d5964e0d9fc8dd412b01e27800733613ace496eeec61dd003",
    "agents/codex/research/adversarial_reviewer.toml": "f452a51a61cd043181443722077af7e41bfef8b558630c76b5003e52db43c0df",
    "agents/codex/research/replication_reviewer.toml": "81d4038144782721c2df34d604df9af86d1a7e00628c9cb8f94c19610bf695c9",
    "agents/codex/research/safety_reviewer.toml": "afe1a80ec71ebb03d62b438d188e8ebbd0670c6460e824dd418048a11165c5a3",
}

VALIDATOR_WRAPPER = """#!/usr/bin/env bash
# Compatibility entrypoint; the authoritative task is `mise run validate`.
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec mise -C "$root" exec -- uv run --python 3.12.11 --script scripts/validate_bundle.py "$@"
"""
BUMP_PREFIX = """#!/bin/bash
# Bump every version-carrying manifest in one shot (targets declared in .version-bump.json).
#   bump-version.sh <new-version>   # write all targets + update .version-bump.json current
#   bump-version.sh --check         # exit 1 if any target disagrees with current
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$repo_root/.version-bump.json"

command -v mise >/dev/null 2>&1 || {
  echo "error: mise 2026.4.27+ is required to update version manifests" >&2
  exit 2
}

mise -C "$repo_root" exec -- uv run --python 3.12.11 python - "$manifest" "$repo_root" "${1:-}" <<'PY'
"""
# CI workflow pin — KEPT as an exact-content pin, expressed as a digest instead of a 34-line
# inline literal. The 2026-08-22 audit argued for shrinking it to "the file exists and contains
# `mise run check`" because the pin is defeated by the exact edit it targets: on a `pull_request`
# event GitHub runs the workflow from the PR's own merge ref, so a PR that deletes the check step
# also deletes the run that would have caught it. That is true and it is not the whole threat
# model. Three facts kept the pin:
#   1. The same validator runs LOCALLY as the lefthook pre-commit hook and as `mise run validate`,
#      which is where an honest CI edit is actually caught — before the push, not after it.
#   2. Substring matching is measurably weaker here. tests/test_gate_graph.py carries a mutation
#      that appends a bypass step spelled `run : curl ...`; YAML accepts the space, a `run:`-
#      anchored regex does not see it, and byte equality does. The two action pins are 40-hex
#      commit SHAs whose whole point is that a floating tag can be repointed upstream — an
#      "exists and mentions mise run check" assertion would let `@v4` back in silently.
#   3. Rank 3 of this demolition deferred a release workflow BECAUSE this pin makes a new CI
#      surface an explicit, reviewed validator edit. Loosening it here would quietly grant the
#      thing that rank deliberately did not take.
# The digest form is the same predicate on the same bytes (`read_text` normalizes CRLF, so a
# Windows checkout behaves as it did before), one line instead of thirty-four, and a legitimate
# CI edit re-pins it in one line exactly as it re-pinned the literal. What is honestly lost is
# readability: the expected workflow is no longer quotable from this file. Re-pin with
# `python3 -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('.github/workflows/validate.yml').read_text(encoding='utf-8').encode()).hexdigest())"`
# after reviewing the diff.
CI_WORKFLOW_RELATIVE_PATH = Path(".github") / "workflows" / "validate.yml"
CI_WORKFLOW_SHA256 = "9e8a1c3f9c142cc82ad42ee920d31151381b309488e6cf51bbca375ec9177dc5"


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return match.group(1) if match else ""


def metadata_value(metadata: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", metadata, re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    if value not in {"|", ">", "|-", ">-"} and not re.fullmatch(r"[|>](?:[+-]?[1-9]|[1-9][+-]?)", value):
        return value
    continuation: list[str] = []
    lines = metadata[match.end() :].splitlines()
    if lines and not lines[0]:
        lines = lines[1:]
    for line in lines:
        if not line.strip():
            continuation.append("")
            continue
        if not line.startswith((" ", "\t")):
            break
        continuation.append(line.strip())
    return " ".join(continuation).strip()


def validate_skills(root: Path, result: Validation) -> None:
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        directory = skill.parent.name
        text = skill.read_text(encoding="utf-8")
        metadata = frontmatter(text)
        if metadata_value(metadata, "name") != directory:
            result.error(f"{directory}: name does not match directory")
        # The description cap and the model-pin check both need the semantic parse. metadata_value
        # reads a plain (unquoted, non-block) multiline scalar's first line only, so measuring the
        # Codex 1024-char cap on it admits an over-cap description (agentic-sdlc-e78f); and a
        # substring test on `metadata` for the pin also hits `name: model-tier-rightsizing`, while
        # a line-anchored regex still misses the quoted and \u-escaped key forms that
        # validate_agents already rejects.
        try:
            skill_metadata = parse_frontmatter_metadata(text)
        except ValueError as exc:
            result.error(f"{directory}: invalid frontmatter: {exc}")
        else:
            description = skill_metadata.get("description")
            if not description:
                result.error(f"{directory}: missing description")
            elif not isinstance(description, str):
                result.error(f"{directory}: description must be a YAML string")
            elif len(description) > 1024:
                result.error(f"{directory}: description exceeds 1024 characters")
            for forbidden in ("model", "model_reasoning_effort"):
                if forbidden in skill_metadata:
                    result.error(f"{directory}: static {forbidden} is forbidden")
        for reference in sorted(set(re.findall(r"\breferences/[A-Za-z0-9._-]+\.md", text))):
            if not (skill.parent / reference).is_file():
                result.error(f"{directory}: missing {reference}")


def _skip_meta_whitespace(source: str, position: int) -> int:
    while position < len(source) and source[position] in " \t\r\n":
        position += 1
    return position


def workflow_meta_violation(text: str, stem: str) -> str | None:
    """Return the first host-meta-contract violation in a workflow document, or None.

    The live host refuses to LOAD a script whose first statement is not the pure-literal
    `export const meta = {...}` declaring name and description, so the gate holds the authored
    bytes to the same closed shape rather than discovering the refusal at activation time.
    """
    statement_start = None
    position = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith("//"):
            statement_start = position + len(line) - len(line.lstrip(" \t"))
            break
        position += len(line)
    if statement_start is None:
        return WORKFLOW_META_FIRST_STATEMENT_ERROR
    opened = WORKFLOW_META_OPEN_PATTERN.match(text, statement_start)
    if opened is None:
        return WORKFLOW_META_FIRST_STATEMENT_ERROR
    # Extract the object literal by matching its closing brace, string-aware so a brace inside a
    # quoted value cannot end the scan early. A backtick outside a string is a template literal,
    # which is the interpolation channel the pure-literal rule exists to refuse.
    depth = 0
    quote: str | None = None
    escaped = False
    close_index = None
    for index in range(opened.end() - 1, len(text)):
        character = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "'\"":
            quote = character
        elif character == "`":
            return WORKFLOW_META_PURE_LITERAL_ERROR
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                close_index = index
                break
    if close_index is None:
        return "the meta export is unterminated"
    body = text[opened.end() : close_index]
    fields: dict[str, object] = {}
    position = _skip_meta_whitespace(body, 0)
    while position < len(body):
        key_match = WORKFLOW_META_KEY_PATTERN.match(body, position)
        if key_match is None:
            return WORKFLOW_META_PURE_LITERAL_ERROR
        key = key_match.group(1)
        if key not in WORKFLOW_META_KEYS:
            return f"meta field '{key}' is not one of name, description, phases"
        if key in fields:
            return f"meta declares '{key}' more than once"
        position = _skip_meta_whitespace(body, key_match.end())
        if key == "phases":
            if position >= len(body) or body[position] != "[":
                return "meta.phases must be an array of string literals"
            position = _skip_meta_whitespace(body, position + 1)
            titles: list[str] = []
            while position < len(body) and body[position] != "]":
                title_match = WORKFLOW_META_STRING_PATTERN.match(body, position)
                if title_match is None:
                    return "meta.phases must be an array of string literals"
                titles.append(title_match.group(0)[1:-1])
                position = _skip_meta_whitespace(body, title_match.end())
                if position < len(body) and body[position] == ",":
                    position = _skip_meta_whitespace(body, position + 1)
            if position >= len(body):
                return "meta.phases must be an array of string literals"
            position += 1
            fields[key] = titles
        else:
            value_match = WORKFLOW_META_STRING_PATTERN.match(body, position)
            if value_match is None:
                return f"meta.{key} must be a string literal"
            fields[key] = value_match.group(0)[1:-1]
            position = value_match.end()
        position = _skip_meta_whitespace(body, position)
        if position < len(body):
            if body[position] != ",":
                return WORKFLOW_META_PURE_LITERAL_ERROR
            position = _skip_meta_whitespace(body, position + 1)
    if "name" not in fields or "description" not in fields:
        return "meta must declare both name and description"
    if fields["name"] != stem:
        return f"meta.name must be the string '{stem}'"
    description = fields["description"]
    if not isinstance(description, str) or not description.strip():
        return "meta.description must be a nonempty string literal"
    return None


def validate_workflows(root: Path, result: Validation) -> None:
    """Check the shape of every workflow overlay document the bundle ships.

    These are the shape rules that make sense for a document the lifecycle owns as BYTES: it must
    be discoverable by the installer, self-declare the name it will be installed under, open with
    the host-required pure-literal meta statement, parse in the runtime shape it will be handed
    to, load no modules, pin no model or effort, and name no user-specific path. Nothing here
    executes a workflow or asserts that a host will accept one; enabling the real overlay stays a
    separately authorized user-configuration effect.
    """
    directory = root / "workflows"
    if not directory.is_dir():
        return
    node = shutil.which("node")
    for path in sorted(directory.iterdir()):
        label = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            result.error(f"{label}: workflows/ holds regular workflow documents only")
            continue
        if path.suffix != ".js":
            # The installer discovers `workflows/*.js`. Anything else here would ship in the
            # payload and never be installed, which is dead weight that reads as a shipped entry.
            result.error(f"{label}: workflow documents must use the .js suffix")
            continue
        stem = path.stem
        if not WORKFLOW_STEM_PATTERN.fullmatch(stem):
            result.error(f"{label}: workflow name must be a lowercase slug")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            result.error(f"{label}: workflow document is unreadable: {exc}")
            continue
        first_line = text.split("\n", 1)[0].rstrip("\r")
        if not first_line.startswith(WORKFLOW_HEADER_PREFIX):
            result.error(f"{label}: missing a leading '{WORKFLOW_HEADER_PREFIX}<name>' header")
        elif first_line[len(WORKFLOW_HEADER_PREFIX) :].strip() != stem:
            result.error(f"{label}: declared workflow name does not match the file name")
        meta_violation = workflow_meta_violation(text, stem)
        if meta_violation:
            result.error(f"{label}: {meta_violation}")
        if WORKFLOW_MODULE_LOAD_PATTERN.search(text):
            result.error(f"{label}: a workflow document must not load modules")
        if WORKFLOW_ROUTE_PIN_PATTERN.search(text):
            result.error(f"{label}: static model or effort pins are forbidden")
        if WORKFLOW_USER_PATH_PATTERN.search(text):
            result.error(f"{label}: user-specific paths are forbidden")
        if node:
            completed = subprocess.run(
                [node, "-e", WORKFLOW_PARSE_PROBE, str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                # Control characters in a child's message would otherwise be replayed straight
                # into the rendered error line.
                detail = completed.stderr.strip().encode("unicode_escape").decode("ascii")
                result.error(f"{label} does not parse: {detail}")


def validate_hooks(root: Path, result: Validation) -> None:
    """Check the shape of every agent-hook script the bundle ships.

    These are the shape rules for a document the lifecycle owns as BYTES: it must be discoverable
    by the installer, self-declare the name it will be installed under, declare an event and
    matcher set the activator's closed vocabulary accepts, parse as POSIX sh, name no
    user-specific path, and fit the self-imposed context-injection budget. Nothing here executes
    a hook or asserts that a host will accept one; wiring one into settings stays a separately
    authorized user-configuration effect. No rule here claims to prove a shell script safe —
    what bounds this surface is that every shipped hook is reviewed bundle bytes and the operator
    explicitly enables each one.
    """
    directory = root / "hooks"
    if not directory.is_dir():
        return
    sh = shutil.which("sh")
    for path in sorted(directory.iterdir()):
        label = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            result.error(f"{label}: hooks/ holds regular hook scripts only")
            continue
        if path.suffix != ".sh":
            # The installer discovers `hooks/*.sh`. Anything else here would ship in the payload
            # and never be installed — dead weight that reads as a shipped entry. This is also
            # what structurally refuses a plugin-channel `hooks.json` in this tree.
            result.error(f"{label}: hook scripts must use the .sh suffix")
            continue
        stem = path.stem
        if not WORKFLOW_STEM_PATTERN.fullmatch(stem):
            result.error(f"{label}: hook name must be a lowercase slug")
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            result.error(f"{label}: hook script is unreadable: {exc}")
            continue
        if len(content) > HOOK_MAX_BYTES:
            result.error(f"{label}: hook script exceeds the {HOOK_MAX_BYTES}-byte context-injection budget")
        lines = [line.rstrip("\r") for line in text.split("\n")]
        if not lines or lines[0] != HOOK_SHEBANG:
            result.error(f"{label}: line 1 must be exactly '{HOOK_SHEBANG}'")
        if len(lines) < 2 or not lines[1].startswith(HOOK_HEADER_PREFIX):
            result.error(f"{label}: missing a '{HOOK_HEADER_PREFIX}<name>' header on line 2")
        elif lines[1][len(HOOK_HEADER_PREFIX) :].strip() != stem:
            result.error(f"{label}: declared hook name does not match the file name")
        if len(lines) < 3 or not lines[2].startswith(HOOK_EVENT_PREFIX):
            result.error(f"{label}: missing a '{HOOK_EVENT_PREFIX}<event>' header on line 3")
            event = None
        else:
            event = lines[2][len(HOOK_EVENT_PREFIX) :].strip()
            if event not in HOOK_EVENT_MATCHERS:
                result.error(f"{label}: unknown hook-event '{event}'")
                event = None
        if len(lines) < 4 or not lines[3].startswith(HOOK_MATCHER_PREFIX):
            result.error(f"{label}: missing a '{HOOK_MATCHER_PREFIX}<matchers>' header on line 4")
        elif event is not None:
            tokens = [token.strip() for token in lines[3][len(HOOK_MATCHER_PREFIX) :].split("|")]
            for token in tokens:
                if token not in HOOK_EVENT_MATCHERS[event]:
                    result.error(f"{label}: unknown hook-matcher token '{token}'")
        if WORKFLOW_USER_PATH_PATTERN.search(text):
            result.error(f"{label}: user-specific paths are forbidden")
        if sh:
            completed = subprocess.run(
                [sh, "-n", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                # Control characters in a child's message would otherwise be replayed straight
                # into the rendered error line.
                detail = completed.stderr.strip().encode("unicode_escape").decode("ascii")
                result.error(f"{label} does not parse: {detail}")


def validate_python(root: Path, result: Validation) -> None:
    installer = root / "scripts" / "install_skill_bundle.py"
    if not installer.is_file():
        result.error("scripts/install_skill_bundle.py is required")
    for source in root.rglob("*.py"):
        if ".git" in source.parts or "__pycache__" in source.parts:
            continue
        try:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            result.error(f"Python source failed to compile: {source.relative_to(root)}: {exc}")
    if shutil.which("git"):
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "*.pyc"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if tracked:
            result.error("Python bytecode must not be committed")


def parse_frontmatter_metadata(text: str) -> dict[str, object]:
    """Parse Claude frontmatter semantically with PyYAML's safe loader."""
    metadata = frontmatter(text)
    if not metadata:
        return {}
    try:
        for event in yaml.parse(metadata, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.events.AliasEvent):
                raise ValueError("YAML aliases are forbidden in frontmatter")
        value = yaml.safe_load(metadata)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML parser rejected frontmatter: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    if not all(isinstance(key, str) for key in value):
        raise ValueError("frontmatter keys must be strings")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, object]:
    """Lenient policy-JSON reader, used by the two managed-role passes and loaded from this
    module by tests/test_workflow_entry_kind.py."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _release_contract_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, member in pairs:
        if key in value:
            raise ValueError(f"duplicate member {key!r}")
        value[key] = member
    return value


def _reject_release_contract_nonfinite(token: str) -> object:
    raise ValueError(f"non-finite JSON value {token!r} is forbidden")


def load_release_contract_json(path: Path) -> dict[str, object]:
    """Load the new release contract with duplicate and non-finite values refused.

    This parser deliberately scopes those stricter JSON rules to the release contract.
    Legacy policy and manifest readers keep their existing compatibility behavior.
    """
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_release_contract_object,
            parse_constant=_reject_release_contract_nonfinite,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid release contract: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("release contract must be a JSON object")
    return value


def _canonical_release_contract_value(value: object, *, top_level: bool = False) -> object:
    if isinstance(value, dict):
        keys = RELEASE_CONTRACT_TOP_LEVEL_KEYS if top_level else tuple(sorted(value))
        ordered = {key: _canonical_release_contract_value(value[key]) for key in keys if key in value}
        if top_level:
            for key in sorted(set(value) - set(RELEASE_CONTRACT_TOP_LEVEL_KEYS)):
                ordered[key] = _canonical_release_contract_value(value[key])
        return ordered
    if isinstance(value, list):
        return [_canonical_release_contract_value(item) for item in value]
    return value


def canonical_release_contract_json(value: object) -> str:
    """Render the release contract in its deterministic v1 JSON representation."""
    return json.dumps(
        _canonical_release_contract_value(value, top_level=True),
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ) + "\n"


def _release_contract_mapping(
    value: object, label: str, result: Validation
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        result.error(f"policy/release-contract.v1.json: {label} must be an object")
        return None
    return value


def _release_contract_exact_keys(
    value: dict[str, object], expected: frozenset[str], label: str, result: Validation
) -> None:
    if set(value) != expected:
        result.error(
            f"policy/release-contract.v1.json: {label} keys must be exactly {sorted(expected)}"
        )


def _release_contract_version(
    value: object, label: str, result: Validation
) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", value):
        result.error(f"policy/release-contract.v1.json: {label} must be a three-part SemVer")
        return None
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def _release_contract_string(value: object, label: str, result: Validation) -> str | None:
    if not isinstance(value, str) or not value:
        result.error(f"policy/release-contract.v1.json: {label} must be a non-empty string")
        return None
    return value


def _validate_release_version_map(
    value: object, label: str, result: Validation
) -> dict[str, object] | None:
    versions = _release_contract_mapping(value, label, result)
    if versions is None:
        return None
    for name, version in versions.items():
        if not isinstance(name, str) or not name:
            result.error(f"policy/release-contract.v1.json: {label} has an invalid name")
        _release_contract_version(version, f"{label}.{name}", result)
    return versions


def _validate_release_checkout(
    root: Path, checkout: dict[str, object], rows: list[dict[str, object]], result: Validation
) -> None:
    _release_contract_exact_keys(checkout, RELEASE_CHECKOUT_KEYS, "checkout", result)
    version = _release_contract_version(checkout.get("version"), "checkout.version", result)
    plane = checkout.get("plane")
    public_channel = checkout.get("public_channel")
    certification_claim = checkout.get("certification_claim")
    adr_status = checkout.get("release_topology_adr_status")

    if plane not in {"checkout-development", "mise-release"}:
        result.error("policy/release-contract.v1.json: checkout.plane must be checkout-development or mise-release")
    if public_channel is not None and public_channel not in {"stable", "preview"}:
        result.error("policy/release-contract.v1.json: checkout.public_channel must be stable, preview, or null")
    if certification_claim not in {"none", "current-certified-core"}:
        result.error("policy/release-contract.v1.json: checkout.certification_claim is invalid")
    if adr_status not in {"proposed", "accepted"}:
        result.error("policy/release-contract.v1.json: checkout.release_topology_adr_status is invalid")

    if plane == "checkout-development":
        if public_channel is not None:
            result.error("policy/release-contract.v1.json: checkout-development has no public channel")
        if certification_claim != "none":
            result.error("policy/release-contract.v1.json: checkout-development has no certification claim")
    if plane == "mise-release":
        if public_channel not in {"stable", "preview"}:
            result.error("policy/release-contract.v1.json: mise-release must select a public channel")
        if adr_status != "accepted":
            result.error("policy/release-contract.v1.json: mise-release requires an accepted release topology ADR")
        if public_channel == "stable" and certification_claim != "current-certified-core":
            result.error("policy/release-contract.v1.json: stable requires the current-certified-core claim")
        if public_channel == "preview" and certification_claim != "none":
            result.error("policy/release-contract.v1.json: preview cannot inherit a stable certification claim")

    # This block is keyed to the CURRENT version from .version-bump.json, never a literal tuple:
    # a literal survives a version bump as dead code, which is exactly how it silently stopped
    # applying at the 0.7.3 -> 0.7.4 transition (caught in review). Unreadable current version
    # fails closed rather than skipping the claim checks.
    bump_current = None
    current_version = None
    bump_manifest = root / ".version-bump.json"
    if bump_manifest.is_file():
        try:
            bump_current = str(json.loads(bump_manifest.read_text(encoding="utf-8"))["current"])
            current_version = tuple(int(part) for part in bump_current.split("."))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            bump_current = None
            current_version = None
            result.error("policy/release-contract.v1.json: the current-version claim guard cannot read .version-bump.json")
    if current_version is not None and version == current_version:
        if plane != "checkout-development":
            result.error(f"policy/release-contract.v1.json: {bump_current} must remain checkout-development")
        if public_channel is not None:
            result.error(f"policy/release-contract.v1.json: {bump_current} must not have a public channel")
        if certification_claim != "none":
            result.error(f"policy/release-contract.v1.json: {bump_current} must not make a certification claim")
        if adr_status != "proposed":
            result.error(f"policy/release-contract.v1.json: {bump_current} keeps the release-topology ADR proposed")
        if rows:
            result.error(f"policy/release-contract.v1.json: {bump_current} checkout-development has no support rows")


def _validate_release_dated_references(
    references: object, result: Validation
) -> None:
    reference_map = _release_contract_mapping(references, "compatibility.dated_references", result)
    if reference_map is None:
        return
    expected = frozenset({"as_of", "stable", "latest"})
    _release_contract_exact_keys(reference_map, expected, "compatibility.dated_references", result)
    if reference_map.get("as_of") != "2026-08-15":
        result.error("policy/release-contract.v1.json: dated references must retain their 2026-08-15 snapshot")
    expected_versions = {"stable": "2.1.224", "latest": "2.1.233"}
    for channel, expected_version in expected_versions.items():
        reference = _release_contract_mapping(
            reference_map.get(channel), f"compatibility.dated_references.{channel}", result
        )
        if reference is None:
            continue
        _release_contract_exact_keys(
            reference,
            frozenset({"ceiling", "certification", "role", "version"}),
            f"compatibility.dated_references.{channel}",
            result,
        )
        if reference.get("version") != expected_version:
            result.error(
                f"policy/release-contract.v1.json: dated reference {channel} version must be {expected_version}"
            )
        if reference.get("role") != "nomination-regression-reference":
            result.error(
                f"policy/release-contract.v1.json: dated reference {channel} must remain a nomination/regression reference"
            )
        if reference.get("certification") is not False or reference.get("ceiling") is not False:
            result.error(
                f"policy/release-contract.v1.json: dated reference {channel} cannot be a certification or ceiling"
            )


def _validate_release_capability_evidence(
    evidence: object, index: int, result: Validation
) -> dict[str, object] | None:
    label = f"compatibility.support_rows[{index}].capability_evidence"
    evidence_map = _release_contract_mapping(evidence, label, result)
    if evidence_map is None:
        return None
    _release_contract_exact_keys(
        evidence_map,
        frozenset({"current", "evidence_id", "passed_capabilities", "published_journey"}),
        label,
        result,
    )
    _release_contract_string(evidence_map.get("evidence_id"), f"{label}.evidence_id", result)
    if not isinstance(evidence_map.get("current"), bool):
        result.error(f"policy/release-contract.v1.json: {label}.current must be boolean")
    if not isinstance(evidence_map.get("published_journey"), bool):
        result.error(f"policy/release-contract.v1.json: {label}.published_journey must be boolean")
    passed = evidence_map.get("passed_capabilities")
    if not isinstance(passed, list) or not all(isinstance(item, str) and item for item in passed):
        result.error(f"policy/release-contract.v1.json: {label}.passed_capabilities must be a string list")
    elif len(set(passed)) != len(passed):
        result.error(f"policy/release-contract.v1.json: {label}.passed_capabilities must be unique")
    return evidence_map


def _validate_release_known_incompatible_versions(
    records: object, result: Validation
) -> set[str]:
    if not isinstance(records, list):
        result.error("policy/release-contract.v1.json: compatibility.known_incompatible_host_versions must be a list")
        return set()
    versions: set[str] = set()
    for index, record in enumerate(records):
        label = f"compatibility.known_incompatible_host_versions[{index}]"
        record_map = _release_contract_mapping(record, label, result)
        if record_map is None:
            continue
        _release_contract_exact_keys(record_map, frozenset({"reason", "version"}), label, result)
        _release_contract_string(record_map.get("reason"), f"{label}.reason", result)
        version = record_map.get("version")
        if _release_contract_version(version, f"{label}.version", result) is None:
            continue
        assert isinstance(version, str)
        if version in versions:
            result.error("policy/release-contract.v1.json: known-incompatible host versions must be unique")
        versions.add(version)
    return versions


def _validate_release_optional_profile_floors(
    floors: object, core: dict[str, object], result: Validation
) -> dict[str, dict[str, object]]:
    floor_map = _release_contract_mapping(floors, "compatibility.optional_profile_floors", result)
    if floor_map is None:
        return {}
    core_minimum = _release_contract_version(
        core.get("minimum_host_version"), "compatibility.core.minimum_host_version", result
    )
    validated: dict[str, dict[str, object]] = {}
    for profile, floor in floor_map.items():
        if not isinstance(profile, str) or not profile:
            result.error("policy/release-contract.v1.json: optional profile floors need non-empty names")
            continue
        label = f"compatibility.optional_profile_floors.{profile}"
        floor_spec = _release_contract_mapping(floor, label, result)
        if floor_spec is None:
            continue
        _release_contract_exact_keys(
            floor_spec, frozenset({"minimum_host_version", "required_capabilities"}), label, result
        )
        minimum = _release_contract_version(
            floor_spec.get("minimum_host_version"), f"{label}.minimum_host_version", result
        )
        if minimum is not None and core_minimum is not None and minimum <= core_minimum:
            result.error(f"policy/release-contract.v1.json: {profile} profile minimum must exceed the Core minimum")
        capabilities = floor_spec.get("required_capabilities")
        if (
            not isinstance(capabilities, list)
            or not capabilities
            or not all(isinstance(capability, str) and capability for capability in capabilities)
            or len(set(capabilities)) != len(capabilities)
        ):
            result.error(f"policy/release-contract.v1.json: {profile} profile needs unique required capabilities")
        validated[profile] = floor_spec
    return validated


def _validate_release_support_rows(
    rows: object,
    checkout: dict[str, object],
    core: dict[str, object],
    known_incompatible_versions: set[str],
    optional_profile_floors: dict[str, dict[str, object]],
    result: Validation,
) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        result.error("policy/release-contract.v1.json: compatibility.support_rows must be a list")
        return []

    checkout_version = checkout.get("version")
    core_minimum = _release_contract_version(
        core.get("minimum_host_version"), "compatibility.core.minimum_host_version", result
    )
    core_capabilities = core.get("required_capabilities")
    required_capabilities = set(core_capabilities) if isinstance(core_capabilities, list) else set()
    seen_tuples: set[str] = set()
    row_maps: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        row_map = _release_contract_mapping(row, f"compatibility.support_rows[{index}]", result)
        if row_map is None:
            continue
        row_maps.append(row_map)
        _release_contract_exact_keys(
            row_map, RELEASE_SUPPORT_ROW_KEYS, f"compatibility.support_rows[{index}]", result
        )
        for field in (
            "surface",
            "host",
            "operating_system",
            "architecture",
            "runtime_boundary",
            "installation_plane",
        ):
            _release_contract_string(row_map.get(field), f"compatibility.support_rows[{index}].{field}", result)
        product_version = _release_contract_version(
            row_map.get("product_release"), f"compatibility.support_rows[{index}].product_release", result
        )
        host_version = _release_contract_version(
            row_map.get("host_version"), f"compatibility.support_rows[{index}].host_version", result
        )
        if row_map.get("product_release") != checkout_version:
            result.error(
                f"policy/release-contract.v1.json: compatibility.support_rows[{index}] product_release must equal checkout.version"
            )
        optional_profiles = _validate_release_version_map(
            row_map.get("optional_profile_versions"),
            f"compatibility.support_rows[{index}].optional_profile_versions",
            result,
        )
        _validate_release_version_map(
            row_map.get("dependency_versions"),
            f"compatibility.support_rows[{index}].dependency_versions",
            result,
        )
        evidence = _validate_release_capability_evidence(
            row_map.get("capability_evidence"), index, result
        )
        tier = row_map.get("tier")
        if tier not in RELEASE_SUPPORT_TIERS:
            result.error(f"policy/release-contract.v1.json: compatibility.support_rows[{index}].tier is invalid")

        tuple_identity = canonical_release_contract_json(
            {field: row_map.get(field) for field in RELEASE_TUPLE_DIMENSIONS}
        )
        if tuple_identity in seen_tuples:
            result.error("policy/release-contract.v1.json: support tuples must be unique")
        seen_tuples.add(tuple_identity)

        if row_map.get("host_version") in known_incompatible_versions:
            if tier != "unsupported":
                result.error(
                    f"policy/release-contract.v1.json: known-incompatible host version {row_map.get('host_version')} must be unsupported"
                )
            continue
        surface = row_map.get("surface")
        if surface == core.get("surface"):
            if row_map.get("host") != core.get("host"):
                result.error(
                    f"policy/release-contract.v1.json: Core support row {index} must use the declared Claude Code host"
                )
            if optional_profiles != {}:
                result.error(
                    f"policy/release-contract.v1.json: Core support row {index} cannot inherit an optional profile"
                )
            if host_version is not None and core_minimum is not None and host_version < core_minimum:
                if tier != "unsupported":
                    result.error(
                        f"policy/release-contract.v1.json: Core support row {index} below the Core minimum must be unsupported"
                    )
                continue
            required_capabilities_for_surface = required_capabilities
            surface_label = "Core"
        elif isinstance(surface, str) and surface in optional_profile_floors:
            floor = optional_profile_floors[surface]
            profile_minimum = _release_contract_version(
                floor.get("minimum_host_version"),
                f"compatibility.optional_profile_floors.{surface}.minimum_host_version",
                result,
            )
            if not isinstance(optional_profiles, dict) or surface not in optional_profiles:
                result.error(
                    f"policy/release-contract.v1.json: {surface} support row {index} must carry its optional profile version"
                )
            if host_version is not None and profile_minimum is not None and host_version < profile_minimum:
                if tier != "unsupported":
                    result.error(
                        f"policy/release-contract.v1.json: support row {index} below the {surface} profile minimum must be unsupported"
                    )
                continue
            floor_capabilities = floor.get("required_capabilities")
            required_capabilities_for_surface = (
                set(floor_capabilities) if isinstance(floor_capabilities, list) else set()
            )
            surface_label = f"{surface} profile"
        else:
            result.error(
                f"policy/release-contract.v1.json: non-Core support row {index} must declare an optional profile floor"
            )
            continue
        if tier in {"certified", "capability-qualified"}:
            passed = evidence.get("passed_capabilities") if evidence is not None else None
            passed_capabilities = set(passed) if isinstance(passed, list) else set()
            if evidence is None or evidence.get("current") is not True:
                result.error(
                    f"policy/release-contract.v1.json: qualified {surface_label} support row {index} requires current capability evidence"
                )
            if not required_capabilities_for_surface.issubset(passed_capabilities):
                result.error(
                    f"policy/release-contract.v1.json: qualified {surface_label} support row {index} is missing a required capability canary"
                )
        if tier == "certified" and (evidence is None or evidence.get("published_journey") is not True):
            result.error(
                f"policy/release-contract.v1.json: certified {surface_label} support row {index} requires a current published journey"
            )
    return row_maps


def _validate_release_compatibility(
    compatibility: dict[str, object], checkout: dict[str, object], result: Validation
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    _release_contract_exact_keys(compatibility, RELEASE_COMPATIBILITY_KEYS, "compatibility", result)
    if compatibility.get("support_tiers") != list(RELEASE_SUPPORT_TIERS):
        result.error("policy/release-contract.v1.json: compatibility.support_tiers must be the closed support-tier vocabulary")
    if compatibility.get("tuple_dimensions") != list(RELEASE_TUPLE_DIMENSIONS):
        result.error("policy/release-contract.v1.json: compatibility.tuple_dimensions must preserve the exact tuple dimensions")
    core = _release_contract_mapping(compatibility.get("core"), "compatibility.core", result)
    if core is None:
        return None, []
    _release_contract_exact_keys(core, RELEASE_CORE_KEYS, "compatibility.core", result)
    if core.get("surface") != "core" or core.get("host") != "claude-code":
        result.error("policy/release-contract.v1.json: compatibility.core must identify the Claude Code Core surface")
    if _release_contract_version(core.get("minimum_host_version"), "compatibility.core.minimum_host_version", result) != (2, 1, 154):
        result.error("policy/release-contract.v1.json: Core minimum host version must be 2.1.154")
    if core.get("required_capabilities") != ["dynamic-workflows-effectively-enabled"]:
        result.error("policy/release-contract.v1.json: Core requires Dynamic Workflows effectively enabled")
    if core.get("minimum_is_eligibility_only") is not True:
        result.error("policy/release-contract.v1.json: Core minimum must be eligibility-only")
    if core.get("certification_requires_current_capability_evidence") is not True:
        result.error("policy/release-contract.v1.json: Core certification requires current capability evidence")
    _validate_release_dated_references(compatibility.get("dated_references"), result)
    known_incompatible_versions = _validate_release_known_incompatible_versions(
        compatibility.get("known_incompatible_host_versions"), result
    )
    optional_profile_floors = _validate_release_optional_profile_floors(
        compatibility.get("optional_profile_floors"), core, result
    )
    return core, _validate_release_support_rows(
        compatibility.get("support_rows"),
        checkout,
        core,
        known_incompatible_versions,
        optional_profile_floors,
        result,
    )


def _validate_release_stable_admission(
    checkout: dict[str, object], rows: list[dict[str, object]], core: dict[str, object], result: Validation
) -> None:
    if checkout.get("public_channel") != "stable":
        return
    for row in rows:
        evidence = row.get("capability_evidence")
        if (
            row.get("surface") == core.get("surface")
            and row.get("tier") == "certified"
            and isinstance(evidence, dict)
            and evidence.get("current") is True
        ):
            return
    result.error("policy/release-contract.v1.json: stable requires a current certified Core tuple")


def _validate_release_channels(channels: dict[str, object], result: Validation) -> None:
    _release_contract_exact_keys(channels, RELEASE_CHANNELS_KEYS, "channels", result)
    if channels.get("public_channel_names") != ["stable", "preview"]:
        result.error("policy/release-contract.v1.json: channels must name stable and preview exactly")

    stable = _release_contract_mapping(channels.get("stable"), "channels.stable", result)
    if stable is not None:
        _release_contract_exact_keys(stable, RELEASE_STABLE_CHANNEL_KEYS, "channels.stable", result)
        expected_stable = {
            "allows_experimental_profiles": False,
            "default_permission_bypass": False,
            "requires_complete_core_release_gate": True,
            "requires_current_certified_core": True,
            "requires_migration_and_recovery": True,
            "selection": "exact",
        }
        for field, expected in expected_stable.items():
            if stable.get(field) != expected:
                result.error(f"policy/release-contract.v1.json: channels.stable.{field} must be {expected!r}")

    preview = _release_contract_mapping(channels.get("preview"), "channels.preview", result)
    if preview is None:
        return
    _release_contract_exact_keys(preview, RELEASE_PREVIEW_CHANNEL_KEYS, "channels.preview", result)
    if preview.get("selection") != "exact":
        result.error("policy/release-contract.v1.json: channels.preview.selection must be 'exact'")
    if preview.get("install_mode") != "side-by-side":
        result.error("policy/release-contract.v1.json: preview must install side-by-side")
    if preview.get("may_overwrite_stable") is not False:
        result.error("policy/release-contract.v1.json: preview cannot overwrite stable state")
    if preview.get("inherits_stable_state") is not False:
        result.error("policy/release-contract.v1.json: preview cannot inherit stable state")


def _validate_release_claim_lint(
    root: Path, claim_lint: dict[str, object], result: Validation
) -> None:
    _release_contract_exact_keys(claim_lint, RELEASE_CLAIM_LINT_KEYS, "claim_lint", result)
    fixture_root = claim_lint.get("fixture_root")
    if fixture_root != "tests/fixtures/release-claims":
        result.error("policy/release-contract.v1.json: claim lint must stay fixture-root-only")
        return
    extensions = claim_lint.get("allowed_extensions")
    if extensions != [".md", ".txt"]:
        result.error("policy/release-contract.v1.json: claim lint extensions must be .md and .txt")
        return
    forbidden = _release_contract_mapping(claim_lint.get("forbidden_claims"), "claim_lint.forbidden_claims", result)
    if forbidden is None:
        return
    if set(forbidden) != RELEASE_CLAIM_CATEGORIES:
        result.error("policy/release-contract.v1.json: claim lint categories must be the closed release-claim vocabulary")
        return
    patterns: dict[str, list[str]] = {}
    for category in sorted(RELEASE_CLAIM_CATEGORIES):
        phrases = forbidden.get(category)
        if (
            not isinstance(phrases, list)
            or not phrases
            or not all(isinstance(phrase, str) and phrase for phrase in phrases)
            or len(set(phrases)) != len(phrases)
        ):
            result.error(f"policy/release-contract.v1.json: claim lint [{category}] needs unique non-empty phrases")
            continue
        patterns[category] = [phrase.casefold() for phrase in phrases]

    candidate_root = root / fixture_root
    if candidate_root.is_symlink():
        result.error("policy/release-contract.v1.json: claim lint fixture root must not be a symlink")
        return
    try:
        repository_root = root.resolve(strict=True)
        physical_candidate_root = candidate_root.resolve(strict=True)
    except OSError as exc:
        result.error(f"policy/release-contract.v1.json: cannot resolve claim lint fixture root: {exc}")
        return
    if not physical_candidate_root.is_relative_to(repository_root):
        result.error("policy/release-contract.v1.json: claim lint fixture root escapes the physical repository boundary")
        return
    if not candidate_root.is_dir():
        result.error("policy/release-contract.v1.json: claim lint fixture root is required")
        return
    for path in sorted(candidate_root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result.error(f"policy/release-contract.v1.json: claim lint fixture must not be a symlink: {relative}")
            continue
        if path.is_dir():
            continue
        if path.suffix not in extensions:
            result.error(f"policy/release-contract.v1.json: claim lint fixture has unsupported extension: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8").casefold()
        except (OSError, UnicodeError) as exc:
            result.error(f"policy/release-contract.v1.json: cannot read claim lint fixture {relative}: {exc}")
            continue
        for category, phrases in patterns.items():
            if any(phrase in text for phrase in phrases):
                result.error(f"policy/release-contract.v1.json: claim lint [{category}] rejected {relative}")


def validate_release_contract(root: Path, result: Validation) -> None:
    path = root / RELEASE_CONTRACT_RELATIVE_PATH
    try:
        contract = load_release_contract_json(path)
    except ValueError as exc:
        result.error(str(exc))
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result.error(f"cannot read release contract: {exc}")
        return
    if raw != canonical_release_contract_json(contract):
        result.error("policy/release-contract.v1.json must use canonical JSON")
    if set(contract) != set(RELEASE_CONTRACT_TOP_LEVEL_KEYS):
        result.error("policy/release-contract.v1.json: top-level keys must be exactly "
                     f"{list(RELEASE_CONTRACT_TOP_LEVEL_KEYS)}")
    if contract.get("schema_version") != "release-contract/v1":
        result.error("policy/release-contract.v1.json: schema_version must be 'release-contract/v1'")
        return
    checkout = _release_contract_mapping(contract.get("checkout"), "checkout", result)
    compatibility = _release_contract_mapping(contract.get("compatibility"), "compatibility", result)
    channels = _release_contract_mapping(contract.get("channels"), "channels", result)
    claim_lint = _release_contract_mapping(contract.get("claim_lint"), "claim_lint", result)
    if channels is not None:
        _validate_release_channels(channels, result)
    if claim_lint is not None:
        _validate_release_claim_lint(root, claim_lint, result)
    if checkout is not None and compatibility is not None:
        core, rows = _validate_release_compatibility(compatibility, checkout, result)
        _validate_release_checkout(root, checkout, rows, result)
        if core is not None:
            _validate_release_stable_admission(checkout, rows, core, result)


def _strict_json_object(raw: bytes, label: str) -> dict[str, object]:
    """Parse policy JSON without accepting duplicate keys or non-finite constants."""
    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant {value!r}")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid strict JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}: JSON object required")
    return value


def _release_candidate_policy_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts) and not any(character in value for character in "*?[]")


def validate_release_candidate_policy(root: Path, result: Validation) -> None:
    """Keep the unpublished-candidate allowlist explicit, finite, and canonical."""
    relative = RELEASE_CANDIDATE_POLICY_RELATIVE_PATH
    path = root / relative
    if path.is_symlink() or not path.is_file():
        result.error(f"{relative}: required release-candidate policy is missing or linked")
        return
    try:
        raw = path.read_bytes()
        policy = _strict_json_object(raw, str(relative))
    except (OSError, ValueError) as exc:
        result.error(str(exc))
        return
    canonical = json.dumps(policy, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    if raw != canonical.encode("ascii"):
        result.error(f"{relative}: policy must use canonical ASCII compact JSON")
    # `archive` and `runtime` stanzas are deliberately absent from this closed set: the deleted
    # acquisition engine was their only producer, and pinning them here defended contracts
    # (a candidate-digest archive name, a bundled Python runtime) that `scripts/build_release.py`
    # can never satisfy. The builder's real naming is derived from `manifest.product_version`.
    expected_top = {"canonical_json", "disclosures", "limits", "manifest", "payload", "schema_version"}
    if set(policy) != expected_top or policy.get("schema_version") != RELEASE_CANDIDATE_POLICY_SCHEMA:
        result.error(f"{relative}: closed policy schema mismatch")
        return
    if policy.get("canonical_json") != {
        "allow_nonfinite": False,
        "ensure_ascii": True,
        "separators": [",", ":"],
        "sort_keys": True,
        "trailing_newline": True,
    }:
        result.error(f"{relative}: canonical JSON contract mismatch")
    if policy.get("disclosures") != {"licensing": "incomplete", "provenance": "unverified", "sbom": "absent"}:
        result.error(f"{relative}: disclosure contract must remain incomplete and unverified")

    limits = policy.get("limits")
    expected_limits = {"max_archive_bytes", "max_entries", "max_file_bytes", "max_path_bytes", "max_total_bytes", "max_uncompressed_bytes"}
    if not isinstance(limits, dict) or set(limits) != expected_limits or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in limits.values()):
        result.error(f"{relative}: bounded verifier limits are invalid")
    elif not (
        limits["max_file_bytes"] <= limits["max_total_bytes"] < limits["max_uncompressed_bytes"] <= 536_870_912
        and limits["max_archive_bytes"] <= 536_870_912
        and limits["max_entries"] <= 100_000
        and limits["max_path_bytes"] <= 4096
    ):
        result.error(f"{relative}: bounded verifier limits exceed the v1 ceiling")

    manifest = policy.get("manifest")
    expected_manifest = {"artifact_kind", "platform", "product_version", "public_channel", "release_claim", "schema_version", "support_tier"}
    if not isinstance(manifest, dict) or set(manifest) != expected_manifest:
        result.error(f"{relative}: candidate manifest descriptor is invalid")
    else:
        if {key: manifest.get(key) for key in expected_manifest - {"product_version"}} != {
            "artifact_kind": "unpublished-candidate",
            "platform": "linux-x64",
            "public_channel": None,
            "release_claim": "none",
            "schema_version": "release-candidate/v1",
            "support_tier": "unsupported",
        }:
            result.error(f"{relative}: candidate manifest must not make a release or support claim")
        try:
            contract = load_release_contract_json(root / RELEASE_CONTRACT_RELATIVE_PATH)
            checkout = contract.get("checkout")
            expected_version = checkout.get("version") if isinstance(checkout, dict) else None
        except ValueError:
            expected_version = None
        if not isinstance(manifest.get("product_version"), str) or manifest.get("product_version") != expected_version:
            result.error(f"{relative}: product version must equal the canonical release contract version")

    payload = policy.get("payload")
    if not isinstance(payload, dict) or set(payload) != {"files", "trees"}:
        result.error(f"{relative}: payload allowlist is invalid")
    else:
        files, trees = payload.get("files"), payload.get("trees")
        if not all(isinstance(value, list) for value in (files, trees)):
            result.error(f"{relative}: payload allowlist members must be lists")
        else:
            assert isinstance(files, list) and isinstance(trees, list)
            if (
                not files
                or not trees
                or files != sorted(files)
                or trees != sorted(trees)
                or len(files) != len(set(files))
                or len(trees) != len(set(trees))
                or not all(_release_candidate_policy_path(value) for value in [*files, *trees])
                or any(file == tree or file.startswith(tree + "/") for file in files for tree in trees)
                or any(left.startswith(right + "/") for left in trees for right in trees if left != right)
            ):
                result.error(f"{relative}: payload allowlist must be sorted, closed, and non-overlapping")
            required_files = {"LICENSE", "NOTICE"}
            # `bin` is required because `bin/ccodex` is the mise github-backend tool's one exposed
            # command: without it the backend's bin lookup falls through to the 8 executable
            # scripts/*.sh, presenting a maintenance surface as the tool's PATH surface.
            required_trees = {"agents", "assets", "bin", "commands", "hooks", "policy", "scripts", "skills", "workflows"}
            if not required_files.issubset(files) or not required_trees.issubset(trees):
                result.error(f"{relative}: minimal authored payload roots are missing")


def validate_packaged_policy_copies(root: Path, result: Validation) -> None:
    """The Research OS ships copies of two canonical policies; they must be the same bytes.

    `skills/codex-research-os/scripts/install_research_os.py` scaffolds a target repository from
    the packaged copies, so a drift here hands a scaffolded repo a different runtime contract than
    this bundle validates against — including a weaker runtime-authority block. This is byte
    equality between two shipped payload files, not a structural re-derivation of either: the
    75-line structural pass that used to assert it went with the rest of the transcription.
    """
    for relative in (NORMATIVE_CONTRACT_RELATIVE_PATH, RECEIPT_POLICY_RELATIVE_PATH):
        canonical = root / relative
        packaged = root / "skills" / "codex-research-os" / "policy" / relative.name
        if not canonical.is_file():
            result.error(f"{relative.as_posix()}: canonical runtime policy is required")
            continue
        if not packaged.is_file() or packaged.read_bytes() != canonical.read_bytes():
            result.error(
                f"skills/codex-research-os/policy/{relative.name} must be byte-identical to "
                f"{relative.as_posix()}"
            )


def validate_ccodex_sdlc_report_policies(root: Path, result: Validation) -> None:
    """Pin the two ccodex report descriptors by digest, and nothing else.

    `scripts/ccodex_sdlc.py` parses both documents on every invocation and refuses a malformed
    one there, which is where a runtime consumer must fail. This pass exists only so a reviewed
    descriptor cannot drift silently in the checkout; the digest is a strictly stronger predicate
    than the structural re-derivation it replaced.
    """
    for relative, digest in sorted(CCODEX_SDLC_REPORT_POLICY_SHA256.items()):
        path = root / relative
        if path.is_symlink() or not path.is_file():
            result.error(f"{relative}: required ccodex report policy is missing or linked")
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            result.error(f"{relative}: unreadable ccodex report policy: {exc}")
            continue
        if sha256_bytes(raw) != digest:
            result.error(f"{relative}: bytes differ from the reviewed ccodex report contract")


def managed_role_instructions(path: Path) -> str:
    if path.suffix == ".toml":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        instructions = data.get("developer_instructions")
        return instructions if isinstance(instructions, str) else ""
    return path.read_text(encoding="utf-8")


def validate_source_pinned_protected_role_authority(root: Path, result: Validation) -> None:
    director_path = root / "agents" / "codex" / "research" / "research_director.toml"
    if director_path.is_file():
        try:
            director_instructions = managed_role_instructions(director_path)
        except (OSError, tomllib.TOMLDecodeError):
            director_instructions = ""
        if sha256_bytes(director_instructions.encode("utf-8")) != RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256:
            result.error(
                "agents/codex/research/research_director.toml: source-pinned protected role authority content differs"
            )
        if director_instructions.count(RESEARCH_DIRECTOR_SEEDS_AUTHORITY) != 1:
            result.error(
                "agents/codex/research/research_director.toml: source-pinned protected role authority "
                "requires the exact Seeds-read-only block once"
            )
        else:
            director_outside = director_instructions.replace(RESEARCH_DIRECTOR_SEEDS_AUTHORITY, "", 1)
            if SEEDS_MUTATION_AUTHORITY_PATTERN.search(director_outside):
                result.error(
                    "agents/codex/research/research_director.toml: source-pinned protected role authority "
                    "forbids Seeds mutation authority"
                )

    for relative in sorted(PROTECTED_REVIEWER_PATHS):
        path = root / relative
        if not path.is_file():
            continue
        if sha256_bytes(path.read_bytes()) != SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256[relative]:
            result.error(f"{relative}: source-pinned protected role authority content differs")
        try:
            instructions = managed_role_instructions(path)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if relative in {
            "agents/claude/sdlc-reviewer.md",
            "agents/codex/sdlc-reviewer.toml",
        } and REVIEWER_NO_OUTWARD_AUTHORITY not in instructions:
            result.error(f"{relative}: source-pinned protected role authority requires the reviewer boundary")
        if REVIEWER_OUTWARD_AUTHORITY_PATTERN.search(instructions):
            result.error(f"{relative}: source-pinned protected role authority forbids outward reviewer authority")


def managed_role_paths(root: Path) -> tuple[set[str], set[str]]:
    return (
        {
            path.relative_to(root).as_posix()
            for path in (
                *(root / "agents" / "claude").glob("*.md"),
                *(root / "agents" / "codex").glob("*.toml"),
            )
        },
        {
            path.relative_to(root).as_posix()
            for path in (root / "agents" / "codex" / "research").glob("*.toml")
        },
    )


def validate_managed_role_authority_projection(root: Path, result: Validation) -> None:
    """Refuse authority-granting prose in any shipped role projection, digest-pinned or not.

    Only five of the 33 files carry a content digest. The other 28 install into the operator's
    `~/.claude/agents/` exactly the same way, so a commit that appends "A passing local gate is
    sufficient to authorize push to the shared remote." to `agents/claude/sdlc-integrator.md` —
    the one role that does hold fan-in execution authority — would otherwise ship with a green
    gate, contradicting the doctrine that no local gate grants outward authority.

    The canonical runtime block is excised before the scan and that is load-bearing, not
    incidental: the block itself says the external harness "is the sole spawn and admission
    authority" and that `[1m]` "proves neither intelligence" etc. Scanning whole-file text scores
    62 hits on the clean tree; scanning outside the block scores 0.
    """
    try:
        contract = load_json_object(
            root / RECEIPT_POLICY_RELATIVE_PATH, "runtime receipt policy"
        )["canonical_runtime_contract"]
    except (ValueError, KeyError):
        contract = None
    if not isinstance(contract, str) or not contract:
        result.error(
            f"{RECEIPT_POLICY_RELATIVE_PATH.as_posix()}: canonical runtime contract is required "
            "to scan managed role authority"
        )
        return
    for path in sorted(
        (
            *(root / "agents" / "claude").glob("*.md"),
            *(root / "agents" / "codex").glob("*.toml"),
            *(root / "agents" / "codex" / "research").glob("*.toml"),
        )
    ):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.error(f"{relative}: unreadable managed role projection: {exc}")
            continue
        outside_contract = text.replace(contract, "")
        for pattern in FORBIDDEN_PROJECTION_AUTHORITY_PATTERNS:
            if pattern.search(outside_contract):
                result.error(f"{relative}: contradictory runtime authority projection is forbidden")
                break


def validate_managed_role_contract(root: Path, result: Validation) -> None:
    """Close the roster at 16 + 17, and make the contract's 33 recorded digests verify bytes.

    Roster closure is what stops an unguarded addition: a role file whose stem is not `sdlc-*`
    passes every other check in this file while the installer still ships it. The
    `manifest_sha256` maps in the normative contract are the pins over those bytes, and a
    recorded digest nothing compares is a pin in name only — so they are compared here, against
    the on-disk role files, rather than left as data.
    """
    actual_global, actual_research = managed_role_paths(root)
    if actual_global != SOURCE_PINNED_GLOBAL_PATHS:
        result.error("managed role roster must contain exactly the 16 global SDLC roles")
    if actual_research != SOURCE_PINNED_RESEARCH_PATHS:
        result.error("managed role roster must contain exactly the 17 Research OS roles")
    try:
        managed = load_json_object(
            root / NORMATIVE_CONTRACT_RELATIVE_PATH, "normative runtime contract"
        )["managed_roles"]
        pinned = dict(managed["global"]["manifest_sha256"])
        for spec in managed["research"]["roles"].values():
            pinned[spec["path"]] = spec["manifest_sha256"]
        if not all(isinstance(item, str) for pair in pinned.items() for item in pair):
            raise TypeError("every pinned path and digest must be a string")
    except (ValueError, AttributeError, KeyError, TypeError) as exc:
        result.error(f"invalid normative managed role contract: {exc}")
        return
    if set(pinned) != SOURCE_PINNED_GLOBAL_PATHS | SOURCE_PINNED_RESEARCH_PATHS:
        result.error(
            "normative managed role contract must pin exactly the 33 managed role projections"
        )
    for relative, digest in sorted(pinned.items()):
        path = root / relative
        if not path.is_file() or sha256_bytes(path.read_bytes()) != digest:
            result.error(f"{relative}: bytes differ from the normative managed role contract pin")


def validate_agents(root: Path, result: Validation) -> None:
    for agent in sorted((root / "agents" / "claude").glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        label = agent.relative_to(root).as_posix()
        try:
            metadata = parse_frontmatter_metadata(text)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result.error(f"{label}: invalid YAML frontmatter: {exc}")
            continue
        if not metadata.get("name"):
            result.error(f"{label}: missing name")
        if not metadata.get("description"):
            result.error(f"{label}: missing description")
        if "model" in metadata:
            result.error(f"{label}: static model is forbidden")
        if "model_reasoning_effort" in metadata:
            result.error(f"{label}: static model_reasoning_effort is forbidden")
    for agent in sorted((root / "agents" / "codex").glob("**/*.toml")):
        try:
            data = tomllib.loads(agent.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            result.error(f"{agent}: invalid TOML: {exc}")
            continue
        if not data.get("name") or not data.get("description"):
            result.error(f"{agent}: missing metadata")
        if "model" in data:
            result.error(f"{agent.relative_to(root)}: static model is forbidden")
        if "model_reasoning_effort" in data:
            result.error(f"{agent.relative_to(root)}: static model_reasoning_effort is forbidden")


def validate_secrets_config(root: Path, result: Validation) -> None:
    """Pin the config the secrets task points `--config` at.

    Pinning the flag only moves the hazard: an edit to this file could set
    `useDefault = false`, or add an allowlist wide enough to match everything, and the gate
    would run green against no rules. The pin is therefore the whole document — exactly one
    `[extend]` table enabling the default ruleset, nothing else — parsed rather than
    byte-compared so the file's explanatory comments stay editable.
    """
    path = root / SECRETS_CONFIG_PATH
    if not path.is_file():
        result.error(f"{SECRETS_CONFIG_PATH} is required: the secrets task pins --config at it")
        return
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        result.error(f"{SECRETS_CONFIG_PATH} is invalid: {exc}")
        return
    if config != {"extend": {"useDefault": True}}:
        result.error(
            f"{SECRETS_CONFIG_PATH} must contain only [extend] useDefault = true, "
            "so the pinned scan cannot be neutered through its own config"
        )


def validate_mermaid_renderer(root: Path, result: Validation) -> None:
    """Pin the M0b renderer supply chain and its Linux-only safety contract.

    The renderer executes a downloaded browser over untrusted diagram text, so the reviewed
    artifact here is the whole identity: exact direct dependencies, exact transitive
    resolutions, the lock bytes, the policy bytes, and the browser digest. Version strings
    alone would leave the sanitizer allowlist and the sandbox limits free to be loosened
    without failing the gate. Rendering itself stays advisory — nothing in `check` invokes
    the renderer or requires a provisioned runtime.
    """
    package_path = root / "package.json"
    lock_path = root / "package-lock.json"
    policy_path = root / "policy" / "mermaid-renderer-linux-v1.json"
    for path, label in (
        (package_path, "package.json"),
        (lock_path, "package-lock.json"),
        (policy_path, "Mermaid renderer policy"),
    ):
        if not path.is_file():
            result.error(f"{label} is required")
            return
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result.error(f"invalid Mermaid renderer artifact: {exc}")
        return

    if package.get("private") is not True or package.get("dependencies") != MERMAID_PACKAGE_PINS:
        result.error("package.json must be private and contain only the exact Mermaid renderer direct pins")
    if package.get("packageManager") != f"npm@{MERMAID_NPM_VERSION}" or package.get("engines") != {"node": NODE_VERSION}:
        result.error("package.json must pin the certified npm and Node identities")

    root_dependencies = lock.get("packages", {}).get("", {}).get("dependencies")
    if lock.get("lockfileVersion") != 3 or root_dependencies != MERMAID_PACKAGE_PINS:
        result.error("package-lock.json must be lockfileVersion 3 with the exact Mermaid direct graph")
    if sha256_bytes(lock_path.read_bytes()) != MERMAID_PACKAGE_LOCK_SHA256:
        result.error("package-lock.json SHA-256 must equal the certified Mermaid dependency graph")
    for path_key, version in MERMAID_LOCK_RESOLUTIONS.items():
        if lock.get("packages", {}).get(path_key, {}).get("version") != version:
            result.error(f"package-lock.json must resolve {path_key} {version}")

    if sha256_bytes(policy_path.read_bytes()) != MERMAID_POLICY_SHA256:
        result.error("Mermaid renderer policy does not match the canonical contract")
    if policy.get("schema_version") != MERMAID_POLICY_SCHEMA:
        result.error(f"Mermaid renderer policy schema must equal {MERMAID_POLICY_SCHEMA}")
    browser = policy.get("browser")
    if not isinstance(browser, dict) or any(browser.get(key) != value for key, value in MERMAID_BROWSER_IDENTITY.items()):
        result.error("Mermaid renderer browser identity mismatch")

    missing = sorted(path for path in MERMAID_REQUIRED_ARTIFACTS if not (root / path).is_file())
    if missing:
        result.error(f"Mermaid renderer artifacts missing: {', '.join(missing)}")


def validate_operator_tools(root: Path, result: Validation) -> None:
    """Parse the shipped shell CLI. A stray `fi` here kills `ccodex launch` on first use.

    This is the one check that reaches `assets/`, which the `scripts/*.sh` glob in
    validate_scripts does not. A missing file is caught by the same run: `bash -n` on a path that
    does not exist exits nonzero and names it.

    Scope change to state plainly: the pre-shrink list also required 19 operator-tool artifacts to
    exist, including `tests/test_operator_tools.py` and `tests/test_claude_statusline.py`. Deleting
    a test module for the shipped operator CLI is therefore no longer a gate failure here. The two
    remaining Python artifacts (`scripts/ccodex_sdlc_readonly.py`,
    `scripts/manage_claude_statusline.py`) still have test-leaf importers, so their disappearance
    still reddens the gate — through the test leaf, not this check.
    """
    bash = shutil.which("bash")
    if bash is None:
        result.warn("bash is unavailable; operator-tool shell syntax was not checked")
        return
    for relative in SHELL_SYNTAX_PATHS:
        completed = subprocess.run(
            [bash, "-n", str(root / relative)], capture_output=True, text=True, check=False
        )
        if completed.returncode:
            result.error(f"invalid shell syntax in {relative}: {completed.stderr.strip()}")


def validate_mise(root: Path, result: Validation) -> None:
    """Keep the GATE's own shape, not a transcription of mise.toml.

    Four checks used to be twelve. What is pinned now: every task the bundle documents exists
    (a renamed task is a dangling entry point), the minimum mise version, `settings.locked` and
    the npm package-manager selection (they decide whether the lock is honored and which resolver
    fetches the npm-backed pins), `check`'s exact composition, and the exact command of each of
    the four leaves `check` depends on — `[tasks.validate] run = "true"` would hollow every check
    in this file, and the same edit to test/self-test/secrets hollows the other three.

    What is deliberately gone: the 197-line restatement of `[tools]`, the per-tool backend and
    per-platform checksum walk, and the exact command of ~25 convenience tasks. `mise.lock` is
    the integrity control — it carries the resolved version, backend, and per-platform checksum
    of every pin, `settings.locked` makes mise honor it, and its bytes are pinned below, so an
    edit to any of those facts fails here without a Python copy of them. A wrong convenience task
    is visible the first time an operator runs it; a hollowed gate leaf is not.

    The lock byte-pin alone would NOT have been enough, and the shrink measured that: `mise.toml`
    is the REQUEST and `mise.lock` is the RESOLUTION, so editing `node = "22.23.1"` in the
    request leaves the lock's bytes untouched and the pin sees nothing. So the two files are
    cross-checked against each other — every requested tool must be resolved in the lock at the
    requested version — which is derived agreement rather than a third Python copy of the
    versions, and it also catches a tool added to the request without being locked and a backend
    repointed by renaming its key (`ubi:` for `github:`). The npm-backend allowlist stays for the
    same reason it was written: an npm pin runs arbitrary transitive install scripts during
    `mise --locked install`, so each one is screened by name per docs/adr/0002's 2026-08-07
    amendment. What is honestly lost is the `depends = ["node"]` edge on the npm-backed pins:
    dropping it fails a fresh machine's first install loudly, which is a DevEx failure and not a
    trust boundary.
    """
    path = root / "mise.toml"
    if not path.is_file():
        result.error("mise.toml is required")
        return
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        tasks = config.get("tasks", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.toml is invalid: {exc}")
        return
    for task in sorted(REQUIRED_TASKS - set(tasks)):
        result.error(f"mise.toml missing task {task}")
    if config.get("min_version") != MIN_MISE_VERSION:
        result.error(f"mise.toml must require mise {MIN_MISE_VERSION}")
    settings = config.get("settings", {})
    if settings.get("locked") is not True:
        result.error("mise.toml must enable locked tool resolution")
    if settings.get("npm", {}).get("package_manager") != "npm":
        result.error("mise.toml npm.package_manager must equal npm")

    expected_check = {
        "description": "Run validation, installer tests, lifecycle self-test, and the secrets scan",
        "depends": ["validate", "test", "self-test", "secrets"],
    }
    if tasks.get("check") != expected_check:
        result.error("mise.toml check must contain only its description and exact validate/test/self-test/secrets dependencies")
    for name, suffix in GATE_LEAF_COMMANDS.items():
        task = tasks.get(name, {})
        for field, executable in (("run", "uv"), ("run_windows", "uv.exe")):
            expected = f"{executable} run --python {PYTHON_VERSION} {suffix}"
            if task.get(field) != expected:
                result.error(f"mise.toml task {name}.{field} must equal {expected!r}")
    expected_secrets = {
        "description": "Scan Git-visible working-tree files with the pinned scanner",
        "run": SECRETS_COMMAND,
        "run_windows": SECRETS_COMMAND_WINDOWS,
    }
    if tasks.get("secrets") != expected_secrets:
        result.error(
            "mise.toml secrets must contain only its description and the exact Git-visible "
            f"scan {SECRETS_COMMAND!r} / {SECRETS_COMMAND_WINDOWS!r}"
        )
    if not (root / SECRETS_SCRIPT_PATH).is_file():
        result.error(f"{SECRETS_SCRIPT_PATH} is required by the secrets task")
    validate_secrets_config(root, result)

    lock_path = root / "mise.lock"
    if not lock_path.is_file():
        result.error("mise.lock is required")
        return
    try:
        lock_bytes = lock_path.read_bytes()
    except OSError as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return
    if sha256_bytes(lock_bytes) != MISE_LOCK_SHA256:
        result.error("mise.lock SHA-256 must equal the canonical generated lock")
    try:
        locked_tools = tomllib.loads(lock_bytes.decode("utf-8")).get("tools", {})
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return

    requested = config.get("tools", {})
    if not isinstance(requested, dict) or not requested:
        result.error("mise.toml must declare its pinned [tools]")
        return
    for name in sorted(requested):
        request = requested[name]
        version = request.get("version") if isinstance(request, dict) else request
        entries = locked_tools.get(name)
        if not isinstance(entries, list) or len(entries) != 1:
            result.error(f"mise.toml tool {name} is not resolved exactly once in mise.lock")
            continue
        if entries[0].get("version") != version:
            result.error(
                f"mise.toml tool {name} requests {version!r} but mise.lock resolves "
                f"{entries[0].get('version')!r}"
            )
    if set(locked_tools) != set(requested):
        result.error("mise.lock must resolve exactly the tools mise.toml requests")
    unreviewed = sorted(
        name for name in requested if name.startswith("npm:") and name not in NPM_BACKED_TOOLS
    )
    if unreviewed:
        result.error(
            "mise.toml npm-backend pins must be reviewed for install-script prerequisites "
            f"per docs/adr/0002 before use: {unreviewed}"
        )


def validate_gate_graph(root: Path, result: Validation) -> None:
    wrapper = root / "scripts" / "validate-bundle.sh"
    if not wrapper.is_file() or wrapper.read_text(encoding="utf-8") != VALIDATOR_WRAPPER:
        result.error("scripts/validate-bundle.sh must be the exec-only pinned mise/uv wrapper")

    bump = root / "scripts" / "bump-version.sh"
    if not bump.is_file():
        result.error("scripts/bump-version.sh is required")
    else:
        bump_text = bump.read_text(encoding="utf-8")
        if not bump_text.startswith(BUMP_PREFIX) or not bump_text.endswith("\nPY\n"):
            result.error("scripts/bump-version.sh must use only the pinned mise/uv Python launcher")
        heredoc_end = bump_text.rfind("\nPY\n")
        if heredoc_end != len(bump_text) - 4:
            result.error("scripts/bump-version.sh must end at the pinned Python heredoc")

    hooks = root / "lefthook.yml"
    expected_hooks = """pre-commit:
  commands:
    validate:
      run: mise run validate

pre-push:
  commands:
    test:
      run: mise run test
    self-test:
      run: mise run self-test
    secrets:
      run: mise run secrets
"""
    if not hooks.is_file() or hooks.read_text(encoding="utf-8") != expected_hooks:
        result.error("lefthook.yml must contain the documented best-effort gate subsets")

    workflow = root / CI_WORKFLOW_RELATIVE_PATH
    if not workflow.is_file():
        result.error(".github/workflows/validate.yml is required")
    else:
        # Exact-content pin, digest form. See CI_WORKFLOW_SHA256 for why this stayed exact rather
        # than becoming a substring check, and for the re-pin command.
        try:
            workflow_text = workflow.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            result.error(f"CI workflow is unreadable: {exc}")
            return
        if sha256_bytes(workflow_text.encode("utf-8")) != CI_WORKFLOW_SHA256:
            result.error("CI workflow must equal the single authoritative mise run check graph")

    claude = root / "CLAUDE.md"
    if not claude.is_file() or not claude.read_text(encoding="utf-8").startswith("@AGENTS.md\n"):
        result.error("CLAUDE.md must begin with @AGENTS.md")


def validate_versions(root: Path, result: Validation) -> None:
    manifest_path = root / ".version-bump.json"
    if not manifest_path.is_file():
        return
    expected: object = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = manifest["current"]
        targets = manifest["targets"]
        for target in targets:
            value: object = json.loads((root / target["file"]).read_text(encoding="utf-8"))
            for key in (part for part in target["jq"].strip(".").split(".") if part):
                value = value[int(key)] if key.isdigit() else value[key]  # type: ignore[index]
            if value != expected:
                result.error(f"version drift: {target['file']} {target['jq']} = {value} (expect {expected})")
    except (KeyError, IndexError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result.error(f"invalid version manifest contract: {exc}")
    if expected is None:
        return
    # The release contract is deliberately NOT a bump target: its version transition is a reviewed
    # edit (scripts/ccodex_sdlc.py refuses any other checkout identity). But build_release.py stamps
    # and names the archive from the contract-tied policy version, so a routine bump-version.sh run
    # that moved `current` without that reviewed edit would ship a mislabeled archive under a green
    # gate. Fail closed on the skew instead.
    try:
        contract = load_release_contract_json(root / RELEASE_CONTRACT_RELATIVE_PATH)
        checkout = contract.get("checkout")
        contract_version = checkout.get("version") if isinstance(checkout, dict) else None
    except ValueError:
        contract_version = None
    if contract_version != expected:
        result.error(
            f".version-bump.json current = {expected!r} but policy/release-contract.v1.json "
            f"checkout.version = {contract_version!r}; bump both in one reviewed change"
        )


def validate_scripts(root: Path, result: Validation) -> None:
    bash = shutil.which("bash") if sys.platform != "win32" else None
    if bash:
        for script in sorted((root / "scripts").glob("*.sh")):
            completed = subprocess.run([bash, "-n", str(script)], check=False, capture_output=True, text=True)
            if completed.returncode:
                result.error(f"{script} does not parse: {completed.stderr.strip()}")

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell:
        for script in sorted((root / "scripts").glob("*.ps1")):
            escaped = str(script).replace("'", "''")
            command = f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$null,[ref]$null)"
            completed = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                result.error(f"{script} does not parse: {completed.stderr.strip()}")


def validate_manifests(root: Path, result: Validation) -> None:
    manifests = (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        # The marketplace entry's source is ./plugin, so this manifest — not the root
        # one — is what a marketplace install actually reads. It must parse too.
        "plugin/.claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        "gemini-extension.json",
    )
    for name in manifests:
        path = root / name
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result.error(f"invalid JSON: {name}: {exc}")


def validate_policy(root: Path, result: Validation) -> None:
    # os.walk rather than rglob so provisioned trees are pruned instead of visited: a
    # provisioned node_modules is tens of thousands of unreviewed files, and scanning it would
    # make this verdict depend on whether the host has run Mermaid provisioning.
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name not in UNREVIEWED_TREES]
        for filename in filenames:
            path = Path(directory) / filename
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if path.name != "validate_bundle.py" and SECRET_PATTERN.search(text):
                result.error(f"possible secret or internal hostname found: {path.relative_to(root)}")


def validate(root: Path) -> Validation:
    result = Validation()
    # Payload guards first: these are the only checks whose absence produces a silent,
    # host-undiagnosable failure for an operator.
    validate_skills(root, result)
    validate_workflows(root, result)
    validate_hooks(root, result)
    validate_agents(root, result)
    validate_python(root, result)
    validate_scripts(root, result)
    validate_operator_tools(root, result)
    validate_manifests(root, result)
    validate_versions(root, result)
    # Trust boundaries over shipped bytes and the gate's own shape.
    validate_source_pinned_protected_role_authority(root, result)
    validate_managed_role_authority_projection(root, result)
    validate_managed_role_contract(root, result)
    validate_packaged_policy_copies(root, result)
    validate_mermaid_renderer(root, result)
    validate_release_contract(root, result)
    validate_release_candidate_policy(root, result)
    validate_ccodex_sdlc_report_policies(root, result)
    validate_mise(root, result)
    validate_gate_graph(root, result)
    validate_policy(root, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = validate(args.root.resolve())
    for warning in result.warnings:
        print(f"warn:  {warning}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"\nvalidate-bundle: {len(result.errors)} error(s), {len(result.warnings)} warning(s)")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
