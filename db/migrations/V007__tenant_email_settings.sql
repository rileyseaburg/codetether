-- Migration: Add tenant email settings table
-- V007__tenant_email_settings.sql

-- Create tenant email settings table
CREATE TABLE IF NOT EXISTS tenant_email_settings (
    tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),
    provider TEXT NOT NULL DEFAULT 'sendgrid',
    -- Encrypted credentials (AES-256 via pgp_sym_encrypt)
    api_key_encrypted TEXT NOT NULL,
    from_email TEXT NOT NULL,
    from_name TEXT,
    reply_to_domain TEXT,
    -- Provider-specific settings (JSON for flexibility)
    provider_settings JSONB DEFAULT '{}'::jsonb,
    -- Feature flags
    enabled BOOLEAN DEFAULT true,
    -- Rate limiting
    daily_limit INTEGER DEFAULT 1000,
    emails_sent_today INTEGER DEFAULT 0,
    last_reset_date DATE DEFAULT CURRENT_DATE,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for tenant lookups
CREATE INDEX IF NOT EXISTS idx_tenant_email_settings_tenant 
ON tenant_email_settings(tenant_id);

-- Create index for enabled status
CREATE INDEX IF NOT EXISTS idx_tenant_email_settings_enabled 
ON tenant_email_settings(enabled) WHERE enabled = true;

-- Enable RLS
ALTER TABLE tenant_email_settings ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Tenants can only see their own settings
CREATE POLICY tenant_email_settings_isolation ON tenant_email_settings
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_tenant_email_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
DROP TRIGGER IF EXISTS tenant_email_settings_updated_at ON tenant_email_settings;
CREATE TRIGGER tenant_email_settings_updated_at
    BEFORE UPDATE ON tenant_email_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_tenant_email_settings_updated_at();

-- Create function to reset daily email counters
CREATE OR REPLACE FUNCTION reset_daily_email_counters()
RETURNS void AS $$
BEGIN
    UPDATE tenant_email_settings
    SET emails_sent_today = 0,
        last_reset_date = CURRENT_DATE
    WHERE last_reset_date < CURRENT_DATE;
END;
$$ LANGUAGE plpgsql;

-- Backfill existing tenants with default settings using global config
-- This requires the encryption key to be set
DO $$
DECLARE
    global_api_key TEXT;
    global_from_email TEXT;
    encryption_key TEXT;
BEGIN
    -- Get global config from environment (set via migration script)
    global_api_key := current_setting('app.global_sendgrid_key', true);
    global_from_email := current_setting('app.global_from_email', true);
    encryption_key := current_setting('app.encryption_key', true);
    
    -- Only backfill if we have the required config
    IF global_api_key IS NOT NULL AND encryption_key IS NOT NULL THEN
        INSERT INTO tenant_email_settings (
            tenant_id,
            provider,
            api_key_encrypted,
            from_email,
            from_name,
            reply_to_domain,
            enabled
        )
        SELECT 
            t.id as tenant_id,
            'sendgrid' as provider,
            encode(pgp_sym_encrypt(global_api_key, encryption_key)::bytea, 'base64') as api_key_encrypted,
            COALESCE(global_from_email, 'noreply@codetether.run') as from_email,
            t.display_name as from_name,
            'codetether.run' as reply_to_domain,
            true as enabled
        FROM tenants t
        LEFT JOIN tenant_email_settings tes ON t.id = tes.tenant_id
        WHERE tes.tenant_id IS NULL;
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE tenant_email_settings IS 'Per-tenant email configuration with encrypted credentials';
COMMENT ON COLUMN tenant_email_settings.api_key_encrypted IS 'AES-256 encrypted API key using pgp_sym_encrypt';
