'use client'

import { useState } from 'react'
import type { BusinessInterviewData, InterviewCommand, TaxonomyMatch } from '@platform/contracts'
import { KindSearch } from '@/components/onboarding/KindSearch'

type Slot = NonNullable<InterviewCommand['slot']>
export type Correct = (slot: Slot, values: string[], text?: string) => Promise<boolean>

/**
 * What LOCAH understands — typed, never a field dump.
 *
 * Offerings, what customers do, how the business works, where it is and its
 * hours are separate kinds of thing, rebuilt by the server on every turn from
 * the owner's own words. Each section says only what is known (an empty one
 * is not shown) and has one "Change" that edits that kind of thing with the
 * right kind of control — a list, a set of choices, a place — never a
 * free-for-all text box that could put "All India" into opening hours.
 */
export function UnderstandingPanel({
  data,
  busy,
  thinking,
  onCorrect,
  onAsk,
}: {
  data: BusinessInterviewData
  busy: boolean
  /** A reply is being read: the panel is about to change. */
  thinking: boolean
  onCorrect: Correct
  /** "Tell LOCAH about…" — puts the words in the composer. */
  onAsk: (prefill: string) => void
}) {
  const u = data.understanding
  const [editing, setEditing] = useState<string>('')
  const close = () => setEditing('')
  const b = u.business
  const kindLine = [b.category, b.place].filter(Boolean).join(' · ')
  const known = {
    offer: u.offer.groups.length > 0,
    actions: u.actions.length > 0,
    buying: u.buying.length > 0,
    place: Boolean(u.contact.location || u.contact.phone || u.contact.hours || u.choices.area),
    direction: Boolean(u.direction?.words?.length || u.content.length),
  }
  const ready = Boolean(data.build_available && data.blueprint.completion_state.ready_at)

  return (
    <div className="up" aria-busy={thinking}>
      <div className="up-head">
        <p className="up-eyebrow">What I understand</p>
        <Progress data={data} />
      </div>

      <Section
        title="Business"
        editing={editing === 'business'}
        onEdit={() => setEditing('business')}
        busy={busy}
      >
        {editing === 'business' ? (
          <BusinessEditor data={data} busy={busy} onCorrect={onCorrect} onDone={close} />
        ) : (
          <>
            <p className="up-name">{b.name || <span className="up-muted">Name still to come</span>}</p>
            {kindLine ? <p className="up-kind">{kindLine}</p> : null}
            {b.category_source === 'inferred' && b.category ? (
              <p className="up-looks">
                Looks like {b.category_group ? `${b.category_group} → ` : ''}
                {b.category}.{' '}
                <button type="button" className="up-link" disabled={busy} onClick={() => setEditing('business')}>
                  Correct
                </button>
              </p>
            ) : null}
            {!b.category && !b.name && !thinking ? (
              <p className="up-muted">Tell LOCAH what you do — it fills in as you talk.</p>
            ) : null}
          </>
        )}
      </Section>

      {known.offer || editing === 'offer' ? (
        <Section title="What you offer" editing={editing === 'offer'} onEdit={() => setEditing('offer')} busy={busy}>
          {editing === 'offer' ? (
            <ListEditor
              initial={u.offer.groups.map((g) => g.name)}
              hint="One per line — the main things people come for."
              busy={busy}
              onSave={(values) => onCorrect('offerings', values)}
              onDone={close}
            />
          ) : (
            <ul className="up-offer">
              {u.offer.groups.map((g) => (
                <li key={g.name}>
                  <strong>{g.name}</strong>
                  {g.items.length ? <span>{g.items.join(' · ')}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}

      {known.actions || editing === 'actions' ? (
        <Section
          title="How customers reach you"
          editing={editing === 'actions'}
          onEdit={() => setEditing('actions')}
          busy={busy}
        >
          {editing === 'actions' ? (
            <ChoiceEditor
              options={u.options.actions}
              more={u.options.all_actions}
              initial={u.choices.actions}
              busy={busy}
              onSave={(values) => onCorrect('actions', values)}
              onDone={close}
            />
          ) : (
            <ul className="up-chips">
              {u.actions.map((a) => (
                <li key={a.id}>{a.label}</li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}

      {known.buying || editing === 'buying' ? (
        <Section
          title="How it works"
          editing={editing === 'buying'}
          onEdit={() => setEditing('buying')}
          busy={busy}
        >
          {editing === 'buying' ? (
            <BuyingEditor data={data} busy={busy} onCorrect={onCorrect} onDone={close} />
          ) : (
            <ul className="up-lines">
              {u.buying.map((row) => (
                <li key={row.kind + row.text}>{row.text}</li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}

      {known.place || editing === 'place' ? (
        <Section title="Where to find you" editing={editing === 'place'} onEdit={() => setEditing('place')} busy={busy}>
          {editing === 'place' ? (
            <PlaceEditor data={data} busy={busy} onCorrect={onCorrect} onDone={close} />
          ) : (
            <dl className="up-facts">
              {u.contact.location ? (
                <div>
                  <dt>Location</dt>
                  <dd>{u.contact.location}</dd>
                </div>
              ) : null}
              {u.choices.area ? (
                <div>
                  <dt>Serves</dt>
                  <dd>{u.choices.area}</dd>
                </div>
              ) : null}
              {u.contact.phone ? (
                <div>
                  <dt>Phone</dt>
                  <dd>{u.contact.phone}</dd>
                </div>
              ) : null}
              {u.contact.hours ? (
                <div>
                  <dt>Hours</dt>
                  <dd>{u.contact.hours}</dd>
                </div>
              ) : null}
            </dl>
          )}
        </Section>
      ) : null}

      {known.direction ? (
        <Section title="Website direction">
          {u.direction?.words?.length ? <p className="up-direction">{u.direction.words.join(' · ')}</p> : null}
          {u.content.length ? (
            <p className="up-muted">You asked for: {u.content.join(', ')}</p>
          ) : null}
        </Section>
      ) : null}

      {u.worth_knowing.length > 0 ? (
        <Section title={ready ? 'Could add later' : 'Still worth knowing'}>
          <ul className="up-worth">
            {u.worth_knowing.slice(0, 5).map((w) => (
              <li key={w.id}>
                <button type="button" disabled={busy} onClick={() => onAsk(`About ${w.short || w.label.toLowerCase()}: `)}>
                  {w.label}
                </button>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {u.tools.length > 0 ? (
        <Section title="Recommended tools">
          <ul className="up-tools">
            {u.tools.slice(0, 4).map((t) => (
              <li key={t.id}>
                <strong>{t.label}</strong>
                {t.why ? <span>{t.why}</span> : null}
              </li>
            ))}
          </ul>
          <p className="up-muted up-small">Nothing switches on by itself — set them up whenever you like.</p>
        </Section>
      ) : null}
    </div>
  )
}

/** Quiet progress: how well each part is understood — never "question 4 of 12". */
export function Progress({ data, compact = false }: { data: BusinessInterviewData; compact?: boolean }) {
  const parts = data.understanding.progress || []
  const ready = Boolean(data.blueprint.completion_state.ready_at)
  const done = parts.filter((p) => p.coverage === 'sufficient' || p.coverage === 'high_confidence').length
  const label = ready ? 'Enough for a strong first version' : done ? 'Getting to know it' : 'Just started'
  return (
    <div className={`up-progress${compact ? ' up-progress--compact' : ''}`} role="status" aria-label={label}>
      <span className="up-progress__bar" aria-hidden="true">
        {parts.map((p) => (
          <i key={p.dimension} data-coverage={ready && p.coverage === 'unknown' ? 'optional' : p.coverage} title={p.label} />
        ))}
      </span>
      {!compact ? <span className="up-progress__label">{label}</span> : null}
    </div>
  )
}

function Section({
  title,
  children,
  editing,
  onEdit,
  busy,
}: {
  title: string
  children: React.ReactNode
  editing?: boolean
  onEdit?: () => void
  busy?: boolean
}) {
  return (
    <section className="up-section" aria-label={title}>
      <div className="up-section__head">
        <h3>{title}</h3>
        {onEdit && !editing ? (
          <button type="button" className="up-link" disabled={busy} onClick={onEdit} aria-label={`Change ${title.toLowerCase()}`}>
            Change
          </button>
        ) : null}
      </div>
      {children}
    </section>
  )
}

function EditorActions({ busy, onCancel, disabled }: { busy: boolean; onCancel: () => void; disabled?: boolean }) {
  return (
    <div className="up-edit__actions">
      <button type="submit" className="lc-btn lc-btn--sm" disabled={busy || disabled}>
        {busy ? 'Saving…' : 'Save'}
      </button>
      <button type="button" className="up-link" onClick={onCancel}>
        Cancel
      </button>
    </div>
  )
}

function BusinessEditor({
  data,
  busy,
  onCorrect,
  onDone,
}: {
  data: BusinessInterviewData
  busy: boolean
  onCorrect: Correct
  onDone: () => void
}) {
  const b = data.understanding.business
  const [name, setName] = useState(b.name)
  const [kind, setKind] = useState<TaxonomyMatch | null>(null)
  return (
    <form
      className="up-edit"
      onSubmit={async (e) => {
        e.preventDefault()
        let ok = true
        if (name.trim() && name.trim() !== b.name) ok = await onCorrect('name', [], name.trim())
        if (ok && kind) ok = await onCorrect('category', [kind.category_key, kind.subcategory_key])
        if (ok) onDone()
      }}
    >
      <label className="up-edit__label" htmlFor="up-name">
        Name
      </label>
      <input id="up-name" className="up-input" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
      <KindSearch
        value={kind}
        onPick={setKind}
        label={b.category ? `Kind of business — now ${b.category}` : 'Kind of business'}
        placeholder="Search: physiotherapy, bakery, builder…"
      />
      <EditorActions busy={busy} onCancel={onDone} />
    </form>
  )
}

function ListEditor({
  initial,
  hint,
  busy,
  onSave,
  onDone,
}: {
  initial: string[]
  hint: string
  busy: boolean
  onSave: (values: string[]) => Promise<boolean>
  onDone: () => void
}) {
  const [text, setText] = useState(initial.join('\n'))
  const values = text
    .split(/\n|,/)
    .map((v) => v.trim())
    .filter(Boolean)
  return (
    <form
      className="up-edit"
      onSubmit={async (e) => {
        e.preventDefault()
        if (await onSave(values)) onDone()
      }}
    >
      <textarea className="up-input" rows={Math.max(3, initial.length + 1)} value={text} onChange={(e) => setText(e.target.value)} />
      <p className="up-muted up-small">{hint}</p>
      <EditorActions busy={busy} onCancel={onDone} disabled={!values.length} />
    </form>
  )
}

function Toggles({
  options,
  chosen,
  onToggle,
}: {
  options: { id: string; label: string }[]
  chosen: string[]
  onToggle: (id: string) => void
}) {
  return (
    <div className="up-toggles">
      {options.map((o) => (
        <button key={o.id} type="button" aria-pressed={chosen.includes(o.id)} onClick={() => onToggle(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id])

function ChoiceEditor({
  options,
  more,
  initial,
  busy,
  onSave,
  onDone,
}: {
  options: { id: string; label: string }[]
  more?: { id: string; label: string }[]
  initial: string[]
  busy: boolean
  onSave: (values: string[]) => Promise<boolean>
  onDone: () => void
}) {
  const [chosen, setChosen] = useState(initial)
  const [all, setAll] = useState(false)
  const shown = all && more ? more : options
  return (
    <form
      className="up-edit"
      onSubmit={async (e) => {
        e.preventDefault()
        if (await onSave(chosen)) onDone()
      }}
    >
      <Toggles options={shown} chosen={chosen} onToggle={(id) => setChosen((c) => toggle(c, id))} />
      {more && !all && more.length > options.length ? (
        <button type="button" className="up-link up-more" onClick={() => setAll(true)}>
          More ways
        </button>
      ) : null}
      <EditorActions busy={busy} onCancel={onDone} disabled={!chosen.length} />
    </form>
  )
}

function BuyingEditor({
  data,
  busy,
  onCorrect,
  onDone,
}: {
  data: BusinessInterviewData
  busy: boolean
  onCorrect: Correct
  onDone: () => void
}) {
  const u = data.understanding
  const [modes, setModes] = useState(u.choices.fulfilment)
  const [pay, setPay] = useState(u.choices.payment)
  return (
    <form
      className="up-edit"
      onSubmit={async (e) => {
        e.preventDefault()
        let ok = await onCorrect('fulfilment', modes)
        if (ok && pay.length) ok = await onCorrect('payment', pay)
        if (ok) onDone()
      }}
    >
      <p className="up-edit__label">How it reaches customers</p>
      <Toggles options={u.options.fulfilment} chosen={modes} onToggle={(id) => setModes((c) => toggle(c, id))} />
      <p className="up-edit__label">How they pay</p>
      <Toggles options={u.options.payment} chosen={pay} onToggle={(id) => setPay((c) => toggle(c, id))} />
      <EditorActions busy={busy} onCancel={onDone} />
    </form>
  )
}

function PlaceEditor({
  data,
  busy,
  onCorrect,
  onDone,
}: {
  data: BusinessInterviewData
  busy: boolean
  onCorrect: Correct
  onDone: () => void
}) {
  const u = data.understanding
  const [location, setLocation] = useState(u.contact.location)
  const [area, setArea] = useState(u.choices.area)
  const [phone, setPhone] = useState(u.contact.phone)
  const [hours, setHours] = useState(u.contact.hours)
  return (
    <form
      className="up-edit"
      onSubmit={async (e) => {
        e.preventDefault()
        const steps: [Parameters<Correct>[0], string, string][] = [
          ['location', location, u.contact.location],
          ['area', area, u.choices.area],
          ['phone', phone, u.contact.phone],
          ['hours', hours, u.contact.hours],
        ]
        for (const [slot, value, before] of steps) {
          if (value.trim() && value.trim() !== before && !(await onCorrect(slot, [], value.trim()))) return
        }
        onDone()
      }}
    >
      {(
        [
          ['up-loc', 'Location', location, setLocation, 'Area and city'],
          ['up-area', 'Areas you serve or deliver to', area, setArea, 'Velachery and Adyar'],
          ['up-phone', 'Phone / WhatsApp', phone, setPhone, '98765 43210'],
          ['up-hours', 'Opening hours', hours, setHours, '9 am to 8 pm, Monday to Saturday'],
        ] as const
      ).map(([id, label, value, set, placeholder]) => (
        <div key={id}>
          <label className="up-edit__label" htmlFor={id}>
            {label}
          </label>
          <input
            id={id}
            className="up-input"
            value={value}
            placeholder={placeholder}
            onChange={(e) => set(e.target.value)}
          />
        </div>
      ))}
      <EditorActions busy={busy} onCancel={onDone} />
    </form>
  )
}
