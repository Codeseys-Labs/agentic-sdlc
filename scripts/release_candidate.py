#!/usr/bin/env python3
"""Build, verify, run, or durably acquire one local unpublished candidate.

The only accepted grammar is:

    release_candidate.py build --output <existing-empty-absolute-physical-dir>
    release_candidate.py verify --archive <absolute-regular-candidate-tar-gz>
    release_candidate.py acquire <the closed policy-defined acquisition grammar>

Verification deliberately never executes code supplied by an archive.  A build runs the
private-runtime canary while its staging tree is still locally controlled; that observation is
recorded as unverified build evidence, never promoted to archive trust at verify time.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import pwd
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
import zlib
from typing import Callable, Mapping, Sequence


SCHEMA_VERSION = "release-candidate/v1"
POLICY_SCHEMA_VERSION = "release-candidate-policy/v1"
PYTHON_VERSION = "3.12.11"
POLICY_RELATIVE = "policy/release-candidate.v1.json"
EXECUTION_POLICY_RELATIVE = "policy/release-candidate-execution.v1.json"
EXECUTION_POLICY_SCHEMA_VERSION = "release-candidate-execution-policy/v1"
ADMISSION_SCHEMA_VERSION = "release-candidate-execution-admission/v1"
CANDIDATE_REPORT_POLICY_RELATIVE = "policy/ccodex-sdlc-read-report.v2.json"
CANDIDATE_REPORT_POLICY_SHA256 = "0667ab351d7ab755f94f4ca74be1d3a6510c0cf7ea30f35ff9a0821e732108d9"
CANDIDATE_REPORT_SCHEMA_VERSION = "ccodex-sdlc-read-report/v2"
CANDIDATE_OBSERVATION_SCHEMA_VERSION = "ccodex-sdlc-candidate-observation/v1"
MANIFEST_NAME = "manifest.json"
INVENTORY_SCOPE = "archive members excluding manifest.json and archive root"
CANARY_OBSERVATION = {
    "runtime_canary": {
        "argv": ["runtime/python/bin/python3.12", "-I", "-B"],
        "state": "passed-unverified",
    }
}
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
ARCHIVE_NAME = re.compile(r"agentic-sdlc-candidate-([0-9a-f]{64})-linux-x64\.tar\.gz\Z")
UNSAFE_MODE_BITS = stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX | 0o022
USTAR_BLOCK = 512
CHUNK = 64 * 1024
GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"
PROCESS_GROUP_WITNESS = {
    "cleanup": "retained",
    "effect_state": "unknown",
    "reason": "process-group-nonconvergence",
    "schema_version": "release-candidate-effect-witness/v1",
}


@dataclass(frozen=True)
class RetainedWitness:
    locator: str
    root_device: int
    root_inode: int
    witness_device: int
    witness_inode: int


class CandidateError(Exception):
    """A stable, content-minimized refusal code."""

    def __init__(self, code: str, retained_witness: RetainedWitness | None = None):
        super().__init__(code)
        self.code = code
        self.retained_witness = retained_witness
        self.witness_locator = retained_witness.locator if retained_witness is not None else None


@dataclass(frozen=True)
class GitTool:
    path: Path
    version: str
    sha256: str


@dataclass(frozen=True)
class SourceEntry:
    mode: int
    oid: str


@dataclass(frozen=True)
class SourceSnapshot:
    root: Path
    commit: str
    tree: str
    epoch: int
    entries: Mapping[str, SourceEntry]
    git: GitTool | None
    test_blobs: Mapping[str, bytes] | None = None


@dataclass(frozen=True)
class RawMember:
    name: str
    kind: str
    mode: int
    size: int
    linkname: str
    mtime: int


@dataclass(frozen=True)
class Publication:
    destination: Path
    device: int
    inode: int
    digest: str


@dataclass(frozen=True)
class ExtractedCandidate:
    private: Path
    root: Path
    archive_sha256: str
    manifest: Mapping[str, object]
    host_source: SourceSnapshot
    host_policy: Mapping[str, object]


def _fail(code: str) -> None:
    raise CandidateError(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        _fail(code)


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    except (TypeError, ValueError):
        _fail("json-noncanonical")
    raise AssertionError("unreachable")


def _duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("json-duplicate")
        result[key] = value
    return result


def _nonfinite(value: str) -> object:
    del value
    _fail("json-nonfinite")
    raise AssertionError("unreachable")


def strict_json_object(raw: bytes, code: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_duplicate_object, parse_constant=_nonfinite)
    except CandidateError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        _fail(code)
    if not isinstance(value, dict):
        _fail(code)
    if raw != canonical_json(value).encode("ascii"):
        _fail("json-noncanonical")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError:
        _fail("file-read")
    return digest.hexdigest()


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(code)
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code)


def _safe_relative_path(value: object, code: str = "path-invalid") -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value or value.startswith("/"):
        _fail(code)
    if unicodedata.normalize("NFC", value) != value:
        _fail(code)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        _fail(code)
    if len(encoded) > 1024 or any(part in {"", ".", ".."} for part in value.split("/")):
        _fail(code)
    return value


def _safe_link_target(value: object, link_path: str, code: str = "link-unsafe") -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value or value.startswith("/"):
        _fail(code)
    if unicodedata.normalize("NFC", value) != value:
        _fail(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail(code)
    parents = link_path.split("/")[:-1]
    for part in value.split("/"):
        if part in {"", "."}:
            _fail(code)
        if part == "..":
            if not parents:
                _fail(code)
            parents.pop()
        else:
            parents.append(part)
    if not parents:
        _fail(code)
    return value


def _policy_paths(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(code)
    result = [_safe_relative_path(item, code) for item in value]
    if result != sorted(result) or len(result) != len(set(result)) or any(any(char in item for char in "*?[]") for item in result):
        _fail(code)
    return result


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail(code)
    return value


def validate_policy(policy: Mapping[str, object]) -> None:
    _exact_keys(policy, {"archive", "canonical_json", "disclosures", "limits", "manifest", "payload", "runtime", "schema_version"}, "policy-keys")
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        _fail("policy-schema")
    if policy.get("canonical_json") != {"allow_nonfinite": False, "ensure_ascii": True, "separators": [",", ":"], "sort_keys": True, "trailing_newline": True}:
        _fail("policy-canonical")
    if policy.get("archive") != {"prefix": "agentic-sdlc-candidate-", "suffix": "-linux-x64.tar.gz"}:
        _fail("policy-archive")
    if policy.get("disclosures") != {"licensing": "incomplete", "provenance": "unverified", "sbom": "absent"}:
        _fail("policy-disclosures")
    limits = _mapping(policy.get("limits"), "policy-limits")
    _exact_keys(limits, {"max_archive_bytes", "max_entries", "max_file_bytes", "max_path_bytes", "max_total_bytes", "max_uncompressed_bytes"}, "policy-limits")
    values = {key: _positive_int(item, "policy-limits") for key, item in limits.items()}
    if not (
        values["max_file_bytes"] <= values["max_total_bytes"] < values["max_uncompressed_bytes"] <= 536_870_912
        and values["max_archive_bytes"] <= 536_870_912
        and values["max_entries"] <= 100_000
        and values["max_path_bytes"] <= 4096
    ):
        _fail("policy-limits")
    manifest = _mapping(policy.get("manifest"), "policy-manifest")
    _exact_keys(manifest, {"artifact_kind", "platform", "product_version", "public_channel", "release_claim", "schema_version", "support_tier"}, "policy-manifest")
    if (
        manifest.get("artifact_kind") != "unpublished-candidate"
        or manifest.get("platform") != "linux-x64"
        or manifest.get("public_channel") is not None
        or manifest.get("release_claim") != "none"
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("support_tier") != "unsupported"
        or not isinstance(manifest.get("product_version"), str)
        or not SEMVER.fullmatch(manifest["product_version"])
    ):
        _fail("policy-manifest")
    payload = _mapping(policy.get("payload"), "policy-payload")
    _exact_keys(payload, {"files", "trees"}, "policy-payload")
    files, trees = _policy_paths(payload.get("files"), "policy-payload"), _policy_paths(payload.get("trees"), "policy-payload")
    if not files or not trees or any(file == tree or file.startswith(tree + "/") for file in files for tree in trees) or any(left.startswith(right + "/") for left in trees for right in trees if left != right):
        _fail("policy-payload")
    runtime = _mapping(policy.get("runtime"), "policy-runtime")
    _exact_keys(runtime, {"destination", "license_paths", "python_executable", "python_version"}, "policy-runtime")
    if runtime.get("destination") != "runtime/python" or runtime.get("python_executable") != "bin/python3.12" or runtime.get("python_version") != PYTHON_VERSION or not _policy_paths(runtime.get("license_paths"), "policy-runtime"):
        _fail("policy-runtime")


def load_policy(path: Path) -> dict[str, object]:
    try:
        policy = strict_json_object(path.read_bytes(), "policy-json")
    except OSError:
        _fail("policy-missing")
    validate_policy(policy)
    return policy


def load_execution_policy(snapshot: SourceSnapshot) -> tuple[dict[str, object], bytes]:
    raw = _snapshot_blob(snapshot, EXECUTION_POLICY_RELATIVE)
    policy = strict_json_object(raw, "execution-policy-json")
    _exact_keys(
        policy,
        {"admission", "commands", "limits", "platform", "projection", "schema_version", "trusted_bash"},
        "execution-policy-keys",
    )
    if policy.get("schema_version") != EXECUTION_POLICY_SCHEMA_VERSION or policy.get("platform") != "linux-x64":
        _fail("execution-policy")
    commands = policy.get("commands")
    expected_commands = [
        ["sdlc", "doctor"], ["sdlc", "doctor", "--json"],
        ["sdlc", "inspect"], ["sdlc", "inspect", "--json"],
        ["sdlc", "recover", "--dry-run"], ["sdlc", "recover", "--dry-run", "--json"],
        ["sdlc", "status"], ["sdlc", "status", "--json"],
    ]
    if commands != expected_commands:
        _fail("execution-policy")
    admission = _mapping(policy.get("admission"), "execution-policy")
    _exact_keys(admission, {"authenticated_files", "schema_version"}, "execution-policy")
    expected_files = [
        "assets/launchers/ccodex.in",
        "policy/ccodex-sdlc-read-report.v2.json",
        EXECUTION_POLICY_RELATIVE,
        POLICY_RELATIVE,
        "scripts/ccodex_sdlc.py",
        "scripts/ccodex_sdlc_readonly.py",
        "scripts/install_operator_tools.py",
        "scripts/install_skill_bundle.py",
    ]
    if admission.get("schema_version") != ADMISSION_SCHEMA_VERSION or admission.get("authenticated_files") != expected_files:
        _fail("execution-policy")
    limits = _mapping(policy.get("limits"), "execution-policy")
    _exact_keys(limits, {"max_child_output_bytes", "max_child_stderr_bytes", "max_seconds", "terminate_grace_seconds"}, "execution-policy")
    if limits != {
        "max_child_output_bytes": 1048576,
        "max_child_stderr_bytes": 65536,
        "max_seconds": 30,
        "terminate_grace_seconds": 3,
    }:
        _fail("execution-policy")
    projection = _mapping(policy.get("projection"), "execution-policy")
    if projection != {"dispatcher": "bin/ccodex", "template": "assets/launchers/ccodex.in"}:
        _fail("execution-policy")
    bash = _mapping(policy.get("trusted_bash"), "execution-policy")
    _exact_keys(bash, {"path", "sha256"}, "execution-policy")
    if bash.get("path") != "/usr/bin/bash" or not isinstance(bash.get("sha256"), str) or not HEX_64.fullmatch(str(bash["sha256"])):
        _fail("execution-policy")
    if raw != canonical_json(policy).encode("ascii"):
        _fail("execution-policy")
    return policy, raw


def validate_candidate_report_policy(policy: Mapping[str, object]) -> None:
    try:
        raw = canonical_json(dict(policy)).encode("ascii")
    except CandidateError:
        _fail("candidate-report-policy")
    if _sha256_bytes(raw) != CANDIDATE_REPORT_POLICY_SHA256:
        _fail("candidate-report-policy")


def load_candidate_report_policy(snapshot: SourceSnapshot) -> tuple[dict[str, object], bytes]:
    raw = _snapshot_blob(snapshot, CANDIDATE_REPORT_POLICY_RELATIVE)
    policy = strict_json_object(raw, "candidate-report-policy")
    validate_candidate_report_policy(policy)
    if raw != canonical_json(policy).encode("ascii"):
        _fail("candidate-report-policy")
    return policy, raw


def _linux_platform_kind(osrelease: str, version: str) -> str:
    evidence = f"{osrelease}\n{version}".casefold()
    if "microsoft" not in evidence and "wsl" not in evidence:
        return "native"
    if "wsl2" in evidence or "microsoft-standard" in evidence:
        return "wsl2"
    return "wsl1"


def _require_linux_x64(read_text: Callable[[Path], str] | None = None) -> str:
    if sys.platform != "linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        _fail("platform-unsupported")
    reader = read_text or (lambda path: path.read_text(encoding="utf-8", errors="replace"))
    try:
        kind = _linux_platform_kind(reader(Path("/proc/sys/kernel/osrelease")), reader(Path("/proc/version")))
    except OSError:
        _fail("platform-unsupported")
    if kind not in {"native", "wsl2"}:
        _fail("platform-unsupported")
    return kind


def _physical_directory(path: Path, code: str) -> Path:
    if not path.is_absolute():
        _fail(code)
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _fail(code)
    if path != resolved or path.is_symlink() or not resolved.is_dir():
        _fail(code)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                _fail(code)
        except OSError:
            _fail(code)
    return resolved


def _safe_output_directory(output: Path, source_root: Path) -> Path:
    resolved = _physical_directory(output, "output-invalid")
    try:
        item = resolved.stat()
        occupied = any(resolved.iterdir())
    except OSError:
        _fail("output-invalid")
    if item.st_uid != os.geteuid() or stat.S_IMODE(item.st_mode) & 0o022:
        _fail("output-owner")
    if occupied:
        _fail("output-not-empty")
    broad = {Path("/"), Path("/tmp"), Path("/var/tmp"), Path.home().resolve(), source_root.parent.resolve()}
    if resolved in broad or resolved.is_relative_to(source_root) or source_root.is_relative_to(resolved):
        _fail("output-boundary")
    return resolved


def source_root_for_script() -> Path:
    try:
        script = Path(__file__).resolve(strict=True)
        root = script.parents[1]
        if (root / "scripts" / "release_candidate.py").resolve(strict=True) != script:
            _fail("source-layout")
    except OSError:
        _fail("source-layout")
    return _physical_directory(root, "source-layout")


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
        "TZ": "UTC",
    }


GIT_EXECUTION_OVERRIDES = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "diff.external=",
    "-c",
    "core.pager=cat",
)


def _system_git(root: Path) -> GitTool:
    candidate_paths = (Path("/usr/bin/git"), Path("/bin/git"))
    chosen: Path | None = None
    for path in candidate_paths:
        try:
            resolved = path.resolve(strict=True)
            item = resolved.stat()
        except OSError:
            continue
        if stat.S_ISREG(item.st_mode) and item.st_uid == 0 and item.st_mode & 0o111 and not stat.S_IMODE(item.st_mode) & 0o022:
            chosen = resolved
            break
    if chosen is None:
        _fail("source-git")
    output = _run_process([str(chosen), "--version"], root, _git_environment(), "source-git")
    version = _single_line(output, "source-git")
    if not version.startswith("git version "):
        _fail("source-git")
    return GitTool(path=chosen, version=version, sha256=_sha256_file(chosen))


def _run_process(arguments: Sequence[str], cwd: Path, environment: Mapping[str, str], code: str) -> bytes:
    try:
        completed = subprocess.run(
            list(arguments),
            check=False,
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        _fail(code)
    if completed.returncode:
        _fail(code)
    return completed.stdout


def _git(tool: GitTool, root: Path, arguments: Sequence[str], code: str = "source-git") -> bytes:
    return _run_process([str(tool.path), "--no-optional-locks", *GIT_EXECUTION_OVERRIDES, "-C", str(root), *arguments], root, _git_environment(), code)


def _single_line(raw: bytes, code: str, *, empty: bool = False) -> str:
    if empty and raw == b"":
        return ""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail(code)
    if not text.endswith("\n") or "\n" in text[:-1] or "\r" in text:
        _fail(code)
    return text[:-1]


def _parse_tree(raw: bytes) -> dict[str, SourceEntry]:
    result: dict[str, SourceEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            head, path_raw = record.split(b"\t", 1)
            mode_raw, kind_raw, oid_raw = head.split(b" ", 2)
            path = _safe_relative_path(path_raw.decode("utf-8"), "source-tree")
            mode, kind, oid = mode_raw.decode("ascii"), kind_raw.decode("ascii"), oid_raw.decode("ascii")
        except (UnicodeDecodeError, ValueError):
            _fail("source-tree")
        if kind != "blob" or mode not in {"100644", "100755", "120000"} or not HEX_40.fullmatch(oid) or path in result:
            _fail("source-tree")
        result[path] = SourceEntry(mode=int(mode, 8), oid=oid)
    return result


def _parse_index(raw: bytes, code: str) -> dict[str, SourceEntry]:
    result: dict[str, SourceEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            head, path_raw = record.split(b"\t", 1)
            mode_raw, oid_raw, stage_raw = head.split(b" ", 2)
            path = _safe_relative_path(path_raw.decode("utf-8"), code)
            mode, oid = mode_raw.decode("ascii"), oid_raw.decode("ascii")
        except (UnicodeDecodeError, ValueError):
            _fail(code)
        if stage_raw != b"0" or mode not in {"100644", "100755", "120000"} or not HEX_40.fullmatch(oid) or path in result:
            _fail(code)
        result[path] = SourceEntry(mode=int(mode, 8), oid=oid)
    return result


def _working_entry_matches(root: Path, path: str, expected: SourceEntry, code: str) -> bool:
    target = root / path
    try:
        before = target.lstat()
    except OSError:
        _fail(code)
    if expected.mode == 0o120000:
        if not stat.S_ISLNK(before.st_mode):
            return False
        try:
            data = os.readlink(target).encode("utf-8")
            after = target.lstat()
        except (OSError, UnicodeEncodeError):
            _fail(code)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            return False
        digest = hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
        return digest == expected.oid
    if not stat.S_ISREG(before.st_mode):
        return False
    mode = 0o100755 if before.st_mode & 0o100 else 0o100644
    if mode != expected.mode:
        return False
    descriptor: int | None = None
    try:
        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns):
            return False
        digest = hashlib.sha1()
        digest.update(f"blob {opened.st_size}\0".encode("ascii"))
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        after = target.lstat()
    except OSError:
        _fail(code)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        return False
    return digest.hexdigest() == expected.oid


def _git_is_clean(tool: GitTool, root: Path, entries: Mapping[str, SourceEntry], code: str) -> bool:
    index = _parse_index(_git(tool, root, ["ls-files", "--stage", "-z"], code), code)
    if index != dict(entries):
        return False
    if _git(tool, root, ["ls-files", "--others", "--exclude-standard", "-z"], code):
        return False
    return all(_working_entry_matches(root, path, entry, code) for path, entry in entries.items())


def admit_source(source_root: Path | None = None) -> SourceSnapshot:
    root = source_root_for_script() if source_root is None else _physical_directory(source_root, "source-layout")
    tool = _system_git(root)
    top = _single_line(_git(tool, root, ["rev-parse", "--show-toplevel"]), "source-git")
    try:
        if Path(top).resolve(strict=True) != root:
            _fail("source-layout")
    except OSError:
        _fail("source-layout")
    if _single_line(_git(tool, root, ["rev-parse", "--show-superproject-working-tree"]), "source-git", empty=True):
        _fail("source-nested")
    worktrees = _git(tool, root, ["worktree", "list", "--porcelain"])
    try:
        roots = [Path(line[9:]).resolve(strict=True) for line in worktrees.decode("utf-8").splitlines() if line.startswith("worktree ")]
    except (OSError, UnicodeDecodeError):
        _fail("source-git")
    if sum(item == root for item in roots) != 1 or any(item != root and item.is_relative_to(root) for item in roots):
        _fail("source-nested")
    commit = _single_line(_git(tool, root, ["rev-parse", "--verify", "HEAD^{commit}"]), "source-git")
    tree = _single_line(_git(tool, root, ["rev-parse", "--verify", "HEAD^{tree}"]), "source-git")
    epoch_text = _single_line(_git(tool, root, ["show", "-s", "--format=%ct", "HEAD"]), "source-git")
    if not HEX_40.fullmatch(commit) or not HEX_40.fullmatch(tree) or not epoch_text.isdecimal():
        _fail("source-git")
    entries = _parse_tree(_git(tool, root, ["ls-tree", "-r", "-z", tree]))
    if not _git_is_clean(tool, root, entries, "source-dirty"):
        _fail("source-dirty")
    return SourceSnapshot(root=root, commit=commit, tree=tree, epoch=int(epoch_text), entries=entries, git=tool)


def source_snapshot_for_testing(root: Path, files: Mapping[str, tuple[int, bytes]], *, commit: str = "a" * 40, tree: str = "b" * 40, epoch: int = 1_700_000_000) -> SourceSnapshot:
    """Compact injected seam for unit tests; CLI builds always use admitted Git objects."""
    entries: dict[str, SourceEntry] = {}
    blobs: dict[str, bytes] = {}
    for path, (mode, data) in files.items():
        safe = _safe_relative_path(path, "source-tree")
        entries[safe] = SourceEntry(mode=mode, oid=_sha256_bytes(data)[:40])
        blobs[safe] = data
    return SourceSnapshot(root=root, commit=commit, tree=tree, epoch=epoch, entries=entries, git=None, test_blobs=blobs)


def _snapshot_blob(snapshot: SourceSnapshot, path: str) -> bytes:
    entry = snapshot.entries.get(path)
    if entry is None:
        _fail("payload-missing")
    if snapshot.test_blobs is not None:
        try:
            return snapshot.test_blobs[path]
        except KeyError:
            _fail("payload-missing")
    if snapshot.git is None:
        _fail("source-git")
    return _git(snapshot.git, snapshot.root, ["cat-file", "blob", entry.oid], "source-git")


def _policy_from_snapshot(snapshot: SourceSnapshot) -> tuple[dict[str, object], bytes]:
    raw = _snapshot_blob(snapshot, POLICY_RELATIVE)
    policy = strict_json_object(raw, "policy-json")
    validate_policy(policy)
    return policy, raw


def _selected_paths(snapshot: SourceSnapshot, policy: Mapping[str, object]) -> list[str]:
    payload = _mapping(policy["payload"], "policy-payload")
    files, trees = _policy_paths(payload["files"], "policy-payload"), _policy_paths(payload["trees"], "policy-payload")
    selected: set[str] = set()
    for path in files:
        if path not in snapshot.entries:
            _fail("payload-missing")
        selected.add(path)
    for tree in trees:
        values = [path for path in snapshot.entries if path.startswith(tree + "/")]
        if not values:
            _fail("payload-missing")
        selected.update(values)
    return sorted(selected)


def _mode_for_file(mode: int) -> int:
    return 0o755 if mode == 0o100755 else 0o644


def _copy_authored_payload(snapshot: SourceSnapshot, policy: Mapping[str, object], destination: Path) -> None:
    for relative in _selected_paths(snapshot, policy):
        entry = snapshot.entries[relative]
        target = destination / relative
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            _fail("payload-copy")
        blob = _snapshot_blob(snapshot, relative)
        if entry.mode in {0o100644, 0o100755}:
            try:
                with target.open("xb") as handle:
                    handle.write(blob)
                os.chmod(target, _mode_for_file(entry.mode))
            except OSError:
                _fail("payload-copy")
        elif entry.mode == 0o120000:
            try:
                target_text = blob.decode("utf-8")
                os.symlink(_safe_link_target(target_text, relative, "payload-link"), target)
            except (OSError, UnicodeDecodeError):
                _fail("payload-copy")
        else:
            _fail("payload-copy")


def _final_source_recheck(snapshot: SourceSnapshot) -> None:
    if snapshot.git is None:
        return
    commit = _single_line(_git(snapshot.git, snapshot.root, ["rev-parse", "--verify", "HEAD^{commit}"], "source-drift"), "source-drift")
    tree = _single_line(_git(snapshot.git, snapshot.root, ["rev-parse", "--verify", "HEAD^{tree}"], "source-drift"), "source-drift")
    if commit != snapshot.commit or tree != snapshot.tree or not _git_is_clean(snapshot.git, snapshot.root, snapshot.entries, "source-drift"):
        _fail("source-drift")


def _runtime_license_paths(policy: Mapping[str, object]) -> list[str]:
    return _policy_paths(_mapping(policy["runtime"], "policy-runtime")["license_paths"], "policy-runtime")


def _validate_tree_links(root: Path, code: str) -> None:
    def visit(directory: Path) -> None:
        try:
            children = list(os.scandir(directory))
        except OSError:
            _fail(code)
        for child in children:
            path = Path(child.path)
            try:
                item = path.lstat()
            except OSError:
                _fail(code)
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(item.st_mode):
                visit(path)
            elif stat.S_ISREG(item.st_mode):
                continue
            elif stat.S_ISLNK(item.st_mode):
                try:
                    target = _safe_link_target(os.readlink(path), relative, code)
                    if not (path.parent / target).resolve(strict=True).is_relative_to(root):
                        _fail(code)
                except OSError:
                    _fail(code)
            else:
                _fail(code)
    visit(root)


def _validate_runtime_root(root: Path, license_paths: Sequence[str] | None = None) -> None:
    try:
        physical = root.resolve(strict=True)
        executable = physical / "bin" / "python3.12"
        if not executable.is_file() or executable.is_symlink():
            _fail("runtime-missing")
        for relative in license_paths or ["lib/python3.12/LICENSE.txt"]:
            path = physical / relative
            if not path.is_file() or path.is_symlink():
                _fail("runtime-missing")
    except OSError:
        _fail("runtime-missing")
    _validate_tree_links(physical, "runtime-missing")


def _resolve_base_runtime(policy: Mapping[str, object]) -> Path:
    if sys.version_info[:3] != (3, 12, 11):
        _fail("runtime-missing")
    try:
        executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve(strict=True)
        prefix = Path(sys.base_prefix).resolve(strict=True)
    except OSError:
        _fail("runtime-missing")
    if executable != prefix / "bin" / "python3.12" or not prefix.name.startswith("cpython-3.12.11-linux-x86_64") or prefix.parent.name != "python":
        _fail("runtime-missing")
    _validate_runtime_root(prefix, _runtime_license_paths(policy))
    return prefix


def _normal_mode(path: Path, kind: str) -> int:
    if kind in {"dir", "symlink"}:
        return 0o755
    try:
        return 0o755 if path.lstat().st_mode & 0o100 else 0o644
    except OSError:
        _fail("file-read")
    raise AssertionError("unreachable")


def _copy_regular(source: Path, destination: Path, mode: int, code: str) -> None:
    try:
        with source.open("rb") as reader, destination.open("xb") as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
        os.chmod(destination, mode)
    except OSError:
        _fail(code)


def _copy_runtime_tree(source: Path, destination: Path, policy: Mapping[str, object] | None = None) -> None:
    _validate_runtime_root(source, _runtime_license_paths(policy) if policy is not None else None)
    def copy_directory(source_dir: Path, target_dir: Path) -> None:
        try:
            target_dir.mkdir(mode=0o755)
            os.chmod(target_dir, 0o755)
            children = sorted(os.scandir(source_dir), key=lambda child: child.name)
        except OSError:
            _fail("runtime-copy")
        for child in children:
            source_path, target_path = Path(child.path), target_dir / child.name
            try:
                item = source_path.lstat()
            except OSError:
                _fail("runtime-copy")
            relative = source_path.relative_to(source).as_posix()
            if stat.S_ISDIR(item.st_mode):
                copy_directory(source_path, target_path)
            elif stat.S_ISREG(item.st_mode):
                _copy_regular(source_path, target_path, _normal_mode(source_path, "file"), "runtime-copy")
            elif stat.S_ISLNK(item.st_mode):
                try:
                    os.symlink(_safe_link_target(os.readlink(source_path), relative, "runtime-copy"), target_path)
                except OSError:
                    _fail("runtime-copy")
            else:
                _fail("runtime-copy")
    copy_directory(source, destination)


def _staging_runtime_canary(candidate_root: Path, policy: Mapping[str, object]) -> None:
    runtime = candidate_root / str(_mapping(policy["runtime"], "policy-runtime")["destination"])
    executable = runtime / "bin" / "python3.12"
    home = candidate_root.parent / "canary-home"
    try:
        home.mkdir(mode=0o700)
    except OSError:
        _fail("runtime-canary")
    program = (
        "import os,sys; expected=os.path.realpath(sys.argv[1]); "
        "ok=(sys.version_info[:3]==(3,12,11) and os.path.realpath(sys.prefix)==expected and "
        "os.path.realpath(sys.base_prefix)==expected and os.path.realpath(sys.executable).startswith(expected+os.sep) and "
        "os.environ.get('PATH')=='' and not any(k.startswith(('PYTHON','UV_','MISE_','GIT_')) for k in os.environ) and "
        "all((not os.path.isabs(p)) or os.path.realpath(p).startswith(expected+os.sep) for p in sys.path)); "
        "print('ok' if ok else 'no'); raise SystemExit(0 if ok else 1)"
    )
    environment = {"HOME": str(home), "LANG": "C", "LC_ALL": "C", "PATH": ""}
    try:
        completed = subprocess.run([str(executable), "-I", "-B", "-c", program, str(runtime)], check=False, cwd=candidate_root.parent, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        _fail("runtime-canary")
    if completed.returncode != 0 or completed.stdout != b"ok\n":
        _fail("runtime-canary")


def _inventory_for_tree(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    def visit(directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda child: child.name)
        except OSError:
            _fail("file-read")
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST_NAME:
                continue
            try:
                item = path.lstat()
            except OSError:
                _fail("file-read")
            if stat.S_ISDIR(item.st_mode):
                entries.append({"mode": 0o755, "path": relative, "size": 0, "type": "dir"})
                visit(path)
            elif stat.S_ISREG(item.st_mode):
                entries.append({"mode": _normal_mode(path, "file"), "path": relative, "sha256": _sha256_file(path), "size": item.st_size, "type": "file"})
            elif stat.S_ISLNK(item.st_mode):
                try:
                    target = _safe_link_target(os.readlink(path), relative)
                except OSError:
                    _fail("file-read")
                entries.append({"mode": 0o755, "path": relative, "size": len(target.encode("utf-8")), "target": target, "type": "symlink"})
            else:
                _fail("file-special")
    visit(root)
    entries.sort(key=lambda item: str(item["path"]))
    return entries


def _entry_digest(entries: Sequence[Mapping[str, object]]) -> str:
    return _sha256_bytes(canonical_json(list(entries)).encode("ascii"))


def _expected_authored_inventory(snapshot: SourceSnapshot, policy: Mapping[str, object]) -> list[dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    for relative in _selected_paths(snapshot, policy):
        parts = relative.split("/")
        for index in range(1, len(parts)):
            directory = "/".join(parts[:index])
            entries[directory] = {"mode": 0o755, "path": directory, "size": 0, "type": "dir"}
        source = snapshot.entries[relative]
        blob = _snapshot_blob(snapshot, relative)
        if source.mode in {0o100644, 0o100755}:
            entries[relative] = {
                "mode": _mode_for_file(source.mode),
                "path": relative,
                "sha256": _sha256_bytes(blob),
                "size": len(blob),
                "type": "file",
            }
        elif source.mode == 0o120000:
            try:
                target = _safe_link_target(blob.decode("utf-8"), relative, "source-tree")
            except UnicodeDecodeError:
                _fail("source-tree")
            entries[relative] = {
                "mode": 0o755,
                "path": relative,
                "size": len(target.encode("utf-8")),
                "target": target,
                "type": "symlink",
            }
        else:
            _fail("source-tree")
    return [entries[path] for path in sorted(entries)]


def _expected_runtime_inventory(runtime_root: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = [
        {"mode": 0o755, "path": "runtime", "size": 0, "type": "dir"},
        {"mode": 0o755, "path": "runtime/python", "size": 0, "type": "dir"},
    ]
    for entry in _inventory_for_tree(runtime_root):
        result.append({**entry, "path": f"runtime/python/{entry['path']}"})
    result.sort(key=lambda item: str(item["path"]))
    return result


def _authenticate_executable_candidate(
    manifest: Mapping[str, object],
    host_source: SourceSnapshot,
    host_policy: Mapping[str, object],
    runtime_root: Path,
) -> tuple[str, str]:
    source = _mapping(manifest.get("source"), "execution-source")
    if source.get("commit") != host_source.commit or source.get("tree") != host_source.tree or source.get("epoch") != host_source.epoch:
        _fail("execution-source-mismatch")
    inventory = _validate_inventory(manifest.get("inventory"), _mapping(host_policy["limits"], "policy-limits"))
    authored = [entry for entry in inventory if not _is_runtime(str(entry["path"]))]
    runtime = [entry for entry in inventory if _is_runtime(str(entry["path"]))]
    expected_authored = _expected_authored_inventory(host_source, host_policy)
    if authored != expected_authored:
        _fail("execution-payload-mismatch")
    expected_runtime = _expected_runtime_inventory(runtime_root)
    if runtime != expected_runtime:
        _fail("execution-runtime-mismatch")
    return _entry_digest(authored), _entry_digest(runtime)


def _trusted_bash(execution_policy: Mapping[str, object]) -> tuple[Path, str]:
    configured = _mapping(execution_policy["trusted_bash"], "execution-policy")
    bash = Path(str(configured["path"]))
    try:
        item = bash.lstat()
    except OSError:
        _fail("execution-bash")
    if (
        bash != Path("/usr/bin/bash")
        or not stat.S_ISREG(item.st_mode)
        or item.st_uid != 0
        or stat.S_IMODE(item.st_mode) & 0o022
        or not item.st_mode & 0o111
    ):
        _fail("execution-bash")
    digest = _sha256_file(bash)
    if digest != configured["sha256"]:
        _fail("execution-bash")
    return bash, digest


def _is_runtime(path: str) -> bool:
    return path == "runtime" or path.startswith("runtime/")


def _manifest_digests(entries: Sequence[Mapping[str, object]]) -> tuple[str, str, str]:
    return (
        _entry_digest(entries),
        _entry_digest([entry for entry in entries if not _is_runtime(str(entry["path"]))]),
        _entry_digest([entry for entry in entries if _is_runtime(str(entry["path"]))]),
    )


def _validate_inventory(value: object, limits: Mapping[str, object]) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) > int(limits["max_entries"]):
        _fail("manifest-inventory")
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    normalized: set[str] = set()
    previous = ""
    regular_total = 0
    kinds: dict[str, str] = {}
    for item in value:
        entry = _mapping(item, "manifest-inventory")
        kind = entry.get("type")
        expected = {"mode", "path", "size", "type"}
        if kind == "file":
            expected.add("sha256")
        elif kind == "symlink":
            expected.add("target")
        elif kind != "dir":
            _fail("manifest-inventory")
        _exact_keys(entry, expected, "manifest-inventory")
        path = _safe_relative_path(entry.get("path"), "manifest-inventory")
        if len(path.encode("utf-8")) > int(limits["max_path_bytes"]) or path in seen or unicodedata.normalize("NFC", path) in normalized or (previous and path <= previous):
            _fail("manifest-inventory")
        previous, seen, normalized = path, seen | {path}, normalized | {unicodedata.normalize("NFC", path)}
        mode, size = entry.get("mode"), entry.get("size")
        if isinstance(mode, bool) or not isinstance(mode, int) or isinstance(size, bool) or not isinstance(size, int) or size < 0 or mode & UNSAFE_MODE_BITS:
            _fail("manifest-inventory")
        if kind == "dir":
            if mode != 0o755 or size != 0:
                _fail("manifest-mode")
        elif kind == "file":
            if mode not in {0o644, 0o755} or size > int(limits["max_file_bytes"]) or not isinstance(entry.get("sha256"), str) or not HEX_64.fullmatch(entry["sha256"]):
                _fail("manifest-inventory")
            regular_total += size
        else:
            if mode != 0o755 or size != len(str(entry.get("target", "")).encode("utf-8")):
                _fail("manifest-mode")
            _safe_link_target(entry.get("target"), path, "manifest-inventory")
        kinds[path] = str(kind)
        entries.append(dict(entry))
    if regular_total > int(limits["max_total_bytes"]):
        _fail("archive-total")
    for path in kinds:
        parts = path.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            if kinds.get("/".join(parts[:index])) != "dir":
                _fail("manifest-inventory")
    return entries


def _manifest_identity(source: Mapping[str, object], policy_sha: str, product_version: str, content: str, payload: str, runtime: str) -> str:
    return _sha256_bytes(canonical_json({"content_sha256": content, "payload_sha256": payload, "platform": "linux-x64", "policy_sha256": policy_sha, "product_version": product_version, "runtime_sha256": runtime, "schema_version": SCHEMA_VERSION, "source": dict(source)}).encode("ascii"))


def validate_manifest(value: object, policy: Mapping[str, object]) -> dict[str, object]:
    validate_policy(policy)
    manifest = _mapping(value, "manifest-json")
    _exact_keys(manifest, {"archive_root", "artifact_kind", "build_observation", "candidate_id", "content_sha256", "disclosures", "inventory", "inventory_scope", "payload_sha256", "platform", "policy_sha256", "product_version", "public_channel", "release_claim", "runtime", "schema_version", "source", "support_tier"}, "manifest-keys")
    policy_manifest = _mapping(policy["manifest"], "policy-manifest")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("artifact_kind") != policy_manifest["artifact_kind"] or manifest.get("platform") != policy_manifest["platform"] or manifest.get("product_version") != policy_manifest["product_version"] or manifest.get("public_channel") is not None or manifest.get("support_tier") != policy_manifest["support_tier"] or manifest.get("release_claim") != policy_manifest["release_claim"] or manifest.get("disclosures") != policy["disclosures"] or manifest.get("inventory_scope") != INVENTORY_SCOPE or manifest.get("build_observation") != CANARY_OBSERVATION
    ):
        _fail("manifest-label")
    for field in ("candidate_id", "content_sha256", "payload_sha256", "policy_sha256"):
        if not isinstance(manifest.get(field), str) or not HEX_64.fullmatch(manifest[field]):
            _fail("manifest-identity")
    source = _mapping(manifest.get("source"), "manifest-source")
    _exact_keys(source, {"commit", "epoch", "tree"}, "manifest-source")
    if not isinstance(source.get("commit"), str) or not HEX_40.fullmatch(source["commit"]) or not isinstance(source.get("tree"), str) or not HEX_40.fullmatch(source["tree"]) or isinstance(source.get("epoch"), bool) or not isinstance(source.get("epoch"), int) or source["epoch"] < 0:
        _fail("manifest-source")
    runtime = _mapping(manifest.get("runtime"), "manifest-runtime")
    _exact_keys(runtime, {"path", "python_version", "sha256"}, "manifest-runtime")
    policy_runtime = _mapping(policy["runtime"], "policy-runtime")
    if runtime.get("path") != policy_runtime["destination"] or runtime.get("python_version") != policy_runtime["python_version"] or not isinstance(runtime.get("sha256"), str) or not HEX_64.fullmatch(runtime["sha256"]):
        _fail("manifest-runtime")
    entries = _validate_inventory(manifest.get("inventory"), _mapping(policy["limits"], "policy-limits"))
    content, payload, runtime_digest = _manifest_digests(entries)
    if manifest["content_sha256"] != content or manifest["payload_sha256"] != payload or runtime["sha256"] != runtime_digest:
        _fail("manifest-digest")
    identifier = _manifest_identity(source, str(manifest["policy_sha256"]), str(manifest["product_version"]), content, payload, runtime_digest)
    if manifest["candidate_id"] != identifier or manifest["archive_root"] != f"agentic-sdlc-candidate-{identifier}-linux-x64":
        _fail("manifest-identity")
    return manifest


def valid_manifest_fixture() -> dict[str, object]:
    entries: list[dict[str, object]] = [
        {"mode": 0o755, "path": "runtime", "size": 0, "type": "dir"},
        {"mode": 0o755, "path": "runtime/python", "size": 0, "type": "dir"},
        {"mode": 0o755, "path": "runtime/python/bin", "size": 0, "type": "dir"},
        {"mode": 0o755, "path": "runtime/python/bin/python3.12", "sha256": _sha256_bytes(b""), "size": 0, "type": "file"},
    ]
    content, payload, runtime = _manifest_digests(entries)
    source: dict[str, object] = {"commit": "0" * 40, "epoch": 0, "tree": "1" * 40}
    policy_sha = "2" * 64
    identifier = _manifest_identity(source, policy_sha, "0.7.3", content, payload, runtime)
    return {"archive_root": f"agentic-sdlc-candidate-{identifier}-linux-x64", "artifact_kind": "unpublished-candidate", "build_observation": CANARY_OBSERVATION, "candidate_id": identifier, "content_sha256": content, "disclosures": {"licensing": "incomplete", "provenance": "unverified", "sbom": "absent"}, "inventory": entries, "inventory_scope": INVENTORY_SCOPE, "payload_sha256": payload, "platform": "linux-x64", "policy_sha256": policy_sha, "product_version": "0.7.3", "public_channel": None, "release_claim": "none", "runtime": {"path": "runtime/python", "python_version": PYTHON_VERSION, "sha256": runtime}, "schema_version": SCHEMA_VERSION, "source": source, "support_tier": "unsupported"}


def _build_manifest(snapshot: SourceSnapshot, policy: Mapping[str, object], root: Path, policy_bytes: bytes) -> dict[str, object]:
    entries = _inventory_for_tree(root)
    content, payload, runtime = _manifest_digests(entries)
    source: dict[str, object] = {"commit": snapshot.commit, "epoch": snapshot.epoch, "tree": snapshot.tree}
    product = str(_mapping(policy["manifest"], "policy-manifest")["product_version"])
    policy_sha = _sha256_bytes(policy_bytes)
    identifier = _manifest_identity(source, policy_sha, product, content, payload, runtime)
    return {"archive_root": f"agentic-sdlc-candidate-{identifier}-linux-x64", "artifact_kind": "unpublished-candidate", "build_observation": CANARY_OBSERVATION, "candidate_id": identifier, "content_sha256": content, "disclosures": dict(_mapping(policy["disclosures"], "policy-disclosures")), "inventory": entries, "inventory_scope": INVENTORY_SCOPE, "payload_sha256": payload, "platform": "linux-x64", "policy_sha256": policy_sha, "product_version": product, "public_channel": None, "release_claim": "none", "runtime": {"path": "runtime/python", "python_version": PYTHON_VERSION, "sha256": runtime}, "schema_version": SCHEMA_VERSION, "source": source, "support_tier": "unsupported"}


def _ustar_text(value: str, code: str) -> bytes:
    try:
        return value.encode("ascii")
    except UnicodeEncodeError:
        _fail(code)
    raise AssertionError("unreachable")


def _assert_ustar_name(name: str, code: str) -> None:
    encoded = _ustar_text(name, code)
    if len(encoded) <= 100:
        return
    for index in range(len(encoded) - 1, -1, -1):
        if encoded[index:index + 1] == b"/" and index <= 155 and len(encoded) - index - 1 <= 100:
            return
    _fail(code)


def _assert_ustar_member(name: str, linkname: str = "") -> None:
    _assert_ustar_name(name, "ustar-unrepresentable")
    if linkname and len(_ustar_text(linkname, "ustar-unrepresentable")) > 100:
        _fail("ustar-unrepresentable")


def _tar_info(name: str, path: Path, epoch: int) -> tarfile.TarInfo:
    try:
        item = path.lstat()
    except OSError:
        _fail("archive-write")
    info = tarfile.TarInfo(name)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = epoch
    if stat.S_ISDIR(item.st_mode):
        info.type, info.mode, info.size = tarfile.DIRTYPE, 0o755, 0
    elif stat.S_ISREG(item.st_mode):
        info.type, info.mode, info.size = tarfile.REGTYPE, _normal_mode(path, "file"), item.st_size
    elif stat.S_ISLNK(item.st_mode):
        try:
            target = _safe_link_target(os.readlink(path), name.split("/", 1)[1], "archive-write")
        except OSError:
            _fail("archive-write")
        info.type, info.mode, info.size, info.linkname = tarfile.SYMTYPE, 0o755, 0, target
    else:
        _fail("archive-write")
    _assert_ustar_member(name, info.linkname)
    return info


def _write_ustar_archive(candidate_root: Path, manifest: Mapping[str, object], stage_archive: Path, policy: Mapping[str, object]) -> None:
    inventory = _validate_inventory(manifest["inventory"], _mapping(policy["limits"], "policy-limits"))
    archive_root, epoch = str(manifest["archive_root"]), int(_mapping(manifest["source"], "manifest-source")["epoch"])
    _assert_ustar_member(archive_root)
    raw_archive = stage_archive.with_suffix(".ustar")
    try:
        # tarfile pads to its 10 KiB record size.  The candidate grammar is
        # intentionally narrower: every archive has exactly the two required
        # terminating zero records, and no trailing transport padding.
        with raw_archive.open("xb") as raw:
            with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as packed:
                root_info = tarfile.TarInfo(archive_root)
                root_info.type, root_info.mode, root_info.size = tarfile.DIRTYPE, 0o755, 0
                root_info.uid = root_info.gid = 0
                root_info.uname = root_info.gname = ""
                root_info.mtime = epoch
                packed.addfile(root_info)
                for relative in sorted([MANIFEST_NAME, *(str(item["path"]) for item in inventory)]):
                    source = candidate_root / relative
                    info = _tar_info(f"{archive_root}/{relative}", source, epoch)
                    if info.isreg():
                        with source.open("rb") as handle:
                            packed.addfile(info, handle)
                    else:
                        packed.addfile(info)
            raw.flush()
            os.fsync(raw.fileno())
        with raw_archive.open("r+b") as raw:
            size = raw.seek(0, io.SEEK_END)
            while size >= USTAR_BLOCK:
                raw.seek(size - USTAR_BLOCK)
                if any(raw.read(USTAR_BLOCK)):
                    break
                size -= USTAR_BLOCK
            if size == 0:
                _fail("archive-write")
            raw.truncate(size + 2 * USTAR_BLOCK)
            raw.flush()
            os.fsync(raw.fileno())
        with stage_archive.open("xb") as output, raw_archive.open("rb") as input_stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as compressed:
                shutil.copyfileobj(input_stream, compressed, CHUNK)
            output.flush()
            os.fsync(output.fileno())
    except (OSError, tarfile.TarError):
        _fail("archive-write")
    finally:
        try:
            raw_archive.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            _fail("archive-write")


def _sync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    try:
        os.lseek(descriptor, 0, io.SEEK_SET)
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        os.lseek(descriptor, 0, io.SEEK_SET)
    except OSError:
        _fail("file-read")
    return digest.hexdigest()


def _rollback_destination(output: Path, name: str, device: int, inode: int, digest: str) -> bool:
    directory_fd: int | None = None
    archive_fd: int | None = None
    try:
        directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        archive_fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), dir_fd=directory_fd)
        item = os.fstat(archive_fd)
        if not stat.S_ISREG(item.st_mode) or item.st_dev != device or item.st_ino != inode or _sha256_descriptor(archive_fd) != digest:
            return False
        os.close(archive_fd)
        archive_fd = None
        os.unlink(name, dir_fd=directory_fd)
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            return False
        except FileNotFoundError:
            os.fsync(directory_fd)
            return True
    except (OSError, CandidateError):
        return False
    finally:
        if archive_fd is not None:
            os.close(archive_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _rollback_publication(publication: Publication) -> bool:
    return _rollback_destination(publication.destination.parent, publication.destination.name, publication.device, publication.inode, publication.digest)


def _publish_no_replace(stage_archive: Path, output: Path, archive_name: str) -> Publication:
    destination = output / archive_name
    linked = False
    source_item: os.stat_result | None = None
    digest = ""
    try:
        source_item = stage_archive.lstat()
        if not stat.S_ISREG(source_item.st_mode):
            _fail("archive-publish")
        digest = _sha256_file(stage_archive)
        os.link(stage_archive, destination)
        linked = True
        destination_item = destination.lstat()
        if destination_item.st_dev != source_item.st_dev or destination_item.st_ino != source_item.st_ino or not stat.S_ISREG(destination_item.st_mode):
            _fail("archive-publish")
        publication = Publication(destination=destination, device=source_item.st_dev, inode=source_item.st_ino, digest=digest)
    except FileExistsError:
        _fail("output-conflict")
    except (OSError, CandidateError):
        if linked and source_item is not None and not _rollback_destination(output, archive_name, source_item.st_dev, source_item.st_ino, digest):
            _fail("archive-unknown-effect")
        _fail("archive-publish")
    try:
        _sync_file(destination)
        _sync_directory(output)
    except OSError:
        if not _rollback_publication(publication):
            _fail("archive-unknown-effect")
        _fail("archive-publish")
    return publication


def _private_stage(output: Path) -> Path:
    try:
        return Path(tempfile.mkdtemp(prefix=".release-candidate-stage-", dir=output))
    except OSError:
        _fail("stage-create")
    raise AssertionError("unreachable")


def _remove_stage(stage: Path) -> None:
    shutil.rmtree(stage)


def build_candidate(output: Path, *, snapshot: SourceSnapshot | None = None, policy: Mapping[str, object] | None = None, runtime_root: Path | None = None, on_publish: Callable[[str], None] | None = None) -> Path:
    _require_linux_x64()
    source = admit_source() if snapshot is None else snapshot
    source_root = _physical_directory(source.root, "source-layout")
    if source_root != source.root:
        _fail("source-layout")
    snapshot_policy, policy_bytes = _policy_from_snapshot(source)
    selected_policy = snapshot_policy if policy is None else dict(policy)
    validate_policy(selected_policy)
    if policy is not None and policy_bytes != canonical_json(selected_policy).encode("ascii"):
        _fail("policy-drift")
    admitted_output = _safe_output_directory(output, source_root)
    stage = _private_stage(admitted_output)
    publication: Publication | None = None
    try:
        candidate_root = stage / "candidate"
        candidate_root.mkdir(mode=0o755)
        _copy_authored_payload(source, selected_policy, candidate_root)
        runtime_destination = candidate_root / "runtime" / "python"
        runtime_destination.parent.mkdir(mode=0o755)
        base_runtime = _resolve_base_runtime(selected_policy) if runtime_root is None else runtime_root
        _copy_runtime_tree(base_runtime, runtime_destination, selected_policy)
        _staging_runtime_canary(candidate_root, selected_policy)
        manifest = _build_manifest(source, selected_policy, candidate_root, policy_bytes)
        validate_manifest(manifest, selected_policy)
        try:
            (candidate_root / MANIFEST_NAME).write_bytes(canonical_json(manifest).encode("ascii"))
            os.chmod(candidate_root / MANIFEST_NAME, 0o644)
            candidate_root.rename(stage / str(manifest["archive_root"]))
        except OSError:
            _fail("stage-create")
        stage_archive = stage / "candidate.tar.gz"
        _write_ustar_archive(stage / str(manifest["archive_root"]), manifest, stage_archive, selected_policy)
        _final_source_recheck(source)
        archive_name = f"agentic-sdlc-candidate-{manifest['candidate_id']}-linux-x64.tar.gz"
        publication = _publish_no_replace(stage_archive, admitted_output, archive_name)
        # _publish_no_replace() already computed this digest from stage_archive
        # (via _sha256_file) before hardlinking it into place, so publication.digest
        # is the published file's digest without a second, unprotected read of it.
        # Implementation Decision 9: a caller that re-reads the archive after this
        # point is reading a file whose durable publish has already completed, so a
        # read failure there can never be honestly reported as a clean refusal.
        if on_publish is not None:
            on_publish(publication.digest)
        return publication.destination
    except CandidateError:
        if publication is not None and publication.destination.exists() and not _rollback_publication(publication):
            _fail("archive-unknown-effect")
        raise
    finally:
        if stage.exists():
            try:
                _remove_stage(stage)
            except OSError:
                if publication is not None and publication.destination.exists() and not _rollback_publication(publication):
                    _fail("archive-unknown-effect")
                _fail("stage-unknown-effect")


def _archive_name(path: Path) -> str:
    if not path.is_absolute() or not ARCHIVE_NAME.fullmatch(path.name):
        _fail("archive-path")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _fail("archive-path")
    if path != resolved:
        _fail("archive-path")
    return path.name


def _archive_identity(item: os.stat_result) -> tuple[int, int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns


def _pin_archive(archive: Path, private: Path, limit: int, *, after_copy: Callable[[], None] | None = None) -> tuple[Path, str]:
    pinned = private / "candidate.tar.gz"
    source_fd: int | None = None
    destination_fd: int | None = None
    try:
        source_fd = os.open(archive, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid() or before.st_size <= 0 or before.st_size > limit:
            _fail("archive-path")
        destination_fd = os.open(pinned, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0), 0o600)
        total = 0
        digest = hashlib.sha256()
        while chunk := os.read(source_fd, CHUNK):
            total += len(chunk)
            if total > limit:
                _fail("archive-path")
            digest.update(chunk)
            _write_all(destination_fd, chunk)
        if total != before.st_size:
            _fail("archive-mutated")
        os.fsync(destination_fd)
        if after_copy is not None:
            after_copy()
        if _archive_identity(os.fstat(source_fd)) != _archive_identity(before):
            _fail("archive-mutated")
        return pinned, digest.hexdigest()
    except CandidateError:
        raise
    except OSError:
        _fail("archive-invalid")
    finally:
        if destination_fd is not None:
            os.close(destination_fd)
        if source_fd is not None:
            os.close(source_fd)


def _inflate_gzip(archive: Path, private: Path, limit: int) -> Path:
    raw = private / "candidate.ustar"
    try:
        descriptor = os.open(archive, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        destination = os.open(raw, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        _fail("archive-invalid")
    total = 0
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as source, os.fdopen(destination, "wb", closefd=True) as target:
            if source.read(len(GZIP_HEADER)) != GZIP_HEADER:
                _fail("archive-gzip")
            source.seek(0)
            inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
            complete = False
            pending = b""
            while True:
                chunk = pending or source.read(CHUNK)
                pending = b""
                if not chunk:
                    break
                remaining = limit - total
                inflated = inflater.decompress(chunk, remaining + 1)
                total += len(inflated)
                if total > limit:
                    _fail("archive-uncompressed")
                target.write(inflated)
                if inflater.eof:
                    if inflater.unused_data or source.read(1):
                        _fail("archive-gzip")
                    complete = True
                    break
                pending = inflater.unconsumed_tail
                if pending == chunk and not inflated:
                    _fail("archive-invalid")
            if not complete:
                _fail("archive-invalid")
            target.flush()
            os.fsync(target.fileno())
    except CandidateError:
        raise
    except (OSError, zlib.error):
        _fail("archive-invalid")
    return raw


def _octal(field: bytes, code: str) -> int:
    if len(field) < 2 or field[-1:] != b"\0" or any(byte < ord("0") or byte > ord("7") for byte in field[:-1]):
        _fail(code)
    try:
        value = int(field[:-1], 8)
    except ValueError:
        _fail(code)
    if field != f"{value:0{len(field) - 1}o}".encode("ascii") + b"\0":
        _fail(code)
    return value


def _checksum(field: bytes, code: str) -> int:
    if len(field) != 8 or field[-2:] != b"\0 " or any(byte < ord("0") or byte > ord("7") for byte in field[:6]):
        _fail(code)
    try:
        return int(field[:6], 8)
    except ValueError:
        _fail(code)
    raise AssertionError("unreachable")


def _ustar_string(field: bytes, code: str) -> str:
    value, separator, rest = field.partition(b"\0")
    if separator and any(rest):
        _fail(code)
    try:
        return value.decode("ascii")
    except UnicodeDecodeError:
        _fail(code)
    raise AssertionError("unreachable")


def _preflight_ustar(path: Path, policy: Mapping[str, object], expected_root: str) -> list[RawMember]:
    limits = _mapping(policy["limits"], "policy-limits")
    try:
        length = path.stat().st_size
        handle = path.open("rb")
    except OSError:
        _fail("archive-preflight")
    if length < 2 * USTAR_BLOCK or length % USTAR_BLOCK:
        _fail("archive-preflight")
    members: list[RawMember] = []
    names: set[str] = set()
    normalized: set[str] = set()
    regular_total = 0
    with handle:
        offset = 0
        while True:
            header = handle.read(USTAR_BLOCK)
            if len(header) != USTAR_BLOCK:
                _fail("archive-preflight")
            offset += USTAR_BLOCK
            if not any(header):
                second = handle.read(USTAR_BLOCK)
                if len(second) != USTAR_BLOCK or any(second) or handle.read(1):
                    _fail("archive-preflight")
                break
            if len(members) >= int(limits["max_entries"]):
                _fail("archive-count")
            if header[257:263] != b"ustar\x00" or header[263:265] != b"00":
                _fail("archive-ustar")
            claimed = _checksum(header[148:156], "archive-ustar")
            checked = bytearray(header)
            checked[148:156] = b" " * 8
            if sum(checked) != claimed:
                _fail("archive-ustar")
            mode, uid, gid = _octal(header[100:108], "archive-ustar"), _octal(header[108:116], "archive-ustar"), _octal(header[116:124], "archive-ustar")
            size, mtime = _octal(header[124:136], "archive-ustar"), _octal(header[136:148], "archive-ustar")
            if uid != 0 or gid != 0 or any(header[265:297]) or any(header[297:329]) or any(header[329:345]) or any(header[500:512]):
                _fail("archive-metadata")
            # USTAR directory names are conventionally stored with one trailing
            # slash.  Normalize that representation only after accepting the
            # typeflag, so a GNU longname record cannot masquerade as a path.
            flag = header[156:157]
            if flag == b"0":
                kind = "file"
            elif flag == b"5":
                kind = "dir"
            elif flag == b"2":
                kind = "symlink"
            else:
                _fail("archive-ustar")
            name_part, prefix = _ustar_string(header[:100], "archive-ustar"), _ustar_string(header[345:500], "archive-ustar")
            name = f"{prefix}/{name_part}" if prefix else name_part
            if kind == "dir" and name.endswith("/"):
                name = name[:-1]
            elif kind == "dir" or name.endswith("/"):
                _fail("archive-metadata")
            _safe_relative_path(name, "archive-path")
            if name != expected_root and not name.startswith(expected_root + "/"):
                _fail("archive-path")
            if name == expected_root and kind != "dir":
                _fail("archive-root")
            if len(name.encode("utf-8")) > int(limits["max_path_bytes"]) or name in names or unicodedata.normalize("NFC", name) in normalized:
                _fail("archive-duplicate")
            names.add(name)
            normalized.add(unicodedata.normalize("NFC", name))
            linkname = _ustar_string(header[157:257], "archive-ustar")
            if mode & UNSAFE_MODE_BITS:
                _fail("archive-mode")
            if kind == "file":
                if linkname:
                    _fail("archive-metadata")
                if mode not in {0o644, 0o755} or size > int(limits["max_file_bytes"]):
                    _fail("archive-mode")
                regular_total += size
                if regular_total > int(limits["max_total_bytes"]):
                    _fail("archive-total")
            elif kind == "dir":
                if mode != 0o755 or size != 0 or linkname:
                    _fail("archive-mode")
            else:
                if mode != 0o755 or size != 0:
                    _fail("archive-mode")
                relative = name.removeprefix(expected_root + "/")
                if not relative:
                    _fail("archive-root")
                _safe_link_target(linkname, relative, "archive-link")
            blocks = (size + USTAR_BLOCK - 1) // USTAR_BLOCK
            if offset + blocks * USTAR_BLOCK > length:
                _fail("archive-preflight")
            if size:
                handle.seek(size, io.SEEK_CUR)
                padding = handle.read(blocks * USTAR_BLOCK - size)
                if any(padding):
                    _fail("archive-metadata")
            offset += blocks * USTAR_BLOCK
            members.append(RawMember(name=name, kind=kind, mode=mode, size=size, linkname=linkname, mtime=mtime))
    return members


def _member_kind(member: tarfile.TarInfo) -> str:
    if member.isfile():
        return "file"
    if member.isdir():
        return "dir"
    if member.issym():
        return "symlink"
    _fail("archive-special")
    raise AssertionError("unreachable")


def _read_member(archive: tarfile.TarFile, member: tarfile.TarInfo, limit: int, code: str) -> bytes:
    try:
        handle = archive.extractfile(member)
        if handle is None:
            _fail(code)
        with handle:
            result = handle.read(limit + 1)
    except (OSError, tarfile.TarError):
        _fail(code)
    if len(result) > limit or len(result) != member.size:
        _fail(code)
    return result


def _hash_member(archive: tarfile.TarFile, member: tarfile.TarInfo, expected_size: int) -> str:
    digest, total = hashlib.sha256(), 0
    try:
        handle = archive.extractfile(member)
        if handle is None:
            _fail("archive-content")
        with handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                total += len(chunk)
    except (OSError, tarfile.TarError):
        _fail("archive-content")
    if total != expected_size:
        _fail("archive-content")
    return digest.hexdigest()


def _validate_layout(entries: Sequence[Mapping[str, object]], policy: Mapping[str, object]) -> None:
    payload = _mapping(policy["payload"], "policy-payload")
    files, trees = _policy_paths(payload["files"], "policy-payload"), _policy_paths(payload["trees"], "policy-payload")
    index = {str(item["path"]): item for item in entries}
    for item in entries:
        path = str(item["path"])
        allowed = path == "runtime" or path.startswith("runtime/") or path in files or any(path == tree or path.startswith(tree + "/") for tree in trees)
        if not allowed:
            _fail("archive-layout")
    for path in files:
        if index.get(path, {}).get("type") != "file":
            _fail("archive-layout")
    for tree in trees:
        if index.get(tree, {}).get("type") != "dir":
            _fail("archive-layout")
    required = ["runtime", "runtime/python", "runtime/python/bin", "runtime/python/bin/python3.12", POLICY_RELATIVE, "LICENSE", "NOTICE"]
    required.extend(f"runtime/python/{path}" for path in _runtime_license_paths(policy))
    for path in required:
        if path not in index:
            _fail("archive-layout")
    required_directories = {"runtime", "runtime/python", "runtime/python/bin", *trees}
    for license_path in _runtime_license_paths(policy):
        parts = ("runtime/python/" + license_path).split("/")[:-1]
        required_directories.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))
    if any(index.get(path, {}).get("type") != "dir" for path in required_directories):
        _fail("archive-layout")
    executable = index["runtime/python/bin/python3.12"]
    if executable.get("type") != "file" or executable.get("mode") != 0o755 or index[POLICY_RELATIVE].get("type") != "file":
        _fail("archive-layout")
    for path in _runtime_license_paths(policy):
        if index[f"runtime/python/{path}"].get("type") != "file":
            _fail("archive-layout")


def _archive_admission(raw_path: Path, archive_name: str, host_policy: Mapping[str, object], host_policy_bytes: bytes) -> tuple[dict[str, object], dict[str, tarfile.TarInfo], bytes]:
    match = ARCHIVE_NAME.fullmatch(archive_name)
    if not match:
        _fail("archive-path")
    candidate_id = match.group(1)
    root = f"agentic-sdlc-candidate-{candidate_id}-linux-x64"
    raw_members = _preflight_ustar(raw_path, host_policy, root)
    try:
        archive = tarfile.open(raw_path, mode="r:")
    except (OSError, tarfile.TarError):
        _fail("archive-invalid")
    with archive:
        try:
            members = archive.getmembers()
        except tarfile.TarError:
            _fail("archive-invalid")
        if len(members) != len(raw_members):
            _fail("archive-preflight")
        member_map: dict[str, tarfile.TarInfo] = {}
        raw_map: dict[str, RawMember] = {}
        for member, raw in zip(members, raw_members):
            member_kind = _member_kind(member)
            member_name = member.name[:-1] if member_kind == "dir" and member.name.endswith("/") else member.name
            if member_name != raw.name or member_kind != raw.kind or stat.S_IMODE(member.mode) != raw.mode or member.size != raw.size or member.linkname != raw.linkname or member.mtime != raw.mtime or member.pax_headers:
                _fail("archive-preflight")
            if member_name in member_map:
                _fail("archive-duplicate")
            member_map[member_name] = member
            raw_map[member_name] = raw
        manifest_member = member_map.get(f"{root}/{MANIFEST_NAME}")
        policy_member = member_map.get(f"{root}/{POLICY_RELATIVE}")
        root_member = member_map.get(root)
        if root_member is None or _member_kind(root_member) != "dir" or root_member.size != 0 or stat.S_IMODE(root_member.mode) != 0o755 or root_member.linkname or manifest_member is None or policy_member is None:
            _fail("archive-root")
        if root_member.uid != 0 or root_member.gid != 0 or root_member.uname or root_member.gname or root_member.devmajor or root_member.devminor:
            _fail("archive-root")
        if manifest_member is None or policy_member is None:
            _fail("archive-manifest")
        manifest_header = raw_map.get(f"{root}/{MANIFEST_NAME}")
        if manifest_header is None or manifest_header.kind != "file" or manifest_header.mode != 0o644 or manifest_header.linkname:
            _fail("archive-manifest")
        limits = _mapping(host_policy["limits"], "policy-limits")
        manifest_raw = _read_member(archive, manifest_member, int(limits["max_file_bytes"]), "archive-manifest")
        embedded_policy = _read_member(archive, policy_member, int(limits["max_file_bytes"]), "archive-policy")
        if embedded_policy != host_policy_bytes:
            _fail("archive-policy")
        manifest = strict_json_object(manifest_raw, "archive-manifest")
        validate_manifest(manifest, host_policy)
        if manifest["candidate_id"] != candidate_id or manifest["archive_root"] != root or manifest["policy_sha256"] != _sha256_bytes(host_policy_bytes):
            _fail("archive-manifest")
        source = _mapping(manifest["source"], "manifest-source")
        if any(member.mtime != source["epoch"] for member in members):
            _fail("archive-metadata")
        inventory = _validate_inventory(manifest["inventory"], limits)
        _validate_layout(inventory, host_policy)
        expected = {str(item["path"]): item for item in inventory}
        present = {name[len(root) + 1:] for name in member_map if name != root and name != f"{root}/{MANIFEST_NAME}"}
        if present != set(expected):
            _fail("archive-inventory")
        by_relative: dict[str, tarfile.TarInfo] = {}
        for relative, entry in expected.items():
            member = member_map.get(f"{root}/{relative}")
            if member is None or _member_kind(member) != entry["type"] or stat.S_IMODE(member.mode) != entry["mode"]:
                _fail("archive-inventory")
            if entry["type"] == "file":
                if member.size != entry["size"] or _hash_member(archive, member, int(entry["size"])) != entry["sha256"]:
                    _fail("archive-content")
            elif entry["type"] == "symlink" and member.linkname != entry["target"]:
                _fail("archive-link")
            by_relative[relative] = member
        return manifest, by_relative, manifest_raw


def _open_dir_at(root_fd: int, parts: Sequence[str], *, create: bool) -> int:
    current = os.dup(root_fd)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        for part in parts:
            try:
                child = os.open(part, flags, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=current)
                child = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = child
        return current
    except OSError:
        os.close(current)
        _fail("extract-path")
    raise AssertionError("unreachable")


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        try:
            written = os.write(descriptor, data[offset:])
        except OSError:
            _fail("extract-write")
        if written <= 0:
            _fail("extract-write")
        offset += written


def _extract_file(archive: tarfile.TarFile, member: tarfile.TarInfo, root_fd: int, relative: str, mode: int) -> None:
    parts = relative.split("/")
    parent = _open_dir_at(root_fd, parts[:-1], create=False)
    try:
        target = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=parent)
    except OSError:
        os.close(parent)
        _fail("extract-write")
    try:
        handle = archive.extractfile(member)
        if handle is None:
            _fail("extract-write")
        with handle:
            while chunk := handle.read(1024 * 1024):
                _write_all(target, chunk)
        os.fchmod(target, mode)
    except (OSError, tarfile.TarError):
        _fail("extract-write")
    finally:
        os.close(target)
        os.close(parent)


def _extract_bytes(root_fd: int, relative: str, data: bytes, mode: int) -> None:
    parts = relative.split("/")
    parent = _open_dir_at(root_fd, parts[:-1], create=False)
    try:
        target = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=parent)
        try:
            _write_all(target, data)
            os.fchmod(target, mode)
        finally:
            os.close(target)
    except OSError:
        _fail("extract-write")
    finally:
        os.close(parent)


def _extract_link(root_fd: int, relative: str, target: str) -> None:
    parts = relative.split("/")
    parent = _open_dir_at(root_fd, parts[:-1], create=False)
    try:
        os.symlink(target, parts[-1], dir_fd=parent)
        if not stat.S_ISLNK(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False).st_mode):
            _fail("extract-write")
    except OSError:
        _fail("extract-write")
    finally:
        os.close(parent)


def _manual_extract(raw_path: Path, manifest: Mapping[str, object], members: Mapping[str, tarfile.TarInfo], manifest_raw: bytes, policy: Mapping[str, object], private: Path) -> Path:
    root = private / str(manifest["archive_root"])
    try:
        root.mkdir(mode=0o755)
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        archive = tarfile.open(raw_path, mode="r:")
    except (OSError, tarfile.TarError):
        _fail("extract-create")
    inventory = _validate_inventory(manifest["inventory"], _mapping(policy["limits"], "policy-limits"))
    try:
        for entry in sorted((entry for entry in inventory if entry["type"] == "dir"), key=lambda item: (str(item["path"]).count("/"), str(item["path"]))):
            descriptor = _open_dir_at(root_fd, str(entry["path"]).split("/"), create=True)
            try:
                os.fchmod(descriptor, 0o755)
            finally:
                os.close(descriptor)
        _extract_bytes(root_fd, MANIFEST_NAME, manifest_raw, 0o644)
        for entry in inventory:
            relative = str(entry["path"])
            if entry["type"] == "file":
                _extract_file(archive, members[relative], root_fd, relative, int(entry["mode"]))
            elif entry["type"] == "symlink":
                _extract_link(root_fd, relative, str(entry["target"]))
        return root
    finally:
        archive.close()
        os.close(root_fd)


def _recompute_extracted(root: Path, manifest: Mapping[str, object]) -> None:
    if _inventory_for_tree(root) != manifest["inventory"]:
        _fail("extract-drift")


def _cleanup_verify_private(private: Path) -> None:
    try:
        shutil.rmtree(private)
    except OSError:
        _fail("verify-stage-unknown-effect")
    try:
        private.lstat()
    except FileNotFoundError:
        return
    except OSError:
        _fail("verify-stage-unknown-effect")
    _fail("verify-stage-unknown-effect")


def _cleanup_run_private(private: Path) -> None:
    try:
        shutil.rmtree(private)
    except OSError:
        _fail("run-stage-unknown-effect")
    try:
        private.lstat()
    except FileNotFoundError:
        return
    except OSError:
        _fail("run-stage-unknown-effect")
    _fail("run-stage-unknown-effect")


def _validated_system_tmp() -> Path:
    parent = Path("/tmp")
    try:
        identity = parent.lstat()
    except OSError:
        _fail("extract-create")
    if (
        not stat.S_ISDIR(identity.st_mode)
        or stat.S_ISLNK(identity.st_mode)
        or stat.S_IMODE(identity.st_mode) != 0o1777
        or identity.st_uid != 0
    ):
        _fail("extract-create")
    return parent


def _retain_process_group_witness(private: Path) -> RetainedWitness:
    witness = private / "effect-state.json"
    root_fd: int | None = None
    witness_fd: int | None = None
    try:
        root_before = private.lstat()
        if (
            not stat.S_ISDIR(root_before.st_mode)
            or stat.S_ISLNK(root_before.st_mode)
            or stat.S_IMODE(root_before.st_mode) != 0o700
            or root_before.st_uid != os.geteuid()
        ):
            _fail("run-stage-unknown-effect")
        root_fd = os.open(
            private,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        root_open = os.fstat(root_fd)
        if (root_open.st_dev, root_open.st_ino) != (root_before.st_dev, root_before.st_ino):
            _fail("run-stage-unknown-effect")
        witness_fd = os.open(
            witness.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=root_fd,
        )
        payload = canonical_json(PROCESS_GROUP_WITNESS).encode("ascii")
        offset = 0
        while offset < len(payload):
            written = os.write(witness_fd, payload[offset:])
            if written <= 0:
                _fail("run-stage-unknown-effect")
            offset += written
        os.fsync(witness_fd)
        witness_open = os.fstat(witness_fd)
        if (
            not stat.S_ISREG(witness_open.st_mode)
            or stat.S_IMODE(witness_open.st_mode) != 0o600
            or witness_open.st_uid != os.geteuid()
            or witness_open.st_nlink != 1
        ):
            _fail("run-stage-unknown-effect")
        os.fsync(root_fd)
    except OSError:
        _fail("run-stage-unknown-effect")
    finally:
        if witness_fd is not None:
            os.close(witness_fd)
        if root_fd is not None:
            os.close(root_fd)
    try:
        root_after = private.lstat()
        witness_after = witness.lstat()
    except OSError:
        _fail("run-stage-unknown-effect")
    if (
        (root_after.st_dev, root_after.st_ino) != (root_before.st_dev, root_before.st_ino)
        or not stat.S_ISDIR(root_after.st_mode)
        or stat.S_ISLNK(root_after.st_mode)
        or (witness_after.st_dev, witness_after.st_ino)
        != (witness_open.st_dev, witness_open.st_ino)
        or not stat.S_ISREG(witness_after.st_mode)
        or stat.S_ISLNK(witness_after.st_mode)
        or stat.S_IMODE(witness_after.st_mode) != 0o600
        or witness_after.st_uid != os.geteuid()
        or witness_after.st_nlink != 1
    ):
        _fail("run-stage-unknown-effect")
    return RetainedWitness(
        locator=str(witness),
        root_device=root_after.st_dev,
        root_inode=root_after.st_ino,
        witness_device=witness_after.st_dev,
        witness_inode=witness_after.st_ino,
    )


def _public_witness_locator(retained: RetainedWitness | None) -> str | None:
    if retained is None:
        return None
    witness = Path(retained.locator)
    private = witness.parent
    root_fd: int | None = None
    witness_fd: int | None = None
    try:
        if (
            not witness.is_absolute()
            or witness.name != "effect-state.json"
            or private.parent != _validated_system_tmp()
            or not private.name.startswith(".release-candidate-run-")
        ):
            return None
        root_identity = private.lstat()
        witness_identity = witness.lstat()
    except (CandidateError, OSError):
        return None
    if (
        not stat.S_ISDIR(root_identity.st_mode)
        or stat.S_ISLNK(root_identity.st_mode)
        or stat.S_IMODE(root_identity.st_mode) != 0o700
        or root_identity.st_uid != os.geteuid()
        or (root_identity.st_dev, root_identity.st_ino)
        != (retained.root_device, retained.root_inode)
        or not stat.S_ISREG(witness_identity.st_mode)
        or stat.S_ISLNK(witness_identity.st_mode)
        or stat.S_IMODE(witness_identity.st_mode) != 0o600
        or witness_identity.st_uid != os.geteuid()
        or witness_identity.st_nlink != 1
        or (witness_identity.st_dev, witness_identity.st_ino)
        != (retained.witness_device, retained.witness_inode)
    ):
        return None
    expected = canonical_json(PROCESS_GROUP_WITNESS).encode("ascii")
    try:
        root_fd = os.open(
            private,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        root_open = os.fstat(root_fd)
        if (root_open.st_dev, root_open.st_ino) != (
            retained.root_device,
            retained.root_inode,
        ):
            return None
        witness_fd = os.open(
            witness.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        witness_open = os.fstat(witness_fd)
        if (
            not stat.S_ISREG(witness_open.st_mode)
            or stat.S_IMODE(witness_open.st_mode) != 0o600
            or witness_open.st_uid != os.geteuid()
            or witness_open.st_nlink != 1
            or (witness_open.st_dev, witness_open.st_ino)
            != (retained.witness_device, retained.witness_inode)
        ):
            return None
        observed = bytearray()
        while len(observed) <= len(expected):
            chunk = os.read(witness_fd, len(expected) + 1 - len(observed))
            if not chunk:
                break
            observed.extend(chunk)
        if bytes(observed) != expected:
            return None
    except OSError:
        return None
    finally:
        if witness_fd is not None:
            os.close(witness_fd)
        if root_fd is not None:
            os.close(root_fd)
    return retained.locator


def _render_candidate_dispatcher(root: Path) -> tuple[Path, str]:
    template = root / "assets" / "launchers" / "ccodex.in"
    try:
        source = template.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _fail("execution-dispatcher")
    rendered = (
        source.replace("@CANDIDATE_READONLY_PROFILE@", "true")
        .replace("@CANONICAL_LAUNCHER@", "''")
        .replace("@CANONICAL_ROOT@", "''")
        .replace("@PINNED_OCX@", "''")
        .replace("@PINNED_JQ@", "''")
        .replace("@PINNED_UV@", "''")
        .replace("@PINNED_SDLC_PYTHON@", "''")
    )
    if "@CANDIDATE_" in rendered or "@CANONICAL_" in rendered or "@PINNED_" in rendered:
        _fail("execution-dispatcher")
    dispatcher = root / "bin" / "ccodex"
    try:
        dispatcher.parent.mkdir(mode=0o755)
        dispatcher.write_text(rendered, encoding="utf-8")
        os.chmod(dispatcher, 0o755)
    except OSError:
        _fail("execution-dispatcher")
    return dispatcher, _sha256_file(dispatcher)


def _root_identity(root: Path) -> tuple[int, int]:
    try:
        item = root.lstat()
    except OSError:
        _fail("execution-root")
    if not stat.S_ISDIR(item.st_mode) or root.is_symlink() or root.resolve(strict=True) != root:
        _fail("execution-root")
    return item.st_dev, item.st_ino


def _admission_record(
    root: Path,
    archive_sha256: str,
    manifest: Mapping[str, object],
    execution_policy: Mapping[str, object],
    command: Sequence[str],
    dispatcher_sha256: str,
    bash_sha256: str,
    authored_inventory_sha256: str,
    runtime_inventory_sha256: str,
) -> dict[str, object]:
    device, inode = _root_identity(root)
    authenticated = _mapping(execution_policy["admission"], "execution-policy")["authenticated_files"]
    assert isinstance(authenticated, list)
    file_digests = {relative: _sha256_file(root / str(relative)) for relative in authenticated}
    source = _mapping(manifest["source"], "manifest-source")
    python = root / "runtime" / "python" / "bin" / "python3.12"
    return {
        "archive_sha256": archive_sha256,
        "authenticated_files": file_digests,
        "authored_inventory_sha256": authored_inventory_sha256,
        "bash_sha256": bash_sha256,
        "candidate_id": manifest["candidate_id"],
        "command": list(command),
        "dispatcher_sha256": dispatcher_sha256,
        "manifest_sha256": _sha256_file(root / MANIFEST_NAME),
        "parent_pid": os.getpid(),
        "python_sha256": _sha256_file(python),
        "root": str(root),
        "root_device": device,
        "root_inode": inode,
        "runtime_inventory_sha256": runtime_inventory_sha256,
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "source_commit": source["commit"],
        "source_epoch": source["epoch"],
        "source_tree": source["tree"],
    }


def _recheck_execution_root(root: Path, admission: Mapping[str, object]) -> None:
    device, inode = _root_identity(root)
    if device != admission["root_device"] or inode != admission["root_inode"]:
        _fail("execution-root-drift")
    authenticated = admission.get("authenticated_files")
    if not isinstance(authenticated, dict):
        _fail("execution-root-drift")
    for relative, expected in authenticated.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or _sha256_file(root / relative) != expected:
            _fail("execution-root-drift")
    if (
        _sha256_file(root / MANIFEST_NAME) != admission["manifest_sha256"]
        or _sha256_file(root / "bin" / "ccodex") != admission["dispatcher_sha256"]
        or _sha256_file(root / "runtime" / "python" / "bin" / "python3.12") != admission["python_sha256"]
    ):
        _fail("execution-root-drift")


def _candidate_environment() -> dict[str, str]:
    try:
        home = Path(pwd.getpwuid(os.geteuid()).pw_dir).resolve(strict=True)
    except (KeyError, OSError):
        _fail("execution-environment")
    return {
        "HOME": str(home),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "",
        "TZ": "UTC",
    }


def _process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except OSError:
        _fail("execution-group-unknown-effect")
    return True


def _wait_process_group_absent(process_group: int, deadline: float) -> bool:
    while time.monotonic() < deadline:
        if not _process_group_exists(process_group):
            return True
        time.sleep(0.02)
    return not _process_group_exists(process_group)


def _signal_process_group(process_group: int, signum: int) -> None:
    if not _process_group_exists(process_group):
        return
    try:
        os.killpg(process_group, signum)
    except ProcessLookupError:
        return
    except OSError:
        _fail("execution-group-unknown-effect")


def _converge_process_group(process: subprocess.Popen[bytes], process_group: int, grace: int) -> None:
    term_deadline = time.monotonic() + grace
    _signal_process_group(process_group, signal.SIGTERM)
    try:
        process.wait(timeout=max(0.0, term_deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        pass
    if _wait_process_group_absent(process_group, term_deadline):
        if process.poll() is None:
            _fail("execution-group-unknown-effect")
        return

    kill_deadline = time.monotonic() + grace
    _signal_process_group(process_group, signal.SIGKILL)
    try:
        process.wait(timeout=max(0.0, kill_deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        _fail("execution-group-unknown-effect")
    if not _wait_process_group_absent(process_group, kill_deadline) or process.poll() is None:
        _fail("execution-group-unknown-effect")


def _supervise_candidate(
    dispatcher: Path,
    command: Sequence[str],
    external_admission: Mapping[str, object],
    execution_policy: Mapping[str, object],
) -> tuple[int, bytes, bytes, int]:
    del external_admission
    limits = _mapping(execution_policy["limits"], "execution-policy")
    process: subprocess.Popen[bytes] | None = None
    process_group: int | None = None
    convergence_attempted = False
    group_converged = False
    previous_handlers: dict[int, object] = {}
    forwarded: list[int] = []
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_total = 0
    stderr_total = 0
    try:
        def converge_group() -> None:
            nonlocal convergence_attempted, group_converged
            if process is None or process_group is None:
                return
            convergence_attempted = True
            _converge_process_group(
                process, process_group, int(limits["terminate_grace_seconds"])
            )
            group_converged = True

        def forward(signum: int, _frame: object) -> None:
            forwarded.append(signum)
            if process_group is not None:
                try:
                    os.killpg(process_group, signum)
                except ProcessLookupError:
                    pass

        handled_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        for signum in handled_signals:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, forward)
        try:
            process = subprocess.Popen(
                [str(dispatcher), *command],
                cwd=dispatcher.parent.parent,
                env=_candidate_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:
            _fail("execution-start")
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, handled_signals)
        try:
            process_group = process.pid
            for queued_signal in tuple(forwarded):
                _signal_process_group(process_group, queued_signal)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        assert process.stdout is not None and process.stderr is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        deadline = time.monotonic() + int(limits["max_seconds"])
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    converge_group()
                    _fail("execution-timeout")
                for key, _events in selector.select(timeout=min(remaining, 0.25)):
                    try:
                        chunk = os.read(key.fileobj.fileno(), CHUNK)
                    except OSError:
                        converge_group()
                        _fail("execution-child-output")
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "stdout":
                        stdout_total += len(chunk)
                        if stdout_total > int(limits["max_child_output_bytes"]):
                            converge_group()
                            _fail("execution-child-output")
                        stdout_chunks.append(chunk)
                    else:
                        stderr_total += len(chunk)
                        if stderr_total > int(limits["max_child_stderr_bytes"]):
                            converge_group()
                            _fail("execution-child-output")
                        stderr_chunks.append(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                converge_group()
                _fail("execution-timeout")
            result = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            converge_group()
            _fail("execution-timeout")
        finally:
            selector.close()
        assert process_group is not None
        if _process_group_exists(process_group):
            converge_group()
            _fail("execution-descendant")
        group_converged = True
        if result < 0:
            return 128 + (-result), b"".join(stdout_chunks), b"".join(stderr_chunks), process.pid
        if forwarded and result == 0:
            return 128 + forwarded[-1], b"".join(stdout_chunks), b"".join(stderr_chunks), process.pid
        return result, b"".join(stdout_chunks), b"".join(stderr_chunks), process.pid
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        try:
            if process is not None and not group_converged and not convergence_attempted:
                converge_group()
        finally:
            if process is not None:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()


def _report_object(value: object, expected: Sequence[str], code: str) -> dict[str, object]:
    result = _mapping(value, code)
    _exact_keys(result, set(expected), code)
    return result


def _report_string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(code)
    return value


def _validate_report_finding(value: object, fields: Mapping[str, object], vocab: Mapping[str, object]) -> dict[str, object]:
    finding = _report_object(value, fields["finding"], "candidate-observation")  # type: ignore[arg-type]
    if (
        finding.get("code") not in vocab["finding_codes"]  # type: ignore[operator]
        or finding.get("component") not in vocab["finding_components"]  # type: ignore[operator]
        or not all(isinstance(finding.get(key), str) and finding.get(key) for key in ("message", "path"))
    ):
        _fail("candidate-observation")
    return finding


def _validate_report_recovery(value: object, fields: Mapping[str, object], vocab: Mapping[str, object]) -> dict[str, object]:
    recovery = _report_object(value, fields["recovery_item"], "candidate-observation")  # type: ignore[arg-type]
    if (
        recovery.get("action") not in vocab["recovery_actions"]  # type: ignore[operator]
        or recovery.get("component") not in {"operator-tools", "bundle"}
        or recovery.get("state") not in vocab["recovery_item_states"]  # type: ignore[operator]
        or not isinstance(recovery.get("path"), str)
        or not recovery["path"]
    ):
        _fail("candidate-observation")
    return recovery


def _validate_report_projection(value: object, fields: Mapping[str, object], vocab: Mapping[str, object]) -> dict[str, object]:
    projection = _report_object(value, fields["bundle"], "candidate-observation")  # type: ignore[arg-type]
    if projection.get("state") not in vocab["component_states"]:  # type: ignore[operator]
        _fail("candidate-observation")
    paths = _report_string_list(projection.get("state_paths"), "candidate-observation")
    if paths != sorted(set(paths)):
        _fail("candidate-observation")
    entries = projection.get("entries")
    findings = projection.get("findings")
    recovery = projection.get("recovery")
    if not isinstance(entries, list) or not isinstance(findings, list) or not isinstance(recovery, list):
        _fail("candidate-observation")
    for entry_value in entries:
        entry = _report_object(entry_value, fields["projection_entry"], "candidate-observation")  # type: ignore[arg-type]
        if (
            entry.get("state") not in vocab["entry_states"]  # type: ignore[operator]
            or not all(isinstance(entry.get(key), str) and entry.get(key) for key in ("name", "path"))
        ):
            _fail("candidate-observation")
    if entries != sorted(entries, key=lambda item: (item["path"], item["name"])):
        _fail("candidate-observation")
    for finding in findings:
        _validate_report_finding(finding, fields, vocab)
    if findings != sorted(findings, key=lambda item: (item["component"], item["path"], item["code"], item["message"])):
        _fail("candidate-observation")
    for item in recovery:
        _validate_report_recovery(item, fields, vocab)
    if recovery != sorted(recovery, key=lambda item: (item["component"], item["path"], item["action"])):
        _fail("candidate-observation")
    return projection


def _projection_overall_state(operator_tools: Mapping[str, object], bundle: Mapping[str, object]) -> str:
    states = {operator_tools["state"], bundle["state"]}
    if "unreadable" in states:
        return "unreadable"
    if "blocked" in states:
        return "blocked"
    if "degraded" in states:
        return "degraded"
    if states == {"absent"}:
        return "absent"
    return "healthy"


def _validate_candidate_observation(
    raw: bytes,
    policy: Mapping[str, object],
    manifest: Mapping[str, object],
    command: Sequence[str],
    admission: Mapping[str, object],
    process_pid: int,
) -> dict[str, object]:
    observation = strict_json_object(raw, "candidate-observation")
    _exact_keys(
        observation,
        {
            "authority", "bundle", "command", "findings", "future_dimensions", "identity",
            "operator_tools", "overall", "recovery", "runtime", "schema_version",
        },
        "candidate-observation",
    )
    if (
        observation.get("schema_version") != CANDIDATE_OBSERVATION_SCHEMA_VERSION
        or observation.get("authority") != "unadmitted-subordinate"
    ):
        _fail("candidate-observation")
    fields = _mapping(policy["field_vocabularies"], "candidate-report-policy")
    vocab = _mapping(policy["vocabularies"], "candidate-report-policy")
    verb = str(command[1])
    dry_run = verb == "recover"
    observed_command = _report_object(observation.get("command"), fields["command"], "candidate-observation")  # type: ignore[arg-type]
    if observed_command != {"dry_run": dry_run, "verb": verb}:
        _fail("candidate-observation")
    identity = _report_object(
        observation.get("identity"),
        ["candidate_id", "dispatcher_sha256", "parent_process_id", "process_id", "root_device", "root_inode"],
        "candidate-observation",
    )
    if identity != {
        "candidate_id": manifest["candidate_id"],
        "dispatcher_sha256": admission["dispatcher_sha256"],
        "parent_process_id": os.getpid(),
        "process_id": process_pid,
        "root_device": admission["root_device"],
        "root_inode": admission["root_inode"],
    }:
        _fail("candidate-observation")
    runtime = _report_object(observation.get("runtime"), fields["runtime"], "candidate-observation")  # type: ignore[arg-type]
    if runtime != {
        "interpreter": "runtime/python/bin/python3.12",
        "inventory_sha256": admission["runtime_inventory_sha256"],
        "isolated": True,
        "state": "admitted",
        "version": PYTHON_VERSION,
    }:
        _fail("candidate-observation")
    operator_tools = _validate_report_projection(observation.get("operator_tools"), fields, vocab)
    bundle = _validate_report_projection(observation.get("bundle"), fields, vocab)
    recovery = _report_object(observation.get("recovery"), fields["recovery"], "candidate-observation")  # type: ignore[arg-type]
    proposals = recovery.get("proposals")
    if (
        recovery.get("effect") != "none"
        or recovery.get("state") not in vocab["recovery_states"]  # type: ignore[operator]
        or not isinstance(proposals, list)
    ):
        _fail("candidate-observation")
    for proposal in proposals:
        _validate_report_recovery(proposal, fields, vocab)
    expected_proposals = sorted(
        [*operator_tools["recovery"], *bundle["recovery"]],  # type: ignore[misc]
        key=lambda item: (item["component"], item["path"], item["action"]),
    )
    expected_recovery_state = "proposed" if dry_run and expected_proposals else "pending" if expected_proposals else "not-needed"
    if proposals != expected_proposals or recovery["state"] != expected_recovery_state:
        _fail("candidate-observation")
    future = _report_object(observation.get("future_dimensions"), fields["future_dimensions"], "candidate-observation")  # type: ignore[arg-type]
    if future != {"activation": "unsupported", "release": "unpublished", "waves": "unsupported"}:
        _fail("candidate-observation")
    findings = observation.get("findings")
    if not isinstance(findings, list):
        _fail("candidate-observation")
    for finding in findings:
        _validate_report_finding(finding, fields, vocab)
    expected_findings = sorted(
        [*operator_tools["findings"], *bundle["findings"]],  # type: ignore[misc]
        key=lambda item: (item["component"], item["path"], item["code"], item["message"]),
    )
    if findings != expected_findings:
        _fail("candidate-observation")
    overall = _report_object(observation.get("overall"), fields["overall"], "candidate-observation")  # type: ignore[arg-type]
    if overall != {"exit_class": "ok", "state": _projection_overall_state(operator_tools, bundle)}:
        _fail("candidate-observation")
    return observation


def _candidate_final_report(
    policy: Mapping[str, object],
    manifest: Mapping[str, object],
    admission: Mapping[str, object],
    observation: Mapping[str, object],
) -> dict[str, object]:
    source = _mapping(manifest["source"], "manifest-source")
    disclosures = _mapping(manifest["disclosures"], "manifest-label")
    report = {
        "schema_version": CANDIDATE_REPORT_SCHEMA_VERSION,
        "command": observation["command"],
        "distribution": {
            "candidate_id": manifest["candidate_id"],
            "licensing": disclosures["licensing"],
            "lifecycle": "ephemeral",
            "product_version": manifest["product_version"],
            "provenance": disclosures["provenance"],
            "public_channel": None,
            "publication": "unpublished",
            "release_claim": manifest["release_claim"],
            "release_topology_adr_status": "proposed",
            "sbom": disclosures["sbom"],
            "source_commit": source["commit"],
            "source_tree": source["tree"],
            "support_tier": manifest["support_tier"],
        },
        "admission": {
            "archive_sha256": admission["archive_sha256"],
            "bash_sha256": admission["bash_sha256"],
            "dispatcher_sha256": admission["dispatcher_sha256"],
            "root_identity": f"{admission['root_device']}:{admission['root_inode']}",
            "schema_version": ADMISSION_SCHEMA_VERSION,
            "state": "admitted",
        },
        "runtime": observation["runtime"],
        "operator_tools": observation["operator_tools"],
        "bundle": observation["bundle"],
        "recovery": observation["recovery"],
        "future_dimensions": observation["future_dimensions"],
        "findings": observation["findings"],
        "overall": observation["overall"],
    }
    if list(report) != policy["report_top_level_fields"]:
        _fail("candidate-report")
    return report


def _render_candidate_human(report: Mapping[str, object]) -> str:
    command = _mapping(report["command"], "candidate-report")
    distribution = _mapping(report["distribution"], "candidate-report")
    admission = _mapping(report["admission"], "candidate-report")
    runtime = _mapping(report["runtime"], "candidate-report")
    operator_tools = _mapping(report["operator_tools"], "candidate-report")
    bundle = _mapping(report["bundle"], "candidate-report")
    recovery = _mapping(report["recovery"], "candidate-report")
    overall = _mapping(report["overall"], "candidate-report")
    lines = [
        f"ccodex sdlc {command['verb']}: {overall['state']}",
        f"candidate: {distribution['product_version']} ephemeral/unpublished; public_channel=null; support_tier={distribution['support_tier']}; release_claim={distribution['release_claim']}",
        f"disclosures: provenance={distribution['provenance']}, sbom={distribution['sbom']}, licensing={distribution['licensing']}",
        f"release topology: ADR-0021 {distribution['release_topology_adr_status']}",
        f"admission: {admission['state']} ({admission['schema_version']}, host-finalized)",
        f"runtime: {runtime['state']} ({runtime['version']}, isolated={str(runtime['isolated']).lower()})",
        f"operator-tools: {operator_tools['state']}",
        f"bundle: {bundle['state']}",
        f"recovery: {recovery['state']} (no effects)",
        "future dimensions: release=unpublished, activation=unsupported, waves=unsupported",
    ]
    findings = report["findings"]
    proposals = recovery["proposals"]
    assert isinstance(findings, list) and isinstance(proposals, list)
    for finding_value in findings:
        finding = _mapping(finding_value, "candidate-report")
        lines.append(f"finding [{finding['component']}/{finding['code']}]: {finding['message']} ({finding['path']})")
    for proposal_value in proposals:
        proposal = _mapping(proposal_value, "candidate-report")
        lines.append(f"recovery proposal [{proposal['component']}]: {proposal['action']} ({proposal['path']})")
    return "\n".join(lines) + "\n"


def run_readonly(
    archive: Path,
    command: Sequence[str],
    *,
    temp_parent: Path | None = None,
    _host_snapshot: SourceSnapshot | None = None,
    _runtime_root: Path | None = None,
    _after_pin_copy: Callable[[], None] | None = None,
) -> int:
    _require_linux_x64()
    host_source = admit_source() if _host_snapshot is None else _host_snapshot
    host_policy, host_policy_bytes = _policy_from_snapshot(host_source)
    execution_policy, _execution_policy_bytes = load_execution_policy(host_source)
    report_policy, _report_policy_bytes = load_candidate_report_policy(host_source)
    if list(command) not in execution_policy["commands"]:
        _fail("execution-command")
    runtime_root = _resolve_base_runtime(host_policy) if _runtime_root is None else _runtime_root
    _validate_runtime_root(runtime_root, _runtime_license_paths(host_policy))
    bash, bash_sha256 = _trusted_bash(execution_policy)
    del bash
    limits = _mapping(host_policy["limits"], "policy-limits")
    archive_name = _archive_name(archive)
    retain_private = False
    try:
        parent = temp_parent if temp_parent is not None else _validated_system_tmp()
        private = Path(tempfile.mkdtemp(prefix=".release-candidate-run-", dir=parent))
    except OSError:
        _fail("extract-create")
    try:
        pinned, archive_sha256 = _pin_archive(archive, private, int(limits["max_archive_bytes"]), after_copy=_after_pin_copy)
        raw = _inflate_gzip(pinned, private, int(limits["max_uncompressed_bytes"]))
        manifest, members, manifest_raw = _archive_admission(raw, archive_name, host_policy, host_policy_bytes)
        root = _manual_extract(raw, manifest, members, manifest_raw, host_policy, private)
        _recompute_extracted(root, manifest)
        authored_digest, runtime_digest = _authenticate_executable_candidate(manifest, host_source, host_policy, runtime_root)
        dispatcher, dispatcher_sha256 = _render_candidate_dispatcher(root)
        admission = _admission_record(
            root,
            archive_sha256,
            manifest,
            execution_policy,
            command,
            dispatcher_sha256,
            bash_sha256,
            authored_digest,
            runtime_digest,
        )
        _final_source_recheck(host_source)
        if _entry_digest(_expected_runtime_inventory(runtime_root)) != runtime_digest:
            _fail("execution-runtime-drift")
        result, child_stdout, child_stderr, child_pid = _supervise_candidate(
            dispatcher, command, admission, execution_policy
        )
        if result != 0 or child_stderr:
            _fail("execution-child-refused")
        observation = _validate_candidate_observation(
            child_stdout, report_policy, manifest, command, admission, child_pid
        )
        _final_source_recheck(host_source)
        if _entry_digest(_expected_runtime_inventory(runtime_root)) != runtime_digest:
            _fail("execution-runtime-drift")
        _recheck_execution_root(root, admission)
        report = _candidate_final_report(report_policy, manifest, admission, observation)
        if command[-1] == "--json":
            sys.stdout.write(canonical_json(report))
        else:
            sys.stdout.write(_render_candidate_human(report))
        return 0
    except CandidateError as error:
        if error.code == "execution-group-unknown-effect":
            retain_private = True
            retained_witness = _retain_process_group_witness(private)
            raise CandidateError(error.code, retained_witness) from None
        raise
    finally:
        if not retain_private:
            _cleanup_run_private(private)


def verify_archive(archive: Path, *, temp_parent: Path | None = None, _host_snapshot: SourceSnapshot | None = None, _after_pin_copy: Callable[[], None] | None = None) -> str:
    _require_linux_x64()
    host_source = admit_source() if _host_snapshot is None else _host_snapshot
    host_policy, host_policy_bytes = _policy_from_snapshot(host_source)
    limits = _mapping(host_policy["limits"], "policy-limits")
    archive_name = _archive_name(archive)
    try:
        private = Path(tempfile.mkdtemp(prefix=".release-candidate-verify-", dir=temp_parent)) if temp_parent is not None else Path(tempfile.mkdtemp(prefix=".release-candidate-verify-"))
    except OSError:
        _fail("extract-create")
    try:
        pinned, digest = _pin_archive(archive, private, int(limits["max_archive_bytes"]), after_copy=_after_pin_copy)
        raw = _inflate_gzip(pinned, private, int(limits["max_uncompressed_bytes"]))
        manifest, members, manifest_raw = _archive_admission(raw, archive_name, host_policy, host_policy_bytes)
        extracted = _manual_extract(raw, manifest, members, manifest_raw, host_policy, private)
        _recompute_extracted(extracted, manifest)
        return digest
    finally:
        _cleanup_verify_private(private)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    actions = parser.add_subparsers(dest="action", required=True)
    build = actions.add_parser("build", allow_abbrev=False)
    build.add_argument("--output", required=True, type=Path)
    verify = actions.add_parser("verify", allow_abbrev=False)
    verify.add_argument("--archive", required=True, type=Path)
    readonly = actions.add_parser("run-readonly", allow_abbrev=False)
    readonly.add_argument("--archive", required=True, type=Path)
    readonly.add_argument("command", nargs=argparse.REMAINDER)
    acquire = actions.add_parser("acquire", allow_abbrev=False)
    acquire_actions = acquire.add_subparsers(dest="acquire_action", required=True)
    acquire_plan = acquire_actions.add_parser("plan", allow_abbrev=False)
    acquire_plan.add_argument("--archive", required=True, type=Path)
    acquire_plan.add_argument("--trust-root", required=True, type=Path)
    acquire_plan.add_argument("--xdg-data-home", required=True, type=Path)
    acquire_plan.add_argument("--xdg-state-home", required=True, type=Path)
    acquire_inspect = acquire_actions.add_parser("inspect", allow_abbrev=False)
    acquire_inspect.add_argument("--plan", required=True, type=Path)
    acquire_apply = acquire_actions.add_parser("apply", allow_abbrev=False)
    acquire_apply.add_argument("--plan", required=True, type=Path)
    acquire_apply.add_argument("--grant", required=True, type=Path)
    acquire_recover = acquire_actions.add_parser("recover", allow_abbrev=False)
    recover_actions = acquire_recover.add_subparsers(dest="recover_action", required=True)
    recover_inspect = recover_actions.add_parser("inspect", allow_abbrev=False)
    recover_inspect.add_argument("--xdg-state-home", required=True, type=Path)
    recover_inspect.add_argument("--journal-locator", required=True)
    recover_finish = recover_actions.add_parser("finish", allow_abbrev=False)
    recover_finish.add_argument("--xdg-state-home", required=True, type=Path)
    recover_finish.add_argument("--journal-locator", required=True)
    recover_finish.add_argument("--grant", required=True, type=Path)
    arguments = parser.parse_args(argv)
    if arguments.action == "run-readonly":
        raw = arguments.command
        if not raw or raw[0] != "--":
            parser.error("run-readonly requires a literal -- before the candidate command")
        command = raw[1:]
        admitted = (
            command in (["sdlc", "inspect"], ["sdlc", "inspect", "--json"])
            or command in (["sdlc", "status"], ["sdlc", "status", "--json"])
            or command in (["sdlc", "doctor"], ["sdlc", "doctor", "--json"])
            or command in (
                ["sdlc", "recover", "--dry-run"],
                ["sdlc", "recover", "--dry-run", "--json"],
            )
        )
        if not admitted:
            parser.error("run-readonly admits only the closed read-only ccodex sdlc grammar")
        arguments.command = command
    return arguments


def _failure_exit_code(code: str) -> int:
    return 4 if code in {
        "archive-unknown-effect",
        "execution-group-unknown-effect",
        "execution-orphan-unknown-effect",
        "execution-termination-unknown-effect",
        "run-stage-unknown-effect",
        "stage-unknown-effect",
        "verify-stage-unknown-effect",
    } else 3


def _load_acquisition_engine():
    """Load the pinned sibling even when the dispatcher runs under Python ``-I``."""
    name = "release_candidate_acquisition"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    try:
        path = Path(__file__).resolve(strict=True).with_name("release_candidate_acquisition.py")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            _fail("acquisition-dispatch")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except CandidateError:
        raise
    except Exception:
        sys.modules.pop(name, None)
        _fail("acquisition-dispatch")
    raise AssertionError("unreachable")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = parse_args(argv)
    except SystemExit as error:
        return int(error.code)
    try:
        if arguments.action == "build":
            # Capture the digest build_candidate() already computed before it
            # published the archive, instead of re-reading the now-published file
            # here: that second read would run strictly after the durable publish
            # and its failure could never be honestly reported as a clean refusal.
            published_digest: list[str] = []
            result = build_candidate(arguments.output, on_publish=published_digest.append)
            print(f"built {result.name} sha256={published_digest[0]}")
        elif arguments.action == "verify":
            print(f"verified {arguments.archive.name} sha256={verify_archive(arguments.archive)}")
        elif arguments.action == "run-readonly":
            return run_readonly(arguments.archive, arguments.command)
        elif arguments.action == "acquire":
            return _load_acquisition_engine().run(arguments, candidate=sys.modules[__name__])
        else:
            _fail("usage")
    except CandidateError as error:
        exit_code = _failure_exit_code(error.code)
        suffix = " effect_state=unknown" if exit_code == 4 else ""
        locator = _public_witness_locator(error.retained_witness)
        if locator is not None:
            suffix += f" witness_locator={locator}"
        print(f"release-candidate: {error.code}{suffix}", file=sys.stderr)
        return exit_code
    except Exception:
        # Implementation Decision 9: this handler is shared by every action above,
        # including "build", where build_candidate() only returns after
        # _publish_no_replace() has already renamed the archive into place — a
        # durable product effect. An exception reaching here is therefore not
        # provably "before any effect"; reporting a clean refusal (3) would be a
        # false claim of no effect. Report unknown effect state (4), matching the
        # CandidateError branch's own unknown-effect codes above.
        print("release-candidate: internal effect_state=unknown", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
