# Build production container for LabAssist AI
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for ChromaDB and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend, data, and frontend assets
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Start server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
