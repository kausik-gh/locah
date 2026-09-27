'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

function refresh(businessId: string) {
  revalidatePath(`/b/${businessId}/team`)
  revalidatePath(`/b/${businessId}/team/roles`)
}

export async function addPerson(
  businessId: string,
  person: { name: string; email: string; role: string; location_ids: string[] },
): Promise<ActionResult<{ invitation_id: string; join_path: string }>> {
  const r = await sendJson<{ invitation_id: string; join_path: string }>(
    `/v1/platform/businesses/${businessId}/team/people`,
    'POST',
    person,
  )
  if (r.ok) refresh(businessId)
  return r
}

export async function newJoinLink(
  businessId: string,
  invitationId: string,
): Promise<ActionResult<{ join_path: string }>> {
  return sendJson<{ join_path: string }>(
    `/v1/platform/businesses/${businessId}/team/invitations/${invitationId}/link`,
    'POST',
  )
}

export async function withdrawInvitation(businessId: string, invitationId: string): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/invitations/${invitationId}`, 'DELETE')
  if (r.ok) refresh(businessId)
  return r
}

export async function assignRole(
  businessId: string,
  membershipId: string,
  role: string,
  locationIds: string[],
): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/members/${membershipId}/role`, 'PUT', {
    role,
    location_ids: locationIds,
  })
  if (r.ok) refresh(businessId)
  return r
}

export async function changeStatus(
  businessId: string,
  membershipId: string,
  action: 'suspend' | 'reactivate' | 'remove',
): Promise<ActionResult> {
  const r =
    action === 'remove'
      ? await sendJson(`/v1/platform/businesses/${businessId}/members/${membershipId}`, 'DELETE')
      : await sendJson(`/v1/platform/businesses/${businessId}/members/${membershipId}/${action}`, 'POST')
  if (r.ok) refresh(businessId)
  return r
}

export async function saveCustomRole(
  businessId: string,
  role: { id?: string; name: string; based_on: string | null; permissions: string[]; scope: string },
): Promise<ActionResult> {
  const r = role.id
    ? await sendJson(`/v1/platform/businesses/${businessId}/roles/custom/${role.id}`, 'PATCH', {
        name: role.name,
        permissions: role.permissions,
      })
    : await sendJson(`/v1/platform/businesses/${businessId}/roles/custom`, 'POST', {
        name: role.name,
        based_on: role.based_on,
        permissions: role.permissions,
        scope: role.scope,
      })
  if (r.ok) refresh(businessId)
  return r
}

export async function removeCustomRole(businessId: string, roleId: string): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/roles/custom/${roleId}`, 'DELETE')
  if (r.ok) refresh(businessId)
  return r
}
