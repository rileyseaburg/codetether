describe('A2A Basic Test', () => {
  it('should connect to server', () => {
    cy.request('GET', 'http://localhost:8000/.well-known/agent-card.json')
      .then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body).to.have.property('name')
        cy.log('Agent card retrieved successfully')
        cy.log(JSON.stringify(response.body, null, 2))
      })
  })

  it('should send basic message', () => {
    const request = {
      jsonrpc: '2.0',
      method: 'message/send',
      params: {
        message: {
          parts: [{ type: 'text', content: 'Hello' }]
        }
      },
      id: '1'
    }

    cy.request({
      method: 'POST',
      url: 'http://localhost:8000',
      headers: { 'Content-Type': 'application/json' },
      body: request
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body).to.have.property('result')
      cy.log('Message sent successfully')
      cy.log(JSON.stringify(response.body, null, 2))
    })
  })
})