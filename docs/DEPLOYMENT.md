# Deployment

Marginalia can run as a no-key seed-data demo. In that mode the backend initializes SQLite, seeds example papers when the database is empty, and leaves live provider work unavailable until credentials are supplied.

## Local Production Build

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=sqlite:///./digest.db \
  ENABLE_SCHEDULER=false \
  SEED_ON_EMPTY=true \
  LLM_RUN_BUDGET_USD=0.25 \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run build
npm run preview -- --host 0.0.0.0 --port 5173
```

Open `http://localhost:5173` and confirm `http://localhost:8000/health` returns `{"status":"ok"}`.

## Docker

```bash
docker build -f backend/Dockerfile -t marginalia-api .
docker build \
  -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=http://localhost:8000 \
  -t marginalia-web .

docker run --rm -p 8000:8000 marginalia-api
docker run --rm -p 8080:8080 marginalia-web
```

The backend container defaults to ephemeral SQLite under `/tmp`, `SEED_ON_EMPTY=true`, `ENABLE_SCHEDULER=false`, and a small run budget.

## Cloud Build / Cloud Run Shape

The repository includes split image build configs:

| File | Purpose |
| --- | --- |
| `cloudbuild.backend.yaml` | Build the FastAPI backend image from `backend/Dockerfile` |
| `cloudbuild.frontend.yaml` | Build the nginx/Vite frontend image from `frontend/Dockerfile` |
| `.gcloudignore` | Exclude secrets, local databases, virtualenvs, node modules, and generated assets |

Recommended public seed-demo settings:

```txt
DATABASE_URL=sqlite:////tmp/digest.db
SEED_ON_EMPTY=true
ENABLE_SCHEDULER=false
LLM_RUN_BUDGET_USD=0.25
ADMIN_API_KEY=<set only if administrative endpoints must be exposed>
```

Set `CORS_ORIGINS` to the exact frontend origin. `VITE_API_BASE_URL` is compiled into the frontend bundle, so backend URL changes require a frontend rebuild.

## Render Blueprint

`render.yaml` remains an alternate no-key deployment path with two services:

| Service | Runtime | Purpose |
| --- | --- | --- |
| `marginalia-api` | Docker web service | FastAPI backend, health check at `/health` |
| `marginalia-web` | Static site | Vite build with SPA rewrite |

If the public repo is renamed, update Render service names and any hard-coded deployment labels in a separate deployment commit.

## Secrets

Do not put provider keys in `render.yaml`, `.env.example`, Docker build args, frontend `VITE_*` variables, screenshots, or docs.

If live summarization is needed after the seeded app is working:

1. Add the provider key through the host dashboard or secret manager.
2. Set `LLM_PROVIDER` to the provider under test.
3. Keep `LLM_RUN_BUDGET_USD=0.25` for the first run.
4. Keep `ENABLE_SCHEDULER=false` until manual runs and `/stats` accounting look correct.
5. Increase `TOP_N`, `FULL_TEXT_TOP_K`, or budget only after reviewing Status and `/stats`.
