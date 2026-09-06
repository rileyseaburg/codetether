import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getApiAuth } from './auth-token'
import { secureApiUrl } from './api-origin'

test('same-origin loopback proxy stays HTTP; remote APIs still require HTTPS', () => {
  assert.equal(
    secureApiUrl('http://localhost:3001/api/tenant', 'http://localhost:3001'),
    'http://localhost:3001/api/tenant',
  )
  assert.equal(
    secureApiUrl('http://127.0.0.1:3001/api', 'http://127.0.0.1:3001'),
    'http://127.0.0.1:3001/api',
  )
  assert.equal(
    secureApiUrl('http://[::1]:3001/api', 'http://[::1]:3001'),
    'http://[::1]:3001/api',
  )
  assert.equal(
    secureApiUrl('http://localhost:3002/api', 'http://localhost:3001'),
    'https://localhost:3002/api',
  )
  assert.equal(
    secureApiUrl('http://localhost.attacker.test/api', 'http://localhost:3001'),
    'https://localhost.attacker.test/api',
  )
  assert.equal(
    secureApiUrl('http://api.codetether.run', 'http://localhost:3001'),
    'https://api.codetether.run',
  )
  assert.equal(
    secureApiUrl('https://api.codetether.run'),
    'https://api.codetether.run',
  )
})

import {
  localAuthRedirect,
  resolveAuthRedirect,
  tenantProviderForRealm,
} from './tenant-auth'

test('callback redirects match trusted origins, not substrings', () => {
  const base = 'https://codetether.run'
  for (const url of [
    'https://codetether.run.attacker.test/',
    'https://attacker.test/?next=.codetether.run',
    'https://user:pass@team.codetether.run/',
  ]) {
    assert.equal(resolveAuthRedirect(url, base), `${base}/dashboard`)
  }
  assert.equal(
    resolveAuthRedirect('/dashboard/tasks', base),
    `${base}/dashboard/tasks`,
  )
  assert.equal(
    resolveAuthRedirect('https://team.codetether.run/dashboard', base),
    'https://team.codetether.run/dashboard',
  )
  assert.equal(localAuthRedirect('/\n/attacker.test'), '/dashboard')
  assert.equal(localAuthRedirect('/\t/attacker.test'), '/dashboard')
})

afterEach(() => {
  Reflect.deleteProperty(globalThis, 'window')
  Reflect.deleteProperty(globalThis, 'localStorage')
})

test('tenant sign-in uses the trusted issuer and provisioned public client', () => {
  const provider = tenantProviderForRealm(
    'acme-123.codetether.run',
    'https://auth.example.test/auth/realms/shared',
  )!
  assert.equal(
    provider.issuer,
    'https://auth.example.test/auth/realms/acme-123.codetether.run',
  )
  assert.equal(provider.clientId, 'acme-123-spa')
  assert.deepEqual(provider.checks, ['pkce', 'state'])
  assert.equal(provider.client.token_endpoint_auth_method, 'none')
  assert.equal('clientSecret' in provider, false)
})

test('untrusted realm URLs and invalid realm names are rejected', () => {
  for (const realm of [
    'https://attacker.test',
    '../admin',
    'evil.codetether.run.attacker.test',
    'a/b.codetether.run',
  ]) {
    assert.throws(() =>
      tenantProviderForRealm(realm, 'https://auth.example.test/realms/shared'),
    )
  }
  assert.equal(
    tenantProviderForRealm(
      undefined,
      'https://auth.example.test/realms/shared',
    ),
    undefined,
  )
})

test('login redirects cannot leave the app', () => {
  for (const value of [
    'https://attacker.test',
    '//attacker.test',
    '/\\attacker.test',
    'javascript:alert(1)',
  ]) {
    assert.equal(localAuthRedirect(value), '/dashboard')
  }
  assert.equal(
    localAuthRedirect('/dashboard/billing?upgraded=true'),
    '/dashboard/billing?upgraded=true',
  )
})

function storage(values: Record<string, string>) {
  Object.defineProperty(globalThis, 'window', { value: {}, configurable: true })
  Object.defineProperty(globalThis, 'localStorage', {
    value: { getItem: (key: string) => values[key] || null },
    configurable: true,
  })
}

test('checkout uses password-login credentials and tenant metadata', () => {
  storage({
    a2a_token: 'password-fixture',
    a2a_user: JSON.stringify({ tenant_id: 'tenant-fixture' }),
  })
  assert.deepEqual(getApiAuth(null), {
    token: 'password-fixture',
    tenantId: 'tenant-fixture',
  })
})

test('SSO credentials take priority over stored credentials', () => {
  storage({ a2a_token: 'stale-fixture' })
  assert.deepEqual(
    getApiAuth({ accessToken: 'sso-fixture', tenantId: 'sso-tenant' }),
    {
      token: 'sso-fixture',
      tenantId: 'sso-tenant',
    },
  )
})

test('malformed profile data does not discard a token', () => {
  storage({ access_token: 'legacy-fixture', a2a_user: '{invalid' })
  assert.equal(getApiAuth().token, 'legacy-fixture')
})

test('SSR and blocked browser storage remain safe', () => {
  assert.deepEqual(getApiAuth(), {})
  Object.defineProperty(globalThis, 'window', { value: {}, configurable: true })
  Object.defineProperty(globalThis, 'localStorage', {
    get() {
      throw new Error('Storage blocked')
    },
    configurable: true,
  })
  assert.deepEqual(getApiAuth(), {})
})
