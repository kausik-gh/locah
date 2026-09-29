'use client'

import { useCallback, useEffect, useState } from 'react'

type Line = {
  id: string
  title: string
  quantity: number
  modifiers: string[]
  station_name: string
  prep_status: string
  origin: string
  attention: string | null
}

type Notice = { kind: string; summary: string; at: string }

type Ticket = {
  id: string
  ticket_number: string
  channel_label: string
  service_mode_label: string
  service_label: string
  priority: string
  attention: string | null
  notes: string
  entered_at: string
  elapsed_seconds: number
  version: number
  lines: Line[]
  events: Notice[]
}

export type Board = {
  now: string
  station_id: string | null
  stations: { id: string; key: string; name: string }[]
  columns: { new: Ticket[]; preparing: Ticket[]; ready: Ticket[] }
}

const COLUMNS: { key: keyof Board['columns']; label: string; action: string; step: string }[] = [
  { key: 'new', label: 'New', action: 'Start', step: 'start' },
  { key: 'preparing', label: 'Preparing', action: 'Ready', step: 'ready' },
  { key: 'ready', label: 'Ready', action: 'Served', step: 'serve' },
]

function ageLabel(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  if (mins < 1) return 'Just in'
  if (mins < 60) return `${mins} min`
  const hours = Math.floor(mins / 60)
  return `${hours}h ${mins % 60}m`
}

export function KdsBoard({
  businessId,
  businessName,
  apiUrl,
  initialToken,
  initial,
}: {
  businessId: string
  businessName: string
  apiUrl: string
  initialToken: string
  initial: Board
}) {
  const [board, setBoard] = useState(initial)
  const [stationId, setStationId] = useState<string | null>(initial.station_id)
  const [now, setNow] = useState(() => Date.now())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async (station: string | null) => {
    const query = station ? `?station_id=${station}` : ''
    const res = await fetch(`${apiUrl}/v1/platform/businesses/${businessId}/kitchen/board${query}`, {
      headers: { Authorization: `Bearer ${initialToken}` },
      cache: 'no-store',
    })
    if (!res.ok) {
      setError('The pass could not refresh.')
      return
    }
    const body = (await res.json()) as { data: Board }
    setBoard(body.data)
    setError('')
  }, [apiUrl, businessId, initialToken])

  useEffect(() => {
    const clock = window.setInterval(() => setNow(Date.now()), 15000)
    const poll = window.setInterval(() => { void load(stationId) }, 8000)
    return () => {
      window.clearInterval(clock)
      window.clearInterval(poll)
    }
  }, [load, stationId])

  async function act(ticket: Ticket, step: string) {
    setBusy(true)
    setError('')
    const res = await fetch(
      `${apiUrl}/v1/platform/businesses/${businessId}/kitchen/tickets/${ticket.id}/${step}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${initialToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ station_id: stationId, version: ticket.version }),
      },
    )
    setBusy(false)
    if (!res.ok) {
      const text = await res.text()
      setError(text.includes('refresh') ? 'This ticket changed. Pulling the pass again.' : 'That step did not go through.')
    }
    await load(stationId)
  }

  async function pickStation(id: string | null) {
    setStationId(id)
    await load(id)
  }

  return (
    <div className="kds-shell">
      <header className="kds-top">
        <strong>{businessName || 'Kitchen'}</strong>
        <div className="kds-stations" role="tablist" aria-label="Stations">
          <button type="button" className={stationId ? '' : 'is-on'} onClick={() => { void pickStation(null) }}>
            All stations
          </button>
          {board.stations.map((station) => (
            <button
              key={station.id}
              type="button"
              className={stationId === station.id ? 'is-on' : ''}
              onClick={() => { void pickStation(station.id) }}
            >
              {station.name}
            </button>
          ))}
        </div>
        <span className="kds-top__spacer" />
        <a href={`/b/${businessId}/kitchen`}>Stations</a>
      </header>
      {error ? <p className="kds-error" role="alert">{error}</p> : null}
      <div className="kds-board">
        {COLUMNS.map((column) => {
          const tickets = board.columns[column.key]
          return (
            <section key={column.key} className="kds-col" data-testid={`kds-column-${column.key}`} aria-label={column.label}>
              <h2>{column.label} <span className="kds-col__count">{tickets.length}</span></h2>
              {tickets.length === 0 ? <p className="kds-empty">Nothing here.</p> : null}
              {tickets.map((ticket) => {
                const waited = Math.max(
                  ticket.elapsed_seconds,
                  Math.floor((now - Date.parse(ticket.entered_at)) / 1000),
                )
                const late = column.key === 'new' && waited >= 600
                return (
                  <article
                    key={ticket.id}
                    className={[
                      'kds-card',
                      ticket.priority === 'rush' ? 'is-rush' : '',
                      ticket.attention === 'cancel' ? 'is-cancel' : '',
                      late ? 'is-late' : '',
                    ].filter(Boolean).join(' ')}
                    data-testid="kds-ticket"
                    data-ticket={ticket.ticket_number}
                  >
                    <div className="kds-card__head">
                      <span className="kds-card__num">{ticket.ticket_number}</span>
                      <span className="kds-card__age" data-testid="kds-elapsed">{ageLabel(waited)}</span>
                    </div>
                    <div className="kds-card__where">
                      <span>{ticket.channel_label}</span>
                      <span>{ticket.service_mode_label}</span>
                      <span>{ticket.service_label}</span>
                      <span className={ticket.priority === 'rush' ? 'kds-chip is-rush' : 'kds-chip'} data-testid="kds-priority">
                        {ticket.priority === 'rush' ? 'Rush' : 'Normal'}
                      </span>
                    </div>
                    {ticket.attention === 'cancel' ? (
                      <p className="kds-banner">Order cancelled. Do not send this.</p>
                    ) : null}
                    {ticket.events.filter((event) => event.kind !== 'cancel_after_start').map((event) => (
                      <p key={`${event.at}-${event.summary}`} className="kds-banner">{event.summary}</p>
                    ))}
                    {ticket.notes ? <p className="kds-notes">{ticket.notes}</p> : null}
                    <ul className="kds-items">
                      {ticket.lines.map((line) => (
                        <li key={line.id} className={line.attention === 'cancel' ? 'kds-item is-off' : 'kds-item'}>
                          <strong>{line.quantity}</strong>
                          <span>
                            {line.title}
                            {stationId ? '' : line.station_name ? ` · ${line.station_name}` : ''}
                            {line.origin === 'added' ? ' · added' : ''}
                          </span>
                          {line.modifiers.map((modifier) => <em key={modifier}>{modifier}</em>)}
                        </li>
                      ))}
                    </ul>
                    <div className="kds-actions">
                      {ticket.attention === 'cancel' ? (
                        <button type="button" className="kds-action is-primary" disabled={busy} onClick={() => { void act(ticket, 'clear') }}>
                          Taken off
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="kds-action is-primary"
                          data-testid={`kds-${column.step}`}
                          disabled={busy}
                          onClick={() => { void act(ticket, column.step) }}
                        >
                          {column.action}
                        </button>
                      )}
                      {ticket.priority === 'normal' ? (
                        <button
                          type="button"
                          className="kds-action"
                          disabled={busy}
                          onClick={() => {
                            void fetch(
                              `${apiUrl}/v1/platform/businesses/${businessId}/kitchen/tickets/${ticket.id}/priority`,
                              {
                                method: 'POST',
                                headers: {
                                  Authorization: `Bearer ${initialToken}`,
                                  'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ priority: 'rush', version: ticket.version }),
                              },
                            ).then(() => load(stationId))
                          }}
                        >
                          Rush
                        </button>
                      ) : null}
                    </div>
                  </article>
                )
              })}
            </section>
          )
        })}
      </div>
    </div>
  )
}
