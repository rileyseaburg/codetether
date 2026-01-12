'use client'

import { type Metadata } from 'next'
import Link from 'next/link'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/Button'
import { SelectField, TextField } from '@/components/Fields'

// export const metadata: Metadata = {
//   title: 'Sign Up',
// }

export default function Register() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    const formData = new FormData(e.currentTarget)
    const data = {
      email: formData.get('email') as string,
      password: formData.get('password') as string,
      first_name: formData.get('first_name') as string,
      last_name: formData.get('last_name') as string,
      referral_source: formData.get('referral_source') as string,
    }

    // Validate password length
    if (data.password.length < 8) {
      setError('Password must be at least 8 characters')
      setIsLoading(false)
      return
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://codetether.com'
      const response = await fetch(`${apiUrl}/v1/users/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Registration failed')
      }

      setSuccess(true)
      
      // Redirect to login after 2 seconds
      setTimeout(() => {
        router.push('/login')
      }, 2000)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setIsLoading(false)
    }
  }

  if (success) {
    return (
      <AuthLayout
        title="Account created!"
        subtitle={
          <>
            Redirecting you to{' '}
            <Link href="/login" className="text-cyan-600">
              sign in
            </Link>
            ...
          </>
        }
      >
        <div className="text-center py-8">
          <div className="text-green-600 text-lg font-medium mb-2">
            Welcome to CodeTether!
          </div>
          <p className="text-gray-600">
            Your account has been created. You can now sign in and start automating.
          </p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Start automating in minutes"
      subtitle={
        <>
          Already have an account?{' '}
          <Link href="/login" className="text-cyan-600">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            {error}
          </div>
        )}
        
        <div className="grid grid-cols-2 gap-6">
          <TextField
            label="First name"
            name="first_name"
            type="text"
            autoComplete="given-name"
            required
          />
          <TextField
            label="Last name"
            name="last_name"
            type="text"
            autoComplete="family-name"
            required
          />
          <TextField
            className="col-span-full"
            label="Email address"
            name="email"
            type="email"
            autoComplete="email"
            required
          />
          <TextField
            className="col-span-full"
            label="Password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
          />
          <SelectField
            className="col-span-full"
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
          disabled={isLoading}
        >
          {isLoading ? 'Creating account...' : 'Get started free'}
        </Button>

        <p className="mt-4 text-center text-sm text-gray-500">
          Free tier includes 10 automations/month. No credit card required.
        </p>
      </form>
    </AuthLayout>
  )
}
