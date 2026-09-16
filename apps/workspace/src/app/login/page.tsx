import { redirect } from 'next/navigation'

/** Workspace auth uses the shared Platform Identity ceremony on apps/web. */
export default function WorkspaceLoginRedirect() {
  const web = process.env.NEXT_PUBLIC_WEB_URL || 'http://127.0.0.1:3000'
  redirect(`${web}/login`)
}
