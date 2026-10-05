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
  expect(screen.getByRole('link', { name: 'Settings', exact: true })).toHaveAttribute(
    'href',
    '/dashboard/settings',
  )
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