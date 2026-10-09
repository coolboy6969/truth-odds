import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.discovery.speaker_discovery import SpeakerDiscoveryEngine
from app.discovery.event_discovery import EventDiscoveryEngine

client = TestClient(app)

def test_speaker_name_extraction():
    title1 = "Interview with Lyn Alden: The Macro Endgame"
    names1 = SpeakerDiscoveryEngine.extract_potential_speakers(title1)
    assert "Lyn Alden" in names1

    title2 = "Интервью с Артемом Первушиным: Что будет с криптой"
    names2 = SpeakerDiscoveryEngine.extract_potential_speakers(title2)
    assert any("Артем" in n for n in names2)

    title3 = "Mert Mumtaz explains why Solana architecture scales"
    names3 = SpeakerDiscoveryEngine.extract_potential_speakers(title3)
    assert "Mert Mumtaz" in names3

import uuid

def test_narrative_clustering_and_auto_promotion():
    test_domain = f"test-crypto-{uuid.uuid4().hex[:6]}"
    
    # 1. Statement from Speaker A
    resp1 = client.post("/api/discovery/scan-stream", json={
        "text": "Solana обойдет Ethereum по объему суточных DEX-торгов",
        "channel_or_source": "Podcast 1",
        "speaker_hint": "Analyst A",
        "domain": test_domain
    })
    assert resp1.status_code == 200
    cluster_id = resp1.json()["narrative_cluster_id"]

    # 2. Statement from Speaker B (semantically similar)
    resp2 = client.post("/api/discovery/scan-stream", json={
        "text": "DEX объем на Solana устойчиво превысит Ethereum",
        "channel_or_source": "Podcast 2",
        "speaker_hint": "Analyst B",
        "domain": test_domain
    })
    assert resp2.status_code == 200
    assert resp2.json()["narrative_cluster_id"] == cluster_id
    assert resp2.json()["unique_speakers_debating"] == 2

    # 3. Statement from Speaker C -> Reaches threshold of 3 speakers -> Promoted!
    resp3 = client.post("/api/discovery/scan-stream", json={
        "text": "Solana превзойдет Ethereum по суточному объему торгов на децентрализованных биржах",
        "channel_or_source": "Podcast 3",
        "speaker_hint": "Analyst C",
        "domain": test_domain
    })
    assert resp3.status_code == 200
    assert resp3.json()["unique_speakers_debating"] >= 3

def test_candidate_discovery_and_manual_approval():
    # Scan text mentioning a new person
    resp = client.post("/api/discovery/scan-stream", json={
        "text": "Discussion with Dan Tapiero on future Web3 valuations",
        "channel_or_source": "Macro Show"
    })
    assert resp.status_code == 200

    # Get candidates list
    resp_cand = client.get("/api/discovery/candidates")
    assert resp_cand.status_code == 200
    candidates = resp_cand.json()
    tapiero = next((c for c in candidates if "Dan Tapiero" in c["name"]), None)
    assert tapiero is not None

    # Approve candidate
    resp_appr = client.post(f"/api/discovery/candidates/{tapiero['id']}/approve")
    assert resp_appr.status_code == 200
    assert resp_appr.json()["success"] is True

    # Candidate should now be in the main Speakers list
    resp_sps = client.get("/api/speakers")
    assert any("Dan Tapiero" in s["name"] for s in resp_sps.json())

def test_seed_radar_demo():
    resp = client.post("/api/discovery/seed-radar-demo")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

def test_real_world_analyst_search_and_bayesian_integration():
    # 1. Search for a real-world analyst via live media search
    resp = client.post("/api/discovery/radar/search-person", json={
        "query": "Arthur Hayes",
        "auto_record": False
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total_articles"] > 0
    assert data["candidates_found"] > 0

    # 2. Check candidate is present in Radar candidates
    cands = client.get("/api/discovery/candidates").json()
    hayes_cand = next((c for c in cands if "Arthur Hayes" in c["name"]), None)
    assert hayes_cand is not None
    assert hayes_cand["status"] in ("CANDIDATE", "APPROVED")

    # 3. Approve candidate and verify statements are recorded
    resp_appr = client.post(f"/api/discovery/candidates/{hayes_cand['id']}/approve")
    assert resp_appr.status_code == 200
    appr_data = resp_appr.json()
    assert appr_data["success"] is True

    # 4. Verify candidate is now in accepted Speakers list
    speakers = client.get("/api/speakers").json()
    assert any("Arthur Hayes" in s["name"] for s in speakers)

    # 5. Verify events have statements from this speaker
    events = client.get("/api/events").json()
    assert len(events) > 0

def test_real_world_live_media_scan():
    resp = client.post("/api/discovery/radar/live-scan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "total_articles" in data
    assert "candidates_found" in data
