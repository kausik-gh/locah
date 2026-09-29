'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function send(businessId: string, path: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to work on tasks')
  await apiSend(`/v1/platform/businesses/${businessId}/tasks${path}`, token, 'POST', body)
  revalidatePath(`/b/${businessId}/tasks`)
}

export async function createTask(form: FormData) {
  const businessId = String(form.get('businessId'))
  const due = String(form.get('dueAt') || '').trim()
  const assignee = String(form.get('assigneeId') || '').trim()
  const location = String(form.get('locationId') || '').trim()
  const related = String(form.get('relatedId') || '').trim()
  const relatedType = String(form.get('relatedType') || 'business')
  await send(businessId, '', {
    title: String(form.get('title')),
    description: String(form.get('description') || '') || null,
    priority: String(form.get('priority') || 'normal'),
    due_at: due ? `${due.length === 16 ? due : due.slice(0, 16)}:00+05:30` : null,
    assignee_member_id: assignee || null,
    location_id: location || null,
    related_type: relatedType,
    related_id: relatedType === 'business' ? businessId : related,
  })
}

export async function addChecklistItem(form: FormData) {
  const businessId = String(form.get('businessId'))
  const taskId = String(form.get('taskId'))
  await send(businessId, `/${taskId}/items`, {
    label: String(form.get('label')),
    required: form.get('required') === 'on',
    photo_required: form.get('photoRequired') === 'on',
  })
}

export async function checkChecklistItem(form: FormData) {
  const businessId = String(form.get('businessId'))
  const taskId = String(form.get('taskId'))
  const itemId = String(form.get('itemId'))
  await send(businessId, `/${taskId}/items/${itemId}/check`, { done: form.get('done') !== '0' })
}

export async function completeTask(form: FormData) {
  const businessId = String(form.get('businessId'))
  await send(businessId, `/${String(form.get('taskId'))}/complete`, {})
}

export async function spawnChecklist(form: FormData) {
  const businessId = String(form.get('businessId'))
  const templateId = String(form.get('templateId'))
  await send(businessId, `/templates/${templateId}/spawn`, {
    occurrence_key: String(form.get('occurrenceKey')),
  })
}

export async function createChecklistTemplate(form: FormData) {
  const businessId = String(form.get('businessId'))
  const labels = String(form.get('items') || '').split('\n').map((line) => line.trim()).filter(Boolean)
  await send(businessId, '/templates', {
    name: String(form.get('name')),
    kind: String(form.get('kind') || 'custom'),
    items: labels.map((label) => ({ label, required: true, photo_required: false })),
  })
}
