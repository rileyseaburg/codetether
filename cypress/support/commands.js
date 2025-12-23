// ***********************************************
// Custom Cypress Commands for A2A Server Testing
// ***********************************************

/**
 * Login via Keycloak OIDC
 * Handles the full OAuth flow including redirect to Keycloak and back
 */
Cypress.Commands.add('loginViaKeycloak', (username, password, options = {}) => {
    const keycloakUrl = options.keycloakUrl || Cypress.env('KEYCLOAK_URL') || 'https://auth.quantum-forge.io'
    const appUrl = options.appUrl || Cypress.env('APP_URL') || 'https://codetether.run'

    // Visit the login page
    cy.visit(`${appUrl}/login`)

    // Click the Keycloak SSO button
    cy.contains('Continue with Quantum Forge SSO').click()

    // Handle Keycloak login form
    cy.origin(keycloakUrl, { args: { username, password } }, ({ username, password }) => {
        cy.get('#username', { timeout: 10000 }).should('be.visible')
        cy.get('#username').type(username)
        cy.get('#password').type(password)
        cy.get('#kc-login').click()
    })

    // Wait for redirect back to app
    cy.url({ timeout: 15000 }).should('include', '/dashboard')
})

/**
 * Login using stored session/token (faster for repeated tests)
 */
Cypress.Commands.add('loginWithToken', (token, options = {}) => {
    const appUrl = options.appUrl || Cypress.env('APP_URL') || 'https://codetether.run'

    cy.visit(appUrl)
    cy.window().then((win) => {
        win.localStorage.setItem('a2a_token', token)
    })
    cy.visit(`${appUrl}/dashboard/sessions`)
})

/**
 * Select a codebase in the sessions dashboard
 */
Cypress.Commands.add('selectCodebase', (codebaseId) => {
    cy.get('select').first().select(codebaseId)
    cy.wait(1000) // Wait for sessions to load
})

/**
 * Select a session by clicking on it
 */
Cypress.Commands.add('selectSession', (sessionId) => {
    cy.get(`[data-session-id="${sessionId}"]`).click()
    cy.wait(1000) // Wait for messages to load
})

/**
 * Wait for session messages to load
 */
Cypress.Commands.add('waitForMessages', (timeout = 5000) => {
    cy.get('[role="log"], [aria-label*="Chat messages"]', { timeout }).should('exist')
})

/**
 * Assert that messages are displayed (or empty state)
 */
Cypress.Commands.add('assertMessagesOrEmpty', () => {
    cy.get('body').then(($body) => {
        const hasMessages = $body.find('[role="log"] li').length > 0
        const hasEmptyState = $body.text().includes('No messages yet')
        expect(hasMessages || hasEmptyState).to.be.true
    })
})