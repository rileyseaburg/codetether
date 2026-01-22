'use client'

import { Container } from '@/components/Container'

const vaComparison = [
    { aspect: 'Cost (300 tasks/mo)', va: '$1,500-2,500/month', codetether: '$297/month' },
    { aspect: 'Availability', va: '8 hours/day', codetether: '24/7' },
    { aspect: 'Speed', va: '2-4 hours', codetether: '5-30 minutes' },
    { aspect: 'Scalability', va: '1 task at a time', codetether: '10+ concurrent' },
    { aspect: 'Consistency', va: 'Varies', codetether: 'Same every time' },
    { aspect: 'Data processing', va: 'Limited by human memory', codetether: '10M+ tokens with RLM' },
]

export function WhyNotDIY() {
    return (
        <section
            id="why-not-diy"
            aria-label="VA comparison"
            className="py-16 sm:py-24 bg-white dark:bg-gray-950"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-2xl text-center">
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        VAs Cost $1,800/mo.<br />
                        <span className="text-cyan-600 dark:text-cyan-400">CodeTether Costs $297.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        For repeatable tasks, AI workers are faster, cheaper, and more consistent.
                    </p>
                </div>

                {/* Comparison Table */}
                <div className="mt-16 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900">
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Aspect</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-500 dark:text-gray-400">Virtual Assistant</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                            {vaComparison.map((row) => (
                                <tr key={row.aspect}>
                                    <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{row.aspect}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{row.va}</td>
                                    <td className="px-6 py-4 text-sm text-cyan-600 dark:text-cyan-400 font-medium">{row.codetether}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Use Cases */}
                <div className="mt-16 grid md:grid-cols-2 gap-8">
                    <div className="rounded-2xl bg-gray-50 dark:bg-gray-900 p-6">
                        <h4 className="font-semibold text-gray-900 dark:text-white">Keep Using VAs For</h4>
                        <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                            <li>• Tasks requiring human judgment</li>
                            <li>• Phone calls and live communication</li>
                            <li>• Nuanced customer interactions</li>
                        </ul>
                    </div>
                    <div className="rounded-2xl bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-900 p-6">
                        <h4 className="font-semibold text-gray-900 dark:text-white">Use CodeTether For</h4>
                        <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-300">
                            <li>• Large-scale data processing (RLM handles 10M+ tokens)</li>
                            <li>• Content generation at scale</li>
                            <li>• Report generation with thorough recursive analysis</li>
                            <li>• Research and information gathering</li>
                        </ul>
                        <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                            RLM technology ensures consistent quality—no context rot, same thorough analysis every time.
                        </p>
                    </div>
                </div>
            </Container>
        </section>
    )
}
