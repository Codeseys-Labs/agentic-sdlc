#!/usr/bin/env node
/**
 * Locked, installed Seeds runtime launcher.
 *
 * Bootstrap is intentionally the only mode allowed to invoke mise. Inspect accepts a
 * previously admitted receipt only; it neither discovers, installs, repairs, nor
 * acquires anything. The receipt protects against accidental drift, not a concurrent
 * same-UID attacker between checks and exec.
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
  statSync,
  unlinkSync,
  writeFileSync,
  fsyncSync,
} from 'node:fs';
import { dirname, isAbsolute, join, normalize, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCHEMA = 1;
const NODE_VERSION = '22.22.3';
const BUN_VERSION = '1.3.10';
const SEEDS_VERSION = '0.5.14';
const SEEDS_TOOL = `npm:@os-eco/seeds-cli@${SEEDS_VERSION}`;
const SEEDS_PACKAGE = '@os-eco/seeds-cli';
const SEEDS_BIN = 'sd';
const TOOL_NAMES = Object.freeze({ node: `node@${NODE_VERSION}`, bun: `bun@${BUN_VERSION}`, seeds: SEEDS_TOOL });
const FORBIDDEN_PACKAGE_KEYS = new Set(['bun', 'bunfig', 'tsconfig', 'jsconfig', 'macro', 'macros', 'preload']);
const FORBIDDEN_PACKAGE_FILES = new Set(['bunfig.toml', 'bunfig.json', 'tsconfig.json', 'jsconfig.json']);
const HELP = 'usage: seeds-launcher.mjs bootstrap --distribution <reviewed-distribution> | inspect --target <repository> (--version | prime | ready [--format json] | blocked [--format json])';

class LauncherError extends Error {}

function fail(message) {
  throw new LauncherError(message);
}

function hashBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function hashFile(path) {
  const node = lstatSync(path);
  if (!node.isFile()) fail(`required regular file is unavailable: ${path}`);
  return hashBytes(readFileSync(path));
}

function realDirectory(path, label) {
  let node;
  try {
    node = lstatSync(path);
  } catch {
    fail(`${label} is unavailable: ${path}`);
  }
  if (node.isSymbolicLink() || !node.isDirectory()) fail(`${label} must be a real directory: ${path}`);
  return realpathSync(path);
}

function realRegularFile(path, label) {
  let resolved;
  try {
    resolved = realpathSync(path);
  } catch {
    fail(`${label} is unavailable: ${path}`);
  }
  let node;
  try {
    node = statSync(resolved);
  } catch {
    fail(`${label} is unavailable: ${path}`);
  }
  if (!node.isFile()) fail(`${label} must be a regular file: ${path}`);
  return resolved;
}

function contained(root, candidate, label) {
  const realRoot = realpathSync(root);
  const realCandidate = realpathSync(candidate);
  const boundary = realRoot.endsWith(sep) ? realRoot : `${realRoot}${sep}`;
  if (!(realCandidate === realRoot || realCandidate.startsWith(boundary))) {
    fail(`${label} escapes its reviewed root: ${candidate}`);
  }
  return realCandidate;
}

function containedFile(root, candidate, label) {
  if (!isAbsolute(candidate)) fail(`${label} must be absolute: ${candidate}`);
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
        fail(`unsupported filesystem node in reviewed tree: ${path}`);
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
        fail(`unsupported filesystem node in distribution tree: ${path}`);
      }
    }
  };
  walk(realRoot);
  return hasher.digest('hex');
}

function exactVersion(executable, expected, label) {
  const completed = spawnSync(executable, ['--version'], { encoding: 'utf8', shell: false, windowsHide: true, env: {} });
  if (completed.error || completed.status !== 0) fail(`cannot execute exact ${label} version probe`);
  const actual = (completed.stdout || '').trim().replace(/^v/, '');
  if (actual !== expected) fail(`exact ${label} version mismatch: expected ${expected}, got ${actual || 'empty'}`);
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
  fail(`${label} is unavailable on PATH`);
}

function runMise(args, cwd) {
  const mise = findExecutable('mise', 'mise');
  const completed = spawnSync(mise, args, { cwd, encoding: 'utf8', shell: false, windowsHide: true });
  if (completed.error || completed.status !== 0) fail(`mise ${args.join(' ')} failed: ${(completed.stderr || completed.error?.message || '').trim()}`);
  return (completed.stdout || '').trim();
}

function parsePackage(path) {
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    fail(`cannot parse Seeds package metadata: ${error.message}`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) fail('Seeds package metadata must be an object');
  return parsed;
}

function packageHasExecutionControl(value) {
  if (Array.isArray(value)) return value.some(packageHasExecutionControl);
  if (!value || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, nested]) => FORBIDDEN_PACKAGE_KEYS.has(key.toLowerCase()) || packageHasExecutionControl(nested));
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
  fail('Seeds package root is unavailable in the expected platform layout');
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
    fail(`Seeds package mismatch: expected ${SEEDS_PACKAGE}@${SEEDS_VERSION}`);
  }
  if (!metadata.bin || typeof metadata.bin !== 'object' || Array.isArray(metadata.bin) || typeof metadata.bin[SEEDS_BIN] !== 'string') {
    fail('Seeds package must define the exact sd bin');
  }
  const binValue = metadata.bin[SEEDS_BIN];
  if (isAbsolute(binValue) || binValue.split(/[\\/]+/).includes('..')) fail('Seeds package bin escapes its package root');
  if (packageHasExecutionControl(metadata)) fail('Seeds package declares prohibited execution control');
  for (const name of FORBIDDEN_PACKAGE_FILES) {
    if (existsSync(join(packageRoot, name))) fail(`Seeds package contains prohibited execution control: ${name}`);
  }
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
    if (parentNode.isSymbolicLink() || !parentNode.isDirectory()) fail(`state path is not a real directory: ${parent}`);
  }
  if (!existsSync(destination)) mkdirSync(destination, { mode: 0o700 });
  const node = lstatSync(destination);
  if (node.isSymbolicLink() || !node.isDirectory()) fail(`state path is not a real directory: ${destination}`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) fail(`state path is not owned by this user: ${destination}`);
  if (process.platform !== 'win32') chmodSync(destination, 0o700);
}

function fsyncDirectory(path) {
  if (process.platform === 'win32') return;
  let descriptor;
  try {
    descriptor = openSync(path, 'r');
    fsyncSync(descriptor);
  } catch {
    fail(`cannot persist state directory: ${path}`);
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
    fail(`trusted ${name} is unavailable`);
  }
  if (node.isSymbolicLink() || !node.isFile() || node.size !== 0) fail(`trusted ${name} must be an owned empty regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) fail(`trusted ${name} is not owned by this user`);
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
  if (node.isSymbolicLink() || !node.isFile() || node.size !== 0) fail(`trusted ${name} must be an owned empty regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) fail(`trusted ${name} is not owned by this user`);
  if (process.platform !== 'win32') chmodSync(path, 0o600);
  return realRegularFile(path, `trusted ${name}`);
}

function receiptDirectory() {
  const path = join(stateBase(), 'agentic-sdlc-orchestrator', 'seeds-runtime', `v${SCHEMA}`);
  ensurePrivateDirectory(path);
  return path;
}

function gitCommit(distribution) {
  const git = findExecutable('git', 'Git');
  const completed = spawnSync(git, ['-C', distribution, 'rev-parse', '--verify', 'HEAD^{commit}'], { encoding: 'utf8', shell: false, windowsHide: true });
  if (completed.error || completed.status !== 0) fail('reviewed distribution must have an exact Git commit');
  return { path: git, hash: hashFile(git), commit: completed.stdout.trim() };
}

function bootstrap(distributionArgument) {
  const distribution = realDirectory(distributionArgument, 'reviewed distribution');
  const miseToml = containedFile(distribution, join(distribution, 'mise.toml'), 'reviewed mise.toml');
  const miseLock = containedFile(distribution, join(distribution, 'mise.lock'), 'reviewed mise.lock');
  const git = gitCommit(distribution);
  runMise(['--locked', 'install'], distribution);
  const roots = {
    node: runMise(['--no-config', 'where', TOOL_NAMES.node], distribution),
    bun: runMise(['--no-config', 'where', TOOL_NAMES.bun], distribution),
    seeds: runMise(['--no-config', 'where', TOOL_NAMES.seeds], distribution),
  };
  if (!Object.values(roots).every((value) => isAbsolute(value))) fail('mise must return absolute exact tool roots');
  const tuple = validateTuple(roots);
  const directory = receiptDirectory();
  const bunfig = trustedEmptyFile(directory, 'trusted-bunfig.toml');
  const gitconfig = trustedEmptyFile(directory, 'trusted-gitconfig');
  const receipt = {
    schema: SCHEMA,
    platform: process.platform,
    createdAt: new Date().toISOString(),
    distribution: { root: distribution, commit: git.commit },
    tuple: {
      node: { root: tuple.nodeRoot, executable: tuple.node, version: NODE_VERSION },
      bun: { root: tuple.bunRoot, executable: tuple.bun, version: BUN_VERSION },
      seeds: { root: tuple.seedsRoot, packageRoot: tuple.packageRoot, package: SEEDS_PACKAGE, version: SEEDS_VERSION, bin: SEEDS_BIN, binValue: tuple.binValue, entry: tuple.entry },
      git,
      trusted: { bunfig, gitconfig },
    },
    hashes: {
      distribution: { tree: distributionTreeHash(distribution), miseToml: hashFile(miseToml), miseLock: hashFile(miseLock), commit: hashBytes(Buffer.from(git.commit, 'utf8')) },
      node: treeHash(tuple.nodeRoot),
      bun: treeHash(tuple.bunRoot),
      seeds: treeHash(tuple.seedsRoot),
      packageJson: hashFile(tuple.packageJson),
      entry: hashFile(tuple.entry),
      git: hashFile(git.path),
      bunfig: hashFile(bunfig),
      gitconfig: hashFile(gitconfig),
    },
  };
  const active = join(directory, 'active.json');
  if (existsSync(active)) {
    // Validate before retaining as rollback material; malformed partial state is never repaired.
    const previous = loadReceipt(active);
    atomicWrite(join(directory, 'previous.json'), `${JSON.stringify(previous, null, 2)}\n`);
  }
  atomicWrite(active, `${JSON.stringify(receipt, null, 2)}\n`);
  process.stdout.write(`bootstrapped locked Seeds tuple receipt: ${active}\n`);
}

function object(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function text(value) {
  return typeof value === 'string' && value.length > 0;
}

function receiptPath() {
  return join(stateBase(), 'agentic-sdlc-orchestrator', 'seeds-runtime', `v${SCHEMA}`, 'active.json');
}

function loadReceipt(path = receiptPath()) {
  let receipt;
  let receiptNode;
  try {
    receiptNode = lstatSync(path);
    if (receiptNode.isSymbolicLink() || !receiptNode.isFile() || (process.platform !== 'win32' && receiptNode.uid !== process.getuid())) fail(`active tuple receipt is missing or corrupt: ${path}`);
    receipt = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    if (error instanceof LauncherError) throw error;
    fail(`active tuple receipt is missing or corrupt: ${path}`);
  }
  if (!object(receipt) || receipt.schema !== SCHEMA || receipt.platform !== process.platform || !object(receipt.distribution) || !object(receipt.tuple) || !object(receipt.hashes)) {
    fail('active tuple receipt is partial or invalid');
  }
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  if (!object(node) || !object(bun) || !object(seeds) || !object(git) || !object(trusted)
    || node.version !== NODE_VERSION || bun.version !== BUN_VERSION || seeds.package !== SEEDS_PACKAGE || seeds.version !== SEEDS_VERSION || seeds.bin !== SEEDS_BIN
    || ![node.root, node.executable, bun.root, bun.executable, seeds.root, seeds.packageRoot, seeds.entry, git.path, git.hash, trusted.bunfig, trusted.gitconfig].every(text)) {
    fail('active tuple receipt is partial or invalid');
  }
  return receipt;
}

function checkCurrentReceipt(receipt) {
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  const expected = receipt.hashes;
  if (!object(expected.distribution) || ![expected.node, expected.bun, expected.seeds, expected.packageJson, expected.entry, expected.git, expected.bunfig, expected.gitconfig].every(text)) fail('active tuple receipt is partial or invalid');
  const tuple = validateTuple({ node: node.root, bun: bun.root, seeds: seeds.root });
  if (tuple.node !== node.executable || tuple.bun !== bun.executable || tuple.packageRoot !== seeds.packageRoot || tuple.entry !== seeds.entry) fail('active tuple receipt does not match exact platform layout');
  if (treeHash(node.root) !== expected.node || treeHash(bun.root) !== expected.bun || treeHash(seeds.root) !== expected.seeds || hashFile(tuple.packageJson) !== expected.packageJson || hashFile(tuple.entry) !== expected.entry) fail('exact tuple hash drift detected');
  if (realRegularFile(git.path, 'recorded Git executable') !== git.path || hashFile(git.path) !== expected.git) fail('recorded Git executable hash drift detected');
  const bunfig = existingTrustedEmptyFile(trusted.bunfig, 'trusted-bunfig.toml');
  const gitconfig = existingTrustedEmptyFile(trusted.gitconfig, 'trusted-gitconfig');
  if (bunfig !== trusted.bunfig || gitconfig !== trusted.gitconfig || hashFile(bunfig) !== expected.bunfig || hashFile(gitconfig) !== expected.gitconfig) fail('trusted configuration hash drift detected');
  return { ...tuple, bunfig, gitconfig, git: git.path };
}

function grammar(values) {
  if (values.length === 1 && values[0] === '--version') return values;
  if (values.length === 1 && values[0] === 'prime') return values;
  if ((values[0] === 'ready' || values[0] === 'blocked') && (values.length === 1 || (values.length === 3 && values[1] === '--format' && values[2] === 'json'))) return values;
  fail('Seeds inspect accepts only --version, prime, ready [--format json], or blocked [--format json]');
}

function inspect(targetArgument, values) {
  const args = grammar(values); // Parse every allowed form before inspecting any executable.
  const target = realDirectory(targetArgument, 'Seeds target');
  const tuple = checkCurrentReceipt(loadReceipt());
  const environment = Object.freeze({
    PATH: dirname(tuple.git),
    GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_GLOBAL: tuple.gitconfig,
  });
  const child = spawn(tuple.bun, [`--config=${tuple.bunfig}`, '--no-env-file', '--no-install', tuple.entry, ...args], {
    cwd: target,
    env: environment,
    shell: false,
    stdio: 'inherit',
    windowsHide: true,
  });
  child.once('error', (error) => {
    process.stderr.write(`cannot start exact Seeds Bun entry: ${error.message}\n`);
    process.exitCode = 2;
  });
  child.once('close', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    else process.exitCode = code === null ? 1 : code;
  });
}

function parse(argv) {
  if (argv[0] === 'bootstrap' && argv.length === 3 && argv[1] === '--distribution') return { mode: 'bootstrap', distribution: argv[2] };
  if (argv[0] === 'inspect' && argv.length >= 4 && argv[1] === '--target') return { mode: 'inspect', target: argv[2], args: argv.slice(3) };
  fail(HELP);
}

try {
  const command = parse(process.argv.slice(2));
  if (command.mode === 'bootstrap') bootstrap(command.distribution);
  else inspect(command.target, command.args);
} catch (error) {
  process.stderr.write(`${error instanceof LauncherError ? error.message : `launcher failure: ${error.message}`}\n`);
  process.exitCode = 2;
}
