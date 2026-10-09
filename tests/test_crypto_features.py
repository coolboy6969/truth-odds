import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine.clustering import SemanticEventMatcher
from app.oracles.crypto_oracle import CryptoPriceOracle

client = TestClient(app)

def test_semantic_event_matching_deduplication():
    # Test token normalization
    tokens1 = SemanticEventMatcher._tokenize_and_normalize("Биткоин достигнет отметки $150,000 до конца 2026")
    tokens2 = SemanticEventMatcher._tokenize_and_normalize("BTC пробьет 150k к декабрю 2026")
    
    sim = SemanticEventMatcher._calculate_jaccard_similarity(tokens1, tokens2)
    boost = SemanticEventMatcher._compare_numeric_targets(
        "Биткоин достигнет отметки $150,000 до конца 2026",
        "BTC пробьет 150k к декабрю 2026"
    )
    assert (sim + boost) >= 0.45

def test_crypto_oracle_price_target_parser():
    p1 = CryptoPriceOracle.parse_event_price_target("Биткоин достигнет отметки $150,000 до конца 2026 года")
    assert p1 is not None
    assert p1["asset"] == "BTC"
    assert p1["target"] == 150000.0

    p2 = CryptoPriceOracle.parse_event_price_target("Ethereum выше $5,000 в 2025")
    assert p2 is not None
    assert p2["asset"] == "ETH"
    assert p2["target"] == 5000.0

    p3 = CryptoPriceOracle.parse_event_price_target("Solana достигнет 300к ? нет, $250")
    assert p3 is not None
    assert p3["asset"] == "SOL"

def test_seed_crypto_top10():
    client.post("/api/demo/reset-db")
    resp = client.post("/api/crypto/seed-top10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["speakers"]) >= 10

    # Verify speakers ranking
    resp_speakers = client.get("/api/speakers")
    assert resp_speakers.status_code == 200
    speakers = resp_speakers.json()
    
    # Saylor, Vitalik, Hayes should have high credibility
    vitalik = next((s for s in speakers if "vitalik" in s["name"].lower()), None)
    schiff = next((s for s in speakers if "schiff" in s["name"].lower()), None)
    
    assert vitalik["overall_credibility"] > 0.65
    assert schiff["overall_credibility"] < 0.35  # Contrarian indicator!

    # Check monitored sources are populated
    resp_sources = client.get("/api/sources")
    assert resp_sources.status_code == 200
    sources = resp_sources.json()
    assert len(sources) >= 10

def test_auto_oracle_endpoints():
    # 1. Status check
    st = client.get("/api/oracle/status")
    assert st.status_code == 200
    assert "is_enabled" in st.json()

    # 2. Toggle check
    tog = client.post("/api/oracle/toggle", json={"enabled": True})
    assert tog.status_code == 200
    assert tog.json()["is_enabled"] is True

    # 3. Check-now trigger
    chk = client.post("/api/oracle/check-now?auto_resolve=true")
    assert chk.status_code == 200
    data = chk.json()
    assert data["success"] is True
    assert "summary" in data

def test_automated_event_analysis_and_forecasting():
    client.post("/api/demo/reset-db")
    # 1. Create event with auto analysis
    ev_res = client.post("/api/events", json={
        "title": "Биткоин превысит $150,000 к концу 2026 года",
        "domain": "general",
        "auto_analyze": True
    })
    assert ev_res.status_code == 200
    data = ev_res.json()
    assert data["domain"] == "crypto"
    assert len(data["statements"]) >= 2
    # Verify probability is calculated based on consensus (not static 0.5)
    assert data["current_probability"] != 0.5

    # 2. Create event with attached speaker
    ev2_res = client.post("/api/events", json={
        "title": "Создание AGI сверхинтеллекта до конца 2026",
        "speaker_name": "Elon Musk",
        "domain": "general",
        "auto_analyze": True
    })
    assert ev2_res.status_code == 200
    data2 = ev2_res.json()
    assert data2["domain"] == "tech"
    speakers_in_ev = [s["speaker_name"] for s in data2["statements"]]
    assert "Elon Musk" in speakers_in_ev


