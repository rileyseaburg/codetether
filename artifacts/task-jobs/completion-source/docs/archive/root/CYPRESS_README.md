# A2A Server Cypress Validation

This directory contains comprehensive Cypress end-to-end tests that validate the A2A (Agent-to-Agent) protocol implementation with video recording capabilities.

## Overview

The Cypress test suite provides comprehensive validation of the A2A Server implementation, including:

- **Agent Discovery**: Validates agent card serving and discovery mechanisms
- **Message Sending**: Tests JSON-RPC message sending and receiving
- **Task Management**: Validates task creation, retrieval, and cancellation
- **Streaming**: Tests streaming functionality
- **Error Handling**: Validates proper error responses
- **Performance**: Tests concurrent requests and response times
- **Integration**: End-to-end workflow scenarios

## Quick Start

### Automated Testing with Video Recording

The easiest way to run the complete validation is using the automated test runner:

```bash
# Run complete validation with video recording
./cypress_test_runner.sh
```

This script will:
1. Install all dependencies
2. Start the A2A server
3. Wait for server to be ready
4. Run comprehensive Cypress tests
5. Record videos of test execution
6. Generate a detailed test report
7. Clean up resources

### Manual Testing

For development and debugging, you can run tests manually:

```bash
# Install dependencies
npm install
pip install -r requirements.txt

# Start A2A server in one terminal
python run_server.py run --name "Test Agent" --port 8000

# Run Cypress tests in another terminal
npm run test

# Or open Cypress UI for interactive testing
npm run test:open
```

## Test Structure

### Test Files

- `cypress/e2e/a2a-protocol.cy.js` - Main test suite covering all A2A protocol features
- `cypress/fixtures/test-data.json` - Test data and expected responses
- `cypress/support/e2e.js` - Custom commands and setup
- `cypress/support/commands.js` - Additional custom commands

### Custom Commands

The test suite includes several custom Cypress commands:

- `cy.waitForA2AServer()` - Waits for A2A server to be ready
- `cy.sendA2ARequest(method, params, options)` - Sends JSON-RPC requests
- `cy.createTestMessage(content, type)` - Creates test message objects

### Test Coverage

#### Agent Discovery
- ✅ Agent card serving at `/.well-known/agent-card.json`
- ✅ Capability validation (streaming, push notifications)
- ✅ Skill validation (echo skill functionality)
- ✅ Provider information validation

#### Message Processing
- ✅ Basic message sending and receiving
- ✅ Echo functionality validation
- ✅ Multiple message types and content
- ✅ Task creation during message processing
- ✅ JSON-RPC protocol compliance

#### Task Management
- ✅ Task creation and tracking
- ✅ Task information retrieval
- ✅ Task cancellation
- ✅ Task status management
- ✅ Non-existent task handling

#### Error Handling
- ✅ Malformed JSON requests
- ✅ Unsupported method calls
- ✅ Missing required parameters
- ✅ Invalid message formats
- ✅ Proper JSON-RPC error codes

#### Performance & Reliability
- ✅ Concurrent request handling
- ✅ Response time validation
- ✅ Server stability under load

#### Integration Scenarios
- ✅ Complete conversation flows
- ✅ Multi-step task workflows
- ✅ Context preservation across requests

## Video Recording

### Automatic Recording

When using the test runner script, videos are automatically recorded and saved to:

```
cypress/videos/
├── a2a-protocol.cy.js.mp4
└── ... (additional test files)
```

### Video Configuration

Video recording is configured in `cypress.config.js`:

```javascript
{
  video: true,
  videoCompression: 32,
  videosFolder: 'cypress/videos',
  // ... other settings
}
```

### Viewing Results

After tests complete, you can:

1. **Watch test videos**: Open files in `cypress/videos/`
2. **Review screenshots**: Check `cypress/screenshots/` for any failures
3. **Read test report**: Open generated `cypress_test_report.md`

## Test Data

The test suite uses predefined test data in `cypress/fixtures/test-data.json`:

```json
{
  "testMessages": [
    {
      "input": "Hello, Agent!",
      "expectedPrefix": "Echo: "
    }
    // ... more test cases
  ],
  "testAgent": {
    "name": "A2A Echo Agent",
    "expectedSkills": ["echo"]
  }
}
```

## Environment Configuration

### Environment Variables

- `A2A_PORT` - Server port (default: 8000)
- `A2A_HOST` - Server host (default: localhost)
- `TEST_TIMEOUT` - Test timeout in seconds (default: 60)
- `CYPRESS_baseUrl` - Base URL for Cypress tests

### Cypress Configuration

Key settings in `cypress.config.js`:

```javascript
{
  baseUrl: 'http://localhost:8000',
  defaultCommandTimeout: 10000,
  requestTimeout: 10000,
  responseTimeout: 10000,
  video: true
}
```

## Troubleshooting

### Common Issues

1. **Server not starting**
   - Check if port 8000 is available
   - Verify Python dependencies are installed
   - Check server logs for errors

2. **Tests timing out**
   - Increase timeout values in configuration
   - Check server responsiveness
   - Verify network connectivity

3. **Video not recording**
   - Ensure sufficient disk space
   - Check video codec availability
   - Verify Cypress version compatibility

### Debug Commands

```bash
# Check server status
curl http://localhost:8000/.well-known/agent-card.json

# Test basic message sending
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"message/send","params":{"message":{"parts":[{"type":"text","content":"test"}]}},"id":"1"}'

# Run specific test
npx cypress run --spec "cypress/e2e/a2a-protocol.cy.js"

# Open Cypress UI for debugging
npx cypress open
```

## CI/CD Integration

For continuous integration, use the automated test runner:

```yaml
# Example GitHub Actions step
- name: Run A2A Validation Tests
  run: |
    chmod +x ./cypress_test_runner.sh
    ./cypress_test_runner.sh

- name: Upload Test Videos
  uses: actions/upload-artifact@v3
  if: always()
  with:
    name: cypress-videos
    path: cypress/videos/
```

## Contributing

When adding new tests:

1. Follow existing test structure and naming conventions
2. Add test data to `cypress/fixtures/test-data.json`
3. Use custom commands for common operations
4. Ensure tests are independent and can run in any order
5. Add appropriate assertions and error handling

## Dependencies

### Node.js Dependencies
- `cypress` - End-to-end testing framework

### Python Dependencies  
- All requirements from `requirements.txt`
- A2A Server implementation

## Test Report Example

After running tests, a comprehensive report is generated:

```markdown
# A2A Server Cypress Validation Report

## Test Summary
- Test Date: 2024-01-15 10:30:00
- Server: http://localhost:8000
- Agent Name: Cypress Test Agent
- Test Status: ✅ PASSED

## Test Coverage
- ✅ Agent Discovery (Agent Card)
- ✅ Message Sending and Receiving
- ✅ Task Management
- ... (complete coverage list)
```

This validation suite provides comprehensive evidence that the A2A Server implementation correctly follows the Agent-to-Agent protocol specification and handles real-world usage scenarios effectively.