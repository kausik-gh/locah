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
