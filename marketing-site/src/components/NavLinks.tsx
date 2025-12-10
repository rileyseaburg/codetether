'use client'

import Link from 'next/link'

export function NavLinks() {
    return (
        <>
            <Link
                href="#features"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
                Features
            </Link>
            <Link
                href="#use-cases"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
                Use Cases
            </Link>
            <Link
                href="#roadmap"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
                Roadmap
            </Link>
            <Link
                href="#pricing"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
                Pricing
            </Link>
            <Link
                href="/docs"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
                Docs
            </Link>
            <Link
                href="https://github.com/rileyseaburg/A2A-Server-MCP"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                target="_blank"
            >
                GitHub
            </Link>
        </>
    )
}
