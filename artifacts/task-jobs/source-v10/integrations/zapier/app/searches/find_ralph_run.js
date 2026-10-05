'use strict';

const API_BASE = 'https://api.codetether.io';

const findRalphRun = async (z, bundle) => {
  const runId = bundle.inputData.run_id;
  
  const response = await z.request({
    url: `${API_BASE}/v1/ralph/runs/${runId}`,
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (response.status === 404) {
    return [];
  }
  
  if (response.status !== 200) {
    throw new z.errors.Error(
      `Failed to find Ralph run: ${response.data.detail || response.statusText}`,
      'FindRalphRunError',
      response.status
    );
  }

  const run = response.data;
  
  // Calculate passed/total
  const passedCount = (run.story_results || []).filter(r => r.status === 'passed').length;
  const totalCount = run.prd.userStories.length;
  
  return [{
    id: run.id,
    run_id: run.id,
    project: run.prd.project,
    branch: run.prd.branchName,
    status: run.status,
    passed_count: passedCount,
    total_count: totalCount,
    progress: `${passedCount}/${totalCount}`,
    current_iteration: run.current_iteration,
    max_iterations: run.max_iterations,
    run_mode: run.run_mode,
    codebase_id: run.codebase_id,
    model: run.model,
    created_at: run.created_at,
    started_at: run.started_at,
    completed_at: run.completed_at,
    error: run.error,
    // Include story statuses as JSON string for reference
    story_results: JSON.stringify(run.story_results || []),
  }];
};

module.exports = {
  key: 'find_ralph_run',
  noun: 'Ralph Run',

  display: {
    label: 'Find Ralph Run',
    description: 'Find a Ralph run by its ID to check status and progress.',
  },

  operation: {
    inputFields: [
      {
        key: 'run_id',
        label: 'Run ID',
        type: 'string',
        required: true,
        helpText: 'The ID of the Ralph run to find.',
      },
    ],

    perform: findRalphRun,

    sample: {
      id: 'run_abc123',
      run_id: 'run_abc123',
      project: 'MyApp',
      branch: 'ralph/new-feature',
      status: 'completed',
      passed_count: 3,
      total_count: 3,
      progress: '3/3',
      current_iteration: 1,
      max_iterations: 10,
      run_mode: 'sequential',
      codebase_id: null,
      model: 'anthropic:claude-sonnet-4',
      created_at: '2026-01-22T08:00:00Z',
      started_at: '2026-01-22T08:00:01Z',
      completed_at: '2026-01-22T08:15:00Z',
      error: null,
      story_results: '[{"story_id":"US-001","status":"passed"}]',
    },

    outputFields: [
      { key: 'id', label: 'ID' },
      { key: 'run_id', label: 'Run ID' },
      { key: 'project', label: 'Project' },
      { key: 'branch', label: 'Branch' },
      { key: 'status', label: 'Status' },
      { key: 'passed_count', label: 'Passed Count' },
      { key: 'total_count', label: 'Total Count' },
      { key: 'progress', label: 'Progress' },
      { key: 'current_iteration', label: 'Current Iteration' },
      { key: 'max_iterations', label: 'Max Iterations' },
      { key: 'run_mode', label: 'Run Mode' },
      { key: 'codebase_id', label: 'Codebase ID' },
      { key: 'model', label: 'Model' },
      { key: 'created_at', label: 'Created At' },
      { key: 'started_at', label: 'Started At' },
      { key: 'completed_at', label: 'Completed At' },
      { key: 'error', label: 'Error' },
      { key: 'story_results', label: 'Story Results (JSON)' },
    ],
  },
};
