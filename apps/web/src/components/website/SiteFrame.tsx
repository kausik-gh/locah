import type { CSSProperties, ReactNode } from 'react'
import type { PublicWebsitePayload } from '@/lib/public-website'
import { LANG_LOCALE, type SiteLang } from '@/lib/site-words'
import { SiteWordsProvider } from './SiteWords'
import { siteFontVariables } from './site-fonts'
import { siteThemeVars } from './WebsitePageView'

/**
 * A tenant page outside the home page (checkout, booking, a bill, a payment
 * link…): the business's own colours, never LOCAH's, and the visitor's
 * language for the words inside (P1-10E6).
 */
export function SiteFrame({
  site,
  lang,
  style,
  className,
  children,
}: {
  site: PublicWebsitePayload | null
  lang: SiteLang
  style?: CSSProperties
  className?: string
  children: ReactNode
}) {
  const theme = site ? siteThemeVars(site) : { styleVars: {}, paletteMode: 'light' }
  return (
    <div data-locah-site="" className={[siteFontVariables, className].filter(Boolean).join(' ')} lang={LANG_LOCALE[lang]} data-palette={theme.paletteMode}
      style={{ ...theme.styleVars, minHeight: '100vh', ...style }}>
      <SiteWordsProvider lang={lang}>{children}</SiteWordsProvider>
    </div>
  )
}
