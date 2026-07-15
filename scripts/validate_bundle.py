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
TEXT_SUFFIXES = {".md", ".sh", ".ps1", ".toml", ".json", ".yml", ".yaml", ".py"}
REQUIRED_TASKS = {
    "bundle:install",
    "bundle:status",
    "bundle:uninstall",
    "bundle:install:claude",
    "bundle:install:codex",
    "bundle:install:all-hosts",
    "bundle:status:all-hosts",
    "research-os:install",
    "test",
    "self-test",
    "check",
    "hooks:install",
    "setup",
}
MIN_MISE_VERSION = "2026.4.27"
UV_VERSION = "0.11.17"
PYTHON_VERSION = "3.12.11"
LEFTHOOK_VERSION = "2.1.10"
LOCK_PLATFORMS = {"linux-x64", "macos-arm64", "macos-x64", "windows-x64"}
LOCK_ARTIFACTS = {
    "uv": {
        "backend": "aqua:astral-sh/uv",
        "linux-x64": ("uv-x86_64-unknown-linux-musl.tar.gz", "4231a429d4e0f7c1937d8916658c08a7706cd7872afebeb87203a18c2e0dc28e"),
        "macos-arm64": ("uv-aarch64-apple-darwin.tar.gz", "2a162f6b90ff3691a2f9cae1622e066a3ce592e110f66670cdcc841324b28226"),
        "macos-x64": ("uv-x86_64-apple-darwin.tar.gz", "6c66e41eaf4d15abeda58d3f268161b6e3f742d98390341b174a7cfc1b48841d"),
        "windows-x64": ("uv-x86_64-pc-windows-msvc.zip", "35fc29e03e62f3cda769bc12773f3cb70ce305d0d36c0d8bd0c117dd0b3fcd14"),
    },
    "lefthook": {
        "backend": "aqua:evilmartians/lefthook",
        "linux-x64": ("lefthook_2.1.10_Linux_x86_64.gz", "0b14162a0bb2f0c64ae0759f6102f6e19c4d00981666a8ac73d4f5a6878ada4f"),
        "macos-arm64": ("lefthook_2.1.10_MacOS_arm64.gz", "1dd4dc7b4c50efb1f9d9122cd6535c793738d6e59751c228d49f768ec9dbb604"),
        "macos-x64": ("lefthook_2.1.10_MacOS_x86_64.gz", "49d905f28ca46442cb236060058b252da650b5f7b864bd275b61aa46945e8c4a"),
        "windows-x64": ("lefthook_2.1.10_Windows_x86_64.gz", "beabbce824641ae71229ed11dd8634f47148921cb649d25c90441b737481494a"),
    },
}
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
    "test": "--with pyyaml==6.0.3 python -m unittest discover -s tests",
    "self-test": "--script scripts/install_skill_bundle.py self-test",
}
RECEIPT_POLICY_PATH = Path(__file__).parents[1] / "skills" / "model-tier-rightsizing" / "policy" / "runtime-assignment-receipt-v1.json"
NORMATIVE_CONTRACT_PATH = Path(__file__).parents[1] / "policy" / "runtime-assignment-normative-contract-v1.json"
PACKAGED_POLICY_DIR = Path(__file__).parents[1] / "skills" / "codex-research-os" / "policy"
RESEARCH_DIRECTOR_SEEDS_CONTRACT_SHA256 = "9835671709c91b8cf936bd5468a1bd7d533c02ae8f3daac852eccaffc96d326f"
RESEARCH_DIRECTOR_SEEDS_AUTHORITY = """Seeds authority:
- Research Director is Seeds-read-only.
- Use only the exact accepted Seeds inspection contract:
  `Seeds(<target>, <args...>)` = `MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sd <args>`.
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
RESEARCH_DIRECTOR_PROTECTED_INSTRUCTIONS_SHA256 = "6ea5d0acaf63497963ee7087874ae20fdb735c0ae0afad8405b4de1c919a32bd"
SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256 = {
    "agents/claude/sdlc-reviewer.md": "2cc7132a36dd93127096448cf214c8a70ae5d7a9aed3d883df3a5af241ed8359",
    "agents/codex/sdlc-reviewer.toml": "31a77d96ea5184f2b4a2f87df250872b5c5e50ccd20c2adb8f15a30bfecba015",
    "agents/codex/research/adversarial_reviewer.toml": "eb8af719f2f4d4c6075f8a7c108bde8f455b0e6db24390e06b348263fb3cb2ec",
    "agents/codex/research/replication_reviewer.toml": "10c549ad2d30fe76837611ee4e5015b6cebf3f646711c67ecf5dd81ab1fe8077",
    "agents/codex/research/safety_reviewer.toml": "1e385fae9448d436188fc84f010c3cbf6a608622c54bdeef6f14c182b5780fa4",
}
CANONICAL_RUNTIME_CONTRACT_SHA256 = "e1872645df2e036770491fab44c122336c2fcf3e3765b10485d04bac06f23314"
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
        or len(fields) != 16
        or not all(isinstance(field, str) and field for field in fields)
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("runtime receipt policy must define exactly 16 unique non-empty canonical fields")
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
        result.error(f"{label}: runtime receipt projection must equal the exact policy-derived 16-field block")
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
    if config.get("settings", {}).get("locked") is not True:
        result.error("mise.toml must enable locked tool resolution")
    expected_tools = {"uv": UV_VERSION, "lefthook": LEFTHOOK_VERSION}
    if config.get("tools") != expected_tools:
        result.error(f"mise.toml tools must equal {expected_tools}")

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
    expected_check = {
        "description": "Run validation, installer tests, and lifecycle self-test",
        "depends": ["validate", "test", "self-test"],
    }
    if tasks.get("check") != expected_check:
        result.error("mise.toml check must contain only its description and exact validate/test/self-test dependencies")

    lock_path = root / "mise.lock"
    if not lock_path.is_file():
        result.error("mise.lock is required")
        return
    try:
        lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return
    locked_tools = lock.get("tools", {})
    for name, version in expected_tools.items():
        entries = locked_tools.get(name, [])
        if len(entries) != 1 or entries[0].get("version") != version:
            result.error(f"mise.lock must resolve {name} {version}")
            continue
        if entries[0].get("backend") != LOCK_ARTIFACTS[name]["backend"]:
            result.error(f"mise.lock {name} backend must equal {LOCK_ARTIFACTS[name]['backend']}")
        platforms = {
            key.removeprefix("platforms."): value
            for key, value in entries[0].items()
            if key.startswith("platforms.")
        }
        if set(platforms) != LOCK_PLATFORMS:
            result.error(f"mise.lock {name} platforms must equal {sorted(LOCK_PLATFORMS)}")
        for platform, record in platforms.items():
            if platform not in LOCK_ARTIFACTS[name]:
                continue
            release = f"https://github.com/{'astral-sh/uv' if name == 'uv' else 'evilmartians/lefthook'}/releases/download/"
            expected_version = version if name == "uv" else f"v{version}"
            artifact, checksum = LOCK_ARTIFACTS[name][platform]
            expected_url = f"{release}{expected_version}/{artifact}"
            if record.get("url") != expected_url:
                result.error(f"mise.lock {name} {platform} URL must equal {expected_url}")
            if record.get("checksum") != f"sha256:{checksum}":
                result.error(f"mise.lock {name} {platform} checksum must equal the reviewed SHA-256")
            if record.get("provenance") != "github-attestations":
                result.error(f"mise.lock {name} {platform} provenance must equal github-attestations")


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


def validate_cao_retirement(root: Path, result: Validation) -> None:
    message = "CAO has been retired; use native Frame/Wave/Mission instead.\n"
    expected_profile_names = {
        "claude-ultracode-workflow.md",
        "codex-implementer.md",
        "codex-macro-orchestrator.md",
        "codex-planner.md",
        "codex-reviewer.md",
    }
    profiles_dir = root / "cao-profiles"
    actual_profile_names = {
        path.name for path in profiles_dir.iterdir() if path.is_file()
    } if profiles_dir.is_dir() else set()
    if actual_profile_names != expected_profile_names:
        result.error(
            "CAO profile tombstone inventory mismatch: "
            f"expected {sorted(expected_profile_names)}, got {sorted(actual_profile_names)}"
        )

    expected_cao_named_files = {
        root / "scripts" / "install-cao-kit.sh",
        root / "skills" / "agentic-sdlc-orchestrator" / "references" / "cao-profiles.md",
        root / "skills" / "agentic-sdlc-orchestrator" / "references" / "cao-operations.md",
        *(profiles_dir / name for name in sorted(expected_profile_names)),
    }
    actual_cao_named_files = {
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "tests" not in path.relative_to(root).parts
        and (
            "cao" in path.name.lower()
            or "cao-profiles" in path.relative_to(root).parts
        )
    }
    if actual_cao_named_files != expected_cao_named_files:
        result.error(
            "CAO named-file inventory mismatch: "
            f"expected {sorted(str(path.relative_to(root)) for path in expected_cao_named_files)}, "
            f"got {sorted(str(path.relative_to(root)) for path in actual_cao_named_files)}"
        )

    tombstone_files = expected_cao_named_files
    script = root / "scripts" / "install-cao-kit.sh"
    if not script.is_file() or script.read_text(encoding="utf-8") != "#!/usr/bin/env bash\nset -euo pipefail\n\nprintf '%s\\n' '" + message.rstrip() + "' >&2\nexit 2\n":
        result.error(f"CAO retirement tombstone mismatch: {script.relative_to(root)}")
    for path in sorted(tombstone_files - {script}):
        if not path.is_file() or path.read_text(encoding="utf-8") != message:
            result.error(f"CAO retirement tombstone mismatch: {path.relative_to(root)}")

    wrapper = root / "scripts" / "install-skill-bundle.sh"
    if not wrapper.is_file():
        result.error(f"CAO retirement wrapper missing: {wrapper.relative_to(root)}")
    else:
        wrapper_text = wrapper.read_text(encoding="utf-8")
        guard = "if [ \"${INSTALL_CAO:-0}\" = \"1\" ]; then\n  printf '%s\\n' \"$retirement_message\" >&2\n  exit 2\nfi"
        if guard not in wrapper_text:
            result.error("CAO retirement wrapper must guard before native installer work")

    active_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "tests" not in path.relative_to(root).parts
        and path not in tombstone_files
        and path != root / "scripts" / "validate_bundle.py"
    ]
    forbidden_command = re.compile(r"\b(?:cao|cao-server)\s+[a-z][a-z0-9_-]*\b")
    forbidden_install_flag = "INSTALL_CAO=1"
    wrapper_path = root / "scripts" / "install-skill-bundle.sh"
    allowed_install_flag_lines = {
        root / "README.md": {
            "`INSTALL_CAO=1` is a retired compatibility path and exits 2 before native installation."
        },
        root / "AGENTS.md": {
            "positional `status`, `uninstall`, `self-test`, legacy `--copy`, and retired `INSTALL_CAO=1`"
        },
    }
    for path in sorted(active_files):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if forbidden_command.search(text):
            result.error(f"active CAO command or claim remains: {path.relative_to(root)}")
        if path != wrapper_path:
            allowed_lines = allowed_install_flag_lines.get(path, set())
            if any(
                forbidden_install_flag in line and line.strip() not in allowed_lines
                for line in text.splitlines()
            ):
                result.error(f"active INSTALL_CAO invocation remains: {path.relative_to(root)}")


def validate_policy(root: Path, result: Validation) -> None:
    validate_cao_retirement(root, result)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or ".git" in path.parts:
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
