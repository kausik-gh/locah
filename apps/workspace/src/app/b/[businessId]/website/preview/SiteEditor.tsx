'use client'

/**
 * The Website editor.
 *
 * Two panes: the controls on the left, and on the right the ACTUAL public site
 * rendering this Business's draft, via a short-lived preview token. Nothing is
 * re-implemented — what the owner sees is the page their customers will get,
 * which is the only honest answer to "what will this look like?".
 *
 * Every save is the existing section content-update endpoint, so the structured
 * Website model stays authoritative and the owner can only change the things
 * their SectionType actually allows. They cannot break the layout, because
 * layout is not theirs to edit here.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  completeImageUpload,
  generateSectionImage,
  refreshPreviewToken,
  requestImageUpload,
  saveSectionContent,
} from './actions'

/** Preview tokens last 10 minutes; re-mint well inside that so a long editing
 *  session never drops to a broken frame. */
const TOKEN_REFRESH_MS = 7 * 60 * 1000

const ACCEPTED_IMAGE_TYPES = 'image/jpeg,image/png,image/webp,image/gif'
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

export type EditorSection = {
  id: string
  section_type_id: string
  layout_variant?: string | null
  content: Record<string, unknown>
  assets?: Record<string, { url: string; alt_text?: string | null }>
  is_visible: boolean
}

export type EditorPage = {
  id: string
  title: string
  slug: string
  sections: EditorSection[]
}

type Field = { key: string; label: string; help?: string; multiline?: boolean }

/** A repeating field: a short list of small records the owner can add to,
 *  reword and remove, within the limit the section type allows. */
type ListField = {
  key: string
  label: string
  help?: string
  max: number
  parts: { key: string; label: string; multiline?: boolean; required?: boolean }[]
  addLabel: string
}

const LISTS: Record<string, ListField> = {
  feature_grid: {
    key: 'items',
    label: 'Items',
    max: 9,
    addLabel: 'Add an item',
    parts: [
      { key: 'title', label: 'Title', required: true },
      { key: 'body', label: 'Description (optional)', multiline: true },
    ],
  },
  highlights: {
    key: 'items',
    label: 'Numbers',
    help: 'Only numbers that are true — for example "15" and "years in business".',
    max: 6,
    addLabel: 'Add a number',
    parts: [
      { key: 'value', label: 'Number', required: true },
      { key: 'label', label: 'What it counts', required: true },
    ],
  },
}

/** What an owner may change, per section type. Anything not listed here is
 *  structure, and structure is not edited by hand. */
const FIELDS: Record<string, Field[]> = {
  hero: [
    { key: 'eyebrow', label: 'Small line above the headline', help: 'e.g. your area' },
    { key: 'headline', label: 'Headline', help: 'The first thing a visitor reads.' },
    {
      key: 'headline_accent',
      label: 'Words to colour',
      help: 'Part of the headline to show in your accent colour. Leave empty for none.',
    },
    { key: 'subheadline', label: 'Supporting line', multiline: true },
    { key: 'cta_label', label: 'Button text', help: 'e.g. "See the menu"' },
    { key: 'cta_url', label: 'Button goes to', help: 'A path on your site, like /menu' },
  ],
  about: [
    { key: 'title', label: 'Heading' },
    { key: 'body', label: 'Your story', multiline: true },
  ],
  text_block: [
    { key: 'title', label: 'Heading' },
    { key: 'body', label: 'Text', multiline: true },
  ],
  contact: [
    { key: 'title', label: 'Heading' },
    { key: 'address', label: 'Address', multiline: true },
    { key: 'phone', label: 'Phone' },
    { key: 'email', label: 'Email' },
    { key: 'hours_summary', label: 'Opening hours', multiline: true },
  ],
  cta_band: [
    { key: 'headline', label: 'Heading' },
    { key: 'body', label: 'Supporting line', multiline: true },
    { key: 'cta_label', label: 'Button text' },
    { key: 'cta_url', label: 'Button goes to' },
  ],
  offerings_list: [
    { key: 'title', label: 'Heading' },
    {
      key: 'subtitle',
      label: 'Supporting line',
      multiline: true,
      help: 'The items themselves come from your Offerings — edit them there.',
    },
  ],
  menu_section: [
    { key: 'title', label: 'Menu heading' },
  ],
  rooms_section: [
    { key: 'title', label: 'Rooms heading' },
    { key: 'subtitle', label: 'Supporting line', multiline: true },
  ],
  plans_section: [
    { key: 'title', label: 'Plans heading' },
    { key: 'subtitle', label: 'Supporting line', multiline: true },
  ],
  classes_section: [
    { key: 'title', label: 'Classes heading' },
  ],
  enquiry_form: [
    { key: 'title', label: 'Form heading' },
    { key: 'subtitle', label: 'Supporting line', multiline: true },
  ],
  gallery: [{ key: 'title', label: 'Gallery heading' }],
  location_list: [{ key: 'title', label: 'Heading' }],
  feature_grid: [
    { key: 'title', label: 'Heading' },
    { key: 'subtitle', label: 'Supporting line', multiline: true },
  ],
  highlights: [{ key: 'title', label: 'Heading (optional)' }],
}

/** Human names for section types. Owners never see the identifier. */
const SECTION_NAMES: Record<string, string> = {
  hero: 'Top of the page',
  about: 'About',
  text_block: 'Text',
  contact: 'Contact details',
  cta_band: 'Call to action',
  offerings_list: 'What you offer',
  menu_section: 'Menu',
  rooms_section: 'Rooms',
  plans_section: 'Plans',
  classes_section: 'Classes',
  enquiry_form: 'Enquiry form',
  gallery: 'Gallery',
  location_list: 'Locations',
  feature_grid: 'What you do',
  highlights: 'Numbers',
}

function sectionName(s: EditorSection): string {
  return SECTION_NAMES[s.section_type_id] || s.section_type_id.replace(/_/g, ' ')
}

type Row = Record<string, string>

function rowsOf(value: unknown): Row[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((v): v is Record<string, unknown> => Boolean(v) && typeof v === 'object')
    .map((v) => Object.fromEntries(Object.entries(v).map(([k, x]) => [k, String(x ?? '')])))
}

function ListEditor({
  field,
  sectionId,
  value,
  onCommit,
}: {
  field: ListField
  sectionId: string
  value: unknown
  onCommit: (rows: Row[]) => void
}) {
  const [rows, setRows] = useState<Row[]>(() => rowsOf(value))
  // Rows missing a required part are kept on screen while the owner types,
  // and left out of what is saved — the section type would reject them.
  const complete = (list: Row[]) =>
    list.filter((r) => field.parts.every((p) => !p.required || (r[p.key] || '').trim()))
  const save = (next: Row[]) => {
    setRows(next)
    onCommit(
      complete(next).map((r) =>
        Object.fromEntries(
          field.parts
            .map((p) => [p.key, (r[p.key] || '').trim()] as const)
            .filter(([, v]) => v !== '')
        )
      )
    )
  }
  return (
    <div className="ed-field">
      <span className="ed-label">{field.label}</span>
      {field.help ? <p className="ed-help" style={{ marginTop: 0 }}>{field.help}</p> : null}
      <ol className="ed-list">
        {rows.map((row, i) => (
          <li className="ed-list__row" key={i}>
            {field.parts.map((part) => {
              const id = `${sectionId}-${field.key}-${i}-${part.key}`
              const common = {
                id,
                className: `ed-input${part.multiline ? ' ed-input--area ed-input--short' : ''}`,
                defaultValue: row[part.key] || '',
                onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
                  if (e.target.value === (row[part.key] || '')) return
                  save(rows.map((r, j) => (j === i ? { ...r, [part.key]: e.target.value } : r)))
                },
              }
              return (
                <div key={part.key}>
                  <label className="ed-sublabel" htmlFor={id}>
                    {part.label}
                  </label>
                  {part.multiline ? <textarea {...common} /> : <input {...common} />}
                </div>
              )
            })}
            <button
              type="button"
              className="ed-list__remove"
              onClick={() => save(rows.filter((_, j) => j !== i))}
            >
              Remove
            </button>
          </li>
        ))}
      </ol>
      {rows.length < field.max ? (
        <button
          type="button"
          className="btn btn-ghost ed-list__add"
          onClick={() => setRows([...rows, {}])}
        >
          {field.addLabel}
        </button>
      ) : null}
    </div>
  )
}

/** Sections that carry a picture. */
const IMAGE_SECTIONS = new Set(['hero', 'about'])

function ImageField({
  businessId,
  sectionId,
  currentUrl,
  onUploaded,
}: {
  businessId: string
  sectionId: string
  currentUrl?: string
  onUploaded: (assetId: string) => void | Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [justUploaded, setJustUploaded] = useState<string | null>(null)
  const shown = justUploaded || currentUrl

  const pick = async (file: File) => {
    setError(null)
    if (file.size > MAX_IMAGE_BYTES) {
      setError('That image is over 10MB. Try a smaller one.')
      return
    }
    setBusy(true)
    try {
      const started = await requestImageUpload(businessId, file.type, file.size, file.name)
      if (!started.ok) {
        setError(started.error)
        return
      }
      const put = await fetch(started.uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': file.type },
        body: file,
      })
      if (!put.ok) {
        setError(`Upload failed (${put.status}).`)
        return
      }
      const done = await completeImageUpload(businessId, started.assetId)
      if (!done.ok) {
        setError(done.error)
        return
      }
      if (done.url) setJustUploaded(done.url)
      await onUploaded(started.assetId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ed-field">
      <span className="ed-label">Picture</span>
      {shown ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="ed-thumb" src={shown} alt="" />
      ) : (
        <p className="ed-help" style={{ marginTop: 0 }}>
          No picture yet. A good photo of your space or your work makes the biggest difference.
        </p>
      )}
      <label className={`btn btn-ghost ed-upload${busy ? ' is-busy' : ''}`}>
        {busy ? 'Working…' : shown ? 'Replace picture' : 'Add a picture'}
        <input
          type="file"
          accept={ACCEPTED_IMAGE_TYPES}
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void pick(file)
          }}
        />
      </label>
      <button
        type="button"
        className="btn btn-ghost"
        disabled={busy}
        onClick={async () => {
          setError(null)
          setBusy(true)
          try {
            const result = await generateSectionImage(businessId, sectionId)
            if (!result.ok) {
              setError(result.error)
              return
            }
            if (result.url) setJustUploaded(result.url)
            await onUploaded(result.assetId)
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Generation failed.')
          } finally {
            setBusy(false)
          }
        }}
      >
        {shown ? 'Generate a new picture' : 'Generate a picture'}
      </button>
      {error ? <p className="ed-error">{error}</p> : null}
    </div>
  )
}

export function SiteEditor({
  businessId,
  pages,
  previewPath,
  webUrl,
  publishHref,
}: {
  businessId: string
  pages: EditorPage[]
  previewPath: string | null
  webUrl: string
  publishHref: string
}) {
  const [pageIdx, setPageIdx] = useState(0)
  const [openSection, setOpenSection] = useState<string | null>(
    pages[0]?.sections[0]?.id ?? null
  )
  const [content, setContent] = useState<Record<string, Record<string, unknown>>>(() =>
    Object.fromEntries(pages.flatMap((p) => p.sections.map((s) => [s.id, { ...s.content }])))
  )
  const [status, setStatus] = useState<{ msg: string; error: boolean } | null>(null)
  const [device, setDevice] = useState<'desktop' | 'mobile'>('desktop')
  const [nonce, setNonce] = useState(0)
  const [path, setPath] = useState(previewPath)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const page = pages[pageIdx]

  useEffect(() => {
    const id = setInterval(async () => {
      const res = await refreshPreviewToken(businessId)
      if (res.ok) {
        setPath(res.previewPath)
        setNonce((n) => n + 1)
      }
    }, TOKEN_REFRESH_MS)
    return () => clearInterval(id)
  }, [businessId])

  // The preview reloads after a save so the owner sees the change land on the
  // real page rather than in a mock of it.
  const reloadPreview = useCallback(() => setNonce((n) => n + 1), [])

  const previewSrc = (() => {
    if (!path) return null
    const [base, query] = path.split('?')
    const pagePath = page && page.slug !== 'home' ? `${base}/${page.slug}` : base
    return `${webUrl}${pagePath}?${query}&v=${nonce}`
  })()

  useEffect(() => {
    setOpenSection(page?.sections[0]?.id ?? null)
  }, [pageIdx, page])

  const commit = async (section: EditorSection, key: string, next: unknown) => {
    const merged = { ...(content[section.id] || {}), [key]: next }
    setContent((prev) => ({ ...prev, [section.id]: merged }))
    setStatus({ msg: 'Saving…', error: false })
    const res = await saveSectionContent(businessId, section.id, merged)
    if (res.ok) {
      // Stays put rather than fading. "Did that save?" is the question an owner
      // asks, and a message that disappears after two seconds does not answer it.
      setStatus({ msg: 'All changes saved to your draft', error: false })
      reloadPreview()
    } else {
      setStatus({ msg: res.error || 'Could not save', error: true })
    }
  }

  return (
    <div className="ed">
      <aside className="ed__rail">
        <div className="ed__railhead">
          <label className="ed-label" htmlFor="ed-page">
            Page
          </label>
          <select
            id="ed-page"
            className="ed-select"
            value={pageIdx}
            onChange={(e) => setPageIdx(Number(e.target.value))}
          >
            {pages.map((p, i) => (
              <option key={p.id} value={i}>
                {p.title}
              </option>
            ))}
          </select>
          <p className="ed-help">
            Changes save to your draft as you make them. Your live site only changes when you
            publish.
          </p>
        </div>

        <div className="ed__sections">
          {(page?.sections || []).map((section) => {
            const isOpen = openSection === section.id
            const fields = FIELDS[section.section_type_id] || []
            const list = LISTS[section.section_type_id]
            const current = content[section.id] || {}
            const bound = Boolean(
              (section as unknown as { module_binding?: unknown }).module_binding
            )
            return (
              <div className="ed-sec" key={section.id} data-open={isOpen}>
                <button
                  type="button"
                  className="ed-sec__head"
                  onClick={() => setOpenSection(isOpen ? null : section.id)}
                  aria-expanded={isOpen}
                >
                  <span>{sectionName(section)}</span>
                  <span aria-hidden="true">{isOpen ? '−' : '+'}</span>
                </button>

                {isOpen ? (
                  <div className="ed-sec__body">
                    {fields.length === 0 && !IMAGE_SECTIONS.has(section.section_type_id) ? (
                      <p className="ed-help">
                        This section arranges itself from your business details. There is nothing
                        to type here.
                      </p>
                    ) : null}

                    {fields.map((f) => (
                      <div className="ed-field" key={f.key}>
                        <label className="ed-label" htmlFor={`${section.id}-${f.key}`}>
                          {f.label}
                        </label>
                        {f.multiline ? (
                          <textarea
                            id={`${section.id}-${f.key}`}
                            className="ed-input ed-input--area"
                            defaultValue={String(current[f.key] ?? '')}
                            onBlur={(e) => {
                              if (e.target.value !== String(current[f.key] ?? '')) {
                                void commit(section, f.key, e.target.value)
                              }
                            }}
                          />
                        ) : (
                          <input
                            id={`${section.id}-${f.key}`}
                            className="ed-input"
                            defaultValue={String(current[f.key] ?? '')}
                            onBlur={(e) => {
                              if (e.target.value !== String(current[f.key] ?? '')) {
                                void commit(section, f.key, e.target.value)
                              }
                            }}
                          />
                        )}
                        {f.help ? <p className="ed-help">{f.help}</p> : null}
                      </div>
                    ))}

                    {list ? (
                      <ListEditor
                        field={list}
                        sectionId={section.id}
                        value={current[list.key]}
                        onCommit={(rows) => void commit(section, list.key, rows)}
                      />
                    ) : null}

                    {IMAGE_SECTIONS.has(section.section_type_id) ? (
                      <ImageField
                        businessId={businessId}
                        sectionId={section.id}
                        currentUrl={section.assets?.image_asset_id?.url}
                        onUploaded={(assetId) => commit(section, 'image_asset_id', assetId)}
                      />
                    ) : null}

                    {bound ? (
                      <p className="ed-help">
                        The items shown here come from your Offerings, so they stay correct as you
                        add and remove them.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>

        <div className="ed__railfoot">
          {status ? (
            <p className={`ed-status${status.error ? ' is-error' : ''}`} role="status">
              {status.msg}
            </p>
          ) : null}
          <a className="btn btn-primary ed__publish" href={publishHref}>
            Review &amp; publish
          </a>
        </div>
      </aside>

      <div className="ed__stage">
        <div className="ed__stagebar">
          <span className="ed-help" style={{ margin: 0 }}>
            Your draft, exactly as visitors will see it
          </span>
          {previewSrc ? (
            <a href={previewSrc} target="_blank" rel="noreferrer" className="ed__full-preview">
              Open full-size preview ↗
            </a>
          ) : null}
          <div className="ed__devices" role="group" aria-label="Preview size">
            <button
              type="button"
              data-active={device === 'desktop'}
              onClick={() => setDevice('desktop')}
            >
              Desktop
            </button>
            <button
              type="button"
              data-active={device === 'mobile'}
              onClick={() => setDevice('mobile')}
            >
              Phone
            </button>
          </div>
        </div>
        <div className="ed__frame" data-device={device}>
          {previewSrc ? (
            <iframe
              ref={iframeRef}
              key={previewSrc}
              src={previewSrc}
              title="Website preview"
              loading="lazy"
            />
          ) : (
            <p className="ed-help" style={{ padding: '2rem' }}>
              The preview could not be opened. Your draft is safe — try reloading this page.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
