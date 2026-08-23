#!/usr/bin/env node
/**
 * Locked, installed Seeds runtime launcher.
 *
 * Bootstrap is intentionally the only mode allowed to invoke mise. Inspect accepts a
 * previously admitted receipt only; it neither discovers, installs, repairs, nor
 * acquires anything. The receipt protects against accidental drift, not a concurrent
 * same-UID attacker between checks and exec.
 *
 * Record is the conductor's queue write. It inherits every inspect admission — same
 * active receipt, same exact hashes, same exact Bun/entry, same allowlisted child
 * environment — and adds compare-and-swap plus post-write readback. Queue initialization
 * is the sole absent-queue form: --expect-queue absent init. It requires no .seeds node,
 * snapshots .gitattributes, and admits only the exact closed initializer surface plus its
 * precise merge-union append. Existing queues use an exact digest and may only create or
 * update the requested record. The underlying queue lock is the writer's own; this seam
 * adds none. A verified record is the conductor's own durable evidence and authorizes no
 * outward effect.
 */
import { createHash, randomBytes } from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import {
  chmodSync,
  closeSync,
  existsSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  readlinkSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync,
  fsyncSync,
} from 'node:fs';
import { basename, dirname, isAbsolute, join, normalize, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCHEMA = 2;
const NODE_VERSION = '22.23.2';
const BUN_VERSION = '1.4.0';
const SEEDS_VERSION = '0.5.15';
const SEEDS_TOOL = `npm:@os-eco/seeds-cli@${SEEDS_VERSION}`;
const SEEDS_PACKAGE = '@os-eco/seeds-cli';
const SEEDS_BIN = 'sd';
const TOOL_NAMES = Object.freeze({ node: `node@${NODE_VERSION}`, bun: `bun@${BUN_VERSION}`, seeds: SEEDS_TOOL });
const NPM_REGISTRY = 'https://registry.npmjs.org/';
const MISE_CONFIG_SENTINEL = '__agentic_sdlc_reviewed_config_only__';
const FORBIDDEN_PACKAGE_KEYS = new Set(['bun', 'bunfig', 'tsconfig', 'jsconfig', 'macro', 'macros', 'preload']);
const FORBIDDEN_PACKAGE_FILES = new Set(['bunfig.toml', 'bunfig.json', 'tsconfig.json', 'jsconfig.json']);
const FORBIDDEN_PACKAGE_STEMS = new Set(['macro', 'macros', 'preload']);
const RECEIPT_KEYS = new Set(['schema', 'platform', 'createdAt', 'distribution', 'runtime', 'tuple', 'hashes']);
const DISTRIBUTION_KEYS = new Set(['root', 'commit', 'gitTree', 'tree', 'miseToml', 'miseLock', 'launcher', 'launcherHash']);
const HASH_KEYS = new Set(['distribution', 'node', 'nodeExecutable', 'bun', 'seeds', 'packageJson', 'entry', 'git', 'gitAdapter', 'bunfig', 'tsconfig', 'gitconfig']);
const DISTRIBUTION_HASH_KEYS = new Set(['tree', 'gitTree', 'miseToml', 'miseLock', 'commit']);
const RUNTIME_KEYS = new Set(['node', 'nodeHash', 'launcherHash']);
const TUPLE_KEYS = new Set(['node', 'bun', 'seeds', 'git', 'trusted']);
const NODE_KEYS = new Set(['root', 'executable', 'version']);
const BUN_KEYS = new Set(['root', 'executable', 'version']);
const SEEDS_KEYS = new Set(['root', 'packageRoot', 'package', 'version', 'bin', 'binValue', 'entry']);
const GIT_KEYS = new Set(['path', 'hash', 'commit', 'tree']);
const TRUSTED_KEYS = new Set(['bunfig', 'tsconfig', 'gitconfig', 'gitAdapter']);
// A receipt records the tuple that was current when it was published. Every verb that RUNS the
// recorded tuple demands that it still equal this launcher's constants. Bootstrap's job is to
// ESTABLISH a tuple, so its retention step reads the prior receipt for structure and internal
// consistency only: a well-formed predecessor that records a superseded tuple is rollback material,
// not corruption. These two spellings are the only admitted modes; nothing else is a mode.
const TUPLE_PINS_CURRENT = 'require-current-tuple-pins';
const TUPLE_PINS_SUPERSEDED = 'admit-superseded-tuple-pins';
const SEEDS_DIRECTORY = '.seeds';
const SEEDS_CONFIG_FILE = 'config.yaml';
const SEEDS_ISSUES_FILE = 'issues.jsonl';
const SEEDS_TEMPLATES_FILE = 'templates.jsonl';
const SEEDS_PLANS_FILE = 'plans.jsonl';
const SEEDS_GITIGNORE_FILE = '.gitignore';
const GITATTRIBUTES_FILE = '.gitattributes';
const INIT_EXPECTATION = 'absent';
const INIT_SURFACE = new Set([
  SEEDS_GITIGNORE_FILE,
  SEEDS_CONFIG_FILE,
  SEEDS_ISSUES_FILE,
  SEEDS_TEMPLATES_FILE,
  SEEDS_PLANS_FILE,
]);
const INIT_MERGE_UNION_LINES = Object.freeze([
  '.seeds/issues.jsonl merge=union',
  '.seeds/templates.jsonl merge=union',
  '.seeds/plans.jsonl merge=union',
]);
// The mission doctrine's sole queue writer, named explicitly so a role agent reaching for
// this seam casually is refused rather than quietly promoted.
const QUEUE_WRITER = 'conductor';
const VALID_ISSUE_TYPES = new Set(['task', 'bug', 'feature', 'epic']);
const VALID_ISSUE_STATUSES = new Set(['open', 'in_progress', 'closed']);
const PLAN_STATUSES = new Set(['draft', 'approved', 'active', 'done']);
const CREATE_FLAGS = new Set(['--title', '--type', '--priority', '--description', '--labels']);
const UPDATE_FLAGS = new Set(['--status', '--title', '--description', '--priority', '--set-labels', '--add-label', '--remove-label']);
const HELP = 'usage: seeds-launcher.mjs --help | bootstrap --distribution <reviewed-distribution> | inspect --target <repository> (--version | prime | ready [--format json] | blocked [--format json]) | record --target <repository> --queue-writer conductor --expect-queue (absent init | <sha256> (create --title <text> [--type <type>] [--priority <0-4>] [--description <text>] [--labels <list>] | update <id> <recorded-field>...))';
// A help request is a valid query, so it is the ONE argv form that answers at 0. It is exactly one
// of these two spellings and nothing else: `inspect --target X --help` stays a grammar error,
// because a request that also names a verb and a target is not a question about usage.
const HELP_FLAGS = new Set(['--help', '-h']);

// ── Implementation Decision 9's exit vocabulary: this launcher's ONE derivation point ───────────
// Every exit this launcher chooses for itself is a member of this table, and the member is carried
// by the thrown `LauncherError` rather than decided at the throw site, so `reportFailure` is the
// only place a code is produced.
//
//   0 `ok`             a valid query (`--help`) or a closed requested result.
//   1 `internal`       an unexpected internal failure: a throw that is not a `LauncherError`, or an
//                      invariant only a launcher bug can reach.
//   2 `grammar`        a bad verb, a bad flag, a flag value this launcher cannot admit, or a path
//                      the CALLER supplied that is unusable as input. State this launcher itself
//                      recorded and must re-read is not caller input; see 3.
//   3 `refusal`        a clean refusal taken BEFORE any surface moved: the wrong executing Node, a
//                      missing/partial/superseded receipt, tuple or hash drift, a dirty
//                      distribution, an occupied `.seeds`, a compare-and-swap mismatch, or any
//                      prestate this launcher will not write over.
//   4 `effectUnknown`  an admitted partial or unknown effect: the queue writer moved a surface and
//                      this launcher will not vouch for the result. See `admitUnprovenSurface`.
//
// ONE code sits outside that reserved block, named and justified here rather than left implicit.
// On the `inspect` verbs the launcher execs a read-only Seeds child with `stdio: 'inherit'` and
// then reports THE CHILD'S OWN status, so a nonzero inspect exit is Seeds' verdict about the
// target, not this launcher's verdict about the request. `scripts/gate_receipt.py:120-125` forbids
// mirroring a producer's code precisely because it makes the two indistinguishable, and that
// warning applies here in full: an inspect exit of 2, 3, or 4 is the Seeds CLI's number and may
// collide with the three above. It is kept because inspect exists to BE that child --- the
// launcher's whole contribution is the exact runtime and the environment allowlist, and callers
// (`scripts/check-agentic-sdlc-prereqs.sh:45`, which returns `child_status` verbatim) read Seeds'
// own status. The collision is bounded to the inspect verbs: `bootstrap` and `record` translate
// their children's failures into 3 or 4 and never mirror them. Widening the reserved block with a
// named 5 for "the child refused" would be the gate-receipt-shaped fix and is deliberately NOT
// taken here, because it would break every caller that reads Seeds' status through this seam.
const EXITS = Object.freeze({
  ok: 0,
  internal: 1,
  grammar: 2,
  refusal: 3,
  effectUnknown: 4,
});

class LauncherError extends Error {
  // `code` is positional and required. It was a keyword default on the sibling activation planner
  // and 85 named refusals silently inherited it (`docs/plans/decision9-conformance-survey.md`,
  // SP-2), so no spelling here lets a raise site stay silent about its class.
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

// The three classes a raise site may choose, one named spelling each. There is deliberately no
// bare `fail`: the class is part of what a refusal SAYS, so a site that does not state one cannot
// compile a message either.
function failGrammar(message) {
  throw new LauncherError(EXITS.grammar, message);
}

function failRefusal(message) {
  throw new LauncherError(EXITS.refusal, message);
}

function failEffectUnknown(message) {
  throw new LauncherError(EXITS.effectUnknown, message);
}

function failInternal(message) {
  throw new LauncherError(EXITS.internal, message);
}

// ── The effect ledger, and why a raise site's class is a FLOOR rather than the verdict ──────────
// `record`'s two mutating verbs start a queue writer this launcher does not control. From the
// instant that child is spawned the launcher can no longer SAY "nothing happened" without proving
// it, and most of what it does next --- reading the queue back, parsing it, comparing the surface
// --- can itself fail. Those failures are refusals in shape but not in truth, so they are
// escalated rather than reported: `admitUnprovenSurface` is called before the writer starts, every
// refusal raised while it stands reports 4, and only `proveSurfaceUnchanged` --- a COMPLETED
// byte-identical readback of the surface snapshotted before the writer ran --- takes it back down.
// This mirrors the escalate-only ledger `activation-planner.py:2337` derives its effect from, and
// it is why the readback divergence checks need no per-site bookkeeping: whether a refusal is
// pre-effect is a fact about when it happened, not about which message it carries.
let UNPROVEN_SURFACE = null;

function admitUnprovenSurface(description) {
  UNPROVEN_SURFACE = description;
}

function proveSurfaceUnchanged() {
  UNPROVEN_SURFACE = null;
}

function hashBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function hashFile(path) {
  const node = lstatSync(path);
  if (!node.isFile()) failRefusal(`required regular file is unavailable: ${path}`);
  return hashBytes(readFileSync(path));
}

function realDirectory(path, label) {
  let node;
  try {
    node = lstatSync(path);
  } catch {
    failRefusal(`${label} is unavailable: ${path}`);
  }
  if (node.isSymbolicLink() || !node.isDirectory()) failRefusal(`${label} must be a real directory: ${path}`);
  return process.platform === 'win32' ? realpathSync.native(path) : realpathSync(path);
}

// The same resolution for a directory the CALLER named on the command line, where an absent path is
// an unusable supplied input (Decision 9's 2) rather than a refusal about the world (3). That is the
// supplied-but-missing distinction `agentic-sdlc-f83f` drew for a supplied-but-missing manifest; a
// directory this launcher RECORDED and must re-read goes through `realDirectory` and keeps 3,
// because its absence is drift the caller did not type. A path that exists but is a symlink or not a
// directory is state, not spelling, so it stays a 3 from `realDirectory`.
function suppliedDirectory(argument, label) {
  if (typeof argument !== 'string' || argument.length === 0) failGrammar(`${label} requires an exact path`);
  let node;
  try {
    node = lstatSync(argument);
  } catch {
    failGrammar(`${label} is unavailable: ${argument}`);
  }
  if (node.isSymbolicLink() && !existsSync(argument)) failGrammar(`${label} is unavailable: ${argument}`);
  return realDirectory(argument, label);
}

function realRegularFile(path, label) {
  let resolved;
  try {
    resolved = realpathSync(path);
  } catch {
    failRefusal(`${label} is unavailable: ${path}`);
  }
  let node;
  try {
    node = statSync(resolved);
  } catch {
    failRefusal(`${label} is unavailable: ${path}`);
  }
  if (!node.isFile()) failRefusal(`${label} must be a regular file: ${path}`);
  return resolved;
}

function contained(root, candidate, label) {
  const realRoot = realpathSync(root);
  const realCandidate = realpathSync(candidate);
  const boundary = realRoot.endsWith(sep) ? realRoot : `${realRoot}${sep}`;
  if (!(realCandidate === realRoot || realCandidate.startsWith(boundary))) {
    failRefusal(`${label} escapes its reviewed root: ${candidate}`);
  }
  return realCandidate;
}

function containedFile(root, candidate, label) {
  if (!isAbsolute(candidate)) failRefusal(`${label} must be absolute: ${candidate}`);
  const resolved = contained(root, candidate, label);
  return realRegularFile(resolved, label);
}

function treeHash(root) {
  const hasher = createHash('sha256');
  const realRoot = realDirectory(root, 'hash root');
  const walk = (directory) => {
    const entries = readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const path = join(directory, entry.name);
      const rel = relative(realRoot, path).split(sep).join('/');
      const node = lstatSync(path);
      if (node.isDirectory()) {
        hasher.update(`D\0${rel}\0`);
        walk(path);
      } else if (node.isFile()) {
        hasher.update(`F\0${rel}\0`);
        hasher.update(readFileSync(path));
      } else if (node.isSymbolicLink()) {
        hasher.update(`L\0${rel}\0`);
        hasher.update(readlinkSync(path));
      } else {
        failRefusal(`unsupported filesystem node in reviewed tree: ${path}`);
      }
    }
  };
  walk(realRoot);
  return hasher.digest('hex');
}

function distributionTreeHash(root) {
  const hasher = createHash('sha256');
  const realRoot = realDirectory(root, 'distribution root');
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
      if (entry.name === '.git') continue;
      const path = join(directory, entry.name);
      const rel = relative(realRoot, path).split(sep).join('/');
      const node = lstatSync(path);
      if (node.isDirectory()) {
        hasher.update(`D\0${rel}\0`);
        walk(path);
      } else if (node.isFile()) {
        hasher.update(`F\0${rel}\0`);
        hasher.update(readFileSync(path));
      } else if (node.isSymbolicLink()) {
        hasher.update(`L\0${rel}\0`);
        hasher.update(readlinkSync(path));
      } else {
        failRefusal(`unsupported filesystem node in distribution tree: ${path}`);
      }
    }
  };
  walk(realRoot);
  return hasher.digest('hex');
}

function exactVersion(executable, expected, label) {
  const completed = spawnSync(executable, ['--version'], { encoding: 'utf8', shell: false, windowsHide: true, env: {} });
  if (completed.error || completed.status !== 0) failRefusal(`cannot execute exact ${label} version probe`);
  const actual = (completed.stdout || '').trim().replace(/^v/, '');
  if (actual !== expected) failRefusal(`exact ${label} version mismatch: expected ${expected}, got ${actual || 'empty'}`);
}

function pathEntries(value) {
  return (value || '').split(process.platform === 'win32' ? ';' : ':').filter(Boolean);
}

function executableNames(name) {
  if (process.platform !== 'win32') return [name];
  const extensions = (process.env.PATHEXT || '.EXE;.CMD;.BAT;.COM').split(';').filter(Boolean);
  return [name, ...extensions.map((extension) => `${name}${extension.toLowerCase()}`), ...extensions.map((extension) => `${name}${extension.toUpperCase()}`)];
}

function findExecutable(name, label) {
  for (const directory of pathEntries(process.env.PATH)) {
    for (const candidateName of executableNames(name)) {
      const candidate = resolve(directory, candidateName);
      try {
        const node = lstatSync(candidate);
        if (node.isFile() || node.isSymbolicLink()) return realRegularFile(candidate, label);
      } catch {
        // Continue only while resolving this untrusted ambient discovery input.
      }
    }
  }
  failRefusal(`${label} is unavailable on PATH`);
}

function runMise(mise, args, cwd, env) {
  const completed = spawnSync(mise, args, { cwd, encoding: 'utf8', shell: false, windowsHide: true, env });
  if (completed.error || completed.status !== 0) failRefusal(`mise ${args.join(' ')} failed: ${(completed.stderr || completed.error?.message || '').trim()}`);
  return (completed.stdout || '').trim();
}

function parsePackage(path) {
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    failRefusal(`cannot parse Seeds package metadata: ${error.message}`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) failRefusal('Seeds package metadata must be an object');
  return parsed;
}

function packageHasExecutionControl(value, ancestors = []) {
  if (Array.isArray(value)) return value.some((nested) => packageHasExecutionControl(nested, ancestors));
  if (!value || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, nested]) => {
    const lowered = key.toLowerCase();
    const compatibilityBun = lowered === 'bun' && ancestors.length === 1 && ancestors[0] === 'engines' && typeof nested === 'string';
    return (!compatibilityBun && FORBIDDEN_PACKAGE_KEYS.has(lowered)) || packageHasExecutionControl(nested, [...ancestors, lowered]);
  });
}

function packageControlFile(name) {
  const lowered = name.toLowerCase();
  if (FORBIDDEN_PACKAGE_FILES.has(lowered)) return true;
  const dot = lowered.indexOf('.');
  const stem = dot === -1 ? lowered : lowered.slice(0, dot);
  return FORBIDDEN_PACKAGE_STEMS.has(stem);
}

function rejectPackageControlFiles(packageRoot) {
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === 'node_modules') continue;
      const path = join(directory, entry.name);
      const node = lstatSync(path);
      if (packageControlFile(entry.name)) failRefusal(`Seeds package contains prohibited execution control: ${relative(packageRoot, path).split(sep).join('/')}`);
      if (node.isDirectory()) walk(path);
      else if (node.isFile() && entry.name.toLowerCase() === 'package.json' && !samePath(path, join(packageRoot, 'package.json')) && packageHasExecutionControl(parsePackage(path))) {
        failRefusal(`Seeds package contains prohibited execution control: ${relative(packageRoot, path).split(sep).join('/')}`);
      }
    }
  };
  walk(packageRoot);
}

function packageRootFor(seedsRoot) {
  const variants = process.platform === 'win32'
    ? [join(seedsRoot, 'node_modules', '@os-eco', 'seeds-cli'), join(seedsRoot, 'lib', 'node_modules', '@os-eco', 'seeds-cli')]
    : [join(seedsRoot, 'lib', 'node_modules', '@os-eco', 'seeds-cli')];
  for (const variant of variants) {
    try {
      return realDirectory(variant, 'Seeds package root');
    } catch {
      // Each platform has an explicit, finite expected layout list.
    }
  }
  failRefusal('Seeds package root is unavailable in the expected platform layout');
}

function expectedBinary(root, kind) {
  const paths = process.platform === 'win32'
    ? { node: join(root, 'node.exe'), bun: join(root, 'bin', 'bun.exe'), seeds: join(root, 'sd.cmd') }
    : { node: join(root, 'bin', 'node'), bun: join(root, 'bin', 'bun'), seeds: join(root, 'bin', 'sd') };
  return containedFile(root, paths[kind], `exact ${kind} platform entry`);
}

function validateTuple(roots) {
  const nodeRoot = realDirectory(roots.node, 'exact Node root');
  const bunRoot = realDirectory(roots.bun, 'exact Bun root');
  const seedsRoot = realDirectory(roots.seeds, 'exact Seeds root');
  const node = expectedBinary(nodeRoot, 'node');
  const bun = expectedBinary(bunRoot, 'bun');
  expectedBinary(seedsRoot, 'seeds');
  exactVersion(node, NODE_VERSION, 'Node');
  exactVersion(bun, BUN_VERSION, 'Bun');
  const packageRoot = packageRootFor(seedsRoot);
  const packageJson = join(packageRoot, 'package.json');
  const metadata = parsePackage(packageJson);
  if (metadata.name !== SEEDS_PACKAGE || metadata.version !== SEEDS_VERSION) {
    failRefusal(`Seeds package mismatch: expected ${SEEDS_PACKAGE}@${SEEDS_VERSION}`);
  }
  if (!metadata.bin || typeof metadata.bin !== 'object' || Array.isArray(metadata.bin) || typeof metadata.bin[SEEDS_BIN] !== 'string') {
    failRefusal('Seeds package must define the exact sd bin');
  }
  const binValue = metadata.bin[SEEDS_BIN];
  if (isAbsolute(binValue) || binValue.split(/[\\/]+/).includes('..')) failRefusal('Seeds package bin escapes its package root');
  if (packageHasExecutionControl(metadata)) failRefusal('Seeds package declares prohibited execution control');
  rejectPackageControlFiles(packageRoot);
  const entry = containedFile(packageRoot, resolve(packageRoot, binValue), 'Seeds bin entry');
  return { nodeRoot, bunRoot, seedsRoot, node, bun, packageRoot, packageJson: realRegularFile(packageJson, 'Seeds package metadata'), entry, binValue };
}

function stateBase() {
  if (process.platform === 'win32') {
    return resolve(process.env.LOCALAPPDATA || join(process.env.USERPROFILE || process.env.HOME || '.', 'AppData', 'Local'));
  }
  return resolve(process.env.XDG_STATE_HOME || join(process.env.HOME || '.', '.local', 'state'));
}

function ensurePrivateDirectory(path) {
  const destination = resolve(path);
  const parent = dirname(destination);
  if (parent !== destination) {
    if (!existsSync(parent)) ensurePrivateDirectory(parent);
    const parentNode = lstatSync(parent);
    if (parentNode.isSymbolicLink() || !parentNode.isDirectory()) failRefusal(`state path is not a real directory: ${parent}`);
  }
  if (!existsSync(destination)) mkdirSync(destination, { mode: 0o700 });
  const node = lstatSync(destination);
  if (node.isSymbolicLink() || !node.isDirectory()) failRefusal(`state path is not a real directory: ${destination}`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal(`state path is not owned by this user: ${destination}`);
  if (process.platform !== 'win32') chmodSync(destination, 0o700);
}

function fsyncDirectory(path) {
  if (process.platform === 'win32') return;
  let descriptor;
  try {
    descriptor = openSync(path, 'r');
    fsyncSync(descriptor);
  } catch {
    failRefusal(`cannot persist state directory: ${path}`);
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
  }
}

function atomicWrite(path, text) {
  const parent = dirname(path);
  ensurePrivateDirectory(parent);
  const temporary = join(parent, `.${normalize(path).split(sep).pop()}.${randomBytes(12).toString('hex')}.tmp`);
  let descriptor;
  try {
    descriptor = openSync(temporary, 'wx', 0o600);
    writeFileSync(descriptor, text, 'utf8');
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    renameSync(temporary, path);
    fsyncDirectory(parent);
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
    try { unlinkSync(temporary); } catch {}
  }
}

function existingTrustedEmptyFile(path, name) {
  let node;
  try {
    node = lstatSync(path);
  } catch {
    failRefusal(`trusted ${name} is unavailable`);
  }
  if (node.isSymbolicLink() || !node.isFile() || node.size !== 0) failRefusal(`trusted ${name} must be an owned empty regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal(`trusted ${name} is not owned by this user`);
  return realRegularFile(path, `trusted ${name}`);
}

function existingTrustedJsonFile(path, name) {
  const bytes = Buffer.from('{}\n', 'utf8');
  let node;
  try {
    node = lstatSync(path);
  } catch {
    failRefusal(`trusted ${name} is unavailable`);
  }
  if (node.isSymbolicLink() || !node.isFile() || node.size !== bytes.length || !readFileSync(path).equals(bytes)) failRefusal(`trusted ${name} must be an owned inert JSON regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal(`trusted ${name} is not owned by this user`);
  return realRegularFile(path, `trusted ${name}`);
}

function trustedEmptyFile(directory, name) {
  const path = join(directory, name);
  if (!existsSync(path)) {
    let descriptor;
    try {
      descriptor = openSync(path, 'wx', 0o600);
      fsyncSync(descriptor);
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
    }
    fsyncDirectory(directory);
  }
  const node = lstatSync(path);
  if (node.isSymbolicLink() || !node.isFile() || node.size !== 0) failRefusal(`trusted ${name} must be an owned empty regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal(`trusted ${name} is not owned by this user`);
  if (process.platform !== 'win32') chmodSync(path, 0o600);
  return realRegularFile(path, `trusted ${name}`);
}

function receiptDirectory() {
  const path = join(stateBase(), 'agentic-sdlc', 'seeds-runtime', `v${SCHEMA}`);
  ensurePrivateDirectory(path);
  return path;
}

function capture(git, args, message, env, input) {
  const completed = spawnSync(git, args, { encoding: 'utf8', shell: false, windowsHide: true, env, input });
  if (completed.error || completed.status !== 0) failRefusal(message);
  return (completed.stdout || '').trim();
}

function captureBytes(git, args, message, env) {
  const completed = spawnSync(git, args, { shell: false, windowsHide: true, env });
  if (completed.error || completed.status !== 0) failRefusal(message);
  return completed.stdout;
}

function samePath(left, right) {
  const normalized = (path) => process.platform === 'win32' ? path.toLowerCase() : path;
  return normalized(left) === normalized(right);
}

function gitEnvironment(gitDirectory, workTree, objectDirectory, indexFile) {
  const inertConfig = process.platform === 'win32' ? 'NUL' : '/dev/null';
  return Object.freeze({
    PATH: dirname(gitDirectory),
    GIT_DIR: gitDirectory,
    GIT_WORK_TREE: workTree,
    GIT_OBJECT_DIRECTORY: objectDirectory,
    GIT_INDEX_FILE: indexFile,
    GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_SYSTEM: inertConfig,
    GIT_CONFIG_GLOBAL: inertConfig,
    GIT_OPTIONAL_LOCKS: '0',
    GIT_TERMINAL_PROMPT: '0',
  });
}

function rawRegularFile(path, label) {
  let node;
  try {
    node = lstatSync(path);
  } catch {
    failRefusal(`${label} is unavailable: ${path}`);
  }
  if (node.isSymbolicLink() || !node.isFile()) failRefusal(`${label} must be a regular file: ${path}`);
  return path;
}

function metadataLine(path, label) {
  const file = rawRegularFile(path, label);
  const bytes = readFileSync(file, 'utf8');
  const line = bytes.endsWith('\n') ? bytes.slice(0, -1).replace(/\r$/, '') : bytes;
  if (!line || line.includes('\n') || line.includes('\0')) failRefusal(`${label} is invalid: ${path}`);
  return line;
}

function metadataDirectory(path, label) {
  return realDirectory(path, label);
}

function referencedGitDirectory(distribution) {
  const marker = join(distribution, '.git');
  let node;
  try {
    node = lstatSync(marker);
  } catch {
    failRefusal(`reviewed distribution must be an exact Git root: ${distribution}`);
  }
  if (node.isDirectory()) return metadataDirectory(marker, 'reviewed distribution Git directory');
  if (!node.isFile() || node.isSymbolicLink()) failRefusal(`reviewed distribution must be an exact Git root: ${distribution}`);
  const reference = metadataLine(marker, 'reviewed distribution Git directory reference');
  if (!reference.startsWith('gitdir: ')) failRefusal(`reviewed distribution must be an exact Git root: ${distribution}`);
  const location = reference.slice('gitdir: '.length);
  if (!location) failRefusal(`reviewed distribution must be an exact Git root: ${distribution}`);
  return metadataDirectory(isAbsolute(location) ? location : resolve(dirname(marker), location), 'reviewed distribution Git directory');
}

function commonGitDirectory(source) {
  const marker = join(source, 'commondir');
  if (!existsSync(marker)) return source;
  const location = metadataLine(marker, 'reviewed distribution common Git directory');
  return metadataDirectory(isAbsolute(location) ? location : resolve(source, location), 'reviewed distribution common Git directory');
}

function refPath(directory, reference) {
  if (!reference.startsWith('refs/') || reference.includes('\0') || reference.split('/').some((part) => !part || part === '.' || part === '..')) {
    failRefusal('reviewed distribution has an invalid Git reference');
  }
  return join(directory, reference);
}

function looseReference(reference, directories) {
  for (const directory of directories) {
    const candidate = refPath(directory, reference);
    if (existsSync(candidate)) return metadataLine(candidate, 'reviewed distribution Git reference');
  }
  return null;
}

function packedReference(reference, directories) {
  for (const directory of directories) {
    const path = join(directory, 'packed-refs');
    if (!existsSync(path)) continue;
    const file = rawRegularFile(path, 'reviewed distribution packed references');
    for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const match = line.match(/^([0-9a-f]{40}|[0-9a-f]{64}) (refs\/[^\s]+)$/);
      if (match && match[2] === reference) return match[1];
    }
  }
  return null;
}

function exactHeadCommit(source, common) {
  const directories = [...new Set([source, common])];
  let value = metadataLine(join(source, 'HEAD'), 'reviewed distribution HEAD');
  for (let redirects = 0; redirects < 8; redirects += 1) {
    if (/^[0-9a-f]{40}$|^[0-9a-f]{64}$/.test(value)) return value;
    if (!value.startsWith('ref: ')) failRefusal('reviewed distribution HEAD must resolve to an exact commit');
    const reference = value.slice('ref: '.length);
    value = looseReference(reference, directories) || packedReference(reference, directories) || '';
  }
  failRefusal('reviewed distribution HEAD must resolve to an exact commit');
}

function gitMetadata(distribution) {
  const source = referencedGitDirectory(distribution);
  const common = commonGitDirectory(source);
  const objects = metadataDirectory(join(common, 'objects'), 'reviewed distribution object directory');
  const index = rawRegularFile(join(source, 'index'), 'reviewed distribution index');
  return { objects, index, head: exactHeadCommit(source, common) };
}

function sandboxGitDistribution(distribution) {
  const metadata = gitMetadata(distribution);
  const sandbox = join(receiptDirectory(), `git-admission-${randomBytes(12).toString('hex')}`);
  mkdirSync(join(sandbox, 'objects'), { mode: 0o700, recursive: true });
  mkdirSync(join(sandbox, 'refs'), { mode: 0o700, recursive: true });
  try {
    writeFileSync(join(sandbox, 'HEAD'), `${metadata.head}\n`, { mode: 0o600 });
    writeFileSync(
      join(sandbox, 'config'),
      `[core]\nrepositoryformatversion = 0\nbare = false\n${metadata.head.length === 64 ? '\n[extensions]\nobjectformat = sha256\n' : ''}`,
      { mode: 0o600 },
    );
    return {
      directory: realDirectory(sandbox, 'Git admission sandbox'),
      environment: gitEnvironment(sandbox, distribution, metadata.objects, metadata.index),
    };
  } catch (error) {
    rmSync(sandbox, { force: true, recursive: true });
    throw error;
  }
}

function gitDistribution(distribution) {
  const git = findExecutable('git', 'Git');
  const admission = sandboxGitDistribution(distribution);
  try {
    const environment = admission.environment;
    const commit = capture(git, ['rev-parse', '--verify', 'HEAD^{commit}'], 'reviewed distribution must have an exact Git commit', environment);
    const expectedTree = capture(git, ['rev-parse', '--verify', 'HEAD^{tree}'], 'reviewed distribution must have an exact Git tree', environment);
    const indexTree = capture(git, ['write-tree'], 'reviewed distribution index must match its exact Git tree', environment);
    if (indexTree !== expectedTree) failRefusal('reviewed distribution must have a clean Git tree and index');
    const indexed = captureBytes(git, ['ls-files', '--stage', '-z'], 'cannot enumerate indexed distribution files', environment);
    for (const record of indexed.toString('utf8').split('\0')) {
      if (!record) continue;
      const separator = record.indexOf('\t');
      const metadata = separator === -1 ? [] : record.slice(0, separator).split(' ');
      const path = separator === -1 ? '' : record.slice(separator + 1);
      if (metadata.length !== 3 || !/^[0-7]{6}$/.test(metadata[0]) || !/^[0-9a-f]{40,64}$/.test(metadata[1]) || metadata[2] !== '0' || !path) failRefusal('reviewed distribution index is not an exact ordinary file tree');
      let bytes;
      try {
        bytes = readFileSync(join(distribution, path));
      } catch {
        failRefusal('reviewed distribution must have a clean Git tree and index');
      }
      const actual = capture(git, ['hash-object', '--no-filters', '--stdin'], 'cannot hash tracked distribution file', environment, bytes);
      if (actual !== metadata[1]) failRefusal('reviewed distribution must have a clean Git tree and index');
    }
    const untracked = capture(git, ['ls-files', '--others', '--exclude-standard'], 'cannot enumerate untracked distribution files', environment);
    const ignored = capture(git, ['ls-files', '--others', '--ignored', '--exclude-standard'], 'cannot enumerate ignored distribution files', environment);
    if (untracked || ignored) failRefusal('reviewed distribution must contain no untracked or ignored files');
    return { path: git, hash: hashFile(git), commit, tree: expectedTree };
  } finally {
    rmSync(admission.directory, { force: true, recursive: true });
  }
}

function bootstrapPath(mise) {
  const platform = process.platform === 'win32'
    ? [join(resolve(process.env.SystemRoot || 'C:\\Windows'), 'System32'), resolve(process.env.SystemRoot || 'C:\\Windows')]
    : ['/usr/bin', '/bin'];
  return [dirname(mise), ...platform].join(process.platform === 'win32' ? ';' : ':');
}

function bootstrapEnvironment(distribution, directory, mise) {
  const home = join(directory, 'bootstrap-home');
  ensurePrivateDirectory(home);
  const userconfig = trustedEmptyFile(directory, 'bootstrap-user.npmrc');
  const globalconfig = trustedEmptyFile(directory, 'bootstrap-global.npmrc');
  return Object.freeze({
    HOME: home,
    USERPROFILE: home,
    PATH: bootstrapPath(mise),
    MISE_DATA_DIR: join(directory, 'bootstrap-mise-data'),
    MISE_CACHE_DIR: join(directory, 'bootstrap-mise-cache'),
    MISE_GLOBAL_CONFIG_FILE: join(distribution, 'mise.toml'),
    MISE_SYSTEM_CONFIG_FILE: process.platform === 'win32' ? 'NUL' : '/dev/null',
    MISE_OVERRIDE_CONFIG_FILENAMES: MISE_CONFIG_SENTINEL,
    MISE_NO_ENV: '1',
    MISE_NO_HOOKS: '1',
    MISE_NPM_PACKAGE_MANAGER: 'npm',
    NPM_CONFIG_REGISTRY: NPM_REGISTRY,
    NPM_CONFIG_USERCONFIG: userconfig,
    NPM_CONFIG_GLOBALCONFIG: globalconfig,
    NPM_CONFIG_STRICT_SSL: 'true',
  });
}

function exactLauncherNode() {
  if (process.versions.node !== NODE_VERSION) failRefusal(`launcher Node version mismatch: expected ${NODE_VERSION}, got ${process.versions.node}`);
}

function currentLauncher() {
  return realRegularFile(fileURLToPath(import.meta.url), 'current installed launcher');
}

function trustedEmptyJsonFile(directory, name) {
  const path = join(directory, name);
  const bytes = Buffer.from('{}\n', 'utf8');
  if (!existsSync(path)) {
    let descriptor;
    try {
      descriptor = openSync(path, 'wx', 0o600);
      writeFileSync(descriptor, bytes);
      fsyncSync(descriptor);
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
    }
    fsyncDirectory(directory);
  }
  const node = lstatSync(path);
  if (node.isSymbolicLink() || !node.isFile() || node.size !== bytes.length || !readFileSync(path).equals(bytes)) failRefusal(`trusted ${name} must be an owned inert JSON regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal(`trusted ${name} is not owned by this user`);
  if (process.platform !== 'win32') chmodSync(path, 0o600);
  return realRegularFile(path, `trusted ${name}`);
}

function posixGitAdapterContent(git) {
  const quote = (value) => `'${value.replaceAll("'", `'"'"'`)}'`;
  return `#!/bin/sh\nif [ "$1" != rev-parse ]; then exit 64; fi\nif [ "$#" -eq 2 ]; then\n  case "$2" in --git-common-dir|--git-dir) ;; *) exit 64 ;; esac\nelif [ "$#" -eq 3 ] && [ "$2" = --verify ] && [ "$3" = 'HEAD^{commit}' ]; then\n  :\nelse\n  exit 64\nfi\nshift\nexec ${quote(git)} -c core.fsmonitor=false -c core.hooksPath=/dev/null rev-parse "$@"\n`;
}

function windowsGitAdapterSource(git) {
  return `const args = process.argv.slice(2);\nconst metadata = args.length === 2 && args[0] === 'rev-parse' && ['--git-dir', '--git-common-dir'].includes(args[1]);\nconst head = args.length === 3 && args[0] === 'rev-parse' && args[1] === '--verify' && args[2] === 'HEAD^{commit}';\nif (!metadata && !head) process.exit(64);\nconst child = Bun.spawnSync([${JSON.stringify(git)}, '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL', ...args], { cwd: process.cwd(), env: process.env });\nprocess.stdout.write(child.stdout);\nprocess.stderr.write(child.stderr);\nprocess.exit(child.exitCode ?? 1);\n`;
}

function compileWindowsGitAdapter(directory, git, bun, bunfig, tsconfig) {
  const build = join(directory, 'git-adapter-build');
  if (existsSync(build)) failRefusal('trusted Git adapter build directory already exists');
  mkdirSync(build, { mode: 0o700 });
  try {
    const source = join(build, 'adapter.ts');
    const output = join(build, 'git.exe');
    writeFileSync(source, windowsGitAdapterSource(git), { encoding: 'utf8', mode: 0o600 });
    const completed = spawnSync(bun, [
      `--config=${bunfig}`,
      '--no-env-file',
      '--no-install',
      '--no-macros',
      `--tsconfig-override=${tsconfig}`,
      'build',
      '--compile',
      `--compile-executable-path=${bun}`,
      '--no-compile-autoload-dotenv',
      '--no-compile-autoload-bunfig',
      '--no-compile-autoload-tsconfig',
      '--no-compile-autoload-package-json',
      `--outfile=${output}`,
      source,
    ], { cwd: build, env: {}, encoding: 'utf8', shell: false, windowsHide: true });
    if (completed.error || completed.status !== 0) failRefusal(`cannot compile trusted Git adapter: ${(completed.stderr || completed.error?.message || '').trim()}`);
    const adapter = realRegularFile(output, 'compiled Git adapter');
    const destination = join(directory, 'git.exe');
    if (existsSync(destination)) {
      const existing = existingTrustedAdapter(destination, git);
      if (hashFile(existing) !== hashFile(adapter)) failRefusal('existing trusted Git adapter does not match exact compiled bytes');
      return existing;
    }
    renameSync(adapter, destination);
    fsyncDirectory(directory);
    return realRegularFile(destination, 'trusted Git adapter');
  } finally {
    rmSync(build, { force: true, recursive: true });
  }
}

function trustedGitAdapter(directory, git, bun, bunfig, tsconfig) {
  if (process.platform === 'win32') return compileWindowsGitAdapter(directory, git, bun, bunfig, tsconfig);
  const path = join(directory, 'git');
  const content = posixGitAdapterContent(git);
  if (!existsSync(path)) {
    let descriptor;
    try {
      descriptor = openSync(path, 'wx', 0o700);
      writeFileSync(descriptor, content, 'utf8');
      fsyncSync(descriptor);
    } finally {
      if (descriptor !== undefined) closeSync(descriptor);
    }
    fsyncDirectory(directory);
  }
  const node = lstatSync(path);
  if (node.isSymbolicLink() || !node.isFile() || readFileSync(path, 'utf8') !== content) failRefusal('trusted Git adapter must be an exact owned regular file');
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal('trusted Git adapter is not owned by this user');
  if (process.platform !== 'win32') chmodSync(path, 0o700);
  return realRegularFile(path, 'trusted Git adapter');
}

function existingTrustedAdapter(path, git) {
  const node = lstatSync(path);
  if (node.isSymbolicLink() || !node.isFile() || (process.platform !== 'win32' && readFileSync(path, 'utf8') !== posixGitAdapterContent(git))) failRefusal('trusted Git adapter must be an exact regular file');
  if (process.platform !== 'win32' && node.uid !== process.getuid()) failRefusal('trusted Git adapter is not owned by this user');
  return realRegularFile(path, 'trusted Git adapter');
}

function bootstrap(distributionArgument) {
  const distribution = suppliedDirectory(distributionArgument, 'reviewed distribution');
  const miseToml = containedFile(distribution, join(distribution, 'mise.toml'), 'reviewed mise.toml');
  const miseLock = containedFile(distribution, join(distribution, 'mise.lock'), 'reviewed mise.lock');
  const git = gitDistribution(distribution);
  const directory = receiptDirectory();
  const mise = findExecutable('mise', 'mise');
  const miseEnvironment = bootstrapEnvironment(distribution, directory, mise);
  runMise(mise, ['--locked', 'install'], miseEnvironment.HOME, miseEnvironment);
  const roots = {
    node: runMise(mise, ['--no-config', 'where', TOOL_NAMES.node], miseEnvironment.HOME, miseEnvironment),
    bun: runMise(mise, ['--no-config', 'where', TOOL_NAMES.bun], miseEnvironment.HOME, miseEnvironment),
    seeds: runMise(mise, ['--no-config', 'where', TOOL_NAMES.seeds], miseEnvironment.HOME, miseEnvironment),
  };
  if (!Object.values(roots).every((value) => isAbsolute(value))) failRefusal('mise must return absolute exact tool roots');
  const tuple = validateTuple(roots);
  const launcher = currentLauncher();
  const bunfig = trustedEmptyFile(directory, 'trusted-bunfig.toml');
  const tsconfig = trustedEmptyJsonFile(directory, 'trusted-tsconfig.json');
  const gitconfig = trustedEmptyFile(directory, 'trusted-gitconfig');
  const gitAdapter = trustedGitAdapter(directory, git.path, tuple.bun, bunfig, tsconfig);
  const distributionHashes = { tree: distributionTreeHash(distribution), gitTree: git.tree, miseToml: hashFile(miseToml), miseLock: hashFile(miseLock), commit: hashBytes(Buffer.from(git.commit, 'utf8')) };
  const runtime = { node: realRegularFile(process.execPath, 'executing Node'), nodeHash: hashFile(realRegularFile(process.execPath, 'executing Node')), launcherHash: hashFile(launcher) };
  const receipt = {
    schema: SCHEMA,
    platform: process.platform,
    createdAt: new Date().toISOString(),
    distribution: { root: distribution, commit: git.commit, gitTree: git.tree, tree: distributionHashes.tree, miseToml: distributionHashes.miseToml, miseLock: distributionHashes.miseLock, launcher, launcherHash: hashFile(launcher) },
    runtime,
    tuple: {
      node: { root: tuple.nodeRoot, executable: tuple.node, version: NODE_VERSION },
      bun: { root: tuple.bunRoot, executable: tuple.bun, version: BUN_VERSION },
      seeds: { root: tuple.seedsRoot, packageRoot: tuple.packageRoot, package: SEEDS_PACKAGE, version: SEEDS_VERSION, bin: SEEDS_BIN, binValue: tuple.binValue, entry: tuple.entry },
      git,
      trusted: { bunfig, tsconfig, gitconfig, gitAdapter },
    },
    hashes: {
      distribution: distributionHashes,
      node: treeHash(tuple.nodeRoot),
      nodeExecutable: hashFile(tuple.node),
      bun: treeHash(tuple.bunRoot),
      seeds: treeHash(tuple.seedsRoot),
      packageJson: hashFile(tuple.packageJson),
      entry: hashFile(tuple.entry),
      git: hashFile(git.path),
      gitAdapter: hashFile(gitAdapter),
      bunfig: hashFile(bunfig),
      tsconfig: hashFile(tsconfig),
      gitconfig: hashFile(gitconfig),
    },
  };
  const active = join(directory, 'active.json');
  const retained = join(directory, 'previous.json');
  let superseded;
  if (existsSync(active)) {
    // Validate shape and internal consistency before retaining as rollback material; malformed
    // partial state is never repaired. A structurally intact predecessor that records a superseded
    // tuple is retained and named here instead of refused, because a pin bump is the one expected
    // reason a prior receipt disagrees with this launcher's constants and publishing the new tuple is
    // precisely this verb's job. Every other verb still refuses that receipt.
    const previous = loadReceipt(active, TUPLE_PINS_SUPERSEDED);
    superseded = supersededTupleDescription(previous);
    atomicWrite(retained, `${JSON.stringify(previous, null, 2)}\n`);
  }
  atomicWrite(active, `${JSON.stringify(receipt, null, 2)}\n`);
  if (superseded !== undefined) process.stdout.write(`superseded prior tuple receipt (${superseded}) retained for rollback: ${retained}\n`);
  process.stdout.write(`bootstrapped locked Seeds tuple receipt: ${active}\n`);
}

function rendered(value) {
  // JSON.stringify quotes the value and escapes the C0 controls; the explicit pass also escapes DEL
  // and the C1 range, so no byte a receipt records can inject or terminate a line of this output.
  return JSON.stringify(value).replace(/[\u007f-\u009f]/gu, (character) => `\\u${character.codePointAt(0).toString(16).padStart(4, '0')}`);
}

function supersededTupleDescription(previous) {
  // Only a recorded tuple that DIFFERS from this launcher's constants is a supersession worth
  // naming; an ordinary re-bootstrap of the same tuple retains its predecessor exactly as before.
  const { node, bun, seeds } = previous.tuple;
  if (node.version === NODE_VERSION && bun.version === BUN_VERSION && seeds.package === SEEDS_PACKAGE && seeds.version === SEEDS_VERSION && seeds.bin === SEEDS_BIN) return undefined;
  return `node ${rendered(node.version)}, bun ${rendered(bun.version)}, ${rendered(seeds.package)} ${rendered(seeds.version)}, bin ${rendered(seeds.bin)}`;
}

function object(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function text(value) {
  return typeof value === 'string' && value.length > 0;
}

function exactKeys(value, keys) {
  if (!object(value)) return false;
  const actual = Object.keys(value);
  return actual.length === keys.size && actual.every((key) => keys.has(key));
}

function receiptPath() {
  return join(stateBase(), 'agentic-sdlc', 'seeds-runtime', `v${SCHEMA}`, 'active.json');
}

function loadReceipt(path = receiptPath(), pins = TUPLE_PINS_CURRENT) {
  if (pins !== TUPLE_PINS_CURRENT && pins !== TUPLE_PINS_SUPERSEDED) failInternal('tuple pin admission mode is unknown');
  const current = pins === TUPLE_PINS_CURRENT;
  let receipt;
  let receiptNode;
  try {
    receiptNode = lstatSync(path);
    if (receiptNode.isSymbolicLink() || !receiptNode.isFile() || (process.platform !== 'win32' && receiptNode.uid !== process.getuid())) failRefusal(`active tuple receipt is missing or corrupt: ${path}`);
    receipt = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    if (error instanceof LauncherError) throw error;
    failRefusal(`active tuple receipt is missing or corrupt: ${path}`);
  }
  if (!exactKeys(receipt, RECEIPT_KEYS) || receipt.schema !== SCHEMA || receipt.platform !== process.platform || !text(receipt.createdAt)
    || !exactKeys(receipt.distribution, DISTRIBUTION_KEYS) || !exactKeys(receipt.runtime, RUNTIME_KEYS) || !exactKeys(receipt.tuple, TUPLE_KEYS) || !exactKeys(receipt.hashes, HASH_KEYS)
    || !exactKeys(receipt.hashes.distribution, DISTRIBUTION_HASH_KEYS)) {
    failRefusal('active tuple receipt is partial or invalid');
  }
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  const distribution = receipt.distribution;
  const runtime = receipt.runtime;
  const distributionHashes = receipt.hashes.distribution;
  if (!exactKeys(node, NODE_KEYS) || !exactKeys(bun, BUN_KEYS) || !exactKeys(seeds, SEEDS_KEYS) || !exactKeys(git, GIT_KEYS) || !exactKeys(trusted, TRUSTED_KEYS)
    // Recorded, non-empty, and typed in BOTH modes; equal to this launcher's constants only when the
    // caller intends to run the recorded tuple. A missing or blank version is malformed either way.
    || ![node.version, bun.version, seeds.package, seeds.version, seeds.bin].every(text)
    || (current && (node.version !== NODE_VERSION || bun.version !== BUN_VERSION || seeds.package !== SEEDS_PACKAGE || seeds.version !== SEEDS_VERSION || seeds.bin !== SEEDS_BIN))
    || ![node.root, node.executable, bun.root, bun.executable, seeds.root, seeds.packageRoot, seeds.binValue, seeds.entry, git.path, git.hash, git.commit, git.tree, trusted.bunfig, trusted.tsconfig, trusted.gitconfig, trusted.gitAdapter].every(text)
    || ![distribution.root, distribution.commit, distribution.gitTree, distribution.tree, distribution.miseToml, distribution.miseLock, distribution.launcher, distribution.launcherHash].every(text)
    || ![runtime.node, runtime.nodeHash, runtime.launcherHash].every(text)
    || ![distributionHashes.tree, distributionHashes.gitTree, distributionHashes.miseToml, distributionHashes.miseLock, distributionHashes.commit].every(text)
    || runtime.nodeHash !== receipt.hashes.nodeExecutable || runtime.launcherHash !== distribution.launcherHash
    || distribution.commit !== git.commit || distribution.gitTree !== git.tree
    || distribution.tree !== distributionHashes.tree || distribution.miseToml !== distributionHashes.miseToml || distribution.miseLock !== distributionHashes.miseLock
    || distributionHashes.commit !== hashBytes(Buffer.from(distribution.commit, 'utf8'))
    || samePath(distribution.root, distribution.launcher)) {
    failRefusal('active tuple receipt is partial or invalid');
  }
  return receipt;
}

function checkCurrentReceipt(receipt) {
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  const expected = receipt.hashes;
  if (![expected.node, expected.nodeExecutable, expected.bun, expected.seeds, expected.packageJson, expected.entry, expected.git, expected.gitAdapter, expected.bunfig, expected.tsconfig, expected.gitconfig].every(text)) failRefusal('active tuple receipt is partial or invalid');
  const tuple = validateTuple({ node: node.root, bun: bun.root, seeds: seeds.root });
  if (tuple.node !== node.executable || tuple.bun !== bun.executable || tuple.packageRoot !== seeds.packageRoot || tuple.binValue !== seeds.binValue || tuple.entry !== seeds.entry) failRefusal('active tuple receipt does not match exact platform layout');
  const executingNode = realRegularFile(process.execPath, 'executing Node');
  if (!samePath(executingNode, receipt.runtime.node) || hashFile(executingNode) !== expected.nodeExecutable) failRefusal('executing Node does not match exact recorded Node');
  if (treeHash(node.root) !== expected.node || treeHash(bun.root) !== expected.bun || treeHash(seeds.root) !== expected.seeds || hashFile(tuple.packageJson) !== expected.packageJson || hashFile(tuple.entry) !== expected.entry) failRefusal('exact tuple hash drift detected');
  if (realRegularFile(git.path, 'recorded Git executable') !== git.path || hashFile(git.path) !== expected.git || hashFile(git.path) !== git.hash) failRefusal('recorded Git executable hash drift detected');
  const launcher = currentLauncher();
  if (!samePath(launcher, receipt.distribution.launcher) || hashFile(launcher) !== receipt.distribution.launcherHash) failRefusal('current installed launcher identity or hash drift detected');
  const bunfig = existingTrustedEmptyFile(trusted.bunfig, 'trusted-bunfig.toml');
  const tsconfig = existingTrustedJsonFile(trusted.tsconfig, 'trusted-tsconfig.json');
  const gitconfig = existingTrustedEmptyFile(trusted.gitconfig, 'trusted-gitconfig');
  const gitAdapter = existingTrustedAdapter(trusted.gitAdapter, git.path);
  if (bunfig !== trusted.bunfig || tsconfig !== trusted.tsconfig || gitconfig !== trusted.gitconfig || gitAdapter !== trusted.gitAdapter
    || hashFile(bunfig) !== expected.bunfig || hashFile(tsconfig) !== expected.tsconfig || hashFile(gitconfig) !== expected.gitconfig
    || hashFile(gitAdapter) !== expected.gitAdapter) failRefusal('trusted configuration hash drift detected');
  return { ...tuple, bunfig, tsconfig, gitconfig, gitAdapter };
}

function grammar(values) {
  if (values.length === 1 && values[0] === '--version') return values;
  if (values.length === 1 && values[0] === 'prime') return values;
  if ((values[0] === 'ready' || values[0] === 'blocked') && (values.length === 1 || (values.length === 3 && values[1] === '--format' && values[2] === 'json'))) return values;
  failGrammar('Seeds inspect accepts only --version, prime, ready [--format json], or blocked [--format json]');
}

function inspect(targetArgument, values) {
  const args = grammar(values); // Parse every allowed form before inspecting any executable.
  const target = suppliedDirectory(targetArgument, 'Seeds target');
  const tuple = checkCurrentReceipt(loadReceipt());
  const child = spawn(tuple.bun, seedsArguments(tuple, args), {
    cwd: target,
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: 'inherit',
    windowsHide: true,
  });
  child.once('error', (error) => {
    // The child never started, so this is the launcher's own clean refusal before any effect, not
    // the child's verdict: it is the one nonzero inspect exit the launcher chooses for itself.
    process.stderr.write(`cannot start exact Seeds Bun entry: ${error.message}\n`);
    process.exitCode = EXITS.refusal;
  });
  child.once('close', (code, signal) => {
    // THE CHILD'S OWN STATUS, deliberately and only here. See the `EXITS` table's named exception:
    // inspect exists to be this read-only child, and its callers read Seeds' verdict about the
    // target. A code that never arrived with no signal is not the child's answer, so it becomes the
    // launcher's own internal failure rather than a fabricated success.
    if (signal) process.kill(process.pid, signal);
    else process.exitCode = code === null ? EXITS.internal : code;
  });
}

function seedsEnvironment(tuple) {
  return Object.freeze({
    PATH: dirname(tuple.gitAdapter),
    GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_SYSTEM: process.platform === 'win32' ? 'NUL' : '/dev/null',
    GIT_CONFIG_GLOBAL: tuple.gitconfig,
    GIT_OPTIONAL_LOCKS: '0',
    GIT_TERMINAL_PROMPT: '0',
    ...(process.platform === 'win32' ? {
      NoDefaultCurrentDirectoryInExePath: '1',
      PATHEXT: '.EXE',
      SystemRoot: resolve(process.env.SystemRoot || 'C:\\Windows'),
    } : {}),
  });
}

function seedsArguments(tuple, args) {
  return [
    `--config=${tuple.bunfig}`,
    '--no-macros',
    '--no-env-file',
    '--no-install',
    `--tsconfig-override=${tuple.tsconfig}`,
    tuple.entry,
    ...args,
  ];
}

function isoTimestamp(value, label) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value) || Number.isNaN(Date.parse(value))) {
    failRefusal(`queue readback ${label} is not an exact timestamp`);
  }
  return value;
}

function recordFlags(values, allowed, label) {
  const flags = new Map();
  for (let index = 0; index < values.length; index += 2) {
    const flag = values[index];
    const value = values[index + 1];
    if (!allowed.has(flag)) failGrammar(`Seeds record ${label} does not admit ${flag}`);
    if (flags.has(flag)) failGrammar(`Seeds record ${label} does not admit a repeated ${flag}`);
    if (value === undefined || value.startsWith('--')) failGrammar(`Seeds record ${label} requires an exact value for ${flag}`);
    if (value.includes('\0')) failGrammar(`Seeds record ${label} rejects a NUL in ${flag}`);
    flags.set(flag, value);
  }
  return flags;
}

function recordGrammar(values) {
  const verb = values[0];
  if (verb === 'create') {
    const flags = recordFlags(values.slice(1), CREATE_FLAGS, 'create');
    if (!flags.has('--title')) failGrammar('a recorded queue creation requires --title');
    // Every requested value is judged here, before the queue writer starts.
    requestedTitle(flags);
    requestedType(flags);
    requestedPriority(flags, 2);
    return { verb, id: null, flags };
  }
  if (verb === 'update') {
    const id = values[1];
    if (!id || id.startsWith('--')) failGrammar('a recorded queue amendment requires an exact issue id');
    const flags = recordFlags(values.slice(2), UPDATE_FLAGS, 'update');
    if (flags.size === 0) failGrammar('a recorded queue amendment requires at least one recorded field');
    requestedTitle(flags);
    requestedStatus(flags);
    requestedPriority(flags, undefined);
    return { verb, id, flags };
  }
  failGrammar(`Seeds record admits only the conductor queue verbs create and update, never ${verb || 'an empty verb'}`);
}

function requestedType(flags) {
  const value = flags.get('--type') ?? 'task';
  if (!VALID_ISSUE_TYPES.has(value)) failGrammar(`Seeds record does not admit the issue type ${value}`);
  return value;
}

function requestedPriority(flags, fallback) {
  const value = flags.get('--priority');
  if (value === undefined) return fallback;
  if (!/^[0-4]$/.test(value)) failGrammar('Seeds record admits only an exact priority 0-4');
  return Number(value);
}

function requestedStatus(flags) {
  const value = flags.get('--status');
  if (value === undefined) return undefined;
  if (!VALID_ISSUE_STATUSES.has(value)) failGrammar(`Seeds record does not admit the issue status ${value}`);
  return value;
}

function requestedLabels(value) {
  const labels = value.split(',').map((label) => label.trim().toLowerCase()).filter(Boolean);
  return labels.length > 0 ? labels : undefined;
}

function requestedTitle(flags) {
  const value = flags.get('--title');
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  if (!trimmed) failGrammar('Seeds record admits only a non-empty title');
  return trimmed;
}

function requireQueueOwningRepositoryRoot(target, operation, tuple) {
  const marker = join(target, '.git');
  let node;
  try {
    node = lstatSync(marker);
  } catch (error) {
    if (error?.code === 'ENOENT') {
      failRefusal(`Seeds ${operation} requires the queue-owning Git repository root: ${target}`);
    }
    failRefusal(`Seeds ${operation} cannot classify the repository marker: ${marker}`);
  }
  if (node.isSymbolicLink() || !node.isDirectory()) {
    failRefusal(`Seeds ${operation} refuses a linked worktree or submodule target: its queue write redirects to another root, and the conductor records at the queue-owning root`);
  }
  const completed = spawnSync(tuple.gitAdapter, ['rev-parse', '--git-dir'], {
    cwd: target,
    encoding: 'utf8',
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: ['ignore', 'pipe', 'ignore'],
    windowsHide: true,
  });
  if (completed.error || completed.status !== 0) {
    failRefusal(`Seeds ${operation} requires a valid queue-owning Git repository root: ${target}`);
  }
  const lines = completed.stdout.trimEnd().split(/\r?\n/);
  if (lines.length !== 1 || !samePath(resolve(target, lines[0]), marker)) {
    failRefusal(`Seeds ${operation} refuses a target that is not its queue-owning Git repository root: ${target}`);
  }
  const common = spawnSync(tuple.gitAdapter, ['rev-parse', '--git-common-dir'], {
    cwd: target,
    encoding: 'utf8',
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: ['ignore', 'pipe', 'ignore'],
    windowsHide: true,
  });
  // An adapter that never started has no stdout to read, so admission is checked before the
  // path comparison: a failed probe is this launcher's named refusal, never a thrown TypeError.
  if (common.error || common.status !== 0) {
    failRefusal(`Seeds ${operation} requires a queue-owning Git repository whose common Git directory the trusted adapter resolves: ${target}`);
  }
  const commonLines = common.stdout.trimEnd().split(/\r?\n/);
  if (commonLines.length !== 1 || !samePath(resolve(target, commonLines[0]), marker)) {
    failRefusal(`Seeds ${operation} refuses a repository whose common Git directory redirects outside the queue-owning root: ${target}`);
  }
  const head = spawnSync(tuple.gitAdapter, ['rev-parse', '--verify', 'HEAD^{commit}'], {
    cwd: target,
    encoding: 'utf8',
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: ['ignore', 'pipe', 'ignore'],
    windowsHide: true,
  });
  if (head.error || head.status !== 0 || !/^[0-9a-f]{40}$|^[0-9a-f]{64}$/.test(head.stdout.trim())) {
    failRefusal(`Seeds ${operation} requires a queue-owning Git repository with an exact HEAD commit: ${target}`);
  }
}

function seedsDirectory(target, tuple) {
  requireQueueOwningRepositoryRoot(target, 'record', tuple);
  const directory = realDirectory(join(target, SEEDS_DIRECTORY), 'target Seeds directory');
  rawRegularFile(join(directory, SEEDS_CONFIG_FILE), 'target Seeds configuration');
  return directory;
}

function queueFile(directory, name, label) {
  const bytes = readFileSync(rawRegularFile(join(directory, name), label));
  return { bytes, digest: hashBytes(bytes) };
}

function queueSurface(directory) {
  const surface = new Map();
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (/\.lock$|\.lock\.stale\.|\.tmp\./.test(entry.name)) continue;
    const path = join(directory, entry.name);
    const node = lstatSync(path);
    if (node.isDirectory()) failRefusal(`unsupported directory inside the Seeds queue: ${entry.name}`);
    if (!node.isFile()) failRefusal(`unsupported filesystem node inside the Seeds queue: ${entry.name}`);
    surface.set(entry.name, hashBytes(readFileSync(path)));
  }
  return surface;
}

function queueRecords(bytes, label) {
  if (bytes.length > 0 && !bytes.subarray(bytes.length - 1).equals(Buffer.from('\n'))) {
    failRefusal(`${label} is not newline-terminated, so an exact readback is unavailable`);
  }
  const content = bytes.toString('utf8');
  const lines = content.length === 0 ? [] : content.slice(0, -1).split('\n');
  const records = [];
  const seen = new Set();
  for (const line of lines) {
    let parsed;
    try {
      parsed = JSON.parse(line);
    } catch {
      failRefusal(`${label} holds a line the queue writer would silently drop, so an exact readback is unavailable`);
    }
    if (!object(parsed) || !text(parsed.id)) failRefusal(`${label} holds a record without an exact id`);
    if (JSON.stringify(parsed) !== line) failRefusal(`${label} is not canonically serialized, so an exact readback is unavailable`);
    if (seen.has(parsed.id)) failRefusal(`${label} holds the duplicate id ${parsed.id}, which the queue writer would collapse`);
    seen.add(parsed.id);
    records.push({ line, parsed });
  }
  return records;
}

function expectedCreatedRecord(id, flags, createdAt, updatedAt) {
  const expected = {
    id,
    title: requestedTitle(flags),
    status: 'open',
    type: requestedType(flags),
    priority: requestedPriority(flags, 2),
    createdAt,
    updatedAt,
  };
  const description = flags.get('--description');
  if (description !== undefined) expected.description = description;
  const labels = flags.has('--labels') ? requestedLabels(flags.get('--labels')) : undefined;
  if (labels !== undefined) expected.labels = labels;
  return expected;
}

function expectedUpdatedRecord(previous, flags, updatedAt) {
  const expected = { ...previous, updatedAt };
  const status = requestedStatus(flags);
  if (status !== undefined) {
    expected.status = status;
    if (status !== 'closed') {
      delete expected.closedAt;
      delete expected.closeReason;
    }
  }
  const title = requestedTitle(flags);
  if (title !== undefined) expected.title = title;
  const description = flags.get('--description');
  if (description !== undefined) expected.description = description;
  const priority = requestedPriority(flags, undefined);
  if (priority !== undefined) expected.priority = priority;
  // The queue writer applies set-labels, then add-label, then remove-label, each against
  // the labels the earlier steps already produced.
  let labels;
  let labelled = false;
  if (flags.has('--set-labels')) {
    labels = requestedLabels(flags.get('--set-labels'));
    labelled = true;
  }
  if (flags.has('--add-label')) {
    const base = (labelled ? labels : previous.labels) ?? [];
    const merged = [...new Set([...base, ...(requestedLabels(flags.get('--add-label')) ?? [])])];
    labels = merged.length > 0 ? merged : undefined;
    labelled = true;
  }
  if (flags.has('--remove-label')) {
    const removed = new Set(flags.get('--remove-label').split(',').map((label) => label.trim().toLowerCase()));
    const remaining = ((labelled ? labels : previous.labels) ?? []).filter((label) => !removed.has(label));
    labels = remaining.length > 0 ? remaining : undefined;
    labelled = true;
  }
  if (labelled) {
    if (labels === undefined) delete expected.labels;
    else expected.labels = labels;
  }
  return expected;
}

function childReport(completed, verb) {
  let report;
  try {
    report = JSON.parse(completed.stdout || '');
  } catch {
    failRefusal('queue writer did not emit an exact JSON record');
  }
  if (!object(report) || report.success !== true || report.command !== verb) failRefusal('queue writer did not report the exact requested queue write');
  return report;
}

function optionalRegularFileSnapshot(path, label) {
  let node;
  try {
    node = lstatSync(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return { exists: false, bytes: null, digest: INIT_EXPECTATION };
    failRefusal(`cannot snapshot ${label}: ${path}`);
  }
  if (node.isSymbolicLink() || !node.isFile()) failRefusal(`${label} must be absent or a regular file: ${path}`);
  const bytes = readFileSync(path);
  return { exists: true, bytes, digest: `file:${hashBytes(bytes)}` };
}

function surfaceNodeDigest(path) {
  let node;
  try {
    node = lstatSync(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return INIT_EXPECTATION;
    return 'unreadable';
  }
  if (node.isSymbolicLink()) return `symlink:${hashBytes(Buffer.from(readlinkSync(path), 'utf8'))}`;
  if (node.isFile()) return `file:${hashFile(path)}`;
  if (node.isDirectory()) {
    try {
      return `directory:${treeHash(path)}`;
    } catch {
      return 'unreadable';
    }
  }
  return `node:${node.mode}`;
}

function admittedGitattributesText(before) {
  if (!before.exists) return '';
  let existing;
  try {
    existing = new TextDecoder('utf-8', { fatal: true }).decode(before.bytes);
  } catch {
    failRefusal('Seeds init refuses non-UTF-8 .gitattributes because the pinned initializer cannot preserve its bytes');
  }
  const exactLines = new Set(existing.split('\n'));
  const exactMissing = INIT_MERGE_UNION_LINES.filter((line) => !exactLines.has(line));
  const upstreamMissing = INIT_MERGE_UNION_LINES.filter((line) => !existing.includes(line));
  if (JSON.stringify(exactMissing) !== JSON.stringify(upstreamMissing)) {
    failRefusal('Seeds init refuses .gitattributes whose exact lines disagree with the pinned initializer substring-match behavior');
  }
  return existing;
}

function expectedGitattributes(before) {
  const beforeBytes = before.exists ? before.bytes : Buffer.alloc(0);
  const lineBytes = INIT_MERGE_UNION_LINES.map((line) => Buffer.from(line, 'utf8'));
  const existing = admittedGitattributesText(before);
  const existingLines = existing.split('\n').map((line) => Buffer.from(line, 'utf8'));
  const missing = lineBytes.filter(
    (line) => !existingLines.some((existing) => existing.equals(line)),
  );
  if (missing.length === 0) return beforeBytes;
  const separator = beforeBytes.length === 0 || beforeBytes.at(-1) === 0x0a
    ? Buffer.alloc(0)
    : Buffer.from('\n');
  return Buffer.concat([
    beforeBytes,
    separator,
    ...missing.flatMap((line) => [line, Buffer.from('\n')]),
  ]);
}

function verifyInitializedSurface(target, beforeAttributes) {
  const directory = realDirectory(join(target, SEEDS_DIRECTORY), 'initialized Seeds directory');
  const entries = readdirSync(directory, { withFileTypes: true });
  const names = new Set(entries.map((entry) => entry.name));
  for (const name of INIT_SURFACE) {
    if (!names.has(name)) failRefusal(`Seeds init readback divergence: initialized .seeds is missing ${name}`);
  }
  for (const name of names) {
    if (!INIT_SURFACE.has(name)) failRefusal(`Seeds init readback divergence: initialized .seeds added unrequested ${name}`);
  }
  for (const entry of entries) {
    const path = join(directory, entry.name);
    const node = lstatSync(path);
    if (node.isSymbolicLink() || !node.isFile()) failRefusal(`Seeds init readback divergence: initialized .seeds contains non-regular ${entry.name}`);
  }
  const config = readFileSync(rawRegularFile(join(directory, SEEDS_CONFIG_FILE), 'initialized Seeds configuration'));
  const expectedConfig = Buffer.from(`project: "${basename(target)}"\nversion: "1"\nmax_plan_depth: 3\n`, 'utf8');
  if (!config.equals(expectedConfig)) failRefusal('Seeds init readback divergence: initialized config.yaml is not the exact initializer policy');
  for (const name of [SEEDS_ISSUES_FILE, SEEDS_TEMPLATES_FILE, SEEDS_PLANS_FILE]) {
    const path = rawRegularFile(join(directory, name), `initialized Seeds ${name}`);
    if (lstatSync(path).size !== 0) failRefusal(`Seeds init readback divergence: initialized ${name} is not empty`);
  }
  const ignore = readFileSync(rawRegularFile(join(directory, SEEDS_GITIGNORE_FILE), 'initialized Seeds ignore file'));
  if (!ignore.equals(Buffer.from('*.lock\n', 'utf8'))) failRefusal('Seeds init readback divergence: initialized .gitignore is not the exact lock-only policy');
  const attributes = optionalRegularFileSnapshot(join(target, GITATTRIBUTES_FILE), 'target .gitattributes readback');
  if (!attributes.exists || !attributes.bytes.equals(expectedGitattributes(beforeAttributes))) {
    failRefusal('Seeds init readback divergence: .gitattributes is not the precise merge-union append');
  }
}

function initialize(targetArgument) {
  const target = suppliedDirectory(targetArgument, 'Seeds target');
  const tuple = checkCurrentReceipt(loadReceipt());
  requireQueueOwningRepositoryRoot(target, 'init', tuple);
  const seedsPath = join(target, SEEDS_DIRECTORY);
  let seedsNode;
  try {
    seedsNode = lstatSync(seedsPath);
  } catch (error) {
    if (error?.code !== 'ENOENT') failRefusal(`Seeds init cannot classify .seeds: ${seedsPath}`);
  }
  if (seedsNode !== undefined) {
    const kind = seedsNode.isSymbolicLink() ? 'symlink' : seedsNode.isDirectory() ? 'directory' : seedsNode.isFile() ? 'file' : 'filesystem node';
    failRefusal(`Seeds init requires --expect-queue absent and an absent .seeds; found existing ${kind}`);
  }
  const attributesPath = join(target, GITATTRIBUTES_FILE);
  const attributes = optionalRegularFileSnapshot(attributesPath, 'target .gitattributes');
  expectedGitattributes(attributes); // Prove the pinned initializer and exact verifier agree before mutation.
  // Everything above this line refuses cleanly. Below it the initializer runs, so the ledger is
  // opened FIRST and every later refusal --- including one raised while reading the surface back ---
  // reports an unknown effect until the two digests below prove nothing moved.
  admitUnprovenSurface(`the .seeds initialization surface under ${rendered(target)}`);
  const completed = spawnSync(tuple.bun, seedsArguments(tuple, ['init', '--json']), {
    cwd: target,
    encoding: 'utf8',
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: ['ignore', 'pipe', 'inherit'],
    windowsHide: true,
  });
  const afterDigest = surfaceNodeDigest(seedsPath);
  const attributesAfterDigest = surfaceNodeDigest(attributesPath);
  const surfaceMoved = afterDigest !== INIT_EXPECTATION || attributesAfterDigest !== attributes.digest;
  // The one proof that closes the ledger: both surfaces still carry their exact prestate digest.
  if (!surfaceMoved) proveSurfaceUnchanged();
  if (completed.error || completed.status !== 0) {
    if (surfaceMoved) failEffectUnknown(`Seeds init effect is unknown: the queue writer failed after moving the initialization surface to .seeds=${afterDigest}, .gitattributes=${attributesAfterDigest}`);
    failRefusal('Seeds init refused: the queue writer failed and left .seeds and .gitattributes unchanged');
  }
  const report = childReport(completed, 'init');
  if (!text(report.dir) || !samePath(resolve(report.dir), seedsPath)) failRefusal('Seeds init readback divergence: the queue writer reported a different directory');
  verifyInitializedSurface(target, attributes);
  process.stdout.write(`recorded conductor queue initialization: ${seedsPath}\nverified absent prestate, exact runtime, closed .seeds surface, and precise .gitattributes merge-union append\n`);
}

// The ledger's proof half: a boolean, not an assertion, because "did anything move" has to be
// answerable before the launcher decides which class its refusal belongs to. `assertUnchangedQueue`
// below is the verdict half and admits the two files a requested write may legitimately move.
function sameQueueSurface(before, after) {
  if (before.size !== after.size) return false;
  for (const [name, digest] of before) {
    if (after.get(name) !== digest) return false;
  }
  return true;
}

function assertUnchangedQueue(before, after, label) {
  for (const [name, digest] of before) {
    if (!after.has(name)) failRefusal(`${label}: the queue writer removed ${name}`);
    if (after.get(name) !== digest && name !== SEEDS_ISSUES_FILE && name !== SEEDS_PLANS_FILE) failRefusal(`${label}: the queue writer changed ${name}`);
  }
  for (const name of after.keys()) {
    if (!before.has(name)) failRefusal(`${label}: the queue writer added ${name}`);
  }
}

function assertBoundedPlanCascade(directory, plansBefore, before, after, id, statusRequested) {
  if (before.get(SEEDS_PLANS_FILE) === after.get(SEEDS_PLANS_FILE)) return;
  if (!statusRequested) failRefusal('queue readback divergence: the queue writer changed plans.jsonl without a recorded status change');
  const previous = queueRecords(plansBefore, 'the Seeds plan queue prestate');
  const current = queueRecords(readFileSync(join(directory, SEEDS_PLANS_FILE)), 'the Seeds plan queue readback');
  if (previous.length !== current.length) failRefusal('queue readback divergence: the plan cascade changed the plan count');
  for (let index = 0; index < previous.length; index += 1) {
    if (previous[index].line === current[index].line) continue;
    const plan = previous[index].parsed;
    const observed = current[index].parsed;
    if (!Array.isArray(plan.children) || !plan.children.includes(id)) {
      failRefusal(`queue readback divergence: the plan cascade changed plan ${plan.id}, which does not own ${id}`);
    }
    // A bounded cascade is verified, not re-derived: only status and updatedAt may move.
    const sealed = { ...plan, status: observed.status, updatedAt: isoTimestamp(observed.updatedAt, `plan ${plan.id} timestamp`) };
    if (!PLAN_STATUSES.has(observed.status) || JSON.stringify(sealed) !== current[index].line) {
      failRefusal(`queue readback divergence: the plan cascade changed more than plan ${plan.id} status and timestamp`);
    }
  }
}

function record(targetArgument, expected, values) {
  const request = recordGrammar(values); // Parse the whole admitted form before touching the queue.
  if (!/^[0-9a-f]{64}$/.test(expected)) failGrammar('Seeds record requires the exact sha256 the conductor decided against in --expect-queue');
  const target = suppliedDirectory(targetArgument, 'Seeds target');
  const tuple = checkCurrentReceipt(loadReceipt());
  const directory = seedsDirectory(target, tuple);
  const surfaceBefore = queueSurface(directory);
  const plansBefore = queueFile(directory, SEEDS_PLANS_FILE, 'target Seeds plan queue').bytes;
  const queue = queueFile(directory, SEEDS_ISSUES_FILE, 'target Seeds queue');
  if (queue.digest !== expected) {
    failRefusal(`Seeds record compare-and-swap refused: the queue is ${queue.digest}, not the ${expected} the conductor decided against`);
  }
  const before = queueRecords(queue.bytes, 'the Seeds queue prestate');
  const index = request.verb === 'update' ? before.findIndex((entry) => entry.parsed.id === request.id) : -1;
  if (request.verb === 'update' && index === -1) failRefusal(`recorded queue amendment refused: ${request.id} is absent from the queue prestate`);
  const args = [request.verb, ...(request.id === null ? [] : [request.id])];
  for (const [flag, value] of request.flags) args.push(flag, value);
  args.push('--json');
  // Same boundary as init: the ledger opens before the queue writer starts, so a readback that
  // cannot even be TAKEN --- a deleted queue file, a directory where a record file was --- reports
  // an unknown effect instead of a clean refusal it cannot honestly claim.
  admitUnprovenSurface(`the Seeds queue under ${rendered(directory)} at prestate sha256 ${queue.digest}`);
  const completed = spawnSync(tuple.bun, seedsArguments(tuple, args), {
    cwd: target,
    encoding: 'utf8',
    env: seedsEnvironment(tuple),
    shell: false,
    stdio: ['ignore', 'pipe', 'inherit'],
    windowsHide: true,
  });
  const after = queueFile(directory, SEEDS_ISSUES_FILE, 'target Seeds queue');
  // ONE post-writer surface snapshot, taken here rather than after the record checks, because it is
  // both halves of the ledger's proof and the input `assertUnchangedQueue` compares below. The queue
  // the conductor named must be byte-identical AND no sibling queue file may have moved; a writer
  // that left issues.jsonl alone but rewrote config.yaml has still had an effect.
  const surfaceAfter = queueSurface(directory);
  if (after.digest === queue.digest && sameQueueSurface(surfaceBefore, surfaceAfter)) proveSurfaceUnchanged();
  if (completed.error || completed.status !== 0) {
    if (after.digest !== queue.digest) failEffectUnknown(`Seeds record effect is unknown: the queue writer failed yet moved the queue to ${after.digest}`);
    failRefusal(`Seeds record refused: the queue writer failed and left the queue at ${queue.digest}`);
  }
  const report = childReport(completed, request.verb);
  const observed = queueRecords(after.bytes, 'the Seeds queue readback');
  if (request.verb === 'create') {
    if (observed.length !== before.length + 1) failRefusal(`queue readback divergence: create recorded ${observed.length - before.length} records, not exactly one`);
    for (let position = 0; position < before.length; position += 1) {
      if (observed[position].line !== before[position].line) failRefusal(`queue readback divergence: create rewrote the existing record ${before[position].parsed.id}`);
    }
    const appended = observed[observed.length - 1];
    if (!text(report.id) || appended.parsed.id !== report.id) failRefusal('queue readback divergence: the appended record is not the record the queue writer reported');
    if (before.some((entry) => entry.parsed.id === report.id)) failRefusal(`queue readback divergence: create reused the existing id ${report.id}`);
    const createdAt = isoTimestamp(appended.parsed.createdAt, 'createdAt');
    const updatedAt = isoTimestamp(appended.parsed.updatedAt, 'updatedAt');
    if (createdAt !== updatedAt) failRefusal('queue readback divergence: a created record must carry one exact timestamp');
    if (JSON.stringify(expectedCreatedRecord(report.id, request.flags, createdAt, updatedAt)) !== appended.line) {
      failRefusal('queue readback divergence: the recorded fields are not exactly the requested fields');
    }
  } else {
    if (observed.length !== before.length) failRefusal('queue readback divergence: update changed the queue record count');
    for (let position = 0; position < before.length; position += 1) {
      if (position === index || observed[position].line === before[position].line) continue;
      failRefusal(`queue readback divergence: update rewrote the untouched record ${before[position].parsed.id}`);
    }
    const changed = observed[index];
    if (changed.parsed.id !== request.id) failRefusal(`queue readback divergence: update moved ${request.id} within the queue`);
    if (!object(report.issue) || report.issue.id !== request.id) failRefusal('queue readback divergence: the queue writer reported a different record');
    const updatedAt = isoTimestamp(changed.parsed.updatedAt, 'updatedAt');
    if (Date.parse(updatedAt) < Date.parse(isoTimestamp(before[index].parsed.updatedAt, 'prestate updatedAt'))) {
      failRefusal('queue readback divergence: update moved the record timestamp backwards');
    }
    if (JSON.stringify(expectedUpdatedRecord(before[index].parsed, request.flags, updatedAt)) !== changed.line) {
      failRefusal('queue readback divergence: the recorded fields are not exactly the requested fields');
    }
  }
  assertUnchangedQueue(surfaceBefore, surfaceAfter, 'queue readback divergence');
  assertBoundedPlanCascade(directory, plansBefore, surfaceBefore, surfaceAfter, request.id, request.flags.has('--status'));
  const recorded = request.verb === 'create' ? report.id : request.id;
  process.stdout.write(`recorded conductor queue write: ${request.verb} ${recorded}\nqueue sha256 ${queue.digest} -> ${after.digest}\nverified by compare-and-swap and exact readback; this record is the conductor's evidence and authorizes no outward effect\n`);
}

function parse(argv) {
  if (argv[0] === 'bootstrap' && argv.length === 3 && argv[1] === '--distribution') return { mode: 'bootstrap', distribution: argv[2] };
  if (argv[0] === 'inspect' && argv.length >= 4 && argv[1] === '--target') return { mode: 'inspect', target: argv[2], args: argv.slice(3) };
  if (argv[0] === 'record') {
    if (argv.length < 8 || argv[1] !== '--target' || argv[3] !== '--queue-writer' || argv[5] !== '--expect-queue') failGrammar(HELP);
    if (argv[4] !== QUEUE_WRITER) {
      failGrammar(`Seeds record admits only the sole queue writer: pass --queue-writer ${QUEUE_WRITER}, never ${argv[4]}`);
    }
    const expected = argv[6];
    const args = argv.slice(7);
    if (args[0] === 'init') {
      if (expected !== INIT_EXPECTATION || args.length !== 1) failGrammar('Seeds init requires exactly --queue-writer conductor --expect-queue absent init');
      return { mode: 'init', target: argv[2] };
    }
    return { mode: 'record', target: argv[2], expected, args };
  }
  failGrammar(HELP);
}

// The single point where a code is derived, and the reason a raise site's class is a floor rather
// than the verdict. Two inputs, and the rule between them is escalate-only:
//
//   1. THE LEDGER IS THE FLOOR. Once a surface may have moved and nothing has proven it did not, no
//      refusal may exit as a grammar verdict, a clean pre-effect refusal, or an internal failure,
//      because on disk the result is partial or unknown. Decision 9's 4 is the only honest answer,
//      and the escalation NAMES what is unproven rather than replacing the refusal's own message.
//   2. A RAISE SITE MAY ONLY ESCALATE. `failEffectUnknown` still reports over an empty ledger, for
//      the case this launcher observes but did not cause. What no site can do any more is claim a
//      clean refusal over something that already happened.
function reportFailure(error) {
  if (!(error instanceof LauncherError)) {
    // Not a classified refusal: a launcher bug, and Decision 9's 1 rather than the 2 every throw in
    // this file used to collapse onto. The ledger outranks even this branch: an unclassified throw
    // raised after the queue writer started still cannot claim less than an unknown effect.
    process.stderr.write(`launcher failure: ${error?.message ?? error}\n`);
    if (UNPROVEN_SURFACE !== null) {
      process.stderr.write(`Seeds effect is unknown: this failure was raised after the queue writer started and nothing proved ${UNPROVEN_SURFACE} unchanged\n`);
      return EXITS.effectUnknown;
    }
    return EXITS.internal;
  }
  process.stderr.write(`${error.message}\n`);
  if (UNPROVEN_SURFACE === null || error.code === EXITS.effectUnknown) return error.code;
  process.stderr.write(`Seeds effect is unknown: this refusal was raised after the queue writer started and nothing proved ${UNPROVEN_SURFACE} unchanged\n`);
  return EXITS.effectUnknown;
}

try {
  const argv = process.argv.slice(2);
  // A help request performs nothing, so it is answered before the executing-Node admission: a query
  // cannot honestly fail on a capability it never uses, and an operator who needs the usage line is
  // usually the operator who does not yet have the exact Node.
  if (argv.length === 1 && HELP_FLAGS.has(argv[0])) {
    process.stdout.write(`${HELP}\n`);
    process.exitCode = EXITS.ok;
  } else {
    exactLauncherNode();
    const command = parse(argv);
    if (command.mode === 'bootstrap') bootstrap(command.distribution);
    else if (command.mode === 'init') initialize(command.target);
    else if (command.mode === 'record') record(command.target, command.expected, command.args);
    else inspect(command.target, command.args);
  }
} catch (error) {
  process.exitCode = reportFailure(error);
}
