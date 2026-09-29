import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { FormComposer } from '../FormComposer'

export const dynamic = 'force-dynamic'

export default async function NewFormPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const context = await apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b))
  const header = <PageHeader title="Create form" subtitle="Fields are stored as version 1. Later edits create a new version without changing past submissions." />
  if (!context.ok) {
    return <div className="bos-page">{header}<GateNotice error={context.error} businessId={b} moduleLabel="Forms & files" /></div>
  }
  if (!context.data.data.permissions.includes('documents.manage')) {
    return <div className="bos-page">{header}<p className="bos-hint">You may view forms but not create them.</p></div>
  }
  return (
    <div className="bos-page">
      {header}
      <FormComposer businessId={b} />
    </div>
  )
}
