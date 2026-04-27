# strike-negotiator

FastAPI + SQLite backend for the Strike Negotiator hackathon prototype.

The architecture is intentionally small: one server process, one SQLite file,
and four tables: `grievance`, `filing_chunk`, `synthesis`, and `export`.

## Backend shape

- `server/main.py` exposes the API routes.
- `server/models.py` contains the SQLAlchemy table models.
- `server/db.py` owns the SQLite engine, sessions, and schema creation.
- `server/ingest.py` hashes the worker secret before any grievance row is stored.
- `server/synthesize.py` has the storage contract for the Claude pipeline. It
  currently creates a deterministic placeholder synthesis so the dashboard can
  build against real rows while prompts are being wired in.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn server.main:app --reload
```

Then check:

```powershell
curl http://127.0.0.1:8000/health
```

## Useful endpoints

- `POST /ingest/text` stores a transcript directly. Use this for synthetic data
  and backend tests.
- `POST /ingest` stores an audio upload and accepts `fallback_transcript` until
  the Whisper wrapper is connected.
- `GET /grievances` lists stored grievance rows.
- `POST /filing-chunks` loads public filing chunks.
- `POST /syntheses` creates a synthesis row for a filter scope.
- `POST /exports` creates a markdown export from a synthesis row.
