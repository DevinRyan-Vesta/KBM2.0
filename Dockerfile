# syntax=docker/dockerfile:1

# Use a slim Python base image for both builder and final stages
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app


# Builder stage: install dependencies in a venv
FROM base AS builder

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements.txt first for better caching
COPY --link requirements.txt ./

# Create virtual environment and install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -r requirements.txt

# Copy the rest of the application code (excluding secrets and unnecessary files)
COPY --link . .

# Final stage: minimal runtime image
FROM base AS final

# Install git and docker CLI for system updates functionality
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and docker group for socket access
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && addgroup --gid 121 docker \
    && adduser appuser docker

WORKDIR /app

#Grant permissions to the non-root user
RUN chown -R appuser:appgroup /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code from builder
COPY --from=builder /app /app

# Copy entrypoint and make executable
COPY --from=builder /app/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown appuser:appgroup /app/entrypoint.sh

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Make Directories for Databases (both old and new paths)
RUN mkdir -p /app/KBM2_data && chown -R appuser:appgroup /app/KBM2_data
RUN mkdir -p /app/master_db && chown -R appuser:appgroup /app/master_db
RUN mkdir -p /app/tenant_dbs && chown -R appuser:appgroup /app/tenant_dbs

# Use non-root user
USER appuser

# Expose the port (assuming 8000, adjust if needed)
EXPOSE 8000

# Run migrations then start gunicorn via the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
