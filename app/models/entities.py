import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    handle_or_channel: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Credibility & Calibration metrics
    overall_credibility: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0 - 1.0 trust score
    overall_brier_score: Mapped[float] = mapped_column(Float, default=0.25) # 0.0 is perfect, 0.25 is random
    total_predictions: Mapped[int] = mapped_column(Integer, default=0)
    resolved_predictions: Mapped[int] = mapped_column(Integer, default=0)
    correct_predictions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Domain-specific calibration JSON:
    # e.g., {"crypto": {"brier": 0.12, "credibility": 0.82, "resolved_count": 8, "correct": 7}}
    domain_scores: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    statements: Mapped[list["Statement"]] = relationship("Statement", back_populates="speaker", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Speaker(name='{self.name}', credibility={self.overall_credibility:.2f}, resolved={self.resolved_predictions})>"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(100), default="general", index=True)
    
    base_rate: Mapped[float] = mapped_column(Float, default=0.5)           # Prior base probability
    current_probability: Mapped[float] = mapped_column(Float, default=0.5) # Aggregated Bayesian probability
    
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status: ACTIVE, RESOLVED_TRUE, RESOLVED_FALSE, VOID
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
    is_manual: Mapped[int] = mapped_column(Integer, default=0)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    statements: Mapped[list["Statement"]] = relationship("Statement", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Event(title='{self.title[:30]}...', prob={self.current_probability:.1%}, status='{self.status}')>"


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    speaker_id: Mapped[str] = mapped_column(String(36), ForeignKey("speakers.id"), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), nullable=False, index=True)
    
    source_platform: Mapped[str] = mapped_column(String(50), default="youtube") # youtube, twitter, telegram, media
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_quote: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Prediction parameters
    speaker_confidence: Mapped[float] = mapped_column(Float, nullable=False) # Probability predicted by speaker [0.0 - 1.0]
    speaker_weight_applied: Mapped[float] = mapped_column(Float, default=0.5) # Speaker's weight when aggregated
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="statements")
    event: Mapped["Event"] = relationship("Event", back_populates="statements")

    def __repr__(self) -> str:
        return f"<Statement(speaker='{self.speaker_id}', conf={self.speaker_confidence:.2f})>"


class MonitoredSource(Base):
    __tablename__ = "monitored_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    speaker_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("speakers.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), default="youtube") # youtube, twitter, telegram
    channel_title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_identifier: Mapped[str] = mapped_column(String(255), nullable=False) # channel_id, @handle
    feed_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    speaker: Mapped[Optional["Speaker"]] = relationship("Speaker")

    def __repr__(self) -> str:
        return f"<MonitoredSource(title='{self.channel_title}', platform='{self.platform}')>"


class DiscoveredSpeakerCandidate(Base):
    __tablename__ = "discovered_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    discovered_via_channel: Mapped[str] = mapped_column(String(255), nullable=False)
    context_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    extracted_predictions: Mapped[Optional[Any]] = mapped_column(JSON, default=list, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    claim_density_score: Mapped[float] = mapped_column(Float, default=0.5)
    
    # Status: CANDIDATE, APPROVED, REJECTED
    status: Mapped[str] = mapped_column(String(50), default="CANDIDATE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Candidate(name='{self.name}', mentions={self.mention_count}, status='{self.status}')>"


class NarrativeCluster(Base):
    __tablename__ = "narrative_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), default="crypto")
    key_phrases: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict) # extracted keywords
    statement_count: Mapped[int] = mapped_column(Integer, default=1)
    unique_speakers_count: Mapped[int] = mapped_column(Integer, default=1)
    
    # Status: EMERGING (1-2 mentions), MATURE (>=3 mentions, ready to promote), PROMOTED (event created)
    status: Mapped[str] = mapped_column(String(50), default="EMERGING", index=True)
    promoted_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<NarrativeCluster(topic='{self.topic_summary[:30]}...', count={self.statement_count})>"
