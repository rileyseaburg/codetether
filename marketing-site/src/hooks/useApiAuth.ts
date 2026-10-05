'use client'

import { useMemo, useSyncExternalStore } from 'react'
import { getApiAuth, subscribeToAuthChanges } from '@/lib/auth-token'

type ApiSession = Parameters<typeof getApiAuth>[0]

/** Reactively resolve SSO or password credentials, including tenant changes. */
export function useApiAuth(session?: ApiSession) {
  const snapshot = useSyncExternalStore(
    subscribeToAuthChanges,
    // Strings provide a stable snapshot even though getApiAuth returns an object.
    () => JSON.stringify(getApiAuth(session)),
    () => '{}',
  )
  return useMemo(
    () => JSON.parse(snapshot) as ReturnType<typeof getApiAuth>,
    [snapshot],
  )
}