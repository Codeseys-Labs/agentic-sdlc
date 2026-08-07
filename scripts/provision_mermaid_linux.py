#!/usr/bin/env python3
"""Provision the immutable Linux Mermaid browser runtime; this is not a renderer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import render_mermaid_linux as renderer


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policy" / "mermaid-renderer-linux-v1.json"


class ProvisionError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _cache_digest(cache: Path) -> str:
    rows: list[str] = []
    for child in sorted(cache.rglob("*")):
        metadata = child.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            if child.is_dir() and not stat.S_ISLNK(metadata.st_mode):
                continue
            raise ProvisionError("browser cache contains a symlink or non-regular entry")
        rows.append(f"{_sha256(child)}  {child.relative_to(cache).as_posix()}\n")
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def _node_modules_digest(node_modules: Path) -> str:
    rows: list[str] = []
    for child in sorted(node_modules.rglob("*")):
        metadata = child.lstat()
        relative = child.relative_to(node_modules).as_posix()
        if stat.S_ISLNK(metadata.st_mode):
            rows.append(f"symlink {os.readlink(child)}  {relative}\n")
            continue
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ProvisionError("node_modules contains a non-regular entry")
        rows.append(f"file {_sha256(child)}  {relative}\n")
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def _owner_only(path: Path, *, directory: bool = False, private_mode: bool = True) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or (directory and not stat.S_ISDIR(metadata.st_mode)) or (not directory and not stat.S_ISREG(metadata.st_mode)):
        raise ProvisionError(f"unsafe runtime path: {path}")
    if metadata.st_uid != os.getuid() or (private_mode and metadata.st_mode & 0o077):
        raise ProvisionError(f"runtime path is not owner-private: {path}")


def _run(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(argv, cwd=ROOT, env=env, text=True, capture_output=True, shell=False, check=False)
    if completed.returncode:
        raise ProvisionError(f"command failed: {argv[0]}: {completed.stderr[-512:]}")
    return completed


def _atomic_receipt(path: Path, value: dict[str, object]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())
        os.fsync(descriptor)
        os.close(descriptor)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def provision() -> None:
    if sys.platform != "linux" or os.uname().machine not in {"x86_64", "amd64"}:
        raise ProvisionError("Linux x64 only")
    policy = renderer.load_policy(POLICY_PATH)
    runtime = ROOT / policy["paths"]["runtime_root"]
    cache = ROOT / policy["paths"]["cache_root"]
    runtime.mkdir(mode=0o700, exist_ok=True)
    cache.mkdir(mode=0o700, exist_ok=True)
    _owner_only(runtime, directory=True)
    _owner_only(cache, directory=True)
    node_modules = ROOT / "node_modules"
    if node_modules.exists():
        shutil.rmtree(node_modules)
    mise = shutil.which("mise")
    if mise is None:
        raise ProvisionError("mise is required to locate certified Node/npm")
    def tool_bin(tool: str, version: str) -> Path:
        located = subprocess.run([mise, "--no-config", "where", f"{tool}@{version}"], text=True, capture_output=True, check=False)
        if located.returncode:
            raise ProvisionError(f"certified {tool} {version} is unavailable")
        candidate = Path(located.stdout.strip()) / "bin"
        if not candidate.is_dir() or candidate.is_symlink():
            raise ProvisionError(f"certified {tool} path is unsafe")
        return candidate
    node_bin = tool_bin("node", policy["node"]["version"])
    npm_bin = tool_bin("npm", policy["node"]["npm_version"])
    if not (node_bin / "node").is_file() or not (npm_bin / "npm").is_file():
        raise ProvisionError("pinned mise Node/npm executables are unavailable")
    env = {
        "PATH": f"{node_bin}:{npm_bin}:/usr/bin:/bin",
        "HOME": str(runtime / "home"),
        "PUPPETEER_SKIP_DOWNLOAD": "1",
    }
    Path(env["HOME"]).mkdir(mode=0o700, exist_ok=True)
    _run([str(npm_bin / "npm"), "ci", "--ignore-scripts", "--no-audit", "--fund=false"], env)
    browsers_shim = ROOT / "node_modules" / ".bin" / "browsers"
    renderer.resolve_node_bin_shim(browsers_shim, ROOT / "node_modules")
    _run([str(browsers_shim), "install", f"chrome-headless-shell@{policy['browser']['build_id']}", "--path", str(cache)], env)
    browser = cache / policy["browser"]["executable_relative_path"]
    _owner_only(browser, private_mode=False)
    if _sha256(browser) != policy["browser"]["executable_sha256"] or _cache_digest(cache) != policy["browser"]["cache_tree_sha256"]:
        raise ProvisionError("browser hash or cache digest mismatch")
    version = _run([str(browser), "--version"], env).stdout.strip()
    if version != policy["browser"]["executable_version"]:
        raise ProvisionError("browser version mismatch")
    node = _run([str(node_bin / "node"), "--version"], env).stdout.strip().removeprefix("v")
    npm = _run([str(npm_bin / "npm"), "--version"], env).stdout.strip()
    receipt = {
        "schema_version": "mermaid-runtime-receipt/v1",
        "node": node,
        "node_executable": str(node_bin / "node"),
        "npm": npm,
        "package_lock_sha256": _sha256(ROOT / "package-lock.json"),
        "node_modules_tree_sha256": _node_modules_digest(ROOT / "node_modules"),
        "browser": policy["browser"],
        "cache": str(cache.relative_to(ROOT)),
        "created_at": datetime.now(UTC).isoformat(),
    }
    if node != policy["node"]["version"] or npm != policy["node"]["npm_version"]:
        raise ProvisionError("Node/npm version mismatch")
    _atomic_receipt(ROOT / policy["paths"]["receipt"], receipt)


def main() -> int:
    try:
        provision()
    except ProvisionError as exc:
        print(f"mermaid-provision: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
