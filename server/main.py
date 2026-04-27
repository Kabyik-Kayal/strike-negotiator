from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from server.constants import CITY_BUCKETS, PLATFORMS
from server.db import get_session, init_db
from server.ingest import create_audio_grievance, create_text_grievance
from server.models import Export, FilingChunk, Grievance, Synthesis
from server.schemas import (
    ExportCreate,
    ExportRead,
    FilingChunkCreate,
    FilingChunkRead,
    GrievanceRead,
    IngestResponse,
    SynthesisRead,
    SynthesisRequest,
    TextIngestRequest,
)
from server.synthesize import create_export, run_synthesis
from server.transcribe import TranscriptionUnavailable


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Strike Negotiator", version="0.1.0", lifespan=lifespan)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _scope_payload(city: str | None, platform: str | None, since: int | None) -> dict[str, str | int]:
    payload: dict[str, str | int] = {}
    if city:
        payload["city"] = city
    if platform:
        payload["platform"] = platform
    if since:
        payload["since"] = since
    return payload


def _compact_scope(scope: dict[str, str | int]) -> str:
    return json.dumps(scope, ensure_ascii=False, separators=(",", ":"))


def _preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split()).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


@app.get("/", include_in_schema=False)
def worker_form() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "form.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "dashboard.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metadata")
def metadata() -> dict[str, list[dict[str, str]]]:
    return {"cities": CITY_BUCKETS, "platforms": PLATFORMS}


@app.get("/dashboard/state")
def dashboard_state(
    db: Annotated[Session, Depends(get_session)],
    city: str | None = None,
    platform: str | None = None,
    since: int | None = None,
    recent_limit: int = 8,
) -> dict[str, object]:
    scope = _scope_payload(city, platform, since)
    grievance_stmt = select(Grievance)
    if city:
        grievance_stmt = grievance_stmt.where(Grievance.city_bucket == city)
    if platform:
        grievance_stmt = grievance_stmt.where(Grievance.platform == platform)
    if since:
        grievance_stmt = grievance_stmt.where(Grievance.created_at >= since)

    grievance_count = db.scalar(select(func.count()).select_from(grievance_stmt.subquery())) or 0
    recent_grievances = list(
        db.scalars(grievance_stmt.order_by(desc(Grievance.created_at)).limit(min(recent_limit, 24)))
    )

    synthesis_stmt = select(Synthesis)
    if scope:
        synthesis_stmt = synthesis_stmt.where(Synthesis.scope_filter == _compact_scope(scope))
    synthesis = db.scalars(synthesis_stmt.order_by(desc(Synthesis.created_at))).first()

    output = {"themes": [], "metrics": [], "findings": [], "exports": {}}
    synthesis_payload: dict[str, object] | None = None
    if synthesis is not None:
        output = json.loads(synthesis.output_json)
        synthesis_payload = {
            "id": synthesis.id,
            "created_at": synthesis.created_at,
            "scope_filter": json.loads(synthesis.scope_filter or "{}"),
            "grievance_ids": json.loads(synthesis.grievance_ids),
            "exports": output.get("exports", {}),
        }

    return {
        "metadata": {"cities": CITY_BUCKETS, "platforms": PLATFORMS},
        "scope": scope,
        "grievance_count": grievance_count,
        "recent_grievances": [
            {
                "id": grievance.id,
                "created_at": grievance.created_at,
                "source": grievance.source,
                "language": grievance.language,
                "city_bucket": grievance.city_bucket,
                "platform": grievance.platform,
                "transcript_preview": _preview(grievance.transcript),
            }
            for grievance in recent_grievances
        ],
        "synthesis": synthesis_payload,
        "output": output,
    }


@app.post("/ingest/text", response_model=IngestResponse, status_code=201)
def ingest_text(
    payload: TextIngestRequest,
    db: Annotated[Session, Depends(get_session)],
) -> IngestResponse:
    grievance = create_text_grievance(db, payload)
    return IngestResponse(id=grievance.id, status="stored")


@app.post("/ingest", response_model=IngestResponse, status_code=201)
async def ingest_audio(
    db: Annotated[Session, Depends(get_session)],
    worker_secret: Annotated[str, Form(min_length=3)],
    audio: Annotated[UploadFile, File()],
    language_hint: Annotated[str | None, Form()] = None,
    city_bucket: Annotated[str | None, Form()] = None,
    platform: Annotated[str | None, Form()] = None,
    fallback_transcript: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    try:
        grievance = await create_audio_grievance(
            db,
            worker_secret=worker_secret,
            audio=audio,
            language_hint=language_hint,
            city_bucket=city_bucket,
            platform=platform,
            fallback_transcript=fallback_transcript,
        )
    except TranscriptionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return IngestResponse(id=grievance.id, status="stored")


@app.get("/grievances", response_model=list[GrievanceRead])
def list_grievances(
    db: Annotated[Session, Depends(get_session)],
    city: str | None = None,
    platform: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[Grievance]:
    stmt = select(Grievance)
    if city:
        stmt = stmt.where(Grievance.city_bucket == city)
    if platform:
        stmt = stmt.where(Grievance.platform == platform)
    if source:
        stmt = stmt.where(Grievance.source == source)
    stmt = stmt.order_by(desc(Grievance.created_at)).limit(min(limit, 500))
    return list(db.scalars(stmt))


@app.get("/grievances/{grievance_id}", response_model=GrievanceRead)
def get_grievance(
    grievance_id: str,
    db: Annotated[Session, Depends(get_session)],
) -> Grievance:
    grievance = db.get(Grievance, grievance_id)
    if grievance is None:
        raise HTTPException(status_code=404, detail="Grievance not found")
    return grievance


@app.post("/filing-chunks", response_model=FilingChunkRead, status_code=201)
def create_filing_chunk(
    payload: FilingChunkCreate,
    db: Annotated[Session, Depends(get_session)],
) -> FilingChunk:
    existing = db.get(FilingChunk, payload.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Filing chunk already exists")

    chunk = FilingChunk(**payload.model_dump())
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


@app.get("/filing-chunks", response_model=list[FilingChunkRead])
def list_filing_chunks(
    db: Annotated[Session, Depends(get_session)],
    platform: str | None = None,
    doc_type: str | None = None,
    limit: int = 100,
) -> list[FilingChunk]:
    stmt = select(FilingChunk)
    if platform:
        stmt = stmt.where(FilingChunk.platform == platform)
    if doc_type:
        stmt = stmt.where(FilingChunk.doc_type == doc_type)
    stmt = stmt.limit(min(limit, 500))
    return list(db.scalars(stmt))


@app.post("/syntheses", response_model=SynthesisRead, status_code=201)
def create_synthesis_run(
    scope: SynthesisRequest,
    db: Annotated[Session, Depends(get_session)],
) -> Synthesis:
    return run_synthesis(db, scope)


@app.get("/syntheses/latest", response_model=SynthesisRead)
def latest_synthesis(db: Annotated[Session, Depends(get_session)]) -> Synthesis:
    synthesis = db.scalars(select(Synthesis).order_by(desc(Synthesis.created_at))).first()
    if synthesis is None:
        raise HTTPException(status_code=404, detail="No synthesis has run yet")
    return synthesis


@app.get("/syntheses/{synthesis_id}", response_model=SynthesisRead)
def get_synthesis(
    synthesis_id: str,
    db: Annotated[Session, Depends(get_session)],
) -> Synthesis:
    synthesis = db.get(Synthesis, synthesis_id)
    if synthesis is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return synthesis


@app.post("/exports", response_model=ExportRead, status_code=201)
def create_export_route(
    payload: ExportCreate,
    db: Annotated[Session, Depends(get_session)],
) -> Export:
    synthesis = db.get(Synthesis, payload.synthesis_id)
    if synthesis is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return create_export(db, synthesis, payload.kind)


@app.get("/exports/{export_id}", response_model=ExportRead)
def get_export(
    export_id: str,
    db: Annotated[Session, Depends(get_session)],
) -> Export:
    export = db.get(Export, export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return export


def run() -> None:
    import uvicorn

    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, reload=True)
