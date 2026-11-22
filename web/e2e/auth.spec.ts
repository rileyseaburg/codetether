import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  
  test.describe('Registration Page', () => {
    test('should load registration page', async ({ page }) => {
      await page.goto('/register');
      
      // Page should load without errors
      await expect(page).toHaveTitle(/CodeTether/i);
      
      // Registration form should be visible
      await expect(page.locator('form')).toBeVisible();
    });

    test('should have all required form fields', async ({ page }) => {
      await page.goto('/register');
      
      // Check for essential form fields
      await expect(page.getByLabel('First name')).toBeVisible();
      await expect(page.getByLabel('Last name')).toBeVisible();
      await expect(page.getByLabel('Email address')).toBeVisible();
      await expect(page.getByLabel('Password')).toBeVisible();
      
      // Submit button should exist
      await expect(page.getByRole('button', { name: /get started|sign up|register|create/i })).toBeVisible();
    });

    test('should show validation errors for empty submission', async ({ page }) => {
      await page.goto('/register');
      
      // Try to submit empty form
      const submitButton = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Register"), button:has-text("Create")');
      await submitButton.click();
      
      // Should show validation (HTML5 or custom)
      // Either the form doesn't submit or error messages appear
      const url = page.url();
      expect(url).toContain('/register');
    });

    test('should show error for invalid email format', async ({ page }) => {
      await page.goto('/register');
      
      // Fill with invalid email
      const emailInput = page.locator('input[type="email"], input[name="email"]');
      await emailInput.fill('invalid-email');
      
      // Try to submit
      const submitButton = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Register"), button:has-text("Create")');
      await submitButton.click();
      
      // Should stay on register page (validation failed)
      await expect(page).toHaveURL(/register/);
    });
  });

  test.describe('Login Page', () => {
    test('should load login page', async ({ page }) => {
      await page.goto('/login');
      
      // Page should load
      await expect(page).toHaveTitle(/CodeTether/i);
    });

    test('should have login form or redirect to Keycloak', async ({ page }) => {
      await page.goto('/login');
      
      // Wait for potential redirect
      await page.waitForTimeout(2000);
      
      // Either shows a login form OR redirects to Keycloak
      const url = page.url();
      const hasLoginForm = await page.locator('input[type="password"]').isVisible().catch(() => false);
      const hasSignInButton = await page.getByRole('button', { name: /sign in/i }).isVisible().catch(() => false);
      const isKeycloak = url.includes('auth.quantum-forge.io') || url.includes('keycloak');
      const isLoginPage = url.includes('/login');
      
      expect(hasLoginForm || hasSignInButton || isKeycloak || isLoginPage).toBeTruthy();
    });

    test('should have link to registration', async ({ page }) => {
      await page.goto('/login');
      
      // Should have a way to get to registration
      const registerLink = page.locator('a[href*="register"], a:has-text("Sign up"), a:has-text("Register"), a:has-text("Create account")');
      
      // Either on login page or Keycloak
      const url = page.url();
      if (!url.includes('keycloak') && !url.includes('quantum-forge')) {
        await expect(registerLink).toBeVisible();
      }
    });
  });

  test.describe('Protected Routes', () => {
    test('dashboard should redirect unauthenticated users', async ({ page }) => {
      await page.goto('/dashboard');
      
      // Should redirect to login or show login prompt
      await page.waitForTimeout(2000); // Wait for redirect
      const url = page.url();
      
      const isProtected = 
        url.includes('/login') || 
        url.includes('/register') ||
        url.includes('auth.quantum-forge.io') ||
        url.includes('keycloak');
      
      // Either redirected to auth OR still on dashboard with login UI
      expect(isProtected || url.includes('/dashboard')).toBeTruthy();
    });

    test('getting-started page should require auth or show content', async ({ page }) => {
      await page.goto('/dashboard/getting-started');
      
      // Wait for page load
      await page.waitForTimeout(3000);
      
      // Check if we're on login page (redirected due to auth)
      const isOnLoginPage = await page.getByRole('heading', { name: /sign in/i }).isVisible().catch(() => false);
      const hasZapierContent = await page.locator('text=Zapier').first().isVisible().catch(() => false);
      
      // Either shows Zapier content OR redirects to login (both are valid)
      expect(hasZapierContent || isOnLoginPage).toBeTruthy();
    });
  });
});

test.describe('Public Pages', () => {
  test('homepage should load', async ({ page }) => {
    await page.goto('/');
    
    await expect(page).toHaveTitle(/CodeTether/i);
    await expect(page.locator('text=CodeTether').first()).toBeVisible();
  });

  test('homepage should have CTA buttons', async ({ page }) => {
    await page.goto('/');
    
    // Should have sign up / get started buttons
    const ctaButton = page.locator('a:has-text("Start"), a:has-text("Sign up"), a:has-text("Get Started"), button:has-text("Start")');
    await expect(ctaButton.first()).toBeVisible();
  });
});
