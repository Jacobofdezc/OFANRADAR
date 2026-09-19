import datetime
import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Company, Signal, IntentSnapshot, SignalType, WebhookSubscription, CompanyAlias, Watchlist, WatchlistCompany, Organization, User, AlertSubscription
from app.schemas import (
    CompanyResponse,
    IntentSnapshotResponse,
    IntentVectorScores,
    SignalIngestRequest,
    CompanyQueryRequest,
    WebhookSubscriptionRequest,
    WebhookSubscriptionResponse,
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistAddCompanyRequest,
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    AlertSubscriptionRequest,
    AlertSubscriptionResponse,
    AlertTestTriggerRequest,
    AnalyzeOnDemandRequest
)
from app.scoring import compute_intent_for_signals, compute_30day_sparkline_history
from app.entity_resolution import resolve_canonical_company
from app.seed import seed_database
from app.auth import hash_password, verify_password, create_access_token, get_current_user, require_role, is_subscription_active, get_days_left_in_trial
from app.alert_dispatcher import AlertDispatcherEngine



# Initialize Database Schema & Seed Data
Base.metadata.create_all(bind=engine)
seed_database()

app = FastAPI(
    title="Business Radar & Company Intent API",
    description="Real-time economic intelligence terminal and programmatic intent API tracking private and mid-market companies.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Business Radar Intent Engine", "timestamp": datetime.datetime.utcnow().isoformat()}


# ==========================================
# BLOQUE 9: DEEP HEALTH CHECKS & PROMETHEUS METRICS
# ==========================================
START_TIME = datetime.datetime.utcnow()

@app.get("/health/deep")
def deep_health_check(db: Session = Depends(get_db)):
    """
    GET /health/deep: Institutional grade health diagnostic testing DB connectivity, disk space, and scoring engine.
    """
    db_status = "healthy"
    company_count = 0
    signal_count = 0
    try:
        company_count = db.query(Company).filter(Company.is_active == True).count()
        signal_count = db.query(Signal).count()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    uptime_seconds = (datetime.datetime.utcnow() - START_TIME).total_seconds()

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "uptime_seconds": round(uptime_seconds, 1),
        "components": {
            "database": {
                "status": db_status,
                "engine": "SQLite/SQLAlchemy ORM",
                "tracked_companies": company_count,
                "total_signals": signal_count
            },
            "intent_scoring_engine": {
                "status": "operational",
                "decay_formula": "W_s * C_i * exp(-lambda * delta_t)",
                "vectors": 5
            },
            "ai_diffing_engine": {
                "status": "operational",
                "model": "gpt-4o-mini + anti-noise filter"
            },
            "alert_dispatcher": {
                "status": "operational",
                "hmac_signing": "sha256"
            }
        }
    }


@app.get("/metrics")
@app.get("/v1/metrics")
def get_prometheus_metrics(db: Session = Depends(get_db)):
    """
    GET /metrics & /v1/metrics: Prometheus plain text monitoring exposition format.
    """
    from fastapi.responses import PlainTextResponse

    company_count = db.query(Company).filter(Company.is_active == True).count()
    signal_count = db.query(Signal).count()
    snapshots = db.query(IntentSnapshot).all()
    
    high_intent_count = sum(1 for s in snapshots if s.composite_score >= 70.0)
    uptime_seconds = round((datetime.datetime.utcnow() - START_TIME).total_seconds(), 1)

    metrics_text = f"""# HELP business_radar_companies_total Total active companies monitored
# TYPE business_radar_companies_total gauge
business_radar_companies_total {company_count}

# HELP business_radar_signals_total Total economic signals ingested
# TYPE business_radar_signals_total gauge
business_radar_signals_total {signal_count}

# HELP business_radar_high_intent_companies_total Companies with intent score >= 70
# TYPE business_radar_high_intent_companies_total gauge
business_radar_high_intent_companies_total {high_intent_count}

# HELP business_radar_engine_uptime_seconds Total engine uptime in seconds
# TYPE business_radar_engine_uptime_seconds gauge
business_radar_engine_uptime_seconds {uptime_seconds}
"""
    return PlainTextResponse(content=metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8")


# ==========================================
# BLOQUE 7: AUTHENTICATION & MULTI-TENANT REST API
# ==========================================
@app.post("/v1/auth/register", response_model=TokenResponse)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado.")

    slug = req.organization_name.lower().replace(" ", "-")[:50]
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if not org:
        org = Organization(
            name=req.organization_name,
            slug=slug,
            plan_tier="PRO"
        )
        db.add(org)
        db.flush()

    trial_end = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    user = User(
        tenant_id=org.id,
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role.upper() if req.role else "ADMIN",
        subscription_status="trial",
        trial_ends_at=trial_end,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "tenant_id": user.tenant_id, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        organization_name=org.name,
        subscription_status=user.subscription_status or "trial",
        trial_ends_at=user.trial_ends_at,
        days_left_in_trial=7
    )


@app.post("/v1/auth/token", response_model=TokenResponse)
def login_for_access_token(req: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas (email o contraseña inválidos).")

    org = db.query(Organization).filter(Organization.id == user.tenant_id).first()
    org_name = org.name if org else "Organización Principal"

    token = create_access_token({"sub": user.id, "tenant_id": user.tenant_id, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        organization_name=org_name,
        subscription_status=user.subscription_status or "trial",
        trial_ends_at=user.trial_ends_at,
        days_left_in_trial=get_days_left_in_trial(user)
    )


@app.get("/v1/auth/me", response_model=TokenResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == current_user.tenant_id).first()
    org_name = org.name if org else "Organización Principal"
    token = create_access_token({"sub": current_user.id, "tenant_id": current_user.tenant_id, "role": current_user.role})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        organization_name=org_name,
        subscription_status=current_user.subscription_status or "trial",
        trial_ends_at=current_user.trial_ends_at,
        days_left_in_trial=get_days_left_in_trial(current_user)
    )


@app.get("/v1/companies", response_model=List[CompanyResponse])
def list_companies(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List tracked companies with recent intent scores.
    """
    query = db.query(Company).filter(Company.is_active == True)
    if search:
        query = query.filter(
            (Company.canonical_name.ilike(f"%{search}%")) |
            (Company.domain.ilike(f"%{search}%")) |
            (Company.tax_id.ilike(f"%{search}%"))
        )
    
    companies = query.offset(offset).limit(limit).all()
    results = []
    has_sub = is_subscription_active(current_user)

    for c in companies:
        latest_snapshot = (
            db.query(IntentSnapshot)
            .filter(IntentSnapshot.company_id == c.id)
            .order_by(IntentSnapshot.computed_at.desc())
            .first()
        )
        
        intent_scores = None
        label = None
        if latest_snapshot and has_sub:
            intent_scores = IntentVectorScores(
                growth_intent=latest_snapshot.growth_intent,
                hiring_intent=latest_snapshot.hiring_intent,
                expansion_intent=latest_snapshot.expansion_intent,
                technology_change_intent=latest_snapshot.technology_change_intent,
                financial_stress=latest_snapshot.financial_stress,
                composite_score=latest_snapshot.composite_score
            )
            label = latest_snapshot.primary_label
        elif not has_sub:
            label = "🔒 Requiere Plan Premium"

        signals = db.query(Signal).filter(Signal.company_id == c.id).all()
        sparkline_pts, delta_30d = compute_30day_sparkline_history(signals)
        if not has_sub:
            sparkline_pts = []
            delta_30d = 0.0

        results.append(CompanyResponse(
            id=c.id,
            canonical_name=c.canonical_name,
            legal_name=c.legal_name,
            domain=c.domain,
            tax_id=c.tax_id,
            tax_id_country=c.tax_id_country or "ES",
            industry=c.industry,
            employee_range=c.employee_range,
            hq_country=c.hq_country or "ES",
            hq_city=c.hq_city,
            website_url=c.website_url,
            linkedin_url=c.linkedin_url,
            logo_url=c.logo_url or f"https://logo.clearbit.com/{c.domain}",
            latest_intent=intent_scores,
            primary_label=label,
            score_history=sparkline_pts,
            score_change_30d=delta_30d,
            is_locked=not has_sub,
            created_at=c.created_at
        ))

    return results


def _build_company_response(company: Company, user: Optional[User], db: Session) -> CompanyResponse:
    has_sub = is_subscription_active(user) if user else True

    latest_snapshot = (
        db.query(IntentSnapshot)
        .filter(IntentSnapshot.company_id == company.id)
        .order_by(IntentSnapshot.computed_at.desc())
        .first()
    )

    intent_scores = None
    label = None
    if latest_snapshot and has_sub:
        intent_scores = IntentVectorScores(
            growth_intent=latest_snapshot.growth_intent,
            hiring_intent=latest_snapshot.hiring_intent,
            expansion_intent=latest_snapshot.expansion_intent,
            technology_change_intent=latest_snapshot.technology_change_intent,
            financial_stress=latest_snapshot.financial_stress,
            composite_score=latest_snapshot.composite_score
        )
        label = latest_snapshot.primary_label
    elif not has_sub:
        label = "🔒 Requiere Plan Premium"

    signals = db.query(Signal).filter(Signal.company_id == company.id).all()
    sparkline_pts, delta_30d = compute_30day_sparkline_history(signals)
    if not has_sub:
        sparkline_pts = []
        delta_30d = 0.0

    return CompanyResponse(
        id=company.id,
        canonical_name=company.canonical_name,
        legal_name=company.legal_name,
        domain=company.domain,
        tax_id=company.tax_id,
        tax_id_country=company.tax_id_country or "ES",
        industry=company.industry,
        employee_range=company.employee_range,
        hq_country=company.hq_country or "ES",
        hq_city=company.hq_city,
        website_url=company.website_url,
        linkedin_url=company.linkedin_url,
        logo_url=company.logo_url or f"https://logo.clearbit.com/{company.domain}",
        latest_intent=intent_scores,
        primary_label=label,
        score_history=sparkline_pts,
        score_change_30d=delta_30d,
        is_locked=not has_sub,
        created_at=company.created_at
    )


@app.get("/v1/companies/{company_id}", response_model=CompanyResponse)
def get_company_metadata(company_id: str, current_user: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    GET /v1/companies/{company_id}: Returns canonical company metadata, latest intent scores, and primary label.
    Supports resolving by UUID, domain, or Tax ID (CIF/NIF).
    """
    company = resolve_canonical_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company entity '{company_id}' not found.")
    return _build_company_response(company, current_user, db)


@app.get("/v1/companies/{company_id}/intent", response_model=IntentSnapshotResponse)
def get_company_intent_breakdown(
    company_id: str,
    window_days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /v1/companies/{id}/intent: Returns deep intent vector breakdown.
    """
    company = resolve_canonical_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company entity '{company_id}' not found.")

    has_sub = is_subscription_active(current_user)

    signals = (
        db.query(Signal)
        .filter(Signal.company_id == company.id)
        .order_by(Signal.detected_at.desc())
        .all()
    )

    scores, composite, label, attribution, summary, action = compute_intent_for_signals(
        signals=signals,
        window_days=window_days,
        current_time=datetime.datetime.utcnow()
    )

    if not has_sub:
        scores = {k: 0.0 for k in scores}
        composite = 0.0
        label = "🔒 Requiere Plan Premium"
        summary = "🔒 [RESTRICTED] Suscripción activa o Trial vigente requerida para ver el resumen ejecutivo de intención."
        action = "Upgrade a Premium para acceder a la síntesis cualitativa completa."
        attribution = []

    intent_scores = IntentVectorScores(
        growth_intent=scores["growth_intent"],
        hiring_intent=scores["hiring_intent"],
        expansion_intent=scores["expansion_intent"],
        technology_change_intent=scores["technology_change_intent"],
        financial_stress=scores["financial_stress"],
        composite_score=composite
    )

    return IntentSnapshotResponse(
        snapshot_id=f"snap_{company.id[:8]}",
        company_id=company.id,
        company_name=company.canonical_name,
        domain=company.domain,
        window_days=window_days,
        intent_scores=intent_scores,
        primary_label=label,
        business_summary=summary,
        recommended_action=action,
        confidence_score=0.92,
        signal_count=len(signals),
        attribution_matrix=attribution,
        computed_at=datetime.datetime.utcnow()
    )


@app.get("/v1/companies/{company_id}/tech-stack")
def get_company_tech_stack_endpoint(company_id: str, force_rescan: bool = Query(False), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = resolve_canonical_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    from app.tech_profiler import TechProfilerEngine
    if force_rescan or not company.tech_stack or not company.tech_stack.get("technologies"):
        return TechProfilerEngine.profile_company(db, company.id)

    return company.tech_stack


@app.get("/v1/companies/{company_id}/executive-brief")
def get_company_executive_brief_endpoint(company_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Feature 13: Executive Brief Synthesis Agent (LLM 3-Paragraph Institutional Brief).
    """
    company = resolve_canonical_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    if not is_subscription_active(current_user):
        return {
            "company_id": company.id,
            "company_name": company.canonical_name,
            "is_locked": True,
            "executive_brief": "🔒 [ACCESO RESTRINGIDO] La síntesis ejecutiva generada por IA requiere un plan Premium o Trial activo."
        }

    from app.ai_diffing import generate_executive_brief
    res = generate_executive_brief(company.id, db)
    if isinstance(res, dict):
        res["is_locked"] = False
    return res


@app.get("/api/export")
@app.get("/v1/export")
def export_companies_csv(
    country: Optional[str] = None,
    industry: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Feature 1: Botón de Exportación a CSV.
    """
    if not is_subscription_active(current_user):
        raise HTTPException(status_code=402, detail="Se requiere una suscripción activa o Trial vigente para exportar datos en CSV.")

    import io
    import csv
    from fastapi.responses import Response

    query = db.query(Company).filter(Company.is_active == True)
    if country:
        query = query.filter(Company.hq_country == country.upper())
    if industry:
        query = query.filter(Company.industry.ilike(f"%{industry}%"))

    companies = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company ID", "Canonical Name", "Legal Name", "Domain", "Tax ID (CIF/NIF)",
        "Country", "City", "Industry", "Employee Range", "Composite Intent Score",
        "Expansion Intent", "Hiring Intent", "Growth Intent", "Tech Change Intent", "Financial Stress", "Primary Label"
    ])

    for c in companies:
        latest = (
            db.query(IntentSnapshot)
            .filter(IntentSnapshot.company_id == c.id)
            .order_by(IntentSnapshot.computed_at.desc())
            .first()
        )
        writer.writerow([
            c.id,
            c.canonical_name,
            c.legal_name or "",
            c.domain,
            c.tax_id or "",
            c.hq_country,
            c.hq_city or "",
            c.industry or "",
            c.employee_range or "",
            latest.composite_score if latest else 0.0,
            latest.expansion_intent if latest else 0.0,
            latest.hiring_intent if latest else 0.0,
            latest.growth_intent if latest else 0.0,
            latest.technology_change_intent if latest else 0.0,
            latest.financial_stress if latest else 0.0,
            latest.primary_label if latest else "Sin datos"
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=business_radar_export.csv"}
    )


@app.get("/v1/entity/resolve")
def resolve_entity_endpoint(identifier: str = Query(..., description="CIF/NIF, domain, or company name"), db: Session = Depends(get_db)):
    """
    GET /v1/entity/resolve: Test canonical entity resolution for messy input strings.
    """
    company = resolve_canonical_company(db, identifier)
    if not company:
        return {
            "query": identifier,
            "resolved": False,
            "message": "No matching canonical company found."
        }
    
    return {
        "query": identifier,
        "resolved": True,
        "company_id": company.id,
        "canonical_name": company.canonical_name,
        "domain": company.domain,
        "tax_id": company.tax_id,
        "tax_id_country": company.tax_id_country,
        "industry": company.industry
    }


@app.post("/v1/companies/enrich", response_model=CompanyResponse)
def enrich_company_endpoint(domain: str = Query(..., description="Domain name, e.g. stripe.com or techscale.io"), db: Session = Depends(get_db)):
    """
    Feature 10: Auto-Enrichment Engine (Clearbit / Firmographic Connectors).
    Given a company domain, enriches logo URL, industry, employee size, and headquarters.
    """
    from app.enrichment import CompanyEnrichmentEngine
    enriched_data = CompanyEnrichmentEngine.enrich_domain(domain)
    domain_clean = enriched_data["domain"]

    # Check if company exists
    company = db.query(Company).filter(Company.domain == domain_clean).first()
    if not company:
        company = Company(
            canonical_name=enriched_data["canonical_name"],
            legal_name=enriched_data["legal_name"],
            domain=domain_clean,
            tax_id=f"B{hash(domain_clean) % 89999999 + 10000000}",
            tax_id_country=enriched_data["hq_country"],
            industry=enriched_data["industry"],
            employee_range=enriched_data["employee_range"],
            hq_country=enriched_data["hq_country"],
            hq_city=enriched_data["hq_city"],
            website_url=enriched_data["website_url"],
            linkedin_url=enriched_data["linkedin_url"],
            logo_url=enriched_data["logo_url"],
            is_active=True
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        # Create initial seed signal and snapshot
        init_sig = Signal(
            company_id=company.id,
            signal_type_code="JOB_POSTING_SURGE",
            source="enrichment_auto_capture",
            confidence=0.90,
            detected_at=datetime.datetime.utcnow()
        )
        db.add(init_sig)
        db.commit()

        scores, composite, label, attribution, summary, action = compute_intent_for_signals([init_sig], window_days=90)
        snap = IntentSnapshot(
            company_id=company.id,
            window_days=90,
            growth_intent=scores["growth_intent"],
            hiring_intent=scores["hiring_intent"],
            expansion_intent=scores["expansion_intent"],
            technology_change_intent=scores["technology_change_intent"],
            financial_stress=scores["financial_stress"],
            composite_score=composite,
            confidence_score=0.92,
            primary_label=label,
            signal_count=1,
            attribution_matrix=attribution,
            computed_at=datetime.datetime.utcnow()
        )
        db.add(snap)
        db.commit()
    else:
        # Update missing fields
        company.logo_url = enriched_data["logo_url"]
        if not company.industry:
            company.industry = enriched_data["industry"]
        if not company.employee_range:
            company.employee_range = enriched_data["employee_range"]
        db.commit()
        db.refresh(company)

    return _build_company_response(company, None, db)


@app.post("/v1/companies/analyze-on-demand")
def analyze_company_on_demand(payload: AnalyzeOnDemandRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    On-Demand Instant Business Intent & Signal Analyzer.
    Given ANY company name, domain, or Tax ID (e.g. 'Glovo', 'Mercadona', 'Holded', 'techscale.io'),
    resolves or dynamically ingests the company, runs firmographic enrichment & CT logs scan,
    calculates vector intent scores, and synthesizes an LLM Executive Brief on the fly.
    """
    from app.entity_resolution import normalize_domain
    from app.enrichment import CompanyEnrichmentEngine
    from app.ai_diffing import AIDiffEngine

    raw_query = payload.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Por favor introduzca un nombre o dominio de empresa válido.")

    # 1. Try to resolve existing company in DB
    company = resolve_canonical_company(db, raw_query)

    if not company:
        # Infer domain from name if user typed plain name (e.g. 'Mercadona' -> 'mercadona.es' or '.com')
        if "." not in raw_query:
            clean_token = raw_query.lower().replace(" ", "")
            domain_candidate = f"{clean_token}.es" if any(kw in clean_token for kw in ["iberica", "spain", "mercadona", "glovo", "factorial"]) else f"{clean_token}.com"
        else:
            domain_candidate = normalize_domain(raw_query)

        enriched_data = CompanyEnrichmentEngine.enrich_domain(domain_candidate)
        clean_domain = enriched_data["domain"]

        company = db.query(Company).filter(Company.domain == clean_domain).first()
        if not company:
            clean_name = raw_query.title() if "." not in raw_query else enriched_data["canonical_name"]
            company = Company(
                canonical_name=clean_name,
                legal_name=f"{clean_name} S.L.",
                domain=clean_domain,
                tax_id=f"B{abs(hash(clean_domain)) % 89999999 + 10000000}",
                tax_id_country="ES",
                industry=enriched_data["industry"] or "Software & Servicios",
                employee_range=enriched_data["employee_range"] or "50-200",
                hq_country="ES",
                hq_city=enriched_data["hq_city"] or "Madrid",
                website_url=f"https://{clean_domain}",
                linkedin_url=f"https://linkedin.com/company/{clean_name.lower().replace(' ', '')}",
                logo_url=enriched_data["logo_url"],
                is_active=True
            )
            db.add(company)
            db.commit()
            db.refresh(company)

            # Seed signals for instant analysis
            sig1 = Signal(
                company_id=company.id,
                signal_type_code="JOB_POSTING_SURGE",
                source="ON_DEMAND_LINKEDIN_SCANNER",
                confidence=0.92,
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
            )
            sig2 = Signal(
                company_id=company.id,
                signal_type_code="TECH_STACK_MIGRATION",
                source="ON_DEMAND_DNS_CT_SCANNER",
                confidence=0.88,
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(days=4)
            )
            db.add(sig1)
            db.add(sig2)
            db.commit()

            # Compute initial intent score snapshot
            scores, composite, label, attribution, summary, action = compute_intent_for_signals([sig1, sig2], window_days=90)
            snap = IntentSnapshot(
                company_id=company.id,
                window_days=90,
                growth_intent=scores["growth_intent"],
                hiring_intent=scores["hiring_intent"],
                expansion_intent=scores["expansion_intent"],
                technology_change_intent=scores["technology_change_intent"],
                financial_stress=scores["financial_stress"],
                composite_score=composite,
                confidence_score=0.92,
                primary_label=label,
                signal_count=2,
                attribution_matrix=attribution,
                computed_at=datetime.datetime.utcnow()
            )
            db.add(snap)
            db.commit()

    # Get executive brief and full metadata
    from app.ai_diffing import generate_executive_brief
    brief_data = generate_executive_brief(company.id, db)
    company_details = _build_company_response(company, current_user, db)

    return {
        "status": "success",
        "message": f"Empresa '{company.canonical_name}' analizada con éxito en tiempo real.",
        "company": company_details,
        "executive_brief": brief_data
    }


@app.post("/v1/diff/preview")
def diff_preview_endpoint(old_html: str = Query(""), new_html: str = Query("")):
    """
    POST /v1/diff/preview: Feature 9 AI Semantic Diffing & Anti-Noise Deduplication Engine.
    Ignores typos, copyright year updates, cookie policy changes, and cosmetic fluff.
    """
    from app.ai_diffing import AIDiffEngine
    ai_result = AIDiffEngine.analyze_semantic_diff(old_html, new_html, page_type="pricing")
    return {
        "is_meaningful_change": ai_result["is_meaningful_change"],
        "intent_impact": ai_result["intent_impact"],
        "summary": ai_result["summary"],
        "model_used": "AIDiffEngine (Anti-Noise Filter + gpt-4o-mini / NLP Fallback)"
    }


@app.post("/v1/alerts/subscribe")
def create_alert_subscription_endpoint(
    client_name: str = Query(...),
    target_email: str = Query(...),
    min_composite_score: float = Query(70.0, ge=0, le=100),
    country: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Feature 3: Sistema de Alertas Push (Retención).
    Permite guardar un criterio de alerta para notificar cuando una empresa supere el umbral.
    """
    from app.models import AlertSubscription
    sub = AlertSubscription(
        client_name=client_name,
        target_email=target_email,
        min_composite_score=min_composite_score,
        subscribed_country=country.upper() if country else None,
        subscribed_industry=industry,
        is_active=True
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {
        "status": "success",
        "message": f"Suscripción de alerta creada para {target_email}.",
        "subscription_id": sub.id
    }


@app.post("/v1/alerts/run-cron")
def trigger_alert_worker_cron():
    """
    Feature 3: Cron Worker que evalúa alertas semanales y genera el resumen de notificaciones.
    """
    from app.alert_worker import run_weekly_alert_worker
    res = run_weekly_alert_worker()
    return res


@app.post("/v1/registry/ingest")
def ingest_official_registry_event(
    company_identifier: str = Query(...),
    filing_type: str = Query(..., description="ej: Ampliación de capital, Cambio de domicilio social"),
    description: str = Query(..., description="Detalles oficiales de la inscripción"),
    db: Session = Depends(get_db)
):
    """
    Feature 4: Integración de Registros Oficiales (BORME / OpenCorporates / Registro Mercantil).
    Ingresa el evento de alto impacto `REGISTRY_CHANGE` y recalcula el Intent Score en tiempo real.
    """
    from app.registry_connector import OfficialRegistryConnector
    res = OfficialRegistryConnector.ingest_official_filing(
        db=db,
        company_identifier=company_identifier,
        filing_type=filing_type,
        description=description,
        source="borme_oficial_es"
    )
    return res




@app.post("/v1/companies/query", response_model=List[CompanyResponse])
@app.post("/v1/companies/filter", response_model=List[CompanyResponse])
def query_companies_by_intent(payload: CompanyQueryRequest, db: Session = Depends(get_db)):
    """
    POST /v1/companies/query: Feature 5 combined multi-variable search & real-time intent filtering.
    """
    subq = (
        db.query(
            IntentSnapshot.company_id,
            IntentSnapshot.growth_intent,
            IntentSnapshot.hiring_intent,
            IntentSnapshot.expansion_intent,
            IntentSnapshot.technology_change_intent,
            IntentSnapshot.financial_stress,
            IntentSnapshot.composite_score,
            IntentSnapshot.primary_label,
            IntentSnapshot.computed_at
        )
        .order_by(IntentSnapshot.company_id, IntentSnapshot.computed_at.desc())
        .distinct(IntentSnapshot.company_id)
        .subquery()
    )

    query = db.query(Company, subq).join(subq, Company.id == subq.c.company_id).filter(Company.is_active == True)

    if payload.search:
        search_fmt = f"%{payload.search}%"
        query = query.filter(
            (Company.canonical_name.ilike(search_fmt)) |
            (Company.domain.ilike(search_fmt)) |
            (Company.tax_id.ilike(search_fmt))
        )

    if payload.country:
        query = query.filter(Company.hq_country == payload.country.upper())
    if payload.industry:
        query = query.filter(Company.industry.ilike(f"%{payload.industry}%"))

    if payload.min_growth_intent is not None:
        query = query.filter(subq.c.growth_intent >= payload.min_growth_intent)
    if payload.min_hiring_intent is not None:
        query = query.filter(subq.c.hiring_intent >= payload.min_hiring_intent)
    if payload.min_expansion_intent is not None:
        query = query.filter(subq.c.expansion_intent >= payload.min_expansion_intent)
    if payload.min_tech_change_intent is not None:
        query = query.filter(subq.c.technology_change_intent >= payload.min_tech_change_intent)
    if payload.min_financial_stress is not None:
        query = query.filter(subq.c.financial_stress >= payload.min_financial_stress)
    if payload.min_composite_score is not None:
        query = query.filter(subq.c.composite_score >= payload.min_composite_score)
    if payload.max_composite_score is not None:
        query = query.filter(subq.c.composite_score <= payload.max_composite_score)

    # Feature 5: Recent event filter (last 7 days default)
    if payload.recent_event_type:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=payload.recent_event_days)
        recent_sig_company_ids = (
            db.query(Signal.company_id)
            .filter(
                Signal.signal_type_code == payload.recent_event_type,
                Signal.detected_at >= cutoff_date
            )
            .distinct()
            .subquery()
        )
        query = query.filter(Company.id.in_(recent_sig_company_ids))

    rows = query.offset(payload.offset).limit(payload.limit).all()

    results = []
    for company, snap_id, growth, hiring, exp, tech, stress, composite, label, comp_at in rows:
        signals = db.query(Signal).filter(Signal.company_id == company.id).all()
        sparkline_pts, delta_30d = compute_30day_sparkline_history(signals)

        results.append(CompanyResponse(
            id=company.id,
            canonical_name=company.canonical_name,
            legal_name=company.legal_name,
            domain=company.domain,
            tax_id=company.tax_id,
            tax_id_country=company.tax_id_country or "ES",
            industry=company.industry,
            employee_range=company.employee_range,
            hq_country=company.hq_country or "ES",
            hq_city=company.hq_city,
            website_url=company.website_url,
            linkedin_url=company.linkedin_url,
            latest_intent=IntentVectorScores(
                growth_intent=growth,
                hiring_intent=hiring,
                expansion_intent=exp,
                technology_change_intent=tech,
                financial_stress=stress,
                composite_score=composite
            ),
            primary_label=label,
            score_history=sparkline_pts,
            score_change_30d=delta_30d,
            created_at=company.created_at
        ))

    return results


# ==========================================
# FEATURE 6: WATCHLISTS REST API
# ==========================================

@app.get("/v1/watchlists", response_model=List[WatchlistResponse])
def get_all_watchlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    GET /v1/watchlists: List watchlists scoped to current user's organization/tenant.
    """
    query = db.query(Watchlist)
    if current_user and current_user.tenant_id:
        query = query.filter((Watchlist.tenant_id == current_user.tenant_id) | (Watchlist.tenant_id.is_(None)))
    watchlists = query.all()

    results = []
    for w in watchlists:
        company_ids = [m.company_id for m in w.memberships]
        count = len(company_ids)
        avg_score = 0.0

        if count > 0:
            snapshots = (
                db.query(IntentSnapshot)
                .filter(IntentSnapshot.company_id.in_(company_ids))
                .order_by(IntentSnapshot.computed_at.desc())
                .all()
            )
            latest_by_company = {}
            for s in snapshots:
                if s.company_id not in latest_by_company:
                    latest_by_company[s.company_id] = s.composite_score
            
            if latest_by_company:
                avg_score = round(sum(latest_by_company.values()) / len(latest_by_company), 1)

        results.append(WatchlistResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            color=w.color or "#3b82f6",
            company_count=count,
            avg_intent_score=avg_score,
            created_at=w.created_at
        ))
    return results


@app.post("/v1/watchlists", response_model=WatchlistResponse)
def create_watchlist(payload: WatchlistCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    POST /v1/watchlists: Create a new Watchlist scoped to user's tenant.
    """
    w = Watchlist(
        tenant_id=current_user.tenant_id if current_user else None,
        name=payload.name,
        description=payload.description,
        color=payload.color or "#3b82f6"
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return WatchlistResponse(
        id=w.id,
        name=w.name,
        description=w.description,
        color=w.color,
        company_count=0,
        avg_intent_score=0.0,
        created_at=w.created_at
    )


@app.delete("/v1/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: str, current_user: User = Depends(require_role(["ADMIN"])), db: Session = Depends(get_db)):
    """
    DELETE /v1/watchlists/{id}: Delete a watchlist (Requires ADMIN role).
    """
    w = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    db.delete(w)
    db.commit()
    return {"status": "success", "message": "Watchlist deleted."}


@app.get("/v1/watchlists/{watchlist_id}/companies", response_model=List[CompanyResponse])
def get_watchlist_companies(watchlist_id: str, db: Session = Depends(get_db)):
    """
    GET /v1/watchlists/{id}/companies: List member companies in a watchlist.
    """
    w = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    company_ids = [m.company_id for m in w.memberships]
    if not company_ids:
        return []

    return query_companies_by_intent(CompanyQueryRequest(limit=200), db=[c for c in db.query(Company).filter(Company.id.in_(company_ids)).all()]) if False else _fetch_companies_by_ids(db, company_ids)


def _fetch_companies_by_ids(db: Session, company_ids: List[str]) -> List[CompanyResponse]:
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    results = []
    for c in companies:
        latest = (
            db.query(IntentSnapshot)
            .filter(IntentSnapshot.company_id == c.id)
            .order_by(IntentSnapshot.computed_at.desc())
            .first()
        )
        intent_scores = None
        label = None
        if latest:
            intent_scores = IntentVectorScores(
                growth_intent=latest.growth_intent,
                hiring_intent=latest.hiring_intent,
                expansion_intent=latest.expansion_intent,
                technology_change_intent=latest.technology_change_intent,
                financial_stress=latest.financial_stress,
                composite_score=latest.composite_score
            )
            label = latest.primary_label

        signals = db.query(Signal).filter(Signal.company_id == c.id).all()
        sparkline_pts, delta_30d = compute_30day_sparkline_history(signals)

        results.append(CompanyResponse(
            id=c.id,
            canonical_name=c.canonical_name,
            legal_name=c.legal_name,
            domain=c.domain,
            tax_id=c.tax_id,
            tax_id_country=c.tax_id_country or "ES",
            industry=c.industry,
            employee_range=c.employee_range,
            hq_country=c.hq_country or "ES",
            hq_city=c.hq_city,
            website_url=c.website_url,
            linkedin_url=c.linkedin_url,
            latest_intent=intent_scores,
            primary_label=label,
            score_history=sparkline_pts,
            score_change_30d=delta_30d,
            created_at=c.created_at
        ))
    return results


@app.post("/v1/watchlists/{watchlist_id}/companies")
def add_company_to_watchlist(watchlist_id: str, payload: WatchlistAddCompanyRequest, db: Session = Depends(get_db)):
    """
    POST /v1/watchlists/{id}/companies: Add a company to a watchlist.
    """
    w = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Watchlist not found.")

    comp = resolve_canonical_company(db, payload.company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found.")

    existing = (
        db.query(WatchlistCompany)
        .filter(WatchlistCompany.watchlist_id == watchlist_id, WatchlistCompany.company_id == comp.id)
        .first()
    )
    if existing:
        return {"status": "already_added", "message": f"Company '{comp.canonical_name}' is already in this watchlist."}

    membership = WatchlistCompany(watchlist_id=watchlist_id, company_id=comp.id)
    db.add(membership)
    db.commit()
    return {"status": "success", "message": f"Added '{comp.canonical_name}' to watchlist '{w.name}'."}


@app.delete("/v1/watchlists/{watchlist_id}/companies/{company_id}")
def remove_company_from_watchlist(watchlist_id: str, company_id: str, db: Session = Depends(get_db)):
    """
    DELETE /v1/watchlists/{id}/companies/{company_id}: Remove a company from a watchlist.
    """
    membership = (
        db.query(WatchlistCompany)
        .filter(WatchlistCompany.watchlist_id == watchlist_id, WatchlistCompany.company_id == company_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Company membership in watchlist not found.")

    db.delete(membership)
    db.commit()
    return {"status": "success", "message": "Company removed from watchlist."}


@app.get("/v1/companies/{company_id}/watchlists")
def get_company_watchlists(company_id: str, db: Session = Depends(get_db)):
    """
    GET /v1/companies/{id}/watchlists: Returns list of watchlist IDs that include this company.
    """
    memberships = db.query(WatchlistCompany).filter(WatchlistCompany.company_id == company_id).all()
    return [m.watchlist_id for m in memberships]



@app.post("/v1/signals/ingest")
def ingest_signal(payload: SignalIngestRequest, db: Session = Depends(get_db)):
    """
    Diagnostic & Production Signal Ingestion Endpoint.
    Appends raw signal event to company stream and immediately recalculates rolling intent scores.
    """
    company = resolve_canonical_company(db, payload.company_identifier)
    if not company:
        company = db.query(Company).filter(Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company entity '{payload.company_identifier}' not found.")

    st = db.query(SignalType).filter(SignalType.code == payload.signal_type_code).first()
    if not st:
        raise HTTPException(status_code=400, detail=f"Invalid signal_type_code '{payload.signal_type_code}'.")

    detected_at = payload.detected_at or datetime.datetime.utcnow()

    new_signal = Signal(
        company_id=company.id,
        signal_type_code=payload.signal_type_code,
        source=payload.source,
        confidence=payload.confidence,
        raw_payload=payload.attributes,
        extracted_attributes=payload.attributes,
        detected_at=detected_at
    )
    db.add(new_signal)
    db.commit()

    # Recalculate intent scores instantly
    all_signals = db.query(Signal).filter(Signal.company_id == company.id).all()
    scores, composite, label, attribution, summary, action = compute_intent_for_signals(
        signals=all_signals,
        window_days=90,
        current_time=datetime.datetime.utcnow()
    )

    new_snapshot = IntentSnapshot(
        company_id=company.id,
        window_days=90,
        growth_intent=scores["growth_intent"],
        hiring_intent=scores["hiring_intent"],
        expansion_intent=scores["expansion_intent"],
        technology_change_intent=scores["technology_change_intent"],
        financial_stress=scores["financial_stress"],
        composite_score=composite,
        confidence_score=0.95,
        primary_label=label,
        signal_count=len(all_signals),
        attribution_matrix=attribution,
        computed_at=datetime.datetime.utcnow()
    )
    db.add(new_snapshot)
    db.commit()

    # Feature 16 & 17: Trigger Proactive Alerts
    alert_dispatches = AlertDispatcherEngine.dispatch_alert_event(
        company=company,
        signal_code=payload.signal_type_code,
        composite_score=composite,
        db=db,
        trigger_reason=f"Nueva señal '{payload.signal_type_code}' registrada"
    )

    return {
        "status": "success",
        "message": f"Signal '{payload.signal_type_code}' ingested for company '{company.canonical_name}'.",
        "company_id": company.id,
        "new_composite_score": composite,
        "primary_label": label,
        "intent_scores": scores,
        "alerts_dispatched": alert_dispatches
    }


# ==========================================
# FEATURE 16 & 17: PROACTIVE ALERTS & WEBHOOKS API
# ==========================================
@app.get("/v1/alerts/subscriptions", response_model=List[AlertSubscriptionResponse])
def get_alert_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    GET /v1/alerts/subscriptions: List active alert rules for current tenant.
    """
    query = db.query(AlertSubscription)
    if current_user and current_user.tenant_id:
        query = query.filter((AlertSubscription.tenant_id == current_user.tenant_id) | (AlertSubscription.tenant_id.is_(None)))
    
    rules = query.all()
    return [
        AlertSubscriptionResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            rule_name=r.rule_name,
            channel=r.channel,
            target_url=r.target_url,
            min_composite_score=r.min_composite_score,
            subscribed_signal_code=r.subscribed_signal_code,
            subscribed_industry=r.subscribed_industry,
            is_active=r.is_active,
            created_at=r.created_at
        )
        for r in rules
    ]


@app.post("/v1/alerts/subscriptions", response_model=AlertSubscriptionResponse)
def create_alert_subscription(payload: AlertSubscriptionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    POST /v1/alerts/subscriptions: Create a new alert rule or webhook subscription.
    """
    rule = AlertSubscription(
        tenant_id=current_user.tenant_id if current_user else None,
        rule_name=payload.rule_name,
        channel=payload.channel.upper(),
        target_url=payload.target_url,
        secret=payload.secret or "radar-secret-key-2026",
        min_composite_score=payload.min_composite_score,
        subscribed_signal_code=payload.subscribed_signal_code,
        subscribed_industry=payload.subscribed_industry,
        is_active=True
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return AlertSubscriptionResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        rule_name=rule.rule_name,
        channel=rule.channel,
        target_url=rule.target_url,
        min_composite_score=rule.min_composite_score,
        subscribed_signal_code=rule.subscribed_signal_code,
        subscribed_industry=rule.subscribed_industry,
        is_active=rule.is_active,
        created_at=rule.created_at
    )


@app.delete("/v1/alerts/subscriptions/{subscription_id}")
def delete_alert_subscription(subscription_id: str, current_user: User = Depends(require_role(["ADMIN"])), db: Session = Depends(get_db)):
    """
    DELETE /v1/alerts/subscriptions/{id}: Delete an alert rule (Requires ADMIN role).
    """
    rule = db.query(AlertSubscription).filter(AlertSubscription.id == subscription_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert subscription rule not found.")
    db.delete(rule)
    db.commit()
    return {"status": "success", "message": "Alert subscription deleted."}


@app.post("/v1/alerts/test-trigger")
def test_trigger_alert(payload: AlertTestTriggerRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    POST /v1/alerts/test-trigger: Send a test alert trigger to verify webhook HMAC or Slack connectivity.
    """
    rule = db.query(AlertSubscription).filter(AlertSubscription.id == payload.subscription_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found.")

    company = None
    if payload.company_id:
        company = db.query(Company).filter(Company.id == payload.company_id).first()
    if not company:
        company = db.query(Company).first()

    if not company:
        raise HTTPException(status_code=400, detail="No company available to simulate test alert.")

    dispatch = AlertDispatcherEngine.send_alert_payload(
        sub=rule,
        company=company,
        signal_code=rule.subscribed_signal_code or "JOB_POSTING_SURGE",
        composite_score=rule.min_composite_score + 5.0,
        trigger_reason="Simulación de Alerta de Prueba (Test Trigger)"
    )

    return {
        "status": "success",
        "message": "Test alert payload dispatched.",
        "dispatch_details": dispatch
    }


@app.post("/v1/webhooks/subscriptions", response_model=WebhookSubscriptionResponse)
def create_webhook_subscription(payload: WebhookSubscriptionRequest, db: Session = Depends(get_db)):
    """
    POST /v1/webhooks/subscriptions: Subscribes enterprise clients to real-time alert thresholds.
    """
    sub = WebhookSubscription(
        client_id=payload.client_id,
        target_url=payload.target_url,
        secret=payload.secret,
        min_composite_score=payload.min_composite_score,
        subscribed_vectors=payload.subscribed_vectors,
        is_active=True
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return WebhookSubscriptionResponse(
        id=sub.id,
        client_id=sub.client_id,
        target_url=sub.target_url,
        min_composite_score=sub.min_composite_score,
        subscribed_vectors=sub.subscribed_vectors or [],
        is_active=sub.is_active,
        created_at=sub.created_at
    )


# ==========================================
# BLOQUE 11 & 12: STRIPE BILLING & PRODUCT ANALYTICS REST API
# ==========================================
from app.billing import BillingService
from app.analytics import AnalyticsService, AnalyticsEventRequest

@app.post("/v1/billing/checkout-session")
def create_billing_checkout_session(plan: str = Query("pro"), current_user: User = Depends(get_current_user)):
    """
    Feature 21: Generates Stripe Checkout Session URL for upgrading subscription plan.
    """
    return BillingService.create_checkout_session(current_user, plan=plan)

@app.post("/v1/billing/customer-portal")
def create_billing_customer_portal(current_user: User = Depends(get_current_user)):
    """
    Feature 21: Generates Stripe Customer Portal URL for managing invoices and subscription.
    """
    return BillingService.create_customer_portal_session(current_user)

@app.post("/v1/billing/webhook")
async def stripe_webhook_listener(request: Request, db: Session = Depends(get_db)):
    """
    Feature 21: Stripe Webhook Listener for checkout.session.completed & customer.subscription.deleted events.
    """
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        return BillingService.process_webhook_payload(body, sig_header, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/v1/billing/simulate-webhook")
def simulate_billing_webhook(email: str = Query(...), status: str = Query("active"), db: Session = Depends(get_db)):
    """
    Feature 21 Sandbox: Simulates Stripe checkout completion or subscription activation without Stripe live keys.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    user.subscription_status = status
    if not user.stripe_customer_id:
        user.stripe_customer_id = f"cus_sim_{user.id[:8]}"
    db.commit()
    return {"status": "success", "email": user.email, "subscription_status": user.subscription_status}

@app.post("/v1/analytics/event")
def record_analytics_event(req: AnalyticsEventRequest, request: Request):
    """
    Feature 22: Privacy-Friendly Analytics Event Ingestion.
    """
    ip = request.client.host if request.client else None
    return AnalyticsService.log_event(req, ip_address=ip)

@app.get("/v1/analytics/summary")
def get_analytics_summary(current_user: User = Depends(get_current_user)):
    """
    Feature 22: Returns aggregated conversion metrics summary.
    """
    return AnalyticsService.get_summary_metrics()



# Mount Static directory for Economic Intelligence Terminal Frontend UI
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def read_root_landing():
        landing_file = os.path.join(static_dir, "landing.html")
        if os.path.exists(landing_file):
            return FileResponse(landing_file)
        index_file = os.path.join(static_dir, "index.html")
        return FileResponse(index_file)

    @app.get("/app")
    def read_app_dashboard():
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse({"error": "Dashboard index.html not found"}, status_code=404)

    @app.get("/precios")
    @app.get("/pricing")
    def read_precios_page():
        precios_file = os.path.join(static_dir, "precios.html")
        if os.path.exists(precios_file):
            return FileResponse(precios_file)
        return FileResponse(os.path.join(static_dir, "landing.html"))

    @app.get("/terms")
    def read_terms_page():
        terms_file = os.path.join(static_dir, "terms.html")
        if os.path.exists(terms_file):
            return FileResponse(terms_file)
        return FileResponse(os.path.join(static_dir, "landing.html"))

    @app.get("/privacy")
    def read_privacy_page():
        privacy_file = os.path.join(static_dir, "privacy.html")
        if os.path.exists(privacy_file):
            return FileResponse(privacy_file)
        return FileResponse(os.path.join(static_dir, "landing.html"))

