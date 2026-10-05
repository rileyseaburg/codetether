import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  client: '@hey-api/client-fetch',
  input: process.env.OPENAPI_URL || 'https://api.codetether.run/openapi.json',
  output: {
    path: 'src/lib/api/generated',
    format: 'prettier',
    lint: 'eslint',
  },
  plugins: [
    '@hey-api/typescript',
    '@hey-api/sdk',
  ],
})
