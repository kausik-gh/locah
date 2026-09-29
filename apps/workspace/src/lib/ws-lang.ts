import { cookies } from 'next/headers'
import { WS_LANG_COOKIE, isWsLang, wsWords, type Words, type WsLang } from './ws-words'

/** This person's Workspace language, as the server last told this browser (see WorkspaceLanguage). */
export function wsLang(): WsLang {
  const value = cookies().get(WS_LANG_COOKIE)?.value
  return isWsLang(value) ? value : 'en'
}

/** The words for a server-rendered Workspace page. */
export function pageWords(): Words {
  return wsWords(wsLang())
}
