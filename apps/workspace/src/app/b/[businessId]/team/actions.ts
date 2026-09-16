'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

async function send(path: string, method: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

export async function memberLifecycle(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const membershipId = String(formData.get('membershipId'))
  const action = String(formData.get('action'))
  await send(`/v1/platform/businesses/${businessId}/members/${membershipId}/${action}`, 'POST')
  revalidatePath(`/b/${businessId}/team`)
}

export async function changeMemberRole(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const membershipId = String(formData.get('membershipId'))
  await send(`/v1/platform/businesses/${businessId}/members/${membershipId}`, 'PATCH', {
    role: String(formData.get('role')),
  })
  revalidatePath(`/b/${businessId}/team`)
}

export async function removeMember(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const membershipId = String(formData.get('membershipId'))
  await send(`/v1/platform/businesses/${businessId}/members/${membershipId}`, 'DELETE')
  revalidatePath(`/b/${businessId}/team`)
}

export async function grantPermissions(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const membershipId = String(formData.get('membershipId'))
  const raw = String(formData.get('permissions') || '')
  const permissions = raw
    .split(/[\s,]+/)
    .map((value) => value.trim())
    .filter(Boolean)
  await send(`/v1/b/${businessId}/team/members/${membershipId}/permissions`, 'POST', {
    permissions,
  })
  revalidatePath(`/b/${businessId}/team`)
}

export async function createInvitation(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/invitations`, 'POST', {
    invited_email: String(formData.get('invited_email')),
    invited_role: String(formData.get('invited_role') || 'member'),
  })
  revalidatePath(`/b/${businessId}/team/invitations`)
}

export async function invitationLifecycle(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const invitationId = String(formData.get('invitationId'))
  const action = String(formData.get('action'))
  if (action === 'revoke') {
    await send(`/v1/platform/businesses/${businessId}/invitations/${invitationId}`, 'DELETE')
  } else {
    await send(
      `/v1/platform/businesses/${businessId}/invitations/${invitationId}/${action}`,
      'POST'
    )
  }
  revalidatePath(`/b/${businessId}/team/invitations`)
}
