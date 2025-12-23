/**
 * Custom Cypress commands for Keycloak authentication
 * Compatible with Cypress 14+ and NextAuth v5
 */

/**
 * Login to Keycloak using the full browser-based OAuth flow
 * Properly handles NextAuth CSRF and cross-origin Keycloak authentication
 */
Cypress.Commands.add('keycloakLogin', ({
    root,
    realm,
    username,
    password,
    client_id,
    client_secret,
    redirect_uri,
    scope = 'openid profile email'
}) => {
    cy.log('Authenticating with Keycloak via OAuth flow...')

    const appUrl = new URL(redirect_uri).origin
    const apiUrl = Cypress.env('API_URL') || 'http://localhost:8000'
    // Clear any existing sessions first
    cy.clearCookies()
    cy.clearLocalStorage()

    // Step 1: Get CSRF token from NextAuth
    cy.request({
        url: `${apiUrl}/api/auth/csrf`,
        method: 'GET'
    }).then((csrfResponse) => {
        const csrfToken = csrfResponse.body.csrfToken
        cy.log(`Got CSRF token: ${csrfToken.substring(0, 10)}...`)

        // Step 2: Initiate OAuth flow by POSTing to signin endpoint
        cy.request({
            url: `${appUrl}/api/auth/signin/keycloak`,
            method: 'POST',
            form: true,
            body: {
                csrfToken: csrfToken,
                callbackUrl: redirect_uri
            },
            followRedirect: false
        }).then((signinResponse) => {
            const keycloakAuthUrl = signinResponse.headers.location || signinResponse.redirectedToUrl
            cy.log(`Keycloak auth URL obtained`)

            if (!keycloakAuthUrl) {
                throw new Error('No redirect URL received from signin endpoint')
            }

            // Step 3: Visit Keycloak auth URL
            cy.visit(keycloakAuthUrl)

            // Step 4: Handle Keycloak login
            cy.get('#username, input[name="username"]', { timeout: 10000 })
                .should('be.visible')
                .clear()
                .type(username)

            cy.get('#password, input[name="password"]')
                .should('be.visible')
                .clear()
                .type(password)

            cy.get('#kc-login, button[type="submit"], input[type="submit"]').click()

            // Step 5: Wait for OAuth callback to complete and redirect
            // NextAuth will set session cookie during the callback
            cy.url({ timeout: 30000 }).should('satisfy', (url) => {
                // Should eventually land on the app (either dashboard or login if failed)
                return url.includes('codetether.run') && !url.includes('auth.quantum-forge.io')
            })

            // Step 6: Check if we're on the dashboard (success) or login (failure)
            cy.url().then((currentUrl) => {
                if (currentUrl.includes('/login')) {
                    // Auth failed - check why
                    cy.log('WARNING: Still on login page after OAuth flow')

                    // Try to debug by checking session
                    cy.request({
                        url: `${appUrl}/api/auth/session`,
                        failOnStatusCode: false
                    }).then((sessionResponse) => {
                        cy.log(`Session response: ${JSON.stringify(sessionResponse.body)}`)
                    })
                } else {
                    cy.log('Successfully authenticated and on dashboard')

                    // Verify we have a valid session
                    cy.request({
                        url: `${appUrl}/api/auth/session`,
                        failOnStatusCode: false
                    }).then((sessionResponse) => {
                        if (sessionResponse.body?.user) {
                            cy.log(`Logged in as: ${sessionResponse.body.user.name || sessionResponse.body.user.email}`)
                        }
                    })
                }
            })
        })
    })
})

/**
 * Logout from Keycloak and NextAuth
 */
Cypress.Commands.add('keycloakLogout', ({
    root,
    realm,
    post_logout_redirect_uri,
    id_token_hint
}) => {
    cy.log('Logging out...')

    const appUrl = post_logout_redirect_uri ? new URL(post_logout_redirect_uri).origin : ''

    if (appUrl) {
        cy.request({
            url: `${appUrl}/api/auth/csrf`,
            method: 'GET'
        }).then((csrfResponse) => {
            cy.request({
                url: `${appUrl}/api/auth/signout`,
                method: 'POST',
                form: true,
                body: {
                    csrfToken: csrfResponse.body.csrfToken
                },
                failOnStatusCode: false
            })
        })
    }

    const params = new URLSearchParams()
    if (post_logout_redirect_uri) {
        params.append('post_logout_redirect_uri', post_logout_redirect_uri)
    }
    if (id_token_hint) {
        params.append('id_token_hint', id_token_hint)
    }

    cy.request({
        method: 'GET',
        url: `${root}/realms/${realm}/protocol/openid-connect/logout?${params.toString()}`,
        followRedirect: true,
        failOnStatusCode: false
    }).then(() => {
        cy.log('Logged out successfully')
        cy.clearCookies()
        cy.clearLocalStorage()
        cy.window().then((win) => {
            win.sessionStorage.clear()
        })
    })
})

/**
 * Simplified login using environment variables
 */
Cypress.Commands.add('keycloakLoginSimple', () => {
    const username = Cypress.env('TEST_USERNAME')
    const password = Cypress.env('TEST_PASSWORD')

    if (!username || !password) {
        throw new Error('TEST_USERNAME and TEST_PASSWORD must be set in cypress.env.json or environment variables')
    }

    const config = {
        root: Cypress.env('KEYCLOAK_URL'),
        realm: Cypress.env('KEYCLOAK_REALM'),
        username: username,
        password: password,
        client_id: Cypress.env('KEYCLOAK_CLIENT_ID'),
        client_secret: Cypress.env('KEYCLOAK_CLIENT_SECRET'),
        redirect_uri: Cypress.env('APP_URL') + '/dashboard'
    }

    return cy.keycloakLogin(config)
})

/**
 * Simplified logout using environment variables
 */
Cypress.Commands.add('keycloakLogoutSimple', () => {
    const config = {
        root: Cypress.env('KEYCLOAK_URL'),
        realm: Cypress.env('KEYCLOAK_REALM'),
        post_logout_redirect_uri: Cypress.env('APP_URL')
    }

    return cy.keycloakLogout(config)
})

/**
 * Login via Keycloak using the programmatic approach from the blog post
 * This is often more reliable in CI than UI-based login
 */
Cypress.Commands.add('kcLogin', (username, password) => {
    const kcRoot = Cypress.env('KEYCLOAK_URL') || 'https://auth.quantum-forge.io'
    const kcRealm = Cypress.env('KEYCLOAK_REALM') || 'quantum-forge'
    const kcClient = Cypress.env('KEYCLOAK_CLIENT_ID') || 'cypress-test'
    const kcRedirectUri = 'http://localhost:3000/'

    // Helper to create UUID (from KC JS client)
    const createUUID = () => {
        var s = [];
        var hexDigits = '0123456789abcdef';
        for (var i = 0; i < 36; i++) {
            s[i] = hexDigits.substr(Math.floor(Math.random() * 0x10), 1);
        }
        s[14] = '4';
        s[19] = hexDigits.substr((s[19] & 0x3) | 0x8, 1);
        s[8] = s[13] = s[18] = s[23] = '-';
        var uuid = s.join('');
        return uuid;
    }

    const loginPageRequest = {
        url: `${kcRoot}/realms/${kcRealm}/protocol/openid-connect/auth`,
        qs: {
            client_id: kcClient,
            redirect_uri: kcRedirectUri,
            state: createUUID(),
            nonce: createUUID(),
            response_mode: 'fragment',
            response_type: 'code',
            mini
        }
    };

    // Open the KC login page, fill in the form with username and password and submit.
    return cy.request(loginPageRequest)
        .then((response) => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(response.body, 'text/html');
            const loginForm = doc.getElementsByTagName('form');

            if (loginForm.length === 0) {
                cy.log('Already logged in or no login form found');
                return;
            }

            const formData = {};
            const inputs = doc.getElementsByTagName('input');
            for (let i = 0; i < inputs.length; i++) {
                const input = inputs[i];
                if (input.name) {
                    formData[input.name] = input.value || '';
                }
            }

            formData['username'] = username;
            formData['password'] = password;

            cy.log('Submitting login form to: ' + loginForm[0].action);

            return cy.request({
                form: true,
                method: 'POST',
                url: loginForm[0].action,
                followRedirect: false, // Don't follow redirects, just get the cookies
                body: formData,
                timeout: 30000
            }).then((postResponse) => {
                cy.log('Login POST status: ' + postResponse.status);
                if (postResponse.status === 302) {
                    cy.log('Redirecting to: ' + postResponse.headers.location);
                }
            });
        });
});

/**
 * Logout from Keycloak using the programmatic approach
 */
Cypress.Commands.add('kcLogout', () => {
    const kcRoot = Cypress.env('KEYCLOAK_URL') || 'https://auth.quantum-forge.io'
    const kcRealm = Cypress.env('KEYCLOAK_REALM') || 'quantum-forge'
    const kcRedirectUri = 'http://localhost:3000/'

    return cy.request({
        url: `${kcRoot}/realms/${kcRealm}/protocol/openid-connect/logout`,
        qs: {
            redirect_uri: kcRedirectUri
        }
    });
});
