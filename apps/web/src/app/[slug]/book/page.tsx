import { notFound } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchBookingOptions } from '@/lib/booking-api'
import { fetchPublicWebsite } from '@/lib/public-website'
import { getAccessToken } from '@/lib/supabase/access-token'
import { siteThemeVars } from '@/components/website/WebsitePageView'
import BookClient from './BookClient'

export const dynamic = 'force-dynamic'

/** WEB-009 Booking Flow — Doc 11 §4.1 / Doc 09 WEB-009. */
export default async function BookPage({ params }: { params: { slug: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  let options
  try {
    options = await fetchBookingOptions(params.slug)
  } catch {
    notFound()
  }
  // The business's own colours (never a stock look), and the signed-in customer, if any.
  const site = await fetchPublicWebsite(params.slug)
  const theme = site ? siteThemeVars(site) : { styleVars: {}, paletteMode: 'light' }
  const token = await getAccessToken()
  let customer: { name: string; email: string } | null = null
  if (token) {
    const me = await fetch(`${platformUrl('api')}/v1/me`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
    if (me.ok) {
      const profile = ((await me.json()) as { data: { email: string; display_name: string | null } }).data
      customer = { name: profile.display_name ?? '', email: profile.email }
    }
  }
  return (
    <div data-locah-site="" data-palette={theme.paletteMode} style={{ ...theme.styleVars, minHeight: '100vh' }}>
      <BookClient slug={params.slug} options={options} customer={customer} authToken={customer ? token : null} />
    </div>
  )
}
