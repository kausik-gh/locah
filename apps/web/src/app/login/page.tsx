import { Suspense } from 'react'
import { LoginForm } from './LoginForm'

export const dynamic = 'force-dynamic'

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh' }} />}>
      <LoginForm />
    </Suspense>
  )
}
