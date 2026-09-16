'use client'

import { useFormState, useFormStatus } from 'react-dom'
import { createBusinessAction, type CreateBusinessState } from './actions'

export type BusinessType = { type_id: string; display_name: string; category: string }

const INITIAL: CreateBusinessState = { error: null }

/** What choosing this type actually changes, in the owner's terms. Keyed by the
 *  type ids the platform supports; anything unrecognised simply shows no hint
 *  rather than a guess. */
const TYPE_HINT: Record<string, string> = {
  restaurant: 'Menu, orders, delivery or pickup',
  cafe: 'Menu, orders, quick pickup',
  retail: 'Products, stock, fulfilment',
  salon: 'Services, appointments, staff',
  spa: 'Treatments, appointments, staff',
  hotel: 'Rooms, availability, reservations',
  homestay: 'Rooms, availability, reservations',
  gym: 'Plans, memberships, classes',
  studio: 'Classes, schedules, memberships',
  clinic: 'Services, appointments, patients',
  professional_service: 'Services, enquiries, follow-up',
  education: 'Courses, enrolment, schedules',
  other: 'A general set you can adjust later',
  not_sure: 'We will suggest a starting point',
}

function SubmitButton() {
  const { pending } = useFormStatus()
  return (
    <button type="submit" disabled={pending} className="lc-btn lc-btn--primary lc-btn--lg">
      {pending ? 'Creating your business…' : 'Create business & build my website'}
    </button>
  )
}

export function StartForm({ types }: { types: BusinessType[] }) {
  const [state, formAction] = useFormState(createBusinessAction, INITIAL)

  return (
    <form action={formAction}>
      {state.error ? (
        <div role="alert" className="ob-error" style={{ marginBottom: 'var(--sp-5)' }}>
          <p>{state.error}</p>
        </div>
      ) : null}

      <fieldset className="ob-field" style={{ border: 0, padding: 0, margin: '0 0 var(--sp-7)' }}>
        <legend className="ob-label" style={{ marginBottom: '0.6rem' }}>
          What kind of business is it?
        </legend>
        <p className="ob-help" style={{ margin: '0 0 var(--sp-4)' }}>
          This is the important one — it decides how your website is built and which tools we
          recommend. You can change it later.
        </p>
        <div className="ob-types">
          {types.map((t) => (
            <label className="ob-type" key={t.type_id}>
              <input type="radio" name="business_type" value={t.type_id} required />
              <span className="ob-type__box">
                <span className="ob-type__name">{t.display_name}</span>
                {TYPE_HINT[t.type_id] ? (
                  <span className="ob-type__hint">{TYPE_HINT[t.type_id]}</span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="ob-field">
        <label className="ob-label" htmlFor="display_name">
          What is your business called?
        </label>
        <input
          id="display_name"
          name="display_name"
          className="ob-input"
          required
          maxLength={200}
          placeholder="e.g. Corner Coffee House"
        />
        <p className="ob-help">
          The name customers will see on your website and your Marketplace listing.
        </p>
      </div>

      <div className="ob-field">
        <label className="ob-label" htmlFor="tagline">
          Describe it in one line
        </label>
        <input
          id="tagline"
          name="tagline"
          className="ob-input"
          maxLength={200}
          placeholder="e.g. Small-batch roastery and neighbourhood café"
        />
        <p className="ob-help">
          This becomes the line under your name, on your site and in the Marketplace.
        </p>
      </div>

      <div className="ob-field">
        <label className="ob-label" htmlFor="description">
          Tell us a bit more
        </label>
        <textarea
          id="description"
          name="description"
          className="ob-textarea"
          maxLength={2000}
          placeholder="What you do, what makes it yours, who comes to you. Two or three sentences is plenty."
        />
        <p className="ob-help">
          This is what LOCAH writes your website from — the more real detail you give, the less
          you will have to edit afterwards.
        </p>
      </div>

      <SubmitButton />
    </form>
  )
}
