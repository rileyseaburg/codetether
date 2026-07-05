import type { Metadata } from 'next'

import { PodcastLanding } from '@/components/PodcastLanding'

export const metadata: Metadata = {
    title: 'CodeTether Radio Podcast',
    description:
        'CodeTether Radio: conversations and field reports about autonomous software development, A2A agents, MCP tools, Ralph, RLM, and AI engineering.',
    alternates: {
        types: {
            'application/rss+xml': '/podcast/feed.xml',
        },
    },
}

export default function PodcastPage() {
    return <PodcastLanding />
}
