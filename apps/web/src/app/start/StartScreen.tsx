'use client'

import { useState, useTransition } from 'react'
import type { TaxonomyMatch } from '@platform/contracts'
import { KindSearch } from '@/components/onboarding/KindSearch'
import { MicIcon } from '@/components/onboarding/icons'
import { startConversation } from './actions'

/**
 * Create Business = talk to LOCAH.
 *
 * Three ways in, one conversation: type about the business, talk, or pick
 * what kind it is first. None is a gate — a picked kind is context for
 * LOCAH's first question, and a first message is answered on the next screen.
 */
export function StartScreen() {
  const [text, setText] = useState('')
  const [kind, setKind] = useState<TaxonomyMatch | null>(null)
  const [error, setError] = useState('')
  const [pending, startTransition] = useTransition()
  const [going, setGoing] = useState<'text' | 'talk' | ''>('')

  function go(talk: boolean) {
    setError('')
    setGoing(talk ? 'talk' : 'text')
    startTransition(async () => {
      const res = await startConversation({
        text: talk ? '' : text,
        categoryKey: kind?.category_key,
        subcategoryKey: kind?.subcategory_key,
        talk,
      })
      // Only reached on failure: success redirects into the conversation.
      if (res?.error) {
        setError(res.error)
        setGoing('')
      }
    })
  }

  const canSend = Boolean(text.trim() || kind)

  return (
    <div className="st">
      <p className="st-eyebrow">New business</p>
      <h1 className="st-title">
        Let&rsquo;s set up your <em>business.</em>
      </h1>
      <p className="st-lede">
        Tell LOCAH what you do. You don&rsquo;t need to know what to fill in — just describe it
        naturally.
      </p>

      <form
        className="st-card"
        onSubmit={(e) => {
          e.preventDefault()
          if (canSend && !pending) go(false)
        }}
      >
        <label className="lc-sr" htmlFor="st-about">
          About your business
        </label>
        <textarea
          id="st-about"
          className="st-input"
          value={text}
          rows={4}
          maxLength={4000}
          disabled={pending}
          placeholder="We sell chicken, mutton and seafood by the kg in Nookampalayam. People order on WhatsApp and we deliver nearby…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && canSend && !pending) {
              e.preventDefault()
              go(false)
            }
          }}
        />
        <div className="st-actions">
          <button
            type="button"
            className="st-talk"
            disabled={pending}
            onClick={() => go(true)}
          >
            <MicIcon />
            {going === 'talk' ? 'Opening…' : 'Talk to LOCAH'}
          </button>
          <button type="submit" className="lc-btn lc-btn--primary st-send" disabled={!canSend || pending}>
            {going === 'text' ? 'Reading…' : 'Continue'}
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </form>
      {error ? (
        <p className="st-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="st-kind">
        <KindSearch value={kind} onPick={setKind} />
        {!kind ? <p className="st-hint">Not sure? Just talk to LOCAH.</p> : null}
      </div>

      <p className="st-foot">Nothing is published until you choose to.</p>
    </div>
  )
}
