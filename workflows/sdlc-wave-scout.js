// workflow: sdlc-wave-scout
//
// Read-only wave scout: two advisory stages (cartography, then a proposed wave graph) whose
// only product is a plan a human still has to approve. It performs no fan-in, no commit, no
// push, no PR mutation, and no other outward effect, and it never renders a repository gate
// verdict. A plan this workflow emits is evidence for the conductor, never authorization.
//
// Installing this file is a byte-ownership effect only. The bundle lifecycle owns these bytes,
// their digest, and their ownership record; installing, refreshing, adopting, or uninstalling a
// workflow never runs it, never enables it, and never reloads the host. Enabling or executing
// the real Claude Code overlay stays a separately authorized user-configuration effect.
//
// The distributed bytes carry NO runtime assignment, on purpose. Provider-neutral roles in this
// bundle contain no static model or effort pin, and exact model/effort request injection is
// mandatory and immutable, so a certified `RuntimeAssignment` per stage is supplied at
// activation time by the conductor. Until then every stage refuses before dispatch, and the
// refusal is one SeedProposal rather than a host-default fallback.

const STAGES = ['cartography', 'wave-graph'];

// The conductor's certified assignments, keyed by stage name. Deliberately empty here: a
// resolved assignment names an exact provider and an exact model id, which is host-specific
// readback evidence and is never authored into distributed bytes.
const ASSIGNMENTS = {};

// A refusal has to say which of the two it is. "Not supplied" means the conductor never wrote
// an assignment for this stage; "supplied but incomplete" means one arrived and did not resolve.
// Collapsing them would let an unresolved assignment read as an absent one and hide a broken
// resolution step. Every interpolated value goes through JSON.stringify so a control character
// or quote inside a supplied string cannot forge the rest of the refusal line.
function requireResolvedAssignment(stage) {
  if (!Object.prototype.hasOwnProperty.call(ASSIGNMENTS, stage)) {
    throw new Error(
      'sdlc-wave-scout: no RuntimeAssignment was supplied for stage ' +
        JSON.stringify(stage) +
        '; stop before dispatch and return one SeedProposal'
    );
  }
  const assignment = ASSIGNMENTS[stage];
  if (assignment === null || typeof assignment !== 'object' || Array.isArray(assignment)) {
    throw new Error(
      'sdlc-wave-scout: the supplied RuntimeAssignment for stage ' +
        JSON.stringify(stage) +
        ' is not an object; stop before dispatch and return one SeedProposal'
    );
  }
  const missing = ['requested_model_id', 'requested_effort', 'resolution_state'].filter(
    (field) => typeof assignment[field] !== 'string' || assignment[field].length === 0
  );
  if (missing.length > 0) {
    throw new Error(
      'sdlc-wave-scout: the supplied RuntimeAssignment for stage ' +
        JSON.stringify(stage) +
        ' is incomplete; missing ' +
        JSON.stringify(missing) +
        '; stop before dispatch and return one SeedProposal'
    );
  }
  if (assignment.resolution_state !== 'resolved') {
    throw new Error(
      'sdlc-wave-scout: the supplied RuntimeAssignment for stage ' +
        JSON.stringify(stage) +
        ' has resolution_state ' +
        JSON.stringify(assignment.resolution_state) +
        ' rather than "resolved"; requested is not resolved, so stop before dispatch and return' +
        ' one SeedProposal'
    );
  }
  return assignment;
}

// One bounded advisory stage. The brief stays short and file-first: the worker reads the
// repository itself instead of receiving an embedded corpus.
async function scout(stage, brief) {
  const assignment = requireResolvedAssignment(stage);
  return agent(brief, {
    model: assignment.requested_model_id,
    effort: assignment.requested_effort,
  });
}

const survey = await scout(
  STAGES[0],
  'You are the cartographer for one bounded wave. Read the repository AGENTS.md router and the' +
    ' active queue, bound every search to the checkout, and reply with the smallest map a' +
    ' planner needs: owned surfaces, their gates, and the unknowns. Change nothing.'
);

const plan = await scout(
  STAGES[1],
  'You are the planner. Using this map, propose ONE bounded wave graph: nodes with declared' +
    ' inputs, outputs, authority, and stop rules, plus the gates each node must pass. Mark' +
    ' every outward effect as requiring separate operation-specific approval. Propose only;' +
    ' a human approves the graph before any wave launches.\n\nMap:\n' +
    JSON.stringify(survey)
);

// The terminal value is a proposal. The conductor records the verdict; this script does not.
return { disposition: 'proposed', stages: STAGES, survey, plan };
