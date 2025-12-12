'use client'

import Link from 'next/link'

export function NavLinks() {
    return (
        <>
            <Link
                href="#features"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            >
                Features
            </Link>
            <Link
                href="#use-cases"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            >
                Use Cases
            </Link>
            <Link
                href="#roadmap"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            >
                Roadmap
            </Link>
            <Link
                href="#pricing"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            >
                Pricing
            </Link>
            <a
                href="https://docs.codetether.run"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
            >
                Docs
            </a>
            <Link
                href="https://github.com/rileyseaburg/codetether"
                className="inline-block rounded-lg px-2 py-1 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
                target="_blank"
            >
                GitHub
            </Link>
        </>
    )
}
