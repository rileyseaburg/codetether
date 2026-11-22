import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { PodcastEpisodeDetail } from '@/components/PodcastEpisodeDetail'
import { podcastEpisodes } from '@/components/podcastData'

type PageProps = {
    params: Promise<{ episodeId: string }>
}

export function generateStaticParams() {
    return podcastEpisodes.map((episode) => ({ episodeId: episode.episode_id }))
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { episodeId } = await params
    const episode = podcastEpisodes.find((item) => item.episode_id === episodeId)
    if (!episode) return { title: 'Podcast episode not found' }
    return {
        title: episode.title,
        description: episode.description,
        alternates: { types: { 'application/rss+xml': '/podcast/feed.xml' } },
    }
}

export default async function EpisodePage({ params }: PageProps) {
    const { episodeId } = await params
    const episode = podcastEpisodes.find((item) => item.episode_id === episodeId)
    if (!episode) notFound()
    return <PodcastEpisodeDetail episode={episode} />
}
