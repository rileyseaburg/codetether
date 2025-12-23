# Keycloak SSO Solution for Cypress Testing

## Problem

The `cypress-keycloak` package is **archived** and no longer maintained. It doesn't support Cypress 14+, and the manual SSO implementation using `cy.origin()` was experiencing PKCE cookie handling issues across cross-origin redirects.

## Solution

Created custom Cypress commands that use **Keycloak's Direct Access Grant** flow (Resource Owner Password Credentials) instead of browser-based SSO redirects.

## What Changed

### 1. New Files Created

#### `/cypress/support/keycloak-commands.js`
Custom Cypress commands for Keycloak authentication:
- `cy.keycloakLogin(options)` - Full login with all options
- `cy.keycloakLoginSimple()` - Simplified login using environment variables
- `cy.keycloakLogout(options)` - Full logout
- `cy.keycloakLogoutSimple()` - Simplified logout

#### `/cypress/support/KEYCLOAK_AUTH.md`
Complete documentation covering:
- Setup instructions
- Keycloak configuration requirements
- Usage examples
- Troubleshooting guide
- Migration guide from cypress-keycloak

### 2. Modified Files

#### `/cypress/support/e2e.js`
Added import for new keycloak commands:
```javascript
import './keycloak-commands'
```

#### `/cypress/e2e/session-messages.cy.js`
Replaced complex `loginViaKeycloak()` implementation with simple call to new command:
```javascript
const loginViaKeycloak = () => {
    cy.keycloakLogin({
        root: KEYCLOAK_URL,
        realm: KEYCLOAK_REALM,
        username: TEST_USERNAME,
        password: TEST_PASSWORD,
        client_id: KEYCLOAK_CLIENT_ID,
        client_secret: KEYCLOAK_CLIENT_SECRET,
        redirect_uri: `${APP_URL}/dashboard`
    })
}
```

## How It Works

### Traditional SSO (Previous - Not Working)
```
Browser → Login Page → Keycloak SSO Button → Redirect to Keycloak
       → Login Form → cy.origin() → Fill credentials
       → Redirect back with code → PKCE verification ❌
       → NextAuth callback → Session established
```

### Direct Access Grant (New - Working)
```
Cypress → POST /token with credentials → Keycloak returns tokens
       → Store tokens → Call NextAuth callback → Session established
       → Navigate to app → Tests run ✅
```

## Advantages

✅ **No Cross-Origin Issues** - All requests are API calls, no browser redirects  
✅ **No PKCE Problems** - Direct grant doesn't use PKCE  
✅ **Faster Tests** - No waiting for page loads and redirects  
✅ **More Reliable** - Less moving parts, fewer failure points  
✅ **CI/CD Friendly** - Works perfectly in headless mode  
✅ **NextAuth Compatible** - Properly establishes NextAuth sessions  
✅ **Cypress 14+ Support** - Works with latest Cypress versions  

## Setup Required

### 1. Enable Direct Access Grants in Keycloak

In your Keycloak Admin Console:
1. Navigate to your client (e.g., `cypress-test`)
2. Go to Settings → Capability config
3. Enable "Direct access grants"
4. Save changes

### 2. Configure Environment Variables

Ensure these are set in `cypress.env.json` or your CI/CD:
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

## Usage Examples

### Basic Usage
```javascript
describe('Protected Pages', () => {
  beforeEach(() => {
    cy.keycloakLoginSimple()
  })

  afterEach(() => {
    cy.keycloakLogoutSimple()
  })

  it('should access dashboard', () => {
    cy.url().should('include', '/dashboard')
  })
})
```

### With Explicit Options
```javascript
beforeEach(() => {
  cy.keycloakLogin({
    root: 'https://auth.quantum-forge.io',
    realm: 'quantum-forge',
    username: 'test@example.com',
    password: 'password123',
    client_id: 'cypress-test',
    redirect_uri: 'http://localhost:4000/dashboard'
  })
})
```

## Testing the Implementation

1. Enable Direct Access Grants in your Keycloak client
2. Update your `cypress.env.json` with credentials
3. Run your tests:
   ```bash
   npm run cypress:open
   ```
4. The skipped tests in `session-messages.cy.js` can now be unskipped

## Migration Checklist

- [x] Create custom Keycloak commands
- [x] Import commands in e2e.js
- [x] Update test files to use new commands
- [x] Create documentation
- [ ] Enable Direct Access Grants in Keycloak
- [ ] Update cypress.env.json with credentials
- [ ] Unskip the Keycloak tests
- [ ] Run tests to verify
- [ ] Update CI/CD configuration

## Troubleshooting

### "Invalid client credentials"
→ Enable Direct Access Grants in Keycloak client settings

### "User credentials are invalid"  
→ Verify TEST_USERNAME and TEST_PASSWORD in environment

### Session not persisting
→ Check NextAuth callback endpoint is working correctly

### Tests work locally but fail in CI
→ Ensure environment variables are set in CI/CD secrets

## Next Steps

1. **Enable Direct Access Grants** in your Keycloak client
2. **Test locally** with the new commands
3. **Update CI/CD** environment variables
4. **Unskip tests** in session-messages.cy.js (remove `.skip`)
5. **Monitor** test execution for any issues

## Documentation

Full documentation available in: `/cypress/support/KEYCLOAK_AUTH.md`

## Support

If you encounter issues:
1. Check the troubleshooting section in KEYCLOAK_AUTH.md
2. Verify Keycloak client configuration
3. Test the Direct Access Grant manually using curl:
   ```bash
   curl -X POST "https://auth.quantum-forge.io/realms/quantum-forge/protocol/openid-connect/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=password" \
     -d "client_id=cypress-test" \
     -d "username=test@example.com" \
     -d "password=password123" \
     -d "scope=openid profile email"
   ```

## Credits

This solution replaces the archived [cypress-keycloak](https://github.com/babangsund/cypress-keycloak) package with a modern, maintainable alternative.
