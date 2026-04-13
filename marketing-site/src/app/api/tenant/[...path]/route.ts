import { NextRequest, NextResponse } from 'next/server'

import { auth } from '@/auth'
import {
  isAllowedTenantProxyTarget,
  normalizeTenantApiUrl,
  TENANT_PROXY_TARGET_HEADER,
} from '@/lib/tenant-api'

const BODYLESS_METHODS = new Set(['GET', 'HEAD'])

type RouteContext = { params: Promise<{ path: string[] }> }

function buildHeaders(source: Headers): Headers {
  const headers = new Headers(source)
  headers.delete('host')
  headers.delete('connection')
  headers.delete('content-length')
  headers.delete('cookie')
  headers.delete(TENANT_PROXY_TARGET_HEADER)
  return headers
}

function resolveProxyTarget(
  session: any,
  request: NextRequest
): string | null {
  const sessionTarget = normalizeTenantApiUrl(
    typeof session?.tenantApiUrl === 'string' ? session.tenantApiUrl : undefined
  )
  const requestedTarget = normalizeTenantApiUrl(
    request.headers.get(TENANT_PROXY_TARGET_HEADER) || undefined
  )

  if (sessionTarget && requestedTarget && sessionTarget !== requestedTarget) {
    return null
  }

  const target = sessionTarget || requestedTarget
  if (!target || target.startsWith('/')) {
    return null
  }

  return isAllowedTenantProxyTarget(target) ? target : null
}

async function handle(
  request: NextRequest,
  context: RouteContext
): Promise<Response> {
  const session = (await auth()) as any
  const targetBase = resolveProxyTarget(session, request)

  if (!targetBase) {
    return NextResponse.json(
      {
        error: session ? 'Invalid tenant proxy target' : 'Authentication required',
      },
      { status: session ? 400 : 401 }
    )
  }

  const { path } = await context.params
  const encodedPath = path.map((segment) => encodeURIComponent(segment)).join('/')
  const target = new URL(`${targetBase}/${encodedPath}`)
  target.search = request.nextUrl.search

  const init: RequestInit = {
    method: request.method,
    headers: buildHeaders(request.headers),
    redirect: 'manual',
    cache: 'no-store',
  }

  if (!BODYLESS_METHODS.has(request.method)) {
    init.body = await request.arrayBuffer()
  }

  try {
    const upstream = await fetch(target, init)
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    })
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Tenant proxy request failed'
    return NextResponse.json(
      { error: message, target: target.toString() },
      { status: 502 }
    )
  }
}

export const dynamic = 'force-dynamic'

export const GET = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const OPTIONS = handle
export const HEAD = handle
