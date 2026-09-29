'use client'

import { createContext, useContext, useMemo } from 'react'
import { siteWords, type SiteLang, type Words } from '@/lib/site-words'

const Lang = createContext<SiteLang>('en')

/** The page's language for the client parts of a tenant site (P1-10E6). */
export function SiteWordsProvider({ lang, children }: { lang: SiteLang; children: React.ReactNode }) {
  return <Lang.Provider value={lang}>{children}</Lang.Provider>
}

export function useSiteLang(): SiteLang {
  return useContext(Lang)
}

export function useWords(): Words {
  const lang = useContext(Lang)
  return useMemo(() => siteWords(lang), [lang])
}
