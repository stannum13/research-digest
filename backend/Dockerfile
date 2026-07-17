FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////tmp/digest.db \
    CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:4173,http://127.0.0.1:4173,http://localhost:5173,http://127.0.0.1:5173 \
    ENABLE_SCHEDULER=false \
    SEED_ON_EMPTY=true \
    LLM_PROVIDER=zai \
    LLM_RUN_BUDGET_USD=0.25

WORKDIR /app/backend

RUN adduser --disabled-password --gecos "" appuser

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
