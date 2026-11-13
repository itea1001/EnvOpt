# The evolve box: runs Claude Code (Opus) and launches Workspace-Bench target runs
# (codex + gpt-5.4-mini) as separate containers via the mounted docker socket.
#
# We copy the docker CLI + compose plugin from the official docker:cli image (static Go
# binaries) so we don't depend on distro docker packages. The box only needs the CLIENT;
# it talks to the host docker engine through the mounted socket — no daemon here.

FROM docker:cli AS dockercli

FROM node:24-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# docker client + `docker compose` plugin (static binaries from docker:cli)
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

# the evolve agent
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /work
CMD ["/bin/bash"]
