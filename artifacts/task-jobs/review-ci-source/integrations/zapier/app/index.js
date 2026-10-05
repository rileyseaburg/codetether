'use strict';

const authentication = require('./authentication');

// Triggers
const newTaskTrigger = require('./triggers/new_task');
const taskCompletedTrigger = require('./triggers/task_completed');
const taskFailedTrigger = require('./triggers/task_failed');

// Creates (Actions)
const createTaskAction = require('./creates/create_task');
const sendMessageAction = require('./creates/send_message');
const sendMessageAsyncAction = require('./creates/send_message_async');
const sendToAgentAction = require('./creates/send_to_agent');
const startRalphAction = require('./creates/start_ralph');
const cancelTaskAction = require('./creates/cancel_task');
const cancelRalphRunAction = require('./creates/cancel_ralph_run');
const createCronjobAction = require('./creates/create_cronjob');
const prdChatAction = require('./creates/prd_chat');

// Searches
const findTaskSearch = require('./searches/find_task');
const findRalphRunSearch = require('./searches/find_ralph_run');
const discoverAgentsSearch = require('./searches/discover_agents');
const listCodebasesSearch = require('./searches/list_codebases');
const listRalphRunsSearch = require('./searches/list_ralph_runs');
const listModelsSearch = require('./searches/list_models');
const getUsageSummarySearch = require('./searches/get_usage_summary');

// Add OAuth token to all requests
const addBearerToken = (request, z, bundle) => {
  if (bundle.authData.access_token) {
    request.headers.Authorization = `Bearer ${bundle.authData.access_token}`;
  }
  return request;
};

// Handle token refresh errors
const handleRefreshError = (response, z, bundle) => {
  if (response.status === 401) {
    throw new z.errors.RefreshAuthError();
  }
  return response;
};

module.exports = {
  version: require('./package.json').version,
  platformVersion: require('zapier-platform-core').version,

  authentication,

  beforeRequest: [addBearerToken],
  afterResponse: [handleRefreshError],

  triggers: {
    [newTaskTrigger.key]: newTaskTrigger,
    [taskCompletedTrigger.key]: taskCompletedTrigger,
    [taskFailedTrigger.key]: taskFailedTrigger,
  },

  searches: {
    [findTaskSearch.key]: findTaskSearch,
    [findRalphRunSearch.key]: findRalphRunSearch,
    [discoverAgentsSearch.key]: discoverAgentsSearch,
    [listCodebasesSearch.key]: listCodebasesSearch,
    [listRalphRunsSearch.key]: listRalphRunsSearch,
    [listModelsSearch.key]: listModelsSearch,
    [getUsageSummarySearch.key]: getUsageSummarySearch,
  },

  creates: {
    [createTaskAction.key]: createTaskAction,
    [sendMessageAction.key]: sendMessageAction,
    [sendMessageAsyncAction.key]: sendMessageAsyncAction,
    [sendToAgentAction.key]: sendToAgentAction,
    [startRalphAction.key]: startRalphAction,
    [cancelTaskAction.key]: cancelTaskAction,
    [cancelRalphRunAction.key]: cancelRalphRunAction,
    [createCronjobAction.key]: createCronjobAction,
    [prdChatAction.key]: prdChatAction,
  },
};
