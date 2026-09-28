import { redirect } from 'next/navigation'

/** Invitations now live on the Team page ("Waiting to join"). */
export default function InvitationsPage({ params }: { params: { businessId: string } }) {
  redirect(`/b/${params.businessId}/team`)
}
