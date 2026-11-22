const feedUrl = 'https://codetether.run/podcast/feed.xml'
const appleAddShowUrl = 'podcasts://podcasts.apple.com/add?feed=' + encodeURIComponent(feedUrl)

export function PodcastSubscribePanel() {
    return (
        <section className="mt-10 rounded-3xl border border-cyan-200 bg-cyan-50 p-6 text-left dark:border-cyan-900 dark:bg-cyan-950/30">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-xl font-semibold text-gray-950 dark:text-white">
                        Follow in Apple Podcasts
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-gray-700 dark:text-gray-300">
                        Use the button, or paste the custom RSS URL into Apple Podcasts.
                    </p>
                </div>
                <a
                    href={appleAddShowUrl}
                    className="rounded-full bg-purple-600 px-5 py-3 text-center text-sm font-semibold text-white hover:bg-purple-500"
                >
                    Open in Apple Podcasts
                </a>
            </div>
            <ol className="mt-5 list-decimal space-y-2 pl-5 text-sm text-gray-700 dark:text-gray-300">
                <li>Open Apple Podcasts.</li>
                <li>Choose File → Follow a Show by URL.</li>
                <li>Paste the RSS feed below and confirm.</li>
            </ol>
            <code className="mt-4 block overflow-x-auto rounded-2xl bg-white p-3 text-sm text-gray-900 dark:bg-gray-900 dark:text-gray-100">
                {feedUrl}
            </code>
        </section>
    )
}
