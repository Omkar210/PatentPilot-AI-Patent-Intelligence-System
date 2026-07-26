# PatentMind AI — Production Dockerfile
# Serves FastAPI backend + static frontend from a single container
FROM python:3.11-slim

LABEL maintainer="Omkar210" \
      description="PatentMind AI - Enterprise Patent Intelligence Platform"

WORKDIR /app

# System dependencies for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/patentmind/

# Set Python path so imports work
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/api/system-status'); exit(0 if r.status_code == 200 else 1)"

CMD ["uvicorn", "patentmind.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
