'use client'

import { useTransition } from 'react'
import { setArchived } from './offering-actions'

export function ArchiveButton({ businessId, offeringId, archived }: { businessId: string; offeringId: string; archived: boolean }) {
  const [pending, start] = useTransition()
  return (
    <button
      type="button"
      className="btn-quiet"
      disabled={pending}
      onClick={() => start(async () => { await setArchived(businessId, offeringId, !archived) })}
    >
      {archived ? 'Restore' : 'Archive'}
    </button>
  )
}
