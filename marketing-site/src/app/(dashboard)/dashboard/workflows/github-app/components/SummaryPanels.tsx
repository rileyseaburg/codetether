import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import { CountCard } from './CountCard'
import { HealthPanel } from './HealthPanel'

const badRouteStates = new Set(['missing_worker', 'stale_worker', 'unscoped_or_missing_target'])

export function SummaryPanels() {
  const { data } = useGithubAppWorkflows()
  const totals = data?.totals || {}
  const pending = totals.pending || 0
  const running = totals.running || 0
  const failed = totals.failed || 0
  const completed = totals.completed || 0
  const routeStates = data?.route_states || {}
  const failures = data?.failure_classes || {}
  const hasBadRoutes = Object.keys(routeStates).some((k) => badRouteStates.has(k))

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <CountCard label="Working now" value={running} hint={running > 0 ? 'agents currently leased' : 'no agent lease active'} tone="sky" />
        <CountCard label="Queued" value={pending} hint="waiting for an agent" tone="amber" />
        <CountCard label="Active backlog" value={pending + running} hint="running + queued" tone="slate" />
        <CountCard label="Completed" value={completed} hint="recent successful tasks" tone="emerald" />
        <CountCard label="Needs attention" value={failed} hint="failed GitHub tasks" tone="rose" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <HealthPanel
          title="Routing health"
          description="Are tasks pointed at live workers?"
          counts={routeStates}
          badge={hasBadRoutes ? 'Check routing' : 'Healthy'}
          tone={hasBadRoutes ? 'warn' : 'good'}
          note={hasBadRoutes ? 'Watch non-active routes first: missing targets, stale workers, or unscoped pending items are common stuck-queue causes.' : undefined}
        />
        <HealthPanel title="Failure classes" description="Grouped errors from the latest GitHub tasks." counts={failures} badge={`${Object.keys(failures).length} classes`} />
      </div>
    </div>
  )
}
