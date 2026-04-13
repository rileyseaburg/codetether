import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://codetether.run';

test.describe('Tenant API proxy rewrite fix', () => {
    test('GET /api/tenant/v1/agent/workers should not return 404', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/tenant/v1/agent/workers`);
        // Should NOT be 404 - the rewrite should proxy it to the backend
        expect(response.status()).not.toBe(404);
        console.log(`/api/tenant/v1/agent/workers → ${response.status()}`);
    });

    test('GET /api/tenant/v1/worker/connected should not return 404', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/tenant/v1/worker/connected`);
        expect(response.status()).not.toBe(404);
        console.log(`/api/tenant/v1/worker/connected → ${response.status()}`);
    });

    test('GET /api/tenant/v1/agent/workspaces/list should not return 404', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/tenant/v1/agent/workspaces/list`);
        expect(response.status()).not.toBe(404);
        console.log(`/api/tenant/v1/agent/workspaces/list → ${response.status()}`);
    });
});

test.describe('Dashboard loads without errors', () => {
    test('dashboard page loads successfully', async ({ page }) => {
        const errors: string[] = [];
        page.on('console', (msg) => {
            if (msg.type() === 'error') {
                errors.push(msg.text());
            }
        });

        const response = await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 30000 });

        // Page should load
        expect(response).toBeTruthy();
        expect(response!.status()).toBe(200);

        // Check for the tenant API 404 errors specifically
        const tenant404s = errors.filter(e => e.includes('/api/tenant/') && e.includes('404'));
        if (tenant404s.length > 0) {
            console.error('Tenant API 404 errors found:', tenant404s);
        }
        expect(tenant404s).toHaveLength(0);
    });
});
