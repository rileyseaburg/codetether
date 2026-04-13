import { NextRequest } from 'next/server'
import { proxyA2ARequest } from '@/lib/a2a/proxy'

type RouteContext = { params: Promise<{ path: string[] }> }

async function handle(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params
  return proxyA2ARequest(request, path)
}

export const GET = handle
export const POST = handle
export const PUT = handle
export const PATCH = handle
export const DELETE = handle
export const OPTIONS = handle
export const HEAD = handle
