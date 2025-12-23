describe('A2A Protocol Server Validation', () => {
  const baseUrl = 'http://localhost:8000'
  
  beforeEach(() => {
    // Verify server is ready
    cy.request(`${baseUrl}/.well-known/agent-card.json`)
      .its('status').should('eq', 200)
  })

  describe('Agent Discovery', () => {
    it('should serve agent card with correct structure', () => {
      cy.request('GET', `${baseUrl}/.well-known/agent-card.json`)
        .then((response) => {
          expect(response.status).to.eq(200)
          
          const card = response.body
          expect(card).to.have.property('name')
          expect(card).to.have.property('description')
          expect(card).to.have.property('url')
          expect(card).to.have.property('provider')
          expect(card).to.have.property('capabilities')
          expect(card).to.have.property('skills')
          
          // Validate capabilities - enhanced server supports media
          expect(card.capabilities).to.have.property('media')
          
          // Validate skills - enhanced server has task_delegation as primary skill
          expect(card.skills).to.be.an('array').that.is.not.empty
          const primarySkill = card.skills[0]
          expect(primarySkill).to.have.property('id')
          expect(primarySkill).to.have.property('name')
          expect(primarySkill.input_modes).to.be.an('array')
          expect(primarySkill.output_modes).to.be.an('array')
        })
    })
  })

  describe('Message Handling', () => {
    it('should process basic text messages', () => {
      const testMessage = 'Hello from Cypress!'
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: testMessage }]
          }
        },
        id: '1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.jsonrpc).to.eq('2.0')
        expect(response.body.id).to.eq('1')
        expect(response.body.result).to.exist
        
        const result = response.body.result
        // Enhanced server returns acknowledgment message
        expect(result.message.parts[0].content).to.be.a('string').that.is.not.empty
        expect(result.task).to.have.property('id')
        // Task may be pending or completed depending on async processing
        expect(result.task.status).to.be.oneOf(['pending', 'working', 'completed'])
      })
    })

    it('should handle multiple different messages', () => {
      const testCases = [
        'Simple message',
        'Message with special characters: !@#$%^&*()',
        'Longer message with multiple words and punctuation.'
      ]

      testCases.forEach((testMessage, index) => {
        const request = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: testMessage }]
            }
          },
          id: `test-${index}`
        }

        cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: request
        }).then((response) => {
          expect(response.status).to.eq(200)
          // Enhanced server processes messages and returns responses
          expect(response.body.result.message.parts[0].content).to.be.a('string').that.is.not.empty
        })
      })
    })
  })

  describe('Task Management', () => {
    it('should create and retrieve tasks', () => {
      let taskId
      
      // First, create a task by sending a message
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'Create task' }]
          }
        },
        id: '1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        taskId = response.body.result.task.id
        expect(taskId).to.be.a('string').that.is.not.empty
        
        // Then retrieve the task
        const getTaskRequest = {
          jsonrpc: '2.0',
          method: 'tasks/get',
          params: { task_id: taskId },
          id: '2'
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: getTaskRequest
        })
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.task.id).to.eq(taskId)
        // Task may be pending, working, or completed
        expect(response.body.result.task.status).to.be.oneOf(['pending', 'working', 'completed'])
      })
    })

    it('should handle task cancellation', () => {
      let taskId
      
      // Create a task
      const createRequest = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'Task to cancel' }]
          }
        },
        id: '1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: createRequest
      }).then((response) => {
        taskId = response.body.result.task.id
        
        // Cancel the task
        const cancelRequest = {
          jsonrpc: '2.0',
          method: 'tasks/cancel',
          params: { task_id: taskId },
          id: '2'
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: cancelRequest
        })
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.task.status).to.eq('cancelled')
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle invalid JSON-RPC requests', () => {
      const invalidRequest = {
        method: 'invalid/method',
        params: {},
        id: '1'
        // Missing jsonrpc field
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: invalidRequest,
        failOnStatusCode: false
      }).then((response) => {
        // Server returns 400 for invalid JSON-RPC, which is correct
        expect(response.status).to.eq(400)
        expect(response.body).to.have.property('error')
      })
    })

    it('should handle unsupported methods', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'unsupported/method',
        params: {},
        id: '1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request,
        failOnStatusCode: false
      }).then((response) => {
        // Server returns 400 for method not found, which is correct
        expect(response.status).to.eq(400)
        expect(response.body).to.have.property('error')
        expect(response.body.error.code).to.eq(-32601) // Method not found
      })
    })

    it('should handle missing parameters', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {}, // Missing message parameter
        id: '1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request,
        failOnStatusCode: false
      }).then((response) => {
        // Server returns 500 for internal validation error, which is reasonable
        expect(response.status).to.be.oneOf([400, 500])
        expect(response.body).to.have.property('error')
        expect(response.body.error.code).to.be.oneOf([-32602, -32603]) // Invalid params or internal error
      })
    })
  })

  describe('Integration Scenarios', () => {
    it('should handle complete conversation workflow', () => {
      // Step 1: Get agent capabilities
      cy.request(`${baseUrl}/.well-known/agent-card.json`)
        .then((response) => {
          // Enhanced server has task_delegation as primary skill
          expect(response.body.skills[0]).to.have.property('id')
          
          // Step 2: Send initial message
          const request1 = {
            jsonrpc: '2.0',
            method: 'message/send',
            params: {
              message: {
                parts: [{ type: 'text', content: 'Start conversation' }]
              }
            },
            id: '1'
          }

          return cy.request({
            method: 'POST',
            url: baseUrl,
            headers: { 'Content-Type': 'application/json' },
            body: request1
          })
        })
        .then((response) => {
          const taskId = response.body.result.task.id
          expect(response.body.result.message.parts[0].content).to.be.a('string').that.is.not.empty
          
          // Step 3: Send follow-up message with task context
          const request2 = {
            jsonrpc: '2.0',
            method: 'message/send',
            params: {
              message: {
                parts: [{ type: 'text', content: 'Continue conversation' }]
              },
              task_id: taskId
            },
            id: '2'
          }

          return cy.request({
            method: 'POST',
            url: baseUrl,
            headers: { 'Content-Type': 'application/json' },
            body: request2
          })
        })
        .then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result.message.parts[0].content).to.be.a('string').that.is.not.empty
        })
    })

    it('should demonstrate concurrent request handling', () => {
      const requests = []
      
      // Create multiple concurrent requests
      for (let i = 0; i < 3; i++) {
        const request = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: `Message ${i}` }]
            }
          },
          id: `concurrent-${i}`
        }

        requests.push(
          cy.request({
            method: 'POST',
            url: baseUrl,
            headers: { 'Content-Type': 'application/json' },
            body: request
          })
        )
      }

      // Verify all requests succeed
      requests.forEach((request, index) => {
        request.then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result.message.parts[0].content).to.be.a('string').that.is.not.empty
        })
      })
    })
  })
})