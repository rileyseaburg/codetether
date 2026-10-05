import Link from 'next/link'

import {
    type Episode,
    formatEpisodeDate,
    formatEpisodeDuration,
} from '@/components/podcastData'

export function PodcastEpisodeDetail({ episode }: { episode: Episode }) {
    return (
        <main className="bg-white py-20 dark:bg-gray-950 sm:py-28">
            <article className="mx-auto max-w-3xl px-6 lg:px-8">
                <Link href="/podcast" className="text-sm font-semibold text-cyan-700 dark:text-cyan-300">
                    ← All episodes
                </Link>
                <p className="mt-8 text-sm font-medium text-cyan-700 dark:text-cyan-300">
                    Episode {episode.episode_number ?? episode.episode_id} · {formatEpisodeDate(episode.published_at)} · {formatEpisodeDuration(episode)}
                </p>
                <h1 className="mt-3 text-4xl font-bold tracking-tight text-gray-950 dark:text-white sm:text-5xl">
                    {episode.title}
                </h1>
                <p className="mt-6 text-lg leading-8 text-gray-700 dark:text-gray-300">
                    {episode.description}
                </p>
                <audio className="mt-8 w-full" controls preload="metadata" src={episode.audio_url} />
                <div className="mt-8 flex flex-wrap gap-3">
                    <a href={episode.audio_url} className="rounded-full bg-gray-950 px-5 py-3 text-sm font-semibold text-white hover:bg-gray-800 dark:bg-white dark:text-gray-950 dark:hover:bg-gray-200">
                        Download MP3
                    </a>
                    <Link href="/podcast/feed.xml" className="rounded-full border border-gray-300 px-5 py-3 text-sm font-semibold text-gray-900 hover:bg-gray-50 dark:border-gray-700 dark:text-white dark:hover:bg-gray-900">
                        RSS feed
                    </Link>
                </div>
            </article>
        </main>
    )
}
