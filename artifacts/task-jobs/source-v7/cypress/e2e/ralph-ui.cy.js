/**
 * Ralph UI Demo Test
 * 
 * Single E2E test that demos the full Ralph loop for video recording.
 * Run with: CYPRESS_BASE_URL=http://localhost:3001 npx cypress run --spec "cypress/e2e/ralph-ui.cy.js"
 */

describe('Ralph Dashboard Demo', () => {
  const TEST_USERNAME = Cypress.env('TEST_USERNAME')
  const TEST_PASSWORD = Cypress.env('TEST_PASSWORD')
  const KEYCLOAK_URL = Cypress.env('KEYCLOAK_URL')

  it('should demo the full Ralph autonomous loop', () => {
    // Login
    cy.visit('/login')
    cy.contains('Quantum Forge').click()
    cy.origin(KEYCLOAK_URL, { args: { TEST_USERNAME, TEST_PASSWORD } }, ({ TEST_USERNAME, TEST_PASSWORD }) => {
      cy.get('#username', { timeout: 10000 }).type(TEST_USERNAME)
      cy.get('#password').type(TEST_PASSWORD)
      cy.get('#kc-login').click()
    })
    cy.url({ timeout: 15000 }).should('not.include', 'auth.quantum-forge.io')

    // Navigate to Ralph
    cy.visit('/dashboard/ralph')
    cy.url().should('include', '/dashboard/ralph')
    
    // Verify header
    cy.get('[data-cy="ralph-header"]', { timeout: 10000 }).should('exist')
    cy.get('[data-cy="ralph-title"]').should('contain', 'Ralph Autonomous Loop')
    cy.screenshot('01-ralph-dashboard')

    // Verify Settings panel - Codebase selector
    cy.get('[data-cy="ralph-settings-panel"]').should('exist')
    cy.get('[data-cy="ralph-codebase-select"]').should('exist')
    cy.screenshot('02-settings-panel')
    
    // Verify Model selector and refresh
    cy.get('[data-cy="ralph-model-select"]').should('exist')
    cy.get('[data-cy="ralph-refresh-models-btn"]').click()
    cy.wait(1000)
    cy.screenshot('03-models-refreshed')

    // Verify PRD Configuration panel
    cy.get('[data-cy="ralph-prd-panel"]').should('exist')
    cy.get('[data-cy="ralph-prd-textarea"]').should('exist')
    cy.screenshot('04-prd-panel')

    // Load example PRD (skip AI builder for now due to postMessage error)
    cy.get('[data-cy="ralph-load-example-btn"]').click()
    cy.wait(500)
    cy.screenshot('05-example-prd-loaded')
    
    // Verify PRD textarea has content
    cy.get('[data-cy="ralph-prd-textarea"]').should('not.have.value', '')
    
    // Start button should now be enabled
    cy.get('[data-cy="ralph-start-btn"]').should('not.be.disabled')
    cy.screenshot('06-ready-to-start')

    // Verify log viewer
    cy.get('[data-cy="ralph-log-viewer"]').should('exist')
    
    // Verify runs panel
    cy.get('[data-cy="ralph-runs-panel"]').should('exist')
    cy.get('[data-cy="ralph-refresh-btn"]').click()
    cy.wait(500)
    cy.screenshot('07-runs-panel')
    
    // Click Start Ralph
    cy.get('[data-cy="ralph-start-btn"]').click()
    cy.screenshot('08-ralph-started')
    
    // Wait for run to begin (log viewer should show activity)
    cy.wait(3000)
    cy.screenshot('09-ralph-running')
  })
})
