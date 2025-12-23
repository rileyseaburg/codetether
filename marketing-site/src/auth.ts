import NextAuth from 'next-auth'
import Keycloak from 'next-auth/providers/keycloak'

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
            session.accessToken = token.accessToken as string
            session.refreshToken = token.refreshToken as string
            session.idToken = token.idToken as string
            if (token.preferred_username && session.user) {
                session.user.name = token.preferred_username as string
            }
            return session
        },
    },
    pages: {
        signIn: '/login',
        error: '/login',
    },
    session: {
        strategy: 'jwt',
    },
})

// Extend the Session type to include our custom properties
declare module 'next-auth' {
    interface Session {
        accessToken?: string
        refreshToken?: string
        idToken?: string
    }
}
