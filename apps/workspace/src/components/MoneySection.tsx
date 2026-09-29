import { apiTry } from '@/lib/api'
import { MoneyPanel, type Due } from './MoneyPanel'
import { pageWords } from '@/lib/ws-lang'

/** Server side of the money panel: what is due on one transaction, for anyone who may see payments. */
export async function MoneySection({
  businessId,
  token,
  sourceType,
  sourceId,
  path,
  title,
}: {
  businessId: string
  token: string
  sourceType: Due['source_type']
  sourceId: string
  path: string
  title?: string
}) {
  const res = await apiTry<{ data: Due }>(
    `/v1/platform/businesses/${businessId}/collect/due?source_type=${sourceType}&source_id=${sourceId}`,
    token
  )
  if (!res.ok) return null
  const t = pageWords()
  return (
    <section style={{ marginTop: '1.75rem' }} aria-labelledby={`money-${sourceId}`}>
      <h2 id={`money-${sourceId}`} className="ws-section-title">
        {title ?? t('Money')}
      </h2>
      <MoneyPanel businessId={businessId} path={path} due={res.data.data} />
    </section>
  )
}
