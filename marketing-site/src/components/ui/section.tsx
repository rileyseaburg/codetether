import clsx from 'clsx'

import { Container } from '@/components/Container'

const sectionVariants = {
  white: 'bg-white dark:bg-gray-950',
  muted: 'bg-gray-50 dark:bg-gray-900',
  dark: 'bg-gray-950',
  brandDark: 'bg-gray-900',
} as const

export type SectionVariant = keyof typeof sectionVariants

export function Section({
  className,
  variant = 'white',
  ...props
}: React.ComponentPropsWithoutRef<'section'> & { variant?: SectionVariant }) {
  return (
    <section
      className={clsx('py-20 sm:py-32', sectionVariants[variant], className)}
      {...props}
    />
  )
}

export function SectionContainer(props: React.ComponentPropsWithoutRef<typeof Container>) {
  return <Container {...props} />
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  align = 'left',
  invert = false,
  id,
  className,
}: {
  eyebrow?: string
  title: string
  description?: string
  align?: 'left' | 'center'
  invert?: boolean
  id?: string
  className?: string
}) {
  return (
    <div
      className={clsx(
        align === 'center' ? 'mx-auto max-w-2xl text-center' : 'mx-auto max-w-2xl lg:mx-0 lg:max-w-3xl',
        className,
      )}
    >
      {eyebrow && (
        <p className={clsx('text-sm font-semibold uppercase tracking-[0.22em]', invert ? 'text-cyan-200/80' : 'text-cyan-600 dark:text-cyan-400')}>
          {eyebrow}
        </p>
      )}
      <h2
        id={id}
        className={clsx('text-3xl font-medium tracking-tight sm:text-4xl', invert ? 'text-white' : 'text-gray-900 dark:text-white')}
      >
        {title}
      </h2>
      {description && (
        <p className={clsx('mt-4 text-lg', invert ? 'text-gray-400' : 'text-gray-600 dark:text-gray-300')}>
          {description}
        </p>
      )}
    </div>
  )
}
