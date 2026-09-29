'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const apiUrl = platformUrl('api')

async function send(path: string, method: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
}

export async function addStation(businessId: string, body: { key?: string; name?: string }) {
  await send(`/v1/platform/businesses/${businessId}/kitchen/stations`, 'POST', body)
  revalidatePath(`/b/${businessId}/kitchen`)
}

export async function saveRoute(businessId: string, offeringId: string, stationIds: string[]) {
  await send(`/v1/platform/businesses/${businessId}/kitchen/routes`, 'PUT', {
    offering_id: offeringId,
    station_ids: stationIds,
  })
  revalidatePath(`/b/${businessId}/kitchen`)
}
