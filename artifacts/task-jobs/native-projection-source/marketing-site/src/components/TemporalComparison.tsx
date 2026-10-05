'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

const gaps = [
    {
        need: 'Process 500 leads with AI analysis',
        zapier: 'Rate limits, timeouts, expensive',
        codetether: 'Webhook in, all 500 processed, callback when done',
    },
    {
        need: 'AI step that runs 20+ minutes',
        zapier: '30-second timeout. Task fails.',
        codetether: 'Up to 60 min with recursive decomposition.',
    },
    {
        need: 'Handle large datasets or context',
        zapier: 'Limited context window.',
        codetether: '10M+ tokens with RLM processing.',
    },
    {
        need: 'Audit trail for compliance',
        zapier: 'Basic run history.',
        codetether: 'Every action append-only logged with timestamps.',
    },
    {
        need: 'Plugin security and isolation',
        zapier: 'Shared runtime, trust-based.',
        codetether: 'Sandboxed with Ed25519 code signing.',
    },
    {
        need: 'Refine the output after seeing it',
        zapier: 'Run the whole Zap again.',
        codetether: 'Reply to email to continue.',
    },
]

export function TemporalComparison() {
    return (
        <section
            id="zapier-comparison"
            aria-label="Zapier comparison"
            className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-2xl text-center">
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        Zapier Moves Data.<br />
                        <span className="text-cyan-600 dark:text-cyan-400">CodeTether Does the Work.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        No 30-second timeouts. No context limits. Real deliverables.
                    </p>
                </div>

                {/* Comparison Table */}
                <div className="mt-16 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-gray-100 dark:bg-gray-800">
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Your Need</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-500 dark:text-gray-400">Zapier AI</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                            {gaps.map((row) => (
                                <tr key={row.need}>
                                    <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300">{row.need}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-500">{row.zapier}</td>
                                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-200 font-medium">{row.codetether}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Why It Works - RLM Explanation */}
                <div className="mt-12 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6">
                    <h3 className="font-semibold text-gray-900 dark:text-white text-lg">Why It Works: Recursive Language Model</h3>
                    <div className="mt-4 grid md:grid-cols-3 gap-6 text-sm">
                        <div>
                            <p className="font-medium text-cyan-600 dark:text-cyan-400">Recursive Processing</p>
                            <p className="mt-2 text-gray-600 dark:text-gray-400">
                                Tasks are decomposed, processed in parallel, verified, and stitched back together. No 30-second wall.
                            </p>
                        </div>
                        <div>
                            <p className="font-medium text-cyan-600 dark:text-cyan-400">Input as Environment</p>
                            <p className="mt-2 text-gray-600 dark:text-gray-400">
                                Your data becomes the context. The model navigates and processes it like a workspace, not a fixed prompt.
                            </p>
                        </div>
                        <div>
                            <p className="font-medium text-cyan-600 dark:text-cyan-400">Cost Efficient</p>
                            <p className="mt-2 text-gray-600 dark:text-gray-400">
                                Median RLM run costs less than a single base model call. Smarter routing, not brute force.
                            </p>
                        </div>
                    </div>
                </div>

                {/* How It Works */}
                <div className="mt-8 grid md:grid-cols-2 gap-8">
                    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6">
                        <h4 className="font-semibold text-gray-900 dark:text-white">Trigger a Task</h4>
                        <pre className="mt-4 text-sm text-gray-600 dark:text-gray-400 overflow-x-auto bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                            {`POST /v1/tasks
{
  "prompt": "Analyze leads.csv",
  "email_results": true,
  "callback_url": "your-webhook"
}`}
                        </pre>
                    </div>
                    <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900 bg-cyan-50 dark:bg-cyan-950/30 p-6">
                        <h4 className="font-semibold text-gray-900 dark:text-white">Get Results</h4>
                        <div className="mt-4 text-sm text-gray-600 dark:text-gray-300">
                            <p className="text-cyan-600 dark:text-cyan-400 font-medium">Email arrives:</p>
                            <p className="mt-2">Your task is complete.</p>
                            <p className="mt-1">Analyzed 847 leads. Found 142 high-value.</p>
                            <p className="mt-2 text-cyan-600 dark:text-cyan-400">lead_scores.csv attached</p>
                            <p className="mt-4 text-xs text-gray-500">Reply to refine the analysis</p>
                        </div>
                    </div>
                </div>

                {/* CTA */}
                <div className="mt-12 text-center">
                    <Button href="/register" color="cyan">
                        Try Free (10 tasks/month)
                    </Button>
                </div>
            </Container>
        </section>
    )
}
