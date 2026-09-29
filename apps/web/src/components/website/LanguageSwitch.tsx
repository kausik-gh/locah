'use client'

import { useRouter } from 'next/navigation'
import { LANG_COOKIE, LANG_NAMES, type SiteLang } from '@/lib/site-words'

/**
 * The visitor's language, from the ones the business offers. Each name is
 * written in its own script so anyone can find theirs. Remembered for a year.
 */
export function LanguageSwitch({ languages, current, place }: { languages: SiteLang[]; current: SiteLang; place: 'nav' | 'foot' }) {
  const router = useRouter()
  if (languages.length < 2) return null
  const choose = (lang: SiteLang) => {
    document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`
    const url = new URL(window.location.href)
    if (url.searchParams.has('lang')) {
      url.searchParams.delete('lang')
      window.location.assign(url.toString())
    } else {
      router.refresh()
    }
  }
  return (
    <div className={`ls-langs ls-langs--${place}`} role="group" aria-label="Language · மொழி · भाषा">
      {languages.map((lang) => (
        <button key={lang} type="button" lang={lang} className="ls-langs__option" aria-pressed={lang === current}
          onClick={() => (lang === current ? undefined : choose(lang))}>
          {LANG_NAMES[lang]}
        </button>
      ))}
    </div>
  )
}
