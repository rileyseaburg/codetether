'use client';
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { useSession, signOut } from 'next-auth/react';
import { useMemo, useCallback, useEffect, useRef } from 'react';
import { hasDedicatedTenantInstance, getSharedTenantApiUrl, normalizeTenantApiUrl, } from '@/lib/tenant-api';
function decodeJwtPayload(token) {
    try {
        const parts = token.split('.');
        if (parts.length < 2)
            return {};
        const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const json = decodeURIComponent(atob(base64)
            .split('')
            .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
            .join(''));
        return JSON.parse(json);
    }
    catch (_a) {
        return {};
    }
}
function extractTenantFromToken(token) {
    if (!token)
        return {};
    const payload = decodeJwtPayload(token);
    return {
        tenantId: payload.tenant_id ||
            payload.tenantId ||
            payload['codetether:tenant_id'] ||
            payload.tid,
        tenantSlug: payload.tenant_slug ||
            payload.tenantSlug ||
            payload['codetether:tenant_slug'],
    };
}
/**
 * Hook to get tenant-aware API configuration.
 *
 * Returns the control-plane API URL used by the dashboard.
 *
 * Dashboard/operator flows stay on the shared API until tenant runtimes expose
 * the same compatibility surface.
 *
 * Usage:
 * ```tsx
 * const { apiUrl, tenantId, tenantSlug, tenantFetch } = useTenantApi()
 *
 * // Make API calls to the correct endpoint
 * const data = await tenantFetch('/v1/tasks')
 * ```
 */
export function useTenantApi() {
    const { data: session, status } = useSession();
    const unauthorizedHandledRef = useRef(false);
    const typedSession = session;
    const localUser = typeof window !== 'undefined'
        ? (() => {
            try {
                const raw = localStorage.getItem('a2a_user');
                return raw ? JSON.parse(raw) : undefined;
            }
            catch (_a) {
                return undefined;
            }
        })()
        : undefined;
    const tenantConfig = useMemo(() => {
        var _a, _b, _c, _d;
        const sharedApiUrl = getSharedTenantApiUrl();
        const sessionToken = typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken;
        const storedToken = typeof window !== 'undefined'
            ? localStorage.getItem('a2a_token') || localStorage.getItem('access_token') || undefined
            : undefined;
        const authToken = sessionToken || storedToken;
        const tokenTenant = extractTenantFromToken(authToken);
        const resolvedTenantId = (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantId) ||
            (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenant_id) ||
            ((_a = typedSession === null || typedSession === void 0 ? void 0 : typedSession.user) === null || _a === void 0 ? void 0 : _a.tenantId) ||
            ((_b = typedSession === null || typedSession === void 0 ? void 0 : typedSession.user) === null || _b === void 0 ? void 0 : _b.tenant_id) ||
            (localUser === null || localUser === void 0 ? void 0 : localUser.tenantId) ||
            (localUser === null || localUser === void 0 ? void 0 : localUser.tenant_id) ||
            tokenTenant.tenantId;
        const resolvedTenantSlug = (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantSlug) ||
            (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenant_slug) ||
            ((_c = typedSession === null || typedSession === void 0 ? void 0 : typedSession.user) === null || _c === void 0 ? void 0 : _c.tenantSlug) ||
            ((_d = typedSession === null || typedSession === void 0 ? void 0 : typedSession.user) === null || _d === void 0 ? void 0 : _d.tenant_slug) ||
            (localUser === null || localUser === void 0 ? void 0 : localUser.tenantSlug) ||
            (localUser === null || localUser === void 0 ? void 0 : localUser.tenant_slug) ||
            tokenTenant.tenantSlug;
        if (!typedSession && !authToken) {
            return {
                apiUrl: sharedApiUrl,
                upstreamApiUrl: sharedApiUrl,
                tenantId: undefined,
                tenantSlug: undefined,
                hasDedicatedInstance: false,
                proxyingTenantApi: false,
            };
        }
        const upstreamApiUrl = normalizeTenantApiUrl((typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantApiUrl) || sharedApiUrl) ||
            sharedApiUrl;
        const hasDedicatedInstance = hasDedicatedTenantInstance(upstreamApiUrl, resolvedTenantSlug);
        return {
            // Keep dashboard/control-plane calls on the shared API until tenant
            // runtimes expose the same compatibility surface.
            apiUrl: sharedApiUrl,
            upstreamApiUrl,
            tenantId: resolvedTenantId,
            tenantSlug: resolvedTenantSlug,
            hasDedicatedInstance,
            proxyingTenantApi: false,
        };
    }, [localUser === null || localUser === void 0 ? void 0 : localUser.tenantId, localUser === null || localUser === void 0 ? void 0 : localUser.tenantSlug, localUser === null || localUser === void 0 ? void 0 : localUser.tenant_id, localUser === null || localUser === void 0 ? void 0 : localUser.tenant_slug, typedSession]);
    useEffect(() => {
        unauthorizedHandledRef.current = false;
    }, [typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken]);
    /**
     * Tenant-aware fetch function.
     * Automatically adds auth headers and routes to the dashboard control plane.
     */
    const tenantFetch = useCallback((path_1, ...args_1) => __awaiter(this, [path_1, ...args_1], void 0, function* (path, options = {}) {
        const headers = Object.assign({ 'Content-Type': 'application/json' }, (options.headers || {}));
        const sessionToken = typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken;
        const storedToken = typeof window !== 'undefined'
            ? localStorage.getItem('a2a_token') || localStorage.getItem('access_token')
            : null;
        const authToken = sessionToken || storedToken;
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        if (tenantConfig.tenantId) {
            headers['X-Tenant-ID'] = tenantConfig.tenantId;
        }
        try {
            const normalizedPath = path.startsWith('http') || path.startsWith('/')
                ? path
                : `/${path}`;
            const url = normalizedPath.startsWith('http')
                ? normalizedPath
                : `${tenantConfig.apiUrl}${normalizedPath}`;
            const response = yield fetch(url, Object.assign(Object.assign({}, options), { headers }));
            if (response.status === 401) {
                if (!unauthorizedHandledRef.current) {
                    unauthorizedHandledRef.current = true;
                    if (typeof window !== 'undefined') {
                        localStorage.removeItem('a2a_token');
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('a2a_refresh_token');
                        localStorage.removeItem('a2a_session');
                        localStorage.removeItem('a2a_user');
                        document.cookie = 'a2a_token=; path=/; max-age=0';
                    }
                    signOut({ callbackUrl: '/login?error=session_expired' }).catch(() => { });
                }
                return { error: 'Session expired. Please sign in again.' };
            }
            if (!response.ok) {
                const errorText = yield response.text();
                const isHtmlResponse = /^\s*<!doctype html/i.test(errorText) ||
                    /^\s*<html/i.test(errorText) ||
                    errorText.includes('<!DOCTYPE html>');
                if (isHtmlResponse) {
                    const usingApiProxy = tenantConfig.apiUrl.startsWith('/api');
                    if (response.status === 404 && usingApiProxy) {
                        return {
                            error: 'API proxy route returned 404 HTML instead of JSON. Ensure Next.js rewrite is configured with A2A_API_BACKEND and restart `next dev`.',
                        };
                    }
                    return {
                        error: `Unexpected HTML response from API (HTTP ${response.status}). Check NEXT_PUBLIC_API_URL and Next.js rewrites.`,
                    };
                }
                let detail = errorText;
                try {
                    const parsed = JSON.parse(errorText);
                    detail = (parsed === null || parsed === void 0 ? void 0 : parsed.detail) || (parsed === null || parsed === void 0 ? void 0 : parsed.message) || errorText;
                }
                catch (_a) {
                    // Non-JSON error payload.
                }
                if (typeof detail === 'string' && detail.toLowerCase().includes('no tenant associated')) {
                    return {
                        error: 'No tenant is associated with this account yet. Complete tenant setup in registration/admin before using tenant-scoped features.',
                    };
                }
                return { error: detail || `HTTP ${response.status}` };
            }
            const data = yield response.json();
            return { data };
        }
        catch (err) {
            return { error: err instanceof Error ? err.message : 'Unknown error' };
        }
    }), [typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken, tenantConfig]);
    return Object.assign(Object.assign({}, tenantConfig), { tenantFetch, isLoading: status === 'loading', isAuthenticated: status === 'authenticated' ||
            (typeof window !== 'undefined' &&
                Boolean(localStorage.getItem('a2a_token') || localStorage.getItem('access_token'))), hasTenant: Boolean(tenantConfig.tenantId) });
}
/**
 * Get headers for tenant-aware API calls.
 * Includes the access token and tenant context.
 */
export function useTenantHeaders() {
    const { data: session } = useSession();
    const typedSession = session;
    return useMemo(() => {
        const headers = {
            'Content-Type': 'application/json',
        };
        if (typedSession === null || typedSession === void 0 ? void 0 : typedSession.accessToken) {
            headers['Authorization'] = `Bearer ${typedSession.accessToken}`;
        }
        if (typedSession === null || typedSession === void 0 ? void 0 : typedSession.tenantId) {
            headers['X-Tenant-ID'] = typedSession.tenantId;
        }
        return headers;
    }, [typedSession]);
}
