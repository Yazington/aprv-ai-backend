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
   uvicorn app.main:app --reload
   ```

## Tools

- **FastAPI**: Web framework
- **Ruff**: Linter
- **Mypy**: Type checker
- **Black**: Formatter
