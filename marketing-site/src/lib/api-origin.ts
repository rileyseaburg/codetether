/** Enforce remote HTTPS without breaking a same-origin local API proxy. */
export function secureApiUrl(value: string, browserOrigin?: string): string {
  if (!value.startsWith('http://')) return value
  try {
    const url = new URL(value)
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if (loopback && url.origin === browserOrigin) return value
  } catch {
    // Preserve the existing HTTPS policy for malformed/non-loopback targets.
  }
  return value.replace(/^http:/, 'https:')
}
