const React = require('react')
const { render, screen, cleanup, fireEvent } = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
jest.mock('next/link', () => ({
  __esModule: true,
  default: React.forwardRef(function MockLink(props, ref) {
    return React.createElement('a', { ...props, ref })
  }),
}))
const { NavLinks } = require('@/components/NavLinks')
const { ChatInput } = require('@/components/ui/ChatInput')

afterEach(cleanup)

test('footer navigation targets the homepage from secondary pages', () => {
  window.history.replaceState({}, '', '/docs')
  try {
    render(React.createElement(NavLinks))
    for (const [name, fragment] of [
      ['Features', 'features'], ['Use Cases', 'use-cases'],
      ['Roadmap', 'roadmap'], ['Pricing', 'pricing'],
    ]) {
      const link = screen.getByRole('link', { name })
      expect(link).toHaveAttribute('href', `/#${fragment}`)
      expect(new URL(link.href).pathname).toBe('/')
    }
    expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute(
      'rel', 'noopener noreferrer',
    )
  } finally {
    window.history.replaceState({}, '', '/')
  }
})

function renderPRDComposer(disabled = false, initial = '未完成') {
  const sent = jest.fn()
  function Composer() {
    const [value, setValue] = React.useState(initial)
    const submit = () => { sent(value); setValue('') }
    return React.createElement(ChatInput, {
      value, onChange: setValue, onSubmit: submit, disabled,
      onKeyDown: (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault()
          submit()
        }
      },
    })
  }
  render(React.createElement(Composer))
  return { sent, input: screen.getByRole('textbox', { name: 'Type a message...' }) }
}

test('PRD composer preserves an IME draft until composition ends', () => {
  const { sent, input } = renderPRDComposer()
  fireEvent.compositionStart(input)
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.submit(input.closest('form'))
  expect(sent).not.toHaveBeenCalled()
  expect(input).toHaveValue('未完成')
  fireEvent.compositionEnd(input)
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(sent).toHaveBeenCalledTimes(1)
  expect(sent).toHaveBeenCalledWith('未完成')
  expect(input).toHaveValue('')
})

test.each([{ isComposing: true }, { keyCode: 229 }])(
  'PRD composer ignores native IME confirmation %j', (nativeState) => {
    const { sent, input } = renderPRDComposer()
    fireEvent.keyDown(input, { key: 'Enter', ...nativeState })
    expect(sent).not.toHaveBeenCalled()
    expect(input).toHaveValue('未完成')
  },
)

test('PRD composer supports Shift+Enter before submitting a multiline draft', async () => {
  const user = userEvent.setup()
  const { sent, input } = renderPRDComposer(false, 'first')
  await user.click(input)
  await user.keyboard('{Shift>}{Enter}{/Shift}second')
  expect(sent).not.toHaveBeenCalled()
  expect(input).toHaveValue('first\nsecond')
  await user.keyboard('{Enter}')
  expect(sent).toHaveBeenCalledWith('first\nsecond')
})

test.each([[true, 'draft'], [false, '   '], [false, '']])(
  'PRD composer rejects disabled or blank form and keyboard submission (%s, %j)', (disabled, initial) => {
    const { sent, input } = renderPRDComposer(disabled, initial)
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    fireEvent.submit(input.closest('form'))
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(sent).not.toHaveBeenCalled()
    expect(input).toHaveValue(initial)
  },
)

test('PRD composer submits using the accessible send button', async () => {
  const user = userEvent.setup()
  const { sent } = renderPRDComposer()
  await user.click(screen.getByRole('button', { name: 'Send message' }))
  expect(sent).toHaveBeenCalledWith('未完成')
})