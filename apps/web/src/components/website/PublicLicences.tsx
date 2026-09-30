import { platformUrl } from '@platform/config'
import { siteWords, type SiteLang } from '@/lib/site-words'

type Licence = { title: string; licence_number: string; authority: string }

/** Only licence numbers explicitly marked public by their owner. */
export async function PublicLicences({ slug, lang = 'en' }: { slug: string; lang?: SiteLang }) {
  // An optional footer block: if it cannot be read, the site still renders.
  let data: Licence[] = []
  try {
    const res = await fetch(`${platformUrl('api')}/v1/public/websites/${encodeURIComponent(slug)}/licences`, { cache: 'no-store' })
    if (!res.ok) return null
    data = ((await res.json()) as { data: Licence[] }).data
  } catch {
    return null
  }
  if (!data.length) return null
  const t = siteWords(lang)
  return <div className="ls-foot__col ls-foot__licences"><p className="ls-foot__heading">{t('Licences')}</p>{data.map((item) => <p key={`${item.title}:${item.licence_number}`}><strong>{item.title}</strong><span>{item.licence_number}</span>{item.authority ? <small>{item.authority}</small> : null}</p>)}</div>
}
