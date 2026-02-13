/**
 * Environment-aware API client
 * Auto-generated SDK from OpenAPI spec via @hey-api/openapi-ts
 */

import { client } from './generated/client.gen'

// Environment-aware base URL configuration
const getBaseUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL
  if (envUrl) return envUrl

  // Default based on environment
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000'
  }
  return 'https://api.codetether.run'
}

// Configure the client with environment-aware base URL
client.setConfig({ baseUrl: getBaseUrl() })

// Module-level auth state — read by the interceptor registered below
let _authToken: string | undefined
let _tenantId: string | undefined

// Register a SINGLE interceptor at module load time.
// It always runs, injecting whatever token is currently set.
client.interceptors.request.use((request) => {
  if (_authToken) {
    request.headers.set('Authorization', `Bearer ${_authToken}`)
  }
  if (_tenantId) {
    request.headers.set('X-Tenant-ID', _tenantId)
  }
  return request
})

/**
 * Set the auth token for all SDK API calls.
 * Updates the module-level token that the always-registered interceptor reads.
 * Call with no arguments to clear auth.
 */
export function setApiAuthToken(token?: string, tenantId?: string) {
  _authToken = token
  _tenantId = tenantId
}

/** Returns true when the SDK client has an auth token configured. */
export function hasApiAuthToken(): boolean {
  return !!_authToken
}

// Re-export everything from generated SDK
export * from './generated'

export { client }
