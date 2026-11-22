const React = require('react')
const {
  render,
  screen,
  cleanup,
  waitFor,
  fireEvent,
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
const { NavLinks } = require('@/components/NavLinks')
const { ChatInput } = require('@/components/ui/ChatInput')

test('footer navigation targets homepage sections from secondary routes', () => {
  render(React.createElement(NavLinks))
  for (const [name, section] of [['Features', 'features'], ['Use Cases', 'use-cases'], ['Roadmap', 'roadmap'], ['Pricing', 'pricing']]) {
    expect(screen.getByRole('link', { name })).toHaveAttribute('href', `/#${section}`)
  }
  expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute('rel', 'noopener noreferrer')
})

function renderComposer(props = {}) {
  const onSubmit = jest.fn()
  const onKeyDown = jest.fn((event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSubmit() }
  })
  render(React.createElement(ChatInput, { value: 'unfinished draft', onChange: jest.fn(), onSubmit, onKeyDown, ...props }))
  const textarea = screen.getByRole('textbox')
  return { textarea, form: textarea.closest('form'), onSubmit, onKeyDown }
}

afterEach(cleanup)

test('PRD composer retains drafts during composition and resumes Enter afterward', () => {
  const { textarea, form, onSubmit } = renderComposer()
  fireEvent.compositionStart(textarea)
  fireEvent.keyDown(textarea, { key: 'Enter' })
  fireEvent.submit(form)
  expect(onSubmit).not.toHaveBeenCalled()
  expect(textarea).toHaveValue('unfinished draft')
  fireEvent.compositionEnd(textarea)
  fireEvent.keyDown(textarea, { key: 'Enter' })
  expect(onSubmit).toHaveBeenCalledTimes(1)
})

test.each([{ isComposing: true }, { keyCode: 229 }])('PRD composer guards native composition flags %j', (flags) => {
  const { textarea, onKeyDown } = renderComposer()
  fireEvent.keyDown(textarea, { key: 'Enter', ...flags })
  expect(onKeyDown).not.toHaveBeenCalled()
})

test('PRD composer leaves Shift+Enter available for multiline drafts', () => {
  const { textarea, onSubmit } = renderComposer()
  expect(fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })).toBe(true)
  expect(onSubmit).not.toHaveBeenCalled()
})

test.each([{ disabled: true }, { value: '   ' }])('PRD composer rejects form submission when unavailable %j', (props) => {
  const { form, onSubmit } = renderComposer(props)
  fireEvent.submit(form)
  expect(onSubmit).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
})

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