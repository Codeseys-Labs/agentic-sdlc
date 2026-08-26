#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run one bundle lifecycle operation on WSL and its native Windows host."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys


# UNC providers native Windows PowerShell will not load a script FILE from. Both spellings of the
# WSL provider are listed: `\\wsl$` is the older one and is still what some builds hand back.
WSL_UNC_PROVIDERS = ("\\\\wsl.localhost", "\\\\wsl$")


def powershell_path() -> str | None:
    discovered = shutil.which("powershell.exe")
    if discovered:
        return discovered
    fallback = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    return str(fallback) if fallback.is_file() else None


def run_host(label: str, command: list[str]) -> int:
    print(f"=== {label} ===", flush=True)
    return subprocess.run(command, check=False).returncode


def is_wsl_absolute(value: str) -> bool:
    """Identify WSL absolute spelling without depending on the test host OS."""
    return PurePosixPath(value).is_absolute() and not PureWindowsPath(value).is_absolute()


def wsl_resident_provider(native_repo: str) -> str | None:
    """Name the UNC provider PowerShell will refuse to run this checkout's script from, if any.

    `-ExecutionPolicy Bypass` is already passed below and is not the problem: Windows PowerShell
    applies a separate zone/AuthorizationManager check to a script FILE loaded from an untrusted UNC
    provider, and the WSL provider is one of those. So a checkout living inside WSL translates to a
    path the Windows leg cannot execute at all, however permissive the execution policy is.

    Measured 2026-08-23 on the primary dev machine, three readings that isolate it: `-File` from the
    UNC path fails with `AuthorizationManager check failed`; `-Command` with the same inline text
    succeeds, so no machine policy is locked down; and the byte-identical script copied to a native
    path passes the security gate and reaches its ordinary argument error (agentic-sdlc-1db2). CI has
    never exercised this because its Windows leg checks out natively under `C:\\runner`.
    """
    lowered = native_repo.lower()
    return next(
        (provider for provider in WSL_UNC_PROVIDERS if lowered.startswith(f"{provider}\\")),
        None,
    )


def windows_arguments(arguments: list[str], wslpath: str) -> list[str]:
    """Translate WSL absolute values for installer path options."""
    converted = list(arguments)
    index = 0
    while index < len(converted):
        argument = converted[index]
        if argument == "--":
            break
        if argument in {"--home", "--codex-home"} and index + 1 < len(converted):
            value = converted[index + 1]
            if is_wsl_absolute(value):
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
                if is_wsl_absolute(value):
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
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] in {"-h", "--help"}:
        parser.parse_args(raw)
    if raw[0] not in {"install", "status"}:
        parser.error(f"argument operation: invalid choice: {raw[0]!r}")
    operation, forwarded = raw[0], raw[1:]

    if sys.platform == "win32" or not Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists():
        parser.error("this coordinator must run inside WSL")
    powershell = powershell_path()
    wslpath = shutil.which("wslpath")
    if not powershell or not wslpath:
        parser.error("native Windows PowerShell and wslpath are required")

    repo = Path(__file__).resolve().parents[1]
    task = f"lifecycle:{operation}"
    # Translated and checked BEFORE the WSL leg runs. A coordinator that installs on one host and
    # only then discovers the other host cannot start reports a half-executed pair as an ordinary
    # leg failure, which is what the opaque PowerShell text looked like on this setup.
    native_repo = subprocess.run(
        [wslpath, "-w", str(repo)], check=True, capture_output=True, text=True
    ).stdout.strip()
    provider = wsl_resident_provider(native_repo)
    if provider:
        parser.error(
            f"this checkout is WSL-resident: {wslpath} -w resolves it onto the UNC provider"
            f" {provider}, and native Windows PowerShell refuses to run a script FILE from there"
            " with 'AuthorizationManager check failed' no matter what -ExecutionPolicy Bypass says,"
            " so the Windows leg cannot start. Run all-host tasks from a checkout on a Windows"
            " filesystem (a /mnt/<drive>/... path), or run each host's lifecycle task on its own"
            " host separately."
        )
    wsl_exit = run_host(
        f"WSL host: {operation}",
        ["mise", "--cd", str(repo), "run", task, "--", *forwarded],
    )
    native_forwarded = windows_arguments(forwarded, wslpath)
    windows_exit = run_host(
        f"Native Windows host: {operation}",
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
    return max(1 if wsl_exit < 0 else wsl_exit, 1 if windows_exit < 0 else windows_exit)


if __name__ == "__main__":
    raise SystemExit(main())
