'use client'

import { HeaderControls } from './components/HeaderControls'
import { RunsTable } from './components/RunsTable'
import { SummaryPanels } from './components/SummaryPanels'
import { TasksTable } from './components/TasksTable'
import { WorkflowsTable } from './components/WorkflowsTable'
import { useTetherScriptWorkflows } from './useTetherScriptWorkflows'

export default function TetherScriptWorkflowsPage() {
  const workflow = useTetherScriptWorkflows()
  const { data, error, loading } = workflow

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <HeaderControls {...workflow} />
        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {error}
          </div>
        ) : null}
        <SummaryPanels data={data} />
        <WorkflowsTable rows={data?.workflows || []} loading={loading} />
        <TasksTable rows={data?.tasks || []} />
        <RunsTable rows={data?.runs || []} loading={loading} />
        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 shadow-sm">
            Loading workflow pane…
          </div>
        ) : null}
      </div>
    </div>
  )
}
