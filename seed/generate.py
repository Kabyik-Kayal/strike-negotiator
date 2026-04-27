from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any

import httpx

from server.claude import ClaudeRateLimited, ClaudeResponseError, ClaudeUnavailable, call


PLATFORMS = [
    "swiggy",
    "zomato",
    "uber",
    "ola",
    "blinkit",
    "zepto",
    "urban company",
    "amazon flex",
]

CITIES = [
    "Bengaluru Urban",
    "Mumbai Suburban",
    "Delhi",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Kolkata",
    "Ahmedabad",
]

LANGUAGES = ["en", "hi"]

COMPLAINTS = [
    "rate cuts",
    "wrongful deactivation",
    "missing incentives",
    "insurance claim denied",
    "safety incident",
    "app glitch eating earnings",
    "longer hours for same payout",
    "surge gaming",
]

TONES = ["calm", "angry", "tired", "anxious", "confused"]
TENURES = ["six months", "two years", "four years"]

GENERATE_SCHEMA: dict[str, Any] = {"required": ["items"]}


@dataclass(frozen=True)
class Spec:
    platform: str
    city_bucket: str
    language: str
    complaint: str
    tone: str
    tenure: str
    hours: int
    earnings: int
    previous_earnings: int
    age: int


def _build_specs(count: int, rng: random.Random) -> list[Spec]:
    specs: list[Spec] = []
    for _ in range(count):
        earnings = rng.randint(12000, 42000)
        previous_earnings = earnings + rng.randint(2000, 14000)
        specs.append(
            Spec(
                platform=rng.choice(PLATFORMS),
                city_bucket=rng.choice(CITIES),
                language=rng.choice(LANGUAGES),
                complaint=rng.choice(COMPLAINTS),
                tone=rng.choice(TONES),
                tenure=rng.choice(TENURES),
                hours=rng.randint(140, 320),
                earnings=earnings,
                previous_earnings=previous_earnings,
                age=rng.randint(20, 52),
            )
        )
    return specs


def _spec_to_prompt_item(spec: Spec) -> dict[str, Any]:
    return {
        "platform": spec.platform,
        "city": spec.city_bucket,
        "language": spec.language,
        "complaint": spec.complaint,
        "tone": spec.tone,
        "tenure": spec.tenure,
        "hours": spec.hours,
        "earnings": spec.earnings,
        "previous_earnings": spec.previous_earnings,
        "age": spec.age,
    }


def _build_generation_prompt(specs: list[Spec]) -> str:
    prompt_items = [_spec_to_prompt_item(spec) for spec in specs]
    return "\n".join(
        [
            "Generate one synthetic gig-worker grievance per spec.",
            "",
            "Rules:",
            "- The voice should sound like spoken notes, with drift and repetition.",
            "- Include specific numbers from the spec naturally.",
            "- transcript must be in English.",
            "- transcript_raw should be in the requested language for that spec.",
            "- Keep each transcript around 80-150 words.",
            "- Return strict JSON only.",
            "",
            "Return shape:",
            "{",
            '  "items": [',
            "    {",
            '      "transcript": "English canonical transcript",',
            '      "transcript_raw": "Original-language transcript"',
            "    }",
            "  ]",
            "}",
            "",
            f"Specs: {json.dumps(prompt_items, ensure_ascii=True, separators=(',', ':'))}",
        ]
    )


def _template_transcript(spec: Spec) -> tuple[str, str | None]:
    english = (
        f"I work on {spec.platform} in {spec.city_bucket}. I have been on the app for {spec.tenure}. "
        f"Last month I worked about {spec.hours} hours and earned around Rs {spec.earnings}. "
        f"Earlier I could make close to Rs {spec.previous_earnings}. "
        f"My complaint is {spec.complaint}. The app keeps changing things and I cannot plan rent. "
        "I am repeating this because support tickets are ignored and payouts are not clear."
    )
    if spec.language == "en":
        return english, None

    raw = (
        f"Main {spec.city_bucket} mein {spec.platform} pe kaam karta hoon. "
        f"Maine {spec.tenure} se app chalaya hai. "
        f"Is mahine {spec.hours} ghante kaam karke lagbhag Rs {spec.earnings} aaye. "
        f"Pehle Rs {spec.previous_earnings} ke aas paas mil jata tha. "
        f"Mera issue hai {spec.complaint}. Support ticket daalte hain par jawab nahin aata."
    )
    return english, raw


def _normalize_generated_items(payload: dict[str, Any], specs: list[Spec]) -> list[dict[str, Any]]:
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(raw_items, list) or len(raw_items) != len(specs):
        raise ClaudeResponseError("Generator response does not match requested batch size.")

    normalized: list[dict[str, Any]] = []
    for raw_item, spec in zip(raw_items, specs):
        if isinstance(raw_item, dict):
            transcript = str(raw_item.get("transcript", "")).strip()
            transcript_raw = str(raw_item.get("transcript_raw", "")).strip() or None
        else:
            transcript = str(raw_item).strip()
            transcript_raw = None

        if not transcript:
            transcript, transcript_raw = _template_transcript(spec)
        elif spec.language == "en":
            transcript_raw = None
        elif not transcript_raw:
            _, transcript_raw = _template_transcript(spec)

        normalized.append(
            {
                "language": spec.language,
                "platform": spec.platform,
                "city_bucket": spec.city_bucket,
                "transcript": transcript,
                "transcript_raw": transcript_raw,
            }
        )

    return normalized


def _generate_batch(specs: list[Spec], model: str | None, offline: bool) -> list[dict[str, Any]]:
    if offline:
        return [
            {
                "language": spec.language,
                "platform": spec.platform,
                "city_bucket": spec.city_bucket,
                "transcript": _template_transcript(spec)[0],
                "transcript_raw": _template_transcript(spec)[1],
            }
            for spec in specs
        ]

    prompt = _build_generation_prompt(specs)
    payload = call(prompt, GENERATE_SCHEMA, model=model)
    return _normalize_generated_items(payload, specs)


def _post_batch(client: httpx.Client, base_url: str, items: list[dict[str, Any]], offset: int) -> None:
    for index, item in enumerate(items):
        payload = {
            "worker_secret": f"synthetic-rider-{offset + index}",
            "language": item["language"],
            "transcript": item["transcript"],
            "transcript_raw": item["transcript_raw"],
            "city_bucket": item["city_bucket"],
            "platform": item["platform"],
            "source": "synthetic",
        }
        response = client.post(f"{base_url}/ingest/text", json=payload)
        response.raise_for_status()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and ingest synthetic grievances.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--count", type=int, default=500, help="Number of grievances to generate")
    parser.add_argument("--batch-size", type=int, default=30, help="Generated grievances per model call")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed")
    parser.add_argument("--model", default=None, help="Optional Claude model override")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic templates instead of Claude calls.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.count <= 0:
        raise ValueError("count must be greater than 0")
    if args.batch_size <= 0:
        raise ValueError("batch-size must be greater than 0")

    rng = random.Random(args.seed)
    specs = _build_specs(args.count, rng)
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base_url}/health")
        health.raise_for_status()

        inserted = 0
        while inserted < len(specs):
            batch_specs = specs[inserted : inserted + args.batch_size]
            try:
                generated = _generate_batch(batch_specs, args.model, args.offline)
            except (ClaudeUnavailable, ClaudeRateLimited, ClaudeResponseError) as exc:
                if not args.offline:
                    raise RuntimeError(
                        "Claude generation failed. Rerun with --offline for deterministic fallback."
                    ) from exc
                generated = _generate_batch(batch_specs, args.model, offline=True)

            _post_batch(client, base_url, generated, inserted)
            inserted += len(generated)
            print(f"Inserted {inserted}/{len(specs)} synthetic grievances")


if __name__ == "__main__":
    main()