-- Migration: First-party analytics for CodeTether
-- Phase 1 of vertical integration strategy
-- 
-- This creates the analytics spine that CodeTether owns:
-- - Event collection (page views, signups, conversions)
-- - Identity stitching (anonymous -> user -> workspace)
-- - Attribution tracking (UTM, touchpoints)

-- ============================================================================
-- EVENTS TABLE
-- Core event stream - all user interactions flow through here
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Timing
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Event classification
    event_type TEXT NOT NULL,  -- page_view, signup_started, signup_completed, etc.
    event_category TEXT,       -- engagement, conversion, retention
    
    -- Identity (progressive enrichment)
    anonymous_id TEXT NOT NULL,          -- Cookie/device ID (always present)
    user_id TEXT,                        -- After signup
    workspace_id TEXT,                   -- After workspace creation
    tenant_id TEXT,                      -- For multi-tenant isolation
    session_id TEXT,                     -- Browser session
    
    -- Attribution (captured on first touch)
    referrer TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_term TEXT,
    utm_content TEXT,
    landing_page TEXT,
    
    -- Context
    page_url TEXT,
    page_title TEXT,
    user_agent TEXT,
    ip_address INET,
    country_code TEXT,
    region TEXT,
    city TEXT,
    
    -- Flexible properties (event-specific data)
    properties JSONB DEFAULT '{}',
    
    -- Conversion tracking
    conversion_value DECIMAL(10,2),  -- Revenue value if applicable
    currency TEXT DEFAULT 'USD',
    
    -- Processing flags
    forwarded_to_x BOOLEAN DEFAULT FALSE,
    forwarded_to_fb BOOLEAN DEFAULT FALSE,
    forwarded_to_google BOOLEAN DEFAULT FALSE,
    forward_error TEXT
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_analytics_events_time 
    ON analytics_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type 
    ON analytics_events(event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_anon 
    ON analytics_events(anonymous_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_user 
    ON analytics_events(user_id, event_time DESC) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_events_workspace 
    ON analytics_events(workspace_id, event_time DESC) WHERE workspace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_events_tenant 
    ON analytics_events(tenant_id, event_time DESC) WHERE tenant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_events_session 
    ON analytics_events(session_id, event_time DESC) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_events_utm 
    ON analytics_events(utm_source, utm_campaign, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_not_forwarded_x
    ON analytics_events(event_time) WHERE forwarded_to_x = FALSE AND event_type IN ('signup_completed', 'trial_started', 'paid');

-- ============================================================================
-- IDENTITY MAP
-- Stitches anonymous IDs to known users progressively
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_identity_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- The anonymous ID being mapped
    anonymous_id TEXT NOT NULL,
    
    -- Progressive identity resolution
    user_id TEXT,
    workspace_id TEXT,
    tenant_id TEXT,
    email TEXT,
    
    -- When each identity was linked
    user_linked_at TIMESTAMPTZ,
    workspace_linked_at TIMESTAMPTZ,
    
    -- Tracking
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Deduplication
    UNIQUE(anonymous_id)
);

CREATE INDEX IF NOT EXISTS idx_identity_map_user 
    ON analytics_identity_map(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identity_map_workspace 
    ON analytics_identity_map(workspace_id) WHERE workspace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identity_map_email 
    ON analytics_identity_map(email) WHERE email IS NOT NULL;

-- ============================================================================
-- TOUCHPOINTS
-- Attribution snapshots for first-touch / last-touch analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_touchpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identity
    anonymous_id TEXT NOT NULL,
    user_id TEXT,
    workspace_id TEXT,
    
    -- Touchpoint type
    touchpoint_type TEXT NOT NULL,  -- first_touch, last_touch, conversion_touch
    
    -- Attribution data (snapshot at time of touch)
    referrer TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_term TEXT,
    utm_content TEXT,
    landing_page TEXT,
    
    -- Event that triggered this touchpoint
    event_id UUID REFERENCES analytics_events(id),
    event_type TEXT NOT NULL,
    
    -- Timing
    touched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Prevent duplicates per identity + type
    UNIQUE(anonymous_id, touchpoint_type)
);

CREATE INDEX IF NOT EXISTS idx_touchpoints_user 
    ON analytics_touchpoints(user_id, touchpoint_type) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_touchpoints_workspace 
    ON analytics_touchpoints(workspace_id, touchpoint_type) WHERE workspace_id IS NOT NULL;

-- ============================================================================
-- CONVERSION EVENTS (for ad platform forwarding)
-- Denormalized for easy queuing to X/FB/Google
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source event
    event_id UUID REFERENCES analytics_events(id),
    
    -- Conversion details
    conversion_type TEXT NOT NULL,  -- signup, trial_start, purchase, etc.
    conversion_value DECIMAL(10,2),
    currency TEXT DEFAULT 'USD',
    
    -- Identity for matching
    email TEXT,
    phone TEXT,
    user_id TEXT,
    workspace_id TEXT,
    
    -- Click IDs for attribution (captured from URL params)
    x_click_id TEXT,      -- twclid from X/Twitter
    fb_click_id TEXT,     -- fbclid from Facebook
    google_click_id TEXT, -- gclid from Google
    
    -- Forwarding status
    x_forwarded BOOLEAN DEFAULT FALSE,
    x_forwarded_at TIMESTAMPTZ,
    x_response JSONB,
    
    fb_forwarded BOOLEAN DEFAULT FALSE,
    fb_forwarded_at TIMESTAMPTZ,
    fb_response JSONB,
    
    google_forwarded BOOLEAN DEFAULT FALSE,
    google_forwarded_at TIMESTAMPTZ,
    google_response JSONB,
    
    -- Timing
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversions_pending_x 
    ON analytics_conversions(occurred_at) WHERE x_forwarded = FALSE;
CREATE INDEX IF NOT EXISTS idx_conversions_pending_fb 
    ON analytics_conversions(occurred_at) WHERE fb_forwarded = FALSE;
CREATE INDEX IF NOT EXISTS idx_conversions_type 
    ON analytics_conversions(conversion_type, occurred_at DESC);

-- ============================================================================
-- FUNNEL DEFINITIONS
-- Configurable conversion funnels for analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_funnels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    
    -- Ordered list of event types that define the funnel
    steps JSONB NOT NULL,  -- [{"event_type": "page_view", "name": "Landing"}, ...]
    
    -- Time window for funnel completion
    window_hours INTEGER DEFAULT 168,  -- 7 days default
    
    -- Ownership
    tenant_id TEXT,
    created_by TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default funnel: Signup to Paid
INSERT INTO analytics_funnels (id, name, description, steps, window_hours)
VALUES (
    'default-signup-funnel',
    'Signup to Paid',
    'Core conversion funnel from first visit to paid subscription',
    '[
        {"event_type": "page_view", "name": "Landing Page"},
        {"event_type": "signup_started", "name": "Started Signup"},
        {"event_type": "signup_completed", "name": "Completed Signup"},
        {"event_type": "workspace_created", "name": "Created Workspace"},
        {"event_type": "trial_started", "name": "Started Trial"},
        {"event_type": "first_success", "name": "First Success"},
        {"event_type": "paid", "name": "Paid Conversion"}
    ]',
    168
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- RLS POLICIES (if RLS is enabled)
-- ============================================================================
-- Events: Tenants can only see their own events
ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY analytics_events_tenant_isolation ON analytics_events
    USING (tenant_id = current_setting('app.current_tenant', true) OR tenant_id IS NULL);

-- Identity map: Tenants can only see their mappings
ALTER TABLE analytics_identity_map ENABLE ROW LEVEL SECURITY;
CREATE POLICY identity_map_tenant_isolation ON analytics_identity_map
    USING (tenant_id = current_setting('app.current_tenant', true) OR tenant_id IS NULL);

COMMENT ON TABLE analytics_events IS 'First-party event stream for CodeTether analytics';
COMMENT ON TABLE analytics_identity_map IS 'Anonymous to known identity stitching';
COMMENT ON TABLE analytics_touchpoints IS 'Attribution touchpoints (first/last touch)';
COMMENT ON TABLE analytics_conversions IS 'Conversion events queued for ad platform forwarding';
