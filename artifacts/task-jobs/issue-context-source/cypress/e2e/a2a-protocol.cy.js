describe('A2A Protocol Server Validation', () => {
  let testData
  let serverProcess
  
  before(() => {
    // Load test data
    cy.fixture('test-data').then((data) => {
      testData = data
    })
  })

  beforeEach(() => {
    // Wait for server to be ready before each test
    cy.request({
      url: 'http://localhost:8000/.well-known/agent-card.json',
      timeout: 10000,
      retryOnStatusCodeFailure: true,
      retryOnNetworkFailure: true
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body).to.have.property('name')
    })
  })

  describe('Agent Discovery', () => {
    it('should serve agent card at well-known endpoint', () => {
      cy.request('GET', '/.well-known/agent-card.json')
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body).to.have.property('name')
          expect(response.body).to.have.property('description')
          expect(response.body).to.have.property('url')
          expect(response.body).to.have.property('provider')
          expect(response.body).to.have.property('capabilities')
          expect(response.body).to.have.property('skills')
          
          // Validate agent name matches expected
          expect(response.body.name).to.include('Agent')
          
          // Validate capabilities
          expect(response.body.capabilities).to.have.property('streaming', true)
          expect(response.body.capabilities).to.have.property('push_notifications', true)
          
          // Validate skills
          expect(response.body.skills).to.be.an('array')
          expect(response.body.skills.length).to.be.greaterThan(0)
          
          const echoSkill = response.body.skills.find(skill => skill.id === 'echo')
          expect(echoSkill).to.exist
          expect(echoSkill.name).to.eq('Echo Messages')
          expect(echoSkill.input_modes).to.include('text')
          expect(echoSkill.output_modes).to.include('text')
        })
    })

    it('should return JSON-RPC error for invalid endpoints', () => {
      cy.request({
        method: 'GET',
        url: '/invalid-endpoint',
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(404)
      })
    })
  })

  describe('Message Sending', () => {
    it('should handle basic message sending', () => {
      const testMessage = 'Hello, A2A Server!'
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [
              {
                type: 'text',
                content: testMessage
              }
            ]
          }
        },
        id: Date.now().toString()
      }

      cy.request({
        method: 'POST',
        url: 'http://localhost:8000',
        headers: {
          'Content-Type': 'application/json'
        },
        body: request
      }).then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body).to.have.property('jsonrpc', '2.0')
          expect(response.body).to.have.property('result')
          expect(response.body.result).to.have.property('message')
          expect(response.body.result).to.have.property('task')
          
          // Validate echo response
          const responseMessage = response.body.result.message
          expect(responseMessage.parts).to.be.an('array')
          expect(responseMessage.parts[0].type).to.eq('text')
          expect(responseMessage.parts[0].content).to.eq(`Echo: ${testMessage}`)
          
          // Validate task creation
          const task = response.body.result.task
          expect(task).to.have.property('id')
          expect(task).to.have.property('status')
          expect(task).to.have.property('created_at')
        })
    })

    it('should handle multiple test messages', () => {
      cy.fixture('test-data').then((data) => {
        data.testMessages.forEach((testCase, index) => {
          const message = {
            parts: [
              {
                type: 'text',
                content: testCase.input
              }
            ]
          }

          cy.sendA2ARequest('message/send', { message }, { id: `test-${index}` })
            .then((response) => {
              expect(response.status).to.eq(200)
              expect(response.body.result.message.parts[0].content)
                .to.eq(`${testCase.expectedPrefix}${testCase.input}`)
            })
        })
      })
    })

    it('should validate JSON-RPC request structure', () => {
      // Test with missing method
      cy.request({
        method: 'POST',
        url: '/',
        headers: { 'Content-Type': 'application/json' },
        body: {
          jsonrpc: '2.0',
          params: {},
          id: 'test-invalid'
        },
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body).to.have.property('error')
        expect(response.body.error).to.have.property('code')
        expect(response.body.error).to.have.property('message')
      })
    })

    it('should handle invalid message format', () => {
      cy.sendA2ARequest('message/send', { 
        message: { invalid: 'format' } 
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body).to.have.property('error')
      })
    })
  })

  describe('Task Management', () => {
    let taskId

    it('should create and track tasks', () => {
      const message = cy.createTestMessage('Create a task for me')

      cy.sendA2ARequest('message/send', { message })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result).to.have.property('task')
          
          taskId = response.body.result.task.id
          expect(taskId).to.be.a('string')
          expect(taskId.length).to.be.greaterThan(0)
        })
    })

    it('should retrieve task information', () => {
      // First create a task
      const message = cy.createTestMessage('Task for retrieval test')

      cy.sendA2ARequest('message/send', { message })
        .then((response) => {
          const createdTaskId = response.body.result.task.id
          
          // Then retrieve it
          return cy.sendA2ARequest('tasks/get', { task_id: createdTaskId })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result).to.have.property('task')
          
          const task = response.body.result.task
          expect(task).to.have.property('id')
          expect(task).to.have.property('status')
          expect(task).to.have.property('created_at')
          expect(task).to.have.property('updatedAt')
        })
    })

    it('should handle task cancellation', () => {
      // First create a task
      const message = cy.createTestMessage('Task for cancellation test')

      cy.sendA2ARequest('message/send', { message })
        .then((response) => {
          const createdTaskId = response.body.result.task.id
          
          // Then cancel it
          return cy.sendA2ARequest('tasks/cancel', { task_id: createdTaskId })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result).to.have.property('task')
          expect(response.body.result.task.status).to.eq('cancelled')
        })
    })

    it('should handle non-existent task requests', () => {
      cy.sendA2ARequest('tasks/get', { task_id: 'non-existent-task-id' })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body).to.have.property('error')
          expect(response.body.error.message).to.include('not found')
        })
    })
  })

  describe('Streaming Functionality', () => {
    it('should support streaming requests', () => {
      const message = cy.createTestMessage('Stream this message')

      // Note: Cypress doesn't handle SSE streams directly, but we can test the endpoint
      cy.sendA2ARequest('message/stream', { message })
        .then((response) => {
          // For streaming, we expect the initial response to acknowledge the request
          expect(response.status).to.eq(200)
        })
    })
  })

  describe('Error Handling', () => {
    it('should handle malformed JSON', () => {
      cy.request({
        method: 'POST',
        url: '/',
        headers: { 'Content-Type': 'application/json' },
        body: '{ invalid json }',
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(400)
      })
    })

    it('should handle unsupported methods', () => {
      cy.sendA2ARequest('unsupported/method', {})
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body).to.have.property('error')
          expect(response.body.error.code).to.eq(-32601) // Method not found
        })
    })

    it('should handle missing required parameters', () => {
      // Test message/send without message parameter
      cy.sendA2ARequest('message/send', {})
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body).to.have.property('error')
          expect(response.body.error.code).to.eq(-32602) // Invalid params
        })
    })
  })

  describe('Performance and Reliability', () => {
    it('should handle concurrent requests', () => {
      const requests = []
      
      // Send multiple concurrent requests
      for (let i = 0; i < 5; i++) {
        const message = cy.createTestMessage(`Concurrent message ${i}`)
        requests.push(
          cy.sendA2ARequest('message/send', { message }, { id: `concurrent-${i}` })
        )
      }

      // Verify all requests succeed
      cy.wrap(requests).each((request) => {
        cy.wrap(request).then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result).to.have.property('message')
        })
      })
    })

    it('should maintain consistent response times', () => {
      const startTime = Date.now()
      const message = cy.createTestMessage('Performance test message')

      cy.sendA2ARequest('message/send', { message })
        .then((response) => {
          const endTime = Date.now()
          const responseTime = endTime - startTime
          
          expect(response.status).to.eq(200)
          expect(responseTime).to.be.lessThan(5000) // Should respond within 5 seconds
        })
    })
  })

  describe('Integration Scenarios', () => {
    it('should handle complete conversation flow', () => {
      // Step 1: Get agent info
      cy.request('GET', '/.well-known/agent-card.json')
        .then((response) => {
          expect(response.status).to.eq(200)
          const agentCard = response.body
          
          // Step 2: Send initial message
          const message1 = cy.createTestMessage('Hello, how can you help me?')
          return cy.sendA2ARequest('message/send', { message: message1 })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          const task1 = response.body.result.task
          
          // Step 3: Send follow-up message with task context
          const message2 = cy.createTestMessage('Can you echo this follow-up?')
          return cy.sendA2ARequest('message/send', { 
            message: message2, 
            task_id: task1.id 
          })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result.message.parts[0].content)
            .to.include('Echo: Can you echo this follow-up?')
        })
    })

    it('should demonstrate multi-step task workflow', () => {
      let taskId
      
      // Create initial task
      const message1 = cy.createTestMessage('Start a multi-step process')
      
      cy.sendA2ARequest('message/send', { message: message1 })
        .then((response) => {
          taskId = response.body.result.task.id
          
          // Check task status
          return cy.sendA2ARequest('tasks/get', { task_id: taskId })
        })
        .then((response) => {
          expect(response.body.result.task.status).to.be.oneOf(['pending', 'completed'])
          
          // Continue with same task
          const message2 = cy.createTestMessage('Continue the process')
          return cy.sendA2ARequest('message/send', { 
            message: message2, 
            task_id: taskId 
          })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result.task.id).to.eq(taskId)
        })
    })
  })
})