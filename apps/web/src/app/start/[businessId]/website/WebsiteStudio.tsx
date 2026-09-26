'use client'

import { useCallback, useState } from 'react'
import type { BusinessInterviewData } from '@platform/contracts'
import { LivePreview } from './LivePreview'
import { WebsiteTalk } from './WebsiteTalk'

/** The website and the conversation that keeps shaping it, side by side. */
export function WebsiteStudio({
  businessId,
  src,
  initialStatus,
  interview,
}: {
  businessId: string
  src: string
  initialStatus: string | null
  interview: BusinessInterviewData | null
}) {
  const [version, setVersion] = useState(0)
  const changed = useCallback(() => setVersion((v) => v + 1), [])
  return (
    <div className={`ws${interview ? '' : ' ws--solo'}`}>
      <LivePreview businessId={businessId} src={src} initialStatus={initialStatus} refreshKey={version} />
      {interview ? <WebsiteTalk initial={interview} onChanged={changed} /> : null}
    </div>
  )
}
