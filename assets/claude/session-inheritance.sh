# session-inheritance.sh — the shared session-inheritance and environment-variable policy for any
# launcher that prepares a SECOND Claude Code plane. scripts/muse-claude.sh is its one consumer
# today: ADR-0014 removed scripts/opencodex-claude.sh's plane, its scrub, and its inheritance call,
# so that launcher no longer sources this file. The policy stays here rather than in the one
# consumer so a future plane inherits the reviewed boundary instead of re-deriving it.
#
# Sourced, never executed. It defines functions and two policy lists and runs nothing at source
# time, so a launcher chooses when the scrub and the inheritance happen (scrub before any route
# variable is exported; inheritance after every credential assertion and before exec).
#
# WHAT THIS SOLVES. Both launchers point a SECOND Claude Code process at an isolated
# CLAUDE_CONFIG_DIR so the gateway/direct plane never mutates the operator's ~/.claude auth,
# roster agents, or model cache. Full isolation also cost the operator their prompt history,
# their project list, and their statusline -- the launched session opened blank. ADR-0010 splits
# the config dir into two classes instead of treating it as one indivisible thing:
#
#   INERT SESSION DATA  -- shared with the global install by symlink, so the launched session
#                          shows the operator's real history and projects.
#   CREDENTIAL-BEARING  -- never shared, never copied, never linked.
#
# WHY settings.json IS CONSTRUCTED AND NEVER COPIED. The global ~/.claude/settings.json `env`
# block is a credential carrier on a real host: verified 2026-08-07, this operator's file
# holds a live AWS_BEARER_TOKEN_BEDROCK alongside CLAUDE_CODE_USE_BEDROCK, AWS_REGION, and
# ANTHROPIC_DEFAULT_*_MODEL pins. Copying or symlinking the file would hand that credential to
# the gateway plane and would ALSO re-point the child at Bedrock, defeating the scrub that
# every ANTHROPIC*/CLAUDE* variable just performed. So the isolated settings.json is built
# key-by-key from an allowlist of exactly one stanza (statusLine), and the constructed result
# is asserted credential-free before it is written. An allowlist, not a denylist: a new
# credential-shaped key upstream is excluded by default rather than by having been predicted.
#
# WHY statusLine IS INHERITED BY VALUE. The stanza is read from whatever the global settings
# declare rather than hardcoded, so an operator who changes their statusline changes both
# planes. On this host it resolves to a `command` type naming an absolute script in the global
# config dir. That script therefore executes in the launched session -- accepted deliberately:
# it is the operator's own script, already trusted by their own primary session, and it is
# strictly less privileged there than here. A missing or non-command statusLine is not a
# failure; the launched session simply has none.

# Entries shared with the global install. Every one is inert per-session DATA that Claude Code
# reads and appends; none is an auth, permission, or routing input:
#   history.jsonl    prompt history across all projects   (the operator's actual reason for this)
#   projects/        per-project session transcripts      (resumable sessions, /resume list)
#   todos/           per-session todo lists
#   shell-snapshots/ captured shell functions and aliases
#   file-history/    edit undo history
# Verified on this host: shell-snapshots hold functions/aliases only -- zero credential-shaped
# variable names across all 11 present, and none contains AWS_BEARER_TOKEN_BEDROCK. They are
# re-verified per entry at link time rather than trusted from that one observation.
#
# DELIBERATELY NOT SHARED, and why each would breach the boundary rather than merely leak data:
#   .credentials.json  the subscription OAuth credential itself -- the exact thing ADR-0003
#                      forbids reaching the gateway, and what the launcher REFUSES over.
#   ../.claude.json    holds `oauthAccount` and `primaryApiKey` (verified present on this
#                      host), plus per-project trust decisions. Sharing it would carry both a
#                      credential marker and trust state across.
#   settings.json      constructed, never linked -- see the header.
#   sessions/          live pid/session registry. Two planes writing one registry would make
#                      each plane's process list report the other's sessions as its own.
#   session-env/       per-session captured environment. The scrub exists precisely so the
#                      child's environment differs from the parent's; sharing this would
#                      reintroduce the parent's.
#   plugins/, agents/  roster and plugin state that ocx REWRITES in the plane it owns. This is
#                      the original reason the config dir is isolated at all.
#   statsig/, cache/   install-scoped identity and model cache.
CLAUDE_SHARED_SESSION_ENTRIES="history.jsonl projects todos shell-snapshots file-history"

# Keys copied into the constructed settings.json. Exactly one stanza. `env` is not here and
# must never be: it is the credential carrier.
CLAUDE_INHERITED_SETTINGS_KEYS="statusLine"

# Link each shared entry from the isolated dir at the global install's copy.
#
# CONCURRENCY (the load-bearing conclusion, verified against the installed CLI 2.1.224 rather
# than assumed). Claude Code appends prompt history under a proper-lockfile mutex: the save
# path calls its lock with {stale:1e4, retries:{retries:3,minTimeout:50}} and distinguishes
# `history_save_lock_failed` from `history_save_write_failed`. The bundled proper-lockfile
# defaults `realpath:!0` and canonicalizes the target with fs.realpath BEFORE deriving the
# lock path as `${resolved}.lock`. So both planes -- one opening the real path, one opening a
# symlink to it -- resolve to the SAME lock directory and serialize against each other. Two
# concurrent appends do not interleave or truncate; the loser retries, and a lock held past
# the 10s stale threshold is broken rather than deadlocking. That is why SYMLINKS are chosen
# over copies: a copy would need a merge-back that has no such mutex, and would diverge or
# clobber the operator's real history the moment both planes ran. Verified empirically: an
# append through the symlink lands in the global file, leaves the link intact, and a second
# acquirer of the same lock directory gets EEXIST.
#
# What is NOT claimed: history is append-and-lock, so it is safe; projects/ transcripts are
# per-session files under distinct session IDs, so two planes do not contend for one file.
# This is not a claim that every future store Claude Code adds under these names is
# concurrency-safe -- a new store lands OUTSIDE the allowlist and stays unshared by default.
#
# FAIL-SOFT BY DESIGN. Inheritance is a convenience, never a gate. Any entry that cannot be
# linked is skipped with a named reason and the launch continues against a private copy: an
# unwritable link, a global entry that is itself a symlink, or -- the case that actually
# occurs -- an isolated entry that already holds REAL data. This launcher never deletes or
# overwrites existing plane data to make room for a link (the ocx plane already held 102MB of
# projects/ on this host), so a pre-existing real entry keeps its data and simply stays
# private. Only a link this function itself created is re-pointed.
#
# THE DEFECT IN HOW THAT WAS REPORTED (2026-08-07, found by reading the launch transcript on the
# operator's own host rather than the code). Every entry in the shared set already held real data
# from launches that predate this feature -- history.jsonl, projects/, shell-snapshots/, and
# file-history/ were all present and all dated earlier. So the feature the operator asked for was
# a permanent no-op for them, and the old wording, "not shared (isolated copy already has its own
# data)", read as a benign note about an implementation detail rather than as "inheritance is OFF
# and will stay off". Refusing to clobber their data is still right; reporting that refusal as
# though nothing were wrong was not. The message now says inheritance is OFF, and names the
# explicit, reviewable migration that turns it on -- see adopt_session_state.
link_shared_session_state() {
  local isolated="$1" global="$2" entry source target
  local attempted=0 blocked=0
  [ -d "$global" ] || return 0
  for entry in $CLAUDE_SHARED_SESSION_ENTRIES; do
    source="$global/$entry"
    target="$isolated/$entry"
    # Only share what the global install actually has. A missing entry is not created: an
    # empty file or dir invented here would be indistinguishable from real emptiness.
    [ -e "$source" ] || [ -L "$source" ] || continue
    attempted=$((attempted + 1))
    # A global entry that is itself a link is not followed. It could point anywhere, including
    # at a credential store, and this function must not launder that indirection.
    [ -L "$source" ] && { printf '  session   : %s not shared (global entry is a link)\n' "$entry"; continue; }
    if [ -L "$target" ]; then
      # Already ours. Re-point it, so an edited allowlist or a moved HOME takes effect.
      [ "$(readlink "$target" 2>/dev/null || true)" = "$source" ] && continue
      ln -sfn "$source" "$target" 2>/dev/null \
        || { blocked=$((blocked + 1)); printf '  session   : %s not shared (could not update link)\n' "$entry"; }
      continue
    fi
    if [ -e "$target" ]; then
      blocked=$((blocked + 1))
      printf '  session   : %s NOT INHERITED -- this plane has its own pre-existing data\n' "$entry"
      continue
    fi
    ln -s "$source" "$target" 2>/dev/null \
      || { blocked=$((blocked + 1)); printf '  session   : %s not shared (could not create link)\n' "$entry"; }
  done
  [ "$blocked" -gt 0 ] || return 0
  printf '  session   : inheritance is OFF for %s of %s inheritable entries. Not a benign note:\n' \
    "$blocked" "$attempted"
  printf '              those entries stay plane-private every launch until the plane data is\n'
  if [ -n "${session_remedy_command:-}" ]; then
    printf '              migrated aside. Nothing here was changed. To see and fix it:\n'
    printf '                %s status\n' "$session_remedy_command"
    printf '                %s adopt            (prints exactly what it would move)\n' "$session_remedy_command"
    printf '                %s adopt --migrate  (moves it to a timestamped backup, then links)\n' "$session_remedy_command"
    printf '              A migration never deletes anything.\n'
  else
    # Named by the sourcing launcher, because only it knows which plane and which
    # operator-facing command reaches this state. Unset means this launcher has no migrate
    # route, and saying so is better than naming a command that does not exist for its plane.
    printf '              migrated aside. This launcher has no migrate route; the data is untouched.\n'
  fi
}

# --- inheritance state: reporting, and the explicit migration that turns it on ---------------
#
# Classify ONE entry of the shared set without changing anything. One word on stdout:
#   shared        the isolated entry is our link at the global copy -- inheritance is ON
#   plane-data    the isolated entry holds its own data -- inheritance is OFF for it
#   other-link    the isolated entry is a link somewhere else; the next launch re-points it
#   linkable      nothing blocks a link; the next launch creates it
#   no-global     the global install has no such entry, so there is nothing to inherit
#   global-link   the global entry is itself a link, which is never followed
#
# Read-only by construction: it runs no ln, no mv, and no mkdir. A status route and the migration
# planner share it, so what the report says and what the migration does cannot disagree.
session_entry_state() {
  local isolated="$1" global="$2" entry="$3" source target
  source="$global/$entry"
  target="$isolated/$entry"
  if [ -L "$source" ]; then printf 'global-link'; return 0; fi
  if [ ! -e "$source" ]; then printf 'no-global'; return 0; fi
  if [ -L "$target" ]; then
    if [ "$(readlink "$target" 2>/dev/null || true)" = "$source" ]; then printf 'shared'; else printf 'other-link'; fi
    return 0
  fi
  [ -e "$target" ] && { printf 'plane-data'; return 0; }
  printf 'linkable'
}

# Per-entry inheritance report, plus the one-line count a launcher's `status` route surfaces.
# Read-only. Prints the count FIRST so it is visible without reading the table, because the
# defect this fixes was precisely a true statement that nobody registered as important.
report_session_inheritance() {
  local isolated="$1" global="$2" entry state shared=0 inheritable=0 blocked=0
  for entry in $CLAUDE_SHARED_SESSION_ENTRIES; do
    state="$(session_entry_state "$isolated" "$global" "$entry")"
    case "$state" in
      shared) shared=$((shared + 1)); inheritable=$((inheritable + 1)) ;;
      plane-data) blocked=$((blocked + 1)); inheritable=$((inheritable + 1)) ;;
      linkable|other-link) inheritable=$((inheritable + 1)) ;;
    esac
  done
  printf '  session inheritance: %s of %s inheritable entries shared\n' "$shared" "$inheritable"
  if [ ! -d "$global" ]; then
    printf '  (the global install has no config dir at %s; nothing is inheritable)\n' "$global"
    return 0
  fi
  for entry in $CLAUDE_SHARED_SESSION_ENTRIES; do
    state="$(session_entry_state "$isolated" "$global" "$entry")"
    case "$state" in
      shared)      printf '  %-16s SHARED (linked at the global copy)\n' "$entry" ;;
      plane-data)  printf '  %-16s NOT INHERITED -- this plane has its own data\n' "$entry" ;;
      other-link)  printf '  %-16s LINKED ELSEWHERE (the next launch re-points it)\n' "$entry" ;;
      linkable)    printf '  %-16s absent here; the next launch links it\n' "$entry" ;;
      no-global)   printf '  %-16s nothing to inherit (the global install has no such entry)\n' "$entry" ;;
      global-link) printf '  %-16s REFUSED (the global entry is a link; never followed)\n' "$entry" ;;
    esac
  done
  [ "$blocked" -gt 0 ] || return 0
  printf '\n  %s entries are NOT INHERITED. That state is permanent until migrated: a launch never\n' "$blocked"
  printf '  moves, deletes, or overwrites plane data to make room for a link.\n'
  if [ -n "${session_remedy_command:-}" ]; then
    printf '  Preview the migration : %s adopt\n' "$session_remedy_command"
    printf '  Perform it            : %s adopt --migrate\n' "$session_remedy_command"
  fi
}

# Turn inheritance ON for entries whose plane copy currently blocks it, by moving that copy to a
# timestamped backup INSIDE the plane and then linking to the global one.
#
# WHY THIS IS A SEPARATE, FLAGGED OPERATION AND NEVER PART OF A LAUNCH. The tension here is real
# and both horns are bad: silently never inheriting is not the feature the operator asked for,
# and silently clobbering their plane data to deliver it would destroy data they never offered.
# So the launch keeps refusing, and the remedy is an operation the operator names explicitly,
# after reading exactly which paths move where. Three properties make that safe to run:
#   * NOTHING IS EVER DELETED. The plane copy is MOVED (mv, same filesystem, so the data is
#     never rewritten) into <plane>/pre-inheritance-backup-<UTC stamp>/. A wrong call is undone
#     by moving it back, which is why no verification flag or --force exists.
#   * A BARE CALL MOVES NOTHING. Without --migrate it prints the exact plan and stops, so the
#     destructive-looking word in the transcript is always preceded by a reviewable list.
#   * A MISSING GLOBAL SOURCE IS A REFUSAL, not a skip. Moving the plane's only copy aside when
#     there is nothing to link to would hide the operator's data to deliver nothing.
# The consequence that must be stated rather than discovered: after a migration the launched
# session shows the GLOBAL history and projects, so the plane's own past prompts stop appearing
# in it. They are still on disk, in the backup, and the path is printed.
adopt_session_state() {
  local isolated="$1" global="$2" migrate="$3"
  shift 3
  local entry state selected wanted source target stamp backup
  local planned=0 moved=0 refused=0 failed=0
  if [ ! -d "$isolated" ]; then
    printf 'error: this plane has no config dir yet: %s\n' "$isolated" >&2
    printf 'Launch once first; there is no plane data to migrate and nothing to report.\n' >&2
    return 1
  fi
  if [ ! -d "$global" ]; then
    printf 'REFUSED: the global install has no config dir at %s\n' "$global" >&2
    printf 'There is nothing to inherit FROM, so moving this plane data aside would only hide it.\n' >&2
    return 3
  fi
  stamp="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || printf 'undated')"
  backup="$isolated/pre-inheritance-backup-$stamp"
  for entry in $CLAUDE_SHARED_SESSION_ENTRIES; do
    if [ "$#" -gt 0 ]; then
      wanted=false
      for selected in "$@"; do [ "$selected" = "$entry" ] && wanted=true; done
      $wanted || continue
    fi
    source="$global/$entry"
    target="$isolated/$entry"
    state="$(session_entry_state "$isolated" "$global" "$entry")"
    case "$state" in
      shared)
        printf '  %-16s already shared; nothing to do\n' "$entry"
        continue
        ;;
      no-global)
        # A refusal only when the operator NAMED this entry. Asking to migrate an entry that has
        # no global counterpart is a request this cannot honestly satisfy; sweeping the whole set
        # and finding one absent is just an absence.
        if [ "$#" -gt 0 ]; then
          refused=$((refused + 1))
          printf '  %-16s REFUSED: the global install has no %s to link to; nothing moved\n' "$entry" "$entry" >&2
        else
          printf '  %-16s nothing to inherit (the global install has no such entry)\n' "$entry"
        fi
        continue
        ;;
      global-link)
        refused=$((refused + 1))
        printf '  %-16s REFUSED: the global entry is a link and is never followed; nothing moved\n' "$entry" >&2
        continue
        ;;
      linkable|other-link)
        # No data to move: the link itself is the whole operation.
        if [ "$migrate" = true ]; then
          if ln -sfn "$source" "$target" 2>/dev/null; then
            moved=$((moved + 1))
            printf '  %-16s LINKED -> %s (nothing to move)\n' "$entry" "$source"
          else
            failed=$((failed + 1))
            printf '  %-16s FAILED to link -> %s\n' "$entry" "$source" >&2
          fi
        else
          planned=$((planned + 1))
          printf '  %-16s would LINK -> %s (nothing to move)\n' "$entry" "$source"
        fi
        continue
        ;;
      plane-data) ;;
    esac
    if [ "$migrate" != true ]; then
      planned=$((planned + 1))
      printf '  %-16s would MOVE %s\n' "$entry" "$target"
      printf '  %-16s        to %s/%s   (%s)\n' "" "$backup" "$entry" "$(entry_size "$target")"
      printf '  %-16s   then LINK -> %s\n' "" "$source"
      continue
    fi
    mkdir -p "$backup" 2>/dev/null || {
      failed=$((failed + 1))
      printf '  %-16s FAILED: could not create the backup directory %s\n' "$entry" "$backup" >&2
      continue
    }
    # mv FIRST and check it, then link. A link created before a failed move would point the plane
    # at the global copy while its own data still sat in the way, which is the one intermediate
    # state that could look like a successful migration and be a loss.
    if ! mv -n "$target" "$backup/$entry" 2>/dev/null || [ -e "$target" ] || [ -L "$target" ]; then
      failed=$((failed + 1))
      printf '  %-16s FAILED: could not move %s aside; nothing was linked\n' "$entry" "$target" >&2
      continue
    fi
    if ln -s "$source" "$target" 2>/dev/null; then
      moved=$((moved + 1))
      printf '  %-16s MOVED to %s/%s, then LINKED -> %s\n' "$entry" "$backup" "$entry" "$source"
    else
      failed=$((failed + 1))
      printf '  %-16s moved to %s/%s but the LINK FAILED; move it back to restore\n' "$entry" "$backup" "$entry" >&2
    fi
  done
  if [ "$migrate" != true ]; then
    if [ "$planned" -eq 0 ]; then
      printf '\nnothing to migrate: no entry is blocked by this plane having its own data.\n'
    else
      printf '\nNOTHING WAS MOVED. This was a plan. Re-run with --migrate to perform exactly the\n'
      printf 'moves above; the backup directory is created only then, and nothing is ever deleted.\n'
    fi
  elif [ "$moved" -gt 0 ]; then
    printf '\nmigrated %s entries. The launched session now shows the GLOBAL history and projects,\n' "$moved"
    printf 'so this plane'"'"'s own past prompts no longer appear in it. They are not gone:\n'
    printf '  %s\n' "$backup"
    printf 'Move an entry back out of there to undo this.\n'
  fi
  [ "$failed" -eq 0 ] || return 1
  [ "$refused" -eq 0 ] || return 3
  return 0
}

# Human-readable size of an entry, for the migration plan. Best-effort: an unavailable or failing
# `du` degrades the plan to "size unknown" and never blocks it, because the size is a courtesy
# and the PATHS are the load-bearing part of the plan.
entry_size() {
  local path="$1" size=""
  command -v du >/dev/null 2>&1 && size="$(du -sh "$path" 2>/dev/null | cut -f1 || true)"
  printf '%s' "${size:-size unknown}"
}

# True when a JSON blob carries anything credential-shaped. Applied to the CONSTRUCTED
# settings document as a post-condition, so the allowlist is proven to have held rather than
# trusted to have held. Matching is on KEY NAMES and never prints a value.
#
# Deliberately broad: any `env` block at all, plus any key containing token/key/secret/
# password/credential/auth, plus any AWS_*. `apiKeyHelper` and `awsAuthRefresh` are named
# because they are settings.json keys that name a credential-producing command.
settings_document_has_credential_shape() {
  local document="$1"
  printf '%s' "$document" | grep -qiE '"(env|apiKeyHelper|awsAuthRefresh|awsCredentialExport)"[[:space:]]*:' && return 0
  printf '%s' "$document" | grep -qiE '"[A-Za-z0-9_.-]*(token|secret|password|credential|bearer|apikey|api_key)[A-Za-z0-9_.-]*"[[:space:]]*:' && return 0
  printf '%s' "$document" | grep -qE '"(AWS|ANTHROPIC)_[A-Za-z0-9_]*"[[:space:]]*:' && return 0
  printf '%s' "$document" | grep -qiE '"[A-Za-z0-9_.-]*_key"[[:space:]]*:' && return 0
  return 1
}

# Build the isolated settings.json from the allowlist and write it.
#
# Requires python3 for a real JSON parse. A regex lift of a nested stanza out of a 60-key
# document would be a guess, and a wrong guess here writes the wrong keys into a file that is
# supposed to be the credential boundary. No python3 means no inheritance, not a partial one.
#
# The child's OWN keys are preserved: Claude Code writes theme and model into this file itself
# (verified: the ocx plane's settings.json holds {"theme","model"} it chose), so a blind
# overwrite would discard in-plane choices every launch. Inherited keys are merged OVER the
# existing document, and any key the launcher previously inherited but the global no longer
# declares is dropped, so removing a global statusLine removes it from the plane too.
write_inherited_settings() {
  local isolated="$1" global_settings="$2" document status=0
  command -v python3 >/dev/null 2>&1 || {
    printf '  settings  : not constructed (python3 unavailable; no statusline inherited)\n'
    return 0
  }
  document="$(CLAUDE_ISOLATED_DIR="$isolated" CLAUDE_GLOBAL_SETTINGS="$global_settings" \
    CLAUDE_INHERITED_KEYS="$CLAUDE_INHERITED_SETTINGS_KEYS" python3 -c '
import json, os, sys

isolated = os.path.join(os.environ["CLAUDE_ISOLATED_DIR"], "settings.json")
allowed = os.environ["CLAUDE_INHERITED_KEYS"].split()
marker = "_agenticSdlcInherited"


def load(path, *, reject_link):
    # A settings file that is a link is not read. On the global side it could point at
    # anything; on the isolated side a link is not a document this plane owns.
    if reject_link and os.path.islink(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


source = load(os.environ["CLAUDE_GLOBAL_SETTINGS"], reject_link=True) or {}
target = load(isolated, reject_link=True) or {}

# Drop what a previous run inherited, so a key removed globally is removed here. Recorded as
# a list of names only -- never the values, which would re-persist an inherited value even
# after the global file stopped declaring it.
for name in target.pop(marker, []) if isinstance(target.get(marker), list) else []:
    if name in allowed:
        target.pop(name, None)

inherited = []
for key in allowed:
    value = source.get(key)
    if value is None:
        continue
    # statusLine is only meaningful as an object. Anything else is malformed upstream and is
    # skipped rather than propagated into a document this launcher vouches for.
    if key == "statusLine" and not isinstance(value, dict):
        continue
    target[key] = value
    inherited.append(key)

if inherited:
    target[marker] = inherited
json.dump(target, sys.stdout, indent=2, sort_keys=True)
' 2>/dev/null)" || status=$?

  if [ "$status" -ne 0 ] || [ -z "$document" ]; then
    printf '  settings  : not constructed (global settings unreadable or unparseable)\n'
    return 0
  fi
  # POST-CONDITION, checked before the write and never after. If the constructed document is
  # credential-shaped at all, nothing is written: an unwritten settings.json costs a statusline,
  # while a written one that smuggled a credential is the failure this whole file exists to
  # prevent. Refusing here rather than in the allowlist means a future allowlist edit that
  # admitted `env` would fail loudly instead of silently shipping the token.
  if settings_document_has_credential_shape "$document"; then
    printf '  settings  : REFUSED to write -- the constructed document is credential-shaped\n' >&2
    printf '              (nothing was written; the launch continues without an inherited statusline)\n' >&2
    return 0
  fi
  local settings_path="$isolated/settings.json"
  [ -L "$settings_path" ] && {
    printf '  settings  : not constructed (isolated settings.json is a link)\n'
    return 0
  }
  local temporary
  temporary="$(mktemp "$isolated/.settings.json.XXXXXX")" || {
    printf '  settings  : not constructed (could not create a temporary file)\n'
    return 0
  }
  printf '%s\n' "$document" > "$temporary" \
    && chmod 600 "$temporary" 2>/dev/null \
    && mv -f "$temporary" "$settings_path" 2>/dev/null \
    || { rm -f "$temporary"; printf '  settings  : not constructed (write failed)\n'; return 0; }
  if printf '%s' "$document" | grep -q '"statusLine"'; then
    printf '  settings  : constructed; statusLine inherited from the global install\n'
  else
    printf '  settings  : constructed; the global install declares no statusLine (none inherited)\n'
  fi
}

# One call for a launcher to make. The global config dir is derived from HOME rather than from
# CLAUDE_CONFIG_DIR, which by this point already names the ISOLATED dir.
inherit_session_state() {
  local isolated="$1" global="${2:-$HOME/.claude}"
  link_shared_session_state "$isolated" "$global"
  write_inherited_settings "$isolated" "$global/settings.json"
}

# --- environment-variable policy -----------------------------------------------------------
#
# The settings.json allowlist above is only half the boundary. Claude Code's precedence is
# CLI flags > SHELL ENVIRONMENT > settings.json env > dedicated settings keys > defaults
# (code.claude.com/docs/en/settings.md), so a variable kept out of the constructed document
# can still arrive from the parent process environment. Both paths must be closed.
#
# THE DEFECT THIS REPLACES, found by running the launcher under a planted parent environment:
# the old scrub matched `^(ANTHROPIC|CLAUDE)` only, so `AWS_BEARER_TOKEN_BEDROCK=<value>`
# exported in the operator's shell reached the child intact — a live Bedrock credential in the
# gateway plane, which is exactly what ADR-0003 and ADR-0010 forbid. The same prefix rule was
# simultaneously too COARSE at the other end: it deleted `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
# and would delete `DISABLE_*`-style preferences if they were prefixed, discarding the
# operator's deliberate privacy and behavior choices.
#
# THE DESIGN TENSION, and how it is resolved. A prefix rule broad enough to catch every model
# pin (`ANTHROPIC_DEFAULT_*_MODEL`, `*_NAME`, `*_DESCRIPTION`, `*_SUPPORTED_CAPABILITIES`,
# `ANTHROPIC_CUSTOM_MODEL_OPTION*` — about twenty names) would also swallow inert `CLAUDE_*`
# preferences. The two namespaces are resolved by OPPOSITE rules, because their contents differ:
#
#   ANTHROPIC_* and AWS_*  -> DENY BY PREFIX, no exceptions. Every documented variable in these
#                             namespaces is a credential, a destination, a workspace/project
#                             identifier, or a model pin. None is an inert preference, so a
#                             prefix rule loses nothing and a new upstream name is denied by
#                             default rather than by having been predicted.
#   CLAUDE_*               -> DENY BY DEFAULT, ALLOW BY NAME. This namespace genuinely mixes
#                             routing/auth flags (CLAUDE_CODE_USE_BEDROCK, the client-cert
#                             trio) with inert preferences (accessibility, compaction, bash
#                             limits). Only an enumeration is honest here, so an unrecognized
#                             new CLAUDE_* variable is dropped rather than guessed at.
#   unprefixed             -> DENY BY NAME, plus one CLOSED CREDENTIAL-NAME GRAMMAR. The named
#                             hazards below are removed, and so is any name whose whole final word
#                             is one of the ten credential endings in
#                             CLAUDE_CREDENTIAL_NAME_ENDINGS (ADR-0010 Amendment A.2): a
#                             credential does not become inert by being spelled outside a
#                             namespace this policy enumerates. Still a NAME policy and never a
#                             value scanner. `DISABLE_*`/`DO_NOT_TRACK`/`BASH_*` are already
#                             untouched by any scrub and stay that way.
#
# Doc references for the classification:
#   code.claude.com/docs/en/env-vars.md       (the variable inventory and set-to-activate rule)
#   code.claude.com/docs/en/settings.md      (precedence, and the env block read once at startup)
#   code.claude.com/docs/en/network-config.md (proxy and client-certificate variables)

# Inert CLAUDE_* preferences preserved across the scrub. Each is the operator's deliberate
# choice and dropping it is a silent regression, most sharply for the privacy flags: Claude Code
# treats these as SET-TO-ACTIVATE (any non-empty value enables, unset/empty disables), so
# turning a set DISABLE_TELEMETRY into an unset one RE-ENABLES telemetry in the launched plane.
# That is a privacy regression the operator never asked for, which is why preservation is
# implemented as capture-then-restore rather than left to chance.
#
# EVERY ENTRY CARRIES ITS OWN REASON, on its own line, because the failure mode of allow-by-name
# is allowing too MUCH: one careless future entry re-opens the boundary that the exported
# AWS_BEARER_TOKEN_BEDROCK finding closed. The admission test each entry passes is about the
# NAME, never about the value the operator happens to have set: a name is admissible only if its
# whole value space is a boolean, a number, or a display/path preference — never a credential, a
# destination, an identity, or a model pin, which are Amendment A's four denied classes. The
# operator's shell supplies the value, so "this variable usually holds something harmless" is not
# an argument. `assert_env_allowlist_is_admissible` re-checks this list mechanically on every
# scrub, so an inadmissible edit refuses the launch instead of shipping.
#
# An ARRAY, not a whitespace-separated string: an array element is never re-split or re-parsed,
# and bash cannot export an array, so this policy state is structurally incapable of reaching the
# child process it governs.
#
# Deliberately NOT here: CLAUDE_CODE_REMOTE, CLAUDE_CODE_ACCOUNT_UUID, and
# CLAUDE_CODE_MESSAGING_SOCKET are owned by Claude Code and always ignored from an env block,
# so forwarding them would be theater. CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY and
# CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST are omitted because `ocx claude` sets both itself with
# "user wins" semantics; inheriting a stale value would override the gateway's own choice.
CLAUDE_INHERITED_ENV_VARS=(
  # Boolean feature flag. The name Amendment A records as WRONGLY deleted by the old prefix
  # scrub: it selects an in-process feature and names no provider, route, or account.
  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
  # A token count. A number cannot name a destination or authenticate anything, and compaction
  # is local bookkeeping over the transcript this plane already owns.
  CLAUDE_CODE_AUTO_COMPACT_WINDOW
  # A 1-100 percentage (ADR-0012). One-directional, so a hostile value compacts EARLIER at worst
  # and can neither raise a limit nor reach the network.
  CLAUDE_AUTOCOMPACT_PCT_OVERRIDE
  # Set-to-activate boolean over context width only. It narrows what this session asks for; it
  # cannot select a provider or a model.
  CLAUDE_CODE_DISABLE_1M_CONTEXT
  # Set-to-activate PRIVACY boolean, and the one Amendment A names outright. Dropping a SET flag
  # re-enables the nonessential traffic, so the deny-only scrub was itself the regression.
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
  # Boolean over how the Bash tool treats the working directory. A tool-behavior choice inside a
  # session that already runs the operator's own commands; it carries no secret and no route.
  CLAUDE_CODE_BASH_MAINTAIN_PROJECT_WORKING_DIR
  # Boolean over whether long tasks background themselves. Scheduling, not authorization.
  CLAUDE_CODE_AUTO_BACKGROUND_TASKS
  # Milliseconds bounding an in-process async-agent stall. Distinct from the DENIED API_TIMEOUT_MS,
  # which bounds an HTTP request to an endpoint this plane replaces: a stall watchdog cannot be
  # "tuned for the wrong endpoint" because it never describes one.
  CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS
  # Accessibility boolean. Dropping it degrades the session for the operator who needs it most,
  # and its value space is a flag.
  CLAUDE_CODE_ACCESSIBILITY
  # Screen-reader output mode boolean. Same class, same reason.
  CLAUDE_CODE_AX_SCREEN_READER
  # Terminal repaint boolean: rendering only.
  CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT
  # Terminal color boolean: rendering only.
  CLAUDE_CODE_TMUX_TRUECOLOR
  # Boolean over whether an artifact opens automatically: local UI behavior.
  CLAUDE_CODE_ARTIFACT_AUTO_OPEN
  # Boolean exposing the effort control in the UI. It surfaces a control; it pins no model.
  CLAUDE_CODE_ALWAYS_ENABLE_EFFORT
  # Whether additional directories' CLAUDE.md files are read. The widest value space on this list
  # — a filesystem path list rather than a flag — and admissible because a path is not a secret
  # and the paths are the operator's own instruction files, which this plane already reads from
  # the same operator's tree. It selects no provider and carries no credential.
  CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD
)

# Unprefixed hazards removed by name. Neither is a credential in the ordinary sense, and both
# are worse than one in effect:
#   NODE_TLS_REJECT_UNAUTHORIZED      disables TLS verification process-wide.
#   FALLBACK_FOR_ALL_PRIMARY_MODELS   forces silent model substitution. In a plane whose catalog
#                                     is restricted, a substitution is precisely the
#                                     unattributable-response failure the gateway canary's C1
#                                     finding is about, so it must never be inherited.
# API_TIMEOUT_MS and the stream-watchdog family are deliberately NOT inherited either: they are
# inert, but a timeout tuned for a direct Anthropic endpoint is the wrong number for a loopback
# gateway, and a wrong timeout reads as a hung model rather than as a misconfiguration.
CLAUDE_DENIED_ENV_VARS=(
  NODE_TLS_REJECT_UNAUTHORIZED
  FALLBACK_FOR_ALL_PRIMARY_MODELS
  API_TIMEOUT_MS
)

# Unprefixed CREDENTIAL-SHAPED NAMES, denied by a closed grammar (ADR-0010 Amendment A.2).
#
# THE DEFECT THIS CLOSES, measured against the shipped launcher rather than reasoned about: with
# only the three enumerated hazards above, an exported `MODEL_API_KEY` reached the child VERBATIM,
# beside the `ANTHROPIC_AUTH_TOKEN` that carried the SAME value and that the prefix sweep did
# remove. `MODEL_API_KEY` is not hypothetical here -- it is this launcher's own documented
# credential input -- so the boundary was closed for the namespaced spelling of a secret and open
# for the unnamespaced one.
#
# STILL A NAME POLICY. That is Amendment A's load-bearing constraint and this grammar does not
# relax it: no value is read, scanned, matched, or classified anywhere below. A value scanner is
# the wrong instrument in both directions -- it misses a low-entropy secret and deletes a
# high-entropy preference -- so what is denied is a NAME whose final word declares that its value
# space is a credential.
#
# CLOSED, and closed deliberately: exactly the ten endings below, each an exact upper-case word,
# matched only as the WHOLE final word of the name (`(^|_)WORD$`). So `MODEL_API_KEY`,
# `MODEL_APIKEY`, and a bare `API_KEY` all go, while `MODEL_API_TIMEOUT`, `MODEL_API_KEYS`, and
# `MONKEY` all stay: a name that merely CONTAINS a credential word is not swept, because
# `*KEY*`-style containment is how a deny grammar starts eating the operator's inert preferences.
# `credential_shaped_env_name_ere` refuses a non-word entry -- a glob, a digit, an alternation, a
# leading or trailing underscore -- rather than expanding it, so this list cannot quietly widen
# into a pattern rule, exactly as the allowlist cannot quietly widen into a prefix rule.
#
# WHY THE ALLOWLIST NEEDS NO EXCEPTION HERE, and why that is tested rather than asserted: every
# ending below is already refused from the allowlist by `assert_env_allowlist_is_admissible`'s
# credential-shape patterns (`*KEY*`, `*TOKEN*`, `*SECRET*`, `*CREDENTIAL*`, `*PASSWORD*`), so no
# ADMISSIBLE allowlist entry can match this grammar -- the two halves are structurally incapable
# of disagreeing. The capture-then-restore is independent belt: it captures before every sweep and
# restores after, so an allowlisted preference survives whatever the sweeps do.
# `tests/test_muse_claude.py` proves both halves per ending instead of trusting this paragraph.
#
# WHAT THIS DOES NOT CLOSE, stated plainly because a name policy cannot: a secret the operator
# stores under a name this grammar does not describe -- `MY_THING`, `DEPLOY_PW`, or any allowlisted
# preference -- still crosses as that variable's value. That limit is documented, not solved.
CLAUDE_CREDENTIAL_NAME_ENDINGS=(
  API_KEY       # the measured reproduction: an exported MODEL_API_KEY reached the child verbatim
  APIKEY        # the same name unpunctuated, which a `*_KEY`-shaped rule does not reach
  AUTH_TOKEN    # a bearer/session token: the shape ANTHROPIC_AUTH_TOKEN wears inside its namespace
  ACCESS_TOKEN  # an OAuth access token
  TOKEN         # the bare word: GITHUB_TOKEN and CI_JOB_TOKEN reached the child verbatim under the
                # nine-ending grammar, because neither ends in AUTH_TOKEN or ACCESS_TOKEN
  SECRET        # a whole-word SECRET names its own value space
  SECRET_KEY    # the two-word form, which `(^|_)SECRET$` alone does not reach
  PASSWORD      # a password, however scoped
  CREDENTIALS   # a credential bundle, e.g. a serialized service-account document
  PRIVATE_KEY   # asymmetric private key material
)

# ONE grammar, TWO consumers: the sweep in `scrub_and_restore_claude_env` and the classification in
# `report_env_policy` both read this ERE. A second hand-maintained copy of the word list is how a
# status route ends up promising that a variable survives a scrub that removes it.
#
# It REFUSES -- nonzero, with no output -- rather than degrading. A missing, empty, or non-word list
# would either sweep nothing or expand into a pattern, and both are silent failures in the dangerous
# direction; callers turn the refusal into a named REFUSED line and stop before anything is unset.
credential_shaped_env_name_ere() {
  declare -p CLAUDE_CREDENTIAL_NAME_ENDINGS >/dev/null 2>&1 || return 1
  [ "${#CLAUDE_CREDENTIAL_NAME_ENDINGS[@]}" -gt 0 ] || return 1
  local ending
  for ending in "${CLAUDE_CREDENTIAL_NAME_ENDINGS[@]}"; do
    # An exact upper-case word with no leading or trailing underscore. This is what forbids a glob,
    # an alternation, an anchor, or a digit from entering the grammar as though it were a word.
    case "$ending" in
      ""|*[!A-Z_]*|_*|*_) return 1 ;;
    esac
  done
  # `|`-joined by IFS, which is why every entry above must already be a bare word: the join is the
  # only place a stray metacharacter could become alternation the reviewer never wrote.
  local IFS='|'
  printf '(^|_)(%s)$\n' "${CLAUDE_CREDENTIAL_NAME_ENDINGS[*]}"
}

# The allowlist's own admission check, run before every scrub rather than trusted to review.
# Allow-by-name fails by allowing too much, and the two shapes that do it are a name whose value
# space can carry a credential/destination/identity/model pin, and a PATTERN that quietly becomes
# a prefix rule. Both are refused here, and a refusal stops the caller before anything is
# unset — a launcher that cannot trust its own policy must not prepare a plane.
assert_env_allowlist_is_admissible() {
  local name status=0
  for name in "$@"; do
    # An exact upper-case name and nothing else. This is what forbids a prefix-level allow:
    # `CLAUDE_*`, `CLAUDE_CODE_?`, and a stray `=` or space all fail here rather than being
    # expanded, matched, or split into something wider than one variable.
    case "$name" in
      *[!A-Z0-9_]*)
        printf 'REFUSED: %s is not an exact upper-case variable name; allow-by-name admits no pattern, prefix, or list\n' "$name" >&2
        status=1
        continue ;;
    esac
    case "$name" in
      CLAUDE_*) ;;
      *)
        printf 'REFUSED: %s is not CLAUDE_*-named; ANTHROPIC_* and AWS_* are denied by prefix with no exceptions\n' "$name" >&2
        status=1
        continue ;;
    esac
    case "$name" in
      *KEY*|*TOKEN*|*SECRET*|*CREDENTIAL*|*PASSWORD*|*PASSPHRASE*|*CERT*|*AUTH*)
        printf 'REFUSED: %s is credential-shaped and must never be allowed by name\n' "$name" >&2
        status=1 ;;
      *URL*|*BASE*|*ENDPOINT*|*PROXY*|*HOST*|*PORT*|CLAUDE_CODE_USE_*)
        printf 'REFUSED: %s could carry a destination or a provider switch; the launcher sets its own route\n' "$name" >&2
        status=1 ;;
      *MODEL*|*API_*)
        printf 'REFUSED: %s could pin a model or a provider API surface; this plane serves its own catalog\n' "$name" >&2
        status=1 ;;
      CLAUDE_CONFIG_DIR|*ACCOUNT*|*UUID*|*SESSION_ID*|*SOCKET*)
        printf 'REFUSED: %s could select a plane or carry session identity across the boundary\n' "$name" >&2
        status=1 ;;
    esac
  done
  [ "$status" -eq 0 ] \
    || printf 'REFUSED: the CLAUDE_* allowlist is inadmissible, so nothing was scrubbed and no plane was prepared\n' >&2
  return "$status"
}

# Replaces a bare `^(ANTHROPIC|CLAUDE)` prefix scrub. Capture-then-restore, because the inert
# CLAUDE_* preferences have to survive a scrub that must otherwise be broad.
#
# Callers must invoke this INSTEAD of their own scrub, and only after the subscription refusal
# has already fired: this function's job is to sanitize, never to decide admissibility.
scrub_and_restore_claude_env() {
  # A MISSING OR EMPTY POLICY LIST REFUSES rather than defaulting, and this is the first thing the
  # function does. Both silent failures are invisible in the output and opposite in effect: an
  # empty denylist launches a child that keeps the operator's hazards, and an empty allowlist
  # silently drops the privacy flag this policy exists to preserve. A `${list:-}` guard would have
  # produced exactly those two failures quietly.
  #
  # It can happen: the lists are themselves named CLAUDE_*, so the prefix sweep below unsets the
  # very lists it is iterating — which under `set -u` once aborted a launch with
  # `CLAUDE_DENIED_ENV_VARS: unbound variable` (caught by running the launcher, not by reading
  # it). They are copied to LOCALS first so the sweep cannot reach them mid-run, and a caller that
  # scrubs twice without re-sourcing this file gets this named refusal instead of a quiet no-op.
  declare -p CLAUDE_INHERITED_ENV_VARS >/dev/null 2>&1 \
    && declare -p CLAUDE_DENIED_ENV_VARS >/dev/null 2>&1 \
    || {
      printf 'REFUSED: the environment policy lists are not defined; re-source session-inheritance.sh before scrubbing\n' >&2
      return 1
    }
  local -a allowed=("${CLAUDE_INHERITED_ENV_VARS[@]}") denied=("${CLAUDE_DENIED_ENV_VARS[@]}")
  { [ "${#allowed[@]}" -gt 0 ] && [ "${#denied[@]}" -gt 0 ]; } \
    || {
      printf 'REFUSED: the environment policy is empty (allow=%s deny=%s); an empty allowlist drops the privacy flags and an empty denylist scrubs nothing\n' \
        "${#allowed[@]}" "${#denied[@]}" >&2
      return 1
    }
  assert_env_allowlist_is_admissible "${allowed[@]}" || return 1
  # Resolve the credential-name grammar into a LOCAL before any sweep, for the same reason the two
  # lists above are copied to locals: the array is CLAUDE_*-named, so the prefix sweep below would
  # unset the very grammar the credential sweep still needs. Refusing here also keeps the guarantee
  # that a refusal happens before anything is unset.
  local credential_ere
  credential_ere="$(credential_shaped_env_name_ere)" \
    || {
      printf 'REFUSED: the unprefixed credential-name grammar is missing, empty, or is not a closed list of exact upper-case words; nothing was scrubbed and no plane was prepared\n' >&2
      return 1
    }
  local -a kept_names=() kept_values=()
  local name value index=0
  # Capture the allowlisted values first; the sweep below cannot distinguish them.
  #
  # PARALLEL ARRAYS, never `name=value` lines. A captured value is the OPERATOR's, and a
  # line-parsed restore let a value containing a newline export a SECOND name of their choosing:
  # `CLAUDE_CODE_ACCESSIBILITY=$'1\nAWS_BEARER_TOKEN_BEDROCK=<token>'` put a Bedrock bearer token
  # in the child and truncated the real preference to `1`. That is the precise boundary failure
  # this whole policy exists to prevent, arriving through the half that is supposed to preserve
  # inert preferences. An array element is stored and restored verbatim and is never re-parsed, so
  # the restored NAME can only ever come from the literal list above.
  for name in "${allowed[@]}"; do
    value="${!name:-}"
    [ -n "$value" ] || continue
    kept_names+=("$name")
    kept_values+=("$value")
  done
  # ANTHROPIC_*, CLAUDE_*, and AWS_* all go. AWS_* is the half the previous rule missed, and it
  # is the half that carried the live Bedrock bearer token.
  for name in $(compgen -v | grep -E '^(ANTHROPIC|CLAUDE|AWS)' || true); do
    unset "$name" || true
  done
  for name in "${denied[@]}"; do
    unset "$name" || true
  done
  # Unprefixed credential-shaped NAMES (Amendment A.2). Placed after the enumerated hazards and
  # before the restore, which is what makes it harmless to the allow half: an allowlisted value was
  # captured above and is re-exported below, and no admissible allowlist entry can match this
  # grammar in the first place. It is also why this launcher's own `MODEL_API_KEY` input can be
  # swept safely -- `resolve_credential` already copied that value into a lowercase shell variable
  # before `prepare_child_environment` runs, and the route slot is exported after the scrub.
  for name in $(compgen -v | grep -E "$credential_ere" || true); do
    unset "$name" || true
  done
  # Restore the operator's inert preferences. Exported, not merely set, so the child receives
  # them; a preference the parent did not set stays unset rather than becoming an empty string,
  # which under set-to-activate semantics would be indistinguishable from disabled anyway.
  while [ "$index" -lt "${#kept_names[@]}" ]; do
    export "${kept_names[index]}=${kept_values[index]}"
    index=$((index + 1))
  done
  # Opinionated default (ADR-0012 amended 2026-08-08): 85% if the operator did not already
  # choose a percentage. The override is one-directional — a value above the (undocumented)
  # default is silently ignored — so shipping 85 is safe even before it is measured: if
  # 85 > default it is a no-op, if 85 < default it compacts earlier at ~0.85*272000≈231200.
  # An installer-exported value preserved above wins over this default via the
  # capture-then-restore, so the default is opinionated rather than mandatory. Exported so
  # the child receives it; a per-installer `export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=<1-100>`
  # before `ccodex launch` overrides it.
  if [ -z "${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-}" ]; then
    export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85
  fi
}

# Report the policy without applying it, for a launcher's status route. Prints the CLASS of each
# variable actually present in this environment, never a value.
report_env_policy() {
  local name shown=0
  declare -p CLAUDE_INHERITED_ENV_VARS >/dev/null 2>&1 \
    && declare -p CLAUDE_DENIED_ENV_VARS >/dev/null 2>&1 \
    || {
      printf '  (the environment policy lists are not defined; nothing was classified)\n' >&2
      return 1
    }
  local credential_ere
  credential_ere="$(credential_shaped_env_name_ere)" \
    || {
      printf '  (the unprefixed credential-name grammar is not a closed word list; nothing was classified)\n' >&2
      return 1
    }
  local -a denied=("${CLAUDE_DENIED_ENV_VARS[@]}")
  # One padded string, so an exact-name membership test is a single `case` rather than a nested
  # loop. Padded on BOTH sides and matched with its spaces attached: an unpadded search would let
  # CLAUDE_CODE_ACCESSIBILITY_EXTRA match CLAUDE_CODE_ACCESSIBILITY and report a denied name as
  # inherited, which is a false statement in the dangerous direction.
  local allowed=" ${CLAUDE_INHERITED_ENV_VARS[*]} "
  # ONE `compgen` pass over both the prefix rules and the credential grammar, rather than two
  # pipelines: a name that satisfies both (`ANTHROPIC_API_KEY` does; `AWS_SECRET_ACCESS_KEY` does
  # NOT, since ACCESS_KEY is not one of the ten endings) must be reported ONCE, and a name reported
  # twice is its own false statement about the shell.
  for name in $(compgen -v | grep -E "^(ANTHROPIC|CLAUDE|AWS)|$credential_ere" || true) "${denied[@]}"; do
    # This helper's own configuration is CLAUDE_*-named, so it shows up in the prefix sweep of
    # the very process doing the sweeping. It is launcher state, not operator environment, and
    # reporting it as "a denied variable you set" would be a false statement about the shell.
    case "$name" in CLAUDE_INHERITED_ENV_VARS|CLAUDE_DENIED_ENV_VARS|CLAUDE_CREDENTIAL_NAME_ENDINGS|CLAUDE_INHERITED_SETTINGS_KEYS|CLAUDE_SHARED_SESSION_ENTRIES) continue ;; esac
    [ -n "${!name:-}" ] || continue
    shown=1
    # The unprefixed credential class is classified from the SAME ERE the sweep uses, never from a
    # mirrored set of globs that could drift from it, and matched with bash's own `=~` rather than a
    # `grep` pipeline (under `pipefail`, a `grep -q` that exits on the first match can report the
    # writer's SIGPIPE as the pipeline's status, which would silently flip this classification).
    # Prefixed names fall through to their own more specific lines below, so this speaks only for
    # the class the prefix rules do not cover.
    case "$name" in
      ANTHROPIC_*|CLAUDE_*|AWS_*) ;;
      *)
        if [[ $name =~ $credential_ere ]]; then
          printf '  %-46s DENIED (credential-shaped unprefixed name; value never printed)\n' "$name"
          continue
        fi ;;
    esac
    case "$name" in
      AWS_*|*_TOKEN|*_API_KEY|*_KEY|*_SECRET|*CLIENT_CERT*|*PASSPHRASE*)
        printf '  %-46s DENIED (credential class; value never printed)\n' "$name" ;;
      ANTHROPIC_*BASE_URL|ANTHROPIC_*RESOURCE|CLAUDE_CODE_USE_*)
        printf '  %-46s DENIED (provider routing; the launcher sets its own destination)\n' "$name" ;;
      ANTHROPIC_*MODEL*|ANTHROPIC_CUSTOM_MODEL_OPTION*|FALLBACK_FOR_ALL_PRIMARY_MODELS)
        printf '  %-46s DENIED (model pin or forced fallback; this plane serves its own catalog)\n' "$name" ;;
      NODE_TLS_REJECT_UNAUTHORIZED)
        printf '  %-46s DENIED (TLS verification downgrade)\n' "$name" ;;
      API_TIMEOUT_MS)
        printf '  %-46s DENIED (tuned for a direct endpoint, wrong for a loopback gateway)\n' "$name" ;;
      *)
        case "$allowed" in
          *" $name "*) printf '  %-46s INHERITED (inert preference, allowed by name)\n' "$name" ;;
          *)           printf '  %-46s DENIED (unrecognized in the CLAUDE_* namespace)\n' "$name" ;;
        esac
        ;;
    esac
  done
  [ "$shown" -eq 1 ] \
    || printf '  (no ANTHROPIC_*/CLAUDE_*/AWS_* or credential-shaped variable is set in this environment)\n'
}
