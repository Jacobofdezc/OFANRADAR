import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Company, Signal, SignalType
from app.entity_resolution import resolve_canonical_company
from app.scoring import recalculate_company_score


class OfficialRegistryConnector:
    """
    Official Corporate Registry Connector (BORME / OpenCorporates / Registro Mercantil).
    Simulates or connects to official legal filing feeds to ingest high-conviction
    `REGISTRY_CHANGE` events (e.g. Capital Increase, HQ Address Change, Executive Appointments).
    """

    @staticmethod
    def ensure_registry_signal_type(db: Session):
        """
        Ensures REGISTRY_CHANGE is seeded in signal_types table.
        """
        st = db.query(SignalType).filter(SignalType.code == "REGISTRY_CHANGE").first()
        if not st:
            st = SignalType(
                code="REGISTRY_CHANGE",
                name="Inscripción en Registro Mercantil / BORME",
                vector_category="expansion_intent",
                base_weight=60.0,
                half_life_days=90,
                description="Modificación oficial registrada (Ampliación de capital, cambio de domicilio, nombramiento legal)"
            )
            db.add(st)
            db.commit()

    @staticmethod
    def ingest_official_filing(
        db: Session,
        company_identifier: str,
        filing_type: str,
        description: str,
        filing_date: Optional[datetime.datetime] = None,
        source: str = "borme_oficial_es"
    ) -> Dict[str, Any]:
        """
        Ingests a REGISTRY_CHANGE filing into the target company's event stream
        and recalculates rolling intent scores live.
        """
        OfficialRegistryConnector.ensure_registry_signal_type(db)
        company = resolve_canonical_company(db, company_identifier)

        if not company:
            return {
                "success": False,
                "message": f"Empresa '{company_identifier}' no encontrada en el sistema."
            }

        detected_at = filing_date or datetime.datetime.utcnow()

        # Ingest high-impact REGISTRY_CHANGE signal
        signal = Signal(
            company_id=company.id,
            signal_type_code="REGISTRY_CHANGE",
            source=source,
            confidence=1.00,  # Official legal filings have 100% confidence
            score_impact=60.00,
            raw_payload={
                "filing_type": filing_type,
                "description": description,
                "source_registry": source
            },
            extracted_attributes={
                "filing_type": filing_type,
                "description": description
            },
            detected_at=detected_at
        )
        db.add(signal)
        db.commit()

        # Recalculate Intent Score live (30-day window with time decay)
        snapshot = recalculate_company_score(db, company.id, window_days=30)

        return {
            "success": True,
            "company_id": company.id,
            "company_name": company.canonical_name,
            "filing_type": filing_type,
            "description": description,
            "new_composite_score": snapshot.composite_score,
            "primary_label": snapshot.primary_label,
            "business_summary": snapshot.attribution_matrix
        }
