-- ============================================================================
-- BUSINESS RADAR & COMPANY INTENT API - DATABASE SCHEMA (PostgreSQL / TimescaleDB)
-- ============================================================================

-- Extension setup
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fast fuzzy name search

-- ----------------------------------------------------------------------------
-- 1. CANONICAL COMPANIES TABLE
-- Primary relational metadata store for verified entities.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    domain VARCHAR(255) UNIQUE NOT NULL,
    tax_id VARCHAR(50), -- Spanish CIF/NIF, UK CRN, US EIN
    tax_id_country VARCHAR(2) DEFAULT 'ES', -- ISO-2 code
    industry VARCHAR(100),
    employee_range VARCHAR(50), -- e.g. "50-200", "201-500"
    hq_country VARCHAR(2) DEFAULT 'ES',
    hq_city VARCHAR(100),
    hq_address TEXT,
    website_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_tax_id ON companies(tax_id, tax_id_country);
CREATE INDEX idx_companies_name_trgm ON companies USING gin (canonical_name gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- 2. COMPANY ALIASES TABLE (Entity Resolution Lookup)
-- Maps messy raw strings, legacy names, and secondary domains to company_id.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    alias_name VARCHAR(255) NOT NULL,
    alias_type VARCHAR(50) NOT NULL CHECK (alias_type IN ('name', 'domain', 'tax_id', 'brand_name')),
    confidence_score NUMERIC(3,2) DEFAULT 1.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aliases_lookup ON company_aliases(alias_name, alias_type);
CREATE INDEX idx_aliases_company ON company_aliases(company_id);

-- ----------------------------------------------------------------------------
-- 3. SIGNAL TYPES CATALOG TABLE
-- Standard definition of intent signals, vector targets, base weights, and half-lives.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_types (
    code VARCHAR(100) PRIMARY KEY, -- e.g., 'JOB_POSTING_SURGE', 'DOM_PRICING_UPDATE'
    name VARCHAR(255) NOT NULL,
    vector_category VARCHAR(50) NOT NULL CHECK (vector_category IN (
        'growth_intent', 
        'hiring_intent', 
        'expansion_intent', 
        'technology_change_intent', 
        'financial_stress'
    )),
    base_weight NUMERIC(5,2) NOT NULL DEFAULT 20.00, -- Base signal impact W_s (0-100)
    half_life_days INT NOT NULL DEFAULT 30, -- Attenuation half-life tau_s
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed Signal Types Data
INSERT INTO signal_types (code, name, vector_category, base_weight, half_life_days, description) VALUES
('JOB_POSTING_SURGE', 'Hiring Surge (>5 positions)', 'hiring_intent', 35.0, 30, 'Surge in operational and engineering job openings'),
('EXEC_ROLE_ADDED', 'Executive Role Addition (C-Suite/VP)', 'growth_intent', 40.0, 60, 'Key executive hire identified via LinkedIn/Registry'),
('DOM_PRICING_CHANGED', 'Pricing Page DOM Structure Change', 'technology_change_intent', 30.0, 30, 'Major update to pricing or tiering structure'),
('NEW_BRAND_DOMAIN', 'New Brand/Product Domain Registered', 'expansion_intent', 45.0, 90, 'WHOIS/DNS activation of secondary product domain'),
('REAL_ESTATE_FILING', 'Commercial Property Lease/Purchase Registry', 'expansion_intent', 50.0, 90, 'Property registry record for new regional office'),
('TECH_STACK_MIGRATION', 'New Cloud/SaaS Subdomain DNS Activation', 'technology_change_intent', 25.0, 30, 'Detection of Salesforce, Hubspot, AWS DNS records'),
('SOCIAL_ACTIVITY_SURGE', 'Executive Social Posting Velocity Surge', 'growth_intent', 15.0, 7, '300%+ increase in executive LinkedIn posting activity'),
('CREDIT_RATING_DOWNGRADE', 'Registry Financial Distress Warning', 'financial_stress', 65.0, 90, 'Official financial filing indication of liquidity stress'),
('EMPLOYEE_RATING_DROP', 'Glassdoor/Employee Review Drop Spike', 'financial_stress', 30.0, 30, 'Spike in negative employee sentiment reviews')
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. SCRAPE LOGS TABLE
-- Audit log of all web scraping attempts, status codes, timeouts, and errors.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrape_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    target_url VARCHAR(500) NOT NULL,
    status_code INT, -- 200, 404, 500, 0 for timeout
    duration_ms NUMERIC(10,2) DEFAULT 0.00,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    content_hash VARCHAR(64),
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scrape_logs_company ON scrape_logs(company_id, scraped_at DESC);
CREATE INDEX idx_scrape_logs_status ON scrape_logs(status_code);

-- ----------------------------------------------------------------------------
-- 5. SIGNALS APPEND-ONLY EVENT STREAM TABLE
-- Time-series store of raw signals ingested into the system.
-- (Can be converted to TimescaleDB hypertable or exported to ClickHouse).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signal_type_code VARCHAR(100) NOT NULL REFERENCES signal_types(code),
    source VARCHAR(100) NOT NULL, -- e.g. 'playwright_careers', 'whois_rdap', 'property_registry'
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.00, -- Detection confidence C_i
    score_impact NUMERIC(5,2) NOT NULL DEFAULT 25.00, -- Direct numeric score impact
    raw_payload JSONB DEFAULT '{}'::jsonb,
    extracted_attributes JSONB DEFAULT '{}'::jsonb,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signals_company_time ON signals(company_id, detected_at DESC);
CREATE INDEX idx_signals_type ON signals(signal_type_code);

-- Convert signals into TimescaleDB Hypertable if Timescale extension enabled:
-- SELECT create_hypertable('signals', 'detected_at', if_not_exists => TRUE);

-- ----------------------------------------------------------------------------
-- 5. INTENT SNAPSHOTS TABLE
-- Precomputed rolling intent vectors calculated by the Intent Engine.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intent_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    window_days INT NOT NULL DEFAULT 30,
    growth_intent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    hiring_intent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    expansion_intent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    technology_change_intent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    financial_stress NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    composite_score NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    confidence_score NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    primary_label VARCHAR(150), -- e.g. "Regional Expansion - Tech/Ops"
    signal_count INT DEFAULT 0,
    attribution_matrix JSONB DEFAULT '[]'::jsonb,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_snapshots_company ON intent_snapshots(company_id, computed_at DESC);
CREATE INDEX idx_intent_snapshots_scores ON intent_snapshots(composite_score DESC, computed_at DESC);

-- ----------------------------------------------------------------------------
-- 6. WEBHOOK SUBSCRIPTIONS TABLE
-- Enterprise real-time alert subscriptions.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id VARCHAR(100) NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    secret VARCHAR(255) NOT NULL,
    min_composite_score NUMERIC(5,2) DEFAULT 70.00,
    subscribed_vectors TEXT[] DEFAULT ARRAY['expansion_intent', 'growth_intent'],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
