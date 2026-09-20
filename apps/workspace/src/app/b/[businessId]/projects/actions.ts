'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

const apiUrl = platformUrl('api')

/**
 * Every write goes to the projects API as it stands.
 *
 * Nothing here decides whether a status change is legal, what a project's
 * progress is, or whether a person may be assigned to it. Those are the
 * service's rules, and a second copy of them in the Workspace would be a second
 * opinion about the state of real work.
 */
async function send(path: string, method: string, body?: unknown): Promise<unknown> {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  if (!res.ok) {
    const text = await res.text()
    let message = `Request failed (${res.status})`
    try {
      message = JSON.parse(text)?.error?.message || message
    } catch {
      // Non-JSON body — the status-derived message is the best available.
    }
    throw new Error(message)
  }
  return res.json()
}

function optional(form: FormData, field: string): string | undefined {
  const value = form.get(field)
  const text = value === null ? '' : String(value).trim()
  return text ? text : undefined
}

function refresh(businessId: string, projectId?: string): void {
  revalidatePath(`/b/${businessId}/projects`)
  if (projectId) revalidatePath(`/b/${businessId}/projects/${projectId}`)
}

export async function createProject(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  // An empty phase list is a real choice — a single-visit job has no stages —
  // so it is only sent when the person actually edited the field. Leaving it
  // out is what asks the API to seed from the business type.
  const phasesRaw = formData.get('phases')
  const phases =
    phasesRaw === null
      ? undefined
      : String(phasesRaw)
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)

  const created = (await send(`/v1/platform/businesses/${businessId}/projects`, 'POST', {
    title: String(formData.get('title') || '').trim(),
    summary: optional(formData, 'summary'),
    internal_notes: optional(formData, 'internal_notes'),
    customer_contact_id: optional(formData, 'customer_contact_id'),
    lead_member_id: optional(formData, 'lead_member_id'),
    priority: optional(formData, 'priority') ?? 'normal',
    starts_on: optional(formData, 'starts_on'),
    due_on: optional(formData, 'due_on'),
    ...(phases === undefined ? {} : { phases }),
  })) as { data?: { id?: string } }

  const projectId = created?.data?.id
  refresh(businessId, projectId)
  redirect(
    projectId
      ? `/b/${businessId}/projects/${projectId}`
      : `/b/${businessId}/projects`
  )
}

export async function updateProject(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  const version = Number(formData.get('version'))
  await send(`/v1/platform/businesses/${businessId}/projects/${projectId}`, 'PATCH', {
    title: String(formData.get('title') || '').trim(),
    summary: optional(formData, 'summary') ?? null,
    internal_notes: optional(formData, 'internal_notes') ?? null,
    customer_contact_id: optional(formData, 'customer_contact_id') ?? null,
    lead_member_id: optional(formData, 'lead_member_id') ?? null,
    priority: optional(formData, 'priority') ?? 'normal',
    starts_on: optional(formData, 'starts_on') ?? null,
    due_on: optional(formData, 'due_on') ?? null,
    ...(Number.isFinite(version) && version >= 1 ? { version } : {}),
  })
  refresh(businessId, projectId)
}

export async function changeProjectStatus(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  await send(`/v1/platform/businesses/${businessId}/projects/${projectId}/status`, 'POST', {
    status: String(formData.get('status')),
    reason: optional(formData, 'reason'),
  })
  refresh(businessId, projectId)
}

export async function addPhase(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  await send(`/v1/platform/businesses/${businessId}/projects/${projectId}/phases`, 'POST', {
    name: String(formData.get('name') || '').trim(),
    due_on: optional(formData, 'due_on'),
    is_milestone: formData.get('is_milestone') === 'on',
  })
  refresh(businessId, projectId)
}

export async function updatePhase(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  const phaseId = String(formData.get('phaseId'))
  await send(
    `/v1/platform/businesses/${businessId}/projects/${projectId}/phases/${phaseId}`,
    'PATCH',
    { status: String(formData.get('status')) }
  )
  refresh(businessId, projectId)
}

export async function addTask(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  await send(`/v1/platform/businesses/${businessId}/projects/${projectId}/tasks`, 'POST', {
    title: String(formData.get('title') || '').trim(),
    description: optional(formData, 'description'),
    phase_id: optional(formData, 'phase_id'),
    assignee_member_id: optional(formData, 'assignee_member_id'),
    due_on: optional(formData, 'due_on'),
  })
  refresh(businessId, projectId)
}

export async function updateTask(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const projectId = String(formData.get('projectId'))
  const taskId = String(formData.get('taskId'))
  const version = Number(formData.get('version'))

  // Each control on a task row submits only what it changes, so an unrelated
  // field is never blanked by a form that did not ask about it.
  const body: Record<string, unknown> = {}
  if (formData.has('status')) body.status = String(formData.get('status'))
  if (formData.has('assignee_member_id')) {
    body.assignee_member_id = optional(formData, 'assignee_member_id') ?? null
  }
  if (formData.has('blocked_reason')) body.blocked_reason = optional(formData, 'blocked_reason')
  if (Number.isFinite(version) && version >= 1) body.version = version

  await send(
    `/v1/platform/businesses/${businessId}/projects/${projectId}/tasks/${taskId}`,
    'PATCH',
    body
  )
  refresh(businessId, projectId)
}

export async function convertQuoteToProject(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const quoteId = String(formData.get('quoteId'))
  const created = (await send(
    `/v1/platform/businesses/${businessId}/quotes/${quoteId}/convert-to-project`,
    'POST',
    {}
  )) as { data?: { id?: string } }
  const projectId = created?.data?.id
  refresh(businessId, projectId)
  revalidatePath(`/b/${businessId}/quotes/${quoteId}`)
  if (projectId) redirect(`/b/${businessId}/projects/${projectId}`)
}
