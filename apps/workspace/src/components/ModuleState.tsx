import type { CSSProperties, ReactNode } from 'react'
import { EmptyState as UiEmptyState, PageHeader as UiPageHeader } from './ui'

/* Re-exports so the ~35 pages that import from here pick up the design system
   without a churn of import rewrites. New code should import from `./ui`. */
export { StatusPill, DataTable, DetailShell, FilterTabs, Section, Skeleton, GateNotice } from './ui'
export type { Column } from './ui'

export function PageHeader(props: {
  title: string
  subtitle?: string
  action?: ReactNode
  actions?: ReactNode
  breadcrumb?: ReactNode
}) {
  return (
    <UiPageHeader
      title={props.title}
      subtitle={props.subtitle}
      breadcrumb={props.breadcrumb}
      actions={props.actions ?? props.action}
    />
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <UiEmptyState>{children}</UiEmptyState>
}

/* Legacy table style constants — many pages still spread these onto raw
   <table>. Re-pointed at the token system; globals.css already styles bare
   <table>/<th>/<td> so these mostly just need to not fight it. */
export const TABLE: CSSProperties = { width: '100%', borderCollapse: 'collapse' }
export const TH: CSSProperties = {}
export const TD: CSSProperties = {}
export const ROW: CSSProperties = {}
