import json
from time import time

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from server.ids import new_ulid
from server.models import Export, Grievance, Synthesis
from server.schemas import ExportKind, SynthesisRequest


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _format_source_ids(grievance_ids: list[str], limit: int = 20) -> str:
    if not grievance_ids:
        return "No grievance IDs yet."

    visible_ids = grievance_ids[:limit]
    footer = ", ".join(visible_ids)
    remaining = len(grievance_ids) - len(visible_ids)
    if remaining:
        footer = f"{footer}, and {remaining} more"
    return footer


def _scoped_grievance_query(scope: SynthesisRequest) -> Select[tuple[Grievance]]:
    stmt = select(Grievance)
    if scope.city:
        stmt = stmt.where(Grievance.city_bucket == scope.city)
    if scope.platform:
        stmt = stmt.where(Grievance.platform == scope.platform)
    if scope.since:
        stmt = stmt.where(Grievance.created_at >= scope.since)
    return stmt.order_by(desc(Grievance.created_at)).limit(500)


def run_synthesis(db: Session, scope: SynthesisRequest) -> Synthesis:
    grievances = list(db.scalars(_scoped_grievance_query(scope)))
    grievance_ids = [grievance.id for grievance in grievances]

    # This is the storage contract for the future Claude pipeline. The placeholder
    # keeps the API usable while prompts and model calls are added.
    output = {
        "themes": [
            {
                "id": "initial-grievance-pool",
                "label": "Initial grievance pool",
                "count": len(grievances),
                "grievance_ids": grievance_ids,
                "quotes": [g.transcript[:240] for g in grievances[:3]],
            }
        ]
        if grievances
        else [],
        "metrics": [],
        "findings": [],
        "exports": {},
    }

    synthesis = Synthesis(
        id=new_ulid(),
        created_at=int(time()),
        scope_filter=_compact_json(scope.model_dump(exclude_none=True)),
        output_json=_compact_json(output),
        grievance_ids=_compact_json(grievance_ids),
    )
    db.add(synthesis)
    db.commit()
    db.refresh(synthesis)
    return synthesis


def create_export(db: Session, synthesis: Synthesis, kind: ExportKind) -> Export:
    output = json.loads(synthesis.output_json)
    grievance_ids = json.loads(synthesis.grievance_ids)
    title = {
        "press_release": "Press Release",
        "demand_list": "Demand List",
        "brief": "Negotiation Brief",
    }[kind]

    theme_lines = [
        f"- {theme['label']} ({theme['count']} supporting grievances)"
        for theme in output.get("themes", [])
    ]
    if not theme_lines:
        theme_lines = ["- No grievances matched this synthesis scope yet."]

    body = "\n".join(
        [
            f"# {title}",
            "",
            "## What people are saying",
            *theme_lines,
            "",
            "## Sources",
            "",
            _format_source_ids(grievance_ids),
        ]
    )

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
    return export
