export const dynamic = 'force-dynamic'

/** Public, non-secret build identity for deployment smoke checks. */
export function GET() {
  return Response.json(
    { revision: process.env.NEXT_PUBLIC_SOURCE_REVISION || 'development' },
    { headers: { 'Cache-Control': 'no-store, max-age=0' } },
  )
}
