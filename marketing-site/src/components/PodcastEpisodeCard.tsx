import Link from 'next/link'

import {
    type Episode,
    formatEpisodeDate,
    formatEpisodeDuration,
} from '@/components/podcastData'

export function PodcastEpisodeCard({ episode }: { episode: Episode }) {
    return (
        <article className="rounded-3xl border border-gray-200 bg-gray-50 p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900/70">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <p className="text-sm font-medium text-cyan-700 dark:text-cyan-300">
                        Episode {episode.episode_number ?? episode.episode_id} · {formatEpisodeDate(episode.published_at)} · {formatEpisodeDuration(episode)}
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold text-gray-950 dark:text-white">
                        <Link href={`/podcast/episodes/${episode.episode_id}`}>
                            {episode.title}
                        </Link>
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
    )
}
