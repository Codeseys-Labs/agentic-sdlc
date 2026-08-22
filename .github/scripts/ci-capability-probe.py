# advisory forensics probe for seed agentic-sdlc-df5f (mechanisms A/B1/B2);
# remove once the runner's btime/ctime data is recorded. Never a gate leaf:
# every section prints-and-continues and the workflow step cannot fail the job.
import ctypes
import errno as errno_mod
import os
import struct
import subprocess
import tempfile
import time
import traceback


def _section(title):
    print("=== SECTION: %s ===" % title, flush=True)


def _statx_btime_ns_and_ino(path):
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, "statx"):
        raise OSError(0, "libc has no statx symbol")
    libc.statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
    libc.statx.restype = ctypes.c_int
    buf = ctypes.create_string_buffer(256)
    at_fdcwd = -100
    statx_basic_stats = 0x7FF
    statx_btime = 0x800
    rc = libc.statx(at_fdcwd, os.fsencode(path), 0, statx_basic_stats | statx_btime, buf)
    if rc != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e))
    mask = struct.unpack_from("<I", buf, 0)[0]
    ino = struct.unpack_from("<Q", buf, 32)[0]
    sec = struct.unpack_from("<q", buf, 80)[0]
    nsec = struct.unpack_from("<I", buf, 88)[0]
    have_btime = bool(mask & statx_btime)
    return have_btime, ino, sec * 10**9 + nsec


_section("1. uname / kernel version")
try:
    print("uname -a:", " ".join(os.uname()))
    try:
        with open("/proc/version") as f:
            print("/proc/version:", f.read().strip())
    except Exception as e:
        print("/proc/version unavailable:", repr(e))
except Exception:
    traceback.print_exc()

_section("2. workspace filesystem")
try:
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    print("workspace path:", workspace)
    found = False
    try:
        result = subprocess.run(
            ["findmnt", "-no", "FSTYPE,SOURCE,OPTIONS", "-T", workspace],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            print("findmnt:", result.stdout.strip())
            found = True
        else:
            print("findmnt failed rc=%r stderr=%r" % (result.returncode, result.stderr.strip()))
    except Exception as e:
        print("findmnt unavailable:", repr(e))
    if not found:
        real_ws = os.path.realpath(workspace)
        best = None
        try:
            with open("/proc/self/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    src, mnt, fstype, opts = parts[0], parts[1], parts[2], parts[3]
                    mnt_decoded = mnt.replace("\\040", " ")
                    if real_ws == mnt_decoded or real_ws.startswith(mnt_decoded.rstrip("/") + "/") or mnt_decoded == "/":
                        if best is None or len(mnt_decoded) > len(best[1]):
                            best = (src, mnt_decoded, fstype, opts)
            if best:
                print("/proc/self/mounts fallback: source=%s mount=%s fstype=%s options=%s" % best)
            else:
                print("/proc/self/mounts fallback: no matching mount found")
        except Exception as e:
            print("/proc/self/mounts fallback failed:", repr(e))
except Exception:
    traceback.print_exc()

_section("3. linkat AT_EMPTY_PATH probe (O_TMPFILE)")
try:
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    with tempfile.TemporaryDirectory(dir=workspace) as td:
        print("probe tempdir:", td)
        o_tmpfile = getattr(os, "O_TMPFILE", 0o20200000)
        tmp_fd = None
        try:
            tmp_fd = os.open(td, o_tmpfile | os.O_WRONLY, 0o600)
            print("O_TMPFILE open: SUCCESS fd=%d" % tmp_fd)
        except OSError as e:
            print(
                "O_TMPFILE open: UNSUPPORTED errno=%d (%s): %s"
                % (e.errno, errno_mod.errorcode.get(e.errno, "?"), e.strerror)
            )
        if tmp_fd is not None:
            dir_fd = None
            try:
                dir_fd = os.open(td, os.O_RDONLY)
                libc = ctypes.CDLL(None, use_errno=True)
                libc.linkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
                libc.linkat.restype = ctypes.c_int
                at_empty_path = 0x1000
                target_name = b"linkat-probe-target"
                rc = libc.linkat(tmp_fd, b"", dir_fd, target_name, at_empty_path)
                if rc == 0:
                    print("linkat AT_EMPTY_PATH: SUCCESS (materialized %s)" % target_name.decode())
                else:
                    err = ctypes.get_errno()
                    print(
                        "linkat AT_EMPTY_PATH: FAILED errno=%d (%s): %s"
                        % (err, errno_mod.errorcode.get(err, "?"), os.strerror(err))
                    )
            except Exception as e:
                print("linkat probe raised:", repr(e))
            finally:
                if dir_fd is not None:
                    os.close(dir_fd)
                os.close(tmp_fd)
except Exception:
    traceback.print_exc()

_section("4. btime granularity")
try:
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    with tempfile.TemporaryDirectory(dir=workspace) as td:
        samples = []
        have_any = False
        t0 = time.monotonic_ns()
        for i in range(40):
            p = os.path.join(td, "btime-%02d.txt" % i)
            with open(p, "wb") as f:
                f.write(b"x")
            try:
                have, ino, btime_ns = _statx_btime_ns_and_ino(p)
                have_any = have_any or have
                samples.append((have, btime_ns))
            except Exception as e:
                samples.append((False, None))
                print("  statx failed on sample %d: %r" % (i, e))
        print("sample window wall elapsed ns:", time.monotonic_ns() - t0)
        available = [b for (have, b) in samples if have and b is not None]
        print("btime available at all:", have_any, "usable samples:", len(available), "/", len(samples))
        if available:
            distinct = sorted(set(available))
            deltas = [b - a for a, b in zip(available, available[1:])]
            print("distinct btime count:", len(distinct))
            print("btime min delta ns (consecutive):", min(deltas) if deltas else None)
            print("btime max delta ns (consecutive):", max(deltas) if deltas else None)
            print("btime overall span ns:", max(available) - min(available))
        else:
            print("no usable btime samples collected")

        b1_path = os.path.join(td, "b1-recreate.txt")
        b1_repeats = 0
        for trial in range(20):
            with open(b1_path, "wb") as f:
                f.write(b"a")
            have1, ino1, bt1 = _statx_btime_ns_and_ino(b1_path)
            os.remove(b1_path)
            with open(b1_path, "wb") as f:
                f.write(b"b")
            have2, ino2, bt2 = _statx_btime_ns_and_ino(b1_path)
            os.remove(b1_path)
            print("B1 witness: first (ino=%r, btime_ns=%r) second (ino=%r, btime_ns=%r)" % (ino1, bt1, ino2, bt2))
            print(
                "B1 witness pair repeated (ino AND btime both equal):",
                "UNAVAILABLE-btime (witness is degenerate; treat as REPEATED)" if not (have1 and have2) else (ino1, bt1) == (ino2, bt2),
            )
            if (ino1, bt1) == (ino2, bt2):
                b1_repeats += 1
        print("B1 witness repeats: %d/20" % b1_repeats)
except Exception:
    traceback.print_exc()

_section("5. ctime_ns / mtime_ns granularity")
try:
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    with tempfile.TemporaryDirectory(dir=workspace) as td:
        ctimes = []
        mtimes = []
        t0 = time.monotonic_ns()
        for i in range(40):
            p = os.path.join(td, "ct-%02d.txt" % i)
            with open(p, "wb") as f:
                f.write(b"x")
            st = os.stat(p)
            ctimes.append(st.st_ctime_ns)
            mtimes.append(st.st_mtime_ns)
        print("sample window wall elapsed ns:", time.monotonic_ns() - t0)

        def _summarize(name, values):
            distinct = sorted(set(values))
            deltas = [b - a for a, b in zip(values, values[1:])]
            nonzero = [d for d in deltas if d > 0]
            print("%s distinct count: %d / %d samples" % (name, len(distinct), len(values)))
            print("%s min delta ns (consecutive, incl. zero): %r" % (name, min(deltas) if deltas else None))
            print("%s min nonzero delta ns: %r" % (name, min(nonzero) if nonzero else None))
            print("%s max delta ns: %r" % (name, max(deltas) if deltas else None))

        _summarize("ctime_ns", ctimes)
        _summarize("mtime_ns", mtimes)
except Exception:
    traceback.print_exc()

_section("6. effective capabilities")
try:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("CapEff:"):
                print(line.strip())
                break
        else:
            print("CapEff line not found in /proc/self/status")
except Exception:
    traceback.print_exc()
