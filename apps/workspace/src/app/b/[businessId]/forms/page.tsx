import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type FormRow = {
  id: string
  title: string
  kind: string
  current_version: number
  created_at: string
  fields: { key: string; type: string; label: string }[]
}

export default async function FormsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [forms, context] = await Promise.all([
    apiTry<{ data: FormRow[] }>(`/v1/b/${b}/documents/forms`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
  ])
  const header = (
    <PageHeader
      title="Forms"
      subtitle="Intake and consent forms with versioned definitions. Submissions stay pinned to the version the customer saw."
    />
  )
  if (!forms.ok) {
    return <div className="bos-page">{header}<GateNotice error={forms.error} businessId={b} moduleLabel="Forms & files" /></div>
  }
  const canManage = context.ok && context.data.data.permissions.includes('documents.manage')
  const rows = forms.data.data
  return (
    <div className="bos-page">
      {header}
      <nav className="bos-compliance__tabs" aria-label="Forms navigation">
        <Link href={`/b/${b}/forms`} aria-current="page">All forms</Link>
        <Link href={`/b/${b}/documents`}>Document requests</Link>
      </nav>
      {rows.length ? (
        <div className="bos-compliance__list">
          {rows.map((form) => (
            <article className="bos-compliance__card" key={form.id}>
              <h2><Link href={`/b/${b}/forms/${form.id}`}>{form.title}</Link></h2>
              <p>{form.kind} · version {form.current_version} · {form.fields.length} fields</p>
              <p className="bos-hint">{form.fields.map((f) => f.label).join(' · ')}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="bos-empty">No forms yet. Create an intake or consent form to send secure links from Documents.</div>
      )}
      {canManage ? (
        <p><Link className="ws-btn ws-btn--primary" href={`/b/${b}/forms/new`}>Create form</Link></p>
      ) : null}
    </div>
  )
}
