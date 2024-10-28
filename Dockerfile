# Use a slim Python base image for your environment
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    poppler-utils \
    git \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your requirements.txt file into the container
COPY requirements.txt .

# Install all Python dependencies at once
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    git+https://github.com/openai/swarm.git \
    git+https://github.com/HKUDS/LightRAG.git && \
    pip install gunicorn

# Copy the application code
COPY ./app ./app

# Expose the port your app runs on
EXPOSE 9000

# Consider switching to a non-root user (optional but recommended)
# RUN useradd -m myuser
# USER myuser

# Set environment variables if needed at runtime
ARG OPENAI_API_KEY
ARG APRV_AI_API_KEY
ARG GOOGLE_CLIENT_ID
ARG MONGO_URL

ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV APRV_AI_API_KEY=${APRV_AI_API_KEY}
ENV GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
ENV MONGO_URL=${MONGO_URL}

# RUN pip install -U memory_profiler


CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--reload", "-b", "0.0.0.0:9000", "app.main:app"]
# CMD to run your FastAPI app with mprof
# CMD ["mprof", "run", "--include-children", "--output", "/tmp/memory_usage.dat", "--python", "gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:9000", "--chdir", "./app", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--timeout", "240"]
# CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:9000", "--chdir", "./app", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--timeout", "240"]