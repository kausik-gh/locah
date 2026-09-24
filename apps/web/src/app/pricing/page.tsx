import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'

export const metadata: Metadata = {
  title: 'Pricing — LOCAH',
  description: 'Clear LOCAH pricing in Indian Rupees: Pay As You Go website services and LOCAH Monthly at ₹999 per business.',
}

const PAYG = [
  { name: 'Website Build & Publish', price: '₹499', unit: 'per build', detail: 'AI-assisted website creation, publishing and 30 days of hosting.' },
  { name: 'AI Website Rebuild', price: '₹199', unit: 'per rebuild', detail: 'An additional major rebuild after your initial website.' },
  { name: 'Website Hosting Renewal', price: '₹199', unit: 'per 30 days', detail: 'Keep your published site hosted without a subscription.' },
] as const

const MONTHLY = [
  'One business on LOCAH',
  'Ongoing published website hosting',
  'Workspace and website/content management',
  'Manual website edits',
  'Up to 5 AI website rebuilds per billing month',
  'Standard capabilities enabled for your account',
  'Standard customer support',
] as const

const FAQ = [
  { question: 'Can I start without paying?', answer: 'Yes. Creating an account and beginning business setup do not require a card. We confirm the price before activating a paid service.' },
  { question: 'Does Pay As You Go renew automatically?', answer: 'No. Individual Pay As You Go purchases do not automatically renew. You choose when to buy another build, rebuild or 30 days of hosting.' },
  { question: 'How does LOCAH Monthly renew?', answer: 'LOCAH Monthly is ₹999 per business for each month. Where recurring billing is enabled, it renews monthly until cancelled before the next renewal date. Your current paid period continues until its end.' },
  { question: 'Are customer payments included?', answer: 'No. Charges for using LOCAH are separate from money your customers pay your business. Payment gateway, delivery and other third-party fees may apply separately.' },
] as const

export default function PricingPage() {
  return <div className="locah-public">
    <PublicNav active="pricing" />
    <main>
      <section className="ui-editorial-hero ui-editorial-hero--cream ui-commercial-hero">
        <div className="lc-container lc-container--wide ui-editorial-hero__grid">
          <div><p className="lc-eyebrow">Straightforward pricing</p><h1 className="ui-display">Choose how your business <em>grows with LOCAH.</em></h1></div>
          <div className="ui-editorial-hero__aside"><p>Pay when you need a website service, or keep your presence and Workspace together with one monthly plan.</p><Link className="lc-btn lc-btn--primary" href="/start">Start setting up <span aria-hidden="true">↗</span></Link><small>No card required to begin setup.</small></div>
        </div>
      </section>

      <section className="lc-container lc-container--wide ui-commercial" aria-labelledby="plans-heading">
        <div className="ui-commercial__intro"><p className="lc-eyebrow">Two ways to begin</p><h2 id="plans-heading">A clear choice, at your pace.</h2><p>All prices are per business and shown in Indian Rupees. Applicable taxes, including GST where legally applicable, are additional and will be shown before payment.</p></div>
        <div className="ui-plan-grid">
          <article className="ui-plan-card">
            <div className="ui-plan-card__top"><span>01 / On demand</span><span>No subscription</span></div>
            <h3>Pay As You Go</h3>
            <p>Only purchase the digital services you choose.</p>
            <div className="ui-plan-card__price">₹0 <span>/ month subscription</span></div>
            <ul>{PAYG.map(item => <li key={item.name}><div><strong>{item.name}</strong><small>{item.detail}</small></div><span><b>{item.price}</b><small>{item.unit}</small></span></li>)}</ul>
            <p className="ui-plan-card__fine">Each purchase is confirmed before payment. No automatic renewal is required for Pay As You Go services.</p>
            <Link className="lc-btn lc-btn--secondary" href="/contact">Ask about Pay As You Go ↗</Link>
          </article>
          <article className="ui-plan-card ui-plan-card--highlight">
            <div className="ui-plan-card__top"><span>02 / Ongoing</span><span>One business</span></div>
            <h3>LOCAH Monthly</h3>
            <p>Keep your digital presence and day-to-day tools together.</p>
            <div className="ui-plan-card__price">₹999 <span>/ month per business</span></div>
            <ul>{MONTHLY.map(item => <li key={item}><span className="ui-plan-card__tick" aria-hidden="true">↗</span><strong>{item}</strong></li>)}</ul>
            <p className="ui-plan-card__fine">Where recurring billing is enabled, the plan renews monthly until cancelled before the next renewal. Your paid period remains available through its end.</p>
            <Link className="lc-btn lc-btn--primary" href="/contact">Ask about LOCAH Monthly ↗</Link>
          </article>
        </div>
        <p className="ui-commercial__activation">Business setup is available now. To arrange a paid service, <Link href="/contact">contact LOCAH</Link>; we confirm the scope and final amount before payment. Self-service platform billing is being connected.</p>
      </section>

      <section className="ui-pricing-note"><div className="lc-container lc-container--wide"><p className="lc-eyebrow">What is separate</p><p>Third-party usage and your customers’ payments stay separate from LOCAH’s service price.</p><div className="ui-pricing-note__detail">WhatsApp, AI or voice usage, advertising spend, delivery providers and payment gateway fees may carry separate charges where applicable. Discretionary third-party spend requires your authorization.</div></div></section>

      <section className="lc-container lc-container--wide ui-faq"><div><p className="lc-eyebrow">Good to know</p><h2>Before you choose.</h2></div><div>{FAQ.map(item => <details key={item.question}><summary>{item.question}</summary><p>{item.answer}</p></details>)}<p className="ui-faq__links">Read the <Link href="/terms">Terms & Conditions</Link> and <Link href="/refunds">Refund & Cancellation Policy</Link> for the full details.</p></div></section>
    </main>
    <PublicFooter />
  </div>
}
