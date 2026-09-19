/**
 * Where the LOCAH platform lives, and how a session spans it.
 *
 * Document 10 §12 already fixes the shape, so nothing here is a new decision:
 * one registrable platform domain, with each surface on a subdomain of it, and
 * every Business website on `{slug}.<domain>`. `FL-DEC-016` leaves only the
 * domain *name* open — not the structure.
 *
 * That structure is what makes the session work. Cookies are scoped by
 * registrable domain, not by origin, so `app.locah.in` can read a cookie that
 * `locah.in` wrote as long as the cookie names `.locah.in` as its Domain. Three
 * unrelated `*.vercel.app` hostnames cannot do this at all: `vercel.app` is on
 * the Public Suffix List, so a cookie scoped to it is rejected outright and
 * every surface is left with its own island of a session. Sign in on one, and
 * the next is still signed out.
 *
 * Resolution runs in three tiers, most explicit first:
 *
 *   1. A per-surface override (`NEXT_PUBLIC_WEB_URL` and friends). This is what
 *      the current `*.vercel.app` deployment uses, and it keeps working
 *      untouched — the surfaces are simply reachable, not session-joined.
 *   2. `NEXT_PUBLIC_PLATFORM_DOMAIN`, which derives all four surfaces and, with
 *      them, a shared cookie domain. This is the production target.
 *   3. Localhost defaults, so `pnpm dev` needs no configuration. Ports differ
 *      between the apps but the cookie domain does not — cookies ignore the
 *      port — which is why a local sign-in reaches Workspace today and a
 *      production one does not.
 */

/**
 * Suffixes under which a cookie Domain is meaningless because the suffix is a
 * public one: anybody can get a name under it, so browsers refuse to let a
 * cookie span it.
 *
 * This is deliberately a short list of the hosts this project actually deploys
 * to rather than a vendored copy of the Public Suffix List. It exists to turn a
 * silent, invisible failure — the cookie is set, the browser drops it, and the
 * app looks signed out for no reason — into a refusal we can see.
 */
const PUBLIC_SUFFIXES = [
  'vercel.app',
  'netlify.app',
  'pages.dev',
  'github.io',
  'onrender.com',
  'herokuapp.com',
  'fly.dev',
  'workers.dev',
  'web.app',
  'firebaseapp.com',
  'azurewebsites.net',
  'amplifyapp.com',
]

/** Subdomains the platform claims for itself; never a Business website slug. */
export const RESERVED_SUBDOMAINS = new Set([
  'app',
  'admin',
  'api',
  'www',
  'mail',
  'email',
  'static',
  'assets',
  'cdn',
  'status',
  'docs',
  'help',
  'support',
  'blog',
  'dev',
  'staging',
  'test',
])

const LOCALHOST_DEFAULTS = {
  web: 'http://localhost:3000',
  workspace: 'http://localhost:3001',
  admin: 'http://localhost:3002',
  api: 'http://127.0.0.1:8000',
} as const

export interface PlatformOrigins {
  /** Public platform: marketing, Marketplace, Business websites, auth. */
  web: string
  /** Business Workspace (`app.<domain>`). */
  workspace: string
  /** Platform Super Admin (`admin.<domain>`). */
  admin: string
  /** FastAPI (`api.<domain>`). */
  api: string
  /**
   * The `Domain` attribute that lets one sign-in cover every surface, or
   * `null` when the deployment cannot support one and each surface keeps its
   * own host-only cookie.
   */
  sessionCookieDomain: string | null
  /** The registrable platform domain, when one is configured. */
  platformDomain: string | null
}

function normalizeOrigin(raw: string | undefined | null): string | null {
  if (!raw) {
    return null
  }
  const trimmed = raw.trim().replace(/\/+$/, '')
  return trimmed.length > 0 ? trimmed : null
}

/**
 * Reduce a configured value to a bare hostname.
 *
 * Accepts `locah.in`, `https://locah.in`, or `https://locah.in/` so that a
 * founder pasting a URL into the dashboard gets the same result as one typing a
 * domain.
 */
function normalizeDomain(raw: string | undefined | null): string | null {
  if (!raw) {
    return null
  }
  let value = raw.trim().toLowerCase()
  if (!value) {
    return null
  }
  value = value.replace(/^https?:\/\//, '')
  value = value.replace(/\/.*$/, '')
  value = value.replace(/:\d+$/, '')
  value = value.replace(/^\.+/, '').replace(/\.+$/, '')
  if (!value || value === 'localhost') {
    return null
  }
  return value
}

/** Whether a cookie scoped to this domain would actually be honoured. */
export function supportsSharedSessionCookie(domain: string | null): boolean {
  if (!domain) {
    return false
  }
  // An IP address has no registrable domain to share.
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(domain)) {
    return false
  }
  // A single label ("localhost", "internal") cannot be a cookie Domain.
  if (!domain.includes('.')) {
    return false
  }
  if (PUBLIC_SUFFIXES.includes(domain)) {
    return false
  }
  // `locah.vercel.app` is no better than `vercel.app` here: the cookie would be
  // scoped below the public suffix but still could not reach a sibling project.
  return !PUBLIC_SUFFIXES.some((suffix) => domain.endsWith(`.${suffix}`))
}

/**
 * Resolve every platform origin for the current environment.
 *
 * `process.env.NEXT_PUBLIC_*` is read through literal member access so that
 * Next.js can inline the values at build time for the browser bundle; a dynamic
 * lookup would come back undefined on the client.
 */
export function resolvePlatformOrigins(): PlatformOrigins {
  const platformDomain = normalizeDomain(process.env.NEXT_PUBLIC_PLATFORM_DOMAIN)
  const canShareCookie = supportsSharedSessionCookie(platformDomain)

  const derived = platformDomain
    ? {
        web: `https://${platformDomain}`,
        workspace: `https://app.${platformDomain}`,
        admin: `https://admin.${platformDomain}`,
        api: `https://api.${platformDomain}`,
      }
    : null

  const web =
    normalizeOrigin(process.env.NEXT_PUBLIC_WEB_URL) ??
    derived?.web ??
    LOCALHOST_DEFAULTS.web
  const workspace =
    normalizeOrigin(process.env.NEXT_PUBLIC_WORKSPACE_URL) ??
    derived?.workspace ??
    LOCALHOST_DEFAULTS.workspace
  const admin =
    normalizeOrigin(process.env.NEXT_PUBLIC_ADMIN_URL) ??
    derived?.admin ??
    LOCALHOST_DEFAULTS.admin
  const api =
    normalizeOrigin(process.env.NEXT_PUBLIC_API_URL) ??
    derived?.api ??
    LOCALHOST_DEFAULTS.api

  // An explicit override wins over the derived value, but never over the
  // browser's own cookie rules — hence the separate check rather than trusting
  // that a configured domain is usable.
  const override = normalizeDomain(process.env.NEXT_PUBLIC_SESSION_COOKIE_DOMAIN)
  const sessionCookieDomain = override
    ? supportsSharedSessionCookie(override)
      ? `.${override}`
      : null
    : canShareCookie
      ? `.${platformDomain}`
      : null

  return {
    web,
    workspace,
    admin,
    api,
    sessionCookieDomain,
    platformDomain,
  }
}

/** Absolute URL on a given surface, e.g. `platformUrl('workspace', '/b/123')`. */
export function platformUrl(
  surface: 'web' | 'workspace' | 'admin' | 'api',
  path = ''
): string {
  const base = resolvePlatformOrigins()[surface]
  if (!path) {
    return base
  }
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

/**
 * The Business website URL for a slug.
 *
 * Under a real platform domain this is the canonical `{slug}.<domain>` of
 * Document 10 §12.1. Without one there is no subdomain to give out, so it falls
 * back to the path form the web app also serves — the same page either way.
 */
export function businessSiteUrl(slug: string, path = ''): string {
  const { platformDomain, web } = resolvePlatformOrigins()
  const suffix = path && path !== '/' ? (path.startsWith('/') ? path : `/${path}`) : ''
  if (platformDomain && supportsSharedSessionCookie(platformDomain)) {
    return `https://${slug}.${platformDomain}${suffix}`
  }
  return `${web}/${slug}${suffix}`
}

/**
 * Read a Business slug out of a Host header, or `null` when the host is not a
 * Business website.
 *
 * Used by the web app's middleware to serve `{slug}.<domain>` from the same
 * route tree as `/{slug}` without duplicating any of it.
 */
export function businessSlugFromHost(host: string | null | undefined): string | null {
  const platformDomain = normalizeDomain(process.env.NEXT_PUBLIC_PLATFORM_DOMAIN)
  if (!platformDomain || !host) {
    return null
  }
  const hostname = host.trim().toLowerCase().replace(/:\d+$/, '')
  if (hostname === platformDomain || !hostname.endsWith(`.${platformDomain}`)) {
    return null
  }
  const label = hostname.slice(0, -(platformDomain.length + 1))
  // Only a single label is a Business website; `a.b.locah.in` is not one.
  if (!label || label.includes('.') || RESERVED_SUBDOMAINS.has(label)) {
    return null
  }
  return label
}
