-- Migration: Add K8s provisioning columns to tenants table
-- These columns track the Kubernetes namespace and URLs for per-tenant instances

-- Add k8s_namespace column (stores the K8s namespace name, e.g., "tenant-acme-corp")
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS k8s_namespace VARCHAR(255);

-- Add k8s_external_url column (stores the external URL, e.g., "https://acme-corp.codetether.run")
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS k8s_external_url VARCHAR(512);

-- Add k8s_internal_url column (stores the internal cluster URL)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS k8s_internal_url VARCHAR(512);

-- Add index for faster lookups by namespace
CREATE INDEX IF NOT EXISTS idx_tenants_k8s_namespace ON tenants(k8s_namespace) WHERE k8s_namespace IS NOT NULL;

-- Comment explaining the columns
COMMENT ON COLUMN tenants.k8s_namespace IS 'Kubernetes namespace for this tenant''s dedicated instance';
COMMENT ON COLUMN tenants.k8s_external_url IS 'External URL for accessing the tenant''s A2A server instance';
COMMENT ON COLUMN tenants.k8s_internal_url IS 'Internal cluster URL for service-to-service communication';
