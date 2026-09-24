import { NextResponse } from 'next/server'
import { fetchPlaces } from '@/lib/marketplace-api'

/**
 * Town and PIN lookup for the Marketplace location control.
 *
 * A thin pass-through to the API's reference data, so the browser never
 * needs the API's address. Coordinates arrive already rounded by the client
 * and are rounded again here before they go anywhere.
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const q = (url.searchParams.get('q') || '').slice(0, 60)
  const rawNear = url.searchParams.get('near') || ''
  let near: string | undefined
  const match = rawNear.match(/^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/)
  if (match) near = `${Number(match[1]).toFixed(2)},${Number(match[2]).toFixed(2)}`
  if (!q && !near) return NextResponse.json({ resolved: null, suggestions: [] })
  try {
    const data = await fetchPlaces({ q: near ? undefined : q, near })
    return NextResponse.json(data, { headers: { 'Cache-Control': 'private, max-age=300' } })
  } catch {
    return NextResponse.json({ resolved: null, suggestions: [] }, { status: 502 })
  }
}
