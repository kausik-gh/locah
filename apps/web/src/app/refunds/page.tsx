import type { Metadata } from 'next'
import Link from 'next/link'
import { PolicyPage, type PolicySection } from '@/components/public/PolicyPage'
import { MERCHANT } from '@/lib/merchant-details'

export const metadata: Metadata = { title: 'Refund & Cancellation Policy — LOCAH', description: 'How LOCAH handles service cancellations, subscription renewals, failed payments and refunds.' }

const sections: PolicySection[] = [
  { id: 'pay-as-you-go', title: 'Pay As You Go purchases', content: <><p>You may cancel a Pay As You Go purchase for a full refund before LOCAH begins delivering the purchased service. For a build, generation or publishing request, work starts when you instruct LOCAH to begin that paid action.</p><p>After work has started or a digital service has been delivered, the payment is generally non-refundable. We review exceptions if we cannot provide the service, the same purchase was charged twice, a payment was captured incorrectly, a refund is required by law, or we approve a refund after reviewing the circumstances.</p></> },
  { id: 'subscriptions', title: 'Monthly subscriptions', content: <><p>LOCAH Monthly can be cancelled before the next renewal date. Cancellation stops future renewal charges where recurring billing is enabled. Access to the current paid period remains available until that period ends.</p><p>We do not normally provide a prorated refund for unused time once a billing period has begun, subject to applicable law and the exceptions described above.</p><p>To request cancellation while self-service billing controls are being connected, contact us using the details below. We will confirm your request and the end of your paid period.</p></> },
  { id: 'failed-payments', title: 'Failed or duplicate transactions', content: <><p>If money is debited but LOCAH does not receive confirmation of a successful transaction, contact us with the payment reference. We will investigate it with the payment provider.</p><p>When a failed or duplicate charge is confirmed and a refund is due, we initiate the refund through the original payment method.</p></> },
  { id: 'method-and-timing', title: 'Refund method and timing', content: <><p>Approved refunds are returned to the original payment method used for the transaction. We do not ordinarily provide cash refunds for electronic payments.</p><p>Once an approved refund has been initiated, it typically takes approximately 5–21 days to appear in your account, depending on the payment method, bank and payment network. Some banks may take longer. Bank processing is outside LOCAH’s direct control after the refund is submitted.</p></> },
  { id: 'request', title: 'Request a refund or cancellation', content: <><p>Email <a href={`mailto:${MERCHANT.email}`}>{MERCHANT.email}</a> or call <a href={MERCHANT.phoneHref}>{MERCHANT.phone}</a>. Include your name, LOCAH account email or phone, transaction or order reference, payment date, amount and reason for the request. Do not include full card details or passwords.</p><p>See our <Link href="/contact">Contact page</Link> for support hours and correspondence address.</p></> },
]

export default function RefundsPage() {
  return <PolicyPage eyebrow="Payments & service" title="Refund & Cancellation Policy" intro="What happens if plans change, a payment fails or a service cannot be delivered." sections={sections} current="/refunds" />
}
