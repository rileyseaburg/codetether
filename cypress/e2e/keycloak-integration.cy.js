describe('Keycloak Integration Test', () => {
    const TEST_USERNAME = Cypress.env('TEST_USERNAME')
    const TEST_PASSWORD = Cypress.env('TEST_PASSWORD')
    const APP_URL = Cypress.env('APP_URL') || 'http://localhost:3000'

    it('should be logged in using kcLogin', () => {
        // Use the new kcLogin command
        cy.kcLogin(TEST_USERNAME, TEST_PASSWORD)

        // Verify session via API request (faster and more reliable for testing auth)
        cy.request({
            url: `${APP_URL}/api/auth/session`,
            failOnStatusCode: false
        }).then((response) => {
            cy.log('Session response: ' + JSON.stringify(response.body));
            expect(response.status).to.eq(200);
            if (response.body && response.body.user) {
                cy.log('Logged in as: ' + response.body.user.email);
            } else {
                throw new Error('Not logged in: ' + JSON.stringify(response.body));
            }
        });
    })
})
