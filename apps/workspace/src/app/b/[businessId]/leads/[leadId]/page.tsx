import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { addLeadNote, moveLeadStage } from '../actions'

export const dynamic = 'force-dynamic'

type LeadDetail = {
  id: string
  display_name: string
  email: string | null
  phone: string | null
  message: string | null
  status: string
  source: string
  lost_reason: string | null
  customer_contact_id: string | null
  status_history: Array<{ from_status: string | null; to_status: string; created_at: string }>
  notes: Array<{ id: string; body: string; created_at: string }>
}

// Doc 11 §10.2: won is terminal; lost can reopen.
const NEXT_STAGE: Record<string, string[]> = {
  new: ['contacted', 'qualified', 'won', 'lost'],
  contacted: ['qualified', 'won', 'lost'],
  qualified: ['won', 'lost'],
  lost: ['new', 'contacted', 'qualified'],
  won: [],
}

export default async function LeadDetailPage({
  params,
}: {
  params: { businessId: string; leadId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const back = `/b/${params.businessId}/leads`

  const res = await apiTry<{ data: LeadDetail }>(
    `/v1/platform/businesses/${params.businessId}/leads/${params.leadId}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Lead" breadcrumb={<Link href={back}>← Leads</Link>} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Leads" />
      </div>
    )
  }

  const lead = res.data.data
  const next = NEXT_STAGE[lead.status] ?? []

  return (
    <DetailShell
      breadcrumb={<Link href={back}>← Leads</Link>}
      title={lead.display_name}
      status={<StatusPill value={lead.status} />}
      meta={[
        ['Contact', [lead.email, lead.phone].filter(Boolean).join(' · ') || '—'],
        ['Source', lead.source],
        ...(lead.lost_reason ? ([['Lost because', lead.lost_reason]] as [string, string][]) : []),
      ]}
    >
      {lead.message ? (
        <blockquote
          style={{
            margin: '0 0 1.5rem',
            padding: '0.75rem 1rem',
            borderLeft: '3px solid var(--color-border-strong)',
            color: 'var(--color-muted)',
          }}
        >
          “{lead.message}”
        </blockquote>
      ) : null}
      {lead.customer_contact_id ? (
        <p>
          Converted to{' '}
          <Link href={`/b/${params.businessId}/customers/${lead.customer_contact_id}`}>
            a customer record
          </Link>
          .
        </p>
      ) : null}

      <Section title="Move stage">
        {next.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>
            Won is the final stage — this lead stays on record as history.
          </p>
        ) : (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            {next.map((stage) => (
              <form key={stage} action={moveLeadStage} style={{ display: 'flex', gap: '0.35rem' }}>
                <input type="hidden" name="businessId" value={params.businessId} />
                <input type="hidden" name="leadId" value={params.leadId} />
                <input type="hidden" name="status" value={stage} />
                {stage === 'lost' ? (
                  <input name="reason" placeholder="Reason (required)" required />
                ) : null}
                <button type="submit" className="btn-ghost" style={{ textTransform: 'capitalize' }}>
                  {stage}
                </button>
              </form>
            ))}
          </div>
        )}
      </Section>

      <Section title="History">
        <ol style={{ margin: 0, paddingLeft: '1.1rem', color: 'var(--color-foreground)' }}>
          {lead.status_history.map((event, idx) => (
            <li key={idx} style={{ marginBottom: '0.3rem' }}>
              {event.from_status ? `${event.from_status} → ` : 'created as '}
              <strong>{event.to_status}</strong>
              <span style={{ color: 'var(--color-muted)' }}>
                {' '}
                · {new Date(event.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Notes" style={{ maxWidth: '34rem' }}>
        {lead.notes.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>No notes yet.</p>
        ) : (
          <ul style={{ margin: '0 0 0.75rem', paddingLeft: '1.1rem' }}>
            {lead.notes.map((note) => (
              <li key={note.id} style={{ marginBottom: '0.4rem' }}>
                {note.body}
                <span style={{ color: 'var(--color-muted)' }}>
                  {' '}
                  · {new Date(note.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
        <form action={addLeadNote} style={{ display: 'grid', gap: '0.5rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="leadId" value={params.leadId} />
          <textarea name="body" placeholder="Add a note" required />
          <button type="submit" style={{ justifySelf: 'start' }}>
            Add note
          </button>
        </form>
      </Section>
    </DetailShell>
  )
}
