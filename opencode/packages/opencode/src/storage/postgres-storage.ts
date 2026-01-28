/**
 * PostgreSQL Storage Backend for OpenCode
 * 
 * This module provides a PostgreSQL-backed storage implementation that
 * mirrors the file-based Storage API. It's designed for distributed
 * worker architectures where multiple processes need shared access.
 * 
 * Security:
 * - Row-Level Security (RLS) enforced via tenant_id column
 * - Tenant context set via app.current_tenant_id session variable
 * - Integrates with Keycloak organizations for multi-tenant isolation
 * 
 * Schema:
 * - Single JSONB table with composite key path + tenant_id
 * - GIN index on key_path for efficient prefix queries (list operations)
 * - Optimistic locking via version column for concurrent updates
 */

import { Log } from "../util/log"
import { NamedError } from "@opencode-ai/util/error"
import z from "zod"
import postgres from "postgres"

const log = Log.create({ service: "postgres-storage" })

export namespace PostgresStorage {
  export const NotFoundError = NamedError.create(
    "NotFoundError",
    z.object({
      message: z.string(),
    }),
  )

  let sql: postgres.Sql | null = null
  let initialized = false
  let currentTenantId: string | null = null

  /**
   * Set the current tenant ID for RLS enforcement
   * This should be called with the Keycloak org ID from the JWT token
   */
  export function setTenantId(tenantId: string | null) {
    currentTenantId = tenantId
    log.info("Tenant context set", { tenantId })
  }

  /**
   * Get the current tenant ID
   */
  export function getTenantId(): string | null {
    // Check environment variable first (for worker mode)
    const envTenantId = process.env.OPENCODE_TENANT_ID
    if (envTenantId) return envTenantId
    return currentTenantId
  }

  /**
   * Initialize the PostgreSQL connection and ensure schema exists
   */
  export async function init(databaseUrl?: string) {
    if (initialized && sql) return sql

    const url = databaseUrl || process.env.DATABASE_URL || process.env.OPENCODE_DATABASE_URL
    if (!url) {
      throw new Error(
        "PostgreSQL storage requires DATABASE_URL or OPENCODE_DATABASE_URL environment variable"
      )
    }

    sql = postgres(url, {
      max: 10,
      idle_timeout: 20,
      connect_timeout: 10,
    })

    // Create schema if not exists (includes tenant_id for RLS)
    // Use COALESCE in unique constraint to handle NULL tenant_id
    await sql`
      CREATE TABLE IF NOT EXISTS opencode_storage (
        id SERIAL PRIMARY KEY,
        key_path TEXT[] NOT NULL,
        tenant_id TEXT DEFAULT NULL,
        value JSONB NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `

    // Add tenant_id column if it doesn't exist (migration for existing tables)
    await sql`
      ALTER TABLE opencode_storage 
      ADD COLUMN IF NOT EXISTS tenant_id TEXT DEFAULT NULL
    `.catch(() => {
      // Column might already exist
    })

    // Create unique constraint on key_path + tenant_id (using COALESCE for NULL handling)
    await sql`
      CREATE UNIQUE INDEX IF NOT EXISTS idx_opencode_storage_key_tenant
      ON opencode_storage (key_path, COALESCE(tenant_id, '__NULL__'))
    `.catch(() => {
      // Index might already exist
    })

    // Create index for prefix queries (list operations)
    await sql`
      CREATE INDEX IF NOT EXISTS idx_opencode_storage_key_path 
      ON opencode_storage USING GIN (key_path)
    `.catch(() => {})

    // Create index for tenant queries
    await sql`
      CREATE INDEX IF NOT EXISTS idx_opencode_storage_tenant
      ON opencode_storage (tenant_id)
    `.catch(() => {})

    // Enable RLS on the table
    await sql`
      ALTER TABLE opencode_storage ENABLE ROW LEVEL SECURITY
    `.catch(() => {
      // Ignore if already enabled
    })

    await sql`
      ALTER TABLE opencode_storage FORCE ROW LEVEL SECURITY
    `.catch(() => {
      // Ignore if already forced
    })

    // Create RLS policies (idempotent - drop first)
    await sql`DROP POLICY IF EXISTS tenant_isolation_opencode_storage_select ON opencode_storage`
    await sql`DROP POLICY IF EXISTS tenant_isolation_opencode_storage_insert ON opencode_storage`
    await sql`DROP POLICY IF EXISTS tenant_isolation_opencode_storage_update ON opencode_storage`
    await sql`DROP POLICY IF EXISTS tenant_isolation_opencode_storage_delete ON opencode_storage`

    // SELECT policy: Can see rows for current tenant or if no tenant context
    await sql`
      CREATE POLICY tenant_isolation_opencode_storage_select ON opencode_storage
        FOR SELECT
        USING (
          tenant_id = current_setting('app.current_tenant_id', true)
          OR current_setting('app.current_tenant_id', true) IS NULL
          OR current_setting('app.current_tenant_id', true) = ''
          OR tenant_id IS NULL
        )
    `

    // INSERT policy
    await sql`
      CREATE POLICY tenant_isolation_opencode_storage_insert ON opencode_storage
        FOR INSERT
        WITH CHECK (
          tenant_id = current_setting('app.current_tenant_id', true)
          OR current_setting('app.current_tenant_id', true) IS NULL
          OR current_setting('app.current_tenant_id', true) = ''
          OR tenant_id IS NULL
        )
    `

    // UPDATE policy
    await sql`
      CREATE POLICY tenant_isolation_opencode_storage_update ON opencode_storage
        FOR UPDATE
        USING (
          tenant_id = current_setting('app.current_tenant_id', true)
          OR current_setting('app.current_tenant_id', true) IS NULL
          OR current_setting('app.current_tenant_id', true) = ''
          OR tenant_id IS NULL
        )
        WITH CHECK (
          tenant_id = current_setting('app.current_tenant_id', true)
          OR current_setting('app.current_tenant_id', true) IS NULL
          OR current_setting('app.current_tenant_id', true) = ''
          OR tenant_id IS NULL
        )
    `

    // DELETE policy
    await sql`
      CREATE POLICY tenant_isolation_opencode_storage_delete ON opencode_storage
        FOR DELETE
        USING (
          tenant_id = current_setting('app.current_tenant_id', true)
          OR current_setting('app.current_tenant_id', true) IS NULL
          OR current_setting('app.current_tenant_id', true) = ''
          OR tenant_id IS NULL
        )
    `

    log.info("PostgreSQL storage initialized with RLS policies")
    initialized = true
    return sql
  }

  /**
   * Execute a function with tenant context set
   */
  async function withTenantContext<T>(fn: (db: postgres.Sql) => Promise<T>): Promise<T> {
    const db = await init()
    const tenantId = getTenantId()

    if (tenantId) {
      // Set tenant context for this transaction
      await db`SELECT set_config('app.current_tenant_id', ${tenantId}, false)`
    }

    try {
      return await fn(db)
    } finally {
      if (tenantId) {
        // Clear tenant context
        await db`RESET app.current_tenant_id`.catch(() => {})
      }
    }
  }

  /**
   * Read a value by key path
   */
  export async function read<T>(key: string[]): Promise<T> {
    return withTenantContext(async (db) => {
      const tenantId = getTenantId()
      
      const result = await db`
        SELECT value FROM opencode_storage 
        WHERE key_path = ${key}
        AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
      `

      if (result.length === 0) {
        throw new NotFoundError({ message: `Resource not found: ${key.join("/")}` })
      }

      // Parse if string (postgres may return JSONB as string depending on config)
      const value = result[0].value
      if (typeof value === 'string') {
        return JSON.parse(value) as T
      }
      return value as T
    })
  }

  /**
   * Write a value to key path (insert or replace)
   */
  export async function write<T>(key: string[], content: T): Promise<void> {
    return withTenantContext(async (db) => {
      const tenantId = getTenantId()
      
      // Use upsert logic: delete existing + insert
      // This handles the COALESCE unique index properly
      await db`
        DELETE FROM opencode_storage 
        WHERE key_path = ${key}
        AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
      `
      
      await db`
        INSERT INTO opencode_storage (key_path, tenant_id, value, version, created_at, updated_at)
        VALUES (${key}, ${tenantId}, ${JSON.stringify(content)}::jsonb, 1, NOW(), NOW())
      `
    })
  }

  /**
   * Update a value with a transform function (read-modify-write)
   * Uses optimistic locking to handle concurrent updates
   */
  export async function update<T>(key: string[], fn: (draft: T) => void): Promise<T> {
    return withTenantContext(async (db) => {
      const tenantId = getTenantId()
      
      // Retry loop for optimistic locking
      for (let attempt = 0; attempt < 3; attempt++) {
        const result = await db`
          SELECT value, version FROM opencode_storage 
          WHERE key_path = ${key}
          AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
        `

        if (result.length === 0) {
          throw new NotFoundError({ message: `Resource not found: ${key.join("/")}` })
        }

        const { value, version } = result[0]
        // Parse if string and create mutable copy (postgres returns JSONB as frozen strings)
        const parsed = typeof value === 'string' ? JSON.parse(value) : value
        const draft = { ...parsed } as T  // Shallow copy - for nested objects use structuredClone on parsed
        fn(draft)

        // Attempt to update with version check
        const updated = await db`
          UPDATE opencode_storage 
          SET value = ${JSON.stringify(draft)}::jsonb,
              version = version + 1,
              updated_at = NOW()
          WHERE key_path = ${key} 
          AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
          AND version = ${version}
          RETURNING value
        `

        if (updated.length > 0) {
          const updatedValue = updated[0].value
          return (typeof updatedValue === 'string' ? JSON.parse(updatedValue) : updatedValue) as T
        }

        // Version mismatch - retry
        log.warn("Optimistic lock conflict, retrying", { key, attempt })
      }

      throw new Error(`Failed to update ${key.join("/")} after 3 attempts`)
    })
  }

  /**
   * Remove a value by key path
   */
  export async function remove(key: string[]): Promise<void> {
    return withTenantContext(async (db) => {
      const tenantId = getTenantId()
      
      await db`
        DELETE FROM opencode_storage 
        WHERE key_path = ${key}
        AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
      `
    })
  }

  /**
   * List all keys with a given prefix
   * Returns array of key paths (without .json suffix, matching file storage behavior)
   */
  export async function list(prefix: string[]): Promise<string[][]> {
    return withTenantContext(async (db) => {
      const tenantId = getTenantId()
      
      // Use array containment for prefix matching
      const result = await db`
        SELECT key_path FROM opencode_storage 
        WHERE key_path[1:${prefix.length}] = ${prefix}
        AND COALESCE(tenant_id, '__NULL__') = COALESCE(${tenantId}, '__NULL__')
        ORDER BY key_path
      `

      return result.map((row) => row.key_path as string[])
    })
  }

  /**
   * Close the database connection
   */
  export async function close(): Promise<void> {
    if (sql) {
      await sql.end()
      sql = null
      initialized = false
      log.info("PostgreSQL storage connection closed")
    }
  }

  /**
   * Check if PostgreSQL storage is available (DATABASE_URL is set)
   */
  export function isAvailable(): boolean {
    return !!(process.env.DATABASE_URL || process.env.OPENCODE_DATABASE_URL)
  }

  /**
   * Execute a raw SQL query
   * Useful for setting tenant context or other administrative queries
   */
  export async function execute<T = any>(
    query: string,
    params?: any[]
  ): Promise<T[]> {
    if (!sql) {
      await init()
    }
    if (!sql) {
      throw new Error("PostgreSQL not initialized")
    }
    
    const result = await sql.unsafe(query, params || [])
    return result as T[]
  }

  /**
   * Migrate data from file storage to PostgreSQL for a specific tenant
   * Useful for transitioning existing users to the new backend
   */
  export async function migrateFromFileStorage(
    fileStorageDir: string,
    tenantId: string
  ): Promise<{ migrated: number; errors: string[] }> {
    const Bun = globalThis.Bun
    const path = await import("path")
    
    const errors: string[] = []
    let migrated = 0

    // Set tenant context for migration
    const previousTenantId = currentTenantId
    setTenantId(tenantId)

    try {
      const glob = new Bun.Glob("**/*.json")
      
      for await (const file of glob.scan({ cwd: fileStorageDir, absolute: true })) {
        try {
          const relativePath = path.relative(fileStorageDir, file)
          const key = relativePath.replace(/\.json$/, "").split(path.sep)
          const content = await Bun.file(file).json()
          
          await write(key, content)
          migrated++
          
          if (migrated % 100 === 0) {
            log.info("Migration progress", { migrated })
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err)
          errors.push(`${file}: ${message}`)
        }
      }

      log.info("Migration complete", { migrated, errors: errors.length })
    } finally {
      // Restore previous tenant context
      setTenantId(previousTenantId)
    }

    return { migrated, errors }
  }
}
