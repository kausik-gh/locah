'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { BusinessInterviewData } from '@platform/contracts'
import { interviewAction } from '../interview/actions'

/** An explicit owner approval, separate from approving Website wording. */
export function SetupOfferings({ data }: { data: BusinessInterviewData }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const bp = data.blueprint
  const names = bp.website_draft.offerings.map((item) => item.name.trim()).filter(Boolean)
  const approved = bp.approved_modules.includes('offerings-catalog')
  if (!approved || names.length === 0 || bp.completion_state.status !== 'built') return null

  const applied = new Set(bp.applied_setup_offerings.map((name) => name.toLocaleLowerCase()))
  const remaining = names.filter((name) => !applied.has(name.toLocaleLowerCase()))

  async function apply() {
    setBusy(true)
    setError('')
    try {
      const result = await interviewAction(bp.business_id, {
        action: 'setup',
        revision: bp.revision,
        request_id: crypto.randomUUID(),
      })
      if (!result.ok) {
        setError(result.error)
        if (result.stale) router.refresh()
        return
      }
      router.refresh()
    } catch {
      setError('Could not create the draft items. Nothing was published; please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="lp-setup" aria-label="Suggested catalogue setup">
      <h2>What I can set up next</h2>
      <p>These are the items you told Locah about. Review them before adding them to your real catalogue.</p>
      <ul>
        {names.map((name) => (
          <li key={name}>
            <strong>{name}</strong>
            <span>{applied.has(name.toLocaleLowerCase()) ? 'Draft created' : 'Price and details needed'}</span>
          </li>
        ))}
      </ul>
      {remaining.length > 0 ? (
        <button type="button" className="lc-btn lc-btn--primary" disabled={busy} onClick={() => void apply()}>
          {busy ? 'Creating drafts…' : `Use these ${remaining.length} as draft catalogue items`}
        </button>
      ) : (
        <p role="status">Draft items created. Add prices, units and options in Workspace before selling them.</p>
      )}
      <p className="lp-setup__note">No prices are invented. These stay private drafts until you complete and publish them.</p>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  )
}
