#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Inspect or explicitly activate the packaged Claude Code status line."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

import install_operator_tools as operator_tools


RECEIPT_VERSION = 1
MISSING = {"missing": True}


class StatuslineError(RuntimeError):
    pass


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def settings_path(home: Path, claude_config_dir: Path | None) -> Path:
    root = absolute(claude_config_dir) if claude_config_dir else absolute(home / ".claude")
    return root / "settings.json"


def receipt_path(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-claude-statusline" / "receipt.json"


def assert_physical_parent(path: Path) -> None:
    if path.is_symlink():
        raise StatuslineError(f"settings path must not be a link: {path}")
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise StatuslineError(f"settings parent must be a physical directory: {current}")
    if hasattr(os, "getuid") and current.stat().st_uid != os.getuid():
        raise StatuslineError(f"settings parent is not owned by the current user: {current}")


def load_settings(path: Path) -> dict[str, Any]:
    assert_physical_parent(path)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatuslineError(f"cannot read Claude settings {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StatuslineError(f"Claude settings must contain a JSON object: {path}")
    statusline = value.get("statusLine")
    if statusline is not None and not isinstance(statusline, dict):
        raise StatuslineError("Claude statusLine must be a JSON object")
    return value


def atomic_json(path: Path, value: dict[str, Any], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try: os.unlink(temporary)
        except FileNotFoundError: pass


def load_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise StatuslineError(f"statusline receipt must not be a link: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatuslineError(f"cannot read statusline receipt {path}: {exc}") from exc
    if value.get("version") != RECEIPT_VERSION or not isinstance(value.get("previous"), dict):
        raise StatuslineError(f"invalid statusline receipt: {path}")
    return value


def managed_values(command: Path) -> dict[str, str]:
    return {"type": "command", "command": str(command)}


def field_or_missing(statusline: dict[str, Any], key: str) -> Any:
    return statusline[key] if key in statusline else MISSING


def activate(config: operator_tools.Config, path: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    if os.name == "nt":
        raise StatuslineError("statusline activation is unsupported on native Windows")
    command = operator_tools.exact_owned_statusline(config)
    receipt = receipt_path(state_root)
    if load_receipt(receipt) is not None:
        raise StatuslineError("a managed statusline activation receipt already exists")
    settings = load_settings(path)
    statusline = settings.get("statusLine") or {}
    wanted = managed_values(command)
    for key, value in wanted.items():
        if key in statusline and statusline[key] != value:
            raise StatuslineError(f"foreign statusLine.{key} value would be overwritten")
    previous = {key: field_or_missing(statusline, key) for key in wanted}
    statusline.update(wanted); settings["statusLine"] = statusline
    messages = [f"would activate: {path} -> {command}" if dry_run else f"activated: {path} -> {command}"]
    if not dry_run:
        original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        atomic_json(path, settings, original_mode)
        atomic_json(receipt, {"version": RECEIPT_VERSION, "settings": str(path), "managed": wanted, "previous": previous}, 0o600)
    return 0, messages


def deactivate(path: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    receipt_file = receipt_path(state_root); receipt = load_receipt(receipt_file)
    if receipt is None:
        return 1, ["statusline is not managed"]
    if receipt.get("settings") != str(path):
        raise StatuslineError("statusline receipt targets a different Claude settings path")
    settings = load_settings(path); statusline = settings.get("statusLine") or {}
    managed = receipt["managed"]
    for key, value in managed.items():
        if statusline.get(key, MISSING) != value:
            raise StatuslineError(f"statusLine.{key} changed after activation; preserving operator edit")
    for key, previous in receipt["previous"].items():
        if previous == MISSING:
            statusline.pop(key, None)
        else:
            statusline[key] = previous
    if statusline:
        settings["statusLine"] = statusline
    else:
        settings.pop("statusLine", None)
    messages = [f"would deactivate: {path}" if dry_run else f"deactivated: {path}"]
    if not dry_run:
        original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        atomic_json(path, settings, original_mode)
        receipt_file.unlink()
    return 0, messages


def status(path: Path, state_root: Path) -> tuple[int, list[str]]:
    settings = load_settings(path); receipt = load_receipt(receipt_path(state_root))
    statusline = settings.get("statusLine") or {}
    if receipt is None:
        if statusline:
            return 1, [f"unmanaged statusline: {path}"]
        return 1, [f"statusline inactive: {path}"]
    managed = receipt["managed"]
    if receipt.get("settings") != str(path) or any(statusline.get(key, MISSING) != value for key, value in managed.items()):
        return 1, [f"statusline conflict: {path}"]
    return 0, [f"statusline active: {path} -> {managed['command']}"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "activate", "deactivate"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = absolute(args.home); state_root = absolute(args.state_root) if args.state_root else operator_tools.state_root_for(home)
    bin_dir = absolute(args.bin_dir) if args.bin_dir else operator_tools.default_bin_dir(home)
    path = settings_path(home, args.claude_config_dir)
    config = operator_tools.Config(Path(__file__).resolve().parents[1], home, bin_dir, state_root, require_path=False)
    try:
        code, messages = {
            "status": lambda: status(path, state_root),
            "activate": lambda: activate(config, path, state_root, args.dry_run),
            "deactivate": lambda: deactivate(path, state_root, args.dry_run),
        }[args.command]()
    except (StatuslineError, operator_tools.OperatorToolsError) as exc:
        print(f"fatal: {exc}", file=sys.stderr); return 2
    for message in messages: print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
