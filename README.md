# OFANRADAR — Inteligencia Operativa de Mercado & Terminal B2B

Plataforma de inteligencia de mercado en tiempo real y terminal comercial B2B para la detección determinista de señales de intención corporativa (`growth_intent`, `hiring_intent`, `expansion_intent`, `technology_change_intent`, `financial_stress`).

---

## 🛠️ Arquitectura & Mejoras V2

### BLOQUE 1: Verificación, Auditoría & Refactorización
* **Esquema Relacional**: Tablas principales `companies`, `scrape_logs` (auditoría de duraciones en ms, códigos HTTP y reintentos) y `signals` (eventos con fecha, tipo e impacto numérico `score_impact`).
* **Scraper Resiliente (`app/scraper.py`)**: Implementación con política de **Exponential Backoff Retries** (hasta 3 reintentos) y manejo estricto de excepciones (timeouts, 404, 500) con registro de logs sin detener el bucle principal.
* **Motor de Intent Score Backend (`app/scoring.py`)**: Función aislada `recalculate_company_score(db, company_id, window_days=30)` basada en decaimiento matemático $w_i(t) = W_s \cdot C_i \cdot e^{-\lambda \cdot \Delta t}$, asegurando que un evento de hace 2 días tenga un peso superior a uno de hace 20 días.

---

### BLOQUE 2: Nuevas Funcionalidades

#### 1. Botón de Exportación a CSV (Quick Win)
* Endpoint `/api/export` (o `/v1/export`) para descargar la lista de empresas filtrada con sus puntuaciones de intención en un archivo CSV formateado.
* Botón en la barra lateral de la interfaz: `<button id="btn-export-csv">Exportar Lista a CSV</button>`.

#### 2. Diffing Semántico con IA (`app/ai_diffing.py`)
* Análisis de cambios en `<title>`, precios o páginas de servicio preparado para OpenAI `gpt-4o-mini` (con motor NLP de respaldo).
* Salida en JSON estructurado: `{"is_meaningful_change": boolean, "intent_impact": number, "summary": "string"}`. Filtra automáticamente cambios estéticos, typos o actualizaciones del año de copyright.

#### 3. Sistema de Alertas Push (Retención - `app/alert_worker.py`)
* Tabla `alert_subscriptions` para registrar criterios de suscripción de clientes (`min_composite_score`, país, sector, email).
* Script Worker semanal (`app/alert_worker.py` / `/v1/alerts/run-cron`) que evalúa qué empresas han superado los umbrales en los últimos 7 días y genera un informe de alerta simulado por consola y en el archivo `alerts_digest_latest.txt`.

#### 4. Integración de Registros Oficiales (`app/registry_connector.py`)
* Módulo de ingesta para fuentes oficiales (BORME, Registro Mercantil, OpenCorporates).
* Evento de alto impacto `REGISTRY_CHANGE` (ej. "Ampliación de capital +2.5M€", "Cambio de domicilio social") que recalcula la puntuación de intención en tiempo real.

---

## 🚀 Cómo Ejecutar Localmente

### 1. Iniciar el Servidor Business Radar V2
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Probar el Worker de Alertas Semanales (Cron Job)
```bash
python -m app.alert_worker
```

### 3. Acceso a la Interfaz Comercial Web
* **Terminal Business Radar**: `http://localhost:8000/`
