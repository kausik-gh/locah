import localFont from 'next/font/local'

/**
 * General Sans — one family, all weights (Frontend Design Work Order, Prompt B).
 * Fontshare woff2 subsets, self-hosted so the dashboard never blocks on a
 * third-party font CDN. `--font-sans` is consumed by globals.css.
 */
export const generalSans = localFont({
  src: [
    { path: './GeneralSans-400.woff2', weight: '400', style: 'normal' },
    { path: './GeneralSans-500.woff2', weight: '500', style: 'normal' },
    { path: './GeneralSans-600.woff2', weight: '600', style: 'normal' },
    { path: './GeneralSans-700.woff2', weight: '700', style: 'normal' },
  ],
  variable: '--font-general-sans',
  display: 'swap',
  fallback: ['ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
})
