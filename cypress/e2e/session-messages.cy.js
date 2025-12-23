/**
 * Cypress E2E tests for React Components in the Chat UI
 *
 * Tests the React component interactions and user flows:
 * 1. Navigation and component mounting
 * 2. User interactions with SessionList component
 * 3. User interactions with ChatMessage component
 * 4. Component accessibility and responsive design
 * 5. Error handling in various scenarios
 */

describe('React Component E2E Tests', () => {
    const API_URL = Cypress.env('API_URL') || 'http://localhost:8000'
    const APP_URL = Cypress.env('APP_URL') || 'http://localhost:4000'
    const KEYCLOAK_URL = Cypress.env('KEYCLOAK_URL') || 'https://auth.quantum-forge.io'
    const KEYCLOAK_REALM = Cypress.env('KEYCLOAK_REALM') || 'quantum-forge'
    const KEYCLOAK_CLIENT_ID = Cypress.env('KEYCLOAK_CLIENT_ID') || 'cypress-test'
    const KEYCLOAK_CLIENT_SECRET = Cypress.env('KEYCLOAK_CLIENT_SECRET') || ''
    const TEST_USERNAME = Cypress.env('TEST_USERNAME')
    const TEST_PASSWORD = Cypress.env('TEST_PASSWORD')

    beforeEach(() => {
        // Note: Don't clear cookies here - let keycloakLogin handle it
        // Clearing cookies between tests would break session persistence
    })

    /**
     * Login via Keycloak using custom command
     * Uses Direct Access Grant flow for reliable token-based authentication
     */
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

    /**
     * Alternative: Simplified login using environment variables
     */
    const loginViaKeycloakSimple = () => {
        cy.keycloakLoginSimple()
    }

    // /**
    //  * Alternative: Login via API token if Keycloak is not available
    //  */
    // const loginViaApiToken = () => {
    //     const token = Cypress.env('API_TOKEN')
    //     if (!token) {
    //         throw new Error('API_TOKEN environment variable required for API token login')
    //     }

    //     cy.visit(APP_URL)
    //     cy.window().then((win) => {
    //         win.localStorage.setItem('a2a_token', token)
    //     })
    //     cy.visit(`${APP_URL}/dashboard/sessions`)
    // }

    it('should navigate to the sessions dashboard and verify components mount', () => {
        // Login first - this will land us on /dashboard
        loginViaKeycloakSimple()

        // Navigate to sessions page from dashboard
        cy.visit(Cypress.env('APP_URL') + '/dashboard/sessions')

        // Verify we're on the correct page (may redirect to login if session isn't valid)
        cy.url({ timeout: 15000 }).should('include', '/dashboard')

        // Check if we're authenticated or got redirected to login
        cy.url().then((url) => {
            if (url.includes('/login')) {
                // Session wasn't preserved - this is the bug we're debugging
                cy.log('ERROR: Session not preserved, redirected to login')
                throw new Error('Authentication session not preserved after OAuth callback')
            }
        })

        // Verify the main sessions component is mounted
        cy.get('[data-testid="sessions-page"]', { timeout: 10000 }).should('exist')

        // Verify key UI elements are present
        cy.get('h1').should('contain.text', 'Chat Sessions')
        cy.get('[data-testid="codebase-selector"]').should('be.visible')
        cy.get('[data-testid="sessions-container"]').should('exist')
    })

    // it('should allow user to select a codebase and load sessions', () => {
    //     // Login first
    //     loginViaKeycloakSimple()

    //     cy.visit('/dashboard/sessions')

    //     // Wait for page to load
    //     cy.get('[data-testid="sessions-page"]').should('exist')

    //     // Click on the codebase dropdown
    //     cy.get('[data-testid="codebase-selector"]').click()

    //     // Wait for options to load from API
    //     cy.get('[role="option"]').should('have.length.greaterThan', 0)

    //     // Select the first available codebase
    //     cy.get('[role="option"]').first().click()

    //     // Verify sessions start loading (loading state should appear)
    //     cy.get('[data-testid="sessions-loading"]').should('be.visible')

    //     // Wait for sessions to load
    //     cy.get('[data-testid="sessions-list"]').should('exist', { timeout: 10000 })

    //     // Verify session items are populated
    //     cy.get('[data-testid="session-item"]').should('have.length.greaterThan', 0)
    // })

    // it('should allow user to select a session and load messages', () => {
    //     // Login first
    //     loginViaKeycloakSimple()

    //     cy.visit('/dashboard/sessions')

    //     // Select a codebase first
    //     cy.get('[data-testid="codebase-selector"]').click()
    //     cy.get('[role="option"]').first().click()

    //     // Wait for sessions to load
    //     cy.get('[data-testid="sessions-list"]', { timeout: 10000 }).should('exist')

    //     // Click on the first session
    //     cy.get('[data-testid="session-item"]').first().click()

    //     // Verify messages start loading
    //     cy.get('[data-testid="messages-loading"]').should('be.visible')

    //     // Wait for messages to load
    //     cy.get('[data-testid="messages-container"]', { timeout: 10000 }).should('exist')

    //     // Verify messages are displayed
    //     cy.get('[data-testid="message-item"]').should('have.length.greaterThan', 0)

    //     // Verify different message types are properly rendered
    //     cy.get('[data-testid="user-message"]').should('exist')
    //     cy.get('[data-testid="assistant-message"]').should('exist')
    // })

    // // UI tests - require Keycloak OIDC flow with NextAuth
    // // Currently skipped due to PKCE cookie handling issues with Cypress cross-origin redirects
    // // The API tests above confirm the backend session/message loading works correctly
    // // To enable: fix PKCE cookie persistence across cross-origin Keycloak redirects

    // it.skip('should login via Keycloak and navigate to sessions', () => {
    //     if (!TEST_USERNAME || !TEST_PASSWORD) {
    //         cy.log('Skipping - no credentials provided')
    //         return
    //     }
    //     loginViaKeycloak()
    // })

    // it.skip('should select a codebase and load sessions in UI', () => {
    //     if (!TEST_USERNAME || !TEST_PASSWORD) {
    //         cy.log('Skipping - no credentials provided')
    //         return
    //     }
    //     loginViaKeycloak()

    //     // Wait for codebases dropdown to load
    //     cy.get('select', { timeout: 10000 }).first().should('be.visible')

    //     // Select a codebase
    //     cy.get('select').first().then(($select) => {
    //         const options = $select.find('option')
    //         cy.log(`Found ${options.length} codebase options`)
    //         if (options.length > 1) {
    //             cy.wrap($select).select(1)
    //         }
    //     })

    //     // Wait for sessions to load
    //     cy.wait(2000)

    //     // Verify sessions sidebar exists
    //     cy.get('[aria-label="Session list sidebar"]').should('exist')
    // })

    // it.skip('should select a session and display messages', () => {
    //     if (!TEST_USERNAME || !TEST_PASSWORD) {
    //         cy.log('Skipping - no credentials provided')
    //         return
    //     }
    //     loginViaKeycloak()

    //     // Select a codebase
    //     cy.get('select', { timeout: 10000 }).first().should('be.visible')
    //     cy.get('select').first().then(($select) => {
    //         if ($select.find('option').length > 1) {
    //             cy.wrap($select).select(1)
    //         }
    //     })

    //     // Wait for sessions to load
    //     cy.wait(3000)

    //     // Click on first session in the list
    //     cy.get('[aria-label="Session list sidebar"]').within(() => {
    //         cy.get('button, [role="button"]').first().click()
    //     })

    //     // Wait for messages to load
    //     cy.wait(3000)

    //     // Check for console debug logs
    //     cy.window().then((win) => {
    //         cy.log('Check browser console for [useSessions] and [useChatItems] logs')
    //     })

    //     // Verify chat area shows messages or empty state
    //     cy.get('[role="region"][aria-label*="Chat"]').should('exist')
    //     cy.get('body').then(($body) => {
    //         const hasMessages = $body.find('[role="log"] li').length > 0
    //         const hasEmptyState = $body.text().includes('No messages yet') || $body.text().includes('Select a session')
    //         cy.log(`Has messages: ${hasMessages}, Has empty state: ${hasEmptyState}`)
    //         expect(hasMessages || hasEmptyState).to.be.true
    //     })
    // })

    // it('should handle real-time UI updates when switching between sessions', () => {
    //     // Login first
    //     loginViaKeycloakSimple()

    //     cy.visit('/dashboard/sessions')

    //     // Select a codebase first
    //     cy.get('[data-testid="codebase-selector"]').click()
    //     cy.get('[role="option"]').first().click()

    //     // Wait for sessions to load
    //     cy.get('[data-testid="sessions-list"]', { timeout: 10000 }).should('exist')

    //     // Get the list of sessions to work with
    //     let sessionCount = 0
    //     cy.get('[data-testid="session-item"]').then(($items) => {
    //         sessionCount = $items.length
    //     })

    //     // Click on the first session
    //     cy.get('[data-testid="session-item"]').first().click()

    //     // Wait for messages to load and get the message count
    //     let firstSessionMessageCount = 0
    //     cy.get('[data-testid="message-item"]').then(($messages) => {
    //         firstSessionMessageCount = $messages.length
    //     })

    //     // Verify session details are displayed
    //     cy.get('[data-testid="session-details"]', { timeout: 5000 }).should('exist')

    //     // If there are multiple sessions, switch to another one
    //     cy.then(() => {
    //         if (sessionCount > 1) {
    //             // Click on a different session
    //             cy.get('[data-testid="session-item"]').eq(1).click()

    //             // Verify messages container updates
    //             cy.get('[data-testid="messages-loading"]').should('be.visible')
    //             cy.get('[data-testid="messages-container"]', { timeout: 10000 }).should('exist')

    //             // Verify the content has changed (different message count or no messages)
    //             cy.get('[data-testid="message-item"]').then(($messages) => {
    //                 const newMessageCount = $messages.length
    //                 // Should either have a different count or be empty
    //                 expect(newMessageCount).not.to.equal(firstSessionMessageCount)
    //             })
    //         }
    //     })
    // })

    // it('should properly render different message types in the chat UI', () => {
    //     // Login first
    //     loginViaKeycloakSimple()

    //     cy.visit('/dashboard/sessions')

    //     // Select a codebase first
    //     cy.get('[data-testid="codebase-selector"]').click()
    //     cy.get('[role="option"]').first().click()

    //     // Wait for sessions to load
    //     cy.get('[data-testid="sessions-list"]', { timeout: 10000 }).should('exist')

    //     // Select a session
    //     cy.get('[data-testid="session-item"]').first().click()

    //     // Wait for messages to load
    //     cy.get('[data-testid="messages-container"]', { timeout: 10000 }).should('exist')

    //     // Verify user messages are rendered correctly
    //     cy.get('[data-testid="user-message"]').each(($userMessage) => {
    //         cy.wrap($userMessage).should('have.attr', 'data-role', 'user')
    //         cy.wrap($userMessage).find('[data-testid="message-avatar"]').should('exist')
    //         cy.wrap($userMessage).find('[data-testid="message-content"]').should('exist')
    //         cy.wrap($userMessage).find('[data-testid="message-timestamp"]').should('exist')
    //     })

    //     // Verify assistant messages are rendered correctly
    //     cy.get('[data-testid="assistant-message"]').each(($assistantMessage) => {
    //         cy.wrap($assistantMessage).should('have.attr', 'data-role', 'assistant')
    //         cy.wrap($assistantMessage).find('[data-testid="message-avatar"]').should('exist')
    //         cy.wrap($assistantMessage).find('[data-testid="message-content"]').should('exist')
    //         // Assistant messages might have model information
    //         cy.wrap($assistantMessage).find('[data-testid="message-model"]').should('exist')
    //     })

    //     // Check for system messages if present
    //     cy.get('[data-testid="system-message"]').then(($sysMessages) => {
    //         if ($sysMessages.length > 0) {
    //             cy.get('[data-testid="system-message"]').should('have.attr', 'data-role', 'system')
    //             cy.get('[data-testid="system-message"]').find('[data-testid="message-content"]').should('exist')
    //         }
    //     })
    // })

    // Component-focused E2E tests - These test the React components directly
    describe('React Component Tests', () => {
        beforeEach(() => {
            // Set up API token authentication for component tests
            const token = Cypress.env('API_TOKEN')
            if (token) {
                cy.visit(APP_URL)
                cy.window().then((win) => {
                    win.localStorage.setItem('a2a_token', token)
                })
            }
        })

        it('should test SessionList component interactions', () => {
            // Login first
            loginViaKeycloakSimple()

            cy.visit(`${APP_URL}/dashboard/sessions`)

            // Test SessionList component structure
            cy.get('nav[aria-label="Chat sessions"]').should('exist')
            cy.get('#sessions-heading').should('contain.text', 'Sessions')

            // Test codebase select exists and is accessible
            cy.get('#codebase-select').should('exist')
            cy.get('[for="codebase-select"]').should('have.text', 'Select codebase')

            // Test empty state when no codebase selected
            cy.get('[role="status"]').should('contain.text', 'Select a codebase')

            // Get available codebases and test selection
            cy.request(`${API_URL}/v1/opencode/codebases`).then((response) => {
                const codebases = response.body

                // Test that codebases are populated in dropdown
                cy.get('#codebase-select').find('option').should('have.length.greaterThan', 1)

                if (codebases.length > 0) {
                    // Select first codebase
                    const firstCodebase = codebases[0]
                    cy.get('#codebase-select').select(firstCodebase.id)

                    // Wait for sessions to load
                    cy.wait(2000)

                    // Test that sessions are displayed
                    cy.get('[role="listbox"]').within(() => {
                        // Check for either sessions or "No sessions found"
                        cy.get('body').then(($body) => {
                            const hasSessions = $body.find('[role="option"]').length > 0
                            const hasEmptyState = $body.text().includes('No sessions found')

                            if (hasSessions) {
                                // Test session items are present and clickable
                                cy.get('[role="option"]').first().should('be.visible')
                                cy.get('[role="option"]').first().click()
                            }
                        })
                    })
                }
            })
        })

        it('should test ChatMessage component rendering', () => {
            // Load a session with messages
            cy.request(`${API_URL}/v1/opencode/codebases`).then((cbResponse) => {
                const codebase = cbResponse.body[0]

                cy.request(`${API_URL}/v1/opencode/codebases/${codebase.id}/sessions`).then((sessResponse) => {
                    const sessionsWithMessages = sessResponse.body.filter(s => s.hasMessages)

                    if (sessionsWithMessages.length > 0) {
                        const session = sessionsWithMessages[0]

                        // Navigate directly to session via URL
                        cy.visit(`${APP_URL}/dashboard/sessions?codebase=${codebase.id}&session=${session.id}`)

                        // Wait for messages to load
                        cy.wait(3000)

                        // Test ChatMessage component structure
                        cy.get('[role="region"][aria-label*="Chat"]').should('exist')

                        cy.request(`${API_URL}/v1/opencode/sessions/${session.id}/messages`).then((msgResponse) => {
                            const messages = msgResponse.body
                            if (messages.length > 0) {
                                // Test that messages are rendered
                                cy.get('[role="log"]').should('exist')

                                // Test user message structure
                                const userMessages = messages.filter(m => m.role === 'user')
                                if (userMessages.length > 0) {
                                    cy.get('article[aria-label*="You"]').first().within(() => {
                                        cy.get('div').should('have.class', 'max-w-[85%]')
                                        cy.get('div').should('have.class', 'text-right')
                                    })
                                }

                                // Test assistant message structure
                                const assistantMessages = messages.filter(m => m.role === 'assistant')
                                if (assistantMessages.length > 0) {
                                    cy.get('article[aria-label*="Assistant"]').first().within(() => {
                                        cy.get('div').should('have.class', 'max-w-[85%]')
                                        cy.get('div').should('have.class', 'text-left')
                                    })
                                }

                                // Test system message structure
                                const systemMessages = messages.filter(m => m.role === 'system')
                                if (systemMessages.length > 0) {
                                    cy.get('[role="status"][aria-label="System message"]').should('exist')
                                    cy.get('[role="status"]').within(() => {
                                        cy.get('div').should('have.class', 'bg-gray-200/70')
                                        cy.get('div').should('have.class', 'px-3')
                                        cy.get('div').should('have.class', 'py-1')
                                    })
                                }
                            }
                        })
                    }
                })
            })
        })

        it('should test component accessibility', () => {
            // Login first
            loginViaKeycloakSimple()

            cy.visit(`${APP_URL}/dashboard/sessions`)

            // Test ARIA labels and roles
            cy.get('nav[aria-label="Chat sessions"]').should('exist')
            cy.get('[role="listbox"]').should('exist')
            cy.get('[role="status"]').should('exist')

            // Test screen reader support
            cy.get('#sessions-heading').should('have.attr', 'id')
            cy.get('[role="listbox"]').should('have.attr', 'aria-labelledby', 'sessions-heading')

            // Test form labels
            cy.get('#codebase-select').should('have.attr', 'aria-describedby', 'codebase-hint')
            cy.get('#codebase-hint').should('exist')

            // Test keyboard navigation
            cy.get('#codebase-select').focus()
            cy.get('#codebase-select').should('be.focused')
            cy.get('#codebase-select').type('{downarrow}')
        })

        it('should test component responsive design', () => {
            // Login first
            loginViaKeycloakSimple()

            cy.visit(`${APP_URL}/dashboard/sessions`)

            // Test mobile viewport
            cy.viewport('iphone-x')
            cy.get('nav[aria-label="Chat sessions"]').should('be.visible')
            cy.get('#codebase-select').should('be.visible')

            // Test tablet viewport
            cy.viewport('ipad-2')
            cy.get('nav[aria-label="Chat sessions"]').should('be.visible')

            // Test desktop viewport
            cy.viewport(1280, 720)
            cy.get('nav[aria-label="Chat sessions"]').should('be.visible')

            // Test max height behavior on different viewports
            cy.get('[role="listbox"]').should('have.css', 'max-height')
        })

        it('should test component error states', () => {
            // Login first
            loginViaKeycloakSimple()

            // Test with invalid codebase ID
            cy.visit(`${APP_URL}/dashboard/sessions?codebase=invalid-id`)
            cy.wait(2000)

            // Should handle errors gracefully
            cy.get('nav[aria-label="Chat sessions"]').should('be.visible')

            // Test API error handling by intercepting requests
            cy.intercept('GET', '**/codebases/**', { forceNetworkError: true }).as('codebaseError')
            cy.visit(`${APP_URL}/dashboard/sessions`)
            cy.wait('@codebaseError')

            // Component should still render despite API errors
            cy.get('nav[aria-label="Chat sessions"]').should('exist')
            cy.get('#sessions-heading').should('exist')
        })
    })
})
