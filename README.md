# strike-negotiator

FastAPI + SQLite backend for the Strike Negotiator hackathon prototype.

The architecture is intentionally small: one server process, one SQLite file,
and four tables: `grievance`, `filing_chunk`, `synthesis`, and `export`.

## Backend shape

- `server/main.py` exposes the API routes.
- `server/models.py` contains the SQLAlchemy table models.
- `server/db.py` owns the SQLite engine, sessions, and schema creation.
- `server/ingest.py` hashes the worker secret before any grievance row is stored.
- `server/synthesize.py` runs the four-stage synthesis pipeline (cluster,
  quantify, cross-reference, draft) and persists export IDs into synthesis
  output JSON.
- `server/claude.py` wraps Anthropic calls with strict JSON parsing and
  retries. If keys are missing, synthesis falls back to deterministic local
  logic so tests still run offline.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:STRIKE_HASH_SALT = "replace-this-with-a-long-random-secret"
$env:ANTHROPIC_API_KEY = "your-key"  # optional for live Claude calls
uvicorn server.main:app --reload
```

`STRIKE_HASH_SALT` is required. The backend refuses to start without a
non-default value because worker phone-like secrets are HMAC-hashed at intake.

Set `ANTHROPIC_API_KEY` (or `STRIKE_ANTHROPIC_API_KEY`) to enable live Claude
calls in synthesis and seeding. Without it, the backend uses local fallbacks.

`pyproject.toml` is the dependency source of truth. `requirements.txt` is kept
for quick setup and is generated with:

```powershell
python scripts/export_requirements.py > requirements.txt
```

Then check:

```powershell
curl http://127.0.0.1:8000/health
```

## Useful endpoints

- `GET /` serves the worker voice-note form.
- `GET /dashboard` serves the organizer dashboard.
- `GET /metadata` returns the canonical city and platform lists used by the UI.
- `GET /dashboard/state` returns parsed dashboard data plus recent grievances for the current filter.
- `POST /ingest/text` stores a transcript directly. Use this for synthetic data
  and backend tests. The `source` field is required so real grievances are not
  silently mislabeled as synthetic.
- `POST /ingest` stores an audio upload and accepts `fallback_transcript` until
  the Whisper wrapper is connected.
- `GET /grievances` lists stored grievance rows.
- `POST /filing-chunks` loads public filing chunks.
- `POST /syntheses` creates a synthesis row for a filter scope.
- `POST /exports` creates a markdown export from a synthesis row.

## Seed synthetic grievances

Run the API first, then load synthetic transcripts:

```powershell
python seed/generate.py --count 500 --batch-size 30
```

For deterministic local generation without Claude:

```powershell
python seed/generate.py --count 500 --offline
```
