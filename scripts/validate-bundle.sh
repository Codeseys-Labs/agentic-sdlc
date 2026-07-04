#!/usr/bin/env bash
# Validate the bundle before commit/release. Catches the cross-agent silent failures:
#   - SKILL.md frontmatter missing name/description
#   - skill name != directory name (breaks some hosts)
#   - description > 1024 chars (Codex SILENTLY SKIPS the skill)
#   - broken relative references (references/*.md links that don't exist)
#   - shell scripts that don't parse (bash -n)
#   - plugin/marketplace manifests invalid (via `claude plugins validate` when available)
#   - accidental secrets/internal hostnames
# Exit non-zero on any error; warnings don't fail.
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
errors=0; warns=0
err() { echo "ERROR: $*" >&2; errors=$((errors+1)); }
warn() { echo "warn:  $*"; warns=$((warns+1)); }

# --- skills ---
for skill in "$repo_root"/skills/*/SKILL.md; do
  [ -e "$skill" ] || continue
  dir="$(basename "$(dirname "$skill")")"
  name="$(awk -F': *' '/^name:/{print $2; exit}' "$skill")"
  [ -n "$name" ] || err "$dir: SKILL.md missing 'name:'"
  [ "$name" = "$dir" ] || err "$dir: name '$name' != directory name '$dir'"
  # description length (block scalar or inline)
  desc_len=$(python3 - "$skill" <<'EOF'
import re, sys
t = open(sys.argv[1]).read()
m = re.search(r'^---\n(.*?)\n---', t, re.S)
fm = m.group(1) if m else ''
d = re.search(r'^description:\s*\|?\s*\n?((?:(?:  .*|\S.*)\n?)*?)(?=^\S|\Z)', fm, re.M)
import textwrap
val = ''
m2 = re.search(r'^description:\s*(.*)$', fm, re.M)
if m2 and m2.group(1).strip() not in ('|', '>', '|-', '>-'):
    val = m2.group(1)
    # continuation lines (indented)
    after = fm[m2.end():]
    for line in after.splitlines():
        if line.startswith(('  ', '\t')) and not re.match(r'^\s*\w+:', line):
            val += ' ' + line.strip()
        else:
            break
else:
    # block scalar
    after = fm[m2.end():] if m2 else ''
    lines = []
    for line in after.splitlines():
        if line.startswith('  '):
            lines.append(line.strip())
        elif line.strip() == '':
            continue
        else:
            break
    val = ' '.join(lines)
print(len(val.strip()))
EOF
)
  if [ "${desc_len:-0}" -eq 0 ]; then err "$dir: SKILL.md missing/empty 'description:'"
  elif [ "$desc_len" -gt 1024 ]; then err "$dir: description ${desc_len} chars > 1024 — Codex will SILENTLY SKIP this skill"
  elif [ "$desc_len" -gt 900 ]; then warn "$dir: description ${desc_len} chars (nearing the 1024 Codex cap)"
  fi
  # broken relative references
  grep -oE '\breferences/[A-Za-z0-9._-]+\.md' "$skill" | sort -u | while read -r ref; do
    [ -f "$(dirname "$skill")/$ref" ] || echo "MISSINGREF $dir $ref"
  done | while read -r _ d r; do err "$d: referenced $r does not exist"; done
done

# --- claude agents ---
for a in "$repo_root"/agents/claude/*.md; do
  [ -e "$a" ] || continue
  grep -q '^name:' "$a" || err "agents/claude/$(basename "$a"): missing 'name:'"
  grep -q '^description:' "$a" || err "agents/claude/$(basename "$a"): missing 'description:'"
done

# --- codex role TOMLs (tomllib parse on py3.11+; grep fallback on older) ---
# Includes repo-scoped sets in subdirs (agents/codex/research/ etc.).
for t in "$repo_root"/agents/codex/*.toml "$repo_root"/agents/codex/*/*.toml; do
  [ -e "$t" ] || continue
  if python3 -c 'import tomllib' 2>/dev/null; then
    python3 -c "import tomllib,sys; d=tomllib.load(open(sys.argv[1],'rb')); assert d.get('name') and d.get('description'), 'name/description required'" "$t" \
      || err "agents/codex/$(basename "$t"): invalid TOML or missing name/description"
  else
    grep -q '^name = ' "$t" && grep -q '^description = ' "$t" \
      || err "agents/codex/$(basename "$t"): missing name/description (grep fallback; py<3.11)"
  fi
done

# --- commands ---
for c in "$repo_root"/commands/*.md; do
  [ -e "$c" ] || continue
  grep -q '^description:' "$c" || warn "commands/$(basename "$c"): missing 'description:' frontmatter"
done

# --- shell scripts parse ---
for s in "$repo_root"/scripts/*.sh; do
  bash -n "$s" || err "scripts/$(basename "$s") does not parse"
done

# --- plugin/marketplace manifests ---
if command -v claude >/dev/null 2>&1; then
  claude plugins validate "$repo_root" >/dev/null 2>&1 || err "claude plugins validate failed for repo root"
else
  python3 -c "import json;json.load(open('$repo_root/.claude-plugin/marketplace.json'));json.load(open('$repo_root/.claude-plugin/plugin.json'))" \
    || err "manifest JSON invalid"
fi

# --- secrets / internal-hostname sweep (bundle must stay shareable) ---
if grep -rInE '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH) PRIVATE KEY|amazon\.com/[a-z]|\.a2z\.com|aws\.dev/)' \
    --include='*.md' --include='*.sh' --include='*.toml' --include='*.json' \
    "$repo_root/skills" "$repo_root/agents" "$repo_root/commands" "$repo_root/scripts" "$repo_root/cao-profiles" 2>/dev/null | grep -v 'validate-bundle.sh'; then
  err "possible secret or internal hostname found (above)"
fi

echo
echo "validate-bundle: $errors error(s), $warns warning(s)"
exit "$([ "$errors" -gt 0 ] && echo 1 || echo 0)"
