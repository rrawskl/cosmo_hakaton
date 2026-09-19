FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
RUN mkdir -p /app/data/runtime /app/data/private && useradd -m orbital && chown -R orbital:orbital /app
USER orbital
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn backend.app.api:app --host 0.0.0.0 --port 8000"]
