from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class SpeakerBase(BaseModel):
    name: str
    handle_or_channel: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class SpeakerCreate(SpeakerBase):
    pass

class SocialAccount(BaseModel):
    platform: str
    identifier: str
    url: Optional[str] = None
    title: Optional[str] = None

class SpeakerResponse(SpeakerBase):
    id: str
    overall_credibility: float
    overall_brier_score: float
    total_predictions: int
    resolved_predictions: int
    correct_predictions: int
    domain_scores: Dict[str, Any]
    created_at: datetime
    social_accounts: List[SocialAccount] = []

    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    domain: str = "general"
    base_rate: float = 0.5
    deadline: Optional[datetime] = None

class EventCreate(EventBase):
    pass

class EventResolveRequest(BaseModel):
    outcome: bool = Field(..., description="True if event occurred, False if not")
    resolution_notes: Optional[str] = Field(None, description="Proof or reasoning")

class StatementResponse(BaseModel):
    id: str
    speaker_id: str
    speaker_name: Optional[str] = None
    speaker_credibility: Optional[float] = None
    event_id: str
    source_platform: str
    source_url: str
    raw_quote: str
    speaker_confidence: float
    speaker_weight_applied: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StatementCreate(BaseModel):
    speaker_name: str
    speaker_handle: Optional[str] = None
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    event_domain: str = "general"
    source_platform: str = "youtube"
    source_url: str
    raw_quote: str
    speaker_confidence: float = Field(..., ge=0.01, le=0.99)

class EventResponse(EventBase):
    id: str
    current_probability: float
    status: str
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    statements: List[StatementResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ExtractFromTextRequest(BaseModel):
    text: str = Field(..., description="Interview transcript, social media post, or statement")
    speaker_name: Optional[str] = None
    source_url: str = Field(..., description="YouTube URL or source link")
    source_platform: str = "youtube"

class ExtractedPrediction(BaseModel):
    speaker_name: str
    event_hypothesis: str
    domain: str
    speaker_confidence: float
    deadline_str: Optional[str] = None
    raw_quote: str
    reasoning: str
