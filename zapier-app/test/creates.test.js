'use strict';

const zapier = require('zapier-platform-core');
const App = require('../index');

const appTester = zapier.createAppTester(App);
zapier.tools.env.inject();

describe('creates', () => {
  describe('create_task', () => {
    it('should create a task', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          title: 'Test task from Zapier',
          description: 'This is a test task created by the Zapier integration test.',
          priority: 1,
          agent_type: 'general',
        },
      };

      const result = await appTester(
        App.creates.create_task.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.title).toBe('Test task from Zapier');
      expect(result.status).toBe('pending');
    });
  });

  describe('send_message', () => {
    it('should send a message', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          message: 'Hello from Zapier test!',
        },
      };

      const result = await appTester(
        App.creates.send_message.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.success).toBe(true);
    });
  });
});
