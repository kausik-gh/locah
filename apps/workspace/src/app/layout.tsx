import React from 'react'
import './globals.css'
import './platform-overhaul.css'
import './business-os.css'
import { generalSans } from './fonts/general-sans'
import { notoDevanagari, notoTamil } from './fonts/indic'
import { WS_LOCALE } from '@/lib/ws-words'
import { wsLang } from '@/lib/ws-lang'

export const metadata = {
  title: 'LOCAH Workspace',
  description: 'Multi-tenant Platform Business Operating Surface',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={WS_LOCALE[wsLang()]} className={`${generalSans.variable} ${notoTamil.variable} ${notoDevanagari.variable}`}>
      <body>{children}</body>
    </html>
  )
}
