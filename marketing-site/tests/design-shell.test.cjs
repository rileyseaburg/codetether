const React = require('react')
const { render, screen, cleanup } = require('@testing-library/react')
jest.mock('next/navigation', () => ({ usePathname: jest.fn() }))
jest.mock('@/lib/api', () => ({ createGlobalTaskV1AgentTasksPost: jest.fn(), getTaskV1AgentTasksTaskIdGet: jest.fn() }))
const { usePathname } = require('next/navigation')
const { ChatWidget } = require('@/components/ChatWidget')

afterEach(cleanup)
test.each(['/dashboard', '/dashboard/tasks', '/dashboard/sessions'])('marketing chat does not cover %s controls', pathname => {
  usePathname.mockReturnValue(pathname)
  render(React.createElement(ChatWidget))
  expect(screen.queryByRole('button', { name: 'Open chat' })).not.toBeInTheDocument()
})

test('marketing pages retain the chat entry point', () => {
  usePathname.mockReturnValue('/')
  render(React.createElement(ChatWidget))
  expect(screen.getByRole('button', { name: 'Open chat' })).toBeVisible()
})
