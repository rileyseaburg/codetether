// ***********************************************************
// This example support/e2e.js is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands'
import './keycloak-commands'

// Alternatively you can use CommonJS syntax:
// require('./commands')
// require('./keycloak-commands')

// Custom command to wait for A2A server to be ready
Cypress.Commands.add('waitForA2AServer', (url = 'http://localhost:8000') => {
  cy.request({
    url: `${url}/.well-known/agent-card.json`,
    timeout: 30000,
    retryOnStatusCodeFailure: true,
    retryOnNetworkFailure: true
  }).then((response) => {
    expect(response.status).to.eq(200)
    expect(response.body).to.have.property('name')
  })
})

// Custom command to send A2A JSON-RPC request
Cypress.Commands.add('sendA2ARequest', (method, params = {}, options = {}) => {
  const baseUrl = options.baseUrl || 'http://localhost:8000'
  const requestId = options.id || Date.now().toString()

  const request = {
    jsonrpc: '2.0',
    method: method,
    params: params,
    id: requestId
  }

  return cy.request({
    method: 'POST',
    url: baseUrl,
    headers: {
      'Content-Type': 'application/json',
      ...(options.auth ? { 'Authorization': `Bearer ${options.auth}` } : {})
    },
    body: request,
    failOnStatusCode: false
  })
})

// Custom command to create a test message
Cypress.Commands.add('createTestMessage', (content, type = 'text') => {
  return {
    parts: [
      {
        type: type,
        content: content
      }
    ]
  }
})
