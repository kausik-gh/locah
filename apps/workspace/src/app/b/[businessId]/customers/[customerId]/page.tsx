import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ModuleState'
import { addCustomerNote, setCustomerState } from '../actions'

export const dynamic = 'force-dynamic'

type CustomerDetail = {
  id: string
  display_name: string
  email: string | null
  phone: string | null
  status: string
  tags?: string[]
}

type TimelineEntry = {
  id: string
  activity_type: string
  summary: string | null
  occurred_at: string
}

type Note = { id: string; body: string; created_at: string }

export default async function CustomerDetailPage({
  params,
}: {
  params: { businessId: string; customerId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}/customers/${params.customerId}`
  const res = await apiTry<{ data: CustomerDetail }>(base, token)
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/customers`}>← Customers</Link>
        <PageHeader title="Customer" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Customers" />
      </div>
    )
  }
  const customer = res.data.data

  const [timelineRes, notesRes] = await Promise.all([
    apiTry<{ data: TimelineEntry[] }>(`${base}/timeline`, token),
    apiTry<{ data: Note[] }>(`${base}/notes`, token),
  ])
  const timeline = timelineRes.ok ? timelineRes.data.data || [] : []
  const notes = notesRes.ok ? notesRes.data.data || [] : []

  const stateActions =
    customer.status === 'active'
      ? [
          { action: 'block', label: 'Block' },
          { action: 'archive', label: 'Archive' },
        ]
      : [{ action: 'restore', label: 'Restore' }]

  return (
    <div>
      <Link href={`/b/${params.businessId}/customers`}>← Customers</Link>
      <PageHeader
        title={customer.display_name}
        subtitle={[customer.email, customer.phone].filter(Boolean).join(' · ') || undefined}
      />

      <p>
        Status: <StatusPill value={customer.status} />
      </p>

      <section style={{ marginTop: '1.25rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {stateActions.map((item) => (
          <form key={item.action} action={setCustomerState}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="customerId" value={params.customerId} />
            <input type="hidden" name="action" value={item.action} />
            <button type="submit" style={BUTTON}>
              {item.label}
            </button>
          </form>
        ))}
      </section>

      <section style={{ marginTop: '1.75rem' }}>
        <h2 >Activity</h2>
        {timeline.length === 0 ? (
          <p style={{ opacity: 0.8 }}>Nothing recorded for this customer yet.</p>
        ) : (
          <ol style={{ paddingLeft: '1.1rem' }}>
            {timeline.map((entry) => (
              <li key={entry.id} style={{ marginBottom: '0.35rem' }}>
                <strong>{entry.activity_type}</strong>
                {entry.summary ? ` — ${entry.summary}` : ''}
                <span style={{ opacity: 0.6 }}>
                  {' '}
                  · {new Date(entry.occurred_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section style={{ marginTop: '1.75rem', maxWidth: '32rem' }}>
        <h2 >Notes</h2>
        {notes.length === 0 ? <p style={{ opacity: 0.8 }}>No notes yet.</p> : null}
        <ul style={{ paddingLeft: '1.1rem' }}>
          {notes.map((note) => (
            <li key={note.id} style={{ marginBottom: '0.4rem' }}>
              {note.body}
              <span style={{ opacity: 0.6 }}> · {new Date(note.created_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
        <form
          action={addCustomerNote}
          style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}
        >
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="customerId" value={params.customerId} />
          <textarea name="body" placeholder="Add a note" required style={INPUT} />
          <button type="submit" style={BUTTON}>
            Add note
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
