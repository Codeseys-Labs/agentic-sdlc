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
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync,
  fsyncSync,
} from 'node:fs';
import { dirname, isAbsolute, join, normalize, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCHEMA = 2;
const NODE_VERSION = '22.22.3';
const BUN_VERSION = '1.3.10';
const SEEDS_VERSION = '0.5.14';
const SEEDS_TOOL = `npm:@os-eco/seeds-cli@${SEEDS_VERSION}`;
const SEEDS_PACKAGE = '@os-eco/seeds-cli';
const SEEDS_BIN = 'sd';
const TOOL_NAMES = Object.freeze({ node: `node@${NODE_VERSION}`, bun: `bun@${BUN_VERSION}`, seeds: SEEDS_TOOL });
const NPM_REGISTRY = 'https://registry.npmjs.org/';
const MISE_CONFIG_SENTINEL = '__agentic_sdlc_reviewed_config_only__';
const FORBIDDEN_PACKAGE_KEYS = new Set(['bun', 'bunfig', 'tsconfig', 'jsconfig', 'macro', 'macros', 'preload']);
const FORBIDDEN_PACKAGE_FILES = new Set(['bunfig.toml', 'bunfig.json', 'tsconfig.json', 'jsconfig.json']);
const FORBIDDEN_PACKAGE_STEMS = new Set(['macro', 'macros', 'preload']);
const RECEIPT_KEYS = new Set(['schema', 'platform', 'createdAt', 'distribution', 'tuple', 'hashes']);
const DISTRIBUTION_KEYS = new Set(['root', 'commit', 'gitTree', 'tree', 'miseToml', 'miseLock', 'launcher', 'launcherHash']);
const HASH_KEYS = new Set(['distribution', 'node', 'nodeExecutable', 'bun', 'seeds', 'packageJson', 'entry', 'git', 'bunfig', 'tsconfig', 'gitconfig']);
const DISTRIBUTION_HASH_KEYS = new Set(['tree', 'gitTree', 'miseToml', 'miseLock', 'commit']);
const TUPLE_KEYS = new Set(['node', 'bun', 'seeds', 'git', 'trusted']);
const NODE_KEYS = new Set(['root', 'executable', 'version']);
const BUN_KEYS = new Set(['root', 'executable', 'version']);
const SEEDS_KEYS = new Set(['root', 'packageRoot', 'package', 'version', 'bin', 'binValue', 'entry']);
const GIT_KEYS = new Set(['path', 'hash', 'commit', 'tree']);
const TRUSTED_KEYS = new Set(['bunfig', 'tsconfig', 'gitconfig']);
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
  return process.platform === 'win32' ? realpathSync.native(path) : realpathSync(path);
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

function runMise(mise, args, cwd, env) {
  const completed = spawnSync(mise, args, { cwd, encoding: 'utf8', shell: false, windowsHide: true, env });
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
      if (packageControlFile(entry.name)) fail(`Seeds package contains prohibited execution control: ${relative(packageRoot, path).split(sep).join('/')}`);
      if (node.isDirectory()) walk(path);
      else if (node.isFile() && entry.name.toLowerCase() === 'package.json' && !samePath(path, join(packageRoot, 'package.json')) && packageHasExecutionControl(parsePackage(path))) {
        fail(`Seeds package contains prohibited execution control: ${relative(packageRoot, path).split(sep).join('/')}`);
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

function existingTrustedJsonFile(path, name) {
  const bytes = Buffer.from('{}\n', 'utf8');
  let node;
  try {
    node = lstatSync(path);
  } catch {
    fail(`trusted ${name} is unavailable`);
  }
  if (node.isSymbolicLink() || !node.isFile() || node.size !== bytes.length || !readFileSync(path).equals(bytes)) fail(`trusted ${name} must be an owned inert JSON regular file`);
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

function capture(git, args, message, env, input) {
  const completed = spawnSync(git, args, { encoding: 'utf8', shell: false, windowsHide: true, env, input });
  if (completed.error || completed.status !== 0) fail(message);
  return (completed.stdout || '').trim();
}

function captureBytes(git, args, message, env) {
  const completed = spawnSync(git, args, { shell: false, windowsHide: true, env });
  if (completed.error || completed.status !== 0) fail(message);
  return completed.stdout;
}

function samePath(left, right) {
  if (process.platform === 'win32') return left.toLowerCase() === right.toLowerCase();
  return left === right;
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
    fail(`${label} is unavailable: ${path}`);
  }
  if (node.isSymbolicLink() || !node.isFile()) fail(`${label} must be a regular file: ${path}`);
  return path;
}

function metadataLine(path, label) {
  const file = rawRegularFile(path, label);
  const bytes = readFileSync(file, 'utf8');
  const line = bytes.endsWith('\n') ? bytes.slice(0, -1).replace(/\r$/, '') : bytes;
  if (!line || line.includes('\n') || line.includes('\0')) fail(`${label} is invalid: ${path}`);
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
    fail(`reviewed distribution must be an exact Git root: ${distribution}`);
  }
  if (node.isDirectory()) return metadataDirectory(marker, 'reviewed distribution Git directory');
  if (!node.isFile() || node.isSymbolicLink()) fail(`reviewed distribution must be an exact Git root: ${distribution}`);
  const reference = metadataLine(marker, 'reviewed distribution Git directory reference');
  if (!reference.startsWith('gitdir: ')) fail(`reviewed distribution must be an exact Git root: ${distribution}`);
  const location = reference.slice('gitdir: '.length);
  if (!location) fail(`reviewed distribution must be an exact Git root: ${distribution}`);
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
    fail('reviewed distribution has an invalid Git reference');
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
    if (!value.startsWith('ref: ')) fail('reviewed distribution HEAD must resolve to an exact commit');
    const reference = value.slice('ref: '.length);
    value = looseReference(reference, directories) || packedReference(reference, directories) || '';
  }
  fail('reviewed distribution HEAD must resolve to an exact commit');
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
    if (indexTree !== expectedTree) fail('reviewed distribution must have a clean Git tree and index');
    const indexed = captureBytes(git, ['ls-files', '--stage', '-z'], 'cannot enumerate indexed distribution files', environment);
    for (const record of indexed.toString('utf8').split('\0')) {
      if (!record) continue;
      const separator = record.indexOf('\t');
      const metadata = separator === -1 ? [] : record.slice(0, separator).split(' ');
      const path = separator === -1 ? '' : record.slice(separator + 1);
      if (metadata.length !== 3 || !/^[0-7]{6}$/.test(metadata[0]) || !/^[0-9a-f]{40,64}$/.test(metadata[1]) || metadata[2] !== '0' || !path) fail('reviewed distribution index is not an exact ordinary file tree');
      let bytes;
      try {
        bytes = readFileSync(join(distribution, path));
      } catch {
        fail('reviewed distribution must have a clean Git tree and index');
      }
      const actual = capture(git, ['hash-object', '--no-filters', '--stdin'], 'cannot hash tracked distribution file', environment, bytes);
      if (actual !== metadata[1]) fail('reviewed distribution must have a clean Git tree and index');
    }
    const untracked = capture(git, ['ls-files', '--others', '--exclude-standard'], 'cannot enumerate untracked distribution files', environment);
    const ignored = capture(git, ['ls-files', '--others', '--ignored', '--exclude-standard'], 'cannot enumerate ignored distribution files', environment);
    if (untracked || ignored) fail('reviewed distribution must contain no untracked or ignored files');
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
  if (process.versions.node !== NODE_VERSION) fail(`launcher Node version mismatch: expected ${NODE_VERSION}, got ${process.versions.node}`);
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
  if (node.isSymbolicLink() || !node.isFile() || node.size !== bytes.length || !readFileSync(path).equals(bytes)) fail(`trusted ${name} must be an owned inert JSON regular file`);
  if (process.platform !== 'win32' && node.uid !== process.getuid()) fail(`trusted ${name} is not owned by this user`);
  if (process.platform !== 'win32') chmodSync(path, 0o600);
  return realRegularFile(path, `trusted ${name}`);
}

function bootstrap(distributionArgument) {
  const distribution = realDirectory(distributionArgument, 'reviewed distribution');
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
  if (!Object.values(roots).every((value) => isAbsolute(value))) fail('mise must return absolute exact tool roots');
  const tuple = validateTuple(roots);
  const launcher = currentLauncher();
  const bunfig = trustedEmptyFile(directory, 'trusted-bunfig.toml');
  const tsconfig = trustedEmptyJsonFile(directory, 'trusted-tsconfig.json');
  const gitconfig = trustedEmptyFile(directory, 'trusted-gitconfig');
  const distributionHashes = { tree: distributionTreeHash(distribution), gitTree: git.tree, miseToml: hashFile(miseToml), miseLock: hashFile(miseLock), commit: hashBytes(Buffer.from(git.commit, 'utf8')) };
  const receipt = {
    schema: SCHEMA,
    platform: process.platform,
    createdAt: new Date().toISOString(),
    distribution: { root: distribution, commit: git.commit, gitTree: git.tree, tree: distributionHashes.tree, miseToml: distributionHashes.miseToml, miseLock: distributionHashes.miseLock, launcher, launcherHash: hashFile(launcher) },
    tuple: {
      node: { root: tuple.nodeRoot, executable: tuple.node, version: NODE_VERSION },
      bun: { root: tuple.bunRoot, executable: tuple.bun, version: BUN_VERSION },
      seeds: { root: tuple.seedsRoot, packageRoot: tuple.packageRoot, package: SEEDS_PACKAGE, version: SEEDS_VERSION, bin: SEEDS_BIN, binValue: tuple.binValue, entry: tuple.entry },
      git,
      trusted: { bunfig, tsconfig, gitconfig },
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
      bunfig: hashFile(bunfig),
      tsconfig: hashFile(tsconfig),
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

function exactKeys(value, keys) {
  if (!object(value)) return false;
  const actual = Object.keys(value);
  return actual.length === keys.size && actual.every((key) => keys.has(key));
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
  if (!exactKeys(receipt, RECEIPT_KEYS) || receipt.schema !== SCHEMA || receipt.platform !== process.platform || !text(receipt.createdAt)
    || !exactKeys(receipt.distribution, DISTRIBUTION_KEYS) || !exactKeys(receipt.tuple, TUPLE_KEYS) || !exactKeys(receipt.hashes, HASH_KEYS)
    || !exactKeys(receipt.hashes.distribution, DISTRIBUTION_HASH_KEYS)) {
    fail('active tuple receipt is partial or invalid');
  }
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  const distribution = receipt.distribution;
  const distributionHashes = receipt.hashes.distribution;
  if (!exactKeys(node, NODE_KEYS) || !exactKeys(bun, BUN_KEYS) || !exactKeys(seeds, SEEDS_KEYS) || !exactKeys(git, GIT_KEYS) || !exactKeys(trusted, TRUSTED_KEYS)
    || node.version !== NODE_VERSION || bun.version !== BUN_VERSION || seeds.package !== SEEDS_PACKAGE || seeds.version !== SEEDS_VERSION || seeds.bin !== SEEDS_BIN
    || ![node.root, node.executable, bun.root, bun.executable, seeds.root, seeds.packageRoot, seeds.binValue, seeds.entry, git.path, git.hash, git.commit, git.tree, trusted.bunfig, trusted.tsconfig, trusted.gitconfig].every(text)
    || ![distribution.root, distribution.commit, distribution.gitTree, distribution.tree, distribution.miseToml, distribution.miseLock, distribution.launcher, distribution.launcherHash].every(text)
    || ![distributionHashes.tree, distributionHashes.gitTree, distributionHashes.miseToml, distributionHashes.miseLock, distributionHashes.commit].every(text)
    || distribution.commit !== git.commit || distribution.gitTree !== git.tree
    || distribution.tree !== distributionHashes.tree || distribution.miseToml !== distributionHashes.miseToml || distribution.miseLock !== distributionHashes.miseLock
    || distributionHashes.commit !== hashBytes(Buffer.from(distribution.commit, 'utf8'))
    || samePath(distribution.root, distribution.launcher)) {
    fail('active tuple receipt is partial or invalid');
  }
  return receipt;
}

function checkCurrentReceipt(receipt) {
  const { node, bun, seeds, git, trusted } = receipt.tuple;
  const expected = receipt.hashes;
  if (![expected.node, expected.nodeExecutable, expected.bun, expected.seeds, expected.packageJson, expected.entry, expected.git, expected.bunfig, expected.tsconfig, expected.gitconfig].every(text)) fail('active tuple receipt is partial or invalid');
  const tuple = validateTuple({ node: node.root, bun: bun.root, seeds: seeds.root });
  if (tuple.node !== node.executable || tuple.bun !== bun.executable || tuple.packageRoot !== seeds.packageRoot || tuple.binValue !== seeds.binValue || tuple.entry !== seeds.entry) fail('active tuple receipt does not match exact platform layout');
  const executingNode = realRegularFile(process.execPath, 'executing Node');
  if (!samePath(executingNode, node.executable) || hashFile(executingNode) !== expected.nodeExecutable) fail('executing Node does not match exact recorded Node');
  if (treeHash(node.root) !== expected.node || treeHash(bun.root) !== expected.bun || treeHash(seeds.root) !== expected.seeds || hashFile(tuple.packageJson) !== expected.packageJson || hashFile(tuple.entry) !== expected.entry) fail('exact tuple hash drift detected');
  if (realRegularFile(git.path, 'recorded Git executable') !== git.path || hashFile(git.path) !== expected.git || hashFile(git.path) !== git.hash) fail('recorded Git executable hash drift detected');
  const launcher = currentLauncher();
  if (!samePath(launcher, receipt.distribution.launcher) || hashFile(launcher) !== receipt.distribution.launcherHash) fail('current installed launcher identity or hash drift detected');
  const bunfig = existingTrustedEmptyFile(trusted.bunfig, 'trusted-bunfig.toml');
  const tsconfig = existingTrustedJsonFile(trusted.tsconfig, 'trusted-tsconfig.json');
  const gitconfig = existingTrustedEmptyFile(trusted.gitconfig, 'trusted-gitconfig');
  if (bunfig !== trusted.bunfig || tsconfig !== trusted.tsconfig || gitconfig !== trusted.gitconfig
    || hashFile(bunfig) !== expected.bunfig || hashFile(tsconfig) !== expected.tsconfig || hashFile(gitconfig) !== expected.gitconfig) fail('trusted configuration hash drift detected');
  return { ...tuple, bunfig, tsconfig, gitconfig, git: git.path };
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
  const child = spawn(tuple.bun, [`--config=${tuple.bunfig}`, '--no-macros', '--no-env-file', '--no-install', tuple.entry, ...args], {
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
  exactLauncherNode();
  const command = parse(process.argv.slice(2));
  if (command.mode === 'bootstrap') bootstrap(command.distribution);
  else inspect(command.target, command.args);
} catch (error) {
  process.stderr.write(`${error instanceof LauncherError ? error.message : `launcher failure: ${error.message}`}\n`);
  process.exitCode = 2;
}
