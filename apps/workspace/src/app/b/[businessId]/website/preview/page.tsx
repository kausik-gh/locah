import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { PreviewCanvas } from './PreviewCanvas'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    website: { status: string }
    draft: {
      generated_by?: string | null
      theme?: Record<string, unknown> | null
      pages: {
        id: string
        title: string
        slug: string
        sections: {
          id: string
          section_type_id: string
          layout_variant?: string | null
          content: Record<string, unknown>
          is_visible: boolean
        }[]
      }[]
    } | null
  }
}

/**
 * CORE-005/006/007 — visual preview of the draft with inline click-to-edit
 * (Doc 09 §9.1.1). Double-click any text to change it in place; each save is
 * the existing section content-update endpoint. Structural changes
 * (add/remove/reorder sections, variants, navigation, theme) stay in the
 * structured editors.
 */
export default async function WebsitePreviewPage({
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
        <PageHeader title="Website Preview" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }

  const draft = res.data.data.draft
  const base = `/b/${params.businessId}/website`

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>Website Preview</h1>
      <p style={{ marginBottom: '1rem', maxWidth: '44rem', lineHeight: 1.5 }}>
        Double-click any text to edit it in place. Changes save to your draft — nothing goes
        live until you{' '}
        <Link href={`${base}/publish`}>publish</Link>. For sections, layout, navigation and
        theme, use <Link href={`${base}/pages`}>Pages</Link> and{' '}
        <Link href={`${base}/theme`}>Theme</Link>.
      </p>
      {!draft || draft.pages.length === 0 ? (
        <p style={{ color: '#8a94a0' }}>No draft yet. Generate your website first.</p>
      ) : (
        <PreviewCanvas
          businessId={params.businessId}
          pages={draft.pages}
          theme={draft.theme || {}}
        />
      )}
    </div>
  )
}
