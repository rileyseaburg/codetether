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

function XIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

export default function SecurityWhitepaper() {
    return (
        <main className="bg-white dark:bg-gray-950">
            {/* Hero */}
            <section className="relative overflow-hidden bg-gradient-to-b from-cyan-600 to-cyan-800 dark:from-cyan-700 dark:to-cyan-900 py-20 sm:py-32">
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
                <Container className="relative">
                    <div className="mx-auto max-w-3xl text-center">
                        <div className="flex justify-center mb-6">
                            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
                                <ShieldIcon className="h-8 w-8 text-white" />
                            </div>
                        </div>
                        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
                            Security Whitepaper
                        </h1>
                        <p className="mt-6 text-lg text-cyan-100">
                            Enterprise-grade security architecture for AI agent orchestration.
                            Zero inbound firewall rules. Data stays in your network.
                        </p>
                        <p className="mt-4 text-sm text-cyan-200">
                            Version 1.0 | December 2025
                        </p>
                    </div>
                </Container>
            </section>

            {/* Executive Summary */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Executive Summary
                        </h2>
                        <div className="mt-6 prose prose-lg dark:prose-invert">
                            <p className="text-gray-600 dark:text-gray-300">
                                CodeTether is an enterprise-grade AI agent orchestration platform designed with security as its foundational principle. Unlike traditional AI solutions that require data egress to cloud services, CodeTether employs a <strong className="text-cyan-600 dark:text-cyan-400">reverse-pull architecture</strong> where workers inside your network pull tasks from a central broker—eliminating inbound firewall rules and keeping sensitive data within your security perimeter.
                            </p>
                        </div>
                    </div>
                </Container>
            </section>

            {/* The Problem */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            The Security Challenge
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            Traditional AI integrations create unacceptable security risks for enterprises.
                        </p>

                        <div className="mt-10 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-100 dark:bg-gray-800">
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Risk Factor</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Traditional AI</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                    <tr>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">Data egress to cloud</td>
                                        <td className="px-6 py-4"><XIcon className="h-5 w-5 text-red-500" /><span className="sr-only">Required</span></td>
                                        <td className="px-6 py-4"><CheckIcon className="h-5 w-5 text-emerald-500" /><span className="sr-only">Optional</span></td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">Inbound firewall rules</td>
                                        <td className="px-6 py-4"><XIcon className="h-5 w-5 text-red-500" /></td>
                                        <td className="px-6 py-4"><CheckIcon className="h-5 w-5 text-emerald-500" /></td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">Code exposure to vendors</td>
                                        <td className="px-6 py-4"><XIcon className="h-5 w-5 text-red-500" /></td>
                                        <td className="px-6 py-4"><CheckIcon className="h-5 w-5 text-emerald-500" /></td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-white">Audit trail control</td>
                                        <td className="px-6 py-4"><XIcon className="h-5 w-5 text-red-500" /></td>
                                        <td className="px-6 py-4"><CheckIcon className="h-5 w-5 text-emerald-500" /></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Zero Inbound Access */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Zero Inbound Access Model
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            CodeTether inverts the traditional client-server model. Workers inside your network initiate all connections.
                        </p>

                        <div className="mt-10 rounded-2xl bg-gray-900 p-6 sm:p-8">
                            <div className="space-y-8">
                                {/* Traditional Model */}
                                <div>
                                    <div className="flex items-center gap-2 mb-4">
                                        <XIcon className="h-5 w-5 text-red-500" />
                                        <span className="text-red-400 font-semibold">Traditional Model (BLOCKED)</span>
                                    </div>
                                    <div className="flex items-center justify-center gap-4 text-gray-400">
                                        <div className="rounded-lg bg-gray-800 px-4 py-2 text-center">
                                            <div className="text-sm font-medium text-gray-300">AI Service</div>
                                            <div className="text-xs text-gray-500">(External)</div>
                                        </div>
                                        <div className="flex flex-col items-center">
                                            <span className="text-xs text-red-400 mb-1">INBOUND</span>
                                            <svg className="h-6 w-16 text-red-500" fill="none" viewBox="0 0 64 24">
                                                <path stroke="currentColor" strokeWidth="2" d="M0 12h54m0 0l-8-8m8 8l-8 8" />
                                            </svg>
                                            <span className="text-xs text-red-400 mt-1">firewall rule</span>
                                        </div>
                                        <div className="rounded-lg bg-gray-800 px-4 py-2 text-center">
                                            <div className="text-sm font-medium text-gray-300">Your Network</div>
                                        </div>
                                    </div>
                                </div>

                                <hr className="border-gray-700" />

                                {/* CodeTether Model */}
                                <div>
                                    <div className="flex items-center gap-2 mb-4">
                                        <CheckIcon className="h-5 w-5 text-emerald-500" />
                                        <span className="text-emerald-400 font-semibold">CodeTether Model (APPROVED)</span>
                                    </div>
                                    <div className="flex items-center justify-center gap-4 text-gray-400">
                                        <div className="rounded-lg bg-cyan-900/30 border border-cyan-500/30 px-4 py-2 text-center">
                                            <div className="text-sm font-medium text-cyan-300">CodeTether</div>
                                            <div className="text-xs text-cyan-500">Broker</div>
                                        </div>
                                        <div className="flex flex-col items-center">
                                            <span className="text-xs text-emerald-400 mb-1">OUTBOUND</span>
                                            <svg className="h-6 w-16 text-emerald-500" fill="none" viewBox="0 0 64 24">
                                                <path stroke="currentColor" strokeWidth="2" d="M64 12H10m0 0l8-8m-8 8l8 8" />
                                            </svg>
                                            <span className="text-xs text-emerald-400 mt-1">worker pulls</span>
                                        </div>
                                        <div className="rounded-lg bg-cyan-900/30 border border-cyan-500/30 px-4 py-2 text-center">
                                            <div className="text-sm font-medium text-cyan-300">Your Network</div>
                                            <div className="text-xs text-cyan-500">(Workers)</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="mt-8 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 p-6">
                            <h3 className="font-semibold text-emerald-800 dark:text-emerald-300">Firewall Configuration</h3>
                            <p className="mt-2 text-emerald-700 dark:text-emerald-400">
                                <strong>Required inbound firewall rules: ZERO</strong>
                            </p>
                            <p className="mt-1 text-sm text-emerald-600 dark:text-emerald-500">
                                Only outbound HTTPS (port 443) to the broker is required—the same traffic pattern as browsing the web.
                            </p>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Data Residency */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Data Residency & Sovereignty
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            Your code and secrets never leave your network.
                        </p>

                        <div className="mt-10 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-100 dark:bg-gray-800">
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Data Type</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Leaves Network?</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Notes</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                    <tr>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">Source code</td>
                                        <td className="px-6 py-4 text-sm text-emerald-600 dark:text-emerald-400 font-semibold">Never</td>
                                        <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">Stays in your VPC</td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">Credentials/secrets</td>
                                        <td className="px-6 py-4 text-sm text-emerald-600 dark:text-emerald-400 font-semibold">Never</td>
                                        <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">Worker uses local vault</td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">Task metadata</td>
                                        <td className="px-6 py-4 text-sm text-yellow-600 dark:text-yellow-400">Minimal</td>
                                        <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">Task ID, status, timing</td>
                                    </tr>
                                    <tr>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">Results/outputs</td>
                                        <td className="px-6 py-4 text-sm text-yellow-600 dark:text-yellow-400">Configurable</td>
                                        <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">PR links, summaries</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Authentication */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Authentication & Authorization
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            Enterprise-grade authentication with multiple options.
                        </p>

                        <div className="mt-10 grid gap-6 sm:grid-cols-2">
                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white">API Token Authentication</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Simple bearer tokens for service-to-service communication.
                                </p>
                            </div>
                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white">Keycloak OIDC</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Enterprise SSO with full OIDC support, MFA, and RBAC.
                                </p>
                            </div>
                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white">mTLS (Mutual TLS)</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Certificate-based authentication for zero-trust environments.
                                </p>
                            </div>
                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white">Role-Based Access</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Admin, Developer, Viewer, and Worker roles with granular permissions.
                                </p>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Compliance */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Compliance Frameworks
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            CodeTether supports the compliance requirements of regulated industries.
                        </p>

                        <div className="mt-10 grid gap-6 sm:grid-cols-2">
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                                        <span className="text-xl">🏥</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">HIPAA</h3>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    PHI stays in your VPC. BAA available for enterprise customers.
                                </p>
                            </div>
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30">
                                        <span className="text-xl">🔒</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">SOC 2 Type II</h3>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Our hosted broker maintains SOC 2 Type II certification.
                                </p>
                            </div>
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/30">
                                        <span className="text-xl">💳</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">PCI-DSS</h3>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Cardholder data never leaves your network. Full network segmentation support.
                                </p>
                            </div>
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/30">
                                        <span className="text-xl">🏛️</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">FedRAMP</h3>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Self-hosted deployment supports FedRAMP requirements. Air-gap compatible.
                                </p>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Key Takeaways */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            Key Takeaways
                        </h2>

                        <div className="mt-10 space-y-4">
                            {[
                                'Zero inbound firewall rules — Workers initiate all connections',
                                'Data stays local — Code and secrets never leave your network',
                                'Enterprise authentication — Keycloak, mTLS, and API tokens',
                                'Compliance-ready — HIPAA, SOC 2, PCI-DSS architectures',
                                'Flexible deployment — SaaS, self-hosted, or hybrid',
                            ].map((item, index) => (
                                <div key={index} className="flex items-start gap-3">
                                    <CheckIcon className="h-6 w-6 text-cyan-500 flex-shrink-0 mt-0.5" />
                                    <p className="text-lg text-gray-700 dark:text-gray-300">{item}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </Container>
            </section>

            {/* CTA */}
            <section className="py-16 sm:py-24 bg-gradient-to-r from-cyan-600 to-cyan-800 dark:from-cyan-700 dark:to-cyan-900">
                <Container>
                    <div className="mx-auto max-w-2xl text-center">
                        <h2 className="text-3xl font-bold tracking-tight text-white">
                            Ready to Secure Your AI Workflows?
                        </h2>
                        <p className="mt-4 text-lg text-cyan-100">
                            Get started with a security architecture review or pilot deployment.
                        </p>
                        <div className="mt-8 flex flex-wrap justify-center gap-4">
                            <Button href="/#contact" className="bg-white text-cyan-700 hover:bg-cyan-50">
                                Request Security Review
                            </Button>
                            <Button href="/security-whitepaper.md" variant="outline" className="border-white/50 text-white hover:bg-white/10">
                                Download PDF
                            </Button>
                        </div>
                    </div>
                </Container>
            </section>
        </main>
    )
}
