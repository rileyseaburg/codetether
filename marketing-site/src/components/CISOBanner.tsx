'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    )
}

export function CISOBanner() {
    return (
        <section className="relative overflow-hidden bg-gradient-to-r from-cyan-600 via-cyan-700 to-cyan-800 dark:from-cyan-700 dark:via-cyan-800 dark:to-cyan-900">
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-10">
                <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                    <defs>
                        <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" strokeWidth="0.5" />
                        </pattern>
                    </defs>
                    <rect width="100" height="100" fill="url(#grid)" />
                </svg>
            </div>

            <Container className="relative py-8 sm:py-12">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
                    {/* Left side - Main message */}
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/20 backdrop-blur">
                                <ShieldIcon className="h-6 w-6 text-white" />
                            </div>
                            <span className="inline-flex items-center rounded-full bg-white/20 px-3 py-1 text-sm font-semibold text-white backdrop-blur">
                                For CISOs & Security Teams
                            </span>
                        </div>
                        <h2 className="text-2xl sm:text-3xl font-bold text-white">
                            Control Plane for Autonomous Execution
                        </h2>
                        <p className="mt-3 text-lg text-cyan-100 max-w-2xl">
                            AI agents are starting to execute real work. CodeTether makes that legible and governable:
                            <span className="font-semibold text-white"> identity, authorization, audit logging, and approval</span>,
                            while workers still <span className="font-semibold text-white">PULL tasks from inside your network</span>
                            (no inbound ports, no VPNs).
                        </p>
                    </div>

                    {/* Right side - Key benefits */}
                    <div className="flex flex-col sm:flex-row lg:flex-col gap-4 lg:min-w-[280px]">
                        <div className="flex items-start gap-3 rounded-xl bg-white/10 backdrop-blur p-4">
                            <CheckIcon className="h-5 w-5 text-emerald-300 mt-0.5 flex-shrink-0" />
                            <div>
                                <p className="font-semibold text-white">Per-Agent Identity + RBAC</p>
                                <p className="text-sm text-cyan-200">No shared credentials, scoped access</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 rounded-xl bg-white/10 backdrop-blur p-4">
                            <CheckIcon className="h-5 w-5 text-emerald-300 mt-0.5 flex-shrink-0" />
                            <div>
                                <p className="font-semibold text-white">Audit Trail + Data Residency</p>
                                <p className="text-sm text-cyan-200">Auditability without proxying payloads</p>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 rounded-xl bg-white/10 backdrop-blur p-4">
                            <CheckIcon className="h-5 w-5 text-emerald-300 mt-0.5 flex-shrink-0" />
                            <div>
                                <p className="font-semibold text-white">Outbound-Only Workers</p>
                                <p className="text-sm text-cyan-200">No inbound ports; no VPN approvals</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* CTA */}
                <div className="mt-8 flex flex-wrap gap-4">
                    <Button
                        href="#features"
                        className="!bg-white !text-cyan-700 hover:!bg-cyan-50 !border-transparent"
                    >
                        See How It Works
                    </Button>
                    <Button
                        href="/security-whitepaper"
                        variant="outline"
                        className="!border-white/50 !text-white hover:!bg-white/10"
                    >
                        Security Whitepaper
                    </Button>
                </div>
            </Container>
        </section>
    )
}
