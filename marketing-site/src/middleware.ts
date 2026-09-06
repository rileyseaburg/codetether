import { auth } from '@/auth'
import { publicRequestOrigin } from '@/lib/request-origin'
import {
  NextResponse,
  type NextRequest,
  type NextFetchEvent,
  type NextMiddleware,
} from 'next/server'

const authorizeDashboard = auth((req) => {
  const { pathname, searchParams } = req.nextUrl

  // Allow bypass for E2E testing with special header or query param
  const cypressBypass =
    req.headers.get('x-cypress-test') === 'true' ||
    searchParams.get('cypress') === 'true'
  if (cypressBypass && process.env.NODE_ENV !== 'production') {
    return NextResponse.next()
  }

  // Protected routes that require authentication
  const protectedRoutes = ['/dashboard']

  const isProtectedRoute = protectedRoutes.some((route) =>
    pathname.startsWith(route),
  )

  // Check for custom auth token in cookie (for self-service users)
  const customToken = req.cookies.get('a2a_token')?.value
  const hasCustomAuth = !!customToken

  if (isProtectedRoute && !req.auth && !hasCustomAuth) {
    // Redirect to login if not authenticated via NextAuth OR custom token
    const loginUrl = new URL('/login', publicRequestOrigin(req) || req.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
})

// The installed Auth.js beta resolves wrappers asynchronously for lazy config.
// Its overload types this as an App Route, although runtime passes through the
// Next middleware event. Keep that compatibility cast at this boundary only.
export default async function middleware(
  request: NextRequest,
  event: NextFetchEvent,
) {
  const handler = (await authorizeDashboard) as unknown as NextMiddleware
  return handler(request, event)
}

export const config = {
  // Only run middleware on dashboard routes - skip public pages for better performance
  matcher: ['/dashboard/:path*'],
}
