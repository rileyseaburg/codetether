import clsx from 'clsx'

const cardVariants = {
  default: 'border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-950',
  elevated: 'border border-gray-200 bg-white shadow-lg shadow-gray-900/5 dark:border-gray-800 dark:bg-gray-900 dark:shadow-black/20',
  glass: 'border border-white/10 bg-white/[0.06] shadow-2xl shadow-cyan-950/30 backdrop-blur-xl',
  dark: 'border border-white/10 bg-gray-950/70 shadow-2xl shadow-black/20',
} as const

export type CardVariant = keyof typeof cardVariants

export function Card({
  className,
  variant = 'default',
  ...props
}: React.ComponentPropsWithoutRef<'div'> & { variant?: CardVariant }) {
  return (
    <div
      className={clsx('rounded-3xl', cardVariants[variant], className)}
      {...props}
    />
  )
}
