import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ModuleState'
import { locationLifecycle, updateLocation } from '../actions'

export const dynamic = 'force-dynamic'

type LocationDetail = {
  id: string
  name: string
  timezone: string
  address: Record<string, unknown> | null
  hours: Record<string, unknown> | null
  is_primary: boolean
  status: string
  phone: string | null
  email: string | null
  notes: string | null
}

/** Doc 09 CORE-009 Location Detail & Hours. */
export default async function LocationDetailPage({
  params,
}: {
  params: { businessId: string; locationId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await apiTry<{ data: LocationDetail }>(
    `/v1/platform/businesses/${params.businessId}/locations/${params.locationId}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/locations`}>← Locations</Link>
        <PageHeader title="Location" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Locations" />
      </div>
    )
  }
  const location = res.data.data

  return (
    <div>
      <Link href={`/b/${params.businessId}/locations`}>← Locations</Link>
      <PageHeader
        title={location.name}
        subtitle={`${location.timezone}${location.is_primary ? ' · primary location' : ''}`}
      />

      <p>
        Status: <StatusPill value={location.status} />
      </p>

      <section style={{ marginTop: '1.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {!location.is_primary && location.status === 'active' ? (
          <form action={locationLifecycle}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="locationId" value={params.locationId} />
            <input type="hidden" name="action" value="set-primary" />
            <button type="submit" style={BUTTON}>
              Make primary
            </button>
          </form>
        ) : null}
        {location.status === 'active' && !location.is_primary ? (
          <form action={locationLifecycle}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="locationId" value={params.locationId} />
            <input type="hidden" name="action" value="archive" />
            <button type="submit" style={BUTTON}>
              Archive
            </button>
          </form>
        ) : null}
        {location.status !== 'active' ? (
          <form action={locationLifecycle}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="locationId" value={params.locationId} />
            <input type="hidden" name="action" value="reactivate" />
            <button type="submit" style={BUTTON}>
              Reactivate
            </button>
          </form>
        ) : null}
      </section>

      {location.is_primary ? (
        <p style={{ opacity: 0.75, marginTop: '0.75rem' }}>
          The primary location cannot be archived. Make another location primary first.
        </p>
      ) : null}

      <section style={{ marginTop: '2rem', maxWidth: '32rem' }}>
        <h2 >Details</h2>
        <form action={updateLocation} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="locationId" value={params.locationId} />
          <label style={LABEL}>
            Name
            <input name="name" defaultValue={location.name} required style={INPUT} />
          </label>
          <label style={LABEL}>
            Phone
            <input name="phone" defaultValue={location.phone ?? ''} style={INPUT} />
          </label>
          <label style={LABEL}>
            Email
            <input name="email" type="email" defaultValue={location.email ?? ''} style={INPUT} />
          </label>
          <label style={LABEL}>
            Notes
            <textarea name="notes" defaultValue={location.notes ?? ''} style={INPUT} />
          </label>
          <button type="submit" style={BUTTON}>
            Save changes
          </button>
        </form>
      </section>

      {location.hours ? (
        <section style={{ marginTop: '2rem' }}>
          <h2 >Opening hours</h2>
          <pre
            style={{
              background: 'var(--color-surface)',
              padding: '1rem',
              borderRadius: '8px',
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(location.hours, null, 2)}
          </pre>
        </section>
      ) : null}
    </div>
  )
}

const LABEL: React.CSSProperties = { display: 'grid', gap: '0.25rem', fontSize: '0.9rem' }
const INPUT: React.CSSProperties = {
  width: '100%',
}
const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
