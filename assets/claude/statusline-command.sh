#!/usr/bin/env bash
# Portable Claude Code status line. It is offline and advisory: price estimates use the
# built-in family table below and never establish billing or model-serving identity.
set -u

input="$(cat 2>/dev/null || true)"
if ! command -v jq >/dev/null 2>&1 || ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"$input"; then
  printf 'claude\n'
  exit 0
fi

# ANSI colors.
dim='\033[2m'; cyan='\033[36m'; green='\033[32m'; yellow='\033[33m'
magenta='\033[35m'; red='\033[31m'; blue='\033[34m'; white='\033[37m'; reset='\033[0m'

jqr() { jq -r "$1 // empty" <<<"$input" 2>/dev/null || true; }
jqn() { local value; value="$(jqr "$1")"; [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] && printf '%s' "$value" || printf '0'; }
integer() { jq -nr --arg value "$1" '($value | tonumber? // 0) | floor' 2>/dev/null || printf '0'; }
rounded() { jq -nr --arg value "$1" '($value | tonumber? // 0) | round' 2>/dev/null || printf '0'; }

project_dir="$(jqr '.workspace.project_dir // .workspace.current_dir // .cwd')"
[ -n "$project_dir" ] || project_dir="${PWD:-.}"
cwd="$project_dir"
case "$cwd" in "$HOME"*) cwd="~${cwd#"$HOME"}" ;; esac
host="$(hostname -s 2>/dev/null || hostname 2>/dev/null || printf '?')"
model="$(jqr '.model.id')"; effort="$(jqr '.effort.level')"
total_input="$(jqn '.context_window.total_input_tokens')"
total_output="$(jqn '.context_window.total_output_tokens')"
used_pct="$(jqr '.context_window.used_percentage')"
window_size="$(jqn '.context_window.context_window_size')"
current_input="$(jqn '.context_window.current_usage.input_tokens')"
cache_creation="$(jqn '.context_window.current_usage.cache_creation_input_tokens')"
cache_read="$(jqn '.context_window.current_usage.cache_read_input_tokens')"
cost_usd="$(jqr '.cost.total_cost_usd')"; duration_ms="$(jqr '.cost.total_duration_ms')"
rl_5h="$(jqr '.rate_limits.five_hour.used_percentage')"; rl_7d="$(jqr '.rate_limits.seven_day.used_percentage')"
pr_number="$(jqr '.pr.number')"; pr_review="$(jqr '.pr.review_state')"
output_style="$(jqr '.output_style.name')"; transcript_path="$(jqr '.transcript_path')"

format_tokens() {
  jq -nr --arg value "$1" '
    ($value | tonumber? // 0) as $n |
    if $n >= 1000000 then (($n / 1000000 * 10 | round) / 10 | tostring) + "m"
    elif $n >= 1000 then (($n / 1000 * 10 | round) / 10 | tostring) + "k"
    else ($n | floor | tostring) end' 2>/dev/null || printf '0'
}

format_duration() {
  local ms total_s hours minutes seconds
  ms="$(integer "$1")"; total_s=$((ms / 1000)); hours=$((total_s / 3600))
  minutes=$(((total_s % 3600) / 60)); seconds=$((total_s % 60))
  if ((hours > 0)); then printf '%dh%dm' "$hours" "$minutes"
  elif ((minutes > 0)); then printf '%dm' "$minutes"
  else printf '%ds' "$seconds"; fi
}

context_bar() {
  local used filled empty color bar='' i
  used="$(integer "$1")"; ((used < 0)) && used=0; ((used > 100)) && used=100
  filled="$(rounded "$(jq -nr --argjson used "$used" '$used * 12 / 100')")"
  ((filled < 0)) && filled=0; ((filled > 12)) && filled=12; empty=$((12 - filled))
  if ((used >= 80)); then color="$red"; elif ((used >= 60)); then color="$yellow"; else color="$green"; fi
  bar="$color"; for ((i=0; i<filled; i++)); do bar+='▓'; done
  bar+="$dim"; for ((i=0; i<empty; i++)); do bar+='░'; done
  printf '%b' "${bar}${reset}"
}

branch=''
if command -v git >/dev/null 2>&1 && git -C "$project_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git -C "$project_dir" --no-optional-locks branch --show-current 2>/dev/null || true)"
  [ -n "$branch" ] || branch="$(git -C "$project_dir" rev-parse --short HEAD 2>/dev/null || true)"
fi

location="${dim}${host}${reset}:${cyan}${cwd}${reset}"
[ -n "$branch" ] && location+=" ${magenta}${branch}${reset}"
if [ -n "$pr_number" ]; then
  case "$pr_review" in approved) glyph='✓'; color="$green";; changes_requested) glyph='✗'; color="$red";; pending) glyph='•'; color="$yellow";; draft) glyph='◌'; color="$dim";; *) glyph=''; color="$dim";; esac
  location+=" ${dim}#${pr_number}${reset}${color}${glyph}${reset}"
fi

model_info=''
if [ -n "$model" ]; then
  short_model="$(grep -oE '(fable|opus|sonnet|haiku)' <<<"$model" | head -1 || true)"; [ -n "$short_model" ] || short_model="$model"
  model_info=" ${dim}|${reset} ${blue}${short_model}${reset}"
  if [ -n "$effort" ]; then
    case "$effort" in low) color="$dim";; medium) color="$white";; high) color="$cyan";; xhigh) color="$yellow";; max) color="$red";; ultra) color="$magenta";; *) color="$dim";; esac
    model_info+="${dim}·${reset}${color}${effort}${reset}"
  fi
fi

if [[ "$used_pct" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  used_int="$(integer "$used_pct")"
  if ((used_int >= 80)); then color="$red"; elif ((used_int >= 60)); then color="$yellow"; else color="$green"; fi
  context_stats="$(context_bar "$used_pct") ${color}${used_int}%${reset} ${dim}·${reset} ${dim}in${reset} ${white}$(format_tokens "$total_input")${reset} ${dim}out${reset} ${white}$(format_tokens "$total_output")${reset} ${dim}/${reset} ${dim}$(format_tokens "$window_size")${reset}"
else
  context_stats="${dim}in${reset} ${white}$(format_tokens "$total_input")${reset} ${dim}out${reset} ${white}$(format_tokens "$total_output")${reset}"
fi

cache_stats=''; cache_read_int="$(integer "$cache_read")"; cache_create_int="$(integer "$cache_creation")"; current_input_int="$(integer "$current_input")"
if ((cache_read_int > 0 || cache_create_int > 0)); then
  cacheable=$((cache_read_int + current_input_int))
  if ((cacheable > 0)); then
    cache_pct="$(rounded "$(jq -nr --argjson read "$cache_read_int" --argjson total "$cacheable" '$read * 100 / $total')")"
    if ((cache_pct >= 80)); then color="$green"; elif ((cache_pct >= 50)); then color="$yellow"; else color="$dim"; fi
    cache_stats=" ${dim}·${reset} ${dim}cache${reset} ${color}${cache_pct}%${reset} ${dim}($(format_tokens "$cache_read"))${reset}"
  fi
fi

cost_stats=''
if [[ "$cost_usd" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  cost_fmt="$(jq -nr --arg value "$cost_usd" '($value | tonumber) * 100 | round / 100 | @text')"
  cost_stats=" ${dim}·${reset} ${green}\$${cost_fmt}${reset}"
  [[ "$duration_ms" =~ ^[0-9]+([.][0-9]+)?$ ]] && cost_stats+=" ${dim}$(format_duration "$duration_ms")${reset}"
fi

# Approximate breakdown of host-reported total cost. Model-family rates are intentionally
# embedded: status rendering never performs network I/O and this value is not a billing receipt.
agent_cost_stats=''
subagents_dir="${transcript_path%.jsonl}/subagents"
if [ -n "$transcript_path" ] && [ -d "$subagents_dir" ]; then
  cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/agentic-sdlc/statusline"
  if mkdir -p -m 700 "$cache_root" 2>/dev/null; then
    session_key="$(printf '%s' "$subagents_dir" | jq -sRr '@uri' | tr '/%' '__' | cut -c1-160)"
    cache_file="$cache_root/${session_key:-session}.cost"
    newest="$(find "$subagents_dir" -name 'agent-*.jsonl' -newer "$cache_file" -print -quit 2>/dev/null || true)"
    if [ -s "$cache_file" ] && [ -z "$newest" ]; then
      agent_cost="$(cat "$cache_file" 2>/dev/null || true)"
    else
      agent_cost="$(find "$subagents_dir" -name 'agent-*.jsonl' -exec cat {} + 2>/dev/null | jq -rs '
        map(select(.message.usage != null and .message.model != null and .message.model != "<synthetic>"))
        | group_by(.message.id) | map(last.message)
        | map((.model | sub("^.*?(?=claude)"; "") | sub("\\[.*\\]$"; "")) as $id
          | (if ($id | test("fable")) then {i:10,o:50} elif ($id | test("opus")) then {i:5,o:25}
             elif ($id | test("sonnet")) then {i:3,o:15} elif ($id | test("haiku")) then {i:1,o:5}
             else {i:5,o:25} end) as $p | .usage as $u
          | ($u.input_tokens // 0)*$p.i + ($u.output_tokens // 0)*$p.o
          + ($u.cache_read_input_tokens // 0)*$p.i*0.1
          + ((($u.cache_creation.ephemeral_5m_input_tokens // $u.cache_creation_input_tokens) // 0)*$p.i*1.25)
          + (($u.cache_creation.ephemeral_1h_input_tokens // 0)*$p.i*2)) | (add // 0)/1000000' 2>/dev/null || true)"
      if [[ "$agent_cost" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        temp_file="$cache_file.$$"; umask 077
        printf '%s\n' "$agent_cost" >"$temp_file" 2>/dev/null && mv -f "$temp_file" "$cache_file" 2>/dev/null || rm -f "$temp_file"
      fi
    fi
    if [[ "${agent_cost:-}" =~ ^[0-9]+([.][0-9]+)?$ ]] && [ "$(jq -nr --arg value "$agent_cost" '($value|tonumber) >= 0.01')" = true ]; then
      agent_cost_fmt="$(jq -nr --arg value "$agent_cost" '($value|tonumber)*100|round/100|@text')"
      agent_cost_stats=" ${dim}·${reset} ${dim}agents${reset} ${green}\$${agent_cost_fmt}${reset}"
    fi
  fi
fi

ratelimit_stats=''
append_rate_limit() {
  local label="$1" value="$2" number color
  [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]] || return 0; number="$(rounded "$value")"
  if ((number >= 80)); then color="$red"; elif ((number >= 50)); then color="$yellow"; else color="$dim"; fi
  ratelimit_stats+=" ${dim}·${reset} ${dim}${label}${reset} ${color}${number}%${reset}"
}
append_rate_limit '5h' "$rl_5h"; append_rate_limit '7d' "$rl_7d"

style_stats=''
[ -n "$output_style" ] && [ "$output_style" != default ] && [ "$output_style" != null ] && style_stats=" ${dim}·${reset} ${dim}[${output_style}]${reset}"
printf '%b\n' "${location}${model_info} ${dim}|${reset} ${context_stats}${cache_stats}${cost_stats}${agent_cost_stats}${ratelimit_stats}${style_stats}"
