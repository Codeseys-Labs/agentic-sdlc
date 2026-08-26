
# Worktree isolation: fail-closed test-design contract

Provenance: this pattern is ported from a TypeScript `node:test` suite in a sibling
project's dynamic-workflow engine (a fail-closed worktree isolation test file for its
agent-dispatch layer). The target repository's test suite is Python `unittest`.

This file stays a test-design contract rather than a test runner, but it is no longer wholly
unimplemented here, and the split is load-bearing: reading it as "all specification" and
reading it as "all covered" are both wrong.

**The git-substrate half is executable and green.** `tests/test_worktree_failclosed.py`
(7 cases) plants git-level preconditions against a throwaway fixture repository and issues
the `commands/sdlc-wave.md` recipe in the same form, defaulting the base to HEAD —
`git worktree add` into `<repo>/.worktrees/<seed-id>-<slug>` with `-b work/<seed-id>-<slug>` —
then asserts the substrate refuses and that the fixture's worktree and branch lists come back
byte-identical to their pre-attempt state.

**The agent-dispatch half has no implementation here.** Every entry that needs a
caller-controlled hook, a cancellation token, a deadline, a typed error object, a lifecycle
event stream, or a dispatch spy needs a worktree-isolated *dispatcher* to plant a violation
against, and this bundle ships none — it delegates fan-out to the host's own subagent tool.
That is why `skills/agentic-sdlc/SKILL.md`'s one-line summary of this file ("A future
implementer's spec, not evidence that this repo already runs isolated dispatch") remains
exactly true as written: it is scoped to isolated *dispatch*, and dispatch is precisely the
uncovered half. The existing tests prove the substrate the runbook stands on is fail-closed
and restorable; they prove nothing about whether a dispatcher refuses instead of silently
running the agent in the shared checkout. That silent downgrade — the single failure mode
"Why this pattern exists" names below — has no executable coverage in this repository.

Coverage entry by entry, as of this pass. Re-derive it rather than trusting it: running the
suite verbosely prints each test's own first docstring line.

| This file's entry | Executable here? | Where, or why not |
| --- | --- | --- |
| General shape 1 — throwaway fixture, never the enclosing checkout | yes | `setUp` builds a `tempfile.TemporaryDirectory` fixture repo, and the suite's `git()` helper strips every `GIT_*` variable so the checkout running the tests cannot leak in |
| General shape 2 — plant the exact precondition | partly | occupied branch, occupied target path, stale registration, and a dirty index/worktree are planted; non-git directory, throwing hook, abort signal, and timeout are not |
| General shape 3 — refusal carries a stable typed error identity | no | the tests assert git's exit status and, in one case, a specific git message (`already registered`); there is no typed error code to assert here because there is no dispatcher to own one |
| General shape 4 — the agent never ran, and never saw the shared checkout path | no | needs a dispatch spy; no dispatcher, no spy |
| General shape 5 — cleanup left no orphan | yes | `test_a` (byte-identical worktree and branch lists after the refusal), `test_b` (pins the *fail-open* case where git strands the isolation branch, then proves the runbook's documented recovery restores that state), `test_e` (prune before the path is reusable), `test_f` (the two cleanup refusals) |
| General shape 6 — tear the fixture down even when assertions fail | yes | `addCleanup(self.tmp.cleanup)` |
| Failure mode 1 — occupied isolation branch | partly | `test_a` executes it at the git level; the non-recoverable flag, the refused agent/label identity, the zero-dispatch assertions, and the lifecycle-pair assertions are not executed |
| Failure mode 2 — non-git working directory | no | not planted anywhere in the suite |
| Failure mode 3 — throwing observer on the acquisition path | no | no acquisition path here accepts a caller-supplied hook |
| Failure mode 4 — mid-flight abort | no | nothing here honours a cancellation token |
| Failure mode 5 — timeout | no | there is no per-call deadline to expire |
| Redaction sub-pattern | no | needs the error-message, structured-details, and log-sink surfaces a dispatcher would expose |
| Pair-completeness sub-pattern | no | no start/end lifecycle events are emitted here to pair |
| Control — satisfiable isolation still runs, into the documented substrate | partly | `test_c` proves the add succeeds into `<repo>/.worktrees/<id>` carrying the branch point's content with a clean status and none of the caller's dirt, and `test_d` proves that path stays invisible to the workspace with an unignored control showing the gitlink the ignore rule prevents; neither proves an agent was dispatched there, and teardown-when-the-agent-finishes is not asserted — only the explicit removal paths in `test_e` and `test_f` are |
| Control — no isolation requested, nothing changes | no | there is no isolation opt-in here to omit |
| Notes — `tempfile` plus `subprocess.run` fixture with paired cleanup | yes | `init_fixture` plus `addCleanup` |
| Notes — slug helper kept in sync with the production derivation | no | the tests use literal branch names; nothing derives a slug here yet, so the drift hazard the note describes has not arrived |
| Notes — recording stub with a `calls` list | no | there is nothing to record |
| Notes — cooperative-cancellation analog | no | see failure mode 4 |

Treat every `no`, and every unexecuted assertion inside a `partly`, as a test case shape —
not as authorization that the described behavior already exists here.

## Why this pattern exists

A worktree-isolation feature has exactly one dangerous failure mode: when isolation cannot
be honored, the dispatcher silently falls back to running the agent in the shared checkout
instead of refusing the run. That failure is invisible in the happy path — it only shows up
when someone plants the exact precondition that used to cause it and checks that the system
now refuses instead of downgrading. A suite that only proves the happy path cannot
distinguish a boundary from a wish, so a happy-path control belongs alongside the planted
violations, not instead of them.

## The general shape

Every case in this pattern:

1. **Builds a throwaway fixture repository** (a fresh, isolated Git repo with one commit),
   never operating against the enclosing checkout that is running the test suite itself —
   a test process may itself be executing inside a worktree of a protected repository, so
   any destructive git operation must target only the disposable fixture.
2. **Plants the exact precondition** that historically produced a silent shared-checkout
   run (an occupied branch, a non-git directory, a throwing caller hook, an abort signal, a
   timeout).
3. **Asserts refusal, not silent degradation**: the call must reject/raise with a specific,
   stable error identity (a typed error code) — not merely "an error happens," which would
   also pass if the error were unrelated.
4. **Asserts the agent never ran**: the dispatcher/runner spy must have recorded zero
   invocations, and specifically must never have received the shared checkout's path as the
   working directory.
5. **Asserts cleanup left no artifact behind**: no orphaned worktree directory, no orphaned
   isolation branch — an orphan from an aborted run is exactly the precondition that makes
   the *next* run's occupied-branch case fire for an unrelated reason.
6. **Tears its own fixture down** in a `finally`/cleanup block, even when the assertions
   above fail, so one failing case cannot pollute a later case's tmp-directory reuse.

Two control cases anchor the boundary from the other side: a satisfiable isolation request
must still run, in its own isolated directory, and that directory must be gone afterward;
and a call that never asked for isolation must be completely unaffected (it inherits the
caller's own working directory, as if the feature didn't exist).

## Failure-mode catalog

Each entry: the **planted violation**, the **expected refusal**, and the **assertion set**
that proves fail-closed behavior rather than merely "an error occurred."

### 1. Occupied isolation branch

- **Planted violation**: before dispatch, create the exact branch name the isolation
  mechanism would derive for this run/call/label triple (deterministic slug: lowercase,
  collapse non-alphanumeric runs to a separator, trim leading/trailing separators, cap
  length). This reproduces what a truncation collision or a crashed predecessor run leaves
  behind.
- **Expected refusal**: the call rejects with a stable "isolation unavailable" error
  identity, marked non-recoverable (retrying into the same occupied branch cannot succeed
  without human intervention), carrying the agent/label identity that was refused.
- **Assertions**:
  - the error's type/code is the specific isolation-unavailable identity, not a generic
    error;
  - the error is explicitly marked non-recoverable;
  - the error message names the refused agent/label and gives a human-readable reason
    (e.g. matches "already exists" or "could not be provided") without requiring the
    caller to parse git internals;
  - the dispatch/run spy recorded zero calls;
  - the dispatch/run spy never received the shared checkout path;
  - if the system emits start/end lifecycle events, exactly one start and one matching end
    fired for the refused agent (see the pair-completeness sub-pattern below) — a start
    with no end is a phantom; an end with no start is invisible to whatever persists the
    failure code.

### 2. Non-git working directory

- **Planted violation**: request isolation with a working directory that is a plain
  filesystem directory, not a Git repository (no `.git`, no ancestor repo).
- **Expected refusal**: the call rejects with the same isolation-unavailable identity, with
  a message that names the real cause ("not a git repository") rather than a generic
  filesystem or git-subprocess error.
- **Assertions**:
  - error identity matches the isolation-unavailable code;
  - message matches a "not a git repository" pattern;
  - the dispatch/run spy recorded zero calls.

### 3. Throwing observer / caller-supplied hook on the acquisition path

- **Planted violation**: supply a caller-controlled lifecycle hook (an "agent started"
  observer, callback, or event listener invoked during worktree acquisition) that throws.
  This models untrusted or buggy caller code running on the same path that owns
  acquisition and teardown. The original defect this guards: a throw here escaped the
  teardown owner, so the acquired worktree directory and its branch survived — manufacturing
  exactly the orphan that later makes a lawful run hit failure mode 1 for an unrelated
  reason.
- **Expected refusal**: the call rejects, propagating the observer's own error (its message
  must survive unmodified — the caller needs to know it was *their* hook that failed).
- **Assertions**:
  - the propagated error's message matches the observer's own thrown message;
  - the dispatch/run spy recorded zero calls (the agent must not run when its own
    start-announcement failed);
  - the acquired worktree directory no longer exists on disk;
  - the acquired isolation branch no longer exists in the repository's branch list;
  - the fixture repository's own working tree is otherwise clean (no stray state left by
    the aborted acquisition).

### 4. Mid-flight abort (cooperative cancellation)

- **Planted violation**: begin a normal isolated dispatch, but have the runner/dispatch
  stub trigger cancellation (an abort signal, cancellation token, or equivalent) *after*
  acquisition has already completed and the agent has already been dispatched into its
  isolated directory — i.e., cancellation arrives mid-flight, not before acquisition.
- **Expected refusal**: the overall call rejects (propagating the cancellation).
- **Assertions**:
  - confirm the agent actually was dispatched with a real working directory before the
    abort (otherwise the case degenerates into failure mode 2/3 and proves nothing new);
  - the acquired worktree directory no longer exists after the call settles;
  - the acquired isolation branch no longer exists after the call settles.
  - The teardown-on-cancellation guarantee is the point of this case: acquisition and
    teardown must be symmetric even when the caller's own cancellation — not a refusal
    inside the isolation mechanism — ends the run early.

### 5. Timeout

- **Planted violation**: begin a normal isolated dispatch against a runner/dispatch stub
  that never resolves on its own (blocks past any reasonable deadline), with a short
  timeout configured for the call.
- **Expected outcome**: unlike failure modes 1–4, a timeout is typically classified as
  *recoverable* — the call may resolve successfully overall (e.g. the timed-out agent's
  own result slot resolves to null/empty) rather than throwing, depending on how the
  system defines recoverable-per-agent vs fatal-per-run failures. The fail-closed
  obligation that must hold regardless of that classification choice is cleanup.
- **Assertions**:
  - whatever the surfaced result is (null slot, thrown error, or partial result), assert it
    matches the system's documented recoverable-timeout contract explicitly — don't assert
    "no error" as a proxy for "cleanup happened";
  - the acquired worktree directory no longer exists after the timeout fires;
  - the acquired isolation branch no longer exists after the timeout fires.

## Cross-cutting assertion sub-patterns

These are not separate failure modes; they are assertion techniques that should be applied
to *every* refusal case above wherever the surface exists in the implementation under test.

### Redaction: public failure surfaces must not leak host/internal detail

- **Planted violation**: reuse failure mode 1 (occupied branch) while also capturing every
  string surface the system exposes to a human or a log sink: the error's own message, any
  structured "reason"/"details" field on the error, and every line passed to a logging
  callback.
- **Assertions**:
  - none of those surfaces contain the absolute filesystem path of the fixture repository
    (or any other host-local absolute path);
  - none of those surfaces contain a raw subprocess/command-failure echo (e.g. a literal
    "Command failed: ..." string from a shelled-out tool) — that leaks the exact command
    line and its host context, which is not something an operator-facing failure should
    surface verbatim;
  - despite the redaction, the message must still let a human diagnose *why* — assert it
    still matches the same human-readable reason pattern used in failure mode 1
    ("already exists" / "could not be provided"), so redaction is proven to remove host
    detail without removing the diagnosis;
  - any structured details object must not carry a raw base-path field at all (redaction
    at the type level, not just string-scrubbing);
  - the log sink must still have received *some* redacted line naming the refused
    agent/label, so the refusal remains observable in aggregate logs even though it is
    silent on host detail.

### Pair-completeness: a refusal is a complete start/end lifecycle pair

- **Planted violation**: reuse failure mode 1 (occupied branch) while capturing every
  start-lifecycle and end-lifecycle event the system emits (whatever the system's names for
  "agent dispatch began" / "agent dispatch ended" are).
- **Assertions**:
  - exactly one start event and exactly one end event fired for the refused agent;
  - the start and end events share the same call/agent identity (so a consumer can
    correlate them without guessing by position or timing);
  - the end event's result slot is empty/null (a refused agent produced no result);
  - the end event carries the same stable error identity as the outer rejection (the
    failure code must "ride on" the per-agent lifecycle carrier, not only the outer
    call's rejection — this is the channel that persistence layers and status panels
    actually read, so a code that only reaches the outer rejection is invisible to them);
  - the end event's recoverability flag matches the outer rejection's;
  - the end event's carried error message is still present and still passes the redaction
    assertions above (redaction must hold on every carrier, not just the one a test happens
    to check first).

### Operator-state isolation belongs OUTSIDE the code under test

**A test whose safety rests on the product refusing first is one mutation away from mutating the
operator's machine.** Mutation testing deletes guards by design, so "the CLI refuses before it reads
a home, therefore no isolated home is needed" is not an isolation argument — it is a bet that the
refusal is still there, and the mutation run is precisely where it is not. Measured, not
hypothetical (`agentic-sdlc-8dca`): a test called an installer's `main(["uninstall"])` with no
isolated homes, and removing the refusal under mutation drove a real uninstall pass across the
operator's own agent-configuration directories.

- **Every test that drives a real entrypoint passes isolated roots**, including — especially — the
  tests where a refusal is expected to fire before any root is read.
- **The isolation is enforced by a shared seam the mutation cannot reach**, not by a rule in a
  docstring: route every such call through one test-support module that resolves what the
  entrypoint *would* select (through the product's own parser and path normalisation, so the guard
  predicts rather than restates) and **fails the calling test** when any of it overlaps the
  operator's real state. Snapshot the operator's real locations at IMPORT, before any test patches
  the environment — a guard that reads them at call time is told by the very patch it exists to
  police that the real home is a fixture.
- **A test that cannot be run safely has not passed**: the verdict is a failure, never a skip.
- **Assert "nothing happened" independently of "it refused."** The exit code and the emptiness of
  the sandbox are two claims; one assertion covering both lets either carry the other, so a
  refusal that fired *after* writing would still read green.
- **Keep the guard's refusal and the product's distinguishable by name.** They answer different
  questions ("the test did not isolate" against "the operator aimed the plane somewhere it may not
  publish"), and a shared or overlapping token lets a report about one pass as evidence about the
  other. Check the guard has not made a product refusal unreachable: keep one test that reaches the
  product's token through a fixture that is isolated *and* carries the shape the product refuses.

## Control cases (the boundary's other side)

Keep both of these alongside the planted violations. Removing them turns the suite into "an
error can happen," not "the boundary is exactly here."

- **Satisfiable isolation still runs, and is torn down.** A request that isolation *can*
  honor must still dispatch the agent, must dispatch it into a directory that is not the
  shared checkout, and that directory must no longer exist once the agent finishes. Assert
  the dispatched working directory positively (not merely "not equal to the shared
  checkout" — assert it structurally matches wherever the implementation is documented to
  place isolated worktrees — for this bundle that is the in-workspace
  `<repo>/.worktrees/<seed-id>-<slug>/` substrate whose canonical rule lives in
  `references/seeds-worktrees.md` § Worktree substrate).
- **No isolation requested, nothing changes.** A call that never asked for isolation must
  dispatch with the caller's own working directory (typically: the dispatch stub receives
  no explicit override at all, i.e. it inherits by omission) — proving the feature is
  opt-in and inert by default.

## Notes for a future Python-`unittest` implementation

- Build the throwaway fixture with `tempfile.mkdtemp()` plus `subprocess.run(["git", ...],
  cwd=...)` for `init`/`config`/`add`/`commit`, mirroring the TypeScript source's
  `execFileSync` fixture helper; always pair fixture creation with `shutil.rmtree(...,
  ignore_errors=True)` in a `try/finally` (or `addCleanup`) so a failing assertion still
  removes the tmp repo.
- The deterministic branch/worktree-id slug (lowercase, collapse non-alphanumeric runs,
  trim, cap length) must be reimplemented identically on both the production path and the
  test's own "what id would be derived" helper, exactly as the source file keeps a
  standalone `derivedId` helper in sync with `src/worktree.ts`'s `slug()` — a drift between
  the two would make the planted-violation branch name miss the real one and the test would
  falsely pass by hitting a different code path (e.g. "not found" instead of "occupied").
- Represent the runner/dispatch spy as a small recording stub (a callable or object with a
  `calls` list) rather than a mocking-framework mock, so the "zero calls" and "never
  received the shared checkout path" assertions read as plain list assertions.
- Cooperative cancellation (failure mode 4) needs whatever Python analog the implementation
  uses for cancellation (a `threading.Event`, an `asyncio.CancelledError`, or a custom
  cancellation token) — pick whichever the actual dispatcher under test honors, and confirm
  in the fixture that cancellation is triggered only *after* the stub observes a real
  working directory, so the case cannot degenerate into an acquisition-time refusal.
