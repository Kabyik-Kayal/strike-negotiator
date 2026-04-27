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
    get_settings.cache_clear()
    settings = get_settings()
    settings.data_dir = tmp_path
    settings.audio_dir = tmp_path / "audio"
    reset_database(f"sqlite:///{tmp_path / 'strike.db'}")
    init_db()


def test_synthesis_citation_ids_exist_and_metric_counts_match(tmp_path, monkeypatch):
    configure_test_database(tmp_path, monkeypatch)
    client = TestClient(app)

    for index in range(3):
        response = client.post(
            "/ingest/text",
            json={
                "worker_secret": f"rider-{index}",
                "language": "en",
                "transcript": f"Wrongful deactivation complaint {index}.",
                "platform": "swiggy",
                "source": "synthetic",
            },
        )
        assert response.status_code == 201

    synthesis_response = client.post("/syntheses", json={"platform": "swiggy"})
    assert synthesis_response.status_code == 201
    output = json.loads(synthesis_response.json()["output_json"])

    with get_session_factory()() as session:
        existing_ids = set(session.scalars(select(Grievance.id)))

    for theme in output.get("themes", []):
        assert set(theme["grievance_ids"]).issubset(existing_ids)

    for metric in output.get("metrics", []):
        assert metric["n"] == len(metric["grievance_ids"])
