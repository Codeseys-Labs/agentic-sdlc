# Seeds Launcher Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the exact Seeds launcher so acquisition is isolated from target-controlled and ambient npm configuration, while native Windows and POSIX safely execute the exact mise-provided executable without a shell.

**Architecture:** Retain the Bash preflight as the POSIX implementation, but delegate the runtime command to the exact pinned Node 22.22.3 executable. Node locates the exact Seeds executable from mise's injected PATH, changes child cwd to the canonical target, and spawns it with an argv array and `shell: false`; its Windows branch invokes `cmd.exe` with the exact `sd.cmd` path because Windows cannot directly spawn `.cmd` with no shell. POSIX creates neutral state under fixed `/var/tmp` and supplies two separate empty `.npmrc` files. The Windows runbook uses the OS temp root, two separate empty config files, and an equivalent Node trampoline; neither platform persists variables/configuration.

**Tech Stack:** Bash, exact Node 22.22.3, mise 2026.4.27+, Python unittest, native Windows PowerShell 5.1.

---

### Task 1: Add focused launcher regression tests

**Files:**
- Modify: `tests/test_preflight_capabilities.py:538-825`
- Test: `tests/test_preflight_capabilities.py`

**Step 1: Write the failing tests**

Extend the fake mise fixture to record neutral directory/config paths and run a supplied Node trampoline. Add tests that require:

```python
self.assertTrue(call["mise_cd"].startswith("/var/tmp/agentic-sdlc-seeds."))
self.assertNotIn("TMPDIR", call["environment"])
self.assertNotEqual(call["npm_environment"]["NPM_CONFIG_USERCONFIG"], call["npm_environment"]["NPM_CONFIG_GLOBALCONFIG"])
self.assertEqual(Path(call["npm_environment"]["NPM_CONFIG_USERCONFIG"]).read_text(), "")
self.assertEqual(Path(call["npm_environment"]["NPM_CONFIG_GLOBALCONFIG"]).read_text(), "")
```

Add cases for hostile `TMPDIR`/`TEMP`, inherited mixed-case `NPM_CONFIG_*`, every exit/failure cleanup path, and arguments with spaces/metacharacters. Require the fake exact launcher to receive cwd and argv unchanged, without `sh -c`.

Add a documentation test requiring the fixed POSIX `/var/tmp` boundary and the Windows `[IO.Path]::GetTempPath()` boundary, two distinct empty config files, an explicit cleanup `finally`, `sd.cmd`, and Node's `shell: false` execution.

**Step 2: Run test to verify it fails**

Run:

```bash
mise exec uv@0.11.17 -- uv run --python 3.12.11 python -m unittest tests.test_preflight_capabilities.PreflightCapabilityTests tests.test_preflight_capabilities.SeedsDocumentationContractTests
```

Expected: FAIL because the current launcher inherits `TMPDIR`, uses `/dev/null` twice, retains `sh -c`, and does not guarantee cleanup on signals.

### Task 2: Implement the minimal POSIX launcher repair

**Files:**
- Modify: `scripts/check-agentic-sdlc-prereqs.sh:12-79`
- Test: `tests/test_preflight_capabilities.py`

**Step 1: Create fixed neutral resources**

Create the neutral parent only with `/var/tmp`, not `TMPDIR`, `TEMP`, the target, or target ancestry. Use `mktemp -d /var/tmp/agentic-sdlc-seeds.XXXXXX`, `umask 077`, and two distinct empty files beneath that neutral directory for `NPM_CONFIG_USERCONFIG` and `NPM_CONFIG_GLOBALCONFIG`.

**Step 2: Install unconditional cleanup before acquisition**

Install a scoped cleanup trap for `EXIT`, `HUP`, `INT`, and `TERM` immediately after creating the neutral resources. Capture and return the child exit status after cleanup. Restore caller traps/avoid trapping when sourced so the launcher does not change the source shell's later behavior.

**Step 3: Replace shell command execution with Node trampoline**

Pass a small literal Node program after `--` to `mise exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14`. The program receives the target and original args separately, finds the exact `sd` or `sd.cmd` by checking only mise-provided PATH entries, and `spawn`s it with `cwd: target`, `shell: false`, inherited stdio, and `windowsHide: true`.

On Windows, invoke `process.env.ComSpec` with `['/d', '/s', '/c', exactSdCmd, ...args]`, still under `shell: false`; this is the documented no-shell Node path for `.cmd` files and retains array boundaries. Propagate the code; for a terminating child signal, re-signal the trampoline so the parent observes failure. Explicitly handle spawn failure.

**Step 4: Run focused test to verify it passes**

Run the command from Task 1.

Expected: PASS.

### Task 3: Correct portable execution documentation

**Files:**
- Modify: `skills/agentic-sdlc-orchestrator/SKILL.md:27-45`
- Modify: `skills/agentic-sdlc-orchestrator/references/seeds-worktrees.md:4-69`
- Modify: `README.md:150-168`
- Test: `tests/test_preflight_capabilities.py`

**Step 1: Document POSIX root boundary**

State that POSIX neutral state is created directly beneath fixed `/var/tmp`, never inherited `TMPDIR`/`TEMP`, never the target, and never target-controlled ancestry. State that both user and global npm config paths are distinct empty files inside it.

**Step 2: Document native Windows boundary**

State precisely that Windows uses `[IO.Path]::GetTempPath()`—the OS-selected local temporary root independent of the target—and a random private directory directly below it. State the target and all its ancestors are excluded. Create two distinct `[IO.Path]::GetTempFileName()` empty files under the private neutral directory; do not reuse a path.

**Step 3: Document exact trampoline and cleanup rule**

Replace every `sh -c` example with the Node 22.22.3 trampoline contract. Explain native Windows executes the exact `sd.cmd` via `ComSpec` as an argv array while Node's `shell` option remains false. Declare cleanup on success, failure, and `HUP`/`INT`/`TERM`, and keep the honest npm tarball/transitive integrity limitation unchanged.

**Step 4: Run documentation tests**

Run the focused command from Task 1.

Expected: PASS.

### Task 4: Run real isolated cross-platform probes and final gates

**Files:**
- Verify only: repository files

**Step 1: Run fake mise mutation tests**

Run the focused unittest classes. Confirm fake mise observes two different empty configs, only reviewed npm variables, `/var/tmp` acquisition, no inherited `NPM_CONFIG_*`, exact tool tuple, target cwd, and preserved hostile arguments.

**Step 2: Run cold Linux real mise/npm probe**

Create an external temporary target with a target `.npmrc`, ancestor `.npmrc`, and hostile inherited `NPM_CONFIG_*`. Set fresh `MISE_DATA_DIR`, `MISE_CACHE_DIR`, and `HOME`; invoke the launcher against the target. Confirm version `0.5.14`, npm acquisition cannot read target/ancestor/ambient registry, exactly two empty config files are passed, and all probe resources are removed.

**Step 3: Run cold native Windows PowerShell real mise/npm probe**

Invoke `powershell.exe -NoProfile -NonInteractive` directly—not Git Bash/MSYS—with the equivalent isolated target/ancestor/ambient registries and fresh mise directories. Confirm `sd.cmd` resolves from exact mise data, `--version` returns `0.5.14`, config files are distinct and empty, target cwd/arguments survive, and cleanup completes. Do not modify the known foreign installer-state record; report it if encountered.

**Step 4: Run repository gates**

Run:

```bash
mise run check
./scripts/install-skill-bundle.sh self-test
```

Run native Windows:

```powershell
mise run check
```

Expected: all applicable gates pass. If native Windows finds an invalid foreign installer-state record, preserve it and report it rather than mutating it.

### Task 5: Commit the verified successor locally

**Files:**
- Stage only: changed launcher, tests, and execution documentation

**Step 1: Review scope**

Run `git status --short`, `git diff --check`, and `git diff --stat`. Confirm no policy/config/identity/remote files and no foreign installer-state changes are staged.

**Step 2: Create local commit**

Commit using the existing concise Conventional Commit style:

```text
fix: harden Seeds execution trampoline

Use neutral config isolation and the pinned Node launcher to avoid shell and target-config execution paths.

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Step 3: Verify commit**

Run `git log -1 --oneline` and `git status --short`. Do not push or contact remotes.
