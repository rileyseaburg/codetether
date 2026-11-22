const React = require('react')
const {
  act,
  render,
  screen,
  fireEvent,
  cleanup,
} = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
jest.mock('next/link', () => ({
  __esModule: true,
  default: React.forwardRef(function Link({ onClick, ...props }, ref) {
    return React.createElement('a', {
      ...props,
      ref,
      onClick: (event) => {
        event.preventDefault()
        onClick?.(event)
      },
    })
  }),
}))
const { DashboardNavigation } = require('@/components/DashboardNavigation')
const icon = (props) => React.createElement('svg', props)
const items = [
  ['Get Started', '/dashboard/getting-started'],
  ['Workspaces', '/dashboard'],
  ['Workers', '/dashboard/workers'],
  ['Swarm', '/dashboard/swarm'],
  ['Tasks', '/dashboard/tasks'],
  ['Sessions', '/dashboard/sessions'],
  ['Activity', '/dashboard/activity'],
  ['Billing', '/dashboard/billing'],
  ['Settings', '/dashboard/settings'],
  ['Admin', '/dashboard/admin'],
].map(([name, href]) => ({ name, href, icon, highlight: true }))
afterEach(cleanup)

test('only five primary destinations and three utilities are initially visible', () => {
  render(
    React.createElement(DashboardNavigation, {
      items,
      activeHref: '/dashboard/tasks',
    }),
  )
  expect(screen.getAllByRole('link').map((link) => link.textContent)).toEqual([
    'Workspaces',
    'Tasks',
    'Sessions',
    'Workers',
    'Activity',
    'Billing',
    'Settings',
    'Setup guide',
  ])
  expect(screen.getByRole('link', { name: 'Tasks' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(screen.queryByText('New')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'More tools' })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  for (const link of screen.getAllByRole('link'))
    expect(link.className).toContain('min-h-11')
})

test('More tools is keyboard-operable and preserves every supplied destination', async () => {
  const user = userEvent.setup()
  render(
    React.createElement(DashboardNavigation, {
      items,
      activeHref: '/dashboard',
    }),
  )
  const toggle = screen.getByRole('button', { name: 'More tools' })
  act(() => toggle.focus())
  await user.keyboard('{Enter}')
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(
    screen
      .getAllByRole('link')
      .map((link) => link.getAttribute('href'))
      .sort(),
  ).toEqual(items.map((item) => item.href).sort())
  await user.keyboard(' ')
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByRole('link', { name: 'Swarm' })).not.toBeInTheDocument()
})

test('advanced active routes expand initially and when route selection changes', () => {
  const view = render(
    React.createElement(DashboardNavigation, {
      items,
      activeHref: '/dashboard/swarm',
    }),
  )
  expect(screen.getByRole('link', { name: 'Swarm' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  fireEvent.click(screen.getByRole('button', { name: 'More tools' }))
  view.rerender(
    React.createElement(DashboardNavigation, {
      items,
      activeHref: '/dashboard/admin',
    }),
  )
  expect(screen.getByRole('button', { name: 'More tools' })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
  expect(screen.getByRole('link', { name: 'Admin' })).toHaveAttribute(
    'aria-current',
    'page',
  )
})

test('admin remains absent when parent permission filtering removes it', () => {
  render(
    React.createElement(DashboardNavigation, {
      items: items.filter((item) => item.name !== 'Admin'),
      activeHref: '/dashboard/swarm',
    }),
  )
  expect(screen.getByRole('link', { name: 'Swarm' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
})

test('navigation callbacks apply to primary, advanced and utility links', () => {
  const navigate = jest.fn()
  render(
    React.createElement(DashboardNavigation, {
      items,
      activeHref: '/dashboard/swarm',
      onNavigate: navigate,
    }),
  )
  for (const name of ['Tasks', 'Swarm', 'Billing', 'Settings', 'Setup guide']) {
    fireEvent.click(screen.getByRole('link', { name, exact: true }))
  }
  expect(navigate).toHaveBeenCalledTimes(5)
})
