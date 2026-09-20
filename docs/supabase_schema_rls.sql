-- =============================================================================
-- BUSINESS RADAR / OFANRADAR — SUPABASE POSTGRESQL SCHEMA & RLS MIGRATION (V6)
-- Connection: Supabase Transaction Pooler (Port 6543) / Direct (Port 5432)
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. ORGANIZATIONS (Tenants)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    plan_type VARCHAR(50) DEFAULT 'Pro',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. USERS
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'analyst',
    subscription_status VARCHAR(50) DEFAULT 'trial',
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    has_seen_tour BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. COMPANIES (Canonical Entities)
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    domain VARCHAR(255) UNIQUE NOT NULL,
    tax_id VARCHAR(100),
    tax_id_country VARCHAR(10) DEFAULT 'ES',
    industry VARCHAR(150),
    employee_range VARCHAR(50),
    hq_country VARCHAR(10) DEFAULT 'ES',
    hq_city VARCHAR(100),
    hq_address TEXT,
    website_url TEXT,
    linkedin_url TEXT,
    logo_url TEXT,
    tech_stack JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. SEED COMPANIES (Master Seed Table for Wow Effect Onboarding)
CREATE TABLE IF NOT EXISTS seed_companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    domain VARCHAR(255) UNIQUE NOT NULL,
    tax_id VARCHAR(100),
    tax_id_country VARCHAR(10) DEFAULT 'ES',
    industry VARCHAR(150),
    employee_range VARCHAR(50),
    hq_country VARCHAR(10) DEFAULT 'ES',
    hq_city VARCHAR(100),
    logo_url TEXT,
    tech_stack JSONB DEFAULT '{}'::jsonb,
    is_seed_master BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. COMPANY ALIASES
CREATE TABLE IF NOT EXISTS company_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    alias_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. SIGNAL TYPES
CREATE TABLE IF NOT EXISTS signal_types (
    code VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    vector_category VARCHAR(100) NOT NULL,
    base_weight DOUBLE PRECISION DEFAULT 10.0,
    half_life_days INT DEFAULT 30,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. SIGNALS
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    signal_type_code VARCHAR(100) REFERENCES signal_types(code) ON DELETE RESTRICT,
    source VARCHAR(150) NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.90,
    raw_payload JSONB DEFAULT '{}'::jsonb,
    extracted_attributes JSONB DEFAULT '{}'::jsonb,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. INTENT SNAPSHOTS
CREATE TABLE IF NOT EXISTS intent_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    window_days INT DEFAULT 90,
    growth_intent DOUBLE PRECISION DEFAULT 0.0,
    hiring_intent DOUBLE PRECISION DEFAULT 0.0,
    expansion_intent DOUBLE PRECISION DEFAULT 0.0,
    technology_change_intent DOUBLE PRECISION DEFAULT 0.0,
    financial_stress DOUBLE PRECISION DEFAULT 0.0,
    composite_score DOUBLE PRECISION DEFAULT 0.0,
    confidence_score DOUBLE PRECISION DEFAULT 0.90,
    primary_label VARCHAR(150),
    signal_count INT DEFAULT 0,
    attribution_matrix JSONB DEFAULT '[]'::jsonb,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. WATCHLISTS
CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(50) DEFAULT '#00e5ff',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. WATCHLIST COMPANIES (Junction)
CREATE TABLE IF NOT EXISTS watchlist_companies (
    watchlist_id UUID REFERENCES watchlists(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (watchlist_id, company_id)
);

-- 11. ALERT SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    rule_name VARCHAR(255),
    channel VARCHAR(50) DEFAULT 'WEBHOOK',
    target_url TEXT,
    secret VARCHAR(255),
    min_composite_score DOUBLE PRECISION DEFAULT 70.0,
    subscribed_signal_code VARCHAR(100),
    subscribed_industry VARCHAR(150),
    client_name VARCHAR(255),
    target_email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_subscriptions ENABLE ROW LEVEL SECURITY;

-- Public/Read-Only Tables (no RLS restrictions)
ALTER TABLE companies DISABLE ROW LEVEL SECURITY;
ALTER TABLE seed_companies DISABLE ROW LEVEL SECURITY;
ALTER TABLE signal_types DISABLE ROW LEVEL SECURITY;
ALTER TABLE signals DISABLE ROW LEVEL SECURITY;
ALTER TABLE intent_snapshots DISABLE ROW LEVEL SECURITY;

-- Allow anonymous / authenticated read access for companies & snapshots
CREATE POLICY "Allow public read access for companies" ON companies FOR SELECT USING (true);
CREATE POLICY "Allow public read access for seed_companies" ON seed_companies FOR SELECT USING (true);

-- Allow authenticated user RLS policies for watchlists
CREATE POLICY "Users can manage their own watchlists" ON watchlists
    FOR ALL USING (auth.uid() = user_id OR tenant_id IS NOT NULL);

CREATE POLICY "Users can manage watchlist companies" ON watchlist_companies
    FOR ALL USING (true);
