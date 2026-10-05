const React = require('react')
const {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} = require('@testing-library/react')
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({
    status: 'authenticated',
    data: { accessToken: 'fixture' },
  })),
}))
jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/lib/api', () => ({
  listProvidersV1AgentProvidersGet: jest.fn(),
  vaultStatusV1AgentVaultStatusGet: jest.fn(),
  listApiKeysV1AgentApiKeysGet: jest.fn(),
  createOrUpdateApiKeyV1AgentApiKeysPost: jest.fn(),
  deleteApiKeyV1AgentApiKeysProviderIdDelete: jest.fn(),
  testApiKeyEndpointV1AgentApiKeysTestPost: jest.fn(),
  getSubscriptionV1BillingSubscriptionGet: jest.fn(),
  getUsageV1BillingUsageGet: jest.fn(),
  createCheckoutV1BillingCheckoutPost: jest.fn(),
  createPortalV1BillingPortalPost: jest.fn(),
  client: {},
}))
const api = require('@/lib/api')
const Settings = require('@/app/(dashboard)/dashboard/settings/page').default
const Billing = require('@/app/(dashboard)/dashboard/billing/page').default
const display = require('@/lib/billing-display')
const subscription = {
  tier: 'pro',
  tier_name: 'Pro',
  tasks_limit: 1000,
  concurrency_limit: 5,
  max_runtime_seconds: 600,
}
beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  require('next-auth/react').useSession.mockReturnValue({
    status: 'authenticated',
    data: { accessToken: 'fixture' },
  })
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503 })
  api.listProvidersV1AgentProvidersGet.mockResolvedValue({
    data: [
      { id: 'openai', name: 'OpenAI' },
      {
        id: 'custom',
        name: 'Custom',
        requires_base_url: true,
        has_base_url: true,
      },
    ],
  })
  api.vaultStatusV1AgentVaultStatusGet.mockResolvedValue({
    data: { connected: true, authenticated: true },
  })
  api.listApiKeysV1AgentApiKeysGet.mockResolvedValue({ data: [] })
  api.getSubscriptionV1BillingSubscriptionGet.mockResolvedValue({
    data: subscription,
  })
  api.getUsageV1BillingUsageGet.mockResolvedValue({
    data: { tasks_used: 12, tasks_limit: 1000 },
  })
  api.testApiKeyEndpointV1AgentApiKeysTestPost.mockResolvedValue({
    data: { success: true, tested: true, message: 'Key verified' },
  })
})
afterEach(cleanup)
async function keyForm(provider = 'openai') {
  render(React.createElement(Settings))
  fireEvent.change(await screen.findByLabelText('Provider'), {
    target: { value: provider },
  })
  fireEvent.change(screen.getByLabelText('API Key'), {
    target: { value: ' entered-fixture-key ' },
  })
}
test('tests an entered key without any saved keys and never saves it', async () => {
  await keyForm()
  fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Key verified')
  expect(api.testApiKeyEndpointV1AgentApiKeysTestPost).toHaveBeenCalledWith(
    expect.objectContaining({
      body: { provider_id: 'openai', api_key: 'entered-fixture-key' },
    }),
  )
  expect(api.createOrUpdateApiKeyV1AgentApiKeysPost).not.toHaveBeenCalled()
})
test.each([
  [{ data: { success: false, message: 'Invalid key' } }, 'Invalid key'],
  [
    { data: { success: true, tested: false, message: 'API key saved' } },
    'has not saved or verified',
  ],
  [{ error: { detail: ['invalid'] } }, 'API key test failed'],
])(
  'does not turn unsuccessful or unsupported tests into success: %j',
  async (result, message) => {
    api.testApiKeyEndpointV1AgentApiKeysTestPost.mockResolvedValue(result)
    await keyForm()
    fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  },
)
test('custom base URL is required and not silently tested against the default endpoint', async () => {
  await keyForm('custom')
  fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('base URL')
  fireEvent.change(screen.getByLabelText('Base URL (required)'), {
    target: { value: 'https://fixture.invalid/v1' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Custom endpoint testing is not supported',
  )
  expect(api.testApiKeyEndpointV1AgentApiKeysTestPost).not.toHaveBeenCalled()
})
test('usage failure preserves subscription quota and retry recovers', async () => {
  api.getUsageV1BillingUsageGet.mockResolvedValueOnce({
    error: { detail: 'unavailable' },
  })
  render(React.createElement(Billing))
  expect(await screen.findByText('Unavailable / 1,000')).toBeInTheDocument()
  expect(screen.queryByText('0 / 0')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry task usage' }))
  expect(await screen.findByText('12 / 1,000')).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'Retry task usage' }),
  ).not.toBeInTheDocument()
})
test.each([
  undefined,
  { tasks_used: null },
  { tasks_used: 'bad' },
  { tasks_used: -1 },
])('malformed usage is unavailable: %j', async (data) => {
  api.getUsageV1BillingUsageGet.mockResolvedValue({ data })
  render(React.createElement(Billing))
  expect(await screen.findByText('Unavailable / 1,000')).toBeInTheDocument()
})
test('rejected usage requests preserve quota', async () => {
  api.getUsageV1BillingUsageGet.mockRejectedValueOnce(
    new Error('fixture failure'),
  )
  render(React.createElement(Billing))
  expect(await screen.findByText('Unavailable / 1,000')).toBeInTheDocument()
})
test('zero usage and missing usage quota do not override subscription quota', async () => {
  api.getUsageV1BillingUsageGet.mockResolvedValue({ data: { tasks_used: 0 } })
  render(React.createElement(Billing))
  expect(await screen.findByText('0 / 1,000')).toBeInTheDocument()
})
test('token API failure is explicit and has a working retry', async () => {
  render(React.createElement(Billing))
  fireEvent.click(
    await screen.findByRole('button', { name: 'Retry token usage' }),
  )
  await waitFor(() =>
    expect(
      global.fetch.mock.calls.filter(([url]) =>
        url.includes('/token-billing/usage/summary'),
      ),
    ).toHaveLength(2),
  )
})
test.each([Settings, Billing])(
  'live plan/unlimited contract renders without pretending to be free',
  async (Page) => {
    api.getSubscriptionV1BillingSubscriptionGet.mockResolvedValue({
      data: { plan: 'enterprise', status: 'active' },
    })
    api.getUsageV1BillingUsageGet.mockResolvedValue({
      data: { tasks_used: 7, tasks_limit: -1 },
    })
    render(React.createElement(Page))
    expect(
      await screen.findByText('Enterprise', { exact: true }),
    ).toBeInTheDocument()
    expect(
      await screen.findByText('7 / Unlimited', { exact: true }),
    ).toBeInTheDocument()
  },
)

test('unlimited quotas remain distinct from unavailable data', () => {
  expect(display.quotaNumber(-1)).toBe(-1)
  expect(display.formatQuota('-1')).toBe('Unlimited')
  expect(display.formatQuota(null)).toBe('Unavailable')
  expect(display.remainingTasks(7, -1)).toBe(-1)
})

test('numeric display handles partial values and bounds percentages', () => {
  for (const input of [undefined, null, '', 'bad', Infinity, NaN, {}, []])
    expect(display.formatNumber(input)).toBe('Unavailable')
  expect(display.formatNumber('12.50', 2)).toBe('12.50')
  expect(display.formatNumber(0)).toBe('0')
  expect(display.remainingTasks(null, 1000)).toBeNull()
  expect(display.remainingTasks(1500, 1000)).toBe(0)
  expect(display.usagePercentage(0, 0)).toBe(0)
  expect(display.usagePercentage(undefined, 100)).toBe(0)
  expect(display.usagePercentage(1000, 100)).toBe(100)
})
test('numeric string token totals and partial budgets render safely', async () => {
  global.fetch.mockImplementation(async (url) => ({
    ok: url.includes('/token-billing/'),
    json: async () =>
      url.includes('/usage/summary')
        ? {
            totals: { total_requests: '4', total_cost_dollars: '0.12' },
            by_model: [
              { model: 'fixture', request_count: null, cost_dollars: '0.12' },
            ],
          }
        : {
            balance_dollars: '3.00',
            monthly_spend_dollars: null,
            monthly_limit_dollars: 0,
          },
  }))
  render(React.createElement(Billing))
  expect(await screen.findByText('$3.00')).toBeInTheDocument()
  expect(screen.getAllByText('$0.1200').length).toBeGreaterThan(0)
})
test.each([Settings, Billing])(
  'password login tokens load account pages without an SSO session',
  async (Page) => {
    require('next-auth/react').useSession.mockReturnValue({
      status: 'unauthenticated',
      data: null,
    })
    localStorage.setItem('a2a_token', 'password-fixture')
    render(React.createElement(Page))
    await waitFor(() =>
      expect(api.getSubscriptionV1BillingSubscriptionGet).toHaveBeenCalledWith({
        headers: { Authorization: 'Bearer password-fixture' },
      }),
    )
    expect(
      await screen.findByRole('heading', {
        name: Page === Settings ? 'Settings' : 'Billing',
        exact: true,
      }),
    ).toBeInTheDocument()
  },
)
test('locks key edits and saving until an in-flight test settles', async () => {
  let finish
  api.testApiKeyEndpointV1AgentApiKeysTestPost.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await keyForm()
  fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
  expect(screen.getByRole('button', { name: 'Save API Key' })).toBeDisabled()
  expect(screen.getByLabelText('Provider')).toBeDisabled()
  expect(screen.getByLabelText('API Key')).toBeDisabled()
  finish({ data: { success: true, tested: true, message: 'Settled' } })
  expect(await screen.findByRole('status')).toHaveTextContent('Settled')
  expect(screen.getByLabelText('API Key')).not.toBeDisabled()
})
test('saves a custom URL with the entered key while treating testing separately', async () => {
  api.createOrUpdateApiKeyV1AgentApiKeysPost.mockResolvedValue({
    data: { message: 'Saved fixture' },
  })
  await keyForm('custom')
  fireEvent.change(screen.getByLabelText('Base URL (required)'), {
    target: { value: 'https://fixture.invalid/v1' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save API Key' }))
  await waitFor(() =>
    expect(api.createOrUpdateApiKeyV1AgentApiKeysPost).toHaveBeenCalledWith(
      expect.objectContaining({
        body: {
          provider_id: 'custom',
          api_key: 'entered-fixture-key',
          base_url: 'https://fixture.invalid/v1',
        },
      }),
    ),
  )
  expect(await screen.findByRole('status')).toHaveTextContent('Saved fixture')
})
test('failed key request gives feedback and restores controls', async () => {
  const log = jest.spyOn(console, 'error').mockImplementation(() => {})
  api.testApiKeyEndpointV1AgentApiKeysTestPost.mockRejectedValueOnce(
    new Error('fixture offline'),
  )
  await keyForm()
  fireEvent.click(screen.getByRole('button', { name: 'Test Key' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Failed to test API key',
  )
  expect(screen.getByRole('button', { name: 'Test Key' })).not.toBeDisabled()
  log.mockRestore()
})
test.each([Settings, Billing])(
  'missing credentials show sign-in instead of spinning forever',
  async (Page) => {
    require('next-auth/react').useSession.mockReturnValue({
      status: 'unauthenticated',
      data: null,
    })
    render(React.createElement(Page))
    expect(
      await screen.findByRole('heading', { name: /Sign in to manage/ }),
    ).toBeInTheDocument()
    expect(api.getSubscriptionV1BillingSubscriptionGet).not.toHaveBeenCalled()
  },
)
