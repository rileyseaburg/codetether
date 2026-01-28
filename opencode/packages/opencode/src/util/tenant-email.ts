/**
 * Tenant Email Configuration Module
 * 
 * Provides multi-tenant email support with per-tenant configuration,
 * API key encryption/decryption, and rate limiting.
 */

import { Storage } from "../storage/storage"
import { Log } from "./log"

const log = Log.create({ service: "tenant-email" })

export interface TenantEmailConfig {
  provider: 'sendgrid' | 'aws-ses' | 'postmark' | 'smtp'
  apiKey: string
  fromEmail: string
  fromName?: string
  replyToDomain?: string
  providerSettings?: Record<string, any>
}

export interface TenantEmailSettings {
  tenantId: string
  enabled: boolean
  dailyLimit: number
  emailsSentToday: number
  lastResetDate: string
  config: TenantEmailConfig
}

/**
 * Get email configuration for a specific tenant
 * Queries the database with tenant context set via RLS
 */
export async function getTenantEmailConfig(
  tenantId: string
): Promise<TenantEmailSettings | null> {
  try {
    // Set tenant context for RLS
    await Storage.query(
      `SELECT set_config('app.current_tenant_id', $1, false)`,
      [tenantId]
    )

    // Query tenant email settings
    const result = await Storage.query(
      `SELECT 
        tenant_id,
        provider,
        api_key_encrypted,
        from_email,
        from_name,
        reply_to_domain,
        provider_settings,
        enabled,
        daily_limit,
        emails_sent_today,
        last_reset_date
      FROM tenant_email_settings 
      WHERE tenant_id = $1 AND enabled = true`,
      [tenantId]
    )

    if (!result.rows.length) {
      log.debug("no email settings found for tenant", { tenantId })
      return null
    }

    const row = result.rows[0]

    // Decrypt API key using database function
    const decryptedResult = await Storage.query(
      `SELECT pgp_sym_decrypt($1::bytea, current_setting('app.encryption_key', true)) as api_key`,
      [row.api_key_encrypted]
    )

    if (!decryptedResult.rows.length || !decryptedResult.rows[0].api_key) {
      log.error("failed to decrypt API key for tenant", { tenantId })
      return null
    }

    return {
      tenantId: row.tenant_id,
      enabled: row.enabled,
      dailyLimit: row.daily_limit,
      emailsSentToday: row.emails_sent_today,
      lastResetDate: row.last_reset_date,
      config: {
        provider: row.provider,
        apiKey: decryptedResult.rows[0].api_key,
        fromEmail: row.from_email,
        fromName: row.from_name,
        replyToDomain: row.reply_to_domain,
        providerSettings: row.provider_settings || {},
      },
    }
  } catch (error) {
    log.error("failed to get tenant email config", { 
      tenantId, 
      error: error instanceof Error ? error.message : String(error) 
    })
    return null
  }
}

/**
 * Check if tenant has exceeded their daily email quota
 */
export async function isEmailQuotaExceeded(tenantId: string): Promise<boolean> {
  try {
    // Set tenant context
    await Storage.query(
      `SELECT set_config('app.current_tenant_id', $1, false)`,
      [tenantId]
    )

    const result = await Storage.query(
      `SELECT daily_limit, emails_sent_today, last_reset_date
      FROM tenant_email_settings 
      WHERE tenant_id = $1`,
      [tenantId]
    )

    if (!result.rows.length) {
      return true // No settings = no emails allowed
    }

    const row = result.rows[0]
    const today = new Date().toISOString().split('T')[0]

    // Reset counter if it's a new day
    if (row.last_reset_date !== today) {
      await Storage.query(
        `UPDATE tenant_email_settings 
        SET emails_sent_today = 0, last_reset_date = $2
        WHERE tenant_id = $1`,
        [tenantId, today]
      )
      return false
    }

    return row.emails_sent_today >= row.daily_limit
  } catch (error) {
    log.error("failed to check email quota", { 
      tenantId, 
      error: error instanceof Error ? error.message : String(error) 
    })
    return true // Fail closed
  }
}

/**
 * Increment the email count for a tenant
 */
export async function incrementEmailCount(tenantId: string): Promise<void> {
  try {
    // Set tenant context
    await Storage.query(
      `SELECT set_config('app.current_tenant_id', $1, false)`,
      [tenantId]
    )

    const today = new Date().toISOString().split('T')[0]

    await Storage.query(
      `UPDATE tenant_email_settings 
      SET emails_sent_today = emails_sent_today + 1,
          last_reset_date = $2
      WHERE tenant_id = $1`,
      [tenantId, today]
    )
  } catch (error) {
    log.error("failed to increment email count", { 
      tenantId, 
      error: error instanceof Error ? error.message : String(error) 
    })
  }
}

/**
 * Check if tenant email is configured and quota not exceeded
 */
export async function isTenantEmailAvailable(tenantId: string): Promise<boolean> {
  const config = await getTenantEmailConfig(tenantId)
  if (!config || !config.enabled) {
    return false
  }

  const quotaExceeded = await isEmailQuotaExceeded(tenantId)
  return !quotaExceeded
}
