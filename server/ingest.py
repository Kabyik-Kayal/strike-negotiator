from pathlib import Path
from time import time

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from server.config import get_settings
from server.ids import new_ulid
from server.models import Grievance
from server.schemas import TextIngestRequest
from server.security import hash_worker_secret
from server.transcribe import transcribe_audio


ALLOWED_AUDIO_SUFFIXES = {".aac", ".m4a", ".mp3", ".ogg", ".wav", ".webm"}


def _now_seconds() -> int:
    return int(time())


def create_text_grievance(db: Session, payload: TextIngestRequest) -> Grievance:
    grievance = Grievance(
        id=new_ulid(),
        created_at=_now_seconds(),
        source=payload.source,
        language=payload.language,
        city_bucket=payload.city_bucket,
        platform=payload.platform,
        audio_path=None,
        transcript=payload.transcript,
        transcript_raw=payload.transcript_raw,
        worker_hash=hash_worker_secret(payload.worker_secret),
    )
    db.add(grievance)
    db.commit()
    db.refresh(grievance)
    return grievance


def _safe_audio_path(grievance_id: str, filename: str | None) -> Path:
    suffix = Path(filename or "").suffix.lower() or ".ogg"
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {suffix}")
    return get_settings().audio_dir / f"{grievance_id}{suffix}"


async def save_audio_upload(grievance_id: str, audio: UploadFile) -> Path:
    settings = get_settings()
    settings.ensure_runtime_dirs()
    target_path = _safe_audio_path(grievance_id, audio.filename)
    total_bytes = 0

    with target_path.open("wb") as target:
        while chunk := await audio.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > settings.max_audio_bytes:
                target.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Audio file is too large")
            target.write(chunk)

    if total_bytes == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Audio file is empty")

    return target_path


async def create_audio_grievance(
    db: Session,
    *,
    worker_secret: str,
    audio: UploadFile,
    language_hint: str | None = None,
    city_bucket: str | None = None,
    platform: str | None = None,
    fallback_transcript: str | None = None,
) -> Grievance:
    grievance_id = new_ulid()
    audio_path = await save_audio_upload(grievance_id, audio)
    result = await transcribe_audio(audio_path, language_hint, fallback_transcript)

    grievance = Grievance(
        id=grievance_id,
        created_at=_now_seconds(),
        source="voice",
        language=result.language,
        city_bucket=city_bucket,
        platform=platform,
        audio_path=str(audio_path),
        transcript=result.transcript,
        transcript_raw=result.transcript_raw,
        worker_hash=hash_worker_secret(worker_secret),
    )
    db.add(grievance)
    db.commit()
    db.refresh(grievance)
    return grievance

