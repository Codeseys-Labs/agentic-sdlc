#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Seal and validate the `distribution-activation@2` receipt body: the family's first payload.

TWO GENERATIONS, ONE WRITABLE. `validate` admits both `distribution-activation-body@1` and `@2`;
`seal` writes `@2` only. That asymmetry is the whole shape of this module's history handling, and it
inverts the ownership ledger's one-schema-no-migration doctrine ON PURPOSE: the installer refuses a
foreign ownership document because its physical witnesses no longer exist and nothing could faithfully
convert it, while a SEALED RECEIPT is immutable evidence whose bytes prove what one run observed.
Rewriting one to @2 would destroy exactly that, and filling @2's new fields (`scope`, per-row `mode`)
would make this module the author of facts no run ever saw. So v1 documents stay readable forever and
are never re-sealed, and the named cost is that every rule added here must be reasoned about twice.
`Generation` holds the per-generation shapes as DATA rather than as branches, so a check reads one key
set instead of asking which generation it is in three places and disagreeing with itself in a fourth.

WHAT @2 CHANGED, AND WHY EACH CHANGE IS A SHAPE RATHER THAN A GUARD. The discipline throughout is one
fact, one spelling, closed key sets per variant: a cross-field prose guard is replaced by a shape that
cannot express the disagreement.

  scope              REPLACES `activation_scope`, as a closed discriminated union whose key set is
                     EXACT per kind: `{kind: user, agent}` or `{kind: project, agent, root}`. A user
                     scope carrying a root and a project scope missing one are both refused by
                     comparison. Keeping v1's display token beside a project spelling would have been
                     two spellings of one fact, and a receipt whose two spellings disagree is a
                     representable illegal state guarded only by a validator clause.
  NO root_key        anywhere in the body. The pointer FILENAME derives `sha256(scope.root)`
                     truncated, and `pointer_disagreements` compares the two at admission. A stored
                     field whose only function is to be checked against a derivation of a sibling
                     field is the same defect `activation_scope` was deleted for.
  NO mode_policy     anywhere in the body. Mode is enforced where it is real -- per inventory row,
                     against bytes -- so `entries[].mode` carries it and project scope refuses any
                     published row that is not a copy. A body-level policy field would be
                     single-valued on the one variant that has a policy, and `scope.kind` already
                     identifies it.
  checkout           the ONE optional object, and the one place this generation ADDS vocabulary:
                     `{commit: <40hex>|"unknown", dirty: bool}`. Present means the payload was a tree
                     rather than an archive, and that single statement fixes two others in both
                     directions: `version_source` is `checkout-tree`, and `archive_sha256` is null --
                     NOT-SUPPLIED, because no archive exists, so no unknown is named for it and a
                     clean checkout activation can still be `complete`. The paired ancestor rule is
                     that the `derived-from` ancestor is FORBIDDEN exactly where `checkout` is
                     present, and required exactly where an archive digest is.
  version_source     gains `checkout-tree`: the version read from exactly ONE authoritative file,
                     `.version-bump.json`'s own `current` field. A mid-bump tree with drifted sibling
                     manifests is a legitimate checkout-install state; that drift is the repository
                     gate's business, and this receipt records the driver value alone.
  prestate_evidence  an UNINSTALL-only closed discriminator: `activation-receipt` (one `derived-from`,
                     naming the receipt retired) or `ledger` (ZERO ancestors, inventory drawn from the
                     ownership rows the run retired). Without the variant the legacy-unreceipted
                     retirement is unrepresentable, because the family requires exactly one ancestor;
                     and deleting that removal path instead would force an INSTALL before a removal on
                     exactly the hosts whose rows no verb would otherwise select.
  candidate_id       stays exact and non-null on every path. A checkout has no manifest to read an
                     identity from, so its producer derives one over the inventory rows and their
                     content digests (`checkout_candidate_id`, exported so there is one definition).
                     This module does NOT re-derive it while validating: a retirement legitimately
                     carries the candidate_id of the payload it retired, whose inventory is not the
                     retirement's own.

Everything else -- `operation`, `host`, the inventory's prestate/disposition matrices, `effect_state`
and `terminal_phase`, `supersedes` for update, the two seals, the unknown-consistency rules -- carries
over unchanged.

`skills/agentic-sdlc/tools/receipt-envelope.py` owns the common envelope and states, in its
"WHAT THIS ENVELOPE DOES NOT OWN YET" paragraph, that producer and schema versions, physical subject
and scope, plan and approval digests, terminal status, effect state, and artifact references "arrive
with the first family that has them". `distribution-activation` is that first family, so those fields
land HERE, inside the closed body the envelope treats as opaque, and not as loose optional keys in the
envelope.

TWO SEALS, DELIBERATELY NESTED, EACH WITH ITS OWN JOB.

    record_sha256  = sha256( canonical( body MINUS record_sha256 ) )
    content_digest = sha256( canonical( body INCLUDING record_sha256 ) )

`record_sha256` is the acquisition receipt's own pattern (`scripts/write_acquisition_receipt.py`
pops the key, seals, then writes the digest back), and it exists because the body travels as a record
in its own right: a consumer holding only the body can still detect a hand-edit. `content_digest` is
the envelope's, unchanged, and it therefore seals the body's seal. `canonical` is one form in both
places -- `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`, `allow_nan=False`, exactly
one trailing newline -- because a second spelling of "canonical" would make the envelope's digest
stop re-deriving over a body this module wrote.

NO CROSS-PLANE IMPORT. The envelope's schema string, its receipt kinds, and its relation vocabulary
are RE-EXPRESSED as constants below rather than imported from `skills/`: the skill tree is a
distributable bundle, not a library this repository's scripts link against, and an import would make
a `scripts/` gate leaf fail when the bundle is absent. Re-expression buys a drift risk instead, so it
is paid for in the test module, which parses the skills-plane source with `ast` -- still not an
import -- and asserts the three vocabularies are identical, then runs the skills-plane checker over
this producer's output as an INDEPENDENT verifier. This module never claims a receipt is envelope-
valid on the strength of its own re-expression alone.

THE BODY, FIELD BY FIELD, EACH WITH THE REASON IT EXISTS.

  schema_version      `agentic-sdlc/distribution-activation-body@2`, or `@1` on a historical
                      document this module reads and never re-seals. The family payload versions
                      itself, which is the whole reason the envelope's `schema` is not asked to.
  operation           `install`, `update`, or `uninstall`, closed. The receipt KIND names the
                      lifecycle FAMILY, not one step of it, so acquisition and activation and
                      retirement are all `distribution-activation` documents and the operation is
                      what distinguishes them. A kind per verb would have made an update's
                      `supersedes` reference kind-incompatible with the receipt it replaces.
  host                `claude`, closed, with NO wildcard. A wildcard host is a receipt that binds
                      nothing: `all` would read as evidence about a plane this operation never
                      touched. `codex` is not admitted here because no activation of it has been
                      observed by this producer; it arrives when its first receipt does.
  scope               which part of the host plane this activation touched, as the closed union above:
                      `host` says which plane, `scope` says which part of it, and `scope.agent` must
                      agree with `host` because they name the same plane. (v1 spelled this as the
                      single lowercase token `activation_scope`, which @2 deletes rather than extends;
                      a v1 document keeps that field and is read with v1's rules.)
  requested_version   the version the CALLER asked for, or `null` for "no version was requested".
                      Null and absent are different facts and are refused differently: an absent key
                      is a body that never spoke about the request, a null is a body that says there
                      was none, and an empty string is a request supplied and lost.
  resolved_version    the EXACT version that was actually resolved. Required, never null, never
                      derived from `requested_version` (Seed agentic-sdlc-0faa: a requested identity
                      never becomes a readback).
  version_source      `adapter-readback`, `archive-manifest`, or `checkout-tree` -- where the resolved
                      version was READ. `request` is a member of the closed vocabulary and is REFUSED, because
                      the honest failure it names ("we only ever had the request") must be
                      expressible in order to be rejected by name rather than silently spelled as a
                      readback.
  candidate_id        sha256 of the candidate this activation drew from: payload identity, not a
                      version label, because two builds of one version are two payloads.
  archive_sha256      sha256 of the archive itself, or null WITH a named unknown.
  entries             the inventory: one record per managed entry, each with its own content digest,
                      its `prestate` from the closed set `absent`/`owned`/`foreign`/`modified`, and
                      its `disposition`. A `foreign` prestate may only be `preserved`, and it is
                      NAMED in the inventory rather than dropped from it, because the installer's
                      ownership model keeps a foreign entry rather than adopting or replacing it, and
                      a receipt that omitted it would read as a clean install of a collided plane.
  effect_state        `none`, `partial`, `complete`, or `unknown`.
  terminal_phase      `not-activated`, `activated`, `activated-partial`, `retired`, or `unknown`.
                      Effect state and terminal phase are cross-checked against each other and
                      against the operation, so "complete" cannot coexist with "unknown" and an
                      uninstall cannot terminate `activated`.
  journal_sha256      the effect journal this receipt binds, or null WITH a named unknown. Any
                      admitted effect requires the binding: the acquisition receipt's precedent.
  plan_sha256         the plan digest, same nullability rule. It binds what was intended to what
                      happened, and it is EVIDENCE of neither review nor approval.
  public_channel      always `null`, and `release_claim` always `none`. ADR-0021's evidence
                      condition has not fired, so no output of this producer may say a published
                      release exists. These are fields rather than omissions precisely so a
                      consumer reads the honest negative instead of inferring from silence.
  unknowns            the closed list of observations that could NOT be made, each naming its
                      `observation`, its `subject`, and a free-text `detail`. This is the field the
                      admission checks read. A check that consulted only recorded FACTS would admit
                      "effect complete" beside a digest nobody could compute, because the absent
                      digest is not a fact and so appears nowhere in a fact-only walk.
  record_sha256       the body's own seal, as above.

SUPPLIED-BUT-MISSING IS NOT NOT-SUPPLIED, and the difference is a different named reason everywhere.
A body with no `archive_sha256` key never spoke about the archive; a body with `archive_sha256: null`
says the archive digest is unknown and must name the unknown; a body with `archive_sha256: ""` supplied
the field and lost the value. The same trichotomy governs an entry's `content_sha256`, where it is
load-bearing rather than pedantic: a `removed` entry has no content LEFT to digest and a null there is
not-supplied, while an `owned` entry that survived has content that must digest, so a null there is
supplied-but-missing and the producer names the unknown instead of writing a hole.

THE PRODUCER HOISTS EVERY OBSERVATION ABOVE THE BODY LITERAL. `build_body` normalises entries and
collects unknowns into locals FIRST, then writes the literal from those locals. Written the other way
-- `{"unknowns": unknowns, "entries": [normalise(e) for e in supplied]}` -- Python evaluates
`unknowns` before the comprehension that appends to it, and every unknown discovered while
normalising an entry is silently dropped from the document that was supposed to report it. That is a
real defect with a real cost: the body would then pass its own unknown-consistency check, because the
check reads the list that lost the record.

CONTROL CHARACTERS ARE ESCAPED IN EVERY RENDERED LINE. `detail` is free text from an artifact, so it
can carry `\\r`, `\\x1b[2J`, or a bare newline. Those bytes rewrite a terminal, truncate a log line, or
forge a second line of output that looks like the tool's own. Rendering escapes them; the stored value
is never mutated, because the receipt records what was observed.

FAIL CLOSED, NAME THE FIELD. Every check accumulates named reasons into its own group, then ONE
selection over ONE partition derives the verdict, so no input yields two verdicts or none. A refused
`seal` emits NO receipt: sealing an inadmissible body would mint exactly the artifact the checks
exist to prevent. Refusing is this module SUCCEEDING, so it exits 0.

EXITS. 0 a result was derived, a named refusal included; 2 the supplied input cannot be read as a
receipt document, or the arguments are unusable; 1 an unexpected internal failure, including a stdout
that cannot receive the one result document, because a receipt derived and not delivered is not a
success. Implementation Decision 9's 3 and 4 are absent for the reason the envelope module states:
this tool opens no output file, spawns no process, touches no network, and mutates no state, and a
command that can cause no effect can neither refuse before one nor admit one.

RESIDUALS, STATED EXACTLY.

  * Both seals are RE-DERIVATION, not a boundary against a same-OS-user forger. What they catch is
    drift, a hand-edit, and a mismatched pair.
  * This module reads the SUPPLIED observation. It never lists a plane, stats an entry, digests an
    archive, or resolves a version, so every fact here is the caller's to have observed honestly and
    every unknown is the caller's to have named.
  * A sealed body is a well-formed payload, not a true one. `prestate: owned` is admitted from a
    caller who never looked.
  * The envelope's own field set is checked here only as far as this kind needs; the skills-plane
    checker remains the authority on the envelope and on the correlation graph.
  * THE BODY CARRIES NO REPOSITORY-HEAD ANCHOR (agentic-sdlc-5ee7, agentic-sdlc-41b5). `candidate_id`
    names the payload this activation drew from and `plan_sha256` names the intent, but neither is a
    point in the repository's own history, so nothing in this body says which commit the activation
    was observed against. `scripts/gate_receipt.py` stamps `{commit, tree}` because it observes a
    gate running in a worktree; this producer observes nothing — it seals what the caller supplies —
    so an anchor here would be a caller-asserted field, not a reading, and one this module could not
    check. The consequence to know is that this receipt beside another artifact does not establish
    that the two describe one tree; a consumer needing that pairs the receipt with a producer that
    really did read a head and refuses the pair whose anchors disagree.
  * A sealed or validated receipt is EVIDENCE. It grants no approval, admission, completion, or
    outward authority, and it authorizes no push, publication, merge, or deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: This family's payload version. The envelope's `schema` versions the envelope, never the payload.
BODY_SCHEMA = "agentic-sdlc/distribution-activation-body@2"
#: The FIRST generation, admitted read-only forever as history. See the docstring's DUAL GENERATION
#: paragraph for the cost this carries and why it is paid rather than migrated away.
BODY_SCHEMA_V1 = "agentic-sdlc/distribution-activation-body@1"
#: Re-expressed from the skills plane, never imported; the test module proves the two agree.
ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/distribution-activation-result@1"

#: The one kind this producer writes. The kind names the lifecycle FAMILY, so all three operations
#: below are documents of this kind and `operation` is what separates them.
RECEIPT_KIND = "distribution-activation"

#: Re-expressed: the envelope's six closed kinds, needed because an ancestor reference states one.
RECEIPT_KINDS = (
    "distribution-activation",
    "incident-recovery",
    "integration-completion",
    "probe-qualification",
    "route-credential-lifecycle",
    "workflow-wave-node-attempt",
)

#: Re-expressed: the envelope's six closed relations.
RELATIONS = (
    "contained-by",
    "derived-from",
    "references-evidence",
    "remediates",
    "retries",
    "supersedes",
)

#: The three of the six this family uses. `contained-by`, `retries`, and `remediates` describe a wave
#: node or an incident, and a distribution activation is neither, so they are refused here rather
#: than admitted meaninglessly.
FAMILY_RELATIONS = ("derived-from", "references-evidence", "supersedes")

VERDICT_SEALED = "sealed"
VERDICT_VALIDATED = "validated"
VERDICT_REFUSED = "refused"

CONSEQUENCE = {
    VERDICT_SEALED: (
        "the supplied observation was admitted as a distribution-activation@2 body, its record seal "
        "and the envelope's content digest were derived over the canonical bytes, and the complete "
        "receipt is reported; a receipt is evidence and grants no approval, admission, completion, "
        "or outward authority"
    ),
    VERDICT_VALIDATED: (
        "the supplied receipt carries a closed distribution-activation body of an admitted generation, every closed "
        "vocabulary and cross-field rule holds, every recorded unknown is consistent with the "
        "recorded facts, and both the record seal and the envelope content digest re-derive; a "
        "validated receipt is evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "no body was admitted, nothing was sealed, and no receipt is reported; the reasons name each "
        "field and what was wrong with it, and a refused seal deliberately emits no document because "
        "sealing an inadmissible body would mint the artifact these checks exist to prevent"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The closed v2 body key set: every key here is REQUIRED of every operation, so an absence is
#: always a named refusal and an unrecognised key is refused rather than ignored. `scope` replaces
#: v1's `activation_scope` AND v1's `host`; none of the three coexist, because two spellings of one
#: fact are exactly the representable illegal state this generation exists to delete. `scope.agent`
#: is the ONE statement of which plane this activation touched, and a reader derives every display
#: string -- including a host-application spelling like `claude-code` -- from it.
BODY_KEYS = (
    "archive_sha256",
    "candidate_id",
    "effect_state",
    "entries",
    "journal_sha256",
    "operation",
    "plan_sha256",
    "public_channel",
    "record_sha256",
    "release_claim",
    "requested_version",
    "resolved_version",
    "schema_version",
    "scope",
    "terminal_phase",
    "unknowns",
    "version_source",
)

#: The v1 body key set, frozen. A v1 document is history: its bytes are never rewritten, so this
#: tuple is never edited again either.
BODY_KEYS_V1 = (
    "activation_scope",
    "archive_sha256",
    "candidate_id",
    "effect_state",
    "entries",
    "host",
    "journal_sha256",
    "operation",
    "plan_sha256",
    "public_channel",
    "record_sha256",
    "release_claim",
    "requested_version",
    "resolved_version",
    "schema_version",
    "terminal_phase",
    "unknowns",
    "version_source",
)

#: The one key an UNINSTALL body carries and no other operation may: which prestate evidence the
#: retirement drew its inventory from. Required there, refused everywhere else, by exact key set --
#: so the ancestor count each evidence kind admits is a shape rather than a prose rule.
BODY_KEYS_UNINSTALL = ("prestate_evidence",)

#: The one OPTIONAL key of this generation, and the only vocabulary v2 adds rather than deletes.
#: Present means "this activation drew from a checkout, not from an archive"; absent means the
#: opposite. There is no `payload_source` spelling beside it, and no body-level `mode_policy`
#: anywhere: mode binds bytes per inventory row, and `scope.kind` already identifies the policy.
BODY_KEYS_OPTIONAL = ("checkout",)

#: The closed envelope key set, re-expressed.
ENVELOPE_KEYS = (
    "ancestors",
    "body",
    "content_digest",
    "emitting_plane",
    "receipt_id",
    "receipt_kind",
    "schema",
    "stated_at",
)

REFERENCE_KEYS = ("expected_kind", "receipt_id", "relation")
#: The v2 entry record. `mode` is the addition: the publication mode is enforced where it is real --
#: per row, against the bytes -- and never as a body-level policy field.
ENTRY_KEYS = ("content_sha256", "disposition", "entry_name", "mode", "prestate")
#: The v1 entry record, frozen with its generation.
ENTRY_KEYS_V1 = ("content_sha256", "disposition", "entry_name", "prestate")
UNKNOWN_KEYS = ("detail", "observation", "subject")

OPERATIONS = ("install", "uninstall", "update")

#: The closed scope union, keyed by `kind`, with EXACT key sets per kind. A user scope carrying a
#: `root` and a project scope missing one are both refused by comparison rather than by a prose
#: guard, and neither kind carries a `root_key`: the pointer FILENAME derives that key, and a stored
#: copy of a derivation of a sibling field is the same two-spellings defect as v1's `activation_scope`
#: beside a project spelling.
SCOPE_KINDS = ("project", "user")
SCOPE_KEYS = {
    "user": ("agent", "kind"),
    "project": ("agent", "kind", "root"),
}
#: One statement of which part of the host this activation touched, so `scope.kind` is the whole
#: policy identifier and no second field restates it.
SCOPE_USER = "user"
SCOPE_PROJECT = "project"

#: The optional checkout object: exactly two fields, and `commit` is either a 40-character git object
#: name or the explicit `unknown`. `dirty` is a real boolean, because `0`/`1`/`"false"` would each
#: read as a state this receipt cannot honestly claim to have observed.
CHECKOUT_KEYS = ("commit", "dirty")
CHECKOUT_COMMIT_UNKNOWN = "unknown"

#: Where an uninstall's inventory came from. `activation-receipt` names the receipt being retired as
#: this document's single `derived-from` ancestor; `ledger` names NO ancestor, because a legacy
#: unreceipted plane has no activation receipt to derive from and inventing one would forge evidence.
PRESTATE_EVIDENCE = ("activation-receipt", "ledger")
PRESTATE_EVIDENCE_ANCESTORS = {"activation-receipt": 1, "ledger": 0}

#: The publication modes the ownership substrate itself records (`install_skill_bundle`'s own
#: `record["mode"]` vocabulary, re-expressed). One spelling of one fact in both documents.
MODES = ("copy", "junction", "link")
#: Project scope is copy-only, and this is where that binds: a row this operation PUBLISHED at
#: project scope records `copy` or the body is refused.
PROJECT_MODE = "copy"
#: The dispositions under which this operation published bytes, so the mode it used is a fact it
#: holds and a null there is supplied-but-missing rather than not-supplied.
PUBLISHED_DISPOSITIONS = ("installed", "refreshed")

#: Closed and single-valued on purpose: a wildcard host binds nothing, and a host whose activation
#: this producer has never observed arrives with its first receipt, not in advance.
HOSTS = ("claude",)

#: Values that read as "every scope". Refused by NAME, because `all` is a well-formed token and the
#: token shape alone would admit it.
WILDCARDS = ("all", "any", "every", "*", "**", "*.*")

PRESTATES = ("absent", "foreign", "modified", "owned")
DISPOSITIONS = ("installed", "preserved", "refreshed", "removed")
EFFECT_STATES = ("complete", "none", "partial", "unknown")
TERMINAL_PHASES = (
    "activated",
    "activated-partial",
    "not-activated",
    "retired",
    "unknown",
)
#: v2 adds exactly ONE member: `checkout-tree`, the version read from exactly one authoritative file
#: -- `.version-bump.json`'s own `current` field, the bump driver. A mid-bump tree whose sibling
#: manifests disagree is a legitimate checkout-install state; that drift is the repository gate's
#: business (`bump-version.sh --check`), and this receipt records the driver value alone.
VERSION_SOURCES = ("adapter-readback", "archive-manifest", "checkout-tree", "request")
#: The v1 vocabulary, frozen with its generation.
VERSION_SOURCES_V1 = ("adapter-readback", "archive-manifest", "request")
#: The refused member of that closed set, kept expressible so it can be rejected by name.
VERSION_SOURCE_REQUEST = "request"
#: The one source a checkout payload may state, paired with the `checkout` object in both directions.
VERSION_SOURCE_CHECKOUT = "checkout-tree"

OBSERVATIONS = ("archive-digest", "entry-content", "journal-digest", "plan-digest")

#: Which body field each non-entry observation is allowed to be about, so an unknown always names
#: something checkable rather than free text.
OBSERVATION_SUBJECT = {
    "archive-digest": "archive_sha256",
    "journal-digest": "journal_sha256",
    "plan-digest": "plan_sha256",
}

RECORD_DIGEST_KEY = "record_sha256"
CONTENT_DIGEST_KEY = "content_digest"
BODY_KEY = "body"

# ---- the pointer plane: the FILENAME is the admission authority ------------------------------------
#
# One pointer per (agent, scope kind, resolved root), because `--agent` is required and carries no
# wildcard: a per-scope-only pointer would let a codex activation overwrite a claude one, and the
# next claude uninstall would then remove codex bytes on the strength of it. Two agents, two files;
# N roots, N files. The root key lives ONLY here, derived from the pointed receipt's own
# `scope.root`, so a hand-moved pointer disagrees with its receipt instead of redirecting a removal.
#: The directory that holds the keyed pointers, beside `receipts/` under the activation plane.
ACTIVE_DIRECTORY = "active"
#: The ONE pointer name the pre-keyed plane could write. Only (claude, user) can have written it,
#: because every writer spelled `activation_scope: claude-home`.
LEGACY_ACTIVE_POINTER_NAME = "active-receipt.json"
USER_POINTER_NAME = "user.json"
PROJECT_POINTER_PREFIX = "project-"
POINTER_SUFFIX = ".json"
#: `sha256(resolved_root)` truncated, generalising the key `manage_claude_workflows.py` already works
#: out for one entry kind. Truncation is a filename-length bound, never a security boundary: the
#: authority is the AGREEMENT between this key and the pointed receipt's own `scope.root`.
ROOT_KEY_CHARACTERS = 16

#: `public_channel` is null and `release_claim` is `none` in every document this module admits.
REQUIRED_PUBLIC_CHANNEL = None
REQUIRED_RELEASE_CLAIM = "none"

CHECKS: tuple[str, ...] = (
    "closed-key-set",
    "payload-identity",
    "host-and-scope",
    "entry-inventory",
    "effect-and-journal",
    "channel-honesty",
    "unknown-consistency",
    "typed-ancestors",
    "record-seal",
)

RESIDUALS = (
    "both seals are re-derivation, not a boundary against a same-OS-user forger: what they catch is "
    "drift, a hand-edit, and a mismatched pair",
    "this module reads the supplied observation and never lists a plane, stats an entry, digests an "
    "archive, or resolves a version, so every fact is the caller's to have observed and every "
    "unknown is the caller's to have named",
    "a sealed body is a well-formed payload, not a true one: a prestate of owned is admitted from a "
    "caller who never looked",
    "the envelope's field set is checked here only as far as this kind needs; the skills-plane "
    "receipt-envelope checker remains the authority on the envelope and on the correlation graph",
    "public_channel is null and release_claim is none because ADR-0021's evidence condition has not "
    "fired: no output of this producer may state that a published release exists",
    "the body carries no repository-head anchor, so nothing here says which commit this activation "
    "was observed against: candidate_id names the payload and plan_sha256 names the intent, and "
    "neither is a point in the repository's own history, so a consumer holding this receipt beside "
    "another artifact cannot tell from these fields alone that the two describe one tree",
    "a sealed or validated receipt is evidence: it grants no approval, admission, completion, or "
    "outward authority, and it authorizes no push, publication, merge, or deployment",
    "this module carries TWO body-validator generations: v1 documents are admitted read-only as "
    "history and no v1 body is ever sealed again. That inverts the ownership ledger's "
    "one-schema-no-migration doctrine on purpose, because a sealed receipt cannot be rewritten to a "
    "later schema without destroying what it proves, and the cost is that a v2 rule added here must "
    "be reasoned about twice",
    "the pointer plane's admission authority is a FILENAME, checked against the pointed receipt's "
    "own scope on the agent, kind, and root-key axes; the truncated root key is a filename bound, "
    "not a boundary, and the agreement check is what makes a hand-moved pointer refuse",
    "a checkout body's candidate_id is derived by its PRODUCER from the inventory rows and their "
    "content digests, and this module does not re-derive it: a retirement legitimately carries the "
    "candidate_id of the payload it retired, whose inventory is not the retirement's own",
)

#: Every character class is written out. `\\d` and `\\w` admit Unicode -- `\\d` matches the
#: Arabic-Indic `٩` -- so a digest or an identity spelled in them would read as the same value
#: while comparing unequal to it everywhere else.
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_ROOT_KEY = re.compile(r"[0-9a-f]{16}\Z")
_TOKEN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z")
_ENTRY_NAME = re.compile(r"[A-Za-z0-9]([A-Za-z0-9._/-]*[A-Za-z0-9])?\Z")
_VERSION = re.compile(r"[0-9A-Za-z]([0-9A-Za-z.+-]*[0-9A-Za-z])?\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")

_MAX_DETAIL = 512
_MAX_VERSION = 64
_MAX_ENTRY_NAME = 256
#: A resolved project root is a filesystem path this document records verbatim. The bound keeps an
#: unbounded string out of a rendered line and out of a digest input.
_MAX_ROOT = 4096

_INFINITY = float("inf")


class _Absent:
    """The third state of a field: the key is not there at all.

    A single sentinel instance, because `None` is a VALUE in this schema -- `public_channel` is
    legitimately null -- so `body.get(key)` returning None cannot distinguish "said null" from
    "said nothing", and those are different refusals.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<absent>"


ABSENT = _Absent()


class InputError(Exception):
    """Supplied input cannot be read as a receipt document at all (exit 2).

    Separate from a named reason on purpose: unusable input means the QUESTION could not be asked,
    while a reason means it was asked and the answer is "refused".
    """


def canonical_bytes(value: Any) -> bytes:
    """The one canonical form: sorted keys, tight separators, ASCII, one trailing newline.

    Identical to the envelope's form by necessity, not by coincidence: the envelope's content digest
    is derived over the bytes of a body this module writes, so a second spelling here would make a
    receipt this module sealed fail the skills-plane checker.
    """
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def body_without_record_digest(body: dict[str, Any]) -> dict[str, Any]:
    """The exact bytes-source of the record seal: the body minus its own digest field."""
    return {key: value for key, value in body.items() if key != RECORD_DIGEST_KEY}


def record_digest(body: dict[str, Any], subject: str) -> str:
    """The ONE record-seal derivation, used both to seal and to re-derive.

    A second derivation would be a second definition of "sealed", and the two would disagree exactly
    once, on the document nobody re-checked. `RecursionError` is classified rather than raised as a
    traceback: the decoder admits nesting the re-encode cannot survive.
    """
    try:
        return sha256_hex(canonical_bytes(body_without_record_digest(body)))
    except RecursionError as exc:
        raise InputError(
            f"{subject} carries a body nested too deeply to re-encode canonically, so its record "
            f"seal cannot be derived: {exc}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise InputError(
            f"{subject} carries a body that cannot be encoded canonically, so its record seal "
            f"cannot be derived: {exc}"
        ) from exc


def envelope_content_digest(body: dict[str, Any], subject: str) -> str:
    """The envelope's digest, re-expressed: sha256 over the canonical bytes of the whole body.

    It seals the body INCLUDING `record_sha256`, which is what makes the two seals nested rather
    than alternative.
    """
    try:
        return sha256_hex(canonical_bytes(body))
    except RecursionError as exc:
        raise InputError(
            f"{subject} carries a body nested too deeply to re-encode canonically, so its envelope "
            f"content digest cannot be derived: {exc}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise InputError(
            f"{subject} carries a body that cannot be encoded canonically, so its envelope content "
            f"digest cannot be derived: {exc}"
        ) from exc


def seal_body(body: dict[str, Any]) -> dict[str, Any]:
    """Return the body with its record seal written, derived over the body minus that field."""
    sealed = body_without_record_digest(body)
    sealed[RECORD_DIGEST_KEY] = record_digest(sealed, "the observation")
    return sealed


_ESCAPES = {
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def escape_display(value: str) -> str:
    """Escape every control character before a value derived from an artifact reaches a rendered line.

    A `detail` is free text observed in the field: a bare newline forges a second line that looks
    like this tool's own output, a `\\r` overwrites the line already printed, and an `\\x1b[2J`
    clears the reader's screen. The STORED value is never touched -- a receipt records what was
    observed -- so this is a rendering rule and nothing else. DEL (0x7f) is included because it is a
    control character that `str.isprintable` already rejects but a naive `< 0x20` test would pass.
    """
    out: list[str] = []
    for char in value:
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\x{ord(char):02x}")
        else:
            out.append(char)
    return "".join(out)


def _reject_nonfinite_constant(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest receipt carries one."""
    raise InputError(f"the supplied document carries the non-finite JSON constant {token}")


def _reject_nonfinite_values(value: Any, subject: str) -> None:
    """Refuse a number that BECAME non-finite while parsing, which `parse_constant` cannot see.

    `json.loads('{"n": 1e400}')` yields `inf` without ever calling `parse_constant`, and that `inf`
    would reach `json.dumps(..., allow_nan=False)` inside a seal derivation as a bare `ValueError`.
    The walk is iterative because the decoder admits nesting deeper than a recursive walk survives.
    """
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, float) and not -_INFINITY < current < _INFINITY:
            raise InputError(
                f"{subject} carries the non-finite number {current!r}, which no canonical document "
                "can encode"
            )
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a body carrying two `effect_state`s
    parses to whichever the writer put second. That is a document with two meanings, and choosing
    one of them is the guess this module refuses everywhere else.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(
                f"the supplied document repeats the JSON key {key!r}, so it has two meanings"
            )
        seen[key] = value
    return seen


def read_regular_file(path: str, label: str) -> str:
    """Read one supplied path as UTF-8 text. Every failure here is unusable input (exit 2).

    The regular-file check runs BEFORE the read: opening a FIFO blocks until a writer appears, which
    for a supplied path may be never, so a directory mistake would exit 2 promptly while a FIFO
    mistake hung forever. `Path.stat()` follows a symlink to its target, which is the question being
    asked -- "is what I would read a regular file" -- not "is the path itself one".
    """
    candidate = Path(path)
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise InputError(f"cannot read the {label} {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise InputError(f"the {label} {path} is not a regular file, so it cannot be read")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read the {label} {path}: {exc}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"the {label} {path} is not UTF-8 text: {exc}") from exc


def parse_json_object(text: str, subject: str) -> dict[str, Any]:
    """Parse one JSON object with the repeated-key and both non-finite guards applied."""
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_nonfinite_constant)
    except RecursionError as exc:
        raise InputError(
            f"{subject} nests JSON deeper than this interpreter can decode, so it cannot be read as "
            f"one receipt document: {exc}"
        ) from exc
    except ValueError as exc:
        raise InputError(f"{subject} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"{subject} is not a JSON object")
    _reject_nonfinite_values(value, subject)
    return value


def load_document(path: str, label: str) -> dict[str, Any]:
    return parse_json_object(read_regular_file(path, label), f"the {label} {path}")


# ---- the accumulating evidence --------------------------------------------------------------------


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the result can say which part of the receipt is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree.
    """

    def __init__(self) -> None:
        self.groups: dict[str, list[str]] = {slug: [] for slug in CHECKS}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in CHECKS:
            flat.extend(self.groups[slug])
        return flat

    def verdict(self, command: str) -> str:
        """Exactly one verdict, always: one selection over one partition.

        The final branch is defence in depth against this module's own worst failure -- returning no
        verdict -- and it is a named reason rather than an `assert`, which `python -O` strips.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command == "seal":
            return VERDICT_SEALED
        if command == "validate":
            return VERDICT_VALIDATED
        self.note(
            "closed-key-set",
            f"no verdict follows from the command {command!r}, and an underivable verdict is a "
            "refusal rather than a guess",
        )
        return VERDICT_REFUSED


class Observed:
    """What the checks OBSERVED, hoisted out of every literal that would otherwise drop it.

    Each attribute is written by the check that can see it and read by the later check that needs it.
    The two `*_null` sets are the load-bearing pair: a later admission check must be able to ask "was
    this value absent" and get an answer that does not depend on the value itself being present.
    """

    __slots__ = (
        "dispositions",
        "entry_names",
        "entry_content_null",
        "digest_null",
        "unknown_index",
        "operation",
        "effect_state",
        "terminal_phase",
        "unknown_records",
        "generation",
        "checkout_present",
        "scope_kind",
        "scope_agent",
        "scope_root",
        "prestate_evidence",
    )

    def __init__(self) -> None:
        #: Which body generation this document declares, resolved once before any check reads a
        #: key set. `None` means the declaration itself is unusable, and every rule that reads it
        #: then falls back to the v1 shape, which is the fail-closed direction: a document that
        #: cannot say which generation it is gets the older, stricter ancestor rule.
        self.generation: Generation | None = None
        #: Whether the body carries a `checkout` OBJECT. Observed as shape, before the checks, so the
        #: archive-digest rules can ask "was there an archive at all" without depending on the value.
        self.checkout_present: bool = False
        self.scope_kind: str | None = None
        self.scope_agent: str | None = None
        self.scope_root: str | None = None
        self.prestate_evidence: str | None = None
        self.dispositions: list[str] = []
        self.entry_names: list[str] = []
        #: Entries whose content digest is null AND whose disposition means content should exist.
        self.entry_content_null: set[str] = set()
        #: Body digest fields explicitly recorded as null.
        self.digest_null: set[str] = set()
        #: (observation, subject) pairs the body actually recorded as unknown.
        self.unknown_index: set[tuple[str, str]] = set()
        self.unknown_records: list[dict[str, Any]] = []
        self.operation: str | None = None
        self.effect_state: str | None = None
        self.terminal_phase: str | None = None


# ---- the two generations --------------------------------------------------------------------------


class Generation:
    """One body generation's closed shapes, resolved ONCE per document and then read everywhere.

    Two generations exist and only one of them is writable. `seal` admits v2 alone: a v1 document is
    immutable evidence, so re-sealing one would destroy exactly what it proves, and there is no
    migration that could faithfully convert it -- the fields v2 needs (`scope`, per-row `mode`) were
    never observed by the run that wrote it, and filling them here would make this module the author
    of facts it did not see.

    The shapes are DATA rather than branches so a check reads one key set instead of asking which
    generation it is in three places and disagreeing with itself in the fourth.
    """

    __slots__ = ("schema", "base_keys", "entry_keys", "version_sources", "sealable", "label")

    def __init__(
        self,
        schema: str,
        base_keys: tuple[str, ...],
        entry_keys: tuple[str, ...],
        version_sources: tuple[str, ...],
        sealable: bool,
        label: str,
    ) -> None:
        self.schema = schema
        self.base_keys = base_keys
        self.entry_keys = entry_keys
        self.version_sources = version_sources
        self.sealable = sealable
        self.label = label

    @property
    def is_v2(self) -> bool:
        return self.schema == BODY_SCHEMA

    def body_keys(self, operation: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return `(required, optional)` for one operation. v1 has no per-operation variance.

        An operation this module cannot read yields the widest admissible pair, so the key-set walk
        does not report a second reason about a document the closed-vocabulary check already refuses
        by name. Two reasons for one defect read as two defects.
        """
        if not self.is_v2:
            return self.base_keys, ()
        if operation == "uninstall":
            return tuple(sorted(self.base_keys + BODY_KEYS_UNINSTALL)), BODY_KEYS_OPTIONAL
        if operation in OPERATIONS:
            return self.base_keys, BODY_KEYS_OPTIONAL
        return self.base_keys, tuple(sorted(BODY_KEYS_OPTIONAL + BODY_KEYS_UNINSTALL))


GENERATION_V1 = Generation(
    BODY_SCHEMA_V1, BODY_KEYS_V1, ENTRY_KEYS_V1, VERSION_SOURCES_V1, False, "v1"
)
GENERATION_V2 = Generation(BODY_SCHEMA, BODY_KEYS, ENTRY_KEYS, VERSION_SOURCES, True, "v2")
GENERATIONS = {GENERATION_V1.schema: GENERATION_V1, GENERATION_V2.schema: GENERATION_V2}


def generation_of(body: dict[str, Any]) -> Generation | None:
    """Resolve the declared generation, or `None` when the declaration itself is unusable."""
    declared = field(body, "schema_version")
    if isinstance(declared, str):
        return GENERATIONS.get(declared)
    return None


# ---- the pointer plane ----------------------------------------------------------------------------


def root_key(root: str) -> str:
    """The pointer filename's root segment: `sha256(resolved_root)` truncated.

    ONE derivation, exported, because the writer that names a pointer file and the reader that
    admits one must agree exactly; two spellings would disagree on the first path whose bytes differ
    outside the first 16 hexadecimal characters, which is to say never in testing and once in the
    field.
    """
    return sha256_hex(root.encode("utf-8"))[:ROOT_KEY_CHARACTERS]


def pointer_name(kind: str, root: str | None = None) -> str:
    """The pointer filename for one scope. A project scope with no root cannot be named."""
    if kind == SCOPE_USER:
        return USER_POINTER_NAME
    if kind == SCOPE_PROJECT:
        if not isinstance(root, str) or not root:
            raise InputError("a project-scope pointer is named by its resolved root, and none was supplied")
        return f"{PROJECT_POINTER_PREFIX}{root_key(root)}{POINTER_SUFFIX}"
    raise InputError(f"{kind!r} is not one of the closed scope kinds {list(SCOPE_KINDS)}")


def pointer_path(activation_root: Path, agent: str, kind: str, root: str | None = None) -> Path:
    """The ONE pointer path for one (agent, scope kind, resolved root)."""
    if not isinstance(agent, str) or not _TOKEN.match(agent) or agent in WILDCARDS or "*" in agent:
        raise InputError(f"{agent!r} is not one agent segment a pointer path may carry")
    return activation_root / ACTIVE_DIRECTORY / agent / pointer_name(kind, root)


def legacy_pointer_path(activation_root: Path) -> Path:
    """The pre-keyed plane's single pointer. Only (claude, user) can have written it."""
    return activation_root / LEGACY_ACTIVE_POINTER_NAME


def parse_pointer_path(path: Path) -> dict[str, Any] | None:
    """Read `(agent, kind, root_key)` out of a keyed pointer path, or `None` if it is not one.

    The filename is the admission authority, so it is PARSED rather than trusted: a name outside the
    two shapes names no scope this plane can act on, and answering `None` is what makes the caller
    refuse instead of guessing which scope an unrecognised file meant.
    """
    name = path.name
    parent = path.parent
    agent = parent.name
    if parent.parent.name != ACTIVE_DIRECTORY:
        return None
    if not agent or not _TOKEN.match(agent) or agent in WILDCARDS:
        return None
    if name == USER_POINTER_NAME:
        return {"agent": agent, "kind": SCOPE_USER, "root_key": None}
    if not name.startswith(PROJECT_POINTER_PREFIX) or not name.endswith(POINTER_SUFFIX):
        return None
    key = name[len(PROJECT_POINTER_PREFIX) : -len(POINTER_SUFFIX)]
    if not _ROOT_KEY.match(key):
        return None
    return {"agent": agent, "kind": SCOPE_PROJECT, "root_key": key}


def pointer_disagreements(path: Path, body: dict[str, Any]) -> list[str]:
    """Every axis on which a pointer FILENAME disagrees with the receipt it points at.

    Three axes, checked in this order because the later ones have nothing to compare when an earlier
    one already failed: the pointer's KIND against `scope.kind` (a `user.json` aimed at a
    project-scope receipt has no root segment to compare at all), the agent segment against
    `scope.agent`, and -- for a project pointer -- the filename's root key against
    `sha256(scope.root)` recomputed here from the receipt's own recorded root.

    Empty means agreement. A caller that finds a non-empty list refuses; this function decides
    nothing and moves nothing.
    """
    parsed = parse_pointer_path(path)
    if parsed is None:
        return [
            f"the pointer {str(path)!r} is not one of this plane's two keyed names "
            f"({USER_POINTER_NAME} or {PROJECT_POINTER_PREFIX}<root-key>{POINTER_SUFFIX} under "
            f"{ACTIVE_DIRECTORY}/<agent>/), so which activation it states cannot be read"
        ]
    scope = field(body, "scope")
    if not isinstance(scope, dict):
        return [
            f"the pointer {str(path)!r} names a receipt whose body carries no scope object, so the "
            "pointer's own key cannot be compared against what the receipt says it activated"
        ]
    disagreements: list[str] = []
    kind = scope.get("kind")
    if kind != parsed["kind"]:
        # The KIND axis first (audit N3): with the kinds disagreeing there is no matching segment to
        # compare on the root axis, and reporting a root mismatch there would name the wrong defect.
        return [
            f"the pointer {str(path)!r} is a {parsed['kind']}-scope pointer while the receipt it "
            f"names records scope.kind {escape_display(str(kind))!r}; a pointer states the scope it "
            "is filed under, and a receipt about another scope is not that statement"
        ]
    agent = scope.get("agent")
    if agent != parsed["agent"]:
        disagreements.append(
            f"the pointer {str(path)!r} is filed under agent {parsed['agent']!r} while the receipt "
            f"it names records scope.agent {escape_display(str(agent))!r}; one pointer per agent is "
            "what keeps one agent's uninstall from removing another's bytes"
        )
    if parsed["kind"] == SCOPE_PROJECT:
        recorded = scope.get("root")
        derived = root_key(recorded) if isinstance(recorded, str) and recorded else None
        if derived != parsed["root_key"]:
            disagreements.append(
                f"the pointer {str(path)!r} carries the root key {parsed['root_key']!r} while the "
                f"receipt it names records a scope.root whose key is "
                f"{escape_display(str(derived))!r}; a hand-moved pointer does not redirect a removal"
            )
    return disagreements


def checkout_candidate_id(entries: Any) -> str:
    """The ONE candidate-identity derivation for a manifest-less checkout payload.

    A checkout has no archive to digest and no manifest to read an identity out of, and
    `candidate_id` is non-null in every generation of this body -- a receipt that cannot name what it
    activated binds nothing. So the identity is a digest over the DISCOVERED INVENTORY ROWS AND THEIR
    CONTENT DIGESTS: two different dirty trees publish different bytes, so their rows differ, so this
    value differs.

    It is deliberately NOT `build_release.py`'s derivation, which digests the source commit and tree
    -- both undefined for a dirty checkout, and substituting `unknown` there would collide every
    dirty tree onto one identity.

    This module does not RE-DERIVE the value while validating: a retirement receipt legitimately
    carries the candidate_id of the payload it retired, whose inventory is not the retirement's own.
    Exported so the producer that does derive it has exactly one definition to call.
    """
    rows: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        rows.append({"content_sha256": entry.get("content_sha256"), "entry_name": entry.get("entry_name")})
    rows.sort(key=lambda row: (str(row["entry_name"]), str(row["content_sha256"])))
    return sha256_hex(canonical_bytes({"rows": rows, "schema": BODY_SCHEMA}))


# ---- field readers: absent, null, and empty are three different facts -----------------------------


def field(container: dict[str, Any], key: str) -> Any:
    """`ABSENT` when the key is not there, the value otherwise.

    `container.get(key)` cannot serve: `None` is a legitimate VALUE in this schema, so a `get` that
    returned None would merge "said null" with "said nothing" -- two different refusals.
    """
    if key not in container:
        return ABSENT
    return container[key]


def _closed(
    assessment: Assessment, slug: str, value: Any, key: str, vocabulary: tuple[str, ...], subject: str
) -> str | None:
    if value is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no {key}, and the closed {BODY_SCHEMA} field set requires one of "
            f"{list(vocabulary)}",
        )
        return None
    if not isinstance(value, str) or value not in vocabulary:
        assessment.note(
            slug,
            f"{subject}'s {key} is {value!r}, which is not one of the closed vocabulary "
            f"{list(vocabulary)}; free text here would make every cross-field rule that reads it "
            "uncheckable",
        )
        return None
    return value


def _hex64(assessment: Assessment, slug: str, value: Any, key: str, subject: str) -> str | None:
    """A required, never-null sha256. Absent, null, and empty are three named reasons."""
    if value is ABSENT:
        assessment.note(slug, f"{subject} carries no {key}, which every receipt of this kind records")
        return None
    if value is None:
        assessment.note(
            slug,
            f"{subject} records {key} as null, but this field identifies the payload and has no "
            "honest unknown: a receipt that cannot name what it activated binds nothing",
        )
        return None
    if isinstance(value, str) and not value:
        assessment.note(
            slug,
            f"{subject} supplies {key} as an empty string, which is a value supplied and lost rather "
            "than a value never supplied; the two are different defects and neither is a digest",
        )
        return None
    if not isinstance(value, str) or not _HEX64.match(value):
        assessment.note(
            slug,
            f"{subject}'s {key} is {value!r}, not 64 lowercase hexadecimal characters; the class is "
            "written [0-9a-f] and never \\d, which admits Unicode digits that compare unequal to the "
            "value they look like",
        )
        return None
    return value


def _nullable_hex64(
    assessment: Assessment, slug: str, value: Any, key: str, subject: str, observed: Observed
) -> str | None:
    """A sha256 that may honestly be null, in which case the null is RECORDED for the unknown check.

    Recording the null in `observed.digest_null` is what lets the later admission check consult a
    recorded UNKNOWN rather than only the recorded facts: the absent digest is not a fact, so a
    fact-only walk would never reach it.
    """
    if value is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no {key}; a value that may be unknown is recorded as null beside a "
            "named unknown, never omitted, because an omitted field reads as a field nobody thought "
            "about",
        )
        return None
    if value is None:
        observed.digest_null.add(key)
        return None
    if isinstance(value, str) and not value:
        assessment.note(
            slug,
            f"{subject} supplies {key} as an empty string; an unobservable digest is null beside a "
            "named unknown, and an empty string is a value supplied and lost",
        )
        return None
    if not isinstance(value, str) or not _HEX64.match(value):
        assessment.note(
            slug,
            f"{subject}'s {key} is {value!r}, not 64 lowercase hexadecimal characters and not null",
        )
        return None
    return value


def _token(assessment: Assessment, slug: str, value: Any, key: str, subject: str) -> str | None:
    if value is ABSENT:
        assessment.note(slug, f"{subject} carries no {key}")
        return None
    if not isinstance(value, str) or not _TOKEN.match(value):
        assessment.note(
            slug,
            f"{subject}'s {key} is not a lowercase ASCII token of letters, ASCII digits, and interior "
            f"hyphens (found {value!r}); correlation compares this value literally, so one identity "
            "must have exactly one spelling",
        )
        return None
    return value


# ---- body checks ---------------------------------------------------------------------------------


def check_body_key_set(
    assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed
) -> None:
    """The closed body: exactly the keys this generation's variant admits, no more and no fewer.

    The key set is per (generation, operation): v2's uninstall variant requires `prestate_evidence`
    and every other operation refuses it, and `checkout` is optional on all three. That is what makes
    "a ledger-evidence install" and "a receipt-evidence body with no evidence field" unrepresentable
    rather than guarded in prose.
    """
    generation = observed.generation
    declared = field(body, "schema_version")
    if generation is None:
        assessment.note(
            "closed-key-set",
            f"{subject} declares schema_version {declared!r}, which is neither {BODY_SCHEMA} nor the "
            f"read-only historical {BODY_SCHEMA_V1}, so which field set and which seal derivation it "
            "is about is not established",
        )
        return
    required, optional = generation.body_keys(field(body, "operation"))
    present = set(body)
    for key in sorted(set(required) - present):
        assessment.note(
            "closed-key-set",
            f"{subject} carries no {key}, which the closed {generation.schema} field set requires",
        )
    for key in sorted(present - set(required) - set(optional)):
        assessment.note(
            "closed-key-set",
            f"{subject} carries the unknown field {key!r}; {generation.schema} is closed, so a field "
            "this version cannot honour is refused rather than ignored, and a new meaning arrives as "
            "a version bump",
        )


def check_payload_identity(assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed) -> None:
    """Exact resolved version plus payload identity, with the request kept separate from the readback."""
    slug = "payload-identity"
    observed.operation = _closed(assessment, slug, field(body, "operation"), "operation", OPERATIONS, subject)
    _hex64(assessment, slug, field(body, "candidate_id"), "candidate_id", subject)
    _nullable_hex64(assessment, slug, field(body, "archive_sha256"), "archive_sha256", subject, observed)

    requested = field(body, "requested_version")
    if requested is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no requested_version; a caller that requested no version records "
            "null, which is a statement, while an absent key is a body that never spoke about the "
            "request at all",
        )
    elif requested is not None:
        if isinstance(requested, str) and not requested:
            assessment.note(
                slug,
                f"{subject} supplies requested_version as an empty string, which is a request "
                "supplied and lost; a caller that requested nothing records null",
            )
        elif not isinstance(requested, str) or not _VERSION.match(requested) or len(requested) > _MAX_VERSION:
            assessment.note(
                slug,
                f"{subject}'s requested_version is {requested!r}, which is neither null nor an ASCII "
                f"version string of at most {_MAX_VERSION} characters",
            )

    resolved = field(body, "resolved_version")
    if resolved is ABSENT:
        assessment.note(slug, f"{subject} carries no resolved_version, which is this kind's whole subject")
    elif resolved is None:
        assessment.note(
            slug,
            f"{subject} records resolved_version as null; this receipt exists to record the EXACT "
            "resolved version, and a null here would leave requested_version as the only version in "
            "the document -- which is the substitution Seed agentic-sdlc-0faa forbids",
        )
    elif isinstance(resolved, str) and not resolved:
        assessment.note(
            slug,
            f"{subject} supplies resolved_version as an empty string, which is a resolved version "
            "supplied and lost rather than one never resolved",
        )
    elif not isinstance(resolved, str) or not _VERSION.match(resolved) or len(resolved) > _MAX_VERSION:
        assessment.note(
            slug,
            f"{subject}'s resolved_version is {resolved!r}, not an ASCII version string of at most "
            f"{_MAX_VERSION} characters",
        )

    generation = observed.generation if observed.generation is not None else GENERATION_V1
    source = _closed(
        assessment, slug, field(body, "version_source"), "version_source", generation.version_sources, subject
    )
    if source == VERSION_SOURCE_REQUEST:
        assessment.note(
            slug,
            f"{subject} records version_source {VERSION_SOURCE_REQUEST!r}: the requested model of the "
            "version is not a readback of it. Seed agentic-sdlc-0faa is exact -- the receipt records "
            "the exact resolved version, and a requested identity never becomes readback -- so this "
            "value is expressible only so that it can be refused by name instead of being spelled as "
            "an adapter readback",
        )
    if generation.is_v2:
        check_checkout(assessment, body, subject, observed, source)


def check_checkout(
    assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed, source: str | None
) -> None:
    """The optional checkout object, and the two facts it is paired with in BOTH directions.

    `checkout` present means the payload was a tree rather than an archive, and that one statement
    fixes two others: the version was read from the checkout tree, and there is no archive digest to
    record. Writing those as three independent fields is what would let a body say "release payload"
    and "checkout payload" at once; pairing them makes the disagreement unrepresentable instead of
    guarded.

    The `derived-from` ancestor half of the same invariant lives in `check_ancestors`, because that is
    where the ancestor counts are.
    """
    slug = "payload-identity"
    value = field(body, "checkout")
    if value is not ABSENT:
        if not isinstance(value, dict):
            assessment.note(
                slug,
                f"{subject}'s checkout is {type(value).__name__}, not a {list(CHECKOUT_KEYS)} object; "
                "a checkout payload is recorded as that object or the key is absent, and null is "
                "neither",
            )
        else:
            for key in sorted(set(CHECKOUT_KEYS) - set(value)):
                assessment.note(slug, f"{subject}'s checkout carries no {key}, which the object requires")
            for key in sorted(set(value) - set(CHECKOUT_KEYS)):
                assessment.note(
                    slug,
                    f"{subject}'s checkout carries the unknown field {key!r}; the object is closed at "
                    f"{list(CHECKOUT_KEYS)}",
                )
            commit = field(value, "commit")
            if commit is ABSENT:
                pass  # already reported by the closed-key walk above
            elif commit == CHECKOUT_COMMIT_UNKNOWN:
                pass  # the honest negative: no readable git metadata, stated rather than inferred
            elif not isinstance(commit, str) or not _HEX40.match(commit):
                assessment.note(
                    slug,
                    f"{subject}'s checkout commit is {commit!r}, which is neither 40 lowercase "
                    f"hexadecimal characters nor the explicit {CHECKOUT_COMMIT_UNKNOWN!r}; a commit "
                    "this run could not read is named, never left as a plausible-looking value",
                )
            dirty = field(value, "dirty")
            if dirty is ABSENT:
                pass  # already reported by the closed-key walk above
            elif not isinstance(dirty, bool):
                assessment.note(
                    slug,
                    f"{subject}'s checkout dirty is {dirty!r}, not a boolean; 0, 1, and \"false\" each "
                    "read as a cleanliness this receipt cannot claim to have observed",
                )
    if observed.checkout_present and source is not None and source != VERSION_SOURCE_CHECKOUT:
        assessment.note(
            slug,
            f"{subject} carries a checkout object while recording version_source {source!r}; a "
            f"checkout payload's version is read from the checkout tree, so the pair is "
            f"{VERSION_SOURCE_CHECKOUT!r} or there is no checkout object",
        )
    if not observed.checkout_present and source == VERSION_SOURCE_CHECKOUT:
        assessment.note(
            slug,
            f"{subject} records version_source {VERSION_SOURCE_CHECKOUT!r} with no checkout object; "
            "the tree the version was read from is recorded, or the source is not that tree",
        )
    if observed.checkout_present and field(body, "archive_sha256") not in (None, ABSENT):
        assessment.note(
            slug,
            f"{subject} carries a checkout object beside a non-null archive_sha256; a checkout payload "
            "has no archive, so a digest here would name a file this activation never drew from, and "
            "the body would state both payload classes at once",
        )


def check_prestate_evidence(
    assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed
) -> None:
    """Which prestate evidence a v2 retirement drew its inventory from, as a closed discriminator.

    The variant exists because the legacy-unreceipted retirement is otherwise UNREPRESENTABLE: the
    family requires exactly one `derived-from` ancestor, and a plane whose rows were written by a
    pre-receipt install has no activation receipt to name. The alternative -- deleting that removal
    path -- would force an INSTALL before a removal on exactly the hosts this program exists to stop
    stranding.
    """
    if observed.generation is None or not observed.generation.is_v2:
        return
    if field(body, "operation") != "uninstall":
        return
    observed.prestate_evidence = _closed(
        assessment,
        "payload-identity",
        field(body, "prestate_evidence"),
        "prestate_evidence",
        PRESTATE_EVIDENCE,
        subject,
    )


def check_host_and_scope(
    assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed
) -> None:
    """Which plane this receipt observed, in whichever generation's spelling -- never in both.

    v1 spelled it TWICE: a `host` token for the plane and an `activation_scope` token for the part of
    it. v2 spells it ONCE, as the closed `scope` union, whose `agent` IS the plane; `host` is deleted
    rather than kept beside it, because one fact in two spellings joined by an agreement check is the
    same representable illegal state `activation_scope` and `root_key` were deleted for (conductor
    ruling, 2026-08-25). A reader derives every display string from `scope.agent`, including a
    host-application spelling like `claude-code`, which is a rendering and not a stored field.

    So the host checks below are v1-only, and they are not a fallback: a v2 body carrying `host` is
    refused by the closed key set before this check runs, and a v1 body missing it is refused there
    too. Neither generation can express the other's shape.
    """
    slug = "host-and-scope"
    if observed.generation is not None and observed.generation.is_v2:
        check_scope(assessment, body, subject, observed)
        return

    host = field(body, "host")
    if isinstance(host, str) and (host in WILDCARDS or "*" in host):
        assessment.note(
            slug,
            f"{subject}'s host is the wildcard {host!r}; a receipt names the ONE host plane it "
            "observed, because a wildcard would read as evidence about a plane this operation never "
            "touched",
        )
    else:
        _closed(assessment, slug, host, "host", HOSTS, subject)

    scope = field(body, "activation_scope")
    if isinstance(scope, str) and (scope in WILDCARDS or "*" in scope):
        assessment.note(
            slug,
            f"{subject}'s activation_scope is the wildcard {scope!r}; the scope is named exactly, and "
            "a well-formed token like 'all' is refused here by name because the token shape alone "
            "would admit it",
        )
    else:
        _token(assessment, slug, scope, "activation_scope", subject)


def check_scope(
    assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed
) -> None:
    """The v2 scope union: closed kinds, EXACT key sets per kind, and an absolute project root.

    What the exactness buys, in the two directions a prose guard would have had to catch: a
    user-scope object carrying a `root` is refused because a user activation has no project root to
    name, and a project-scope object missing one is refused because the pointer that admits it is
    keyed by exactly that value. Neither kind may carry a `root_key`: the pointer filename derives
    that key, and a stored copy of a derivation of a sibling field is the same disagreement-by-
    construction v1's `activation_scope` was deleted for.

    `agent` is the ONE statement of which plane this receipt observed -- there is no body-level `host`
    beside it in this generation, and therefore no agreement check between them to get wrong.
    """
    slug = "host-and-scope"
    scope = field(body, "scope")
    if scope is ABSENT:
        return  # already reported by the closed body key set
    if not isinstance(scope, dict):
        assessment.note(
            slug,
            f"{subject}'s scope is {type(scope).__name__}, not a closed scope object; the union's kind "
            "is what selects every later rule, and a value with no kind selects none of them",
        )
        return
    kind = _closed(assessment, slug, field(scope, "kind"), "scope.kind", SCOPE_KINDS, subject)
    observed.scope_kind = kind
    expected = SCOPE_KEYS.get(kind) if kind is not None else None
    if expected is not None:
        present = set(scope)
        for key in sorted(set(expected) - present):
            assessment.note(
                slug,
                f"{subject}'s {kind}-scope scope carries no {key}, which that kind's exact key set "
                f"{list(expected)} requires",
            )
        for key in sorted(present - set(expected)):
            assessment.note(
                slug,
                f"{subject}'s {kind}-scope scope carries the field {key!r}, which that kind's exact "
                f"key set {list(expected)} does not admit; a root key in the body would be a second "
                "spelling of what the pointer filename derives, and a root on a user scope names a "
                "project this activation never touched",
            )
    agent = field(scope, "agent")
    if isinstance(agent, str) and (agent in WILDCARDS or "*" in agent):
        assessment.note(
            slug,
            f"{subject}'s scope.agent is the wildcard {agent!r}; the pointer plane is keyed by one "
            "agent per file, and a wildcard there would let one agent's removal reach another's bytes",
        )
    else:
        observed.scope_agent = _closed(assessment, slug, agent, "scope.agent", HOSTS, subject)
    if kind != SCOPE_PROJECT:
        return
    root = field(scope, "root")
    if root is ABSENT:
        return  # already reported by the exact key set above
    if not isinstance(root, str) or not root:
        assessment.note(
            slug,
            f"{subject}'s project scope records root {root!r}, which is not a path; the resolved root "
            "is what the pointer key is derived from and what a removal is bounded by",
        )
        return
    if len(root) > _MAX_ROOT:
        assessment.note(
            slug,
            f"{subject}'s project scope records a root of {len(root)} characters, over the "
            f"{_MAX_ROOT}-character bound",
        )
        return
    if not root.startswith("/"):
        assessment.note(
            slug,
            f"{subject}'s project scope records the root {escape_display(root)!r}, which is not an "
            "absolute POSIX path; a relative root resolves against whatever directory a later reader "
            "happens to be in, and the project-scope plane is certified on Linux only",
        )
        return
    if "\x00" in root or root != root.strip() or any(ord(character) < 0x20 for character in root):
        assessment.note(
            slug,
            f"{subject}'s project scope records a root carrying a control character or surrounding "
            "whitespace, so the path this receipt is about is not the path it appears to name",
        )
        return
    observed.scope_root = root


#: Which dispositions each prestate admits. A `foreign` or `modified` entry may only be PRESERVED:
#: the installer's ownership model keeps an entry this bundle does not own rather than replacing it,
#: and recording it as installed or refreshed would be a claim of an adoption that did not happen.
PRESTATE_DISPOSITIONS = {
    "absent": ("installed", "preserved"),
    "owned": ("preserved", "refreshed", "removed"),
    "foreign": ("preserved",),
    "modified": ("preserved",),
}

#: Which dispositions each operation admits. An uninstall that recorded an install, or an install
#: that recorded a removal, is a receipt describing an operation other than the one it names.
OPERATION_DISPOSITIONS = {
    "install": ("installed", "preserved", "refreshed"),
    "update": ("installed", "preserved", "refreshed"),
    "uninstall": ("preserved", "removed"),
}

#: Dispositions under which the entry's content digest MUST be derivable, so a null there is
#: supplied-but-missing and requires a named unknown. `removed` leaves nothing to digest, and
#: `preserved` over an `absent` prestate never had anything: those nulls are not-supplied.
CONTENT_BEARING = ("installed", "refreshed", "preserved")


def check_entry_inventory(assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed) -> None:
    """One record per managed entry, each with its content digest, prestate, and disposition."""
    slug = "entry-inventory"
    entries = field(body, "entries")
    if entries is ABSENT:
        assessment.note(slug, f"{subject} carries no entries, and the inventory is this receipt's subject")
        return
    if not isinstance(entries, list):
        assessment.note(slug, f"{subject}'s entries is {type(entries).__name__}, not a list of entry records")
        return

    generation = observed.generation if observed.generation is not None else GENERATION_V1
    entry_keys = generation.entry_keys
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"{subject}'s entry {index}"
        if not isinstance(entry, dict):
            assessment.note(slug, f"{where} is {type(entry).__name__}, not an entry record object")
            continue
        for key in sorted(set(entry_keys) - set(entry)):
            assessment.note(slug, f"{where} carries no {key}, which every entry record requires")
        for key in sorted(set(entry) - set(entry_keys)):
            assessment.note(
                slug,
                f"{where} carries the unknown field {key!r}; the entry record is closed, so a field "
                "this version cannot honour is refused rather than ignored",
            )

        name = field(entry, "entry_name")
        resolved_name: str | None = None
        if name is ABSENT:
            pass  # already reported by the closed-key walk above
        elif not isinstance(name, str) or not _ENTRY_NAME.match(name) or len(name) > _MAX_ENTRY_NAME:
            assessment.note(
                slug,
                f"{where}'s entry_name is {name!r}, which is not a relative ASCII entry name of at "
                f"most {_MAX_ENTRY_NAME} characters",
            )
        elif ".." in name:
            assessment.note(
                slug,
                f"{where}'s entry_name {name!r} contains '..'; an inventory row names one entry "
                "inside the scope, and a traversal segment makes which entry it named unresolvable",
            )
        elif name in seen:
            assessment.note(
                slug,
                f"{where} repeats the entry_name {name!r}; two rows for one entry are two prestates "
                "for one entry, and picking one of them is a guess",
            )
        else:
            resolved_name = name
            seen.add(name)
            observed.entry_names.append(name)

        prestate = _closed(assessment, slug, field(entry, "prestate"), "prestate", PRESTATES, where)
        disposition = _closed(assessment, slug, field(entry, "disposition"), "disposition", DISPOSITIONS, where)
        if disposition is not None:
            observed.dispositions.append(disposition)
        if prestate is not None and disposition is not None:
            admitted = PRESTATE_DISPOSITIONS[prestate]
            if disposition not in admitted:
                assessment.note(
                    slug,
                    f"{where} records prestate {prestate!r} with disposition {disposition!r}; a "
                    f"{prestate} entry admits only {list(admitted)}. A foreign or modified entry is "
                    "PRESERVED and named in this inventory, never adopted, replaced, or dropped from "
                    "it, because a receipt that omitted it would read as a clean activation of a "
                    "collided plane",
                )

        if generation.is_v2:
            check_entry_mode(assessment, entry, where, observed, disposition)

        content = field(entry, "content_sha256")
        content_is_null = content is None
        if content is ABSENT:
            pass  # already reported by the closed-key walk above
        elif content_is_null:
            pass  # classified against the disposition below
        elif isinstance(content, str) and not content:
            assessment.note(
                slug,
                f"{where} supplies content_sha256 as an empty string, which is a digest supplied and "
                "lost; an undigestable entry records null beside a named unknown",
            )
        elif not isinstance(content, str) or not _HEX64.match(content):
            assessment.note(
                slug,
                f"{where}'s content_sha256 is {content!r}, not 64 lowercase hexadecimal characters "
                "and not null",
            )

        if disposition is not None and content_is_null and resolved_name is not None:
            if content_bearing(prestate, disposition):
                # Supplied-but-missing: content exists and did not digest, so an unknown must name it.
                observed.entry_content_null.add(resolved_name)
        if disposition is not None and not content_is_null and isinstance(content, str) and _HEX64.match(content):
            if disposition == "removed":
                assessment.note(
                    slug,
                    f"{where} records disposition 'removed' with a content_sha256; nothing remains "
                    "at a removed entry to digest, so the digest describes content this receipt says "
                    "is gone",
                )
            elif disposition == "preserved" and prestate == "absent":
                assessment.note(
                    slug,
                    f"{where} records prestate 'absent' with disposition 'preserved' and a "
                    "content_sha256; nothing was there and nothing was written, so there is no "
                    "content this digest could be of",
                )

    if not entries:
        # An empty inventory is honest for exactly one shape: a refusal that moved nothing.
        phase = field(body, "terminal_phase")
        state = field(body, "effect_state")
        if not (phase == "not-activated" and state == "none"):
            assessment.note(
                slug,
                f"{subject}'s entries list is empty while effect_state is {state!r} and "
                f"terminal_phase is {phase!r}; an empty inventory is honest only for a refusal that "
                "moved nothing, and otherwise it reads as an activation of no entries",
            )


def check_entry_mode(
    assessment: Assessment,
    entry: dict[str, Any],
    where: str,
    observed: Observed,
    disposition: str | None,
) -> None:
    """One row's publication mode: required where this run published bytes, and copy-only at project
    scope.

    THIS IS WHERE COPY-ONLY BINDS. There is no body-level `mode_policy`, deliberately: a policy field
    would be single-valued on the one variant that has a policy, `scope.kind` already identifies it,
    and the row is what actually names bytes on disk. If a second project mode is ever designed, a
    policy field returns then, with more than one admissible value.

    Null is the honest value for a row this run did not publish -- a preserved foreign collision, or
    a removed destination whose mode the retirement need not restate -- and it is REQUIRED to be
    non-null for `installed` and `refreshed`, where the run holds the mode it used and a null would
    be supplied-but-missing.
    """
    slug = "entry-inventory"
    mode = field(entry, "mode")
    if mode is ABSENT:
        return  # already reported by the closed entry key walk
    resolved: str | None = None
    if mode is None:
        if disposition in PUBLISHED_DISPOSITIONS:
            assessment.note(
                slug,
                f"{where} records disposition {disposition!r} with a null mode; this operation "
                f"published these bytes, so the mode it used is a fact it holds, and one of "
                f"{list(MODES)} is recorded rather than a hole",
            )
    elif isinstance(mode, str) and not mode:
        assessment.note(
            slug,
            f"{where} supplies mode as an empty string, which is a value supplied and lost; a row this "
            "operation did not publish records null",
        )
    elif not isinstance(mode, str) or mode not in MODES:
        assessment.note(
            slug,
            f"{where}'s mode is {mode!r}, which is not one of the closed publication modes "
            f"{list(MODES)} and not null",
        )
    else:
        resolved = mode
    if (
        observed.scope_kind == SCOPE_PROJECT
        and resolved is not None
        and resolved != PROJECT_MODE
        and disposition in PUBLISHED_DISPOSITIONS
    ):
        assessment.note(
            slug,
            f"{where} records mode {resolved!r} under a project scope; project scope is copy-only, "
            "because a committed entry must be self-contained, a link embeds a user-specific absolute "
            "path, and a later refresh must not silently change what a target's sessions execute",
        )


def check_unknowns(assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed) -> None:
    """The recorded unknowns: closed observations, each naming a checkable subject."""
    slug = "unknown-consistency"
    unknowns = field(body, "unknowns")
    if unknowns is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no unknowns; a body with nothing unknown records the empty list, "
            "which is a statement, while an absent key leaves every later admission check reading a "
            "field that is not there",
        )
        return
    if not isinstance(unknowns, list):
        assessment.note(slug, f"{subject}'s unknowns is {type(unknowns).__name__}, not a list of unknown records")
        return

    for index, record in enumerate(unknowns):
        where = f"{subject}'s unknown {index}"
        if not isinstance(record, dict):
            assessment.note(slug, f"{where} is {type(record).__name__}, not an unknown record object")
            continue
        for key in sorted(set(UNKNOWN_KEYS) - set(record)):
            assessment.note(slug, f"{where} carries no {key}, which every unknown record requires")
        for key in sorted(set(record) - set(UNKNOWN_KEYS)):
            assessment.note(
                slug,
                f"{where} carries the unknown field {key!r}; the unknown record is closed, so a field "
                "this version cannot honour is refused rather than ignored",
            )

        observation = _closed(assessment, slug, field(record, "observation"), "observation", OBSERVATIONS, where)
        detail = field(record, "detail")
        if detail is ABSENT:
            pass  # already reported by the closed-key walk above
        elif not isinstance(detail, str) or not detail:
            assessment.note(
                slug,
                f"{where}'s detail is {detail!r}; an unknown without a detail records that something "
                "could not be observed without recording what stopped it",
            )
        elif len(detail) > _MAX_DETAIL:
            assessment.note(
                slug,
                f"{where}'s detail is {len(detail)} characters, over the {_MAX_DETAIL}-character "
                "limit; a detail is one named obstacle, not a transcript",
            )

        subject_value = field(record, "subject")
        resolved_subject: str | None = None
        if observation is None or subject_value is ABSENT:
            pass
        elif observation == "entry-content":
            if not isinstance(subject_value, str) or subject_value not in observed.entry_names:
                assessment.note(
                    slug,
                    f"{where} records an entry-content unknown whose subject is {subject_value!r}, "
                    "which is not an entry_name in this inventory; an unknown that names nothing in "
                    "the document cannot be reconciled against it",
                )
            else:
                resolved_subject = subject_value
                if subject_value not in observed.entry_content_null:
                    assessment.note(
                        slug,
                        f"{where} records the content of entry {escape_display(subject_value)!r} as "
                        "unknown while the inventory records a digest for it, or records a "
                        "disposition under which it has no content; a fact and an unknown about the "
                        "same observation are a contradiction, not extra caution",
                    )
        else:
            expected = OBSERVATION_SUBJECT[observation]
            if subject_value != expected:
                assessment.note(
                    slug,
                    f"{where} records a {observation} unknown whose subject is {subject_value!r}, not "
                    f"the field it is about ({expected!r})",
                )
            elif expected == "archive_sha256" and observed.checkout_present:
                # The other direction of the checkout rule: an unknown says "this run tried to observe
                # and could not", and there was no archive to try. The body would be claiming a failed
                # observation of a file its own checkout object says never existed.
                resolved_subject = expected
                assessment.note(
                    slug,
                    f"{where} records archive_sha256 as unknown while this body carries a checkout "
                    "object; a checkout payload has no archive, so the null there is not-supplied and "
                    "naming it unknown states an observation this run never attempted",
                )
            else:
                resolved_subject = expected
                if expected not in observed.digest_null:
                    assessment.note(
                        slug,
                        f"{where} records {expected} as unknown while the body records a value for "
                        "it; a fact and an unknown about the same observation are a contradiction",
                    )

        if observation is not None and resolved_subject is not None:
            pair = (observation, resolved_subject)
            if pair in observed.unknown_index:
                assessment.note(
                    slug,
                    f"{where} repeats the unknown {observation!r} about {resolved_subject!r}; one "
                    "unobservable observation is recorded once, and two records of it are two "
                    "explanations for one gap",
                )
            else:
                observed.unknown_index.add(pair)
        if isinstance(record, dict):
            observed.unknown_records.append(record)


def check_unknown_coverage(assessment: Assessment, subject: str, observed: Observed) -> None:
    """Every null this body recorded must be NAMED as an unknown, or it is a hole.

    This is the check that reads recorded unknowns rather than recorded facts: an absent digest
    appears in no fact-only walk, so without this the body would report a gap nobody declared.

    ONE EXEMPTION, and it is a real distinction rather than a loophole. Under `effect_state: none`
    nothing was activated, so there is no archive to have digested: that null is NOT-SUPPLIED, and
    demanding an unknown for it would force every honest refusal to invent one. `candidate_id` stays
    required and non-null in that case, so a refusal still names the payload it refused.
    `journal_sha256` and `plan_sha256` are covered by the effect check, which owns their binding rule
    and would otherwise report the same defect twice.
    """
    slug = "unknown-consistency"
    if null_digest_requires_unknown(observed.effect_state):
        for key in sorted(observed.digest_null - {"journal_sha256", "plan_sha256"}):
            if key == "archive_sha256" and not archive_digest_requires_unknown(
                observed.effect_state, observed.checkout_present
            ):
                continue  # a checkout payload has no archive: that null is not-supplied
            if (_digest_observation(key), key) not in observed.unknown_index:
                assessment.note(
                    slug,
                    f"{subject} records {key} as null while its unknowns name no "
                    f"{_digest_observation(key)} for it; a value that could not be observed is "
                    "declared as an unknown, and an undeclared null is a hole a consumer would read "
                    "as a fact",
                )
    for name in sorted(observed.entry_content_null):
        if ("entry-content", name) not in observed.unknown_index:
            assessment.note(
                slug,
                f"{subject} records entry {escape_display(name)!r} with a null content_sha256 under a "
                "disposition whose content exists, while its unknowns name no entry-content for it; "
                "a digest that could not be taken is declared, never left as a hole",
            )


def _digest_observation(key: str) -> str:
    for observation, field_name in OBSERVATION_SUBJECT.items():
        if field_name == key:
            return observation
    return "entry-content"


def check_effect_and_journal(assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed) -> None:
    """Effect state, terminal phase, and the journal/plan binding, cross-checked against each other."""
    slug = "effect-and-journal"
    state = _closed(assessment, slug, field(body, "effect_state"), "effect_state", EFFECT_STATES, subject)
    phase = _closed(assessment, slug, field(body, "terminal_phase"), "terminal_phase", TERMINAL_PHASES, subject)
    observed.effect_state = state
    observed.terminal_phase = phase

    journal = _nullable_hex64(assessment, slug, field(body, "journal_sha256"), "journal_sha256", subject, observed)
    plan = _nullable_hex64(assessment, slug, field(body, "plan_sha256"), "plan_sha256", subject, observed)

    if state is not None and phase is not None:
        admitted = EFFECT_PHASES[state]
        if phase not in admitted:
            assessment.note(
                slug,
                f"{subject} records effect_state {state!r} with terminal_phase {phase!r}; that state "
                f"admits only {list(admitted)}, because an effect state and a terminal phase that "
                "disagree leave a consumer to choose which one happened",
            )
    if observed.operation is not None and phase is not None:
        admitted_phases = OPERATION_PHASES[observed.operation]
        if phase not in admitted_phases:
            assessment.note(
                slug,
                f"{subject} records operation {observed.operation!r} with terminal_phase {phase!r}; "
                f"that operation admits only {list(admitted_phases)}",
            )
    if observed.operation is not None:
        admitted_dispositions = OPERATION_DISPOSITIONS[observed.operation]
        for disposition in sorted(set(observed.dispositions) - set(admitted_dispositions)):
            assessment.note(
                slug,
                f"{subject} records operation {observed.operation!r} with an entry disposition "
                f"{disposition!r}; that operation admits only {list(admitted_dispositions)}, and a "
                "receipt recording another one describes an operation other than the one it names",
            )

    if phase == "not-activated":
        for disposition in sorted(set(observed.dispositions) - {"preserved"}):
            assessment.note(
                slug,
                f"{subject} terminates 'not-activated' while an entry records disposition "
                f"{disposition!r}; a refusal before effect moved nothing, so every entry is preserved",
            )

    # The admission checks below consult the RECORDED UNKNOWNS, not only the recorded facts.
    if state == "complete" and observed.unknown_index:
        assessment.note(
            slug,
            f"{subject} records effect_state 'complete' while naming the unknowns "
            f"{sorted(observed.unknown_index)}; an effect whose own observations could not all be "
            "made is partial or unknown, never complete, and reading only the recorded facts here "
            "would have admitted it because an unmade observation is not a fact",
        )
    if state is not None and state != "none":
        if journal is None and ("journal-digest", "journal_sha256") not in observed.unknown_index:
            assessment.note(
                slug,
                f"{subject} records effect_state {state!r} without binding a journal digest and "
                "without naming journal-digest as unknown; an admitted effect is bound to the "
                "journal that recorded it, which is the acquisition receipt's precedent",
            )
        if plan is None and ("plan-digest", "plan_sha256") not in observed.unknown_index:
            assessment.note(
                slug,
                f"{subject} records effect_state {state!r} without binding a plan digest and without "
                "naming plan-digest as unknown; the plan digest binds what was intended to what "
                "happened, and it is evidence of neither review nor approval",
            )


#: Which terminal phases each effect state admits.
EFFECT_PHASES = {
    "none": ("not-activated",),
    "complete": ("activated", "retired"),
    "partial": ("activated-partial", "unknown"),
    "unknown": ("unknown",),
}

#: Which terminal phases each operation admits. An uninstall cannot terminate `activated`, and an
#: install cannot terminate `retired`.
OPERATION_PHASES = {
    "install": ("activated", "activated-partial", "not-activated", "unknown"),
    "update": ("activated", "activated-partial", "not-activated", "unknown"),
    "uninstall": ("not-activated", "retired", "unknown"),
}


def check_channel_honesty(assessment: Assessment, body: dict[str, Any], subject: str) -> None:
    """`public_channel` is null and `release_claim` is `none`, in every document this module admits."""
    slug = "channel-honesty"
    channel = field(body, "public_channel")
    if channel is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no public_channel; the honest negative is RECORDED as null so a "
            "consumer reads it, rather than inferred from a field that is not there",
        )
    elif channel is not REQUIRED_PUBLIC_CHANNEL:
        assessment.note(
            slug,
            f"{subject} records public_channel {channel!r}; it is null until ADR-0021's evidence "
            "condition fires, and no output of this producer may state that a published release "
            "exists. Note that the STRING 'none' is a channel named 'none', not the absence of one",
        )
    claim = field(body, "release_claim")
    if claim is ABSENT:
        assessment.note(slug, f"{subject} carries no release_claim; the honest negative is recorded as 'none'")
    elif claim != REQUIRED_RELEASE_CLAIM:
        assessment.note(
            slug,
            f"{subject} records release_claim {claim!r}, not {REQUIRED_RELEASE_CLAIM!r}; until "
            "ADR-0021's evidence condition fires there is no published release for a receipt to claim",
        )


def null_digest_requires_unknown(effect_state: Any) -> bool:
    """Must a null archive, journal, or plan digest be NAMED as an unknown?

    Yes for every admitted effect, and no under `effect_state: none`, where nothing was activated and
    so there was nothing to digest: that null is not-supplied rather than supplied-but-missing. The
    one definition, read by the producer and by both checks that depend on it, because a producer that
    named an unknown the checker did not require -- or omitted one it did -- would make sealing and
    validating the same observation disagree.
    """
    return effect_state != "none"


def archive_digest_requires_unknown(effect_state: Any, checkout_present: Any) -> bool:
    """Must a null `archive_sha256` be NAMED as an unknown?

    The general rule is `null_digest_requires_unknown`, and this adds the ONE case v2 introduces: a
    checkout payload has NO ARCHIVE. That null is not-supplied in exactly the sense the general rule
    already exempts under `effect_state: none` -- there was nothing to digest -- and it is a different
    fact from supplied-but-missing, which is what an unknown records. Naming an archive-digest unknown
    on a checkout body would state that this run tried to digest an archive and failed, which is
    false; and because the family refuses `complete` beside ANY named unknown, requiring one here
    would make every clean checkout activation permanently partial and leave the pointer unmoved.

    ONE definition, read by the producer and by both checks, for the reason the general rule states:
    a producer that named an unknown the checker did not require -- or omitted one it did -- would
    make sealing and validating the same observation disagree.
    """
    if checkout_present:
        return False
    return null_digest_requires_unknown(effect_state)


def content_bearing(prestate: Any, disposition: Any) -> bool:
    """Does this entry have content a digest could be OF?

    The one definition, read by the inventory check and by the producer, because two definitions of
    "should have digested" would disagree exactly once -- on the entry nobody re-checked -- and the
    producer would then name an unknown the checker did not require, or fail to name one it did.
    """
    if disposition not in CONTENT_BEARING:
        return False  # `removed`: nothing remains to digest
    if disposition == "preserved" and prestate == "absent":
        return False  # nothing was there and nothing was written
    return True


# ---- envelope checks, re-expressed only as far as this kind needs ---------------------------------


def check_envelope(assessment: Assessment, document: dict[str, Any], subject: str) -> dict[str, Any] | None:
    """The closed envelope around this kind's body. Returns the body, or None if it is unusable.

    Deliberately NOT a reimplementation of the skills-plane checker: it stops at what this producer
    must know to write a correct document. The skills-plane tool remains the authority, and the test
    module runs it over this producer's output as an independent verifier.
    """
    slug = "closed-key-set"
    present = set(document)
    for key in sorted(set(ENVELOPE_KEYS) - present):
        assessment.note(slug, f"{subject} carries no {key}, which the closed {ENVELOPE_SCHEMA} field set requires")
    for key in sorted(present - set(ENVELOPE_KEYS)):
        assessment.note(
            slug,
            f"{subject} carries the unknown envelope field {key!r}; {ENVELOPE_SCHEMA} is closed, and a "
            "family's own payload fields belong inside body",
        )
    schema = field(document, "schema")
    if schema is not ABSENT and schema != ENVELOPE_SCHEMA:
        assessment.note(
            slug,
            f"{subject} declares schema {schema!r}, not {ENVELOPE_SCHEMA}; the payload's own version "
            "lives in body.schema_version",
        )
    kind = field(document, "receipt_kind")
    if kind is not ABSENT and kind != RECEIPT_KIND:
        assessment.note(
            slug,
            f"{subject} declares receipt_kind {kind!r}; this producer writes exactly {RECEIPT_KIND!r}, "
            "which is the lifecycle FAMILY rather than one verb of it, and the verb is body.operation",
        )
    _token(assessment, slug, field(document, "receipt_id"), "receipt_id", subject)
    _token(assessment, slug, field(document, "emitting_plane"), "emitting_plane", subject)
    stated = field(document, "stated_at")
    if stated is ABSENT:
        assessment.note(slug, f"{subject} carries no stated_at")
    elif not isinstance(stated, str) or not _TIME.match(stated):
        assessment.note(
            slug,
            f"{subject}'s stated_at is not a YYYY-MM-DDTHH:MM:SSZ instant (found {stated!r}); this "
            "module reads no clock, because this project's WSL2 host steps CLOCK_REALTIME backwards "
            "(Seed agentic-sdlc-184b) and a tool that read its own would refuse honest input at random",
        )
    body = field(document, BODY_KEY)
    if body is ABSENT:
        return None
    if not isinstance(body, dict):
        assessment.note(slug, f"{subject}'s body is {type(body).__name__}, not a {BODY_SCHEMA} object")
        return None
    return body


def check_ancestors(assessment: Assessment, document: dict[str, Any], subject: str, observed: Observed) -> None:
    """Typed ancestors, in the envelope's OWN closed relation vocabulary.

    A repeated or self-naming reference is deliberately NOT refused here: the envelope's design makes
    those graph FINDINGS reported by `check-graph`, and refusing them as a shape defect would make the
    finding unreachable. What this checks is what this FAMILY means by its references.
    """
    slug = "typed-ancestors"
    ancestors = field(document, "ancestors")
    if ancestors is ABSENT:
        assessment.note(
            slug,
            f"{subject} carries no ancestors; a receipt with no typed ancestor records the empty list, "
            "and this kind never legitimately has one",
        )
        return
    if not isinstance(ancestors, list):
        assessment.note(slug, f"{subject}'s ancestors is {type(ancestors).__name__}, not a list of references")
        return

    counts: dict[str, int] = {relation: 0 for relation in RELATIONS}
    for index, reference in enumerate(ancestors):
        where = f"{subject}'s ancestor reference {index}"
        if not isinstance(reference, dict):
            assessment.note(slug, f"{where} is {type(reference).__name__}, not a typed ancestor reference")
            continue
        for key in sorted(set(REFERENCE_KEYS) - set(reference)):
            assessment.note(slug, f"{where} carries no {key}, which every typed ancestor reference requires")
        for key in sorted(set(reference) - set(REFERENCE_KEYS)):
            assessment.note(slug, f"{where} carries the unknown field {key!r}; the reference is closed")
        _token(assessment, slug, field(reference, "receipt_id"), "receipt_id", where)
        expected = _closed(assessment, slug, field(reference, "expected_kind"), "expected_kind", RECEIPT_KINDS, where)
        relation = _closed(assessment, slug, field(reference, "relation"), "relation", RELATIONS, where)
        if relation is None:
            continue
        counts[relation] += 1
        if relation not in FAMILY_RELATIONS:
            assessment.note(
                slug,
                f"{where} holds the relation {relation!r}; a distribution activation is neither a wave "
                f"node nor an incident, so this family uses only {list(FAMILY_RELATIONS)} of the "
                "envelope's six relations",
            )
            continue
        if relation in ("derived-from", "supersedes") and expected is not None and expected != RECEIPT_KIND:
            assessment.note(
                slug,
                f"{where} holds {relation!r} with expected_kind {expected!r}; the acquisition receipt "
                f"this activation derives from and the receipt an update replaces are both "
                f"{RECEIPT_KIND!r} documents, because the kind names the lifecycle family",
            )

    check_derived_from_count(assessment, subject, observed, counts["derived-from"])
    if observed.operation == "update":
        if counts["supersedes"] != 1:
            assessment.note(
                slug,
                f"{subject} records operation 'update' with {counts['supersedes']} supersedes "
                "references; an update replaces exactly one earlier receipt and names it, because "
                "migration writes a new typed artifact and keeps the original",
            )
    elif observed.operation is not None and counts["supersedes"]:
        assessment.note(
            slug,
            f"{subject} records operation {observed.operation!r} with {counts['supersedes']} supersedes "
            "references; only an update replaces an earlier receipt, and an install or an uninstall "
            "that claimed to would retire a record it did not replace",
        )


def check_derived_from_count(
    assessment: Assessment, subject: str, observed: Observed, count: int
) -> None:
    """How many `derived-from` ancestors this body's own shape admits -- exactly, per variant.

    v1 admitted exactly one, unconditionally. v2 makes the count a CONSEQUENCE of what the body says
    it drew from, in both directions, so no combination needs a prose guard:

      * install / update with an archive: exactly one, naming the acquisition receipt.
      * install / update from a checkout: ZERO, because no acquisition receipt exists and inventing one
        would name a document no plane holds. The paired `archive_sha256` rule lives in
        `check_checkout`.
      * uninstall with `prestate_evidence: activation-receipt`: exactly one, the receipt being retired.
      * uninstall with `prestate_evidence: ledger`: ZERO, the legacy-unreceipted retirement.

    A generation this module could not resolve falls back to v1's rule, which is the stricter of the
    two and therefore the fail-closed direction.
    """
    slug = "typed-ancestors"
    generation = observed.generation
    if generation is None or not generation.is_v2:
        if count != 1:
            assessment.note(
                slug,
                f"{subject} holds {count} derived-from references; exactly one names the acquisition "
                "receipt this activation drew its payload from, and without it the activation binds a "
                "candidate no receipt in the graph accounts for",
            )
        return
    if observed.operation == "uninstall":
        if observed.prestate_evidence is None:
            return  # the closed-vocabulary check already refused the discriminator by name
        expected = PRESTATE_EVIDENCE_ANCESTORS[observed.prestate_evidence]
        if count != expected:
            assessment.note(
                slug,
                f"{subject} records prestate_evidence {observed.prestate_evidence!r} with {count} "
                f"derived-from references; that evidence admits exactly {expected}. Receipt evidence "
                "NAMES the receipt it retires, and ledger evidence names none, because a legacy "
                "unreceipted plane has no activation receipt and a fabricated ancestor would point at "
                "a document no plane holds",
            )
        return
    if observed.checkout_present:
        if count != 0:
            assessment.note(
                slug,
                f"{subject} carries a checkout object with {count} derived-from references; a checkout "
                "payload has no acquisition receipt to derive from, so the ancestor is forbidden "
                "exactly where the checkout object is present",
            )
        return
    if count != 1:
        assessment.note(
            slug,
            f"{subject} holds {count} derived-from references; exactly one names the acquisition "
            "receipt this activation drew its payload from, and without it the activation binds a "
            "candidate no receipt in the graph accounts for",
        )


# ---- the two seals -------------------------------------------------------------------------------

#: The explicit unsealed placeholder. Absent means the body never spoke about its seal, which the
#: closed key set already refuses; an empty string means "this document is unsealed, seal it".
UNSEALED = ""


def check_seal_generation(assessment: Assessment, body: dict[str, Any], subject: str) -> None:
    """`seal` writes THIS generation and no other. A v1 body is history, and history is not authored.

    v1 documents stay admissible under `validate` forever, which is the whole point of carrying two
    generations: a sealed receipt is immutable evidence, and rewriting one to a later schema would
    destroy what it proves. Sealing a NEW v1 body is a different act -- authoring history -- and it is
    refused by name, because the fields v2 requires (`scope`, per-row `mode`) were never observed by
    any run that would ask for a v1 seal.
    """
    declared = field(body, "schema_version")
    if declared == BODY_SCHEMA_V1:
        assessment.note(
            "closed-key-set",
            f"{subject} asks to seal a {BODY_SCHEMA_V1} body; that generation is admitted read-only as "
            f"history and every new seal is {BODY_SCHEMA}. A v1 receipt is never rewritten, and one is "
            "never authored either",
        )


def check_seal_placeholders(assessment: Assessment, document: dict[str, Any], body: dict[str, Any], subject: str) -> None:
    """`seal` accepts only an explicitly UNSEALED document, and never re-seals a sealed one."""
    slug = "record-seal"
    digest = field(document, CONTENT_DIGEST_KEY)
    if digest is not ABSENT and digest != UNSEALED:
        assessment.note(
            slug,
            f"{subject} already carries a content_digest ({digest!r}); seal writes the two digests "
            f"over an explicitly unsealed document whose content_digest and body.record_sha256 are "
            f"both {UNSEALED!r}, and re-sealing a sealed document would overwrite the evidence it "
            "already carries. Use validate to re-derive them",
        )
    record = field(body, RECORD_DIGEST_KEY)
    if record is ABSENT:
        assessment.note(
            slug,
            f"{subject}'s body carries no record_sha256; an unsealed body records the explicit "
            f"placeholder {UNSEALED!r} there, because seal WRITES that field and an absent key would "
            "let this producer fill a value the observation never asked it to",
        )
    elif record != UNSEALED:
        assessment.note(
            slug,
            f"{subject}'s body already carries a record_sha256 ({record!r}); an unsealed body records "
            f"{UNSEALED!r} there",
        )


def check_seals(assessment: Assessment, document: dict[str, Any], body: dict[str, Any], subject: str) -> None:
    """Both seals re-derive, or each names which one did not."""
    slug = "record-seal"
    recorded_record = field(body, RECORD_DIGEST_KEY)
    if recorded_record is ABSENT:
        pass  # already reported by the closed body key set
    elif not isinstance(recorded_record, str) or not _HEX64.match(recorded_record):
        assessment.note(
            slug,
            f"{subject}'s body record_sha256 is {recorded_record!r}, not 64 lowercase hexadecimal "
            "characters, so there is nothing to re-derive against",
        )
    else:
        derived = record_digest(body, subject)
        if derived != recorded_record:
            assessment.note(
                slug,
                f"{subject}'s body records record_sha256 {recorded_record} but its canonical bytes "
                f"minus that field seal to {derived}; the body and its own seal are a mismatched pair",
            )
    recorded_content = field(document, CONTENT_DIGEST_KEY)
    if recorded_content is ABSENT:
        pass  # already reported by the closed envelope key set
    elif not isinstance(recorded_content, str) or not _HEX64.match(recorded_content):
        assessment.note(
            slug,
            f"{subject}'s content_digest is {recorded_content!r}, not 64 lowercase hexadecimal "
            "characters, so there is nothing to re-derive against",
        )
    else:
        derived = envelope_content_digest(body, subject)
        if derived != recorded_content:
            assessment.note(
                slug,
                f"{subject} records content_digest {recorded_content} but the canonical bytes of its "
                f"body digest to {derived}; the envelope and the body are a mismatched pair",
            )


# ---- the producer --------------------------------------------------------------------------------

_DERIVED_ENTRY_DETAIL = (
    "the observation recorded this entry's content as null under a disposition whose content exists, "
    "so the digest is unknown rather than absent"
)
_DERIVED_DIGEST_DETAIL = (
    "the observation recorded this digest as null, so the value is unknown rather than absent"
)


def build_body(observation: dict[str, Any]) -> dict[str, Any]:
    """Derive the sealed body from an unsealed observation, NAMING every gap it finds on the way.

    EVERY OBSERVATION THAT CAN NAME AN UNKNOWN IS HOISTED ABOVE THE BODY LITERAL. Written the other
    way -- `{"unknowns": unknowns, "entries": [normalise(e) for e in supplied]}` -- Python evaluates
    `unknowns` into the new dict before the comprehension that appends to it runs, so every unknown
    discovered while walking the entries is dropped from the document that exists to report it. The
    body would then PASS its own unknown-consistency check, because the check reads the list that lost
    the record.

    A null the producer cannot explain is named, never filled: this module observes nothing itself, so
    it can say "unknown" and it can never say a digest.
    """
    entries_in = field(observation, "entries")
    if not isinstance(entries_in, list):
        # Not normalisable. Returned unchanged so the checks report the shape defect rather than this
        # function inventing an inventory.
        return dict(observation)

    supplied = field(observation, "unknowns")
    if not isinstance(supplied, list):
        # Also not normalisable. The closed key set refuses an absent or non-list unknowns list, and
        # inventing one here would replace that named refusal with a list this producer made up --
        # and would then let a derived unknown hide inside a field the body never declared.
        return seal_body(dict(observation))
    unknowns: list[Any] = list(supplied)
    index: set[tuple[Any, Any]] = {
        (record.get("observation"), record.get("subject")) for record in unknowns if isinstance(record, dict)
    }

    entries: list[Any] = []
    derived: list[dict[str, Any]] = []
    for entry in entries_in:
        entries.append(entry)
        if not isinstance(entry, dict):
            continue
        name = field(entry, "entry_name")
        if field(entry, "content_sha256") is not None or not isinstance(name, str):
            continue
        if not content_bearing(field(entry, "prestate"), field(entry, "disposition")):
            continue  # not-supplied, not supplied-but-missing: there is no content to digest
        if ("entry-content", name) in index:
            continue
        derived.append({"detail": _DERIVED_ENTRY_DETAIL, "observation": "entry-content", "subject": name})
        index.add(("entry-content", name))

    checkout_present = isinstance(field(observation, "checkout"), dict)
    for observation_name, key in sorted(OBSERVATION_SUBJECT.items()):
        if field(observation, key) is not None:
            continue
        if not null_digest_requires_unknown(field(observation, "effect_state")):
            continue  # nothing was activated, so there was no archive, journal, or plan to digest
        if key == "archive_sha256" and not archive_digest_requires_unknown(
            field(observation, "effect_state"), checkout_present
        ):
            continue  # a checkout payload has no archive: the null is not-supplied, not unknown
        if (observation_name, key) in index:
            continue
        derived.append({"detail": _DERIVED_DIGEST_DETAIL, "observation": observation_name, "subject": key})
        index.add((observation_name, key))

    unknowns.extend(derived)
    body = {**observation, "entries": entries, "unknowns": unknowns}
    return seal_body(body)


# ---- rendering: control characters never reach a line ---------------------------------------------


def _short(value: Any) -> str:
    if isinstance(value, str) and _HEX64.match(value):
        return value[:12]
    if value is None:
        return "unknown"
    return escape_display(str(value))


def plane_display(body: dict[str, Any]) -> str:
    """Which plane this body observed, DERIVED: `scope.agent` in v2, the `host` token in v1.

    v2 stores that fact once, in the union, so every rendering of it is derived here rather than read
    from a second field that could disagree with the first.
    """
    scope = field(body, "scope")
    if isinstance(scope, dict):
        return _short(field(scope, "agent"))
    legacy = field(body, "host")
    if legacy is not ABSENT:
        return _short(legacy)
    return "unknown"


def scope_display(body: dict[str, Any]) -> str:
    """One display string for either generation's scope, DERIVED and never stored.

    v1 stored a display token; v2 stores the union and readers derive from it. That is the point of
    deleting `activation_scope`: a stored display string beside a structured scope is a second
    spelling that can disagree with the first.
    """
    scope = field(body, "scope")
    if isinstance(scope, dict):
        kind = field(scope, "kind")
        if kind == SCOPE_PROJECT:
            root = field(scope, "root")
            return f"{_short(kind)}:{_short(root)}"
        return _short(kind)
    legacy = field(body, "activation_scope")
    if legacy is not ABSENT:
        return _short(legacy)
    return "unknown"


def render_lines(body: dict[str, Any]) -> list[str]:
    """One human-readable line per fact, with every artifact-derived string ESCAPED.

    `detail` and `entry_name` come from the field. A bare newline in one of them forges a second line
    that looks like this tool's own output, a carriage return overwrites the line already printed, and
    an escape sequence rewrites the reader's terminal. The stored values are untouched.
    """
    lines: list[str] = [
        f"{RECEIPT_KIND} {_short(field(body, 'operation'))} on "
        f"{plane_display(body)}/{scope_display(body)}"
        f" resolved {_short(field(body, 'resolved_version'))}"
        f" via {_short(field(body, 'version_source'))}"
        f" candidate {_short(field(body, 'candidate_id'))}"
        f" archive {_short(field(body, 'archive_sha256'))}",
        # A null request is "no version was requested", which is NOT the "unknown" that a null digest
        # means, so it is rendered as its own word rather than through the digest spelling.
        f"requested "
        f"{'no-version-requested' if field(body, 'requested_version') is None else _short(field(body, 'requested_version'))}"
        f" (a request is never a readback of the resolved version)",
        f"effect {_short(field(body, 'effect_state'))}"
        f" terminal {_short(field(body, 'terminal_phase'))}"
        f" journal {_short(field(body, 'journal_sha256'))}"
        f" plan {_short(field(body, 'plan_sha256'))}",
    ]
    checkout = field(body, "checkout")
    if isinstance(checkout, dict):
        # A null archive digest beside this line is NOT-SUPPLIED: there is no archive. The line says so
        # rather than leaving a reader to infer it from the "archive unknown" above.
        lines.append(
            f"checkout payload commit={_short(field(checkout, 'commit'))}"
            f" dirty={_short(field(checkout, 'dirty'))}"
            " (no archive exists, so archive_sha256 is null and not an unknown)"
        )
    evidence = field(body, "prestate_evidence")
    if evidence is not ABSENT:
        lines.append(f"prestate evidence {_short(evidence)}")
    entries = field(body, "entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            mode = field(entry, "mode")
            lines.append(
                f"entry {_short(field(entry, 'entry_name'))}"
                f" prestate={_short(field(entry, 'prestate'))}"
                f" disposition={_short(field(entry, 'disposition'))}"
                f" content={_short(field(entry, 'content_sha256'))}"
                + (
                    ""
                    if mode is ABSENT
                    else f" mode={'not-published' if mode is None else _short(mode)}"
                )
            )
    unknowns = field(body, "unknowns")
    if isinstance(unknowns, list):
        for record in unknowns:
            if not isinstance(record, dict):
                continue
            lines.append(
                f"unknown {_short(field(record, 'observation'))}"
                f" subject={_short(field(record, 'subject'))}"
                f" detail={_short(field(record, 'detail'))}"
            )
    lines.append(
        "public_channel null and release_claim none: this receipt states no published release exists"
    )
    return lines


# ---- one derivation, one verdict -----------------------------------------------------------------


def observe_before_checks(body: dict[str, Any], observed: Observed) -> None:
    """Record every explicitly null digest, and the effect state, BEFORE any check consults one.

    This exists because of the order the checks would otherwise have to run in. The unknowns check
    needs to know which digests are null (to catch a fact and an unknown claimed about the same
    observation), and the effect check needs to know which unknowns were named (to refuse
    `complete`). Each would therefore have to run first. Hoisting the observation out of both breaks
    the cycle, and it is the same discipline the producer applies to its body literal: an observation
    that a later reader depends on is made before the reader, never during it.

    It notes NO reason. Shape is the nullable-digest predicate's and the closed vocabulary's job, and a
    second opinion here would report the same defect twice. An effect state this pass cannot recognise
    is left as None, which every rule reading it treats as "an effect was admitted" -- fail closed --
    while the closed-vocabulary check refuses the value on its own account.
    """
    for key in sorted(OBSERVATION_SUBJECT.values()):
        if field(body, key) is None:
            observed.digest_null.add(key)
    state = field(body, "effect_state")
    observed.effect_state = state if isinstance(state, str) and state in EFFECT_STATES else None
    # Which generation, and whether a checkout object is PRESENT, are both pure shape questions, and
    # both are read by rules that run before the checks that validate them. Hoisting them here is the
    # same discipline the rest of this pass applies: an observation a later reader depends on is made
    # before the reader, never during it. `checkout_present` is deliberately presence-of-a-dict rather
    # than validity: a malformed checkout object still says "this body claims a checkout payload", and
    # the archive rules must fail closed on that claim rather than on its wellformedness.
    observed.generation = generation_of(body)
    observed.checkout_present = isinstance(field(body, "checkout"), dict)


def run_body_checks(assessment: Assessment, body: dict[str, Any], subject: str, observed: Observed) -> None:
    """The body's checks, in the one order their dependencies allow.

    Nulls are observed first, for the reason `observe_nulls` states. Identity runs before effect
    because the effect matrix reads the operation; the inventory runs before the unknowns because an
    entry-content unknown must name an entry; the unknowns run before the effect check because the
    admission rules there consult the RECORDED UNKNOWNS and an empty index would have admitted an
    effect nobody could fully observe; and coverage reconciles what the inventory and the unknowns
    each recorded.
    """
    observe_before_checks(body, observed)
    check_body_key_set(assessment, body, subject, observed)
    check_payload_identity(assessment, body, subject, observed)
    check_prestate_evidence(assessment, body, subject, observed)
    check_host_and_scope(assessment, body, subject, observed)
    check_entry_inventory(assessment, body, subject, observed)
    check_unknowns(assessment, body, subject, observed)
    check_unknown_coverage(assessment, subject, observed)
    check_effect_and_journal(assessment, body, subject, observed)
    check_channel_honesty(assessment, body, subject)


def derive(command: str, document: dict[str, Any], subject: str) -> dict[str, Any]:
    """Derive the one result document for one command over one supplied document."""
    assessment = Assessment()
    observed = Observed()
    body = check_envelope(assessment, document, subject)
    sealed: dict[str, Any] | None = None
    content: str | None = None

    if body is not None and command == "seal":
        check_seal_generation(assessment, body, subject)
        check_seal_placeholders(assessment, document, body, subject)
        sealed = build_body(body)
        run_body_checks(assessment, sealed, subject, observed)
        content = envelope_content_digest(sealed, subject)
    elif body is not None:
        sealed = body
        run_body_checks(assessment, body, subject, observed)
        check_seals(assessment, document, body, subject)
        recorded = field(document, CONTENT_DIGEST_KEY)
        content = recorded if isinstance(recorded, str) else None

    check_ancestors(assessment, document, subject, observed)

    verdict = assessment.verdict(command)
    receipt: dict[str, Any] | None = None
    record: str | None = None
    rendered: list[str] = []
    if verdict != VERDICT_REFUSED and sealed is not None and content is not None:
        receipt = {**document, BODY_KEY: sealed, CONTENT_DIGEST_KEY: content}
        recorded_record = field(sealed, RECORD_DIGEST_KEY)
        record = recorded_record if isinstance(recorded_record, str) else None
        rendered = render_lines(sealed)
    return {
        "body_schema": BODY_SCHEMA,
        "checks": {slug: list(assessment.groups[slug]) for slug in CHECKS},
        "command": command,
        "consequence": CONSEQUENCE[verdict],
        "content_digest": content if verdict != VERDICT_REFUSED else None,
        "reasons": assessment.reasons(),
        "record_sha256": record,
        "receipt": receipt,
        "rendered": rendered,
        "residuals": list(RESIDUALS),
        "schema": RESULT_SCHEMA,
        "verdict": verdict,
    }


def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "seal":
        return derive("seal", load_document(args.observation, "observation"), f"the observation {args.observation}")
    return derive("validate", load_document(args.receipt, "receipt"), f"the receipt {args.receipt}")


# ---- streams: a display channel costs its line, never the classified exit code --------------------


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Catching the failed write is not enough: the bytes stay PENDING in the stream's buffer and
    CPython flushes `sys.stdout`/`sys.stderr` once more while finalizing; that second failure replaces
    the process exit code with 120, which is outside this module's closed exit set. The identity check
    is load-bearing because `main` is importable: only the stream that actually failed may be dropped,
    never a caller's replacement.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Callable[[str], None]:
    """Wrap one display stream so a failed write retires the channel rather than the exit code."""
    if stream is None:  # `2>&-`: this process was handed no such stream
        return lambda line: None
    emit_to = getattr(stream, "write", None)
    if not callable(emit_to):
        return lambda line: None
    flush = getattr(stream, "flush", None)
    live = [True]

    def emit(line: str) -> None:
        if not live[0]:
            return
        try:
            emit_to(line)
            if callable(flush):
                flush()
        except (OSError, ValueError):  # EPIPE/ENOSPC, or a stream closed underneath us
            live[0] = False
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    return guarded_sink("stderr", sys.stderr)


def report_input_error(message: str) -> None:
    advisory_stderr()(f"distribution_activation_receipt.py: {message}\n")


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence: a receipt derived and not delivered is
    not a success. `canonical_bytes` is `ensure_ascii=True`, so the payload is ASCII and a text stream
    with no `.buffer` -- what an importing caller's `redirect_stdout(StringIO())` installs -- receives
    byte-identical characters rather than being made to fail.
    """
    try:
        payload = canonical_bytes(result)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defence in depth
        report_input_error(f"the derived result cannot be encoded canonically: {exc}")
        return EXIT_INTERNAL
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    emit_to: Any = None
    flush: Any = None
    body: Any = payload
    if buffer is not None and callable(getattr(buffer, "write", None)):
        emit_to, flush = buffer.write, getattr(buffer, "flush", None)
    elif stream is not None and callable(getattr(stream, "write", None)):
        emit_to, flush, body = stream.write, getattr(stream, "flush", None), payload.decode("ascii")
    if emit_to is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "result could not be delivered; nothing was sealed and nothing was validated"
        )
        return EXIT_INTERNAL
    try:
        emit_to(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        # Abandoned BEFORE returning: the classification below is worthless if the interpreter's
        # shutdown flush of the same broken stream replaces this exit code with 120.
        abandon_broken_stream("stdout", stream)
        report_input_error(
            f"cannot write the result document to stdout: {exc}; an unknown prefix of it may already "
            "have reached the consumer, so the result was derived but not delivered"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules.

    `error` writes usage through `print_usage`, which FALLS BACK TO STDOUT when `sys.stderr is None`:
    under `2>&-` a grammar error would keep exit 2 while putting usage bytes where this module's one
    result document lives.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            return
        if file is sys.stdout or file is sys.__stdout__:
            guarded_sink("stdout", file)(message)
            return
        guarded_sink("stderr", file)(message)

    def error(self, message: str) -> Any:
        note = advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_INPUT)


EPILOG = (
    "Exit codes: 0 a result was derived, a named refusal included; 2 the supplied input cannot be read "
    "as a receipt document, or the arguments themselves are unusable; 1 an unexpected internal "
    "failure, INCLUDING a stdout that cannot receive the one result document, because a receipt "
    "derived and not delivered is not a success. Implementation Decision 9's 3 and 4 do not apply: a "
    "command that causes no effect can neither refuse before one nor admit one. A sealed or validated "
    "receipt is evidence and authorizes no push, publication, merge, or deployment."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="distribution_activation_receipt.py",
        description=(
            f"Seal and validate the {BODY_SCHEMA} body carried by a {ENVELOPE_SCHEMA} receipt of kind "
            f"{RECEIPT_KIND}. Read-only, offline, subprocess-free, and effect-free: this producer "
            "observes nothing itself and authorizes nothing."
        ),
        epilog=EPILOG,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser(
        "seal",
        description=(
            "Admit an explicitly UNSEALED receipt document (content_digest and body.record_sha256 "
            "both an empty string), name every unknown its nulls imply, derive both seals over the "
            "canonical bytes, and report the complete receipt. A refused body is NOT sealed."
        ),
        epilog=EPILOG,
    )
    seal.add_argument("--observation", required=True, help="the unsealed receipt document to read")
    validate = commands.add_parser(
        "validate",
        description=(
            f"Check one sealed receipt against the closed {BODY_SCHEMA} body, every cross-field rule, "
            "and both seals. Derives nothing and repairs nothing."
        ),
        epilog=EPILOG,
    )
    validate.add_argument("--receipt", required=True, help="the sealed receipt document to read")
    args = parser.parse_args(argv)
    try:
        result = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
