import NextAuth from 'next-auth'
import Keycloak from 'next-auth/providers/keycloak'

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

export const { handlers, signIn, signOut, auth } = NextAuth({
    providers: [
        Keycloak({
            clientId: process.env.KEYCLOAK_CLIENT_ID || 'a2a-monitor',
            clientSecret: process.env.KEYCLOAK_CLIENT_SECRET || '',
            issuer: process.env.KEYCLOAK_ISSUER || 'https://auth.quantum-forge.io/realms/quantum-forge',
        }),
    ],
    callbacks: {
        async jwt({ token, account, profile }) {
            // Persist the OAuth access_token and refresh_token to the token
            if (account) {
                token.accessToken = account.access_token
                token.refreshToken = account.refresh_token
                token.expiresAt = account.expires_at
                token.idToken = account.id_token
            }
            
            // Extract roles from the access token (do this every time to handle existing sessions)
            if (token.accessToken) {
                token.roles = extractRolesFromToken(token.accessToken as string)
            }
            
            // Add user info from profile
            if (profile) {
                token.email = profile.email
                token.name = profile.name
                token.preferred_username = profile.name
            }
            return token
        },
        async session({ session, token }) {
            // Send properties to the client
            if (token && session.user) {
                session.accessToken = token.accessToken as string
                session.refreshToken = token.refreshToken as string
                session.idToken = token.idToken as string
                // Pass roles to the session user object
                ;(session.user as any).roles = token.roles || []
                if (token.preferred_username) {
                    session.user.name = token.preferred_username as string
                }
            }
            return session
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
    }
    interface User {
        roles?: string[]
    }
}
