import clsx from 'clsx'

export function MetricCard({
  value,
  label,
  className,
  invert = false,
}: {
  value: string
  label: string
  className?: string
  invert?: boolean
}) {
  return (
    <div className={clsx('rounded-2xl p-4 text-center', invert ? 'border border-white/10 bg-white/[0.04]' : 'border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900', className)}>
      <div className={clsx('text-2xl font-bold', invert ? 'text-white' : 'text-gray-900 dark:text-white')}>{value}</div>
      <div className={clsx('mt-1 text-[11px] leading-4', invert ? 'text-gray-400' : 'text-gray-500 dark:text-gray-400')}>{label}</div>
    </div>
  )
}
