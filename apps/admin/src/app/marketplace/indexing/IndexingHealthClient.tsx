'use client'

import { useState } from 'react'

type HealthRow = {
  business_id: string
  last_status: string
  last_indexed_at?: string | null
  last_attempt_at?: string | null
  last_error?: string | null
  last_reason?: string | null
}

type DeadLetter = {
  id: string
  event_type: string
  final_error?: string | null
  attempt_count?: number
  created_at?: string | null
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export default function IndexingHealthClient() {
  const [token, setToken] = useState('')
  const [status, setStatus] = useState('')
  const [health, setHealth] = useState<HealthRow[]>([])
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  async function load() {
    setError(null)
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    const res = await fetch(`${apiUrl}/v1/admin/marketplace/indexing${qs}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (!res.ok) {
      setError(`Load failed (${res.status})`)
      return
    }
    const json = (await res.json()) as {
      data: { health: HealthRow[]; dead_letters: DeadLetter[] }
    }
    setHealth(json.data.health || [])
    setDeadLetters(json.data.dead_letters || [])
  }

  async function reindex(businessId: string) {
    setBusyId(businessId)
    setError(null)
    try {
      const res = await fetch(
        `${apiUrl}/v1/admin/marketplace/indexing/${businessId}/reindex`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (!res.ok) {
        setError(`Re-index failed (${res.status})`)
        return
      }
      await load()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <div style={{ display: 'grid', gap: '0.6rem', maxWidth: '36rem' }}>
        <label>
          Super Admin bearer token
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.5rem' }}
          />
        </label>
        <label>
          Filter status (optional)
          <input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            placeholder="indexed | deindexed | failed | never"
            style={{ display: 'block', width: '100%', marginTop: '0.25rem', padding: '0.5rem' }}
          />
        </label>
        <button type="button" onClick={load} style={{ padding: '0.55rem 0.9rem', width: 'fit-content' }}>
          Load indexing health
        </button>
      </div>

      {error ? <p style={{ color: '#ff8f8f', marginTop: '1rem' }}>{error}</p> : null}

      <section style={{ marginTop: '1.75rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Business index status</h2>
        {health.length === 0 ? (
          <p style={{ opacity: 0.75 }}>No rows loaded yet.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.75rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', opacity: 0.7 }}>
                <th style={{ padding: '0.4rem' }}>Business</th>
                <th style={{ padding: '0.4rem' }}>Status</th>
                <th style={{ padding: '0.4rem' }}>Last indexed</th>
                <th style={{ padding: '0.4rem' }}>Reason / error</th>
                <th style={{ padding: '0.4rem' }} />
              </tr>
            </thead>
            <tbody>
              {health.map((row) => (
                <tr key={row.business_id} style={{ borderTop: '1px solid rgba(255,255,255,0.12)' }}>
                  <td style={{ padding: '0.5rem', fontFamily: 'ui-monospace, monospace' }}>
                    {row.business_id}
                  </td>
                  <td style={{ padding: '0.5rem' }}>{row.last_status}</td>
                  <td style={{ padding: '0.5rem' }}>{row.last_indexed_at || '—'}</td>
                  <td style={{ padding: '0.5rem', opacity: 0.85 }}>
                    {row.last_error || row.last_reason || '—'}
                  </td>
                  <td style={{ padding: '0.5rem' }}>
                    <button
                      type="button"
                      disabled={!token || busyId === row.business_id}
                      onClick={() => reindex(row.business_id)}
                    >
                      {busyId === row.business_id ? 'Re-indexing…' : 'Re-index'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Indexing dead letters</h2>
        {deadLetters.length === 0 ? (
          <p style={{ opacity: 0.75 }}>No marketplace dead-letter events.</p>
        ) : (
          <ul style={{ marginTop: '0.75rem', lineHeight: 1.6 }}>
            {deadLetters.map((d) => (
              <li key={d.id}>
                <code>{d.event_type}</code> · attempts {d.attempt_count ?? '?'} ·{' '}
                {d.final_error || 'no error text'}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
