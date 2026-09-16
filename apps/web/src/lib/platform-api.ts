/**
 * Authenticated Platform API calls from apps/web.
 *
 * Mirrors the `apiTry` contract already used in apps/workspace: never throw on
 * a gate/auth failure, hand the caller a typed result so the page can render a
 * truthful state instead of blanking.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export type ApiError = {
  status: number
  code: string
  message: string
  details?: Record<string, unknown>
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError }

async function toError(res: Response): Promise<ApiError> {
  let code = 'UNKNOWN'
  let message = res.statusText || 'Request failed'
  let details: Record<string, unknown> | undefined
  try {
    const body = await res.json()
    if (body?.error) {
      code = body.error.code || code
      message = body.error.message || message
      details = body.error.details
    }
  } catch {
    // non-JSON body — keep the status-derived message
  }
  return { status: res.status, code, message, details }
}

export async function apiTry<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<ApiResult<T>> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init?.headers || {}),
      },
    })
  } catch (err) {
    return {
      ok: false,
      error: {
        status: 0,
        code: 'NETWORK_ERROR',
        message:
          err instanceof Error
            ? `Could not reach the Platform API: ${err.message}`
            : 'Could not reach the Platform API.',
      },
    }
  }
  if (!res.ok) return { ok: false, error: await toError(res) }
  return { ok: true, data: (await res.json()) as T }
}

export async function apiPost<T>(
  path: string,
  token: string,
  body?: unknown
): Promise<ApiResult<T>> {
  return apiTry<T>(path, token, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function apiPatch<T>(
  path: string,
  token: string,
  body: unknown
): Promise<ApiResult<T>> {
  return apiTry<T>(path, token, { method: 'PATCH', body: JSON.stringify(body) })
}

/** Business summary as returned by GET /v1/platform/businesses. */
export type BusinessSummary = {
  id: string
  slug: string
  display_name: string
  status: string
  state: string
  business_type?: string | null
}

/**
 * The caller's businesses, or an empty list when unauthenticated / on any
 * failure. Used for homepage routing, where "can't tell" and "none" lead to
 * the same place: show the landing page.
 */
export async function listMyBusinesses(token: string): Promise<BusinessSummary[]> {
  const res = await apiTry<{ data: BusinessSummary[] }>('/v1/platform/businesses', token)
  return res.ok ? res.data.data || [] : []
}
