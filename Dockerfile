# Use a slim Python base image for your environment
FROM python:3.11-slim

ARG OPENAI_API_KEY
ARG APRV_AI_API_KEY
ARG GOOGLE_CLIENT_ID
ARG MONGO_URL

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    pkg-config \
    poppler-utils \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your requirements.txt file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt
# RUN pip install --no-cache-dir -e ./LightRAG
# Install additional packages from Git and other specifications
RUN pip install --no-cache-dir \
    git+https://github.com/openai/swarm.git \
    git+https://github.com/KHUDS/LightRAG.git


# Install gunicorn
RUN pip install  gunicorn

# Copy the 'app' directory into the container's '/app' directory
COPY ./app ./app

# Expose the port your app runs on
EXPOSE 9000

# Set the default command to run your FastAPI app using gunicorn with uvicorn workers
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:9000", "--chdir", "./app"]
