import clsx from 'clsx'

const badgeVariants = {
  brand: 'bg-cyan-300/10 text-cyan-100 ring-cyan-300/20',
  brandLight: 'bg-cyan-50 text-cyan-700 ring-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:ring-cyan-800',
  success: 'bg-green-100 text-green-700 ring-green-200 dark:bg-green-900/30 dark:text-green-400 dark:ring-green-800',
  neutral: 'bg-gray-100 text-gray-700 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700',
} as const

export type BadgeVariant = keyof typeof badgeVariants

export function Badge({
  className,
  variant = 'neutral',
  ...props
}: React.ComponentPropsWithoutRef<'span'> & { variant?: BadgeVariant }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset',
        badgeVariants[variant],
        className,
      )}
      {...props}
    />
  )
}
