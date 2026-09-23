import React from 'react'
import type { Metadata } from 'next'
import { Plus_Jakarta_Sans, Instrument_Serif } from 'next/font/google'

// The design tokens must load before anything that reads them. `public.css`
// styles LOCAH's own surfaces (marketing, Marketplace); `website.css` styles
// published tenant sites, which read the `--site-*` contract instead of the
// LOCAH brand so a business's site looks like that business.
import '@platform/ui/tokens.css'
import '@platform/ui/public.css'
import '@platform/ui/website.css'
// A site's creative direction (profile, type system, cards, nav) on top.
import '@platform/ui/site-studio.css'

const sans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-general-sans',
})

const display = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  display: 'swap',
  variable: '--font-display-serif',
})

export const metadata: Metadata = {
  title: {
    default: 'LOCAH — Local Businesses. Limitless Possibilities.',
    template: '%s',
  },
  description:
    'LOCAH is the digital operating layer for local businesses: build your presence, get discovered, take orders and bookings, and run the whole business in one place.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body>{children}</body>
    </html>
  )
}
