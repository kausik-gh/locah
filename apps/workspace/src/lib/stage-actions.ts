'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export type StageEntity = 'orders' | 'leads' | 'projects'
export type StageRow = { key?: string; label: string; status: string; needs_note?: boolean; custom?: boolean }

const PAGE: Record<StageEntity, string> = { orders: 'orders', leads: 'leads', projects: 'projects' }

/** Move a record to a stage (P2-01). The API checks the move, the permission and the note. */
export async function moveStage(businessId: string, entity: StageEntity, recordId: string, to: string,
  note: string, version: number): Promise<ActionResult> {
  const r = await sendJson(`/v1/b/${businessId}/stages/${entity}/${recordId}/move`, 'POST',
    { to, note: note.trim() || null, version })
  if (r.ok) {
    revalidatePath(`/b/${businessId}/${PAGE[entity]}/${recordId}`)
    revalidatePath(`/b/${businessId}/${PAGE[entity]}`)
  }
  return r
}

/** Save a business's stages for one module: its renamed stages and its own steps. */
export async function saveStages(businessId: string, entity: StageEntity, stages: StageRow[]): Promise<ActionResult> {
  const r = await sendJson(`/v1/b/${businessId}/stages/${entity}`, 'PUT', { stages })
  if (r.ok) revalidatePath(`/b/${businessId}/settings/stages`)
  return r
}
