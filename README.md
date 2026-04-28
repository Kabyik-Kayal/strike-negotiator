# Strike Negotiator

**Voice in. Cited synthesis out.**

Strike Negotiator is a voice-first grievance platform built for gig-worker organizing. Workers record a complaint in their own language — the platform transcribes it, clusters it with similar grievances, extracts numeric claims, cross-references them against company filings, and produces a cited demand list, press release, and negotiation brief for organizers.

Built for CBC Spring 2026.

---

## How it works

```
Worker records voice note
        ↓
Local Whisper transcribes + translates to English
        ↓
Four-stage Claude pipeline:
  1. Cluster   — groups grievances into themes
  2. Quantify  — extracts median numeric claims per theme
  3. Cross-ref — compares worker metrics against Swiggy/Zomato filings
  4. Draft     — writes demand list, press release, brief with citations
        ↓
Dashboard shows themes, metrics, contradictions, and export buttons
```

Every stage has a deterministic local fallback — the demo runs end-to-end even without an Anthropic API key.

---

## Stack

- **Backend** — FastAPI + SQLite (SQLAlchemy, no migrations)
- **Transcription** — `openai-whisper` running locally (base model, ffmpeg required)
- **AI pipeline** — Anthropic Claude via `anthropic` SDK, with local fallbacks
- **Frontend** — Vanilla JS + Tailwind CSS CDN + Ionicons, served as static files
- **Fonts** — Space Grotesk (headings) + Inter (body) via Google Fonts

---

## Setup

### Prerequisites

- Python 3.11+ in a conda environment (`hms`)
- [ffmpeg](https://ffmpeg.org/) installed and on PATH (required by Whisper for audio decoding)

```bash
# Install ffmpeg on Windows
winget install ffmpeg
```

### Install dependencies

```bash
conda activate hms
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `STRIKE_HASH_SALT` | Yes | Long random secret used to hash worker phone numbers |
| `ANTHROPIC_API_KEY` | No | Enables Claude-backed synthesis. Falls back to local heuristics without it. |
| `STRIKE_LOCAL_WHISPER_MODEL` | No | Whisper model size (default: `base`). Use `small` or `medium` for better accuracy. |

### Start the server

```bash
conda activate hms
uvicorn server.main:app --reload
```

The Whisper model pre-warms at startup. First boot downloads the model (~145 MB) if not cached.

Verify it's live:
```bash
curl http://127.0.0.1:8000/health
```

OpenAPI docs: `http://127.0.0.1:8000/docs`

---

## Seed data

Run these in order against a running server:

```bash
# 1. Load filing chunks from Swiggy DRHP, Zomato annual report, Zomato investor call
python -m seed.load_filings

# 2. Seed targeted grievances designed to surface contradictions against the filings
python -m seed.seed_targeted_grievances

# 3. Generate broad synthetic grievances across all cities, platforms, and complaint types
python -m seed.generate --offline        # deterministic, no API key needed
# or
python -m seed.generate                  # Claude-backed, richer output
```

---

## Demo deployment

### Local + Cloudflare Tunnel (recommended for demos)

```bash
# Terminal 1 — server
conda activate hms
uvicorn server.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — public tunnel
cloudflared tunnel --url http://localhost:8000
```

Cloudflare prints a public `https://xxxx.trycloudflare.com` URL. Share it with judges. Keep both terminals open.

**Tips:** disable laptop sleep, have a mobile hotspot ready as backup.

---

## API routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Worker intake form |
| `GET` | `/dashboard` | Organizer dashboard |
| `GET` | `/health` | Health check |
| `GET` | `/metadata` | City and platform lists |
| `GET` | `/dashboard/state` | Full dashboard payload (filters: city, platform, since, recent_limit) |
| `POST` | `/ingest/text` | Insert a text grievance |
| `POST` | `/ingest` | Upload and transcribe an audio grievance |
| `GET` | `/grievances` | List grievances |
| `GET` | `/grievances/{id}` | Get one grievance |
| `POST` | `/filing-chunks` | Create a filing chunk |
| `GET` | `/filing-chunks` | List filing chunks |
| `POST` | `/syntheses` | Run synthesis for a scope (city, platform, since) |
| `GET` | `/syntheses/latest` | Get the latest synthesis |
| `GET` | `/syntheses/{id}` | Get one synthesis |
| `POST` | `/exports` | Generate or reuse a markdown export |
| `GET` | `/exports/{id}` | Get one export |

---

## Project layout

```
server/
  main.py          FastAPI app and all routes
  models.py        SQLAlchemy models (grievance, filing_chunk, synthesis, export)
  ingest.py        Audio upload handler, worker secret hashing
  transcribe.py    Local Whisper transcription (3-pass: detect → transcribe → translate)
  synthesize.py    Four-stage pipeline with local fallbacks
  claude.py        Anthropic SDK wrapper with structured output enforcement
  prompts/         cluster.md, quantify.md, crossref.md, draft.md
frontend/
  form.html        Worker intake (audio recording, city/platform, EN/HI toggle)
  dashboard.html   Organizer dashboard (themes, metrics, contradiction, exports)
  shared.css       Shared design tokens and component styles
  utils.js         escapeHtml, relativeTime
seed/
  generate.py      Synthetic grievance generator (30-axis: city, platform, language, complaint)
  load_filings.py  Chunks and loads Swiggy/Zomato filings into filing_chunk table
  seed_targeted_grievances.py  Surgical grievances designed to trigger contradictions
  filings/raw/     Source PDFs (Swiggy DRHP 2024, Zomato annual report, investor call)
  filings/text/    Plain-text conversions used by the loader
docs/
  architecture.md  Full system spec
tests/
  test_pipeline.py    End-to-end synthesis contract (runs with local fallback, no API key)
  test_citations.py   Verifies citation IDs exist and n-counts match grievance_ids length
```

---

## Tests

```bash
conda activate hms
pytest -q
```

Both test suites run fully offline — no Anthropic API key required.

---
