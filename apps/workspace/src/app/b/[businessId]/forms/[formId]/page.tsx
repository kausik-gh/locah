import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { FormComposer } from '../FormComposer'

export const dynamic = 'force-dynamic'

type FormRow = {
  id: string
  title: string
  kind: string
  current_version: number
  consent_text?: string | null
  guardian_required?: boolean
  fields: { key: string; type: string; label: string; required?: boolean; help_text?: string; options?: string[] }[]
}

export default async function FormDetailPage({ params }: { params: { businessId: string; formId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [forms, context] = await Promise.all([
    apiTry<{ data: FormRow[] }>(`/v1/b/${b}/documents/forms`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
  ])
  const header = <PageHeader title="Form detail" subtitle="Saving changes publishes a new version for future requests only." />
  if (!forms.ok) {
    return <div className="bos-page">{header}<GateNotice error={forms.error} businessId={b} moduleLabel="Forms & files" /></div>
  }
  const form = forms.data.data.find((row) => row.id === params.formId)
  if (!form) {
    return <div className="bos-page">{header}<p className="bos-empty">Form not found.</p><Link href={`/b/${b}/forms`}>Back to forms</Link></div>
  }
  const canManage = context.ok && context.data.data.permissions.includes('documents.manage')
  const initial = {
    title: form.title,
    kind: form.kind,
    consent_text: form.consent_text || '',
    guardian_required: Boolean(form.guardian_required),
    fields: form.fields.map((field) => ({
      key: field.key,
      type: field.type as 'text',
      label: field.label,
      required: Boolean(field.required),
      help_text: field.help_text || '',
      options: (field.options || []).join('\n'),
    })),
  }
  return (
    <div className="bos-page">
      {header}
      <p><Link href={`/b/${b}/forms`}>← All forms</Link></p>
      <p><strong>{form.title}</strong> · v{form.current_version} · {form.kind}</p>
      {canManage ? <FormComposer businessId={b} formId={form.id} initial={initial} /> : (
        <ul>{form.fields.map((field) => (
          <li key={field.key}>{field.label} ({field.type}){field.required ? ' · required' : ''}</li>
        ))}</ul>
      )}
    </div>
  )
}
