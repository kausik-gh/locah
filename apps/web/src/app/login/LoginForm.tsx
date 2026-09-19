'use client'

import { useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { resolveDestinationIntent, siteUrl } from '@platform/auth'
import { createClient } from '@/lib/supabase/client'
import { Wordmark } from '@/components/public/Wordmark'

type Intent = 'signin' | 'signup'

/**
 * Turn an auth failure into something the person can act on.
 *
 * The provider's own wording describes its internals — "Anonymous sign-ins are
 * disabled" is what it says when the form was submitted empty — and putting
 * that in front of someone trying to open their business tells them nothing
 * and exposes how the platform is built. Anything unrecognised falls back to a
 * plain sentence rather than the raw message.
 */
function humanAuthError(message: string, intent: Intent): string {
  const m = message.toLowerCase()
  if (m.includes('anonymous')) {
    return 'Enter your email and password to continue.'
  }
  if (m.includes('invalid login credentials')) {
    return 'That email and password do not match. Check both and try again.'
  }
  if (m.includes('email not confirmed')) {
    return 'This email is not confirmed yet. Open the confirmation link we sent you.'
  }
  if (m.includes('already registered') || m.includes('already been registered')) {
    return 'There is already an account with this email. Sign in instead.'
  }
  if (m.includes('password') && (m.includes('least') || m.includes('short') || m.includes('weak'))) {
    return 'Choose a password of at least 8 characters.'
  }
  if (m.includes('rate limit') || m.includes('too many')) {
    return 'Too many attempts. Wait a minute and try again.'
  }
  if (m.includes('invalid') && m.includes('email')) {
    return 'That does not look like an email address.'
  }
  return intent === 'signup'
    ? 'We could not create the account. Check the details and try again.'
    : 'We could not sign you in. Check the details and try again.'
}

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<Intent | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()
  const supabase = createClient()
  const destination = resolveDestinationIntent(searchParams.get('destination'))

  // Which button was pressed. Both are submit buttons so that the browser's own
  // `required` and `type="email"` checks run first — as a plain click handler,
  // "Create an account" sent an empty sign-up straight to the provider.
  const intent = useRef<Intent>('signin')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const action = intent.current
    setError(null)
    setNotice(null)
    setBusy(action)

    if (action === 'signup') {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        // Not window.location.origin: that is whatever host this browser is on,
        // so signing up from a dev machine mails a localhost link to a real
        // inbox. Supabase only honours this if it matches the project's
        // Redirect URLs allowlist — otherwise it substitutes Site URL.
        options: { emailRedirectTo: siteUrl('/auth/callback') },
      })
      setBusy(null)
      if (error) {
        setError(humanAuthError(error.message, 'signup'))
      } else {
        setNotice(
          `We sent a confirmation link to ${email}. Open it to finish setting up your account — it expires shortly.`
        )
      }
      return
    }

    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setBusy(null)
    if (error) {
      setError(humanAuthError(error.message, 'signin'))
    } else {
      router.push(destination)
      router.refresh()
    }
  }

  return (
    <div className="locah-public ob-shell">
      <header className="ob-shell__head">
        <div className="lc-container">
          <Link href="/" aria-label="LOCAH home">
            <Wordmark />
          </Link>
        </div>
      </header>

      <main className="lc-container" style={{ maxWidth: '27rem', paddingBlock: '3rem 4rem' }}>
        <form className="lc-card" onSubmit={handleSubmit}>
          <h1 style={{ fontSize: '1.6rem', marginBottom: '0.35rem' }}>Sign in</h1>
          <p className="lc-muted lc-small" style={{ marginBottom: 'var(--sp-6)' }}>
            Use your email to continue to your business.
          </p>

          {error ? (
            <div role="alert" className="ob-error" style={{ marginBottom: 'var(--sp-4)' }}>
              <p>{error}</p>
            </div>
          ) : null}

          {notice ? (
            <div role="status" className="ob-notice" style={{ marginBottom: 'var(--sp-4)' }}>
              <p>{notice}</p>
            </div>
          ) : null}

          <div className="ob-field">
            <label htmlFor="email" className="ob-label">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="ob-input"
            />
          </div>

          <div className="ob-field">
            <label htmlFor="password" className="ob-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="ob-input"
            />
            <p className="lc-muted lc-small" style={{ marginTop: '0.35rem' }}>
              At least 8 characters.
            </p>
          </div>

          <div style={{ display: 'grid', gap: '0.6rem' }}>
            <button
              type="submit"
              onClick={() => {
                intent.current = 'signin'
              }}
              disabled={busy !== null}
              className="lc-btn lc-btn--primary lc-btn--block"
            >
              {busy === 'signin' ? 'Signing in…' : 'Sign in'}
            </button>
            <button
              type="submit"
              onClick={() => {
                intent.current = 'signup'
              }}
              disabled={busy !== null}
              className="lc-btn lc-btn--ghost lc-btn--block"
            >
              {busy === 'signup' ? 'Creating your account…' : 'Create an account'}
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
