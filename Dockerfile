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

# Install all Python dependencies globally
RUN pip install -r requirements.txt && \
    pip install \
    git+https://github.com/openai/swarm.git \
    git+https://github.com/HKUDS/LightRAG.git && \
    pip install gunicorn memory_profiler

# Add a non-root user and change ownership of /app directory
RUN adduser --disabled-password appuser && \
    chown -R appuser:appuser /app

USER appuser

# Copy the application code
COPY ./app ./app

# Expose the port your app runs on
EXPOSE 9000

# Set environment variables if needed at runtime (removed secrets)
# You can set default values here if necessary, or omit entirely
# ENV SOME_ENV_VAR=default_value

################ PROFILING ################
# CMD ["mprof", "run", "--include-children", "--output", "/tmp/memory_usage.dat", "--python", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:9000", "app.main:app", "--timeout", "240"]
################ PROFILING ################

# Command to run your application
CMD ["sh", "-c", "chown -R appuser:appuser /app/data && gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9000 app.main:app --timeout 240"]
