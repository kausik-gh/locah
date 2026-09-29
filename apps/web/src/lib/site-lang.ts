import { cookies } from 'next/headers'
import { LANG_COOKIE, isSiteLang, offered, type SiteLang } from './site-words'

/**
 * Which language a tenant page speaks: the visitor's pick (the switcher's
 * cookie), when the site offers it; else the site's first language.
 *
 * `asked` is an explicit ?lang= on a link — WhatsApp sends a Tamil customer's
 * bill, payment or tracking link with ?lang=ta — and is honoured on those
 * pages even when the site itself is English-only (`anyLanguage`).
 */
export function siteLang(languages: unknown, asked?: string | null, anyLanguage = false): SiteLang {
  const list = offered(languages)
  if (isSiteLang(asked) && (anyLanguage || list.includes(asked))) return asked
  const picked = cookies().get(LANG_COOKIE)?.value
  if (isSiteLang(picked) && list.includes(picked)) return picked
  return list[0]
}
