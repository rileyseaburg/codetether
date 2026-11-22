// Mocked local protocol proof using Auth.js itself; no real Keycloak tenant is used.
import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import test from 'node:test'
import { Auth, customFetch, type AuthConfig } from '@auth/core'
import Keycloak from '@auth/core/providers/keycloak'
import { generateKeyPair, SignJWT } from 'jose'
import { tenantProviderForRealm } from './tenant-auth'

if (!globalThis.crypto) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto })
}

const site = 'https://app.example.test'
const keycloak = 'https://identity.example.test'
const realm = 'acme-123.codetether.run'
const provider = tenantProviderForRealm(realm, `${keycloak}/realms/codetether`)!

// The mock IdP verifies PKCE rather than simply returning a fixture token for any code.
async function harness() {
  const { privateKey } = await generateKeyPair('RS256')
  let challenge: string | null = null
  let tokenRequests = 0
  const errors: Error[] = []
  const fetchIdp: typeof fetch = async (input, init) => {
    const request = new Request(input, init)
    if (request.url === `${provider.issuer}/.well-known/openid-configuration`) {
      return Response.json({
        issuer: provider.issuer,
        authorization_endpoint: `${provider.issuer}/protocol/openid-connect/auth`,
        token_endpoint: `${provider.issuer}/protocol/openid-connect/token`,
        jwks_uri: `${provider.issuer}/protocol/openid-connect/certs`,
        userinfo_endpoint: `${provider.issuer}/protocol/openid-connect/userinfo`,
        response_types_supported: ['code'],
        subject_types_supported: ['public'],
        id_token_signing_alg_values_supported: ['RS256'],
        token_endpoint_auth_methods_supported: ['none'],
        code_challenge_methods_supported: ['S256'],
      })
    }
    assert.equal(request.url, `${provider.issuer}/protocol/openid-connect/token`)
    tokenRequests++
    const body = new URLSearchParams(await request.text())
    assert.equal(body.get('client_id'), provider.clientId)
    assert.equal(body.get('redirect_uri'), `${site}/api/auth/callback/keycloak`)
    assert.equal(body.get('grant_type'), 'authorization_code')
    assert.equal(body.get('code'), 'fixture-auth-code')
    assert.equal(request.headers.get('Authorization'), null, 'public tenant client must not send the shared secret')
    assert.ok(body.get('code_verifier'), 'token exchange needs the cookie-backed verifier')
    assert.equal(
      createHash('sha256').update(body.get('code_verifier')!).digest('base64url'),
      challenge,
      'the callback verifier must match the fresh authorization challenge',
    )
    const idToken = await new SignJWT({
      email: 'fixture@example.test', name: 'Fixture User', email_verified: true,
    })
      .setProtectedHeader({ alg: 'RS256' })
      .setIssuer(provider.issuer)
      .setAudience(provider.clientId)
      .setSubject('fixture-user')
      .setIssuedAt()
      .setExpirationTime('5m')
      .sign(privateKey)
    return Response.json({
      access_token: 'fixture-tenant-access-token', token_type: 'Bearer',
      refresh_token: 'fixture-tenant-refresh-token', expires_in: 300, id_token: idToken,
    })
  }

  const config: AuthConfig = {
    basePath: '/api/auth', trustHost: true,
    secret: 'mocked-local-auth-secret-at-least-thirty-two-characters',
    session: { strategy: 'jwt' },
    logger: { error: (error) => { errors.push(error) } },
    providers: [Keycloak({ ...provider, [customFetch]: fetchIdp })],
    callbacks: {
      jwt: async ({ token, account }) => ({ ...token, accessToken: account?.access_token ?? token.accessToken }),
      session: async ({ session, token }) => Object.assign(session, { accessToken: token.accessToken }),
    },
  }
  const jar = new Map<string, string>()
  function absorb(response: Response) {
    for (const cookie of response.headers.getSetCookie()) {
      const [pair] = cookie.split(';')
      const separator = pair.indexOf('=')
      const name = pair.slice(0, separator)
      const value = pair.slice(separator + 1)
      if (value) jar.set(name, value)
      else jar.delete(name)
    }
  }
  async function auth(path: string, init?: RequestInit) {
    const headers = new Headers(init?.headers)
    headers.set('cookie', [...jar].map(([name, value]) => `${name}=${value}`).join('; '))
    const response = await Auth(new Request(`${site}${path}`, { ...init, headers }), config)
    absorb(response)
    return response
  }
  async function begin() {
    // Start with an empty browser jar. Obtain the real Auth.js CSRF token first.
    const csrf = await auth('/api/auth/csrf')
    const { csrfToken } = await csrf.json()
    assert.ok(csrfToken)
    const result = await auth('/api/auth/signin/keycloak', {
      method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ csrfToken, callbackUrl: `${site}/dashboard` }),
    })
    assert.equal(result.status, 302)
    const authorization = new URL(result.headers.get('location')!)
    assert.equal(authorization.origin, keycloak)
    assert.equal(authorization.pathname, `/realms/${realm}/protocol/openid-connect/auth`)
    assert.equal(authorization.searchParams.get('client_id'), 'acme-123-spa')
    assert.equal(authorization.searchParams.get('redirect_uri'), `${site}/api/auth/callback/keycloak`)
    assert.equal(authorization.searchParams.get('response_type'), 'code')
    assert.equal(authorization.searchParams.get('code_challenge_method'), 'S256')
    challenge = authorization.searchParams.get('code_challenge')
    assert.ok(challenge)
    const state = authorization.searchParams.get('state')
    assert.ok(state)
    assert.ok(jar.has('__Secure-authjs.pkce.code_verifier'))
    assert.ok(jar.has('__Secure-authjs.state'))
    return state
  }
  return { jar, begin, auth, errors, tokenRequests: () => tokenRequests }
}

function callbackPath(state: string) {
  return `/api/auth/callback/keycloak?${new URLSearchParams({ code: 'fixture-auth-code', state })}`
}

test('fresh tenant signup has PKCE/state and produces a session through a real Auth.js callback', async () => {
  const run = await harness()
  const state = await run.begin()
  const callback = await run.auth(callbackPath(state))
  // Report captured Auth.js names/causes before a less informative redirect assertion.
  assert.deepEqual(run.errors, [], 'Auth.js fresh callback must not report an internal error')
  assert.equal(callback.status, 302)
  assert.equal(callback.headers.get('location'), `${site}/dashboard`)
  assert.equal(run.tokenRequests(), 1)
  assert.ok(run.jar.has('__Secure-authjs.session-token'))
  assert.ok(!run.jar.has('__Secure-authjs.pkce.code_verifier'))
  assert.ok(!run.jar.has('__Secure-authjs.state'))
  const session = await run.auth('/api/auth/session')
  assert.equal(session.status, 200)
  const data = await session.json()
  assert.equal(data.user.email, 'fixture@example.test')
  assert.equal(data.accessToken, 'fixture-tenant-access-token')
})

test('a direct provider callback without initiating Auth.js cannot create a session', async () => {
  const run = await harness()
  const response = await run.auth(callbackPath('uninitialized-state'))
  assert.match(response.headers.get('location')!, /error=Configuration/)
  assert.equal(run.tokenRequests(), 0)
  assert.ok(!run.jar.has('__Secure-authjs.session-token'))
  assert.equal(run.errors.length, 1)
  assert.equal(run.errors[0]?.name, 'InvalidCheck')
  assert.match(String(run.errors[0]?.cause), /state cookie was missing/)
})

test('a tenant callback with a missing PKCE cookie cannot exchange a code', async () => {
  const run = await harness()
  const state = await run.begin()
  run.jar.delete('__Secure-authjs.pkce.code_verifier')
  const response = await run.auth(callbackPath(state))
  assert.match(response.headers.get('location')!, /error=Configuration/)
  assert.equal(run.tokenRequests(), 0)
  assert.ok(!run.jar.has('__Secure-authjs.session-token'))
  assert.equal(run.errors.length, 1)
  assert.equal(run.errors[0]?.name, 'InvalidCheck')
  assert.match(String(run.errors[0]?.cause), /pkceCodeVerifier cookie was missing/)
})

test('mismatched OAuth state fails before exchanging the tenant code', async () => {
  const run = await harness()
  await run.begin()
  const response = await run.auth(callbackPath('wrong-state'))
  assert.match(response.headers.get('location')!, /error=Configuration/)
  assert.equal(run.tokenRequests(), 0)
  assert.ok(!run.jar.has('__Secure-authjs.session-token'))
  assert.equal(run.errors.length, 1)
  assert.equal(run.errors[0]?.name, 'CallbackRouteError')
  const cause = run.errors[0]?.cause as { err?: Error } | undefined
  assert.match(cause?.err?.message ?? '', /unexpected "state" response parameter value/)
})
