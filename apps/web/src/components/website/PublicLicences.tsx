import { platformUrl } from '@platform/config'

type Licence = { title: string; licence_number: string; authority: string }

/** Only licence numbers explicitly marked public by their owner. */
export async function PublicLicences({ slug }: { slug: string }) {
  const res = await fetch(`${platformUrl('api')}/v1/public/websites/${encodeURIComponent(slug)}/licences`, { cache: 'no-store' })
  if (!res.ok) return null
  const data = ((await res.json()) as { data: Licence[] }).data
  if (!data.length) return null
  return <div className="ls-foot__col ls-foot__licences"><p className="ls-foot__heading">Licences</p>{data.map((item) => <p key={`${item.title}:${item.licence_number}`}><strong>{item.title}</strong><span>{item.licence_number}</span>{item.authority ? <small>{item.authority}</small> : null}</p>)}</div>
}
