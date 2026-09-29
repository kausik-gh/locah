import WORDS from './ws-words.json'

/**
 * The Workspace in English, Tamil or Hindi (P1-10E6; MD "Dashboard Language —
 * UI language preference (English / Tamil / Hindi)"; GP-22 P1 part).
 *
 * Keyed by the English text; a phrase with no wording yet stays English. The
 * first surfaces are the ones a pilot shop lives in — the navigation, Home
 * and Orders; the rest of the Workspace is still English. The Tamil and Hindi
 * are LOCAH's first draft, pending a native speaker's review (VB-22).
 * apps/api/tests/test_workspace_words.py checks every t('…') here has both.
 */

export type WsLang = 'en' | 'ta' | 'hi'
export type Words = (text: string, params?: Record<string, string | number>) => string

export const WS_LANGS: readonly WsLang[] = ['en', 'ta', 'hi']
export const WS_LANG_NAMES: Record<WsLang, string> = { en: 'English', ta: 'தமிழ்', hi: 'हिंदी' }
export const WS_LOCALE: Record<WsLang, string> = { en: 'en-IN', ta: 'ta-IN', hi: 'hi-IN' }
export const WS_LANG_COOKIE = 'ws_lang'

export function isWsLang(value: unknown): value is WsLang {
  return value === 'en' || value === 'ta' || value === 'hi'
}

const TABLE = WORDS as Record<string, { ta: string; hi: string }>

export function wsWords(lang: WsLang): Words {
  return (text, params) => {
    const raw = lang === 'en' ? text : TABLE[text]?.[lang] ?? text
    return params ? raw.replace(/\{(\w+)\}/g, (m, key: string) => (key in params ? String(params[key]) : m)) : raw
  }
}
