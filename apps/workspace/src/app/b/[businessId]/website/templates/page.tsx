import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { ApplyTemplate } from './ApplyTemplate'
import { TemplatePreview, type PreviewSection } from './TemplatePreview'

export const dynamic = 'force-dynamic'

type Template = {
  id: string
  name: string
  tagline: string
  description: string
  suits: string[]
  personality: string
  primary_color: string
  accent_color: string
  look: string[]
  required_modules: string[]
  available: boolean
  missing_modules: string[]
  page_count: number
  section_count: number
  pages: { slug: string; title: string; sections: PreviewSection[] }[]
}

type TemplatesResponse = {
  data: {
    templates: Template[]
    recommended_template_id: string
    business_type: string | null
  }
}

type WebsiteResponse = {
  data: {
    website: { status: string }
    draft: {
      generated_by?: string | null
      theme?: { template_id?: string | null } | null
      pages: unknown[]
    } | null
  }
}

/** Module ids are developer identifiers; an owner should never meet one. */
const MODULE_NAMES: Record<string, string> = {
  'offerings-catalog': 'Offerings',
  bookings: 'Bookings',
  memberships: 'Memberships',
  orders: 'Orders',
  leads: 'Leads',
}

function moduleName(id: string): string {
  return MODULE_NAMES[id] ?? id
}

/**
 * Choosing where the website starts.
 *
 * Every template is shown, best fit first, each with a wireframe of what it
 * actually builds rather than a photograph of somebody else's site. The three
 * things an owner is really deciding between — what leads the page, how much it
 * asks of the reader, and how it feels — are all visible in the preview, so the
 * copy does not have to claim them.
 */
export default async function WebsiteTemplatesPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    redirect(
      `/login?destination=${encodeURIComponent(`/b/${params.businessId}/website/templates`)}`
    )
  }

  const base = `/b/${params.businessId}/website`
  const [res, siteRes] = await Promise.all([
    apiTry<TemplatesResponse>(`/v1/b/${params.businessId}/website/templates`, token),
    apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token),
  ])

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Templates" breadcrumb={<Link href={base}>← Your website</Link>} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }

  const { templates, recommended_template_id: recommendedId } = res.data.data
  const draft = siteRes.ok ? siteRes.data.data.draft : null
  const generatedBy = draft?.generated_by ?? null
  // Two different relationships a draft can have with a template, and they
  // carry different consequences. An applied template is the plain starting
  // composition: replacing it loses nothing. A generated draft names the
  // template it was personalised from, but the copy in it was written for this
  // business, so re-applying that same template would throw that away.
  const appliedTemplateId = generatedBy?.startsWith('template:')
    ? generatedBy.slice('template:'.length)
    : null
  const sourceTemplateId = draft?.theme?.template_id ?? null
  const hasDraftWork = Boolean(draft) && !appliedTemplateId

  return (
    <div>
      <PageHeader
        title="Pick a starting point"
        subtitle="Each one builds a real site you can edit straight away. Nothing goes live until you publish."
        breadcrumb={<Link href={base}>← Your website</Link>}
      />

      <div className="tpl-grid">
        {templates.map((template) => {
          const home = template.pages[0]
          const isRecommended = template.id === recommendedId
          const relationship: 'applied' | 'generated-from' | 'none' =
            template.id === appliedTemplateId
              ? 'applied'
              : template.id === sourceTemplateId
                ? 'generated-from'
                : 'none'
          const missing = template.missing_modules.map(moduleName).join(' and ')

          return (
            <article
              key={template.id}
              className="tpl-card"
              data-recommended={isRecommended || undefined}
              data-unavailable={!template.available || undefined}
            >
              <div className="tpl-card__preview">
                <TemplatePreview
                  sections={home?.sections ?? []}
                  personality={template.personality}
                  primaryColor={template.primary_color}
                  accentColor={template.accent_color}
                  label={`${template.name} — ${template.tagline}`}
                />
              </div>

              <div className="tpl-card__body">
                <div className="tpl-card__head">
                  <h2 className="tpl-card__name">{template.name}</h2>
                  {relationship === 'generated-from' ? (
                    <span className="tpl-badge">Your site was built from this</span>
                  ) : isRecommended ? (
                    <span className="tpl-badge">Suits your business</span>
                  ) : null}
                </div>

                <p className="tpl-card__tagline">{template.tagline}</p>
                <p className="tpl-card__desc">{template.description}</p>

                <dl className="tpl-facts">
                  <div>
                    <dt>Opens with</dt>
                    <dd>{sectionLabel(home?.sections?.[0])}</dd>
                  </div>
                  <div>
                    <dt>Structure</dt>
                    <dd>
                      {template.page_count} {template.page_count === 1 ? 'page' : 'pages'} ·{' '}
                      {template.section_count} sections
                    </dd>
                  </div>
                  <div>
                    <dt>Feel</dt>
                    <dd>{template.look.join(', ')}</dd>
                  </div>
                </dl>

                <div className="tpl-card__foot">
                  <ApplyTemplate
                    businessId={params.businessId}
                    templateId={template.id}
                    templateName={template.name}
                    relationship={relationship}
                    hasDraftWork={hasDraftWork}
                    disabled={!template.available}
                    disabledReason={
                      template.available
                        ? undefined
                        : `Needs ${missing} turned on first`
                    }
                  />
                  {!template.available ? (
                    <Link href={`/b/${params.businessId}/modules`} className="tpl-link">
                      Turn on {missing} →
                    </Link>
                  ) : null}
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

/** What the first section actually is, in a customer's words. */
function sectionLabel(section: PreviewSection | undefined): string {
  if (!section) return '—'
  const { section_type_id: type, layout_variant: variant } = section
  if (type === 'hero') {
    if (variant === 'full_width') return 'A full-width opening image'
    if (variant === 'centered') return 'A centred statement'
    if (variant === 'image_left' || variant === 'image_right') return 'A statement beside an image'
    return 'A left-aligned statement'
  }
  if (type === 'menu_section') return 'Your menu'
  if (type === 'offerings_list') return 'What you offer'
  if (type === 'plans_section') return 'Your plans'
  if (type === 'rooms_section') return 'Your rooms'
  if (type === 'classes_section') return 'Your timetable'
  if (type === 'gallery') return 'Photographs'
  return 'An introduction'
}
