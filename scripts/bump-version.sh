#!/bin/bash
# Bump every version-carrying manifest in one shot (targets declared in .version-bump.json).
#   bump-version.sh <new-version>   # write all targets + update .version-bump.json current
#   bump-version.sh --check         # exit 1 if any target disagrees with current
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$repo_root/.version-bump.json"

python_cmd=()
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(python3)
elif command -v python >/dev/null 2>&1 && python -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(python)
elif command -v py >/dev/null 2>&1 && py -3 -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(py -3)
else
  echo "error: Python 3.8+ is required to update version manifests" >&2
  exit 1
fi

"${python_cmd[@]}" - "$manifest" "$repo_root" "${1:-}" <<'PY'
import json, sys, re
manifest_path, root, arg = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(manifest_path, encoding="utf-8"))
current = m["current"]
drift = []

def get_set(path, jqfield, newval=None):
    d = json.load(open(path, encoding="utf-8"))
    keys = [k for k in jqfield.strip('.').split('.') if k]
    obj = d
    for k in keys[:-1]:
        obj = obj[int(k)] if k.isdigit() else obj[k]
    last = keys[-1]
    cur = obj[int(last)] if last.isdigit() else obj[last]
    if newval is not None:
        if last.isdigit(): obj[int(last)] = newval
        else: obj[last] = newval
        json.dump(d, open(path, 'w', encoding="utf-8"), indent=2)
        open(path, 'a', encoding="utf-8").write('\n')
    return cur

if arg == "--check":
    for t in m["targets"]:
        v = get_set(f"{root}/{t['file']}", t["jq"])
        status = "ok " if v == current else "DRIFT"
        print(f"{status} {t['file']} {t['jq']} = {v} (expect {current})")
        if v != current: drift.append(t['file'])
    sys.exit(1 if drift else 0)
elif re.match(r'^\d+\.\d+\.\d+$', arg or ""):
    for t in m["targets"]:
        old = get_set(f"{root}/{t['file']}", t["jq"], arg)
        print(f"bumped {t['file']}: {old} -> {arg}")
    m["current"] = arg
    json.dump(m, open(manifest_path, 'w', encoding="utf-8"), indent=2)
    open(manifest_path, 'a', encoding="utf-8").write('\n')
    print(f"current -> {arg}")
else:
    print("usage: bump-version.sh <x.y.z> | --check", file=sys.stderr)
    sys.exit(2)
PY
