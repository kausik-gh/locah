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
import { createInvitation, invitationLifecycle } from '../actions'

export const dynamic = 'force-dynamic'

type Invitation = {
  id: string
  invited_email: string
  invited_role: string
  status: string
  expires_at: string
  accepted_at: string | null
}

/** Doc 09 CORE-011 Invitation & Member Access. */
export default async function InvitationsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await apiTry<{ data: Invitation[] }>(
    `/v1/platform/businesses/${params.businessId}/invitations`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/team`}>← Team</Link>
        <PageHeader title="Invitations" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Invitations" />
      </div>
    )
  }
  const invitations = res.data.data || []
  const now = Date.now()

  return (
    <div>
      <Link href={`/b/${params.businessId}/team`}>← Team</Link>
      <PageHeader title="Invitations" subtitle="People invited to join, and where each stands." />

      <table style={TABLE}>
        <thead>
          <tr>
            <th style={TH}>Email</th>
            <th style={TH}>Role</th>
            <th style={TH}>Status</th>
            <th style={TH}>Expires</th>
            <th style={TH}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {invitations.map((invitation) => {
            const expired =
              invitation.status === 'pending' && new Date(invitation.expires_at).getTime() < now
            return (
              <tr key={invitation.id} style={ROW}>
                <td style={TD}>{invitation.invited_email}</td>
                <td style={TD}>{invitation.invited_role}</td>
                <td style={TD}>
                  <StatusPill value={expired ? 'expired' : invitation.status} />
                </td>
                <td style={TD}>{new Date(invitation.expires_at).toLocaleDateString()}</td>
                <td style={{ ...TD, display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                  {invitation.status === 'pending' ? (
                    <>
                      <form action={invitationLifecycle}>
                        <input type="hidden" name="businessId" value={params.businessId} />
                        <input type="hidden" name="invitationId" value={invitation.id} />
                        <input type="hidden" name="action" value="resend" />
                        <button type="submit" style={LINK_BUTTON}>
                          Resend
                        </button>
                      </form>
                      <form action={invitationLifecycle}>
                        <input type="hidden" name="businessId" value={params.businessId} />
                        <input type="hidden" name="invitationId" value={invitation.id} />
                        <input type="hidden" name="action" value="revoke" />
                        <button type="submit" style={LINK_BUTTON}>
                          Revoke
                        </button>
                      </form>
                    </>
                  ) : null}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {invitations.length === 0 ? (
        <EmptyState>Nobody has been invited yet. Send the first invitation below.</EmptyState>
      ) : null}

      <section style={{ marginTop: '2rem', maxWidth: '32rem' }}>
        <h2 >Invite someone</h2>
        <form action={createInvitation} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input
            name="invited_email"
            type="email"
            placeholder="Their email address"
            required
            style={INPUT}
          />
          <select name="invited_role" style={INPUT} defaultValue="member">
            <option value="member">Member</option>
            <option value="manager">Manager</option>
          </select>
          <button type="submit" style={BUTTON}>
            Send invitation
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
const LINK_BUTTON: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--color-primary)',
  cursor: 'pointer',
  font: 'inherit',
  fontWeight: 500,
  padding: 0,
  minHeight: 'auto',
  textDecoration: 'underline',
}
