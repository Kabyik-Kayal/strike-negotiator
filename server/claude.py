from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover - handled at runtime for offline fallback
    Anthropic = None


DEFAULT_MODEL = "claude-3-5-sonnet-latest"


class ClaudeUnavailable(RuntimeError):
    pass


class ClaudeRateLimited(RuntimeError):
    pass


class ClaudeResponseError(RuntimeError):
    pass


_json_fence_pattern = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL | re.IGNORECASE)
_cached_client: Any | None = None


def _api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("STRIKE_ANTHROPIC_API_KEY")


def _get_client() -> Any:
    global _cached_client
    key = _api_key()
    if not key:
        raise ClaudeUnavailable(
            "Anthropic API key is not configured. Set ANTHROPIC_API_KEY or STRIKE_ANTHROPIC_API_KEY."
        )
    if Anthropic is None:
        raise ClaudeUnavailable(
            "anthropic package is not installed. Install dependencies before running synthesis."
        )
    if _cached_client is None:
        _cached_client = Anthropic(api_key=key)
    return _cached_client


def _message_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", "") == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts).strip()


def _parse_json_payload(text: str) -> dict[str, Any]:
    candidates: list[str] = [text.strip()]
    fenced_match = _json_fence_pattern.search(text)
    if fenced_match:
        candidates.append(fenced_match.group(1).strip())

    left = text.find("{")
    right = text.rfind("}")
    if left >= 0 and right > left:
        candidates.append(text[left : right + 1])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            raise ClaudeResponseError("Claude response must be a JSON object.")
        return payload

    raise ClaudeResponseError("Claude returned invalid JSON.")


def _validate_required_keys(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [key for key in required if key not in payload]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ClaudeResponseError(f"Claude response missing required key(s): {missing_str}")


def _is_rate_limit_error(error: Exception) -> bool:
    name = error.__class__.__name__.lower()
    message = str(error).lower()
    return "ratelimit" in name or "rate limit" in message


def call(
    prompt: str,
    schema: dict[str, Any],
    *,
    model: str | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    client = _get_client()
    model_name = model or os.getenv("STRIKE_ANTHROPIC_MODEL", DEFAULT_MODEL)

    system_instructions = (
        "Return valid JSON only. Do not wrap JSON in markdown. "
        "Follow the schema exactly and do not include extra top-level fields."
    )
    if schema:
        schema_json = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        system_instructions = f"{system_instructions}\nSchema: {schema_json}"

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model=model_name,
                max_tokens=4096,
                temperature=0,
                system=system_instructions,
                messages=[{"role": "user", "content": prompt}],
            )
            payload = _parse_json_payload(_message_text(response))
            _validate_required_keys(payload, schema)
            return payload
        except ClaudeResponseError as exc:
            last_error = exc
            if attempt >= max_retries:
                raise
        except Exception as exc:  # pragma: no cover - depends on external API behavior
            if _is_rate_limit_error(exc):
                raise ClaudeRateLimited("Claude API is rate limited.") from exc
            last_error = exc
            if attempt >= max_retries:
                break

    raise ClaudeResponseError("Claude call failed after retries.") from last_error