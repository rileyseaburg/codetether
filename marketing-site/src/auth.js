var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import NextAuth from 'next-auth';
import Keycloak from 'next-auth/providers/keycloak';
function getFirstNonEmptyEnv(...names) {
    for (const name of names) {
        const value = process.env[name];
        if (value && value.trim().length > 0) {
            return value.trim();
        }
    }
    return undefined;
}
const keycloakUrl = getFirstNonEmptyEnv('KEYCLOAK_URL', 'AUTH_KEYCLOAK_URL') || 'https://auth.quantum-forge.io';
const keycloakRealm = getFirstNonEmptyEnv('KEYCLOAK_REALM', 'AUTH_KEYCLOAK_REALM') || 'quantum-forge';
const keycloakIssuer = getFirstNonEmptyEnv('KEYCLOAK_ISSUER', 'AUTH_KEYCLOAK_ISSUER') || `${keycloakUrl}/realms/${keycloakRealm}`;
const keycloakClientId = getFirstNonEmptyEnv('KEYCLOAK_CLIENT_ID', 'AUTH_KEYCLOAK_ID') || 'a2a-monitor';
const keycloakClientSecret = getFirstNonEmptyEnv('KEYCLOAK_CLIENT_SECRET', 'AUTH_KEYCLOAK_SECRET');
const explicitPublicClient = getFirstNonEmptyEnv('KEYCLOAK_PUBLIC_CLIENT');
const keycloakPublicClient = explicitPublicClient === 'true' ||
    (!keycloakClientSecret && explicitPublicClient !== 'false');
const keycloakTokenEndpointAuthMethod = getFirstNonEmptyEnv('KEYCLOAK_TOKEN_ENDPOINT_AUTH_METHOD') || (keycloakPublicClient ? 'none' : 'client_secret_post');
if (explicitPublicClient === 'false' && !keycloakClientSecret) {
    throw new Error('KEYCLOAK_CLIENT_SECRET is required when KEYCLOAK_PUBLIC_CLIENT=false. ' +
        'Set a valid client secret or set KEYCLOAK_PUBLIC_CLIENT=true for public clients.');
}
if (!keycloakClientSecret && explicitPublicClient !== 'true') {
    console.warn('No KEYCLOAK_CLIENT_SECRET found; treating Keycloak client as public. ' +
        'If your client is confidential, set KEYCLOAK_CLIENT_SECRET and KEYCLOAK_PUBLIC_CLIENT=false.');
}
// Debug logging for auth configuration
console.log('[AUTH CONFIG] Keycloak configuration:', {
    clientId: keycloakClientId,
    issuer: keycloakIssuer,
    hasSecret: !!keycloakClientSecret,
    secretLength: keycloakClientSecret === null || keycloakClientSecret === void 0 ? void 0 : keycloakClientSecret.length,
    publicClient: keycloakPublicClient,
    tokenAuthMethod: keycloakTokenEndpointAuthMethod,
    nodeEnv: process.env.NODE_ENV,
});
const keycloakProviderConfig = {
    clientId: keycloakClientId,
    issuer: keycloakIssuer,
    client: {
        token_endpoint_auth_method: keycloakTokenEndpointAuthMethod,
    },
    // Disable PKCE and state checks for Cypress E2E testing (cookies don't persist across cy.origin)
    // WARNING: Only use in dev/test - re-enable for production
    checks: process.env.NODE_ENV === 'development' ? [] : ['pkce'],
};
if (!keycloakPublicClient && keycloakClientSecret) {
    keycloakProviderConfig.clientSecret = keycloakClientSecret;
}
// Helper to decode JWT payload (without verification - just for reading claims)
function decodeJwtPayload(token) {
    try {
        const parts = token.split('.');
        if (parts.length !== 3)
            return null;
        const payload = parts[1];
        const decoded = Buffer.from(payload, 'base64').toString('utf-8');
        return JSON.parse(decoded);
    }
    catch (_a) {
        return null;
    }
}
// Extract roles from Keycloak JWT token
function extractRolesFromToken(accessToken) {
    var _a;
    const payload = decodeJwtPayload(accessToken);
    if (!payload)
        return [];
    const roles = [];
    // Realm roles (realm_access.roles)
    if ((_a = payload.realm_access) === null || _a === void 0 ? void 0 : _a.roles) {
        roles.push(...payload.realm_access.roles);
    }
    // Client roles (resource_access.<client>.roles)
    if (payload.resource_access) {
        for (const client of Object.values(payload.resource_access)) {
            if (client === null || client === void 0 ? void 0 : client.roles) {
                roles.push(...client.roles);
            }
        }
    }
    return [...new Set(roles)]; // dedupe
}
// Extract tenant info from Keycloak JWT token
function extractTenantFromToken(accessToken) {
    const payload = decodeJwtPayload(accessToken);
    if (!payload)
        return {};
    return {
        // Keycloak can include custom claims for tenant
        tenantId: payload.tenant_id || payload.tenantId || payload['codetether:tenant_id'],
        tenantSlug: payload.tenant_slug || payload.tenantSlug || payload['codetether:tenant_slug'],
    };
}
// Fall back to the shared API unless the backend explicitly returns a tenant instance URL.
function getSharedApiUrl() {
    return process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run';
}
// Fetch tenant info from the API (for users whose JWT doesn't have tenant claims)
function fetchTenantInfo(accessToken) {
    return __awaiter(this, void 0, void 0, function* () {
        var _a;
        try {
            // Server-side: use API_URL (full URL), fall back to NEXT_PUBLIC_API_URL or production
            const apiUrl = getSharedApiUrl();
            const response = yield fetch(`${apiUrl}/v1/tenants/me`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
            });
            if (!response.ok) {
                // User may not have a tenant yet (new signup flow)
                console.log('User does not have a tenant yet');
                return {};
            }
            const tenant = yield response.json();
            // Extract subdomain from realm_name (e.g., "riley-041b27.codetether.run" -> "riley-041b27")
            const tenantSlug = ((_a = tenant.realm_name) === null || _a === void 0 ? void 0 : _a.split('.')[0]) || tenant.subdomain;
            // Ensure HTTPS — k8s_external_url may be stored with http:// which causes mixed content errors
            let tenantApiUrl = getSharedApiUrl();
            if (typeof tenant.k8s_external_url === 'string' && tenant.k8s_external_url.trim()) {
                tenantApiUrl = tenant.k8s_external_url.trim();
            }
            if (tenantApiUrl.startsWith('http://')) {
                tenantApiUrl = tenantApiUrl.replace('http://', 'https://');
            }
            return {
                tenantId: tenant.id,
                tenantSlug: tenantSlug,
                tenantApiUrl,
            };
        }
        catch (error) {
            console.error('Failed to fetch tenant info:', error);
            return {};
        }
    });
}
// Refresh the access token using Keycloak's token endpoint
function refreshAccessToken(token) {
    return __awaiter(this, void 0, void 0, function* () {
        var _a;
        try {
            const tokenEndpoint = `${keycloakIssuer}/protocol/openid-connect/token`;
            const requestBody = new URLSearchParams({
                grant_type: 'refresh_token',
                client_id: keycloakClientId,
                refresh_token: token.refreshToken,
            });
            if (!keycloakPublicClient && keycloakClientSecret) {
                requestBody.set('client_secret', keycloakClientSecret);
            }
            const response = yield fetch(tokenEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: requestBody,
            });
            const refreshedTokens = yield response.json();
            if (!response.ok) {
                console.error('Token refresh failed:', refreshedTokens);
                // For invalid_grant, the refresh token is revoked - clear all tokens to force re-login
                if (refreshedTokens.error === 'invalid_grant') {
                    return {
                        error: 'RefreshAccessTokenError',
                    };
                }
                // Return error state instead of throwing - allows graceful session invalidation
                return Object.assign(Object.assign({}, token), { error: refreshedTokens.error || 'RefreshAccessTokenError' });
            }
            console.log('Token refreshed successfully');
            return Object.assign(Object.assign({}, token), { accessToken: refreshedTokens.access_token, idToken: refreshedTokens.id_token, expiresAt: Math.floor(Date.now() / 1000) + refreshedTokens.expires_in, refreshToken: (_a = refreshedTokens.refresh_token) !== null && _a !== void 0 ? _a : token.refreshToken, roles: extractRolesFromToken(refreshedTokens.access_token) });
        }
        catch (error) {
            console.error('Error refreshing access token:', error);
            return Object.assign(Object.assign({}, token), { error: 'RefreshAccessTokenError' });
        }
    });
}
export const { handlers, signIn, signOut, auth } = NextAuth({
    providers: [
        Keycloak(keycloakProviderConfig),
    ],
    pages: {
        error: '/login',
    },
    callbacks: {
        jwt(_a) {
            return __awaiter(this, arguments, void 0, function* ({ token, account, profile }) {
                // Initial sign in - persist OAuth tokens
                if (account) {
                    console.log('Initial sign in, storing tokens');
                    token.accessToken = account.access_token;
                    token.refreshToken = account.refresh_token;
                    token.expiresAt = account.expires_at;
                    token.idToken = account.id_token;
                    token.roles = extractRolesFromToken(account.access_token);
                    // Try to extract tenant info from JWT claims first
                    const jwtTenantInfo = extractTenantFromToken(account.access_token);
                    if (jwtTenantInfo.tenantId) {
                        // Tenant info in JWT - use it directly
                        token.tenantId = jwtTenantInfo.tenantId;
                        token.tenantSlug = jwtTenantInfo.tenantSlug;
                        token.tenantApiUrl = getSharedApiUrl();
                    }
                    else {
                        // No tenant in JWT - fetch from API
                        const apiTenantInfo = yield fetchTenantInfo(account.access_token);
                        token.tenantId = apiTenantInfo.tenantId;
                        token.tenantSlug = apiTenantInfo.tenantSlug;
                        token.tenantApiUrl = apiTenantInfo.tenantApiUrl;
                    }
                    // Add user info from profile
                    if (profile) {
                        token.email = profile.email;
                        token.name = profile.name;
                        token.preferred_username = profile.name;
                    }
                    return token;
                }
                // Return previous token if the access token has not expired yet
                // Add 60 second buffer to refresh before actual expiration
                const expiresAt = token.expiresAt;
                const now = Math.floor(Date.now() / 1000);
                const bufferSeconds = 60;
                // If a previous refresh already failed, don't retry — let the client handle sign-out
                if (token.error === 'RefreshAccessTokenError') {
                    return token;
                }
                if (expiresAt && now < expiresAt - bufferSeconds) {
                    // Token is still valid
                    return token;
                }
                // Access token has expired (or will expire soon), try to refresh it
                console.log('Access token expired, attempting refresh...');
                const refreshedToken = yield refreshAccessToken(token);
                if (refreshedToken.error) {
                    console.log('Refresh failed, clearing session:', refreshedToken.error);
                    return refreshedToken;
                }
                return refreshedToken;
            });
        },
        session(_a) {
            return __awaiter(this, arguments, void 0, function* ({ session, token }) {
                // Send properties to the client
                if (token && session.user) {
                    session.accessToken = token.accessToken;
                    session.refreshToken = token.refreshToken;
                    session.idToken = token.idToken;
                    session.error = token.error;
                    session.user.roles = token.roles || [];
                    if (token.preferred_username) {
                        session.user.name = token.preferred_username;
                    }
                    // Explicitly pass email from token to session
                    if (token.email) {
                        session.user.email = token.email;
                    }
                    // Pass tenant info to session
                    session.tenantId = token.tenantId;
                    session.tenantSlug = token.tenantSlug;
                    session.tenantApiUrl = token.tenantApiUrl;
                }
                // Propagate error to client so it can trigger signOut
                if (token.error) {
                    session.error = token.error;
                }
                return session;
            });
        },
        redirect(_a) {
            return __awaiter(this, arguments, void 0, function* ({ url, baseUrl }) {
                // Allow redirects to dedicated tenant instances
                // If user has a dedicated instance, redirect there after login
                if (url.startsWith(baseUrl)) {
                    return url;
                }
                // Allow redirects to codetether.run subdomains (tenant instances)
                if (url.includes('.codetether.run')) {
                    return url;
                }
                // Default to dashboard
                return `${baseUrl}/dashboard`;
            });
        },
    },
    session: {
        strategy: 'jwt',
        maxAge: 30 * 24 * 60 * 60,
    },
});
