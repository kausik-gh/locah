'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

// Returns void: this is passed straight to <form action>, which discards any
// return value. It previously returned {ok,error} objects that nothing could
// read, so a failed save was indistinguishable from a successful one.
// Throwing matches every other server action in this app.
export async function saveSectionContent(formData: FormData): Promise<void> {
  const token = await getAccessToken()
  if (!token) {
    throw new Error('Unauthorized')
  }
  const businessId = String(formData.get('businessId') || '')
  const sectionId = String(formData.get('sectionId') || '')
  const sectionTypeId = String(formData.get('sectionTypeId') || '')
  const headline = String(formData.get('headline') || '')
  const body = String(formData.get('body') || '')
  const rawInitial = String(formData.get('initialContent') || '{}')
  let content: Record<string, unknown> = {}
  try {
    content = JSON.parse(rawInitial) as Record<string, unknown>
  } catch {
    content = {}
  }
  if (sectionTypeId === 'hero' || sectionTypeId === 'cta_band' || 'headline' in content) {
    content.headline = headline
  }
  if ('subheadline' in content) content.subheadline = body
  if ('body' in content || sectionTypeId === 'about' || sectionTypeId === 'text_block') {
    content.body = body
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/website/sections/${sectionId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    throw new Error(`Saving the section failed: ${res.status} ${await res.text()}`)
  }
  revalidatePath(`/b/${businessId}/website/pages`)
}
