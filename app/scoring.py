import math
import datetime
from typing import List, Dict, Tuple, Any
from app.config import SIGNAL_CATALOG, VECTOR_CATEGORIES, SATURATION_GAMMA, calculate_decay_lambda
from app.models import Signal, IntentSnapshot, Company


def compute_intent_for_signals(
    signals: List[Signal],
    window_days: int = 90,
    current_time: datetime.datetime = None
) -> Tuple[Dict[str, float], float, str, List[Dict[str, Any]]]:
    """
    Computes intent score vectors using signal exponential time decay:
    w_i(t) = W_s * C_i * exp(-lambda_s * delta_t)

    Returns:
    - vector_scores: Dict[str, float] (growth_intent, hiring_intent, expansion_intent, technology_change_intent, financial_stress)
    - composite_score: float (0-100)
    - primary_label: str
    - attribution_matrix: List[Dict[str, Any]]
    """
    if current_time is None:
        current_time = datetime.datetime.utcnow()

    # Raw score accumulators
    raw_vector_scores: Dict[str, float] = {cat: 0.0 for cat in VECTOR_CATEGORIES}
    attribution_matrix: List[Dict[str, Any]] = []

    cutoff_date = current_time - datetime.timedelta(days=window_days)

    for signal in signals:
        # Ignore signals outside window or in the future
        signal_time = signal.detected_at
        if signal_time < cutoff_date or signal_time > current_time:
            continue

        signal_code = signal.signal_type_code
        cat_info = SIGNAL_CATALOG.get(signal_code, {
            "name": signal_code,
            "vector_category": "growth_intent",
            "base_weight": 20.0,
            "half_life_days": 30,
            "description": "Generic Signal"
        })

        base_weight = float(cat_info["base_weight"])
        half_life_days = int(cat_info["half_life_days"])
        vector_category = cat_info["vector_category"]

        # Calculate time delta in days
        delta_seconds = (current_time - signal_time).total_seconds()
        delta_days = max(0.0, delta_seconds / 86400.0)

        # Decay parameter lambda
        decay_lambda = calculate_decay_lambda(half_life_days)

        # Exponential attenuation: w_i(t) = W_s * C_i * exp(-lambda * delta_t)
        confidence = float(signal.confidence) if signal.confidence else 1.0
        attenuated_weight = base_weight * confidence * math.exp(-decay_lambda * delta_days)

        if vector_category in raw_vector_scores:
            raw_vector_scores[vector_category] += attenuated_weight

        attribution_matrix.append({
            "signal_id": str(signal.id),
            "signal_code": signal_code,
            "signal_name": cat_info["name"],
            "vector_category": vector_category,
            "source": signal.source,
            "detected_at": signal_time.isoformat(),
            "age_days": round(delta_days, 2),
            "confidence": round(confidence, 2),
            "base_weight": base_weight,
            "half_life_days": half_life_days,
            "attenuated_weight": round(attenuated_weight, 2),
        })

    # Saturating score mapping: Score = 100 * (1 - exp(-gamma * Raw_Sum))
    vector_scores: Dict[str, float] = {}
    for cat in VECTOR_CATEGORIES:
        raw_val = raw_vector_scores[cat]
        scaled_val = 100.0 * (1.0 - math.exp(-SATURATION_GAMMA * raw_val))
        vector_scores[cat] = round(scaled_val, 2)

    # Composite Score calculation (Weighted combination)
    weights = {
        "growth_intent": 0.25,
        "hiring_intent": 0.25,
        "expansion_intent": 0.30,
        "technology_change_intent": 0.20,
    }
    # If financial stress is high, it adjusts composite
    growth_composite = sum(vector_scores[k] * weights[k] for k in weights)
    composite_score = round(growth_composite, 2)

    # Label classification & business summary
    primary_label, business_summary, recommended_action = generate_business_insights(vector_scores, attribution_matrix)

    return vector_scores, composite_score, primary_label, attribution_matrix, business_summary, recommended_action


def generate_business_insights(scores: Dict[str, float], attribution: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """
    Generates human-friendly Spanish deterministic intent labels, business summaries, and sales/banking recommendations.
    """
    stress = scores.get("financial_stress", 0)
    expansion = scores.get("expansion_intent", 0)
    hiring = scores.get("hiring_intent", 0)
    growth = scores.get("growth_intent", 0)
    tech = scores.get("technology_change_intent", 0)

    if stress >= 60:
        label = "⚠️ Alerta de Inestabilidad Financiera y Reestructuración"
        summary = "Se han detectado advertencias en registros mercantiles o caídas severas en valoraciones de empleados. Indicios de necesidad de refinanciación o ajuste presupuestario."
        action = "Prioridad para equipos de reestructuración, asesoría legal o servicios de optimización de costes."

    elif expansion >= 75 and hiring >= 60:
        label = "🚀 Expansión Regional Agresiva (Operaciones y Tecnología)"
        summary = f"Gran aceleración detectada ({len(attribution)} eventos recientes): Registro de nuevas sedes comerciales, subdominios de producto y búsqueda intensiva de talento operativo."
        action = "Alta prioridad para Crédito Corporativo, Real Estate Comercial y Venta Enterprise de software operacional."

    elif expansion >= 70:
        label = "🏢 Expansión de Superficie Física y Nuevos Mercados"
        summary = "Inscripción de nuevos inmuebles o dominios de marca detectada en los últimos 30 días. La empresa está preparando su desembarco en una nueva región."
        action = "Contactar con el departamento de Expansión o Dirección Inmobiliaria Corporativa."

    elif hiring >= 75:
        label = "💼 Crecimiento Acelerado en Contratación de Personal"
        summary = "Oleada de ofertas de empleo publicadas en canales de carrera y LinkedIn en roles clave de tecnología, ventas y gestión."
        action = "Excelente oportunidad para proveedores de RRHH, Payroll, beneficios corporativos y licencias SaaS."

    elif tech >= 70:
        label = "⚡ Transformación Digital y Cambio de Modelo de Precios"
        summary = "Modificaciones estructurales en las páginas `/pricing` y `/services`, así como alta de subdominios Cloud/AWS/Salesforce."
        action = "Momento oportuno para ofrecer servicios de integración de software, migración Cloud o consultoría tecnológica."

    elif growth >= 60:
        label = "📈 Aumento de Actividad Ejecutiva y Presencia de Marca"
        summary = "Nuevos nombramientos en el equipo directivo (C-Suite) y alta frecuencia de notas de prensa y actividad institucional."
        action = "Ideal para banca de inversión, fondos de capital privado y servicios de relaciones públicas/consultoría."

    else:
        label = "🟢 Actividad Estable / Mantener Seguimiento"
        summary = "Patrón de actividad dentro de parámetros normales sin picos extraordinarios de expansión o contratación."
        action = "Mantener en radar de seguimiento automatizado con alertas semanales."

    return label, summary, action


def recalculate_company_score(db: Any, company_id: str, window_days: int = 30) -> IntentSnapshot:
    """
    Isolated backend engine service.
    Queries all signals for company_id, calculates exponential time-decay attenuation over
    the last 30 days (where a 2-day-old event weighs significantly more than a 20-day-old event),
    persists a new IntentSnapshot to DB, and returns the snapshot.
    """
    signals = (
        db.query(Signal)
        .filter(Signal.company_id == company_id)
        .order_by(Signal.detected_at.desc())
        .all()
    )

    now = datetime.datetime.utcnow()
    scores, composite, label, attribution, summary, action = compute_intent_for_signals(
        signals=signals,
        window_days=window_days,
        current_time=now
    )

    snapshot = IntentSnapshot(
        company_id=company_id,
        window_days=window_days,
        growth_intent=scores["growth_intent"],
        hiring_intent=scores["hiring_intent"],
        expansion_intent=scores["expansion_intent"],
        technology_change_intent=scores["technology_change_intent"],
        financial_stress=scores["financial_stress"],
        composite_score=composite,
        confidence_score=0.95,
        primary_label=label,
        signal_count=len(signals),
        attribution_matrix=attribution,
        computed_at=now
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def compute_30day_sparkline_history(signals: List[Signal], current_time: datetime.datetime = None) -> Tuple[List[float], float]:
    """
    Computes a 7-point sliding historical Intent Score trend over the last 30 days
    (t-30d, t-25d, t-20d, t-15d, t-10d, t-5d, t-0d) for rendering sparklines and calculating 30-day delta changes.
    """
    if current_time is None:
        current_time = datetime.datetime.utcnow()

    points: List[float] = []
    days_offsets = [30, 25, 20, 15, 10, 5, 0]

    for offset in days_offsets:
        point_time = current_time - datetime.timedelta(days=offset)
        # Filter signals detected on or before point_time
        historical_signals = [s for s in signals if s.detected_at <= point_time]
        _, composite, _, _, _, _ = compute_intent_for_signals(
            signals=historical_signals,
            window_days=90,
            current_time=point_time
        )
        points.append(round(composite, 1))

    score_change_30d = round(points[-1] - points[0], 1)
    return points, score_change_30d



