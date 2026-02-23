# ── Stage 1: Build frontends ──────────────────────────────────────────
FROM oven/bun:1-alpine AS frontend-builder

WORKDIR /build

# Copy shared types/data (operator-dashboard aliases @shared → ../shared)
COPY shared/ shared/

# ── Audience Display ──
COPY audience-display/package.json audience-display/bun.lock audience-display/
RUN cd audience-display && bun install --frozen-lockfile

COPY audience-display/ audience-display/
RUN cd audience-display && bun run build

# ── Operator Dashboard ──
COPY operator-dashboard/package.json operator-dashboard/bun.lock operator-dashboard/
RUN cd operator-dashboard && bun install --frozen-lockfile

COPY operator-dashboard/ operator-dashboard/
RUN cd operator-dashboard && bun run build

# ── Stage 2: Python runtime ──────────────────────────────────────────
FROM python:3.13-slim AS python-runtime

# System dependencies for tesseract, OpenCV, PortAudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libportaudio2 \
    portaudio19-dev \
    lsof \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Non-root user (UID 1001, group root for volume write access)
RUN groupadd --gid 1001 arbiter \
    && useradd --uid 1001 --gid 1001 --create-home arbiter \
    && chown arbiter:arbiter /app \
    && mkdir -p /app/data && chown arbiter:arbiter /app/data

# ── Python dependency layer (cached across code changes) ──
COPY --chown=arbiter:arbiter pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Application code ──
COPY --chown=arbiter:arbiter src/ src/
COPY --chown=arbiter:arbiter shared/ shared/
RUN uv sync --frozen --no-dev

# ── Built frontends from stage 1 ──
COPY --from=frontend-builder --chown=arbiter:arbiter /build/audience-display/dist/ audience-display/dist/
COPY --from=frontend-builder --chown=arbiter:arbiter /build/operator-dashboard/dist/ operator-dashboard/dist/

# ── Runtime configuration ──
ENV PATH="/app/.venv/bin:$PATH" \
    DISPLAY_HOST=0.0.0.0 \
    DISPLAY_PORT=8080 \
    ARBITER_LOG_CONSOLE=true \
    ARBITER_LOG_FILE="" \
    ARBITER_LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')"

USER arbiter
EXPOSE 8080

ENTRYPOINT ["arbiter"]
CMD ["--operator", "web"]
