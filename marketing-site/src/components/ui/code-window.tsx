import clsx from 'clsx'

export function CodeWindow({
  children,
  className,
  chromeClassName,
}: {
  children: React.ReactNode
  className?: string
  chromeClassName?: string
}) {
  return (
    <div className={clsx('overflow-hidden rounded-xl bg-gray-950 shadow-xl ring-1 ring-white/10', className)}>
      <div className={clsx('flex items-center gap-2 border-b border-white/10 px-4 py-2', chromeClassName)}>
        <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
        <div className="h-2.5 w-2.5 rounded-full bg-yellow-500" />
        <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
      </div>
      {children}
    </div>
  )
}

export function PreCode({ code, className }: { code: string; className?: string }) {
  return (
    <pre className={clsx('overflow-x-auto p-4 text-sm text-gray-300', className)}>
      <code>{code}</code>
    </pre>
  )
}
