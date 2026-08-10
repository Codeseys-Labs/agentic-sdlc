#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Validate Agentic SDLC bundle metadata and lifecycle contracts."""

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
TEXT_SUFFIXES = {".md", ".mjs", ".sh", ".ps1", ".toml", ".json", ".yml", ".yaml", ".py"}
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
UV_VERSION = "0.11.17"
PYTHON_VERSION = "3.12.11"
LEFTHOOK_VERSION = "2.1.10"
NODE_VERSION = "22.22.3"
BUN_VERSION = "1.3.10"
SEEDS_VERSION = "0.5.15"
SEEDS_TOOL = "npm:@os-eco/seeds-cli"
# Convenience tier. Pinned for identical resolution across hosts; no gate depends on them.
RIPGREP_VERSION = "15.2.0"
FD_VERSION = "10.4.2"
JQ_VERSION = "1.8.2"
GH_VERSION = "2.97.0"
BETTERLEAKS_VERSION = "1.7.3"
BETTERLEAKS_TOOL = "github:betterleaks/betterleaks"
# The renderer's mmdc version. It is pinned by package-lock.json digest below, NOT by a mise
# [tools] entry: that entry was removed 2026-08-07 (docs/adr/0002 amendment) because puppeteer's
# postinstall came with it and needed a zip archiver mise does not install, failing the whole
# `mise --locked install`. Nothing resolves mmdc through mise, so there is no lock/tool pin here.
MERMAID_VERSION = "11.16.0"
# Installed by default per docs/adr/0005. The packaging pin is convenience tier like the two
# npm pins above; the boundary that matters is usage-level and lives in the launcher script,
# not here (docs/adr/0003: non-Anthropic routing only, never subscription OAuth).
OPENCODEX_VERSION = "2.11.1"
OPENCODEX_TOOL = "npm:@bitkyc08/opencodex"
# node 22.22.3 bundles npm 10.9.8, so the M0b renderer's npm identity is pinned as its own
# tool. scripts/provision_mermaid_linux.py resolves exactly this version through `mise where`
# to install the renderer's node_modules. Provisioning is an explicit operator step and no
# gate leaf invokes it, so this pin never becomes a bootstrap prerequisite.
MERMAID_NPM_VERSION = "10.8.1"
MERMAID_NPM_TOOL = "npm"
MERMAID_NPM_BACKEND = "npm:npm"
# The renderer supply chain is pinned by exact digest, not by version range: the lock bytes and
# the policy bytes are both hashed, so a dependency edit or a policy loosening fails the gate.
MERMAID_PACKAGE_LOCK_SHA256 = "939c3abe521d3e2075cf757f2761fa1d3103daf270be778eae159b45e6e3bb88"
MERMAID_POLICY_SHA256 = "ee669a8ee36c085713071e91cb1b2b38c75f28dec9a0cfbbc1cd86559ca6ecce"
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
        "scripts/install_operator_tools.py",
        "scripts/manage_claude_statusline.py",
        "tests/test_claude_statusline.py",
        "tests/test_manage_claude_statusline.py",
        "tests/test_operator_tools.py",
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
MISE_LOCK_SHA256 = "3a4d510446bdbf1456ef29d976a03f0d096f58fc524b7bb4a823930e085ab9db"
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
# The secrets task runs the pinned scanner binary directly, not through uv, so it is pinned
# on its own. `dir` scans the working tree; the full-history verb (`git`) is deliberately not
# wired here — history scanning is a consent-requiring pre-publish step, not a commit gate.
# `--config` is part of the pin, not a convenience: without it the scanner auto-loads a drop-in
# .gitleaks.toml/.betterleaks.toml from cwd or a GITLEAKS_CONFIG*/BETTERLEAKS_CONFIG* variable,
# so an untracked `[extend] useDefault = false` file silently replaces the ruleset. mise resolves
# the pinned binary on PATH identically on both platforms, so run_windows is the same string.
SECRETS_CONFIG_PATH = ".config/betterleaks.toml"
SECRETS_COMMAND = f"betterleaks dir . --config {SECRETS_CONFIG_PATH}"
RECEIPT_POLICY_PATH = Path(__file__).parents[1] / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
NORMATIVE_CONTRACT_PATH = Path(__file__).parents[1] / "policy" / "runtime-assignment-normative-contract-v1.json"
ROLE_MANIFEST_PATH = Path(__file__).parents[1] / "policy" / "role-manifest.v1.json"
PACKAGED_POLICY_DIR = Path(__file__).parents[1] / "skills" / "codex-research-os" / "policy"
RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256 = "2ca7f36c728d324ab60f2b99d4b3fb03f064180496c0731aa33447a7dee4ba72"
RESEARCH_DIRECTOR_SEEDS_AUTHORITY = """Seeds authority:
- Research Director is Seeds-read-only.
- Use only the exact accepted Seeds inspection contract:
  `Seeds(<target>, <args...>)` = `MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.15 -- sd <args>`.
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
RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256 = "e490284af11143c71a9a07d0e5778594c3ba99bd648220dec3268b4d5491e0b8"
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
EXPECTED_WORKFLOW = """name: validate-bundle

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
        "description": "Scan the working tree for secrets with the pinned scanner",
        "run": SECRETS_COMMAND,
        "run_windows": SECRETS_COMMAND,
    }
    if tasks.get("secrets") != expected_secrets:
        result.error(f"mise.toml secrets must contain only its description and the exact working-tree scan {SECRETS_COMMAND!r}")
    validate_secrets_config(root, result)
    expected_ocx_tasks = {
        "ocx:launch": {
            "description": "Launch a second Claude Code process through the opencodex gateway",
            "run": "scripts/opencodex-claude.sh launch",
        },
        "ocx:ultracode": {
            "description": "Launch opencodex Claude with session Ultracode and ordinary permissions",
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
    validate_python(root, result)
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
