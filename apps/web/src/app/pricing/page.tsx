import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'

export const metadata: Metadata = {
  title: 'Pricing — LOCAH',
  description: 'Understand what is included in LOCAH setup and why public plan pricing is not yet available.',
}

const CORE = [
  ['Business profile', 'The details that describe who you are and what you offer.'],
  ['Website', 'Structured pages and sections you can review and edit.'],
  ['Workspace', 'The place to manage your business and the tools you enable.'],
  ['Marketplace presence', 'Discovery for a published, visible business.'],
] as const

const FAQ = [
  { question: 'Can I see a fixed monthly price?', answer: 'Not yet. LOCAH has not announced public plan names, prices or usage limits. We will show these clearly before any paid commitment is required.' },
  { question: 'Do I need a card to start setting up?', answer: 'No card is required to begin setup. Your website stays private until you choose to publish it.' },
  { question: 'Are customer payments the same as LOCAH billing?', answer: 'No. Money your customers pay your business is separate from any future charge by LOCAH for using the platform.' },
] as const

export default function PricingPage() {
  return <div className="locah-public">
    <PublicNav active="pricing" />
    <main>
      <section className="ui-editorial-hero ui-editorial-hero--cream"><div className="lc-container lc-container--wide ui-editorial-hero__grid">
        <div><p className="lc-eyebrow">Pricing, without guesswork</p><h1 className="ui-display">Know what you are getting. <em>Know what is still being decided.</em></h1></div>
        <div className="ui-editorial-hero__aside"><p>Public plan names and prices are not announced yet. You can begin setup without a card; we will show the terms before any paid commitment.</p><Link className="lc-btn lc-btn--primary" href="/start">Start setting up <span aria-hidden="true">↗</span></Link><small>No card required to begin.</small></div>
      </div></section>
      <section className="lc-container lc-container--wide ui-price-layout">
        <div className="ui-price-layout__heading"><p className="lc-eyebrow">What stays connected</p><h2>The foundation is one system.</h2><p>These are the core parts of LOCAH. Operating modules can be enabled when they fit your business; their commercial packaging has not been finalised.</p><Link className="lc-link lc-link--accent" href="/capabilities">Explore capabilities →</Link></div>
        <div className="ui-price-list">{CORE.map(([title, body], i) => <div className="ui-price-list__item" key={title}><span>0{i + 1}</span><div><h3>{title}</h3><p>{body}</p></div><span aria-hidden="true">↗</span></div>)}</div>
      </section>
      <section className="ui-pricing-note"><div className="lc-container lc-container--wide"><p className="lc-eyebrow">Our promise about clarity</p><p>When LOCAH introduces public plans, we will explain the price, included capabilities and any limits before asking you to choose. Platform billing and the payments you collect from customers will remain separate.</p></div></section>
      <section className="lc-container lc-container--wide ui-faq"><div><p className="lc-eyebrow">Straight answers</p><h2>Good questions to ask.</h2></div><div>{FAQ.map(item => <details key={item.question}><summary>{item.question}</summary><p>{item.answer}</p></details>)}</div></section>
    </main><PublicFooter />
  </div>
}
