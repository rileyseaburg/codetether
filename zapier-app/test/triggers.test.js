'use strict';

const zapier = require('zapier-platform-core');
const App = require('../index');

const appTester = zapier.createAppTester(App);
zapier.tools.env.inject();

describe('triggers', () => {
  describe('new_task', () => {
    it('should load tasks', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.triggers.new_task.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    it('should filter tasks by status', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          status: 'pending',
        },
      };

      const results = await appTester(
        App.triggers.new_task.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);

      if (results.length > 0) {
        expect(results[0].status).toBe('pending');
      }
    });
  });

  describe('task_completed', () => {
    it('should load completed tasks', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.triggers.task_completed.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);

      if (results.length > 0) {
        expect(results[0].status).toBe('completed');
        expect(results[0].id).toBeDefined();
      }
    });
  });

  describe('task_failed', () => {
    it('should load failed tasks', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.triggers.task_failed.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);

      if (results.length > 0) {
        expect(results[0].status).toBe('failed');
        expect(results[0].id).toBeDefined();
      }
    });
  });
});
