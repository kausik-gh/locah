import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import type { RoleCatalogue } from '../types'
import { AddPersonForm } from './AddPersonForm'

export const dynamic = 'force-dynamic'

/** Team → Add a person: name, the email they sign in with, role and where. */
export default async function AddPersonPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const [rolesRes, bizRes] = await Promise.all([
    apiTry<{ data: RoleCatalogue }>(`/v1/platform/businesses/${params.businessId}/roles`, token),
    apiTry<{ data: { display_name: string } }>(`/v1/b/${params.businessId}`, token),
  ])
  const header = (
    <PageHeader
      title="Add a person"
      subtitle="Choose what they do. LOCAH makes a join link; they create their own login with it and land on the right screen."
      breadcrumb={<Link href={`/b/${params.businessId}/team`}>Team</Link>}
    />
  )
  if (!rolesRes.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={rolesRes.error} businessId={params.businessId} moduleLabel="Team" />
      </div>
    )
  }
  return (
    <div className="bos-page">
      {header}
      <AddPersonForm
        businessId={params.businessId}
        businessName={bizRes.ok ? bizRes.data.data.display_name : 'our business'}
        roles={rolesRes.data.data}
      />
    </div>
  )
}
