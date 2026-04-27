from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from anyio import to_thread


class TranscriptionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    transcript: str
    transcript_raw: str | None = None


def _local_whisper_model_name() -> str:
    return os.getenv("STRIKE_LOCAL_WHISPER_MODEL", "base")


_local_model_cache: dict[str, Any] = {}


def _get_local_model(model_name: str) -> Any:
    if model_name not in _local_model_cache:
        try:
            import whisper as _whisper
        except ImportError:
            raise TranscriptionUnavailable(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        _local_model_cache[model_name] = _whisper.load_model(model_name)
    return _local_model_cache[model_name]


def _transcribe_with_local_whisper(
    audio_path: Path,
    language_hint: str | None,
) -> TranscriptionResult:
    if not audio_path.exists():
        raise TranscriptionUnavailable(f"Audio file does not exist: {audio_path}")

    try:
        model_name = _local_whisper_model_name()
        model = _get_local_model(model_name)

        # Pass 1+2: transcribe in original language; local whisper detects language automatically.
        raw_result = model.transcribe(str(audio_path))
        transcript_raw = raw_result["text"].strip()
        detected_language = raw_result.get("language") or language_hint or "unknown"

        # Pass 3: translate to English when source is not English.
        if detected_language not in ("en", "english"):
            translated_result = model.transcribe(str(audio_path), task="translate")
            transcript_english = translated_result["text"].strip()
        else:
            transcript_english = transcript_raw

        return TranscriptionResult(
            language=detected_language,
            transcript=transcript_english or transcript_raw,
            transcript_raw=transcript_raw,
        )
    except TranscriptionUnavailable:
        raise
    except Exception as exc:
        raise TranscriptionUnavailable(f"Local Whisper failed for {audio_path.name}: {exc}") from exc


async def transcribe_audio(
    audio_path: Path,
    language_hint: str | None = None,
    fallback_transcript: str | None = None,
) -> TranscriptionResult:
    if fallback_transcript:
        return TranscriptionResult(
            language=language_hint or "unknown",
            transcript=fallback_transcript,
            transcript_raw=fallback_transcript,
        )

    return await to_thread.run_sync(_transcribe_with_local_whisper, audio_path, language_hint)
