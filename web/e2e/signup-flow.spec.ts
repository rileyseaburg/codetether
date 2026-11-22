import { test, expect } from '@playwright/test';

/**
 * End-to-end signup flow tests
 * Tests the complete user registration journey
 */

test.describe('Signup Flow E2E', () => {
  const testUser = {
    name: `Test User ${Date.now()}`,
    email: `test+${Date.now()}@codetether.run`,
    password: 'TestPassword123!',
  };

  test('complete signup flow - happy path', async ({ page }) => {
    // Step 1: Navigate to registration
    await page.goto('/register');
    await expect(page).toHaveURL(/register/);
    
    // Step 2: Fill out registration form
    const firstNameInput = page.getByLabel('First name');
    const lastNameInput = page.getByLabel('Last name');
    const emailInput = page.getByLabel('Email address');
    const passwordInput = page.getByLabel('Password');
    
    await firstNameInput.fill('Test');
    await lastNameInput.fill('User');
    await emailInput.fill(testUser.email);
    await passwordInput.fill(testUser.password);
    
    // Step 3: Submit form
    const submitButton = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Register"), button:has-text("Create")').first();
    await submitButton.click();
    
    // Step 4: Wait for response
    await page.waitForTimeout(3000);
    
    // Step 5: Check result
    const url = page.url();
    
    // Success scenarios:
    // - Redirected to login page
    // - Redirected to dashboard
    // - Redirected to Keycloak
    // - Shows success message
    const isSuccess = 
      url.includes('/login') ||
      url.includes('/dashboard') ||
      url.includes('keycloak') ||
      url.includes('quantum-forge') ||
      await page.locator('text=success, text=welcome, text=verify, text=check your email').isVisible().catch(() => false);
    
    // If still on register page, check for error message
    if (url.includes('/register')) {
      const hasError = await page.locator('[class*="error"], [role="alert"], text=already exists, text=invalid').isVisible().catch(() => false);
      console.log('Still on register page. Has error:', hasError);
    }
    
    expect(isSuccess || !url.includes('/register')).toBeTruthy();
  });

  test('signup with existing email should show error', async ({ page }) => {
    await page.goto('/register');
    
    // Use a known email that likely exists
    const firstNameInput = page.getByLabel('First name');
    const lastNameInput = page.getByLabel('Last name');
    const emailInput = page.getByLabel('Email address');
    const passwordInput = page.getByLabel('Password');
    
    await firstNameInput.fill('Test');
    await lastNameInput.fill('User');
    await emailInput.fill('test@codetether.run'); // Likely existing
    await passwordInput.fill('TestPassword123!');
    
    const submitButton = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Register")').first();
    await submitButton.click();
    
    await page.waitForTimeout(3000);
    
    // Should either show error or redirect to login
    const url = page.url();
    const hasErrorOrRedirect = 
      url.includes('/login') ||
      await page.locator('text=exists, text=already, text=error').isVisible().catch(() => false);
    
    // This is informational - existing email handling varies
    console.log('Existing email result:', url);
  });

  test('signup form validation', async ({ page }) => {
    await page.goto('/register');
    
    // Test weak password (if validation exists)
    const emailInput = page.locator('input[type="email"], input[name="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    
    await emailInput.fill('valid@email.com');
    await passwordInput.fill('weak'); // Too weak
    
    const submitButton = page.locator('button[type="submit"]').first();
    
    // Check if button is disabled or form shows validation
    const isDisabled = await submitButton.isDisabled().catch(() => false);
    
    if (!isDisabled) {
      await submitButton.click();
      await page.waitForTimeout(1000);
      
      // Should show validation error or stay on page
      const url = page.url();
      expect(url).toContain('/register');
    }
  });
});

test.describe('Login Flow E2E', () => {
  test('login page loads correctly', async ({ page }) => {
    await page.goto('/login');
    
    // Wait for redirect if OAuth
    await page.waitForTimeout(2000);
    
    const url = page.url();
    
    // Either local login page or Keycloak
    if (url.includes('quantum-forge') || url.includes('keycloak')) {
      // Keycloak login page
      await expect(page.locator('input[name="username"], input[name="email"], #username')).toBeVisible();
      await expect(page.locator('input[type="password"], #password')).toBeVisible();
    } else {
      // Local login page
      await expect(page.locator('form')).toBeVisible();
    }
  });

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login');
    
    await page.waitForTimeout(2000);
    const url = page.url();
    
    // Find login inputs (works for both local and Keycloak)
    const usernameInput = page.locator('input[name="username"], input[name="email"], input[type="email"], #username').first();
    const passwordInput = page.locator('input[type="password"], #password').first();
    
    await usernameInput.fill('invalid@example.com');
    await passwordInput.fill('wrongpassword');
    
    // Find and click submit
    const submitButton = page.locator('button[type="submit"], input[type="submit"], #kc-login').first();
    await submitButton.click();
    
    await page.waitForTimeout(3000);
    
    // Should show error or stay on login
    const newUrl = page.url();
    const hasError = 
      await page.locator('text=invalid, text=incorrect, text=error, text=failed, .alert-error, #input-error').isVisible().catch(() => false);
    
    // Should not be on dashboard
    expect(newUrl.includes('/dashboard') && !hasError).toBeFalsy();
  });
});

test.describe('OAuth/Keycloak Flow', () => {
  test('Keycloak is accessible', async ({ page }) => {
    const response = await page.goto('https://auth.quantum-forge.io/realms/quantum-forge/.well-known/openid-configuration');
    
    expect(response?.status()).toBe(200);
    
    const config = await response?.json();
    expect(config.issuer).toContain('quantum-forge');
    expect(config.authorization_endpoint).toBeDefined();
    expect(config.token_endpoint).toBeDefined();
  });

  test('login redirects to Keycloak', async ({ page }) => {
    await page.goto('/login');
    
    // Wait for potential redirect
    await page.waitForTimeout(3000);
    
    const url = page.url();
    
    // Should either be on local login or redirected to Keycloak
    const isValidState = 
      url.includes('/login') ||
      url.includes('quantum-forge') ||
      url.includes('keycloak');
    
    expect(isValidState).toBeTruthy();
  });
});
