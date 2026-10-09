import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "TruthOdds - Forecaster Accuracy & Event Probability Engine"
    DATABASE_URL: str = "sqlite:///./truth_odds.db"
    
    # LLM API configuration (optional, fallback to heuristic/mock parser if not provided)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Scoring hyperparameters
    DEFAULT_BASE_RATE: float = 0.5  # Prior probability when no predictions exist
    PRIOR_SAMPLE_SIZE: int = 3       # Shrinkage prior weight (Beta-binomial pseudo-observations)
    DEFAULT_PRIOR_WEIGHT: float = 0.5 # Default credibility before enough predictions
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
