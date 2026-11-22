'use server'

import { cookies } from 'next/headers'
import { AuthError } from 'next-auth'
import { redirect } from 'next/navigation'
import { signIn } from '@/auth'
import {
  localAuthRedirect,
  TENANT_AUTH_COOKIE,
  tenantProviderForRealm,
} from '@/lib/tenant-auth'

export async function startWorkspaceSignIn(formData: FormData) {
  const realm = String(formData.get('realm') || '')
  const redirectTo = localAuthRedirect(
    String(formData.get('callbackUrl') || '/dashboard'),
  )
  // Validate before setting the selector; auth.ts derives the actual issuer
  // exclusively from server configuration, not from signup-response URLs.
  tenantProviderForRealm(realm, 'https://auth.invalid/realms/default')
  const store = await cookies()
  if (realm) {
    store.set(TENANT_AUTH_COOKIE, realm, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 900,
    })
  } else {
    store.delete(TENANT_AUTH_COOKIE)
  }
  try {
    await signIn('keycloak', { redirectTo })
  } catch (error) {
    if (!(error instanceof AuthError)) throw error
    redirect(`/login?error=OAuthSignin&realm=${encodeURIComponent(realm)}`)
  }
}
