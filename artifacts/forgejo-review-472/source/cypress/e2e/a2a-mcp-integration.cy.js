describe('A2A Protocol Server with MCP Integration Validation', () => {
  const baseUrl = 'http://localhost:8000'
  
  beforeEach(() => {
    // Verify server is ready
    cy.request(`${baseUrl}/.well-known/agent-card.json`)
      .its('status').should('eq', 200)
  })

  describe('Enhanced Agent Discovery', () => {
    it('should serve agent card with MCP-enhanced capabilities', () => {
      cy.request('GET', `${baseUrl}/.well-known/agent-card.json`)
        .then((response) => {
          expect(response.status).to.eq(200)
          
          const card = response.body
          expect(card).to.have.property('name', 'Enhanced A2A Agent')
          expect(card).to.have.property('description').that.includes('MCP tool integration')
          expect(card).to.have.property('skills')
          
          // Validate MCP-enhanced skills
          expect(card.skills).to.be.an('array').with.length.greaterThan(4)
          
          const skillIds = card.skills.map(skill => skill.id)
          expect(skillIds).to.include.members(['calculator', 'text_analysis', 'weather', 'memory', 'echo'])
          
          // Validate calculator skill
          const calculatorSkill = card.skills.find(skill => skill.id === 'calculator')
          expect(calculatorSkill).to.exist
          expect(calculatorSkill.name).to.eq('Mathematical Calculator')
          expect(calculatorSkill.description).to.include('mathematical calculations')
          
          // Validate analysis skill
          const analysisSkill = card.skills.find(skill => skill.id === 'text_analysis')
          expect(analysisSkill).to.exist
          expect(analysisSkill.name).to.eq('Text Analysis')
          
          // Validate memory skill
          const memorySkill = card.skills.find(skill => skill.id === 'memory')
          expect(memorySkill).to.exist
          expect(memorySkill.name).to.eq('Memory Management')
        })
    })
  })

  describe('MCP Calculator Integration', () => {
    it('should perform addition using MCP calculator tool', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'add 15 and 27' }]
          }
        },
        id: 'calc-add-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Calculation: 15 add 27 = 42')
        expect(response.body.result.task.status).to.eq('completed')
      })
    })

    it('should perform multiplication using MCP calculator tool', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'multiply 8 and 9' }]
          }
        },
        id: 'calc-mult-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Calculation: 8 multiply 9 = 72')
      })
    })

    it('should perform square root using MCP calculator tool', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'square root of 64' }]
          }
        },
        id: 'calc-sqrt-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Square root of 64 = 8')
      })
    })

    it('should handle division by zero gracefully', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'divide 10 by 0' }]
          }
        },
        id: 'calc-div-zero-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Cannot divide by zero')
      })
    })
  })

  describe('MCP Text Analysis Integration', () => {
    it('should analyze text using MCP text analyzer tool', () => {
      const testText = 'This is a sample text for analysis. It contains multiple sentences!'
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: `analyze this text: ${testText}` }]
          }
        },
        id: 'analysis-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        const content = response.body.result.message.parts[0].content
        expect(content).to.include('Text Analysis:')
        expect(content).to.include('words')
        expect(content).to.include('sentences')
        expect(content).to.include('characters')
        expect(content).to.include('Average word length:')
      })
    })
  })

  describe('MCP Weather Integration', () => {
    it('should provide weather information using MCP weather tool', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'weather in San Francisco' }]
          }
        },
        id: 'weather-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        const content = response.body.result.message.parts[0].content
        expect(content).to.include('Weather for San Francisco')
        expect(content).to.include('°C')
        expect(content).to.include('Humidity:')
        expect(content).to.include('Wind:')
      })
    })
  })

  describe('MCP Memory Management Integration', () => {
    it('should store and retrieve data using MCP memory tool', () => {
      // Store data
      const storeRequest = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'store "John Doe" as user_name' }]
          }
        },
        id: 'memory-store-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: storeRequest
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Stored')
        expect(response.body.result.message.parts[0].content)
          .to.include('user_name')

        // Retrieve data
        const retrieveRequest = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: 'retrieve user_name' }]
            }
          },
          id: 'memory-retrieve-1'
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: retrieveRequest
        })
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Retrieved')
        expect(response.body.result.message.parts[0].content)
          .to.include('John Doe')
      })
    })

    it('should list stored keys using MCP memory tool', () => {
      // First store some data
      const storeRequests = [
        { key: 'key1', value: 'value1' },
        { key: 'key2', value: 'value2' }
      ]

      // Store data sequentially
      cy.wrap(storeRequests).each((item) => {
        const request = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: `store "${item.value}" as ${item.key}` }]
            }
          },
          id: `memory-store-${item.key}`
        }

        cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: request
        }).then((response) => {
          expect(response.status).to.eq(200)
        })
      }).then(() => {
        // List all keys
        const listRequest = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: 'list stored keys' }]
            }
          },
          id: 'memory-list-1'
        }

        cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: listRequest
        }).then((response) => {
          expect(response.status).to.eq(200)
          const content = response.body.result.message.parts[0].content
          expect(content).to.include('Stored keys')
          expect(content).to.include('key1')
          expect(content).to.include('key2')
        })
      })
    })
  })

  describe('Complex A2A + MCP Workflows', () => {
    it('should demonstrate agent coordination with MCP tool usage', () => {
      // Step 1: Store calculation parameters
      const storeRequest = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'store "calculation_params" as last_operation' }]
          }
        },
        id: 'workflow-store-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: storeRequest
      }).then((response) => {
        expect(response.status).to.eq(200)

        // Step 2: Perform calculation
        const calcRequest = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: 'add 100 and 200' }]
            }
          },
          id: 'workflow-calc-1'
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: calcRequest
        })
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('= 300')

        // Step 3: Analyze the result text
        const resultText = response.body.result.message.parts[0].content
        const analysisRequest = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: `analyze this calculation result: ${resultText}` }]
            }
          },
          id: 'workflow-analysis-1'
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: analysisRequest
        })
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Text Analysis:')
      })
    })

    it('should handle concurrent MCP tool requests', () => {
      const requests = [
        {
          content: 'multiply 5 and 6',
          id: 'concurrent-calc-1'
        },
        {
          content: 'weather in New York',
          id: 'concurrent-weather-1'
        },
        {
          content: 'analyze this text: Hello world from concurrent test',
          id: 'concurrent-analysis-1'
        }
      ]

      // Send all requests concurrently
      const requestPromises = requests.map(req => {
        const request = {
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              parts: [{ type: 'text', content: req.content }]
            }
          },
          id: req.id
        }

        return cy.request({
          method: 'POST',
          url: baseUrl,
          headers: { 'Content-Type': 'application/json' },
          body: request
        })
      })

      // Verify all requests succeed
      cy.wrap(requestPromises).each((requestPromise, index) => {
        requestPromise.then((response) => {
          expect(response.status).to.eq(200)
          expect(response.body.result.task.status).to.eq('completed')
          
          const content = response.body.result.message.parts[0].content
          if (index === 0) {
            expect(content).to.include('= 30')
          } else if (index === 1) {
            expect(content).to.include('Weather for New York')
          } else if (index === 2) {
            expect(content).to.include('Text Analysis:')
          }
        })
      })
    })
  })

  describe('Error Handling with MCP Integration', () => {
    it('should handle MCP tool failures gracefully', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'square root of -25' }]
          }
        },
        id: 'error-handling-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Cannot take square root of negative number')
      })
    })

    it('should fallback to echo for unrecognized patterns', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'this is just a random message that should echo' }]
          }
        },
        id: 'fallback-echo-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('Echo: this is just a random message that should echo')
      })
    })
  })

  describe('MCP Tool Performance Validation', () => {
    it('should process MCP tool requests within reasonable time', () => {
      const startTime = Date.now()
      
      const request = {
        jsonrpc: '2.0',
        method: 'message/send',
        params: {
          message: {
            parts: [{ type: 'text', content: 'add 1000 and 2000' }]
          }
        },
        id: 'performance-test-1'
      }

      cy.request({
        method: 'POST',
        url: baseUrl,
        headers: { 'Content-Type': 'application/json' },
        body: request
      }).then((response) => {
        const duration = Date.now() - startTime
        expect(response.status).to.eq(200)
        expect(response.body.result.message.parts[0].content)
          .to.include('= 3000')
        
        // Should complete within 5 seconds (generous allowance for MCP overhead)
        expect(duration).to.be.lessThan(5000)
      })
    })
  })
})