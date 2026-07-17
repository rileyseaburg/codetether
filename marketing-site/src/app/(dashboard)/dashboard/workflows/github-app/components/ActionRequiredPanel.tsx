import { useMemo } from 'react'
import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import {
  badgeClasses,
  buildActionItems,
  toneClasses,
  type ActionItem,
} from './actionRequiredItems'

export function ActionRequiredPanel() {
  const { data } = useGithubAppWorkflows()
  const items = useMemo(() => buildActionItems(data), [data])
  if (!items.length) return <CalmState />
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-rose-600">
            Action required
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">
            Fix these before customers ask
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Prioritized operational risks from the GitHub automation queue.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
          {items.length} live signals
        </span>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {items.map((item) => <ActionCard key={item.title} item={item} />)}
      </div>
    </section>
  )
}

function CalmState() {
  return (
    <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
            Action required
          </p>
          <h2 className="mt-1 text-xl font-semibold text-emerald-950">
            No urgent GitHub agent issues
          </h2>
          <p className="mt-1 text-sm text-emerald-800">
            Routing, failures, and active queue signals look calm right now.
          </p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
          Ready for customers
        </span>
      </div>
    </section>
  )
}

function ActionCard({ item }: { item: ActionItem }) {
  return (
    <article className={`rounded-2xl border p-4 ${toneClasses[item.tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{item.title}</h3>
          <p className="mt-1 text-sm opacity-80">{item.detail}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${badgeClasses[item.tone]}`}
        >
          {item.count}
        </span>
      </div>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wide opacity-70">
        {item.cta}
      </p>
    </article>
  )
}
