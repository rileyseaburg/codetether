import TenantStatusBanner from '@/components/TenantStatusBanner'
import { NotificationBanner } from './NotificationBanner'
import type { Notice } from '../../lib/dashboard-types'
import type { ReactNode } from 'react'

interface Props {
  notice: Notice | null
  children: ReactNode
}

export function PageLayout({ notice, children }: Props) {
  return (
    <div className="space-y-6">
      <TenantStatusBanner />
      <NotificationBanner notice={notice} />
      {children}
    </div>
  )
}
