const React = require('react')
const {
  render,
  screen,
  cleanup,
  waitFor,
  within,
} = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
jest.mock('next/link', () => ({
  __esModule: true,
  default: React.forwardRef(function MockLink(props, ref) {
    return React.createElement('a', {
      ...props,
      ref,
      onClick: (event) => {
        props.onClick?.(event)
        event.preventDefault()
      },
    })
  }),
}))
const { Header } = require('@/components/Header')
jest.mock('next/navigation', () => ({ usePathname: jest.fn() }))
jest.mock('@/lib/api', () => ({
  createGlobalTaskV1AgentTasksPost: jest.fn(),
  getTaskV1AgentTasksTaskIdGet: jest.fn(),
}))
const { usePathname } = require('next/navigation')
const { ChatWidget } = require('@/components/ChatWidget')

afterEach(cleanup)

test('marketing desktop navigation uses homepage-qualified anchors and named links', () => {
  render(React.createElement(Header))
  const navigation = screen.getByRole('navigation', { name: 'Main navigation' })
  expect(
    within(navigation).getByRole('link', { name: 'Platform' }),
  ).toHaveAttribute('href', '/#features')
  expect(
    within(navigation).getByRole('link', { name: 'Use cases' }),
  ).toHaveAttribute('href', '/#use-cases')
  expect(
    screen.getByRole('link', { name: 'CodeTether on GitHub' }),
  ).toHaveAttribute('href', 'https://github.com/rileyseaburg/codetether')
  const docs = within(navigation).getByRole('link', { name: 'Docs' })
  expect(docs).toHaveAttribute('rel', 'noopener noreferrer')
})

test('marketing mobile navigation has an associated trigger and Escape restores focus', async () => {
  const user = userEvent.setup()
  render(React.createElement(Header))
  const trigger = screen.getByRole('button', { name: 'Open menu' })
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await user.click(trigger)
  const navigation = screen.getByRole('navigation', {
    name: 'Mobile navigation',
  })
  expect(trigger).toHaveAccessibleName('Close menu')
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(trigger).toHaveAttribute('aria-controls', navigation.id)
  expect(
    within(navigation).getByRole('link', { name: 'Platform' }),
  ).toHaveAttribute('href', '/#features')
  expect(
    within(navigation).getByRole('link', { name: 'Use cases' }),
  ).toHaveAttribute('href', '/#use-cases')
  within(navigation).getByRole('link', { name: 'Platform' }).focus()
  await user.keyboard('{Escape}')
  await waitFor(() =>
    expect(
      screen.queryByRole('navigation', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument(),
  )
  expect(trigger).toHaveFocus()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
})

test('marketing mobile navigation closes after activating a homepage anchor', async () => {
  const user = userEvent.setup()
  render(React.createElement(Header))
  const trigger = screen.getByRole('button', { name: 'Open menu' })
  await user.click(trigger)
  await user.click(
    within(
      screen.getByRole('navigation', { name: 'Mobile navigation' }),
    ).getByRole('link', { name: 'Platform' }),
  )
  await waitFor(() =>
    expect(
      screen.queryByRole('navigation', { name: 'Mobile navigation' }),
    ).not.toBeInTheDocument(),
  )
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
})
test.each(['/dashboard', '/dashboard/tasks', '/dashboard/sessions'])(
  'marketing chat does not cover %s controls',
  (pathname) => {
    usePathname.mockReturnValue(pathname)
    render(React.createElement(ChatWidget))
    expect(
      screen.queryByRole('button', { name: 'Open chat' }),
    ).not.toBeInTheDocument()
  },
)

test('marketing pages retain the chat entry point', () => {
  usePathname.mockReturnValue('/')
  render(React.createElement(ChatWidget))
  expect(screen.getByRole('button', { name: 'Open chat' })).toBeVisible()
})
