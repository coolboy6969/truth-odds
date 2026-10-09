from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.entities import Base

# Using SQLite with check_same_thread=False for async/FastAPI compatibility
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import text

def clean_db_artifacts(db: Session):
    """
    Cleans up any invalid analyst entries (e.g. random words like 'Год')
    and deduplicates speakers and candidates by name and source URL.
    """
    from app.models.entities import Speaker, Statement, Event, MonitoredSource, DiscoveredSpeakerCandidate
    from app.discovery.speaker_discovery import is_valid_analyst_name, normalize_analyst_url
    from app.engine.scoring import ForecasterScorer
    from app.services.prediction_service import PredictionService

    # 1. Purge invalid speakers (words like 'Год', 'Predicts Xrp', etc.)
    all_speakers = db.query(Speaker).all()
    affected_event_ids = set()
    for sp in all_speakers:
        if not is_valid_analyst_name(sp.name):
            for st in sp.statements:
                affected_event_ids.add(st.event_id)
            db.query(MonitoredSource).filter(MonitoredSource.speaker_id == sp.id).delete()
            db.delete(sp)

    db.commit()

    # Recalculate affected events
    for ev_id in affected_event_ids:
        ev = db.query(Event).filter(Event.id == ev_id).first()
        if ev:
            stmts = ev.statements or []
            if stmts:
                stmt_dicts = []
                for s in stmts:
                    s_sp = db.query(Speaker).filter(Speaker.id == s.speaker_id).first()
                    sp_weight = PredictionService.get_speaker_weight_for_domain(s_sp, ev.domain) if s_sp else s.speaker_weight_applied
                    stmt_dicts.append({
                        "speaker_confidence": s.speaker_confidence,
                        "speaker_weight": sp_weight
                    })
                ev.current_probability = ForecasterScorer.aggregate_event_probability(stmt_dicts, ev.base_rate)
            else:
                ev.current_probability = ev.base_rate
    db.commit()

    # 2. Deduplicate remaining speakers by name
    speakers_by_name = {}
    for sp in db.query(Speaker).all():
        key = sp.name.strip().lower()
        if key not in speakers_by_name:
            speakers_by_name[key] = [sp]
        else:
            speakers_by_name[key].append(sp)

    for key, sp_list in speakers_by_name.items():
        if len(sp_list) > 1:
            primary = max(sp_list, key=lambda s: s.total_predictions)
            for duplicate in sp_list:
                if duplicate.id != primary.id:
                    for st in duplicate.statements:
                        st.speaker_id = primary.id
                    db.query(MonitoredSource).filter(MonitoredSource.speaker_id == duplicate.id).update({"speaker_id": primary.id})
                    db.delete(duplicate)
    db.commit()

    # 3. Purge invalid candidates
    all_candidates = db.query(DiscoveredSpeakerCandidate).all()
    for cand in all_candidates:
        if not is_valid_analyst_name(cand.name):
            db.delete(cand)
    db.commit()

    # 4. Deduplicate remaining candidates by name and source_url
    candidates = db.query(DiscoveredSpeakerCandidate).all()
    seen_cand_names = {}
    seen_cand_urls = {}

    for cand in candidates:
        name_key = cand.name.strip().lower()
        norm_url = normalize_analyst_url(cand.source_url) if cand.source_url else ""

        match = None
        if name_key in seen_cand_names:
            match = seen_cand_names[name_key]
        elif norm_url and norm_url in seen_cand_urls:
            match = seen_cand_urls[norm_url]

        if match:
            # Merge duplicate into match
            match.mention_count += cand.mention_count
            existing_preds = match.extracted_predictions or []
            new_preds = cand.extracted_predictions or []
            existing_hyps = {p.get('event_hypothesis', '').lower().strip() for p in existing_preds if p.get('event_hypothesis')}
            for p in new_preds:
                hyp = (p.get('event_hypothesis') or '').lower().strip()
                if hyp and hyp not in existing_hyps:
                    existing_preds.append(p)
                    existing_hyps.add(hyp)
            match.extracted_predictions = existing_preds[:10]
            if not match.source_url and cand.source_url:
                match.source_url = cand.source_url
            db.delete(cand)
        else:
            seen_cand_names[name_key] = cand
            if norm_url:
                seen_cand_urls[norm_url] = cand

    db.commit()

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure any new columns exist in sqlite if table was already created
    with engine.connect() as conn:
        for col_def in [
            "ALTER TABLE discovered_candidates ADD COLUMN source_url VARCHAR(1000)",
            "ALTER TABLE discovered_candidates ADD COLUMN extracted_predictions JSON"
        ]:
            try:
                conn.execute(text(col_def))
                conn.commit()
            except Exception:
                pass

    # Run cleanup of invalid words and deduplicate records
    with SessionLocal() as db:
        try:
            clean_db_artifacts(db)
        except Exception as e:
            print(f"[InitDB] Cleanup error: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
