import React from 'react'

export function Logomark(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 40 40" aria-hidden="true" {...props}>
            <circle cx="20" cy="20" r="18" strokeWidth="2" stroke="currentColor" fill="none" />
            <circle cx="12" cy="16" r="4" fill="currentColor" />
            <circle cx="28" cy="16" r="4" fill="currentColor" />
            <path
                d="M12 16L20 28L28 16"
                strokeWidth="2"
                stroke="currentColor"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <circle cx="20" cy="28" r="3" fill="currentColor" />
        </svg>
    )
}

export function Logo(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 160 40" aria-hidden="true" {...props}>
            {/* Icon */}
            <circle cx="20" cy="20" r="18" strokeWidth="2" stroke="currentColor" fill="none" />
            <circle cx="12" cy="16" r="4" fill="currentColor" />
            <circle cx="28" cy="16" r="4" fill="currentColor" />
            <path
                d="M12 16L20 28L28 16"
                strokeWidth="2"
                stroke="currentColor"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <circle cx="20" cy="28" r="3" fill="currentColor" />
            {/* Text */}
            <text x="48" y="26" fontSize="14" fontWeight="600" fill="currentColor" fontFamily="system-ui, sans-serif">
                CodeTether
            </text>
        </svg>
    )
}
