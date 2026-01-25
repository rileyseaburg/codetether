/**
 * Ralph Loop Demo Test
 * 
 * This test demonstrates the Ralph autonomous development loop in action.
 * The recorded video can be used for marketing materials.
 * 
 * Features demonstrated:
 * - PRD creation via AI chat
 * - Ralph loop execution
 * - Real-time task status updates
 * - Story completion tracking
 */

describe('Ralph Autonomous Loop Demo', () => {
  // Use production URLs by default for demo recording
  const API_URL = Cypress.env('API_URL') || 'https://api.codetether.run'
  const APP_URL = Cypress.env('APP_URL') || 'https://codetether.run'
  
  // Skip API tests if server unavailable
  let apiAvailable = false

  // Demo PRD for video recording
  const demoPRD = {
    project: 'Demo Feature',
    branchName: 'feature/demo-cypress-test',
    description: 'A simple demo feature to showcase Ralph autonomous development',
    userStories: [
      {
        id: 'US-001',
        title: 'Create greeting function',
        description: 'As a developer, I want a greeting function that returns a personalized message',
        acceptanceCriteria: [
          'Function accepts a name parameter',
          'Returns "Hello, {name}!" format',
          'Handles empty name gracefully'
        ],
        priority: 1
      },
      {
        id: 'US-002', 
        title: 'Add unit tests',
        description: 'As a developer, I want unit tests for the greeting function',
        acceptanceCriteria: [
          'Test with valid name',
          'Test with empty name',
          'All tests pass'
        ],
        priority: 2
      }
    ]
  }

  beforeEach(() => {
    // Clear any previous test data
    cy.clearLocalStorage()
  })

  before(() => {
    // Check API availability before tests
    cy.request({
      method: 'GET',
      url: `${API_URL}/health`,
      failOnStatusCode: false,
      timeout: 10000
    }).then((response) => {
      apiAvailable = response.status === 200
      cy.log(apiAvailable ? '✅ API is available' : '⚠️ API not available')
    })
  })

  it('should demonstrate Ralph loop via API', function() {
    if (!apiAvailable) {
      this.skip()
      return
    }
    
    // Step 1: Check API health
    cy.log('🔍 Checking API health...')
    cy.request({
      method: 'GET',
      url: `${API_URL}/health`,
      failOnStatusCode: false
    }).then((response) => {
      expect(response.status).to.eq(200)
      cy.log('✅ API is healthy')

      // Step 2: Create Ralph run
      cy.log('🚀 Creating Ralph run with demo PRD...')
      cy.request({
        method: 'POST',
        url: `${API_URL}/v1/ralph/runs`,
        headers: { 'Content-Type': 'application/json' },
        body: {
          prd: demoPRD,
          max_iterations: 5,
          run_mode: 'sequential'
        }
      }).then((createResponse) => {
        expect(createResponse.status).to.eq(200)
        const runId = createResponse.body.id
        cy.log(`✅ Ralph run created: ${runId}`)

        // Step 3: Poll for status updates
        cy.log('⏳ Monitoring Ralph progress...')
        pollRalphStatus(runId, 0)
      })
    })
  })

  it('should demonstrate Ralph via frontend UI', function() {
    // Visit the Ralph dashboard directly
    cy.visit('/dashboard/ralph', { failOnStatusCode: false })
    cy.wait(2000)

    // Check if we need to login
    cy.url().then((url) => {
      if (url.includes('/login') || url.includes('/auth')) {
        cy.log('⚠️ Login required - skipping UI demo')
        cy.screenshot('login-page')
        return
      }

      // Verify Ralph components loaded using data-cy attributes
      cy.log('📍 Verifying Ralph dashboard components...')
      
      // Check for Ralph header
      cy.get('[data-cy="ralph-header"]', { timeout: 5000 }).should('exist').then(() => {
        cy.log('✅ Ralph header found')
      })

      // Check for Ralph title
      cy.get('[data-cy="ralph-title"]').should('contain', 'Ralph')

      // Check for control buttons
      cy.get('[data-cy="ralph-controls"]').should('exist')
      
      // Check for Start button (should be visible when no run is active)
      cy.get('[data-cy="ralph-start-btn"]').should('exist').then(() => {
        cy.log('✅ Start button found')
      })

      // Check for log viewer
      cy.get('[data-cy="ralph-log-viewer"]', { timeout: 5000 }).should('exist').then(() => {
        cy.log('✅ Log viewer found')
      })

      // Check for stories panel (may not exist if no PRD loaded)
      cy.get('body').then(($body) => {
        if ($body.find('[data-cy="ralph-stories-panel"]').length > 0) {
          cy.log('✅ Stories panel found')
        }
      })

      // Check for runs panel
      cy.get('[data-cy="ralph-runs-panel"]', { timeout: 5000 }).should('exist').then(() => {
        cy.log('✅ Runs panel found')
        
        // Check if there are any runs
        cy.get('body').then(($body) => {
          if ($body.find('[data-cy="ralph-runs-list"]').length > 0) {
            cy.get('[data-cy="ralph-run-item"]').then(($runs) => {
              cy.log(`📋 Found ${$runs.length} Ralph runs`)
            })
          } else {
            cy.log('📋 No Ralph runs yet')
          }
        })
      })

      cy.screenshot('ralph-dashboard')
      cy.log('✅ Ralph UI verification complete')
    })
  })

  // Helper function to poll Ralph status
  function pollRalphStatus(runId, iteration) {
    if (iteration > 30) {
      cy.log('⏰ Max polling iterations reached')
      return
    }

    cy.request({
      method: 'GET',
      url: `${API_URL}/v1/ralph/runs/${runId}`,
      failOnStatusCode: false
    }).then((response) => {
      if (response.status !== 200) {
        cy.log(`❌ Failed to get status: ${response.status}`)
        return
      }

      const run = response.body
      const status = run.status
      const storyResults = run.story_results || []
      
      // Log progress
      const passed = storyResults.filter(s => s.status === 'passed').length
      const failed = storyResults.filter(s => s.status === 'failed').length
      const running = storyResults.filter(s => s.status === 'running').length
      const total = demoPRD.userStories.length

      cy.log(`📊 Status: ${status} | Progress: ${passed}/${total} passed, ${running} running, ${failed} failed`)

      // Log recent activity
      if (run.logs && run.logs.length > 0) {
        const recentLogs = run.logs.slice(-3)
        recentLogs.forEach(log => {
          cy.log(`   📝 ${log.type}: ${log.message}`)
        })
      }

      // Check if complete
      if (status === 'completed') {
        cy.log('🎉 Ralph run COMPLETED!')
        cy.log(`   Final: ${passed}/${total} stories passed`)
        return
      }

      if (status === 'failed') {
        cy.log(`❌ Ralph run FAILED: ${run.error}`)
        return
      }

      if (status === 'cancelled') {
        cy.log('⚠️ Ralph run was cancelled')
        return
      }

      // Continue polling
      cy.wait(3000).then(() => {
        pollRalphStatus(runId, iteration + 1)
      })
    })
  }
})

describe('Task Queue Demo', () => {
  const API_URL = Cypress.env('API_URL') || 'https://api.codetether.run'
  let apiAvailable = false

  before(() => {
    cy.request({
      method: 'GET',
      url: `${API_URL}/health`,
      failOnStatusCode: false,
      timeout: 10000
    }).then((response) => {
      apiAvailable = response.status === 200
    })
  })

  it('should demonstrate task queue operations', function() {
    if (!apiAvailable) {
      this.skip()
      return
    }
    cy.log('🔍 Fetching task queue status...')
    
    cy.request({
      method: 'GET',
      url: `${API_URL}/v1/tasks`,
      failOnStatusCode: false
    }).then((response) => {
      if (response.status !== 200) {
        cy.log('⚠️ Task queue API not available')
        return
      }

      const tasks = response.body
      cy.log(`📋 Found ${tasks.length} tasks in queue`)

      // Group by status
      const byStatus = {}
      tasks.forEach(t => {
        byStatus[t.status] = (byStatus[t.status] || 0) + 1
      })

      Object.entries(byStatus).forEach(([status, count]) => {
        cy.log(`   ${status}: ${count}`)
      })
    })
  })

  it('should create and monitor a test task', function() {
    if (!apiAvailable) {
      this.skip()
      return
    }
    cy.log('🚀 Creating test task...')

    cy.request({
      method: 'POST',
      url: `${API_URL}/v1/tasks`,
      headers: { 'Content-Type': 'application/json' },
      body: {
        title: 'Cypress Demo Task',
        description: 'A test task created by Cypress for demo purposes',
        agent_type: 'general',
        priority: 5
      },
      failOnStatusCode: false
    }).then((response) => {
      if (response.status !== 200 && response.status !== 201) {
        cy.log(`⚠️ Could not create task: ${response.status}`)
        return
      }

      const task = response.body
      cy.log(`✅ Task created: ${task.id}`)
      cy.log(`   Status: ${task.status}`)
    })
  })
})

describe('Ralph UI Interaction Demo', () => {
  it('should interact with Ralph run history', function() {
    cy.visit('/dashboard/ralph', { failOnStatusCode: false })
    cy.wait(2000)

    cy.url().then((url) => {
      if (url.includes('/login') || url.includes('/auth')) {
        this.skip()
        return
      }

      // Wait for runs panel to load
      cy.get('[data-cy="ralph-runs-panel"]', { timeout: 10000 }).should('exist')

      // Click refresh button
      cy.get('[data-cy="ralph-refresh-btn"]').click()
      cy.log('🔄 Refreshed runs list')
      cy.wait(1000)

      // Check for run items
      cy.get('body').then(($body) => {
        if ($body.find('[data-cy="ralph-run-item"]').length > 0) {
          // Click on first run to expand
          cy.get('[data-cy="ralph-run-item"]').first().click()
          cy.log('📂 Expanded first run')
          cy.wait(500)

          // Get run status
          cy.get('[data-cy="ralph-run-item"]').first().then(($run) => {
            const status = $run.attr('data-run-status')
            const runId = $run.attr('data-run-id')
            cy.log(`📊 Run ${runId?.slice(0,8)}... status: ${status}`)
          })

          cy.screenshot('ralph-run-expanded')
        } else {
          cy.log('📋 No runs to interact with')
          cy.screenshot('ralph-no-runs')
        }
      })
    })
  })

  it('should show Ralph log viewer states', function() {
    cy.visit('/dashboard/ralph', { failOnStatusCode: false })
    cy.wait(2000)

    cy.url().then((url) => {
      if (url.includes('/login') || url.includes('/auth')) {
        this.skip()
        return
      }

      cy.get('[data-cy="ralph-log-viewer"]', { timeout: 10000 }).should('exist')

      // Check log viewer state
      cy.get('body').then(($body) => {
        if ($body.find('[data-cy="ralph-empty-state"]').length > 0) {
          cy.log('📝 Log viewer showing empty state')
          cy.screenshot('ralph-log-empty')
        } else if ($body.find('[data-cy="ralph-log-entry"]').length > 0) {
          cy.get('[data-cy="ralph-log-entry"]').then(($entries) => {
            cy.log(`📝 Found ${$entries.length} log entries`)
          })
          cy.screenshot('ralph-log-entries')
        }

        // Check for streaming indicator
        if ($body.find('[data-cy="ralph-streaming-indicator"]').length > 0) {
          cy.log('🔴 Live streaming active')
        }

        // Check for running indicator
        if ($body.find('[data-cy="ralph-running-indicator"]').length > 0) {
          cy.get('[data-cy="ralph-running-indicator"]').then(($indicator) => {
            cy.log(`⏳ ${$indicator.text()}`)
          })
        }
      })
    })
  })

  it('should display story cards with proper attributes', function() {
    cy.visit('/dashboard/ralph', { failOnStatusCode: false })
    cy.wait(2000)

    cy.url().then((url) => {
      if (url.includes('/login') || url.includes('/auth')) {
        this.skip()
        return
      }

      cy.get('body').then(($body) => {
        if ($body.find('[data-cy="ralph-stories-panel"]').length > 0) {
          cy.get('[data-cy="ralph-stories-panel"]').should('exist')
          
          // Check progress
          cy.get('[data-cy="ralph-stories-progress"]').then(($progress) => {
            cy.log(`📊 Progress: ${$progress.text()}`)
          })

          // Check story cards
          cy.get('[data-cy="ralph-story-card"]').each(($card, index) => {
            const storyId = $card.attr('data-story-id')
            const status = $card.attr('data-story-status')
            cy.log(`  ${storyId}: ${status}`)
          })

          // Expand first story
          cy.get('[data-cy="ralph-story-expand-btn"]').first().click()
          cy.wait(300)
          cy.screenshot('ralph-story-expanded')

        } else {
          cy.log('⚠️ No stories panel - PRD not loaded')
        }
      })
    })
  })
})

describe('Agent Discovery Demo', () => {
  const API_URL = Cypress.env('API_URL') || 'https://api.codetether.run'
  let apiAvailable = false

  before(() => {
    cy.request({
      method: 'GET',
      url: `${API_URL}/health`,
      failOnStatusCode: false,
      timeout: 10000
    }).then((response) => {
      apiAvailable = response.status === 200
    })
  })

  it('should discover available agents', function() {
    if (!apiAvailable) {
      this.skip()
      return
    }
    cy.log('🔍 Discovering agents in network...')

    cy.request({
      method: 'GET',
      url: `${API_URL}/v1/agents`,
      failOnStatusCode: false
    }).then((response) => {
      if (response.status !== 200) {
        cy.log('⚠️ Agent discovery API not available')
        return
      }

      const agents = response.body
      cy.log(`🤖 Found ${agents.length} agents`)

      agents.forEach(agent => {
        cy.log(`   - ${agent.name}: ${agent.description || 'No description'}`)
        if (agent.capabilities) {
          cy.log(`     Capabilities: ${JSON.stringify(agent.capabilities)}`)
        }
      })
    })
  })
})
