'use client'

import { useMemo, useSyncExternalStore } from 'react'
import { useSession } from 'next-auth/react'
import { subscribeToAuthChanges } from '@/lib/auth-token'
export { notifyApiAuthChange as notifyDashboardAuthChange } from '@/lib/auth-token'

interface PasswordUser {
  name?: string | null
  email?: string | null
  first_name?: string
  image?: string | null
  role?: string
  roles?: string[]
}

function readProfile(): string | null {
  try {
    const token =
      localStorage.getItem('a2a_token') || localStorage.getItem('access_token')
    return token ? localStorage.getItem('a2a_user') : null
  } catch {
    return null
  }
}

export function useDashboardAuth() {
  const { data: session, status } = useSession()
  const profile = useSyncExternalStore(
    subscribeToAuthChanges,
    readProfile,
    () => undefined,
  )
  const customUser = useMemo((): PasswordUser | null => {
    if (!profile) return null
    try {
      const parsed = JSON.parse(profile)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
        return null
      const user: PasswordUser = {}
      for (const key of [
        'name',
        'email',
        'first_name',
        'image',
        'role',
      ] as const) {
        if (typeof parsed[key] === 'string') user[key] = parsed[key]
      }
      if (Array.isArray(parsed.roles))
        user.roles = parsed.roles.filter(
          (role: unknown) => typeof role === 'string',
        )
      return user
    } catch {
      return null
    }
  }, [profile])
  const user: PasswordUser | null = session?.user || customUser
  return {
    user,
    session,
    isAuthenticated: !!user,
    loading: status === 'loading' || profile === undefined,
  }
}
