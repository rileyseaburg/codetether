-- Migration: Create users table for self-service registration
-- This enables consumer/mid-market signup without Keycloak

-- Users table for self-service authentication
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    -- Account status
    status TEXT DEFAULT 'pending_verification',  -- pending_verification, active, suspended, deleted
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_token TEXT,
    email_verification_expires TIMESTAMPTZ,
    -- Password reset
    password_reset_token TEXT,
    password_reset_expires TIMESTAMPTZ,
    -- Tenant association
    tenant_id TEXT REFERENCES tenants(id),
    -- Referral tracking
    referral_source TEXT,
    -- Usage tracking
    tasks_used_this_month INTEGER DEFAULT 0,
    tasks_limit INTEGER DEFAULT 10,  -- Free tier default
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    -- Stripe billing (for individual users not part of org tenant)
    stripe_customer_id TEXT
);

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(email_verification_token);
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(password_reset_token);

-- API keys for programmatic access
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,  -- SHA256 hash of the API key
    key_prefix TEXT NOT NULL,  -- First 8 chars for identification
    -- Permissions
    scopes TEXT[] DEFAULT ARRAY['tasks:read', 'tasks:write'],
    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    -- Status
    status TEXT DEFAULT 'active',  -- active, revoked
    last_used_at TIMESTAMPTZ,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ  -- NULL means never expires
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

-- Automation templates (pre-built workflows for quick start)
CREATE TABLE IF NOT EXISTS automation_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- 'research', 'content', 'data', 'outreach'
    -- The actual prompt template with {{placeholders}}
    prompt_template TEXT NOT NULL,
    -- Required inputs from user
    required_inputs JSONB DEFAULT '[]'::jsonb,
    -- Optional configuration
    default_config JSONB DEFAULT '{}'::jsonb,
    -- Visibility
    is_public BOOLEAN DEFAULT TRUE,
    created_by TEXT REFERENCES users(id),
    -- Usage stats
    usage_count INTEGER DEFAULT 0,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_templates_category ON automation_templates(category);
CREATE INDEX IF NOT EXISTS idx_templates_public ON automation_templates(is_public);

-- User automations (saved/scheduled tasks)
CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    -- Template reference (optional)
    template_id TEXT REFERENCES automation_templates(id),
    -- The actual prompt/task
    prompt TEXT NOT NULL,
    -- Schedule (NULL = manual trigger only)
    schedule_cron TEXT,  -- cron expression for recurring
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    -- Status
    status TEXT DEFAULT 'active',  -- active, paused, deleted
    -- Configuration
    config JSONB DEFAULT '{}'::jsonb,
    -- Notification settings
    notify_email BOOLEAN DEFAULT TRUE,
    notify_webhook_url TEXT,
    -- Stats
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automations_user ON automations(user_id);
CREATE INDEX IF NOT EXISTS idx_automations_status ON automations(status);
CREATE INDEX IF NOT EXISTS idx_automations_next_run ON automations(next_run_at);

-- Insert default automation templates for first-run experience
INSERT INTO automation_templates (id, name, description, category, prompt_template, required_inputs, is_public)
VALUES 
    (
        'tpl_competitor_intel',
        'Competitor Intelligence Report',
        'Research your competitors and get a detailed analysis of their online presence, marketing, and positioning.',
        'research',
        'Research the following competitors for {{company_name}} in the {{industry}} industry: {{competitors}}

Analyze each competitor and provide:
1. Their main value proposition and positioning
2. Key products/services they offer
3. Recent news or announcements
4. Their apparent target audience
5. Strengths and potential weaknesses

Then provide 3 actionable opportunities for {{company_name}} based on gaps in the competitive landscape.

Format the results as a clear, executive-friendly report.',
        '[{"name": "company_name", "label": "Your Company Name", "type": "text", "required": true}, {"name": "industry", "label": "Your Industry", "type": "text", "required": true}, {"name": "competitors", "label": "Competitor Names (comma-separated)", "type": "text", "required": true}]'::jsonb,
        TRUE
    ),
    (
        'tpl_content_batch',
        'Weekly Content Batch',
        'Generate a week''s worth of social media content tailored to your brand voice.',
        'content',
        'Create a week of social media content for {{brand_name}}, a {{business_type}}.

Target audience: {{target_audience}}
Brand voice: {{brand_voice}}
Key topics to cover: {{topics}}

Generate:
- 5 LinkedIn posts (professional, thought leadership)
- 7 Twitter/X posts (concise, engaging)
- 3 longer-form content ideas (blog post outlines)

Each piece should:
- Include a hook that grabs attention
- Provide value to the reader
- End with a clear call-to-action
- Be ready to post (no placeholders)

Format with clear headers for each platform.',
        '[{"name": "brand_name", "label": "Brand/Company Name", "type": "text", "required": true}, {"name": "business_type", "label": "What does your business do?", "type": "text", "required": true}, {"name": "target_audience", "label": "Who is your target audience?", "type": "text", "required": true}, {"name": "brand_voice", "label": "Describe your brand voice", "type": "text", "required": false, "default": "Professional yet approachable"}, {"name": "topics", "label": "Key topics to cover", "type": "text", "required": true}]'::jsonb,
        TRUE
    ),
    (
        'tpl_lead_research',
        'Lead Research & Enrichment',
        'Research potential leads and gather detailed information for personalized outreach.',
        'research',
        'Research the following companies/people as potential leads for {{my_company}}:

{{leads}}

For each lead, find:
1. Company overview and size
2. Key decision makers (names, titles, LinkedIn if available)
3. Recent company news or funding
4. Potential pain points we could solve
5. Personalized outreach angle

My company sells: {{what_we_sell}}
Our ideal customer: {{ideal_customer}}

Format as a table/spreadsheet-ready output with columns for easy import.',
        '[{"name": "my_company", "label": "Your Company Name", "type": "text", "required": true}, {"name": "leads", "label": "Companies/People to Research (one per line)", "type": "textarea", "required": true}, {"name": "what_we_sell", "label": "What do you sell?", "type": "text", "required": true}, {"name": "ideal_customer", "label": "Describe your ideal customer", "type": "text", "required": true}]'::jsonb,
        TRUE
    ),
    (
        'tpl_email_sequence',
        'Outreach Email Sequence',
        'Generate a personalized cold outreach email sequence for sales or partnerships.',
        'outreach',
        'Create a 3-email outreach sequence for {{purpose}}.

Context about my company: {{company_context}}
Target recipient profile: {{recipient_profile}}
Key value proposition: {{value_prop}}
Desired outcome: {{desired_outcome}}

Generate 3 emails:
1. Initial outreach (cold email)
2. Follow-up #1 (if no response, sent 3 days later)
3. Follow-up #2 (break-up email, sent 5 days after #2)

Each email should:
- Be under 150 words
- Have a compelling subject line
- Feel personal, not templated
- Include a specific, low-friction CTA
- Reference something specific about the recipient (use {{placeholder}} for personalization points)

Also provide guidance on what to personalize for each prospect.',
        '[{"name": "purpose", "label": "Purpose of outreach", "type": "select", "options": ["Sales", "Partnership", "Investor", "Press/Media", "Other"], "required": true}, {"name": "company_context", "label": "About your company (2-3 sentences)", "type": "textarea", "required": true}, {"name": "recipient_profile", "label": "Who are you reaching out to?", "type": "text", "required": true}, {"name": "value_prop", "label": "Your key value proposition", "type": "text", "required": true}, {"name": "desired_outcome", "label": "What do you want them to do?", "type": "text", "required": true}]'::jsonb,
        TRUE
    )
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    required_inputs = EXCLUDED.required_inputs,
    updated_at = NOW();
