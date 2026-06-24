## Alemeno Transaction Pipeline

FastAPI backend for asynchronous transaction CSV processing with PostgreSQL, Redis, Celery, and Gemini-based LLM enrichment.

## Features

- `POST /jobs/upload` accepts a transaction CSV, validates the required columns, creates a pending job, and enqueues processing.
- Celery worker cleans data, removes exact duplicate rows, normalizes dates/casing/amounts, detects anomalies, classifies missing categories in one batch, and stores a structured summary.
- `GET /jobs/{job_id}/status` supports polling and includes summary stats when complete.
- `GET /jobs/{job_id}/results` returns cleaned transactions, anomalies, category spend breakdown, and narrative summary.
- `GET /jobs?status=completed` lists jobs and can filter by status.

## Run

Create a `.env` file in the project root:

```env
POSTGRES_USER=alemeno
POSTGRES_PASSWORD=alemeno
POSTGRES_DB=alemeno
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
```

`GEMINI_API_KEY` is optional for local testing. If it is empty or the LLM API fails after retries, the job still completes and uncategorized rows are marked with `llm_failed=true`.

Start the full stack:

```bash
docker compose up --build
```

The API runs at `http://localhost:8000`.

## Example Requests

Upload a CSV:

```bash
curl -X POST "http://localhost:8000/jobs/upload" \
  -F "file=@transactions.csv"
```

Check job status:

```bash
curl "http://localhost:8000/jobs/<job_id>/status"
```

Fetch completed results:

```bash
curl "http://localhost:8000/jobs/<job_id>/results"
```

List jobs:

```bash
curl "http://localhost:8000/jobs"
curl "http://localhost:8000/jobs?status=completed"
```

## Data Flow

1. API receives the CSV and validates required headers.
2. A `jobs` row is inserted with `pending` status.
3. The API enqueues `app.tasks.pipeline.process_job` on Redis queue `main-queue`.
4. Celery worker consumes the job and updates status to `processing`.
5. Cleaned transactions, anomalies, LLM metadata, and job summary are persisted.
6. Worker marks the job `completed` or `failed`, and polling endpoints expose the latest state.
