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
            json.dumps(forwarded),
        ],
    )
    print(f"=== Host summary: WSL={wsl_exit} Windows={windows_exit} ===")
    return max(wsl_exit, windows_exit)


if __name__ == "__main__":
    raise SystemExit(main())
