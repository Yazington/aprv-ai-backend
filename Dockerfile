# Stage 1: Builder
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    poppler-utils \
    git \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt gunicorn memory_profiler

# Cleanup builder stage
RUN find /app/venv -type d -name 'tests' -exec rm -rf {} + && \
    rm -rf /app/venv/lib/python3.11/site-packages/pip

# Stage 2: Runtime
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    pkg-config \
    poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

COPY ./app ./app

EXPOSE 9000
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:9000", "app.main:app", "--timeout", "240"]