# 📡 **Resumen del Proyecto: Business Radar**

*Última actualización: 19 de Septiembre de 2026*

---

### 1. 🎯 **Visión General del Producto**
**Business Radar** es un **Terminal Web de Inteligencia Económica e Intención Comercial de Grado Institucional**. Su propósito es rastrear empresas del mercado mediano (*mid-market*) y transformar señales públicas no estructuradas (ofertas de empleo masivas, inscripciones en el Registro Mercantil/BORME, cambios en precios web, registros inmobiliarios y migraciones de tecnología) en **Puntuaciones Deterministas de Intención Comercial (Intent Scores de 0 a 100)**.

Permite a directores comerciales, analistas de Private Equity y equipos de banca corporativa identificar **"agujas en el pajar"** (oportunidades de expansión, riesgo de churn o necesidades de financiación) antes de que sean obvias para el mercado.

---

### 2. 🏗️ **Arquitectura y Stack Tecnológico**

```text
  🌐 Fuentes Públicas (Web, BORME, Careers, CT Logs)
             │
             ▼
  ⚡ Resilient Ingestion & Scraping (ScrapeLog Audit + Retries)
             │
             ▼
  🤖 Anti-Noise & AI Diff Engine (Filtro Cookies/Copyright + gpt-4o-mini)
             │
             ▼
  🧮 Exponential Decay Scoring Engine [W_s * C_i * exp(-lambda * delta_t)]
             │
             ▼
  🗄️ SQLite Database (radar.db) [Companies, Signals, Snapshots, Watchlists]
             │
             ▼
  🚀 FastAPI Backend REST Layer (/v1/companies, /v1/query, /v1/watchlists)
             │
             ▼
  💻 Terminal Web UI (HTML5, Glassmorphism, Theme Toggle, Chart.js, Sparklines)
```

* **Backend:** Python 3.13 + FastAPI (Servidor asíncrono Uvicorn) + SQLAlchemy ORM.
* **Base de Datos:** SQLite (`radar.db`) con modelos relacionales indexados para resiliencia y consultas en milisegundos.
* **Frontend:** HTML5, Vanilla CSS3 (Modo Oscuro/Claro tipo Bloomberg, diseño glassmorphism), JavaScript ES6 puro, Chart.js para gráficos radiales y gráficos Sparklines SVG dinámicos.
* **Capa de Inteligencia Artificial:** `AIDiffEngine` (gpt-4o-mini + motor anti-ruido) y `CompanyEnrichmentEngine` (Clearbit Logos + Autocomplete).

---

### 3. 🚀 **Funcionalidades Clave Implementadas (V1 a V3)**

#### 🧮 **A. Motor Matemático de Intención (Scoring Engine)**
* **Vectores de Intención:** `Expansion Intent`, `Hiring Intent`, `Growth Intent`, `Tech Stack Change` y `Financial Stress`.
* **Atenuación Exponencial:** Fórmula $w_i(t) = W_s \cdot C_i \cdot e^{-\lambda \Delta t}$, donde los eventos de hace 2 días ponderan significativamente más que los de hace 20 días.
* **Mapeo Saturado:** Puntuación global acotada mediante curva de saturación $100 \cdot (1 - e^{-\gamma S})$.

#### 🔎 **B. Búsqueda Avanzada y Filtros Multi-Variable (Experiencia Bloomberg - Feature 5)**
* **Filtros Combinados en Tiempo Real:** Por *Sector*, *País*, *Rango de Score Mínimo* y *Tipo de Evento Reciente (últimos 7 días)*.
* **Sincronización Bidireccional con URL:** Los parámetros se sincronizan dinámicamente con la barra del navegador (`?score=40&event=JOB_POSTING_SURGE&industry=Software`) para compartir o guardar búsquedas directamente.

#### ⭐ **C. Listas de Vigilancia ("Watchlists" - Feature 6)**
* **Persistencia Relacional:** Creación de listas personalizadas (*🔥 Prospectos Calientes*, *⚔️ Competidores Directos*, *⚠️ Riesgo de Churn*).
* **Score Promedio Agregado (`Avg Score`):** La barra lateral muestra el promedio ponderado de intención de las empresas miembros en tiempo real.
* **Acción en la Ficha de Empresa:** Menú desplegable para añadir/quitar empresas de una o varias listas al instante.

#### 📊 **D. Densidad Visual y Analítica Histórica (Bloque 4)**
* **Gráficos Sparkline SVG (Feature 7):** Cada tarjeta en el directorio incluye un micrográfico de tendencia de 30 días con el indicador de variación acumulada (ej. `↗ +60.6 pt`).
* **Sección "Por qué este Score" (Feature 8):** Desglose cualitativo y cuantitativo de las razones clave y eventos de mayor significación que justifican la puntuación.

#### 🧹 **E. Calidad de Ingesta, Anti-Ruido y Auto-Enriquecimiento (Bloque 5)**
* **Filtro Anti-Ruido (Feature 9):** `AIDiffEngine` limpia automáticamente frases de relleno (*política de cookies*, *aviso legal*, *términos de servicio*, *copyright 2025/2026* y reordenación de logos).
* **Auto-Enriquecimiento de Dominios (Feature 10):** Botón **"Auto-Enriquecer Dominio"** que extrae automáticamente logotipos oficiales (`Clearbit Logo API`), sector y tamaño de plantilla al introducir un dominio (ej. `shopify.com`).

#### 🔍 **F. Deep Dive y Fuentes Alternativas - El Valor del Dato (Bloque 6 - V4)**
* **Módulo de Tecnologías e Infraestructura Oculta (Feature 11):** `tech_profiler.py` (`TechProfilerEngine`) analiza registros DNS MX y cabeceras HTTP/scripts para detectar proveedores de email corporativo (Google Workspace, Microsoft 365), infraestructura cloud (AWS, Cloudflare), CRM (Salesforce, HubSpot), pagos (Stripe) y e-commerce (Shopify). Incluye cuadrícula visual interactiva de badges tecnológicos con nivel de convicción.
* **Catálogo de Señales Cualitativas Expandido (Feature 12):** Incorporación de señales avanzadas como `EXEC_TURNOVER_RISK` (dimisión/cambio de directivos) y `PRICING_MONETIZATION_FOCUS` (cambios en planes de precios/monetización).
* **Agente LLM Executive Brief (Feature 13):** Endpoint `/v1/companies/{id}/executive-brief` y tarjeta visual en el Dashboard que genera una síntesis ejecutiva estructurada en 3 párrafos (Fase de Crecimiento, Movimientos Tecnológicos, y Oportunidad Comercial Recomendada) sintetizados por un agente de inteligencia.

#### 🛡️ **G. Multi-Tenant, Permisos y Seguridad Enterprise (Bloque 7 - V4)**
* **Aislamiento por Tenant / Organización (Feature 14):** Nuevos modelos relacionales `Organization` y `User` con asignación de `tenant_id` en `Watchlist`. Garantiza aislamiento estricto de datos entre distintas entidades financieras u organizaciones SaaS.
* **Autenticación JWT y Roles RBAC (Feature 15):** Endpoints `/v1/auth/register`, `/v1/auth/token` y `/v1/auth/me` con tokens JWT firmados encriptados con PBKDF2-HMAC-SHA256. Soporta roles `ADMIN`, `ANALYST` y `VIEWER` con middleware de permisos y widget visual de usuario/organización en el navbar.

#### 🔔 **H. Motor de Alertas Proactivas y Webhooks Enterprise (Bloque 8 - V4)**
* **Motor de Reglas y Suscripción de Alertas (Feature 16):** Modelo `AlertSubscription` con filtrado por `tenant_id`, umbral de `min_composite_score`, código de señal activadora y sector. Permite crear reglas personalizadas por organización.
* **Integración Slack, Teams y Webhooks HMAC SHA-256 (Feature 17):** `alert_dispatcher.py` (`AlertDispatcherEngine`) formatea notificaciones automáticas para Slack Incoming Webhooks, Microsoft Teams Connector y Webhooks genericos firmados con cabecera `X-Radar-Signature` (HMAC SHA-256). Endpoints: `/v1/alerts/subscriptions` (GET, POST, DELETE) y `/v1/alerts/test-trigger` (Simulación de alertas en vivo).

#### 🐳 **I. Producción, Dockerization y Monitorización Enterprise (Bloque 9 - V4)**
* **Multi-Stage Dockerization (Feature 18):** `Dockerfile` multi-etapa optimizado en Python 3.13-slim con usuario de ejecución sin privilegios (`radaruser`), volúmenes persistentes y `docker-compose.yml` preconfigurado.
* **Diagnóstico Institucional Deep Health Check (Feature 19):** Endpoints `/api/health` y `/health/deep` con verificación de conectividad SQLite/ORM, conteo de empresas/señales activas, tiempo de actividad (*uptime*) y estado de motores IA/Alertas.
* **Exposición de Métricas Estándar Prometheus (Feature 20):** Endpoints `/metrics` y `/v1/metrics` en formato de texto plano Prometheus para monitorización institucional.

#### 🚀 **J. Escaparate Comercial PLG & Freemium Gating (Bloque 10 - V5)**
* **Landing Page Comercial (Feature 19):** Web pública comercial de alta conversión servida en `/` con Hero section, propuesta de valor, matriz de características, tabla de precios (Pro $99/mes e Institutional $499/mes) y modales de registro/login. Terminal Web movido a `/app`.
* **Lógica de Trial y Paywall Anti-Trampas (Feature 20):** Asignación automática de 7 días de Trial en `User` al registrarse. Sanitización estricta en el backend en FastAPI (redacción de scores a `None`, difuminado visual y retorno de `HTTP 402 Payment Required` en exportación CSV si la suscripción o trial expira).

#### 💳 **K. Sistema de Pagos con Stripe (Bloque 11 - V5)**
* **Integración de Suscripciones & Modo Sandbox (Feature 21):** Módulo `app/billing.py` con la SDK oficial `stripe` y soporte de simulación sandbox sin requerir claves activas en vivo inmediatamente.
* **Endpoints REST:** `/v1/billing/checkout-session` (generación de enlace de pago), `/v1/billing/customer-portal` (gestión de facturación y descargas) y `/v1/billing/webhook` (escucha de `checkout.session.completed` y `customer.subscription.deleted`).

#### 📊 **L. Páginas Legales y Analítica de Producto (Bloque 12 - V5)**
* **Páginas Legales (Feature 22):** Rutas estáticas `/terms` y `/privacy` con plantillas SaaS B2B de Términos de Servicio y Política de Privacidad.
* **Telemetría Respetuosa:** Tracker ligero de cliente `static/js/analytics.js` y servicio `app/analytics.py` con endpoints `/v1/analytics/event` y `/v1/analytics/summary` para la medición de eventos de conversión (`export_csv_click`, `add_to_watchlist_click`, `start_trial_click`).

---

### 4. 🗺️ **Estado del Roadmap V5 (Go-to-Market, Pagos y Onboarding)**

| Bloque | Descripción | Estado |
| :--- | :--- | :--- |
| **Bloque 10** | **El Escaparate y la Experiencia de Prueba (PLG)** (Landing Page en `/`, Dashboard en `/app`, 7-Day Trial, Paywall Anti-Trampas) | `[x] COMPLETADO` |
| **Bloque 11** | **Sistema de Pagos (Stripe Integration)** (Checkout Session, Webhook `checkout.session.completed`, Customer Portal, Sandbox Mode) | `[x] COMPLETADO` |
| **Bloque 12** | **Legal y Analítica Básica** (Páginas `/terms`, `/privacy`, Script de analítica respetuoso) | `[x] COMPLETADO` |



---

### 5. 📂 **Estructura del Proyecto**

```text
Radar/
├── PROJECT_SUMMARY.md       # Documentación viva y resumen ejecutivo del proyecto
├── app/
│   ├── main.py              # Endpoints API REST FastAPI (Empresas, Query, Watchlists, Enrich, Tech-Stack, Executive Brief)
│   ├── models.py            # Modelos ORM (Company, Signal, IntentSnapshot, Watchlist, CompanyTechStack)
│   ├── schemas.py           # Validadores y esquemas Pydantic
│   ├── tech_profiler.py     # Motor de detección de Stack Tecnológico e Infraestructura DNS/MX
│   ├── scoring.py           # Motor de puntuación y tendencias Sparklines de 30 días
│   ├── ai_diffing.py        # Motor de IA semántica, filtro anti-ruido y síntesis LLM Executive Brief
│   ├── enrichment.py        # Conector de auto-enriquecimiento de firmas y logotipos Clearbit
│   ├── scraper.py           # Scraper resiliente con retries y auditoría ScrapeLog
│   ├── entity_resolution.py # Resolución de entidades por NIF/CIF, dominio o alias
│   └── seed.py              # Datos iniciales y seeding de Watchlists por defecto
├── static/
│   ├── index.html           # Interfaz principal del Terminal Web (Executive Brief, Tech Stack Grid)
│   ├── css/style.css        # Sistema de diseño CSS Glassmorphism y temas Claro/Oscuro
│   └── js/app.js            # Lógica cliente (URL sync, Watchlists, Executive Brief, Tech Badges)
└── radar.db                 # Base de datos SQLite
```

---

### 🌐 **Acceso y Ejecución**
* **Terminal Web Principal:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Documentación Interactiva Swagger:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)

