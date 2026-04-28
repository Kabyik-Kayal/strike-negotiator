from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import median
from time import time
from typing import Any, Iterable

from sqlalchemy import Select, desc, or_, select
from sqlalchemy.orm import Session

from server.claude import ClaudeRateLimited, ClaudeResponseError, ClaudeUnavailable, call
from server.ids import new_ulid
from server.models import Export, FilingChunk, Grievance, Synthesis
from server.schemas import ExportKind, SynthesisRequest


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
VERDICTS = {"contradiction", "support", "silence"}
THEME_MIN_SUPPORT = 5

CLUSTER_SCHEMA: dict[str, Any] = {"required": ["themes"]}
QUANTIFY_SCHEMA: dict[str, Any] = {"required": ["metrics"]}
CROSSREF_SCHEMA: dict[str, Any] = {"required": ["findings"]}
DRAFT_SCHEMA: dict[str, Any] = {"required": ["demand_list", "press_release", "brief"]}

THEME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "Per-order rate cuts since March 2026",
        ("rate cut", "rate reduced", "payout cut", "per-order", "per order", "fare cut"),
    ),
    (
        "Wrongful deactivations without due process",
        ("deactivation", "de-activation", "blocked account", "suspended", "id blocked"),
    ),
    (
        "Missing incentives despite completed targets",
        ("missing incentive", "incentive not", "bonus not", "target complete", "no incentive"),
    ),
    (
        "Insurance claims denied after incidents",
        ("insurance", "claim denied", "claim reject", "hospital", "accident"),
    ),
    (
        "Safety incidents with weak support response",
        ("safety", "harassed", "threat", "assault", "unsafe", "night shift"),
    ),
    (
        "App glitches reducing recorded earnings",
        ("app glitch", "app bug", "trip missing", "order missing", "earnings missing", "crash"),
    ),
    (
        "Longer hours for the same payout",
        ("long hours", "more hours", "same payout", "same earning", "longer shift"),
    ),
    (
        "Surge pricing manipulation concerns",
        ("surge", "peak bonus", "dynamic pricing", "multiplier", "surge shown"),
    ),
]

# Matches an optional leading minus sign followed by an integer or decimal number.
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@lru_cache(maxsize=16)
def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _render_prompt(name: str, replacements: dict[str, str]) -> str:
    prompt = _load_prompt(name)
    for key, value in replacements.items():
        prompt = prompt.replace(f"<<{key}>>", value)
    return prompt


def _format_source_ids(grievance_ids: list[str], limit: int = 20) -> str:
    if not grievance_ids:
        return "No grievance IDs yet."

    visible_ids = grievance_ids[:limit]
    footer = ", ".join(visible_ids)
    remaining = len(grievance_ids) - len(visible_ids)
    if remaining:
        footer = f"{footer}, and {remaining} more"
    return footer


def _format_filing_ids(filing_ids: list[str], limit: int = 20) -> str:
    if not filing_ids:
        return "No filing chunk IDs yet."

    visible_ids = filing_ids[:limit]
    footer = ", ".join(visible_ids)
    remaining = len(filing_ids) - len(visible_ids)
    if remaining:
        footer = f"{footer}, and {remaining} more"
    return footer


def _source_footer_lines(grievance_ids: list[str], filing_ids: list[str]) -> list[str]:
    return [
        "## Sources",
        "",
        "### Grievance IDs",
        _format_source_ids(grievance_ids),
        "",
        "### Filing chunk IDs",
        _format_filing_ids(filing_ids),
    ]


def _scoped_grievance_query(scope: SynthesisRequest) -> Select[tuple[Grievance]]:
    stmt = select(Grievance)
    if scope.city:
        stmt = stmt.where(Grievance.city_bucket == scope.city)
    if scope.platform:
        stmt = stmt.where(Grievance.platform == scope.platform)
    if scope.since:
        stmt = stmt.where(Grievance.created_at >= scope.since)
    return stmt.order_by(desc(Grievance.created_at)).limit(500)


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _slugify(label: str) -> str:
    slug = SLUG_PATTERN.sub("-", label.lower()).strip("-")
    return slug[:64] or "theme"


def _unique_slug(base_slug: str, seen: set[str]) -> str:
    slug = base_slug or "theme"
    if slug not in seen:
        seen.add(slug)
        return slug
    index = 2
    while f"{slug}-{index}" in seen:
        index += 1
    final_slug = f"{slug}-{index}"
    seen.add(final_slug)
    return final_slug


def _theme_label_from_transcript(transcript: str) -> str:
    lowered = transcript.lower()
    for label, keywords in THEME_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return label
    return "Other unresolved grievances"


def _trim_quote(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split()).strip()
    return cleaned[:limit]


def _cluster_locally(grievances: list[Grievance]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Grievance]] = defaultdict(list)
    for grievance in grievances:
        grouped[_theme_label_from_transcript(grievance.transcript)].append(grievance)

    themes: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for label, rows in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        if len(rows) < THEME_MIN_SUPPORT:
            continue
        grievance_ids = [row.id for row in rows]
        quotes = [_trim_quote(row.transcript) for row in rows if row.transcript.strip()][:3]
        themes.append(
            {
                "id": _unique_slug(_slugify(label), seen_slugs),
                "label": label,
                "count": len(grievance_ids),
                "grievance_ids": grievance_ids,
                "quotes": quotes,
            }
        )
    return themes


def _normalize_themes(payload: dict[str, Any], grievances: list[Grievance]) -> list[dict[str, Any]]:
    grievance_by_id = {grievance.id: grievance for grievance in grievances}
    valid_ids = set(grievance_by_id)
    raw_themes = payload.get("themes", []) if isinstance(payload, dict) else []
    if not isinstance(raw_themes, list):
        return []

    themes: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for raw_theme in raw_themes:
        if not isinstance(raw_theme, dict):
            continue

        label = str(raw_theme.get("label", "")).strip()
        if not label:
            continue

        raw_ids = raw_theme.get("grievance_ids", [])
        if not isinstance(raw_ids, list):
            continue

        grievance_ids = _dedupe([str(grievance_id) for grievance_id in raw_ids if grievance_id in valid_ids])
        if len(grievance_ids) < THEME_MIN_SUPPORT:
            continue

        raw_quotes = raw_theme.get("quotes", [])
        quotes: list[str] = []
        if isinstance(raw_quotes, list):
            quotes = [_trim_quote(str(quote)) for quote in raw_quotes if str(quote).strip()][:3]
        if not quotes:
            quotes = [_trim_quote(grievance_by_id[grievance_id].transcript) for grievance_id in grievance_ids[:3]]

        candidate_id = str(raw_theme.get("id", "")).strip() or _slugify(label)
        themes.append(
            {
                "id": _unique_slug(_slugify(candidate_id), seen_slugs),
                "label": label,
                "count": len(grievance_ids),
                "grievance_ids": grievance_ids,
                "quotes": quotes,
            }
        )

    themes.sort(key=lambda theme: theme["count"], reverse=True)
    return themes


def _run_cluster_stage(grievances: list[Grievance]) -> list[dict[str, Any]]:
    if not grievances:
        return []

    grievances_json = _compact_json(
        [{"id": grievance.id, "transcript": grievance.transcript} for grievance in grievances]
    )
    prompt = _render_prompt("cluster.md", {"GRIEVANCES_JSON": grievances_json})

    try:
        payload = call(prompt, CLUSTER_SCHEMA)
        themes = _normalize_themes(payload, grievances)
        if themes:
            return themes
    except (ClaudeUnavailable, ClaudeRateLimited, ClaudeResponseError):
        pass

    return _cluster_locally(grievances)


def _extract_numeric_claim(transcript: str) -> float | None:
    lowered = transcript.lower()

    percent_match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", lowered)
    if percent_match:
        return float(percent_match.group(1))

    currency_match = re.search(r"(?:rs\.?|inr|rupees?)\s*(-?\d+(?:\.\d+)?)", lowered)
    if currency_match:
        return float(currency_match.group(1))

    hours_match = re.search(r"(-?\d+(?:\.\d+)?)\s*hours?", lowered)
    if hours_match:
        return float(hours_match.group(1))

    for raw_number in NUMBER_PATTERN.findall(lowered):
        value = float(raw_number)
        if 1900 <= value <= 2100:
            continue
        return value

    return None


def _format_metric_value(values: list[float]) -> str:
    low = min(values)
    high = max(values)
    middle = median(values)
    if low == high:
        return f"{middle:g}"
    return f"{middle:g} (range {low:g} to {high:g})"


def _quantify_locally(
    themes: list[dict[str, Any]],
    grievance_by_id: dict[str, Grievance],
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for theme in themes:
        values: list[float] = []
        cited_ids: list[str] = []
        for grievance_id in theme["grievance_ids"]:
            grievance = grievance_by_id.get(grievance_id)
            if grievance is None:
                continue
            value = _extract_numeric_claim(grievance.transcript)
            if value is None:
                continue
            values.append(value)
            cited_ids.append(grievance_id)

        if not cited_ids:
            continue

        metrics.append(
            {
                "theme_id": theme["id"],
                "name": "median reported numeric claim",
                "value": _format_metric_value(values),
                "n": len(cited_ids),
                "method": "median of first numeric claim per cited grievance transcript",
                "grievance_ids": cited_ids,
            }
        )
    return metrics


def _normalize_metrics(
    payload: dict[str, Any],
    themes: list[dict[str, Any]],
    grievance_by_id: dict[str, Grievance],
) -> list[dict[str, Any]]:
    theme_ids = {theme["id"] for theme in themes}
    valid_ids = set(grievance_by_id)

    raw_metrics = payload.get("metrics", []) if isinstance(payload, dict) else []
    if not isinstance(raw_metrics, list):
        return []

    metrics: list[dict[str, Any]] = []
    for raw_metric in raw_metrics:
        if not isinstance(raw_metric, dict):
            continue

        theme_id = str(raw_metric.get("theme_id", "")).strip()
        if theme_id not in theme_ids:
            continue

        name = str(raw_metric.get("name", "")).strip()
        value = str(raw_metric.get("value", "")).strip()
        method = str(raw_metric.get("method", "")).strip() or "Unspecified method."
        if not name or not value:
            continue

        raw_ids = raw_metric.get("grievance_ids", [])
        if not isinstance(raw_ids, list):
            continue

        grievance_ids = _dedupe([str(grievance_id) for grievance_id in raw_ids if grievance_id in valid_ids])
        if not grievance_ids:
            continue

        try:
            n_value = int(raw_metric.get("n", len(grievance_ids)))
        except (TypeError, ValueError):
            continue

        if n_value != len(grievance_ids):
            continue

        metrics.append(
            {
                "theme_id": theme_id,
                "name": name,
                "value": value,
                "n": n_value,
                "method": method,
                "grievance_ids": grievance_ids,
            }
        )
    return metrics


def _run_quantify_stage(
    themes: list[dict[str, Any]],
    grievances: list[Grievance],
    grievance_by_id: dict[str, Grievance],
) -> list[dict[str, Any]]:
    if not themes:
        return []

    themes_json = _compact_json(themes)
    grievances_json = _compact_json(
        [{"id": grievance.id, "transcript": grievance.transcript} for grievance in grievances]
    )
    prompt = _render_prompt(
        "quantify.md",
        {
            "THEMES_JSON": themes_json,
            "GRIEVANCES_JSON": grievances_json,
        },
    )

    try:
        payload = call(prompt, QUANTIFY_SCHEMA)
        metrics = _normalize_metrics(payload, themes, grievance_by_id)
        if metrics:
            return metrics
    except (ClaudeUnavailable, ClaudeRateLimited, ClaudeResponseError):
        pass

    return _quantify_locally(themes, grievance_by_id)


def _derive_keywords(theme_label: str) -> list[str]:
    tokens = set(re.findall(r"[a-z]{4,}", theme_label.lower()))
    if {"rate", "payout", "earning", "earnings"} & tokens:
        tokens.update({"rate", "earnings", "partner", "payout", "incentive"})
    if {"deactivation", "suspend", "blocked"} & tokens:
        tokens.update({"deactivation", "suspended", "account", "partner"})
    if {"safety", "incident", "unsafe"} & tokens:
        tokens.update({"safety", "incident", "support", "helpline"})
    if {"insurance", "claim"} & tokens:
        tokens.update({"insurance", "claim", "coverage"})
    if not tokens:
        tokens = {"partner", "earnings"}
    return sorted(tokens)[:10]


def _retrieve_chunks(
    db: Session,
    *,
    theme_label: str,
    platform: str | None,
    limit: int = 10,
) -> list[FilingChunk]:
    if not platform:
        return []

    keyword_filters = [FilingChunk.text.ilike(f"%{keyword}%") for keyword in _derive_keywords(theme_label)]
    stmt = (
        select(FilingChunk)
        .where(FilingChunk.platform == platform)
        .where(or_(*keyword_filters))
        .limit(limit)
    )
    return list(db.scalars(stmt))


def _theme_platform(
    theme: dict[str, Any],
    grievance_by_id: dict[str, Grievance],
    default_platform: str | None,
) -> str | None:
    platforms: list[str] = []
    for grievance_id in theme.get("grievance_ids", []):
        grievance = grievance_by_id.get(grievance_id)
        if grievance and grievance.platform:
            platforms.append(grievance.platform)
    if not platforms:
        return default_platform
    return Counter(platforms).most_common(1)[0][0]


def _metric_summary(metrics: list[dict[str, Any]]) -> str:
    if not metrics:
        return "No quantified metric available."
    top_metric = metrics[0]
    return f"{top_metric['name']}: {top_metric['value']}"


def _truncate_words(text: str, max_words: int = 10) -> str:
    words = text.split()
    return " ".join(words[:max_words])


def _infer_verdict(worker_metric: str, filing_text: str) -> str:
    worker = worker_metric.lower()
    filing = filing_text.lower()

    worker_down = any(token in worker for token in ("drop", "down", "cut", "reduced", "decline", "-"))
    worker_up = any(token in worker for token in ("up", "increase", "grew", "growth"))
    filing_up = any(token in filing for token in ("up", "increase", "increased", "grew", "growth"))
    filing_down = any(token in filing for token in ("down", "decline", "decrease", "reduced"))

    if worker_down and filing_up:
        return "contradiction"
    if worker_up and filing_up:
        return "support"
    if worker_down and filing_down:
        return "support"
    return "silence"


def _crossref_locally(
    db: Session,
    themes: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    grievance_by_id: dict[str, Grievance],
    default_platform: str | None,
) -> list[dict[str, Any]]:
    metrics_by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metric in metrics:
        metrics_by_theme[metric["theme_id"]].append(metric)

    findings: list[dict[str, Any]] = []
    for theme in themes:
        platform = _theme_platform(theme, grievance_by_id, default_platform)
        chunks = _retrieve_chunks(db, theme_label=theme["label"], platform=platform)
        worker_metric = _metric_summary(metrics_by_theme.get(theme["id"], []))
        if not chunks:
            findings.append(
                {
                    "theme_id": theme["id"],
                    "verdict": "silence",
                    "filing_chunk_id": "none",
                    "filing_excerpt": "",
                    "worker_metric": worker_metric,
                    "summary": "No matching filing chunk was retrieved for this worker claim.",
                }
            )
            continue

        chunk = chunks[0]
        verdict = _infer_verdict(worker_metric, chunk.text)
        findings.append(
            {
                "theme_id": theme["id"],
                "verdict": verdict,
                "filing_chunk_id": chunk.id,
                "filing_excerpt": _truncate_words(" ".join(chunk.text.split()), 10),
                "worker_metric": worker_metric,
                "summary": f"{theme['label']}: filing passage evaluated as {verdict}.",
            }
        )

    return findings


def _normalize_findings(
    payload: dict[str, Any],
    themes: list[dict[str, Any]],
    metrics_by_theme: dict[str, list[dict[str, Any]]],
    valid_chunk_ids: set[str],
) -> list[dict[str, Any]]:
    theme_ids = {theme["id"] for theme in themes}
    raw_findings = payload.get("findings", []) if isinstance(payload, dict) else []
    if not isinstance(raw_findings, list):
        return []

    findings: list[dict[str, Any]] = []
    seen_themes: set[str] = set()
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            continue

        theme_id = str(raw_finding.get("theme_id", "")).strip()
        if theme_id not in theme_ids or theme_id in seen_themes:
            continue

        verdict = str(raw_finding.get("verdict", "silence")).strip().lower()
        if verdict not in VERDICTS:
            verdict = "silence"

        filing_chunk_id = str(raw_finding.get("filing_chunk_id", "")).strip()
        if filing_chunk_id not in valid_chunk_ids:
            filing_chunk_id = "none"

        filing_excerpt = _truncate_words(str(raw_finding.get("filing_excerpt", "")).strip(), 10)
        worker_metric = str(raw_finding.get("worker_metric", "")).strip() or _metric_summary(
            metrics_by_theme.get(theme_id, [])
        )
        summary = str(raw_finding.get("summary", "")).strip() or "No filing contradiction could be established."

        findings.append(
            {
                "theme_id": theme_id,
                "verdict": verdict,
                "filing_chunk_id": filing_chunk_id,
                "filing_excerpt": filing_excerpt,
                "worker_metric": worker_metric,
                "summary": summary,
            }
        )
        seen_themes.add(theme_id)

    return findings


def _run_crossref_stage(
    db: Session,
    themes: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    grievance_by_id: dict[str, Grievance],
    default_platform: str | None,
) -> list[dict[str, Any]]:
    if not themes:
        return []

    metrics_by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metric in metrics:
        metrics_by_theme[metric["theme_id"]].append(metric)

    theme_packets: list[dict[str, Any]] = []
    known_chunk_ids: set[str] = set()

    for theme in themes:
        platform = _theme_platform(theme, grievance_by_id, default_platform)
        chunks = _retrieve_chunks(db, theme_label=theme["label"], platform=platform)
        known_chunk_ids.update(chunk.id for chunk in chunks)
        theme_packets.append(
            {
                "theme_id": theme["id"],
                "theme_label": theme["label"],
                "platform": platform,
                "worker_metrics": metrics_by_theme.get(theme["id"], []),
                "filing_chunks": [
                    {
                        "id": chunk.id,
                        "doc_type": chunk.doc_type,
                        "doc_date": chunk.doc_date,
                        "page": chunk.page,
                        "text": chunk.text,
                    }
                    for chunk in chunks
                ],
            }
        )

    prompt = _render_prompt(
        "crossref.md",
        {"THEME_PACKETS_JSON": _compact_json(theme_packets)},
    )

    try:
        payload = call(prompt, CROSSREF_SCHEMA)
        findings = _normalize_findings(payload, themes, metrics_by_theme, known_chunk_ids)
        if findings:
            return findings
    except (ClaudeUnavailable, ClaudeRateLimited, ClaudeResponseError):
        pass

    return _crossref_locally(db, themes, metrics, grievance_by_id, default_platform)


def _collect_filing_ids(findings: list[dict[str, Any]]) -> list[str]:
    return _dedupe(
        [
            str(finding.get("filing_chunk_id", ""))
            for finding in findings
            if str(finding.get("filing_chunk_id", "")).strip() not in {"", "none"}
        ]
    )


def _build_local_drafts(
    themes: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    grievance_ids: list[str],
    filing_ids: list[str],
) -> dict[str, str]:
    ranked_themes = sorted(themes, key=lambda item: item["count"], reverse=True)
    contradiction = next((finding for finding in findings if finding["verdict"] == "contradiction"), None)

    demand_lines = ["# Demand List", "", "## Prioritized demands"]
    ranked_index = 1
    for theme in ranked_themes:
        count = theme["count"]
        if count < 20:
            continue
        emerging = " (emerging)" if 20 <= count <= 30 else ""
        demand_lines.append(f"{ranked_index}. {theme['label']} ({count} supporters){emerging}")
        ranked_index += 1
    if ranked_index == 1:
        demand_lines.append("No demand has at least 20 supporters in this filter yet.")
    demand_lines.extend(["", *_source_footer_lines(grievance_ids, filing_ids)])

    press_lines = ["# Press Release", ""]
    if contradiction:
        press_lines.append(f"Workers report: {contradiction['worker_metric']}.")
        press_lines.append(f"Public filing says: {contradiction['filing_excerpt']}.")
        press_lines.append(contradiction["summary"])
    elif ranked_themes:
        top_theme = ranked_themes[0]
        press_lines.append(
            f"Workers from this scope report {top_theme['label'].lower()} with {top_theme['count']} supporting grievances."
        )
    else:
        press_lines.append("No grievances matched the selected filter yet.")
    press_lines.append("")
    press_lines.append("Requested actions:")
    for theme in ranked_themes[:3]:
        press_lines.append(f"- Address {theme['label'].lower()} immediately.")
    if not ranked_themes:
        press_lines.append("- Collect additional verified grievances from workers.")
    press_lines.extend(["", *_source_footer_lines(grievance_ids, filing_ids)])

    brief_lines = [
        "# Negotiation Brief",
        "",
        "## What workers are saying",
    ]
    if ranked_themes:
        for theme in ranked_themes[:5]:
            brief_lines.append(f"- {theme['label']} ({theme['count']} supporters)")
    else:
        brief_lines.append("- No themes met minimum support in this slice.")

    brief_lines.extend(["", "## Numbers behind it"])
    if metrics:
        for metric in metrics[:5]:
            brief_lines.append(f"- {metric['name']}: {metric['value']} (n={metric['n']})")
    else:
        brief_lines.append("- No substantiated numeric metrics yet.")

    brief_lines.extend(["", "## Filing cross-reference"])
    if findings:
        for finding in findings[:5]:
            brief_lines.append(
                f"- {finding['theme_id']}: {finding['verdict']} ({finding['filing_chunk_id']})"
            )
    else:
        brief_lines.append("- No filing findings yet.")

    brief_lines.extend(["", *_source_footer_lines(grievance_ids, filing_ids)])

    return {
        "demand_list": "\n".join(demand_lines),
        "press_release": "\n".join(press_lines),
        "brief": "\n".join(brief_lines),
    }


def _normalize_drafts(
    payload: dict[str, Any],
    grievance_ids: list[str],
    filing_ids: list[str],
) -> dict[str, str]:
    drafts: dict[str, str] = {}
    for kind in ("demand_list", "press_release", "brief"):
        value = payload.get(kind)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        if "## Sources" not in cleaned:
            cleaned = "\n\n".join([cleaned, "\n".join(_source_footer_lines(grievance_ids, filing_ids))])
        drafts[kind] = cleaned
    return drafts


def _run_draft_stage(
    themes: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    grievance_ids: list[str],
) -> dict[str, str]:
    filing_ids = _collect_filing_ids(findings)
    synthesis_packet = {
        "themes": themes,
        "metrics": metrics,
        "findings": findings,
        "grievance_ids": grievance_ids,
        "filing_chunk_ids": filing_ids,
    }
    prompt = _render_prompt("draft.md", {"SYNTHESIS_PACKET_JSON": _compact_json(synthesis_packet)})

    try:
        payload = call(prompt, DRAFT_SCHEMA)
        drafts = _normalize_drafts(payload, grievance_ids, filing_ids)
        if len(drafts) == 3:
            return drafts
    except (ClaudeUnavailable, ClaudeRateLimited, ClaudeResponseError):
        pass

    return _build_local_drafts(themes, metrics, findings, grievance_ids, filing_ids)


def _persist_draft_exports(db: Session, synthesis: Synthesis, drafts: dict[str, str]) -> dict[str, str]:
    export_ids: dict[str, str] = {}
    now = int(time())
    for kind, body in drafts.items():
        export = Export(
            id=new_ulid(),
            synthesis_id=synthesis.id,
            kind=kind,
            body_md=body,
            created_at=now,
        )
        db.add(export)
        export_ids[kind] = export.id
    db.commit()
    return export_ids


def run_synthesis(db: Session, scope: SynthesisRequest) -> Synthesis:
    grievances = list(db.scalars(_scoped_grievance_query(scope)))
    grievance_ids = [grievance.id for grievance in grievances]
    grievance_by_id = {grievance.id: grievance for grievance in grievances}

    themes = _run_cluster_stage(grievances)
    metrics = _run_quantify_stage(themes, grievances, grievance_by_id)
    findings = _run_crossref_stage(db, themes, metrics, grievance_by_id, scope.platform)
    drafts = _run_draft_stage(themes, metrics, findings, grievance_ids)

    output = {
        "themes": themes,
        "metrics": metrics,
        "findings": findings,
        "exports": {},
    }

    # Exclude `since` from scope_filter: it's a rolling timestamp that changes every
    # second in the browser, so including it makes exact-match lookups always miss.
    scope_key = {k: v for k, v in scope.model_dump(exclude_none=True).items() if k != "since"}
    synthesis = Synthesis(
        id=new_ulid(),
        created_at=int(time()),
        scope_filter=_compact_json(scope_key),
        output_json=_compact_json(output),
        grievance_ids=_compact_json(grievance_ids),
    )
    db.add(synthesis)
    db.commit()
    db.refresh(synthesis)

    if drafts:
        output["exports"] = _persist_draft_exports(db, synthesis, drafts)
        synthesis.output_json = _compact_json(output)
        db.add(synthesis)
        db.commit()
        db.refresh(synthesis)

    return synthesis


def create_export(db: Session, synthesis: Synthesis, kind: ExportKind) -> Export:
    output = json.loads(synthesis.output_json)
    existing_exports = output.get("exports", {})
    existing_export_id = existing_exports.get(kind) if isinstance(existing_exports, dict) else None
    if isinstance(existing_export_id, str):
        existing_export = db.get(Export, existing_export_id)
        if existing_export is not None:
            return existing_export

    grievance_ids = json.loads(synthesis.grievance_ids)
    themes = output.get("themes", [])
    metrics = output.get("metrics", [])
    findings = output.get("findings", [])
    filing_ids = _collect_filing_ids(findings)
    drafts = _build_local_drafts(themes, metrics, findings, grievance_ids, filing_ids)
    body = drafts[kind]

    export = Export(
        id=new_ulid(),
        synthesis_id=synthesis.id,
        kind=kind,
        body_md=body,
        created_at=int(time()),
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    output_exports = output.get("exports")
    if not isinstance(output_exports, dict):
        output_exports = {}
    output_exports[kind] = export.id
    output["exports"] = output_exports
    synthesis.output_json = _compact_json(output)
    db.add(synthesis)
    db.commit()
    db.refresh(synthesis)

    return export
