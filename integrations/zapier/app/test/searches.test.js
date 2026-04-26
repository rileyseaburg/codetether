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

  describe('discover_agents', () => {
    it('should list agents', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.searches.discover_agents.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    it('should filter agents by name', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          name: 'codetether',
        },
      };

      const results = await appTester(
        App.searches.discover_agents.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('list_codebases', () => {
    it('should list codebases', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.searches.list_codebases.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('list_ralph_runs', () => {
    it('should list ralph runs', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.searches.list_ralph_runs.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    it('should filter by status', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          status: 'completed',
        },
      };

      const results = await appTester(
        App.searches.list_ralph_runs.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('list_models', () => {
    it('should list available models', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.searches.list_models.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });

    it('should filter models by provider', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {
          provider: 'anthropic',
        },
      };

      const results = await appTester(
        App.searches.list_models.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('get_usage_summary', () => {
    it('should get usage summary', async () => {
      const bundle = {
        authData: {
          access_token: process.env.ACCESS_TOKEN,
        },
        inputData: {},
      };

      const results = await appTester(
        App.searches.get_usage_summary.operation.perform,
        bundle
      );

      expect(results).toBeDefined();
      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        expect(results[0].id).toBeDefined();
      }
    });
  });
});
