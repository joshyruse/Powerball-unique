# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (lxml builds need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install your package (src/lotto) in editable-ish mode
COPY pyproject.toml ./
COPY src ./src
RUN pip install -e .

# Copy the rest (API, scripts, data folder placeholder)
COPY api ./api
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000
# use the platform's PORT if set, else default to 8000 for local runs
CMD ["sh", "-lc", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]