
# Worktree isolation: fail-closed test-design contract

Provenance: this pattern is ported from a TypeScript `node:test` suite in a sibling
project's dynamic-workflow engine (a fail-closed worktree isolation test file for its
agent-dispatch layer). The target repository's test suite is Python `unittest`, and
nothing here is executable — it is a specification a future implementer turns into real
Python tests once this repo has (or adopts) worktree-isolated agent dispatch. Treat each
entry below as a test case shape, not as authorization that the described behavior already
exists here.

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

## Control cases (the boundary's other side)

Keep both of these alongside the planted violations. Removing them turns the suite into "an
error can happen," not "the boundary is exactly here."

- **Satisfiable isolation still runs, and is torn down.** A request that isolation *can*
  honor must still dispatch the agent, must dispatch it into a directory that is not the
  shared checkout, and that directory must no longer exist once the agent finishes. Assert
  the dispatched working directory positively (not merely "not equal to the shared
  checkout" — assert it structurally matches wherever the implementation is documented to
  place isolated worktrees).
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
