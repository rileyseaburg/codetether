type RequestOriginInput = { url: string; headers: Pick<Headers, 'get'> }

/** Resolve only application-owned origins behind the trusted ingress proxy. */
export function publicRequestOrigin(
  request: RequestOriginInput,
): string | null {
  const forwardedProtocol = request.headers
    .get('x-forwarded-proto')
    ?.split(',')[0]
    .trim()
  for (const raw of [
    request.headers.get('x-forwarded-host'),
    request.headers.get('host'),
  ]) {
    if (!raw) continue
    const host = raw.split(',')[0].trim()
    try {
      const url = new URL(`https://${host}`)
      if (
        url.username ||
        url.password ||
        url.pathname !== '/' ||
        url.search ||
        url.hash
      )
        continue
      const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(
        url.hostname,
      )
      const owned =
        url.hostname === 'codetether.run' ||
        url.hostname.endsWith('.codetether.run')
      if (!loopback && (!owned || url.port)) continue
      if (
        loopback &&
        forwardedProtocol !== 'https:' &&
        forwardedProtocol !== 'https'
      ) {
        url.protocol = new URL(request.url).protocol
      }
      return url.origin
    } catch {
      // Ignore malformed forwarded hosts and try the actual Host header.
    }
  }
  return null
}

/** Next standalone may expose localhost:3000 in request.url after TLS offload. */
export function publicRequestUrl(request: RequestOriginInput): URL | null {
  const origin = publicRequestOrigin(request)
  if (!origin) return null
  const incoming = new URL(request.url)
  return new URL(incoming.pathname + incoming.search, origin)
}
