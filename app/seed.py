import datetime
import random
from sqlalchemy.orm import Session
from app.database import Base, engine, SessionLocal
from app.models import Company, CompanyAlias, SignalType, Signal, IntentSnapshot
from app.config import SIGNAL_CATALOG
from app.scoring import compute_intent_for_signals


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Signal Types if missing
        for code, info in SIGNAL_CATALOG.items():
            st = db.query(SignalType).filter(SignalType.code == code).first()
            if not st:
                st = SignalType(
                    code=code,
                    name=info["name"],
                    vector_category=info["vector_category"],
                    base_weight=info["base_weight"],
                    half_life_days=info["half_life_days"],
                    description=info["description"],
                )
                db.add(st)
        db.commit()

        # Seed default Organization and Users if missing
        _seed_default_organization_and_users(db)

        # Check if companies already seeded
        if db.query(Company).count() > 0:
            print("Database already seeded with companies.")
            _seed_default_watchlists_if_missing(db)
            return

        now = datetime.datetime.utcnow()

        # 2. Company Profiles
        companies_data = [
            {
                "canonical_name": "Ibérica Logística & Freight S.L.",
                "legal_name": "Ibérica Logística & Freight Sociedad Limitada",
                "domain": "ibericalogistica.es",
                "tax_id": "B87654321",
                "tax_id_country": "ES",
                "industry": "Logistics & Supply Chain",
                "employee_range": "201-500",
                "hq_country": "ES",
                "hq_city": "Madrid",
                "hq_address": "Calle Gran Vía 48, 28013 Madrid",
                "website_url": "https://ibericalogistica.es",
                "linkedin_url": "https://linkedin.com/company/iberica-logistica",
                "signals": [
                    {"code": "REAL_ESTATE_FILING", "days_ago": 7, "source": "property_registry_madrid", "conf": 0.95},
                    {"code": "NEW_BRAND_DOMAIN", "days_ago": 11, "source": "whois_rdap", "conf": 0.90},
                    {"code": "DOM_PRICING_CHANGED", "days_ago": 18, "source": "dom_diff_engine", "conf": 0.85},
                    {"code": "JOB_POSTING_SURGE", "days_ago": 3, "source": "playwright_careers", "conf": 0.92},
                    {"code": "SOCIAL_ACTIVITY_SURGE", "days_ago": 24, "source": "linkedin_scraper", "conf": 0.88},
                    {"code": "TECH_STACK_MIGRATION", "days_ago": 14, "source": "dns_ct_logs", "conf": 0.85},
                ]
            },
            {
                "canonical_name": "TechScale Soluciones SaaS",
                "legal_name": "TechScale Soluciones Tecnológicas S.L.",
                "domain": "techscale.io",
                "tax_id": "B98765432",
                "tax_id_country": "ES",
                "industry": "Enterprise Software",
                "employee_range": "51-200",
                "hq_country": "ES",
                "hq_city": "Barcelona",
                "hq_address": "Avinguda Diagonal 120, 08018 Barcelona",
                "website_url": "https://techscale.io",
                "linkedin_url": "https://linkedin.com/company/techscale-io",
                "signals": [
                    {"code": "JOB_POSTING_SURGE", "days_ago": 5, "source": "careers_dom", "conf": 0.95},
                    {"code": "EXEC_ROLE_ADDED", "days_ago": 12, "source": "linkedin_exec_monitor", "conf": 0.90},
                    {"code": "DOM_PRICING_CHANGED", "days_ago": 10, "source": "dom_diff_engine", "conf": 0.92},
                    {"code": "TECH_STACK_MIGRATION", "days_ago": 2, "source": "dns_monitor", "conf": 0.88},
                ]
            },
            {
                "canonical_name": "Veloce Mobility S.r.l.",
                "legal_name": "Veloce Mobility Italia S.r.l.",
                "domain": "velocemobility.it",
                "tax_id": "IT12345678901",
                "tax_id_country": "IT",
                "industry": "Automotive & Fleet",
                "employee_range": "501-1000",
                "hq_country": "IT",
                "hq_city": "Milan",
                "hq_address": "Via Montenapoleone 8, 20121 Milano",
                "website_url": "https://velocemobility.it",
                "linkedin_url": "https://linkedin.com/company/veloce-mobility",
                "signals": [
                    {"code": "CREDIT_RATING_DOWNGRADE", "days_ago": 8, "source": "commercial_registry_it", "conf": 0.95},
                    {"code": "EMPLOYEE_RATING_DROP", "days_ago": 15, "source": "glassdoor_scraper", "conf": 0.85},
                ]
            },
            {
                "canonical_name": "Nordic Infra Systems AB",
                "legal_name": "Nordic Infrastructure Systems AB",
                "domain": "nordicinfra.se",
                "tax_id": "SE5561234567",
                "tax_id_country": "SE",
                "industry": "Clean Energy & Infra",
                "employee_range": "100-250",
                "hq_country": "SE",
                "hq_city": "Stockholm",
                "hq_address": "Kungsgatan 44, 111 35 Stockholm",
                "website_url": "https://nordicinfra.se",
                "linkedin_url": "https://linkedin.com/company/nordic-infra",
                "signals": [
                    {"code": "REAL_ESTATE_FILING", "days_ago": 2, "source": "se_property_register", "conf": 0.98},
                    {"code": "NEW_BRAND_DOMAIN", "days_ago": 6, "source": "whois_rdap", "conf": 0.94},
                    {"code": "EXEC_ROLE_ADDED", "days_ago": 20, "source": "linkedin_monitor", "conf": 0.88},
                ]
            },
            {
                "canonical_name": "Valencia BioPharma Tech",
                "legal_name": "Valencia BioPharma Innovations S.A.",
                "domain": "valenciabiopharma.com",
                "tax_id": "A46123987",
                "tax_id_country": "ES",
                "industry": "Biotechnology",
                "employee_range": "20-50",
                "hq_country": "ES",
                "hq_city": "Valencia",
                "hq_address": "Parc Científic Universitat de València, 46980 Paterna",
                "website_url": "https://valenciabiopharma.com",
                "linkedin_url": "https://linkedin.com/company/valencia-biopharma",
                "signals": [
                    {"code": "JOB_POSTING_SURGE", "days_ago": 4, "source": "playwright_careers", "conf": 0.90},
                    {"code": "EXEC_ROLE_ADDED", "days_ago": 19, "source": "linkedin_exec_monitor", "conf": 0.95},
                ]
            }
        ]

        for cdata in companies_data:
            sig_list = cdata.pop("signals")
            company = Company(**cdata)
            db.add(company)
            db.flush()

            # Add primary Alias
            alias = CompanyAlias(
                company_id=company.id,
                alias_name=company.canonical_name,
                alias_type="name",
                confidence_score=1.0
            )
            db.add(alias)

            created_signals = []
            for sig in sig_list:
                sig_date = now - datetime.timedelta(days=sig["days_ago"])
                s = Signal(
                    company_id=company.id,
                    signal_type_code=sig["code"],
                    source=sig["source"],
                    confidence=sig["conf"],
                    detected_at=sig_date,
                    raw_payload={"sample_raw": f"Detected event via {sig['source']}"},
                    extracted_attributes={"days_ago": sig["days_ago"]}
                )
                db.add(s)
                created_signals.append(s)
            
            db.flush()

            # Compute initial intent snapshot
            scores, composite, label, attribution, summary, action = compute_intent_for_signals(created_signals, window_days=90, current_time=now)
            snapshot = IntentSnapshot(
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
                signal_count=len(created_signals),
                attribution_matrix=attribution,
                computed_at=now
            )
            db.add(snapshot)

        db.commit()
        print("Successfully seeded Business Radar database with mid-market companies & 90-day signal streams!")

        # 3. Seed Default Watchlists if none exist
        _seed_default_watchlists_if_missing(db)

    finally:
        db.close()


def _seed_default_organization_and_users(db: Session):
    from app.models import Organization, User
    from app.auth import hash_password

    org = db.query(Organization).filter(Organization.slug == "acme-capital").first()
    if not org:
        org = Organization(
            id="tenant-acme-001",
            name="Acme Capital & Analytics",
            slug="acme-capital",
            plan_tier="ENTERPRISE"
        )
        db.add(org)
        db.flush()

    admin_user = db.query(User).filter(User.email == "admin@radar.com").first()
    if not admin_user:
        admin_user = User(
            tenant_id=org.id,
            email="admin@radar.com",
            hashed_password=hash_password("admin123"),
            full_name="Director de Inteligencia Comercial",
            role="ADMIN",
            subscription_status="active",
            trial_ends_at=datetime.datetime.utcnow() + datetime.timedelta(days=365),
            is_active=True
        )
        db.add(admin_user)

    analyst_user = db.query(User).filter(User.email == "analyst@radar.com").first()
    if not analyst_user:
        analyst_user = User(
            tenant_id=org.id,
            email="analyst@radar.com",
            hashed_password=hash_password("analyst123"),
            full_name="Analista Senior PE",
            role="ANALYST",
            subscription_status="trial",
            trial_ends_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
            is_active=True
        )
        db.add(analyst_user)

    db.commit()
    print("Successfully seeded default Organization & User accounts (admin@radar.com / analyst@radar.com)!")


def _seed_default_watchlists_if_missing(db: Session):
    from app.models import Watchlist, WatchlistCompany, Organization
    org = db.query(Organization).first()
    tenant_id = org.id if org else "tenant-acme-001"

    if db.query(Watchlist).count() == 0:
        w1 = Watchlist(tenant_id=tenant_id, name="🔥 Prospectos Calientes", description="Empresas con alta intención de compra y expansión inmediata", color="#ef4444")
        w2 = Watchlist(tenant_id=tenant_id, name="⚔️ Competidores Directos", description="Seguimiento de tecnología y contrataciones de rivales", color="#f59e0b")
        w3 = Watchlist(tenant_id=tenant_id, name="⚠️ Riesgo de Churn / Estrés", description="Empresas con señales de degradación o congelación", color="#10b981")
        db.add_all([w1, w2, w3])
        db.flush()

        # Attach some companies
        all_comps = db.query(Company).all()
        if len(all_comps) >= 2:
            db.add(WatchlistCompany(watchlist_id=w1.id, company_id=all_comps[0].id))
            db.add(WatchlistCompany(watchlist_id=w1.id, company_id=all_comps[1].id))
        if len(all_comps) >= 3:
            db.add(WatchlistCompany(watchlist_id=w2.id, company_id=all_comps[1].id))
            db.add(WatchlistCompany(watchlist_id=w2.id, company_id=all_comps[2].id))
        if len(all_comps) >= 4:
            db.add(WatchlistCompany(watchlist_id=w3.id, company_id=all_comps[2].id))
        db.commit()
        print("Successfully seeded default Watchlists!")


if __name__ == "__main__":
    seed_database()


