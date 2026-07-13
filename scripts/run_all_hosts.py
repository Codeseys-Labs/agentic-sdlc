#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run one bundle lifecycle operation on WSL and its native Windows host."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def powershell_path() -> str | None:
    discovered = shutil.which("powershell.exe")
    if discovered:
        return discovered
    fallback = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    return str(fallback) if fallback.is_file() else None


def run_host(label: str, command: list[str]) -> int:
    print(f"=== {label} ===", flush=True)
    return subprocess.run(command, check=False).returncode


def windows_arguments(arguments: list[str], wslpath: str) -> list[str]:
    """Translate WSL absolute values for installer path options."""
    converted = list(arguments)
    index = 0
    while index < len(converted):
        argument = converted[index]
        if argument in {"--home", "--codex-home"} and index + 1 < len(converted):
            value = converted[index + 1]
            if Path(value).is_absolute():
                converted[index + 1] = subprocess.run(
                    [wslpath, "-w", value],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            index += 2
            continue
        for option in ("--home", "--codex-home"):
            prefix = f"{option}="
            if argument.startswith(prefix):
                value = argument[len(prefix) :]
                if Path(value).is_absolute():
                    native = subprocess.run(
                        [wslpath, "-w", value],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    converted[index] = f"{prefix}{native}"
                break
        index += 1
    return converted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("install", "status"))
    args, forwarded = parser.parse_known_args(argv)

    if sys.platform == "win32" or not Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists():
        parser.error("this coordinator must run inside WSL")
    powershell = powershell_path()
    wslpath = shutil.which("wslpath")
    if not powershell or not wslpath:
        parser.error("native Windows PowerShell and wslpath are required")

    repo = Path(__file__).resolve().parents[1]
    task = f"bundle:{args.operation}"
    wsl_exit = run_host(
        f"WSL host: {args.operation}",
        ["mise", "--cd", str(repo), "run", task, "--", *forwarded],
    )
    native_repo = subprocess.run(
        [wslpath, "-w", str(repo)], check=True, capture_output=True, text=True
    ).stdout.strip()
    native_forwarded = windows_arguments(forwarded, wslpath)
    windows_exit = run_host(
        f"Native Windows host: {args.operation}",
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            f"{native_repo}\\scripts\\run-windows-mise.ps1",
            "-RepoRoot",
            native_repo,
            "-Task",
            task,
            "-TaskArgsJson",
            json.dumps(native_forwarded),
        ],
    )
    print(f"=== Host summary: WSL={wsl_exit} Windows={windows_exit} ===")
    return max(wsl_exit, windows_exit)


if __name__ == "__main__":
    raise SystemExit(main())
