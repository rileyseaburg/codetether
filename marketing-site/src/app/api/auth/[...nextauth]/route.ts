import { handlers } from '@/auth'
import { NextRequest } from 'next/server'
import { publicRequestUrl } from '@/lib/request-origin'

function externalRequest(request: NextRequest): NextRequest | null {
  const url = publicRequestUrl(request)
  if (!url) return null
  return new NextRequest(url, {
    method: request.method,
    headers: request.headers,
    body:
      request.method === 'GET' || request.method === 'HEAD'
        ? undefined
        : request.body,
    signal: request.signal,
  })
}

export async function GET(request: NextRequest) {
  const normalized = externalRequest(request)
  if (!normalized)
    return new Response('Unrecognized authentication host', { status: 400 })
  return handlers.GET(normalized)
}

export async function POST(request: NextRequest) {
  const normalized = externalRequest(request)
  if (!normalized)
    return new Response('Unrecognized authentication host', { status: 400 })
  return handlers.POST(normalized)
}
