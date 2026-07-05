import Link from 'next/link'

import { PodcastEpisodeCard } from '@/components/PodcastEpisodeCard'
import { podcastEpisodes, podcastInfo } from '@/components/podcastData'

export function PodcastLanding() {
    return (
        <main className="bg-white py-20 dark:bg-gray-950 sm:py-28">
            <div className="mx-auto max-w-5xl px-6 lg:px-8">
                <PodcastHero />
                <section className="mt-16 space-y-8">
                    {podcastEpisodes.map((episode) => (
                        <PodcastEpisodeCard key={episode.episode_id} episode={episode} />
                    ))}
                </section>
            </div>
        </main>
    )
}

function PodcastHero() {
    return (
        <div className="mx-auto max-w-3xl text-center">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-600 dark:text-cyan-400">
                Podcast
            </p>
            <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-950 dark:text-white sm:text-6xl">
                {podcastInfo.title}
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-700 dark:text-gray-300">
                {podcastInfo.description}
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link
                    href="/podcast/feed.xml"
                    className="rounded-full bg-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-cyan-500"
                >
                    Subscribe via RSS
                </Link>
                <a
                    href={podcastEpisodes[0]?.audio_url ?? '/podcast/feed.xml'}
                    className="rounded-full border border-gray-300 px-5 py-3 text-sm font-semibold text-gray-900 hover:bg-gray-50 dark:border-gray-700 dark:text-white dark:hover:bg-gray-900"
                >
                    Play latest episode
                </a>
            </div>
        </div>
    )
}
