'use client'

import { Container } from '@/components/Container'

export function CISOBanner() {
    return (
        <section className="bg-gray-900 border-b border-gray-800">
            <Container className="py-3">
                <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-2 text-sm">
                    <div className="flex items-center gap-4">
                        {['Open Source', 'Written in Rust', 'Self-Hosted', 'Auth Mandatory'].map((item, i) => (
                            <span key={item} className="flex items-center gap-2">
                                {i > 0 && <span className="text-gray-700">·</span>}
                                <span className="text-gray-400 text-xs font-medium">{item}</span>
                            </span>
                        ))}
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-gray-500 text-xs">MIT License</span>
                        <span className="text-gray-700">·</span>
                        <span className="text-cyan-400 text-xs font-medium">Free to self-host</span>
                    </div>
                </div>
            </Container>
        </section>
    )
}
