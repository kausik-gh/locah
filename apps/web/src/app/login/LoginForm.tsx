'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { resolveDestinationIntent, siteUrl } from '@platform/auth'
import { createClient } from '@/lib/supabase/client'
import { Wordmark } from '@/components/public/Wordmark'

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const supabase = createClient()
  const destination = resolveDestinationIntent(searchParams.get('destination'))

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)

    if (error) {
      setError(error.message)
    } else {
      router.push(destination)
      router.refresh()
    }
  }

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setNotice(null)
    setBusy(true)
    const { error } = await supabase.auth.signUp({
      email,
      password,
      // Not window.location.origin: that is whatever host this browser is on,
      // so signing up from a dev machine mails a localhost link to a real
      // inbox. Supabase only honours this if it matches the project's Redirect
      // URLs allowlist — otherwise it silently substitutes Site URL.
      options: { emailRedirectTo: siteUrl('/auth/callback') },
    })
    setBusy(false)

    if (error) {
      setError(error.message)
    } else {
      setNotice(
        `We sent a confirmation link to ${email}. Open it to finish setting up your account — it expires shortly.`
      )
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
        <form className="lc-card" onSubmit={handleLogin}>
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
              className="ob-input"
            />
          </div>

          <div style={{ display: 'grid', gap: '0.6rem' }}>
            <button type="submit" disabled={busy} className="lc-btn lc-btn--primary lc-btn--block">
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={handleSignUp}
              disabled={busy}
              className="lc-btn lc-btn--ghost lc-btn--block"
            >
              Create an account
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
