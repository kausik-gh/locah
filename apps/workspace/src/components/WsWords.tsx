'use client'

import { createContext, useContext, useMemo } from 'react'
import { wsWords, type Words, type WsLang } from '@/lib/ws-words'

const Lang = createContext<WsLang>('en')

/** The Workspace language for client components (P1-10E6). */
export function WsWordsProvider({ lang, children }: { lang: WsLang; children: React.ReactNode }) {
  return <Lang.Provider value={lang}>{children}</Lang.Provider>
}

export function useWsLang(): WsLang {
  return useContext(Lang)
}

export function useWsWords(): Words {
  const lang = useContext(Lang)
  return useMemo(() => wsWords(lang), [lang])
}
