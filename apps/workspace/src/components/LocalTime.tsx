'use client'

import { useEffect, useState } from 'react'

/**
 * A timestamp as a person reads it.
 *
 * Workspace was printing `2026-09-22T05:30:00+00:00` in the When column of the
 * bookings list — the wire format, which is both unreadable and, because it is
 * in UTC, shows an 11am appointment as 5:30. Formatting has to happen in the
 * browser: a server component would format in the server's zone, which is
 * neither the owner's nor the business's and would differ between render and
 * hydration.
 *
 * The ISO string is rendered until the browser takes over, so the value is
 * never missing — only briefly unformatted.
 *
 * Note this shows the *viewer's* zone. That is right for someone working in
 * their own shop and wrong for an owner reading it from another country; the
 * business's configured timezone is the eventual source, once it is carried
 * this far.
 */
export function LocalTime({
  value,
  mode = 'datetime',
}: {
  value: string | null | undefined
  mode?: 'datetime' | 'date'
}) {
  const [text, setText] = useState<string | null>(null)

  useEffect(() => {
    if (!value) return
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return
    setText(
      mode === 'date'
        ? d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
        : d.toLocaleString(undefined, {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
            hour: 'numeric',
            minute: '2-digit',
          })
    )
  }, [value, mode])

  if (!value) return <>—</>
  return <time dateTime={value}>{text ?? value}</time>
}
