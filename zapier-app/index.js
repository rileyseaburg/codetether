'use strict';

const authentication = require('./authentication');
const newTaskTrigger = require('./triggers/new_task');
const createTaskAction = require('./creates/create_task');
const sendMessageAction = require('./creates/send_message');
const startRalphAction = require('./creates/start_ralph');
const findTaskSearch = require('./searches/find_task');
const findRalphRunSearch = require('./searches/find_ralph_run');
const cancelTaskAction = require('./creates/cancel_task');

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
  },

  searches: {
    [findTaskSearch.key]: findTaskSearch,
    [findRalphRunSearch.key]: findRalphRunSearch,
  },

  creates: {
    [createTaskAction.key]: createTaskAction,
    [sendMessageAction.key]: sendMessageAction,
    [startRalphAction.key]: startRalphAction,
    [cancelTaskAction.key]: cancelTaskAction,
  },
};
