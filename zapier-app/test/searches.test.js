'use strict';

const zapier = require('zapier-platform-core');
const App = require('../index');

const appTester = zapier.createAppTester(App);
zapier.tools.env.inject();

describe('searches', () => {
  describe('find_task', () => {
    it('should find tasks by status', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          status: 'completed',
        },
      };

      const results = await appTester(
        App.searches.find_task.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
      // Search should return 0 or 1 result
      expect(results.length).toBeLessThanOrEqual(1);
    });

    it('should return empty array for non-existent task', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          task_id: 'non_existent_task_id_12345',
        },
      };

      const results = await appTester(
        App.searches.find_task.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(0);
    });
  });
});
