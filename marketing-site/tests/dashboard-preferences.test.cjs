const React = require('react')
jest.mock('@/lib/api', () => ({ setApiAuthToken: jest.fn() }))

test('SDK credentials track password-token rotation and logout', () => {
  const { ApiAuthSync } = jest.requireActual('@/components/ApiAuthSync')
  const { setApiAuthToken } = require('@/lib/api')
  localStorage.setItem('a2a_token', 'initial-fixture')
  render(React.createElement(ApiAuthSync))
  expect(setApiAuthToken).toHaveBeenLastCalledWith('initial-fixture', undefined)
  act(() => {
    localStorage.setItem('a2a_token', 'rotated-fixture')
    window.dispatchEvent(new StorageEvent('storage', { key: 'a2a_token' }))
  })
  expect(setApiAuthToken).toHaveBeenLastCalledWith('rotated-fixture', undefined)
  act(() => {
    localStorage.removeItem('a2a_token')
    notifyDashboardAuthChange()
  })
  expect(setApiAuthToken).toHaveBeenLastCalledWith(undefined, undefined)
})

const DashboardError = require('@/app/(dashboard)/dashboard/error').default
const DashboardLoading = require('@/app/(dashboard)/dashboard/loading').default

test('dashboard error fallback offers recovery without exposing exception text', () => {
  const reset = jest.fn()
  render(
    React.createElement(DashboardError, {
      error: new Error('sensitive fixture detail'),
      reset,
    }),
  )
  expect(screen.getByRole('alert')).toHaveTextContent('This page couldn’t load')
  expect(screen.queryByText('sensitive fixture detail')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(reset).toHaveBeenCalledTimes(1)
  expect(
    screen.getByRole('link', { name: 'Back to workspaces' }),
  ).toHaveAttribute('href', '/dashboard')
})

test('dashboard loading skeleton has an accessible status', () => {
  render(React.createElement(DashboardLoading))
  expect(
    screen.getByRole('status', { name: 'Loading dashboard page' }),
  ).toBeInTheDocument()
})
const {
  act,
  renderHook,
  render,
  screen,
  cleanup,
  fireEvent,
} = require('@testing-library/react')
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
  signOut: jest.fn(),
}))
const push = jest.fn()
jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/tasks/details',
  useRouter: () => ({ push }),
}))
jest.mock('@/components/ApiAuthSync', () => ({ ApiAuthSync: () => null }))
const { useSession } = require('next-auth/react')
const {
  useDashboardAuth,
  notifyDashboardAuthChange,
} = require('@/hooks/useDashboardAuth')
const {
  useDashboardTheme,
  DASHBOARD_THEME_KEY,
} = require('@/hooks/useDashboardTheme')
const Layout = require('@/app/(dashboard)/layout').default

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(DASHBOARD_THEME_KEY, 'dark')
  const theme = renderHook(useDashboardTheme)
  act(() => {
    window.dispatchEvent(
      new StorageEvent('storage', { key: DASHBOARD_THEME_KEY }),
    )
  })
  theme.unmount()
  useSession.mockReturnValue({ data: null, status: 'unauthenticated' })
  push.mockClear()
  window.matchMedia = jest.fn(() => ({
    matches: false,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  }))
})
afterEach(() => {
  cleanup()
  jest.restoreAllMocks()
})

test('theme restores the saved preference and persists toggles', () => {
  localStorage.setItem(DASHBOARD_THEME_KEY, 'light')
  const { result, unmount } = renderHook(useDashboardTheme)
  expect(result.current.darkMode).toBe(false)
  expect(document.documentElement).not.toHaveClass('dark')
  act(() => result.current.toggleTheme())
  expect(localStorage.getItem(DASHBOARD_THEME_KEY)).toBe('dark')
  expect(document.documentElement).toHaveClass('dark')
  expect(document.documentElement.style.colorScheme).toBe('dark')
  unmount()
  expect(renderHook(useDashboardTheme).result.current.darkMode).toBe(true)
})

test('theme follows updates and removal in another tab', () => {
  const { result } = renderHook(useDashboardTheme)
  act(() => {
    localStorage.setItem(DASHBOARD_THEME_KEY, 'light')
    window.dispatchEvent(
      new StorageEvent('storage', { key: DASHBOARD_THEME_KEY }),
    )
  })
  expect(result.current.darkMode).toBe(false)
  act(() => {
    localStorage.removeItem(DASHBOARD_THEME_KEY)
    window.dispatchEvent(
      new StorageEvent('storage', { key: DASHBOARD_THEME_KEY }),
    )
  })
  expect(result.current.darkMode).toBe(true)
})

test.each([true, false])(
  'theme survives failed writes (reads blocked: %s)',
  (blockReads) => {
    const { result } = renderHook(useDashboardTheme)
    if (blockReads) {
      jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('Blocked')
      })
    }
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Blocked')
    })
    act(() => result.current.toggleTheme())
    expect(result.current.darkMode).toBe(false)
  },
)

test('password auth reacts to cross-tab logout', () => {
  localStorage.setItem('a2a_token', 'fixture')
  localStorage.setItem(
    'a2a_user',
    JSON.stringify({ name: 'Fixture', roles: ['viewer'] }),
  )
  const { result } = renderHook(useDashboardAuth)
  expect(result.current.isAuthenticated).toBe(true)
  act(() => {
    localStorage.removeItem('a2a_token')
    window.dispatchEvent(new StorageEvent('storage', { key: 'a2a_token' }))
  })
  expect(result.current.isAuthenticated).toBe(false)
})

test('same-tab auth changes are observable without reloading', () => {
  const { result } = renderHook(useDashboardAuth)
  act(() => {
    localStorage.setItem('a2a_token', 'fixture')
    localStorage.setItem('a2a_user', JSON.stringify({ name: 'Fixture' }))
    notifyDashboardAuthChange()
  })
  expect(result.current.user.name).toBe('Fixture')
})

test.each(['null', '[]', 'invalid'])(
  'malformed profile %s does not authenticate',
  (profile) => {
    localStorage.setItem('a2a_token', 'fixture')
    localStorage.setItem('a2a_user', profile)
    expect(renderHook(useDashboardAuth).result.current.isAuthenticated).toBe(
      false,
    )
  },
)

test('SSO remains usable with blocked local storage', () => {
  useSession.mockReturnValue({
    data: { user: { name: 'SSO User' } },
    status: 'authenticated',
  })
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('Blocked')
  })
  const { result } = renderHook(useDashboardAuth)
  expect(result.current.user.name).toBe('SSO User')
  expect(result.current.loading).toBe(false)
})

test('nested routes mark the current section and offer a skip link, not fake metrics', () => {
  useSession.mockReturnValue({
    data: { user: { name: 'SSO User' } },
    status: 'authenticated',
  })
  render(React.createElement(Layout, null, 'Content'))
  expect(screen.getByRole('link', { name: 'Tasks' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(
    screen.getByRole('link', { name: 'Skip to main content' }),
  ).toHaveAttribute('href', '#dashboard-main')
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1')
  expect(screen.queryByText('Connected')).not.toBeInTheDocument()
})
