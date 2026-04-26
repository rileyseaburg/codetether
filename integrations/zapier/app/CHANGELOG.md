# Changelog

## 1.2.0

Expanded Zapier integration with new actions, searches, and triggers covering agents, codebases, cron jobs, PRD generation, billing, and more.

### New Actions (Creates)
- **send_message_async** - Send a message asynchronously (fire-and-forget). Returns task_id for tracking.
- **send_to_agent** - Send a message to a specific named agent. Queues until the agent is available.
- **cancel_ralph_run** - Cancel a running Ralph autonomous development run.
- **create_cronjob** - Create a scheduled cron job that triggers tasks on a recurring schedule.
- **prd_chat** - Chat with AI to generate a Product Requirements Document with user stories.

### New Searches
- **discover_agents** - Find registered worker agents in the network (filter by name).
- **list_codebases** - Find registered codebases for targeting tasks and Ralph runs.
- **list_ralph_runs** - List Ralph runs filtered by status to monitor autonomous development.
- **list_models** - Discover available AI models from registered workers (filter by provider).
- **get_usage_summary** - Get token usage and billing summary for the current or a specific month.

### New Triggers
- **task_completed** - Triggers when a task finishes successfully. Chain follow-up actions.
- **task_failed** - Triggers when a task fails. Set up alerts or retry logic.

## 1.1.0

Full CLI-based Zapier integration for CodeTether.

### New Features
- New trigger/new_task - Fires when tasks are created
- New create/create_task - Create tasks in the queue
- New create/send_message - Send messages to AI agents
- New create/cancel_task - Cancel pending tasks
- New search/find_task - Find tasks by ID or status

### Authentication
- OAuth2 authentication with Keycloak
- Automatic token refresh support

## 1.0.0

Initial release created via Zapier Platform UI.
