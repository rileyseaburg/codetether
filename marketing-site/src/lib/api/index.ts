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

// Re-export everything from generated SDK
export * from './generated'

export { client }
