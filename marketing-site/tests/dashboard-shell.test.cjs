const React = require('react')
const {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
const { readFileSync } = require('node:fs')
const { join } = require('node:path')

jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/tasks',
  useRouter: () => ({ push: jest.fn() }),
}))
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { name: 'UI Test', email: 'ui@example.invalid' } },
    status: 'authenticated',
  }),
  signOut: jest.fn(),
}))
jest.mock('@/components/ApiAuthSync', () => ({ ApiAuthSync: () => null }))
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
const DashboardLayout = require('../src/app/(dashboard)/layout').default
const {
  ChatInput,
} = require('../src/app/(dashboard)/dashboard/sessions/components/ChatInput')

let desktopChange
let desktop
beforeAll(() => {
  window.matchMedia = jest.fn().mockImplementation((query) => ({
    get matches() {
      return query === '(min-width: 768px)' && desktop
    },
    media: query,
    addEventListener: (_event, callback) => {
      if (query === '(min-width: 768px)') desktopChange = callback
    },
    removeEventListener: jest.fn(),
    addListener: jest.fn(),
    removeListener: jest.fn(),
  }))
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Element.prototype.scrollIntoView = jest.fn()
})
beforeEach(() => {
  desktop = false
  desktopChange = undefined
})

function shell() {
  return render(
    React.createElement(DashboardLayout, {
      children: React.createElement('button', null, 'Page action'),
    }),
  )
}

test('closed drawer unmounts; Escape dismisses and restores focus', async () => {
  const user = userEvent.setup()
  shell()
  expect(
    screen.queryByRole('button', { name: 'Close navigation menu' }),
  ).not.toBeInTheDocument()
  const open = screen.getByRole('button', { name: 'Open navigation menu' })
  await user.click(open)
  const dialog = screen.getByRole('dialog', { name: 'Dashboard navigation' })
  await waitFor(() =>
    expect(
      within(dialog).getByRole('button', { name: 'Close navigation menu' }),
    ).toHaveFocus(),
  )
  const links = within(dialog).getAllByRole('link')
  act(() => links.at(-1).focus())
  await user.tab()
  expect(dialog).toContainElement(document.activeElement)
  await user.keyboard('{Escape}')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
  await waitFor(() => expect(open).toHaveFocus())
})

test('open drawer makes background inert, traps backward Tab, and restores it on close', async () => {
  const user = userEvent.setup()
  const { container } = shell()
  const open = screen.getByRole('button', { name: 'Open navigation menu' })
  expect(open).toHaveAttribute('aria-haspopup', 'dialog')
  expect(open).toHaveAttribute('aria-expanded', 'false')
  await user.click(open)
  const dialog = screen.getByRole('dialog', { name: 'Dashboard navigation' })
  expect(open).toHaveAttribute('aria-controls', dialog.id)
  expect(open).toHaveAttribute('aria-expanded', 'true')
  expect(container).toHaveAttribute('aria-hidden', 'true')
  expect(container.inert).toBe(true)
  expect(screen.queryByRole('button', { name: 'Page action' })).toBeNull()
  act(() => within(dialog).getAllByRole('link')[0].focus())
  await user.tab({ shift: true })
  expect(dialog).toContainElement(document.activeElement)
  await user.click(
    within(dialog).getByRole('button', { name: 'Close navigation menu' }),
  )
  await waitFor(() => expect(open).toHaveFocus())
  expect(container).not.toHaveAttribute('aria-hidden')
  expect(container.inert).not.toBe(true)
  expect(open).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByRole('button', { name: 'Page action' })).toBeVisible()
})

test('theme control announces the action for the current mode', async () => {
  const user = userEvent.setup()
  shell()
  const theme = screen.getByRole('button', { name: /Switch to .* mode/ })
  const initialLabel = theme.getAttribute('aria-label')
  await user.click(theme)
  expect(theme).not.toHaveAttribute('aria-label', initialLabel)
  expect(theme).toHaveAccessibleName(
    initialLabel === 'Switch to light mode'
      ? 'Switch to dark mode'
      : 'Switch to light mode',
  )
})

test('user menu keyboard opening and Escape restore focus', async () => {
  const user = userEvent.setup()
  shell()
  const trigger = screen.getByRole('button', { name: 'Open user menu' })
  act(() => trigger.focus())
  await user.keyboard('{ArrowDown}')
  const menu = await screen.findByRole('menu')
  expect(
    within(menu).getByRole('menuitem', { name: 'Billing' }),
  ).toHaveAttribute('href', '/dashboard/billing')
  await user.keyboard('{Escape}')
  await waitFor(() =>
    expect(screen.queryByRole('menu')).not.toBeInTheDocument(),
  )
  await waitFor(() => expect(trigger).toHaveFocus())
})

test('switching to desktop dismisses the modal', async () => {
  const user = userEvent.setup()
  shell()
  await user.click(screen.getByRole('button', { name: 'Open navigation menu' }))
  act(() => {
    desktop = true
    desktopChange?.()
  })
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
})

test('drawer close control and navigation both dismiss the modal', async () => {
  const user = userEvent.setup()
  shell()
  const open = screen.getByRole('button', { name: 'Open navigation menu' })
  await user.click(open)
  await user.click(
    screen.getByRole('button', { name: 'Close navigation menu' }),
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await user.click(open)
  await user.click(
    within(screen.getByRole('dialog')).getByRole('link', {
      name: 'CodeTether',
    }),
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('settings remains available without a duplicate toolbar gear', () => {
  shell()
  expect(
    screen.getByRole('link', { name: 'Settings', exact: true }),
  ).toHaveAttribute('href', '/dashboard/settings')
  expect(document.querySelector('a[aria-label="Settings"]')).toBeNull()
})

test.each([
  [{ key: 'Enter', isComposing: true }, 0],
  [{ key: 'Enter', keyCode: 229 }, 0],
  [{ key: 'Enter', shiftKey: true }, 0],
  [{ key: 'Enter' }, 1],
])('chat Enter respects composition and Shift: %j', (event, sends) => {
  const onSend = jest.fn()
  render(
    React.createElement(ChatInput, {
      draftMessage: 'Draft',
      hasSession: true,
      loading: false,
      actionStatus: null,
      onDraftChange: jest.fn(),
      onSend,
    }),
  )
  fireEvent.keyDown(screen.getByRole('textbox'), event)
  expect(onSend).toHaveBeenCalledTimes(sends)
})

test('chat retains composition state even when the final Enter clears the native flag', () => {
  const send = jest.fn()
  render(
    React.createElement(ChatInput, {
      draftMessage: '未確定',
      loading: false,
      hasSession: true,
      onDraftChange: jest.fn(),
      onSend: send,
    }),
  )
  const input = screen.getByRole('textbox')
  fireEvent.compositionStart(input)
  const confirmation = new KeyboardEvent('keydown', {
    key: 'Enter',
    isComposing: false,
    bubbles: true,
    cancelable: true,
  })
  fireEvent(input, confirmation)
  fireEvent.submit(input.closest('form'))
  expect(send).not.toHaveBeenCalled()
  expect(confirmation.defaultPrevented).toBe(false)
  expect(input).toHaveValue('未確定')
  fireEvent.compositionEnd(input)
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(send).toHaveBeenCalledTimes(1)
})

test.each([
  { draftMessage: '', loading: false },
  { draftMessage: '   ', loading: false },
  { draftMessage: 'Draft', loading: true },
])('chat never submits an unavailable draft: %j', (props) => {
  const send = jest.fn()
  render(
    React.createElement(ChatInput, {
      ...props,
      hasSession: true,
      onDraftChange: jest.fn(),
      onSend: send,
    }),
  )
  const input = screen.getByRole('textbox')
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.submit(input.closest('form'))
  expect(
    screen.getByRole('button', { name: /Sending message|Send message/ }),
  ).toBeDisabled()
  expect(send).not.toHaveBeenCalled()
})

test('chat submits a ready draft once through the named Send button', async () => {
  const send = jest.fn()
  render(
    React.createElement(ChatInput, {
      draftMessage: 'Ready draft',
      loading: false,
      hasSession: true,
      onDraftChange: jest.fn(),
      onSend: send,
    }),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
  expect(send).toHaveBeenCalledTimes(1)
})

test('task selection uses one native button without nested controls', () => {
  const source = readFileSync(
    join(process.cwd(), 'src/app/(dashboard)/dashboard/tasks/page.tsx'),
    'utf8',
  )
  const row = source.slice(
    source.indexOf('filteredTasks.map((task) => ('),
    source.indexOf('{/* Task Detail */}'),
  )
  expect(row).toMatch(/<button\s+key=\{task.id\}/)
  expect(row).toContain('type="button"')
  expect(row).toContain('aria-pressed={selectedTask?.id === task.id}')
  expect(row).toContain('onClick=')
  expect(row.match(/<button\b/g)).toHaveLength(1)
  expect(row).not.toMatch(/<(a|input|select|textarea)\b/)
  expect(row).toContain('</button>')
})

test('desktop inset matches sidebar width', () => {
  const source = readFileSync(
    join(process.cwd(), 'src/app/(dashboard)/layout.tsx'),
    'utf8',
  )
  expect(source).toContain('md:w-60 lg:w-56')
  expect(source).toContain('md:left-60 lg:left-56')
})
