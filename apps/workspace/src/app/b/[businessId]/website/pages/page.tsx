import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { SectionEditor } from './SectionEditor'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    draft: {
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
    }
  }
}

type SectionTypesResponse = {
  data: {
    section_types: {
      id: string
      allowed_variants: string[]
    }[]
  }
}

export default async function WebsitePagesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const [res, sectionTypes] = await Promise.all([
    apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token),
    apiTry<SectionTypesResponse>(`/v1/b/${params.businessId}/website/section-types`, token),
  ])
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Pages & Structured Content" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }
  const variants = new Map(
    sectionTypes.ok
      ? sectionTypes.data.data.section_types.map((section) => [
          section.id,
          section.allowed_variants,
        ])
      : []
  )

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Pages & Structured Content</h1>
      <p style={{ marginBottom: '1.25rem', maxWidth: '42rem' }}>
        Edit the content of each page section. Your site is built from structured sections, so
        everything stays consistent and mobile-friendly.
      </p>
      {res.data.data.draft.pages.map((page) => (
        <section
          key={page.id}
          style={{
            marginBottom: '1.5rem',
            padding: '1rem',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <h2 style={{ fontSize: '1.2rem' }}>
            {page.title} <small>/{page.slug}</small>
          </h2>
          {page.sections.map((section) => (
            <SectionEditor
              key={section.id}
              businessId={params.businessId}
              sectionId={section.id}
              sectionTypeId={section.section_type_id}
              initialContent={section.content}
              initialVariant={section.layout_variant}
              allowedVariants={variants.get(section.section_type_id) || []}
            />
          ))}
        </section>
      ))}
    </div>
  )
}
