#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Marker-aware hierarchical instruction generator (Lane A3).

A single InstructionManifest drives generation of the repository's agent-instruction
surface: the root ``AGENTS.md`` (canonical cross-host policy), a thin root ``CLAUDE.md``
(``@AGENTS.md`` import plus Claude routing), subtree ``AGENTS.md`` files, and
``.claude/rules/*.md``. Every generated file carries exactly one marked region
(``<!-- agentic-sdlc:start -->`` / ``<!-- agentic-sdlc:end -->``); content outside the
markers is hand-authored and never touched.

The generator is dry-run-first, refuse-on-conflict, and idempotent by rerun. It is the
write-executor that the ``/sdlc-init`` ActivationPlan (Lane A2) delegates to for every
instruction-file item; A2 owns approval and the receipt, A3 owns marker-safe rendering
and validation.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

SCHEMA = "agentic-sdlc/instruction-generator@1"

# The minimum number of distinct verbatim doctrine lines whose presence in a rendered
# instruction file is treated as doctrine duplication (M5): a single incidental match is
# tolerated, a wholesale copy of the SKILL body is refused.
DOCTRINE_DUPLICATION_THRESHOLD = 2
# A doctrine line must be at least this long to count toward duplication, so short
# headings or fragments do not trip the check.
DOCTRINE_LINE_MIN_LENGTH = 20


class GeneratorError(Exception):
    """Raised for manifest-level problems that abort planning before any file work."""


def _marker_pair(manifest: dict) -> tuple[str, str]:
    marker = manifest.get("marker") or {}
    start = marker.get("start", "<!-- agentic-sdlc:start -->")
    end = marker.get("end", "<!-- agentic-sdlc:end -->")
    return start, end


def render_sections(sections: list[dict]) -> str:
    """Render manifest sections in order as ``## key`` blocks; deterministic, no timestamps."""
    parts = []
    for section in sections or []:
        key = str(section.get("key", "")).strip()
        body = str(section.get("body", "")).rstrip("\n")
        heading = f"## {key}" if key else ""
        block = f"{heading}\n{body}" if heading else body
        parts.append(block.strip("\n"))
    return "\n\n".join(part for part in parts if part)


def render_body(manifest: dict, kind: str, spec: dict) -> str:
    """Render the marked-region interior for one file. Stable serialization -> idempotent."""
    pointer = manifest.get("doctrine_pointer", "skills/agentic-sdlc/SKILL.md")
    if kind == "root_claude":
        routing = spec.get("claude_routing") or []
        lines = "\n".join(f"- {item}" for item in routing)
        return f"## Claude command routing\n{lines}".rstrip("\n")

    if kind in ("root_agents", "subtree"):
        body = render_sections(spec.get("sections") or [])
        if pointer not in body:
            footer = f"## doctrine\nSee {pointer} for the orchestration doctrine."
            body = f"{body}\n\n{footer}" if body else footer
        return body.rstrip("\n")

    # claude_rule and any other marked file: sections only.
    return render_sections(spec.get("sections") or [])


def _preamble(manifest: dict, kind: str, spec: dict) -> str:
    if kind == "root_claude":
        return f"{spec.get('import', '@AGENTS.md')}\n\n"
    return ""


def _collect_targets(manifest: dict) -> list[dict]:
    """Flatten the manifest into an ordered list of ``{kind, path, spec}`` file targets."""
    targets: list[dict] = []
    if "root_agents" in manifest:
        spec = manifest["root_agents"]
        targets.append({"kind": "root_agents", "path": spec["path"], "spec": spec})
    if "root_claude" in manifest:
        spec = manifest["root_claude"]
        targets.append({"kind": "root_claude", "path": spec["path"], "spec": spec})
    for spec in manifest.get("subtrees") or []:
        targets.append({"kind": "subtree", "path": spec["path"], "spec": spec})
    for spec in manifest.get("claude_rules") or []:
        targets.append({"kind": "claude_rule", "path": spec["path"], "spec": spec})
    return targets


def _within_target(root: Path, rel: str) -> Path | None:
    """Resolve ``rel`` under ``root``; return the path only if it stays inside the target."""
    if Path(rel).is_absolute():
        return None
    root_real = root.resolve()
    candidate = (root / rel).resolve()
    if candidate == root_real or root_real in candidate.parents:
        return candidate
    return None


def _doctrine_lines(root: Path, manifest: dict) -> list[str]:
    pointer = manifest.get("doctrine_pointer", "skills/agentic-sdlc/SKILL.md")
    doctrine_path = _within_target(root, pointer)
    if doctrine_path is None or not doctrine_path.is_file():
        return []
    lines = []
    for raw in doctrine_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if len(line) >= DOCTRINE_LINE_MIN_LENGTH and not line.startswith("#") and not line.startswith("---"):
            lines.append(line)
    return lines


def _marked_block(start: str, end: str, body: str) -> str:
    return f"{start}\n{body}\n{end}"


def _locate_block(text: str, start: str, end: str) -> tuple[int, int, str | None, str]:
    """Return ``(n_start, n_end, interior, status)`` for the marker pair in ``text``.

    ``status`` is one of ``absent``, ``well-formed``, or ``malformed``. ``interior`` is the
    stripped body of a single well-ordered pair, else ``None``.
    """
    n_start = text.count(start)
    n_end = text.count(end)
    if n_start == 0 and n_end == 0:
        return 0, 0, None, "absent"
    if n_start == 1 and n_end == 1:
        start_idx = text.index(start)
        end_idx = text.index(end)
        if start_idx < end_idx:
            interior = text[start_idx + len(start):end_idx].strip("\n")
            return 1, 1, interior, "well-formed"
    return n_start, n_end, None, "malformed"


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    start_idx = text.index(start)
    end_idx = text.index(end) + len(end)
    return text[:start_idx] + _marked_block(start, end, body) + text[end_idx:]


def _validate_output(kind: str, content: str, body: str, start: str, end: str, doctrine_lines: list[str], pointer: str) -> str | None:
    """Return a conflict reason if the would-be output fails validation, else ``None``."""
    if content.count(start) != 1 or content.count(end) != 1:
        return "malformed-marker"
    if content.index(start) > content.index(end):
        return "malformed-marker"
    if kind == "root_claude":
        if not content.startswith("@AGENTS.md\n"):
            return "thin-claude"
        if pointer.rsplit("/", 1)[-1] in body and "doctrine" in body.lower():
            return "thin-claude"
    if kind in ("root_agents", "subtree"):
        if pointer not in body:
            return "missing-doctrine-pointer"
        matches = sum(1 for line in doctrine_lines if line in body)
        if matches >= DOCTRINE_DUPLICATION_THRESHOLD:
            return "doctrine-duplication"
    return None


def _plan_file(target: dict, root: Path, manifest: dict, doctrine_lines: list[str], duplicated: bool) -> dict:
    kind = target["kind"]
    rel = target["path"]
    pointer = manifest.get("doctrine_pointer", "skills/agentic-sdlc/SKILL.md")
    start, end = _marker_pair(manifest)
    record: dict = {"path": rel, "kind": kind, "action": "skip", "unified_diff": ""}

    if duplicated:
        record.update(action="refuse", conflict="duplicate-target")
        return record

    resolved = _within_target(root, rel)
    if resolved is None:
        record.update(action="refuse", conflict="path-escape")
        return record

    body = render_body(manifest, kind, target["spec"])
    preamble = _preamble(manifest, kind, target["spec"])
    exists = resolved.is_file()
    old = resolved.read_text(encoding="utf-8") if exists else ""

    if not exists:
        new_content = preamble + _marked_block(start, end, body) + "\n"
        action = "create"
    else:
        n_start, n_end, interior, status = _locate_block(old, start, end)
        if status == "malformed":
            reason = "duplicate-marker" if (n_start > 1 or n_end > 1) else "malformed-marker"
            record.update(action="refuse", conflict=reason)
            return record
        if status == "absent":
            base = old if old.endswith("\n") else old + "\n"
            if kind == "root_claude" and not base.startswith("@AGENTS.md\n"):
                base = preamble + base
            new_content = base + "\n" + _marked_block(start, end, body) + "\n"
            action = "merge"
        else:  # well-formed
            if interior == body:
                new_content = old
                action = "adopt"
            else:
                new_content = _replace_block(old, start, end, body)
                if kind == "root_claude" and not new_content.startswith("@AGENTS.md\n"):
                    new_content = preamble + new_content
                action = "merge"

    conflict = _validate_output(kind, new_content, body, start, end, doctrine_lines, pointer)
    if conflict is not None:
        record.update(action="refuse", conflict=conflict)
        return record

    if action != "adopt":
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        record["unified_diff"] = diff
    record["action"] = action
    record["_new_content"] = new_content
    record["_resolved"] = str(resolved)
    return record


def generate(manifest: dict, root: Path, apply: bool = False) -> dict:
    """Plan (and optionally apply) the manifest against ``root``.

    Returns ``{schema, mode, ok, files, conflicts}``. ``files`` carries one record per
    manifest target with ``{path, kind, action, unified_diff}`` and, on refusal, a
    ``conflict`` reason. ``ok`` is false whenever any file is refused or a manifest-level
    conflict (duplicate target) is present.
    """
    root = Path(root)
    targets = _collect_targets(manifest)
    doctrine_lines = _doctrine_lines(root, manifest)

    seen: dict[str, int] = {}
    for target in targets:
        seen[target["path"]] = seen.get(target["path"], 0) + 1
    duplicated_paths = {path for path, count in seen.items() if count > 1}

    conflicts: list[dict] = []
    for path in sorted(duplicated_paths):
        conflicts.append({"path": path, "reason": "duplicate-target"})

    files: list[dict] = []
    for target in targets:
        record = _plan_file(target, root, manifest, doctrine_lines, target["path"] in duplicated_paths)
        if record["action"] == "refuse" and record["path"] not in duplicated_paths:
            conflicts.append({"path": record["path"], "reason": record["conflict"]})
        files.append(record)

    ok = not conflicts

    if apply:
        for record in files:
            if record["action"] in ("create", "merge") and "_new_content" in record:
                resolved = Path(record["_resolved"])
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(record["_new_content"], encoding="utf-8")

    public_files = [
        {k: v for k, v in record.items() if not k.startswith("_")}
        for record in files
    ]
    return {
        "schema": SCHEMA,
        "mode": "apply" if apply else "plan",
        "ok": ok,
        "files": public_files,
        "conflicts": conflicts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "apply"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read manifest: {exc}", file=sys.stderr)
        return 2
    if not isinstance(manifest, dict):
        print("ERROR: manifest must be a JSON object", file=sys.stderr)
        return 2

    result = generate(manifest, args.target, apply=args.command == "apply")
    print(json.dumps(result, indent=2))
    if args.command == "plan":
        return 0
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
