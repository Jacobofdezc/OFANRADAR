import uuid
import datetime
import time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Company, Signal, IntentSnapshot
from app.entity_resolution import resolve_canonical_company, normalize_domain
from app.enrichment import CompanyEnrichmentEngine
from app.scoring import compute_intent_for_signals
from app.ai_diffing import generate_executive_brief

# In-memory storage for background task statuses
TASKS_DB: Dict[str, Dict[str, Any]] = {}

def create_task(task_type: str, target: str) -> Dict[str, Any]:
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.utcnow().isoformat()
    task_data = {
        "task_id": task_id,
        "type": task_type,
        "target": target,
        "status": "PENDING",
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now
    }
    TASKS_DB[task_id] = task_data
    return task_data

def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    return TASKS_DB.get(task_id)

def run_async_scrape_task(task_id: str, target: str):
    """
    Background worker function for executing scrapers and AI diffing asynchronously.
    Avoids Vercel 10s-60s timeout by decoupling client HTTP response.
    """
    if task_id not in TASKS_DB:
        return

    TASKS_DB[task_id]["status"] = "PROCESSING"
    TASKS_DB[task_id]["progress"] = 25
    TASKS_DB[task_id]["updated_at"] = datetime.datetime.utcnow().isoformat()

    db = SessionLocal()
    try:
        # 1. Resolve or create target company
        company = resolve_canonical_company(db, target)
        if not company:
            clean_domain = normalize_domain(target)
            enriched = CompanyEnrichmentEngine.enrich_domain(clean_domain)
            domain_to_use = enriched["domain"]
            company = db.query(Company).filter(Company.domain == domain_to_use).first()
            if not company:
                company = Company(
                    canonical_name=enriched["canonical_name"],
                    legal_name=enriched["legal_name"],
                    domain=domain_to_use,
                    tax_id=f"B{abs(hash(domain_to_use)) % 89999999 + 10000000}",
                    tax_id_country="ES",
                    industry=enriched["industry"] or "Software & Servicios",
                    employee_range=enriched["employee_range"] or "20-100",
                    hq_country="ES",
                    hq_city=enriched["hq_city"] or "Madrid",
                    website_url=f"https://{domain_to_use}",
                    logo_url=enriched["logo_url"],
                    is_active=True
                )
                db.add(company)
                db.commit()
                db.refresh(company)

        TASKS_DB[task_id]["progress"] = 60

        # 2. Simulate CT logs & Web scraping signal capture
        new_sig = Signal(
            company_id=company.id,
            signal_type_code="TECH_STACK_MIGRATION",
            source="ASYNC_TASK_SCRAPER",
            confidence=0.94,
            detected_at=datetime.datetime.utcnow()
        )
        db.add(new_sig)
        db.commit()

        # 3. Recalculate intent scores & generate brief
        all_signals = db.query(Signal).filter(Signal.company_id == company.id).all()
        scores, composite, label, attribution, summary, action = compute_intent_for_signals(all_signals, window_days=90)
        
        snap = IntentSnapshot(
            company_id=company.id,
            window_days=90,
            growth_intent=scores["growth_intent"],
            hiring_intent=scores["hiring_intent"],
            expansion_intent=scores["expansion_intent"],
            technology_change_intent=scores["technology_change_intent"],
            financial_stress=scores["financial_stress"],
            composite_score=composite,
            confidence_score=0.94,
            primary_label=label,
            signal_count=len(all_signals),
            attribution_matrix=attribution,
            computed_at=datetime.datetime.utcnow()
        )
        db.add(snap)
        db.commit()

        TASKS_DB[task_id]["progress"] = 90
        brief = generate_executive_brief(company.id, db)

        TASKS_DB[task_id]["progress"] = 100
        TASKS_DB[task_id]["status"] = "COMPLETED"
        TASKS_DB[task_id]["result"] = {
            "company_id": company.id,
            "canonical_name": company.canonical_name,
            "domain": company.domain,
            "composite_score": composite,
            "primary_label": label,
            "signals_processed": len(all_signals),
            "executive_brief": brief
        }
        TASKS_DB[task_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
    except Exception as e:
        import traceback
        traceback.print_exc()
        TASKS_DB[task_id]["status"] = "FAILED"
        TASKS_DB[task_id]["error"] = str(e)
        TASKS_DB[task_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
    finally:
        db.close()
