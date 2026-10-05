/** Defensive display conversion for partially available billing APIs. */
export function finiteNumber(value: unknown): number | null {
  if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim()))
    return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function nonNegativeNumber(value: unknown): number | null {
  const number = finiteNumber(value)
  return number !== null && number >= 0 ? number : null
}

/** The live billing API uses -1, not a missing value, for unlimited quotas. */
export function quotaNumber(value: unknown): number | null {
  const number = finiteNumber(value)
  return number === -1 ? -1 : nonNegativeNumber(value)
}

export function formatQuota(value: unknown): string {
  const number = quotaNumber(value)
  return number === -1 ? 'Unlimited' : formatNumber(number)
}

export function subscriptionPlan(data: {
  tier?: unknown
  tier_name?: unknown
  plan?: unknown
}) {
  const value = data.tier ?? data.plan
  const tier = typeof value === 'string' ? value : 'unknown'
  const names: Record<string, string> = {
    free: 'Free',
    pro: 'Pro',
    enterprise: 'Enterprise',
  }
  return {
    tier,
    tier_name:
      typeof data.tier_name === 'string'
        ? data.tier_name
        : names[tier] || 'Unavailable',
  }
}

export function formatNumber(value: unknown, digits?: number): string {
  const number = finiteNumber(value)
  return number === null
    ? 'Unavailable'
    : digits === undefined
      ? number.toLocaleString()
      : number.toFixed(digits)
}

export function usagePercentage(used: unknown, limit: unknown): number {
  const numerator = nonNegativeNumber(used)
  const denominator = nonNegativeNumber(limit)
  if (numerator === null || denominator === null || denominator === 0) return 0
  return Math.max(0, Math.min(100, (numerator / denominator) * 100))
}

export function remainingTasks(used: unknown, limit: unknown): number | null {
  const count = nonNegativeNumber(used)
  const quota = quotaNumber(limit)
  if (quota === -1) return -1
  return count === null || quota === null ? null : Math.max(0, quota - count)
}
