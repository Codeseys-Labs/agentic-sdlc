# The bounded lab loop: three owners, two planes, and a ratchet that needs authorization

Self-contained: how to run a self-improving research loop whose scoring harness the probe cannot
edit, whose negative results survive, and whose advances stop at a human. You do not need
`SKILL.md` open to use this.

Like `claim-obligations.md`, this is a **design refinement** for the generated research layer. §8
states what is built versus designed. Read it before describing any of this as available.

## 1. Why "self-improving" needs a boundary at all

The loop shape this borrows from — an agent iterating against a fixed scalar oracle, accepting on
improvement and reverting on regression — works well in its original setting: one editable file,
one number, a judge the agent cannot touch, and a blast radius of one throwaway run. In that
setting "never stop, do not pause to ask" is correct advice.

It is wrong here, and the difference is not caution. Here the loop touches a real repository, a
shared queue, and a ledger whose promoted claims are consumed as evidence by later delivery work.
So this design keeps the loop shape, the cheap-probe economics, the fixed budgets, and the
ratchet, and replaces "never stop" with **bounded continuity**.

**Self-improving is not self-authorizing.** That is the whole boundary, and everything below is a
mechanism for holding it.

## 2. The three owners

Every file in a lab belongs to exactly one of three owners, and the split is what makes the
guarantees checkable rather than aspirational.

| Owner | Path | Who may write it |
|---|---|---|
| **Program** | `lab/program.md` | The human, only. This is their single lever: the question, the budgets, the stall threshold, the kill criterion. Agents may propose changes; the human decides. |
| **Harness** | `lab/harness/**` | Nobody, during a run. It is the scoring machinery — the oracle command, the fixtures, the metric extraction. |
| **Workspace** | `lab/workspace/**` | The probe. Its sandbox. |

**A probe that edits its own judge is void** — not wrong, not penalized: void, its result
discarded. This is detected by comparing a recorded digest, not by reading the probe's assurances
that it did not.

Freeze the harness before the first probe by recording the digest of `lab/harness/**` into
`lab/state/harness.lock`. Re-verify after each probe. A mismatch means that probe is void and an
incident is recorded. Changing the harness mid-run is not an edit — it is **a new run**, with a
new digest and a new baseline, and it needs human authorization.

## 3. Two planes

**The inner ratchet.** Probes iterate inside a scratch worktree with no human prompt, bounded by
a trial count and a wall-clock budget from `program.md`. This is where the loop actually runs, and
it runs unattended by design.

**The outer fan-in.** The only place results touch a durable branch, advance a rung, or affect a
queue. A conductor records; an authorized integrator executes an already-authorized mutation.

The inner plane is where "keep going" is honoured. The outer plane is where it is refused. Because
the fan-in happens at most once per session rather than once per trial, the authority boundary is
not a per-iteration tax — the loop stays cheap and the boundary stays absolute.

**Continuous does not mean unbounded.** Continuity lives in `lab/state/next_action.md`: a cold
session resumes by reading that one file. It never means a resident process advancing state with
no conductor present. An unattended scheduler is not authorized here, and the reason is exact — it
would advance state with nobody accountable for the advance, which is the precise thing the plane
split exists to prevent.

## 4. Preconditions — refuse to start

Six, and every one is a refusal condition rather than a warning. Any gap means emit exactly one
typed `SeedProposal` and **stop before dispatch, and therefore before spawn**.

1. **A named oracle command** that prints one scalar and a direction (higher-is-better or
   lower-is-better). Without this there is nothing to ratchet on, and "improvement" becomes a
   judgment call the probe makes about its own work.
2. **A reproduced baseline**, with the exact command and the exact commit that produced it. Not a
   remembered number.
3. **A variance figure** from two or more identical runs. This is the precondition most often
   skipped and the one that most often ends the whole exercise usefully — if variance exceeds the
   improvement you are chasing, the honest verdict is that more trials cannot detect the win, and
   that verdict is a success of the design, not a failure to deliver.
4. **Budgets:** per-trial wall-clock and maximum trials.
5. **A kill criterion, plus the instrument that measures it.** "Stop if it is not working" is not
   a kill criterion; "stop after eight trials with no ten-percent improvement, measured by the
   seconds column" is.
6. **A conductor-supplied certified `RuntimeAssignment`** whose `resolution_state` is `resolved`.
   Requested, inherited, unresolved, or incomplete assignments stop before dispatch. The lab
   contains no static model or effort pin; the exact identifiers arrive at dispatch time.

## 5. The loop

| # | Step | Produces | Boundary |
|---|---|---|---|
| 0 | **Precondition check** — all six above | — | Any gap: one `SeedProposal`, stop |
| 1 | **Freeze** — record the harness digest | `harness.lock` | Changing the harness later starts a new run |
| 2 | **Select** — one highest-leverage uncertainty; probe kind; budget; ratchet or exploration | assignment | — |
| 3 | **Hypothesize** — five or more independent hypotheses including one long shot, each with a falsifier and its cheapest decisive trial; recommend one on cost-per-bit | research brief | The proposer does not run or grade its own trial |
| 4 | **Pre-register** — metric name, direction, comparison baseline, success and failure criteria, budget — **written before the run** | experiment record | Changing the metric afterwards makes it a new probe, not a better result |
| 5 | **Probe** — edit only in-scope files; commit; run the oracle under the wall-clock budget with output redirected to a log; extract only the metric lines into context; append one line to the trial ledger; re-verify the harness digest | trial line | Writes nothing outside `lab/`. Digest mismatch: void |
| 6 | **Record** — write the claim, experiment, and obligation records with obligations unresolved | ledger diff | Single writer — the ledger is a shared file |
| 7 | **Review** — independent reviewers discharge obligations in parallel; the review author must differ from the claim owner | review records | Verdicts are recommendations, never acceptance |
| 8 | **Gate** — run the checks | gate receipt | The output is evidence; the exit code is not permission |
| 9 | **Ratchet or discard** | integration report | See below — human authorization required per advance |
| 10 | **Checkpoint** — append a lesson record; write `next_action.md`; at most one `SeedProposal` | `next_action.md` | Lessons never self-apply |

Steps 2 through 8 repeat inside the trial budget with no human prompt. Steps 9 and 10 run at most
once per session.

**Step 4 deserves emphasis** because it is the cheapest guard against the most common
self-deception: a metric chosen after seeing the result is not a measurement, it is a
justification. Pre-registration as a written field, before the run, is what makes the difference
checkable later.

**Step 5's log discipline** matters for a mundane reason: redirecting the oracle's full output to
a file and pulling only the metric lines into context is what keeps a long run from consuming the
context budget it needs to finish.

## 6. The ratchet, and its known defect

Advance only when **all four** hold:

1. The metric moved in the **pre-registered** direction;
2. The gate passed;
3. The adversarial verdict is accepting;
4. Explicit per-advance human authorization exists.

Otherwise discard the commit — **and keep the trial line.** Negative results are the asset. A
ledger that only records wins cannot tell you what has already been tried, which is the single
most expensive thing to lose across sessions.

**The defect in pure metric ratcheting**, stated because it is real and not obvious: a loop that
only accepts on improvement stops learning as soon as the cheap wins are gone. It hill-climbs into
a local maximum and then burns its remaining budget confirming it.

Two mechanisms fix it:

- **Exploration probes.** A fixed fraction of probes are accepted on **information gain** rather
  than metric improvement — an assumption falsified, an obligation discharged, a rung moved, a
  dead end proven dead. These probes are pre-registered as exploration probes, so their acceptance
  criterion cannot be chosen retroactively.
- **The stall rule.** After N non-improving trials (N from `program.md`, a small number by
  default), the next probe **must change a different named axis**. The stall is recorded in
  `next_action.md`, so a resuming session knows which axes are exhausted rather than rediscovering
  them.

## 7. The seven invariants

Each is a few lines of checking over `lab/`, and each replaces a promise with a comparison.

1. **Harness immutability** — the `lab/harness/**` digest is identical across every commit any
   trial line references. Mismatch: that probe is void, its result discarded, an incident
   recorded.
2. **Program custody** — `lab/program.md` is unmodified by any probe commit.
3. **Append-only ledger** — every previously recorded trial line is byte-identical and in the same
   position. The only diff is appended lines.
4. **Baseline and variance present** — both recorded, with the command and commit. No improvement
   claim without them.
5. **Rung implies resolved obligations by identifier** — per the matrix in `claim-obligations.md`,
   checked by resolving identifiers to records, never by matching words.
6. **Negatives retained** — no failed, worse, void, or falsified line is ever removed. The trial
   count is at least what the branch history implies.
7. **Ratchet legitimacy** — every advance on the durable branch maps to a trial line satisfying
   all four step-9 conditions, and was executed by the authorized integrator.

Invariant 1 is the one that makes the three-owner split real, and 3 and 6 together are what make
the ledger trustworthy as memory. A passing invariant set is **evidence for** the conductor; it is
never authorization for the next advance.

## 8. Built versus designed

- **Shipped today:** the greenfield and brownfield loops and the evidence ladder in
  `operating-model.md`; the roster in `agent-roster.md`; the installer's generated research tree,
  its ownership manifest, and its review gate (whose defect `claim-obligations.md` §1 documents).
- **Designed here, not built:** the `lab/` tree, the harness digest freeze, the append-only trial
  ledger, the exploration reserve, the stall rule, and all seven invariants. No generated file
  emits or enforces any of them yet.
- **No new agent roles are needed.** A lab role is a pinned generic role plus a written charter,
  and a charter must be tool-compatible with the role hosting it. The specific trap: prior-art and
  novelty work needs web access, so it cannot run on a read-only critic role that has none, and
  anything needing to edit files cannot run on a reviewer role that cannot write. Check the host
  role's tool list before writing a charter that assumes a capability.
- **Host degradation.** Where a host cannot delegate at all, one agent plays the charters
  **sequentially, in writing**. This works because the prohibitions are enforced by **artifact
  ordering**, not by process separation: the brief must exist as a file before the probe commit
  exists; a review must cite trial identifiers already in the append-only ledger; the writer may
  cite only what is already written. The gate verifies the ordering afterwards and **records that
  independence was textual rather than structural.** What never degrades on any host: harness
  immutability, the append-only ledger, the independence comparison, the conductor-records step,
  integrator-only advance, and the assignment precondition.

## 9. Authorization boundaries

Every one is operation-specific. None is granted by a green gate, a reviewer verdict, a metric
improvement, or a conductor's decision.

1. **Any advance onto a durable branch** — per advance, executed by an authorized integrator on an
   already-authorized mutation.
2. **Push, pull-request creation or update, merge, publication, deployment, release, version
   bump.** The lab never publishes.
3. **Queue mutation** — the lab emits at most one typed `SeedProposal` and never self-files. The
   conductor alone acts, after verifying the evidence.
4. **Editing `lab/program.md`** — the human's lever. Agents propose; the human decides.
5. **Editing `lab/harness/**` mid-run** — forbidden. A harness change is a new run.
6. **Waiving an obligation** — needs a recorded human authorization reference, and shows in every
   rollup.
7. **Applying a lesson record** — never self-applied. A lesson that would loosen a gate
   additionally needs adversarial review, because a loop that can relax its own scoring has no
   scoring.
8. **Writing anywhere outside `lab/`**, and running against any repository other than the
   authorized one.
9. **Probes with spend, credentials, network writes, or destructive filesystem effects** — a
   resolved safety obligation plus explicit authorization. The default probe has no web access.
10. **Any unattended or scheduled invocation** — not authorized. Continuity is resumption from
    `next_action.md`, never a resident loop.

The asymmetry to keep in view: the inner plane is deliberately permissive so the loop is cheap
enough to be worth running, and the outer boundary is deliberately absolute so that cheapness
never converts into unreviewed change. Both properties are required. A loop bounded at every step
is too expensive to use; a loop bounded nowhere is not a loop but an unsupervised writer.
