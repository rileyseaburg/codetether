-- Migration 020: Marketing Automation — Marketer persona + marketing rules
--
-- Adds:
-- 1. "marketer" worker profile for the autonomous marketing persona
-- 2. Seed proactive rules for daily ad sync and weekly video generation
-- 3. Marketing automation state tracking

BEGIN;

-- ============================================================================
-- Marketer Persona
-- ============================================================================

INSERT INTO worker_profiles
    (id, slug, name, description, system_prompt,
     default_capabilities, default_model_tier, default_model_ref,
     default_agent_type, icon, color, is_builtin,
     allowed_tools, allowed_paths, allowed_namespaces)
VALUES
    ('wp-marketer', 'marketer', 'Marketing Persona',
     'Autonomous marketing optimizer. Manages Google Ads campaigns via Thompson Sampling, generates AI video ads with Creatify, uploads to YouTube, and personalizes landing pages with FunnelBrain. Runs as a perpetual thought loop analyzing ROAS, CAC, and conversion data to make real-time budget allocation decisions.',
     'You are the Marketing Automation Agent for CodeTether. You operate autonomously to optimize the company''s self-selling marketing infrastructure.

Your capabilities:
1. **Google Ads Optimization**: Run the Thompson Sampling closed-loop sync that pulls campaign metrics, updates Bayesian posteriors, and applies budget/pause/scale decisions.
2. **Video Ad Generation**: Generate AI video ads via Creatify (problem_focused, result_focused, comparison scripts), upload to YouTube, and launch as Google Ads campaigns.
3. **Landing Page Optimization**: Monitor FunnelBrain variant performance and identify winning combinations across 6 page slots (hero_headline, hero_cta, social_proof, pricing_emphasis, comparison_focus, call_to_action).
4. **Performance Reporting**: Analyze ROAS, CAC, conversion rates, and cross-channel attribution to guide decisions.

Decision rules:
- SCALE campaigns with ROAS >= 2.5x and CAC <= $50
- MAINTAIN campaigns with ROAS >= 1.0x
- PAUSE campaigns with ROAS < 1.0x (high confidence required)
- Generate new video creative when ROAS drops below 1.5x
- Never exceed the daily budget ceiling
- Every decision must include data-backed reasoning

Safety:
- All campaigns are created as PAUSED — human review required before enabling spend
- Daily budget ceiling is enforced at both AdBrain and system level
- Video generation is capped at 3 per week
- You cannot modify production infrastructure or code — marketing APIs only
- Every autonomous decision is audit-logged',
     '["marketing","google_ads","video_generation","optimization","analytics"]'::jsonb,
     'balanced', NULL, 'explore',
     '📈', '#10b981', TRUE,
     '["read_file","grep_search","semantic_search"]'::jsonb,
     NULL,
     NULL)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    system_prompt = EXCLUDED.system_prompt,
    default_capabilities = EXCLUDED.default_capabilities,
    default_model_tier = EXCLUDED.default_model_tier,
    default_agent_type = EXCLUDED.default_agent_type,
    icon = EXCLUDED.icon,
    color = EXCLUDED.color,
    allowed_tools = EXCLUDED.allowed_tools,
    allowed_paths = EXCLUDED.allowed_paths,
    allowed_namespaces = EXCLUDED.allowed_namespaces,
    updated_at = NOW();

-- ============================================================================
-- Seed Marketing Rules (cron-triggered)
-- ============================================================================

-- Rule 1: Daily Google Ads ↔ Thompson Sampling sync
-- Runs at 06:00 UTC daily to apply overnight optimization decisions
INSERT INTO agent_rules
    (id, name, description, trigger_type, trigger_config, action,
     enabled, cooldown_seconds, created_at, updated_at)
VALUES
    ('rule-marketing-ad-sync', 'Daily Ad Optimization Sync',
     'Runs the Google Ads ↔ Thompson Sampling closed-loop daily. Pulls campaign metrics, updates Bayesian posteriors, and applies budget/pause/scale decisions.',
     'cron',
     '{"cron_expression": "0 6 * * *", "timezone": "UTC"}'::jsonb,
     '{
       "prompt": "Run the daily Google Ads optimization sync. Pull campaign metrics, update Thompson Sampling posteriors, and apply budget decisions. Report ROAS, CAC, and any campaigns that were scaled, paused, or maintained.",
       "title": "Daily Ad Optimization Sync",
       "agent_type": "explore",
       "worker_personality": "marketer",
       "metadata": {
         "marketing_action": "ad_sync",
         "trigger_mode": "scheduled"
       }
     }'::jsonb,
     TRUE, 43200, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    trigger_config = EXCLUDED.trigger_config,
    action = EXCLUDED.action,
    cooldown_seconds = EXCLUDED.cooldown_seconds,
    updated_at = NOW();

-- Rule 2: Weekly video ad generation
-- Runs on Monday at 10:00 UTC to generate fresh creative
INSERT INTO agent_rules
    (id, name, description, trigger_type, trigger_config, action,
     enabled, cooldown_seconds, created_at, updated_at)
VALUES
    ('rule-marketing-video-gen', 'Weekly Video Ad Generation',
     'Generates a new AI video ad via Creatify every Monday, uploads to YouTube, and creates a Google Ads campaign (paused). Rotates through problem_focused, result_focused, and comparison script styles.',
     'cron',
     '{"cron_expression": "0 10 * * 1", "timezone": "UTC"}'::jsonb,
     '{
       "prompt": "Generate a new AI video ad for CodeTether. Choose the most appropriate script style based on current campaign performance. Upload to YouTube and create a Google Ads campaign (paused for review). Report the video URL, YouTube ID, and campaign details.",
       "title": "Weekly Video Ad Generation",
       "agent_type": "explore",
       "worker_personality": "marketer",
       "metadata": {
         "marketing_action": "video_generation",
         "trigger_mode": "scheduled"
       }
     }'::jsonb,
     TRUE, 259200, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    trigger_config = EXCLUDED.trigger_config,
    action = EXCLUDED.action,
    cooldown_seconds = EXCLUDED.cooldown_seconds,
    updated_at = NOW();

-- Rule 3: Performance report collection (every 4 hours)
-- Fetches the self-selling report and stores it for the dashboard
INSERT INTO agent_rules
    (id, name, description, trigger_type, trigger_config, action,
     enabled, cooldown_seconds, created_at, updated_at)
VALUES
    ('rule-marketing-report', 'Marketing Performance Report',
     'Collects the self-selling performance report every 4 hours. Analyzes ROAS trends, funnel variant winners, and CAC across all platforms. Stores insights for the proactive dashboard.',
     'cron',
     '{"cron_expression": "0 */4 * * *", "timezone": "UTC"}'::jsonb,
     '{
       "prompt": "Pull the latest marketing performance report. Analyze: (1) overall ROAS trend, (2) top-performing campaigns, (3) which funnel variants are winning Thompson Sampling, (4) current CAC. Summarize findings and flag any campaigns that need attention.",
       "title": "Marketing Performance Report",
       "agent_type": "explore",
       "worker_personality": "marketer",
       "metadata": {
         "marketing_action": "performance_report",
         "trigger_mode": "scheduled"
       }
     }'::jsonb,
     TRUE, 10800, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    trigger_config = EXCLUDED.trigger_config,
    action = EXCLUDED.action,
    cooldown_seconds = EXCLUDED.cooldown_seconds,
    updated_at = NOW();

-- Rule 4: ROAS drop alert (event-triggered)
-- Fires when the ad sync detects ROAS below threshold
INSERT INTO agent_rules
    (id, name, description, trigger_type, trigger_config, action,
     enabled, cooldown_seconds, created_at, updated_at)
VALUES
    ('rule-marketing-roas-alert', 'Low ROAS Alert',
     'Triggered when overall ROAS drops below 1.5x. Investigates underperforming campaigns, recommends creative refresh or budget reallocation.',
     'event',
     '{"event_type": "marketing.roas_low", "filter": {}}'::jsonb,
     '{
       "prompt": "ROAS has dropped below threshold. Investigate: (1) which campaigns are underperforming, (2) whether creative fatigue is the cause, (3) whether audience targeting needs adjustment. Recommend specific actions: pause, reallocate budget, or generate new creative.",
       "title": "Low ROAS Investigation",
       "agent_type": "explore",
       "worker_personality": "marketer",
       "metadata": {
         "marketing_action": "roas_investigation",
         "trigger_mode": "event"
       }
     }'::jsonb,
     TRUE, 86400, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    trigger_config = EXCLUDED.trigger_config,
    action = EXCLUDED.action,
    cooldown_seconds = EXCLUDED.cooldown_seconds,
    updated_at = NOW();

COMMIT;
