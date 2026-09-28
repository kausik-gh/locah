import Link from 'next/link'
import { notFound } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { siteThemeVars } from '@/components/website/WebsitePageView'

export const dynamic = 'force-dynamic'

type Statement = {
  business_name: string
  name: string
  balance: number
  party_type: 'customer' | 'supplier'
  overdue: number
  entries: { kind_label: string; amount: number; balance_after: number; entry_date: string; reference: string | null }[]
  upi_uri: string | null
}

async function fetchStatement(slug: string, token: string): Promise<Statement | null> {
  const res = await fetch(`${platformUrl('api')}/v1/public/websites/${encodeURIComponent(slug)}/khata/${encodeURIComponent(token)}`, { cache: 'no-store' })
  if (!res.ok) return null
  return ((await res.json()) as { data: Statement }).data
}

const rupees = (v: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v)
const day = (v: string) => new Date(`${v.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/**
 * "Your khata with <business>" (Capability Universe §14.5): what the customer
 * owes, the latest entries, and a UPI link to pay — opened from the statement
 * the business sends on WhatsApp, in the business's own colours. The link is
 * the credential; nothing else about the business's customers is shown.
 */
export default async function KhataStatementPage({ params }: { params: { slug: string; token: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const st = await fetchStatement(params.slug, params.token)
  if (!st) notFound()
  const site = await fetchPublicWebsite(params.slug)
  const theme = site ? siteThemeVars(site) : { styleVars: {}, paletteMode: 'light' }
  const name = site?.business.display_name || st.business_name
  const qr = `${platformUrl('api')}/v1/public/websites/${encodeURIComponent(params.slug)}/khata/${encodeURIComponent(params.token)}/upi-qr.svg`
  return (
    <div data-locah-site="" data-palette={theme.paletteMode} style={theme.styleVars}>
      <main className="ls-section">
        <div className="ls-inner ls-bill">
          {site ? <p><Link href={`/${params.slug}`}>← {name}</Link></p> : null}
          <header className="ls-bill__head">
            <p className="ls-meta">Your account with {name}</p>
            <h1 className="ls-title">
              {st.balance > 0 ? `${rupees(st.balance)} due` : st.balance < 0 ? `${rupees(-st.balance)} in your favour` : 'Nothing due'}
            </h1>
            <p className="ls-meta">{st.name}{st.overdue > 0 ? ` · ${rupees(st.overdue)} of it is past its due date` : ''}</p>
          </header>
          {st.upi_uri && st.balance > 0 ? (
            <div className="ls-bill__card ls-khata__pay">
              <a className="ls-btn" href={st.upi_uri}>Pay {rupees(st.balance)} by UPI</a>
              {/* eslint-disable-next-line @next/next/no-img-element -- a QR image served by the platform */}
              <img className="ls-khata__qr" src={qr} alt={`UPI QR to pay ${rupees(st.balance)} to ${name}`} width={180} height={180} />
              <p className="ls-meta">Opens your UPI app on this phone; on a computer, scan the code. {name} confirms the payment on their side.</p>
            </div>
          ) : null}
          <div className="ls-bill__card">
            <h2 className="ls-khata__h">Latest entries</h2>
            {st.entries.length ? (
              <ul className="ls-bill__lines">
                {st.entries.map((e, i) => (
                  <li key={i}>
                    <span>
                      {e.kind_label}{e.reference ? ` · ${e.reference}` : ''}
                      <small>{day(e.entry_date)} · balance {rupees(e.balance_after)}</small>
                    </span>
                    <strong>{e.amount > 0 ? '+' : '−'}{rupees(Math.abs(e.amount))}</strong>
                  </li>
                ))}
              </ul>
            ) : <p className="ls-meta">No entries yet.</p>}
          </div>
          <footer className="ls-bill__seller ls-meta">
            <span>Questions about an entry? Ask {name}.</span>
          </footer>
        </div>
      </main>
    </div>
  )
}
