# Claude Code version and platform support evidence

**Research date:** 2026-08-15

**Scope:** Current first-party Anthropic documentation, Anthropic's public release
endpoints, the official npm registry record, and the official
`anthropics/claude-code` release repository. This report records vendor support
and release facts. It does not certify any Agentic SDLC tuple.

## BLUF

Use **Claude Code 2.1.224** as the current `stable`-channel nomination and
**2.1.233** as the current `latest`-channel nomination. The Anthropic channel
endpoints and npm distribution tags agreed on those exact values on the
research date.[2][3][9] GitHub identifies 2.1.233 as the latest non-prerelease
release, published on 2026-08-14.[4]

Do not publish either nomination as an Agentic SDLC compatibility claim until
the exact host, OS/runtime, architecture, installation plane, authentication or
provider mode, and selected Agentic SDLC profile pass their required tests and
live canaries. Anthropic's platform support makes a tuple eligible for testing;
it does not prove this repository has tested it.

Dynamic Workflows have a documented minimum of **2.1.154**.[5] That floor is
not a sufficient compatibility range. The current guide records later
behavior-specific boundaries, including Ultracode at 2.1.203+, human-origin
keyword restrictions changing at 2.1.210, and workflow-save symlink behavior
changing at 2.1.216.[5] Agentic SDLC should therefore certify exact versions,
not claim `>=2.1.154` compatibility.

## Current version snapshot

| Release surface | Observed exact value | Meaning |
| --- | --- | --- |
| Anthropic `stable` channel | `2.1.224` | Delayed channel nomination; the endpoint returned this exact value on the research date, and an official release exists for it.[2][10] |
| npm `stable` distribution tag | `2.1.224` | Independent official registry confirmation of the stable-channel value.[9] |
| Anthropic `latest` channel | `2.1.233` | Immediate channel nomination; the endpoint returned this exact value on the research date.[3] |
| npm `latest` and `next` tags | `2.1.233` | Official registry metadata; not evidence that the release is safe for this harness.[9] |
| Latest GitHub release | `v2.1.233` | Marked latest, not draft or prerelease, and published 2026-08-14.[4] |

`stable` is a moving release channel, not a semantic stability guarantee or a
version range. Anthropic says it is normally about one week behind `latest` and
skips releases with major regressions.[1] A release record should capture the
resolved exact version and verification date, not only the channel name.

## Official platform and installation support

Anthropic's current minimum system requirements are macOS 13.0+, Windows 10
1809+ or Windows Server 2019+, Ubuntu 20.04+, Debian 10+, or Alpine Linux 3.19+;
4 GB RAM; an x64 or ARM64 processor; internet access; and Bash, Zsh, PowerShell,
or CMD.[1]

| Runtime boundary | Official fact | Matrix consequence |
| --- | --- | --- |
| macOS | macOS 13.0+ on x64 or ARM64 is supported.[1] | Test each architecture and acquisition plane separately. Vendor support is not an Agentic SDLC certified row. |
| Linux | Ubuntu 20.04+, Debian 10+, and Alpine 3.19+ are named minimums. Anthropic also publishes signed apt, dnf, and apk repositories; Alpine and other musl systems need extra runtime packages.[1] | Do not collapse glibc and musl or different distribution families into one row. The docs give no Fedora/RHEL minimum version even though they provide dnf instructions. |
| WSL 2 | Claude Code installs and runs inside WSL with the Linux installer; sandboxing is supported.[1] | Treat WSL2 as its own Linux-runtime tuple with Windows-interoperability exclusions. It is not native-Windows evidence. |
| WSL 1 | WSL1 is supported for Claude Code, but sandboxing is not.[1] | A profile that requires sandboxing cannot inherit WSL2 support. |
| Native Windows | Windows 10 1809+ and Server 2019+ are supported. Git for Windows is optional: it supplies Bash; without it Claude Code uses PowerShell. Claude Code sandboxing is not supported on native Windows.[1] | Certify PowerShell and Git-Bash modes independently when their behavior matters. Any safety contract that depends on the Claude sandbox must fail closed or remain uncertified. |

The recommended native installers cover macOS, Linux, WSL, and native Windows.[1]
Homebrew and WinGet are also documented, as are signed apt, dnf, and apk
repositories.[1] npm installation is still available, but Anthropic's official
repository labels it deprecated.[1][11] Since
Claude Code 2.1.198, the npm package declares Node.js 22+ and installs the same
native binary for eight documented OS/architecture combinations.[1]

Installation method is load-bearing compatibility data:

- Native installs update in the background. `latest` is the default channel;
  `stable` is selectable.[1]
- Homebrew, WinGet, apt, dnf, and apk do not auto-update through Claude Code by
  default. Homebrew exposes separate stable and latest casks.[1]
- The native installer accepts an exact version. `minimumVersion` is only an
  update floor; managed `requiredMinimumVersion` and `requiredMaximumVersion`
  can enforce a launch range.[1]
- Signed manifests cover releases from 2.1.89 onward. macOS and Windows
  binaries also carry platform-native signatures; Linux integrity relies on
  the signed manifest or signed package repository.[1]

Agentic SDLC should record the executed `claude --version` and installation
plane after acquisition. A channel name, package-manager selection, or update
notification is not exact runtime-version evidence.

## Dynamic Workflows boundary

Anthropic documents Dynamic Workflows as requiring Claude Code 2.1.154 or later.[5]
They are available on all paid Claude plans, with Anthropic API access, and on
Amazon Bedrock, Google Cloud's Agent Platform, and Microsoft Foundry.[5] Pro users
must enable the feature in `/config`.[5] The first-party v2.1.154 release note
is the matching introduction point.[6]

Current official availability guidance lists Workflows among the local features
available on every documented provider.[7] It also says that gateway feature
availability follows the underlying provider.[7] This does not establish
support for arbitrary non-Claude models. Anthropic's gateway guide requires a
supported Anthropic, Bedrock, or Vertex API shape, requires preservation of
Anthropic beta/version fields, and uses access to Claude models in its documented
gateway prerequisites.[8]

An exact Dynamic Workflow support tuple must therefore include at least:

- exact Claude Code version and release channel at verification time;
- OS, architecture, native/WSL boundary, and installation method;
- account or provider mode and the feature's effective enablement state;
- the exact Agentic SDLC core/profile and manifest digest;
- observed workflow creation, approval, agent execution, pause/resume, stop,
  result, and required tool/permission behavior; and
- any provider or gateway route as a separate qualified dimension.

## Evidence gaps and unknowns

- Anthropic publishes current moving channel values, but no promise that a
  particular `stable` version will remain selected for a fixed time. Re-read the
  live endpoint during each Agentic SDLC release.
- The documentation names Fedora and RHEL package instructions but does not state
  their minimum supported versions.[1]
- The documentation does not turn general OS support into feature parity. It
  explicitly distinguishes sandboxing on native Windows, WSL1, and WSL2, and
  some other features have separate OS/version constraints.[1][7]
- The Dynamic Workflow minimum is documented, but later point releases changed
  permissions, triggers, saving, monitoring, and related orchestration behavior.
  A minimum-version check cannot replace a release canary.[5]
- No first-party source reviewed certifies OCX or a non-Claude model as a
  supported Claude Code transport. Such a route must remain an Agentic SDLC
  experimental or independently qualified claim, not an Anthropic support
  claim.[8]

## Decision-ready recommendation

For the next Agentic SDLC release, nominate two independent Claude Code rows:

1. `2.1.224` from the `stable` channel as the primary release-candidate row.
2. `2.1.233` from the `latest` channel as the newer compatibility-candidate row.

Start full certification on Linux x64 and WSL2 Linux x64 as already planned,
but publish a row only after the repository's own complete journey and live
Dynamic Workflow canaries pass. Keep macOS, native Windows, WSL1, ARM64, musl,
and each alternative installation plane as separate unverified candidates until
their own evidence exists. Re-resolve both channel values immediately before
release; if either moves, the new value is a new candidate, not an automatic
substitute for the tested binary.

## Sources

[1] https://code.claude.com/docs/en/setup
[2] https://downloads.claude.ai/claude-code-releases/stable
[3] https://downloads.claude.ai/claude-code-releases/latest
[4] https://github.com/anthropics/claude-code/releases/tag/v2.1.233
[5] https://code.claude.com/docs/en/workflows
[6] https://github.com/anthropics/claude-code/releases/tag/v2.1.154
[7] https://code.claude.com/docs/en/feature-availability
[8] https://code.claude.com/docs/en/llm-gateway
[9] https://registry.npmjs.org/@anthropic-ai%2Fclaude-code
[10] https://github.com/anthropics/claude-code/releases/tag/v2.1.224
[11] https://github.com/anthropics/claude-code
