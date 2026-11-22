import { useMemo } from 'react'
import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import type { GithubAppWorkflowResponse } from '../types'

interface Metric {
  label: string
  value: string
  hint: string
  accent: string
}

export function ValueMetricsPanel() {
  const { data } = useGithubAppWorkflows()
  const metrics = useMemo(() => buildMetrics(data), [data])

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <article
          key={metric.label}
          className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className={`h-1.5 w-12 rounded-full ${metric.accent}`} />
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {metric.label}
          </p>
          <div className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
            {metric.value}
          </div>
          <p className="mt-2 text-sm leading-5 text-slate-500">{metric.hint}</p>
        </article>
      ))}
    </section>
  )
}

function buildMetrics(data: GithubAppWorkflowResponse | null): Metric[] {
  const totals = data?.totals || {}
  const workflows = data?.workflows || []
  const tasks = data?.tasks || []
  const completed = totals.completed || 0
  const running = totals.running || 0
  const pending = totals.pending || 0
  const failed = totals.failed || 0
  const repos = new Set(
    workflows.map((workflow) => workflow.repo).filter(Boolean),
  ).size
  const surfacedRisks = failed + countBadRoutes(data)
  const estimatedHours = Math.max(completed, tasks.length) * 2

  return [
    {
      label: 'Repos protected',
      value: String(repos || '—'),
      hint: repos ? 'Repositories with recent GitHub agent activity.' : 'Connect repos to show coverage.',
      accent: 'bg-cyan-500',
    },
    {
      label: 'Work in motion',
      value: String(running + pending),
      hint: `${running} running and ${pending} queued right now.`,
      accent: 'bg-sky-500',
    },
    {
      label: 'Risks surfaced',
      value: String(surfacedRisks),
      hint: 'Failures and routing issues visible before customers escalate.',
      accent: surfacedRisks > 0 ? 'bg-amber-500' : 'bg-emerald-500',
    },
    {
      label: 'Hours leveraged',
      value: `${estimatedHours}h`,
      hint: 'Simple estimate from agent-handled tasks; tune with billing data.',
      accent: 'bg-violet-500',
    },
  ]
}

function countBadRoutes(data: GithubAppWorkflowResponse | null) {
  const routeStates = data?.route_states || {}
  return (
    (routeStates.missing_worker || 0) +
    (routeStates.stale_worker || 0) +
    (routeStates.unscoped_or_missing_target || 0)
  )
}
