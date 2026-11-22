#!/usr/bin/env node
/**
 * Generates a type-safe API client from the OpenAPI spec
 * Uses @orpc/openapi-client for runtime SDK generation
 */

import { writeFileSync, mkdirSync } from 'fs'
import { dirname } from 'path'

const API_URLS = {
  production: 'https://api.codetether.run',
  development: 'http://localhost:8000',
}

const OPENAPI_URL = `${API_URLS.production}/openapi.json`
const OUTPUT_PATH = 'src/lib/api/generated-client.ts'

async function fetchOpenAPISpec() {
  console.log(`Fetching OpenAPI spec from ${OPENAPI_URL}...`)
  const res = await fetch(OPENAPI_URL)
  if (!res.ok) throw new Error(`Failed to fetch OpenAPI spec: ${res.status}`)
  return res.json()
}

function generateClient(spec) {
  const paths = spec.paths || {}
  const operations = []

  for (const [path, methods] of Object.entries(paths)) {
    for (const [method, op] of Object.entries(methods)) {
      if (['get', 'post', 'put', 'patch', 'delete'].includes(method)) {
        operations.push({ path, method: method.toUpperCase(), ...op })
      }
    }
  }

  // Group by tags
  const byTag = {}
  for (const op of operations) {
    const tag = op.tags?.[0] || 'default'
    if (!byTag[tag]) byTag[tag] = []
    byTag[tag].push(op)
  }

  return { spec, operations, byTag }
}

function generateTypeScript({ spec, byTag }) {
  const lines = [
    `/**`,
    ` * Auto-generated API client from OpenAPI spec`,
    ` * Generated: ${new Date().toISOString()}`,
    ` * DO NOT EDIT MANUALLY`,
    ` */`,
    ``,
    `import { createORPCClient } from '@orpc/client'`,
    `import { createOpenAPIClient } from '@orpc/openapi-client'`,
    ``,
    `// Environment-aware base URL`,
    `const getBaseUrl = () => {`,
    `  if (typeof window !== 'undefined') {`,
    `    return process.env.NEXT_PUBLIC_API_URL || '${API_URLS.production}'`,
    `  }`,
    `  return process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || '${API_URLS.production}'`,
    `}`,
    ``,
    `// OpenAPI spec (embedded for type inference)`,
    `const openAPISpec = ${JSON.stringify(spec, null, 2)} as const`,
    ``,
    `// Create the type-safe client`,
    `export const api = createOpenAPIClient({`,
    `  baseURL: getBaseUrl(),`,
    `  spec: openAPISpec,`,
    `})`,
    ``,
    `// Re-export for convenience`,
    `export type Api = typeof api`,
    `export { getBaseUrl }`,
  ]

  return lines.join('\n')
}

async function main() {
  try {
    const spec = await fetchOpenAPISpec()
    console.log(`Found ${Object.keys(spec.paths || {}).length} paths`)

    const data = generateClient(spec)
    const code = generateTypeScript(data)

    mkdirSync(dirname(OUTPUT_PATH), { recursive: true })
    writeFileSync(OUTPUT_PATH, code)
    console.log(`Generated ${OUTPUT_PATH}`)
  } catch (err) {
    console.error('Failed to generate API client:', err.message)
    process.exit(1)
  }
}

main()
