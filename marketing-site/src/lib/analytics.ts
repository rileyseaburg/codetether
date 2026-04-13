'use client'

declare global {
    interface Window {
        gtag?: (...args: unknown[]) => void
    }
}

type AnalyticsParams = Record<string, string | number | boolean | null | undefined>

export function trackEvent(eventName: string, params: AnalyticsParams = {}) {
    if (typeof window === 'undefined' || !window.gtag) return

    window.gtag('event', eventName, params)
}

export function trackCtaClick(location: string, label: string) {
    trackEvent('cta_click', {
        event_category: 'engagement',
        cta_location: location,
        cta_label: label,
    })
}

export function trackSignupStart(method: string = 'unknown') {
    trackEvent('sign_up_start', {
        event_category: 'conversion',
        method,
    })
}

export function trackContactSubmit(source: string) {
    trackEvent('contact_submit', {
        event_category: 'conversion',
        source,
    })
}
