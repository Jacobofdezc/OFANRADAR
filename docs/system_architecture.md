# Business Radar & Company Intent API - System Architecture Blueprint

## 1. End-to-End Event-Driven Architecture

```
                                  DATA INGESTION VECTORS
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ Headcount & Talent  │  │ Footprint & WHOIS   │  │ Web & Pricing DOM   │  │ PR & Social Velocity│
│ (LinkedIn, Careers) │  │ (DNS, SSL, Registry)│  │ (Pricing, Services) │  │ (Glassdoor, News)   │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │                        │
           └────────────────────────┴───────────┬────────────┴────────────────────────┘
                                                │
                                                ▼
                             ┌─────────────────────────────────────┐
                             │    Distributed Collector Cluster    │
                             │  (Playwright, Anti-Ban & Proxies)   │
                             └──────────────────┬──────────────────┘
                                                │ Raw HTML / JSON Payload
                                                ▼
                             ┌─────────────────────────────────────┐
                             │       Semantic & DOM Diff Engine    │
                             │   (Structural Noise Stripper & AST) │
                             └──────────────────┬──────────────────┘
                                                │ Delta Events
                                                ▼
                             ┌─────────────────────────────────────┐
                             │     Canonical Entity Resolution     │
                             │ (CIF/NIF, Domains, Levenshtein, ML) │
                             └──────────────────┬──────────────────┘
                                                │ Canonical company_id + Event
                                                ▼
                             ┌─────────────────────────────────────┐
                             │      Apache Kafka / Redpanda        │
                             │      (Topic: raw-company-signals)   │
                             └──────────────────┬──────────────────┘
                                                │
                      ┌─────────────────────────┴─────────────────────────┐
                      ▼                                                   ▼
       ┌─────────────────────────────┐                     ┌─────────────────────────────┐
       │ Primary Time-Series Store   │                     │      Entity Signal Graph    │
       │ (ClickHouse / TimescaleDB)  │                     │  (Neo4j / PostgreSQL Graph) │
       └──────────────┬──────────────┘                     └──────────────┬──────────────┘
                      │                                                   │
                      └─────────────────────────┬─────────────────────────┘
                                                │
                                                ▼
                             ┌─────────────────────────────────────┐
                             │    Composite Intent Scoring Engine  │
                             │   (Exponential Time Decay e^-λt)    │
                             └──────────────────┬──────────────────┘
                                                │ Calculated Intent Snapshots
                                                ▼
                             ┌─────────────────────────────────────┐
                             │  PostgreSQL Metadata & Intent Store │
                             │  + Redis Hot Cache (5 min TTL)      │
                             └──────────────────┬──────────────────┘
                                                │
                      ┌─────────────────────────┴─────────────────────────┐
                      ▼                                                   ▼
       ┌─────────────────────────────┐                     ┌─────────────────────────────┐
       │     Company Intent API      │                     │ Webhook Dispatcher Engine   │
       │ (FastAPI REST & GraphQL)    │                     │ (Alert Threshold Triggers)  │
       └─────────────────────────────┘                     └─────────────────────────────┘
```

---

## 2. Ingestion & Collector Subsystem Architecture

### Distributed Polling & Web Scraping (Playwright Cluster)
* **Stealth & Evasion**: Scrapers leverage `playwright-extra` with `puppeteer-extra-plugin-stealth` equivalents, rotating residential proxy IPs (smart proxy router), spoofed TLS fingerprints (JA3/JA4 evasion), and randomized viewport / user-agent signatures.
* **Target Scheduling**: Scaled via a Redis-backed priority queue (Celery / Temporal). High-value target companies (e.g. watchlist mid-market firms) are checked every 6–24 hours; baseline target companies every 48–72 hours.
* **Deduplication**: SHA-256 content hashing at the raw HTML/DOM layer ensures duplicate web pages bypass processing.

### Multi-Attribute Entity Resolution Engine
Entities are messy across public databases (e.g., "TechScale Soluciones S.L.", "TechScale Solutions", domain `techscale.io`, CIF `B87654321`).
The Entity Resolution Engine executes a multi-stage deterministic & probabilistic funnel:

1. **Exact Tax ID (Deterministic)**: Match Spanish CIF/NIF, UK CRN, or US EIN normalized via regex.
2. **Normalized Domain Matching**: Extract root domain (`techscale.io`) from WHOIS, SSL certs, or website metadata.
3. **Fuzzy Name & Context Match**: 
   - String distance: Levenshtein & Jaro-Winkler similarity ($\ge 0.88$).
   - Location & Industry context comparison (Postal code, NACE/SIC code).
4. **Graph Alias Assignment**: Insert alias record into `company_aliases` pointing to the canonical `company_id`.

---

## 3. Semantic & Structural DOM Diffing Engine

Static HTML diffing creates false positives due to CSRF tokens, dynamic script tags, current timestamps, and layout boilerplate.

### Architecture:
1. **Sanitization Phase**:
   - Strip dynamic script tags `<script>`, style tags `<style>`, invisible trackers, CSRF nonces, and standard footer copyright years.
2. **DOM AST Tree Hashing**:
   - Parse clean HTML into DOM tree.
   - Compute structural hashes for subsections (`/pricing`, `/careers`, `/services`, `/about`).
3. **Delta Extraction**:
   - Compare current AST hash against previous target snapshot.
   - Highlight structural additions (e.g. new pricing tier `$499/mo`, new division "Enterprise Security Services").
4. **Signal Extraction via DSPy / LLM Schema**:
   - Send clean diff text to fast local embedding/small LLM classification model.
   - Output structured Pydantic `SignalEvent` schema (e.g., `type: pricing_tier_added`, `confidence: 0.92`).

---

## 4. Time-Series Event Store & Intent Scoring Engine

### Storage Separation Pattern:
* **ClickHouse / TimescaleDB**: Append-only log of immutable signals (`signals` stream). Partitioned by `toYYYYMM(detected_at)`, indexed by `(company_id, signal_type, detected_at)`.
* **PostgreSQL**: Canonical metadata (`companies`), computed snapshots (`intent_snapshots`), and subscription rules (`webhook_subscriptions`).
* **Redis**: Caches recent rolling intent vectors per company to serve sub-10ms API reads.

### Intent Scoring Formulation & Exponential Time Decay
Given a company $C$ and a sliding window of time $T$, intent scores are computed over 5 composite vectors:
1. `growth_intent`
2. `hiring_intent`
3. `expansion_intent`
4. `technology_change_intent`
5. `financial_stress`

#### Signal Attenuation Formula:
For a signal $i$ detected at timestamp $t_i$, with current time $t$:
$$\Delta t_i = t - t_i \quad (\text{in days})$$
$$w_i(t) = W_s \cdot C_i \cdot e^{-\lambda_s \Delta t_i}$$

Where:
- $W_s \in [0, 100]$: Base weight of signal category $s$.
- $C_i \in [0, 1.0]$: Confidence score of signal detection.
- $\lambda_s = \frac{\ln(2)}{\tau_s}$: Decay factor derived from signal half-life $\tau_s$ (in days).

#### Half-Life Parameters ($\tau_s$):
- **Fast-Decay Signals** ($\tau_s = 7$ days, $\lambda \approx 0.0990$): Social posting velocity surge, PR announcements.
- **Medium-Decay Signals** ($\tau_s = 30$ days, $\lambda \approx 0.0231$): Job postings, website DOM diff pricing change, new DNS record activation.
- **Slow-Decay Signals** ($\tau_s = 90$ days, $\lambda \approx 0.0077$): Commercial real estate lease registration, new brand trademark, executive hire.

#### Vector Score Aggregation:
The cumulative un-bounded intent score for vector $k$ is:
$$S_k = \sum_{i \in \text{Signals}_k} w_i(t)$$
To map $S_k$ cleanly to $[0, 100]$, we apply a bounded exponential saturation function:
$$\text{IntentVector}_k(t) = 100 \cdot \left(1 - e^{-\gamma \cdot S_k}\right)$$
where $\gamma = 0.025$. This ensures single signals register meaningful scores while preventing multi-signal surges from over-saturating above 100.
