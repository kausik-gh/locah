'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function post(businessId: string, path: string, body: unknown, refresh: string) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to continue')
  await apiSend(`/v1/platform/businesses/${businessId}${path}`, token, 'POST', body)
  revalidatePath(`/b/${businessId}/${refresh}`)
}

export async function prepareRequirement(form: FormData) {
  const businessId = String(form.get('businessId'))
  await post(businessId, '/buying/prepare', {
    supplier_id: String(form.get('supplier_id')),
    offering_id: String(form.get('offering_id')),
    demand: Number(form.get('demand') || 0),
    location_id: String(form.get('location_id') || '') || null,
    pack_size: Number(form.get('pack_size') || 1),
    moq: Number(form.get('moq') || 1),
  }, 'buying')
}

export async function approveRequirement(form: FormData) {
  const businessId = String(form.get('businessId'))
  const requisitionId = String(form.get('requisitionId'))
  await post(businessId, `/buying/requisitions/${requisitionId}/approve`, {}, 'buying')
}

export async function receiveGoods(form: FormData) {
  const businessId = String(form.get('businessId'))
  const purchaseOrderId = String(form.get('purchaseOrderId'))
  await post(businessId, `/buying/purchase-orders/${purchaseOrderId}/receive`, {
    location_id: String(form.get('location_id')),
    received_quantity: Number(form.get('received_quantity') || 0),
    damaged_quantity: Number(form.get('damaged_quantity') || 0),
    idempotency_key: `ui-${purchaseOrderId}-${Date.now()}`,
  }, 'buying')
}

export async function addSupplier(form: FormData) {
  const businessId = String(form.get('businessId'))
  await post(businessId, '/suppliers', {
    name: String(form.get('name') || '').trim(),
    contact_name: String(form.get('contact_name') || '') || null,
    phone: String(form.get('phone') || '') || null,
    connection: 'off_network',
    credit_days: Number(form.get('credit_days') || 0),
  }, 'buying')
}

export async function addExpense(form: FormData) {
  const businessId = String(form.get('businessId'))
  const rupees = Number(form.get('rupees') || 0)
  await post(businessId, '/expenses', {
    category: String(form.get('category') || '').trim(),
    amount_paise: Math.round(rupees * 100),
    method: String(form.get('method') || 'cash'),
    payee: String(form.get('payee') || '') || null,
    petty_cash: form.get('petty_cash') === 'on',
  }, 'expenses')
}

export async function addCause(form: FormData) {
  const businessId = String(form.get('businessId'))
  await post(businessId, '/donations/causes', { name: String(form.get('name') || '').trim() }, 'donations')
}

export async function addGift(form: FormData) {
  const businessId = String(form.get('businessId'))
  const rupees = Number(form.get('rupees') || 0)
  await post(businessId, '/donations/gifts', {
    cause_id: String(form.get('cause_id')),
    donor_name: String(form.get('donor_name') || '').trim(),
    amount_paise: Math.round(rupees * 100),
  }, 'donations')
}
