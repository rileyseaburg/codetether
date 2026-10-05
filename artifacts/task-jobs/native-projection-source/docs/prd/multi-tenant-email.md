# Multi-Tenant Email Support for Knative Workers

## Overview

Currently, the Knative worker email notification system uses a global SendGrid configuration, which doesn't align with our multi-tenant architecture. This PRD outlines the implementation of per-tenant email configuration that integrates with our existing Row-Level Security (RLS) and tenant isolation patterns.

## Current State

### What's Working
- ✅ SendGrid email integration in TypeScript worker
- ✅ Task completion emails with output content
- ✅ PostgreSQL RLS with `tenant_id` context
- ✅ Multi-tenant database schema

### What's Missing
- ❌ `tenant_id` not passed from A2A server to workers
- ❌ Workers don't set tenant context before DB operations
- ❌ No per-tenant email configuration storage
- ❌ Workers use global SendGrid credentials instead of tenant-specific

## Goals

1. **Tenant Isolation**: Each tenant uses their own email provider credentials
2. **Backward Compatibility**: Existing single-tenant deployments continue to work
3. **Security**: Email credentials encrypted at rest, never logged
4. **Flexibility**: Support multiple providers (SendGrid, AWS SES, Postmark, etc.)

## Technical Architecture

### Data Flow

```
User Request (with JWT containing tenant_id)
    ↓
A2A Server (Python)
    ↓
CloudEvent Published (includes tenant_id)
    ↓
Knative Worker (TypeScript)
    ↓
1. Set DB tenant context
2. Query tenant email config
3. Send email using tenant credentials
```

### Database Schema

#### New Table: `tenant_email_settings`

```sql
CREATE TABLE tenant_email_settings (
    tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),
    provider TEXT NOT NULL DEFAULT 'sendgrid',
    -- Encrypted credentials (AES-256)
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
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS Policy: Tenants can only see their own settings
CREATE POLICY tenant_email_settings_isolation ON tenant_email_settings
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Enable RLS
ALTER TABLE tenant_email_settings ENABLE ROW LEVEL SECURITY;
```

#### Migration for Existing Tenants

```sql
-- Insert default email settings for existing tenants using global config
INSERT INTO tenant_email_settings (
    tenant_id, 
    provider, 
    api_key_encrypted, 
    from_email, 
    from_name,
    reply_to_domain
)
SELECT 
    id as tenant_id,
    'sendgrid' as provider,
    encrypt(global_sendgrid_key, encryption_key, 'aes') as api_key_encrypted,
    'noreply@codetether.run' as from_email,
    display_name as from_name,
    'codetether.run' as reply_to_domain
FROM tenants;
```

### API Changes

#### 1. CloudEvent Extension (A2A Server)

Modify `publish_task_event()` in `knative_events.py`:

```python
async def publish_task_event(
    session_id: str,
    task_id: str,
    prompt: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,  # NEW PARAMETER
    notify_email: Optional[str] = None,  # NEW PARAMETER
) -> bool:
    headers = _build_cloudevent_headers(
        event_type='codetether.task.created',
        session_id=session_id,
        extensions={
            'taskid': task_id,
            'agent': agent,
            'model': model,
            'tenant': tenant_id,  # NEW: Pass tenant_id in headers
        },
    )

    body = {
        'task_id': task_id,
        'session_id': session_id,
        'prompt': prompt,
        'agent': agent,
        'model': model,
        'tenant_id': tenant_id,  # NEW: Include in body
        'notify_email': notify_email,  # NEW: Include notification email
        'metadata': metadata or {},
    }
```

#### 2. Worker Email Configuration Interface

New file: `agent/packages/agent/src/util/tenant-email.ts`

```typescript
interface TenantEmailConfig {
  provider: 'sendgrid' | 'aws-ses' | 'postmark' | 'smtp';
  apiKey: string;  // Decrypted
  fromEmail: string;
  fromName?: string;
  replyToDomain?: string;
  providerSettings?: Record<string, any>;
}

interface TenantEmailSettings {
  tenantId: string;
  enabled: boolean;
  dailyLimit: number;
  emailsSentToday: number;
  config: TenantEmailConfig;
}

async function getTenantEmailConfig(tenantId: string): Promise<TenantEmailSettings | null>;
async function incrementEmailCount(tenantId: string): Promise<void>;
async function isEmailQuotaExceeded(tenantId: string): Promise<boolean>;
```

#### 3. Admin API Endpoints

New endpoints in `admin_api.py`:

```python
@app.post("/api/v1/admin/tenants/{tenant_id}/email-settings")
async def update_tenant_email_settings(
    tenant_id: str,
    settings: TenantEmailSettingsRequest,
    current_user: User = Depends(get_current_user),
):
    """Update email settings for a tenant."""

@app.get("/api/v1/admin/tenants/{tenant_id}/email-settings")
async def get_tenant_email_settings(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get email settings for a tenant (API key masked)."""

@app.get("/api/v1/admin/tenants/{tenant_id}/email-stats")
async def get_tenant_email_stats(
    tenant_id: str,
    days: int = 30,
    current_user: User = Depends(get_current_user),
):
    """Get email sending statistics for a tenant."""
```

### Implementation Details

#### Phase 1: A2A Server Changes

**File: `a2a_server/knative_events.py`**

1. Add `tenant_id` parameter to `publish_task_event()`
2. Include `tenant_id` in CloudEvent headers (`ce-tenant`)
3. Include `tenant_id` in event body
4. Add `notify_email` parameter support

**File: `a2a_server/automation_api.py`**

1. Pass `tenant_id` from authenticated user to `publish_task_event()`
2. Pass `notify_email` from task request

**File: `a2a_server/database.py`**

1. Add migration for `tenant_email_settings` table
2. Add encryption/decryption functions for API keys

#### Phase 2: Worker Changes

**File: `agent/packages/agent/src/server/routes/cloudevent.ts`**

1. Extract `tenant_id` from CloudEvent headers (`ce-tenant`)
2. Set PostgreSQL tenant context before all DB operations:
   ```typescript
   await sql`SELECT set_config('app.current_tenant_id', ${tenantId}, false)`
   ```
3. Query tenant email config from DB
4. Use tenant-specific credentials for SendGrid

**File: `agent/packages/agent/src/util/tenant-email.ts`** (NEW)

```typescript
import { Storage } from '../storage/storage';

export async function getTenantEmailConfig(tenantId: string): Promise<TenantEmailConfig | null> {
  // Set tenant context
  await Storage.query(
    `SELECT set_config('app.current_tenant_id', $1, false)`,
    [tenantId]
  );
  
  // Query settings
  const result = await Storage.query(
    `SELECT * FROM tenant_email_settings WHERE tenant_id = $1 AND enabled = true`,
    [tenantId]
  );
  
  if (!result.rows.length) {
    return null;
  }
  
  const row = result.rows[0];
  
  // Decrypt API key
  const decryptedKey = await Storage.query(
    `SELECT pgp_sym_decrypt($1::bytea, $2) as key`,
    [row.api_key_encrypted, process.env.DB_ENCRYPTION_KEY]
  );
  
  return {
    provider: row.provider,
    apiKey: decryptedKey.rows[0].key,
    fromEmail: row.from_email,
    fromName: row.from_name,
    replyToDomain: row.reply_to_domain,
    providerSettings: row.provider_settings,
  };
}
```

**File: `agent/packages/agent/src/util/email.ts`**

Modify to support tenant-specific configuration:

```typescript
export async function sendTaskCompletionEmail(
  params: TaskCompletionEmailParams,
  tenantConfig?: TenantEmailConfig  // NEW PARAMETER
): Promise<boolean> {
  // Use tenant config if provided, otherwise fall back to global
  const config = tenantConfig || getGlobalEmailConfig();
  
  if (!config.apiKey || !config.fromEmail) {
    console.warn('[email] Email not configured for tenant');
    return false;
  }
  
  // Build email with tenant-specific from address
  const fromEmail = config.fromEmail;
  const fromName = config.fromName || 'CodeTether';
  
  // ... rest of email logic
}
```

#### Phase 3: Helm/Kubernetes Changes

**File: `chart/a2a-server/templates/knative-worker-template.yaml`**

Add database encryption key:

```yaml
env:
  # ... existing env vars ...
  - name: DB_ENCRYPTION_KEY
    valueFrom:
      secretKeyRef:
        name: {{ .Values.knative.worker.dbEncryptionSecret }}
        key: encryption-key
```

### Security Considerations

1. **Encryption at Rest**: API keys encrypted with AES-256
2. **Encryption in Transit**: Use TLS for all SendGrid API calls
3. **Key Rotation**: Support for rotating encryption keys without downtime
4. **Audit Logging**: Log all email sends with tenant_id (but not API keys)
5. **Rate Limiting**: Per-tenant daily limits to prevent abuse
6. **Credential Isolation**: Workers only access their own tenant's credentials

### Configuration

#### Environment Variables (A2A Server)

```bash
# Global fallback settings (for single-tenant or default)
SENDGRID_API_KEY=SG.xxx
SENDGRID_FROM_EMAIL=noreply@codetether.run

# Database encryption
DB_ENCRYPTION_KEY=32-byte-key-for-aes-256
```

#### Environment Variables (Worker)

```bash
# Database encryption key (must match A2A server)
DB_ENCRYPTION_KEY=32-byte-key-for-aes-256

# Global fallback (optional)
SENDGRID_API_KEY=SG.xxx
```

### Testing Requirements

#### Unit Tests

1. **Tenant Context Setting**: Verify RLS policies work correctly
2. **Email Config Retrieval**: Test encryption/decryption
3. **Rate Limiting**: Test daily limit enforcement
4. **Provider Switching**: Test different email providers

#### Integration Tests

1. **End-to-End Flow**:
   - Create tenant with email settings
   - Submit task with `notify_email`
   - Verify email received with correct From address
   
2. **Multi-Tenant Isolation**:
   - Tenant A sends email
   - Verify Tenant B cannot see Tenant A's settings
   - Verify emails use correct tenant-specific From addresses

3. **Failure Scenarios**:
   - Tenant without email settings (should use global fallback)
   - Invalid API key (should fail gracefully)
   - Rate limit exceeded (should queue or reject)

### Migration Plan

#### Step 1: Database Migration (Zero Downtime)

```sql
-- Create new table
CREATE TABLE tenant_email_settings (...);

-- Enable RLS
ALTER TABLE tenant_email_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY ...;

-- Backfill existing tenants with global config
INSERT INTO tenant_email_settings (...) 
SELECT ... FROM tenants;
```

#### Step 2: A2A Server Update

1. Deploy new version that passes `tenant_id` in CloudEvents
2. Both old and new workers can process events

#### Step 3: Worker Update

1. Deploy workers with tenant email support
2. Workers read tenant config from DB
3. Gradually migrate tenants to use per-tenant settings

#### Step 4: Cleanup

1. Remove global SendGrid config from workers (optional)
2. Update documentation

### Rollback Plan

If issues occur:
1. Revert to previous worker image (uses global config)
2. A2A server continues to work (backward compatible)
3. No data loss (tenant settings preserved)

### Documentation Updates

1. **Admin Guide**: How to configure per-tenant email
2. **API Docs**: New endpoints for email settings
3. **Deployment Guide**: Environment variable configuration
4. **Security Guide**: Encryption and credential management

### Success Metrics

1. **Functional**: All tenants can send emails with their own credentials
2. **Performance**: Email sending latency < 5 seconds
3. **Security**: Zero credential leaks in logs
4. **Reliability**: 99.9% email delivery rate
5. **Isolation**: Tenant A cannot access Tenant B's settings

### Future Enhancements

1. **Multiple Providers per Tenant**: Support for primary/backup providers
2. **Email Templates**: Per-tenant customizable templates
3. **Advanced Analytics**: Delivery rates, open rates per tenant
4. **Webhook Support**: Real-time delivery status
5. **Email Scheduling**: Queue emails for off-peak sending

## Acceptance Criteria

- [ ] A2A server passes `tenant_id` in all CloudEvents
- [ ] Workers set tenant context before DB operations
- [ ] Workers query tenant-specific email config
- [ ] Emails sent with tenant-specific From address
- [ ] RLS prevents cross-tenant data access
- [ ] API keys encrypted at rest
- [ ] Rate limiting enforced per-tenant
- [ ] Backward compatibility maintained
- [ ] All tests passing
- [ ] Documentation updated

## Estimated Effort

- **A2A Server Changes**: 1 day
- **Database Migration**: 2 hours
- **Worker Changes**: 2 days
- **Testing**: 1 day
- **Documentation**: 4 hours

**Total: ~5 days**

## Risks

1. **Performance**: DB encryption/decryption overhead
   - **Mitigation**: Benchmark and optimize queries
   
2. **Complexity**: More moving parts
   - **Mitigation**: Comprehensive testing, feature flags
   
3. **Migration**: Existing tenants need settings
   - **Mitigation**: Automated backfill script

## Open Questions

1. Should we support multiple email providers simultaneously?
2. How should we handle email bounces per tenant?
3. Should tenants be able to configure their own email templates?
4. What's the maximum daily email limit per tenant?

## Appendix

### Database Encryption Example

```sql
-- Encrypt API key
SELECT pgp_sym_encrypt('SG.xxx', 'encryption-key');

-- Decrypt API key
SELECT pgp_sym_decrypt(encrypted_column::bytea, 'encryption-key');
```

### CloudEvent Example

```json
{
  "specversion": "1.0",
  "type": "codetether.task.created",
  "source": "a2a-server",
  "id": "uuid",
  "tenant": "tenant-uuid-123",
  "data": {
    "task_id": "task-456",
    "session_id": "session-789",
    "tenant_id": "tenant-uuid-123",
    "notify_email": "user@example.com",
    "prompt": "Say hello"
  }
}
```
