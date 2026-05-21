export function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export const DEFAULT_REPOS =
  'CodeTether/TetherScript,rileyseaburg/codetether-agent'
