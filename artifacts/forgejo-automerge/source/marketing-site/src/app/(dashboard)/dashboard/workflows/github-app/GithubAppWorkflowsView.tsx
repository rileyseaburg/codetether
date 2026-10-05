'use client'

import { useGithubAppWorkflows } from './GithubAppWorkflowsContext'
import { ActionRequiredPanel } from './components/ActionRequiredPanel'
import { EmptyState } from './components/EmptyState'
import { HeaderControls } from './components/HeaderControls'
import { RunsTable } from './components/RunsTable'
import { SummaryPanels } from './components/SummaryPanels'
import { ValueMetricsPanel } from './components/ValueMetricsPanel'
import { TasksTable } from './components/TasksTable'
import { WorkflowsTable } from './components/WorkflowsTable'

export function GithubAppWorkflowsView() {
  const { error, loading } = useGithubAppWorkflows()
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <HeaderControls />
        {loading ? (
          <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm font-medium text-sky-800">
            Refreshing GitHub agent telemetry…
          </div>
        ) : null}
        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {error}
          </div>
        ) : null}
        <ActionRequiredPanel />
        <ValueMetricsPanel />
        <EmptyState />
        <SummaryPanels />
        <WorkflowsTable />
        <TasksTable />
        <RunsTable />
      </div>
    </div>
  )
}
