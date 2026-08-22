# ADR-0016 — Make yolo an explicit permission profile on both ccodex launch forms

- **Status:** accepted
- **Date:** 2026-08-12
- **Deciders:** operator (decision and review); agent drafted the record and implementation
- **Relates to:** `docs/adr/0014-gateway-launch-preserves-the-operators-own-claude-login.md`

## Context

The operator reported an existing `ccode-ultracode` workflow. A read-only local shell inspection
(`bash -lic 'type -a ccode-ultracode'`) observed that alias combining session Ultracode with Claude
Code's explicit `--dangerously-skip-permissions` flag. `ccodex` exposes the same gateway
session and an Ultracode convenience route, but the latter deliberately rejected every bypass
flag. Reproducing the established workflow therefore required dropping to an external alias or
manually combining ordinary `ccodex launch` arguments, while the installed dispatcher presented
no single, conspicuous spelling for the risk choice.

The permission choice and the Ultracode choice are independent. Making one imply the other would
give `launch --yolo` an unrelated behavioral side effect, while allowing raw bypass flags only on
one route would preserve an arbitrary difference between the two launch forms.

The decisive driver is legibility at the risk boundary. The existing host-level bypass workflow
already exists through a user alias and through raw arguments on ordinary launch; leaving it
outside ccodex does not remove the risk, it removes ccodex's ability to give the workflow one
stable spelling, reject conflicting controls, and display the bypass state. That benefit outweighs
adding an owned convenience only because the flag is explicit, first-position, and leaves every
gateway and billing refusal in force.

## Considered options

- **Keep bypass outside ccodex.** Rejected because it leaves a daily workflow in an unowned shell
  alias and prevents the dispatcher from validating conflicts or displaying the active risk.
- **Make `launch --yolo` imply Ultracode.** Rejected because a permission profile should not
  silently select a reasoning/session profile.
- **Remove raw Claude permission arguments and make yolo the exclusive bypass path.** Rejected
  because ordinary `ccodex launch` preserves accepted Claude argument bytes and boundaries;
  removing that compatibility is not necessary to add an owned convenience profile. The launcher
  may still validate a trust-boundary argument before forwarding it—for example, explicit
  `--settings` values are checked for route bypass after this ADR's 2026-08-13 amendment. When yolo
  is selected, competing permission controls are still refused.
- **Make first-position `--yolo` orthogonal on both launch forms.** Selected because the command
  continues to choose Ultracode while the flag alone chooses the permission profile.

## Decision

1. `ccodex launch` and `ccodex ultracode` select no bypass profile by default; absent a raw
   caller-supplied Claude permission override, ordinary Claude Code permissions apply.
2. A first argument of `--yolo` on either form is consumed by ccodex and translated to Claude
   Code's explicit permission-bypass flag. It is never forwarded as `--yolo`.
3. `--yolo` refuses competing permission-mode controls. Ultracode continues to own its session
   settings value and refuses a competing settings document.
4. A leading forwarding separator disables wrapper interpretation, so `-- --yolo` remains a
   literal pass-through escape.
5. Every yolo launch prints that permissions are bypassed. Gateway-health, route-effectiveness,
   and billing-honesty checks remain unchanged.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Refines | ADR-0005 | Overrides only Decision item 2's rule that `launch-ultracode` cannot bypass permissions; ordinary permissions remain the default and every gateway boundary otherwise stands. |
| Relates-To | ADR-0014 | Both launch profiles continue using the operator's own Claude login and the same gateway billing-honesty checks. |

## Compliance

- With neither a raw Claude permission override nor a first-position `--yolo`, neither launch
  profile injects a bypass flag.
- A first-position `--yolo` on either launch profile produces exactly one injected
  `--dangerously-skip-permissions` argument and is not forwarded literally.
- A YOLO launch carrying any competing permission control refuses before gateway contact.
- `-- --yolo` forwards the spelling literally and does not select the YOLO profile.
- Route-effectiveness and billing-honesty failures refuse before the bypass banner or launch on
  both YOLO profiles.

## Consequences

- Positive: the four combinations of ordinary/yolo and plain/Ultracode are explicit and
  predictable, and `ccodex ultracode --yolo` replaces the historical external alias.
- Negative: ccodex now offers a host-level path that disables ordinary permission checks and
  Auto's classifier. A typo-free explicit spelling and a warning cannot make that safe outside an
  isolated, disposable environment.
- **Confirmation:** `python3 -m unittest tests.test_opencodex_claude tests.test_operator_tools`,
  `bash -n scripts/opencodex-claude.sh assets/launchers/ccodex.in`, and `mise run check` verify the
  contract. A passing result is evidence only and authorizes no installation or outward effect.

## Reversal condition

If Claude Code removes or changes the semantics of `--dangerously-skip-permissions`, or a focused
test shows that either default launch profile enters bypass without a caller-supplied raw Claude
permission control or a first-position `--yolo`, the operator-tools maintainer re-examines this
decision.
