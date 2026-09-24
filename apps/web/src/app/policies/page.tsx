import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { POLICY_LINKS } from '@/components/public/PolicyPage'

export const metadata: Metadata = { title: 'Policies & legal information — LOCAH', description: 'Find LOCAH terms, privacy, refunds, digital delivery, disclaimer and contact information in one place.' }

const DESCRIPTIONS: Record<string, string> = {
  '/terms': 'How LOCAH accounts, business content, digital services and purchases work.',
  '/privacy': 'What information we collect and how we use, share and protect it.',
  '/refunds': 'Cancellation rules, payment issues, refund requests and timing.',
  '/delivery': 'How access, websites and other digital services are delivered.',
  '/disclaimer': 'Important boundaries around AI content, merchant listings and third parties.',
}

export default function PoliciesPage() {
  return <div className="locah-public">
    <PublicNav />
    <main>
      <header className="ui-policy-hero"><div className="lc-container lc-container--wide"><p className="lc-eyebrow">The details, clearly laid out</p><h1>Policies & legal information.</h1><div className="ui-policy-hero__bottom"><p>Everything you need to know about using LOCAH, making a purchase and reaching us.</p><span>Last updated 24 September 2026</span></div></div></header>
      <section className="lc-container lc-container--wide ui-policies-index" aria-label="Policies">
        {POLICY_LINKS.map((item, index) => <Link href={item.href} key={item.href}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{item.label}</h2><p>{DESCRIPTIONS[item.href]}</p></div><span aria-hidden="true">↗</span></Link>)}
      </section>
      <section className="lc-container lc-container--wide ui-policies-contact"><p className="lc-eyebrow">Need a person?</p><h2>We’re here to help.</h2><p>Find our legal business name, correspondence address, support email and phone on the contact page.</p><Link className="lc-btn lc-btn--primary" href="/contact">Contact LOCAH ↗</Link></section>
    </main>
    <PublicFooter />
  </div>
}
