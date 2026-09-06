// Tenant clients are provisioned as <slug>-spa in <slug>.codetether.run.
// Never accept a caller-supplied issuer URL or client secret.
export const TENANT_AUTH_COOKIE = 'codetether-auth-realm'

export function tenantProviderForRealm(
  realm: string | undefined,
  defaultIssuer: string,
) {
  if (!realm) return undefined
  const match =
    /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.codetether\.run$/.exec(realm)
  if (!match) throw new Error('Invalid workspace realm')

  const issuer = new URL(defaultIssuer)
  if (!/\/realms\/[^/]+\/?$/.test(issuer.pathname)) {
    throw new Error('Invalid Keycloak issuer configuration')
  }
  issuer.pathname = issuer.pathname.replace(
    /\/realms\/[^/]+\/?$/,
    `/realms/${realm}`,
  )
  issuer.search = ''
  issuer.hash = ''

  return {
    issuer: issuer.toString(),
    clientId: `${match[1]}-spa`,
    client: { token_endpoint_auth_method: 'none' as const },
    checks: ['pkce', 'state'] as ('pkce' | 'state')[],
  }
}

export function localAuthRedirect(value: string) {
  // Auth destinations must remain on this app, where the session is stored.
  return value.startsWith('/') &&
    !value.startsWith('//') &&
    !/[\u0000-\u0020\\]/.test(value)
    ? value
    : '/dashboard'
}

export function resolveAuthRedirect(value: string, baseUrl: string) {
  const fallback = new URL('/dashboard', baseUrl).href
  try {
    const target = new URL(value, baseUrl)
    if (target.username || target.password) return fallback
    const sameOrigin = target.origin === new URL(baseUrl).origin
    const tenantOrigin =
      target.protocol === 'https:' &&
      !target.port &&
      target.hostname.endsWith('.codetether.run')
    return sameOrigin || tenantOrigin ? target.href : fallback
  } catch {
    return fallback
  }
}
