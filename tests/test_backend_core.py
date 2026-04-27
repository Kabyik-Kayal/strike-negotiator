import json

from fastapi.testclient import TestClient

from server.config import get_settings
from server.db import get_engine, init_db, reset_database
from server.main import app
from server.models import Grievance
from server.security import hash_worker_secret


TEST_HASH_SALT = "test-hash-salt-change-for-production"


def configure_test_database(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIKE_HASH_SALT", TEST_HASH_SALT)
    get_settings.cache_clear()
    settings = get_settings()
    settings.data_dir = tmp_path
    settings.audio_dir = tmp_path / "audio"
    reset_database(f"sqlite:///{tmp_path / 'strike.db'}")
    init_db()
    return get_engine()


def test_text_ingest_hashes_worker_secret(tmp_path, monkeypatch):
    engine = configure_test_database(tmp_path, monkeypatch)
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


def test_hash_worker_secret_is_stable_and_distinguishes_inputs(tmp_path, monkeypatch):
    configure_test_database(tmp_path, monkeypatch)

    first = hash_worker_secret("9999999999")
    second = hash_worker_secret("9999999999")
    different = hash_worker_secret("8888888888")

    assert first == second
    assert first != different
    assert first != "9999999999"


def test_settings_reject_missing_or_default_hash_salt(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("STRIKE_HASH_SALT", raising=False)
    try:
        get_settings()
    except RuntimeError as exc:
        assert "STRIKE_HASH_SALT must be set" in str(exc)
    else:
        raise AssertionError("Settings accepted a missing STRIKE_HASH_SALT")

    get_settings.cache_clear()
    monkeypatch.setenv("STRIKE_HASH_SALT", "dev-salt-change-me")
    try:
        get_settings()
    except RuntimeError as exc:
        assert "STRIKE_HASH_SALT must be set" in str(exc)
    else:
        raise AssertionError("Settings accepted the default STRIKE_HASH_SALT")


def test_grievance_read_omits_private_fields(tmp_path, monkeypatch):
    configure_test_database(tmp_path, monkeypatch)
    client = TestClient(app)

    ingest_response = client.post(
        "/ingest/text",
        json={
            "worker_secret": "9999999999",
            "language": "en",
            "transcript": "My per-order payout was cut in March.",
            "source": "synthetic",
        },
    )
    grievance_id = ingest_response.json()["id"]

    list_response = client.get("/grievances")
    detail_response = client.get(f"/grievances/{grievance_id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert "worker_hash" not in list_response.json()[0]
    assert "audio_path" not in list_response.json()[0]
    assert "worker_hash" not in detail_response.json()
    assert "audio_path" not in detail_response.json()


def test_synthesis_keeps_citation_ids_valid(tmp_path, monkeypatch):
    configure_test_database(tmp_path, monkeypatch)
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
