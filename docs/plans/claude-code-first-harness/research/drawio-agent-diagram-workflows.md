# Draw.io / diagrams.net agent diagram workflows

**Research status:** complete — decision-sufficient primary-source review, 2026-08-14

## Question and gated decision

**Question.** What can an agent safely author, validate, preview, render, and maintain as
editable draw.io / diagrams.net diagrams, and what evidence should gate an optional sister
skill family's umbrella-versus-per-diagram-type selection surface?

**Decision gated.** Whether and how this repository should expose an optional draw.io skill
family alongside its Mermaid capabilities, without designing that family beyond the evidence.

## Scope and evidence labels

- **Verified** — observed in cited first-party source code, an official repository artifact,
  or a local repository control at the inspected revision.
- **Documented** — asserted by the owner in official documentation or by the article author
  about that author's own demonstrated workflow; not independently reproduced here.
- **Inferred** — a bounded recommendation derived from verified/documented facts; it is not
  itself a product guarantee.

The May 2026 Matheus Costa article is admissible only as primary evidence of its author's
own workflow. Technical claims about draw.io, Kiro, and Agent Skills require first-party
confirmation.

## Local decision constraints (established before external research)

1. **Verified — current Mermaid rendering is a materially hardened local boundary, not just
   a CLI invocation.** The repository pins Mermaid/CLI/Parser/Puppeteer/Chrome identities,
   requires `bwrap`, denies network access, owner-generates configs, rejects source URIs and
   inline init directives, validates and sanitizes SVG, applies size/time/process/memory/file
   limits, publishes atomically, and records a runtime receipt. It is explicitly advisory,
   absent from `mise run check`, and Linux x64 only. Sources:
   [`AGENTS.md`](../../../AGENTS.md),
   [`policy/mermaid-renderer-linux-v1.json`](../../../policy/mermaid-renderer-linux-v1.json),
   [`scripts/render_mermaid_linux.py`](../../../scripts/render_mermaid_linux.py), and
   [ADR-0006](../../../docs/adr/0006-mermaid-sandbox-resource-limits.md).
2. **Verified — an external renderer must not become a hidden bootstrap prerequisite.** An
   earlier `npm:@mermaid-js/mermaid-cli` mise pin was removed because its transitive browser
   postinstall required a system unzip tool and wrote an unreviewed browser outside the
   repository's provenance boundary. Optional provisioning may remain explicit and outside
   the gate graph. Source: [ADR-0002](../../../docs/adr/0002-mise-is-the-single-front-door.md).
3. **Verified — a top-level skill needs more than technical feasibility.** The repository's
   authoring doctrine requires: a description that selects the skill against its nearest
   neighbor; proportional selection-surface cost; a trigger that exists now; and task-shaped,
   not always-on, behavior. Promotion additionally needs at least two of recurrence, specific
   sequencing, repeated buried failures, a stable input/output contract, or an explicit handoff
   benefit. A focused `references/*.md` is the cheaper default. Source:
   [`skills/agentic-sdlc/references/skill-authoring.md`](../../../skills/agentic-sdlc/references/skill-authoring.md).

## Recommendation

**Conditional GO for one optional umbrella authoring skill; NO-GO for one top-level skill
per diagram type; DEFER a repository-owned render promise. Confidence: high (0.87) on the
selection shape, medium-high (0.78) on the safe author/validate boundary, and low (0.35) on
cross-platform deterministic rendering until the experiment below is run.**

1. **Expose at most one generic draw.io selection row initially.** Its distinguishing trigger
   is an editable native canvas artifact: `.drawio` source, draw.io libraries/stencils,
   explicit geometry, layers/pages/metadata, or an editable PNG/SVG/PDF handoff. Requests whose
   desired source of truth is concise text and whose shapes fit Mermaid should stay on this
   repository's existing Mermaid path. This is an **inferred** selector, grounded by draw.io's
   own single umbrella skill, which chooses Mermaid conversion versus XML internally instead of
   publishing flowchart/UML/ER/sequence siblings ([official draw.io skill at inspected commit](https://github.com/jgraph/drawio-mcp/blob/14b318b19cc37b159f841227b9d11fbd18ce18ea/plugins/codex/drawio/skills/drawio/SKILL.md)).
2. **Keep flowchart, sequence, class, ER, network, wireframe, and similar type guidance as
   on-demand references/assets under the umbrella.** File grammar, validation, security,
   preview, export, and provenance do not change merely because the visual notation changes.
   A type gets a top-level sibling only after it presents decision evidence described in
   "Selection-surface gate" below. Diagram-type names alone are not enough.
3. **Admit native authoring and deterministic validation before rendering.** The safe default
   artifact is bounded, UTF-8, uncompressed `.drawio` XML with no comments, no remote resources,
   no executable/interactive embed formats, and stable IDs. Validate with a hardened XML parser,
   the official XSD, and repository-owned semantic/security checks. XSD success alone is not a
   verdict.
4. **Treat every preview or export as a separate capability with an honest receipt.** A browser
   `#create` preview is an explicit network/browser action, not validation. Local draw.io Desktop
   export is technically supported, but this repository has not pinned, sandboxed, bounded, or
   measured it. Do not describe it as equivalent to the existing Mermaid renderer. Until a
   cheapest-decisive render experiment passes, an umbrella skill may detect and explain an
   operator-installed desktop CLI, but it should not claim a certified render path or make it a
   bootstrap/gate dependency.
5. **Keep `.drawio` as canonical source even when an editable image is delivered.** `--embed-diagram`
   can place XML into PNG/SVG/PDF, but official documentation warns that third-party SVG consumers
   may strip that metadata. A render is derived evidence; it must not become the only maintained
   copy ([official export comparison](https://www.drawio.com/docs/manual/export/export-diagram/)).

### Safe capability boundary

| Operation | Decision now | Required boundary |
|---|---|---|
| Author new editable source | **Admit** | Uncompressed `.drawio` XML; full `mxfile` wrapper; bounded UTF-8 regular file; stable unique IDs; no comments; built-in or pinned/locally reviewed shapes only; no remote URI/font/image/library by default. |
| Update an existing diagram | **Admit conditionally** | Parse safely; preserve unknown attributes/elements/pages/layers and user coordinates; edit the smallest semantic unit; re-run all checks; never round-trip through a lossy image. |
| Parse compressed source | **Read-only compatibility, conditional** | Bounded Base64 + raw-DEFLATE expansion with a strict decompressed-size/ratio cap; normalize to uncompressed XML before agent editing. Never generate compressed source. |
| Validate | **Admit** | Hardened parser + official XSD + semantic graph checks + URI/embed policy + size/depth/count limits. Diagnostics must be content-sanitized before returning to a model. |
| Browser preview / URL | **Opt-in only** | Validation first; disclose that the browser loads `app.diagrams.net`; refuse sensitive content by default; avoid URL mode for large diagrams; never treat opening success as a gate. |
| Local desktop preview | **Conditional** | Sanitized source, update check disabled, dedicated private profile, no external resource references, and explicit operator-installed CLI/app. Opening is still not validation. |
| PNG/SVG/PDF export | **Technically feasible, not certified here** | Pin exact desktop build/artifact, isolate network/profile/filesystem, bound resources/time/output, pin fonts and libraries, sanitize/validate the derived file, and write a source-to-render receipt. |
| Hosted MCP inline preview | **Outside safe default** | Official hosted app-server use sends the diagram in the MCP request; require explicit data-egress approval or self-host. |
| Maintain in version control | **Admit** | Canonical uncompressed `.drawio` plus optional derived render and receipt; normalized volatile metadata; semantic validation; visual review for meaningful changes. |

### Selection-surface gate for any per-type sibling

A proposed per-type skill must supply all of the following evidence; otherwise it remains a
reference beneath the umbrella:

1. **Distinct selection sentence:** a description can select it against both the generic draw.io
   umbrella and Mermaid without reading its body. Kiro documents that name/description metadata
   is loaded first and the description determines activation; wrong activation is addressed by
   differentiating descriptions ([Kiro Agent Skills](https://kiro.dev/docs/skills/)).
2. **Different workflow, not merely different notation:** domain discovery or inputs, mandatory
   questions, specialized output contract, or a distinct review handoff. The current AWS skill,
   for example, scans IaC, extracts services/relationships, asks for a diagram type, applies an
   AWS-specific style, and emits under `docs/` ([AWS skill](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/skills/aws-architecture-diagram/SKILL.md)).
3. **Machine-checkable specialization:** a maintained shape/icon registry, notation semantics,
   or deterministic post-checks beyond the generic XSD. AWS has a static AWS4 registry plus checks
   for shape names, edge endpoints, required geometry, minimum fonts, and dark-mode constraints
   ([AWS validator](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/scripts/lib/validate_drawio.py)).
4. **Evidence of recurrence and handoff value:** satisfy this repository's four admission gates
   and at least two of its five promotion criteria with actual requests or failure history, not a
   catalog of diagram names.
5. **Maintenance owner and provenance:** name the upstream library/template/icon source, license,
   pinned revision, refresh procedure, fixtures, and rejection behavior when the library drifts.
   Remote icon search is not a provenance strategy.

AWS therefore demonstrates that specialization *can* be justified; it does not prove that this
repository currently needs an AWS sibling or authorize copying the AWS plugin. Its bytes remain
foreign, and the live-trigger/recurrence evidence for this bundle was not part of this question.

## Evidence

### 1. The demonstrated Matheus Costa workflow — and its actual boundary

1. **Documented — article installation path.** The 12 May 2026 article tells a Kiro CLI user
   to install Python 3.10+, `uv`, Bun, `defusedxml`, and optionally draw.io Desktop; run
   `@every-env/compound-plugin` against `awslabs/agent-plugins` to install `deploy-on-aws`
   globally into `~/.kiro`; repair an observed extra `.kiro/.kiro/skills` nesting if present;
   add AWS knowledge/documentation/IaC/pricing MCP servers; and remove the discontinued diagram
   MCP server. The article reports two installed skills, `aws-architecture-diagram` and `deploy`.
   It is primary evidence only for what that author did
   ([article](https://matheuscosta.dev/posts/2026/05/generating-aws-architecture-diagrams-with-kiro-cli-and-agent-skills/)).
2. **Documented — article generation path.** The author invokes Kiro either from a natural-language
   AWS design prompt or from an existing project; the skill is said to detect CloudFormation,
   CDK, Terraform, and Docker; explicit skill naming is the fallback when activation misses.
   Requested variants include sketch mode, no legend, and PNG export. The reported output is
   uncompressed editable `.drawio` XML using AWS4 icons, orthogonal edges, badges, category
   containers, a legend, and adaptive colors. Again, that documents this author's observed
   workflow, not a general draw.io guarantee ([article](https://matheuscosta.dev/posts/2026/05/generating-aws-architecture-diagrams-with-kiro-cli-and-agent-skills/)).
3. **Verified — the current AWS plugin supports the core skill workflow.** At inspected commit
   `bab56a3b`, its AWS skill has codebase-analysis and brainstorming modes, loads references only
   at generation time, requires uncompressed full-wrapper XML, calls a postprocessor/validator,
   produces a `#create` preview URL after validation, and optionally calls Desktop for export
   ([skill](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/skills/aws-architecture-diagram/SKILL.md)).
4. **Verified — automatic validation is not established in the article's Kiro path.** AWS labels
   the Kiro conversion experimental and states that hooks are currently dropped because Claude
   and Kiro hook models are not 1:1
   ([AWS repository README](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/README.md)).
   The validator is wired as a Claude `PostToolUse` hook, not as a Kiro-native gate
   ([hook manifest](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/hooks/hooks.json)).
   Therefore installing `defusedxml` does not by itself cause validation. The article's
   "automatic XML validation" conclusion should be treated as unsupported for the exact
   converted Kiro setup unless a current Kiro hook/explicit validator run is demonstrated.
5. **Verified — even the Claude hook is advisory/fail-open as a gate.** If `defusedxml` is missing,
   the shell hook emits an install prompt and exits 0. It ignores postprocessor/validator command
   failures with `|| true`, recognizes success by grepping text, reports the result as a
   `systemMessage`, and always exits 0
   ([validation hook](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/scripts/validate-drawio.sh)).
   It is useful feedback, not a blocking validation receipt. A sister skill must not inherit its
   "automatic" wording without a fail-closed explicit command and exit-status contract.
6. **Inferred — the article demonstrates editable-source value, not a reusable generic skill
   architecture.** The high-value evidence is that an agent can create a useful editable XML
   artifact using a constrained icon/style corpus and deterministic checks. Its global install,
   unpinned `@latest` MCP commands, third-party converter, AWS credentials, and AWS-only layout
   rules are neither prerequisites nor defaults for a generic draw.io capability in this bundle.

### 2. Editable XML and compression

1. **Documented — native source is XML.** draw.io now publishes an AI-generation reference and
   an `mxfile.xsd`. A full document is `<mxfile>` containing one or more `<diagram>` pages, each
   with an `<mxGraphModel><root>...`; cells `0` and `1` are the root/default layer
   ([official generation reference](https://www.drawio.com/docs/reference/diagram-generation/)).
   The full wrapper can also carry page names, file variables, host/agent/version/modified
   metadata, and multiple pages. Those metadata fields identify a producer but do not attest it.
2. **Documented — AI should generate uncompressed XML.** Native saves may put Base64 text inside
   `<diagram>` after `encodeURIComponent`, raw DEFLATE, and Base64. draw.io explicitly tells AI
   systems not to generate that representation because it is opaque, larger in tokens, and not
   directly debuggable/validatable
   ([official generation reference](https://www.drawio.com/docs/reference/diagram-generation/)).
3. **Inferred — accept compressed input only through a bomb-resistant compatibility decoder.**
   Existing human-edited files may be compressed, so refusing to read all compressed files would
   undermine maintenance. But decode must cap encoded bytes, decoded bytes, compression ratio,
   and time before parsing, then save an uncompressed canonical source. Neither Base64 nor
   compression is validation.
4. **Documented — the core structural rules are stable enough to lint.** Official guidance
   requires the two structural cells, unique IDs, mutually exclusive vertex/edge roles,
   semicolon-delimited styles, escaped HTML, and relative coordinates for group children; it also
   tells AI not to emit XML comments
   ([official rules](https://www.drawio.com/docs/reference/diagram-generation/)).
5. **Verified — XSD is necessary but incomplete.** The inspected official XSD describes element
   and attribute shapes but has no `xs:key`, `xs:keyref`, or `xs:unique`; `style`, `source`,
   `target`, `parent`, and IDs are strings, and prose comments carry constraints such as vertex/
   edge exclusivity. It also models only uncompressed child XML even while documenting compressed
   text. Therefore XSD validation cannot prove unique IDs, valid edge/parent references,
   acyclic containment, valid styles/shapes, or visual correctness
   ([official XSD at inspected commit](https://github.com/jgraph/drawio-mcp/blob/14b318b19cc37b159f841227b9d11fbd18ce18ea/shared/mxfile.xsd)).
6. **Verified — style acceptance is intentionally permissive.** Official style documentation says
   unknown keys are silently ignored. A syntactically valid file can therefore contain misspelled
   properties and render differently from intent
   ([official style reference at inspected commit](https://github.com/jgraph/drawio-mcp/blob/14b318b19cc37b159f841227b9d11fbd18ce18ea/shared/style-reference.md)).
   Unknown styles need a warning or a library-version-aware registry; a clean parse is not enough.

### 3. Validation contract that is decision-sufficient

The evidence supports the following **inferred** validation stack. All stages are needed for a
repository claim of "validated":

1. **Admission:** regular non-symlink input, private/bounded read, UTF-8, explicit file/decompressed
   size, depth, element-count, attribute-length, and total-text limits.
2. **Safe parse:** an XML implementation that disables DTDs, external entities, entity expansion,
   and network/file resolution. The AWS validator demonstrates `defusedxml`, a 2 MiB file limit,
   depth 50, element count 50,000, and sanitized diagnostics, but those values are its policy, not
   universal draw.io limits
   ([AWS validator](https://github.com/awslabs/agent-plugins/blob/bab56a3b9991aa0c6857b05198a61ba14a60bce4/plugins/deploy-on-aws/scripts/lib/validate_drawio.py)).
3. **Schema:** validate the uncompressed full wrapper with the pinned official `mxfile.xsd`.
4. **Graph semantics:** enforce required structural cells per page; unique page/cell IDs; exactly
   one role per visible cell; parent/source/target references within the page; no containment
   cycles; required geometry; finite bounded numbers; and valid page/layer relationships.
5. **Style/library semantics:** split style strings deterministically; reject or warn on unknown
   keys and unavailable shape names relative to a pinned renderer/library catalog; check required
   perimeter/edge geometry conventions where applicable.
6. **Content policy:** by default reject comments, DTD/entity/CDATA, HTML labels, `javascript:` and
   other active links, non-fragment URIs, background/image/font URLs, remote/custom libraries,
   and oversized data URIs. Relax each class only through an explicit profile with matching render
   controls.
7. **Round-trip check:** load/export via the *pinned local* renderer only after the renderer is
   admitted; reparse the result, ensure the source graph is still present, and fail on unexpected
   semantic loss. This is not available before renderer certification.
8. **Visual check:** inspect a derived preview for clipped labels, overlap, edge ambiguity,
   unreadable contrast, incorrect notation, and missing icons. Visual acceptance remains advisory
   and cannot be replaced by XML/XSD success.

### 4. Diagram types, libraries, templates, icons, and licenses

1. **Documented — draw.io is one generic graph/canvas format across many notations.** Official
   examples span flowcharts, UML, ER, C4, BPMN, cloud/network/rack diagrams, threat models,
   wireframes, org charts, mind maps, Gantt/timelines, engineering diagrams, floorplans, and more;
   the native model remains shapes, edges, groups/layers/pages, styles, and geometry rather than a
   different file grammar per notation
   ([official diagram-type catalog](https://www.drawio.com/docs/diagram-types/)). This supports
   per-type authoring references and review rules, not per-type parser/export implementations.
2. **Documented — libraries and templates are separate dependency surfaces.** A custom library is
   XML containing an `<mxlibrary>` node whose text is a JSON array; entries carry width/height and
   either escaped/compressed graph XML or image data. A template index can name diagram and preview
   URLs plus built-in and custom libraries
   ([custom-library format](https://www.drawio.com/docs/reference/format-custom-shape-library/),
   [template-library format](https://www.drawio.com/docs/reference/format-template-library/)).
   **Inferred:** a reproducible agent workflow pins reviewed local copies and hashes; loading a
   mutable public URL is discovery/preview, not provenance.
3. **Verified — the official generic skill uses one umbrella.** At inspected commit `14b318b`,
   draw.io's own Codex skill selects Mermaid-to-native conversion for standard types and direct XML
   for precise geometry, custom styling, or domain libraries; it does not publish one skill per
   flowchart/UML/ER/sequence type
   ([official draw.io skill](https://github.com/jgraph/drawio-mcp/blob/14b318b19cc37b159f841227b9d11fbd18ce18ea/plugins/codex/drawio/skills/drawio/SKILL.md)).
   The AWS Labs skill is the counterexample that supports a specialized sibling only when the
   domain adds IaC discovery, an icon registry, layout/style doctrine, and semantic checks.
4. **Verified — software and visual assets do not share one blanket license.** The draw.io source
   is Apache-2.0, but its current README gives icon sets, stencil libraries, and templates separate
   terms, notes that some icons belong to third parties, exempts end-user diagram output from its
   Atlassian-asset restriction, and makes no copyright claim on user diagrams
   ([draw.io README at inspected commit](https://github.com/jgraph/drawio/blob/a1f615b7f5a5237da71de2ce2f057b5fa70b0aeb/README.md)).
   `drawio-mcp` and `awslabs/agent-plugins` are Apache-2.0, but that does not relicense branded AWS,
   Azure, Cisco, or other marks embedded or referenced by a diagram. **Inferred:** reference a
   renderer's built-in stencil ID where permitted; never vendor a library/template/icon corpus
   without an asset-by-asset source, license/trademark decision, hash, and repository NOTICE review.

### 5. Preview, export, embedded content, security, and runtime

1. **Verified — Desktop exposes a real conversion/export CLI.** Current source accepts `-x`,
   XML/PNG/JPEG/SVG/PDF/HTML formats, layout presets/JSON, Mermaid input, embedded diagram data for
   PNG/SVG/PDF, page/layer/size/theme/font options, and a no-overwrite check
   ([Desktop argument definitions at inspected commit](https://github.com/jgraph/drawio-desktop/blob/6937156737666a80196217478766d11f8c1a71c7/src/main/args.js)).
   Official releases cover Windows, macOS, and Linux; the official skill documents native paths and
   a WSL route through the Windows executable. Plain XML authoring and URL construction do not need
   Desktop; Mermaid conversion, layout, and local image/PDF export do. The inspected option set has
   an export mode but no distinct `--headless` contract; because the process is still Electron,
   describe this as non-interactive command-line export, not as a certified displayless/headless
   renderer, until the runtime experiment qualifies it.
2. **Documented — editable exports duplicate the source.** PNG stores XML in a compressed text
   chunk; SVG may contain diagram XML and hyperlinks; PNG/SVG/PDF can include the diagram for
   re-opening in draw.io
   ([embedded PNG](https://www.drawio.com/docs/manual/export/xml-in-png/),
   [export formats](https://www.drawio.com/docs/manual/export/export-diagram/)). Third-party tools
   may strip embedded SVG metadata or resample PNGs. **Inferred:** an editable export is a derived
   convenience, not a robust canonical source; publishing it may also publish hidden pages,
   metadata, links, and the full editable model.
3. **Verified — URL and hosted previews have different egress.** The official MCP project states
   that an editor URL carries XML in the browser `#fragment`, which the browser does not transmit
   to the server, while the hosted MCP App receives the diagram in the MCP request. The URL path
   still downloads app/viewer code and assets, and external image/font/library references can make
   further requests
   ([official draw.io MCP data-residency table](https://github.com/jgraph/drawio-mcp/blob/14b318b19cc37b159f841227b9d11fbd18ce18ea/README.md#data-residency--offline-use)).
   Therefore URL preview is opt-in browser/network activity; hosted preview is explicit data egress.
4. **Verified — well-formed XML is not safe content.** An official 2026 advisory reports that a
   crafted HTML cell label could execute script when selected in draw.io `<=29.7.11`; Desktop and
   self-hosted deployments without a strict CSP were affected, while production `app.diagrams.net`
   was protected by CSP. The fix shipped in `29.7.12`
   ([GHSA-fqhg-287p-c6vf](https://github.com/jgraph/drawio/security/advisories/GHSA-fqhg-287p-c6vf)).
   **Inferred:** treat every imported/generated diagram as untrusted active content, default to
   plain labels and no external URIs, and pin a patched renderer even after local validation.
5. **Verified — Desktop is not equivalent to this repo's sandboxed Mermaid boundary.** It is an
   Electron application; current source enables context isolation and web security, but its call to
   `app.enableSandbox()` remains commented out
   ([Desktop window setup](https://github.com/jgraph/drawio-desktop/blob/6937156737666a80196217478766d11f8c1a71c7/src/main/electron.js#L371-L409)).
   No repository-owned draw.io wrapper currently pins the executable/cache tree, unshares network,
   constrains its process tree, sanitizes derived SVG, or emits a receipt. A Desktop export command
   is therefore technically available but uncertified here.

### 6. Determinism and source/render provenance

1. **Verified — current CLI options expose no reproducible-build mode.** They do expose theme,
   size, page/layer, scale, layout, font/image embedding, and output-format choices, all of which can
   change output. SVG uses system fonts unless embedded; adaptive theme is another variable
   ([Desktop arguments](https://github.com/jgraph/drawio-desktop/blob/6937156737666a80196217478766d11f8c1a71c7/src/main/args.js),
   [editor configuration](https://www.drawio.com/docs/reference/configure-diagram-editor/)).
   No inspected first-party source promises byte-identical exports across runs or platforms.
2. **Inferred — deterministic source checks are feasible.** Keep agent-authored XML uncompressed;
   omit or normalize volatile `modified`, `agent`, `etag`, and producer-version metadata; use stable
   page/cell IDs and a deterministic serializer; hash both original admitted bytes and normalized
   semantic form; diff graph meaning separately from layout/style churn. Never recompress merely
   to compare sources.
3. **Inferred — every derived render needs a sidecar receipt.** At minimum record canonical source
   hash, normalized semantic hash, exact Desktop artifact/version/hash, platform/architecture,
   layout/export flags, page/layer selection, theme, font set, referenced library/icon hashes and
   licenses, output hash/size, sanitizer policy, and visual-review verdict. The `mxfile` producer
   attributes are useful hints but are not cryptographic provenance.
4. **Cheapest decisive experiment for the remaining renderer question.** On one supported host,
   pin a current patched Desktop artifact and fonts; block network; provide a fresh private profile;
   render a small corpus containing basic shapes, HTML/plain labels, pages/layers, AWS stencil IDs,
   embedded/local images, and adversarial URIs three times in separate processes; compare bytes and
   decoded pixels/structure; record peak RSS, processes, files, wall time, external-access attempts,
   and sanitizer compatibility. Repeat the exact receipt on a second OS only if cross-platform
   equivalence is a product requirement. Until then, deterministic rendering is undecided, not
   presumed.

## Rejected alternatives

1. **One top-level skill per generic diagram type.** Rejected: it duplicates the same file,
   validation, security, preview, export, and provenance contract while multiplying selection rows.
2. **Verbatim import of the official draw.io or AWS Labs skill.** Rejected: foreign bytes and
   changing raw-`main` references conflict with this repository's no-vendoring/adaptation/NOTICE
   rules; the official skills also delete intermediate canonical sources after some exports and do
   not provide this repository's renderer boundary.
3. **Make draw.io Desktop a gate or bootstrap prerequisite.** Rejected: platform/runtime cost and
   security/provenance are not yet certified, and the existing Mermaid precedent keeps explicit
   renderer provisioning advisory.
4. **Call XSD success, hook feedback, or a successful open "validated."** Rejected: the XSD omits
   graph-reference/style/security semantics, the AWS hook is fail-open, and recent valid XML could
   exploit a renderer.
5. **Delete `.drawio` after producing an editable PNG/SVG/PDF.** Rejected: embedded source can be
   stripped or resampled, makes review/diff harder, and can silently diverge from a derived render.
6. **Default to hosted MCP or browser preview.** Rejected: it adds data-egress or network/runtime
   behavior to a capability that can safely stop after authoring and local validation.

## Limitations and adversarial failure modes

- No Desktop render/export was executed in this research; runtime, resource ceilings, output
  determinism, and sanitizer compatibility remain unverified experiments.
- The official XSD and style catalog are young, permissive AI aids rather than a complete formal
  specification. Renderer acceptance can be wider than the schema, and upstream shape/style IDs
  can drift.
- Safe XML plus a clean render still cannot prove the diagram is factually correct, uses the right
  notation, preserves user intent, or is visually legible. Human/vision review remains load-bearing.
- Updating a human-authored file is riskier than generating a new one: unknown elements, metadata,
  pages/layers, custom libraries, and intentional coordinates must be preserved without a lossy
  reserialization.
- HTML labels, hyperlinks, embedded source, data URIs, remote images/fonts/libraries, PDF/SVG
  interactivity, and hidden layers enlarge both the security and accidental-disclosure surface.
- Branded libraries carry copyright/trademark terms distinct from draw.io's Apache-2.0 code; an
  icon that renders is not thereby cleared for redistribution or incorporation into a skill.

## Open risks

1. Whether this bundle has a live recurring editable-draw.io trigger sufficient for a top-level
   skill was not established; without it, the evidence supports a focused reference and promotion
   trigger rather than immediate admission.
2. An installed official `drawio` plugin or host-provided diagram skill could collide with a
   repository-owned umbrella; effective inventories and description-byte overlap need a live audit
   at implementation time.
3. The exact allowlist for safe HTML, link schemes, custom metadata, data images, and stencil IDs
   must be decided against a pinned renderer and threat model; this report deliberately does not
   guess it.
4. Cross-platform Desktop behavior, especially Linux display/session requirements and WSL path/
   profile isolation, remains unqualified until the decisive experiment runs.

## Out-of-scope discoveries (Seed proposals only)

- **SeedProposal — certify a draw.io Desktop renderer boundary.** Owner: renderer/security
  workstream. Acceptance: cheapest decisive experiment above, explicit provisioning, exact artifact
  and font/library pins, sandbox/network/resource policy, sanitizer, receipts, and platform claim.
- **SeedProposal — build a generic draw.io XML validator/canonicalizer.** Owner: diagram tooling.
  Acceptance: hardened parser, bounded decompression, pinned XSD, semantic graph/style/URI checks,
  sanitized diagnostics, fixtures, and stable semantic hashing; no renderer dependency.
- **SeedProposal — audit host/plugin collision before exposing an umbrella.** Owner: skill
  admission. Acceptance: effective installed skill inventory, nearest-neighbor descriptions,
  measured trigger recurrence, and an explicit four-gate/at-least-two-of-five result.
- **SeedProposal — evaluate a domain sibling only from observed failures.** Owner: future domain
  requester. Acceptance: recurring requests plus domain discovery, maintained icon/notation corpus,
  semantic validator, licensing/provenance owner, and a distinct selector; AWS is evidence of the
  pattern, not a pre-approved sibling.
