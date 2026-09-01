# syntax=docker/dockerfile:1
#
# Two stages: the SvelteKit interface, then the application that serves it.
#
# This image runs the server only. It does not need Docker-in-Docker or a mounted socket —
# ADR 15 (docs/adr/0015-running-code-in-a-container.md) plans a *separate* sandbox MCP server
# for v0.3 that would launch its own throwaway containers; that is a different, deferred
# concern and this Dockerfile should not grow one by accident.

FROM node:24-slim AS frontend
WORKDIR /app/apps/core/web
COPY apps/core/web/package.json apps/core/web/package-lock.json ./
RUN npm ci
COPY apps/core/web/ ./
# adapter-static (svelte.config.js) writes straight into ../src/hera_core/static — the
# directory has to exist one level up for that relative path to resolve.
RUN mkdir -p ../src/hera_core/static && npm run build

FROM python:3.12-slim AS runtime

# git: hera_profiles.mind shells out to it to manage ~/.hera/mind as a real repository.
# curl: used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/core/pyproject.toml apps/core/README.md apps/core/
COPY apps/core/src/ apps/core/src/

# The built interface, landing exactly where hera_core.app.STATIC_DIR looks for it —
# index.html being present is what turns the SPA mount on.
COPY --from=frontend /app/apps/core/src/hera_core/static/ apps/core/src/hera_core/static/

RUN uv sync --all-packages --no-dev --frozen

# The venv's own binary, not `uv run hera serve`: `uv run` re-syncs the environment against
# pyproject.toml before every invocation, which would pull the dev dependency group (mypy,
# ruff, playwright — tens of megabytes) back in at container start and undo --no-dev above.
ENV PATH="/app/.venv/bin:${PATH}"

# Self-hosted and holds a person's whole memory: apps/core/src/hera_core/settings.py defaults
# HERA_HOST to loopback on purpose, so a container has to override it explicitly rather than
# the default quietly changing underneath anyone running this outside Docker.
ENV HERA_HOST=0.0.0.0
ENV HERA_HOME=/data

EXPOSE 8756
VOLUME /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8756/api/v1/health || exit 1

# No --reload: the same command CONTRIBUTING.md tells a developer to run (modulo `uv run`,
# see above), so the container is not a second, divergent way of starting the application.
CMD ["hera", "serve"]
