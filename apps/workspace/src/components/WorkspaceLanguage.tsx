'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useTransition } from 'react'
import { setWorkspaceLanguage } from '@/lib/language-actions'
import { WS_LANG_COOKIE, WS_LANGS, WS_LANG_NAMES, type WsLang } from '@/lib/ws-words'

/**
 * The Workspace language picker (P1-10E6). Each language is named in its own
 * script so anyone can find theirs; the choice is saved on the person's account.
 */
export function WorkspaceLanguage({ current }: { current: WsLang }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  return (
    <label className="ws-lang">
      <span className="ws-lang__label" lang="en">Language · <span lang="ta">மொழி</span> · <span lang="hi">भाषा</span></span>
      <select name="workspace-language" value={current} disabled={pending}
        onChange={(e) => {
          const next = e.target.value
          start(async () => {
            const r = await setWorkspaceLanguage(next)
            if (r.ok) router.refresh()
          })
        }}>
        {WS_LANGS.map((l) => <option key={l} value={l} lang={l}>{WS_LANG_NAMES[l]}</option>)}
      </select>
    </label>
  )
}

/** The account says a language this browser does not know yet (a new device): adopt it once. */
export function AdoptLanguage({ lang }: { lang: WsLang }) {
  const router = useRouter()
  useEffect(() => {
    // Once per session: a browser that refuses the cookie must not refresh for ever.
    try {
      if (sessionStorage.getItem('ws-lang-adopted') === lang) return
      sessionStorage.setItem('ws-lang-adopted', lang)
    } catch {
      return
    }
    document.cookie = `${WS_LANG_COOKIE}=${lang}; path=/; max-age=31536000; samesite=lax`
    router.refresh()
  }, [lang, router])
  return null
}
