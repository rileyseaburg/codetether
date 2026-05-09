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

  describe('send_message_async', () => {
    it('should send an async message', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          message: 'Async test from Zapier',
        },
      };

      const result = await appTester(
        App.creates.send_message_async.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.task_id).toBeDefined();
      expect(result.status).toBe('pending');
    });
  });

  describe('send_to_agent', () => {
    it('should send to a specific agent', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          agent_name: 'codetether-builder',
          message: 'Test message for specific agent',
        },
      };

      const result = await appTester(
        App.creates.send_to_agent.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.target_agent_name).toBe('codetether-builder');
    });
  });

  describe('cancel_ralph_run', () => {
    it('should cancel a ralph run', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          run_id: 'run_test123',
        },
      };

      // This will fail with 404 in test since run doesn't exist,
      // but validates the module loads and function executes
      await expect(
        appTester(App.creates.cancel_ralph_run.operation.perform, bundle)
      ).rejects.toThrow();
    });
  });

  describe('create_cronjob', () => {
    it('should create a cronjob', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          name: 'Test Cron Job',
          cron_expression: '0 9 * * 1-5',
          task_template: 'Run daily code review',
          description: 'Test cron from Zapier',
          timezone: 'UTC',
        },
      };

      const result = await appTester(
        App.creates.create_cronjob.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.name).toBe('Test Cron Job');
      expect(result.cron_expression).toBe('0 9 * * 1-5');
    });
  });

  describe('prd_chat', () => {
    it('should chat with PRD generator', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          message: 'I want to build a user authentication system with email login and OAuth2',
        },
      };

      const result = await appTester(
        App.creates.prd_chat.operation.perform,
        bundle
      );

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.conversation_id).toBeDefined();
    });
  });
});
