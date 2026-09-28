'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function act(form: FormData, suffix: string, method: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to manage reviews')
  const businessId = String(form.get('businessId'))
  const reviewId = String(form.get('reviewId'))
  await apiSend(`/v1/platform/businesses/${businessId}/reviews/${reviewId}/${suffix}`, token, method, body)
  revalidatePath(`/b/${businessId}/reviews`)
}

export async function replyReview(form: FormData) {
  await act(form, 'reply', 'PUT', { body: String(form.get('body') || '').trim() || null })
}

export async function featureReview(form: FormData) {
  await act(form, 'feature', 'PUT', { featured: form.get('featured') === 'true' })
}

export async function reportReview(form: FormData) {
  await act(form, 'report', 'POST', { reason: String(form.get('reason')), note: String(form.get('note') || '') || null })
}
