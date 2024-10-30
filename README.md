# APRV AI Backend

A FastAPI project with integrated Ruff, Mypy, and Black for linting, type checking, and formatting.

## Setup

1. **Clone the repository**

2. **Create and activate the Conda environment**

   ```bash
   conda create -n aprv-ai-backend python=3.11
   conda activate aprv-ai-backend
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**

   ```bash
   uvicorn app.main:app --reload --port 9000
   ```

## Tools

- **FastAPI**: Web framework
- **Ruff**: Linter
- **Mypy**: Type checker
- **Black**: Formatter

# Commands

```
run app under docker: docker-compose up -d
get logs for app under docker: docker logs $(docker ps -a | grep aprv-ai | awk '{print $1}')
start app: uvicorn app.main:app --reload --port 9000
```

DOCKER:

```
docker build --build-arg OPENAI_API_KEY=api-key \
	     --build-arg APRV_AI_API_KEY=api-key \
	     --build-arg GOOGLE_CLIENT_ID=client-id \
	     --build-arg MONGO_URL=db-url \
	     -t my-fastapi-app .
docker run -p 9000:9000   --network=aprv-ai-local   --cpus="8"   --memory="8g"   -v /home/yaz/Workspace/aprv-ai/aprv-ai-backend/data:/app/data   my-fastapi-app
```
