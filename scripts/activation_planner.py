#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""ActivationPlan/ActivationReceipt helper for /sdlc-init (Lane A2).

Dry-run-first activation of Agentic SDLC in a target repository: a ``plan`` that
writes nothing, an ``apply`` that performs only approved per-item actions
(create|adopt|merge|refuse|skip) and records an ActivationReceipt distinguishing
explicit, defaulted, and derived choices, and a ``deactivate`` that removes only
generator-authored content. The instruction files themselves are rendered by the
Lane-A3 generator (scripts/instruction_generator.py); this module owns approval,
baseline/CI/trust/Seeds sequencing, the reversible gate proof, and the receipt.

The only supported profile is ``git``. ``jj-colocated`` is refused and points at
the jj compatibility reference; it arrives later as a separately certified
child amendment.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:  # imported as a package member (tests) or as a bare script (CLI)
    from scripts import instruction_generator as gen
except ImportError:  # pragma: no cover - script-execution fallback
    import instruction_generator as gen  # type: ignore

SCHEMA = "agentic-sdlc/activation@1"
JJ_REFERENCE = "skills/agentic-sdlc/references/jj-vcs.md"
INSTRUCTION_FILENAMES = {"AGENTS.md", "CLAUDE.md", "README.md"}
GATE_FIXTURE_GLOB = ".agentic-sdlc/gate-fixture.*"
CI_WORKFLOW = ".github/workflows/validate.yml"
CI_WORKFLOW_BODY = (
    "name: validate\n"
    "on:\n"
    "  push:\n"
    "  pull_request:\n"
    "jobs:\n"
    "  check:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - uses: jdx/mise-action@v2\n"
    "      - run: mise run check\n"
)


def _git(target: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _is_repo(target: Path) -> bool:
    return (target / ".git").exists()


def _has_commits(target: Path) -> bool:
    return _git(target, "rev-parse", "--verify", "HEAD", check=False).returncode == 0


def _tracked(target: Path) -> list[str]:
    if not _is_repo(target):
        return []
    return [line for line in _git(target, "ls-files").stdout.splitlines() if line]


def _porcelain(target: Path) -> list[str]:
    if not _is_repo(target):
        return []
    return [line for line in _git(target, "status", "--porcelain").stdout.splitlines() if line]


def _dirty_tracked(target: Path) -> bool:
    """Modified/staged tracked content; untracked files alone are not dirt."""
    return any(not line.startswith("??") for line in _porcelain(target))


def _untracked_product(target: Path) -> list[str]:
    product = []
    for line in _porcelain(target):
        if not line.startswith("??"):
            continue
        rel = line[3:].strip().rstrip("/")
        name = Path(rel).name
        if name.startswith(".") or name in INSTRUCTION_FILENAMES:
            continue
        product.append(rel)
    return sorted(product)


def _instruction_items(target: Path, manifest: dict | None) -> tuple[list[dict], dict | None]:
    if manifest is None:
        return [], None
    result = gen.generate(manifest, target, apply=False)
    items = [
        {
            "key": f"instructions:{record['path']}",
            "target_path": record["path"],
            "action": record["action"],
            "chosen_source": "derived",
        }
        for record in result["files"]
    ]
    return items, result


def plan(
    target: Path,
    *,
    now: str,
    profile: str | None = None,
    manifest: dict | None = None,
) -> dict:
    """Compute the dry-run ActivationPlan. Performs zero writes."""
    target = Path(target)
    chosen_profile = profile or "git"
    profile_source = "explicit" if profile is not None else "defaulted"

    repo = _is_repo(target)
    inventory = {
        "tracked": _tracked(target),
        "untracked_product": _untracked_product(target),
        "seeds": {"present": (target / ".seeds").is_dir()},
    }

    items: list[dict] = [
        {
            "key": "git-baseline",
            "target_path": None,
            "action": "adopt" if repo else "create",
            "chosen_source": "derived" if repo else "defaulted",
        }
    ]
    instruction_items, _ = _instruction_items(target, manifest)
    items.extend(instruction_items)

    # Queue mutation stays conductor/runbook-scoped: the plan names the runbook
    # step that owns each queue call instead of restating the launcher form.
    seeds_calls = [
        {
            "call": "commands/sdlc-init.md step 3: queue init",
            "guard": "runs only when .seeds is absent; conductor-owned runbook step",
        },
        {
            "call": "commands/sdlc-init.md step 3: queue readiness readback",
            "guard": "read-only queue inspection; always safe",
        },
    ]

    return {
        "schema": SCHEMA,
        "mode": "dry-run",
        "now": now,
        "profile": chosen_profile,
        "profile_source": profile_source,
        "baseline_inventory": inventory,
        "items": items,
        "seeds_calls": seeds_calls,
    }


def plan_item(activation_plan: dict, key: str) -> dict:
    return next(item for item in activation_plan["items"] if item["key"] == key)


def _stopped(receipt: dict, reason: str, detail: str = "") -> None:
    receipt["stops"].append({"reason": reason, "detail": detail})


def _base_receipt(activation_plan: dict, now: str, marker: dict | None) -> dict:
    return {
        "schema": SCHEMA,
        "now": now,
        "status": "applied",
        "profile": activation_plan["profile"],
        "profile_source": activation_plan["profile_source"],
        "baseline": {"empty_commit": False, "tracked_committed": []},
        "baseline_inventory": activation_plan["baseline_inventory"],
        "seeds": {"init_ran": False, "ready": 0, "blocked": 0, "queue_nonempty": False},
        "gate_proof": {"fixture_fail": False, "clean_pass": False},
        "trust_actions": [],
        "stops": [],
        "conflicts": [],
        "created": [],
        "merged": [],
        "adopted": [],
        "results": [],
        "marker": marker or {},
        "wave_ready": False,
    }


def apply(
    target: Path,
    *,
    yes: bool = False,
    tty: bool = False,
    now: str,
    profile: str | None = None,
    kind: str | None = None,
    seeds: dict | None = None,
    gate_runner=None,
    manifest: dict | None = None,
    ci_provider: str | None = None,
    trust_requests: list[dict] | None = None,
    trust_approvals: dict[str, bool] | None = None,
    confirm=None,
) -> dict:
    """Apply the ActivationPlan. Any stop, refusal, or cancellation writes nothing."""
    target = Path(target)
    marker = (manifest or {}).get("marker") if manifest else None
    activation_plan = plan(target, now=now, profile=profile, manifest=manifest)
    receipt = _base_receipt(activation_plan, now, marker)

    if activation_plan["profile"] != "git":
        receipt["status"] = "refused"
        _stopped(
            receipt,
            "unsupported-profile",
            f"profile {activation_plan['profile']} is not activatable; see {JJ_REFERENCE}",
        )
        return {"exit_code": 1, "receipt": receipt}

    approved = yes or (tty and confirm is not None and bool(confirm(activation_plan)))
    if not approved:
        receipt["status"] = "cancelled"
        return {"exit_code": 1, "receipt": receipt}

    repo = _is_repo(target)
    if repo and _dirty_tracked(target):
        _stopped(receipt, "dirty-tree", "tracked changes present; commit or stash first")
    if (
        repo
        and not _has_commits(target)
        and kind is None
        and not _untracked_product(target)
        and any(path for path in target.iterdir() if path.name != ".git")
    ):
        _stopped(receipt, "needs-input", "no derivable baseline content; pass an explicit kind")
    seeds = seeds or {}
    ready = int(seeds.get("ready", 0))
    if ready <= 0:
        _stopped(receipt, "empty-queue", "Seeds ready queue is empty; activation cannot be wave-ready")
    if ci_provider == "ambiguous":
        _stopped(receipt, "ci-ambiguous", "multiple CI providers detected; select one explicitly")
    if receipt["stops"]:
        receipt["status"] = "stopped"
        return {"exit_code": 1, "receipt": receipt}

    # --- writes begin -----------------------------------------------------
    created_repo = False
    if not repo:
        _git(target, "init", "-b", "main")
        created_repo = True
    readme = target / "README.md"
    if created_repo and not readme.exists():
        readme.write_text(f"# {target.name}\n", encoding="utf-8")

    generation = None
    if manifest is not None:
        # Plan first: any per-file conflict refuses the WHOLE instruction apply
        # (no half-authored instruction surface), reported via the receipt.
        preview = gen.generate(manifest, target, apply=False)
        receipt["conflicts"] = preview["conflicts"]
        if preview["conflicts"]:
            generation = preview
        else:
            generation = gen.generate(manifest, target, apply=True)
        for record in generation["files"]:
            if generation["mode"] != "apply":
                continue
            if record["action"] == "create":
                receipt["created"].append(record["path"])
            elif record["action"] == "merge":
                receipt["merged"].append(record["path"])
            elif record["action"] == "adopt":
                receipt["adopted"].append(record["path"])

    if gate_runner is not None:
        meta = target / ".agentic-sdlc"
        meta.mkdir(exist_ok=True)
        fixture = meta / "gate-fixture.marker"
        fixture.write_text("reversible gate fixture; must never be committed\n", encoding="utf-8")
        try:
            # A raising gate counts as a failing gate; the fixture must never
            # survive the proof either way.
            try:
                fixture_result = bool(gate_runner(target))
            except Exception:
                fixture_result = False
        finally:
            if fixture.exists():
                fixture.unlink()
        try:
            clean_result = bool(gate_runner(target))
        except Exception:
            clean_result = False
        receipt["gate_proof"] = {
            "fixture_fail": not fixture_result,
            "clean_pass": clean_result,
        }

    approvals = trust_approvals or {}
    for request in trust_requests or []:
        path = str(request.get("path", ""))
        granted = bool(tty and approvals.get(path, False))
        receipt["trust_actions"].append(
            {
                "kind": request.get("kind"),
                "path": path,
                "approved": granted,
                "status": "approved" if granted else "needs-approval",
            }
        )

    receipt["seeds"] = {
        "init_ran": bool(seeds.get("init_ran", False)),
        "ready": ready,
        "blocked": int(seeds.get("blocked", 0)),
        "queue_nonempty": ready > 0,
    }

    if ci_provider == "github":
        workflow = target / CI_WORKFLOW
        if not workflow.exists():
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(CI_WORKFLOW_BODY, encoding="utf-8")

    if created_repo:
        _git(target, "add", "--", ".", ":(exclude).agentic-sdlc")
        commit = _git(
            target,
            "-c", "user.name=agentic-sdlc-activation",
            "-c", "user.email=activation@agentic-sdlc.invalid",
            "commit", "-m", "chore: activate agentic-sdlc baseline",
            check=False,
        )
        if commit.returncode == 0:
            receipt["baseline"]["tracked_committed"] = _tracked(target)
        receipt["baseline"]["empty_commit"] = False

    for item in activation_plan["items"]:
        chosen = item["chosen_source"]
        if item["key"] == "git-baseline" and profile is not None:
            chosen = "explicit"
        receipt["results"].append(
            {"key": item["key"], "action": item["action"], "chosen_source": chosen}
        )

    trust_ok = all(action["approved"] for action in receipt["trust_actions"])
    # Falsifiability is part of readiness: the gate must have demonstrably
    # FAILED on the planted fixture and passed clean, not merely passed.
    gate_ok = (
        receipt["gate_proof"]["fixture_fail"] and receipt["gate_proof"]["clean_pass"]
        if gate_runner is not None
        else True
    )
    receipt["wave_ready"] = (
        not receipt["stops"]
        and not receipt["conflicts"]
        and receipt["seeds"]["queue_nonempty"]
        and trust_ok
        and gate_ok
    )

    meta = target / ".agentic-sdlc"
    meta.mkdir(exist_ok=True)
    (meta / "activation-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"exit_code": 0, "receipt": receipt}


def deactivate(target: Path, *, receipt: dict, dry_run: bool) -> dict:
    """Remove only generator-authored content: created files and marked blocks.

    A receipt without an explicit marker pair only removes created files; it
    never guesses markers inside merged/adopted files (guessing could strip
    coincidental foreign content).
    """
    target = Path(target)
    marker = receipt.get("marker") or {}
    start = marker.get("start")
    end = marker.get("end")
    if not start or not end:
        planned = {"created_removed": list(receipt.get("created", [])), "blocks_removed": []}
        if dry_run:
            return {"mode": "plan", **planned}
        for rel in receipt.get("created", []):
            path = target / rel
            if path.is_file():
                path.unlink()
        return {"mode": "apply", **planned}

    planned = {"created_removed": list(receipt.get("created", [])),
               "blocks_removed": list(receipt.get("merged", []) + receipt.get("adopted", []))}
    if dry_run:
        return {"mode": "plan", **planned}

    for rel in receipt.get("created", []):
        path = target / rel
        if path.is_file():
            path.unlink()
    for rel in receipt.get("merged", []) + receipt.get("adopted", []):
        path = target / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if start in text and end in text and text.index(start) < text.index(end):
            head = text[: text.index(start)]
            tail = text[text.index(end) + len(end):]
            cleaned = (head.rstrip("\n") + "\n" + tail.lstrip("\n")).strip("\n")
            path.write_text((cleaned + "\n") if cleaned else "", encoding="utf-8")
    return {"mode": "apply", **planned}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan"])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--now", default="1970-01-01T00:00:00Z")
    args = parser.parse_args(argv)

    result = plan(args.target, now=args.now, profile=args.profile)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
