import { platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

/**
 * The customer's door to a quote, on the platform's own address.
 *
 * The document itself is rendered by the API (`/v1/public/quotes/{token}`),
 * which is the right place for it — it reads the quote, applies the share-token
 * policy, and knows the commercial truth. But the link a business sends to a
 * customer should not be an `api.` hostname: it reads as internal, it would not
 * survive the API moving, and it splits the platform across two names in front
 * of someone who has no account and no reason to see either.
 *
 * So this proxies rather than redirects. The rendered document posts its accept
 * and decline buttons back to its own URL with no `action`, which means it works
 * unchanged at whatever address is serving it — the decision lands here and is
 * forwarded on with the token intact.
 */

const UPSTREAM = () => platformUrl('api')

/** Headers worth carrying back: the document's own caching and indexing rules. */
const PASS_THROUGH = ['content-type', 'cache-control', 'x-robots-tag']

async function forward(
  token: string,
  init: { method: string; body?: BodyInit; contentType?: string | null }
): Promise<Response> {
  const target = `${UPSTREAM()}/v1/public/quotes/${encodeURIComponent(token)}`

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: init.method,
      headers: init.contentType ? { 'Content-Type': init.contentType } : undefined,
      body: init.body,
      cache: 'no-store',
      redirect: 'manual',
    })
  } catch {
    // The customer is holding a link someone sent them; an unreachable API is
    // our problem, not a reason to show them a stack trace.
    return new Response(unavailable(), {
      status: 503,
      headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
    })
  }

  const headers = new Headers()
  for (const name of PASS_THROUGH) {
    const value = upstream.headers.get(name)
    if (value) headers.set(name, value)
  }
  // A priced offer addressed to one person is never cached or indexed, whatever
  // the upstream said.
  headers.set('Cache-Control', 'no-store, private')
  headers.set('X-Robots-Tag', 'noindex, nofollow')

  return new Response(await upstream.text(), { status: upstream.status, headers })
}

export async function GET(_request: Request, { params }: { params: { token: string } }) {
  return forward(params.token, { method: 'GET' })
}

export async function POST(request: Request, { params }: { params: { token: string } }) {
  // The document posts a plain form; hand the body through exactly as received
  // so the API sees the same request it would have got directly.
  const body = await request.text()
  return forward(params.token, {
    method: 'POST',
    body,
    contentType: request.headers.get('content-type'),
  })
}

function unavailable(): string {
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quote unavailable</title></head>
<body style="margin:0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;background:#f7f4ef;color:#1b1f3b;">
<div style="max-width:32rem;margin:18vh auto;padding:0 1.5rem;">
<h1 style="font-size:1.5rem;margin:0 0 .6rem;">This quote cannot be loaded right now</h1>
<p style="line-height:1.6;color:#6b6862;margin:0;">Something on our side is not responding. Your link is still valid — try again in a few minutes, or contact the business directly.</p>
</div></body></html>`
}
