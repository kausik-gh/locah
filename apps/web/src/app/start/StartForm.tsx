'use client'

import { useFormState, useFormStatus } from 'react-dom'
import { createBusinessAction, type CreateBusinessState } from './actions'

const INITIAL: CreateBusinessState = { error: null }
function Submit() {
  const { pending } = useFormStatus()
  return <button className="lc-btn lc-btn--primary lc-btn--lg" disabled={pending}>
    {pending ? 'Saving your business…' : 'Chat with Locah →'}
  </button>
}

export function StartForm() {
  const [state, action] = useFormState(createBusinessAction, INITIAL)
  return <form action={action}>
    {state.error && <p className="ob-error" role="alert">{state.error}</p>}
    <div className="ob-field">
      <label className="ob-label" htmlFor="display_name">First, what is your business called?</label>
      <input id="display_name" name="display_name" className="ob-input" required maxLength={200}
        autoComplete="organization" placeholder="Your business name" />
      <p className="ob-help">We’ll save your business first. Your answers and images can follow at your pace.</p>
    </div>
    <Submit />
    <button type="button" className="lc-btn" disabled aria-describedby="voice-note" style={{ marginLeft: 12 }}>Talk to Locah</button>
    <p id="voice-note" className="ob-help">Voice is not available yet. You can complete everything in chat.</p>
  </form>
}
