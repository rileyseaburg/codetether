var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { isAllowedTenantProxyTarget, normalizeTenantApiUrl, TENANT_PROXY_TARGET_HEADER, } from '@/lib/tenant-api';
const BODYLESS_METHODS = new Set(['GET', 'HEAD']);
function buildHeaders(source) {
    const headers = new Headers(source);
    headers.delete('host');
    headers.delete('connection');
    headers.delete('content-length');
    headers.delete('cookie');
    headers.delete(TENANT_PROXY_TARGET_HEADER);
    return headers;
}
function resolveProxyTarget(session, request) {
    const sessionTarget = normalizeTenantApiUrl(typeof (session === null || session === void 0 ? void 0 : session.tenantApiUrl) === 'string' ? session.tenantApiUrl : undefined);
    const requestedTarget = normalizeTenantApiUrl(request.headers.get(TENANT_PROXY_TARGET_HEADER) || undefined);
    if (sessionTarget && requestedTarget && sessionTarget !== requestedTarget) {
        return null;
    }
    const target = sessionTarget || requestedTarget;
    if (!target || target.startsWith('/')) {
        return null;
    }
    return isAllowedTenantProxyTarget(target) ? target : null;
}
function handle(request, context) {
    return __awaiter(this, void 0, void 0, function* () {
        const session = (yield auth());
        const targetBase = resolveProxyTarget(session, request);
        if (!targetBase) {
            return NextResponse.json({
                error: session ? 'Invalid tenant proxy target' : 'Authentication required',
            }, { status: session ? 400 : 401 });
        }
        const { path } = yield context.params;
        const encodedPath = path.map((segment) => encodeURIComponent(segment)).join('/');
        const target = new URL(`${targetBase}/${encodedPath}`);
        target.search = request.nextUrl.search;
        const init = {
            method: request.method,
            headers: buildHeaders(request.headers),
            redirect: 'manual',
            cache: 'no-store',
        };
        if (!BODYLESS_METHODS.has(request.method)) {
            init.body = yield request.arrayBuffer();
        }
        try {
            const upstream = yield fetch(target, init);
            return new Response(upstream.body, {
                status: upstream.status,
                statusText: upstream.statusText,
                headers: upstream.headers,
            });
        }
        catch (error) {
            const message = error instanceof Error ? error.message : 'Tenant proxy request failed';
            return NextResponse.json({ error: message, target: target.toString() }, { status: 502 });
        }
    });
}
export const dynamic = 'force-dynamic';
export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
