import { saveSectionContent } from './actions'

type Props = {
  businessId: string
  sectionId: string
  sectionTypeId: string
  initialContent: Record<string, unknown>
}

export function SectionEditor({
  businessId,
  sectionId,
  sectionTypeId,
  initialContent,
}: Props) {
  const headline = String(initialContent.headline || '')
  const body = String(initialContent.body || initialContent.subheadline || '')

  return (
    <form
      action={saveSectionContent}
      style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #ddd' }}
    >
      <input type="hidden" name="businessId" value={businessId} />
      <input type="hidden" name="sectionId" value={sectionId} />
      <input type="hidden" name="sectionTypeId" value={sectionTypeId} />
      <input type="hidden" name="initialContent" value={JSON.stringify(initialContent)} />
      <div style={{ fontSize: '0.85rem', opacity: 0.75 }}>{sectionTypeId}</div>
      {(sectionTypeId === 'hero' ||
        sectionTypeId === 'cta_band' ||
        'headline' in initialContent) && (
        <label style={{ display: 'block', marginTop: '0.4rem' }}>
          Headline
          <input
            name="headline"
            defaultValue={headline}
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.4rem' }}
          />
        </label>
      )}
      <label style={{ display: 'block', marginTop: '0.4rem' }}>
        Body / subheadline
        <textarea
          name="body"
          defaultValue={body}
          rows={3}
          style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.4rem' }}
        />
      </label>
      <button type="submit" style={{ marginTop: '0.5rem' }}>
        Save section
      </button>
    </form>
  )
}
