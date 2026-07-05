import type { Metadata } from 'next'
import Link from 'next/link'

import podcast from '../../../../public/podcast/podcast.json'

type Episode = {
    episode_id: string
    episode_number?: number
    title: string
    description: string
    audio_url: string
    duration_text?: string
    duration_seconds?: number
    published_at?: string
}

const episodes = (podcast.episodes as Episode[]).slice().sort((a, b) => {
    return String(b.published_at ?? '').localeCompare(String(a.published_at ?? ''))
})

function formatDuration(episode: Episode) {
    if (episode.duration_text) return episode.duration_text
    const total = Math.round(Number(episode.duration_seconds ?? 0))
    const minutes = Math.floor(total / 60)
    const seconds = total % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

function formatDate(value?: string) {
    if (!value) return 'Unpublished'
    return new Intl.DateTimeFormat('en', {
        dateStyle: 'medium',
        timeZone: 'UTC',
    }).format(new Date(value))
}

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
    return (
        <main className="bg-white py-20 dark:bg-gray-950 sm:py-28">
            <div className="mx-auto max-w-5xl px-6 lg:px-8">
                <div className="mx-auto max-w-3xl text-center">
                    <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-600 dark:text-cyan-400">
                        Podcast
                    </p>
                    <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-950 dark:text-white sm:text-6xl">
                        {podcast.title}
                    </h1>
                    <p className="mt-6 text-lg leading-8 text-gray-700 dark:text-gray-300">
                        {podcast.description}
                    </p>
                    <div className="mt-8 flex flex-wrap justify-center gap-3">
                        <Link
                            href="/podcast/feed.xml"
                            className="rounded-full bg-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-cyan-500"
                        >
                            Subscribe via RSS
                        </Link>
                        <a
                            href={episodes[0]?.audio_url ?? '/podcast/feed.xml'}
                            className="rounded-full border border-gray-300 px-5 py-3 text-sm font-semibold text-gray-900 hover:bg-gray-50 dark:border-gray-700 dark:text-white dark:hover:bg-gray-900"
                        >
                            Play latest episode
                        </a>
                    </div>
                </div>

                <section className="mt-16 space-y-8">
                    {episodes.map((episode) => (
                        <article
                            key={episode.episode_id}
                            className="rounded-3xl border border-gray-200 bg-gray-50 p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900/70"
                        >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                    <p className="text-sm font-medium text-cyan-700 dark:text-cyan-300">
                                        Episode {episode.episode_number ?? episode.episode_id} · {formatDate(episode.published_at)} · {formatDuration(episode)}
                                    </p>
                                    <h2 className="mt-2 text-2xl font-semibold text-gray-950 dark:text-white">
                                        {episode.title}
                                    </h2>
                                </div>
                                <a
                                    href={episode.audio_url}
                                    className="mt-2 shrink-0 rounded-full bg-gray-950 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800 dark:bg-white dark:text-gray-950 dark:hover:bg-gray-200 sm:mt-0"
                                >
                                    MP3
                                </a>
                            </div>
                            <p className="mt-4 text-base leading-7 text-gray-700 dark:text-gray-300">
                                {episode.description}
                            </p>
                            <audio className="mt-5 w-full" controls preload="none" src={episode.audio_url} />
                        </article>
                    ))}
                </section>
            </div>
        </main>
    )
}
