import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    website: { status: string; published_version_id: string | null }
    draft: {
      generated_by?: string | null
      pages: { id: string; title: string; slug: string }[]
      navigation: { label: string; path: string }[]
    }
  }
}

export default async function WebsiteOverviewPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Website Overview" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }
  const { website, draft } = res.data.data
  const base = `/b/${params.businessId}/website`

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Website Overview</h1>
      <p style={{ marginBottom: '1rem' }}>
        Your website&apos;s publish status, draft content, and page structure.
      </p>
      <p>
        Status: <strong>{website.status === 'published' ? 'Published' : 'Draft'}</strong>
        {draft.generated_by
          ? ` · ${
              draft.generated_by === 'ai_generation'
                ? 'written by AI from your business details'
                : 'built from your business details'
            }`
          : ''}
      </p>
      <p>Draft pages: {draft.pages.length}</p>
      <ul>
        {draft.pages.map((p) => (
          <li key={p.id}>
            {p.title} <code>/{p.slug}</code>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
        <Link href={`${base}/preview`}>Visual preview & inline edit</Link>
        <Link href={`${base}/pages`}>Edit pages</Link>
        <Link href={`${base}/theme`}>Theme & navigation</Link>
        <Link href={`${base}/publish`}>Preview & publish</Link>
      </div>
    </div>
  )
}
