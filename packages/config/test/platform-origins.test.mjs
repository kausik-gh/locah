/**
 * The cookie-domain rules decide whether a signed-in person reaches Workspace
 * at all, and they fail invisibly when they are wrong: the browser accepts the
 * response, drops the cookie, and the next request looks like a fresh visitor.
 * Nothing in a build or a typecheck catches that, so it is asserted here.
 *
 * Run with `node --test` against the built output (`pnpm build` first).
 */

import test from 'node:test'
import assert from 'node:assert/strict'

const mod = await import('../dist/platform-origins.js')
const {
  resolvePlatformOrigins,
  supportsSharedSessionCookie,
  businessSlugFromHost,
  businessSiteUrl,
  platformUrl,
} = mod

/** Run `fn` with exactly the given platform env vars set. */
function withEnv(vars, fn) {
  const keys = [
    'NEXT_PUBLIC_PLATFORM_DOMAIN',
    'NEXT_PUBLIC_SESSION_COOKIE_DOMAIN',
    'NEXT_PUBLIC_WEB_URL',
    'NEXT_PUBLIC_WORKSPACE_URL',
    'NEXT_PUBLIC_ADMIN_URL',
    'NEXT_PUBLIC_API_URL',
  ]
  const saved = Object.fromEntries(keys.map((k) => [k, process.env[k]]))
  keys.forEach((k) => delete process.env[k])
  Object.entries(vars).forEach(([k, v]) => {
    process.env[k] = v
  })
  try {
    return fn()
  } finally {
    keys.forEach((k) => {
      if (saved[k] === undefined) delete process.env[k]
      else process.env[k] = saved[k]
    })
  }
}

test('a public suffix cannot carry a shared session cookie', () => {
  assert.equal(supportsSharedSessionCookie('railway.app'), false)
  assert.equal(supportsSharedSessionCookie('locah-web-production.up.railway.app'), false)
  assert.equal(supportsSharedSessionCookie('pages.dev'), false)
})

test('a single label, an IP or nothing cannot carry one either', () => {
  assert.equal(supportsSharedSessionCookie('localhost'), false)
  assert.equal(supportsSharedSessionCookie('internal'), false)
  assert.equal(supportsSharedSessionCookie('203.0.113.7'), false)
  assert.equal(supportsSharedSessionCookie(null), false)
})

test('a registrable domain can', () => {
  assert.equal(supportsSharedSessionCookie('locah.in'), true)
  assert.equal(supportsSharedSessionCookie('staging.locah.in'), true)
})

test('provider-generated service domains get no shared cookie domain', () => {
  withEnv(
    {
      NEXT_PUBLIC_WEB_URL: 'https://locah-web-production.up.railway.app',
      NEXT_PUBLIC_WORKSPACE_URL: 'https://locah-workspace-production.up.railway.app',
    },
    () => {
      const origins = resolvePlatformOrigins()
      assert.equal(origins.sessionCookieDomain, null)
      assert.equal(origins.web, 'https://locah-web-production.up.railway.app')
      assert.equal(origins.workspace, 'https://locah-workspace-production.up.railway.app')
    }
  )
})

test('naming a Railway service domain as the platform domain is refused', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah-web-production.up.railway.app' }, () => {
    assert.equal(resolvePlatformOrigins().sessionCookieDomain, null)
  })
})

test('a platform domain derives every surface and the shared cookie', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah.in' }, () => {
    const o = resolvePlatformOrigins()
    assert.equal(o.web, 'https://locah.in')
    assert.equal(o.workspace, 'https://app.locah.in')
    assert.equal(o.admin, 'https://admin.locah.in')
    assert.equal(o.api, 'https://api.locah.in')
    assert.equal(o.sessionCookieDomain, '.locah.in')
  })
})

test('a per-surface override beats the derived origin', () => {
  withEnv(
    {
      NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah.in',
      NEXT_PUBLIC_API_URL: 'https://api.locah-staging.in',
    },
    () => {
      const o = resolvePlatformOrigins()
      assert.equal(o.api, 'https://api.locah-staging.in')
      assert.equal(o.workspace, 'https://app.locah.in')
      // An override names one surface; it does not disband the shared session.
      assert.equal(o.sessionCookieDomain, '.locah.in')
    }
  )
})

test('a pasted URL is accepted where a domain is expected', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'https://LOCAH.in/' }, () => {
    assert.equal(resolvePlatformOrigins().sessionCookieDomain, '.locah.in')
  })
})

test('with nothing configured, local development still resolves', () => {
  withEnv({}, () => {
    const o = resolvePlatformOrigins()
    assert.equal(o.web, 'http://localhost:3000')
    assert.equal(o.workspace, 'http://localhost:3001')
    assert.equal(o.admin, 'http://localhost:3002')
    assert.equal(o.sessionCookieDomain, null)
    assert.equal(platformUrl('workspace', '/b/abc'), 'http://localhost:3001/b/abc')
  })
})

test('a Business subdomain resolves to its slug', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah.in' }, () => {
    assert.equal(businessSlugFromHost('saffron-house.locah.in'), 'saffron-house')
    assert.equal(businessSlugFromHost('saffron-house.locah.in:443'), 'saffron-house')
  })
})

test('platform subdomains are never read as a Business', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah.in' }, () => {
    for (const host of ['app.locah.in', 'admin.locah.in', 'api.locah.in', 'www.locah.in', 'locah.in']) {
      assert.equal(businessSlugFromHost(host), null, host)
    }
    // A nested label is not a Business website.
    assert.equal(businessSlugFromHost('a.b.locah.in'), null)
    // Nor is an unrelated domain that merely ends in something similar.
    assert.equal(businessSlugFromHost('evil-locah.in'), null)
    assert.equal(businessSlugFromHost('saffron.notlocah.in'), null)
  })
})

test('without a platform domain, no host is a Business subdomain', () => {
  withEnv({ NEXT_PUBLIC_WEB_URL: 'https://locah-web-production.up.railway.app' }, () => {
    assert.equal(businessSlugFromHost('saffron-house.locah-web-production.up.railway.app'), null)
  })
})

test('a Business website URL follows whichever shape is available', () => {
  withEnv({ NEXT_PUBLIC_PLATFORM_DOMAIN: 'locah.in' }, () => {
    assert.equal(businessSiteUrl('saffron-house'), 'https://saffron-house.locah.in')
    assert.equal(businessSiteUrl('saffron-house', '/book'), 'https://saffron-house.locah.in/book')
  })
  withEnv({ NEXT_PUBLIC_WEB_URL: 'https://locah-web-production.up.railway.app' }, () => {
    assert.equal(
      businessSiteUrl('saffron-house'),
      'https://locah-web-production.up.railway.app/saffron-house'
    )
    assert.equal(
      businessSiteUrl('saffron-house', '/book'),
      'https://locah-web-production.up.railway.app/saffron-house/book'
    )
  })
})
