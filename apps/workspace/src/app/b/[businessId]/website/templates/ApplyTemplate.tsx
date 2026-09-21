'use client'

import { useState } from 'react'
import { applyTemplate } from './actions'

/**
 * Choosing a template, with the consequence stated before it happens.
 *
 * Applying replaces the current draft — that is the honest meaning of "use this
 * one instead", and it is not something to discover afterwards. So the first
 * click asks, and only the second one does it. A business that has never
 * published has nothing to lose and is told so; one that has published is told
 * its live site is untouched until it publishes again, because that is the
 * thing they would actually worry about.
 */
export function ApplyTemplate({
  businessId,
  templateId,
  templateName,
  isCurrent,
  hasDraftWork,
  disabled,
  disabledReason,
}: {
  businessId: string
  templateId: string
  templateName: string
  isCurrent: boolean
  hasDraftWork: boolean
  disabled?: boolean
  disabledReason?: string
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)

  if (disabled) {
    return (
      <p className="tpl-locked" role="note">
        {disabledReason}
      </p>
    )
  }

  if (isCurrent) {
    return (
      <p className="tpl-current" role="status">
        You are using this one
      </p>
    )
  }

  if (!confirming) {
    return (
      <button type="button" className="btn btn-ghost" onClick={() => setConfirming(true)}>
        Use this template
      </button>
    )
  }

  return (
    <form action={applyTemplate} onSubmit={() => setBusy(true)} className="tpl-confirm">
      <input type="hidden" name="businessId" value={businessId} />
      <input type="hidden" name="templateId" value={templateId} />
      <p className="tpl-confirm__text">
        {hasDraftWork
          ? `This replaces your current draft with ${templateName}. Anything you have edited but not published will be lost. Your live site does not change until you publish.`
          : `Start from ${templateName}? You can change everything on it afterwards.`}
      </p>
      <div className="tpl-confirm__row">
        <button type="submit" className="btn" disabled={busy}>
          {busy ? 'Applying…' : `Use ${templateName}`}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setConfirming(false)}
          disabled={busy}
        >
          Keep what I have
        </button>
      </div>
    </form>
  )
}
