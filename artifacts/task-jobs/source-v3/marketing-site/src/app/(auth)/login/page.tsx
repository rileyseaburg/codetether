// The login shell is auth-gated UI and must never be served from a long-lived
// prerender cache. Production returned `cache-control: s-maxage=31536000` with
// `x-nextjs-cache: HIT` for this route, so a stale pre-auth shell kept
// re-triggering the dashboard redirect and rendered as nonstop flicker.
export const dynamic = 'force-dynamic'
export const revalidate = 0

export { default } from './login-form'
