#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Scan tracked and nonignored untracked files with the pinned secrets rules.

Exit table. This is the single derivation point for every code this module produces:

| exit | name              | meaning                                                      |
| ---- | ----------------- | ------------------------------------------------------------ |
| 0    | EXIT_OK           | the scan ran and no batch reported a finding                  |
| 1    | EXIT_FINDING      | the scan ran and betterleaks reported a finding. `mise run    |
|      |                   | check` depends on this code, so it must never move            |
| 2    | EXIT_USAGE        | argparse rejected the argv, or an enumerated path cannot fit  |
|      |                   | the scanner's argv ceiling (`path-exceeds-scanner-argv-limit`) |
| 3    | EXIT_PRECONDITION | refusal before any file is scanned: every reason in           |
|      |                   | `PRECONDITION_REASONS`                                        |

A scanner exit other than 0 or 1 is passed through unchanged, so betterleaks' own codes stay
legible and outrank a finding. `--help` is the only 0-class query and never enumerates.
`refusal_exit_code` is the only place a raised `SecretsScanError` becomes an exit code.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


CONFIG_PATH = Path(".config/betterleaks.toml")
# ponytail: conservative cross-platform argv ceiling; raise only if measured repos need it.
DEFAULT_MAX_ARGV_BYTES = 24_000 if os.name == "nt" else 128_000
EXIT_OK = 0
EXIT_FINDING = 1
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
# Reasons that are refused before any file is handed to the scanner, so nothing was scanned.
PRECONDITION_REASONS = frozenset(
    {
        "pinned-secrets-config-missing",
        "betterleaks-not-found",
        "git-visible-file-enumeration-failed",
    }
)


class SecretsScanError(RuntimeError):
    pass


def refusal_exit_code(error: SecretsScanError) -> int:
    """Map one raised refusal onto the exit table; the only raise-to-exit derivation here."""
    return EXIT_PRECONDITION if str(error) in PRECONDITION_REASONS else EXIT_USAGE


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
        path = root
        for component in Path(relative).parts:
            path /= component
            if path.is_symlink():
                break
        else:
            if path.is_file():
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
        return EXIT_OK
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
    return scanner_error or (EXIT_FINDING if finding else EXIT_OK)


def build_parser() -> argparse.ArgumentParser:
    """No positional or optional arguments: the scan is the explicit default action."""
    return argparse.ArgumentParser(
        prog="secrets_scan.py",
        description=(
            "Scan tracked and nonignored untracked files with the pinned secrets rules. "
            "Takes no arguments; running it with no arguments is the scan."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
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
        raise SystemExit(refusal_exit_code(exc)) from exc
