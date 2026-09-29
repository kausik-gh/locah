import WORDS from './site-words.json'

/**
 * A tenant website's own words in English, Tamil and Hindi (P1-10E6; PR-10,
 * GP-22 P1 part).
 *
 * Only the words LOCAH supplies — buttons, headings used when the owner wrote
 * none, the basket, checkout, and the pages a customer is sent to. What the
 * owner wrote stays exactly as they wrote it. Keyed by the English text, so a
 * phrase with no wording yet simply stays in English. The Tamil and Hindi are
 * LOCAH's first draft and need a native speaker's review before launch
 * (VB-22). apps/api/tests/test_site_words.py checks every t('…') on a tenant
 * page has both.
 */

export type SiteLang = 'en' | 'ta' | 'hi'
export type Words = (text: string, params?: Record<string, string | number>) => string

export const SITE_LANGS: readonly SiteLang[] = ['en', 'ta', 'hi']
export const LANG_NAMES: Record<SiteLang, string> = { en: 'English', ta: 'தமிழ்', hi: 'हिंदी' }
/** The HTML lang value, and the locale dates and numbers are written in. */
export const LANG_LOCALE: Record<SiteLang, string> = { en: 'en-IN', ta: 'ta-IN', hi: 'hi-IN' }
export const LANG_COOKIE = 'ls_lang'

export function isSiteLang(value: unknown): value is SiteLang {
  return value === 'en' || value === 'ta' || value === 'hi'
}

const TABLE = WORDS as Record<string, { ta: string; hi: string }>

export function siteWords(lang: SiteLang): Words {
  return (text, params) => {
    const raw = lang === 'en' ? text : TABLE[text]?.[lang] ?? text
    return params ? raw.replace(/\{(\w+)\}/g, (m, key: string) => (key in params ? String(params[key]) : m)) : raw
  }
}

/** The languages a site offers, English when it says none. */
export function offered(languages: unknown): SiteLang[] {
  const list = Array.isArray(languages) ? languages.filter(isSiteLang) : []
  return list.length ? list : ['en']
}
