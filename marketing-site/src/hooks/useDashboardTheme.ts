'use client'

import { useEffect, useSyncExternalStore } from 'react'

export const DASHBOARD_THEME_KEY = 'codetether-theme'
const THEME_CHANGE = 'codetether-theme-change'
type Theme = 'light' | 'dark'
let volatileTheme: Theme | undefined

function readTheme(): Theme {
  if (volatileTheme) return volatileTheme
  try {
    const stored = localStorage.getItem(DASHBOARD_THEME_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // A privacy-restricted browser can still switch themes for this page.
  }
  return 'dark'
}

function subscribe(notify: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === DASHBOARD_THEME_KEY) {
      volatileTheme = undefined
      notify()
    }
  }
  window.addEventListener('storage', onStorage)
  window.addEventListener(THEME_CHANGE, notify)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener(THEME_CHANGE, notify)
  }
}

export function useDashboardTheme() {
  const theme = useSyncExternalStore(
    subscribe,
    readTheme,
    () => 'dark' as const,
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
  }, [theme])

  const toggleTheme = () => {
    const next = readTheme() === 'dark' ? 'light' : 'dark'
    try {
      localStorage.setItem(DASHBOARD_THEME_KEY, next)
      volatileTheme = undefined
    } catch {
      // Existing stored values must not override a choice we could not save.
      volatileTheme = next
    }
    window.dispatchEvent(new Event(THEME_CHANGE))
  }
  return { darkMode: theme === 'dark', toggleTheme }
}
