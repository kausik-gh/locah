'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost } from '@/lib/api'

async function send(path: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in as a Super Admin')
  await apiPost(`/v1/admin/reviews${path}`, body, token)
  revalidatePath('/reviews')
}

export async function dismissReport(form: FormData) {
  await send(`/reports/${String(form.get('reportId'))}/dismiss`, { note: String(form.get('note') || '') || null })
}

export async function removeReview(form: FormData) {
  await send(`/${String(form.get('reviewId'))}/remove`, {
    reason: String(form.get('reason')),
    note: String(form.get('note') || '') || null,
  })
}

export async function decideAppeal(form: FormData) {
  await send(`/${String(form.get('reviewId'))}/appeal`, {
    restore: form.get('restore') === 'true',
    note: String(form.get('note') || '') || null,
  })
}

export async function redactReview(form: FormData) {
  const span = String(form.get('span') || '').trim()
  if (!span) throw new Error('Enter the exact personal data to redact')
  await send(`/${String(form.get('reviewId'))}/redact`, { spans: [span] })
}

export async function removeReviewPhoto(form: FormData) {
  await send(`/photos/${String(form.get('photoId'))}/remove`, undefined)
}
