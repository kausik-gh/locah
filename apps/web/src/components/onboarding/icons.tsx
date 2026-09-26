/** Small line icons for onboarding. Stroke follows currentColor. */

export function MicIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" fill="none">
      <rect x="7" y="2.5" width="6" height="10" rx="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function SendIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" fill="none">
      <path d="M10 16V4M4.5 9.5 10 4l5.5 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function ClipIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" fill="none">
      <path
        d="M15.5 9.2 9.6 15.1a3.6 3.6 0 0 1-5.1-5.1l6.3-6.3a2.4 2.4 0 0 1 3.4 3.4l-6.2 6.2a1.2 1.2 0 0 1-1.7-1.7l5.6-5.6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function CheckIcon({ size = 16 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true" fill="none">
      <path d="m4.5 10.5 3.5 3.5 7.5-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function StopIcon({ size = 16 }: { size?: number }) {
  return (
    <svg viewBox="0 0 20 20" width={size} height={size} aria-hidden="true">
      <rect x="5" y="5" width="10" height="10" rx="2" fill="currentColor" />
    </svg>
  )
}
