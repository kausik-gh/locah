const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export type ApiError = {
  status: number
  code: string
  message: string
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError }

/**
 * Fetch that surfaces the failure instead of throwing (mirrors
 * apps/workspace/src/lib/api.ts). Every `/v1/admin/*` route is guarded by
 * `require_super_admin`, so the failures this page must render truthfully are:
 * 401 (not signed in), 403 `admin.access` (signed in, not a Super Admin), and
 * the occasional 404 / 5xx. `AdminNotice` turns each into a real message.
 */
export async function apiTry<T>(path: string, token: string): Promise<ApiResult<T>> {
  const res = await fetch(`${apiUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (res.ok) {
    return { ok: true, data: (await res.json()) as T }
  }
  let code = 'UNKNOWN'
  let message = `Request failed with status ${res.status}`
  try {
    const body = await res.json()
    code = body?.error?.code ?? code
    message = body?.error?.message ?? message
  } catch {
    // Non-JSON error body — keep the status-derived defaults.
  }
  return { ok: false, error: { status: res.status, code, message } }
}

export async function apiPost<T>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${apiUrl}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  if (!res.ok) {
    throw new Error(`POST ${path} failed: ${res.status} ${await res.text()}`)
  }
  return res.json() as Promise<T>
}
