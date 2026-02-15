import NextAuth from 'next-auth'
import Keycloak from 'next-auth/providers/keycloak'

type KeycloakTokenEndpointAuthMethod = 'none' | 'client_secret_post' | 'client_secret_basic'

function getFirstNonEmptyEnv(...names: string[]): string | undefined {
    for (const name of names) {
        const value = process.env[name]
        if (value && value.trim().length > 0) {
            return value.trim()
        }
    }
    return undefined
}

const keycloakUrl = getFirstNonEmptyEnv('KEYCLOAK_URL', 'AUTH_KEYCLOAK_URL') || 'https://auth.quantum-forge.io'
const keycloakRealm = getFirstNonEmptyEnv('KEYCLOAK_REALM', 'AUTH_KEYCLOAK_REALM') || 'quantum-forge'
const keycloakIssuer = getFirstNonEmptyEnv('KEYCLOAK_ISSUER', 'AUTH_KEYCLOAK_ISSUER') || `${keycloakUrl}/realms/${keycloakRealm}`
const keycloakClientId = getFirstNonEmptyEnv('KEYCLOAK_CLIENT_ID', 'AUTH_KEYCLOAK_ID') || 'a2a-monitor'
const keycloakClientSecret = getFirstNonEmptyEnv('KEYCLOAK_CLIENT_SECRET', 'AUTH_KEYCLOAK_SECRET')
const explicitPublicClient = getFirstNonEmptyEnv('KEYCLOAK_PUBLIC_CLIENT')
const keycloakPublicClient =
    explicitPublicClient === 'true' ||
    (!keycloakClientSecret && explicitPublicClient !== 'false')
const keycloakTokenEndpointAuthMethod = (getFirstNonEmptyEnv(
    'KEYCLOAK_TOKEN_ENDPOINT_AUTH_METHOD'
) as KeycloakTokenEndpointAuthMethod | undefined) || (keycloakPublicClient ? 'none' : 'client_secret_post')

if (explicitPublicClient === 'false' && !keycloakClientSecret) {
    throw new Error(
        'KEYCLOAK_CLIENT_SECRET is required when KEYCLOAK_PUBLIC_CLIENT=false. ' +
        'Set a valid client secret or set KEYCLOAK_PUBLIC_CLIENT=true for public clients.'
    )
}

if (!keycloakClientSecret && explicitPublicClient !== 'true') {
    console.warn(
        'No KEYCLOAK_CLIENT_SECRET found; treating Keycloak client as public. ' +
        'If your client is confidential, set KEYCLOAK_CLIENT_SECRET and KEYCLOAK_PUBLIC_CLIENT=false.'
    )
}

// Debug logging for auth configuration
console.log('[AUTH CONFIG] Keycloak configuration:', {
    clientId: keycloakClientId,
    issuer: keycloakIssuer,
    hasSecret: !!keycloakClientSecret,
    secretLength: keycloakClientSecret?.length,
    publicClient: keycloakPublicClient,
    tokenAuthMethod: keycloakTokenEndpointAuthMethod,
    nodeEnv: process.env.NODE_ENV,
})

const keycloakProviderConfig: any = {
    clientId: keycloakClientId,
    issuer: keycloakIssuer,
    client: {
        token_endpoint_auth_method: keycloakTokenEndpointAuthMethod,
    },
    // Disable PKCE and state checks for Cypress E2E testing (cookies don't persist across cy.origin)
    // WARNING: Only use in dev/test - re-enable for production
    checks: process.env.NODE_ENV === 'development' ? [] : ['pkce'],
}

if (!keycloakPublicClient && keycloakClientSecret) {
    keycloakProviderConfig.clientSecret = keycloakClientSecret
}

// Helper to decode JWT payload (without verification - just for reading claims)
function decodeJwtPayload(token: string): Record<string, any> | null {
    try {
        const parts = token.split('.')
        if (parts.length !== 3) return null
        const payload = parts[1]
        const decoded = Buffer.from(payload, 'base64').toString('utf-8')
        return JSON.parse(decoded)
    } catch {
        return null
    }
}

// Extract roles from Keycloak JWT token
function extractRolesFromToken(accessToken: string): string[] {
    const payload = decodeJwtPayload(accessToken)
    if (!payload) return []

    const roles: string[] = []

    // Realm roles (realm_access.roles)
    if (payload.realm_access?.roles) {
        roles.push(...payload.realm_access.roles)
    }

    // Client roles (resource_access.<client>.roles)
    if (payload.resource_access) {
        for (const client of Object.values(payload.resource_access) as any[]) {
            if (client?.roles) {
                roles.push(...client.roles)
            }
        }
    }

    return [...new Set(roles)] // dedupe
}

// Extract tenant info from Keycloak JWT token
function extractTenantFromToken(accessToken: string): { tenantId?: string; tenantSlug?: string } {
    const payload = decodeJwtPayload(accessToken)
    if (!payload) return {}

    return {
        // Keycloak can include custom claims for tenant
        tenantId: payload.tenant_id || payload.tenantId || payload['codetether:tenant_id'],
        tenantSlug: payload.tenant_slug || payload.tenantSlug || payload['codetether:tenant_slug'],
    }
}

// Get the API URL for a tenant
function getTenantApiUrl(tenantSlug?: string): string {
    // If tenant has a dedicated instance, use it
    if (tenantSlug) {
        return `https://${tenantSlug}.codetether.run`
    }
    // Fall back to shared API
    return process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'
}

// Fetch tenant info from the API (for users whose JWT doesn't have tenant claims)
async function fetchTenantInfo(accessToken: string): Promise<{
    tenantId?: string
    tenantSlug?: string
    tenantApiUrl?: string
}> {
    try {
        // Server-side: use API_URL (full URL), fall back to NEXT_PUBLIC_API_URL or production
        const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'
        const response = await fetch(`${apiUrl}/v1/tenants/me`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        })

        if (!response.ok) {
            // User may not have a tenant yet (new signup flow)
            console.log('User does not have a tenant yet')
            return {}
        }

        const tenant = await response.json()

        // Extract subdomain from realm_name (e.g., "riley-041b27.codetether.run" -> "riley-041b27")
        const tenantSlug = tenant.realm_name?.split('.')[0] || tenant.subdomain

        // Ensure HTTPS — k8s_external_url may be stored with http:// which causes mixed content errors
        let tenantApiUrl = tenant.k8s_external_url || getTenantApiUrl(tenantSlug)
        if (tenantApiUrl.startsWith('http://')) {
            tenantApiUrl = tenantApiUrl.replace('http://', 'https://')
        }

        return {
            tenantId: tenant.id,
            tenantSlug: tenantSlug,
            tenantApiUrl,
        }
    } catch (error) {
        console.error('Failed to fetch tenant info:', error)
        return {}
    }
}

// Refresh the access token using Keycloak's token endpoint
async function refreshAccessToken(token: any): Promise<any> {
    try {
        const tokenEndpoint = `${keycloakIssuer}/protocol/openid-connect/token`
        const requestBody = new URLSearchParams({
            grant_type: 'refresh_token',
            client_id: keycloakClientId,
            refresh_token: token.refreshToken as string,
        })

        if (!keycloakPublicClient && keycloakClientSecret) {
            requestBody.set('client_secret', keycloakClientSecret)
        }

        const response = await fetch(tokenEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: requestBody,
        })

        const refreshedTokens = await response.json()

        if (!response.ok) {
            console.error('Token refresh failed:', refreshedTokens)
            // For invalid_grant, the refresh token is revoked - clear all tokens to force re-login
            if (refreshedTokens.error === 'invalid_grant') {
                return {
                    error: 'RefreshAccessTokenError',
                }
            }
            // Return error state instead of throwing - allows graceful session invalidation
            return {
                ...token,
                error: refreshedTokens.error || 'RefreshAccessTokenError',
            }
        }

        console.log('Token refreshed successfully')

        return {
            ...token,
            accessToken: refreshedTokens.access_token,
            idToken: refreshedTokens.id_token,
            expiresAt: Math.floor(Date.now() / 1000) + refreshedTokens.expires_in,
            refreshToken: refreshedTokens.refresh_token ?? token.refreshToken, // Fall back to old refresh token
            roles: extractRolesFromToken(refreshedTokens.access_token),
        }
    } catch (error) {
        console.error('Error refreshing access token:', error)

        return {
            ...token,
            error: 'RefreshAccessTokenError',
        }
    }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
    providers: [
        Keycloak(keycloakProviderConfig),
    ],
    pages: {
        error: '/login',
    },
    callbacks: {
        async jwt({ token, account, profile }) {
            // Initial sign in - persist OAuth tokens
            if (account) {
                console.log('Initial sign in, storing tokens')
                token.accessToken = account.access_token
                token.refreshToken = account.refresh_token
                token.expiresAt = account.expires_at
                token.idToken = account.id_token
                token.roles = extractRolesFromToken(account.access_token as string)

                // Try to extract tenant info from JWT claims first
                const jwtTenantInfo = extractTenantFromToken(account.access_token as string)

                if (jwtTenantInfo.tenantId) {
                    // Tenant info in JWT - use it directly
                    token.tenantId = jwtTenantInfo.tenantId
                    token.tenantSlug = jwtTenantInfo.tenantSlug
                    token.tenantApiUrl = getTenantApiUrl(jwtTenantInfo.tenantSlug)
                } else {
                    // No tenant in JWT - fetch from API
                    const apiTenantInfo = await fetchTenantInfo(account.access_token as string)
                    token.tenantId = apiTenantInfo.tenantId
                    token.tenantSlug = apiTenantInfo.tenantSlug
                    token.tenantApiUrl = apiTenantInfo.tenantApiUrl
                }

                // Add user info from profile
                if (profile) {
                    token.email = profile.email
                    token.name = profile.name
                    token.preferred_username = profile.name
                }

                return token
            }

            // Return previous token if the access token has not expired yet
            // Add 60 second buffer to refresh before actual expiration
            const expiresAt = token.expiresAt as number
            const now = Math.floor(Date.now() / 1000)
            const bufferSeconds = 60

            // If a previous refresh already failed, don't retry — let the client handle sign-out
            if (token.error === 'RefreshAccessTokenError') {
                return token
            }

            if (expiresAt && now < expiresAt - bufferSeconds) {
                // Token is still valid
                return token
            }

            // Access token has expired (or will expire soon), try to refresh it
            console.log('Access token expired, attempting refresh...')
            const refreshedToken = await refreshAccessToken(token)
            if (refreshedToken.error) {
                console.log('Refresh failed, clearing session:', refreshedToken.error)
                return refreshedToken
            }
            return refreshedToken
        },
        async session({ session, token }) {
            // Send properties to the client
            if (token && session.user) {
                session.accessToken = token.accessToken as string
                session.refreshToken = token.refreshToken as string
                session.idToken = token.idToken as string
                session.error = token.error as string | undefined

                    // Pass roles to the session user object
                    ; (session.user as any).roles = token.roles || []
                if (token.preferred_username) {
                    session.user.name = token.preferred_username as string
                }

                // Pass tenant info to session
                session.tenantId = token.tenantId as string | undefined
                session.tenantSlug = token.tenantSlug as string | undefined
                session.tenantApiUrl = token.tenantApiUrl as string | undefined
            }
            // Propagate error to client so it can trigger signOut
            if (token.error) {
                session.error = token.error as string
            }
            return session
        },
        async redirect({ url, baseUrl }) {
            // Allow redirects to dedicated tenant instances
            // If user has a dedicated instance, redirect there after login
            if (url.startsWith(baseUrl)) {
                return url
            }
            // Allow redirects to codetether.run subdomains (tenant instances)
            if (url.includes('.codetether.run')) {
                return url
            }
            // Default to dashboard
            return `${baseUrl}/dashboard`
        },
    },
    session: {
        strategy: 'jwt',
        maxAge: 30 * 24 * 60 * 60,
    },
})

// Extend the Session type to include our custom properties
declare module 'next-auth' {
    interface Session {
        accessToken?: string
        refreshToken?: string
        idToken?: string
        error?: string
        // Tenant info for multi-tenancy
        tenantId?: string
        tenantSlug?: string
        tenantApiUrl?: string
    }
    interface User {
        roles?: string[]
    }
}
