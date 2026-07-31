# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # produces /ui/dist

# ---- Stage 2: Python app (serves API + the built UI in one process) ----
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: curl for healthchecks. psycopg[binary] and grpcio ship wheels,
# so no compiler toolchain is required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application code.
COPY . .

# Copy the built frontend from stage 1 so FastAPI serves the UI.
COPY --from=frontend /ui/dist ./frontend/dist

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chmod +x docker/entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# $PORT is provided by the host (Render); default to 8000 for local `docker run`.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
