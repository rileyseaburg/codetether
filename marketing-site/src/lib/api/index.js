/**
 * Environment-aware API client
 * Auto-generated SDK from OpenAPI spec via @hey-api/openapi-ts
 */
import { client } from './generated/client.gen';
import { getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet, listWorkspacesV1AgentWorkspacesListGet, listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet, registerWorkspaceV1AgentWorkspacesPost, triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost, unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete, } from './generated';
// Environment-aware base URL configuration
const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl)
        return envUrl;
    // Default based on environment
    if (process.env.NODE_ENV === 'development') {
        return 'http://localhost:8000';
    }
    return 'https://api.codetether.run';
};
// Configure the client with environment-aware base URL
client.setConfig({ baseUrl: getBaseUrl() });
// Module-level auth state — read by the interceptor registered below
let _authToken;
let _tenantId;
// Register a SINGLE interceptor at module load time.
// It always runs, injecting whatever token is currently set.
client.interceptors.request.use((request) => {
    if (_authToken) {
        request.headers.set('Authorization', `Bearer ${_authToken}`);
    }
    if (_tenantId) {
        request.headers.set('X-Tenant-ID', _tenantId);
    }
    return request;
});
/**
 * Set the auth token for all SDK API calls.
 * Updates the module-level token that the always-registered interceptor reads.
 * Call with no arguments to clear auth.
 */
export function setApiAuthToken(token, tenantId) {
    _authToken = token;
    _tenantId = tenantId;
}
/** Returns true when the SDK client has an auth token configured. */
export function hasApiAuthToken() {
    return !!_authToken;
}
/**
 * Backward-compat exports for legacy "codebases" naming used by dashboard pages.
 * The API now uses "workspaces", but these wrappers avoid breaking existing callers.
 */
export const listCodebasesV1AgentCodebasesListGet = listWorkspacesV1AgentWorkspacesListGet;
export const triggerAgentV1AgentCodebasesCodebaseIdTriggerPost = (options) => {
    var _a, _b, _c, _d;
    const workspaceId = (_d = (_b = (_a = options === null || options === void 0 ? void 0 : options.path) === null || _a === void 0 ? void 0 : _a.workspace_id) !== null && _b !== void 0 ? _b : (_c = options === null || options === void 0 ? void 0 : options.path) === null || _c === void 0 ? void 0 : _c.codebase_id) !== null && _d !== void 0 ? _d : '';
    return triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost(Object.assign(Object.assign({}, options), { path: { workspace_id: workspaceId } }));
};
export const registerCodebaseV1AgentCodebasesPost = registerWorkspaceV1AgentWorkspacesPost;
export const unregisterCodebaseV1AgentCodebasesCodebaseIdDelete = (options) => {
    var _a, _b, _c, _d;
    const workspaceId = (_d = (_b = (_a = options === null || options === void 0 ? void 0 : options.path) === null || _a === void 0 ? void 0 : _a.workspace_id) !== null && _b !== void 0 ? _b : (_c = options === null || options === void 0 ? void 0 : options.path) === null || _c === void 0 ? void 0 : _c.codebase_id) !== null && _d !== void 0 ? _d : '';
    return unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete(Object.assign(Object.assign({}, options), { path: { workspace_id: workspaceId } }));
};
export const listSessionsV1AgentCodebasesCodebaseIdSessionsGet = (options) => {
    var _a, _b, _c, _d;
    const workspaceId = (_d = (_b = (_a = options === null || options === void 0 ? void 0 : options.path) === null || _a === void 0 ? void 0 : _a.workspace_id) !== null && _b !== void 0 ? _b : (_c = options === null || options === void 0 ? void 0 : options.path) === null || _c === void 0 ? void 0 : _c.codebase_id) !== null && _d !== void 0 ? _d : '';
    return listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet(Object.assign(Object.assign({}, options), { path: { workspace_id: workspaceId } }));
};
export const getSessionMessagesByIdV1AgentCodebasesCodebaseIdSessionsSessionIdMessagesGet = (options) => {
    var _a, _b, _c, _d;
    const workspaceId = (_d = (_b = (_a = options === null || options === void 0 ? void 0 : options.path) === null || _a === void 0 ? void 0 : _a.workspace_id) !== null && _b !== void 0 ? _b : (_c = options === null || options === void 0 ? void 0 : options.path) === null || _c === void 0 ? void 0 : _c.codebase_id) !== null && _d !== void 0 ? _d : '';
    return getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet(Object.assign(Object.assign({}, options), { path: {
            workspace_id: workspaceId,
            session_id: options.path.session_id,
        } }));
};
// Re-export everything from generated SDK
export * from './generated';
export { client };
