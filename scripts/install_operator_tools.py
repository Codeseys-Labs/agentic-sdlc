#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install lifecycle-owned Agentic SDLC operator commands into an existing user PATH."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterator


STATE_VERSION = 2
LEGACY_STATE_VERSION = 1
# `ccodex` is the dispatcher for the whole USE surface (ADR-0010). A fresh install owns only it
# and the packaged statusline support command. The two ocx-* names were shipped previously and
# remain valid in v1/v2 state and pending transitions, but they are historical aliases rather
# than desired files: status never requires them and install never recreates or refreshes them.
DESIRED_COMMANDS = ("agentic-sdlc-statusline", "ccodex")
HISTORICAL_ALIASES = ("ocx-launch", "ocx-ultracode")
RECOGNIZED_COMMANDS = DESIRED_COMMANDS + HISTORICAL_ALIASES
# The dispatcher is a bash script, and bash has no single absolute path across the platforms this
# lifecycle claims: Linux ships /usr/bin/bash (with /bin/bash usually a merged-usr link to it) and
# macOS ships only /bin/bash. The template's shebang is therefore a pin resolved here, in probe
# order, rather than a literal -- a hard-coded `#!/usr/bin/bash` installed a command that reported
# `0 installed` on macOS and then failed at every exec with ENOENT on the interpreter.
#
# The list is CLOSED and ABSOLUTE: no PATH lookup and no environment override, so nothing a caller
# controls can steer an installed command at an interpreter of their choosing. What this is NOT is
# an interpreter integrity check -- the kernel re-resolves the path at every exec, so a later
# replacement of that file is outside this lifecycle, and claiming otherwise would be a false
# guarantee. What it does record is the binding: the resolved path is part of the installed bytes,
# so the entry's ownership digest covers it and a rebinding surfaces as a refresh or a conflict
# rather than silently. Digest-pinned bash ADMISSION has no home in this tree at all now: the
# linux-x64 candidate-execution surface that measured it, its policy document, and its enforcement
# were deleted with the acquisition engine, so this resolver's binding record is the whole of what
# is claimed here.
BASH_INTERPRETER_CANDIDATES = (Path("/usr/bin/bash"), Path("/bin/bash"))


class OperatorToolsError(RuntimeError):
    pass


class HostPreconditionError(OperatorToolsError):
    """A fact about the HOST (not the caller's argv) blocks the requested lifecycle action.

    Decision 9 reserves 2 for a grammar/schema/input error and 3 for a clean refusal before
    effect. `bin_dir` being absent from PATH is nothing the caller typed wrong -- it is a
    fact about this host's shell -- so it is one derivation point away from every other
    `OperatorToolsError` (main()'s `except` clauses below), which stay 2.
    """


@dataclass(frozen=True)
class Config:
    repo_root: Path
    home: Path
    bin_dir: Path
    state_root: Path
    dry_run: bool = False
    require_path: bool = True
    ocx_path: Path | None = None
    jq_path: Path | None = None
    uv_path: Path | None = None
    # Test-only seam for the interpreter rendered into the `ccodex sdlc` route. Production
    # installations leave this unset and resolve it through the already-bound uv executable.
    sdlc_python_path: Path | None = None
    # Declared last so the positional Config(...) calls that predate it keep their meaning.
    node_path: Path | None = None

    @property
    def state_path(self) -> Path:
        return self.state_root / "agentic-sdlc-operator-tools" / "state.json"

    @property
    def lock_path(self) -> Path:
        return self.state_root / "agentic-sdlc-operator-tools" / "lock"


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def state_root_for(home: Path) -> Path:
    value = os.environ.get("XDG_STATE_HOME")
    return absolute(Path(value)) if value else absolute(home / ".local" / "state")


def default_bin_dir(home: Path) -> Path:
    value = os.environ.get("XDG_BIN_HOME")
    return absolute(Path(value)) if value else absolute(home / ".local" / "bin")


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def path_entries() -> set[str]:
    return {
        os.path.normcase(os.path.abspath(os.path.expanduser(entry)))
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }


def path_guidance(bin_dir: Path) -> str:
    """Explain the PATH boundary without changing it on the operator's behalf."""
    return (
        f"add {bin_dir} to PATH in your shell configuration, start a new shell, "
        "then retry; this lifecycle never edits PATH"
    )


def conflict_messages(path: Path, reason: str) -> list[str]:
    """Name a preserved file and the operator action required to proceed."""
    return [
        f"conflict: {path}",
        f"preserved: {path} ({reason}; inspect and resolve it before retrying)",
    ]


def operator_summary(operation: str, messages: list[str]) -> str:
    """Render one final lifecycle line for install, status, and uninstall."""
    if operation == "install":
        installed = sum(message.startswith("installed:") for message in messages)
        refreshed = sum(message.startswith("refreshed:") for message in messages)
        adopted = sum(message.startswith("adopted ") for message in messages)
        unchanged = sum(message.startswith("ok:") for message in messages)
        planned = sum(message.startswith("would ") for message in messages)
        conflicts = sum(message.startswith("conflict:") for message in messages)
        return (
            "install summary: "
            f"{installed} installed, {refreshed} refreshed, {adopted} adopted, "
            f"{unchanged} unchanged, {planned} planned, {conflicts} conflict"
        )
    if operation == "status":
        ok = sum(message.startswith("ok:") for message in messages)
        unmanaged = sum(message.startswith("unmanaged:") for message in messages)
        absent = sum(message.startswith("absent:") for message in messages)
        conflicts = sum(message.startswith("conflict:") for message in messages)
        pending = sum(message.startswith("would recover") or message.startswith("interrupted") for message in messages)
        return f"status summary: {ok} ok, {unmanaged + conflicts} conflict, {absent} absent, {pending} pending"
    if operation == "uninstall":
        removed = sum(message.startswith("removed:") for message in messages)
        kept = sum(message.startswith("kept:") for message in messages)
        absent = sum(message.startswith("absent:") for message in messages)
        planned = sum(message.startswith("would ") for message in messages)
        conflicts = sum(message.startswith("conflict:") for message in messages)
        return (
            "uninstall summary: "
            f"{removed} removed, {kept} kept, {absent} absent, {planned} planned, {conflicts} conflict"
        )
    if operation == "retire":
        retired = sum(message.startswith("retired historical alias:") for message in messages)
        kept = sum(message.startswith("kept historical alias") for message in messages)
        forgotten = sum(message.startswith("forgot missing") for message in messages)
        planned = sum(message.startswith("would ") for message in messages)
        return (
            "alias retirement summary: "
            f"{retired} retired, {kept} kept, {forgotten} forgotten, {planned} planned"
        )
    raise ValueError(f"unsupported operator lifecycle summary: {operation}")


def validate_bin_dir(config: Config) -> None:
    bin_dir = config.bin_dir
    if not bin_dir.is_absolute():
        raise OperatorToolsError("bin directory must be absolute")
    if bin_dir == Path(bin_dir.anchor) or bin_dir == config.repo_root or config.repo_root in bin_dir.parents:
        raise OperatorToolsError(f"unsafe operator-tools bin directory: {bin_dir}")
    if config.require_path and os.path.normcase(str(bin_dir)) not in path_entries():
        raise HostPreconditionError(
            f"operator-tools bin directory is not on PATH: {bin_dir}; {path_guidance(bin_dir)}"
        )
    current = bin_dir
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise OperatorToolsError(f"operator-tools bin ancestor is not a physical directory: {current}")
    if hasattr(os, "getuid") and current.stat().st_uid != os.getuid():
        raise OperatorToolsError(f"operator-tools bin ancestor is not owned by the current user: {current}")
    if bin_dir.exists():
        if bin_dir.is_symlink() or not bin_dir.is_dir():
            raise OperatorToolsError(f"operator-tools bin must be a physical directory: {bin_dir}")
        if hasattr(os, "getuid") and bin_dir.stat().st_uid != os.getuid():
            raise OperatorToolsError(f"operator-tools bin is not owned by the current user: {bin_dir}")


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def bash_interpreter(candidates: tuple[Path, ...] | None = None) -> Path:
    """Return the first admissible absolute bash for the dispatcher's shebang.

    A candidate is admissible when it is absolute, free of whitespace (a shebang cannot be quoted,
    so the kernel would split the interpreter word), and an executable regular file. Nothing is
    executed to decide this: the probe is a capability question about the host, and the answer is
    rendered into the installed bytes.

    When no candidate is admissible this raises the ordinary ``OperatorToolsError`` -- exit 2, the
    same class as the sibling "pinned <tool> is not an executable file" refusals -- rather than the
    ``HostPreconditionError`` exit-3 class, which stays reserved for the one raise site its own
    docstring names. The refusal names every path it probed, and it happens in ``desired_files()``
    before any file is written.

    The probe list is read from the module at CALL time, not bound as a default argument value: a
    default would be captured at import and the host-shape seam would be unpatchable, which is the
    difference between testing this platform rule and testing the machine the suite happens to run
    on.
    """
    candidates = BASH_INTERPRETER_CANDIDATES if candidates is None else candidates
    for candidate in candidates:
        text = str(candidate)
        if not candidate.is_absolute() or any(character.isspace() for character in text):
            continue
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    probed = ", ".join(str(candidate) for candidate in candidates) or "no candidate"
    raise OperatorToolsError(
        "cannot resolve a bash interpreter for the ccodex dispatcher; none of "
        f"{probed} is an executable file on this host"
    )


def mise_executable(config: Config, tool: str) -> Path:
    configured_paths = {
        "ocx": config.ocx_path,
        "jq": config.jq_path,
        "uv": config.uv_path,
        "node": config.node_path,
    }
    if configured := configured_paths[tool]:
        path = absolute(configured)
    else:
        try:
            value = subprocess.run(
                ["mise", "-C", str(config.repo_root), "which", tool],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise OperatorToolsError(
                f"cannot resolve the pinned {tool}; run `mise --locked install` in {config.repo_root}"
            ) from exc
        path = absolute(Path(value))
    if not path.is_file() or not os.access(path, os.X_OK):
        raise OperatorToolsError(f"pinned {tool} is not an executable file: {path}")
    return path


def sdlc_python_executable(config: Config, uv: Path) -> Path:
    """Resolve and verify the exact uv-managed interpreter for read-only SDLC inspection.

    The returned absolute executable is rendered into the dispatcher so daily reads never need
    to invoke uv or select an interpreter from the caller's PATH. `sdlc_python_path` is an
    injection seam for isolated tests; it is still subjected to the same exact-version check.
    """
    if config.sdlc_python_path is not None:
        candidate = absolute(config.sdlc_python_path)
    else:
        try:
            resolved = subprocess.run(
                [
                    str(uv),
                    "python",
                    "find",
                    "--managed-python",
                    "--no-config",
                    "--no-project",
                    "--offline",
                    "--no-python-downloads",
                    "3.12.11",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise OperatorToolsError(
                "cannot resolve uv-managed Python 3.12.11; run `mise --locked install` in "
                f"{config.repo_root}"
            ) from exc
        candidate = absolute(Path(resolved))
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise OperatorToolsError(f"uv-managed Python 3.12.11 is not an executable file: {candidate}")
    try:
        observed = subprocess.run(
            [str(candidate), "-I", "-B", "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise OperatorToolsError(f"cannot execute uv-managed Python 3.12.11: {candidate}") from exc
    if observed != "3.12.11":
        raise OperatorToolsError(
            f"uv-managed Python must be exactly 3.12.11, got {observed or 'no version'}: {candidate}"
        )
    return candidate


def desired_files(config: Config) -> dict[str, bytes]:
    statusline = config.repo_root / "assets" / "claude" / "statusline-command.sh"
    launcher = config.repo_root / "scripts" / "opencodex-claude.sh"
    templates = config.repo_root / "assets" / "launchers"
    sources = (statusline, launcher, templates / "ccodex.in")
    for path in sources:
        if not path.is_file():
            raise OperatorToolsError(f"required operator-tools source is missing: {path}")
    # Resolved before the pinned toolchain on purpose: it is the cheapest, purely local host fact,
    # and it is the one that decides whether the file this function returns could ever exec at all.
    bash = bash_interpreter()
    ocx = mise_executable(config, "ocx")
    jq = mise_executable(config, "jq")
    uv = mise_executable(config, "uv")
    # The pinned `ocx` is a `#!/usr/bin/env node` script, so binding its path is not the whole
    # binding: the kernel resolves `node` from the CHILD's PATH, and a fresh container with mise's
    # shim directory off PATH killed every gateway verb while the bound ocx sat there executable
    # (agentic-sdlc-21f4). Resolved through the same reviewed toolchain as the other three, so the
    # interpreter is the tree's pinned node rather than whatever the caller happens to have.
    node = mise_executable(config, "node")
    sdlc_python = sdlc_python_executable(config, uv)
    # The dispatcher resolves its root at run time from AGENTIC_SDLC_ROOT, falling back to this
    # install-time value, so a clone that later moves to a managed path can be pointed at without a
    # reinstall. Pinned runtime executables are deliberately absolute: daily use must not depend on
    # ambient PATH or re-evaluate repository-scoped mise. Values are shell-quoted because roots and
    # tool stores may contain spaces or quotes.
    #
    # @PINNED_BASH@ is the one substitution that is NOT shell-quoted, because it is the shebang: the
    # kernel reads that line literally and a quote character would become part of the interpreter
    # path. bash_interpreter() is what makes that safe, by admitting no whitespace-bearing path.
    dispatcher = (
        (templates / "ccodex.in")
        .read_text(encoding="utf-8")
        .replace("@CANONICAL_LAUNCHER@", shell_quote(str(launcher)))
        .replace("@CANONICAL_ROOT@", shell_quote(str(config.repo_root)))
        .replace("@PINNED_BASH@", str(bash))
        .replace("@PINNED_OCX@", shell_quote(str(ocx)))
        .replace("@PINNED_JQ@", shell_quote(str(jq)))
        .replace("@PINNED_UV@", shell_quote(str(uv)))
        .replace("@PINNED_NODE@", shell_quote(str(node)))
        .replace("@PINNED_SDLC_PYTHON@", shell_quote(str(sdlc_python)))
    )
    # An unsubstituted placeholder is exactly the defect class the shebang pin exists to close: it
    # renders a file that installs cleanly and cannot exec. Fail closed instead of shipping it.
    for leftover in ("@CANDIDATE_", "@CANONICAL_", "@PINNED_"):
        if leftover in dispatcher:
            raise OperatorToolsError(
                f"the ccodex dispatcher template has an unsubstituted {leftover}placeholder: "
                f"{templates / 'ccodex.in'}"
            )
    return {
        "agentic-sdlc-statusline": statusline.read_bytes(),
        "ccodex": dispatcher.encode(),
    }


def empty_state() -> dict[str, object]:
    return {"version": STATE_VERSION, "entries": {}, "pending": None}


def valid_record(record: Any, key: str) -> bool:
    return (
        isinstance(record, dict)
        and set(record) == {"path", "digest", "removable"}
        and record.get("path") == key
        and isinstance(record.get("digest"), str)
        and len(record["digest"]) == 64
        and record.get("removable") in {"true", "false"}
    )


def validate_pending(config: Config, state: dict[str, object]) -> None:
    pending = state.get("pending")
    if pending is None:
        return
    if not isinstance(pending, dict) or pending.get("operation") not in {"install", "refresh", "uninstall"}:
        raise OperatorToolsError(f"invalid operator-tools pending operation: {config.state_path}")
    key = pending.get("path")
    if not isinstance(key, str) or Path(key).parent != config.bin_dir or Path(key).name not in RECOGNIZED_COMMANDS:
        raise OperatorToolsError(f"invalid operator-tools pending path: {key}")
    before, after = pending.get("before"), pending.get("after")
    if before is not None and not valid_record(before, key):
        raise OperatorToolsError(f"invalid operator-tools pending before record: {key}")
    if after is not None and not valid_record(after, key):
        raise OperatorToolsError(f"invalid operator-tools pending after record: {key}")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    operation = pending["operation"]
    valid = (
        operation == "install" and before is None and after is not None and key not in entries
    ) or (
        operation == "refresh" and before is not None and after is not None
        and entries.get(key) == before and before["digest"] != after["digest"]
        and before["removable"] == after["removable"]
    ) or (
        operation == "uninstall" and before is not None and after is None and entries.get(key) == before
    )
    if not valid:
        raise OperatorToolsError(f"invalid operator-tools pending transition: {key}")


def load_state(path: Path, config: Config | None = None) -> dict[str, object]:
    if not path.exists():
        return empty_state()
    if path.is_symlink():
        raise OperatorToolsError(f"operator-tools state must not be a link: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorToolsError(f"cannot read operator-tools state {path}: {exc}") from exc
    if value.get("version") == LEGACY_STATE_VERSION and isinstance(value.get("entries"), dict):
        value = {"version": STATE_VERSION, "entries": value["entries"], "pending": None}
    if value.get("version") != STATE_VERSION or not isinstance(value.get("entries"), dict) or "pending" not in value:
        raise OperatorToolsError(f"invalid operator-tools state: {path}")
    for key, record in value["entries"].items():
        if not isinstance(key, str) or Path(key).name not in RECOGNIZED_COMMANDS or not valid_record(record, key):
            raise OperatorToolsError(f"invalid operator-tools ownership record: {key}")
    if config is not None:
        validate_pending(config, value)
    return value


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_mkdir(path: Path, mode: int = 0o700) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=mode)
        sync_directory(directory)
        sync_directory(directory.parent)


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    durable_mkdir(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            if sys.platform == "darwin":
                import fcntl
                fcntl.fcntl(handle.fileno(), fcntl.F_FULLFSYNC)
            else:
                os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def durable_unlink(path: Path) -> None:
    path.unlink()
    sync_directory(path.parent)


def write_state(config: Config, state: dict[str, object]) -> None:
    if config.dry_run:
        return
    content = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
    atomic_write(config.state_path, content, 0o600)


@contextmanager
def lifecycle_lock(config: Config) -> Iterator[None]:
    if config.dry_run:
        yield
        return
    durable_mkdir(config.lock_path.parent)
    descriptor = os.open(config.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def live_matches(path: Path, record: dict[str, str]) -> bool:
    return path.is_file() and not path.is_symlink() and digest_file(path) == record["digest"]


def recover_pending(config: Config, state: dict[str, object], *, read_only: bool) -> str | None:
    pending = state.get("pending")
    if pending is None:
        return None
    assert isinstance(pending, dict)
    path = Path(pending["path"])
    operation = pending["operation"]
    before = pending.get("before")
    after = pending.get("after")
    if path.parent.exists():
        sync_directory(path.parent)
    outcome: str | None = None
    if operation == "install":
        if not path.exists() and not path.is_symlink():
            outcome = "abort"
        elif isinstance(after, dict) and live_matches(path, after):
            outcome = "commit"
    elif operation == "refresh":
        if isinstance(before, dict) and live_matches(path, before):
            outcome = "abort"
        elif isinstance(after, dict) and live_matches(path, after):
            outcome = "commit"
    elif operation == "uninstall":
        if isinstance(before, dict) and live_matches(path, before):
            outcome = "abort"
        elif not path.exists() and not path.is_symlink():
            outcome = "commit"
    if outcome is None:
        raise OperatorToolsError(f"interrupted operator-tools {operation} conflicts with current file: {path}")
    if read_only:
        return f"would recover {outcome}: {path}"
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    key = str(path)
    if outcome == "commit":
        if operation in {"install", "refresh"}:
            entries[key] = after  # type: ignore[assignment]
        else:
            entries.pop(key, None)
    state["pending"] = None
    write_state(config, state)
    return f"recovered {outcome}: {path}"


def exact_owned_statusline(config: Config) -> Path:
    path = config.bin_dir / "agentic-sdlc-statusline"
    state = load_state(config.state_path, config)
    if state.get("pending") is not None:
        raise OperatorToolsError("the operator-tools lifecycle has an interrupted pending operation")
    record = state["entries"].get(str(path))  # type: ignore[index]
    if not isinstance(record, dict) or not live_matches(path, record):
        raise OperatorToolsError("the packaged statusline is not an installed owned operator tool")
    return path


def arm(config: Config, state: dict[str, object], operation: str, path: Path, before: Any, after: Any) -> None:
    state["pending"] = {
        "operation": operation,
        "path": str(path),
        "before": before,
        "after": after,
    }
    write_state(config, state)


def commit_pending(config: Config, state: dict[str, object]) -> None:
    pending = state["pending"]
    assert isinstance(pending, dict)
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    key = pending["path"]
    if pending["operation"] in {"install", "refresh"}:
        entries[key] = pending["after"]
    else:
        entries.pop(key, None)
    state["pending"] = None
    write_state(config, state)


def _install(config: Config) -> tuple[int, list[str]]:
    desired = desired_files(config)
    state = load_state(config.state_path, config)
    messages: list[str] = []
    if state.get("pending") is not None:
        if config.dry_run:
            messages.append(recover_pending(config, state, read_only=True) or "")
            messages.append(operator_summary("install", messages))
            return 1, messages
        messages.append(recover_pending(config, state, read_only=False) or "")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    partial = False
    for name, content in desired.items():
        path = config.bin_dir / name
        key = str(path)
        wanted = digest_bytes(content)
        record = entries.get(key)
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                partial = True; messages.extend(conflict_messages(path, "an unsupported non-file entry already exists")); continue
            actual = digest_file(path)
            if record is None:
                if actual == wanted:
                    messages.append(f"adopted (preserved on uninstall): {path}")
                    if not config.dry_run:
                        entries[key] = {"path": key, "digest": actual, "removable": "false"}
                        write_state(config, state)
                else:
                    partial = True; messages.extend(conflict_messages(path, "a foreign file already exists"))
                continue
            if actual != record.get("digest"):
                partial = True; messages.extend(conflict_messages(path, "owned file changed")); continue
            if actual == wanted:
                messages.append(f"ok: {path}"); continue
            if config.dry_run:
                messages.append(f"would refresh: {path}"); continue
            after = {"path": key, "digest": wanted, "removable": record["removable"]}
            arm(config, state, "refresh", path, record, after)
            atomic_write(path, content, 0o755)
            commit_pending(config, state)
            messages.append(f"refreshed: {path}"); continue
        if config.dry_run:
            messages.append(f"would install: {path}"); continue
        durable_mkdir(config.bin_dir)
        after = {"path": key, "digest": wanted, "removable": "true"}
        arm(config, state, "install", path, None, after)
        atomic_write(path, content, 0o755)
        commit_pending(config, state)
        messages.append(f"installed: {path}")
    messages.append(operator_summary("install", messages))
    return (1 if partial else 0), messages


def install(config: Config) -> tuple[int, list[str]]:
    # validate_bin_dir() runs BEFORE the lock is even taken, so a host precondition refusal
    # never creates the lock file or its parent directories -- lifecycle_lock() itself is an
    # effect (durable_mkdir + O_CREAT), and admitting it before the precondition check would
    # make the "before any effect" refusal untrue.
    validate_bin_dir(config)
    with lifecycle_lock(config):
        return _install(config)


def _status(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    state = load_state(config.state_path, config)
    messages: list[str] = []
    partial = False
    if state.get("pending") is not None:
        try:
            messages.append(recover_pending(config, state, read_only=True) or "")
        except OperatorToolsError as exc:
            messages.append(str(exc))
        partial = True
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    for name in DESIRED_COMMANDS:
        path = config.bin_dir / name
        record = entries.get(str(path))
        if record is None:
            # `unmanaged` and `absent` are different facts. A desired file that is not present is
            # required/absent; an existing file outside this lifecycle is unmanaged. Historical
            # aliases are handled below and are never classified as required or absent.
            partial = True
            if path.exists() or path.is_symlink():
                messages.append(f"unmanaged: {path}")
                messages.append(
                    f"preserved: {path} (an unmanaged file already exists; inspect and resolve it before retrying)"
                )
            else:
                messages.append(f"absent: {path} (not installed; run `mise run operator-tools:install`)")
        elif not live_matches(path, record):
            partial = True; messages.extend(conflict_messages(path, "owned file changed"))
        else:
            messages.append(f"ok: {path}")
    for name in HISTORICAL_ALIASES:
        path = config.bin_dir / name
        record = entries.get(str(path))
        if record is None:
            if path.exists() or path.is_symlink():
                messages.append(f"kept historical alias (unmanaged): {path}")
            continue
        if not path.exists() and not path.is_symlink():
            messages.append(f"historical alias ownership record retained; file is missing: {path}")
        elif not live_matches(path, record):
            partial = True
            messages.extend(conflict_messages(path, "historical alias changed and was preserved"))
        elif record.get("removable") == "false":
            messages.append(f"kept historical alias (adopted pre-existing entry): {path}")
        else:
            messages.append(
                f"retirable historical alias: {path} "
                "(run `mise run operator-tools:retire-aliases`; use `ccodex launch|ultracode`)"
            )
    messages.append(operator_summary("status", messages))
    return (1 if partial else 0), messages


def _retire_aliases(config: Config) -> tuple[int, list[str]]:
    state = load_state(config.state_path, config)
    messages: list[str] = []
    if state.get("pending") is not None:
        if config.dry_run:
            messages.append(recover_pending(config, state, read_only=True) or "")
            messages.append(operator_summary("retire", messages))
            return 1, messages
        messages.append(recover_pending(config, state, read_only=False) or "")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    partial = False
    for name in HISTORICAL_ALIASES:
        path = config.bin_dir / name
        key = str(path)
        record = entries.get(key)
        if record is None:
            if path.exists() or path.is_symlink():
                messages.append(f"kept historical alias (unmanaged): {path}")
            continue
        if not path.exists() and not path.is_symlink():
            if config.dry_run:
                messages.append(f"would forget missing historical alias ownership: {path}")
            else:
                entries.pop(key)
                write_state(config, state)
                messages.append(f"forgot missing historical alias ownership: {path}")
            continue
        if not live_matches(path, record):
            partial = True
            messages.append(f"kept historical alias (changed since install): {path}")
            messages.append(f"preserved: {path} (inspect it and move to `ccodex launch|ultracode` manually)")
            continue
        if record.get("removable") == "false":
            messages.append(f"kept historical alias (adopted pre-existing entry): {path}")
            continue
        if config.dry_run:
            messages.append(f"would retire historical alias: {path}")
            continue
        arm(config, state, "uninstall", path, record, None)
        durable_unlink(path)
        commit_pending(config, state)
        messages.append(f"retired historical alias: {path}")
    if not messages:
        messages.append("no historical aliases are owned or present")
    messages.append(operator_summary("retire", messages))
    return (1 if partial else 0), messages


def retire_aliases(config: Config) -> tuple[int, list[str]]:
    # See install()'s comment: the precondition check must precede lifecycle_lock() itself.
    validate_bin_dir(config)
    with lifecycle_lock(config):
        return _retire_aliases(config)


def state_snapshot(path: Path) -> tuple[bool, bytes | None]:
    if not path.exists():
        return False, None
    if path.is_symlink() or not path.is_file():
        raise OperatorToolsError(f"operator-tools state must be a regular file: {path}")
    return True, path.read_bytes()


def _readonly_json_document(content: bytes, path: Path) -> dict[str, object]:
    """Decode one ownership document without duplicate-key or non-finite ambiguity."""
    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON value {value!r}")

    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        # Parser diagnostics can include document keys and values.  The read-only report is an
        # external surface, so keep that untrusted state body out of it.
        raise OperatorToolsError("operator-tools state is malformed") from exc
    if not isinstance(value, dict):
        raise OperatorToolsError("operator-tools state is malformed")
    return value


def _readonly_read_file(path: Path) -> tuple[str, bytes | None, str | None]:
    """Read a regular file once and reject a changed inode/metadata witness as racy."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return "absent", None, None
    except OSError:
        return "unreadable", None, None
    if stat.S_ISLNK(before.st_mode):
        return "symlinked", None, None
    if not stat.S_ISREG(before.st_mode):
        return "unsupported", None, None
    try:
        content = path.read_bytes()
        after = os.lstat(path)
    except OSError:
        return "unreadable", None, None
    witness_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    witness_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if witness_before != witness_after:
        return "racy", None, None
    return "present", content, None


def _readonly_entry_state(path: Path, digest: str) -> tuple[str, str | None]:
    observed, content, detail = _readonly_read_file(path)
    if observed == "absent":
        return "absent", None
    if observed in {"symlinked", "unsupported", "unreadable", "racy"}:
        return observed, detail
    assert content is not None
    return ("owned", None) if digest_bytes(content) == digest else ("modified", None)


def _readonly_finding(code: str, message: str, path: Path) -> dict[str, str]:
    return {"code": code, "component": "operator-tools", "message": message, "path": str(path)}


def readonly_projection(config: Config) -> dict[str, object]:
    """Return a pure, structured operator-tools observation.

    This deliberately does not call the legacy lifecycle's status or pending-recovery helpers.
    It neither acquires a lock nor normalizes/migrates/writes a state document.  Malformed and
    racy evidence is preserved as a typed finding so the caller can remain read-only.
    """
    state_path = config.state_path
    findings: list[dict[str, str]] = []
    entries: list[dict[str, str]] = []
    recovery: list[dict[str, str]] = []
    observed, content, _detail = _readonly_read_file(state_path)
    state: dict[str, object] | None = None
    projection_state = "absent"

    if observed == "present":
        assert content is not None
        try:
            state = _readonly_json_document(content, state_path)
        except OperatorToolsError:
            findings.append(_readonly_finding("state-malformed", "operator-tools state is malformed", state_path))
            projection_state = "unreadable"
    elif observed != "absent":
        code = f"state-{observed}"
        findings.append(_readonly_finding(code, f"operator-tools state is {observed}", state_path))
        projection_state = "unreadable" if observed == "unreadable" else "blocked"

    records: dict[str, object] = {}
    pending: object = None
    if state is not None:
        if set(state) != {"version", "entries", "pending"}:
            findings.append(_readonly_finding("state-malformed", "operator-tools state has an unknown field", state_path))
            projection_state = "unreadable"
        elif state.get("version") != STATE_VERSION:
            findings.append(
                _readonly_finding(
                    "state-unsupported",
                    "operator-tools state version is not readable without migration",
                    state_path,
                )
            )
            projection_state = "blocked"
        elif not isinstance(state.get("entries"), dict):
            findings.append(_readonly_finding("state-malformed", "operator-tools entries are not an object", state_path))
            projection_state = "unreadable"
        else:
            records = state["entries"]
            pending = state["pending"]
            for key, record in records.items():
                if (
                    not isinstance(key, str)
                    or not valid_record(record, key)
                    or Path(key).parent != config.bin_dir
                    or Path(key).name not in RECOGNIZED_COMMANDS
                ):
                    findings.append(
                        _readonly_finding("state-malformed", "operator-tools ownership record is invalid", state_path)
                    )
                    projection_state = "unreadable"
                    records = {}
                    break
            if projection_state != "unreadable" and pending is not None:
                try:
                    validate_pending(config, {"version": STATE_VERSION, "entries": records, "pending": pending})
                except OperatorToolsError:
                    findings.append(
                        _readonly_finding(
                            "pending-invalid", "operator-tools pending transition is malformed", state_path
                        )
                    )
                    projection_state = "blocked"
                else:
                    assert isinstance(pending, dict)
                    recovery.append(
                        {
                            "action": "lifecycle-dry-run",
                            "component": "operator-tools",
                            "path": str(config.bin_dir / Path(pending["path"]).name),
                            "state": "pending",
                        }
                    )
                    findings.append(
                        _readonly_finding(
                            "pending-recovery",
                            "operator-tools has an interrupted lifecycle transition; only a lifecycle dry run may propose recovery",
                            state_path,
                        )
                    )
                    projection_state = "blocked"

    for name in DESIRED_COMMANDS:
        path = config.bin_dir / name
        record = records.get(str(path))
        if isinstance(record, dict):
            entry_state, _detail = _readonly_entry_state(path, str(record["digest"]))
            entries.append({"name": name, "path": str(path), "state": entry_state})
            if entry_state != "owned":
                code = "owned-entry-racy" if entry_state == "racy" else "owned-entry-conflict"
                findings.append(_readonly_finding(code, f"owned operator command is {entry_state}", path))
                if projection_state not in {"blocked", "unreadable"}:
                    projection_state = "degraded"
        else:
            observed, _content, _detail = _readonly_read_file(path)
            entry_state = "foreign" if observed == "present" else observed
            entries.append({"name": name, "path": str(path), "state": entry_state})
            if entry_state != "absent":
                findings.append(_readonly_finding("foreign-entry", f"unowned operator command is {entry_state}", path))
                if projection_state not in {"blocked", "unreadable"}:
                    projection_state = "degraded"

    # Historical aliases are lifecycle evidence when an ownership record or a real file remains,
    # but fresh installs deliberately neither create nor require them.  Keep their established
    # status semantics: an unowned or missing historical alias is retained as information, while
    # a changed owned alias is a conflict.
    for name in HISTORICAL_ALIASES:
        path = config.bin_dir / name
        record = records.get(str(path))
        if isinstance(record, dict):
            entry_state, _detail = _readonly_entry_state(path, str(record["digest"]))
            if entry_state == "absent":
                # A retained historical ownership record is not a requirement to recreate the
                # alias.  Match status: preserve the fact internally without reporting it as an
                # absent command in this public projection.
                continue
            entries.append({"name": name, "path": str(path), "state": entry_state})
            if entry_state != "owned" and entry_state != "absent":
                code = "owned-entry-racy" if entry_state == "racy" else "owned-entry-conflict"
                findings.append(_readonly_finding(code, f"owned historical alias is {entry_state}", path))
                if projection_state not in {"blocked", "unreadable"}:
                    projection_state = "degraded"
            continue
        observed, _content, _detail = _readonly_read_file(path)
        if observed == "absent":
            continue
        entry_state = "foreign" if observed == "present" else observed
        entries.append({"name": name, "path": str(path), "state": entry_state})

    if projection_state == "absent" and records:
        desired_entries = [entry for entry in entries if entry["name"] in DESIRED_COMMANDS]
        projection_state = "healthy" if all(entry["state"] == "owned" for entry in desired_entries) else "degraded"
    elif projection_state == "absent" and any(entry["state"] != "absent" for entry in entries):
        projection_state = "degraded"
    return {
        "entries": entries,
        "findings": findings,
        "recovery": recovery,
        "state": projection_state,
        "state_paths": [str(state_path)],
    }


def status(config: Config) -> tuple[int, list[str]]:
    # Status stays lock-free so a never-installed inspection creates nothing. Detect a writer
    # racing the scan by comparing the durable ownership document before and after it.
    before = state_snapshot(config.state_path)
    code, messages = _status(config)
    after = state_snapshot(config.state_path)
    if after != before:
        messages.insert(-1, "interrupted status: ownership state changed during inspection; retry")
        messages[-1] = operator_summary("status", messages[:-1])
        return 1, messages
    return code, messages


def _uninstall(config: Config) -> tuple[int, list[str]]:
    state = load_state(config.state_path, config)
    messages: list[str] = []
    if state.get("pending") is not None:
        if config.dry_run:
            messages.append(recover_pending(config, state, read_only=True) or "")
            messages.append(operator_summary("uninstall", messages))
            return 1, messages
        messages.append(recover_pending(config, state, read_only=False) or "")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    partial = False
    for name in RECOGNIZED_COMMANDS:
        path = config.bin_dir / name; key = str(path); record = entries.get(key)
        if record is None:
            continue
        if not path.exists() and not path.is_symlink():
            if not config.dry_run:
                entries.pop(key); write_state(config, state)
            messages.append(f"absent: {path}"); continue
        if not live_matches(path, record):
            partial = True; messages.extend(conflict_messages(path, "owned file changed")); continue
        if record.get("removable") == "false":
            messages.append(f"kept: {path} (adopted pre-existing entry)"); continue
        if config.dry_run:
            messages.append(f"would remove: {path}"); continue
        arm(config, state, "uninstall", path, record, None)
        durable_unlink(path)
        commit_pending(config, state)
        messages.append(f"removed: {path}")
    messages.append(operator_summary("uninstall", messages))
    return (1 if partial else 0), messages


def uninstall(config: Config) -> tuple[int, list[str]]:
    # See install()'s comment: the precondition check must precede lifecycle_lock() itself.
    validate_bin_dir(config)
    with lifecycle_lock(config):
        return _uninstall(config)


def self_test(repo_root: Path) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory(prefix="agentic-sdlc-operator-tools-") as temp:
        root = Path(temp); home = root / "home"; bin_dir = home / ".local" / "bin"
        config = Config(repo_root, home, bin_dir, root / "state", require_path=False)
        installed = install(config); checked = status(config); retired = retire_aliases(config); removed = uninstall(config)
        if installed[0] or checked[0] or retired[0] or removed[0] or any((bin_dir / name).exists() for name in RECOGNIZED_COMMANDS):
            return 1, installed[1] + checked[1] + retired[1] + removed[1] + ["operator-tools self-test failed"]
    return 0, ["operator-tools self-test passed"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "The target bin directory must already exist under a user-owned physical path and be "
            "on PATH. This lifecycle never creates shell aliases or edits PATH. Status and --dry-run "
            "are read-only."
        ),
    )
    parser.add_argument(
        "command",
        choices=("install", "status", "retire-aliases", "uninstall", "self-test"),
        help="operator-command lifecycle action",
    )
    parser.add_argument(
        "--home",
        type=Path,
        # The default is resolved in main(), not here: argparse evaluates a default at parser
        # construction, and Path.home() raises RuntimeError on a host with no home variable --
        # before main()'s own named refusals could print.
        default=None,
        metavar="PATH",
        help="operator home used to derive default bin and state directories (default: the current user's home)",
    )
    parser.add_argument(
        "--bin-dir",
        type=Path,
        metavar="PATH",
        help="existing user-owned PATH directory to receive commands",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        metavar="PATH",
        help="ownership-state root (default: XDG_STATE_HOME or HOME/.local/state)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report install or removal changes without writing",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # The platform refusal must be the FIRST thing an unsupported host reaches: a scrubbed
    # Windows environment has no USERPROFILE, so any Path.home() evaluated before this line
    # (including an eager argparse default) dies as an unnamed RuntimeError instead.
    if os.name == "nt":
        print("fatal: operator tools are currently supported on Unix, WSL, and macOS only", file=sys.stderr)
        return 2
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    if args.command == "self-test":
        code, messages = self_test(repo_root)
    else:
        home = absolute(args.home if args.home is not None else Path.home())
        config = Config(
            repo_root,
            home,
            absolute(args.bin_dir) if args.bin_dir else default_bin_dir(home),
            absolute(args.state_root) if args.state_root else state_root_for(home),
            args.dry_run,
        )
        try:
            code, messages = {
                "install": install,
                "status": status,
                "retire-aliases": retire_aliases,
                "uninstall": uninstall,
            }[args.command](config)
        except HostPreconditionError as exc:
            # Decision 9's clean-refusal-before-effect class: this exact exception type is
            # raised only from validate_bin_dir(), before any of the four verbs above has
            # written anything, so no effect boundary is crossed by reporting it here.
            print(f"fatal: {exc}", file=sys.stderr)
            return 3
        except OperatorToolsError as exc:
            print(f"fatal: {exc}", file=sys.stderr)
            return 2
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
