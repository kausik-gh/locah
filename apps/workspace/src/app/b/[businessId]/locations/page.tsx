import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  EmptyState,
  GateNotice,
  PageHeader,
  ROW,
  StatusPill,
  TABLE,
  TD,
  TH,
} from '@/components/ModuleState'
import { createLocation } from './actions'

export const dynamic = 'force-dynamic'

type LocationRow = {
  id: string
  name: string
  timezone: string
  is_primary: boolean
  status: string
  phone: string | null
  email: string | null
}

/** Doc 09 CORE-008 Locations. */
export default async function LocationsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await apiTry<{ data: LocationRow[] }>(
    `/v1/platform/businesses/${params.businessId}/locations`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Locations" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Locations" />
      </div>
    )
  }
  const locations = res.data.data || []
  const base = `/b/${params.businessId}/locations`

  return (
    <div>
      <PageHeader
        title="Locations"
        subtitle="Where this Business operates. One is always primary."
      />

      <div className="ws-tablewrap">
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>Name</th>
              <th style={TH}>Timezone</th>
              <th style={TH}>Contact</th>
              <th style={TH}>Status</th>
            </tr>
          </thead>
          <tbody>
            {locations.map((location) => (
              <tr key={location.id} style={ROW}>
                <td style={TD}>
                  <Link href={`${base}/${location.id}`}>{location.name}</Link>
                  {location.is_primary ? (
                    <span style={{ opacity: 0.65, fontSize: '0.85rem' }}> · primary</span>
                  ) : null}
                </td>
                <td style={TD}>{location.timezone}</td>
                <td style={TD}>{location.phone || location.email || '—'}</td>
                <td style={TD}>
                  <StatusPill value={location.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {locations.length === 0 ? (
        <EmptyState>No locations yet. Add the first one below.</EmptyState>
      ) : null}

      <section style={{ marginTop: '2rem', maxWidth: '32rem' }}>
        <h2 >Add a location</h2>
        <form action={createLocation} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input name="name" placeholder="Location name" required style={INPUT} />
          <select name="timezone" style={INPUT} defaultValue="Asia/Kolkata">
            {[
              'Asia/Kolkata',
              'Asia/Dubai',
              'Asia/Singapore',
              'Europe/London',
              'America/New_York',
              'America/Los_Angeles',
              'Australia/Sydney',
              'UTC',
            ].map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
          <input name="phone" placeholder="Phone" style={INPUT} />
          <input name="email" type="email" placeholder="Email" style={INPUT} />
          <button type="submit" style={BUTTON}>
            Add location
          </button>
        </form>
      </section>
    </div>
  )
}

const INPUT: React.CSSProperties = {
  width: '100%',
}
const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
