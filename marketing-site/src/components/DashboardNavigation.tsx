'use client'

import type { ComponentType, SVGProps } from 'react'
import Link from 'next/link'
import {
  Disclosure,
  DisclosureButton,
  DisclosurePanel,
} from '@headlessui/react'
import clsx from 'clsx'

type NavigationItem = {
  name: string
  href: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

type DashboardNavigationProps = {
  items: NavigationItem[]
  activeHref?: string
  onNavigate?: () => void
}

const primaryRoutes = [
  '/dashboard',
  '/dashboard/tasks',
  '/dashboard/sessions',
  '/dashboard/workers',
  '/dashboard/activity',
]
const utilityRoutes = ['/dashboard/billing', '/dashboard/settings']
const setupRoute = '/dashboard/getting-started'

export function DashboardNavigation({
  items,
  activeHref,
  onNavigate,
}: DashboardNavigationProps) {
  const primary = primaryRoutes.flatMap((href) =>
    items.filter((item) => item.href === href),
  )
  const utilities = utilityRoutes.flatMap((href) =>
    items.filter((item) => item.href === href),
  )
  const setup = items.find((item) => item.href === setupRoute)
  const advanced = items.filter(
    (item) =>
      !primaryRoutes.includes(item.href) &&
      !utilityRoutes.includes(item.href) &&
      item.href !== setupRoute,
  )
  const activeAdvanced = advanced.some((item) => item.href === activeHref)

  function renderLink(item: NavigationItem, label = item.name) {
    const selected = item.href === activeHref
    return (
      <Link
        href={item.href}
        onClick={onNavigate}
        aria-current={selected ? 'page' : undefined}
        className={clsx(
          'relative flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600',
          selected
            ? 'bg-gray-100 text-gray-950 dark:bg-gray-800 dark:text-white'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-950 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-gray-100',
        )}
      >
        {selected && (
          <span
            aria-hidden="true"
            className="absolute inset-y-3 left-0 w-0.5 rounded-full bg-cyan-600 dark:bg-cyan-400"
          />
        )}
        <item.icon
          aria-hidden="true"
          className="h-5 w-5 shrink-0 text-gray-400 dark:text-gray-500"
        />
        <span>{label}</span>
      </Link>
    )
  }

  return (
    <nav aria-label="Dashboard" className="flex flex-1 flex-col px-3 pt-5 pb-4">
      <ul className="space-y-1">
        {primary.map((item) => (
          <li key={item.href}>{renderLink(item)}</li>
        ))}
      </ul>
      {advanced.length > 0 && (
        <Disclosure
          key={activeAdvanced ? activeHref : 'primary'}
          defaultOpen={activeAdvanced}
          as="div"
          className="mt-4 border-t border-gray-200 pt-3 dark:border-gray-800"
        >
          {({ open }) => (
            <>
              <DisclosureButton className="flex min-h-11 w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-gray-100">
                More tools
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  fill="none"
                  className={clsx(
                    'h-4 w-4 transition-transform',
                    open && 'rotate-180',
                  )}
                >
                  <path
                    d="m6 8 4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </DisclosureButton>
              <DisclosurePanel>
                <ul className="mt-1 space-y-1">
                  {advanced.map((item) => (
                    <li key={item.href}>{renderLink(item)}</li>
                  ))}
                </ul>
              </DisclosurePanel>
            </>
          )}
        </Disclosure>
      )}
      <div className="mt-auto pt-8">
        <ul className="space-y-1 border-t border-gray-200 pt-3 dark:border-gray-800">
          {utilities.map((item) => (
            <li key={item.href}>{renderLink(item)}</li>
          ))}
          {setup && <li>{renderLink(setup, 'Setup guide')}</li>}
        </ul>
      </div>
    </nav>
  )
}
