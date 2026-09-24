import type { ReactNode } from 'react'
import Link from 'next/link'
import { PublicNav } from './PublicNav'
import { PublicFooter } from './PublicFooter'
import { MERCHANT } from '@/lib/merchant-details'

export const POLICY_LINKS = [
  { href: '/terms', label: 'Terms & Conditions' },
  { href: '/privacy', label: 'Privacy Policy' },
  { href: '/refunds', label: 'Refund & Cancellation' },
  { href: '/delivery', label: 'Shipping & Delivery' },
  { href: '/disclaimer', label: 'Disclaimer' },
] as const

export type PolicySection = { id: string; title: string; content: ReactNode }

export function MerchantContact({ compact = false }: { compact?: boolean }) {
  return <address className={compact ? 'ui-merchant-contact ui-merchant-contact--compact' : 'ui-merchant-contact'}>
    <strong>{MERCHANT.tradingName}</strong>
    <span>Operated by {MERCHANT.legalName}</span>
    <span>{MERCHANT.addressLine}</span>
    <span>{MERCHANT.cityLine}, {MERCHANT.country}</span>
    <a href={`mailto:${MERCHANT.email}`}>{MERCHANT.email}</a>
    <a href={MERCHANT.phoneHref}>{MERCHANT.phone}</a>
  </address>
}

export function PolicyPage({
  eyebrow,
  title,
  intro,
  sections,
  current,
}: {
  eyebrow: string
  title: string
  intro: string
  sections: PolicySection[]
  current: string
}) {
  return <div className="locah-public">
    <PublicNav />
    <main>
      <header className="ui-policy-hero">
        <div className="lc-container lc-container--wide">
          <p className="lc-eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <div className="ui-policy-hero__bottom"><p>{intro}</p><span>Last updated 24 September 2026</span></div>
        </div>
      </header>
      <div className="lc-container lc-container--wide ui-policy-layout">
        <aside className="ui-policy-sidebar" aria-label="Policy navigation">
          <p className="lc-eyebrow">On this page</p>
          <nav aria-label="Sections"><ul>{sections.map(section => <li key={section.id}><a href={`#${section.id}`}>{section.title}</a></li>)}</ul></nav>
          <div className="ui-policy-sidebar__related"><p className="lc-eyebrow">Other policies</p><ul>{POLICY_LINKS.filter(item => item.href !== current).map(item => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul></div>
        </aside>
        <article className="ui-policy-article">
          {sections.map((section, index) => <section id={section.id} key={section.id} aria-labelledby={`${section.id}-title`}>
            <div className="ui-policy-article__number">{String(index + 1).padStart(2, '0')}</div>
            <div><h2 id={`${section.id}-title`}>{section.title}</h2><div className="ui-policy-article__body">{section.content}</div></div>
          </section>)}
          <div className="ui-policy-help"><p className="lc-eyebrow">Questions?</p><h2>We can help clarify.</h2><p>For questions about this policy, your account or a payment, contact us using the details below.</p><MerchantContact compact /><Link className="lc-link lc-link--accent" href="/contact">Visit the contact page ↗</Link></div>
        </article>
      </div>
    </main>
    <PublicFooter />
  </div>
}
