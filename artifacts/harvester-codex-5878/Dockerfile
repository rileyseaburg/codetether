# Reuse the newer, prebuilt CodeTether client without rebuilding Rust or
# removing tools from the currently deployed harvester image.
FROM registry.quantum-forge.net/cluster-ci-cache/codetether-worker:4.7.5-dev.49-wrapup-devtools-f65279c7 AS client
FROM registry.quantum-forge.net/cluster-ci-cache/codetether-worker@sha256:53d24a55940738441f6ba070d2021863e7caa4d8c11a942440143b231edd2622
COPY --from=client /usr/local/bin/codetether /usr/local/bin/codetether
LABEL org.opencontainers.image.revision="f65279c7" \
      org.opencontainers.image.description="Codex client compatibility upgrade preserving deployed harvester tools"
RUN codetether --version && command -v forgejo-cli && command -v rustyroad && command -v python3