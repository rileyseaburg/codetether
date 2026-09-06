'use client'

import Link from 'next/link'

export default function DashboardError({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <section
      role="alert"
      aria-labelledby="dashboard-error-title"
      className="mx-auto max-w-xl rounded-xl border border-red-200 bg-white p-6 shadow-sm dark:border-red-900 dark:bg-gray-800"
    >
      <h1
        id="dashboard-error-title"
        className="text-xl font-semibold text-gray-900 dark:text-white"
      >
        This page couldn’t load
      </h1>
      <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">
        An unexpected error interrupted the page. Your latest changes may not
        have been saved. Try loading it again, or return to your workspaces.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600"
        >
          Try again
        </button>
        <Link
          href="/dashboard"
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          Back to workspaces
        </Link>
      </div>
    </section>
  )
}
