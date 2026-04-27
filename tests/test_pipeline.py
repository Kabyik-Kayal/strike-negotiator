import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.config import get_settings
from server.db import get_session_factory, init_db, reset_database
from server.main import app
from server.models import Grievance


TEST_HASH_SALT = "test-hash-salt-change-for-production"


def configure_test_database(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIKE_HASH_SALT", TEST_HASH_SALT)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("STRIKE_ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    settings.data_dir = tmp_path
    settings.audio_dir = tmp_path / "audio"
    reset_database(f"sqlite:///{tmp_path / 'strike.db'}")
    init_db()


def _ingest_synthetic(client: TestClient, worker_id: int, transcript: str) -> None:
    response = client.post(
        "/ingest/text",
        json={
            "worker_secret": f"pipeline-rider-{worker_id}",
            "language": "en",
            "transcript": transcript,
            "platform": "swiggy",
            "city_bucket": "Bengaluru Urban",
            "source": "synthetic",
        },
    )
    assert response.status_code == 201


def test_pipeline_end_to_end_contract_with_local_fallback(tmp_path, monkeypatch):
    configure_test_database(tmp_path, monkeypatch)
    client = TestClient(app)

    for index in range(8):
        _ingest_synthetic(
            client,
            index,
            (
                f"Rate cut complaint {index}: per-order payout fell from Rs 35 to Rs 28, "
                "I now work 260 hours and still cannot make rent."
            ),
        )
    for index in range(6):
        _ingest_synthetic(
            client,
            index + 100,
            (
                f"Incentive complaint {index}: I completed 52 deliveries but incentive is missing, "
                "my weekly earning dropped to Rs 14000."
            ),
        )

    filing_response = client.post(
        "/filing-chunks",
        json={
            "id": "swiggy-drhp-p84-c3",
            "platform": "swiggy",
            "doc_type": "drhp",
            "doc_date": "2026-03-31",
            "page": 84,
            "text": "Partner earnings grew 18 percent year over year with stronger incentive realization.",
        },
    )
    assert filing_response.status_code == 201

    synthesis_response = client.post("/syntheses", json={"platform": "swiggy"})
    assert synthesis_response.status_code == 201
    synthesis = synthesis_response.json()
    output = json.loads(synthesis["output_json"])

    assert output["themes"]
    assert any(theme["count"] >= 5 for theme in output["themes"])

    with get_session_factory()() as session:
        grievance_ids = set(session.scalars(select(Grievance.id)))

    for theme in output.get("themes", []):
        assert set(theme["grievance_ids"]).issubset(grievance_ids)

    for metric in output.get("metrics", []):
        assert metric["n"] == len(metric["grievance_ids"])

    for finding in output.get("findings", []):
        assert len(finding["filing_excerpt"].split()) <= 10

    assert set(output["exports"]) == {"demand_list", "press_release", "brief"}
    for export_id in output["exports"].values():
        export_response = client.get(f"/exports/{export_id}")
        assert export_response.status_code == 200
        body_md = export_response.json()["body_md"]
        assert "## Sources" in body_md