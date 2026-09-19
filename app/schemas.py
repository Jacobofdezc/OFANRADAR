import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class SignalAttribution(BaseModel):
    signal_id: str
    signal_code: str
    signal_name: str
    vector_category: str
    source: str
    detected_at: datetime.datetime
    age_days: float
    confidence: float
    base_weight: float
    half_life_days: int
    attenuated_weight: float


class IntentVectorScores(BaseModel):
    growth_intent: float = Field(..., ge=0.0, le=100.0, description="Growth intent score (0-100)")
    hiring_intent: float = Field(..., ge=0.0, le=100.0, description="Hiring intent score (0-100)")
    expansion_intent: float = Field(..., ge=0.0, le=100.0, description="Expansion intent score (0-100)")
    technology_change_intent: float = Field(..., ge=0.0, le=100.0, description="Technology change intent score (0-100)")
    financial_stress: float = Field(..., ge=0.0, le=100.0, description="Financial stress score (0-100)")
    composite_score: float = Field(..., ge=0.0, le=100.0, description="Overall weighted composite score (0-100)")


class IntentSnapshotResponse(BaseModel):
    snapshot_id: str
    company_id: str
    company_name: str
    domain: str
    window_days: int
    intent_scores: IntentVectorScores
    primary_label: str
    business_summary: Optional[str] = None
    recommended_action: Optional[str] = None
    confidence_score: float
    signal_count: int
    attribution_matrix: List[SignalAttribution]
    computed_at: datetime.datetime


class CompanyResponse(BaseModel):
    id: str
    canonical_name: str
    legal_name: Optional[str] = None
    domain: str
    tax_id: Optional[str] = None
    tax_id_country: str = "ES"
    industry: Optional[str] = None
    employee_range: Optional[str] = None
    hq_country: str = "ES"
    hq_city: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    logo_url: Optional[str] = None
    latest_intent: Optional[IntentVectorScores] = None
    primary_label: Optional[str] = None
    business_summary: Optional[str] = None
    recommended_action: Optional[str] = None
    score_history: List[float] = Field(default_factory=list, description="30-day historical score points for sparkline trends")
    score_change_30d: float = Field(default=0.0, description="Delta change in composite score over 30 days")
    is_locked: bool = Field(default=False, description="True if payload is obfuscated due to expired trial/subscription")
    created_at: datetime.datetime


class SignalIngestRequest(BaseModel):
    company_identifier: str = Field(..., description="Domain, Tax ID (CIF/NIF), or UUID")
    signal_type_code: str = Field(..., description="Valid signal code, e.g., 'JOB_POSTING_SURGE'")
    source: str = Field(..., description="Ingestion source name")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    detected_at: Optional[datetime.datetime] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class CompanyQueryRequest(BaseModel):
    min_growth_intent: Optional[float] = Field(None, ge=0, le=100)
    min_hiring_intent: Optional[float] = Field(None, ge=0, le=100)
    min_expansion_intent: Optional[float] = Field(None, ge=0, le=100)
    min_tech_change_intent: Optional[float] = Field(None, ge=0, le=100)
    min_financial_stress: Optional[float] = Field(None, ge=0, le=100)
    min_composite_score: Optional[float] = Field(None, ge=0, le=100)
    max_composite_score: Optional[float] = Field(None, ge=0, le=100)
    recent_event_type: Optional[str] = Field(None, description="Signal type code, e.g., 'JOB_POSTING_SURGE'")
    recent_event_days: int = Field(default=7, ge=1, le=90, description="Window in days for recent events")
    country: Optional[str] = None
    industry: Optional[str] = None
    search: Optional[str] = None
    active_within_days: int = Field(default=30, ge=1, le=180)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class WebhookSubscriptionRequest(BaseModel):
    client_id: str
    target_url: str
    secret: str
    min_composite_score: float = 70.0
    subscribed_vectors: List[str] = Field(default=["expansion_intent", "growth_intent"])


class WebhookSubscriptionResponse(BaseModel):
    id: str
    client_id: str
    target_url: str
    min_composite_score: float
    subscribed_vectors: List[str]
    is_active: bool
    created_at: datetime.datetime


class WatchlistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"


class WatchlistResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    color: str
    company_count: int = 0
    avg_intent_score: float = 0.0
    created_at: datetime.datetime


class WatchlistAddCompanyRequest(BaseModel):
    company_id: str


class UserRegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    full_name: str
    organization_name: str
    role: str = "ADMIN"


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    role: str
    tenant_id: str
    organization_name: str
    subscription_status: str = "trial"
    trial_ends_at: Optional[datetime.datetime] = None
    days_left_in_trial: int = 7


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    full_name: str
    role: str
    subscription_status: str = "trial"
    trial_ends_at: Optional[datetime.datetime] = None
    days_left_in_trial: int = 7
    is_active: bool
    created_at: datetime.datetime


class AlertSubscriptionRequest(BaseModel):
    rule_name: str = Field(..., min_length=2, max_length=200)
    channel: str = Field(default="WEBHOOK", description="'SLACK', 'TEAMS', 'WEBHOOK', 'EMAIL'")
    target_url: str = Field(..., description="Webhook URL or Slack/Teams Incoming Webhook endpoint")
    secret: Optional[str] = Field(None, description="Secret key for HMAC SHA256 signature")
    min_composite_score: float = Field(default=70.0, ge=0.0, le=100.0)
    subscribed_signal_code: Optional[str] = None
    subscribed_industry: Optional[str] = None


class AlertSubscriptionResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    rule_name: str
    channel: str
    target_url: str
    min_composite_score: float
    subscribed_signal_code: Optional[str] = None
    subscribed_industry: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime


class AlertTestTriggerRequest(BaseModel):
    subscription_id: str
    company_id: Optional[str] = None


class AnalyzeOnDemandRequest(BaseModel):
    query: str = Field(..., description="Company name, domain, CIF/NIF, or keyword to analyze on-demand")




