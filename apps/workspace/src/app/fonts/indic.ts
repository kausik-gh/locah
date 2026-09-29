import { Noto_Sans_Devanagari, Noto_Sans_Tamil } from 'next/font/google'

/**
 * Tamil and Devanagari faces behind General Sans (P1-10E6), so a customer's
 * Tamil or Hindi WhatsApp message, a product named in Tamil, and the Workspace
 * in Tamil or Hindi render in a real face. Latin text keeps General Sans.
 */
export const notoTamil = Noto_Sans_Tamil({
  subsets: ['tamil'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-ws-tamil',
})

export const notoDevanagari = Noto_Sans_Devanagari({
  subsets: ['devanagari'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-ws-devanagari',
})
