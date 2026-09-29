'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const apiUrl = platformUrl('api')

async function send(path: string, method: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`)
  return res.json()
}

function base(formData: FormData) {
  return `/v1/platform/businesses/${String(formData.get('businessId'))}/loyalty`
}

export async function saveLoyaltyProgram(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const expiry = String(formData.get('expiry_days') || '')
  await send(`${base(formData)}/program`, 'PUT', {
    name: String(formData.get('name') || ''),
    points_per_rupee: Number(formData.get('points_per_rupee')),
    redemption_rupees_per_point: Number(formData.get('redemption_rupees_per_point')),
    min_redemption_points: Number(formData.get('min_redemption_points')),
    expiry_days: expiry === '' ? null : Number(expiry),
    status: String(formData.get('status') || 'active'),
  })
  revalidatePath(`/b/${businessId}/loyalty`)
}

export async function createStampCard(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`${base(formData)}/stamps`, 'POST', {
    name: String(formData.get('name') || ''),
    required_stamps: Number(formData.get('required_stamps') || 10),
    reward_kind: 'free_item',
    reward_item: String(formData.get('reward_item') || 'Free reward'),
  })
  revalidatePath(`/b/${businessId}/loyalty`)
}

export async function issueVoucher(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const rupees = Number(formData.get('amount_rupees'))
  await send(`${base(formData)}/vouchers`, 'POST', {
    issued_amount_paise: Math.round(rupees * 100),
    recipient_name: String(formData.get('recipient_name') || '') || null,
    holder_contact_id: String(formData.get('holder_contact_id') || '') || null,
  })
  revalidatePath(`/b/${businessId}/loyalty`)
}

export async function earnPoints(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const contactId = String(formData.get('contact_id'))
  const rupees = Number(formData.get('amount_rupees'))
  const sourceId = `desk-${Date.now()}`
  await send(`${base(formData)}/customers/${contactId}/earn`, 'POST', {
    order_amount_paise: Math.round(rupees * 100),
    source_type: 'pos',
    source_id: sourceId,
    idempotency_key: sourceId,
  })
  revalidatePath(`/b/${businessId}/loyalty`)
}

export async function redeemPoints(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const contactId = String(formData.get('contact_id'))
  const sourceId = `redeem-${Date.now()}`
  await send(`${base(formData)}/customers/${contactId}/redeem`, 'POST', {
    points_to_redeem: Number(formData.get('points')),
    order_amount_paise: Number(formData.get('order_amount_paise') || 0),
    source_type: 'pos',
    source_id: sourceId,
    idempotency_key: sourceId,
  })
  revalidatePath(`/b/${businessId}/loyalty`)
}
