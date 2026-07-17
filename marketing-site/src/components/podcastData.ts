import podcast from '../../public/podcast/podcast.json'

export type Episode = {
    episode_id: string
    episode_number?: number
    title: string
    description: string
    audio_url: string
    duration_text?: string
    duration_seconds?: number
    published_at?: string
}

export const podcastInfo = podcast

export const podcastEpisodes = (podcast.episodes as Episode[]).slice().sort((a, b) =>
    String(b.published_at ?? '').localeCompare(String(a.published_at ?? '')),
)

export function formatEpisodeDuration(episode: Episode) {
    if (episode.duration_text) return episode.duration_text
    const total = Math.round(Number(episode.duration_seconds ?? 0))
    const minutes = Math.floor(total / 60)
    const seconds = total % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export function formatEpisodeDate(value?: string) {
    if (!value) return 'Unpublished'
    return new Intl.DateTimeFormat('en', {
        dateStyle: 'medium',
        timeZone: 'UTC',
    }).format(new Date(value))
}
