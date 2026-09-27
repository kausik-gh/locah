import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { fetchPublicOfferings } from '@/lib/checkout-api'
import { siteThemeVars } from '@/components/website/WebsitePageView'
import { EnquiryForm } from '@/components/website/EnquiryForm'
import { Specs, priceLabel, type PublicOffering } from '@/components/website/offering-view'

export const dynamic = 'force-dynamic'

/** A business's enquiry page — its own colours, the item asked about, the form. */
export default async function EnquirePage({
  params,
  searchParams,
}: {
  params: { slug: string }
  searchParams: { offering_id?: string; purpose?: string }
}) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const site = await fetchPublicWebsite(params.slug)
  if (!site) notFound()
  const { styleVars, paletteMode } = siteThemeVars(site)
  const offerings = ((await fetchPublicOfferings(params.slug)).offerings ?? []) as PublicOffering[]
  const offering = searchParams.offering_id ? offerings.find((o) => o.id === searchParams.offering_id) : undefined
  const name = site.business.display_name
  const open = Boolean(site.capabilities?.enquire)
  return (
    <div data-locah-site="" data-palette={paletteMode} style={styleVars}>
      <main className="ls-section">
        <div className="ls-inner ls-enquire">
          <p><Link href={`/${params.slug}`}>← {name}</Link></p>
          {offering ? (
            <article className="ls-enquire__item">
              {offering.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={offering.image_url} alt="" />
              ) : null}
              <div>
                {offering.kind ? <p className="ls-offer__kind">{offering.kind.label}</p> : null}
                <h1 className="ls-title">{offering.title}</h1>
                {priceLabel(offering) ? <p className="ls-price">{priceLabel(offering)}</p> : null}
                {offering.description ? <p className="ls-item__desc">{offering.description}</p> : null}
                <Specs o={offering} />
              </div>
            </article>
          ) : (
            <h1 className="ls-title">Contact {name}</h1>
          )}
          {open ? (
            <EnquiryForm slug={params.slug} businessName={name} offeringId={offering?.id}
              offeringTitle={offering?.title} purpose={searchParams.purpose} />
          ) : (
            <p className="ls-meta">{name} is not taking enquiries online yet. Use the contact details on their site.</p>
          )}
        </div>
      </main>
    </div>
  )
}
