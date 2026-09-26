'use client'

import { useEffect, useId, useRef, useState } from 'react'
import type { TaxonomyMatch } from '@platform/contracts'
import { searchKinds } from '@/app/start/actions'

/**
 * "What kind of business?" — search, never a form.
 *
 * Owners type what they would say ("meat shop", "physio", "wedding
 * photographer"); LOCAH's taxonomy answers with the kinds it knows. Picking
 * one is optional context, never a gate before talking.
 */
export function KindSearch({
  value,
  onPick,
  placeholder = 'Search: meat shop, gym, dentist, hotel…',
  autoFocus = false,
  label = 'What kind of business?',
}: {
  value: TaxonomyMatch | null
  onPick: (match: TaxonomyMatch | null) => void
  placeholder?: string
  autoFocus?: boolean
  label?: string
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TaxonomyMatch[]>([])
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const listId = useId()
  const inputId = useId()
  const seq = useRef(0)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      return
    }
    const mine = ++seq.current
    const timer = window.setTimeout(async () => {
      const found = await searchKinds(q)
      if (mine === seq.current) {
        setResults(found)
        setActive(0)
        setOpen(true)
      }
    }, 180)
    return () => window.clearTimeout(timer)
  }, [query])

  function pick(match: TaxonomyMatch) {
    onPick(match)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  if (value) {
    return (
      <div className="ks-picked">
        <span className="ks-picked__label">{label}</span>
        <span className="ks-chip">
          <strong>{value.subcategory_label}</strong>
          <span>{value.category_label}</span>
          <button type="button" aria-label={`Remove ${value.subcategory_label}`} onClick={() => onPick(null)}>
            ×
          </button>
        </span>
      </div>
    )
  }

  return (
    <div className="ks">
      <label className="ks-label" htmlFor={inputId}>
        {label} <span>optional</span>
      </label>
      <div className="ks-field">
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="m13 13 4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          id={inputId}
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          autoFocus={autoFocus}
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(false)
          }}
          onFocus={() => results.length && setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (!results.length) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActive((i) => Math.min(i + 1, results.length - 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((i) => Math.max(i - 1, 0))
            } else if (e.key === 'Enter') {
              e.preventDefault()
              pick(results[active])
            } else if (e.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
      </div>
      {open && results.length > 0 ? (
        <ul className="ks-results" id={listId} role="listbox">
          {results.map((r, i) => (
            <li
              key={r.subcategory_key}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault()
                pick(r)
              }}
              onMouseEnter={() => setActive(i)}
            >
              <strong>{r.subcategory_label}</strong>
              <span>{r.category_label}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {open && query.trim().length >= 2 && results.length === 0 ? (
        <p className="ks-none">Nothing by that name — just describe it to LOCAH instead.</p>
      ) : null}
    </div>
  )
}
