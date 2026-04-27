import json

from fastapi.testclient import TestClient

from server.config import get_settings
from server.db import Base, get_engine, init_db, reset_database
from server.main import app
from server.models import Grievance


def configure_test_database(tmp_path):
    get_settings().data_dir = tmp_path
    get_settings().audio_dir = tmp_path / "audio"
    reset_database(f"sqlite:///{tmp_path / 'strike.db'}")
    init_db()
    return get_engine()


def test_text_ingest_hashes_worker_secret(tmp_path):
    engine = configure_test_database(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/ingest/text",
        json={
            "worker_secret": "9999999999",
            "language": "en",
            "transcript": "My per-order payout was cut in March.",
            "city_bucket": "Bengaluru Urban",
            "platform": "swiggy",
            "source": "synthetic",
        },
    )

    assert response.status_code == 201
    with engine.connect() as connection:
        row = connection.execute(Grievance.__table__.select()).mappings().one()

    assert row["worker_hash"] != "9999999999"
    assert row["audio_path"] is None
    assert row["transcript"] == "My per-order payout was cut in March."


def test_synthesis_keeps_citation_ids_valid(tmp_path):
    configure_test_database(tmp_path)
    client = TestClient(app)

    ingest_response = client.post(
        "/ingest/text",
        json={
            "worker_secret": "rider-1",
            "language": "en",
            "transcript": "Incentive payouts are missing for two weeks.",
            "platform": "zomato",
            "source": "synthetic",
        },
    )
    grievance_id = ingest_response.json()["id"]

    synthesis_response = client.post("/syntheses", json={"platform": "zomato"})

    assert synthesis_response.status_code == 201
    synthesis = synthesis_response.json()
    output = json.loads(synthesis["output_json"])
    grievance_ids = json.loads(synthesis["grievance_ids"])

    assert grievance_ids == [grievance_id]
    assert output["themes"][0]["grievance_ids"] == [grievance_id]

