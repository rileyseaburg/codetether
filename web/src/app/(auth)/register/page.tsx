'use client'

import Link from 'next/link'
import { useState } from 'react'
import { useFormStatus } from 'react-dom'
import { startWorkspaceSignIn } from '../actions'
import { useClientReady } from '@/hooks/useClientReady'

import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/Button'
import { SelectField, TextField } from '@/components/Fields'

interface SignupResult {
  tenant_id: string
  realm_name: string
  login_url: string
  spa_client_id: string
  instance_url?: string
  instance_namespace?: string
  provisioning_status: string
}

function WorkspaceSignInButton() {
  const { pending } = useFormStatus()
  return (
    <button
      type="submit"
      disabled={pending}
      className="block w-full rounded-md bg-cyan-700 px-4 py-3 text-center text-sm font-semibold text-white shadow-sm transition-colors hover:bg-cyan-800 disabled:opacity-50"
    >
      {pending ? 'Connecting to your workspace…' : 'Sign in to your workspace'}
    </button>
  )
}

export default function Register() {
  const clientReady = useClientReady()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [signupResult, setSignupResult] = useState<SignupResult | null>(null)

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    const formData = new FormData(e.currentTarget)
    const orgName = formData.get('org_name') as string
    const email = formData.get('email') as string
    const password = formData.get('password') as string

    // Validate
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      setIsLoading(false)
      return
    }

    if (orgName.length < 3) {
      setError('Organization name must be at least 3 characters')
      setIsLoading(false)
      return
    }

    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

      // Call tenant signup endpoint (provisions Keycloak + K8s)
      const response = await fetch(`${apiUrl}/v1/tenants/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          org_name: orgName,
          admin_email: email,
          admin_password: password,
          plan: 'free',
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Signup failed')
      }

      // Store signup result and show success state
      setSignupResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setIsLoading(false)
    }
  }

  // Success state - show provisioning status and login button
  if (signupResult) {
    return (
      <AuthLayout
        title="Workspace Created!"
        subtitle={<>Your dedicated instance is being set up</>}
      >
        <div className="space-y-6">
          {/* Status Banner */}
          <div className="rounded-lg border border-cyan-500/20 bg-gradient-to-r from-cyan-950/40 to-gray-900 p-4">
            <div className="mb-3 flex items-center gap-3">
              <span className="h-3 w-3 animate-pulse rounded-full bg-green-500" />
              <span className="text-sm font-medium text-gray-200">
                Provisioning{' '}
                {signupResult.provisioning_status === 'completed'
                  ? 'Complete'
                  : 'In Progress'}
              </span>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Tenant ID:</span>
                <code className="font-mono text-xs text-cyan-300">
                  {signupResult.tenant_id.slice(0, 12)}...
                </code>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Realm:</span>
                <code className="font-mono text-xs text-cyan-300">
                  {signupResult.realm_name}
                </code>
              </div>
              {signupResult.instance_url && (
                <div className="flex justify-between">
                  <span className="text-gray-400">Instance:</span>
                  <code className="font-mono text-xs text-cyan-300">
                    {signupResult.instance_url.replace('https://', '')}
                  </code>
                </div>
              )}
            </div>
          </div>

          {/* Login Button */}
          <form action={startWorkspaceSignIn}>
            <input type="hidden" name="realm" value={signupResult.realm_name} />
            <WorkspaceSignInButton />
          </form>

          <p className="text-center text-xs text-gray-500">
            You will be redirected to authenticate with your new credentials.
          </p>
        </div>
      </AuthLayout>
    )
  }

  // Signup form
  return (
    <AuthLayout
      title="Create your workspace"
      subtitle={
        <>
          Already have an account?{' '}
          <Link href="/login" className="text-cyan-600">
            Sign in
          </Link>
        </>
      }
    >
      <form method="post" onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <TextField
            label="Organization name"
            name="org_name"
            type="text"
            placeholder="Acme Inc"
            autoComplete="organization"
            required
            minLength={3}
            maxLength={50}
          />
          <TextField
            label="Email address"
            name="email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            placeholder="Min 8 characters"
            autoComplete="new-password"
            required
            minLength={8}
          />
          <SelectField
            label="How did you hear about us?"
            name="referral_source"
          >
            <option value="">Select an option</option>
            <option value="search">Search engine</option>
            <option value="social">Social media</option>
            <option value="referral">Friend or colleague</option>
            <option value="podcast">Podcast</option>
            <option value="blog">Blog or article</option>
            <option value="other">Other</option>
          </SelectField>
        </div>

        <Button
          type="submit"
          color="cyan"
          className="mt-8 w-full"
          disabled={!clientReady || isLoading}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Creating workspace...
            </span>
          ) : (
            'Get started free'
          )}
        </Button>

        <div className="mt-6 space-y-2">
          <p className="text-center text-xs text-gray-500">
            Free tier includes 10 tasks/month. No credit card required.
          </p>
          <p className="text-center text-xs text-gray-400">
            Your workspace includes a dedicated Kubernetes instance with data
            isolation.
          </p>
        </div>
      </form>
    </AuthLayout>
  )
}
