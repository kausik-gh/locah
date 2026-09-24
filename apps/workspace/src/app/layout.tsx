import React from 'react'
import './globals.css'
import './platform-overhaul.css'
import { generalSans } from './fonts/general-sans'

export const metadata = {
  title: 'LOCAH Workspace',
  description: 'Multi-tenant Platform Business Operating Surface',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={generalSans.variable}>
      <body>{children}</body>
    </html>
  )
}
