import { NextRequest, NextResponse } from 'next/server'

const BODYLESS_METHODS = new Set(['GET', 'HEAD'])

function resolveA2ABackend(): string | null {
  const baseUrl = process.env.A2A_API_BACKEND || process.env.API_URL || null
  if (!baseUrl || baseUrl.startsWith('/')) return null
  return baseUrl.replace(/\/+$/, '')
}

function buildHeaders(source: Headers): Headers {
  const headers = new Headers(source)
  headers.delete('host')
  headers.delete('connection')
  headers.delete('content-length')
  return headers
}

export async function proxyA2ARequest(
  request: NextRequest,
  path: string[],
): Promise<Response> {
  const backend = resolveA2ABackend()
  if (!backend) {
    return NextResponse.json({ error: 'A2A_API_BACKEND or API_URL must be set for /api/v1 proxy' }, { status: 500 })
  }
  const target = `${backend}/v1/${path.join('/')}${request.nextUrl.search}`
  const init: RequestInit = {
    method: request.method,
    headers: buildHeaders(request.headers),
    redirect: 'manual',
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
    const message = error instanceof Error ? error.message : 'Proxy request failed'
    return NextResponse.json({ error: message, target }, { status: 502 })
  }
}
