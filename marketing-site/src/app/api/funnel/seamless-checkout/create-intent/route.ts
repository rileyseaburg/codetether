import { NextRequest, NextResponse } from 'next/server'

const API_BASE_URL =
  process.env.CODETETHER_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'

/**
 * Production compatibility proxy for the seamless-checkout funnel.
 *
 * The deployed checkout posts to this Next.js route. Proxy it to the A2A
 * billing API so Stripe Elements receives the SetupIntent client_secret instead
 * of surfacing a 500 before the embedded payment processor can render.
 */
export async function POST(request: NextRequest) {
  const authorization = request.headers.get('authorization')

  if (!authorization) {
    return NextResponse.json({ detail: 'Missing authorization header' }, { status: 401 })
  }

  const upstream = await fetch(`${API_BASE_URL}/v1/billing/create-intent`, {
    method: 'POST',
    headers: {
      authorization,
      'content-type': 'application/json',
    },
    cache: 'no-store',
  })

  const text = await upstream.text()
  let body: unknown
  try {
    body = text ? JSON.parse(text) : {}
  } catch {
    body = { detail: text || 'Billing intent request failed' }
  }

  return NextResponse.json(body, { status: upstream.status })
}
