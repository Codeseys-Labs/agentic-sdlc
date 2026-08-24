# Routing: lifecycle moments → skills

One table, three duties. It is the routing card any session-priming surface condenses; it is
the specification the twelve `skills/*/SKILL.md` descriptions each express — the same moments
and symptoms, row by row; and it is the reviewer's checklist when a skill is added, renamed,
or retired, because a row and a description drifting apart is silent rot. Rows are
host-agnostic: they name lifecycle moments and observable symptoms, never one host's
mechanics. Routing is retrieval, never authorization — no row's firing, no gate result, and
no reviewer label authorizes push, publication, PR mutation, merge, deployment, or any other
outward effect.

## The table

Each row reads: at this moment, or on observing this symptom, load that skill before
improvising.

| Skill | Fires at (lifecycle moment) | Fires on (symptom) |
|---|---|---|
| `agentic-sdlc` | intake of project-scale work; opening an SDLC-activated repository with open seeds; the frame → ship loop | a backlog that needs waves; multi-agent implementation being improvised ad hoc |
| `change-writing` | any commit/PR/squash message surface, including the message the agent itself is preparing; another skill needing message text | attribution slop in a draft: Co-Authored-By trailers, generated-by footers, badges |
| `adr-lifecycle` | the moment a hard-to-reverse choice is settled during framing, planning, review, or reconciling | the same choice re-argued across sessions; "why did we choose X" |
| `model-tier-rightsizing` | before ANY agent or workflow dispatch that names a model or effort; before a `RuntimeAssignment` is written | null output, semantic uncertainty, throttling, missing readback, or unresolved transport identity mid-run |
| `dispatching-exact-ocx-models` | the spawn boundary, after rightsizing has chosen an exact OCX route and before the worker starts | a generated `ocx-*` agent or namespaced provider ID whose post-run identity is unverified |
| `reviewing-overengineering` | before a plan is accepted or a diff merged when its size or abstraction budget is questioned; re-review of any remediated candidate | "simplify", "cut this down", line-count targets, or deadline pressure entering a review |
| `repo-toolchain-gates` | setting up or auditing a repository's gate stack; wiring pre-commit/pre-push hooks or CI; running waves in fresh git worktrees | local lint green but CI red; worktree `config not trusted`; workers skipping hooks; a missing secrets gate |
| `stacked-prs` | splitting dependent changes into separate, reviewable pull requests | a lower layer changed, merged, retargeted, or restacked while descendants stay open |
| `stacked-prs-gh-cli` | the same moments as `stacked-prs`, tooling constrained to plain `gh` and git | a child needing a base change; a branch being rewritten; incomplete governance/check evidence |
| `external-skill-libraries` | intake of any foreign skill library: install, update, remove, or check through its own front door | a skill name resolving twice or the wrong copy loading; weighing an always-on catalog cost |
| `cmux-event-bus-messaging` | only when cmux is already active and workers need pub/sub, replay, or >16 KiB payloads | idle-bus or lost-wakeup races inside cmux workspaces |
| `codex-research-os` | explicit request to scaffold or operate the research organization in a repository | none by design — an installer does not fire on ambient moments |

Two rows carry deliberate exceptions to the moment/symptom pattern, and both are
load-bearing. `cmux-event-bus-messaging` keeps its negative trigger — it never fires for
native host orchestration or completion signaling outside cmux — because native collaboration
requires no cmux setup. `codex-research-os` stays request-triggered because firing an
installer on an ambient moment would scaffold repositories nobody asked to scaffold.

Two rows are sequenced, not alternatives: `model-tier-rightsizing` chooses the tier and
certifies the exact route; `dispatching-exact-ocx-models` then injects that route at the
spawn boundary. A dispatch that reaches the second row without the first has skipped the
router.

## What this router never does

The table routes; it never overrides. Four practices are refused by name, and they bound
every future row as doctrine:

- **No sticky modes.** Routing is primed at a session boundary at most; nothing re-inserts a
  router nudge every turn or holds a session in a mode the host did not put it in.
- **No standing-order descriptions.** A description may name a broad moment ("any commit
  message surface" is a moment); it may never command global application ("must always
  apply") or claim priority over the host's own routing. The line is descriptive-when versus
  imperative-always.
- **No default self-insertion into delegation.** Roles here are dispatched only by a
  conductor with a resolved `RuntimeAssignment`; nothing rewrites the host's default
  subagent or wraps another skill's dispatch in this bundle's own.
- **No global-configuration capture.** No shipped surface writes the user's global
  instructions (CLAUDE.md or equivalent), global memory, or another tool's routing; a
  settings mutation is always a separately authorized, operation-specific step that owns
  only the exact entry it can later remove.

Stated once: this bundle occupies only surfaces a host designed to be additive for third
parties — the description inventory and explicitly authorized, individually owned
configuration entries. Surfaces the user owns as defaults are never written.
