// Mocked local UI/server-action proof; no identity provider or Stripe is contacted.
const React = require('react')
const { render, screen, fireEvent, waitFor, cleanup, act } = require('@testing-library/react')
const { renderToString } = require('react-dom/server')

jest.mock('next-auth', () => ({ AuthError: class AuthError extends Error {} }))
jest.mock('next-auth/react', () => ({ useSession: jest.fn() }))
jest.mock('next/headers', () => ({ cookies: jest.fn() }))
jest.mock('next/navigation', () => ({
  redirect: jest.fn((url) => { throw new Error(`NEXT_REDIRECT:${url}`) }),
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/auth', () => ({ signIn: jest.fn() }))
jest.mock('@/components/AuthLayout', () => ({
  AuthLayout: ({ children }) => React.createElement('main', null, children),
}))

const { startWorkspaceSignIn } = require('@/app/(auth)/actions')
const Register = require('@/app/(auth)/register/page').default
const { Pricing } = require('@/components/Pricing')
const { useSession } = require('next-auth/react')
const { AuthError } = require('next-auth')
const { cookies } = require('next/headers')
const { signIn } = require('@/auth')
const { TENANT_AUTH_COOKIE } = require('@/lib/tenant-auth')
const { notifyApiAuthChange } = require('@/lib/auth-token')
const store = { set: jest.fn(), delete: jest.fn() }

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  window.location.hash = ''
  cookies.mockResolvedValue(store)
  signIn.mockReset().mockResolvedValue(undefined)
  useSession.mockReturnValue({ data: null, status: 'unauthenticated' })
  global.fetch = jest.fn()
  jest.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => { cleanup(); jest.restoreAllMocks() })

function signInData(realm, callbackUrl = '/dashboard') {
  const data = new FormData()
  data.set('realm', realm)
  data.set('callbackUrl', callbackUrl)
  return data
}
function proButton() {
  return screen.getByRole('button', { name: /on the Pro plan/ })
}
function unavailableCheckout() {
  fetch.mockResolvedValue({
    ok: false, status: 503,
    json: async () => ({ detail: 'Billing temporarily unavailable' }),
  })
}
function submitSignup(container) {
  fireEvent.change(container.querySelector('[name="org_name"]'), { target: { value: 'Acme' } })
  fireEvent.change(container.querySelector('[name="email"]'), { target: { value: 'fixture@example.test' } })
  fireEvent.change(container.querySelector('[name="password"]'), { target: { value: 'fixture-only-password' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Get started free' }).closest('form'))
}

test('workspace action selects the tenant before Auth.js initializes sign-in', async () => {
  signIn.mockImplementation(async (provider, options) => {
    expect(store.set).toHaveBeenCalledWith(TENANT_AUTH_COOKIE, 'acme-123.codetether.run', {
      httpOnly: true, secure: false, sameSite: 'lax', path: '/', maxAge: 900,
    })
    expect(provider).toBe('keycloak')
    expect(options).toEqual({ redirectTo: '/dashboard/billing' })
  })
  await startWorkspaceSignIn(signInData('acme-123.codetether.run', '/dashboard/billing'))
  expect(signIn).toHaveBeenCalledTimes(1)
})

test('shared-realm login clears the prior selector and rejects an external callback', async () => {
  await startWorkspaceSignIn(signInData('', '//attacker.example'))
  expect(store.delete).toHaveBeenCalledWith(TENANT_AUTH_COOKIE)
  expect(signIn).toHaveBeenCalledWith('keycloak', { redirectTo: '/dashboard' })
})

test.each(['https://attacker.example', '../admin', 'acme.codetether.run.attacker.example'])(
  'invalid workspace selector %s cannot set cookies or start OAuth', async (realm) => {
    await expect(startWorkspaceSignIn(signInData(realm))).rejects.toThrow('Invalid workspace realm')
    expect(cookies).not.toHaveBeenCalled()
    expect(signIn).not.toHaveBeenCalled()
  },
)

test('OAuth initialization errors return to login with the tenant available for retry', async () => {
  signIn.mockRejectedValue(new AuthError())
  await expect(startWorkspaceSignIn(signInData('acme.codetether.run')))
    .rejects.toThrow('NEXT_REDIRECT:/login?error=OAuthSignin&realm=acme.codetether.run')
})

test('Auth.js redirect exceptions are not swallowed as sign-in failures', async () => {
  signIn.mockRejectedValue(new Error('NEXT_REDIRECT:provider'))
  await expect(startWorkspaceSignIn(signInData('acme.codetether.run')))
    .rejects.toThrow('NEXT_REDIRECT:provider')
})

test('signup success sends the workspace to the server action, never the response login URL', async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({
    tenant_id: 'tenant-fixture', realm_name: 'acme.codetether.run',
    spa_client_id: 'acme-spa', login_url: 'https://attacker.example/authorize',
  }) })
  const { container } = render(React.createElement(Register))
  submitSignup(container)
  const button = await screen.findByRole('button', { name: 'Sign in to your workspace' })
  expect(button.closest('form').querySelector('[name="realm"]')).toHaveValue('acme.codetether.run')
  expect(container.querySelector('a[href*="attacker.example"]')).toBeNull()
  fireEvent.click(button)
  await waitFor(() => expect(signIn).toHaveBeenCalledWith('keycloak', { redirectTo: '/dashboard' }))
  expect(store.set).toHaveBeenCalledWith(TENANT_AUTH_COOKIE, 'acme.codetether.run', expect.any(Object))
})

test('signup failure displays provider feedback without offering a workspace login', async () => {
  fetch.mockResolvedValue({ ok: false, json: async () => ({ detail: 'Workspace provisioning unavailable' }) })
  const { container } = render(React.createElement(Register))
  submitSignup(container)
  expect(await screen.findByText('Workspace provisioning unavailable')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Sign in to your workspace' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Get started free' })).toBeEnabled()
})

test.each([
  ['Auth.js', { accessToken: 'sso-fixture' }, 'authenticated', { a2a_token: 'stale-fixture' }, 'sso-fixture'],
  ['password', null, 'unauthenticated', { a2a_token: 'password-fixture' }, 'password-fixture'],
  ['legacy password', null, 'unauthenticated', { access_token: 'legacy-fixture' }, 'legacy-fixture'],
])('%s checkout sends the correct bearer credentials and billing URLs', async (_, session, status, values, token) => {
  useSession.mockReturnValue({ data: session, status })
  for (const [key, value] of Object.entries(values)) localStorage.setItem(key, value)
  unavailableCheckout()
  render(React.createElement(Pricing))
  fireEvent.click(proButton())
  await screen.findByRole('alert')
  expect(fetch).toHaveBeenCalledTimes(1)
  const [url, options] = fetch.mock.calls[0]
  expect(url).toMatch(/\/v1\/users\/billing\/checkout$/)
  expect(options.method).toBe('POST')
  expect(options.headers.Authorization).toBe(`Bearer ${token}`)
  expect(JSON.parse(options.body)).toEqual({
    tier: 'pro', success_url: `${window.location.origin}/dashboard/billing?upgraded=true`,
    cancel_url: `${window.location.origin}/#pricing`,
  })
  expect(screen.getByRole('alert')).toHaveTextContent('Billing temporarily unavailable')
  expect(proButton()).toBeEnabled()
})

test.each(['a2a_token', 'access_token'])(
  'a usable %s can checkout while Auth.js is still loading', async (key) => {
    useSession.mockReturnValue({ data: null, status: 'loading' })
    localStorage.setItem(key, 'password-fixture')
    unavailableCheckout()
    render(React.createElement(Pricing))
    expect(proButton()).toBeEnabled()
    fireEvent.click(proButton())
    await screen.findByRole('alert')
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer password-fixture')
  },
)

test('loading without any token waits instead of starting checkout or registration', () => {
  useSession.mockReturnValue({ data: null, status: 'loading' })
  render(React.createElement(Pricing))
  expect(proButton()).toBeDisabled()
  fireEvent.click(proButton())
  expect(fetch).not.toHaveBeenCalled()
})

test('server-rendered pricing waits for client password-token readiness', () => {
  useSession.mockReturnValue({ data: null, status: 'loading' })
  localStorage.setItem('a2a_token', 'password-fixture')
  const markup = renderToString(React.createElement(Pricing))
  expect(markup).toMatch(/<button[^>]*aria-label="Upgrade to Pro on the Pro plan"[^>]*disabled=""/)
})

test('same-tab auth notification enables checkout after password sign-in', () => {
  useSession.mockReturnValue({ data: null, status: 'loading' })
  render(React.createElement(Pricing))
  expect(proButton()).toBeDisabled()
  act(() => {
    localStorage.setItem('a2a_token', 'new-password-fixture')
    notifyApiAuthChange()
  })
  expect(proButton()).toBeEnabled()
})

test.each(['a2a_token', 'access_token'])(
  'cross-tab removal of %s updates checkout readiness', (key) => {
    useSession.mockReturnValue({ data: null, status: 'loading' })
    localStorage.setItem(key, 'password-fixture')
    render(React.createElement(Pricing))
    expect(proButton()).toBeEnabled()
    act(() => {
      localStorage.removeItem(key)
      window.dispatchEvent(new StorageEvent('storage', { key, oldValue: 'password-fixture', newValue: null }))
    })
    expect(proButton()).toBeDisabled()
  },
)

test('checkout reads the latest token at click, not the value captured during render', async () => {
  localStorage.setItem('a2a_token', 'old-password-fixture')
  unavailableCheckout()
  render(React.createElement(Pricing))
  localStorage.setItem('a2a_token', 'rotated-password-fixture')
  fireEvent.click(proButton())
  await screen.findByRole('alert')
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer rotated-password-fixture')
})

test('in-flight checkout disables all paid plans and cannot duplicate a request', () => {
  localStorage.setItem('a2a_token', 'password-fixture')
  fetch.mockReturnValue(new Promise(() => {}))
  render(React.createElement(Pricing))
  fireEvent.click(proButton())
  expect(proButton()).toBeDisabled()
  expect(screen.getByRole('button', { name: /on the Enterprise plan/ })).toBeDisabled()
  fireEvent.click(proButton())
  expect(fetch).toHaveBeenCalledTimes(1)
})

test('successful checkout navigates to the returned URL (same-document fixture)', async () => {
  localStorage.setItem('a2a_token', 'password-fixture')
  fetch.mockResolvedValue({ ok: true, json: async () => ({ checkout_url: `${window.location.origin}/#checkout-fixture` }) })
  render(React.createElement(Pricing))
  fireEvent.click(proButton())
  await waitFor(() => expect(window.location.hash).toBe('#checkout-fixture'))
})

test('a successful response without a checkout URL gives retryable feedback', async () => {
  localStorage.setItem('a2a_token', 'password-fixture')
  fetch.mockResolvedValue({ ok: true, json: async () => ({}) })
  render(React.createElement(Pricing))
  fireEvent.click(proButton())
  expect(await screen.findByRole('alert')).toHaveTextContent('No checkout URL returned')
  expect(proButton()).toBeEnabled()
})
