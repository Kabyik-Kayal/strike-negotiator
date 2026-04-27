# strike-negotiator

FastAPI + SQLite prototype for the Strike Negotiator hackathon build.

The service is intentionally minimal: one Python process, one SQLite database,
and a small API surface that supports voice/text grievance intake, synthesis,
cross-reference against filing chunks, and markdown exports.

## What is in this repo

- `server/` API, ingestion, synthesis pipeline, data models
- `frontend/` static worker form and organizer dashboard pages
- `seed/` synthetic grievance generator/loader
- `tests/` backend, citations, and pipeline contract tests
- `docs/` architecture and team working notes

## Architecture snapshot

- Storage: SQLite with `grievance`, `filing_chunk`, `synthesis`, and `export`
  tables.
- Ingestion: stores text grievances directly and audio grievances through
  transcription wrappers.
- Synthesis: four stages run in sequence.
  - cluster themes from grievances
  - quantify numeric claims with citation IDs
  - cross-reference with filing chunks
  - draft three markdown artefacts (`demand_list`, `press_release`, `brief`)
- Privacy baseline: worker secrets are hashed before persistence; the raw secret
  is never stored.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Required
$env:STRIKE_HASH_SALT = "replace-with-a-long-random-secret"

# Optional (enables live Claude calls)
$env:ANTHROPIC_API_KEY = "your-key"

uvicorn server.main:app --reload
```

The backend auto-loads variables from repo-root `.env` at import time.
Shell-exported variables still take precedence.

Then verify:

```powershell
curl http://127.0.0.1:8000/health
```

You can also run with the project script:

```powershell
strike-server
```

## Configuration

`STRIKE_HASH_SALT` is mandatory and must not be the default placeholder value.

Environment variables:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `STRIKE_HASH_SALT` | Yes | none | HMAC-style salt used for worker secret hashing. |
| `STRIKE_DATA_DIR` | No | `<repo>/data` | Base runtime data directory. |
| `STRIKE_AUDIO_DIR` | No | `<data_dir>/audio` | Audio file storage directory. |
| `STRIKE_DB_URL` | No | `sqlite:///<data_dir>/strike.db` | SQLAlchemy database URL. |
| `STRIKE_MAX_AUDIO_BYTES` | No | `15728640` | Maximum accepted upload size for audio ingest. |
| `OPENAI_API_KEY` or `STRIKE_OPENAI_API_KEY` | No | none | Enables live Whisper audio transcription and translation. |
| `STRIKE_WHISPER_MODEL` | No | `whisper-1` | Whisper model override for transcription and translation passes. |
| `ANTHROPIC_API_KEY` or `STRIKE_ANTHROPIC_API_KEY` | No | none | Enables live Claude calls in synthesis and seeding. |
| `STRIKE_ANTHROPIC_MODEL` | No | `claude-3-5-sonnet-latest` | Claude model override. |

## API routes

UI and metadata:

- `GET /` worker voice-note page
- `GET /dashboard` organizer dashboard page
- `GET /metadata` canonical city and platform lists used by frontend
- `GET /dashboard/state` parsed dashboard data plus recent grievances for the current filter
- `GET /health` health check

Core workflow:

- `POST /ingest/text` insert a grievance from transcript text
- `POST /ingest` insert a grievance from uploaded audio
  - runs a three-pass Whisper flow when OpenAI key is configured
  - pass 1: language detection
  - pass 2: transcript in detected language (stored as `transcript_raw`)
  - pass 3: English translation (stored as canonical `transcript`)
  - `fallback_transcript` still works for demo/offline mode
- `GET /grievances` list grievances with optional `city`, `platform`, `source`, `limit`
- `GET /grievances/{grievance_id}` retrieve one grievance
- `POST /filing-chunks` create filing chunk
- `GET /filing-chunks` list filing chunks with optional filters
- `POST /syntheses` run a synthesis for `{city, platform, since}` scope
- `GET /syntheses/latest` latest synthesis row
- `GET /syntheses/{synthesis_id}` retrieve one synthesis row
- `POST /exports` create/get export from synthesis (`press_release`, `demand_list`, `brief`)
- `GET /exports/{export_id}` retrieve one export row

OpenAPI docs are available at `/docs` when the server is running.

## Synthesis behavior

`server/synthesize.py` uses prompt templates in `server/prompts/` and the
Anthropic wrapper in `server/claude.py`.

If a Claude key is present, the pipeline attempts model-backed stages with
strict JSON contracts. If Claude is unavailable, rate-limited, or returns bad
JSON, the code falls back to deterministic local logic so the app remains
functional and tests remain offline-safe.

Guardrails enforced in code:

- metrics are dropped unless `n == len(grievance_ids)`
- filing excerpts are capped to 10 words
- source footer lists grievance IDs and filing chunk IDs with truncation

## Seed synthetic grievances

Run the API first, then seed:

```powershell
python seed/generate.py --count 500 --batch-size 30
```

Useful options:

- `--offline` deterministic local text generation (no Claude)
- `--seed <int>` repeatable synthetic dataset
- `--model <name>` override Claude model
- `--base-url <url>` target a non-default API host

Example offline run:

```powershell
python seed/generate.py --count 500 --batch-size 30 --offline
```

## Run tests

```powershell
pytest -q
```

Current suite covers hashing/privacy, frontend routes and metadata, citation
integrity, export source formatting, and end-to-end synthesis contract behavior.

## Dependency source of truth

`pyproject.toml` is authoritative.

`requirements.txt` is generated with:

```powershell
python scripts/export_requirements.py > requirements.txt
```
