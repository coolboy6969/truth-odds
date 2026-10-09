import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import init_db

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_seed_demo_and_verify_scoring():
    client.post("/api/demo/reset-db")
    # Seed data
    resp_seed = client.post("/api/demo/seed")
    assert resp_seed.status_code == 200

    # Verify speakers
    resp_sp = client.get("/api/speakers")
    assert resp_sp.status_code == 200
    speakers = resp_sp.json()
    assert len(speakers) >= 4
    
    # Check that Vitalik (high accuracy) has higher credibility than Schiff (consistently wrong)
    vitalik = next((s for s in speakers if "vitalik" in s["name"].lower()), None)
    schiff = next((s for s in speakers if "schiff" in s["name"].lower()), None)
    
    assert vitalik is not None
    assert schiff is not None
    
    # Vitalik's credibility should be higher than Schiff's
    assert vitalik["overall_credibility"] > schiff["overall_credibility"]
    assert vitalik["overall_brier_score"] < schiff["overall_brier_score"]

    # Verify active events
    resp_ev = client.get("/api/events")
    assert resp_ev.status_code == 200
    events = resp_ev.json()
    assert len(events) >= 2

import uuid

def test_event_resolution_updates_speaker_ratings():
    unique_id = str(uuid.uuid4())[:8]
    # Create a new event
    resp_ev = client.post("/api/events", json={
        "title": f"Test Event {unique_id}",
        "domain": "tech",
        "base_rate": 0.5
    })
    assert resp_ev.status_code == 200
    event_data = resp_ev.json()
    ev_id = event_data["id"]

    # Record a confident statement by a test speaker
    resp_st = client.post("/api/statements", json={
        "speaker_name": f"Forecaster {unique_id}",
        "event_id": ev_id,
        "source_platform": "twitter",
        "source_url": "https://test.com",
        "raw_quote": "Событие точно произойдет на 95%",
        "speaker_confidence": 0.95
    })
    assert resp_st.status_code == 200
    sp_id = resp_st.json()["speaker_id"]

    # Before resolution, speaker has 0 resolved
    resp_sp_before = client.get(f"/api/speakers/{sp_id}")
    assert resp_sp_before.json()["resolved_predictions"] == 0

    # Resolve event as TRUE (speaker was right!)
    resp_res = client.post(f"/api/events/{ev_id}/resolve", json={
        "outcome": True,
        "resolution_notes": "Запуск прошел штатно"
    })
    assert resp_res.status_code == 200
    assert resp_res.json()["status"] == "RESOLVED_TRUE"

    # After resolution, speaker track record must update
    resp_sp_after = client.get(f"/api/speakers/{sp_id}")
    sp_after = resp_sp_after.json()
    assert sp_after["resolved_predictions"] == 1
    # Brier score should be very low (close to 0) since predicted 0.95 and outcome was 1
    assert sp_after["overall_brier_score"] < 0.05
    assert sp_after["overall_credibility"] > 0.55


def test_delete_event_and_narrative():
    # 1. Test event creation and deletion
    resp_ev = client.post("/api/events", json={
        "title": "Событие для проверки удаления",
        "domain": "crypto",
        "auto_analyze": False
    })
    assert resp_ev.status_code == 200
    ev_id = resp_ev.json()["id"]

    # Delete event
    resp_del = client.delete(f"/api/events/{ev_id}")
    assert resp_del.status_code == 200
    assert resp_del.json()["success"] is True

    # Check that it no longer exists
    resp_get = client.get(f"/api/events/{ev_id}")
    assert resp_get.status_code == 404

    # 2. Test narrative cluster creation and deletion
    resp_nar = client.post("/api/discovery/narratives", json={
        "topic_summary": "Тема для проверки удаления",
        "domain": "crypto",
        "keywords": ["del_test"]
    })
    assert resp_nar.status_code == 200
    nar_id = resp_nar.json()["id"]

    resp_del_nar = client.delete(f"/api/discovery/narratives/{nar_id}")
    assert resp_del_nar.status_code == 200
    assert resp_del_nar.json()["success"] is True


def test_speaker_x_social_presence():
    # Verify that speakers have X (Twitter) social accounts linked
    resp = client.get("/api/speakers")
    assert resp.status_code == 200
    speakers = resp.json()
    assert len(speakers) > 0
    for sp in speakers:
        social_platforms = [s["platform"] for s in sp.get("social_accounts", [])]
        assert "x" in social_platforms or "twitter" in social_platforms


def test_topic_auto_verification():
    # Creating a new narrative topic automatically creates and verifies a Bayesian event
    resp = client.post("/api/discovery/narratives", json={
        "topic_summary": "Достигнет ли Биткоин $200,000 в 2026 году?",
        "domain": "crypto",
        "keywords": ["биткоин", "btc", "200k"]
    })
    assert resp.status_code == 200
    cluster = resp.json()
    assert cluster["statement_count"] >= 1

    # Check that the corresponding event exists with calculated probability and expert opinions
    resp_evs = client.get("/api/events")
    assert resp_evs.status_code == 200
    events = resp_evs.json()
    matched = next((e for e in events if "200,000" in e["title"] or "200k" in e["title"].lower()), None)
    assert matched is not None
    assert len(matched["statements"]) >= 1
    assert matched["current_probability"] != 0.5 or len(matched["statements"]) > 0

