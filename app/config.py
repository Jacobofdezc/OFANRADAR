import math
from typing import Dict, Any

# Vector Categories
VECTOR_CATEGORIES = [
    "growth_intent",
    "hiring_intent",
    "expansion_intent",
    "technology_change_intent",
    "financial_stress",
]

# Signal Definitions: Base Weight (W_s), Half Life in Days (tau_s), Default Category
SIGNAL_CATALOG: Dict[str, Dict[str, Any]] = {
    "JOB_POSTING_SURGE": {
        "name": "Hiring Surge (>5 positions)",
        "vector_category": "hiring_intent",
        "base_weight": 35.0,
        "half_life_days": 30,
        "description": "Surge in operational and engineering job openings",
    },
    "EXEC_ROLE_ADDED": {
        "name": "Executive Role Addition (C-Suite/VP)",
        "vector_category": "growth_intent",
        "base_weight": 40.0,
        "half_life_days": 60,
        "description": "Key executive hire identified via LinkedIn/Registry",
    },
    "DOM_PRICING_CHANGED": {
        "name": "Pricing Page DOM Structure Change",
        "vector_category": "technology_change_intent",
        "base_weight": 30.0,
        "half_life_days": 30,
        "description": "Major update to pricing or tiering structure",
    },
    "NEW_BRAND_DOMAIN": {
        "name": "New Brand/Product Domain Registered",
        "vector_category": "expansion_intent",
        "base_weight": 45.0,
        "half_life_days": 90,
        "description": "WHOIS/DNS activation of secondary product domain",
    },
    "REAL_ESTATE_FILING": {
        "name": "Commercial Property Lease/Purchase Registry",
        "vector_category": "expansion_intent",
        "base_weight": 50.0,
        "half_life_days": 90,
        "description": "Property registry record for new regional office",
    },
    "TECH_STACK_MIGRATION": {
        "name": "New Cloud/SaaS Subdomain DNS Activation",
        "vector_category": "technology_change_intent",
        "base_weight": 25.0,
        "half_life_days": 30,
        "description": "Detection of Salesforce, Hubspot, AWS DNS records",
    },
    "SOCIAL_ACTIVITY_SURGE": {
        "name": "Executive Social Posting Velocity Surge",
        "vector_category": "growth_intent",
        "base_weight": 15.0,
        "half_life_days": 7,
        "description": "300%+ increase in executive LinkedIn posting activity",
    },
    "CREDIT_RATING_DOWNGRADE": {
        "name": "Registry Financial Distress Warning",
        "vector_category": "financial_stress",
        "base_weight": 65.0,
        "half_life_days": 90,
        "description": "Official financial filing indication of liquidity stress",
    },
    "EMPLOYEE_RATING_DROP": {
        "name": "Glassdoor/Employee Review Drop Spike",
        "vector_category": "financial_stress",
        "base_weight": 30.0,
        "half_life_days": 30,
        "description": "Spike in negative employee sentiment reviews",
    },
    "EXEC_TURNOVER_RISK": {
        "name": "Rotación Directiva C-Level (Riesgo Operativo)",
        "vector_category": "financial_stress",
        "base_weight": 45.0,
        "half_life_days": 60,
        "description": "Desaparición o reemplazo rápido de perfiles C-Level (CFO/CTO/VP)",
    },
    "PRICING_MONETIZATION_FOCUS": {
        "name": "Enfoque en Monetización & Margen Comercial",
        "vector_category": "growth_intent",
        "base_weight": 35.0,
        "half_life_days": 30,
        "description": "Eliminación de planes gratuitos o subida de precios en planes Enterprise",
    },
    "REGISTRY_CHANGE": {
        "name": "Inscripción en Registro Mercantil / BORME",
        "vector_category": "expansion_intent",
        "base_weight": 40.0,
        "half_life_days": 90,
        "description": "Ampliación de capital, nombramientos o cambio de domicilio social en BORME",
    },
}

# Saturation scaling gamma factor for Score = 100 * (1 - exp(-gamma * Sum_W))
SATURATION_GAMMA = 0.025


def calculate_decay_lambda(half_life_days: int) -> float:
    """
    Computes the decay constant lambda = ln(2) / tau
    """
    if half_life_days <= 0:
        return 0.0
    return math.log(2) / float(half_life_days)
