# Design: first-party threat-modeling workflow (V52) — seed agentic-sdlc-910b

Design-only artifact, 2026-08-24. No repo edits. Sources read at HEAD (849bdb5):
`.seeds/issues.jsonl:195` (the seed),
`docs/plans/claude-code-first-harness/issues/25-define-threat-modeling-workflow.md` (the
resolved product spec this V1 lands the first slice of),
`skills/reviewing-overengineering/SKILL.md` (shape exemplar),
`skills/agentic-sdlc/references/skill-authoring.md` (four-gate + ≥2-of-5 tests),
`skills/agentic-sdlc/references/evidence-discipline.md` (five-class vocabulary),
`skills/agentic-sdlc/references/routing.md` (row form and router doctrine),
`skills/agentic-sdlc/references/mission-loop.md:25-26` (classification vocabulary),
`agents/claude/sdlc-critic.md:56-79` (seed-shaped finding + structured submission),
`workflows/sdlc-wave-scout.js` (workflow admission/refusal pattern), `AGENTS.md`
(named residuals), and the D4 verdict (seed `agentic-sdlc-0c38`'s closure record: the
rank-4 install-lifecycle shrink, ownership now byte identity, residuals named).

Verified this pass (`primary-artifact`): `grep -ri stride` over `skills/`, `agents/`,
`commands/`, `workflows/` returns zero matches — the seed's "grep zero at HEAD" still
holds, so nothing in Section 2's already-loaded audit owns this ground.

---

## 1. Form: a skill first; a Dynamic Workflow as a deferred optional accelerator

**Decision: ship `skills/sdlc-threat-model/` (SKILL.md + one reference) as the canonical,
host-agnostic surface. The Dynamic Workflow variant is specified here but deferred behind a
named promotion trigger; when built, the skill drives it optionally and never requires it.**
This is option (c) from the design question, with the workflow half explicitly *not* in V1.

### The already-loaded audit (skill-authoring §2)

Nearest incumbents, named per the mechanical check:

- `agents/*/sdlc-reviewer` and `sdlc-critic` carry a *security/secrets lens* over a diff or
  merged snapshot — code-level secure review. Plan issue 25 explicitly rejects generic
  secure code review as this capability's ground and routes it there. Not a duplicate.
- `skills/reviewing-overengineering/` carries the *safety-preservation rebuttal* — a
  defensive check that a proposed deletion doesn't remove a control. It fires on deletion
  pressure; it does not enumerate threats against a boundary that nobody proposed deleting.
  Complementary, and each description must name the other (Gate 1 counterexample rule).
- `docs/plans/.../issues/25` defines the full eventual product (typed DFD, ledgers, freshness
  axes, method profiles) but ships nothing; no skill, agent, command, or workflow expresses it.

Already covered by: **nothing**. That licenses Section 3 of skill-authoring.

### The four-gate admission test, applied explicitly

**Gate 1 — selection.** The description (drafted in §4 below, written before any body) lets a
selector pick this skill and reject both neighbors without reading the body: it fires on
*trust-boundary lifecycle moments* ("a trust boundary is created, moved, or deleted") and
names its counterexamples — generic secure code review belongs to reviewer/critic lenses,
complexity audit belongs to `reviewing-overengineering`. PASS.

**Gate 2 — proportionality.** The trigger is task-shaped and recurring but not per-session:
this repo alone changed authority boundaries repeatedly in the last month (ADR-0014 plane
removal, ADR-0020 jq pinning, the D4 install-lifecycle shrink, the Seeds launcher seam), and
each was a moment this skill would have fired. One description row against that firing rate
is proportionate; a `references/*.md` under `agentic-sdlc` would cost zero rows but would
never fire for the cross-repository case the plan issue requires ("a live cross-repository
use case"), and threat modeling is exactly the work a selector must be able to reach from a
symptom, not from already knowing the flagship skill's reference list. PASS.

**Gate 3 — trigger existence today.** Live now, not plausibly-later: the D4 verdict
(seed `agentic-sdlc-0c38`) closed the demolition rank-4 shrink with *named, accepted residual
windows* that have prose but no threat records behind them — the byte-identity ownership
weakening, the rename-aside `.old-*` interval, the pre-v4 state refusal — and AGENTS.md
states two more (the Seeds receipt's same-UID TOCTOU non-detection; the jq/mise substitution
residual under ADR-0020). Those are a ready-made first scoped subject sitting unowned at
HEAD. PASS.

**Gate 4 — always-on vs task-shaped.** A bounded run over one bound subject with a start, an
output artifact, and an end — a task, not a per-turn rule. Nothing here belongs in AGENTS.md
as standing doctrine except what AGENTS.md already says (evidence ≠ authorization). PASS.

### The ≥2-of-5 promotion test (needs 2; clears 4)

1. **Recurs** — across sessions and repositories: every authority-boundary change is a
   trigger, and the plan issue requires cross-repository use. YES.
2. **Needs specific sequencing** — bind-the-subject → per-letter lenses → classify →
   report-without-fixing, with author/challenger separation; a single paragraph inside the
   flagship skill cannot carry six lens definitions plus a finding contract. YES.
3. **Failures repeat** — the exact symptom the seed records: residual windows get named in
   prose (AGENTS.md, ADR closures, seed descriptions) and then nothing systematic ever
   enumerates what else sits in the same boundary; security review stays folded into a
   general reviewer lens and design-level threats are skipped. YES.
4. **Stable input/output contract** — input: one immutable scoped subject (digest-bound);
   output: one findings report of classified, evidence-graded, seed-shaped recommendations.
   A caller can name both without reading the bundle. YES.
5. **Benefits from explicit handoff** — findings route to conductor capture and a human-only
   disposition gate; a separate selection surface is what makes the challenger role
   selectable independently of the author. YES.

Write these into the landing change's admission-rationale section, exactly as
`reviewing-overengineering` does in its closing section.

### Why not a Dynamic Workflow as the primary form

- **Host-agnosticism is the admission floor.** Skills must serve Codex, Gemini CLI, and
  OpenCode via AGENTS.md routing; `workflows/` is a Claude-Code-only plane whose files are
  installed bytes that a separately authorized user-configuration step enables. A
  workflow-primary capability would be invisible to every other host and to any Claude host
  that never enables the overlay. Plan issue 25 also requires "no draw.io renderer, gateway,
  external provider, or third-party skill library" — the same minimal-prerequisite posture.
- **The fan-out it buys is real but not load-bearing.** Six STRIDE lenses parallelize
  nicely, but a *scoped* subject (one diff, one boundary) is deliberately small; sequential
  per-letter passes inside one session are acceptable at V1, and the flagship skill's
  ordinary subagent fan-out (one read-only lens agent per letter, conductor-dispatched with
  resolved `RuntimeAssignment`s) is already available to a conductor who wants concurrency
  today without any workflow file.
- **Workflow cost is nonzero and fails Gate 3 on its own.** Per the sdlc-wave-scout pattern
  the distributed bytes carry no model/effort pin, every stage refuses until the conductor
  supplies a resolved `RuntimeAssignment`, and the validator enforces first-line pairing,
  lowercase slug, module-free parseability, and no user paths. All buildable — but no live
  trigger *today* demands concurrent-lens automation. Defer it exactly as skill-authoring
  prescribes: written down with a named promotion trigger.

**Deferred workflow spec (build only when the trigger fires).** Trigger: a conductor
requests concurrent lenses on a bound subject, or a sequential run demonstrably exceeds the
session budget recorded at admission. Shape: `workflows/sdlc-threat-lenses.js`, first line
`// workflow: sdlc-threat-lenses`; `export const meta` as the first statement, pure literal;
stages `['bind', 'S','T','R','I','D','E', 'synthesize']` driven through `agent()`;
`ASSIGNMENTS = {}` in distributed bytes; a `requireResolvedAssignment(stage)` clone of the
scout's — distinguishing "not supplied" from "supplied but incomplete", JSON.stringify on
every interpolated value, refusal text ending "stop before dispatch and return one
SeedProposal". Read-only stages; the synthesize stage performs deterministic fan-in
preserving minority findings (plan issue 25's fan-in rule) and still emits only the report.
Installing the file never runs or enables it.

### Naming: `sdlc-threat-model`, a recorded deviation from issue 25's bare selector

Plan issue 25 (resolved) says "Ship `threat-modeling`". New evidence since that answer: a
foreign generic STRIDE skill named exactly `threat-modeling` is *observed installed on this
reference operator host right now* (`primary-artifact`: it appears in the live host's skill
inventory with a "Lightweight STRIDE-based threat modeling" description). Issue 25's own
lifecycle rule says exact-name overlap "preserves the foreign entry and skips only the
first-party projection" — so under the bare name, the first-party skill would silently fail
to load precisely on hosts whose operators already care about threat modeling. Name
collision is mechanical and silent (skill-authoring §4: first writer holds the name, the
loser simply is not the one that loads). Skill-authoring §4's naming rule for new
capabilities is a project-scoped prefix (`skills/sdlc-<capability>/`). **Recommend
`sdlc-threat-model`** and record the deviation in the landing change for human
ratification; if the bare name is ratified instead, the overlap-skip semantics stand and
the routing row must say so.

### Relation to issue 25's full workflow

Issue 25 defines the eventual product: Admit→Discover→Model→Enumerate→Propose→Challenge→
Human triage→Implement separately→Verify→Handoff, with `model-manifest.json`,
`threat-ledger.json`, `risk-dispositions.json`, versioned schemas, four freshness axes, and
method profiles (`security-dfd-v1`, `stride-v1`, `adversarial-abuse-case-v1`). This V1 lands
the *prose discipline* of Enumerate→Propose→Challenge→Human triage in the
reviewing-overengineering shape — no JSON schemas, no typed DFD, no drift machinery. Each
deferred layer gets a named trigger in the skill's closing section: typed model + ledger
schemas when two independent runs need to diff against each other; freshness axes when a
recorded model outlives one release; the independent `adversarial-abuse-case-v1` challenger
as a separate profile when the first human triage reports lens blindness; import/export
adapters never before a researched use case (issue 25's native-first boundary). V1 does not
contradict the resolved answer; it sequences it.

---

## 2. Lenses: STRIDE over a scoped subject, with this repo's residuals as worked examples

**Scope rule, stated first because everything below depends on it.** A run binds exactly one
subject before any lens fires — one diff, one subsystem, or one trust boundary — as an
immutable snapshot: commit, tree/diff digest, or frozen plan bytes, mirroring
reviewing-overengineering's "Bind the candidate". Record the producer of the subject and,
when available, run lenses from a different model or independent perspective than the
producer's. The whole repository is never a subject; "the repo" is refused with an offer to
scope (§5). Per-lens coverage over the subject's elements uses issue 25's vocabulary:
every element/lens pair records `applicable`, `not_applicable` (with rationale), `deferred`
(owner + re-entry trigger), or `out_of_scope` (citing the approved boundary); a missing pair
is `not_evaluated` and blocks any coverage claim; `no_threat_identified` means only that
this run found none.

The six paragraphs below are the content of `references/stride-lenses.md` in summary: what
each letter means against this repo's real trust boundaries, each anchored to a named,
already-documented residual so the first run has worked examples rather than textbook prose.

**S — Spoofing: which names are resolved rather than bound?** In this repo the identities
that matter are tool and model identities, not user logins. The worked example is
AGENTS.md's jq/mise substitution residual (ADR-0020): `ccodex`'s launch refusals depend on a
`jq` parse of settings documents adjacent to credentials, so the route pins `jq` — but the
pinned route locates `mise` itself by PATH name, because mise is the sole unpinned bootstrap
prerequisite; a substituted `mise` impersonates the toolchain front door and governs that
parse exactly as it governs `ocx`, and a substituted `jq` answering "clean" would suppress
every settings refusal. The same lens covers model identity: a `RuntimeAssignment`'s
`resolved_model_id` requires verified readback precisely because a gateway *claiming* an
identity is a spoofing surface — requested values never become readback. The lens question
for any subject: enumerate every name resolved at use time (PATH lookups, provider ids,
config keys) and ask who can write ahead of the resolver.

**T — Tampering: what invariant holds *inside* each multi-step mutation, and who shares the
UID?** Two named residuals are the worked examples. First, the Seeds launcher's receipt
"detects ordinary drift, not a same-UID TOCTOU racer": hashes are checked at admission, the
exact Bun/entry is executed after, and a same-UID process can swap the bytes in the interval
— a tampering window the doctrine accepts and names rather than claims to close. Second, the
D4-era rename-aside interval: a copy-mode tree swap is a rename-aside *pair*, not one atomic
replace, so an interruption inside it leaves the previous tree parked in a named
`.<name>.old-*` sibling, and staged copy content is process-crash consistent rather than
power-loss durable — here the mutator is a crash, not an attacker, but the lens is the same:
the invariant is suspended mid-sequence and the design's honesty is to name the interval and
report leftovers instead of guessing. The lens question: for every write sequence crossing
the subject boundary, state the invariant at each intermediate step and which same-UID actor
could interleave.

**R — Repudiation: could a dispute about who did what be decided from artifacts alone?** The
repo's canonical statement is evidence-discipline's receipt-vs-control rule: a receipt
writable by the same actor as the mechanism it attests is forgeable by construction, and the
fix is to *remove* the self-declared field, never to add a second one forgeable the same
way. Worked examples: the bootstrap receipt lands under `XDG_STATE_HOME` *outside the
clone*, so the clone cannot rewrite its own provenance; ADR-0030 moved wave evidence into
git history — an append-only store a worker cannot quietly rewrite; and the credential-URL
refusal is designed to land *before* the line that would echo the remote, preserving the
record without leaking the value. The lens question: for each mutation on the boundary, name
who writes the record, whether the mutator can rewrite it, and whether a later reader could
reconstruct the action without trusting any single agent's prose.

**I — Information disclosure: enumerate the sinks, then check the refusal fires before the
first one.** The bootstrap script's userinfo rule is the worked example: a `--remote` URL's
userinfo is a credential channel that *every consumer keeps* — stdout, the receipt, Git's
argv, the clone's config — so the refusal names the option and fires before the value
reaches any of them, and where an existing origin must be READ to detect a credential, the
value is inspected but never echoed. Same lens, second example: the muse-claude plane
inherits only the `statusLine` stanza and deliberately not the `env` block, because `env`
can carry a live credential and copying it would also re-point the child off its verified
route. Third: the secrets gate scans tracked-plus-untracked selections and refuses symlinked
paths rather than following them outside the repository — the scan surface itself is a
disclosure boundary. The lens question: list every sink a secret-adjacent value can reach
(output, receipts, argv, configs, error text, caches) and verify ordering — refusal before
first sink, not after.

**D — Denial of service: budgets, ceilings, and the difference between designed refusal and
accidental exhaustion.** The Mermaid renderer's policy is the worked example in both
directions. Its `max_rss_bytes` and `RLIMIT_FSIZE` limits are resource-*availability*
ceilings calibrated to the pinned browser (ADR-0006 records the measurement), and the
recorded failure is self-inflicted: retightening `max_output_file_bytes` toward an
SVG-shaped number kills the browser mid-session as an opaque `Connection closed` — a control
misclassified as an output bound becomes a DoS of one's own surface, which is why the
doctrine says re-measure on any pin bump. The operational sibling is the recorded lesson
that one unbounded whole-disk search exhausted a WSL host's RAM: fan-out without a bounded
search surface is the agentic DoS shape. The lens also distinguishes *designed*
unavailability — `MISE_PARANOID=1` failing closed until explicit trust, a launch refusing at
exit 3 — from accidental exhaustion. The lens question: does every loop, fan-out, render,
and retry on the subject carry a budget and a stop condition, and is each deliberate refusal
distinguishable from a hang?

**E — Elevation of privilege: can evidence be spent as authorization?** In this repo,
privilege means authority for outward effects, and the canonical EoP is a green gate, a
reviewer verdict, or a conductor record leaking into push/merge/deploy/credential authority.
The doctrine repeats it at every layer ("a passing gate is evidence only"; "no local status,
gate, reviewer label, or conductor choice grants authority for … outward effect"), and the
skill-authoring admission floor makes *implying otherwise* a defect in a skill body. Worked
examples: `--yolo` is an explicit, wrapper-consumed unsafe opt-in that deliberately does
*not* weaken the gateway-health or billing-honesty refusals — privilege boundaries compose
rather than inherit; hooks are best-effort convenience, never release authority; and this
skill's own output contract is the same rule applied to itself — a findings report, however
severe, authorizes nothing, and the human-only disposition gate (§3) exists so no agent's
draft becomes a risk acceptance by transcription. The lens question: trace each verdict,
receipt, or status the subject produces to every effect it could be cited for, and confirm
an authorization step exists there that no agent can perform.

---

## 3. Output contract: classified seed-shaped findings, evidence-graded, human-disposed

One findings report per run, bound to the subject snapshot digest and naming the producer
and the lens actor. Structure, in order:

1. **Subject binding block** — subject kind (diff | subsystem | trust boundary), snapshot
   identifier (commit / tree- or diff-digest / frozen plan bytes), producer, lens actor and
   whether it is independent of the producer, date, and the admission-time budget.
2. **Disposition rows before findings** (evidence-discipline): one row per source consulted
   — identifier, retrieved yes/partial/no, retrieval method, class actually reached, author
   and relation, failed ranges for partials. Gaps stay in this report, embarrassing and
   visible: not-retrieved / partial / negative finding / staleness, never reconstructed
   across.
3. **Per-lens coverage table** — every subject element × STRIDE letter pair carries
   `applicable` | `not_applicable`+rationale | `deferred`+owner+re-entry trigger |
   `out_of_scope`+cited boundary. A missing pair reads `not_evaluated` and blocks any
   coverage claim. `no_threat_identified` states only that this run found none.
4. **Findings**, each one a classified seed-shaped recommendation matching the critic's
   landed shape:

   ```
   {title, type, severity, blocking?,
    found_by: sdlc-threat-model,
    source: <subject snapshot digest>,
    stride: [<letters>],
    evidence: file:line + the observed mechanism, with each claim carrying exactly one of
              the five evidence classes (primary-artifact | primary-claim | vendor-doc |
              author-claim | community-report; sub-class partial retrievals, e.g.
              vendor-doc-snippet),
    acceptance: what a mitigation must demonstrate, stated as a checkable condition,
    class: ACTIVE_MILESTONE | BLOCKED_CI | BLOCKED_DESIGN | BLOCKED_DEPENDENCY |
           POST_MILESTONE | OUT_OF_SCOPE | DUPLICATE | INVALID,
    rationale}
   ```

   Classes come once, at retrieval, from the agent that retrieved the artifact; no later
   actor raises one (the anti-inflation rule). Refuse the refused phrasings: never
   "verified", write the command and output; never "the code does X", write `path:line`
   plus class.
5. **Structured submission** with exactly the critic's headings — `role`, `scope`,
   `findings`, `evidence`, `recommendation`, `blockers`, `unknowns`, `next_action` — so a
   conductor consumes threat findings and critique findings through one contract.

**Human-only disposition, mechanically stated.** The report carries a disposition column
that the run leaves empty except for `pending`. Agents may *draft* a proposed disposition in
`recommendation`, clearly labeled a proposal; only a human writes accepted / action /
deferred / dismissed / external, with rationale, identity, and (for deferrals) expiry —
issue 25's disposition classes, minus the JSON artifact until that layer's trigger fires. A
disposition written by any agent, including the conductor, is a defect the acceptance tests
check for (§7). Mitigation of an accepted finding is an ordinary authorized SDLC workstream;
its verification is a *new run by a different actor* against the new snapshot — a mitigated
subject is re-reviewed, never waved through (the exemplar's remediation loop). No finding,
report, coverage table, or disposition authorizes any outward effect, and the report's
closing line states so verbatim.

**No fixes, no queue writes.** The skill attacks and reports. It never edits the subject,
never proposes a patch hunk as a "finding", and never invokes `sd` or any queue mutation —
findings are recommendations for conductor capture through the launcher's conductor-write
seam, exactly as the critic's contract already works.

---

## 4. The routing.md row and the frontmatter description

Row, in the landed moment/symptom form:

| Skill | Fires at (lifecycle moment) | Fires on (symptom) |
|---|---|---|
| `sdlc-threat-model` | a trust boundary being created, moved, or deleted during framing, planning, or review; before accepting a change that touches identity, credentials, untrusted input, or an authority boundary; re-review of any mitigated finding | a residual window named in prose with no threat record behind it; "is this safe?" entering a review; a deletion review reclassifying a control as presentation |

Sequencing note for the router prose: `reviewing-overengineering` and `sdlc-threat-model`
share the deletion-review moment from opposite directions — the former defends existing
controls against deletion pressure, the latter enumerates what threatens a boundary — and
both descriptions name each other rather than merging.

Frontmatter description (872 characters, under the 1024 cap; moment-trigger form per the
landed pattern):

> Fires when a trust boundary is created, moved, or deleted — during framing, planning, or
> review of one scoped subject (one diff, one subsystem, one boundary) — and before a change
> touching identity, credentials, untrusted input, or an authority boundary is accepted.
> Also fires on the symptom of a residual window named in prose with no threat record behind
> it, and when a mitigation claims to close a finding: a mitigated subject is re-reviewed,
> never waved through. Applies STRIDE-shaped lenses over the bound snapshot and returns
> classified, evidence-graded findings as seed-shaped recommendations with human-only risk
> disposition. Advisory, never a gate leaf: it attacks, never fixes; never scans beyond the
> bound subject; consumes no CVE or vulnerability feeds; files no seeds itself. Not for
> generic secure code review (reviewer/critic lenses) or complexity audit
> (reviewing-overengineering).

---

## 5. What it refuses, by name

1. **No scanning-the-world.** The subject is one named immutable snapshot. "Threat-model
   the repo" is refused with an offer to scope: name one boundary, one subsystem, or one
   diff. A run that discovers an adjacent boundary returns it as a seed-shaped
   recommendation for a *future* subject, never silently widens.
2. **No CVE or vulnerability feeds, no scanners.** Vulnerability scanning, dependency
   scanning, penetration testing, red-team execution, incident response, forensics, and
   compliance audit are separate capabilities or human responsibilities (issue 25's
   rejection list). The skill works from the repository's own artifacts, ADRs, and stated
   residuals. A request to "pull the CVE feed" is refused by name and routed away
   (dependency auditing has its own tooling surface).
3. **No gate integration.** Never a gate leaf: not reachable from `mise run check`,
   `lefthook.yml`, or CI; no repository policy may make a run's outcome block a commit. A
   repo may *cite* findings in review; the run itself blocks nothing, and a completed run
   never means the system is secure.
4. **No auto-filed seeds.** The skill emits recommendations; only the conductor mutates the
   queue, through the launcher's conductor-write path. (Operationally: seed ids are read
   back from `.seeds/issues.jsonl` after the conductor writes, never cited from memory.)
5. **No fixes, no self-verified mitigations.** Attacks-never-fixes; mitigation is a
   separate authorized workstream; verification is a new run by a different actor against
   the new snapshot. `implemented` never implies `verified`.
6. **No agent-written risk disposition, no completeness claims.** Disposition fields stay
   `pending` until a human writes them. STRIDE coverage, a clean coverage table, or zero
   findings never becomes a security-completeness claim; the report states its snapshot and
   date because its truth decays silently from there.
7. **No sensitive-content egress by default.** The working set defaults to local, untracked
   storage; publishing a threat report anywhere outward (repo tracking, PR body, external
   tool) is a separately authorized, operation-specific effect — a threat report is a map
   of the softest ground and is treated with the sensitivity of one.

---

## 6. Build estimate

**Slice 1 — the skill (V1, this seed's exit).** Prose only, no code, no schemas:
- `skills/sdlc-threat-model/SKILL.md` (~110 lines): bind-the-subject, the six lens
  one-liners pointing at the reference, the output contract of §3, the refusal list of §5,
  and a closing admission-rationale section stating the four gates and which promotion
  signals cleared (per §1).
- `skills/sdlc-threat-model/references/stride-lenses.md` (~160 lines): the six lens
  paragraphs of §2 with the worked residual examples, self-contained per the
  references-load-on-demand rule.
- `routing.md`: the §4 row plus the sequencing note; `AGENTS.md` bundle list: one bullet.
- No `NOTICE` change expected: STRIDE is cited as method provenance (Microsoft's
  methodology, re-expressed) with no foreign bytes copied; if any passage is adapted from a
  specific foreign document, the donor entry lands in the same change per skill-authoring §4.
- Effort: one implementer plus one reviewer, about one day including `mise run check` and
  the naming-deviation ratification (§1). The validator picks the skill up automatically.

**Slice 1b — first real run (proof, same wave):** subject = "the installer's
publication/removal boundary at HEAD", seeded with the D4 residual set (byte-identity
uninstall window, rename-aside interval, pre-v4 refusal) plus AGENTS.md's Seeds-receipt
TOCTOU and jq/mise substitution residuals. Its report is the wave's exit artifact and the
live test of the output contract. ~Half a day.

**Slice 2 — the optional workflow (deferred).** `workflows/sdlc-threat-lenses.js` per the
spec in §1, built only when the named trigger fires. ~Half a day when triggered.

**Later slices (issue 25 layers, each behind its named trigger, not estimated here):** typed
model + ledger JSON schemas; freshness axes; the independent abuse-case challenger profile;
adapters (native-first until a researched use case).

---

## 7. Acceptance tests

Mechanical (checked by existing machinery):
- **A1** `mise run check` green with the skill landed: name==dirname, description ≤1024,
  no broken reference links, no secret-shaped strings.
- **A2** No gate integration: `grep -r sdlc-threat-model mise.toml lefthook.yml .github/`
  returns zero; the skill name appears in `routing.md` and `AGENTS.md` only as advisory
  surface. (Read the verdict and act in separate commands — never chain an effect after an
  evidence grep.)
- **A3** Skill body contains no static model/effort pin, no user-specific path, no
  provider credential (validator + admission floor).

Behavioral (review-verified against the slice-1b run):
- **A4** Selection vignettes: "this diff adds a new trust boundary" selects
  `sdlc-threat-model`; "cut this down" selects `reviewing-overengineering`; each
  description names the other. A host with the foreign generic `threat-modeling` installed
  still loads this skill (the project-scoped name does not collide).
- **A5** The run over the worked subject produces: subject binding with digest; disposition
  rows including at least one honest gap; a full per-lens coverage table with zero
  `not_evaluated` pairs *or* an explicit blocked coverage claim; ≥1 finding carrying
  stride letters, per-claim evidence class, acceptance condition, and a mission-loop class;
  the critic-shaped structured submission headings; zero queue mutations and zero edits to
  the subject.
- **A6** Refusals fire by name: a whole-repo subject request and a CVE-feed request are
  each refused with the routing guidance of §5, not silently narrowed.
- **A7** Human-only disposition holds: every disposition field in the emitted report is
  `pending`; no agent-authored accepted/dismissed value appears anywhere, including the
  conductor's capture.
- **A8** The report's closing line states that no finding or coverage result authorizes
  any outward effect, and the wave's own handling honors it (the report lands as evidence,
  the seed closes only on the conductor's recorded acceptance).

Slice-2 only:
- **A9** Workflow validator passes (first-line `// workflow:` pairing, lowercase slug,
  module-free parse, no model/effort pin, no user paths); executing any stage with empty
  `ASSIGNMENTS` refuses before dispatch with the "return one SeedProposal" error,
  distinguishing not-supplied from supplied-but-incomplete; installing the file runs and
  enables nothing.
