'use server'

import { cookies } from 'next/headers'
import { sendJson } from '@/lib/server-send'
import { WS_LANG_COOKIE, isWsLang } from './ws-words'

/** Save this person's Workspace language on their account, and remember it in this browser. */
export async function setWorkspaceLanguage(language: string) {
  if (!isWsLang(language)) return { ok: false as const, message: 'Choose English, Tamil or Hindi.' }
  const r = await sendJson<{ workspace_language: string }>('/v1/me/workspace-language', 'PUT', { language })
  if (r.ok) cookies().set(WS_LANG_COOKIE, language, { path: '/', maxAge: 60 * 60 * 24 * 365, sameSite: 'lax' })
  return r
}
