'use client'

import { Container } from '@/components/Container'

export function CISOBanner() {
    return (
        <section className="bg-gray-900 border-b border-gray-800">
            <Container className="py-3">
                <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-2 text-sm">
                    <div className="flex items-center gap-2">
                        <span className="text-gray-500 text-xs uppercase tracking-wide">Powered by</span>
                        <span className="text-cyan-400 font-medium">RLM</span>
                        <span className="text-gray-600">·</span>
                        <span className="text-gray-400 text-xs">MIT Research</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                        <span className="text-gray-500">Integrates with:</span>
                        {['Zapier', 'n8n', 'Make', 'Any Webhook'].map((platform) => (
                            <span key={platform} className="text-gray-400 font-medium">
                                {platform}
                            </span>
                        ))}
                    </div>
                </div>
            </Container>
        </section>
    )
}
