// Local stand-in for the Supabase Auth "who is this token" endpoint.
// Test-only: answers /auth/v1/user from the (locally minted, HS256) token's
// own claims so @supabase/ssr's getClaims()/getUser() succeed on localhost.
// The FastAPI side still verifies the token signature itself.
import http from 'node:http'

const port = Number(process.env.PORT || 54321)

function claims(auth) {
  const token = (auth || '').replace(/^Bearer\s+/i, '')
  const part = token.split('.')[1]
  if (!part) return null
  try {
    return JSON.parse(Buffer.from(part.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
  } catch {
    return null
  }
}

http
  .createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.setHeader('Access-Control-Allow-Headers', '*')
    if (req.method === 'OPTIONS') return res.writeHead(204).end()
    const url = new URL(req.url, `http://localhost:${port}`)
    if (url.pathname === '/auth/v1/user') {
      const c = claims(req.headers.authorization)
      if (!c) return res.writeHead(401, { 'content-type': 'application/json' }).end('{"msg":"no token"}')
      return res.writeHead(200, { 'content-type': 'application/json' }).end(
        JSON.stringify({
          id: c.sub, aud: 'authenticated', role: 'authenticated', email: c.email,
          email_confirmed_at: new Date().toISOString(), app_metadata: { provider: 'email' },
          user_metadata: {}, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        })
      )
    }
    if (url.pathname.endsWith('/jwks.json')) {
      return res.writeHead(200, { 'content-type': 'application/json' }).end('{"keys":[]}')
    }
    res.writeHead(404, { 'content-type': 'application/json' }).end('{"msg":"not in the local mock"}')
  })
  .listen(port, () => console.log(`mock auth on ${port}`))
