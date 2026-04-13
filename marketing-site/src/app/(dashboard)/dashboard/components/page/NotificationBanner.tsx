import type { Notice } from '../../lib/dashboard-types'

interface Props {
  notice: Notice | null
}

const toneMap: Record<Notice['type'], string> = {
  success: 'bg-green-50 text-green-800 dark:bg-green-900 dark:text-green-200',
  warning: 'bg-yellow-50 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  error: 'bg-red-50 text-red-800 dark:bg-red-900 dark:text-red-200',
}

export function NotificationBanner({ notice }: Props) {
  if (!notice) return null
  return (
    <div className={`fixed top-4 right-4 z-50 max-w-md rounded-lg p-4 shadow-lg ${toneMap[notice.type]}`}>
      <p className="font-medium">{notice.message}</p>
      {notice.detail ? <p className="mt-1 text-sm opacity-90">{notice.detail}</p> : null}
    </div>
  )
}
