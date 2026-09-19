import os
import json
import re
import datetime
import urllib.request
from typing import Dict, Any, Tuple


class AIDiffEngine:
    """
    AI-Powered Semantic Diffing & Anti-Noise Deduplication Engine (Feature 9).
    Filters out footer copyright updates, cookie policy changes, legal disclaimers, and logo reorderings.
    """

    NOISE_KEYWORDS = [
        "política de cookies", "politica de cookies", "términos de servicio", "terminos de servicio",
        "aviso legal", "copyright", "todos los derechos reservados", "all rights reserved",
        "privacy policy", "cookies policy", "derechos reservados", "gdpr", "rgpd",
        "términos y condiciones", "terminos y condiciones", "aviso de privacidad"
    ]

    SYSTEM_PROMPT = (
        "You are an expert B2B Corporate Intelligence AI analyst. Analyze the following BEFORE and AFTER text "
        "extracted from a company's web page (title, pricing page, or service page). "
        "Determine if the change represents a meaningful business intent signal (e.g., pricing model change, "
        "new product line launch, enterprise tier addition) vs. dynamic fluff, typos, or copyright year updates. "
        "Respond STRICTLY in JSON format matching this schema:\n"
        "{\n"
        '  "is_meaningful_change": boolean,\n'
        '  "intent_impact": number (0-100),\n'
        '  "summary": "string in Spanish describing the business impact"\n'
        "}"
    )

    @staticmethod
    def clean_noise_text(text: str) -> str:
        """
        Strips out legal disclaimers, cookie banners, copyright years, and normalizes image/logo orders.
        """
        if not text:
            return ""
        
        cleaned = text.lower()
        # Remove copyright years e.g., 2024, 2025, 2026, 2027
        cleaned = re.sub(r'©?\s*(202[0-9])', '', cleaned)

        # Remove image tag order noise e.g., <img ...>
        cleaned = re.sub(r'<img[^>]*>', '[logo]', cleaned)

        # Remove noise phrases
        for noise in AIDiffEngine.NOISE_KEYWORDS:
            cleaned = cleaned.replace(noise, '')

        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @classmethod
    def analyze_semantic_diff(cls, old_text: str, new_text: str, page_type: str = "pricing") -> Dict[str, Any]:
        """
        Analyzes old_text vs new_text after stripping noise and checking strict deduplication.
        """
        clean_old = cls.clean_noise_text(old_text)
        clean_new = cls.clean_noise_text(new_text)

        # Feature 9: Anti-noise deduplication check
        if clean_old == clean_new:
            return {
                "is_meaningful_change": False,
                "intent_impact": 0.0,
                "summary": "Ignorado (Anti-Ruido): Cambio estético de copyright, aviso de cookies o reordenación de logos sin impacto estratégico."
            }

        openai_key = os.getenv("OPENAI_API_KEY")

        if openai_key:
            try:
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": cls.SYSTEM_PROMPT},
                        {"role": "user", "content": f"PAGE TYPE: {page_type}\nBEFORE TEXT:\n{old_text[:1500]}\n\nAFTER TEXT:\n{new_text[:1500]}"}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }

                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json"
                    },
                    data=json.dumps(payload).encode('utf-8')
                )

                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    res_json = json.loads(resp.read().decode('utf-8'))
                    content = res_json['choices'][0]['message']['content']
                    parsed = json.loads(content)
                    return {
                        "is_meaningful_change": bool(parsed.get("is_meaningful_change", True)),
                        "intent_impact": float(parsed.get("intent_impact", 30.0)),
                        "summary": str(parsed.get("summary", "Cambio detectado mediante análisis de IA gpt-4o-mini."))
                    }

            except Exception as e:
                print(f"[WARN] OpenAI API call failed ({e}), falling back to deterministic AI engine.")

        # Fallback Deterministic NLP Engine
        return cls._deterministic_fallback_diff(old_text, new_text, page_type)

    @classmethod
    def _deterministic_fallback_diff(cls, old_text: str, new_text: str, page_type: str) -> Dict[str, Any]:
        """
        Rule-based NLP fallback engine with anti-noise keyword filter.
        """
        clean_old = cls.clean_noise_text(old_text)
        clean_new = cls.clean_noise_text(new_text)

        old_words = set(re.findall(r'\w+', clean_old))
        new_words = set(re.findall(r'\w+', clean_new))

        added_words = new_words - old_words

        ignore_keywords = {'2024', '2025', '2026', 'copyright', 'rights', 'reserved', 'cookie', 'csrf', 'logo'}
        meaningful_added = {w for w in added_words if w not in ignore_keywords and len(w) > 2}

        if not meaningful_added:
            return {
                "is_meaningful_change": False,
                "intent_impact": 0.0,
                "summary": "Ignorado (Anti-Ruido): Cambio estético menor o actualización de fecha/cookies (sin impacto estratégico)."
            }

        # Pricing or Tier Expansion Signals
        pricing_keywords = {'pricing', 'precio', 'tarifa', 'enterprise', 'plan', 'mes', 'year', 'cost', 'quote', '499', '999'}
        if any(w in meaningful_added for w in pricing_keywords) or 'pricing' in page_type.lower():
            return {
                "is_meaningful_change": True,
                "intent_impact": 45.0,
                "summary": f"Modificación sustancial detectada en la estructura de precios o tarifas web ({len(meaningful_added)} términos clave)."
            }

        # Title / Services Change
        if 'title' in page_type.lower() or any(w in meaningful_added for w in {'servicio', 'plataforma', 'solución', 'api', 'expansion'}):
            return {
                "is_meaningful_change": True,
                "intent_impact": 35.0,
                "summary": "Actualización de posicionamiento estratégico o lanzamiento de nueva línea de servicios."
            }

        return {
            "is_meaningful_change": True,
            "intent_impact": 20.0,
            "summary": "Actualización de contenido general en el sitio web de la empresa."
        }


def generate_executive_brief(company_id: str, db: Any) -> Dict[str, Any]:
    """
    Feature 13: Executive Brief Agent (LLM Institutional Summarization).
    Synthesizes deep alternative data (tech stack, executive turnover, BORME filings, intent scores)
    into a 3-paragraph executive summary tailored for sales directors & PE analysts.
    """
    from app.models import Company, IntentSnapshot, Signal, CompanyTechStack

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"error": "Company entity not found"}

    snapshot = (
        db.query(IntentSnapshot)
        .filter(IntentSnapshot.company_id == company.id)
        .order_by(IntentSnapshot.computed_at.desc())
        .first()
    )

    tech_entries = db.query(CompanyTechStack).filter(CompanyTechStack.company_id == company.id).all()
    signals = db.query(Signal).filter(Signal.company_id == company.id).order_by(Signal.detected_at.desc()).all()

    tech_names = [t.tech_name for t in tech_entries] if tech_entries else ["Herramientas SaaS Estándar"]
    score = round(snapshot.composite_score, 1) if snapshot else 0.0
    label = snapshot.primary_label if snapshot else "Sin clasificar"
    sig_count = len(signals)

    # Paragraph 1: Growth & Operational Phase
    p1 = (
        f"{company.canonical_name} ({company.industry or 'Sector General'}, {company.hq_city or 'Sede Central'}, {company.hq_country}) "
        f"registra una puntuación global de intención de {score}/100, etiquetada como '{label}'. "
        f"El volumen de captura de datos muestra {sig_count} eventos significativos en la ventana móvil de 90 días, "
        f"reflejando un nivel de actividad corporativa constante en sus operaciones principales."
    )

    # Paragraph 2: Technology Movements & Vendor Dependency
    tech_str = ", ".join(tech_names[:4]) if tech_names else "infraestructura web estándar"
    p2 = (
        f"En el plano tecnológico e infraestructura (Tech Stack & Vendor Dependency), la empresa opera principalmente con {tech_str}. "
        f"Se observan patrones de madurez digital preparados para escalabilidad operativa, con baja tolerancia a interrupciones y "
        f"potencial necesidad de integración de sistemas adicionales para optimizar su embudo comercial."
    )

    # Paragraph 3: Commercial Opportunity & Strategic Recommendation
    p3 = (
        f"Oportunidad Comercial Estratégica: Dado el nivel de intención actual ({score}/100) y las señales de mercado recientes, "
        f"se recomienda desplegar una aproximación consultiva centrada en la optimización de procesos y expansión de capacidad. "
        f"Prioridad alta para directores de cuenta Enterprise y equipos de soluciones corporativas."
    )

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            prompt = (
                f"Genera un informe ejecutivo institucional de 3 párrafos en español sobre la empresa '{company.canonical_name}'. "
                f"DATOS: Sector: {company.industry}, Score Intención: {score}/100 ({label}), Stack Tecnológico: {tech_str}, Eventos: {sig_count}.\n"
                f"Párrafo 1: Fase de crecimiento/riesgo operativo.\n"
                f"Párrafo 2: Movimientos tecnológicos y dependencia de proveedores.\n"
                f"Párrafo 3: Oportunidad comercial encubierta y recomendación de venta.\n"
                f"Responde estrictamente en JSON con claves: 'paragraph_1', 'paragraph_2', 'paragraph_3'."
            )
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                data=json.dumps(payload).encode('utf-8')
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                res_json = json.loads(resp.read().decode('utf-8'))
                parsed = json.loads(res_json['choices'][0]['message']['content'])
                p1 = parsed.get("paragraph_1", p1)
                p2 = parsed.get("paragraph_2", p2)
                p3 = parsed.get("paragraph_3", p3)
        except Exception as e:
            print(f"[WARN] OpenAI brief generation fallback used: {e}")

    return {
        "company_id": company.id,
        "company_name": company.canonical_name,
        "composite_score": score,
        "primary_label": label,
        "executive_brief": {
            "growth_phase": p1,
            "tech_movements": p2,
            "commercial_opportunity": p3
        },
        "generated_at": datetime.datetime.utcnow().isoformat()
    }


