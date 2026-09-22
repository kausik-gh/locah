import Link from 'next/link'
import React from 'react'
import { Wordmark } from '@/components/public/Wordmark'

const STEPS = ['Your business', 'Your website', 'Your tools', 'Done'] as const

/** Shared chrome for the /start onboarding sequence. */
/** `wide` gives a step room for a real website preview rather than prose. */
export function OnboardingShell({
  children,
  wide = false,
}: {
  children: React.ReactNode
  wide?: boolean
}) {
  return (
    <div className="locah-public ob-shell">
      <header className="ob-shell__head">
        <div className="lc-container">
          <Link href="/" aria-label="LOCAH home">
            <Wordmark />
          </Link>
        </div>
      </header>
      <main
        className={`lc-container ob-shell__body${wide ? ' ob-shell__body--wide' : ''}`}
      >
        {children}
      </main>
    </div>
  )
}

/** Where the owner is in the sequence. `current` is 1-based. */
export function Steps({ current }: { current: number }) {
  return (
    <ol className="ob-steps" aria-label="Setup progress">
      {STEPS.map((label, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <li
            key={label}
            className="ob-step"
            data-state={active ? 'active' : done ? 'done' : 'todo'}
            aria-current={active ? 'step' : undefined}
          >
            <span className="ob-step__n" aria-hidden="true">
              {done ? '✓' : n}
            </span>
            {label}
          </li>
        )
      })}
    </ol>
  )
}

/** A recoverable failure inside onboarding, stated plainly. */
export function OnboardingError({
  title,
  code,
  message,
  children,
}: {
  title: string
  code?: string
  message: string
  children?: React.ReactNode
}) {
  return (
    <div role="alert" className="ob-error">
      <h2>{title}</h2>
      <p>
        {message}
        {code ? ` (${code})` : ''}
      </p>
      {children ? <div style={{ marginTop: 'var(--sp-4)' }}>{children}</div> : null}
    </div>
  )
}
