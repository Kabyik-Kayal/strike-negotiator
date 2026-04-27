from dataclasses import dataclass
from pathlib import Path


class TranscriptionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    transcript: str
    transcript_raw: str | None = None


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

    raise TranscriptionUnavailable(
        f"No transcriber is configured for {audio_path}. "
        "Pass a fallback transcript in demo mode or wire this to Whisper."
    )
