#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Validate Agentic SDLC bundle metadata and lifecycle contracts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    "try { new AsyncFunction(fs.readFileSync(process.argv[1], 'utf8')); }"
    "catch (error) { process.stderr.write(String((error && error.message) || error)); process.exit(1); }"
)
REQUIRED_TASKS = {
    "bundle:install",
    "bundle:status",
    "bundle:uninstall",
    "bundle:install:claude",
    "bundle:install:codex",
    "bundle:install:all-hosts",
    "bundle:status:all-hosts",
    "research-os:install",
    "operator-tools:install",
    "operator-tools:status",
    "operator-tools:retire-aliases",
    "operator-tools:uninstall",
    "operator-tools:self-test",
    "claude:statusline:status",
    "claude:statusline:activate",
    "claude:statusline:deactivate",
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
UV_VERSION = "0.12.5"
PYTHON_VERSION = "3.12.11"
LEFTHOOK_VERSION = "2.1.10"
NODE_VERSION = "22.23.2"
BUN_VERSION = "1.4.0"
SEEDS_VERSION = "0.5.15"
SEEDS_TOOL = "npm:@os-eco/seeds-cli"
# Convenience tier. Pinned for identical resolution across hosts; no gate depends on them.
RIPGREP_VERSION = "15.2.0"
FD_VERSION = "10.4.2"
JQ_VERSION = "1.8.2"
GH_VERSION = "2.98.0"
BETTERLEAKS_VERSION = "1.8.1"
BETTERLEAKS_TOOL = "github:betterleaks/betterleaks"
# The renderer's mmdc version. It is pinned by package-lock.json digest below, NOT by a mise
# [tools] entry: that entry was removed 2026-08-07 (docs/adr/0002 amendment) because puppeteer's
# postinstall came with it and needed a zip archiver mise does not install, failing the whole
# `mise --locked install`. Nothing resolves mmdc through mise, so there is no lock/tool pin here.
MERMAID_VERSION = "11.16.0"
# Installed by default per docs/adr/0005. The packaging pin is convenience tier like the two
# npm pins above; the boundary that matters is usage-level and lives in the launcher script,
# not here (docs/adr/0003: non-Anthropic routing only, never subscription OAuth).
OPENCODEX_VERSION = "2.28.0"
OPENCODEX_TOOL = "npm:@bitkyc08/opencodex"
# node 22.23.2 bundles npm 10.9.8, so the M0b renderer's npm identity is pinned as its own
# tool. scripts/provision_mermaid_linux.py resolves exactly this version through `mise where`
# to install the renderer's node_modules. Provisioning is an explicit operator step and no
# gate leaf invokes it, so this pin never becomes a bootstrap prerequisite.
MERMAID_NPM_VERSION = "10.8.1"
MERMAID_NPM_TOOL = "npm"
MERMAID_NPM_BACKEND = "npm:npm"
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
OPERATOR_TOOL_ARTIFACTS = frozenset(
    {
        "assets/claude/statusline-command.sh",
        # Sourced by both launchers (ADR-0010). Registered here so the gate parses it: it lives
        # under assets/, which the scripts/*.sh syntax glob does not reach.
        "assets/claude/session-inheritance.sh",
        "assets/launchers/ccodex.in",
        "policy/ccodex-sdlc-read-report.v1.json",
        "policy/ccodex-sdlc-read-report.v2.json",
        "policy/release-candidate-execution.v1.json",
        "scripts/ccodex_sdlc.py",
        "scripts/ccodex_sdlc_readonly.py",
        "scripts/install_operator_tools.py",
        "scripts/manage_claude_statusline.py",
        "tests/test_claude_statusline.py",
        "tests/test_manage_claude_statusline.py",
        "tests/test_operator_tools.py",
        "tests/test_ccodex_sdlc.py",
        "tests/test_opencodex_claude.py",
    }
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
NPM_BACKED_TOOLS = frozenset({SEEDS_TOOL, OPENCODEX_TOOL, MERMAID_NPM_TOOL})
# Every npm-backend pin resolves an arbitrary dependency tree whose postinstall scripts run on
# install, so this is the reviewed allowlist for that backend, screened per docs/adr/0002's
# 2026-08-07 amendment: a pin may not require a tool mise itself does not install. Reviewed
# 2026-08-07 — Seeds runs no install script; opencodex runs one (transitive bun 1.3.14) that
# extracts with Node's built-in zlib; bare npm is npm itself.
# A pinned backend is part of the contract: it fixes WHERE a tool comes from, so a registry
# alias cannot be silently repointed at a different upstream.
EXPECTED_LOCK_BACKENDS = {
    "uv": "aqua:astral-sh/uv",
    "lefthook": "aqua:evilmartians/lefthook",
    "node": "core:node",
    "bun": "core:bun",
    "ripgrep": "aqua:BurntSushi/ripgrep",
    "fd": "aqua:sharkdp/fd",
    "jq": "aqua:jqlang/jq",
    "gh": "aqua:cli/cli",
    SEEDS_TOOL: SEEDS_TOOL,
    BETTERLEAKS_TOOL: BETTERLEAKS_TOOL,
    OPENCODEX_TOOL: OPENCODEX_TOOL,
    MERMAID_NPM_TOOL: MERMAID_NPM_BACKEND,
}
MISE_LOCK_SHA256 = "31ed02eb15e425253e90b3f3b4d117f0b5c3876fa9351e27b6b6375fd47d5b1c"
TASK_COMMANDS = {
    "validate": "--script scripts/validate_bundle.py",
    "bundle:install": "--script scripts/install_skill_bundle.py install",
    "bundle:status": "--script scripts/install_skill_bundle.py status",
    "bundle:uninstall": "--script scripts/install_skill_bundle.py uninstall",
    "bundle:install:claude": "--script scripts/install_skill_bundle.py install --agent claude",
    "bundle:install:codex": "--script scripts/install_skill_bundle.py install --agent codex",
    "bundle:install:all-hosts": "--script scripts/run_all_hosts.py install",
    "bundle:status:all-hosts": "--script scripts/run_all_hosts.py status",
    "research-os:install": "--script skills/codex-research-os/scripts/install_research_os.py",
    "operator-tools:install": "--script scripts/install_operator_tools.py install",
    "operator-tools:status": "--script scripts/install_operator_tools.py status",
    "operator-tools:retire-aliases": "--script scripts/install_operator_tools.py retire-aliases",
    "operator-tools:uninstall": "--script scripts/install_operator_tools.py uninstall",
    "operator-tools:self-test": "--script scripts/install_operator_tools.py self-test",
    "claude:statusline:status": "--script scripts/manage_claude_statusline.py status",
    "claude:statusline:activate": "--script scripts/manage_claude_statusline.py activate",
    "claude:statusline:deactivate": "--script scripts/manage_claude_statusline.py deactivate",
    # Pinned like the operator-tools rows: same uv entrypoint on both platforms, so the exact
    # command string is part of the contract. `install` carries no --yes here; the dry run is
    # the default and the operator supplies --yes as a task argument.
    "libraries:list": "--script scripts/install_external_libraries.py list",
    "libraries:install": "--script scripts/install_external_libraries.py install",
    "libraries:status": "--script scripts/install_external_libraries.py status",
    "libraries:migrate": "--script scripts/install_external_libraries.py migrate",
    "mermaid:linux-test": "--with pyyaml==6.0.3 python -m unittest discover -s tests_linux",
    "test": "--with pyyaml==6.0.3 python -m unittest discover -s tests",
    "self-test": "--script scripts/install_skill_bundle.py self-test",
}
# Pinned outside TASK_COMMANDS because the M0b boundary is Linux x64 only: a run_windows
# variant would advertise a platform the renderer explicitly refuses (EXIT_UNSUPPORTED).
MERMAID_PROVISION_TASK = {
    "description": "Provision the pinned Linux Mermaid browser runtime (explicit, not a gate)",
    "run": f"uv run --python {PYTHON_VERSION} --script scripts/provision_mermaid_linux.py",
}
# The secrets task runs one stdlib wrapper through the pinned Python. It asks Git for exactly
# tracked + nonignored-untracked files, so ignored operator runtime state is absent without hiding
# a force-tracked file beneath an ignored prefix. The wrapper supplies this explicit tracked config
# to every scanner batch; history scanning remains a separate consent-requiring operation.
SECRETS_CONFIG_PATH = ".config/betterleaks.toml"
SECRETS_SCRIPT_PATH = "scripts/secrets_scan.py"
SECRETS_COMMAND = f"uv run --python {PYTHON_VERSION} --script {SECRETS_SCRIPT_PATH}"
SECRETS_COMMAND_WINDOWS = f"uv.exe run --python {PYTHON_VERSION} --script {SECRETS_SCRIPT_PATH}"
RECEIPT_POLICY_PATH = Path(__file__).parents[1] / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
NORMATIVE_CONTRACT_PATH = Path(__file__).parents[1] / "policy" / "runtime-assignment-normative-contract-v1.json"
ROLE_MANIFEST_PATH = Path(__file__).parents[1] / "policy" / "role-manifest.v1.json"
RELEASE_CONTRACT_RELATIVE_PATH = Path("policy") / "release-contract.v1.json"
RELEASE_CANDIDATE_POLICY_RELATIVE_PATH = Path("policy") / "release-candidate.v1.json"
RELEASE_CANDIDATE_POLICY_SCHEMA = "release-candidate-policy/v1"
RELEASE_CANDIDATE_ACQUISITION_POLICY_RELATIVE_PATH = (
    Path("policy") / "release-candidate-acquisition.v1.json"
)
RELEASE_CANDIDATE_ACQUISITION_POLICY_SCHEMA = "release-candidate-acquisition-policy/v1"
RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256 = (
    "4a8b379ff7724653082d380a5fd627241e26c07347e34c48b1dffb688952743a"
)
CCODEX_SDLC_READ_REPORT_POLICY_RELATIVE_PATH = Path("policy") / "ccodex-sdlc-read-report.v1.json"
CCODEX_SDLC_READ_REPORT_POLICY_SCHEMA = "ccodex-sdlc-read-report-policy/v1"
CCODEX_SDLC_READ_REPORT_SCHEMA = "ccodex-sdlc-read-report/v1"
RELEASE_CANDIDATE_EXECUTION_POLICY_RELATIVE_PATH = Path("policy") / "release-candidate-execution.v1.json"
CCODEX_SDLC_CANDIDATE_REPORT_POLICY_RELATIVE_PATH = Path("policy") / "ccodex-sdlc-read-report.v2.json"
CCODEX_SDLC_CANDIDATE_REPORT_POLICY_SHA256 = "0667ab351d7ab755f94f4ca74be1d3a6510c0cf7ea30f35ff9a0821e732108d9"
CCODEX_SDLC_READ_REPORT_TOP_LEVEL_FIELDS = [
    "schema_version",
    "command",
    "checkout",
    "runtime",
    "operator_tools",
    "bundle",
    "recovery",
    "future_dimensions",
    "findings",
    "overall",
]
CCODEX_SDLC_READ_REPORT_FIELDS = {
    "bundle": ["entries", "findings", "recovery", "state", "state_paths"],
    "checkout": ["certification_claim", "plane", "public_channel", "release", "release_topology_adr_status", "version"],
    "command": ["dry_run", "verb"],
    "finding": ["code", "component", "message", "path"],
    "future_dimensions": ["activation", "release", "waves"],
    "overall": ["exit_class", "state"],
    "projection_entry": ["name", "path", "state"],
    "recovery": ["effect", "proposals", "state"],
    "recovery_item": ["action", "component", "path", "state"],
    "runtime": ["interpreter", "isolated", "state", "version"],
}
CCODEX_SDLC_READ_REPORT_VOCABULARIES = {
    "command_verbs": ["doctor", "inspect", "recover", "status"],
    "component_states": ["absent", "blocked", "degraded", "healthy", "unreadable"],
    "entry_states": ["absent", "foreign", "modified", "owned", "racy", "symlinked", "unreadable", "unsupported"],
    "exit_classes": ["invariant-failure", "ok", "safe-refusal"],
    "finding_codes": [
        "checkout-contract-invalid",
        "foreign-entry",
        "foreign-state",
        "owned-entry-conflict",
        "owned-entry-racy",
        "pending-invalid",
        "pending-recovery",
        "runtime-admission-refused",
        "state-ambiguous",
        "state-malformed",
        "state-racy",
        "state-symlinked",
        "state-unsupported",
        "state-unreadable",
    ],
    "finding_components": ["bundle", "checkout", "operator-tools", "runtime"],
    "overall_states": ["absent", "blocked", "degraded", "healthy", "unreadable"],
    "recovery_actions": ["lifecycle-dry-run"],
    "recovery_effects": ["none"],
    "recovery_item_states": ["pending"],
    "recovery_states": ["not-needed", "pending", "proposed"],
    "runtime_states": ["admitted", "refused"],
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
PACKAGED_POLICY_DIR = Path(__file__).parents[1] / "skills" / "codex-research-os" / "policy"
RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256 = "675c8799587b9b7151fd7f98f3424e5e9783986d2db9dc5488bb2a1a704b7794"
RESEARCH_DIRECTOR_SEEDS_AUTHORITY = """Seeds authority:
- Research Director is Seeds-read-only.
- Use only the exact accepted Seeds inspection contract:
  `Seeds(<target>, <args...>)` = `MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec node@22.23.2 bun@1.4.0 npm:@os-eco/seeds-cli@0.5.15 -- sd <args>`.
- Inspect `Seeds(<target>, prime)`, `Seeds(<target>, ready --format json)`, and `Seeds(<target>, blocked --format json)` before substantive orchestration when Seeds is available.
- Do not create, claim, update, close, sync, or disposition Seeds.
- For work that outlives the session, emit exactly one typed `SeedProposal { title: str, summary: str, acceptance_criteria: list[str], priority: str, blocking: bool, scope: list[str], evidence: list[str], dependencies: list[str], recommended_owner: str }` for conductor triage.
"""
CLAUDE_GLOBAL_ROLE_FILENAMES = frozenset(
    {
        "sdlc-cartographer.md",
        "sdlc-critic.md",
        "sdlc-implementer.md",
        "sdlc-integrator.md",
        "sdlc-planner.md",
        "sdlc-researcher.md",
        "sdlc-reviewer.md",
    }
)
CODEX_GLOBAL_ROLE_FILENAMES = frozenset(
    {
        "sdlc-cartographer.toml",
        "sdlc-critic.toml",
        "sdlc-implementer.toml",
        "sdlc-integrator.toml",
        "sdlc-planner.toml",
        "sdlc-researcher.toml",
        "sdlc-reviewer.toml",
    }
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
PROTECTED_REVIEWER_PATHS = frozenset(
    {
        "agents/claude/sdlc-reviewer.md",
        "agents/codex/sdlc-reviewer.toml",
        "agents/codex/research/adversarial_reviewer.toml",
        "agents/codex/research/replication_reviewer.toml",
        "agents/codex/research/safety_reviewer.toml",
    }
)
SOURCE_PINNED_GLOBAL_PATHS = frozenset(
    {
        *(f"agents/claude/{filename}" for filename in CLAUDE_GLOBAL_ROLE_FILENAMES),
        *(f"agents/codex/{filename}" for filename in CODEX_GLOBAL_ROLE_FILENAMES),
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
    r"(?i)\b(?:may|can|should|will|is\s+authorized\s+to)\s+"
    r"(?:create|claim|update|close|sync|disposition|label|delete|archive|mutate)\b.{0,80}\b(?:Seeds?|SeedProposal)\b"
)
RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256 = "22c165551389b844fc46b8fcae2e7cd750254181ad2096b6884b0ee8f25b801c"
SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256 = {
    "agents/claude/sdlc-reviewer.md": "fe2297470d4c0cc8fce37fbc8f2b4b24c117ba808cf5ddd199f5a2c7c699f860",
    "agents/codex/sdlc-reviewer.toml": "816f52d896821f4d5964e0d9fc8dd412b01e27800733613ace496eeec61dd003",
    "agents/codex/research/adversarial_reviewer.toml": "f452a51a61cd043181443722077af7e41bfef8b558630c76b5003e52db43c0df",
    "agents/codex/research/replication_reviewer.toml": "81d4038144782721c2df34d604df9af86d1a7e00628c9cb8f94c19610bf695c9",
    "agents/codex/research/safety_reviewer.toml": "afe1a80ec71ebb03d62b438d188e8ebbd0670c6460e824dd418048a11165c5a3",
}
CANONICAL_RUNTIME_CONTRACT_SHA256 = "9399a0d9ebed19cefd020ac190ac772641e804e9f8a1632fb2b01059c94ba420"
EXACT_MODEL_PROVIDER_MAP = {
    "claude-fable-5": "anthropic",
    "claude-opus-4-8": "anthropic",
    "claude-sonnet-5": "anthropic",
    "gpt-5.6-luna": "openai",
    "gpt-5.6-sol": "openai",
    "gpt-5.6-terra": "openai",
}
EXACT_MODEL_PAIRS = {
    "frontier": ["gpt-5.6-sol", "claude-fable-5"],
    "judgment": ["gpt-5.6-terra", "claude-opus-4-8"],
    "volume": ["gpt-5.6-luna", "claude-sonnet-5"],
}
ALLOWED_EFFORTS = ["low", "medium", "high", "xhigh", "max"]
ALLOWED_CONTEXT_FORMS = ["base", "[1m]"]
ALLOWED_EVIDENCE = {
    "request_injection": {
        "source_kinds": ["immutable_request_receipt"],
        "statuses": ["verified"],
        "schemas": ["launcher-request-evidence/v1"],
    },
    "model_mapping": {
        "source_kinds": ["policy_exact_id_mapping"],
        "statuses": ["unavailable"],
        "schemas": ["runtime-assignment-policy-v1"],
    },
    "transport_readback": {
        "source_kinds": ["transport_readback"],
        "statuses": ["verified", "unavailable"],
        "schemas": ["runtime-assignment-readback/v1"],
    },
}
CERTIFIED_MODEL_ORDER = [
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
]
CERTIFIED_CONTEXT_FORMS_BY_MODEL = {
    "claude-fable-5": ["base"],
    "claude-opus-4-8": ["base"],
    "claude-sonnet-5": ["base"],
    "gpt-5.6-luna": ["base", "[1m]"],
    "gpt-5.6-sol": ["base", "[1m]"],
    "gpt-5.6-terra": ["base", "[1m]"],
}
PRODUCTION_EFFORTS_BY_MODEL = {
    "claude-fable-5": ["xhigh", "max"],
    "claude-opus-4-8": ["high", "xhigh"],
    "claude-sonnet-5": ["high", "xhigh"],
    "gpt-5.6-luna": ["high", "xhigh"],
    "gpt-5.6-sol": ["high", "xhigh"],
    "gpt-5.6-terra": ["xhigh", "max"],
}
VALIDATION_ONLY_SEMANTICS = (
    "The receipt is validated only for canonical internal consistency. It does not authenticate an issuer "
    "or prove external request injection, readback, spawn identity, or admission. The external authenticated "
    "harness is the sole spawn and admission authority."
)
ONE_MILLION_CONTEXT_SEMANTICS = (
    "A `[1m]` request or base-ID readback proves neither intelligence, upstream context capacity, "
    "compaction, nor effort compliance."
)
SEEDS_READ_ONLY_SEMANTICS = (
    "Every managed role is Seeds-read-only. No runtime, authority, or other protected block is excluded: "
    "managed roles must not create, claim, update, close, sync, disposition, label, delete, archive, or "
    "otherwise mutate Seeds. They may inspect through the accepted launcher and return advisory SeedProposal "
    "values to the conductor."
)
RUNTIME_RECEIPT_SOURCE_FIELDS = frozenset(
    {
        "request_injection_source",
        "model_readback_source",
        "effort_readback_source",
        "context_readback_source",
    }
)
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

ROLE_MANIFEST_SCHEMA_VERSION = "role-manifest/v1"
ROLE_MANIFEST_RUNTIME_MODEL_SOURCE = "conductor-supplied-RuntimeAssignment"
ROLE_MANIFEST_LANE_FAMILIES = frozenset(
    {"frontier", "judgment", "volume", "mechanical-floor"}
)
ROLE_MANIFEST_ARTIFACTS = frozenset(
    {"Map", "ResearchBrief", "SeedProposal", "Candidate", "ReviewFinding", "IntegrationReport"}
)
ROLE_MANIFEST_SUBMISSION_CONTRACTS = frozenset({"eight-heading", "research-ledger"})
ROLE_MANIFEST_TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "generated_from", "counts", "roles"}
)
ROLE_MANIFEST_ROLE_KEYS = frozenset(
    {
        "kind",
        "phase",
        "purpose",
        "delegation_limit",
        "queue_authority",
        "fan_in_authority",
        "publication_authority",
        "model",
        "capabilities",
        "artifacts",
        "projections",
        "advisory_only",
        "cartography",
    }
)
ROLE_MANIFEST_REQUIRED_ROLE_KEYS = ROLE_MANIFEST_ROLE_KEYS - {"advisory_only", "cartography"}
# The seven delivery role IDs (logical), each carrying claude + codex projections.
DELIVERY_ROLE_IDS = frozenset(
    filename[len("sdlc-"):-len(".md")] for filename in CLAUDE_GLOBAL_ROLE_FILENAMES
)
# advisory_only=true is mandatory for the protected-reviewer roles and forbidden as an
# authority-widening escape hatch elsewhere; the anti-bypass check keys off this set.
ROLE_MANIFEST_ADVISORY_ONLY_ROLES = frozenset(
    {"reviewer", "critic", "adversarial_reviewer", "replication_reviewer", "safety_reviewer"}
)

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
EXPECTED_WORKFLOW = r"""name: validate-bundle

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    name: mise check (${{ matrix.os }})
    strategy:
      fail-fast: false
      matrix:
        os:
          - blacksmith-2vcpu-ubuntu-2404
          - blacksmith-6vcpu-macos-latest
          - blacksmith-2vcpu-windows-2025
    runs-on: ${{ matrix.os }}
    steps:
      # actions/checkout v4.3.1
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      # jdx/mise-action v2.4.7
      - uses: jdx/mise-action@c37c93293d6b742fc901e1406b8f764f6fb19dac
        with:
          install: true
      # advisory forensics probe for seed agentic-sdlc-df5f (mechanisms A/B1/B2); remove once the runner's btime/ctime data is recorded
      - name: Advisory host capability probe (never a gate leaf)
        if: runner.os == 'Linux'
        continue-on-error: true
        timeout-minutes: 2
        run: |
          python3 -u - <<'PROBE_EOF' || true
          import ctypes
          import errno as errno_mod
          import os
          import struct
          import subprocess
          import tempfile
          import time
          import traceback


          def _section(title):
              print("=== SECTION: %s ===" % title, flush=True)


          def _statx_btime_ns_and_ino(path):
              libc = ctypes.CDLL(None, use_errno=True)
              if not hasattr(libc, "statx"):
                  raise OSError(0, "libc has no statx symbol")
              libc.statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
              libc.statx.restype = ctypes.c_int
              buf = ctypes.create_string_buffer(256)
              at_fdcwd = -100
              statx_basic_stats = 0x7FF
              statx_btime = 0x800
              rc = libc.statx(at_fdcwd, os.fsencode(path), 0, statx_basic_stats | statx_btime, buf)
              if rc != 0:
                  e = ctypes.get_errno()
                  raise OSError(e, os.strerror(e))
              mask = struct.unpack_from("<I", buf, 0)[0]
              ino = struct.unpack_from("<Q", buf, 32)[0]
              sec = struct.unpack_from("<q", buf, 80)[0]
              nsec = struct.unpack_from("<I", buf, 88)[0]
              have_btime = bool(mask & statx_btime)
              return have_btime, ino, sec * 10**9 + nsec


          _section("1. uname / kernel version")
          try:
              print("uname -a:", " ".join(os.uname()))
              try:
                  with open("/proc/version") as f:
                      print("/proc/version:", f.read().strip())
              except Exception as e:
                  print("/proc/version unavailable:", repr(e))
          except Exception:
              traceback.print_exc()

          _section("2. workspace filesystem")
          try:
              workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
              print("workspace path:", workspace)
              found = False
              try:
                  result = subprocess.run(
                      ["findmnt", "-no", "FSTYPE,SOURCE,OPTIONS", "-T", workspace],
                      capture_output=True, text=True, timeout=10,
                  )
                  if result.returncode == 0 and result.stdout.strip():
                      print("findmnt:", result.stdout.strip())
                      found = True
                  else:
                      print("findmnt failed rc=%r stderr=%r" % (result.returncode, result.stderr.strip()))
              except Exception as e:
                  print("findmnt unavailable:", repr(e))
              if not found:
                  real_ws = os.path.realpath(workspace)
                  best = None
                  try:
                      with open("/proc/self/mounts") as f:
                          for line in f:
                              parts = line.split()
                              if len(parts) < 4:
                                  continue
                              src, mnt, fstype, opts = parts[0], parts[1], parts[2], parts[3]
                              mnt_decoded = mnt.replace("\\040", " ")
                              if real_ws == mnt_decoded or real_ws.startswith(mnt_decoded.rstrip("/") + "/") or mnt_decoded == "/":
                                  if best is None or len(mnt_decoded) > len(best[1]):
                                      best = (src, mnt_decoded, fstype, opts)
                      if best:
                          print("/proc/self/mounts fallback: source=%s mount=%s fstype=%s options=%s" % best)
                      else:
                          print("/proc/self/mounts fallback: no matching mount found")
                  except Exception as e:
                      print("/proc/self/mounts fallback failed:", repr(e))
          except Exception:
              traceback.print_exc()

          _section("3. linkat AT_EMPTY_PATH probe (O_TMPFILE)")
          try:
              workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
              with tempfile.TemporaryDirectory(dir=workspace) as td:
                  print("probe tempdir:", td)
                  o_tmpfile = getattr(os, "O_TMPFILE", 0o20200000)
                  tmp_fd = None
                  try:
                      tmp_fd = os.open(td, o_tmpfile | os.O_WRONLY, 0o600)
                      print("O_TMPFILE open: SUCCESS fd=%d" % tmp_fd)
                  except OSError as e:
                      print(
                          "O_TMPFILE open: UNSUPPORTED errno=%d (%s): %s"
                          % (e.errno, errno_mod.errorcode.get(e.errno, "?"), e.strerror)
                      )
                  if tmp_fd is not None:
                      dir_fd = None
                      try:
                          dir_fd = os.open(td, os.O_RDONLY)
                          libc = ctypes.CDLL(None, use_errno=True)
                          libc.linkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
                          libc.linkat.restype = ctypes.c_int
                          at_empty_path = 0x1000
                          target_name = b"linkat-probe-target"
                          rc = libc.linkat(tmp_fd, b"", dir_fd, target_name, at_empty_path)
                          if rc == 0:
                              print("linkat AT_EMPTY_PATH: SUCCESS (materialized %s)" % target_name.decode())
                          else:
                              err = ctypes.get_errno()
                              print(
                                  "linkat AT_EMPTY_PATH: FAILED errno=%d (%s): %s"
                                  % (err, errno_mod.errorcode.get(err, "?"), os.strerror(err))
                              )
                      except Exception as e:
                          print("linkat probe raised:", repr(e))
                      finally:
                          if dir_fd is not None:
                              os.close(dir_fd)
                          os.close(tmp_fd)
          except Exception:
              traceback.print_exc()

          _section("4. btime granularity")
          try:
              workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
              with tempfile.TemporaryDirectory(dir=workspace) as td:
                  samples = []
                  have_any = False
                  t0 = time.monotonic_ns()
                  for i in range(40):
                      p = os.path.join(td, "btime-%02d.txt" % i)
                      with open(p, "wb") as f:
                          f.write(b"x")
                      try:
                          have, ino, btime_ns = _statx_btime_ns_and_ino(p)
                          have_any = have_any or have
                          samples.append((have, btime_ns))
                      except Exception as e:
                          samples.append((False, None))
                          print("  statx failed on sample %d: %r" % (i, e))
                  print("sample window wall elapsed ns:", time.monotonic_ns() - t0)
                  available = [b for (have, b) in samples if have and b is not None]
                  print("btime available at all:", have_any, "usable samples:", len(available), "/", len(samples))
                  if available:
                      distinct = sorted(set(available))
                      deltas = [b - a for a, b in zip(available, available[1:])]
                      print("distinct btime count:", len(distinct))
                      print("btime min delta ns (consecutive):", min(deltas) if deltas else None)
                      print("btime max delta ns (consecutive):", max(deltas) if deltas else None)
                      print("btime overall span ns:", max(available) - min(available))
                  else:
                      print("no usable btime samples collected")

                  b1_path = os.path.join(td, "b1-recreate.txt")
                  b1_repeats = 0
                  for trial in range(20):
                      with open(b1_path, "wb") as f:
                          f.write(b"a")
                      have1, ino1, bt1 = _statx_btime_ns_and_ino(b1_path)
                      os.remove(b1_path)
                      with open(b1_path, "wb") as f:
                          f.write(b"b")
                      have2, ino2, bt2 = _statx_btime_ns_and_ino(b1_path)
                      os.remove(b1_path)
                      print("B1 witness: first (ino=%r, btime_ns=%r) second (ino=%r, btime_ns=%r)" % (ino1, bt1, ino2, bt2))
                      print(
                          "B1 witness pair repeated (ino AND btime both equal):",
                          "UNAVAILABLE-btime (witness is degenerate; treat as REPEATED)" if not (have1 and have2) else (ino1, bt1) == (ino2, bt2),
                      )
                      if (ino1, bt1) == (ino2, bt2):
                          b1_repeats += 1
                  print("B1 witness repeats: %d/20" % b1_repeats)
          except Exception:
              traceback.print_exc()

          _section("5. ctime_ns / mtime_ns granularity")
          try:
              workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
              with tempfile.TemporaryDirectory(dir=workspace) as td:
                  ctimes = []
                  mtimes = []
                  t0 = time.monotonic_ns()
                  for i in range(40):
                      p = os.path.join(td, "ct-%02d.txt" % i)
                      with open(p, "wb") as f:
                          f.write(b"x")
                      st = os.stat(p)
                      ctimes.append(st.st_ctime_ns)
                      mtimes.append(st.st_mtime_ns)
                  print("sample window wall elapsed ns:", time.monotonic_ns() - t0)

                  def _summarize(name, values):
                      distinct = sorted(set(values))
                      deltas = [b - a for a, b in zip(values, values[1:])]
                      nonzero = [d for d in deltas if d > 0]
                      print("%s distinct count: %d / %d samples" % (name, len(distinct), len(values)))
                      print("%s min delta ns (consecutive, incl. zero): %r" % (name, min(deltas) if deltas else None))
                      print("%s min nonzero delta ns: %r" % (name, min(nonzero) if nonzero else None))
                      print("%s max delta ns: %r" % (name, max(deltas) if deltas else None))

                  _summarize("ctime_ns", ctimes)
                  _summarize("mtime_ns", mtimes)
          except Exception:
              traceback.print_exc()

          _section("6. effective capabilities")
          try:
              with open("/proc/self/status") as f:
                  for line in f:
                      if line.startswith("CapEff:"):
                          print(line.strip())
                          break
                  else:
                      print("CapEff line not found in /proc/self/status")
          except Exception:
              traceback.print_exc()
          PROBE_EOF
          exit 0
      - name: Run authoritative check
        run: mise run check
"""


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
        description = metadata_value(metadata, "description")
        if not description:
            result.error(f"{directory}: missing description")
        elif len(description) > 1024:
            result.error(f"{directory}: description exceeds 1024 characters")
        # A skill may not pin a model either. Parse semantically rather than matching the raw
        # frontmatter string: a substring test on `metadata` also hits `name:
        # model-tier-rightsizing`, and a line-anchored regex still misses the quoted and
        # \u-escaped key forms that validate_agents already rejects.
        try:
            skill_metadata = parse_frontmatter_metadata(text)
        except ValueError as exc:
            result.error(f"{directory}: invalid frontmatter: {exc}")
        else:
            for forbidden in ("model", "model_reasoning_effort"):
                if forbidden in skill_metadata:
                    result.error(f"{directory}: static {forbidden} is forbidden")
        for reference in sorted(set(re.findall(r"\breferences/[A-Za-z0-9._-]+\.md", text))):
            if not (skill.parent / reference).is_file():
                result.error(f"{directory}: missing {reference}")


def validate_workflows(root: Path, result: Validation) -> None:
    """Check the shape of every workflow overlay document the bundle ships.

    These are the shape rules that make sense for a document the lifecycle owns as BYTES: it must
    be discoverable by the installer, self-declare the name it will be installed under, parse in
    the runtime shape it will be handed to, load no modules, pin no model or effort, and name no
    user-specific path. Nothing here executes a workflow or asserts that a host will accept one;
    enabling the real overlay stays a separately authorized user-configuration effect.
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


def certified_request_tuples() -> list[list[str]]:
    return [
        [model, effort, context]
        for model in CERTIFIED_MODEL_ORDER
        for context in CERTIFIED_CONTEXT_FORMS_BY_MODEL[model]
        for effort in ALLOWED_EFFORTS
    ]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json_object(path: Path, label: str) -> dict[str, object]:
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
    checkout: dict[str, object], rows: list[dict[str, object]], result: Validation
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

    if version == (0, 7, 3):
        if plane != "checkout-development":
            result.error("policy/release-contract.v1.json: 0.7.3 must remain checkout-development")
        if public_channel is not None:
            result.error("policy/release-contract.v1.json: 0.7.3 must not have a public channel")
        if certification_claim != "none":
            result.error("policy/release-contract.v1.json: 0.7.3 must not make a certification claim")
        if adr_status != "proposed":
            result.error("policy/release-contract.v1.json: 0.7.3 keeps the release-topology ADR proposed")
        if rows:
            result.error("policy/release-contract.v1.json: 0.7.3 checkout-development has no support rows")


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
        _validate_release_checkout(checkout, rows, result)
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


def _canonical_read_report_policy_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"


def _release_candidate_policy_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts) and not any(character in value for character in "*?[]")


# How far a recorded_at chain may step BACKWARDS before it is a defect rather than a clock.
#
# `recorded_at` is CLOCK_REALTIME evidence and stays that way: an operator reads it against other
# logs and against wall time, and it has to survive the reboot the receipt outlives, which a
# monotonic counter does not. The cost of that choice is that a real host's realtime clock steps
# backwards. MEASURED on the WSL2 host this repository is developed on (agentic-sdlc-184b): a
# 100-second CLOCK_REALTIME monitor observed four backwards steps of 0.22-0.53 seconds, from the
# guest's own time synchronization. Entries are recorded whole-second, so a sub-second step is
# invisible unless two appends straddle a second boundary -- and then it surfaces as a one-second
# regression, which reddened this ordering check intermittently (one observed failure, then zero in
# 60 repeats and 14 suite runs) on a check that is otherwise deterministic.
#
# 2.0 seconds is roughly four times the largest measured step, and absorbs two consecutive steps
# plus whole-second truncation, while still refusing every regression big enough to mean a
# backdated, rewritten, or forged chain rather than a clock correction. It is a tolerance, not a
# window: the comparison below carries the high-water mark forward, so a chain that slides backwards
# one tolerated second at a time still refuses once the TOTAL regression passes this bound.
#
# Deliberately NOT widened alongside it: the grant validity comparison (`issued_at`/`expires_at`
# against a supplied `now_utc`) keeps exact ordering, because that one bounds AUTHORITY in time and
# any tolerance there lengthens the window in which a grant can be used.
ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS = 2.0


def _acquisition_recorded_at_regresses(prior: datetime, current: datetime) -> bool:
    """Whether `current` sits far enough below `prior` to be a defect rather than a clock step."""
    return (prior - current).total_seconds() > ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS


def _acquisition_utc_timestamp(value: object, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ):
        errors.append(f"{label} must use strict UTC YYYY-MM-DDTHH:MM:SSZ")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        errors.append(f"{label} must use strict UTC YYYY-MM-DDTHH:MM:SSZ")
        return None


def _acquisition_record_format_error(value: object, format_name: object) -> str | None:
    if format_name == "sha256":
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            return "must be a lowercase SHA-256"
    elif format_name == "sha256_or_null":
        if value is not None and (
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        ):
            return "must be null or a lowercase SHA-256"
    elif format_name == "operation_id":
        if not isinstance(value, str) or not re.fullmatch(r"op-[0-9a-f]{32}", value):
            return "must be an op- prefix followed by 32 lowercase hex characters"
    elif format_name == "nonce":
        if (
            not isinstance(value, str)
            or not value.isascii()
            or not 32 <= len(value.encode("ascii")) <= 128
        ):
            return "must be an ASCII value from 32 through 128 bytes"
    elif format_name == "opaque_locator":
        if (
            not isinstance(value, str)
            or not value.isascii()
            or not re.fullmatch(
                r"journal:v1:op-[0-9a-f]{32}:[0-9a-f]{64}", value
            )
        ):
            return "must be a non-disclosing journal:v1 operation and digest handle"
    elif format_name == "absolute_physical_path":
        if (
            not isinstance(value, str)
            or not value.startswith("/")
            or value == "/"
            or "\\" in value
            or "\x00" in value
            or "//" in value
            or any(part in {"", ".", ".."} for part in value[1:].split("/"))
        ):
            return "must be a normalized absolute physical path"
    elif format_name != "utc_timestamp":
        return f"uses unsupported policy format {format_name!r}"
    return None


def validate_release_candidate_acquisition_record(
    kind: str,
    raw: bytes,
    policy: dict[str, object],
    *,
    now_utc: str | None = None,
    consumed_nonces: set[str] | None = None,
    effective_uid: int | None = None,
    expected_authority: dict[str, object] | None = None,
) -> list[str]:
    """Validate one canonical acquisition record against the shipped closed descriptor."""
    label = f"release-candidate acquisition {kind} record"
    errors: list[str] = []
    try:
        record = _strict_json_object(raw, label)
    except ValueError as exc:
        return [str(exc)]
    if raw != _canonical_read_report_policy_json(record).encode("ascii"):
        errors.append(f"{label} must use canonical ASCII compact JSON")

    records = policy.get("records")
    schemas = records.get("schemas") if isinstance(records, dict) else None
    schema = schemas.get(kind) if isinstance(schemas, dict) else None
    if not isinstance(schema, dict):
        errors.append(f"{label} kind is not admitted by the closed policy")
        return errors
    required = schema.get("required_keys")
    if not isinstance(required, list) or not all(isinstance(key, str) for key in required):
        errors.append(f"{label} policy required_keys descriptor is invalid")
        return errors
    expected_keys = set(required)
    missing = sorted(expected_keys - set(record))
    extra = sorted(set(record) - expected_keys)
    if missing:
        errors.append(f"{label} missing required keys: {missing}")
    if extra:
        errors.append(f"{label} has extra keys: {extra}")

    expected_version = schema.get("schema_version")
    if record.get("schema_version") != expected_version:
        errors.append(f"{label} schema_version must equal {expected_version!r}")
    constants = schema.get("constants")
    if isinstance(constants, dict):
        for field, expected in constants.items():
            if record.get(field) != expected:
                errors.append(f"{label} {field} must equal {expected!r}")

    formats = schema.get("formats")
    limits = policy.get("limits")
    max_path_bytes = limits.get("max_path_bytes") if isinstance(limits, dict) else None
    if isinstance(formats, dict):
        for field, format_name in formats.items():
            value = record.get(field)
            if format_name == "utc_timestamp":
                _acquisition_utc_timestamp(value, f"{label} {field}", errors)
                continue
            format_error = _acquisition_record_format_error(value, format_name)
            if format_error:
                errors.append(f"{label} {field} {format_error}")
            if (
                format_name == "absolute_physical_path"
                and isinstance(value, str)
                and isinstance(max_path_bytes, int)
                and len(value.encode("utf-8")) > max_path_bytes
            ):
                errors.append(
                    f"{label} {field} exceeds the policy max_path_bytes {max_path_bytes}"
                )

    types = schema.get("types")
    if isinstance(types, dict):
        for field, type_name in types.items():
            value = record.get(field)
            if type_name == "positive-integer":
                valid = isinstance(value, int) and not isinstance(value, bool) and value > 0
            elif type_name == "nonnegative-integer":
                valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
            elif type_name == "journal-entry-list":
                valid = isinstance(value, list) and all(isinstance(item, dict) for item in value)
            else:
                valid = False
            if not valid:
                errors.append(f"{label} {field} must be a {type_name}")

    archive_size = record.get("archive_size_bytes")
    max_archive_bytes = limits.get("max_archive_bytes") if isinstance(limits, dict) else None
    if (
        isinstance(archive_size, int)
        and not isinstance(archive_size, bool)
        and archive_size > 0
        and isinstance(max_archive_bytes, int)
        and not isinstance(max_archive_bytes, bool)
        and archive_size > max_archive_bytes
    ):
        errors.append(
            f"{label} archive_size_bytes exceeds max_archive_bytes {max_archive_bytes}"
        )

    vocabularies = schema.get("vocabularies")
    if isinstance(vocabularies, dict):
        for field, allowed in vocabularies.items():
            if not isinstance(allowed, list) or record.get(field) not in allowed:
                errors.append(f"{label} {field} is outside the closed vocabulary")

    if "record_sha256" in record:
        digest_input = dict(record)
        supplied_digest = digest_input.pop("record_sha256")
        expected_digest = sha256_bytes(
            _canonical_read_report_policy_json(digest_input).encode("ascii")
        )
        if supplied_digest != expected_digest:
            errors.append(f"{label} record_sha256 does not match canonical record content")

    if kind == "journal_entry":
        _validate_acquisition_journal_entry(record, policy, errors)
    elif kind == "operation_journal":
        _validate_acquisition_operation_journal(record, raw, policy, errors)
    elif kind == "assessment":
        _validate_acquisition_assessment(record, errors)
    elif kind == "exit4_diagnostic":
        _validate_acquisition_exit4_diagnostic(record, errors)

    if kind in {"apply_grant", "recover_finish_grant"}:
        if now_utc is None:
            errors.append(f"{label} grant validation requires now_utc")
        if consumed_nonces is None:
            errors.append(f"{label} grant validation requires consumed_nonces")
        if effective_uid is None:
            errors.append(f"{label} grant validation requires effective_uid")
        elif record.get("same_user_uid") != effective_uid:
            errors.append(f"{label} same_user_uid does not match effective_uid")
        authority_fields = {
            "archive_absolute_path",
            "archive_sha256",
            "archive_size_bytes",
            "decision",
            "effects_sha256",
            "operation_id",
            "original_effects",
            "plan_sha256",
            "trust_root_absolute_path",
            "trust_root_sha256",
            "xdg_data_home_absolute_path",
            "xdg_data_prestate_sha256",
            "xdg_state_home_absolute_path",
            "xdg_state_prestate_sha256",
        }
        if kind == "recover_finish_grant":
            authority_fields.update(
                {"journal_absolute_physical_path", "journal_sha256"}
            )
        if expected_authority is None or set(expected_authority) != authority_fields:
            errors.append(
                f"{label} grant validation requires the complete expected authority"
            )
        issued_errors: list[str] = []
        expires_errors: list[str] = []
        issued = _acquisition_utc_timestamp(record.get("issued_at"), "issued_at", issued_errors)
        expires = _acquisition_utc_timestamp(record.get("expires_at"), "expires_at", expires_errors)
        if issued is not None and expires is not None:
            max_ttl = limits.get("max_grant_ttl_seconds") if isinstance(limits, dict) else None
            if expires <= issued:
                errors.append(f"{label} expires_at must be after issued_at")
            elif not isinstance(max_ttl, int) or isinstance(max_ttl, bool) or max_ttl <= 0:
                errors.append(f"{label} policy max_grant_ttl_seconds is invalid")
            elif (expires - issued).total_seconds() > max_ttl:
                errors.append(f"{label} grant TTL exceeds {max_ttl} seconds")
        now_errors: list[str] = []
        now = _acquisition_utc_timestamp(now_utc, "now_utc", now_errors) if now_utc is not None else None
        errors.extend(now_errors)
        if now is not None and issued is not None and issued > now:
            errors.append(f"{label} grant is not yet valid")
        if now is not None and expires is not None and expires <= now:
            errors.append(f"{label} grant is expired")
        nonce = record.get("nonce")
        if isinstance(nonce, str) and consumed_nonces is not None and nonce in consumed_nonces:
            errors.append(f"{label} grant nonce was already consumed")

    if expected_authority is not None:
        for field, expected in expected_authority.items():
            if record.get(field) != expected:
                errors.append(f"{label} {field} does not match expected authority")
    return errors


def _validate_acquisition_journal_entry(
    entry: dict[str, object],
    policy: dict[str, object],
    errors: list[str],
) -> None:
    label = "release-candidate acquisition journal_entry record"
    records = policy.get("records")
    effect_rules = (
        records.get("effect_state_rules") if isinstance(records, dict) else None
    )
    effect_state_by_phase = (
        effect_rules.get("journal_effect_state_by_phase")
        if isinstance(effect_rules, dict)
        else None
    )
    if not isinstance(effect_state_by_phase, dict):
        errors.append(f"{label} policy phase/effect descriptor is invalid")
        return
    phase = entry.get("phase")
    expected_effect_state = effect_state_by_phase.get(phase)
    if (
        isinstance(expected_effect_state, str)
        and entry.get("effect_state") != expected_effect_state
    ):
        errors.append(
            f"{label} effect_state must equal {expected_effect_state!r} "
            f"for phase {phase!r}"
        )


def _validate_acquisition_operation_journal(
    journal: dict[str, object],
    raw: bytes,
    policy: dict[str, object],
    errors: list[str],
) -> None:
    label = "release-candidate acquisition operation_journal record"
    limits = policy.get("limits")
    max_journal_bytes = limits.get("max_journal_bytes") if isinstance(limits, dict) else None
    if isinstance(max_journal_bytes, int) and len(raw) > max_journal_bytes:
        errors.append(f"{label} operation_journal exceeds max_journal_bytes {max_journal_bytes}")

    entries = journal.get("entries")
    if not isinstance(entries, list):
        return
    phases = ["opened", "pinned", "staged", "published", "receipted", "installed-unselected"]
    if not entries:
        errors.append(f"{label} operation journal requires genesis entry at sequence 0")
        return
    first = entries[0]
    if (
        not isinstance(first, dict)
        or first.get("sequence") != 0
        or first.get("phase") != "opened"
        or first.get("previous_entry_sha256") is not None
    ):
        errors.append(f"{label} operation journal requires genesis entry at sequence 0")
    if len(entries) > len(phases):
        errors.append(f"{label} contains more entries than the closed phase sequence")

    identity_fields = (
        "operation_id",
        "plan_sha256",
        "effects_sha256",
        "allowed_effects",
    )
    archive_fields = (
        "archive_absolute_path",
        "archive_sha256",
        "archive_size_bytes",
    )
    prior_entry: dict[str, object] | None = None
    prior_time: datetime | None = None
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_raw = _canonical_read_report_policy_json(entry).encode("ascii")
        for nested_error in validate_release_candidate_acquisition_record(
            "journal_entry", entry_raw, policy
        ):
            errors.append(f"{label} entry {index}: {nested_error}")

        if entry.get("sequence") != index:
            errors.append(f"{label} entry {index} sequence must equal {index}")
        if index < len(phases) and entry.get("phase") != phases[index]:
            errors.append(f"{label} entry {index} phase must equal {phases[index]!r}")
        if index == 0:
            if entry.get("previous_entry_sha256") is not None:
                errors.append(f"{label} genesis predecessor must be null")
        elif prior_entry is not None:
            expected_predecessor = sha256_bytes(
                _canonical_read_report_policy_json(prior_entry).encode("ascii")
            )
            if entry.get("previous_entry_sha256") != expected_predecessor:
                errors.append(
                    f"{label} entry {index} previous_entry_sha256 does not match exact preceding entry bytes"
                )

        for field in identity_fields:
            if entry.get(field) != journal.get(field):
                errors.append(f"{label} entry {index} {field} must equal journal {field}")
        if any(entry.get(field) != journal.get(field) for field in archive_fields):
            errors.append(
                f"{label} entry {index} archive identity must equal journal archive identity"
            )

        timestamp_errors: list[str] = []
        timestamp = _acquisition_utc_timestamp(
            entry.get("recorded_at"), f"entry {index} recorded_at", timestamp_errors
        )
        # A bounded backwards step is tolerated because the recording clock really does step back
        # (see ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS for the measurement); a larger
        # regression is still refused. The comparison is against the HIGH-WATER mark rather than the
        # immediate predecessor, so the tolerance bounds the total regression across the chain
        # instead of being re-granted at every entry.
        if (
            timestamp is not None
            and prior_time is not None
            and _acquisition_recorded_at_regresses(prior_time, timestamp)
        ):
            errors.append(
                f"{label} entry {index} recorded_at regresses more than "
                f"{ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS}s below the preceding entries"
            )
        if timestamp is not None:
            prior_time = timestamp if prior_time is None else max(prior_time, timestamp)
        prior_entry = entry


def _validate_acquisition_assessment(
    assessment: dict[str, object], errors: list[str]
) -> None:
    label = "release-candidate acquisition assessment record"
    exact_by_phase = {
        "absent": "none",
        "opened": "partial",
        "pinned": "partial",
        "staged": "partial",
        "published": "partial",
        "receipted": "partial",
        "installed-unselected": "complete",
    }
    classification = assessment.get("classification")
    phase = assessment.get("last_proven_phase")
    effect_state = assessment.get("effect_state")
    if classification == "exact":
        expected = exact_by_phase.get(phase)
        if expected is not None and effect_state != expected:
            errors.append(
                f"{label} effect_state must equal {expected!r} for exact phase {phase!r}"
            )
    elif classification == "unavailable":
        if effect_state != "unknown":
            errors.append(
                f"{label} unavailable classification must use effect_state 'unknown'"
            )
        if phase == "installed-unselected":
            errors.append(f"{label} unavailable classification cannot claim terminal phase")


def _validate_acquisition_exit4_diagnostic(
    diagnostic: dict[str, object], errors: list[str]
) -> None:
    label = "release-candidate acquisition exit4_diagnostic record"
    preterminal = {"opened", "pinned", "staged", "published", "receipted"}
    classification = diagnostic.get("classification")
    effect_state = diagnostic.get("effect_state")
    phase = diagnostic.get("last_proven_phase")
    if effect_state not in {"partial", "unknown"}:
        errors.append(f"{label} effect_state must be partial or unknown")
        return
    if effect_state == "partial":
        if classification != "exact":
            errors.append(f"{label} partial requires classification 'exact'")
        if phase not in preterminal:
            errors.append(
                f"{label} partial requires an exact preterminal last_proven_phase"
            )
    else:
        if classification != "unavailable":
            errors.append(f"{label} unknown requires classification 'unavailable'")
        if phase == "installed-unselected":
            errors.append(f"{label} unknown classification cannot claim terminal phase")


def _acquisition_record_schema(
    schema_version: str,
    required_keys: list[str],
    formats: dict[str, str],
    *,
    constants: dict[str, object] | None = None,
    types: dict[str, str] | None = None,
    vocabularies: dict[str, object] | None = None,
) -> dict[str, object]:
    schema: dict[str, object] = {
        "constants": constants or {},
        "formats": formats,
        "required_keys": required_keys,
        "schema_version": schema_version,
        "types": types or {},
    }
    if vocabularies is not None:
        schema["vocabularies"] = vocabularies
    return schema


def _expected_acquisition_record_contract() -> dict[str, object]:
    effects = [
        "xdg-data-candidate-publish",
        "xdg-data-candidate-stage",
        "xdg-state-grant-consumption",
        "xdg-state-journal",
        "xdg-state-receipt",
        "xdg-state-writer-lock",
    ]
    phases = ["opened", "pinned", "staged", "published", "receipted"]
    next_actions = [
        [
            "acquire", "recover", "inspect", "--xdg-state-home",
            "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>",
        ],
        [
            "acquire", "recover", "finish", "--xdg-state-home",
            "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>",
            "--grant", "<absolute-grant>",
        ],
    ]
    common_grant_formats = {
        "archive_absolute_path": "absolute_physical_path",
        "archive_sha256": "sha256",
        "effects_sha256": "sha256",
        "expires_at": "utc_timestamp",
        "issued_at": "utc_timestamp",
        "nonce": "nonce",
        "operation_id": "operation_id",
        "plan_sha256": "sha256",
        "record_sha256": "sha256",
        "trust_root_absolute_path": "absolute_physical_path",
        "trust_root_sha256": "sha256",
        "xdg_data_home_absolute_path": "absolute_physical_path",
        "xdg_data_prestate_sha256": "sha256",
        "xdg_state_home_absolute_path": "absolute_physical_path",
        "xdg_state_prestate_sha256": "sha256",
    }
    common_grant_keys = [
        "archive_absolute_path",
        "archive_sha256",
        "archive_size_bytes",
        "decision",
        "effects_sha256",
        "expires_at",
        "issued_at",
        "nonce",
        "operation_id",
        "original_effects",
        "plan_sha256",
        "record_sha256",
        "same_user_uid",
        "schema_version",
        "trust_root_absolute_path",
        "trust_root_sha256",
        "xdg_data_home_absolute_path",
        "xdg_data_prestate_sha256",
        "xdg_state_home_absolute_path",
        "xdg_state_prestate_sha256",
    ]
    schemas = {
        "acquisition_plan": _acquisition_record_schema(
            "release-candidate-acquisition-plan/v1",
            [
                "archive_absolute_path", "archive_sha256", "archive_size_bytes", "created_at",
                "effects_sha256", "planned_effects", "record_sha256", "schema_version",
                "trust_root_absolute_path", "trust_root_sha256",
                "xdg_data_home_absolute_path", "xdg_data_prestate_sha256",
                "xdg_state_home_absolute_path", "xdg_state_prestate_sha256",
            ],
            {
                "archive_absolute_path": "absolute_physical_path",
                "archive_sha256": "sha256",
                "created_at": "utc_timestamp",
                "effects_sha256": "sha256",
                "record_sha256": "sha256",
                "trust_root_absolute_path": "absolute_physical_path",
                "trust_root_sha256": "sha256",
                "xdg_data_home_absolute_path": "absolute_physical_path",
                "xdg_data_prestate_sha256": "sha256",
                "xdg_state_home_absolute_path": "absolute_physical_path",
                "xdg_state_prestate_sha256": "sha256",
            },
            constants={"planned_effects": effects},
            types={"archive_size_bytes": "positive-integer"},
        ),
        "apply_grant": _acquisition_record_schema(
            "release-candidate-acquisition-apply-grant/v1",
            common_grant_keys,
            common_grant_formats,
            constants={"decision": "apply", "original_effects": effects},
            types={
                "archive_size_bytes": "positive-integer",
                "same_user_uid": "nonnegative-integer",
            },
        ),
        "assessment": _acquisition_record_schema(
            "release-candidate-acquisition-assessment/v1",
            [
                "assessment_kind", "classification", "effect_state", "journal_locator",
                "last_proven_phase", "next_action", "operation_id", "record_sha256",
                "schema_version",
            ],
            {
                "journal_locator": "opaque_locator",
                "operation_id": "operation_id",
                "record_sha256": "sha256",
            },
            vocabularies={
                "assessment_kind": ["inspect", "recover-inspect"],
                "classification": ["exact", "unavailable"],
                "effect_state": ["none", "partial", "unknown", "complete"],
                "last_proven_phase": ["absent", *phases, "installed-unselected"],
                "next_action": next_actions,
            },
        ),
        "exit4_diagnostic": _acquisition_record_schema(
            "release-candidate-acquisition-exit4-diagnostic/v1",
            [
                "classification", "effect_state", "journal_locator", "last_proven_phase",
                "next_action", "operation_id", "record_sha256", "schema_version",
            ],
            {
                "journal_locator": "opaque_locator",
                "operation_id": "operation_id",
                "record_sha256": "sha256",
            },
            vocabularies={
                "classification": ["exact", "unavailable"],
                "effect_state": ["partial", "unknown"],
                "last_proven_phase": ["absent", *phases, "installed-unselected"],
                "next_action": next_actions,
            },
        ),
        "immutable_receipt": _acquisition_record_schema(
            "release-candidate-acquisition-receipt/v1",
            [
                "activation", "archive_sha256", "candidate_root_absolute_physical_path",
                "effect_state", "installed_at", "journal_sha256", "operation_id",
                "plan_sha256", "public_channel", "record_sha256", "release_claim",
                "schema_version", "selection", "support", "terminal_phase",
            ],
            {
                "archive_sha256": "sha256",
                "candidate_root_absolute_physical_path": "absolute_physical_path",
                "installed_at": "utc_timestamp",
                "journal_sha256": "sha256",
                "operation_id": "operation_id",
                "plan_sha256": "sha256",
                "record_sha256": "sha256",
            },
            constants={
                "activation": "absent",
                "effect_state": "complete",
                "public_channel": None,
                "release_claim": "none",
                "selection": "absent",
                "support": "unsupported",
                "terminal_phase": "installed-unselected",
            },
        ),
        "journal_entry": _acquisition_record_schema(
            "release-candidate-acquisition-journal-entry/v1",
            [
                "allowed_effects", "archive_absolute_path", "archive_sha256",
                "archive_size_bytes", "candidate_root_sha256", "effect_state",
                "effects_sha256", "interpreter_relative_path", "interpreter_sha256",
                "operation_id", "phase", "plan_sha256", "previous_entry_sha256",
                "record_sha256", "recorded_at", "schema_version", "sequence",
            ],
            {
                "archive_absolute_path": "absolute_physical_path",
                "archive_sha256": "sha256",
                "candidate_root_sha256": "sha256",
                "effects_sha256": "sha256",
                "interpreter_sha256": "sha256",
                "operation_id": "operation_id",
                "plan_sha256": "sha256",
                "previous_entry_sha256": "sha256_or_null",
                "record_sha256": "sha256",
                "recorded_at": "utc_timestamp",
            },
            constants={
                "allowed_effects": effects,
                "interpreter_relative_path": "runtime/python/bin/python3.12",
            },
            types={
                "archive_size_bytes": "positive-integer",
                "sequence": "nonnegative-integer",
            },
            vocabularies={
                "effect_state": ["partial", "complete"],
                "phase": [*phases, "installed-unselected"],
            },
        ),
        "operation_journal": _acquisition_record_schema(
            "release-candidate-acquisition-operation-journal/v1",
            [
                "allowed_effects", "archive_absolute_path", "archive_sha256",
                "archive_size_bytes", "effects_sha256", "entries", "operation_id",
                "plan_sha256", "record_sha256", "schema_version",
            ],
            {
                "archive_absolute_path": "absolute_physical_path",
                "archive_sha256": "sha256",
                "effects_sha256": "sha256",
                "operation_id": "operation_id",
                "plan_sha256": "sha256",
                "record_sha256": "sha256",
            },
            constants={"allowed_effects": effects},
            types={
                "archive_size_bytes": "positive-integer",
                "entries": "journal-entry-list",
            },
        ),
        "recover_finish_grant": _acquisition_record_schema(
            "release-candidate-acquisition-recover-finish-grant/v1",
            [
                *common_grant_keys[:7],
                "journal_absolute_physical_path",
                "journal_sha256",
                *common_grant_keys[7:],
            ],
            {
                **common_grant_formats,
                "journal_absolute_physical_path": "absolute_physical_path",
                "journal_sha256": "sha256",
            },
            constants={"decision": "finish", "original_effects": effects},
            types={
                "archive_size_bytes": "positive-integer",
                "same_user_uid": "nonnegative-integer",
            },
        ),
    }
    return {
        "canonical_json": "policy-canonical-json",
        "digest": {
            "algorithm": "sha256",
            "covers": "canonical-record-with-record_sha256-omitted",
            "field": "record_sha256",
        },
        "effect_state_rules": {
            "assessment": {
                "exact_by_phase": {
                    "absent": "none",
                    "installed-unselected": "complete",
                    "opened": "partial",
                    "pinned": "partial",
                    "published": "partial",
                    "receipted": "partial",
                    "staged": "partial",
                },
                "unavailable": {
                    "effect_state": "unknown",
                    "forbidden_last_proven_phases": ["installed-unselected"],
                },
            },
            "classification_vocabulary": ["exact", "unavailable"],
            "exit4": {
                "allowed_effect_states": ["partial", "unknown"],
                "partial": {
                    "classification": "exact",
                    "last_proven_phases": phases,
                },
                "unknown": {
                    "classification": "unavailable",
                    "forbidden_last_proven_phases": ["installed-unselected"],
                },
            },
            "journal_effect_state_by_phase": {
                "installed-unselected": "complete",
                "opened": "partial",
                "pinned": "partial",
                "published": "partial",
                "receipted": "partial",
                "staged": "partial",
            },
            "none_scope": "pre-journal-absent-assessment-only",
            "unknown_scope": "assessment-or-exit4-with-unavailable-classification-only",
        },
        "field_formats": {
            "absolute_physical_path": "absolute-no-dot-segments-runtime-no-symlink",
            "nonce": "ascii-32-to-128-bytes",
            "opaque_locator": "journal-v1-operation-id-and-sha256",
            "operation_id": "op-lowerhex-32",
            "sha256": "lowerhex-64",
            "sha256_or_null": "lowerhex-64-or-null-genesis-only",
            "utc_timestamp": "YYYY-MM-DDTHH:MM:SSZ",
        },
        "journal_binding": {
            "grant_fields": [
                "operation_id",
                "journal_absolute_physical_path",
                "journal_sha256",
            ],
            "journal_sha256": "sha256-of-exact-canonical-operation-journal-bytes",
            "recovery_decision": "finish",
        },
        "journal_rules": {
            "aggregate_limit": "limits.max_journal_bytes",
            "entry_bytes": "canonical-json-with-trailing-newline",
            "genesis": {
                "phase": "opened",
                "previous_entry_sha256": None,
                "sequence": 0,
            },
            "identity_fields": [
                "operation_id",
                "archive_absolute_path",
                "archive_sha256",
                "archive_size_bytes",
                "plan_sha256",
                "effects_sha256",
                "allowed_effects",
            ],
            "pending_prefixes_allowed": True,
            "phase_prefix": [*phases, "installed-unselected"],
            "predecessor_digest": "sha256-of-exact-canonical-preceding-entry-bytes",
            "sequence": "zero-based-contiguous",
            # Built from the tolerance constant rather than typed as a literal, so retuning the
            # tolerance cannot leave the shipped policy asserting a bound the validator no longer
            # enforces: the retune fails this equality first, and the policy has to be re-agreed
            # (and re-digested) deliberately. It said "strict-utc-nondecreasing" until
            # agentic-sdlc-184b, and a real clock made that claim false rather than strict.
            "timestamp_order": (
                "utc-nondecreasing-within-"
                f"{ACQUISITION_RECORDED_AT_BACKWARD_TOLERANCE_SECONDS}s-backward-clock-tolerance"
            ),
        },
        "no_extra_fields": True,
        "schemas": schemas,
    }


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
    expected_top = {"archive", "canonical_json", "disclosures", "limits", "manifest", "payload", "runtime", "schema_version"}
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
    if policy.get("archive") != {"prefix": "agentic-sdlc-candidate-", "suffix": "-linux-x64.tar.gz"}:
        result.error(f"{relative}: archive naming contract mismatch")
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
            required_trees = {"agents", "assets", "commands", "policy", "scripts", "skills", "workflows"}
            if not required_files.issubset(files) or not required_trees.issubset(trees):
                result.error(f"{relative}: minimal authored payload roots are missing")

    runtime = policy.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {"destination", "license_paths", "python_executable", "python_version"}:
        result.error(f"{relative}: runtime descriptor is invalid")
    elif (
        runtime.get("destination") != "runtime/python"
        or runtime.get("python_executable") != "bin/python3.12"
        or runtime.get("python_version") != PYTHON_VERSION
        or not isinstance(runtime.get("license_paths"), list)
        or not runtime["license_paths"]
        or runtime["license_paths"] != sorted(runtime["license_paths"])
        or not all(_release_candidate_policy_path(value) for value in runtime["license_paths"])
    ):
        result.error(f"{relative}: private Python runtime contract is invalid")


def validate_release_candidate_acquisition_policy(root: Path, result: Validation) -> None:
    """Admit one exact, closed developer-only candidate acquisition contract."""
    relative = RELEASE_CANDIDATE_ACQUISITION_POLICY_RELATIVE_PATH
    path = root / relative
    if path.is_symlink() or not path.is_file():
        result.error(f"{relative}: required candidate acquisition policy is missing or linked")
        return
    try:
        raw = path.read_bytes()
        policy = _strict_json_object(raw, str(relative))
    except (OSError, ValueError) as exc:
        result.error(str(exc))
        return

    if raw != _canonical_read_report_policy_json(policy).encode("ascii"):
        result.error(f"{relative}: policy must use canonical ASCII compact JSON")

    expected_top = {
        "admission",
        "authority",
        "canonical_json",
        "commands",
        "disclosures",
        "effects",
        "exit_codes",
        "filesystem",
        "grant",
        "limits",
        "platform",
        "preservation",
        "records",
        "recovery",
        "redaction",
        "schema_version",
        "state_machine",
    }
    if set(policy) != expected_top:
        result.error(f"{relative}: closed top-level schema mismatch")
    if policy.get("schema_version") != RELEASE_CANDIDATE_ACQUISITION_POLICY_SCHEMA:
        result.error(f"{relative}: acquisition schema version mismatch")
    if policy.get("canonical_json") != {
        "allow_nonfinite": False,
        "ensure_ascii": True,
        "separators": [",", ":"],
        "sort_keys": True,
        "trailing_newline": True,
    }:
        result.error(f"{relative}: canonical JSON descriptor mismatch")

    expected_sections: dict[str, object] = {
        "admission": {
            "archive_identity": ["absolute_path", "sha256", "size_bytes"],
            "artifact_kind": "unpublished-candidate",
            "external_admission_required": True,
            "manifest_schema": "release-candidate/v1",
            "tool_self_authenticates": False,
            "trust_root_identity": ["absolute_path", "sha256"],
        },
        "authority": {
            "allowed_effects": [
                "xdg-data-candidate-publish",
                "xdg-data-candidate-stage",
                "xdg-state-grant-consumption",
                "xdg-state-journal",
                "xdg-state-receipt",
                "xdg-state-writer-lock",
            ],
            "forbidden_effects": [
                "activation",
                "credential-read",
                "credential-write",
                "gateway",
                "git",
                "host-configuration",
                "mise-global",
                "network",
                "path-environment",
                "provider",
                "publication",
                "pull-request",
                "push",
                "release",
                "repository",
                "seeds",
                "selection",
                "tag",
                "trust-mutation",
            ],
            "outward_effect_authority": "none",
            "repository_and_trust_root_access": "read-only",
        },
        "commands": [
            {
                "argv": [
                    "acquire", "plan", "--archive", "<absolute-archive>",
                    "--trust-root", "<absolute-trust-root>",
                    "--xdg-data-home", "<absolute-xdg-data-home>",
                    "--xdg-state-home", "<absolute-xdg-state-home>",
                ],
                "effects": "none",
                "grant": "forbidden",
                "name": "plan",
                "read_only": True,
            },
            {
                "argv": ["acquire", "inspect", "--plan", "<absolute-plan>"],
                "effects": "none",
                "grant": "forbidden",
                "name": "inspect",
                "read_only": True,
            },
            {
                "argv": [
                    "acquire", "apply", "--plan", "<absolute-plan>",
                    "--grant", "<absolute-grant>",
                ],
                "effects": "candidate-install",
                "grant": "required",
                "name": "apply",
                "read_only": False,
            },
            {
                "argv": [
                    "acquire", "recover", "inspect", "--xdg-state-home",
                    "<absolute-xdg-state-home>", "--journal-locator",
                    "<journal-locator>",
                ],
                "effects": "none",
                "grant": "forbidden",
                "name": "recover-inspect",
                "read_only": True,
            },
            {
                "argv": [
                    "acquire", "recover", "finish", "--xdg-state-home",
                    "<absolute-xdg-state-home>", "--journal-locator",
                    "<journal-locator>",
                    "--grant", "<absolute-grant>",
                ],
                "effects": "finish-candidate-install",
                "grant": "required",
                "name": "recover-finish",
                "read_only": False,
            },
        ],
        "disclosures": {
            "activation": "absent",
            "licensing": "incomplete",
            "provenance": "unverified",
            "public_channel": None,
            "release_claim": "none",
            "sbom": "absent",
            "selection": "absent",
            "support": "unsupported",
        },
        "effects": {
            "candidate_data_effects_begin_at": "staged",
            "durable_phase_advances": True,
            "exit_routing": {
                "clean_refusal_before_journal_or_product_effect": 3,
                "internal_incomplete_after_journal": 4,
                "unexpected_internal_before_admitted_effect": 1,
            },
            "immutable_receipt": True,
            "first_namespace_effect": "grant-bound-opened-bootstrap",
            "journal_before_candidate_data": True,
            "journal_open_phase": "opened",
            "no_replace_publication": ["stage", "final", "receipt"],
            "partial_or_unknown_exit": 4,
            "recovery_first_new_namespace_effect": "grant-consumption-marker",
            "serialized_writer_count": 1,
            "serialized_writers": ["apply", "recover-finish"],
        },
        "exit_codes": {
            "0": "success-query-or-exact-no-effect",
            "1": "unexpected-internal-failure-before-admitted-effect",
            "2": "grammar-schema-or-invalid-input",
            "3": "clean-refusal-before-journal-or-product-effect",
            "4": "admitted-partial-or-unknown-effect",
        },
        "filesystem": {
            "directory_mode": "0700",
            "file_mode": "0600",
            "implicit_environment_defaults": False,
            "layout": {
                "candidate_root": "$XDG_DATA_HOME/agentic-sdlc/acquisition/candidates/<archive-sha256>/root",
                "candidate_stage": "$XDG_DATA_HOME/agentic-sdlc/acquisition/staging/<operation-id>",
                "data_root": "$XDG_DATA_HOME/agentic-sdlc/acquisition",
                "grant_consumption": "$XDG_STATE_HOME/.agentic-sdlc-acquisition-v1-<operation-id>-<grant-sha256>-<nonce-sha256>.opened.json",
                "journal": "$XDG_STATE_HOME/agentic-sdlc/acquisition/journals/<operation-id>.json",
                "receipt": "$XDG_STATE_HOME/agentic-sdlc/acquisition/receipts/<archive-sha256>.json",
                "recovery_grant_consumption": "$XDG_STATE_HOME/.agentic-sdlc-acquisition-recovery-v1-<operation-id>-<grant-sha256>-<nonce-sha256>.used",
                "state_root": "$XDG_STATE_HOME/agentic-sdlc/acquisition",
                "writer_lock": "existing-explicit-xdg-state-home-directory-fd",
            },
            "physical_path_policy": "no-symlink-components",
            "root_arguments": "explicit-absolute-only",
        },
        "grant": {
            "approval_authenticated": False,
            "bound_fields": {
                "apply": [
                    "decision", "operation_id", "plan_sha256", "archive.absolute_path",
                    "archive.sha256", "archive.size_bytes", "trust_root.absolute_path",
                    "trust_root.sha256", "xdg_data_home.absolute_path",
                    "xdg_data_home.prestate_sha256", "xdg_state_home.absolute_path",
                    "xdg_state_home.prestate_sha256", "effects.sha256",
                    "original_allowed_effects", "same_user_uid", "issued_at", "expires_at",
                    "nonce",
                ],
                "recover-finish": [
                    "decision", "operation_id", "journal.absolute_physical_path",
                    "journal.sha256", "plan_sha256", "archive.absolute_path",
                    "archive.sha256", "archive.size_bytes", "trust_root.absolute_path",
                    "trust_root.sha256", "xdg_data_home.absolute_path",
                    "xdg_data_home.prestate_sha256", "xdg_state_home.absolute_path",
                    "xdg_state_home.prestate_sha256", "effects.sha256",
                    "original_allowed_effects", "same_user_uid", "issued_at", "expires_at",
                    "nonce",
                ],
            },
            "expiring": True,
            "kind": "procedural-effect-grant",
            "minted_by_tool": False,
            "required_by": ["apply", "recover-finish"],
            "same_user": True,
            "single_use": True,
            "timestamp_format": "YYYY-MM-DDTHH:MM:SSZ",
            "runtime_checks": [
                "strict-utc-timestamps",
                "expires-after-issued",
                "ttl-at-most-policy-limit",
                "issued-not-in-future",
                "not-expired-at-use",
                "nonce-not-consumed",
                "consume-nonce-no-replace-before-effects",
                "same-effective-uid",
                "exact-authority-match",
            ],
        },
        "limits": {
            "max_archive_bytes": 134217728,
            "max_candidates_per_apply": 1,
            "max_entries": 10000,
            "max_extracted_bytes": 268435456,
            "max_file_bytes": 67108864,
            "max_grant_bytes": 65536,
            "max_grant_ttl_seconds": 900,
            "max_journal_bytes": 1048576,
            "max_path_bytes": 1024,
            "max_plan_bytes": 1048576,
            "max_receipt_bytes": 1048576,
            "max_recovery_journals_per_inspect": 10000,
            "max_writer_count": 1,
        },
        "platform": {
            "architecture": "x86_64",
            "certification": "linux-x64-only",
            "operating_system": "linux",
            "other_platforms": "refused",
            "purpose": "developer-only",
        },
        "preservation": {
            "action": "preserve-and-refuse",
            "delete": False,
            "preserved_states": ["foreign", "modified", "racy", "unsupported", "unknown"],
        },
        "records": _expected_acquisition_record_contract(),
        "recovery": {
            "delete": False,
            "finish_only": True,
            "grant_required_for_finish": True,
            "inspect_read_only": True,
            "journal_required": True,
            "original_effects_only": True,
            "private_python": {
                "arguments": ["-I", "-B"],
                "execution_root": "acquired-root",
                "interpreter_journal_pins": [
                    "candidate_root_sha256",
                    "interpreter_relative_path",
                    "interpreter_sha256",
                ],
                "relative_path": "runtime/python/bin/python3.12",
                "requires_existing_journal_pin": True,
                "role": "acquired-root-continuity-evidence",
                "self_authentication": False,
                "source_checkout": "unavailable-and-not-required",
            },
            "rollback": False,
        },
        "redaction": {
            "allowed_output": [
                "action", "archive-sha256", "effect-state", "exit-code",
                "journal-locator", "operation-id", "receipt-locator",
            ],
            "forbidden_output": [
                "archive-path", "credential", "environment", "file-contents", "grant-body",
                "trust-root-path", "xdg-data-home", "xdg-state-home",
            ],
            "retained_evidence": "content-minimized-identities-and-state",
        },
        "state_machine": {
            "exact_rerun": "success-no-effect",
            "exit_code_4_states": ["partial", "unknown"],
            "mismatched_rerun": "safe-refusal-preserve",
            "phases": [
                "absent", "opened", "pinned", "staged", "published", "receipted",
                "installed-unselected",
            ],
            "terminal": "installed-unselected",
            "transitions": [
                ["absent", "opened"],
                ["opened", "pinned"],
                ["pinned", "staged"],
                ["staged", "published"],
                ["published", "receipted"],
                ["receipted", "installed-unselected"],
            ],
        },
    }
    for section, expected in expected_sections.items():
        if policy.get(section) != expected:
            result.error(f"{relative}: closed {section} contract mismatch")

    if sha256_bytes(raw) != RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256:
        result.error(f"{relative}: exact acquisition policy digest mismatch")


def validate_ccodex_sdlc_read_report_policy(root: Path, result: Validation) -> None:
    """Keep the checkout-development reader's closed semantic report descriptor deterministic."""
    relative = CCODEX_SDLC_READ_REPORT_POLICY_RELATIVE_PATH
    path = root / relative
    if path.is_symlink() or not path.is_file():
        result.error(f"{relative}: required canonical read-report policy is missing or linked")
        return
    try:
        raw = path.read_bytes()
        policy = _strict_json_object(raw, str(relative))
    except (OSError, ValueError) as exc:
        result.error(str(exc))
        return
    if raw != _canonical_read_report_policy_json(policy).encode("utf-8"):
        result.error(f"{relative}: policy must use canonical JSON")
    expected = {
        "canonical_serialization": {
            "allow_nonfinite": False,
            "ensure_ascii": True,
            "indent": None,
            "separators": [",", ":"],
            "sort_keys": True,
            "trailing_newline": True,
        },
        "field_vocabularies": CCODEX_SDLC_READ_REPORT_FIELDS,
        "report_schema_version": CCODEX_SDLC_READ_REPORT_SCHEMA,
        "report_top_level_fields": CCODEX_SDLC_READ_REPORT_TOP_LEVEL_FIELDS,
        "schema_version": CCODEX_SDLC_READ_REPORT_POLICY_SCHEMA,
        "vocabularies": CCODEX_SDLC_READ_REPORT_VOCABULARIES,
    }
    if policy != expected:
        result.error(f"{relative}: closed schema/vocabulary descriptor differs from the read-report contract")


def validate_release_candidate_execution_policy(root: Path, result: Validation) -> None:
    """Bind executable-candidate admission to one closed external policy."""
    relative = RELEASE_CANDIDATE_EXECUTION_POLICY_RELATIVE_PATH
    path = root / relative
    if path.is_symlink() or not path.is_file():
        result.error(f"{relative}: required candidate execution policy is missing or linked")
        return
    try:
        raw = path.read_bytes()
        policy = _strict_json_object(raw, str(relative))
    except (OSError, ValueError) as exc:
        result.error(str(exc))
        return
    if raw != _canonical_read_report_policy_json(policy).encode("ascii"):
        result.error(f"{relative}: policy must use canonical ASCII compact JSON")
    expected = {
        "admission": {
            "authenticated_files": [
                "assets/launchers/ccodex.in",
                "policy/ccodex-sdlc-read-report.v2.json",
                "policy/release-candidate-execution.v1.json",
                "policy/release-candidate.v1.json",
                "scripts/ccodex_sdlc.py",
                "scripts/ccodex_sdlc_readonly.py",
                "scripts/install_operator_tools.py",
                "scripts/install_skill_bundle.py",
            ],
            "schema_version": "release-candidate-execution-admission/v1",
        },
        "commands": [
            ["sdlc", "doctor"], ["sdlc", "doctor", "--json"],
            ["sdlc", "inspect"], ["sdlc", "inspect", "--json"],
            ["sdlc", "recover", "--dry-run"], ["sdlc", "recover", "--dry-run", "--json"],
            ["sdlc", "status"], ["sdlc", "status", "--json"],
        ],
        "limits": {
            "max_child_output_bytes": 1048576,
            "max_child_stderr_bytes": 65536,
            "max_seconds": 30,
            "terminate_grace_seconds": 3,
        },
        "platform": "linux-x64",
        "projection": {"dispatcher": "bin/ccodex", "template": "assets/launchers/ccodex.in"},
        "schema_version": "release-candidate-execution-policy/v1",
        "trusted_bash": {
            "path": "/usr/bin/bash",
            "sha256": "bc5945feb8bd26203ebfafea5ce1878bb2e32cb8fb50ab7ae395cfb1e1aaaef1",
        },
    }
    if policy != expected:
        result.error(f"{relative}: closed execution policy differs from the candidate bridge contract")


def validate_ccodex_sdlc_candidate_report_policy(root: Path, result: Validation) -> None:
    """Keep the ephemeral candidate-only v2 report schema closed and explicit."""
    relative = CCODEX_SDLC_CANDIDATE_REPORT_POLICY_RELATIVE_PATH
    path = root / relative
    if path.is_symlink() or not path.is_file():
        result.error(f"{relative}: required candidate read-report policy is missing or linked")
        return
    try:
        raw = path.read_bytes()
        policy = _strict_json_object(raw, str(relative))
    except (OSError, ValueError) as exc:
        result.error(str(exc))
        return
    if raw != _canonical_read_report_policy_json(policy).encode("utf-8"):
        result.error(f"{relative}: policy must use canonical JSON")
    if hashlib.sha256(raw).hexdigest() != CCODEX_SDLC_CANDIDATE_REPORT_POLICY_SHA256:
        result.error(f"{relative}: exact closed schema/vocabulary descriptor differs from the candidate report contract")


def runtime_receipt_policy() -> dict[str, object]:
    return load_json_object(RECEIPT_POLICY_PATH, "runtime receipt policy")


def normative_runtime_contract() -> dict[str, object]:
    return load_json_object(NORMATIVE_CONTRACT_PATH, "normative runtime contract")


def validate_runtime_policy_contract(root: Path, result: Validation) -> None:
    try:
        policy = runtime_receipt_policy()
        normative = normative_runtime_contract()
    except ValueError as exc:
        result.error(str(exc))
        return

    policy_path = RECEIPT_POLICY_PATH
    if normative.get("schema_version") != "runtime-assignment-normative-contract/v1":
        result.error("normative runtime contract schema_version mismatch")
    expected_values = {
        "canonical_receipt_fields": list(runtime_receipt_fields()),
        "exact_model_provider_map": EXACT_MODEL_PROVIDER_MAP,
        "exact_model_pairs": EXACT_MODEL_PAIRS,
        "allowed_efforts": ALLOWED_EFFORTS,
        "allowed_context_forms": ALLOWED_CONTEXT_FORMS,
        "allowed_evidence": ALLOWED_EVIDENCE,
        "certified_context_forms_by_model": CERTIFIED_CONTEXT_FORMS_BY_MODEL,
        "production_efforts_by_model": PRODUCTION_EFFORTS_BY_MODEL,
        "validation_only_semantics": VALIDATION_ONLY_SEMANTICS,
        "one_million_context_semantics": ONE_MILLION_CONTEXT_SEMANTICS,
        "seeds_read_only_semantics": SEEDS_READ_ONLY_SEMANTICS,
    }
    for field, expected in expected_values.items():
        if normative.get(field) != expected:
            result.error(f"normative runtime contract {field} mismatch")

    if policy.get("allowed_exact_model_ids") != EXACT_MODEL_PROVIDER_MAP:
        result.error("runtime receipt policy exact model/provider map mismatch")
    if policy.get("allowed_efforts") != ALLOWED_EFFORTS:
        result.error("runtime receipt policy effort vocabulary mismatch")
    if policy.get("allowed_context_forms") != ALLOWED_CONTEXT_FORMS:
        result.error("runtime receipt policy context vocabulary mismatch")
    if policy.get("allowed_evidence") != ALLOWED_EVIDENCE:
        result.error("runtime receipt policy allowed_evidence vocabulary mismatch")
    if normative.get("allowed_evidence") != ALLOWED_EVIDENCE:
        result.error("normative runtime contract allowed_evidence vocabulary mismatch")
    if normative.get("certified_request_tuples") != policy.get("certified_request_tuples"):
        result.error("normative runtime contract certified request tuples mismatch")
    if policy.get("certified_request_tuples") != certified_request_tuples():
        result.error("runtime receipt policy certified request tuples differ from the source-pinned model/context matrix")

    contract = policy.get("canonical_runtime_contract")
    if not isinstance(contract, str):
        result.error("runtime receipt policy must define a canonical runtime contract")
        return
    if normative.get("canonical_receipt_policy_sha256") != sha256_bytes(policy_path.read_bytes()):
        result.error("normative runtime contract digest does not bind the canonical receipt policy")
    if normative.get("canonical_runtime_contract_sha256") != sha256_bytes(contract.encode("utf-8")):
        result.error("normative runtime contract digest does not bind the canonical runtime block")
    if normative.get("canonical_runtime_contract_sha256") != CANONICAL_RUNTIME_CONTRACT_SHA256:
        result.error("normative runtime contract digest does not match the source-pinned canonical runtime authority contract")
    if normative.get("research_director_seeds_contract_sha256") != RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256:
        result.error("normative runtime contract digest does not bind the Research Director Seeds boundary")
    packaged_receipt = PACKAGED_POLICY_DIR / RECEIPT_POLICY_PATH.name
    packaged_normative = PACKAGED_POLICY_DIR / NORMATIVE_CONTRACT_PATH.name
    if not packaged_receipt.is_file() or packaged_receipt.read_bytes() != policy_path.read_bytes():
        result.error("packaged Research OS receipt policy must be byte-identical to the canonical policy")
    if not packaged_normative.is_file() or packaged_normative.read_bytes() != NORMATIVE_CONTRACT_PATH.read_bytes():
        result.error("packaged Research OS normative contract must be byte-identical to the canonical contract")
    if VALIDATION_ONLY_SEMANTICS not in contract:
        result.error("canonical runtime block must preserve validation-only semantics")
    if ONE_MILLION_CONTEXT_SEMANTICS not in contract:
        result.error("canonical runtime block must preserve evidence-qualified [1m] semantics")
    if not any(
        value in contract
        for value in (
            "external authenticated harness is the sole spawn and admission authority",
            "external authenticated harness is solely responsible for spawn and admission",
        )
    ):
        result.error("canonical runtime block must preserve the source-pinned canonical runtime authority contract")
    if "Local validation authorizes push" in contract or "local validation authorizes push" in contract:
        result.error("canonical runtime block must preserve the source-pinned canonical runtime authority contract")


def managed_global_paths(root: Path) -> set[str]:
    return {
        *(path.relative_to(root).as_posix() for path in (root / "agents" / "claude").glob("*.md")),
        *(path.relative_to(root).as_posix() for path in (root / "agents" / "codex").glob("*.toml")),
    }


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


ROLE_MANIFEST_WEB_SIGNAL = re.compile(r"(?i)\b(?:live research|prior art)\b")


def _role_manifest_web_required(root: Path) -> set[str]:
    """Derive, from the pinned role files, which logical roles genuinely need web.

    Fail-closed and cross-checked, not asserted (spec §7/§4): a delivery role needs web
    only if its Claude projection allow-lists WebFetch/WebSearch; a research role needs web
    only if its pinned prose signals live research / prior-art work. The manifest's
    web_access field is then required to equal this derived truth.
    """
    required: set[str] = set()
    for filename in CLAUDE_GLOBAL_ROLE_FILENAMES:
        role_id = filename[len("sdlc-"):-len(".md")]
        path = root / "agents" / "claude" / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        in_tools = False
        tools: set[str] = set()
        for line in text.splitlines():
            if line.strip() == "tools:":
                in_tools = True
                continue
            if in_tools:
                match = re.match(r"\s*-\s*(\w+)", line)
                if match:
                    tools.add(match.group(1))
                elif line.strip() == "---":
                    break
        if {"WebFetch", "WebSearch"} & tools:
            required.add(role_id)
    for role in RESEARCH_ROLE_IDS:
        path = root / "agents" / "codex" / "research" / f"{role}.toml"
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if ROLE_MANIFEST_WEB_SIGNAL.search(data.get("developer_instructions", "") or ""):
            required.add(role)
    return required


def _role_manifest_pinned_digests(normative: dict[str, object]) -> tuple[dict[str, str], dict[str, str]]:
    """Return (path -> content_digest, path -> sandbox_mode) drawn from the pinned contract.

    Both maps are the SOLE source of truth for manifest cross-checks: the manifest may
    only reference these bytes, never restate a different authority.
    """
    managed = normative["managed_roles"]
    global_hashes = dict(managed["global"]["manifest_sha256"])
    research_roles = managed["research"]["roles"]
    digests = dict(global_hashes)
    sandboxes: dict[str, str] = {}
    for spec in research_roles.values():
        if isinstance(spec, dict) and isinstance(spec.get("path"), str):
            digests[spec["path"]] = spec.get("manifest_sha256")
            sandboxes[spec["path"]] = spec.get("sandbox_mode")
    return digests, sandboxes


def validate_role_manifest(root: Path, result: Validation) -> None:
    """Validate the versioned role-contract manifest against the source-pinned contract.

    The manifest documents orchestration metadata for the 24 logical roles (7 delivery x2
    projections + 17 research). Every authority-relevant field is either derived-and-
    cross-checked against the digest-pinned normative contract or inert with respect to
    runtime authority; the manifest can never widen authority the pinned prose forbids.
    """
    manifest_path = root / "policy" / "role-manifest.v1.json"
    if not manifest_path.is_file():
        result.error("policy/role-manifest.v1.json: missing versioned role-contract manifest")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.error(f"policy/role-manifest.v1.json: invalid JSON: {exc}")
        return
    if not isinstance(manifest, dict):
        result.error("policy/role-manifest.v1.json: manifest must be a JSON object")
        return

    # F1 — schema validity: exact top-level key set and schema version.
    if set(manifest) != ROLE_MANIFEST_TOP_LEVEL_KEYS:
        result.error("policy/role-manifest.v1.json: top-level keys must be exactly "
                     f"{sorted(ROLE_MANIFEST_TOP_LEVEL_KEYS)}")
    if manifest.get("schema_version") != ROLE_MANIFEST_SCHEMA_VERSION:
        result.error("policy/role-manifest.v1.json: schema_version must be "
                     f"{ROLE_MANIFEST_SCHEMA_VERSION!r}")

    try:
        normative = normative_runtime_contract()
        pinned_digests, pinned_sandboxes = _role_manifest_pinned_digests(normative)
    except (ValueError, KeyError, TypeError) as exc:
        result.error(f"policy/role-manifest.v1.json: cannot bind pinned contract: {exc}")
        return
    web_required_roles = _role_manifest_web_required(root)

    # F3/Q5 — the manifest is bound to a specific normative contract by digest; a drift
    # here forces a manifest regen + digest refresh rather than a silent bypass.
    generated_from = manifest.get("generated_from")
    if not isinstance(generated_from, dict):
        result.error("policy/role-manifest.v1.json: generated_from must be an object")
        generated_from = {}
    actual_normative_sha = sha256_bytes(NORMATIVE_CONTRACT_PATH.read_bytes())
    if generated_from.get("normative_contract_sha256") != actual_normative_sha:
        result.error("policy/role-manifest.v1.json: generated_from.normative_contract_sha256 "
                     "does not bind the pinned normative contract")

    roles = manifest.get("roles")
    if not isinstance(roles, dict):
        result.error("policy/role-manifest.v1.json: roles must be an object")
        return

    # F2 — roster completeness & counts (mirrors the 14 global + 17 research invariants).
    expected_role_ids = DELIVERY_ROLE_IDS | RESEARCH_ROLE_IDS
    if set(roles) != expected_role_ids:
        result.error("policy/role-manifest.v1.json: roles must be exactly the 7 delivery "
                     "and 17 Research OS logical roles")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or counts.get("delivery_roles") != 7 \
            or counts.get("research_roles") != 17 or counts.get("projection_files") != 31:
        result.error("policy/role-manifest.v1.json: counts must be 7 delivery, 17 research, "
                     "31 projection files")

    projection_paths: set[str] = set()
    for role_id in sorted(roles):
        role = roles[role_id]
        if not isinstance(role, dict):
            result.error(f"policy/role-manifest.v1.json: role {role_id} must be an object")
            continue
        extra = set(role) - ROLE_MANIFEST_ROLE_KEYS
        missing = ROLE_MANIFEST_REQUIRED_ROLE_KEYS - set(role)
        if extra:
            result.error(f"policy/role-manifest.v1.json: role {role_id} has unknown keys {sorted(extra)}")
        if missing:
            result.error(f"policy/role-manifest.v1.json: role {role_id} missing keys {sorted(missing)}")

        kind = role.get("kind")
        is_delivery = role_id in DELIVERY_ROLE_IDS
        if kind != ("delivery" if is_delivery else "research"):
            result.error(f"policy/role-manifest.v1.json: role {role_id} kind mismatch")

        # §3/§4 — publication authority is none for every managed role, always.
        if role.get("publication_authority") != "none":
            result.error(f"policy/role-manifest.v1.json: role {role_id} publication_authority must be none")

        # §3.1/§4.2 — fan_in_authority=authorized-executor ONLY for the integrator.
        fan_in = role.get("fan_in_authority")
        if role_id == "integrator":
            if fan_in != "authorized-executor":
                result.error("policy/role-manifest.v1.json: integrator fan_in_authority must be authorized-executor")
        elif fan_in != "none":
            result.error(f"policy/role-manifest.v1.json: role {role_id} fan_in_authority must be none")

        # §3.2/§4.2 — queue_authority is read-only for the research director, none otherwise;
        # never a mutate value. This is checked against the role id, not the manifest's claim.
        queue = role.get("queue_authority")
        allowed_queue = {"read-only", "none"} if role_id == "research_director" else {"none"}
        if queue not in allowed_queue:
            result.error(f"policy/role-manifest.v1.json: role {role_id} queue_authority must be "
                         f"one of {sorted(allowed_queue)}")

        # §3.3-4/§4.2 — advisory_only is mandatory-true for protected reviewers and the
        # standing critic; asserting advisory_only=false there is the coordinated-repin bypass.
        advisory = role.get("advisory_only", None)
        if role_id in ROLE_MANIFEST_ADVISORY_ONLY_ROLES:
            if advisory is not True:
                result.error(f"policy/role-manifest.v1.json: role {role_id} must be advisory_only=true")
        elif advisory is not None and advisory is not False:
            result.error(f"policy/role-manifest.v1.json: role {role_id} advisory_only must be boolean")

        # §4.3/F5 — model lane is a family hint; the exact model comes from the conductor's
        # RuntimeAssignment. Reject any resolved exact model ID or wrong runtime source.
        model = role.get("model")
        if not isinstance(model, dict):
            result.error(f"policy/role-manifest.v1.json: role {role_id} model must be an object")
            model = {}
        if model.get("lane_family") not in ROLE_MANIFEST_LANE_FAMILIES:
            result.error(f"policy/role-manifest.v1.json: role {role_id} model.lane_family invalid")
        if model.get("runtime_model_source") != ROLE_MANIFEST_RUNTIME_MODEL_SOURCE:
            result.error(f"policy/role-manifest.v1.json: role {role_id} model.runtime_model_source must be "
                         f"{ROLE_MANIFEST_RUNTIME_MODEL_SOURCE!r}")
        model_blob = json.dumps(model)
        for exact_id in EXACT_MODEL_PROVIDER_MAP:
            if exact_id in model_blob:
                result.error(f"policy/role-manifest.v1.json: role {role_id} model block leaks exact model id {exact_id}")
        if "resolved_model_id" in model:
            result.error(f"policy/role-manifest.v1.json: role {role_id} model must not carry a resolved_model_id")
        if model.get("context_forms_eligible") != ["base"]:
            result.error(f"policy/role-manifest.v1.json: role {role_id} model.context_forms_eligible must be ['base']")

        # §2/§2.2 — artifacts reference the six standard names; no new artifact format.
        artifacts = role.get("artifacts")
        if not isinstance(artifacts, dict):
            result.error(f"policy/role-manifest.v1.json: role {role_id} artifacts must be an object")
            artifacts = {}
        for slot in ("accepted", "produced"):
            names = artifacts.get(slot)
            if not isinstance(names, list) or any(n not in ROLE_MANIFEST_ARTIFACTS for n in names):
                result.error(f"policy/role-manifest.v1.json: role {role_id} artifacts.{slot} must be "
                             "standard artifact names")

        # §7/F6 — capabilities are default-closed and cross-checked; web=required implies
        # network=required. Only researcher (delivery) and the web-consuming research roles
        # may request web.
        capabilities = role.get("capabilities")
        if not isinstance(capabilities, dict):
            result.error(f"policy/role-manifest.v1.json: role {role_id} capabilities must be an object")
            capabilities = {}
        web = capabilities.get("web_access")
        network = capabilities.get("network")
        if web not in {"required", "none"}:
            result.error(f"policy/role-manifest.v1.json: role {role_id} capabilities.web_access invalid")
        if network not in {"required", "none"}:
            result.error(f"policy/role-manifest.v1.json: role {role_id} capabilities.network invalid")
        if web == "required" and network != "required":
            result.error(f"policy/role-manifest.v1.json: role {role_id} web_access=required implies network=required")
        # Cross-check web against the pinned role files, not the manifest's own claim:
        # a role may declare web=required only if its pinned surface genuinely needs it,
        # and a genuinely web-needing role may not silently drop to none (fail-closed).
        expected_web = "required" if role_id in web_required_roles else "none"
        if web != expected_web:
            result.error(f"policy/role-manifest.v1.json: role {role_id} web_access must be "
                         f"{expected_web!r} to match its pinned capability surface")

        # §6/F7 — cartography discriminant: delivery cartographer is ephemeral/delivery,
        # research repo_cartographer is durable/research_memory; present only for map roles.
        cartography = role.get("cartography")
        if role_id == "cartographer":
            if cartography != {"map_kind": "delivery", "persistence": "ephemeral"}:
                result.error("policy/role-manifest.v1.json: cartographer cartography must be delivery/ephemeral")
        elif role_id == "repo_cartographer":
            if cartography != {"map_kind": "research_memory", "persistence": "durable"}:
                result.error("policy/role-manifest.v1.json: repo_cartographer cartography must be "
                             "research_memory/durable")
        elif cartography is not None:
            result.error(f"policy/role-manifest.v1.json: role {role_id} must not declare cartography")

        # F3/F8 — projections: digest coexistence + sandbox equality + submission-contract tag.
        projections = role.get("projections")
        if not isinstance(projections, dict):
            result.error(f"policy/role-manifest.v1.json: role {role_id} projections must be an object")
            continue
        expected_hosts = {"claude", "codex"} if is_delivery else {"codex"}
        if set(projections) != expected_hosts:
            result.error(f"policy/role-manifest.v1.json: role {role_id} projections must be {sorted(expected_hosts)}")
        for host, projection in projections.items():
            if not isinstance(projection, dict):
                result.error(f"policy/role-manifest.v1.json: role {role_id}/{host} projection must be an object")
                continue
            path = projection.get("path")
            projection_paths.add(path)
            # F3 — content_digest MUST equal the pinned bytes; a mutated digest is an error,
            # not a new source of truth. sandbox_mode MUST equal the pinned sandbox_mode.
            if path not in pinned_digests:
                result.error(f"policy/role-manifest.v1.json: role {role_id}/{host} path {path} not pinned")
            elif projection.get("content_digest") != pinned_digests[path]:
                result.error(f"policy/role-manifest.v1.json: role {role_id}/{host} content_digest differs "
                             "from the source-pinned normative contract")
            if host == "codex" and not is_delivery:
                if projection.get("sandbox_mode") != pinned_sandboxes.get(path):
                    result.error(f"policy/role-manifest.v1.json: role {role_id}/{host} sandbox_mode differs "
                                 "from the source-pinned normative contract")
            # F8 — submission-contract tag: eight-heading for delivery, research-ledger for research.
            expected_contract = "eight-heading" if is_delivery else "research-ledger"
            if projection.get("submission_contract") != expected_contract:
                result.error(f"policy/role-manifest.v1.json: role {role_id}/{host} submission_contract must be "
                             f"{expected_contract!r}")

    # F2 — the 31 pinned projection files are all referenced exactly once by the manifest.
    if projection_paths != set(pinned_digests):
        result.error("policy/role-manifest.v1.json: projections must reference exactly the 31 pinned role files")


def validate_managed_role_contract(root: Path, result: Validation) -> None:
    try:
        normative = normative_runtime_contract()
        managed = normative["managed_roles"]
        global_spec = managed["global"]
        research_spec = managed["research"]
    except (ValueError, KeyError, TypeError) as exc:
        result.error(f"invalid normative managed role contract: {exc}")
        return

    global_paths = managed_global_paths(root)
    actual_global = {
        str(path.relative_to(root)).replace("\\", "/")
        for path in (
            *(root / "agents" / "claude").glob("*.md"),
            *(root / "agents" / "codex").glob("*.toml"),
        )
    }
    expected_global_hashes = global_spec.get("manifest_sha256", {})
    if (
        global_spec.get("count") != 14
        or set(expected_global_hashes) != SOURCE_PINNED_GLOBAL_PATHS
        or global_paths != SOURCE_PINNED_GLOBAL_PATHS
        or actual_global != SOURCE_PINNED_GLOBAL_PATHS
    ):
        result.error("managed role roster must contain exactly the 14 global SDLC roles")
    for relative in sorted(SOURCE_PINNED_GLOBAL_PATHS):
        path = root / relative
        if not path.is_file() or sha256_bytes(path.read_bytes()) != expected_global_hashes.get(relative):
            result.error(f"{relative}: full manifest content differs from normative managed role contract")

    expected_roles = research_spec.get("roles", {})
    expected_research_paths = {
        spec.get("path") for spec in expected_roles.values() if isinstance(spec, dict)
    }
    actual_research_paths = {
        str(path.relative_to(root)).replace("\\", "/")
        for path in (root / "agents" / "codex" / "research").glob("*.toml")
    }
    if (
        research_spec.get("count") != 17
        or set(expected_roles) != RESEARCH_ROLE_IDS
        or expected_research_paths != SOURCE_PINNED_RESEARCH_PATHS
        or actual_research_paths != SOURCE_PINNED_RESEARCH_PATHS
    ):
        result.error("managed role roster must contain exactly the 17 Research OS roles")
    for role in sorted(RESEARCH_ROLE_IDS):
        spec = expected_roles.get(role)
        if not isinstance(spec, dict) or spec.get("path") != f"agents/codex/research/{role}.toml":
            result.error(f"managed research role {role}: invalid normative specification")
            continue
        path = root / spec["path"]
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if data.get("name") != role:
            result.error(f"{spec['path']}: managed role name mismatch")
        if data.get("sandbox_mode") != spec.get("sandbox_mode"):
            result.error(f"{spec['path']}: sandbox_mode differs from normative managed role contract")
        description = data.get("description")
        instructions = data.get("developer_instructions")
        if not isinstance(description, str) or sha256_bytes(description.encode("utf-8")) != spec.get("description_sha256"):
            result.error(f"{spec['path']}: description differs from normative managed role contract")
        if not isinstance(instructions, str) or sha256_bytes(instructions.encode("utf-8")) != spec.get("developer_instructions_sha256"):
            result.error(f"{spec['path']}: developer instructions differ from normative managed role contract")
        if sha256_bytes(path.read_bytes()) != spec.get("manifest_sha256"):
            result.error(f"{spec['path']}: full manifest content differs from normative managed role contract")

    validate_source_pinned_protected_role_authority(root, result)


def runtime_receipt_contract() -> str:
    policy = runtime_receipt_policy()
    contract = policy.get("canonical_runtime_contract")
    if not isinstance(contract, str) or not contract:
        raise ValueError("runtime receipt policy must define a canonical runtime contract")
    return contract


def runtime_receipt_fields() -> tuple[str, ...]:
    try:
        fields = runtime_receipt_policy()["canonical_receipt_fields"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid runtime receipt policy: {exc}") from exc
    if (
        not isinstance(fields, list)
        or len(fields) != 18
        or not all(isinstance(field, str) and field for field in fields)
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("runtime receipt policy must define exactly 18 unique non-empty canonical fields")
    return tuple(fields)


def projected_runtime_receipt_fields(text: str) -> tuple[str, ...]:
    marker = "canonical v1 top-level shape is exactly:\n"
    if text.count(marker) != 1:
        return ()
    projection: list[str] = []
    for line in text.split(marker, 1)[1].splitlines():
        match = re.fullmatch(r"- `([a-z][a-z0-9_]*)`: .+", line)
        if match:
            projection.append(match.group(1))
            continue
        if projection:
            break
    return tuple(projection)


def validate_runtime_receipt_projection(text: str, label: Path | str, result: Validation) -> None:
    try:
        required = runtime_receipt_fields()
    except ValueError as exc:
        result.error(str(exc))
        return
    projected = projected_runtime_receipt_fields(text)
    missing = sorted(set(required) - set(projected))
    if missing:
        result.error(f"{label}: runtime receipt projection missing {', '.join(missing)}")
    if projected != required:
        result.error(f"{label}: runtime receipt projection must equal the exact policy-derived 18-field block")
    try:
        contract = runtime_receipt_contract()
    except ValueError as exc:
        result.error(str(exc))
    else:
        if text.count(contract) != 1:
            result.error(f"{label}: runtime receipt projection must equal the exact policy-derived canonical runtime block")
        else:
            outside_contract = text.replace(contract, "", 1)
            for pattern in FORBIDDEN_PROJECTION_AUTHORITY_PATTERNS:
                if pattern.search(outside_contract):
                    result.error(f"{label}: contradictory runtime authority projection is forbidden")
    if any(field in text for field in RUNTIME_RECEIPT_SOURCE_FIELDS):
        result.error(f"{label}: stale runtime receipt source projection is forbidden")


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
        validate_runtime_receipt_projection(text, label, result)
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
        validate_runtime_receipt_projection(agent.read_text(encoding="utf-8"), agent.relative_to(root).as_posix(), result)


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
    missing = sorted(path for path in OPERATOR_TOOL_ARTIFACTS if not (root / path).is_file())
    if missing:
        result.error(f"operator-tool artifacts missing: {', '.join(missing)}")
        return
    bash = shutil.which("bash")
    if bash is None:
        result.warn("bash is unavailable; operator-tool shell syntax was not checked")
        return
    for relative in (
        "assets/claude/statusline-command.sh",
        "assets/claude/session-inheritance.sh",
        "assets/launchers/ccodex.in",
        "scripts/opencodex-claude.sh",
    ):
        completed = subprocess.run(
            [bash, "-n", str(root / relative)], capture_output=True, text=True, check=False
        )
        if completed.returncode:
            result.error(f"invalid shell syntax in {relative}: {completed.stderr.strip()}")


def validate_mise(root: Path, result: Validation) -> None:
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
    expected_tools = {
        "uv": UV_VERSION,
        "lefthook": LEFTHOOK_VERSION,
        "node": NODE_VERSION,
        "bun": BUN_VERSION,
        # npm carries the node edge because its own installer IS npm: without it, a fresh
        # machine's first `mise install` fails and then skips every other npm-backend pin.
        MERMAID_NPM_TOOL: {"version": MERMAID_NPM_VERSION, "depends": ["node"]},
        "ripgrep": RIPGREP_VERSION,
        "fd": FD_VERSION,
        "jq": JQ_VERSION,
        "gh": GH_VERSION,
        SEEDS_TOOL: {"version": SEEDS_VERSION, "depends": ["node"]},
        BETTERLEAKS_TOOL: {"version": BETTERLEAKS_VERSION},
        OPENCODEX_TOOL: {"version": OPENCODEX_VERSION, "depends": ["node"]},
    }
    if config.get("tools") != expected_tools:
        result.error(f"mise.toml tools must equal {expected_tools}")
    # Every npm-backend pin drags in a transitive dependency tree whose install scripts run
    # during `mise --locked install`, so each one is reviewed by name against docs/adr/0002's
    # 2026-08-07 screening rule before it is allowed. This catches an UNREVIEWED npm pin being
    # added; it cannot detect that an already-listed pin's upstream added a hostile postinstall.
    unreviewed = sorted(
        name
        for name in config.get("tools", {})
        if name.startswith("npm:") and name not in NPM_BACKED_TOOLS
    )
    if unreviewed:
        result.error(
            "mise.toml npm-backend pins must be reviewed for install-script prerequisites "
            f"per docs/adr/0002 before use: {unreviewed}"
        )
    seeds = config.get("tools", {}).get(SEEDS_TOOL, {})
    if seeds.get("depends") != ["node"]:
        result.error("mise.toml Seeds tool must depend on node")

    for name, suffix in TASK_COMMANDS.items():
        task = tasks.get(name, {})
        windows_suffix = suffix
        if name == "bundle:install:all-hosts":
            windows_suffix = "--script scripts/install_skill_bundle.py install"
        elif name == "bundle:status:all-hosts":
            windows_suffix = "--script scripts/install_skill_bundle.py status"
        for field, executable, command_suffix in (
            ("run", "uv", suffix),
            ("run_windows", "uv.exe", windows_suffix),
        ):
            expected = f"{executable} run --python {PYTHON_VERSION} {command_suffix}"
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
    expected_ocx_tasks = {
        "ocx:launch": {
            "description": "Launch a second Claude Code process through the opencodex gateway",
            "run": "scripts/opencodex-claude.sh launch",
        },
        "ocx:ultracode": {
            "description": "Launch opencodex Claude with Ultracode and optional explicit permission bypass",
            "run": "scripts/opencodex-claude.sh launch-ultracode",
        },
        "ocx:status": {
            "description": "Report opencodex gateway reachability and configured providers",
            "run": "scripts/opencodex-claude.sh status",
        },
        "ocx:restart": {
            "description": "Stop the opencodex gateway cleanly and ensure it is healthy again",
            "run": "scripts/opencodex-claude.sh restart",
        },
        "ocx:configure": {
            "description": "Configure opencodex providers through their own login flows",
            "run": "scripts/opencodex-claude.sh configure",
        },
    }
    for name, expected in expected_ocx_tasks.items():
        if tasks.get(name) != expected:
            result.error(f"mise.toml task {name} must contain only {expected}")
    expected_contributor_setup = {
        "description": "Install this host's bundle and contributor Git hooks",
        "depends": ["bundle:install", "hooks:install"],
    }
    expected_setup_forwarder = {
        "description": "Deprecated: use contributor:setup",
        "depends": ["contributor:setup"],
    }
    if tasks.get("contributor:setup") != expected_contributor_setup:
        result.error(
            "mise.toml contributor:setup must contain only the bundle:install and hooks:install dependencies"
        )
    if tasks.get("setup") != expected_setup_forwarder:
        result.error(
            "mise.toml setup must be only the one-release deprecated contributor:setup forwarder"
        )
    if tasks.get("mermaid:provision") != MERMAID_PROVISION_TASK:
        result.error(f"mise.toml mermaid:provision must contain only {MERMAID_PROVISION_TASK}")
    expected_check = {
        "description": "Run validation, installer tests, lifecycle self-test, and the secrets scan",
        "depends": ["validate", "test", "self-test", "secrets"],
    }
    if tasks.get("check") != expected_check:
        result.error("mise.toml check must contain only its description and exact validate/test/self-test/secrets dependencies")
    # Provisioning downloads a pinned browser, so wiring either Mermaid task into the gate
    # would turn a convenience surface into a bootstrap prerequisite and make the verdict
    # depend on network reachability. The exact-dict check above already rejects that; this
    # states the boundary where a future edit would look for it.
    for leaf in expected_check["depends"]:
        if leaf.startswith("mermaid:"):
            result.error("mise.toml check must not depend on a Mermaid task: rendering is advisory")

    lock_path = root / "mise.lock"
    if not lock_path.is_file():
        result.error("mise.lock is required")
        return
    try:
        lock_bytes = lock_path.read_bytes()
    except OSError as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return
    if hashlib.sha256(lock_bytes).hexdigest() != MISE_LOCK_SHA256:
        result.error("mise.lock SHA-256 must equal the canonical generated lock")
    try:
        lock = tomllib.loads(lock_bytes.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return
    locked_tools = lock.get("tools", {})
    expected_versions = {
        "uv": UV_VERSION,
        "lefthook": LEFTHOOK_VERSION,
        "node": NODE_VERSION,
        "bun": BUN_VERSION,
        MERMAID_NPM_TOOL: MERMAID_NPM_VERSION,
        "ripgrep": RIPGREP_VERSION,
        "fd": FD_VERSION,
        "jq": JQ_VERSION,
        "gh": GH_VERSION,
        SEEDS_TOOL: SEEDS_VERSION,
        BETTERLEAKS_TOOL: BETTERLEAKS_VERSION,
        OPENCODEX_TOOL: OPENCODEX_VERSION,
    }
    if set(locked_tools) != set(expected_versions):
        result.error(f"mise.lock tools must equal {sorted(expected_versions)}")
    for name, version in expected_versions.items():
        entries = locked_tools.get(name, [])
        if len(entries) != 1 or entries[0].get("version") != version:
            result.error(f"mise.lock must resolve {name} {version}")
            continue
        entry = entries[0]
        expected_backend = EXPECTED_LOCK_BACKENDS.get(name)
        if expected_backend is not None and entry.get("backend") != expected_backend:
            result.error(f"mise.lock {name} backend must equal {expected_backend}")
        # npm-backed pins carry no per-platform record: the npm backend resolves one
        # package for every platform, so version+backend is the whole integrity surface.
        if name in NPM_BACKED_TOOLS:
            if set(entry) != {"version", "backend"}:
                result.error(f"mise.lock {name} must contain version and backend only")
            continue
        platform_keys = {key for key in entry if key.startswith("platforms.")}
        if not platform_keys:
            result.error(f"mise.lock {name} must record per-platform checksums")
        for key in platform_keys:
            if "checksum" not in entry[key]:
                result.error(f"mise.lock {name} {key} must record a checksum")


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

    workflow = root / ".github" / "workflows" / "validate.yml"
    if not workflow.is_file():
        result.error(".github/workflows/validate.yml is required")
    else:
        workflow_text = workflow.read_text(encoding="utf-8")
        if workflow_text != EXPECTED_WORKFLOW:
            result.error("CI workflow must equal the single authoritative mise run check graph")

    claude = root / "CLAUDE.md"
    if not claude.is_file() or not claude.read_text(encoding="utf-8").startswith("@AGENTS.md\n"):
        result.error("CLAUDE.md must begin with @AGENTS.md")


def validate_versions(root: Path, result: Validation) -> None:
    manifest_path = root / ".version-bump.json"
    if not manifest_path.is_file():
        return
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
    validate_skills(root, result)
    validate_workflows(root, result)
    validate_python(root, result)
    validate_release_contract(root, result)
    validate_release_candidate_policy(root, result)
    validate_release_candidate_acquisition_policy(root, result)
    validate_ccodex_sdlc_read_report_policy(root, result)
    validate_release_candidate_execution_policy(root, result)
    validate_ccodex_sdlc_candidate_report_policy(root, result)
    validate_runtime_policy_contract(root, result)
    validate_agents(root, result)
    validate_managed_role_contract(root, result)
    validate_role_manifest(root, result)
    validate_mermaid_renderer(root, result)
    validate_operator_tools(root, result)
    validate_mise(root, result)
    validate_gate_graph(root, result)
    validate_versions(root, result)
    validate_scripts(root, result)
    validate_manifests(root, result)
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
