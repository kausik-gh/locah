'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function send(form: FormData, path: string, method: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to manage licences and filings')
  const b = String(form.get('businessId'))
  await apiSend(`/v1/platform/businesses/${b}/compliance/items${path}`, token, method, body)
  revalidatePath(`/b/${b}/compliance`)
}

export async function createComplianceItem(form: FormData) {
  await send(form, '', 'POST', {
    item_type: String(form.get('item_type')),
    kind: String(form.get('kind')),
    title: String(form.get('title')),
    due_on: String(form.get('due_on')),
    recurrence: String(form.get('recurrence') || 'none'),
    licence_number: String(form.get('licence_number') || '') || null,
    authority: String(form.get('authority') || '') || null,
    document_url: String(form.get('document_url') || '') || null,
    notes: String(form.get('notes') || '') || null,
    show_on_site: form.get('item_type') === 'licence' && form.get('show_on_site') === 'on',
  })
}

export async function updateComplianceItem(form: FormData) {
  const item = String(form.get('itemId'))
  await send(form, `/${item}`, 'PATCH', {
    title: String(form.get('title')),
    due_on: String(form.get('due_on')),
    licence_number: String(form.get('licence_number') || '') || null,
    authority: String(form.get('authority') || '') || null,
    document_url: String(form.get('document_url') || '') || null,
    notes: String(form.get('notes') || '') || null,
    show_on_site: form.get('show_on_site') === 'on',
  })
}

export async function renewComplianceItem(form: FormData) {
  await send(form, `/${String(form.get('itemId'))}/renew`, 'POST', {
    new_due_on: String(form.get('new_due_on')),
    note: String(form.get('note') || '') || null,
  })
}

export async function markComplianceFiled(form: FormData) {
  await send(form, `/${String(form.get('itemId'))}/filed`, 'POST', { note: String(form.get('note') || '') || null })
}

export async function setComplianceArchived(form: FormData) {
  await send(form, `/${String(form.get('itemId'))}/archive`, 'POST', { archived: form.get('archived') === 'true' })
}
