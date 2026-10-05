const React = require('react')
const { ModelSelector } = require('@/components/ModelSelector')

test.each(['default', 'compact', 'card', 'sessions'])(
  'outer %s selector forwards disabled semantics',
  (variant) => {
    const changed = jest.fn()
    render(
      React.createElement(ModelSelector, {
        visualVariant: variant,
        disabled: true,
        label: 'Model',
        selectedModel: 'openai/alpha',
        availableModels: ['openai/alpha'],
        loading: false,
        onSelectedModelChange: changed,
      }),
    )
    const input = screen.getByRole('combobox', { name: 'Model' })
    expect(input).toBeDisabled()
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(changed).not.toHaveBeenCalled()
  },
)
const { render, screen, fireEvent, cleanup } = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
const {
  SearchableDropdown,
} = require('@/components/ModelSelector/SearchableDropdown')
const {
  DefaultSelector,
  CompactSelector,
  CardSelector,
  SessionsSelector,
} = require('@/components/ModelSelector/variants')

const options = ['openai/alpha', 'anthropic/beta', 'groq/gamma']
afterEach(() => {
  cleanup()
  jest.restoreAllMocks()
})

function setup(props = {}) {
  const changed = jest.fn()
  const submitted = jest.fn()
  function Fixture() {
    const [value, setValue] = React.useState(props.value || '')
    return React.createElement(
      'form',
      {
        onSubmit: (event) => {
          event.preventDefault()
          submitted()
        },
      },
      React.createElement('button', { type: 'button' }, 'Before'),
      React.createElement(SearchableDropdown, {
        options,
        label: 'Model',
        ...props,
        value,
        onChange: (next) => {
          changed(next)
          setValue(next)
        },
      }),
      React.createElement('button', { type: 'submit' }, 'Submit'),
    )
  }
  const view = render(React.createElement(Fixture))
  return {
    ...view,
    changed,
    submitted,
    input: screen.getByRole('combobox', { name: 'Model' }),
    user: userEvent.setup(),
  }
}

test('combobox has relationships, selected semantics, and keyboard selection', async () => {
  const { input, user, changed, submitted } = setup({ value: options[1] })
  expect(input).toHaveAttribute('aria-expanded', 'false')
  await user.click(input)
  const list = screen.getByRole('listbox', { name: 'Model' })
  expect(input).toHaveAttribute('aria-controls', list.id)
  expect(screen.getByRole('option', { selected: true })).toHaveTextContent(
    'beta',
  )
  await user.keyboard('{ArrowDown}')
  expect(
    document.getElementById(input.getAttribute('aria-activedescendant')),
  ).toHaveTextContent('beta')
  await user.keyboard('{ArrowDown}{Enter}')
  expect(changed).toHaveBeenCalledWith(options[2])
  expect(input).toHaveValue(options[2])
  expect(input).toHaveFocus()
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(input).not.toHaveAttribute('aria-activedescendant')
  expect(submitted).not.toHaveBeenCalled()
})

test('Escape closes; ArrowUp reopens and End/Home navigate without typing', async () => {
  const { input, user } = setup()
  await user.click(input)
  await user.keyboard('{Escape}')
  expect(input).toHaveAttribute('aria-expanded', 'false')
  await user.keyboard('{ArrowUp}')
  expect(
    document.getElementById(input.getAttribute('aria-activedescendant')),
  ).toHaveTextContent('gamma')
  await user.keyboard('{Home}')
  expect(
    document.getElementById(input.getAttribute('aria-activedescendant')),
  ).toHaveTextContent('alpha')
  await user.keyboard('{End}')
  expect(
    document.getElementById(input.getAttribute('aria-activedescendant')),
  ).toHaveTextContent('gamma')
})

test('Tab reaches filter controls without selecting, trapping, or blur-timer dismissal', async () => {
  const { input, user, changed } = setup()
  await user.click(input)
  await user.keyboard('{ArrowDown}')
  await user.tab()
  expect(screen.getByRole('button', { name: 'All', exact: true })).toHaveFocus()
  expect(input).toHaveAttribute('aria-expanded', 'true')
  expect(changed).not.toHaveBeenCalled()
  for (
    let i = 0;
    i < 20 &&
    document.activeElement !== screen.getByRole('button', { name: 'Submit' });
    i++
  )
    await user.tab()
  expect(screen.getByRole('button', { name: 'Submit' })).toHaveFocus()
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(changed).not.toHaveBeenCalled()
})

test('Shift+Tab exits, Escape from a filter restores input focus, and drafts are discarded', async () => {
  const { input, user, changed } = setup({ value: options[0] })
  await user.click(input)
  fireEvent.change(input, { target: { value: 'beta' } })
  await user.tab()
  await user.keyboard('{Escape}')
  expect(input).toHaveFocus()
  expect(input).toHaveValue(options[0])
  expect(input).toHaveAttribute('aria-expanded', 'false')
  await user.tab({ shift: true })
  expect(screen.getByRole('button', { name: 'Before' })).toHaveFocus()
  expect(changed).not.toHaveBeenCalled()
})

test('filters and pointer selection never submit an enclosing form', async () => {
  const { input, user, submitted, changed } = setup()
  await user.click(input)
  const category = screen.getByRole('button', { name: 'Direct', exact: true })
  await user.click(category)
  expect(category).toHaveAttribute('aria-pressed', 'true')
  await user.click(screen.getByRole('button', { name: 'All', exact: true }))
  await user.click(screen.getByRole('button', { name: 'All providers' }))
  await user.click(screen.getByRole('option', { name: /alpha/ }))
  expect(changed).toHaveBeenCalledTimes(1)
  expect(changed).toHaveBeenCalledWith(options[0])
  expect(submitted).not.toHaveBeenCalled()
})

test('search is immediate so Enter cannot commit a stale highlighted result', async () => {
  const { input, user, changed } = setup()
  await user.click(input)
  await user.keyboard('{ArrowDown}')
  fireEvent.change(input, { target: { value: 'zzzzzzzzzz' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(changed).not.toHaveBeenCalled()
  expect(screen.queryAllByRole('option')).toHaveLength(0)
})

test('no results and no registered models have distinct accessible feedback', async () => {
  const { input, user, rerender } = setup()
  await user.click(input)
  fireEvent.change(input, { target: { value: 'zzzzzzzzzz' } })
  expect(screen.getByRole('status')).toHaveTextContent(
    'No models match your search or filters',
  )
  expect(input).not.toHaveAttribute('aria-activedescendant')
  rerender(
    React.createElement(SearchableDropdown, {
      value: '',
      onChange: jest.fn(),
      options: [],
      label: 'Model',
    }),
  )
  expect(screen.getByRole('status')).toHaveTextContent('No models available')
})

test.each([{ isComposing: true }, { keyCode: 229 }])(
  'composing Enter never selects: %j',
  async (event) => {
    const { input, user, changed } = setup({ options: [options[0]] })
    await user.click(input)
    fireEvent.keyDown(input, { key: 'Enter', ...event })
    expect(changed).not.toHaveBeenCalled()
    expect(input).toHaveAttribute('aria-expanded', 'true')
  },
)

test('replacing the model list invalidates the active descendant even at the same length', async () => {
  const onChange = jest.fn()
  const view = render(
    React.createElement(SearchableDropdown, { value: '', options, onChange }),
  )
  const input = screen.getByRole('combobox')
  fireEvent.focus(input)
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(input).toHaveAttribute('aria-activedescendant')
  view.rerender(
    React.createElement(SearchableDropdown, {
      value: '',
      options: ['openai/new', 'anthropic/new', 'groq/new'],
      onChange,
    }),
  )
  expect(input).not.toHaveAttribute('aria-activedescendant')
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(onChange).not.toHaveBeenCalled()
})

test('loading disables and closes a popup without changing its value or reopening afterward', () => {
  const props = { value: options[0], options, onChange: jest.fn() }
  const view = render(React.createElement(SearchableDropdown, props))
  const input = screen.getByRole('combobox')
  fireEvent.focus(input)
  view.rerender(
    React.createElement(SearchableDropdown, { ...props, loading: true }),
  )
  expect(input).toBeDisabled()
  expect(input).toHaveAttribute('aria-busy', 'true')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Loading models')
  view.rerender(React.createElement(SearchableDropdown, props))
  expect(input).toBeEnabled()
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(input).toHaveValue(options[0])
  expect(props.onChange).not.toHaveBeenCalled()
})

test('outside pointerdown dismisses without committing the active option', async () => {
  const { input, user, changed } = setup()
  await user.click(input)
  await user.keyboard('{ArrowDown}')
  fireEvent.pointerDown(document.body)
  expect(input).toHaveAttribute('aria-expanded', 'false')
  expect(changed).not.toHaveBeenCalled()
})

test('fixed popup uses viewport coordinates, including after page scroll', () => {
  const { input } = setup()
  const rect = jest
    .spyOn(input, 'getBoundingClientRect')
    .mockReturnValue({ bottom: 60, left: 30, width: 220 })
  jest.replaceProperty(window, 'scrollY', 400)
  jest.replaceProperty(window, 'scrollX', 100)
  fireEvent.focus(input)
  const popup = screen.getByRole('listbox').parentElement
  expect(popup).toHaveStyle({ top: '60px', left: '30px', width: '220px' })
  rect.mockReturnValue({ bottom: 90, left: 15, width: 240 })
  fireEvent.scroll(window)
  expect(popup).toHaveStyle({ top: '90px', left: '15px', width: '240px' })
})

test('keyboard navigation scrolls the option list independently of filter headers', () => {
  const { input } = setup()
  fireEvent.focus(input)
  const list = screen.getByRole('listbox')
  const option = screen.getAllByRole('option')[0]
  jest
    .spyOn(list, 'getBoundingClientRect')
    .mockReturnValue({ top: 200, bottom: 400 })
  jest
    .spyOn(option, 'getBoundingClientRect')
    .mockReturnValue({ top: 450, bottom: 490 })
  fireEvent.keyDown(input, { key: 'ArrowDown' })
  expect(list.scrollTop).toBe(90)
})

test('a footer combobox opens upward and bounds its height to the viewport', () => {
  const { input } = setup()
  jest
    .spyOn(input, 'getBoundingClientRect')
    .mockReturnValue({ top: 700, bottom: 740, left: 30, width: 220 })
  jest.replaceProperty(window, 'innerHeight', 768)
  fireEvent.focus(input)
  const popup = screen.getByRole('listbox').parentElement
  expect(popup).toHaveStyle({
    top: '692px',
    transform: 'translateY(-100%)',
    maxHeight: '448px',
  })
})

describe.each([
  ['default', DefaultSelector],
  ['compact', CompactSelector],
  ['card', CardSelector],
  ['sessions', SessionsSelector],
])('%s variant', (_name, Variant) => {
  const props = {
    selectedModel: '',
    setSelectedModel: jest.fn(),
    availableModels: options,
    loadingAgents: false,
    showSelectedInfo: true,
    showEmptyState: true,
    hasCountBadge: true,
    label: 'Choose model',
    className: 'fixture-class',
  }
  test('explicit disabled state is not announced as loading', () => {
    render(React.createElement(Variant, { ...props, disabled: true }))
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByRole('combobox')).toHaveAttribute('aria-busy', 'false')
    expect(screen.getByRole('status')).not.toHaveTextContent('Loading')
  })
  test('associates visible labels with unique input IDs', () => {
    const { container } = render(
      React.createElement(
        'div',
        null,
        React.createElement(Variant, props),
        React.createElement(Variant, props),
      ),
    )
    const inputs = screen.getAllByRole('combobox', { name: 'Choose model' })
    expect(inputs[0].id).not.toBe(inputs[1].id)
    for (const input of inputs)
      expect(
        Array.from(container.querySelectorAll('label')).some(
          (label) => label.htmlFor === input.id,
        ),
      ).toBe(true)
  })
  test('announces loading before empty-state feedback', () => {
    const view = render(
      React.createElement(Variant, {
        ...props,
        loadingAgents: true,
        availableModels: [],
      }),
    )
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Loading models')
    expect(
      screen.queryByText('No workers with models registered'),
    ).not.toBeInTheDocument()
    view.rerender(
      React.createElement(Variant, { ...props, availableModels: [] }),
    )
    expect(screen.getByRole('status')).toHaveTextContent('No models available')
  })
})
