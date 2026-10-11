import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import NarrativeCluster, Event, Statement
from app.engine.clustering import SemanticEventMatcher
from app.services.prediction_service import PredictionService

class EventDiscoveryEngine:
    """
    Analyzes raw streams of claims and statements from social media,
    clusters them into emerging narratives, and promotes mature debates
    into official active events with probability tracking.
    """

    @classmethod
    def ingest_statement_to_narratives(
        cls,
        db: Session,
        statement_text: str,
        speaker_name: str,
        domain: str = "crypto"
    ) -> NarrativeCluster:
        """
        Takes an unstructured statement and assigns it to an emerging narrative cluster,
        or starts a new cluster if novel.
        """
        # Tokenize incoming statement
        incoming_tokens = SemanticEventMatcher._tokenize_and_normalize(statement_text)
        
        # Check active clusters
        clusters = db.query(NarrativeCluster).filter(
            NarrativeCluster.status != "PROMOTED",
            NarrativeCluster.domain.ilike(domain)
        ).all()

        best_cluster = None
        highest_score = 0.0

        for c in clusters:
            c_tokens = set(c.key_phrases.get("tokens", []))
            sim = SemanticEventMatcher._calculate_jaccard_similarity(incoming_tokens, c_tokens)
            if sim > highest_score:
                highest_score = sim
                best_cluster = c

        # If similarity is significant, attach to existing cluster
        if best_cluster and highest_score >= 0.25:
            best_cluster.statement_count += 1
            # Update key tokens
            all_tokens = list(set(best_cluster.key_phrases.get("tokens", [])).union(incoming_tokens))
            speakers = set(best_cluster.key_phrases.get("speakers", []))
            speakers.add(speaker_name)
            
            best_cluster.key_phrases = {
                "tokens": all_tokens,
                "speakers": list(speakers)
            }
            best_cluster.unique_speakers_count = len(speakers)

            # Check promotion threshold: >= 3 unique speakers debating this topic
            if best_cluster.unique_speakers_count >= 3:
                best_cluster.status = "MATURE"
                # Auto-promote mature narrative to an official event
                cls.promote_narrative_to_event(db, best_cluster.id)

            db.commit()
            db.refresh(best_cluster)
            return best_cluster

        # Otherwise create a new emerging narrative cluster
        new_cluster = NarrativeCluster(
            topic_summary=statement_text[:200],
            domain=domain,
            key_phrases={
                "tokens": list(incoming_tokens),
                "speakers": [speaker_name]
            },
            statement_count=1,
            unique_speakers_count=1,
            status="EMERGING"
        )
        db.add(new_cluster)
        db.commit()
        db.refresh(new_cluster)
        return new_cluster

    @classmethod
    def promote_narrative_to_event(cls, db: Session, cluster_id: str) -> Optional[Event]:
        """
        Converts a mature narrative cluster into an officially tracked Event in TruthOdds.
        """
        cluster = db.query(NarrativeCluster).filter(NarrativeCluster.id == cluster_id).first()
        if not cluster:
            return None

        # Clean event title
        event_title = cls._clean_narrative_to_event_title(cluster.topic_summary)
        from app.engine.auto_analysis import AutoEventAnalysisEngine
        calib = AutoEventAnalysisEngine.evaluate_claim_calibration(event_title, cluster.domain)

        # Create official event
        event = PredictionService.get_or_create_event(
            db=db,
            title=event_title,
            domain=cluster.domain,
            base_rate=float(calib.get("base_rate", 0.5))
        )
        AutoEventAnalysisEngine.analyze_and_forecast_event(db, event)

        cluster.status = "PROMOTED"
        cluster.promoted_event_id = event.id
        db.commit()
        db.refresh(cluster)
        return event

    @staticmethod
    def _clean_narrative_to_event_title(raw_text: str) -> str:
        clean = raw_text.strip()
        # Ensure capitalization
        if clean:
            clean = clean[0].upper() + clean[1:]
        # Remove quotation marks
        clean = clean.replace('«', '').replace('»', '').replace('"', '').strip()
        return clean[:300]
