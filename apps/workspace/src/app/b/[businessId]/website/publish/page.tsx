import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { publishWebsite, generatePreviewToken } from './actions'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    website: { status: string }
    draft: { pages: { slug: string; title: string }[]; generated_by?: string | null }
  }
}

export default async function WebsitePublishPage({
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
        <PageHeader title="Preview & Publish" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Preview & Publish</h1>
      <p style={{ marginBottom: '1rem', maxWidth: '42rem' }}>
        Preview gives you a private link to check your site before customers see it. Publishing
        makes your current draft live. Nothing goes live until you publish.
      </p>
      <p>
        Current status:{' '}
        <strong>
          {res.data.data.website.status === 'published' ? 'Published' : 'Draft — not yet live'}
        </strong>
      </p>
      <ul>
        {res.data.data.draft.pages.map((p) => (
          <li key={p.slug}>
            {p.title} /{p.slug}
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <form action={generatePreviewToken}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <button type="submit">Get preview link</button>
        </form>
        <form action={publishWebsite}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <button type="submit">Publish</button>
        </form>
        <Link href={`/b/${params.businessId}/website`}>Back to overview</Link>
      </div>
    </div>
  )
}
