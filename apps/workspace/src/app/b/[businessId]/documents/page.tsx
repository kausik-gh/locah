import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { RequestComposer, FileAccessButton } from './RequestComposer'
import { TemplateComposer } from './TemplateComposer'

export const dynamic = 'force-dynamic'

type Template = { id: string; kind: string; title: string; version: number; created_at: string }
type RequestRow = {
  id: string; request_type: 'form' | 'upload'; title: string; status: string
  expires_at: string; created_at: string; fulfilled_at: string | null
  submission_id: string | null; file_id: string | null; related_type: string
}
type FormRow = { id: string; title: string; kind: string; current_version: number }
type Submission = {
  id: string; signer_name: string; form_version: number; submitted_at: string
  signature_kind: string | null; content_sha256: string
}

const when = (value: string) => new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })

export default async function DocumentsPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { view?: string; submission?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const view = searchParams?.view === 'templates' ? 'templates' : searchParams?.view === 'received' ? 'received' : 'active'

  const [templates, forms, requests, context] = await Promise.all([
    apiTry<{ data: Template[] }>(`/v1/b/${b}/documents/templates`, token),
    apiTry<{ data: FormRow[] }>(`/v1/b/${b}/documents/forms`, token),
    apiTry<{ data: RequestRow[] }>(`/v1/b/${b}/documents/requests`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
  ])

  const header = (
    <PageHeader
      title="Documents & requests"
      subtitle="Send secure form and upload links. Customer files stay private — access is short-lived, never a public gallery."
    />
  )

  if (!requests.ok) {
    return <div className="bos-page">{header}<GateNotice error={requests.error} businessId={b} moduleLabel="Forms & files" /></div>
  }

  const perms = new Set(context.ok ? context.data.data.permissions : [])
  const canManage = perms.has('documents.manage')
  const canRequest = perms.has('documents.request')
  const formOptions = forms.ok ? forms.data.data : []
  const templateRows = templates.ok ? templates.data.data : []
  const rows = requests.data.data
  const awaiting = rows.filter((r) => r.status === 'open')
  const received = rows.filter((r) => r.status === 'fulfilled')
  const shown = view === 'received' ? received : view === 'templates' ? [] : rows

  const submissionId = searchParams?.submission
  const submission = submissionId && perms.has('documents.read')
    ? await apiTry<{ data: Submission }>(`/v1/b/${b}/documents/submissions/${submissionId}`, token)
    : null

  return (
    <div className="bos-page">
      {header}
      <div className="bos-review-summary">
        <div><span>Awaiting customer</span><strong>{awaiting.length}</strong><small>Open secure links</small></div>
        <div><span>Received</span><strong>{received.length}</strong><small>Signed or uploaded</small></div>
        <div><span>Templates</span><strong>{templateRows.length}</strong><small>Reusable wording</small></div>
      </div>
      <nav className="bos-compliance__tabs" aria-label="Documents views">
        <Link href={`/b/${b}/documents`} aria-current={view === 'active' ? 'page' : undefined}>Recent</Link>
        <Link href={`/b/${b}/documents?view=received`} aria-current={view === 'received' ? 'page' : undefined}>Received</Link>
        <Link href={`/b/${b}/documents?view=templates`} aria-current={view === 'templates' ? 'page' : undefined}>Templates</Link>
        <Link href={`/b/${b}/forms`}>Forms</Link>
      </nav>

      {view === 'templates' ? (
        <section aria-labelledby="doc-templates">
          <h2 id="doc-templates">Document templates</h2>
          {templateRows.length ? (
            <ul>{templateRows.map((t) => (
              <li key={t.id}><strong>{t.title}</strong> · {t.kind} · v{t.version} · {when(t.created_at)}</li>
            ))}</ul>
          ) : <p className="bos-hint">No templates yet. Add reusable agreement or certificate wording below.</p>}
          {canManage ? <TemplateComposer businessId={b} /> : null}
        </section>
      ) : (
        <>
          {shown.length ? (
            <div className="bos-compliance__list">
              {shown.map((row) => (
                <article className="bos-compliance__card" key={row.id}>
                  <div>
                    <span className={`bos-compliance__state is-${row.status === 'open' ? 'due_soon' : 'ok'}`}>
                      {row.status === 'open' ? 'Awaiting customer' : 'Received'}
                    </span>
                    <span className="bos-hint"> {row.request_type === 'form' ? 'Form' : 'Upload'}</span>
                  </div>
                  <h2>{row.title}</h2>
                  <p>Expires {when(row.expires_at)}{row.fulfilled_at ? ` · Fulfilled ${when(row.fulfilled_at)}` : ''}</p>
                  {row.submission_id ? (
                    <p><Link href={`/b/${b}/documents?submission=${row.submission_id}`}>View signed submission</Link></p>
                  ) : null}
                  {row.file_id ? (
                    <p><FileAccessButton businessId={b} fileId={row.file_id} /></p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="bos-empty">No document requests in this view yet.</div>
          )}
        </>
      )}

      {submission?.ok ? (
        <section className="bos-compliance__detail" aria-labelledby="submission-detail">
          <h2 id="submission-detail">Signed submission</h2>
          <p><strong>{submission.data.data.signer_name}</strong> · form v{submission.data.data.form_version}</p>
          <p className="bos-hint">Submitted {when(submission.data.data.submitted_at)} · {submission.data.data.signature_kind || 'no signature'} · hash {submission.data.data.content_sha256.slice(0, 12)}…</p>
        </section>
      ) : null}

      {canRequest ? (
        <section className="bos-compliance__detail" aria-labelledby="request-form">
          <h2 id="request-form">Request a form</h2>
          <p className="bos-hint">Creates a one-time private link pinned to the form version active today.</p>
          <RequestComposer businessId={b} kind="form" forms={formOptions} />
        </section>
      ) : null}
      {canRequest ? (
        <section className="bos-compliance__detail" aria-labelledby="request-upload">
          <h2 id="request-upload">Request a file upload</h2>
          <RequestComposer businessId={b} kind="upload" />
        </section>
      ) : null}
    </div>
  )
}
