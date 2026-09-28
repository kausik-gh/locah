import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import type { RoleCatalogue } from '../types'
import { RolesBoard } from './RolesBoard'

export const dynamic = 'force-dynamic'

/**
 * Team → Roles (Capability Universe §7.2–§7.3). The roles this business can
 * give, each as what they do, where, and the screen they land on; plus the
 * owner's own custom roles, cloned from a template.
 */
export default async function RolesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: RoleCatalogue }>(`/v1/platform/businesses/${params.businessId}/roles`, token)
  const header = (
    <PageHeader
      title="Roles"
      subtitle="A role is what someone can do, where, and the screen they see first. Start from one of these, or make your own."
      breadcrumb={<Link href={`/b/${params.businessId}/team`}>Team</Link>}
    />
  )
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Team" />
      </div>
    )
  }
  return (
    <div className="bos-page">
      {header}
      <RolesBoard businessId={params.businessId} roles={res.data.data} />
    </div>
  )
}
