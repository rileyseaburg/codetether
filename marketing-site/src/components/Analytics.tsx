'use client'

import { useEffect } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import Script from 'next/script'

const GA_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID

declare global {
    interface Window {
        gtag?: (...args: unknown[]) => void
        dataLayer?: unknown[]
    }
}

export function Analytics() {
    const pathname = usePathname()
    const searchParams = useSearchParams()

    useEffect(() => {
        if (!GA_ID || !window.gtag) return

        const query = searchParams?.toString()
        const pagePath = query ? `${pathname}?${query}` : pathname

        window.gtag('event', 'page_view', {
            page_path: pagePath,
            page_title: document.title,
        })
    }, [pathname, searchParams])

    if (!GA_ID) return null

    return (
        <>
            <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
            <Script id="gtag-init" strategy="afterInteractive">
                {`
                  window.dataLayer = window.dataLayer || [];
                  function gtag(){dataLayer.push(arguments);}
                  window.gtag = gtag;
                  gtag('js', new Date());
                  gtag('config', '${GA_ID}', { send_page_view: false });
                `}
            </Script>
        </>
    )
}
