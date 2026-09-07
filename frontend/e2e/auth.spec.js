import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses
    await page.route('**/api/csrf-token', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ token: 'mock-csrf-token' }),
      });
    });
  });

  test('complete signup to dashboard flow', async ({ page }) => {
    // Mock signup API
    await page.route('**/api/auth/signup', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { id: '1', name: 'John Doe', email: 'john@example.com' },
        }),
      });
    });

    // Navigate to signup page
    await page.goto('/signup');

    // Fill out signup form
    await page.fill('input[placeholder="Full Name"]', 'John Doe');
    await page.fill('input[placeholder="Work Email"]', 'john@example.com');
    await page.fill('input[placeholder="Password"]', 'SecurePass123');
    await page.check('input[type="checkbox"]#terms');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('**/dashboard');
    await expect(page.locator('h1')).toContainText('Welcome, John Doe!');
  });

  test('complete login to dashboard flow', async ({ page }) => {
    // Mock login API
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { id: '1', name: 'John Doe', email: 'john@example.com' },
        }),
      });
    });

    // Navigate to login page
    await page.goto('/login');

    // Fill out login form
    await page.fill('input[placeholder="Work Email"]', 'john@example.com');
    await page.fill('input[placeholder="Password"]', 'SecurePass123');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('**/dashboard');
    await expect(page.locator('h1')).toContainText('Welcome, John Doe!');
  });

  test('shows validation errors for invalid email', async ({ page }) => {
    await page.goto('/login');

    await page.fill('input[placeholder="Work Email"]', 'invalid-email');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=Invalid email address')).toBeVisible();
  });

  test('logout redirects to login page', async ({ page }) => {
    // Mock getMe API
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { id: '1', name: 'John Doe', email: 'john@example.com' },
        }),
      });
    });

    // Mock logout API
    await page.route('**/api/auth/logout', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Logged out successfully' }),
      });
    });

    await page.goto('/dashboard');

    // Click logout button
    await page.click('button:has-text("Logout")');

    // Verify redirect to login
    await page.waitForURL('**/login');
  });

  test('remember me checkbox works', async ({ page }) => {
    await page.goto('/login');

    const rememberMeCheckbox = page.locator('input#remember');
    await expect(rememberMeCheckbox).not.toBeChecked();

    await rememberMeCheckbox.check();
    await expect(rememberMeCheckbox).toBeChecked();
  });

  test('password visibility toggle works', async ({ page }) => {
    await page.goto('/login');

    const passwordInput = page.locator('input[placeholder="Password"]');
    const toggleButton = page.locator('button[aria-label*="password"]');

    // Initially password should be hidden
    await expect(passwordInput).toHaveAttribute('type', 'password');

    // Click toggle to show password
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'text');

    // Click toggle to hide password again
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('protected route redirects when not authenticated', async ({ page }) => {
    // Mock getMe to return 401
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Unauthorized' }),
      });
    });

    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('**/login');
  });
});