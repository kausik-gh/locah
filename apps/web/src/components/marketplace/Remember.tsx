'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { forgetBrowse, rememberBrowse } from '@/lib/visitor-signals-client'

/** Notes, in this browser only, which kind of business was just looked at. */
export function Remember({
  family,
  category,
  q,
}: {
  family?: string | null
  category?: string | null
  q?: string | null
}) {
  // One visit counts once, even when an effect runs twice in development.
  const noted = useRef<string | null>(null)
  useEffect(() => {
    const key = `${family}|${category}|${q}`
    if (noted.current === key || !(family || category || q)) return
    noted.current = key
    rememberBrowse({ family, category, q })
  }, [family, category, q])
  return null
}

/** The visible way out: clears what the browser remembered and redraws. */
export function ForgetBrowsing({ label = 'Forget what I browsed' }: { label?: string }) {
  const router = useRouter()
  return (
    <button
      type="button"
      className="mx-forget"
      onClick={() => {
        forgetBrowse()
        router.refresh()
      }}
    >
      {label}
    </button>
  )
}
