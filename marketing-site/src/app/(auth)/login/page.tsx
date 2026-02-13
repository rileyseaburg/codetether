'use client'

import Link from 'next/link'
import { signIn, useSession } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState, Suspense } from 'react'

import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/Button'
import { TextField } from '@/components/Fields'

function LoginForm() {
  const { status } = useSession()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const callbackUrl = searchParams.get('callbackUrl') || '/dashboard'
  const authError = searchParams.get('error')

  useEffect(() => {
    if (status === 'authenticated') {
      router.push(callbackUrl)
    }
  }, [status, router, callbackUrl])

  useEffect(() => {
    if (authError) {
      setError(
        authError === 'OAuthSignin'
          ? 'Error connecting to Keycloak'
          : authError === 'OAuthCallback'
            ? 'Authentication callback failed'
            : authError === 'Configuration'
              ? 'Authentication is misconfigured (check Keycloak client ID/secret and issuer settings).'
            : authError === 'OAuthAccountNotLinked'
              ? 'Account not linked'
              : 'Authentication failed'
      )
    }
  }, [authError])

  const handleKeycloakLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      await signIn('keycloak', { callbackUrl })
    } catch {
      setError('Failed to initiate login')
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const formData = new FormData(e.currentTarget)
    const email = formData.get('email') as string
    const password = formData.get('password') as string

     const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

    try {
      // Try new self-service user auth first
      const userAuthResponse = await fetch(
        `${apiUrl}/v1/users/login`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        }
      )

      if (userAuthResponse.ok) {
        const data = await userAuthResponse.json()
        // Store token and user info
        localStorage.setItem('a2a_token', data.access_token)
        localStorage.setItem('a2a_user', JSON.stringify(data.user))
        // Also set cookie for server-side middleware
        document.cookie = `a2a_token=${data.access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`
        router.push(callbackUrl)
        return
      }

      // Fall back to Keycloak-based auth
      const keycloakResponse = await fetch(
        `${apiUrl}/v1/auth/login`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: email, password }),
        }
      )

      if (keycloakResponse.ok) {
        const data = await keycloakResponse.json()
        // Store token and redirect
        localStorage.setItem('a2a_token', data.accessToken || data.access_token)
        localStorage.setItem('a2a_refresh_token', data.refreshToken || data.refresh_token || '')
        localStorage.setItem('a2a_session', JSON.stringify(data.session || {}))
        router.push(callbackUrl)
      } else {
        const errorData = await keycloakResponse.json().catch(() => ({}))
        setError(errorData.detail || 'Invalid email or password')
      }
    } catch {
      setError('Failed to connect to authentication server')
    } finally {
      setLoading(false)
    }
  }

  if (status === 'loading') {
    return (
      <AuthLayout title="Loading..." subtitle="">
        <div className="flex justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Sign in to account"
      subtitle={
        <>
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-cyan-600">
            Sign up
          </Link>{' '}
          for a free trial.
        </>
      }
    >
      {error && (
        <div className="mb-6 rounded-lg bg-red-50 p-4 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Keycloak SSO Button */}
      <button
        type="button"
        onClick={handleKeycloakLogin}
        disabled={loading}
        data-testid="keycloak-sso-button"
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
        </svg>
        {loading ? 'Connecting...' : 'Continue with Quantum Forge SSO'}
      </button>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-300 dark:border-gray-600" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-2 text-gray-500 dark:bg-gray-900 dark:text-gray-400">
            Or continue with email
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="space-y-6">
          <TextField
            label="Email address"
            name="email"
            type="email"
            autoComplete="email"
            required
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </div>
        <Button
          type="submit"
          color="cyan"
          className="mt-8 w-full"
          disabled={loading}
        >
          {loading ? 'Signing in...' : 'Sign in to account'}
        </Button>
      </form>
    </AuthLayout>
  )
}

export default function Login() {
  return (
    <Suspense
      fallback={
        <AuthLayout title="Loading..." subtitle="">
          <div className="flex justify-center py-8">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
          </div>
        </AuthLayout>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
