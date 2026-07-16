Add request-scoped feature-flag cache

Resolve feature flags once at request entry and serve every downstream read
from a request-scoped snapshot. Net effect over the branch: one flag fetch per
request instead of one per access, with a consistent snapshot across handlers.
