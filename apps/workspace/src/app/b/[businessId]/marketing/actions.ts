'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
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

function root(formData: FormData) {
  return `/v1/platform/businesses/${String(formData.get('businessId'))}/marketing`
}

export async function createCampaign(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const created = await send(`${root(formData)}/campaigns`, 'POST', {
    name: String(formData.get('name') || ''),
    goal: String(formData.get('goal') || ''),
    channel: String(formData.get('channel') || 'whatsapp'),
    budget_paise: Math.round(Number(formData.get('budget_rupees') || 0) * 100),
  })
  revalidatePath(`/b/${businessId}/marketing`)
  redirect(`/b/${businessId}/marketing/${created.id}`)
}

export async function saveCampaignBuild(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const campaignId = String(formData.get('campaignId'))
  const segment = String(formData.get('audience_segment_id') || '')
  const offer = String(formData.get('offer_id') || '')
  await send(`${root(formData)}/campaigns/${campaignId}`, 'PATCH', {
    audience_segment_id: segment || null,
    offer_id: offer || null,
    creative: { text: String(formData.get('creative') || '') },
    budget_paise: Math.round(Number(formData.get('budget_rupees') || 0) * 100),
    channel: String(formData.get('channel') || 'whatsapp'),
  })
  revalidatePath(`/b/${businessId}/marketing/${campaignId}`)
}

export async function prepareCampaign(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const campaignId = String(formData.get('campaignId'))
  await send(`${root(formData)}/campaigns/${campaignId}/prepare`, 'POST')
  revalidatePath(`/b/${businessId}/marketing/${campaignId}`)
}

export async function approveCampaign(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const campaignId = String(formData.get('campaignId'))
  await send(`${root(formData)}/campaigns/${campaignId}/approve`, 'POST')
  revalidatePath(`/b/${businessId}/marketing/${campaignId}`)
}

export async function dispatchCampaign(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const campaignId = String(formData.get('campaignId'))
  await send(`${root(formData)}/campaigns/${campaignId}/dispatch`, 'POST')
  revalidatePath(`/b/${businessId}/marketing/${campaignId}`)
}

export async function createOffer(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`${root(formData)}/offers`, 'POST', {
    code: String(formData.get('code') || ''),
    name: String(formData.get('name') || ''),
    kind: String(formData.get('kind') || 'percentage_discount'),
    discount_value: Number(formData.get('discount_value')),
    usage_limit_per_customer: Number(formData.get('usage_limit_per_customer') || 1),
  })
  revalidatePath(`/b/${businessId}/marketing/offers`)
}
