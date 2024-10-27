# Use a slim Python base image for your environment
FROM python:3.11-slim

# Install system dependencies
# Install system dependencies
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
ARG OPENAI_API_KEY
ARG APRV_AI_API_KEY
ARG GOOGLE_CLIENT_ID
ARG MONGO_URL

# Set environment variables if needed at runtime
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV APRV_AI_API_KEY=${APRV_AI_API_KEY}
ENV GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
ENV MONGO_URL=${MONGO_URL}

# RUN echo $MONGO_URL
# RUN echo pwd
# RUN echo ls -a


# Set the default command to run your FastAPI app using gunicorn with uvicorn workers
CMD ["gunicorn", "-w", "8", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:9000", "--chdir", "./app", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--timeout", "240"]

