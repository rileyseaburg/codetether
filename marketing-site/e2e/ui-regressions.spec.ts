import { test, expect as baseExpect, type Page } from '@playwright/test'
import { createServer, type Server } from 'node:http'
const expect = baseExpect.configure({ timeout: 15000 })

// These tests intentionally use fixture accounts and never contact production.
test.skip(
  process.env.BASE_URL !== 'http://127.0.0.1:3107',
  'Requires the local UI regression server',
)
test.use({
  launchOptions: {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  },
})
test.setTimeout(90_000)
let oidc: Server
test.beforeAll(async () => {
  oidc = createServer((req, res) => {
    const issuer = `http://127.0.0.1:3108${req.url?.replace('/.well-known/openid-configuration', '')}`
    res.setHeader('Content-Type', 'application/json')
    res.end(
      JSON.stringify({
        issuer,
        authorization_endpoint: `${issuer}/protocol/openid-connect/auth`,
        token_endpoint: `${issuer}/protocol/openid-connect/token`,
        jwks_uri: `${issuer}/certs`,
        response_types_supported: ['code'],
        subject_types_supported: ['public'],
        id_token_signing_alg_values_supported: ['RS256'],
        code_challenge_methods_supported: ['S256'],
      }),
    )
  })
  await new Promise<void>((resolve) => oidc.listen(3108, '127.0.0.1', resolve))
})
test.afterAll(async () => {
  if (oidc) await new Promise<void>((resolve) => oidc.close(() => resolve()))
})

async function fixtures(
  page: Page,
  auth: 'sso' | 'password' | 'anonymous' = 'sso',
) {
  const writes: {
    path: string
    body: Record<string, unknown>
    authorization?: string
  }[] = []
  await page.setExtraHTTPHeaders({ 'x-cypress-test': 'true' })
  if (auth === 'password') {
    await page.addInitScript(() => {
      localStorage.setItem('a2a_token', 'password-fixture')
      localStorage.setItem(
        'a2a_user',
        JSON.stringify({ name: 'Audit User', email: 'audit@example.invalid' }),
      )
    })
  }
  let usageUnavailable = true
  let tasksUnavailable = false
  let sessionsUnavailable = false
  let messagesUnavailable = false
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (path === '/api/auth/session') {
      return route.fulfill({
        json:
          auth === 'sso'
            ? {
                user: { name: 'Audit User', email: 'audit@example.invalid' },
                expires: '2099-01-01T00:00:00.000Z',
                accessToken: 'sso-fixture',
              }
            : null,
      })
    }
    if (
      ['http://127.0.0.1:3107', 'http://localhost:3107'].includes(url.origin) &&
      !path.startsWith('/api/')
    )
      return route.continue()
    if (path.endsWith('/protocol/openid-connect/auth')) {
      return route.fulfill({
        contentType: 'text/html',
        body: '<h1>Fixture identity provider</h1>',
      })
    }
    if (request.method() === 'POST') {
      writes.push({
        path,
        body: request.postDataJSON(),
        authorization: request.headers().authorization,
      })
      if (path === '/v1/tenants/signup')
        return route.fulfill({
          status: 201,
          json: {
            tenant_id: 'tenant-fixture',
            realm_name: 'audit-123.codetether.run',
            login_url: 'https://untrusted.example.invalid/auth',
            spa_client_id: 'untrusted-client',
            instance_url: 'https://audit-123.codetether.run',
            provisioning_status: 'completed',
          },
        })
      if (path.endsWith('/api-keys/test'))
        return route.fulfill({
          json: { success: true, message: 'Fixture key accepted' },
        })
      if (path.endsWith('/billing/checkout'))
        return route.fulfill({
          json: {
            checkout_url:
              'http://127.0.0.1:3107/dashboard/billing?fixture=checkout',
          },
        })
    }
    if (path.endsWith('/agent/providers'))
      return route.fulfill({
        json: {
          providers: [
            {
              id: 'fixture',
              name: 'Fixture Provider',
              requires_base_url: false,
            },
          ],
        },
      })
    if (path.endsWith('/agent/vault/status'))
      return route.fulfill({ json: { connected: true, authenticated: true } })
    if (path.endsWith('/agent/api-keys'))
      return route.fulfill({ json: { keys: [] } })
    if (path.endsWith('/billing/subscription'))
      return route.fulfill({
        json: {
          tier: 'pro',
          tier_name: 'Pro',
          tasks_limit: 1000,
          concurrency_limit: 5,
          max_runtime_seconds: 600,
        },
      })
    if (path.endsWith('/billing/usage'))
      return route.fulfill(
        usageUnavailable
          ? { status: 503, json: { detail: 'Fixture usage unavailable' } }
          : { json: { tasks_used: 25, tasks_limit: 1000 } },
      )
    if (path.endsWith('/agent/workers'))
      return route.fulfill({
        json: [
          {
            worker_id: 'fixture-worker',
            name: 'Fixture Worker',
            models: ['openai/alpha', 'anthropic/beta'],
            status: 'online',
            last_seen: new Date().toISOString(),
            registered_at: new Date().toISOString(),
            capabilities: [],
            codebases: [],
          },
        ],
      })
    if (path.endsWith('/worker/connected'))
      return route.fulfill({
        json: {
          workers: [
            {
              worker_id: 'fixture-worker',
              agent_name: 'Fixture Worker',
              last_heartbeat: new Date().toISOString(),
            },
          ],
        },
      })
    if (path.endsWith('/agent/models'))
      return route.fulfill({
        json: { models: [{ id: 'openai/alpha' }, { id: 'anthropic/beta' }] },
      })

    if (path.endsWith('/agent/workspaces/list'))
      return route.fulfill({
        json: {
          workspaces: [
            {
              id: 'workspace-fixture',
              name: 'Fixture workspace',
              path: '/fixture',
              status: 'online',
            },
          ],
        },
      })
    if (path.endsWith('/workspaces/workspace-fixture/sessions'))
      return route.fulfill(
        sessionsUnavailable
          ? { status: 503, json: { detail: 'Fixture sessions unavailable' } }
          : {
              json: {
                sessions: [
                  {
                    id: 'session-fixture',
                    title: 'Keyboard session',
                    version: '1',
                    projectID: 'workspace-fixture',
                    directory: '/fixture',
                    time: { created: 1767225600000, updated: 1767225600000 },
                  },
                ],
                total: 1,
                hasMore: false,
              },
            },
      )
    if (path.endsWith('/sessions/session-fixture/messages'))
      return route.fulfill(
        messagesUnavailable
          ? { status: 503, json: { detail: 'Fixture messages unavailable' } }
          : { json: { messages: [], total: 0, hasMore: false } },
      )

    if (path.endsWith('/agent/tasks'))
      if (tasksUnavailable)
        return route.fulfill({
          status: 503,
          json: { detail: 'Fixture tasks unavailable' },
        })
    if (path.endsWith('/agent/tasks'))
      return route.fulfill({
        json: {
          tasks: [
            {
              id: 'task-fixture',
              title: 'Keyboard task',
              description: 'Task detail fixture',
              status: 'completed',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
            },
          ],
        },
      })
    return route.fulfill({
      status: 503,
      json: { detail: 'External service blocked by UI fixture' },
    })
  })
  return {
    writes,
    failSessions: () => {
      sessionsUnavailable = true
    },
    restoreSessions: () => {
      sessionsUnavailable = false
    },
    failMessages: () => {
      messagesUnavailable = true
    },
    restoreMessages: () => {
      messagesUnavailable = false
    },
    failTasks: () => {
      tasksUnavailable = true
    },
    restoreTasks: () => {
      tasksUnavailable = false
    },
    restoreUsage: () => {
      usageUnavailable = false
    },
  }
}

test('signup initiates tenant Auth.js sign-in with PKCE and state', async ({
  page,
}) => {
  await fixtures(page, 'anonymous')
  await page.goto('/register')
  await page.locator('[name=org_name]').fill('Audit Workspace')
  await page.locator('[name=email]').fill('audit@example.invalid')
  await page.locator('[name=password]').fill('fixture-password-123')
  await page.locator('button[type=submit]').click()
  await expect(
    page.getByRole('button', { name: 'Sign in to your workspace' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click()
  await page.waitForURL(
    '**/realms/audit-123.codetether.run/protocol/openid-connect/auth?**',
  )
  const params = new URL(page.url()).searchParams
  expect(params.get('client_id')).toBe('audit-123-spa')
  expect(params.get('redirect_uri')).toBe(
    'http://127.0.0.1:3107/api/auth/callback/keycloak',
  )
  expect(params.get('code_challenge_method')).toBe('S256')
  expect(params.get('code_challenge')).toBeTruthy()
  expect(params.get('state')).toBeTruthy()
  const cookies = await page.context().cookies('http://127.0.0.1:3107')
  expect(
    cookies.some(
      (cookie) => cookie.name.includes('pkce.code_verifier') && cookie.httpOnly,
    ),
  ).toBeTruthy()
  expect(
    cookies.some((cookie) => cookie.name.endsWith('.state') && cookie.httpOnly),
  ).toBeTruthy()
})

test('ordinary SSO clears a stale workspace selector', async ({ page }) => {
  await fixtures(page, 'anonymous')
  await page.context().addCookies([
    {
      name: 'codetether-auth-realm',
      value: 'previous-123.codetether.run',
      url: 'http://127.0.0.1:3107',
      httpOnly: true,
      sameSite: 'Lax',
    },
  ])
  await page.goto('/login')
  await page
    .getByRole('button', { name: 'Continue with Quantum Forge SSO' })
    .click()
  await page.waitForURL('**/realms/shared/protocol/openid-connect/auth?**')
  expect(new URL(page.url()).searchParams.get('client_id')).toBe('ui-fixture')
  expect(
    (await page.context().cookies('http://127.0.0.1:3107')).some(
      (cookie) => cookie.name === 'codetether-auth-realm',
    ),
  ).toBe(false)
})

test('password-authenticated users can start paid checkout', async ({
  page,
}) => {
  const { writes } = await fixtures(page, 'password')
  await page.goto('/#pricing')
  const checkout = page.locator('#pricing button').first()
  await expect(checkout).toBeEnabled()
  await checkout.click()
  await page.waitForURL('**/dashboard/billing?fixture=checkout')
  const request = writes.find((write) =>
    write.path.endsWith('/billing/checkout'),
  )!
  expect(request.authorization).toBe('Bearer password-fixture')
  expect(request.body.tier).toBeTruthy()
})

test('dashboard middleware redirects unauthenticated visitors without a test bypass', async ({
  page,
}) => {
  await fixtures(page, 'anonymous')
  await page.setExtraHTTPHeaders({})
  await page.goto('/dashboard/settings')
  await expect(page).toHaveURL(/\/login\?callbackUrl=%2Fdashboard%2Fsettings$/)
  await expect(page.locator('input[name=email]')).toBeVisible()
})

test('secondary-page marketing links reach homepage sections', async ({
  page,
}) => {
  await fixtures(page, 'anonymous')
  await page.goto('/privacy')
  await page
    .locator('header')
    .getByRole('link', { name: 'Pricing', exact: true })
    .click()
  await expect(page).toHaveURL(/\/#pricing$/)
  await expect(page.locator('#pricing')).toBeVisible()
})

test('mobile navigation is hidden from keyboard until opened and restores focus', async ({
  page,
}, info) => {
  await fixtures(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/dashboard/settings')
  const open = page.getByRole('button', { name: 'Open navigation menu' })
  await expect(open).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(
    page.getByRole('link', { name: 'Skip to main content' }),
  ).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#dashboard-main')).toBeFocused()
  const bounds = await page.locator(':focus').boundingBox()
  expect(bounds && bounds.x + bounds.width > 0).toBeTruthy()
  await open.click()
  await expect(
    page.getByRole('dialog', { name: 'Dashboard navigation' }),
  ).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(open).toBeFocused()
  await page.screenshot({
    path: info.outputPath('mobile-settings.png'),
    fullPage: true,
  })
})

test('dashboard theme persists and synchronizes across tabs', async ({
  page,
}, info) => {
  await fixtures(page)
  await page.goto('/dashboard/settings')
  const other = await page.context().newPage()
  await fixtures(other)
  await other.goto('/dashboard/settings')
  await expect(
    other.getByRole('button', { name: 'Switch to light mode' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Switch to light mode' }).click()
  await expect(page.locator('html')).not.toHaveClass(/(?:^|\s)dark(?:\s|$)/)
  await expect(other.locator('html')).not.toHaveClass(/(?:^|\s)dark(?:\s|$)/)
  await other.reload()
  await expect(
    other.getByRole('button', { name: 'Switch to dark mode' }),
  ).toBeVisible()
  await expect(other.locator('html')).not.toHaveClass(/(?:^|\s)dark(?:\s|$)/)
  await expect(page.getByText('Connected', { exact: true })).toHaveCount(0)
  await expect(
    page.getByRole('navigation', { name: 'Breadcrumb' }),
  ).toContainText('Settings')
  await page.screenshot({
    path: info.outputPath('dashboard-light.png'),
    fullPage: true,
  })
  await other.close()
})

test('desktop shell aligns and user menu handles Escape', async ({
  page,
}, info) => {
  await fixtures(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/dashboard/settings')
  const open = page.getByRole('button', { name: 'Open user menu' })
  await open.click()
  await expect(page.getByRole('menu')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(open).toBeFocused()
  const boxes = await page.evaluate(() => ({
    sidebar: document.querySelector('div.md\\:fixed')?.getBoundingClientRect()
      .right,
    content: document
      .querySelector('div.absolute.inset-0')
      ?.getBoundingClientRect().left,
  }))
  expect(boxes.sidebar).toBeDefined()
  expect(boxes.sidebar).toBe(boxes.content)
  await expect(
    page.getByRole('link', { name: 'Settings', exact: true }).last(),
  ).toHaveAttribute('href', '/dashboard/settings')
  await page.screenshot({
    path: info.outputPath('desktop-settings.png'),
    fullPage: true,
  })
})

test('a newly entered API key can be tested without saving first', async ({
  page,
}) => {
  const { writes } = await fixtures(page)
  await page.goto('/dashboard/settings')
  await page.locator('#provider').selectOption('fixture')
  await page.locator('#apiKey').fill('unsaved-fixture-key')
  await page.getByRole('button', { name: 'Test Key', exact: true }).click()
  await expect(page.getByText('Fixture key accepted')).toBeVisible()
  const request = writes.find((write) => write.path.endsWith('/api-keys/test'))!
  expect(request.body).toMatchObject({
    provider_id: 'fixture',
    api_key: 'unsaved-fixture-key',
  })
  expect(writes.some((write) => write.path.endsWith('/api-keys'))).toBe(false)
})

test('billing preserves quota, shows usage unavailable, and retries', async ({
  page,
}) => {
  const { restoreUsage } = await fixtures(page)
  await page.goto('/dashboard/billing')
  const retry = page.getByRole('button', { name: 'Retry task usage' })
  await expect(retry).toBeVisible()
  await expect(
    page.getByText('Unavailable / 1,000', { exact: true }),
  ).toBeVisible()
  restoreUsage()
  await retry.click()
  await expect(page.getByText('25 / 1,000', { exact: true })).toBeVisible()
  await expect(retry).toHaveCount(0)
})

test('task list failure is distinct from empty and retry recovers', async ({
  page,
}, info) => {
  const api = await fixtures(page)
  api.failTasks()
  await page.goto('/dashboard/tasks')
  const retry = page.getByRole('button', { name: 'Retry loading tasks' })
  await expect(retry).toBeVisible()
  await expect(page.getByText('No tasks found', { exact: true })).toHaveCount(0)
  await page.screenshot({
    path: info.outputPath('tasks-unavailable.png'),
    fullPage: true,
  })
  api.restoreTasks()
  await retry.click()
  await expect(
    page.getByRole('button', { name: /Keyboard task/ }),
  ).toBeVisible()
  await expect(retry).toHaveCount(0)
})

test('sessions and messages expose failures and retry without looking empty', async ({
  page,
}, info) => {
  const api = await fixtures(page)
  api.failSessions()
  api.failMessages()
  await page.goto('/dashboard/sessions')
  await page
    .getByLabel('Select workspace', { exact: true })
    .selectOption('workspace-fixture')
  const retry = page.getByRole('button', { name: 'Retry sessions' })
  await expect(retry).toBeVisible()
  await expect(
    page.getByText('No sessions found', { exact: true }),
  ).toHaveCount(0)
  await page.screenshot({
    path: info.outputPath('sessions-unavailable.png'),
    fullPage: true,
  })
  api.restoreSessions()
  await retry.click()
  const session = page.getByRole('button', { name: /^Keyboard session/ })
  await session.focus()
  await page.keyboard.press('Enter')
  await expect(session).toHaveAttribute('aria-pressed', 'true')
  await expect(
    page.getByRole('button', { name: 'Retry messages' }),
  ).toBeVisible()
  api.restoreMessages()
  await page.getByRole('button', { name: 'Retry messages' }).click()
  await expect(
    page.getByText('No messages yet.', { exact: true }),
  ).toBeVisible()
})

test('task creation dialog validates input and restores keyboard focus', async ({
  page,
}, info) => {
  const api = await fixtures(page)
  await page.goto('/dashboard/tasks')
  const open = page.getByRole('button', { name: 'New Task', exact: true })
  await open.click()
  const dialog = page.getByRole('dialog', { name: 'Create New Task' })
  await expect(dialog).toBeVisible()
  const title = dialog.getByLabel('Title', { exact: true })
  await expect(title).toBeFocused()
  await title.fill('   ')
  await dialog
    .getByLabel('Description', { exact: true })
    .fill('Fixture description')
  await dialog
    .getByRole('button', { name: 'Dispatch Task', exact: true })
    .click()
  await expect(title).toHaveAttribute('aria-invalid', 'true')
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(api.writes).toHaveLength(0)
  await page.screenshot({
    path: info.outputPath('task-validation.png'),
    fullPage: true,
  })
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(open).toBeFocused()
})

test('tasks can be selected with the keyboard', async ({ page }) => {
  await fixtures(page)
  await page.goto('/dashboard/tasks')
  const task = page.getByRole('button', { name: /Keyboard task/ })
  await task.focus()
  await page.keyboard.press('Enter')
  await expect(task).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('#task-details')).toContainText('Keyboard task')
})

test('primary CTA contrast and mobile menu Escape', async ({ page }) => {
  await fixtures(page, 'anonymous')
  await page.goto('/#pricing')
  const button = page.getByRole('button', { name: /^Upgrade to Pro/ })
  await expect(button).toBeVisible()
  const contrast = await button.evaluate((element) => {
    const styles = getComputedStyle(element)
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const context = canvas.getContext('2d')!
    const luminance = (color: string) => {
      context.fillStyle = color
      context.fillRect(0, 0, 1, 1)
      const rgb = Array.from(context.getImageData(0, 0, 1, 1).data)
        .slice(0, 3)
        .map((value) => value / 255)
        .map((value) =>
          value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
        )
      return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
    }
    const values = [
      luminance(styles.color),
      luminance(styles.backgroundColor),
    ].sort((a, b) => a - b)
    return (values[1] + 0.05) / (values[0] + 0.05)
  })
  expect(contrast).toBeGreaterThanOrEqual(4.5)
  await page.setViewportSize({ width: 390, height: 844 })
  const menu = page.getByRole('button', { name: 'Toggle menu' })
  await menu.click()
  await page.keyboard.press('Escape')
  await expect(menu).toHaveAttribute('aria-expanded', 'false')
  await expect(menu).toBeFocused()
})

test('model picker supports keyboard selection without trapping Tab', async ({
  page,
}, info) => {
  const api = await fixtures(page)
  await page.goto('/dashboard/workers')
  await page.getByRole('button', { name: 'Chat via SSE', exact: true }).click()
  const model = page.getByRole('combobox', { name: 'Model', exact: true })
  await model.fill('alpha')
  await expect(page.getByRole('option', { name: /alpha/i })).toBeVisible()
  await model.press('ArrowDown')
  await expect(model).toHaveAttribute('aria-activedescendant', /.+/)
  await page.screenshot({
    path: info.outputPath('model-picker.png'),
    fullPage: true,
  })
  await model.press('Enter')
  await expect(model).toHaveValue('openai:alpha')
  await expect(model).toHaveAttribute('aria-expanded', 'false')
  await model.fill('beta')
  await model.press('ArrowDown')
  await model.press('Tab')
  await expect(model).not.toBeFocused()
  await page.keyboard.press('Escape')
  await expect(model).toBeFocused()
  await expect(model).toHaveValue('openai:alpha')
  expect(api.writes).toHaveLength(0)
})

test('homepage fits mobile, tablet, and desktop widths', async ({
  page,
}, info) => {
  await fixtures(page, 'anonymous')
  await page.goto('/')
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(width)
    await page.screenshot({
      path: info.outputPath(`homepage-${width}.png`),
      fullPage: true,
    })
  }
})
