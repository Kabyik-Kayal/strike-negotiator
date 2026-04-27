from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from anyio import to_thread

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - runtime fallback when dependency is absent
    OpenAI = None


class TranscriptionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    transcript: str
    transcript_raw: str | None = None


def _whisper_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY") or os.getenv("STRIKE_OPENAI_API_KEY")


def _whisper_model() -> str:
    return os.getenv("STRIKE_WHISPER_MODEL", "whisper-1")


def _get_client() -> Any:
    api_key = _whisper_api_key()
    if not api_key:
        raise TranscriptionUnavailable(
            "No transcriber is configured. Set OPENAI_API_KEY (or STRIKE_OPENAI_API_KEY), "
            "or pass a fallback transcript in demo mode."
        )
    if OpenAI is None:
        raise TranscriptionUnavailable(
            "openai package is not installed. Install dependencies to enable Whisper transcription."
        )
    return OpenAI(api_key=api_key)


def _extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()

    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()

    if isinstance(result, dict):
        maybe_text = result.get("text")
        if isinstance(maybe_text, str):
            return maybe_text.strip()

    raise TranscriptionUnavailable("Whisper response did not include transcript text.")


def _extract_language(result: Any, language_hint: str | None) -> str:
    language = getattr(result, "language", None)
    if isinstance(language, str) and language.strip():
        return language.strip().lower()

    if isinstance(result, dict):
        maybe_language = result.get("language")
        if isinstance(maybe_language, str) and maybe_language.strip():
            return maybe_language.strip().lower()

    if language_hint and language_hint.strip():
        return language_hint.strip().lower()

    return "unknown"


def _transcribe_with_whisper(
    audio_path: Path,
    language_hint: str | None,
) -> TranscriptionResult:
    if not audio_path.exists():
        raise TranscriptionUnavailable(f"Audio file does not exist: {audio_path}")

    client = _get_client()
    model = _whisper_model()

    try:
        # Pass 1: detect language from the uploaded audio.
        with audio_path.open("rb") as audio_file:
            detection = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json",
            )
        detected_language = _extract_language(detection, language_hint)

        # Pass 2: transcribe in the detected language.
        with audio_path.open("rb") as audio_file:
            if detected_language != "unknown":
                raw_transcription = client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=detected_language,
                    response_format="json",
                )
            else:
                raw_transcription = client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    response_format="json",
                )
        transcript_raw = _extract_text(raw_transcription)

        # Pass 3: translate transcript to English for canonical pipeline input.
        with audio_path.open("rb") as audio_file:
            translated = client.audio.translations.create(
                model=model,
                file=audio_file,
                response_format="json",
            )
        transcript_english = _extract_text(translated)

        if not transcript_english:
            transcript_english = transcript_raw

        return TranscriptionResult(
            language=detected_language,
            transcript=transcript_english,
            transcript_raw=transcript_raw,
        )
    except TranscriptionUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - depends on external API behavior
        raise TranscriptionUnavailable(f"Whisper API failed for {audio_path}: {exc}") from exc


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

    return await to_thread.run_sync(_transcribe_with_whisper, audio_path, language_hint)
