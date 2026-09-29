'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function send(businessId: string, path: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to run the queue')
  await apiSend(`/v1/platform/businesses/${businessId}/queue${path}`, token, 'POST', body)
  revalidatePath(`/b/${businessId}/queue`)
}

export async function createQueueLane(form: FormData) {
  const businessId = String(form.get('businessId'))
  const department = String(form.get('department') || '').trim()
  const provider = String(form.get('providerId') || '').trim()
  const minutes = String(form.get('avgServiceMinutes') || '').trim()
  await send(businessId, '/lanes', {
    location_id: String(form.get('locationId')),
    name: String(form.get('name')),
    department: department || null,
    provider_id: provider || null,
    allow_requeue: form.get('allowRequeue') === 'on',
    turn_soon_ahead: Number(form.get('turnSoonAhead') || 2),
    avg_service_minutes: minutes ? Number(minutes) : null,
  })
}

export async function issueToken(form: FormData) {
  const businessId = String(form.get('businessId'))
  const booking = String(form.get('bookingId') || '').trim()
  const name = String(form.get('partyLabel') || '').trim()
  await send(businessId, '/entries', {
    lane_id: String(form.get('laneId')),
    party_label: booking ? null : name,
    booking_id: booking || null,
    priority: Number(form.get('priority') || 0),
  })
}

export async function queueAct(form: FormData) {
  const businessId = String(form.get('businessId'))
  const action = String(form.get('action'))
  const laneId = String(form.get('laneId') || '')
  const entryId = String(form.get('entryId') || '')
  const path = action === 'call-next' ? `/lanes/${laneId}/call-next` : `/entries/${entryId}/${action}`
  await send(businessId, path, {})
}
