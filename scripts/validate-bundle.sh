#!/bin/bash
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
bash_bin="${BASH:-/bin/bash}"
errors=0; warns=0
err() { echo "ERROR: $*" >&2; errors=$((errors+1)); }
warn() { echo "warn:  $*"; warns=$((warns+1)); }

# Use a real Python 3 interpreter on Unix and Windows (where only python or py may exist).
python_cmd=()
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(python3)
elif command -v python >/dev/null 2>&1 && python -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(python)
elif command -v py >/dev/null 2>&1 && py -3 -c 'import sys; assert sys.version_info >= (3, 8)' >/dev/null 2>&1; then
  python_cmd=(py -3)
else
  echo "ERROR: Python 3.8+ is required to validate skill metadata and manifests" >&2
  exit 1
fi

# --- skills ---
for skill in "$repo_root"/skills/*/SKILL.md; do
  [ -e "$skill" ] || continue
  dir="$(basename "$(dirname "$skill")")"
  name="$(awk -F': *' '/^name:/{print $2; exit}' "$skill")"
  [ -n "$name" ] || err "$dir: SKILL.md missing 'name:'"
  [ "$name" = "$dir" ] || err "$dir: name '$name' != directory name '$dir'"
  # description length (block scalar or inline)
  desc_len=$("${python_cmd[@]}" - "$skill" <<'EOF'
import re, sys
t = open(sys.argv[1], encoding='utf-8').read()
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
  # broken relative references — NO pipeline-subshell: err() must mutate the real counter
  # (a `... | while read` loop runs in a subshell and its errors+=1 is discarded — the
  # gate then prints ERROR but exits 0; caught by the 2026-07-04 session audit).
  while IFS= read -r ref; do
    [ -n "$ref" ] || continue
    [ -f "$(dirname "$skill")/$ref" ] || err "$dir: referenced $ref does not exist"
  done < <(grep -oE '\breferences/[A-Za-z0-9._-]+\.md' "$skill" | sort -u)
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
  if "${python_cmd[@]}" -c 'import tomllib' 2>/dev/null; then
    "${python_cmd[@]}" -c "import tomllib,sys; d=tomllib.load(open(sys.argv[1],'rb')); assert d.get('name') and d.get('description'), 'name/description required'" "$t" \
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
  "$bash_bin" -n "$s" || err "scripts/$(basename "$s") does not parse"
done

# --- plugin/marketplace manifests (all hosts) ---
if command -v claude >/dev/null 2>&1; then
  claude plugins validate "$repo_root" >/dev/null 2>&1 || err "claude plugins validate failed for repo root"
fi
for mf in .claude-plugin/plugin.json .claude-plugin/marketplace.json \
          .codex-plugin/plugin.json .agents/plugins/marketplace.json gemini-extension.json; do
  [ -f "$repo_root/$mf" ] || continue
  "${python_cmd[@]}" -c 'import json,sys;json.load(open(sys.argv[1], encoding="utf-8"))' "$repo_root/$mf" || err "invalid JSON: $mf"
done

# --- version drift across manifests ---
if [ -x "$repo_root/scripts/bump-version.sh" ]; then
  "$bash_bin" "$repo_root/scripts/bump-version.sh" --check >/dev/null 2>&1 || err "manifest version drift — run scripts/bump-version.sh --check"
fi

# --- native-baseline policy (optional adapters must never become prerequisites) ---
flagship="$repo_root/skills/agentic-sdlc-orchestrator/SKILL.md"
preflight="$repo_root/scripts/check-agentic-sdlc-prereqs.sh"
installer="$repo_root/scripts/install-skill-bundle.sh"
openai_meta="$repo_root/skills/agentic-sdlc-orchestrator/agents/openai.yaml"

if [ ! -f "$preflight" ]; then
  err "native-baseline preflight is missing"
else
  grep -qE '^[[:space:]]*req[[:space:]]+(cao|cmux|tmux)([[:space:]]|$)' "$preflight" \
    && err "preflight makes an optional adapter required (cao/cmux/tmux)"

  # Behavioral regression: a native host with core tools and no adapters must pass.
  policy_tmp="$(mktemp -d)"
  for tool in git gh sd; do
    printf '#!%s\nexit 0\n' "$bash_bin" > "$policy_tmp/$tool"
    chmod +x "$policy_tmp/$tool"
  done
  if ! PATH="$policy_tmp" AGENTIC_SDLC_HOST_READY=1 CODEX_HOME="$policy_tmp/no-codex" \
    "$bash_bin" "$preflight" >/dev/null 2>&1; then
    err "preflight fails on a native host when cao, cmux, and tmux are absent"
  fi
  rm -rf -- "$policy_tmp"
fi

if [ ! -f "$installer" ]; then
  err "bundle installer is missing"
else
  grep -qF 'elif [ "${INSTALL_CAO:-0}" != "1" ]; then' "$installer" \
    || err "installer must require explicit INSTALL_CAO=1 opt-in before touching CAO"
fi

grep -qF "requires no CAO, cmux, or tmux" "$flagship" \
  || err "flagship must declare the provider-native no-CAO/cmux/tmux baseline"
grep -qF "provider-native" "$openai_meta" \
  || err "flagship default prompt must lead with provider-native orchestration"
grep -qF "CAO/DWL" "$openai_meta" \
  && err "flagship default prompt must not require the CAO/DWL path"
for mf in .claude-plugin/plugin.json .claude-plugin/marketplace.json \
          .codex-plugin/plugin.json .agents/plugins/marketplace.json gemini-extension.json; do
  grep -qi "provider-native" "$repo_root/$mf" \
    || err "$mf must describe the provider-native baseline"
done

# --- secrets / internal-hostname sweep (bundle must stay shareable) ---
# Whole repo (audit fix: previously skipped README/AGENTS.md/manifests/.github), minus .git.
if grep -rInE '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH) PRIVATE KEY|amazon\.com/[a-z]|\.a2z\.com|aws\.dev/)' \
    --include='*.md' --include='*.sh' --include='*.toml' --include='*.json' --include='*.yml' --include='*.yaml' --include='*.py' \
    --exclude-dir='.git' \
    "$repo_root" 2>/dev/null | grep -v 'validate-bundle.sh'; then
  err "possible secret or internal hostname found (above)"
fi

echo
echo "validate-bundle: $errors error(s), $warns warning(s)"
exit "$([ "$errors" -gt 0 ] && echo 1 || echo 0)"
