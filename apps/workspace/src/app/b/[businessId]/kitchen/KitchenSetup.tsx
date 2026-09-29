'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { addStation, saveRoute } from './actions'

type Station = { id: string; key: string; name: string }
type Offering = { id: string; title: string; kind: string }

export function KitchenSetup({
  businessId,
  stations,
  kinds,
  routes,
  offerings,
}: {
  businessId: string
  stations: Station[]
  kinds: { key: string; name: string }[]
  routes: { offering_id: string; station_ids: string[] }[]
  offerings: Offering[]
}) {
  const router = useRouter()
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [pending, start] = useTransition()
  const routed = new Map(routes.map((route) => [route.offering_id, new Set(route.station_ids)]))
  const open = offerings.filter((item) => item.kind === 'menu_item' || routed.has(item.id))

  function run(work: () => Promise<void>) {
    start(async () => {
      try {
        await work()
        setError('')
        router.refresh()
      } catch {
        setError('That did not save.')
      }
    })
  }

  return (
    <div style={{ display: 'grid', gap: '1.5rem', maxWidth: '46rem' }}>
      {error ? <p role="alert">{error}</p> : null}
      <section>
        <h2>Stations</h2>
        <ul>
          {stations.map((station) => <li key={station.id}>{station.name}</li>)}
          {stations.length === 0 ? <li>No stations yet. General is created when the first prepared order arrives.</li> : null}
        </ul>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.6rem' }}>
          {kinds.filter((kind) => !stations.some((station) => station.key === kind.key)).map((kind) => (
            <button
              key={kind.key}
              type="button"
              className="btn"
              disabled={pending}
              onClick={() => run(() => addStation(businessId, { key: kind.key, name: kind.name }))}
            >
              Add {kind.name}
            </button>
          ))}
        </div>
        <form
          style={{ display: 'flex', gap: '0.5rem', marginTop: '0.8rem' }}
          onSubmit={(event) => {
            event.preventDefault()
            if (!name.trim()) return
            run(async () => {
              await addStation(businessId, { name: name.trim() })
              setName('')
            })
          }}
        >
          <input
            aria-label="Station name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Your own station"
            maxLength={40}
          />
          <button type="submit" className="btn" disabled={pending}>Add station</button>
        </form>
      </section>
      <section>
        <h2>What each station cooks</h2>
        {open.length === 0 ? <p>No prepared items yet.</p> : null}
        {open.map((item) => {
          const selected = routed.get(item.id) ?? new Set<string>()
          return (
            <fieldset key={item.id} style={{ marginBottom: '0.8rem' }}>
              <legend>{item.title}</legend>
              {stations.map((station) => (
                <label key={station.id} style={{ display: 'inline-flex', gap: '0.35rem', marginRight: '0.8rem' }}>
                  <input
                    type="checkbox"
                    checked={selected.has(station.id)}
                    disabled={pending}
                    onChange={(event) => {
                      const next = new Set(selected)
                      if (event.target.checked) next.add(station.id)
                      else next.delete(station.id)
                      run(() => saveRoute(businessId, item.id, [...next]))
                    }}
                  />
                  {station.name}
                </label>
              ))}
            </fieldset>
          )
        })}
      </section>
    </div>
  )
}
