import datetime
import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Company, IntentSnapshot, AlertSubscription


def run_weekly_alert_worker(output_file: str = "alerts_digest_latest.txt") -> Dict[str, Any]:
    """
    Weekly Push Alert Cron Worker.
    Evaluates active subscriptions against companies whose composite intent score exceeded
    defined threshold levels in the last 7 days.
    Generates a clean email digest printed to console and written to `alerts_digest_latest.txt`.
    """
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        now = datetime.datetime.utcnow()
        seven_days_ago = now - datetime.timedelta(days=7)

        # 1. Fetch active alert subscriptions or create seed subscription if empty
        subscriptions = db.query(AlertSubscription).filter(AlertSubscription.is_active == True).all()
        if not subscriptions:
            seed_sub = AlertSubscription(
                client_name="Director de Inversiones - Capital & Growth",
                target_email="inversiones@capitalgrowth.es",
                min_composite_score=50.0,
                subscribed_industry=None,
                subscribed_country="ES",
                is_active=True
            )
            db.add(seed_sub)
            db.commit()
            db.refresh(seed_sub)
            subscriptions = [seed_sub]

        digest_lines = []
        digest_lines.append("================================================================================")
        digest_lines.append("BUSINESS RADAR - RESUMEN SEMANAL DE ALERTAS DE INTENCIÓN DE MERCADO")
        digest_lines.append(f"Fecha de Generación: {now.strftime('%d/%m/%Y %H:%M:%S UTC')}")
        digest_lines.append("================================================================================\n")

        total_alerts_sent = 0

        for sub in subscriptions:
            # Query companies with latest snapshots in last 7 days exceeding min_composite_score
            subq = (
                db.query(
                    IntentSnapshot.company_id,
                    IntentSnapshot.composite_score,
                    IntentSnapshot.primary_label,
                    IntentSnapshot.computed_at
                )
                .filter(
                    IntentSnapshot.composite_score >= sub.min_composite_score,
                    IntentSnapshot.computed_at >= seven_days_ago
                )
                .order_by(IntentSnapshot.company_id, IntentSnapshot.computed_at.desc())
                .distinct(IntentSnapshot.company_id)
                .subquery()
            )

            query = db.query(Company, subq).join(subq, Company.id == subq.c.company_id)
            if sub.subscribed_country:
                query = query.filter(Company.hq_country == sub.subscribed_country.upper())
            if sub.subscribed_industry:
                query = query.filter(Company.industry.ilike(f"%{sub.subscribed_industry}%"))

            matches = query.all()

            digest_lines.append(f"📩 DESTINATARIO: {sub.client_name} <{sub.target_email}>")
            digest_lines.append(f"   Criterios de Alerta: Intent Score >= {sub.min_composite_score} | País: {sub.subscribed_country or 'Todos'}")
            digest_lines.append(f"   Resultados Detectados: {len(matches)} empresas con alta intención\n")

            if matches:
                for company, snap_id, comp_score, label, comp_at in matches:
                    total_alerts_sent += 1
                    digest_lines.append(f"   • {company.canonical_name} ({company.domain})")
                    digest_lines.append(f"     - Intent Score: {comp_score}/100")
                    digest_lines.append(f"     - Diagnóstico: {label}")
                    digest_lines.append(f"     - CIF/NIF: {company.tax_id or 'N/A'} | Sede: {company.hq_city or 'N/A'}, {company.hq_country}")
                    digest_lines.append("")
            else:
                digest_lines.append("   (Sin alertas nuevas esta semana para este criterio)\n")

            digest_lines.append("--------------------------------------------------------------------------------\n")

        digest_content = "\n".join(digest_lines)
        try:
            print(digest_content)
        except Exception:
            pass

        # Write to file (simulating email delivery digest)
        abs_output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), output_file)
        with open(abs_output_path, "w", encoding="utf-8") as f:
            f.write(digest_content)

        return {
            "status": "success",
            "timestamp": now.isoformat(),
            "subscriptions_evaluated": len(subscriptions),
            "total_alerts_triggered": total_alerts_sent,
            "digest_file": abs_output_path
        }

    finally:
        db.close()


if __name__ == "__main__":
    run_weekly_alert_worker()
