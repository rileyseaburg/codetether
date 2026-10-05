import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'

export function EmptyState() {
  const { data, loading } = useGithubAppWorkflows()
  const hasRows = Boolean(
    data?.workflows.length || data?.tasks.length || data?.runs.length,
  )
  if (loading || hasRows) return null

  return (
    <section className="rounded-3xl border border-dashed border-cyan-300 bg-cyan-50/70 p-8 text-center shadow-sm">
      <div className="mx-auto max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">
          Ready to prove value
        </p>
        <h2 className="mt-2 text-2xl font-bold text-slate-950">
          No GitHub agent workflows yet
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Install the GitHub App, comment{' '}
          <code className="rounded bg-white px-1.5 py-0.5 text-cyan-800">
            @codetether handle this issue
          </code>{' '}
          on a repository task, and this command center will show live work,
          evidence, routing health, and customer-safe actions.
        </p>
        <div className="mt-6 grid gap-3 text-left sm:grid-cols-3">
          <Step number="1" title="Connect" body="Install the GitHub App." />
          <Step number="2" title="Trigger" body="Mention CodeTether on an issue or PR." />
          <Step number="3" title="Prove" body="Track PRs, validation, and agent evidence here." />
        </div>
      </div>
    </section>
  )
}

function Step({ number, title, body }: { number: string; title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-cyan-100 bg-white p-4">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
        {number}
      </div>
      <h3 className="mt-3 font-semibold text-slate-950">{title}</h3>
      <p className="mt-1 text-sm text-slate-500">{body}</p>
    </div>
  )
}
