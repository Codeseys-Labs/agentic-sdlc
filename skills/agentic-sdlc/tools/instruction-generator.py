#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Render, apply, and classify one repository's marked instruction block.

`plan --manifest --entry` renders one selected output and prints its canonical result document.

`apply --target --manifest --entry` splices the same block into the target file, prints a unified
diff of before and after, and writes only when `--yes` is supplied, so approval and write are one
invocation and no approved-then-changed window exists between them.

`classify --target` answers exactly one of three verdicts about the repository's operating-contract
surface, and every one of them asks the operator before a baseline is proposed:

  * `brownfield` -- at least one contract surface is occupied, in Git's index or on disk, and each
    occupied surface is named. This is the only verdict settled by positive observation.
  * `greenfield` -- a PROPOSAL, not a licence to write: nothing is occupied, the repository holds at
    most one commit, and the working tree is clean. Confirm with the operator before writing.
  * `refuse-and-ask` -- anything else, with each reason named. Ask the operator.

`--target` must be the repository ROOT, and a subdirectory is refused by name at exit 2: occupancy
is measured at the supplied directory while commit count and cleanliness are repository-wide, so a
subdirectory would mix two scopes in one verdict.

A verdict is advisory evidence about what is on disk. It claims no readiness, ownership, or trust,
and it authorizes no write.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "agentic-sdlc/instruction-manifest@2"
CLASS_SCHEMA = "agentic-sdlc/repository-class@1"
KINDS = {"root_agents", "root_claude", "subtree_agents", "claude_rule"}
_REL_RE = re.compile(r"[^/\\\x00]+")

#: The operating-contract surfaces whose occupancy decides brownfield. Read in Git's index and on
#: disk, because either alone answers "occupied" for a surface the other does not know about.
CONTRACT_SURFACES = (
    "AGENTS.md",
    "CLAUDE.md",
    "mise.toml",
    "lefthook.yml",
    ".seeds",
    "docs/adr",
    ".github",
    ".gitlab-ci.yml",
    ".agentic-sdlc",
)

#: Exec resolution is carried across; everything else is asserted, so no ambient `GIT_*` variable
#: and no system or global config can change what a read-only observation reports.
_EXEC_RESOLUTION_ENV = ("PATH", "PATHEXT", "SYSTEMROOT")
_GIT_ENVIRONMENT = {
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_ATTR_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "LC_ALL": "C",
    "LANG": "C",
}

# EXITS, as one derivation point (product-spec Implementation Decision 9).
#: The selected verb completed: a rendered result document, a classification document, or an
#: applied write, on stdout.
EXIT_OK = 0
#: A `GeneratorError` was raised: an unusable manifest (missing, malformed, non-canonical,
#: schema-invalid), an unusable `--entry` selection, an unusable `--target`, a refused target node,
#: or an entry whose parent directory is absent in the target. Nothing was written to the target.
EXIT_INPUT = 2
#: `apply` rendered a change and was not given `--yes`. The diff is on stdout, the target is
#: untouched, and the same invocation with `--yes` is the approval.
EXIT_REFUSED = 3


class GeneratorError(ValueError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GeneratorError(f"invalid {label} schema")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or unicodedata.normalize("NFC", value) != value:
        raise GeneratorError(f"invalid {label}")
    return value


def _relative_path(value: Any) -> str:
    path = _text(value, "path")
    if not path or path.startswith("/") or "\\" in path:
        raise GeneratorError("invalid path")
    pieces = path.split("/")
    if any(piece in {"", ".", ".."} or not _REL_RE.fullmatch(piece) for piece in pieces):
        raise GeneratorError("invalid path")
    return path


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = _exact(manifest, {"schema", "marker", "doctrine_pointer", "outputs"}, "manifest")
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise GeneratorError("unsupported manifest schema")
    marker = _exact(manifest["marker"], {"start", "end"}, "marker")
    start, end = _text(marker["start"], "marker start"), _text(marker["end"], "marker end")
    if not start or not end or start == end:
        raise GeneratorError("invalid marker")
    _text(manifest["doctrine_pointer"], "doctrine pointer")
    outputs = manifest["outputs"]
    if not isinstance(outputs, list) or not outputs:
        raise GeneratorError("outputs must be nonempty")
    seen: set[str] = set()
    for output in outputs:
        output = _exact(output, {"path", "kind", "prefix", "sections"}, "output")
        path = _relative_path(output["path"])
        if path in seen:
            raise GeneratorError("duplicate output path")
        seen.add(path)
        if output["kind"] not in KINDS:
            raise GeneratorError("invalid output kind")
        _text(output["prefix"], "prefix")
        sections = output["sections"]
        if not isinstance(sections, list):
            raise GeneratorError("invalid sections")
        for section in sections:
            section = _exact(section, {"key", "body"}, "section")
            if not _text(section["key"], "section key"):
                raise GeneratorError("empty section key")
            _text(section["body"], "section body")
    return manifest


def collect_output(manifest: dict[str, Any], selected_path: str) -> dict[str, Any]:
    validate_manifest(manifest)
    selected_path = _relative_path(selected_path)
    matches = [item for item in manifest["outputs"] if item["path"] == selected_path]
    if len(matches) != 1:
        raise GeneratorError("selected path is not an output")
    return matches[0]


def render_sections(sections: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"## {item['key']}\n{item['body'].rstrip()}".rstrip() for item in sections)


def _block(manifest: dict[str, Any], output: dict[str, Any]) -> str:
    body = render_sections(output["sections"])
    if output["kind"] in {"root_agents", "subtree_agents"}:
        pointer = manifest["doctrine_pointer"]
        doctrine = f"## doctrine\n{pointer}"
        body = f"{body}\n\n{doctrine}" if body else doctrine
    return f"{manifest['marker']['start']}\n{body}\n{manifest['marker']['end']}\n"


def locate_marked_block(text: str, start: str, end: str) -> tuple[int, int] | None:
    starts, ends = text.count(start), text.count(end)
    if starts == ends == 0:
        return None
    if starts != 1 or ends != 1:
        raise GeneratorError("malformed markers")
    left, right = text.index(start), text.index(end)
    if left >= right:
        raise GeneratorError("malformed markers")
    return left, right + len(end)


def render_create(manifest: dict[str, Any], output: dict[str, Any]) -> bytes:
    return (output["prefix"] + _block(manifest, output)).encode("utf-8")


def render_replace(old: bytes, manifest: dict[str, Any], output: dict[str, Any]) -> bytes:
    try:
        old_text = old.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GeneratorError("existing instruction is not UTF-8") from exc
    marker = manifest["marker"]
    found = locate_marked_block(old_text, marker["start"], marker["end"])
    block = _block(manifest, output)
    if found is None:
        separator = "" if not old_text or old_text.endswith("\n") else "\n"
        return (old_text + separator + ("\n" if old_text else "") + block).encode("utf-8")
    begin, end = found
    return (old_text[:begin] + block.rstrip("\n") + old_text[end:]).encode("utf-8")


def validate_rendered_output(rendered: dict[str, Any]) -> dict[str, Any]:
    _exact(rendered, {"path", "action", "content", "mode"}, "rendered output")
    if not isinstance(rendered["content"], bytes) or rendered["action"] not in {"create", "replace", "no-op"}:
        raise GeneratorError("invalid rendered output")
    if rendered["mode"] != 0o644:
        raise GeneratorError("invalid rendered mode")
    return rendered


def render_selected(
    manifest: dict[str, Any],
    selected_path: str,
    target_reader: Callable[[str], tuple[dict[str, Any], bytes | None]],
) -> dict[str, Any]:
    """Render exactly one selected output using only the declared target reader."""
    output = collect_output(manifest, selected_path)
    prestate, old = target_reader(output["path"])
    if not isinstance(prestate, dict) or prestate.get("kind") not in {"absent", "regular"}:
        raise GeneratorError("invalid target prestate")
    if prestate["kind"] == "absent":
        if old is not None:
            raise GeneratorError("absent target supplied bytes")
        content, action = render_create(manifest, output), "create"
    else:
        if not isinstance(old, bytes):
            raise GeneratorError("regular target missing bytes")
        content = render_replace(old, manifest, output)
        action = "no-op" if content == old else "replace"
    return validate_rendered_output({"path": output["path"], "action": action, "content": content, "mode": 0o644})


def read_target(path: Path) -> tuple[dict[str, Any], bytes | None]:
    """The target's prestate and bytes, opened so every non-regular node is refused at `EXIT_INPUT`.

    `O_NOFOLLOW` refuses a planted symlink where the platform defines it; where it does not
    (Windows), the explicit `islink` check below carries the same refusal, so the semantics
    survive the missing flag. `O_NONBLOCK` keeps a planted FIFO from blocking the open until a
    writer appears, so the refusal below is reached instead of the process hanging -- a POSIX-only
    concern, since Windows has no FIFOs reachable through this path, so the flag is likewise
    applied only where it exists. The raw descriptor is `fstat`ed before it becomes a file object,
    because wrapping a directory descriptor raises `IsADirectoryError` outside this function's
    refusal contract; the descriptor is closed on that refusal path.
    """
    if not hasattr(os, "O_NOFOLLOW") and os.path.islink(path):
        raise GeneratorError(f"refusing target {path}: it is a symbolic link")
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except FileNotFoundError:
        return {"kind": "absent", "identity": None}, None
    except OSError as exc:
        raise GeneratorError(f"refusing target {path}: {exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise GeneratorError(f"refusing target {path}: not a regular file")
    except BaseException:
        os.close(descriptor)
        raise
    with open(descriptor, "rb") as handle:
        return {"kind": "regular", "identity": None}, handle.read()


def unified_diff(before: bytes, after: bytes, label: str) -> str:
    old = before.decode("utf-8", "replace").splitlines(keepends=True)
    new = after.decode("utf-8", "replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(old, new, f"a/{label}", f"b/{label}"))


def write_target(path: Path, content: bytes) -> None:
    """Publish `content` at `path` through a same-directory temporary and `os.replace`.

    `os.replace` renames rather than opens, so it cannot be redirected through a symlink planted at
    the destination: the link itself is replaced. The directory is fsynced so the rename survives a
    crash as either the old bytes or the new ones, never a truncated file -- on POSIX. Windows
    cannot open a directory via `os.open` at all, so there is no stdlib parent-directory durability
    barrier there and the publication remains process-crash recoverable, not power-loss durable
    (the `scripts/install_skill_bundle.py` `fsync_directory` precedent).

    A manifest entry may name a nested path, so the parent is checked before `mkstemp` is asked to
    create a temporary inside it: a directory this tool does not create is a refusal that names that
    parent, not a `FileNotFoundError` out of the publication path.
    """
    if not path.parent.is_dir():
        raise GeneratorError(f"refusing to write {path}: its parent {path.parent} is not an existing directory")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".new")
    try:
        with open(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise
    if os.name == "nt":
        # No parent-directory durability barrier exists on Windows: the docstring above
        # records that the publication is process-crash recoverable, not power-loss durable.
        return
    parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def apply_entry(manifest: dict[str, Any], entry: str, target: Path, approved: bool) -> int:
    """Render one entry against the live target, print the diff, and write only when approved."""
    if not target.is_absolute() or not target.is_dir():
        raise GeneratorError(f"--target must be an absolute existing directory: {target}")
    observed: dict[str, bytes] = {}

    def reader(relative: str) -> tuple[dict[str, Any], bytes | None]:
        prestate, old = read_target(target / relative)
        observed["before"] = old or b""
        return prestate, old

    rendered = render_selected(manifest, entry, reader)
    sys.stdout.write(unified_diff(observed["before"], rendered["content"], rendered["path"]))
    if rendered["action"] == "no-op":
        print(f"no-op: {rendered['path']} already carries this block")
        return EXIT_OK
    if not approved:
        print(
            f"REFUSED: {rendered['path']} would be {rendered['action']}d and was not written; "
            "re-run this exact command with --yes to approve the diff above",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    write_target(target / rendered["path"], rendered["content"])
    print(f"{rendered['action']}: {rendered['path']}")
    return EXIT_OK


def _git(target: Path, *arguments: str, allow_failure: bool = False) -> tuple[int, str]:
    environment = {key: os.environ[key] for key in _EXEC_RESOLUTION_ENV if key in os.environ}
    environment.update(_GIT_ENVIRONMENT)
    try:
        completed = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(target), *arguments],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GeneratorError(f"cannot run git: {exc}") from exc
    if completed.returncode != 0 and not allow_failure:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise GeneratorError(f"git {arguments[0]} exited {completed.returncode} in {target}: {detail}")
    return completed.returncode, completed.stdout.decode("utf-8", "replace")


def _commit_count(target: Path) -> int:
    code, out = _git(target, "rev-list", "--count", "HEAD", allow_failure=True)
    if code != 0:
        _git(target, "rev-parse", "--git-dir")
        return 0
    return int(out.strip() or "0")


def classify_repository(target: Path) -> dict[str, Any]:
    """One of `brownfield`, `greenfield`, or `refuse-and-ask`; all three ask before a write.

    Refuses anything that is not the repository root, because the two halves of the question have
    different scopes: occupancy is read at the supplied directory, while commit count and working
    tree cleanliness are properties of the whole repository. Answering both from a subdirectory
    would report one verdict over two scopes.
    """
    if not target.is_absolute() or not target.is_dir():
        raise GeneratorError(f"--target must be an absolute existing directory: {target}")
    toplevel = _git(target, "rev-parse", "--show-toplevel")[1].strip()
    if not toplevel or Path(toplevel).resolve() != target.resolve():
        raise GeneratorError(f"--target is not a repository root; its root is {toplevel or 'unavailable'}: {target}")
    listed = [item for item in _git(target, "ls-files", "-z", "--", *CONTRACT_SURFACES)[1].split("\0") if item]
    occupied = sorted(
        surface
        for surface in CONTRACT_SURFACES
        if os.path.lexists(target / surface) or any(item == surface or item.startswith(f"{surface}/") for item in listed)
    )
    if occupied:
        reasons = [f"{surface} is an occupied operating-contract surface" for surface in occupied]
        return {"schema": CLASS_SCHEMA, "verdict": "brownfield", "occupied": occupied, "reasons": reasons, "ask": True}
    commits = _commit_count(target)
    dirty = [item for item in _git(target, "status", "--porcelain", "-z")[1].split("\0") if item]
    reasons = []
    if commits > 1:
        reasons.append(f"the repository already has {commits} commits")
    if dirty:
        reasons.append(f"the working tree is not clean ({len(dirty)} reported entries)")
    verdict = "refuse-and-ask" if reasons else "greenfield"
    return {"schema": CLASS_SCHEMA, "verdict": verdict, "occupied": [], "reasons": reasons, "ask": True}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode() + b"\n"


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeneratorError(f"invalid canonical manifest: {path}") from exc
    if _canonical(value) != raw:
        raise GeneratorError("manifest is not canonical")
    return validate_manifest(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "apply", "classify"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--entry")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--yes", action="store_true", help="approve the printed diff and write it in this same invocation")
    args = parser.parse_args(argv)
    try:
        if args.command == "classify":
            if args.target is None:
                raise GeneratorError("classify requires --target")
            sys.stdout.buffer.write(_canonical(classify_repository(args.target)))
            return EXIT_OK
        if args.manifest is None or args.entry is None:
            raise GeneratorError(f"{args.command} requires --manifest and --entry")
        manifest = _load(args.manifest)
        if args.command == "apply":
            if args.target is None:
                raise GeneratorError("apply requires --target")
            return apply_entry(manifest, args.entry, args.target, args.yes)
        rendered = render_selected(manifest, args.entry, lambda _: ({"kind": "absent", "identity": None}, None))
        result = {"schema": "agentic-sdlc/instruction-render@2", "path": rendered["path"], "action": rendered["action"], "sha256": hashlib.sha256(rendered["content"]).hexdigest()}
        sys.stdout.buffer.write(_canonical(result))
        return EXIT_OK
    except GeneratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
