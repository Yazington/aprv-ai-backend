FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the app port
EXPOSE 8000
# RUN ls && sleep 5
# RUN pwd && sleep 5
# Run FastAPI app using uvicorn
CMD ["uvicorn", "main:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8000"]
