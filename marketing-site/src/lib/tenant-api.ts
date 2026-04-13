export const TENANT_API_PROXY_BASE = '/api/tenant'
export const TENANT_PROXY_TARGET_HEADER = 'x-codetether-tenant-origin'

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0'])
const SHARED_API_HOSTS = new Set(['api.codetether.run'])
const DEFAULT_SHARED_API_URL = 'https://api.codetether.run'

function isLocalHost(hostname: string): boolean {
  return LOCAL_HOSTS.has(hostname.toLowerCase())
}

export function normalizeTenantApiUrl(apiUrl?: string): string | undefined {
  if (!apiUrl) {
    return undefined
  }

  const trimmed = apiUrl.trim()
  if (!trimmed) {
    return undefined
  }

  if (trimmed.startsWith('/')) {
    return trimmed.replace(/\/+$/, '')
  }

  try {
    const parsed = new URL(trimmed)
    if (parsed.protocol === 'http:' && !isLocalHost(parsed.hostname)) {
      parsed.protocol = 'https:'
    }
    parsed.pathname = parsed.pathname.replace(/\/+$/, '')
    parsed.search = ''
    parsed.hash = ''
    return parsed.toString().replace(/\/+$/, '')
  } catch {
    return trimmed.replace(/\/+$/, '')
  }
}

export function getSharedTenantApiUrl(): string {
  return (
    normalizeTenantApiUrl(
      process.env.NEXT_PUBLIC_API_URL || DEFAULT_SHARED_API_URL
    ) || DEFAULT_SHARED_API_URL
  )
}

export function hasDedicatedTenantInstance(
  tenantApiUrl?: string,
  tenantSlug?: string
): boolean {
  const normalized = normalizeTenantApiUrl(tenantApiUrl)
  if (!normalized || normalized.startsWith('/')) {
    return false
  }

  try {
    const hostname = new URL(normalized).hostname.toLowerCase()
    if (isLocalHost(hostname) || SHARED_API_HOSTS.has(hostname)) {
      return false
    }

    if (tenantSlug && normalized.includes(tenantSlug)) {
      return true
    }

    return hostname.endsWith('.codetether.run')
  } catch {
    return Boolean(tenantSlug && normalized.includes(tenantSlug))
  }
}

export function shouldUseTenantApiProxy(
  tenantApiUrl?: string,
  tenantSlug?: string,
  currentHost?: string
): boolean {
  if (!currentHost) {
    return false
  }

  const normalized = normalizeTenantApiUrl(tenantApiUrl)
  if (!normalized || normalized.startsWith('/')) {
    return false
  }

  try {
    return (
      new URL(normalized).host !== currentHost &&
      hasDedicatedTenantInstance(normalized, tenantSlug)
    )
  } catch {
    return false
  }
}

export function isAllowedTenantProxyTarget(apiUrl?: string): boolean {
  const normalized = normalizeTenantApiUrl(apiUrl)
  if (!normalized || normalized.startsWith('/')) {
    return false
  }

  try {
    const parsed = new URL(normalized)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return false
    }

    const hostname = parsed.hostname.toLowerCase()
    return (
      hostname === 'api.codetether.run' ||
      hostname.endsWith('.codetether.run') ||
      isLocalHost(hostname)
    )
  } catch {
    return false
  }
}
