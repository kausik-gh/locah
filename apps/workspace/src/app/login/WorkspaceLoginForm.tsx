'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createSupabaseBrowserClientInstance } from '@platform/auth'

const supabase = createSupabaseBrowserClientInstance(
  process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://127.0.0.1:54321',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature'
)

export function WorkspaceLoginForm({ destination }: { destination: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const result = await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)
    if (result.error) {
      setError('We could not sign you in. Check your email and password, then try again.')
      return
    }
    router.replace(destination)
    router.refresh()
  }

  return (
    <main style={{ maxWidth: 420, margin: '10vh auto', padding: '2rem' }}>
      <form onSubmit={signIn} style={{ display: 'grid', gap: '1rem' }}>
        <p style={{ fontWeight: 700, color: 'var(--color-primary)' }}>LOCAH Workspace</p>
        <h1>Sign in to your Workspace</h1>
        <p style={{ color: 'var(--color-muted)' }}>
          This Workspace has its own secure sign-in on the staging address. Use the same account as
          on Locah.
        </p>
        {error ? <p role="alert" style={{ color: 'var(--status-bad-fg)' }}>{error}</p> : null}
        <label style={{ display: 'grid', gap: 6 }}>
          Email
          <input type="email" autoComplete="email" required value={email}
            onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          Password
          <input type="password" autoComplete="current-password" required value={password}
            onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button type="submit" disabled={busy} className="btn btn-primary">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
