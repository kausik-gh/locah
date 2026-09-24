import type { Metadata } from 'next'
import Link from 'next/link'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { MerchantContact, POLICY_LINKS } from '@/components/public/PolicyPage'
import { MERCHANT } from '@/lib/merchant-details'

export const metadata: Metadata = {
  title: 'Contact LOCAH',
  description: 'Contact LOCAH for account, pricing, website, billing and payment support. Find our public business address, email and phone number.',
}

export default function ContactPage() {
  return <div className="locah-public">
    <PublicNav active="contact" />
    <main>
      <section className="ui-editorial-hero ui-editorial-hero--cream ui-contact-hero"><div className="lc-container lc-container--wide ui-editorial-hero__grid">
        <div><p className="lc-eyebrow">Contact LOCAH</p><h1 className="ui-display">Good questions deserve <em>a real answer.</em></h1></div>
        <div className="ui-editorial-hero__aside"><p>We can help with your account, website, pricing, billing, payments and use of LOCAH.</p><a className="lc-btn lc-btn--primary" href={`mailto:${MERCHANT.email}`}>Email our team ↗</a><small>We aim to acknowledge requests within two business days.</small></div>
      </div></section>
      <section className="lc-container lc-container--wide ui-contact-grid" aria-label="Contact details">
        <div className="ui-contact-grid__intro"><p className="lc-eyebrow">Here to help</p><h2>Reach us your way.</h2><p>For a payment or refund question, include the email or phone on your LOCAH account and your transaction reference, if you have one. Please do not email card details or passwords.</p></div>
        <div className="ui-contact-cards">
          <div><span>01 / Write to us</span><h3>Email support</h3><a href={`mailto:${MERCHANT.email}`}>{MERCHANT.email} ↗</a><p>Account access, business setup, billing, website creation and refund requests.</p></div>
          <div><span>02 / Speak to us</span><h3>Call support</h3><a href={MERCHANT.phoneHref}>{MERCHANT.phone} ↗</a><p>{MERCHANT.supportHours}</p></div>
          <div><span>03 / Find us</span><h3>Business address</h3><MerchantContact compact /></div>
        </div>
      </section>
      <section className="ui-contact-policies"><div className="lc-container lc-container--wide"><div><p className="lc-eyebrow">The details in writing</p><h2>Clear answers, always available.</h2></div><ul>{POLICY_LINKS.map(item => <li key={item.href}><Link href={item.href}>{item.label}<span aria-hidden="true">↗</span></Link></li>)}</ul></div></section>
    </main>
    <PublicFooter />
  </div>
}
