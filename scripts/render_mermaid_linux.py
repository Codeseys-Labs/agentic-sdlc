#!/usr/bin/env python3
"""Render one Mermaid definition through the Linux-only M0b safety boundary."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


if sys.platform == "linux":
    import fcntl
    import resource


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "policy" / "mermaid-renderer-linux-v1.json"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3
_URI = re.compile(r"(?:^|[^#])(?:javascript:|data:|file:|https?:|//)", re.IGNORECASE)
_CSS_UNSAFE = re.compile(r"@(?:import|namespace)|url\(\s*(?!['\"]?#)[^)]|(?:behavior|expression)\s*:", re.IGNORECASE)
_CSS_PROPERTY = re.compile(r"(?<![\w-])([a-z-]+)\s*:", re.IGNORECASE)
_SOURCE_URI = re.compile(r"(?:https?:|//|file:|data:|javascript:)", re.IGNORECASE)
SANDBOX_ROOT = "/m0b"
SANDBOX_NODE = f"{SANDBOX_ROOT}/node"
SANDBOX_MMDC_ROOT = f"{SANDBOX_ROOT}/mermaid-cli"
SANDBOX_MMDC = f"{SANDBOX_MMDC_ROOT}/src/cli.js"
SANDBOX_BROWSER_ROOT = f"{SANDBOX_ROOT}/browser"
SANDBOX_BROWSER = f"{SANDBOX_BROWSER_ROOT}/chrome-headless-shell"
SANDBOX_SANITIZER = f"{SANDBOX_ROOT}/sanitize_mermaid_svg.mjs"
SANDBOX_POLICY = f"{SANDBOX_ROOT}/policy.json"
SANDBOX_NODE_MODULES = f"{SANDBOX_ROOT}/node_modules"
# chrome-headless-shell spawns its zygote, GPU, and renderer processes with many threads
# each, and RLIMIT_NPROC charges threads. The policy's max_processes is the process budget;
# this factor converts it into the task budget the kernel actually enforces.
NPROC_HEADROOM_FACTOR = 16


class RendererError(RuntimeError):
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
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RendererError("browser cache contains a symbolic link or non-regular entry")
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
            raise RendererError("node_modules contains a non-regular entry")
        rows.append(f"file {_sha256(child)}  {relative}\n")
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def _private_regular(path: Path, *, limit: int, label: str) -> None:
    metadata = _deny_symlink(path, label)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise RendererError(f"{label} must be an owner-private bounded regular file")


def load_policy(path: Path = POLICY_PATH) -> dict[str, object]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RendererError(f"invalid renderer policy: {exc}") from exc
    if policy.get("schema_version") != "mermaid-renderer-linux/v1":
        raise RendererError("unsupported renderer policy schema")
    return policy


def _deny_symlink(path: Path, label: str) -> os.stat_result:
    try:
        result = path.lstat()
    except OSError as exc:
        raise RendererError(f"cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(result.st_mode):
        raise RendererError(f"{label} must not be a symbolic link")
    return result


def _safe_parent_chain(path: Path) -> None:
    if not path.is_absolute():
        raise RendererError("path must be absolute")
    current = path
    while True:
        _deny_symlink(current, "path parent")
        if current == current.parent:
            break
        current = current.parent


def _open_regular_input(path: Path, limit: int) -> tuple[int, tuple[int, int, int]]:
    if path.is_absolute() is False or ".." in path.parts:
        raise RendererError("input path must be absolute and traversal-free")
    _deny_symlink(path, "input")
    _safe_parent_chain(path.parent)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RendererError(f"cannot open input: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
        os.close(descriptor)
        raise RendererError("input must be a bounded regular file")
    return descriptor, (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns)


def _revalidate_input(descriptor: int, identity: tuple[int, int, int]) -> None:
    metadata = os.fstat(descriptor)
    if (metadata.st_dev, metadata.st_ino, metadata.st_mtime_ns) != identity:
        raise RendererError("input identity changed")


def _read_admitted_input(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit + 1
    while remaining:
        chunk = os.read(descriptor, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    value = b"".join(chunks)
    if len(value) > limit:
        raise RendererError("input exceeds policy size limit")
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RendererError("input must be UTF-8") from exc
    if "%%{" in text or "%%{init" in text:
        raise RendererError("definition config directives are forbidden")
    if _SOURCE_URI.search(text):
        raise RendererError("definition may not name a URI-bearing external asset")
    return value


def _write_private(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    try:
        os.write(descriptor, value)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_owner_configs(workspace: Path, executable: Path, policy: dict[str, object]) -> tuple[Path, Path]:
    if workspace.stat().st_mode & 0o777 != 0o700:
        raise RendererError("workspace must be owner-private")
    mermaid = workspace / "mermaid.json"
    puppeteer = workspace / "puppeteer.json"
    mermaid_config = dict(policy["mermaid_config"])
    puppeteer_template = dict(policy["puppeteer_config"])
    puppeteer_config = {
        "executablePath": SANDBOX_BROWSER,
        "headless": puppeteer_template["headless"],
        "userDataDir": str(workspace / "profile"),
        "args": puppeteer_template["args"],
    }
    _write_private(mermaid, json.dumps(mermaid_config, separators=(",", ":"), sort_keys=True).encode() + b"\n")
    _write_private(puppeteer, json.dumps(puppeteer_config, separators=(",", ":"), sort_keys=True).encode() + b"\n")
    return mermaid, puppeteer


def _expanded_name(name: str) -> tuple[str, str]:
    if name.startswith("{"):
        namespace, local = name[1:].split("}", 1)
        return namespace, local
    return "", name


def _validate_css(value: str, allowed_properties: set[str]) -> None:
    if _CSS_UNSAFE.search(value):
        raise RendererError("unsafe CSS declaration")
    blocks = re.findall(r"\{([^{}]*)\}", value) or [value]
    for block in blocks:
        for property_name in _CSS_PROPERTY.findall(block):
            if property_name.lower() not in allowed_properties and not property_name.startswith("--"):
                raise RendererError(f"CSS property is not allowlisted: {property_name}")


def validate_final_svg(value: bytes, policy: dict[str, object]) -> bytes:
    limits = policy["limits"]
    svg = policy["svg"]
    if not value or len(value) > limits["max_final_bytes"]:
        raise RendererError("final SVG byte limit violated")
    upper = value.upper()
    if any(declaration.encode() in upper for declaration in svg["forbidden_declarations"]):
        raise RendererError("DTD, entity, or CDATA declaration is forbidden")
    try:
        root = ET.fromstring(value)
    except ET.ParseError as exc:
        raise RendererError("final SVG is not well-formed XML") from exc
    namespaces = set(svg["namespaces"].values())
    elements = set(svg["elements"])
    forbidden_elements = set(svg["forbidden_elements"])
    attributes = set(svg["attributes"])
    uri_attributes = set(svg["uri_attributes"])
    css_properties = set(svg["css_properties"])
    for element in root.iter():
        namespace, local = _expanded_name(element.tag)
        if namespace not in namespaces or local in forbidden_elements or local not in elements:
            raise RendererError(f"forbidden SVG element: {local}")
        if local == "style":
            _validate_css(element.text or "", css_properties)
        for expanded, raw in element.attrib.items():
            attribute_namespace, local_attribute = _expanded_name(expanded)
            policy_name = "xlink:href" if attribute_namespace == "http://www.w3.org/1999/xlink" and local_attribute == "href" else local_attribute
            if attribute_namespace and attribute_namespace not in namespaces:
                raise RendererError("disallowed attribute namespace")
            if local_attribute.lower().startswith("on") or policy_name not in attributes:
                raise RendererError(f"forbidden SVG attribute: {policy_name}")
            if policy_name == "style":
                _validate_css(raw, css_properties)
            if policy_name in uri_attributes and raw.strip() and not (raw.strip().startswith("#") or raw.strip().lower().startswith("url(#")):
                raise RendererError(f"non-fragment SVG reference: {policy_name}")
            if policy_name in uri_attributes and _URI.search(raw):
                raise RendererError(f"unsafe SVG reference: {policy_name}")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_final(destination: Path, value: bytes, policy: dict[str, object]) -> None:
    final = validate_final_svg(value, policy)
    parent = destination.parent
    if not destination.is_absolute() or ".." in destination.parts:
        raise RendererError("destination path must be absolute and traversal-free")
    _safe_parent_chain(parent)
    parent_metadata = _deny_symlink(parent, "destination parent")
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise RendererError("destination parent is not a directory")
    if destination.exists() and not stat.S_ISREG(_deny_symlink(destination, "destination").st_mode):
        raise RendererError("destination must be a regular file")
    temporary = parent / f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        os.write(descriptor, final)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if _deny_symlink(parent, "destination parent").st_ino != parent_metadata.st_ino:
            raise RendererError("destination parent identity changed")
        if validate_final_svg(temporary.read_bytes(), policy) != final:
            raise RendererError("staged final SVG changed")
        os.replace(temporary, destination)
        _fsync_directory(parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def resolve_node_bin_shim(shim: Path, node_modules: Path) -> Path:
    """Admit npm's relative executable shim without permitting an external target."""
    if not shim.is_symlink():
        raise RendererError("npm executable must be a symbolic shim")
    try:
        target = shim.resolve(strict=True)
        root = node_modules.resolve(strict=True)
        target.relative_to(root)
    except (OSError, ValueError) as exc:
        raise RendererError("npm executable shim escapes node_modules") from exc
    metadata = target.lstat()
    if target.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise RendererError("npm executable target is unsafe")
    return target


def _runtime_receipt(policy: dict[str, object]) -> dict[str, object]:
    path = ROOT / policy["paths"]["receipt"]
    _private_regular(path, limit=65536, label="runtime receipt")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RendererError("runtime receipt is missing or malformed; run Linux provisioning") from exc
    expected = {"schema_version", "node", "node_executable", "npm", "package_lock_sha256", "node_modules_tree_sha256", "browser", "cache", "created_at"}
    if set(receipt) != expected or receipt["schema_version"] != "mermaid-runtime-receipt/v1":
        raise RendererError("runtime receipt shape is invalid")
    if receipt["node"] != policy["node"]["version"] or receipt["npm"] != policy["node"]["npm_version"]:
        raise RendererError("runtime receipt tool identity mismatch")
    if receipt["package_lock_sha256"] != hashlib.sha256((ROOT / "package-lock.json").read_bytes()).hexdigest():
        raise RendererError("runtime receipt lock identity mismatch")
    if receipt["browser"] != policy["browser"]:
        raise RendererError("runtime receipt browser identity mismatch")
    node = Path(receipt["node_executable"])
    if not node.is_file() or node.is_symlink():
        raise RendererError("runtime receipt Node executable is unsafe")
    node_modules = ROOT / "node_modules"
    if receipt["node_modules_tree_sha256"] != _node_modules_digest(node_modules):
        raise RendererError("node_modules identity mismatch")
    return receipt


def _clean_env(workspace: Path) -> dict[str, str]:
    return {
        "HOME": str(workspace / "home"),
        "TMPDIR": str(workspace / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def _uid_task_count(proc_root: Path = Path("/proc")) -> int:
    """Count this UID's live tasks (threads), which is what RLIMIT_NPROC actually charges.

    RLIMIT_NPROC is per-UID and counts tasks, not processes, so a browser session's threads
    all draw on the same budget as unrelated processes this operator is already running.
    """
    total = 0
    uid = os.getuid()
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return 0
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            if os.stat(proc_root / entry).st_uid != uid:
                continue
            total += len(os.listdir(proc_root / entry / "task"))
        except OSError:
            continue
    return total


def _limit_resources(limits: dict[str, int]) -> None:
    if sys.platform != "linux":
        raise RendererError("Linux resource controls are unavailable")
    resource.setrlimit(resource.RLIMIT_NOFILE, (limits["max_descriptors"], limits["max_descriptors"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits["max_output_file_bytes"], limits["max_output_file_bytes"]))
    # RLIMIT_NPROC is charged per-UID against every task this operator owns, not just this
    # render subtree, so applying max_processes as an absolute cap fails closed on any host
    # where the session already exceeds it — bwrap's own namespace setup is the first fork to
    # be refused, which is exactly the EAGAIN this relative budget avoids. Chrome is
    # thread-heavy, so the browser's own threads need headroom on top of the current census;
    # the cap still bounds runaway forking, just relative to observed load rather than zero.
    # The hard ceiling is never raised, and a limit already tighter than the budget is kept.
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    budget = _uid_task_count() + max(limits["max_processes"], 1) * NPROC_HEADROOM_FACTOR
    if hard != resource.RLIM_INFINITY:
        budget = min(budget, hard)
    if soft == resource.RLIM_INFINITY or budget < soft:
        resource.setrlimit(resource.RLIMIT_NPROC, (budget, hard))


def _process_tree_rss(pid: int, proc_root: Path = Path("/proc")) -> int:
    """Return current RSS for a process and its descendants, in bytes."""
    todo = [pid]
    visited: set[int] = set()
    total = 0
    while todo:
        current = todo.pop()
        if current in visited:
            continue
        visited.add(current)
        try:
            status = (proc_root / str(current) / "status").read_text(encoding="utf-8")
            children = (proc_root / str(current) / "task" / str(current) / "children").read_text(encoding="utf-8")
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                fields = line.split()
                if len(fields) >= 2 and fields[1].isdigit():
                    total += int(fields[1]) * 1024
                break
        todo.extend(int(child) for child in children.split() if child.isdigit())
    return total


def _remaining_timeout(deadline: float, cap: int, label: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RendererError(f"total render deadline expired before {label}")
    return min(float(cap), remaining)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            raise RendererError("render process group did not exit after termination") from None


def _sandbox_argv(workspace: Path, command: list[str], policy: dict[str, object], readonly_paths: list[tuple[Path, str]]) -> list[str]:
    bwrap = Path(policy["sandbox"]["bwrap"])
    if not bwrap.is_file() or bwrap.is_symlink() or not os.access(bwrap, os.X_OK):
        raise RendererError("required /usr/bin/bwrap capability is unavailable")
    # Browser dependencies, fonts, and node are intentionally read-only; only the private workspace is writable.
    binds = ["/usr", "/lib", "/lib64", "/bin", "/etc/fonts", "/etc/ld.so.cache"]
    argv = [str(bwrap), "--die-with-parent", "--new-session", "--unshare-net", "--unshare-pid", "--unshare-user", "--proc", "/proc", "--dev", "/dev", "--dir", SANDBOX_ROOT]
    for candidate in binds:
        if Path(candidate).exists():
            argv += ["--ro-bind", candidate, candidate]
    for source, destination in readonly_paths:
        if not source.exists() or not destination.startswith(f"{SANDBOX_ROOT}/"):
            raise RendererError("sandbox runtime input is unavailable or unsafe")
        argv += ["--ro-bind", str(source), destination]
    argv += ["--bind", str(workspace), str(workspace), "--chdir", str(workspace), "--"]
    return argv + command


def _run_child(command: list[str], workspace: Path, deadline: float, policy: dict[str, object], label: str, readonly_paths: list[tuple[Path, str]]) -> None:
    limits = dict(policy["limits"])
    process = subprocess.Popen(
        _sandbox_argv(workspace, command, policy, readonly_paths),
        cwd=workspace,
        env=_clean_env(workspace),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=True,
        preexec_fn=lambda: _limit_resources(limits),
    )
    try:
        while True:
            completed = process.poll()
            if completed is not None:
                _, stderr = process.communicate()
                if completed != 0:
                    raise RendererError(f"{label} failed with exit {completed}: {stderr.decode(errors='replace')[-512:]}")
                return
            observed = _process_tree_rss(process.pid)
            if observed > limits["max_rss_bytes"]:
                _terminate_process_tree(process)
                raise RendererError(
                    f"{label} exceeded the RSS limit: {observed} bytes observed against "
                    f"max_rss_bytes {limits['max_rss_bytes']}"
                )
            if time.monotonic() >= deadline:
                _terminate_process_tree(process)
                raise RendererError(f"{label} timed out")
            time.sleep(0.05)
    except BaseException:
        if process.poll() is None:
            _terminate_process_tree(process)
        raise


def _private_workspace() -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="mermaid-renderer-"))
    os.chmod(workspace, 0o700)
    for name in ("home", "tmp", "profile"):
        child = workspace / name
        child.mkdir(mode=0o700)
    return workspace


def _render(input_bytes: bytes, workspace: Path, policy: dict[str, object], deadline: float) -> bytes:
    receipt = _runtime_receipt(policy)
    cache = ROOT / policy["paths"]["cache_root"]
    _safe_parent_chain(cache)
    cache_metadata = _deny_symlink(cache, "browser cache")
    if not stat.S_ISDIR(cache_metadata.st_mode) or cache_metadata.st_uid != os.getuid():
        raise RendererError("browser cache is unsafe")
    if _cache_digest(cache) != policy["browser"]["cache_tree_sha256"]:
        raise RendererError("browser cache identity mismatch")
    executable = cache / policy["browser"]["executable_relative_path"]
    if not executable.is_file() or executable.is_symlink() or _sha256(executable) != policy["browser"]["executable_sha256"]:
        raise RendererError("pinned browser executable is unavailable")
    node_modules = ROOT / "node_modules"
    mmdc = resolve_node_bin_shim(node_modules / ".bin" / "mmdc", node_modules)
    mmdc_root = node_modules / "@mermaid-js" / "mermaid-cli"
    sanitizer = ROOT / "scripts" / "sanitize_mermaid_svg.mjs"
    node = Path(receipt["node_executable"])
    for path, label in ((mmdc, "mmdc"), (node, "node"), (sanitizer, "sanitizer")):
        if not path.is_file() or (path != mmdc and path.is_symlink()):
            raise RendererError(f"verified {label} is unavailable")
    _write_private(workspace / "input.mmd", input_bytes)
    mermaid, puppeteer = write_owner_configs(workspace, executable, policy)
    raw, final = workspace / "raw.svg", workspace / "final.svg"
    readonly = [
        (node, SANDBOX_NODE),
        (mmdc_root, SANDBOX_MMDC_ROOT),
        (executable.parent, SANDBOX_BROWSER_ROOT),
        (sanitizer, SANDBOX_SANITIZER),
        (POLICY_PATH, SANDBOX_POLICY),
        (node_modules, SANDBOX_NODE_MODULES),
    ]
    render_deadline = min(deadline, time.monotonic() + policy["limits"]["render_wall_seconds"])
    _run_child([SANDBOX_NODE, SANDBOX_MMDC, "-i", str(workspace / "input.mmd"), "-o", str(raw), "-c", str(mermaid), "-p", str(puppeteer)], workspace, render_deadline, policy, "Mermaid render", readonly)
    if not raw.is_file() or raw.is_symlink() or raw.stat().st_size > policy["limits"]["max_raw_bytes"]:
        raise RendererError("raw SVG violates private output policy")
    sanitize_deadline = min(deadline, time.monotonic() + policy["limits"]["sanitize_wall_seconds"])
    _run_child([SANDBOX_NODE, SANDBOX_SANITIZER, str(raw), str(final), SANDBOX_POLICY, SANDBOX_BROWSER], workspace, sanitize_deadline, policy, "SVG sanitizer", readonly)
    return final.read_bytes()


def _render_lock(policy: dict[str, object]) -> int:
    runtime = ROOT / policy["paths"]["runtime_root"]
    runtime.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(runtime / "render.lock", os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(descriptor)
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            raise RendererError("another Mermaid render is active") from exc
        raise
    return descriptor


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) != 2:
        return EXIT_USAGE
    if sys.platform != "linux" or os.uname().machine not in {"x86_64", "amd64"}:
        return EXIT_UNSUPPORTED
    workspace: Path | None = None
    descriptor: int | None = None
    lock_descriptor: int | None = None
    try:
        policy = load_policy()
        lock_descriptor = _render_lock(policy)
        source, destination = Path(values[0]), Path(values[1])
        descriptor, identity = _open_regular_input(source, policy["limits"]["max_input_bytes"])
        input_bytes = _read_admitted_input(descriptor, policy["limits"]["max_input_bytes"])
        _revalidate_input(descriptor, identity)
        workspace = _private_workspace()
        deadline = time.monotonic() + policy["limits"]["total_wall_seconds"]
        final = _render(input_bytes, workspace, policy, deadline)
        if validate_final_svg(final, policy) != final:
            raise RendererError("browser sanitizer is not idempotent")
        shutil.rmtree(workspace)
        workspace = None
        publish_final(destination, final, policy)
        return EXIT_OK
    except RendererError as exc:
        print(f"mermaid-renderer: {exc}", file=sys.stderr)
        return EXIT_ERROR
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if workspace is not None:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
