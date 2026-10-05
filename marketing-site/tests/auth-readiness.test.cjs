const React = require('react')
const { renderToString } = require('react-dom/server')
const { render, screen, cleanup } = require('@testing-library/react')
jest.mock('@/app/(auth)/actions', () => ({ startWorkspaceSignIn: jest.fn() }))
jest.mock('next-auth/react', () => ({
  useSession: () => ({ status: 'unauthenticated', data: null }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/components/AuthLayout', () => ({
  AuthLayout: ({ children }) => React.createElement('main', null, children),
}))
const Register = require('@/app/(auth)/register/page').default
const Login = require('@/app/(auth)/login/login-form').default
const { useClientReady } = require('@/hooks/useClientReady')
afterEach(cleanup)

test('hydration readiness is false for server-rendered client-only actions', () => {
  function Readiness() {
    return React.createElement(
      'button',
      { disabled: !useClientReady() },
      'Submit',
    )
  }
  expect(renderToString(React.createElement(Readiness))).toContain(
    'disabled=""',
  )
  render(React.createElement(Readiness))
  expect(screen.getByRole('button', { name: 'Submit' })).toBeEnabled()
})

test('signup cannot submit credentials through a native GET before hydration', () => {
  const markup = renderToString(React.createElement(Register))
  expect(markup).toContain('method="post"')
  expect(markup).toMatch(/<button[^>]*disabled=""/)
})

test('hydrated signup enables the submit handler', () => {
  render(React.createElement(Register))
  expect(screen.getByRole('button', { name: 'Get started free' })).toBeEnabled()
  expect(
    screen.getByRole('button', { name: 'Get started free' }).closest('form'),
  ).toHaveAttribute('method', 'post')
})

test('password login uses POST as a safe native fallback', () => {
  render(React.createElement(Login))
  expect(
    screen.getByRole('button', { name: 'Sign in to account' }).closest('form'),
  ).toHaveAttribute('method', 'post')
})
