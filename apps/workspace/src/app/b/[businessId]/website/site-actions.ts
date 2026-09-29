'use server'

import { revalidatePath } from 'next/cache'
import { sendJson } from '@/lib/server-send'

/** Show or hide a section one of the business's tools adds to the home page. */
export async function setToolSection(businessId: string, module: string, hidden: boolean) {
  const r = await sendJson<{ hidden: string[] }>(`/v1/b/${businessId}/website/auto-sections`, 'PATCH', {
    module,
    hidden,
  })
  if (r.ok) revalidatePath(`/b/${businessId}/website`)
  return r
}

/** The languages the site's own words come in; the first is what visitors see first (P1-10E6). */
export async function setSiteLanguages(businessId: string, languages: string[]) {
  const r = await sendJson<{ languages: string[] }>(`/v1/b/${businessId}/website/languages`, 'PUT', { languages })
  if (r.ok) revalidatePath(`/b/${businessId}/website`)
  return r
}
