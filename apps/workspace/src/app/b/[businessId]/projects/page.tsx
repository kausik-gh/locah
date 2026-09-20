import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  DataTable,
  EmptyState,
  FilterTabs,
  GateNotice,
  PageHeader,
  StatusPill,
} from '@/components/ui'
import {
  dayLabel,
  daysUntil,
  statusLabel,
  STATUS_TONE,
  type ProjectRow,
  type ProjectSemantics,
} from './shared'

export const dynamic = 'force-dynamic'

type CustomerRow = { id: string; display_name: string }

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Not started' },
  { value: 'active', label: 'In progress' },
  { value: 'on_hold', label: 'On hold' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

/**
 * Projects and work orders — the list.
 *
 * What an owner scans for is what is running, how far along it is, and what is
 * about to be late. Those are the three columns that lead. The heading uses the
 * business's own word for the work, which the API supplies with the list.
 */
export default async function ProjectsPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string; q?: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    redirect(`/login?destination=${encodeURIComponent(`/b/${params.businessId}/projects`)}`)
  }

  const base = `/b/${params.businessId}/projects`
  const status = (searchParams?.status || '').trim()
  const search = (searchParams?.q || '').trim().toLowerCase()
  const qs = status ? `?status=${encodeURIComponent(status)}&limit=200` : '?limit=200'

  const [res, customersRes] = await Promise.all([
    apiTry<{ data: { projects: ProjectRow[]; semantics: ProjectSemantics } }>(
      `/v1/platform/businesses/${params.businessId}/projects${qs}`,
      token
    ),
    apiTry<{ data: CustomerRow[] }>(
      `/v1/platform/businesses/${params.businessId}/customers`,
      token
    ),
  ])

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Projects" />
        <GateNotice
          error={res.error}
          businessId={params.businessId}
          moduleLabel="Projects & Work Orders"
        />
      </div>
    )
  }

  const all = res.data.data.projects || []
  const semantics = res.data.data.semantics
  const names = new Map(
    (customersRes.ok ? customersRes.data.data || [] : []).map((c) => [c.id, c.display_name])
  )

  const rows = search
    ? all.filter((p) => {
        const customer = p.customer_contact_id ? names.get(p.customer_contact_id) || '' : ''
        return (
          p.reference.toLowerCase().includes(search) ||
          p.title.toLowerCase().includes(search) ||
          customer.toLowerCase().includes(search)
        )
      })
    : all

  const running = all.filter((p) => p.status === 'active').length
  const overdue = all.filter(
    (p) => p.is_open && p.due_on && (daysUntil(p.due_on) ?? 0) < 0
  ).length

  return (
    <div>
      <PageHeader
        title={semantics.noun_plural}
        subtitle={
          all.length === 0
            ? `Work you have committed to, tracked from start to finish.`
            : `${running} in progress${overdue ? ` · ${overdue} past due` : ''}`
        }
        actions={
          <Link href={`${base}/new`} className="btn">
            New {semantics.noun.toLowerCase()}
          </Link>
        }
      />

      <FilterTabs
        current={status}
        hrefFor={(v) => (v ? `${base}?status=${v}` : base)}
        options={FILTERS.map((f) => ({
          ...f,
          count: f.value ? all.filter((p) => p.status === f.value).length : all.length,
        }))}
      />

      <form method="get" style={{ margin: '0 0 1.1rem', display: 'flex', gap: '0.5rem' }}>
        {status ? <input type="hidden" name="status" value={status} /> : null}
        <input
          type="search"
          name="q"
          defaultValue={searchParams?.q || ''}
          placeholder="Search by reference, title or customer"
          aria-label={`Search ${semantics.noun_plural.toLowerCase()}`}
          style={{ maxWidth: '22rem' }}
        />
        <button type="submit" className="btn btn-ghost">
          Search
        </button>
      </form>

      <DataTable
        rows={rows}
        rowKey={(p) => p.id}
        empty={
          <EmptyState
            title={all.length === 0 ? `No ${semantics.noun_plural.toLowerCase()} yet` : 'Nothing matches that'}
            action={
              all.length === 0 ? (
                <Link href={`${base}/new`} className="btn">
                  Start your first {semantics.noun.toLowerCase()}
                </Link>
              ) : (
                <Link href={base} className="btn btn-ghost">
                  Clear filters
                </Link>
              )
            }
          >
            {all.length === 0
              ? `A ${semantics.noun.toLowerCase()} holds the stages, the tasks and who is doing each part — so work that runs over days or weeks has somewhere to live.`
              : 'Try a different status, or clear the search.'}
          </EmptyState>
        }
        columns={[
          {
            key: 'ref',
            header: 'Reference',
            render: (p) => (
              <Link href={`${base}/${p.id}`} style={{ fontWeight: 600 }}>
                {p.reference}
              </Link>
            ),
          },
          {
            key: 'what',
            header: 'What',
            render: (p) => (
              <span>
                {p.title}
                {p.customer_contact_id ? (
                  <span style={{ display: 'block', color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                    {names.get(p.customer_contact_id) || 'Customer'}
                  </span>
                ) : null}
              </span>
            ),
          },
          {
            key: 'status',
            header: 'Status',
            render: (p) => (
              <StatusPill value={statusLabel(p.status)} tone={STATUS_TONE[p.status]} />
            ),
          },
          {
            key: 'progress',
            header: 'Progress',
            render: (p) => <Progress project={p} />,
          },
          {
            key: 'due',
            header: 'Due',
            render: (p) => <Due project={p} />,
          },
        ]}
      />
    </div>
  )
}

/**
 * Progress as a count with a bar behind it.
 *
 * A project with no tasks recorded shows a dash rather than 0% — nothing has
 * been planned yet, which is not the same as nothing being done.
 */
function Progress({ project }: { project: ProjectRow }) {
  const percent = project.progress_percent
  if (percent === null || percent === undefined) {
    return <span style={{ color: 'var(--color-muted)' }}>No tasks yet</span>
  }
  return (
    <span style={{ display: 'inline-flex', flexDirection: 'column', gap: '0.25rem', minWidth: '7rem' }}>
      <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: '0.88rem' }}>
        {project.tasks_done}/{project.task_count} done
      </span>
      <span
        aria-hidden
        style={{
          height: 4,
          borderRadius: 999,
          background: 'var(--color-border)',
          overflow: 'hidden',
        }}
      >
        <span
          style={{
            display: 'block',
            height: '100%',
            width: `${percent}%`,
            background: percent === 100 ? 'var(--status-good-fg, #1c7c4a)' : 'var(--color-primary)',
          }}
        />
      </span>
    </span>
  )
}

function Due({ project }: { project: ProjectRow }) {
  if (!project.due_on) return <span style={{ color: 'var(--color-muted)' }}>—</span>
  const days = daysUntil(project.due_on)
  const late = project.is_open && days !== null && days < 0
  return (
    <span>
      {dayLabel(project.due_on)}
      {project.is_open && days !== null ? (
        <span
          style={{
            display: 'block',
            fontSize: '0.82rem',
            color: late ? 'var(--status-bad-fg, #b3261e)' : 'var(--color-muted)',
          }}
        >
          {days < 0
            ? `${Math.abs(days)} day${Math.abs(days) === 1 ? '' : 's'} late`
            : days === 0
              ? 'today'
              : `in ${days} day${days === 1 ? '' : 's'}`}
        </span>
      ) : null}
    </span>
  )
}
