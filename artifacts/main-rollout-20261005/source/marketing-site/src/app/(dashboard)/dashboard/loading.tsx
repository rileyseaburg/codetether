export default function DashboardLoading() {
  return (
    <section
      role="status"
      aria-label="Loading dashboard page"
      className="space-y-6"
    >
      <span className="sr-only">Loading dashboard page…</span>
      <div aria-hidden="true" className="space-y-6 motion-safe:animate-pulse">
        <div className="h-8 w-48 rounded bg-gray-200 dark:bg-gray-700" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="h-28 rounded-xl bg-gray-200 dark:bg-gray-800"
            />
          ))}
        </div>
        <div className="space-y-4 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="h-5 rounded bg-gray-200 dark:bg-gray-800"
            />
          ))}
        </div>
      </div>
    </section>
  )
}
