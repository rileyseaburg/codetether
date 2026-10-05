'use strict';

const API_BASE = 'https://api.codetether.io';

const startRalph = async (z, bundle) => {
  // Parse the PRD from JSON or build from fields
  let prd;
  
  if (bundle.inputData.prd_json) {
    try {
      prd = JSON.parse(bundle.inputData.prd_json);
    } catch (e) {
      throw new z.errors.Error(
        'Invalid PRD JSON format. Please provide valid JSON.',
        'InvalidPRDError',
        400
      );
    }
  } else {
    // Build PRD from individual fields
    const stories = [];
    
    // Support up to 10 user stories via numbered fields
    for (let i = 1; i <= 10; i++) {
      const storyId = bundle.inputData[`story_${i}_id`];
      const storyTitle = bundle.inputData[`story_${i}_title`];
      const storyDescription = bundle.inputData[`story_${i}_description`];
      const storyCriteria = bundle.inputData[`story_${i}_criteria`];
      
      if (storyId && storyTitle) {
        stories.push({
          id: storyId,
          title: storyTitle,
          description: storyDescription || storyTitle,
          acceptanceCriteria: storyCriteria 
            ? storyCriteria.split('\n').filter(c => c.trim())
            : [storyTitle],
          priority: i,
        });
      }
    }
    
    if (stories.length === 0) {
      throw new z.errors.Error(
        'No user stories provided. Either provide PRD JSON or fill in story fields.',
        'NoStoriesError',
        400
      );
    }
    
    prd = {
      project: bundle.inputData.project_name || 'Zapier Project',
      branchName: bundle.inputData.branch_name || `ralph/zapier-${Date.now()}`,
      description: bundle.inputData.project_description || 'Ralph run from Zapier',
      userStories: stories,
    };
  }
  
  const response = await z.request({
    url: `${API_BASE}/v1/ralph/runs`,
    method: 'POST',
    body: {
      prd: prd,
      codebase_id: bundle.inputData.codebase_id || null,
      model: bundle.inputData.model || null,
      max_iterations: parseInt(bundle.inputData.max_iterations) || 10,
      run_mode: bundle.inputData.run_mode || 'sequential',
      max_parallel: parseInt(bundle.inputData.max_parallel) || 3,
    },
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (response.status !== 200 && response.status !== 201) {
    throw new z.errors.Error(
      `Failed to start Ralph run: ${response.data.detail || response.statusText}`,
      'StartRalphError',
      response.status
    );
  }

  const run = response.data;
  
  return {
    id: run.id,
    run_id: run.id,
    project: run.prd.project,
    branch: run.prd.branchName,
    status: run.status,
    story_count: run.prd.userStories.length,
    max_iterations: run.max_iterations,
    run_mode: run.run_mode,
    codebase_id: run.codebase_id,
    model: run.model,
    created_at: run.created_at,
  };
};

module.exports = {
  key: 'start_ralph',
  noun: 'Ralph Run',

  display: {
    label: 'Start Ralph Run',
    description: 'Start an autonomous Ralph development run from a PRD. Ralph will implement each user story, run tests, and commit changes.',
    important: true,
  },

  operation: {
    inputFields: [
      // Option 1: Full PRD JSON
      {
        key: 'prd_json',
        label: 'PRD (JSON)',
        type: 'text',
        required: false,
        helpText: 'Full PRD as JSON. If provided, other story fields are ignored. Example: {"project": "MyApp", "branchName": "ralph/feature", "description": "New feature", "userStories": [...]}',
      },
      // Option 2: Individual fields
      {
        key: 'project_name',
        label: 'Project Name',
        type: 'string',
        required: false,
        helpText: 'Name of the project (used if PRD JSON not provided).',
      },
      {
        key: 'branch_name',
        label: 'Branch Name',
        type: 'string',
        required: false,
        helpText: 'Git branch name for changes (e.g., ralph/new-feature).',
      },
      {
        key: 'project_description',
        label: 'Project Description',
        type: 'text',
        required: false,
        helpText: 'Brief description of what Ralph should accomplish.',
      },
      // Story 1
      {
        key: 'story_1_id',
        label: 'Story 1 - ID',
        type: 'string',
        required: false,
        helpText: 'Unique ID for story 1 (e.g., US-001).',
      },
      {
        key: 'story_1_title',
        label: 'Story 1 - Title',
        type: 'string',
        required: false,
        helpText: 'Title for story 1.',
      },
      {
        key: 'story_1_description',
        label: 'Story 1 - Description',
        type: 'text',
        required: false,
        helpText: 'Full description of what story 1 should accomplish.',
      },
      {
        key: 'story_1_criteria',
        label: 'Story 1 - Acceptance Criteria',
        type: 'text',
        required: false,
        helpText: 'Acceptance criteria (one per line).',
      },
      // Story 2
      {
        key: 'story_2_id',
        label: 'Story 2 - ID',
        type: 'string',
        required: false,
      },
      {
        key: 'story_2_title',
        label: 'Story 2 - Title',
        type: 'string',
        required: false,
      },
      {
        key: 'story_2_description',
        label: 'Story 2 - Description',
        type: 'text',
        required: false,
      },
      {
        key: 'story_2_criteria',
        label: 'Story 2 - Acceptance Criteria',
        type: 'text',
        required: false,
      },
      // Story 3
      {
        key: 'story_3_id',
        label: 'Story 3 - ID',
        type: 'string',
        required: false,
      },
      {
        key: 'story_3_title',
        label: 'Story 3 - Title',
        type: 'string',
        required: false,
      },
      {
        key: 'story_3_description',
        label: 'Story 3 - Description',
        type: 'text',
        required: false,
      },
      {
        key: 'story_3_criteria',
        label: 'Story 3 - Acceptance Criteria',
        type: 'text',
        required: false,
      },
      // Settings
      {
        key: 'codebase_id',
        label: 'Codebase ID',
        type: 'string',
        required: false,
        helpText: 'Target codebase ID. Leave empty for global.',
      },
      {
        key: 'model',
        label: 'AI Model',
        type: 'string',
        required: false,
        helpText: 'AI model to use (e.g., anthropic:claude-sonnet-4).',
      },
      {
        key: 'max_iterations',
        label: 'Max Iterations',
        type: 'integer',
        required: false,
        default: '10',
        helpText: 'Maximum iterations per story (for retries).',
      },
      {
        key: 'run_mode',
        label: 'Run Mode',
        type: 'string',
        choices: ['sequential', 'parallel'],
        required: false,
        default: 'sequential',
        helpText: 'Run stories sequentially or in parallel.',
      },
      {
        key: 'max_parallel',
        label: 'Max Parallel',
        type: 'integer',
        required: false,
        default: '3',
        helpText: 'Max concurrent stories when running in parallel mode.',
      },
    ],

    perform: startRalph,

    sample: {
      id: 'run_abc123',
      run_id: 'run_abc123',
      project: 'MyApp',
      branch: 'ralph/new-feature',
      status: 'running',
      story_count: 3,
      max_iterations: 10,
      run_mode: 'sequential',
      codebase_id: null,
      model: 'anthropic:claude-sonnet-4',
      created_at: '2026-01-22T08:00:00Z',
    },

    outputFields: [
      { key: 'id', label: 'ID' },
      { key: 'run_id', label: 'Run ID' },
      { key: 'project', label: 'Project' },
      { key: 'branch', label: 'Branch' },
      { key: 'status', label: 'Status' },
      { key: 'story_count', label: 'Story Count' },
      { key: 'max_iterations', label: 'Max Iterations' },
      { key: 'run_mode', label: 'Run Mode' },
      { key: 'codebase_id', label: 'Codebase ID' },
      { key: 'model', label: 'Model' },
      { key: 'created_at', label: 'Created At' },
    ],
  },
};
