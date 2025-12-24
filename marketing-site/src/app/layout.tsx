import { type Metadata } from 'next'
import { Inter } from 'next/font/google'
import clsx from 'clsx'

import '@/styles/tailwind.css'
import { AuthProvider } from '@/components/AuthProvider'

const inter = Inter({
    subsets: ['latin'],
    display: 'swap',
    variable: '--font-inter',
})

export const metadata: Metadata = {
    title: {
        template: '%s - CodeTether',
        default: 'CodeTether - Production A2A Coordination Platform',
    },
    description:
        'CodeTether is a production-ready A2A (Agent-to-Agent) coordination layer that lets your AI agents collaborate, share tools, and orchestrate complex workflows with real-time streaming and enterprise-grade security.',
    keywords: [
        'CodeTether',
        'A2A',
        'Agent-to-Agent',
        'MCP',
        'Model Context Protocol',
        'AI Agents',
        'Multi-Agent Systems',
        'Agent Orchestration',
        'Kubernetes',
        'Enterprise AI',
    ],
    authors: [{ name: 'Riley Seaburg' }],
    openGraph: {
        title: 'CodeTether - Production A2A Coordination Platform',
        description:
            'The A2A protocol-native platform for connecting AI agents. Routing, sessions, history, observability, and MCP tool integration.',
        url: 'https://codetether.run',
        siteName: 'CodeTether',
        type: 'website',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'CodeTether',
        description: 'Production-ready A2A coordination layer for AI agent teams.',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" style={{ maxHeight: '100vh' }} className={clsx('bg-gray-50 dark:bg-blue-950 antialiased', inter.variable)}>
            <body style={{ maxHeight: '100vh' }} className="bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen">
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    )
}
