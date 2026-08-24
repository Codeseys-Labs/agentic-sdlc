#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build one deterministic release archive of the committed HEAD tree.

CONTRACT.

  * The payload is exactly ``policy/release-candidate.v1.json`` -> ``payload.files`` and
    ``payload.trees``.  Nothing else is archived and the allowlist is never widened here.
  * The bytes come from ``git archive`` over the committed tree, never from the working tree.
    ``git archive`` supplies the commit epoch as every member's mtime, uid/gid 0, and
    fixed modes, so two builds of one commit are byte-identical and the digest in
    ``dist/SHA256SUMS`` genuinely names that commit's content.  ``tar`` over a working tree
    records the checkout's own mtimes and the caller's ownership, and the digest then means
    nothing; that substitution is the one-line defect this module exists to prevent.
  * ``HEAD`` is resolved EXACTLY ONCE, by ``require_clean``, and every later step is pinned to
    the commit it returned -- the tree it names and the bytes ``git archive`` reads.  Re-reading
    ``HEAD`` per step would let a head that moved mid-build produce a manifest whose recorded
    source, recorded tree, and member bytes came from up to three different commits.
  * ``manifest.json`` is appended to git's own tar as the single member this process writes.
    Every other member's bytes are git's, untouched.  The manifest inventories every member by
    relative path with a sha256 for each file and a target for each symlink, and it does not
    inventory itself.
  * A dirty tree is refused: a build whose source is not exactly HEAD cannot be named by a
    commit.  There is no override.
  * No interpreter is bundled.  ``mise.toml``'s pinned uv supplies Python 3.12.11 to every
    entrypoint, so the archive carries authored bytes only.

WHAT THE DIGEST DOES AND DOES NOT PROVE.  The tar member bytes are stable across hosts.  The
gzip envelope's bytes depend on the host's zlib build, so ``SHA256SUMS`` names the exact archive
this host produced, and a rebuild elsewhere may compress the same tar to different bytes.  The
manifest's per-entry digests are the cross-host identity.  A built archive is evidence of what
was archived; it is not a release, a publication, or a support claim, and the manifest carries
the policy's own disclosures verbatim so no consumer has to infer that.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_REFUSED = 3

POLICY_RELATIVE = Path("policy") / "release-candidate.v1.json"
MANIFEST_NAME = "manifest.json"
SUMS_NAME = "SHA256SUMS"
PLATFORM = "linux-x64"


class Refusal(RuntimeError):
    pass


def canonical(document: Any) -> bytes:
    return (
        json.dumps(document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("ascii")


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
    )
    if completed.returncode:
        raise Refusal(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def require_clean(root: Path) -> tuple[str, str]:
    """Refuse a dirty tree, then read the head ONCE as an atomic `(commit, tree)` pair.

    The tree is resolved from the commit this function just read (``rev-parse <commit>^{tree}``),
    never by a second independent ``rev-parse HEAD^{tree}``.  A commit object names exactly one
    tree, so the pair is atomic by construction; two independent reads of ``HEAD`` can straddle a
    head that moved between them and produce a commit and a tree from different histories, which is
    a manifest naming a source that never existed.  The dirty-tree check above does not close that
    window -- a commit made in another worktree on the same repository moves ``HEAD`` without
    dirtying anything here (agentic-sdlc-4b0f, the idiom ``scripts/gate_receipt.py``'s
    ``observe_repository_head`` owns).
    """
    status = git(root, "status", "--porcelain")
    if status.strip():
        listed = ", ".join(sorted(line[3:] for line in status.splitlines())[:10])
        raise Refusal(
            f"the tree at {root} is dirty ({listed}); this build archives the committed HEAD tree,"
            " so a digest built here would name a commit whose content is not what you are looking at"
        )
    commit = git(root, "rev-parse", "HEAD").strip()
    return commit, git(root, "rev-parse", f"{commit}^{{tree}}").strip()


def read_policy(root: Path) -> dict[str, Any]:
    path = root / POLICY_RELATIVE
    try:
        policy = json.loads(path.read_bytes().decode("ascii"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"{POLICY_RELATIVE} is unreadable or not canonical ASCII JSON: {exc}") from exc
    if not isinstance(policy, dict):
        raise Refusal(f"{POLICY_RELATIVE} is not a JSON object")
    for key in ("disclosures", "limits", "manifest", "payload"):
        if not isinstance(policy.get(key), dict):
            raise Refusal(f"{POLICY_RELATIVE} carries no {key} object")
    payload = policy["payload"]
    files, trees = payload.get("files"), payload.get("trees")
    if not isinstance(files, list) or not isinstance(trees, list) or not files or not trees:
        raise Refusal(f"{POLICY_RELATIVE} payload allowlist is empty or not two lists")
    return policy


def archive_tar(root: Path, prefix: str, allowlist: list[str], destination: Path, commit: str) -> None:
    """Archive the EXACT commit `require_clean` recorded, never ``HEAD`` re-resolved here.

    ``HEAD`` would be a third independent read of a moving reference: the manifest would name one
    commit while the member bytes came from whichever commit ``HEAD`` pointed at by the time this
    ran, and the digest would then name content the recorded source does not describe.
    """
    completed = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", f"--prefix={prefix}", commit, "--", *allowlist],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise Refusal(f"git archive refused the payload allowlist: {completed.stderr.decode(errors='replace').strip()}")
    destination.write_bytes(completed.stdout)


def inventory(tar_path: Path, prefix: str) -> tuple[list[dict[str, Any]], int]:
    """Index git's own members, and return the commit epoch git stamped on every one of them."""
    rows: list[dict[str, Any]] = []
    mtimes: set[int] = set()
    with tarfile.open(tar_path) as tar:
        for member in tar.getmembers():
            mtimes.add(int(member.mtime))
            if member.name == prefix.rstrip("/"):
                continue
            if not member.name.startswith(prefix):
                raise Refusal(f"the archive member {member.name!r} sits outside the prefix {prefix!r}")
            relative = member.name[len(prefix) :]
            if member.isdir():
                rows.append({"mode": member.mode, "path": relative, "size": 0, "type": "dir"})
            elif member.issym():
                rows.append(
                    {
                        "mode": member.mode,
                        "path": relative,
                        "size": len(member.linkname.encode("utf-8")),
                        "target": member.linkname,
                        "type": "symlink",
                    }
                )
            elif member.isfile():
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise Refusal(f"the archive member {relative!r} carries no readable content")
                rows.append(
                    {
                        "mode": member.mode,
                        "path": relative,
                        "sha256": hashlib.sha256(extracted.read()).hexdigest(),
                        "size": member.size,
                        "type": "file",
                    }
                )
            else:
                raise Refusal(f"the archive member {relative!r} is neither a file, a directory, nor a symlink")
    rows.sort(key=lambda row: str(row["path"]))
    if len(mtimes) != 1:
        raise Refusal(
            f"git archive stamped {len(mtimes)} distinct member timestamps; one commit epoch is the"
            " determinism this build depends on"
        )
    return rows, mtimes.pop()


def enforce_limits(limits: dict[str, Any], rows: list[dict[str, Any]], archive_bytes: int, tar_bytes: int) -> None:
    checks = (
        ("max_entries", len(rows), "inventoried entries"),
        ("max_file_bytes", max((int(row["size"]) for row in rows), default=0), "largest member size"),
        ("max_path_bytes", max((len(str(row["path"]).encode("utf-8")) for row in rows), default=0), "longest member path"),
        ("max_total_bytes", sum(int(row["size"]) for row in rows), "summed member size"),
        ("max_uncompressed_bytes", tar_bytes, "uncompressed archive size"),
        ("max_archive_bytes", archive_bytes, "compressed archive size"),
    )
    for name, observed, subject in checks:
        ceiling = limits.get(name)
        if isinstance(ceiling, int) and not isinstance(ceiling, bool) and observed > ceiling:
            raise Refusal(f"{subject} {observed} exceeds {POLICY_RELATIVE}'s {name} {ceiling}")


def build(root: Path, dist: Path) -> dict[str, Any]:
    commit, tree = require_clean(root)
    policy = read_policy(root)
    version = policy["manifest"].get("product_version")
    if not isinstance(version, str) or not version:
        raise Refusal(f"{POLICY_RELATIVE} carries no product_version")
    allowlist = [*policy["payload"]["files"], *policy["payload"]["trees"]]
    stem = f"agentic-sdlc-{version}"
    prefix = f"{stem}/"

    dist.mkdir(parents=True, exist_ok=True)
    tar_path = dist / f"{stem}.tar"
    archive_path = dist / f"{stem}.tar.gz"
    try:
        return _build_into(root, dist, tar_path, archive_path, policy, allowlist, prefix, stem, version, commit, tree)
    finally:
        tar_path.unlink(missing_ok=True)


def _build_into(
    root: Path,
    dist: Path,
    tar_path: Path,
    archive_path: Path,
    policy: dict[str, Any],
    allowlist: list[str],
    prefix: str,
    stem: str,
    version: str,
    commit: str,
    tree: str,
) -> dict[str, Any]:
    archive_tar(root, prefix, allowlist, tar_path, commit)
    rows, epoch = inventory(tar_path, prefix)

    manifest = {
        "archive_root": stem,
        "artifact_kind": policy["manifest"].get("artifact_kind"),
        "candidate_id": hashlib.sha256(
            canonical(
                {
                    "inventory": rows,
                    "platform": PLATFORM,
                    "product_version": version,
                    "schema_version": policy["manifest"].get("schema_version"),
                    "source": {"commit": commit, "tree": tree},
                }
            )
        ).hexdigest(),
        "disclosures": policy["disclosures"],
        "inventory": rows,
        "platform": PLATFORM,
        "product_version": version,
        "public_channel": policy["manifest"].get("public_channel"),
        "release_claim": policy["manifest"].get("release_claim"),
        "schema_version": policy["manifest"].get("schema_version"),
        "source": {"commit": commit, "tree": tree},
        "support_tier": policy["manifest"].get("support_tier"),
    }
    body = canonical(manifest)
    with tarfile.open(tar_path, "a", format=tarfile.PAX_FORMAT) as tar:
        member = tarfile.TarInfo(f"{prefix}{MANIFEST_NAME}")
        member.size = len(body)
        member.mode = 0o644
        member.mtime = epoch
        member.uid = member.gid = 0
        member.uname = member.gname = "root"
        tar.addfile(member, io.BytesIO(body))

    tar_content = tar_path.read_bytes()
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=buffer, mtime=0) as compressed:
        compressed.write(tar_content)
    compressed_bytes = buffer.getvalue()
    enforce_limits(policy["limits"], rows, len(compressed_bytes), len(tar_content))
    archive_path.write_bytes(compressed_bytes)

    digest = hashlib.sha256(compressed_bytes).hexdigest()
    (dist / SUMS_NAME).write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    return {
        "archive": archive_path,
        "archive_sha256": digest,
        "candidate_id": manifest["candidate_id"],
        "commit": commit,
        "entries": len(rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic release archive of HEAD")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dist", type=Path, default=None)
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    dist = (arguments.dist or root / "dist").resolve()
    try:
        built = build(root, dist)
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    for key in ("commit", "candidate_id", "entries", "archive", "archive_sha256"):
        print(f"{key} {built[key]}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
