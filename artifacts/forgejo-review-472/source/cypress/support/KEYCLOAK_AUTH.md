# Keycloak Authentication in Cypress Tests

## Overview

This project uses custom Cypress commands for Keycloak authentication, replacing the archived `cypress-keycloak` package. The implementation is compatible with Cypress 14+ and NextAuth.js.

## Authentication Methods

### 1. Direct Access Grant (Resource Owner Password Credentials)

This is the **recommended approach** for E2E testing. It bypasses the UI flow and directly exchanges credentials for tokens.

**Advantages:**
- ✅ No cross-origin redirect issues
- ✅ No PKCE cookie handling problems
- ✅ Faster test execution
- ✅ More reliable in CI/CD environments
- ✅ Works with NextAuth.js

**Requirements:**
- Direct Access Grants must be enabled in your Keycloak client settings
- Client must allow "Resource Owner Password Credentials" grant type

### 2. Browser UI Flow (cy.origin)

The traditional approach using Cypress's `cy.origin()` command.

**Disadvantages:**
- ❌ PKCE cookie handling issues across cross-origin redirects
- ❌ More complex and fragile
- ❌ Slower test execution
- ❌ Unreliable in headless mode

## Setup

### 1. Enable Direct Access Grants in Keycloak

1. Go to Keycloak Admin Console
2. Navigate to your client (e.g., `cypress-test`)
3. Under "Settings" → "Capability config"
4. Enable "Direct access grants"
5. Save

### 2. Configure Environment Variables

Create or update `cypress.env.json`:

```json
{
  "KEYCLOAK_URL": "https://auth.quantum-forge.io",
  "KEYCLOAK_REALM": "quantum-forge",
  "KEYCLOAK_CLIENT_ID": "cypress-test",
  "KEYCLOAK_CLIENT_SECRET": "your-secret-if-required",
  "TEST_USERNAME": "testuser@example.com",
  "TEST_PASSWORD": "testpassword",
  "APP_URL": "http://localhost:4000"
}
```

**Security Note:** Never commit `cypress.env.json` with real credentials. Use `.env` files or CI/CD secrets for sensitive values.

### 3. Import the Commands

The commands are automatically imported in `cypress/support/e2e.js`:

```javascript
import './keycloak-commands'
```

## Usage

### Basic Login

```javascript
describe('My Test Suite', () => {
  beforeEach(() => {
    cy.keycloakLogin({
      root: 'https://auth.quantum-forge.io',
      realm: 'quantum-forge',
      username: 'testuser@example.com',
      password: 'testpassword',
      client_id: 'cypress-test',
      client_secret: 'your-secret', // optional
      redirect_uri: 'http://localhost:4000/dashboard'
    })
  })

  it('should access protected page', () => {
    cy.url().should('include', '/dashboard')
  })
})
```

### Simplified Login (Using Environment Variables)

```javascript
describe('My Test Suite', () => {
  beforeEach(() => {
    cy.keycloakLoginSimple()
  })

  afterEach(() => {
    cy.keycloakLogoutSimple()
  })

  it('should access protected page', () => {
    cy.url().should('include', '/dashboard')
  })
})
```

### Manual Logout

```javascript
cy.keycloakLogout({
  root: 'https://auth.quantum-forge.io',
  realm: 'quantum-forge',
  post_logout_redirect_uri: 'http://localhost:4000'
})
```

## Available Commands

### `cy.keycloakLogin(options)`

Login to Keycloak using Direct Access Grant flow.

**Options:**
- `root` (string): Keycloak root URL
- `realm` (string): Keycloak realm
- `username` (string): Username
- `password` (string): Password
- `client_id` (string): Keycloak client ID
- `client_secret` (string, optional): Keycloak client secret
- `redirect_uri` (string): App redirect URI
- `scope` (string, optional): OAuth scopes (default: 'openid profile email')

**Returns:** Promise with tokens (`access_token`, `id_token`, `refresh_token`)

### `cy.keycloakLoginSimple()`

Simplified login using environment variables. Reads configuration from:
- `KEYCLOAK_URL`
- `KEYCLOAK_REALM`
- `TEST_USERNAME`
- `TEST_PASSWORD`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_CLIENT_SECRET`
- `APP_URL`

### `cy.keycloakLogout(options)`

Logout from Keycloak.

**Options:**
- `root` (string): Keycloak root URL
- `realm` (string): Keycloak realm
- `post_logout_redirect_uri` (string, optional): Where to redirect after logout
- `id_token_hint` (string, optional): ID token for logout hint

### `cy.keycloakLogoutSimple()`

Simplified logout using environment variables.

## Troubleshooting

### "Invalid client credentials" error

**Solution:** Ensure your client has Direct Access Grants enabled and the client secret (if required) is correct.

### "User credentials are invalid" error

**Solution:** Verify your username and password are correct.

### NextAuth session not established

**Solution:** 
1. Check that your NextAuth callback endpoint is configured correctly
2. Verify the callback URL matches your NextAuth configuration
3. Ensure cookies are being set properly (check `cy.getCookie()` in tests)

### Tests pass locally but fail in CI

**Solution:**
1. Ensure environment variables are set in CI
2. Check network connectivity to Keycloak from CI environment
3. Verify Keycloak client is configured to allow the CI IP/domain

## Comparison with cypress-keycloak

| Feature | cypress-keycloak | This Implementation |
|---------|------------------|---------------------|
| Cypress Version | ≤ 13 | 14+ |
| Maintenance | ❌ Archived | ✅ Active |
| PKCE Support | ✅ | ✅ (via Direct Grant) |
| NextAuth.js | ⚠️ Limited | ✅ Full Support |
| Cross-origin Issues | ❌ Common | ✅ Resolved |
| Test Speed | Slow | Fast |

## Migration from cypress-keycloak

If you were using `cypress-keycloak`:

**Before:**
```javascript
cy.login({
  root: 'https://keycloak.example.com',
  realm: 'myrealm',
  username: 'user',
  password: 'pass',
  client_id: 'myclient',
  redirect_uri: 'http://localhost:3000',
  code_challenge_method: 'S256'
})
```

**After:**
```javascript
cy.keycloakLogin({
  root: 'https://keycloak.example.com',
  realm: 'myrealm',
  username: 'user',
  password: 'pass',
  client_id: 'myclient',
  redirect_uri: 'http://localhost:3000'
})
```

## Additional Resources

- [Keycloak Resource Owner Password Credentials Grant](https://www.keycloak.org/docs/latest/securing_apps/#_resource_owner_password_credentials_flow)
- [Cypress Cross-Origin Testing](https://docs.cypress.io/guides/guides/web-security#Disabling-Web-Security)
- [NextAuth.js Callbacks](https://next-auth.js.org/configuration/callbacks)

## Contributing

If you encounter issues or have improvements, please open an issue or PR.
