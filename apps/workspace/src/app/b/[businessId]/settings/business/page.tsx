import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { BusinessWorksEditor, type Kind, type TraitGroup } from './BusinessWorksEditor'

export const dynamic = 'force-dynamic'

type Classification = {
  category_key: string | null
  subcategory_key: string | null
  category_label: string | null
  subcategory_label: string | null
  org_shape: string
  org_shapes: { key: string; label: string }[]
  trait_groups: TraitGroup[]
}

type Catalogue = {
  categories: { key: string; label: string; subcategories: { key: string; label: string }[] }[]
}

/** Settings → How your business works (Capability Universe §4.3–§4.4). */
export default async function BusinessWorksPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/v1/platform/businesses/${params.businessId}`
  const [res, cat] = await Promise.all([
    apiTry<{ data: Classification }>(`${base}/classification`, token),
    apiTry<{ data: Catalogue }>(`/v1/public/taxonomy`, token),
  ])
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="How your business works" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Settings" />
      </div>
    )
  }
  const c = res.data.data
  const kinds: Kind[] = cat.ok
    ? cat.data.data.categories.flatMap((g) =>
        g.subcategories.map((s) => ({ category_key: g.key, category_label: g.label, key: s.key, label: s.label })),
      )
    : []
  return (
    <div className="bos-page">
      <PageHeader
        title="How your business works"
        subtitle="What you are and how you sell decide what LOCAH recommends. You stay in charge of what is switched on."
        breadcrumb={<Link href={`/b/${params.businessId}/settings`}>Settings</Link>}
        actions={<Link className="btn-quiet" href={`/b/${params.businessId}/modules`}>See recommended tools</Link>}
      />
      <BusinessWorksEditor
        businessId={params.businessId}
        kindLabel={c.subcategory_label}
        groupLabel={c.category_label}
        orgShape={c.org_shape}
        orgShapes={c.org_shapes}
        groups={c.trait_groups}
        kinds={kinds}
      />
    </div>
  )
}
