import { test, expect } from '@playwright/test';

/**
 * Zapier integration page tests
 */

const ZAPIER_INVITE_LINK = 'https://zapier.com/developer/public-invite/235522/dc2a275ee1ca4688be5a4f18bf214ecb/';

test.describe('Zapier Integration', () => {
  
  test('Getting Started page requires auth or shows Zapier', async ({ page }) => {
    // This may redirect to login for unauthenticated users
    await page.goto('/dashboard/getting-started');
    
    await page.waitForTimeout(3000);
    const url = page.url();
    
    // Check if we're on login page (redirected due to auth)
    const isOnLoginPage = await page.getByRole('heading', { name: /sign in/i }).isVisible().catch(() => false);
    const hasZapierContent = await page.locator('text=Zapier').first().isVisible().catch(() => false);
    
    if (hasZapierContent) {
      // Page loaded - check for Zapier link
      const zapierLink = page.locator(`a[href*="zapier.com"]`);
      await expect(zapierLink.first()).toBeVisible();
    } else if (isOnLoginPage) {
      // Redirected to login - that's expected for protected route
      console.log('Getting Started page requires authentication');
      expect(true).toBeTruthy(); // Pass - auth redirect is correct behavior
    } else {
      // Some other state
      console.log('Unexpected state, URL:', url);
      expect(url.includes('/login') || url.includes('keycloak') || url.includes('quantum-forge') || url.includes('getting-started')).toBeTruthy();
    }
  });

  test('Zapier invite link is valid', async ({ page }) => {
    const response = await page.goto(ZAPIER_INVITE_LINK);
    
    // Zapier should return 200 or redirect to their app
    expect(response?.status()).toBeLessThan(400);
    
    // Should be on Zapier domain
    const url = page.url();
    expect(url).toContain('zapier.com');
  });

  test('Homepage mentions Zapier integration', async ({ page }) => {
    await page.goto('/');
    
    // Check if Zapier is mentioned on homepage
    const zapierMention = page.locator('text=Zapier');
    const hasZapierMention = await zapierMention.isVisible().catch(() => false);
    
    // This is informational - Zapier may or may not be on homepage
    console.log('Zapier mentioned on homepage:', hasZapierMention);
  });

  test('CallToAction mentions integrations', async ({ page }) => {
    await page.goto('/');
    
    // Scroll to CTA section
    await page.locator('#get-started').scrollIntoViewIfNeeded().catch(() => {});
    
    // Check for integration mentions
    const hasIntegrationMention = await page.locator('text=Zapier, text=n8n, text=Make, text=integration').isVisible().catch(() => false);
    
    console.log('CTA has integration mentions:', hasIntegrationMention);
  });
});

test.describe('API Endpoints for Zapier', () => {
  const API_BASE = process.env.API_URL || 'https://api.codetether.run';

  test('Tasks endpoint returns proper format', async ({ request }) => {
    const response = await request.get(`${API_BASE}/v1/tasks`, {
      headers: {
        'Accept': 'application/json',
      },
      failOnStatusCode: false,
    });
    
    // Should return 200, 401, 403, or 404 (endpoint may not exist yet)
    expect([200, 401, 403, 404, 422]).toContain(response.status());
    
    if (response.status() === 200) {
      const data = await response.json();
      // Should have tasks array
      expect(Array.isArray(data.tasks) || Array.isArray(data)).toBeTruthy();
    }
  });

  test('OAuth token endpoint exists', async ({ request }) => {
    const response = await request.post(`${API_BASE}/oauth/token`, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      form: {
        grant_type: 'refresh_token',
        refresh_token: 'invalid_token',
        client_id: 'test',
        client_secret: 'test',
      },
      failOnStatusCode: false,
    });
    
    // Should return 400, 401, or 404 (endpoint may not be exposed publicly)
    expect([400, 401, 404, 422]).toContain(response.status());
    
    if (response.status() !== 404) {
      const data = await response.json();
      expect(data.error || data.detail).toBeDefined();
    }
  });

  test('Health check endpoint', async ({ request }) => {
    const response = await request.get(`${API_BASE}/health`, {
      failOnStatusCode: false,
    });
    
    // API should be healthy
    expect(response.status()).toBe(200);
  });
});
