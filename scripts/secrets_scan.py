#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Scan tracked and nonignored untracked files with the pinned secrets rules."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


CONFIG_PATH = Path(".config/betterleaks.toml")
# ponytail: conservative cross-platform argv ceiling; raise only if measured repos need it.
DEFAULT_MAX_ARGV_BYTES = 24_000 if os.name == "nt" else 128_000


class SecretsScanError(RuntimeError):
    pass


def argv_size(argv: list[str]) -> int:
    return sum(len(os.fsencode(argument)) + 1 for argument in argv)


def git_visible_files(root: Path) -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        raise SecretsScanError("git-visible-file-enumeration-failed")

    paths: list[str] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = os.fsdecode(raw)
        path = root / relative
        if path.is_file() and not path.is_symlink():
            paths.append(relative)
    return paths


def batched_commands(
    prefix: list[str], paths: list[str], *, max_argv_bytes: int = DEFAULT_MAX_ARGV_BYTES
) -> list[list[str]]:
    batches: list[list[str]] = []
    current = prefix.copy()
    for path in paths:
        candidate = [*current, path]
        if len(current) > len(prefix) and argv_size(candidate) > max_argv_bytes:
            batches.append(current)
            current = [*prefix, path]
        else:
            current = candidate
        if argv_size(current) > max_argv_bytes:
            raise SecretsScanError("path-exceeds-scanner-argv-limit")
    if len(current) > len(prefix):
        batches.append(current)
    return batches


def run_scanner_batch(command: list[str], cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False).returncode


def scan_paths(
    root: Path,
    paths: list[str],
    config: Path,
    *,
    max_argv_bytes: int = DEFAULT_MAX_ARGV_BYTES,
) -> int:
    if not paths:
        return 0
    scanner = shutil.which("betterleaks")
    if scanner is None:
        raise SecretsScanError("betterleaks-not-found")
    prefix = [scanner, "dir", "--redact=100", "--config", str(config), "--"]
    finding = False
    scanner_error = 0
    for command in batched_commands(prefix, paths, max_argv_bytes=max_argv_bytes):
        code = run_scanner_batch(command, root)
        if code == 1:
            finding = True
        elif code and not scanner_error:
            scanner_error = code
    return scanner_error or (1 if finding else 0)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config = (root / CONFIG_PATH).resolve()
    if not config.is_file():
        raise SecretsScanError("pinned-secrets-config-missing")
    return scan_paths(root, git_visible_files(root), config)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SecretsScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
