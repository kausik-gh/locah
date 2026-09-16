import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { optInDiscoverable, setVisibility } from './actions'

export const dynamic = 'force-dynamic'

type MarketplaceSettings = {
  visibility: string
  state: string
  eligibility: { eligible: boolean; reasons: string[] }
  discoverability_means: string[]
  index_health?: { last_status: string; last_reason?: string | null } | null
}

export default async function MarketplacePresencePage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: MarketplaceSettings }>(
    `/v1/b/${params.businessId}/marketplace`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Marketplace Presence" />
        <GateNotice
          error={res.error}
          businessId={params.businessId}
          moduleLabel="Marketplace Presence"
        />
      </div>
    )
  }
  const data = res.data.data

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Marketplace Presence</h1>
      <p style={{ maxWidth: '40rem', lineHeight: 1.5 }}>
        Choose whether customers can find you in Marketplace search. You are never listed
        automatically — this is always your decision, and you can change it at any time.
      </p>
      <dl style={{ marginTop: '1rem', lineHeight: 1.6 }}>
        <dt style={{ fontWeight: 700 }}>Current visibility</dt>
        <dd>{data.visibility}</dd>
        <dt style={{ fontWeight: 700 }}>Business state</dt>
        <dd>{data.state}</dd>
        <dt style={{ fontWeight: 700 }}>Eligible to index?</dt>
        <dd>
          {data.eligibility.eligible
            ? 'Yes'
            : `No — ${data.eligibility.reasons.join(', ')}`}
        </dd>
        <dt style={{ fontWeight: 700 }}>Index health</dt>
        <dd>
          {data.index_health
            ? `${data.index_health.last_status}${
                data.index_health.last_reason ? ` (${data.index_health.last_reason})` : ''
              }`
            : 'never'}
        </dd>
      </dl>

      <section style={{ marginTop: '1.5rem' }}>
        <h2>What discoverability means</h2>
        <ul>
          {data.discoverability_means.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <form action={optInDiscoverable}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="confirmed" value="true" />
          <button type="submit">Confirm & become discoverable</button>
        </form>
        <form action={setVisibility}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="visibility" value="unlisted" />
          <button type="submit">Set unlisted</button>
        </form>
        <form action={setVisibility}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="visibility" value="private" />
          <button type="submit">Set private</button>
        </form>
      </section>
    </div>
  )
}
