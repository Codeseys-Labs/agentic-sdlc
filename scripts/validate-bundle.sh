#!/bin/bash
# Validate bundle metadata, portable installer source, scripts, and task contracts.
set -uo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
errors=0; warns=0
err(){ printf 'ERROR: %s\n' "$*" >&2; errors=$((errors+1)); }
warn(){ printf 'warn:  %s\n' "$*"; warns=$((warns+1)); }
python_cmd=()
if command -v uv >/dev/null 2>&1 && uv run --python 3.12.11 python -c 'import sys; assert sys.version_info >= (3,12)' >/dev/null 2>&1; then
  python_cmd=(uv run --python 3.12.11 python)
else
  # Bootstrap CI may validate source before mise installs uv. Public mise tasks use uv above.
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,8)' >/dev/null 2>&1; then python_cmd=("$candidate"); break; fi
  done
  if [ "${#python_cmd[@]}" -eq 0 ] && command -v py >/dev/null 2>&1 && py -3 -c 'import sys; assert sys.version_info >= (3,8)' >/dev/null 2>&1; then python_cmd=(py -3); fi
fi
[ "${#python_cmd[@]}" -gt 0 ] || { err 'uv-managed Python 3.12.11 is required (or Python 3.8+ for direct bootstrap validation)'; python_cmd=(false); }

for skill in "$root"/skills/*/SKILL.md; do
  [ -e "$skill" ] || continue
  dir=$(basename "$(dirname "$skill")"); name=$(awk -F': *' '/^name:/{print $2; exit}' "$skill")
  [ "$name" = "$dir" ] || err "$dir: name does not match directory"
  desc_len=$("${python_cmd[@]}" - "$skill" <<'PY'
import re,sys
text=open(sys.argv[1],encoding='utf-8').read(); m=re.search(r'^---\n(.*?)\n---',text,re.S); fm=m.group(1) if m else ''
d=re.search(r'^description:\s*(.*)$',fm,re.M); value=''
if d:
    value=d.group(1).strip()
    if value in {'|','>','|-','>-'}: value=' '.join(x.strip() for x in fm[d.end():].splitlines() if x.startswith('  '))
    else:
        for x in fm[d.end():].splitlines():
            if x.startswith(('  ','\t')): value+=' '+x.strip()
            else: break
print(len(value.strip()))
PY
)
  [ "${desc_len:-0}" -gt 0 ] || err "$dir: missing description"
  [ "${desc_len:-0}" -le 1024 ] || err "$dir: description exceeds 1024 characters"
  while IFS= read -r ref; do [ -f "$(dirname "$skill")/$ref" ] || err "$dir: missing $ref"; done < <(grep -oE '\breferences/[A-Za-z0-9._-]+\.md' "$skill" | sort -u)
done

installer="$root/scripts/install_skill_bundle.py"
[ -f "$installer" ] || err 'scripts/install_skill_bundle.py is required'
if [ -f "$installer" ]; then
  "${python_cmd[@]}" - "$root" <<'PY' || err 'Python source failed to compile'
import pathlib,sys
for p in pathlib.Path(sys.argv[1]).rglob('*.py'):
    if '.git' not in p.parts and '__pycache__' not in p.parts: compile(p.read_text(),str(p),'exec')
PY
fi
if command -v git >/dev/null 2>&1 && git -C "$root" ls-files -z -- '*.pyc' | grep -qz .; then
  err 'Python bytecode must not be committed'
fi

for a in "$root"/agents/claude/*.md; do [ -e "$a" ] || continue; grep -q '^name:' "$a" || err "$a: missing name"; grep -q '^description:' "$a" || err "$a: missing description"; done
for t in "$root"/agents/codex/*.toml "$root"/agents/codex/*/*.toml; do
  [ -e "$t" ] || continue
  "${python_cmd[@]}" -c "import tomllib; d=tomllib.load(open('$t','rb')); assert d.get('name') and d.get('description')" 2>/dev/null || err "$t: invalid TOML or missing metadata"
done

required=(bundle:install bundle:status bundle:uninstall bundle:install:claude bundle:install:codex bundle:install:all-hosts bundle:status:all-hosts test self-test check hooks:install jj:init setup)
if [ ! -f "$root/mise.toml" ]; then err 'mise.toml is required'; else
  for task in "${required[@]}"; do
    if ! "${python_cmd[@]}" - "$root/mise.toml" "$task" <<'PY'
import sys
try:
    import tomllib
except ImportError:
    raise SystemExit(2)
with open(sys.argv[1], 'rb') as handle:
    tasks = tomllib.load(handle).get('tasks', {})
raise SystemExit(0 if sys.argv[2] in tasks else 1)
PY
    then err "mise.toml missing task $task"; fi
  done
fi
for s in "$root"/scripts/*.sh; do [ -e "$s" ] || continue; bash -n "$s" || err "$s does not parse"; done
if command -v pwsh >/dev/null 2>&1; then for p in "$root"/scripts/*.ps1; do [ -e "$p" ] || continue; pwsh -NoProfile -NonInteractive -Command "[System.Management.Automation.Language.Parser]::ParseFile('$p',[ref]\$null,[ref]\$null)" >/dev/null || err "$p does not parse"; done; fi
for mf in .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json gemini-extension.json; do [ -f "$root/$mf" ] || continue; "${python_cmd[@]}" -c 'import json,sys; json.load(open(sys.argv[1]))' "$root/$mf" || err "invalid JSON: $mf"; done

# Optional CAO remains opt-in; retain an explicit policy check even on partial branches.
if [ -f "$root/scripts/install-skill-bundle.sh" ]; then grep -q 'INSTALL_CAO' "$root/scripts/install-skill-bundle.sh" || err 'CAO opt-in check missing'; fi
if grep -rInE '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH) PRIVATE KEY|amazon\.com/[a-z]|\.a2z\.com|aws\.dev/)' --include='*.md' --include='*.sh' --include='*.ps1' --include='*.toml' --include='*.json' --include='*.yml' --include='*.yaml' --include='*.py' --exclude-dir=.git "$root" 2>/dev/null | grep -v validate-bundle.sh; then err 'possible secret or internal hostname found'; fi
printf '\nvalidate-bundle: %d error(s), %d warning(s)\n' "$errors" "$warns"
exit "$([ "$errors" -gt 0 ] && echo 1 || echo 0)"
