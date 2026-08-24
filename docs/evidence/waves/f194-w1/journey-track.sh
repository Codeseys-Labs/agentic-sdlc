#!/bin/bash
# f194-w1 installed-byte acceptance journey.
# Runs INSIDE the disposable asdlc-fresh:latest container as user `op` with stdin=/dev/null.
# The container HOME is the journey's plane; the host's real ~/.claude is never touched.
# /src is the PRIMARY checkout mounted READ-ONLY; the journey clones from it and pins the clone.
set -u
PIN=6c30728677c4e122bf294a887c62fbb63a1b05c5
CLONE=/home/op/asdlc
FIX=/home/op/fixtures
STATE="${XDG_STATE_HOME:-$HOME/.local/state}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"

step(){ echo; echo "##### STEP $1 [$(date -u +%FT%TZ)] elapsed=${SECONDS}s"; }
stop(){ echo "##### JOURNEY-STOP: $1"; exit 90; }
must(){ "$@" || stop "rc=$? from: $*"; }
art(){ echo "##### BEGIN-ARTIFACT $1"; cat "$2" 2>&1; echo; echo "##### END-ARTIFACT $1"; }

step "S0 environment observation"
echo "uname: $(uname -a)"
echo "id: $(id)"
echo "HOME=$HOME"
echo "git: $(git --version)"
echo "python3: $(python3 --version)"
echo "tar: $(tar --version | head -1)"
echo "mise: $(mise --version 2>/dev/null | head -1)"
command -v claude >/dev/null || stop "claude CLI absent from image"
CLAUDE_V_RAW="$(claude --version 2>&1)"
echo "claude --version: $CLAUDE_V_RAW"
CV=$(echo "$CLAUDE_V_RAW" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
FLOOR=2.1.154
if [ -z "$CV" ] || { [ "$CV" != "$FLOOR" ] && [ "$(printf '%s\n%s\n' "$CV" "$FLOOR" | sort -V | head -1)" != "$FLOOR" ]; }; then
  echo "claude '$CV' is below floor $FLOOR - installing current CLI inside the container (recorded)"
  curl -fsSL https://claude.ai/install.sh | bash || stop "in-container claude reinstall failed"
  CLAUDE_V_RAW="$(claude --version 2>&1)"
  echo "claude --version (reinstalled): $CLAUDE_V_RAW"
fi
echo "claude-home prestate:"
ls -la "$HOME/.claude" 2>&1 || true
ls -la "$HOME/.claude.json" 2>&1 || true

step "S1 clone from read-only mount, pinned to $PIN"
git config --global user.name "f194 journey operator-proxy"
git config --global user.email "journey@f194.invalid"
git config --global safe.directory /src
git config --global --add safe.directory /src/.git
t0=$SECONDS
must git clone --no-local /src "$CLONE"
echo "STEP-TIME clone $((SECONDS-t0))s"
cd "$CLONE" || stop "clone directory missing"
must git checkout -B journey "$PIN"
echo "HEAD: $(git rev-parse HEAD)"
[ "$(git rev-parse HEAD)" = "$PIN" ] || stop "clone is not at the pinned commit"
DIRTY="$(git status --porcelain)"
[ -z "$DIRTY" ] || stop "clone dirty: $DIRTY"
echo "clone clean at $PIN"

step "S2 container-local mise trust + pinned toolchain"
t0=$SECONDS
must mise trust ./mise.toml
must mise --locked install
echo "STEP-TIME toolchain $((SECONDS-t0))s"
echo "uv: $(mise exec -- uv --version)"

step "S3 mise run release:build"
t0=$SECONDS
must mise run release:build
echo "STEP-TIME release-build $((SECONDS-t0))s"
ls -l dist/
art dist-SHA256SUMS dist/SHA256SUMS
ARCHIVE=$(ls dist/agentic-sdlc-*.tar.gz | head -1)
[ -n "$ARCHIVE" ] || stop "no archive in dist/"
DIGEST=$(sha256sum "$ARCHIVE" | cut -d' ' -f1)
echo "ARCHIVE: $ARCHIVE"
echo "ARCHIVE-SHA256: $DIGEST"
grep -q "$DIGEST" dist/SHA256SUMS && echo "SHA256SUMS names the measured archive digest" || stop "SHA256SUMS disagrees with measured digest"

step "S4 placement bridge (Install-UX 'Pre-release candidate placement', verbatim shape)"
CAND="$DATA/agentic-sdlc/acquisition/candidates/$DIGEST"
must mkdir -p "$CAND"
must tar -xzf "$ARCHIVE" -C "$CAND"
echo "extracted: $(ls "$CAND")"
must mv "$CAND"/agentic-sdlc-*/ "$CAND/root"
echo "candidate root: $CAND/root"
ls "$CAND/root" | head -30
[ -f "$CAND/root/manifest.json" ] || stop "manifest.json absent in candidate root"
art candidate-manifest.json "$CAND/root/manifest.json"

step "S5 seal acquisition receipt"
t0=$SECONDS
must mise exec -- uv run --python 3.12.11 --script scripts/write_acquisition_receipt.py \
  --root "$CAND/root" --state-home "$STATE" --archive "$ARCHIVE"
echo "STEP-TIME acquisition-receipt $((SECONDS-t0))s"
RCPTS="$STATE/agentic-sdlc/acquisition/receipts"
ls -la "$RCPTS"
ACQ=$(ls "$RCPTS"/*.json | head -1)
[ -n "$ACQ" ] || stop "no acquisition receipt sealed"
echo "ACQ-RECEIPT: $ACQ"
echo "ACQ-RECEIPT-SHA256: $(sha256sum "$ACQ" | cut -d' ' -f1)"
art acquisition-receipt.json "$ACQ"

step "S6 operator-tools install (ccodex, checkout plane)"
t0=$SECONDS
must mise run operator-tools:install -- --bin-dir "$HOME/.local/bin"
echo "STEP-TIME operator-tools $((SECONDS-t0))s"
command -v ccodex >/dev/null || stop "ccodex not on PATH after operator-tools:install"
echo "ccodex: $(command -v ccodex)"
mise run operator-tools:status 2>&1 || true

step "S7 readers before install"
rc=0; ccodex sdlc status --json > /tmp/status-preinstall.json 2>/tmp/status-preinstall.err || rc=$?
echo "status --json (pre-install) exit=$rc"
art status-preinstall.json /tmp/status-preinstall.json
[ -s /tmp/status-preinstall.err ] && { echo "stderr:"; cat /tmp/status-preinstall.err; }

step "S8 ccodex sdlc install --host claude"
t0=$SECONDS
rc=0; ccodex sdlc install --host claude 2>&1 || rc=$?
echo "install exit=$rc"
[ $rc -eq 0 ] || stop "ccodex sdlc install failed rc=$rc"
echo "STEP-TIME sdlc-install $((SECONDS-t0))s"
ACT="$STATE/agentic-sdlc/activation"
ls -la "$ACT" "$ACT/receipts"
[ -f "$ACT/active-receipt.json" ] || stop "active-receipt.json absent after install"
art active-receipt.json "$ACT/active-receipt.json"
ARCPT=$(ls "$ACT/receipts"/*.json | head -1)
echo "ACT-RECEIPT: $ARCPT"
echo "ACT-RECEIPT-SHA256: $(sha256sum "$ARCPT" | cut -d' ' -f1)"
art activation-receipt.json "$ARCPT"
echo "claude home after install (2 levels):"
find "$HOME/.claude" -maxdepth 2 | sort

step "S9 reachability: activation-receipt inventory vs on-disk digests"
python3 - "$ARCPT" "$CLONE" <<'PYEOF'
import importlib.util, json, sys
from pathlib import Path
receipt_path, clone = Path(sys.argv[1]), Path(sys.argv[2])
doc = json.loads(receipt_path.read_text())

def find_entries(node):
    if isinstance(node, dict):
        val = node.get("entries")
        if isinstance(val, list) and val and all(isinstance(x, dict) and "entry_name" in x for x in val):
            return val
        for child in node.values():
            hit = find_entries(child)
            if hit is not None:
                return hit
    return None

entries = find_entries(doc)
if entries is None:
    print("REACHABILITY-STOP: no entries list found in receipt; top-level keys:", sorted(doc))
    raise SystemExit(1)
spec = importlib.util.spec_from_file_location("isb", clone / "scripts" / "install_skill_bundle.py")
isb = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = isb
spec.loader.exec_module(isb)
claude = Path.home() / ".claude"

def resolve(name):
    cands = [claude / name]
    if "/" not in name:
        for coll in ("commands", "skills", "agents", "workflows", "hooks", "output-styles"):
            cands += [claude / coll / name, claude / coll / f"{name}.md", claude / coll / f"{name}.sh", claude / coll / f"{name}.js"]
    for cand in cands:
        if cand.exists() or cand.is_symlink():
            return cand
    return None

five = {"sdlc-init", "sdlc-frame", "sdlc-wave", "sdlc-mission", "sdlc-rightsize"}
found_five, ok, bad, skip = {}, 0, 0, 0
for entry in entries:
    name, want = entry["entry_name"], entry["content_sha256"]
    pre, disp = entry.get("prestate"), entry.get("disposition")
    if want is None:
        print(f"SKIP  {name} prestate={pre} disposition={disp} (no content digest recorded)")
        skip += 1
        continue
    dest = resolve(name)
    if dest is None:
        print(f"MISS  {name} prestate={pre} disposition={disp}: no destination found under {claude}")
        bad += 1
        continue
    try:
        got = isb.digest(dest)
    except Exception as exc:
        print(f"ERROR {name}: digest failed at {dest}: {exc}")
        bad += 1
        continue
    if got == want:
        ok += 1
        print(f"MATCH {name} prestate={pre} disposition={disp} dest={dest} sha256={got}")
    else:
        bad += 1
        print(f"DIGEST-MISMATCH {name} dest={dest} receipt={want} disk={got}")
    stem = Path(name).stem
    if stem in five:
        found_five[stem] = (str(dest), got == want)
print(f"REACHABILITY-SUMMARY entries={len(entries)} match={ok} mismatch_or_missing={bad} skipped={skip}")
for cmd in sorted(five):
    hit = found_five.get(cmd)
    if hit:
        print(f"REACHABILITY command {cmd}: present at {hit[0]} digest_match={hit[1]}")
    else:
        print(f"REACHABILITY command {cmd}: NOT FOUND in receipt inventory")
PYEOF
[ $? -eq 0 ] || stop "reachability verification errored"

step "S10 readers on the activated plane"
for verb in inspect status doctor; do
  rc=0; ccodex sdlc "$verb" --json > "/tmp/${verb}-postinstall.json" 2>"/tmp/${verb}-postinstall.err" || rc=$?
  echo "$verb --json (post-install) exit=$rc"
  art "${verb}-postinstall.json" "/tmp/${verb}-postinstall.json"
  [ -s "/tmp/${verb}-postinstall.err" ] && { echo "stderr:"; cat "/tmp/${verb}-postinstall.err"; }
done
rc=0; ccodex sdlc status > /tmp/status-postinstall.txt 2>&1 || rc=$?
echo "status (human, post-install) exit=$rc"
art status-postinstall.txt /tmp/status-postinstall.txt

step "S11 fixtures driven from the ACTIVATED plane's generator"
GEN="$HOME/.claude/skills/agentic-sdlc/tools/instruction-generator.py"
[ -f "$GEN" ] || stop "generator absent from activated plane: $GEN"
echo "GENERATOR: $GEN sha256=$(sha256sum "$GEN" | cut -d' ' -f1)"
mkdir -p "$FIX"
python3 - <<'PYEOF'
import json
manifest = {
    "schema": "agentic-sdlc/instruction-manifest@2",
    "marker": {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"},
    "doctrine_pointer": "Full orchestration doctrine lives in the installed agentic-sdlc skill (skills/agentic-sdlc/SKILL.md in the host agent home); this file carries repository policy only.",
    "outputs": [
        {"path": "AGENTS.md", "kind": "root_agents", "prefix": "# journey fixture\n\n",
         "sections": [
             {"key": "project intent", "body": "Disposable fixture repository for wave f194-w1: proves the installed-byte activation journey (classify, reviewed manifest, shown-diff apply). No product code lives here."},
             {"key": "gates", "body": "`mise run check` is the authoritative repository gate once a toolchain is pinned. A passing gate is evidence only; it never authorizes an outward effect."},
             {"key": "waves", "body": "Wave substrate is Git worktrees. Workers own disjoint worktrees; fan-in is serial and conductor-authorized."},
             {"key": "seeds", "body": "The Seeds queue of record is written only by the conductor through the receipt-bound launcher (record --queue-writer conductor)."},
         ]},
        {"path": "CLAUDE.md", "kind": "root_claude", "prefix": "",
         "sections": [
             {"key": "routing", "body": "Read AGENTS.md as the canonical project policy. Claude-specific intents route through the installed /sdlc-init, /sdlc-frame, /sdlc-wave, /sdlc-mission, and /sdlc-rightsize commands."},
         ]},
    ],
}
raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
open("/home/op/fixtures/manifest.json", "w").write(raw)
print("manifest bytes:", len(raw))
PYEOF
art instruction-manifest.json "$FIX/manifest.json"

echo "--- greenfield fixture ---"
GF="$FIX/greenfield"
must git init -b main "$GF"
echo "Journey greenfield fixture: intent recorded per runbook step 2." > "$GF/README.md"
git -C "$GF" add README.md || stop "gf add"
git -C "$GF" commit -q -m "docs: record fixture intent" || stop "gf commit"
rc=0; python3 "$GEN" classify --target "$GF" > /tmp/classify-gf.json 2>&1 || rc=$?
echo "classify exit=$rc"
art classify-greenfield.json /tmp/classify-gf.json
grep -q '"verdict":"greenfield"' /tmp/classify-gf.json || stop "greenfield fixture did not classify greenfield"
echo 'OPERATOR-PROXY CONFIRMATION (greenfield): "Confirmed: no hosted tracker and no forge-side required check exist for this disposable fixture; the greenfield proposal is approved - apply the baseline instruction files." (journey runner acting as operator for fixture repos only, per wave frame section 2)'
rc=0; python3 "$GEN" apply --target "$GF" --manifest "$FIX/manifest.json" --entry AGENTS.md > /tmp/gf-agents-diff.txt 2>/tmp/gf-agents-diff.err || rc=$?
echo "apply AGENTS.md (no --yes) exit=$rc (expect 3)"
[ $rc -eq 3 ] || stop "expected refusal exit 3, got $rc"
[ ! -e "$GF/AGENTS.md" ] || stop "refused apply wrote the greenfield target"
echo "refusal stderr: $(cat /tmp/gf-agents-diff.err)"
art gf-agents-review-diff /tmp/gf-agents-diff.txt
echo 'OPERATOR-PROXY CONFIRMATION: "The AGENTS.md diff above is approved verbatim; re-run the same command with --yes."'
rc=0; python3 "$GEN" apply --target "$GF" --manifest "$FIX/manifest.json" --entry AGENTS.md --yes > /tmp/gf-agents-yes.txt 2>&1 || rc=$?
echo "apply AGENTS.md --yes exit=$rc"
[ $rc -eq 0 ] || stop "greenfield AGENTS.md apply --yes failed"
art gf-agents-yes-output /tmp/gf-agents-yes.txt
if diff -q /tmp/gf-agents-diff.txt <(head -n -1 /tmp/gf-agents-yes.txt) >/dev/null; then
  echo "RE-PRINTED DIFF: byte-identical to the reviewed diff"
else
  echo "RE-PRINTED DIFF: DIFFERS from the reviewed diff (compare artifacts above)"
fi
rc=0; python3 "$GEN" apply --target "$GF" --manifest "$FIX/manifest.json" --entry CLAUDE.md > /tmp/gf-claude-diff.txt 2>/dev/null || rc=$?
echo "apply CLAUDE.md (no --yes) exit=$rc (expect 3)"
[ $rc -eq 3 ] || stop "expected refusal exit 3 for CLAUDE.md, got $rc"
art gf-claude-review-diff /tmp/gf-claude-diff.txt
echo 'OPERATOR-PROXY CONFIRMATION: "The CLAUDE.md diff above is approved verbatim; re-run the same command with --yes."'
rc=0; python3 "$GEN" apply --target "$GF" --manifest "$FIX/manifest.json" --entry CLAUDE.md --yes > /tmp/gf-claude-yes.txt 2>&1 || rc=$?
echo "apply CLAUDE.md --yes exit=$rc"
[ $rc -eq 0 ] || stop "greenfield CLAUDE.md apply --yes failed"
tail -1 /tmp/gf-claude-yes.txt
rc=0; python3 "$GEN" apply --target "$GF" --manifest "$FIX/manifest.json" --entry AGENTS.md --yes > /tmp/gf-agents-noop.txt 2>&1 || rc=$?
echo "idempotence re-apply exit=$rc: $(cat /tmp/gf-agents-noop.txt)"
grep -q '^no-op' /tmp/gf-agents-noop.txt || stop "idempotence re-apply was not a no-op"
git -C "$GF" add AGENTS.md CLAUDE.md || stop "gf activation add"
git -C "$GF" commit -q -m "chore: activate agentic-sdlc instruction surfaces (journey fixture)" || stop "gf activation commit"
echo "greenfield log:"; git -C "$GF" log --oneline
echo "greenfield status after activation commit: '$(git -C "$GF" status --porcelain)'"

echo "--- brownfield fixture ---"
BF="$FIX/brownfield"
must git init -b main "$BF"
mkdir -p "$BF/.github/workflows" "$BF/src"
cat > "$BF/AGENTS.md" <<'EOF2'
# Legacy payments service - agent notes

Run `make test` before proposing changes. Deployments go through the release captain.
EOF2
printf '[tools]\nnode = "20.11.1"\n' > "$BF/mise.toml"
printf 'name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n' > "$BF/.github/workflows/ci.yml"
echo 'console.log("legacy");' > "$BF/src/index.js"
git -C "$BF" add AGENTS.md && git -C "$BF" commit -q -m "docs: agent notes" || stop "bf c1"
git -C "$BF" add mise.toml src && git -C "$BF" commit -q -m "chore: toolchain and src" || stop "bf c2"
git -C "$BF" add .github && git -C "$BF" commit -q -m "ci: workflow" || stop "bf c3"
rc=0; python3 "$GEN" classify --target "$BF" > /tmp/classify-bf.json 2>&1 || rc=$?
echo "classify exit=$rc"
art classify-brownfield.json /tmp/classify-bf.json
grep -q '"verdict":"brownfield"' /tmp/classify-bf.json || stop "brownfield fixture did not classify brownfield"
echo 'OPERATOR-PROXY CONFIRMATION (brownfield): "Occupied surfaces reviewed (.github, AGENTS.md, mise.toml). Approve the additive marked-block merge into the existing AGENTS.md; touch nothing else."'
BF_BEFORE=$(sha256sum "$BF/AGENTS.md" | cut -d' ' -f1)
rc=0; python3 "$GEN" apply --target "$BF" --manifest "$FIX/manifest.json" --entry AGENTS.md > /tmp/bf-agents-diff.txt 2>/dev/null || rc=$?
echo "apply AGENTS.md (no --yes) exit=$rc (expect 3)"
[ $rc -eq 3 ] || stop "expected refusal exit 3, got $rc"
[ "$(sha256sum "$BF/AGENTS.md" | cut -d' ' -f1)" = "$BF_BEFORE" ] || stop "refused apply mutated the brownfield target"
art bf-agents-review-diff /tmp/bf-agents-diff.txt
echo 'OPERATOR-PROXY CONFIRMATION: "Diff approved verbatim; re-run the same command with --yes."'
rc=0; python3 "$GEN" apply --target "$BF" --manifest "$FIX/manifest.json" --entry AGENTS.md --yes > /tmp/bf-agents-yes.txt 2>&1 || rc=$?
echo "apply AGENTS.md --yes exit=$rc"
[ $rc -eq 0 ] || stop "brownfield apply --yes failed"
tail -1 /tmp/bf-agents-yes.txt
grep -q '^# Legacy payments service' "$BF/AGENTS.md" || stop "pre-existing brownfield content lost"
grep -q 'agentic-sdlc:start' "$BF/AGENTS.md" || stop "marked block absent after brownfield apply"
echo "brownfield AGENTS.md after splice:"
art bf-agents-after.md "$BF/AGENTS.md"
git -C "$BF" add AGENTS.md && git -C "$BF" commit -q -m "chore: splice agentic-sdlc marked block into AGENTS.md (journey fixture)" || stop "bf activation commit"
echo "brownfield log:"; git -C "$BF" log --oneline

echo "--- refuse-and-ask fixture ---"
RA="$FIX/refuse-ask"
must git init -b main "$RA"
echo 'print("one")' > "$RA/one.py"; git -C "$RA" add one.py; git -C "$RA" commit -q -m "one" || stop "ra c1"
echo 'print("two")' > "$RA/two.py"; git -C "$RA" add two.py; git -C "$RA" commit -q -m "two" || stop "ra c2"
echo 'print("dirty")' >> "$RA/one.py"
rc=0; python3 "$GEN" classify --target "$RA" > /tmp/classify-ra.json 2>&1 || rc=$?
echo "classify exit=$rc"
art classify-refuse-and-ask.json /tmp/classify-ra.json
grep -q '"verdict":"refuse-and-ask"' /tmp/classify-ra.json || stop "refuse-and-ask fixture did not classify refuse-and-ask"
echo "operator would be ASKED here; the fixture run stops at the named refusal, per runbook step 2"
rc=0; python3 "$GEN" classify --target "$BF/src" > /tmp/classify-subdir.out 2>&1 || rc=$?
echo "classify(subdirectory) exit=$rc (expect 2)"
cat /tmp/classify-subdir.out
[ $rc -eq 2 ] || stop "subdirectory probe expected exit 2, got $rc"

step "S12 ccodex sdlc uninstall (receipt-directed retirement)"
t0=$SECONDS
rc=0; ccodex sdlc uninstall 2>&1 || rc=$?
echo "uninstall exit=$rc"
[ $rc -eq 0 ] || stop "uninstall failed rc=$rc"
echo "STEP-TIME uninstall $((SECONDS-t0))s"
echo "activation plane after uninstall:"
ls -la "$ACT" "$ACT/receipts" 2>&1
if [ -e "$ACT/active-receipt.json" ]; then
  art active-receipt-postuninstall.json "$ACT/active-receipt.json"
else
  echo "active-receipt.json: ABSENT after uninstall"
fi
for f in "$ACT/receipts"/*.json; do
  echo "receipt: $f sha256=$(sha256sum "$f" | cut -d' ' -f1)"
  art "activation-plane-receipt-$(basename "$f")" "$f"
done
echo "claude home after uninstall:"
find "$HOME/.claude" 2>/dev/null | sort
for c in sdlc-init sdlc-frame sdlc-wave sdlc-mission sdlc-rightsize; do
  if find "$HOME/.claude" -name "${c}*" 2>/dev/null | grep -q .; then echo "RESIDUAL: $c still present"; else echo "RETIRED: command $c absent"; fi
done
if [ -d "$HOME/.claude/skills/agentic-sdlc" ]; then echo "RESIDUAL: skills/agentic-sdlc still present"; else echo "RETIRED: skills/agentic-sdlc absent"; fi
rc=0; ccodex sdlc status --json > /tmp/status-postuninstall.json 2>/dev/null || rc=$?
echo "status --json (post-uninstall) exit=$rc"
art status-postuninstall.json /tmp/status-postuninstall.json

step "S13 final sweep"
echo "state plane tree:"
find "$STATE/agentic-sdlc" -maxdepth 3 2>/dev/null | sort
echo "data plane tree (top):"
find "$DATA/agentic-sdlc" -maxdepth 4 2>/dev/null | sort | head -20
echo "TOTAL-ELAPSED ${SECONDS}s"
echo "##### JOURNEY-COMPLETE"
