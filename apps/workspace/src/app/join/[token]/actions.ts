'use server'

import { sendJson, type ActionResult } from '@/lib/server-send'

/** Join as the signed-in person. The API checks they are the invited email. */
export async function acceptInvitation(businessId: string, invitationId: string): Promise<ActionResult> {
  return sendJson(`/v1/platform/businesses/${businessId}/invitations/${invitationId}/accept`, 'POST')
}
