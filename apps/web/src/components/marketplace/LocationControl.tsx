'use client'

import { useEffect, useId, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { clearPlace, savePlace } from '@/lib/visitor-signals-client'

type Suggestion = { city: string; state: string }

/**
 * "Where are you?" — optional, and never a wall.
 *
 * Current location is rounded to two decimals (about a kilometre) in the
 * browser before it leaves the device, and is kept in a cookie on this
 * device only. Declining permission just leaves the Marketplace ordered
 * by what is newest; typing a town or PIN works the same as sharing.
 */
export function LocationControl({
  label,
  cities = [],
  variant = 'pill',
}: {
  label?: string | null
  cities?: Array<{ city: string; count: number }>
  variant?: 'pill' | 'inline'
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [status, setStatus] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const panelId = useId()
  const wrap = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    input.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onClick = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [open])

  useEffect(() => {
    const typed = text.trim()
    if (typed.length < 2 || /^\d+$/.test(typed)) {
      setSuggestions([])
      return
    }
    const ctrl = new AbortController()
    const t = window.setTimeout(() => {
      fetch(`/api/places?q=${encodeURIComponent(typed)}`, { signal: ctrl.signal })
        .then((r) => r.json())
        .then((d) => setSuggestions((d.suggestions || []).slice(0, 6)))
        .catch(() => undefined)
    }, 160)
    return () => {
      ctrl.abort()
      window.clearTimeout(t)
    }
  }, [text])

  function done(message: string) {
    setStatus(message)
    setBusy(false)
    setOpen(false)
    router.refresh()
  }

  async function choose(typed: string) {
    const q = typed.trim()
    if (!q) return
    setBusy(true)
    setStatus('Finding that place…')
    try {
      const res = await fetch(`/api/places?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      if (!data.resolved) {
        setBusy(false)
        setStatus(`We could not place “${q}”. Try the town it is in, or a 6-digit PIN.`)
        return
      }
      savePlace({ l: data.resolved.label, p: q })
      done(`Showing businesses near ${data.resolved.label}.`)
    } catch {
      setBusy(false)
      setStatus('That did not work. Check your connection and try again.')
    }
  }

  function useDevice() {
    if (!('geolocation' in navigator)) {
      setStatus('This browser cannot share a location. Type your town or PIN instead.')
      return
    }
    setBusy(true)
    setStatus('Asking your browser…')
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const near = `${pos.coords.latitude.toFixed(2)},${pos.coords.longitude.toFixed(2)}`
        try {
          const res = await fetch(`/api/places?near=${near}`)
          const data = await res.json()
          if (!data.resolved) {
            setBusy(false)
            setStatus('That location is outside the areas we can order by yet. Type a town instead.')
            return
          }
          savePlace({ l: data.resolved.label, n: near })
          done(`Showing businesses near ${data.resolved.label}.`)
        } catch {
          setBusy(false)
          setStatus('That did not work. Type your town or PIN instead.')
        }
      },
      () => {
        setBusy(false)
        setStatus('Location is off for this site. You can type your town or PIN instead.')
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
    )
  }

  function forget() {
    clearPlace()
    done('Location cleared.')
  }

  return (
    <div className={`mx-loc mx-loc--${variant}`} ref={wrap}>
      <button
        type="button"
        className="mx-loc__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Z" />
          <circle cx="12" cy="9.5" r="2.5" />
        </svg>
        <span>{label ? `Near ${label}` : 'Choose your area'}</span>
      </button>
      {open ? (
        <div className="mx-loc__panel" id={panelId} role="dialog" aria-label="Choose your area">
          <button type="button" className="mx-loc__device" onClick={useDevice} disabled={busy}>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" />
            </svg>
            Use my current location
          </button>
          <p className="mx-loc__note">
            Rounded to about 1 km and kept in this browser. We do not store it.
          </p>
          <form
            className="mx-loc__form"
            onSubmit={(e) => {
              e.preventDefault()
              void choose(text)
            }}
          >
            <label htmlFor={`${panelId}-q`}>Or type a town or PIN</label>
            <div className="mx-loc__row">
              <input
                id={`${panelId}-q`}
                ref={input}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Chennai, Kovai, 600040"
                autoComplete="off"
                inputMode="search"
              />
              <button type="submit" className="lc-btn lc-btn--ink lc-btn--sm" disabled={busy || !text.trim()}>
                Set
              </button>
            </div>
          </form>
          {suggestions.length > 0 ? (
            <ul className="mx-loc__suggest" aria-label="Matching towns">
              {suggestions.map((s) => (
                <li key={`${s.city}-${s.state}`}>
                  <button type="button" onClick={() => void choose(s.city)}>
                    {s.city}
                    <small>{s.state}</small>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {cities.length > 0 ? (
            <div className="mx-loc__cities">
              <p>Towns with listings</p>
              <div>
                {cities.slice(0, 8).map((c) => (
                  <button type="button" key={c.city} onClick={() => void choose(c.city)}>
                    {c.city} <span className="lc-num">{c.count}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {label ? (
            <button type="button" className="mx-loc__clear" onClick={forget}>
              Clear my location
            </button>
          ) : null}
          <p className="mx-loc__status" role="status" aria-live="polite">
            {status}
          </p>
        </div>
      ) : (
        <span className="lc-sr" role="status" aria-live="polite">
          {status}
        </span>
      )}
    </div>
  )
}
