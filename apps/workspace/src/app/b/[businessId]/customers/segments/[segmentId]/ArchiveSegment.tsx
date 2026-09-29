'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { archiveSegment } from '../segment-actions'

export function ArchiveSegment({ businessId, segmentId }: { businessId: string; segmentId: string }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  return (
    <span>
      <button type="button" className="btn-ghost" disabled={pending} onClick={() => start(async () => {
        const r = await archiveSegment(businessId, segmentId)
        if (!r.ok) return setError(r.message)
        router.push(`/b/${businessId}/customers/segments`)
      })}>{pending ? 'Removing…' : 'Remove segment'}</button>
      {error ? <span className="bos-error" role="status">{error}</span> : null}
    </span>
  )
}
