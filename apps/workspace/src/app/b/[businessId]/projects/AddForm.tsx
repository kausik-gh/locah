'use client'

import { useRef, type ReactNode } from 'react'

/**
 * A form that empties itself once the server has taken what it was given.
 *
 * The "add a task" and "add a stage" forms live on a server-rendered page, so
 * revalidation replaces the list above them but leaves the inputs exactly as
 * they were. Adding three tasks in a row then silently filed the second and
 * third under the first one's stage, with the first one's assignee and due
 * date — and left the title box loaded to submit a duplicate.
 *
 * Resetting after the action resolves is the whole fix. It is a client
 * component only because `reset()` needs the DOM node; the action it calls is
 * still the server action, unchanged.
 */
export function AddForm({
  action,
  children,
  style,
  ...rest
}: {
  action: (formData: FormData) => Promise<void>
  children: ReactNode
  style?: React.CSSProperties
} & Omit<React.FormHTMLAttributes<HTMLFormElement>, 'action' | 'style'>) {
  const ref = useRef<HTMLFormElement>(null)
  return (
    <form
      ref={ref}
      style={style}
      action={async (formData) => {
        await action(formData)
        // Only on success: a failed action throws, the error boundary shows it,
        // and what the person typed is still there to correct.
        ref.current?.reset()
      }}
      {...rest}
    >
      {children}
    </form>
  )
}
