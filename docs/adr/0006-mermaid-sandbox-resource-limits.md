# ADR-0006 — Two Mermaid sandbox limits are recalibrated as resource-availability ceilings for the pinned browser, and the output-size controls stay put

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (measurement and implementation)
- **Relates to:** `policy/mermaid-renderer-linux-v1.json`,
  `scripts/render_mermaid_linux.py`, `scripts/sanitize_mermaid_svg.mjs`,
  `scripts/validate_bundle.py` (`MERMAID_POLICY_SHA256`),
  `tests_linux/test_mermaid_renderer_e2e.py`, the "Linux Mermaid renderer
  boundary" section of `AGENTS.md`

## Context

The Linux M0b Mermaid renderer runs a pinned `chrome-headless-shell` over
untrusted diagram text inside `bwrap`, with network unshared and every config
owner-generated. Its policy document is pinned by exact SHA-256 in
`scripts/validate_bundle.py`, so no limit can be loosened without failing the
repository gate — that is the property this record is spending.

Provisioning succeeded on a Linux x64 host, but no diagram could be rendered.
Two of the policy's limits were calibrated below what the pinned browser
actually needs, and both failures were isolated by measurement rather than
inference:

1. **`max_rss_bytes` (384 MiB) was exceeded on every render.** The wrapper polls
   the summed resident memory of the sandboxed process tree and kills it past the
   cap. The shipped value tripped at **406,355,968 bytes observed** against
   `402,653,184` — a hard stop before any SVG existed.
2. **`max_output_file_bytes` (512 KiB) killed the browser mid-session.** It is
   applied as `RLIMIT_FSIZE`, which the kernel charges against **every** file the
   process writes, not the SVG alone. The failure surfaced as a puppeteer
   `Connection closed` while closing the page, which reads like a browser crash
   and not like a limit at all.

**Measured on this host, with the trusted flowchart fixture and the pinned
browser 150.0.7871.24.** Both bisections toggled one variable and held the other
at a known-generous value, so neither number is inferred from the other:

- **RSS.** With `RLIMIT_FSIZE` generous, peak summed process-tree RSS across
  repeated renders was **605.2, 618.5, 621.9, 622.3 MiB** for the 58-byte
  fixture. A deliberately heavier 120-edge flowchart peaked at **684.3, 688.0,
  690.1 MiB**, and a 65,477-byte definition at the `max_input_bytes` ceiling
  peaked at **615.1 MiB** — diagram *complexity*, not input length, drives the
  peak. The port's earlier reading of ~565–597 MiB is consistent but low; this
  record uses the higher figure it measured directly.
- **`RLIMIT_FSIZE`.** With RSS generous: 512 KiB **fails**, 1 MiB **fails**,
  2 MiB, 3 MiB, 4 MiB, 16 MiB, 64 MiB, and 256 MiB all **render**. The threshold
  is an order of magnitude below the 64 MiB the port had reported as its lower
  verified bound. Inspecting the private workspace immediately before teardown
  shows what is actually being written and why the SVG is not the constraint:
  a 393,872-byte fontconfig cache, three 270,336-byte GPU/Dawn cache blobs,
  three 262,512-byte cache indexes — about 2.5 MB of browser bookkeeping
  against a 13,064-byte published SVG.

The load-bearing correction is the second one. `max_output_file_bytes` sits in a
`limits` block beside `max_raw_bytes` and `max_final_bytes` and reads like a
third size control, which is how it came to be set at 512 KiB — the same value
as `max_raw_bytes`. It is not one. SVG size is bounded independently and
redundantly at four points: the wrapper checks `raw.svg` against
`max_raw_bytes` after the render child exits, the sanitizer re-checks the raw
text against `max_raw_bytes` before it will parse it, the sanitizer checks the
serialized result against `max_final_bytes` before writing, and the wrapper's
`validate_final_svg` re-checks `max_final_bytes` on both the returned bytes and
the staged file before publication. Raising `RLIMIT_FSIZE` loosens none of that.

This is confirmed rather than argued: the 120-edge flowchart, with both ceilings
generous, is rejected by `max_final_bytes` in the sanitizer — the independent
size control refusing an oversized diagram exactly as intended, while the
resource ceilings stayed out of its way.

## Decision

1. **`max_rss_bytes`: 402,653,184 → 1,610,612,736 (1.5 GiB).** The smallest
   round value comfortably above the measured worst case, at ~2.3x the 690 MiB
   complex-diagram peak and ~2.5x the fixture's ~620 MiB. The operator's default
   suggestion was 1 GiB against a reported ~565–597 MiB peak; this host measured
   690 MiB, which leaves 1 GiB at only ~1.5x and inside the run-to-run spread
   observed on a loaded machine. Verified: renders at this value.
2. **`max_output_file_bytes`: 524,288 → 67,108,864 (64 MiB).** Of the two values
   the port verified, this is the tighter one, and it is the one chosen. It is
   ~26x the ~2.5 MB of browser bookkeeping actually observed and ~17x the
   measured 4 MiB pass threshold — enough headroom for a heavier profile without
   granting the 256 MiB alternative's much larger runaway-write budget. Its role
   is bounding disk writes, nothing else.
3. **These two are recorded in the policy as resource-availability ceilings, not
   size controls.** A new top-level `limits_note` states that
   `max_output_file_bytes` is `RLIMIT_FSIZE` over all browser writes, that SVG
   size is controlled by `max_raw_bytes`/`max_final_bytes`, and that a browser
   pin bump re-opens the calibration. A gate test in
   `tests/test_mermaid_renderer_gate.py` pins both calibrated values, the two
   size controls, the process budget, and the timeouts, so a future reader cannot
   "tighten" `max_output_file_bytes` back toward an SVG-shaped number without the
   test stating why that breaks rendering.
4. **`MERMAID_POLICY_SHA256` is repinned in the same change:**
   `4df1c81ae47413ebbc96e918f792677a966cd690a9f542518a1f5b1be2cf9514` →
   `ee669a8ee36c085713071e91cb1b2b38c75f28dec9a0cfbbc1cd86559ca6ecce`. A
   digest-pinned policy edited without its digest is a broken gate, not a
   loosened one.
5. **Nothing else moves.** Explicitly unchanged: `max_raw_bytes` (524,288) and
   `max_final_bytes` (262,144); `max_processes` (16) and the relative task-census
   budget the port correctly built around it, because `RLIMIT_NPROC` is charged
   per-UID against threads and an absolute cap refuses `bwrap`'s own namespace
   setup on any real session; `max_input_bytes`; `max_descriptors`;
   `concurrency`; all three wall-clock timeouts (20/15/40s); the sanitizer
   element, attribute, URI, and CSS allowlists; the `bwrap` required and
   forbidden argument sets, including `--unshare-net`; and the pinned browser
   identity, executable digest, and cache-tree digest.
6. **Rendering remains advisory.** It is not a gate leaf, not a bootstrap
   prerequisite, and `mise run check` stays green on a host that has never
   provisioned the runtime. This record raises two ceilings; it grants the
   renderer no authority it did not have.

## Consequences

- Positive: the renderer works. The pipeline renders the fixture end to end and
  the published output is byte-identical across separate process invocations
  (SHA-256 `4e0b2c05…`, 13,064 bytes, three consecutive runs), validating against
  the shipped sanitizer allowlist unmodified.
- Positive: the two limits now carry their rationale in the policy itself and in
  a gate test, so the misreading that produced the original 512 KiB value is
  documented at the point where someone would repeat it.
- Negative: a sandboxed render may now hold up to 1.5 GiB resident and write up
  to 64 MiB inside its private workspace. On a memory-constrained host a render
  can therefore contribute to pressure it previously could not. `concurrency`
  stays at 1 and the workspace is removed on every exit path, which bounds the
  exposure to one render at a time.
- Negative: both numbers are calibrated against one browser pin on one host
  (Linux x64, 6 CPUs, 24 GB). They are ceilings, not measurements of a
  guarantee, and a different host may peak elsewhere.
- Neutral: the SVG size an operator can publish is unchanged. `max_final_bytes`
  still refuses a diagram more complex than the fixture, which is the observed
  behavior of the 120-edge flowchart and not a regression introduced here.
- **Confirmation:** `MERMAID_M0B_E2E=1` against
  `tests_linux/test_mermaid_renderer_e2e.py` failed before this change on the
  RSS cap and passes after it, run twice (4 tests, 1 named skip, OK both times);
  three separate renderer invocations published byte-identical SVG;
  `tests/test_mermaid_renderer`, `tests/test_mermaid_renderer_gate`, and
  `tests/test_gate_graph` pass; `scripts/validate_bundle.py` reports 0 errors.

## Reversal condition

A bump to the pinned `chrome-headless-shell` build re-opens both numbers and
they must be **re-measured, not assumed** — this browser's peak RSS and write
volume are properties of that build, and the browser digest and cache-tree
digest in the same policy already force a deliberate edit at that moment. Two
other triggers: if a render is ever observed peaking near 1.5 GiB, the right
response is to investigate what changed rather than to raise the ceiling again;
and if `RLIMIT_FSIZE` ever becomes the failing limit, the workspace write
inventory above is the measurement to redo, because the answer will be a
browser-behavior change and not an SVG that grew.

This record is evidence for a conductor to cite; it authorizes no push,
publication, merge, deployment, provisioning download, or other outward effect
on its own.
