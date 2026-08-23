#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Pure one-output renderer for the P2 activation transaction."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "agentic-sdlc/instruction-manifest@2"
KINDS = {"root_agents", "root_claude", "subtree_agents", "claude_rule"}
_REL_RE = re.compile(r"[^/\\\x00]+")

# EXITS, as one derivation point (product-spec Implementation Decision 9). This module only ever
# produces the two codes below: `main` has exactly one refusal path (`GeneratorError`) and one
# success path, so no other code is named here.
#: The one selected output rendered and its canonical result document was written to stdout.
EXIT_OK = 0
#: A `GeneratorError` was raised: an unusable manifest (missing, malformed, non-canonical,
#: schema-invalid) or an unusable `--entry` selection. Nothing was written to stdout.
EXIT_INPUT = 2


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--entry", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _load(args.manifest)
        rendered = render_selected(manifest, args.entry, lambda _: ({"kind": "absent", "identity": None}, None))
        result = {"schema": "agentic-sdlc/instruction-render@2", "path": rendered["path"], "action": rendered["action"], "sha256": hashlib.sha256(rendered["content"]).hexdigest()}
        sys.stdout.buffer.write(_canonical(result))
        return EXIT_OK
    except GeneratorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
