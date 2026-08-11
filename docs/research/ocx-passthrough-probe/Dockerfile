# Clean-room probe for opencodex native Claude passthrough (the mechanism ADR-0014 adopted).
# NOT part of the bundle, NOT a gate leaf, NOT installed by any task. Throwaway harness.
#
# The point of a container here is NEGATIVE: the host carries CLAUDE_CODE_USE_BEDROCK=1,
# AWS_BEARER_TOKEN_BEDROCK, and a stored sk-ant-api key, each of which outranks subscription
# OAuth in Claude Code's credential precedence. A verified-empty environment is the only place
# the passthrough claim can be tested without a confounded result.
#
# Base image and Claude Code are pinned exactly (base by tag + digest) so this harness can be
# rebuilt byte-for-byte; RESULTS.md records the versions the measurement ran on and MUST be
# updated whenever either pin changes.
FROM node:22.23.2-bookworm-slim@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436

# ca-certificates for TLS to api.anthropic.com; iproute2+curl are the verification tools
# (a connection-level signal, since the response body cannot prove which model answered).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl iproute2 jq procps \
    && rm -rf /var/lib/apt/lists/*

# opencodex pinned to the same version the repo pins (mise.toml [tools]); Claude Code pinned to
# the exact version RESULTS.md records. opencodex's postinstall lays down a bundled bun binary
# and extracts with node zlib, so no system package is needed.
RUN npm install -g @bitkyc08/opencodex@2.11.1 @anthropic-ai/claude-code@2.1.227

# A non-root user so nothing writes into a root-owned home that the host then cannot clean up.
RUN useradd -m -u 1001 probe
USER probe
WORKDIR /home/probe

# The isolation invariant, asserted rather than assumed: an empty env block means the container
# cannot inherit a provider-routing or credential key from anywhere.
RUN mkdir -p /home/probe/.claude && printf '{"env":{}}' > /home/probe/.claude/settings.json

# 54545 is the OAuth callback port opencodex's own flow uses (src/oauth/anthropic.ts CALLBACK_PORT);
# Claude Code's own /login callback also binds a localhost port. Publish it so a browser on the
# host can complete the redirect into the container.
EXPOSE 10100 54545

CMD ["/bin/bash"]
