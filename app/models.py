import uuid
import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    canonical_name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255), nullable=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    tax_id = Column(String(50), nullable=True, index=True)
    tax_id_country = Column(String(2), default="ES")
    industry = Column(String(100), nullable=True)
    employee_range = Column(String(50), nullable=True)
    hq_country = Column(String(2), default="ES")
    hq_city = Column(String(100), nullable=True)
    hq_address = Column(Text, nullable=True)
    website_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
    tech_stack = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    aliases = relationship("CompanyAlias", back_populates="company", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="company", cascade="all, delete-orphan")
    scrape_logs = relationship("ScrapeLog", back_populates="company", cascade="all, delete-orphan")
    intent_snapshots = relationship("IntentSnapshot", back_populates="company", cascade="all, delete-orphan")
    tech_entries = relationship("CompanyTechStack", back_populates="company", cascade="all, delete-orphan")


class CompanyTechStack(Base):
    __tablename__ = "company_tech_stack"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), nullable=False)  # 'Email', 'CRM', 'CMS', 'CDN', 'Analytics'
    tech_name = Column(String(100), nullable=False, index=True)  # 'Google Workspace', 'Salesforce'
    icon = Column(String(50), default="fa-laptop-code")
    confidence = Column(Float, default=1.0)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)

    company = relationship("Company", back_populates="tech_entries")



class CompanyAlias(Base):
    __tablename__ = "company_aliases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    alias_name = Column(String(255), nullable=False, index=True)
    alias_type = Column(String(50), nullable=False)  # 'name', 'domain', 'tax_id'
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    company = relationship("Company", back_populates="aliases")


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=True)  # e.g., 200, 404, 500, 0 for timeout
    duration_ms = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    content_hash = Column(String(64), nullable=True)
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    company = relationship("Company", back_populates="scrape_logs")


class SignalType(Base):
    __tablename__ = "signal_types"

    code = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    vector_category = Column(String(50), nullable=False)
    base_weight = Column(Float, nullable=False, default=20.0)
    half_life_days = Column(Integer, nullable=False, default=30)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_type_code = Column(String(100), ForeignKey("signal_types.code"), nullable=False)
    source = Column(String(100), nullable=False)
    confidence = Column(Float, default=1.0)
    score_impact = Column(Float, default=25.0)  # Numeric impact on Intent Score
    raw_payload = Column(JSON, default=dict)
    extracted_attributes = Column(JSON, default=dict)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    company = relationship("Company", back_populates="signals")
    signal_type = relationship("SignalType")


class IntentSnapshot(Base):
    __tablename__ = "intent_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    window_days = Column(Integer, default=30)
    growth_intent = Column(Float, default=0.0)
    hiring_intent = Column(Float, default=0.0)
    expansion_intent = Column(Float, default=0.0)
    technology_change_intent = Column(Float, default=0.0)
    financial_stress = Column(Float, default=0.0)
    composite_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=1.0)
    primary_label = Column(String(150), nullable=True)
    signal_count = Column(Integer, default=0)
    attribution_matrix = Column(JSON, default=list)
    computed_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    company = relationship("Company", back_populates="intent_snapshots")


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    client_id = Column(String(100), nullable=False)
    target_url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)
    min_composite_score = Column(Float, default=70.0)
    subscribed_vectors = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_name = Column(String(200), nullable=False, default="Alerta de Intención Comercial")
    channel = Column(String(50), default="WEBHOOK")  # 'SLACK', 'TEAMS', 'WEBHOOK', 'EMAIL'
    target_url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=True)  # Secret key for HMAC SHA256 signature
    min_composite_score = Column(Float, default=70.0)
    subscribed_signal_code = Column(String(100), nullable=True)
    subscribed_industry = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)



class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    plan_tier = Column(String(50), default="ENTERPRISE")  # 'FREE', 'PRO', 'ENTERPRISE'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="ANALYST")  # 'ADMIN', 'ANALYST', 'VIEWER'
    subscription_status = Column(String(50), default="trial")  # 'trial', 'active', 'past_due', 'canceled'
    trial_ends_at = Column(DateTime, default=lambda: datetime.datetime.utcnow() + datetime.timedelta(days=7))
    stripe_customer_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(30), default="#3b82f6")  # Accent color tag
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    memberships = relationship("WatchlistCompany", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistCompany(Base):
    __tablename__ = "watchlist_companies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    watchlist_id = Column(String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

    watchlist = relationship("Watchlist", back_populates="memberships")
    company = relationship("Company")



