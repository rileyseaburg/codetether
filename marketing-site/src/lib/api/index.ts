/**
 * Environment-aware API client
 * Auto-generated SDK from OpenAPI spec via @hey-api/openapi-ts
 */

import { client } from './generated/client.gen'
import {
  getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet,
  listWorkspacesV1AgentWorkspacesListGet,
  listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet,
  registerWorkspaceV1AgentWorkspacesPost,
  triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost,
  unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete,
} from './generated'

// Environment-aware base URL configuration
const getBaseUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL
  if (envUrl) return envUrl

  // Default based on environment
  if (process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000'
  }
  return 'https://api.codetether.run'
}

// Configure the client with environment-aware base URL
client.setConfig({ baseUrl: getBaseUrl() })

// Module-level auth state — read by the interceptor registered below
let _authToken: string | undefined
let _tenantId: string | undefined

// Register a SINGLE interceptor at module load time.
// It always runs, injecting whatever token is currently set.
client.interceptors.request.use((request) => {
  if (_authToken) {
    request.headers.set('Authorization', `Bearer ${_authToken}`)
  }
  if (_tenantId) {
    request.headers.set('X-Tenant-ID', _tenantId)
  }
  return request
})

/**
 * Set the auth token for all SDK API calls.
 * Updates the module-level token that the always-registered interceptor reads.
 * Call with no arguments to clear auth.
 */
export function setApiAuthToken(token?: string, tenantId?: string) {
  _authToken = token
  _tenantId = tenantId
}

/** Returns true when the SDK client has an auth token configured. */
export function hasApiAuthToken(): boolean {
  return !!_authToken
}

/**
 * Backward-compat exports for legacy "codebases" naming used by dashboard pages.
 * The API now uses "workspaces", but these wrappers avoid breaking existing callers.
 */
export const listCodebasesV1AgentCodebasesListGet =
  listWorkspacesV1AgentWorkspacesListGet

type LegacyTriggerOptions = Parameters<
  typeof triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost
>[0] & {
  path: {
    codebase_id?: string
    workspace_id?: string
  }
}

export const triggerAgentV1AgentCodebasesCodebaseIdTriggerPost = (
  options: LegacyTriggerOptions,
) => {
  const workspaceId =
    options?.path?.workspace_id ?? options?.path?.codebase_id ?? ''
  return triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost({
    ...(options as any),
    path: { workspace_id: workspaceId },
  })
}

export const registerCodebaseV1AgentCodebasesPost =
  registerWorkspaceV1AgentWorkspacesPost

type LegacyUnregisterOptions = Parameters<
  typeof unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete
>[0] & {
  path: {
    codebase_id?: string
    workspace_id?: string
  }
}

export const unregisterCodebaseV1AgentCodebasesCodebaseIdDelete = (
  options: LegacyUnregisterOptions,
) => {
  const workspaceId =
    options?.path?.workspace_id ?? options?.path?.codebase_id ?? ''
  return unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete({
    ...(options as any),
    path: { workspace_id: workspaceId },
  })
}

type LegacyListSessionsOptions = Parameters<
  typeof listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet
>[0] & {
  path: {
    codebase_id?: string
    workspace_id?: string
  }
}

export const listSessionsV1AgentCodebasesCodebaseIdSessionsGet = (
  options: LegacyListSessionsOptions,
) => {
  const workspaceId =
    options?.path?.workspace_id ?? options?.path?.codebase_id ?? ''
  return listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet({
    ...(options as any),
    path: { workspace_id: workspaceId },
  })
}

type LegacySessionMessagesOptions = Parameters<
  typeof getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet
>[0] & {
  path: {
    codebase_id?: string
    workspace_id?: string
    session_id: string
  }
}

export const getSessionMessagesByIdV1AgentCodebasesCodebaseIdSessionsSessionIdMessagesGet =
  (options: LegacySessionMessagesOptions) => {
    const workspaceId =
      options?.path?.workspace_id ?? options?.path?.codebase_id ?? ''
    return getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet(
      {
        ...(options as any),
        path: {
          workspace_id: workspaceId,
          session_id: options.path.session_id,
        },
      },
    )
  }

// Re-export everything from generated SDK
export * from './generated'

export { client }
