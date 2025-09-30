# Multi-stage Dockerfile for portl CLI
# Stage 1: Builder
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and use a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code
COPY pyproject.toml .
COPY src/ ./src/

# Build the package
RUN pip install .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /home/app -s /sbin/nologin app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create work directory and set ownership
RUN mkdir -p /home/app/work && chown -R app:app /home/app

# Switch to non-root user
USER app

# Set working directory
WORKDIR /home/app/work

# Set entrypoint and default command
ENTRYPOINT ["portl"]
CMD ["--help"]
