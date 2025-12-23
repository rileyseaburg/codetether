const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || 'https://codetether.run',
    supportFile: 'cypress/support/e2e.js',
    specPattern: 'cypress/e2e/**/*.cy.{js,jsx,ts,tsx}',
    videosFolder: 'cypress/videos',
    screenshotsFolder: 'cypress/screenshots',
    video: true,
    videoCompression: 32,
    defaultCommandTimeout: 10000,
    requestTimeout: 15000,
    responseTimeout: 15000,
    // Enable experimental features for cross-origin testing (Keycloak)
    experimentalModifyObstructiveThirdPartyCode: true,
    chromeWebSecurity: false,
    // Default env values - these can be overridden by cypress.env.json
    env: {
      API_URL: 'https://api.codetether.run',
      APP_URL: 'https://codetether.run',
      KEYCLOAK_URL: 'https://auth.quantum-forge.io',
      KEYCLOAK_REALM: 'quantum-forge',
      KEYCLOAK_CLIENT_ID: 'cypress-test',
    },
    setupNodeEvents(on, config) {
      // Process.env overrides take precedence over cypress.env.json
      if (process.env.CYPRESS_API_URL) config.env.API_URL = process.env.CYPRESS_API_URL
      if (process.env.CYPRESS_APP_URL) config.env.APP_URL = process.env.CYPRESS_APP_URL
      if (process.env.CYPRESS_KEYCLOAK_URL) config.env.KEYCLOAK_URL = process.env.CYPRESS_KEYCLOAK_URL
      if (process.env.CYPRESS_KEYCLOAK_REALM) config.env.KEYCLOAK_REALM = process.env.CYPRESS_KEYCLOAK_REALM
      if (process.env.CYPRESS_KEYCLOAK_CLIENT_ID) config.env.KEYCLOAK_CLIENT_ID = process.env.CYPRESS_KEYCLOAK_CLIENT_ID
      if (process.env.CYPRESS_KEYCLOAK_CLIENT_SECRET) config.env.KEYCLOAK_CLIENT_SECRET = process.env.CYPRESS_KEYCLOAK_CLIENT_SECRET
      if (process.env.CYPRESS_TEST_USERNAME) config.env.TEST_USERNAME = process.env.CYPRESS_TEST_USERNAME
      if (process.env.CYPRESS_TEST_PASSWORD) config.env.TEST_PASSWORD = process.env.CYPRESS_TEST_PASSWORD
      if (process.env.CYPRESS_API_TOKEN) config.env.API_TOKEN = process.env.CYPRESS_API_TOKEN
      return config
    },
  },
  component: {
    devServer: {
      framework: 'create-react-app',
      bundler: 'webpack',
    },
  },
})