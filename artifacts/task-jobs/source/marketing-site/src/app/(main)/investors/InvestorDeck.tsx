'use client'

import type React from 'react'

import { useEffect, useMemo, useRef, useState } from 'react'

import clsx from 'clsx'

import { Button } from '@/components/Button'
import { Container } from '@/components/Container'

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" {...props}>
            <path
                fillRule="evenodd"
                d="M16.704 5.292a1 1 0 010 1.416l-8 8a1 1 0 01-1.415 0l-4-4a1 1 0 111.414-1.416l3.293 3.293 7.293-7.293a1 1 0 011.415 0z"
                clipRule="evenodd"
            />
        </svg>
    )
}

function BoltIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
    )
}

function clamp(value: number, min: number, max: number) {
    return Math.min(max, Math.max(min, value))
}

type DeckSlide = {
    title: string
    subtitle?: React.ReactNode
    body: React.ReactNode
}

function BulletList({ items }: { items: React.ReactNode[] }) {
    return (
        <ul className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
            {items.map((item, index) => (
                <li key={index} className="flex gap-3">
                    <CheckIcon className="h-5 w-5 flex-none text-cyan-700 dark:text-cyan-300" />
                    <span className="min-w-0 break-words">{item}</span>
                </li>
            ))}
        </ul>
    )
}

function Slide({
    number,
    title,
    subtitle,
    children,
}: {
    number: string
    title: string
    subtitle?: React.ReactNode
    children: React.ReactNode
}) {
    return (
        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 sm:p-10">
            <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        Slide {number}
                    </p>
                    <h2 className="mt-2 text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
                        {title}
                    </h2>
                    {subtitle ? (
                        <p className="mt-3 text-sm leading-relaxed text-gray-700 dark:text-gray-300 break-words">
                            {subtitle}
                        </p>
                    ) : null}
                </div>
                <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-cyan-100 dark:bg-cyan-900/30">
                    <BoltIcon className="h-5 w-5 text-cyan-700 dark:text-cyan-300" />
                </div>
            </div>
            <div className="mt-6 min-w-0">{children}</div>
        </div>
    )
}

function parseHashSlideNumber(hash: string) {
    const trimmed = hash.replace(/^#/, '').trim()
    if (!trimmed) return null

    const slideMatch = trimmed.match(/^slide-(\d+)$/i)
    if (slideMatch) return Number(slideMatch[1])

    const plainMatch = trimmed.match(/^(\d+)$/)
    if (plainMatch) return Number(plainMatch[1])

    return null
}

export function InvestorDeck() {
    const deckRef = useRef<HTMLDivElement | null>(null)
    const [slideIndex, setSlideIndex] = useState(0)
    const [showOverview, setShowOverview] = useState(false)
    const [isFullscreen, setIsFullscreen] = useState(false)

    const slides: DeckSlide[] = useMemo(
        () => [
            {
                title: 'CodeTether',
                subtitle: (
                    <>
                        <span className="font-semibold text-gray-900 dark:text-white">The control plane for autonomous execution.</span>{' '}
                        The next wave of enterprise AI is agents doing real work. They need governance.
                    </>
                ),
                body: (
                    <div className="space-y-6">
                        <div className="space-y-4">
                            <p className="text-base leading-relaxed text-gray-700 dark:text-gray-300">
                                You&apos;ve seen this movie before: a new class of compute shows up, teams ship it with duct tape, and then one day it becomes a board-level control problem.
                                We did it for CI/CD, cloud access, and containers. Agents are next.
                            </p>
                            <p className="text-base leading-relaxed text-gray-700 dark:text-gray-300">
                                The question won&apos;t be “are agents useful?” The question will be: <span className="font-semibold text-gray-900 dark:text-white">can we prove control when an agent executes inside the perimeter?</span>
                            </p>
                        </div>

                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                One sentence
                            </p>
                            <p className="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                                CodeTether is a self-hostable agent runtime that makes autonomous execution governable with identity, least privilege, audit trails, and approval gates—
                                while keeping work inside the customer&apos;s network via outbound-only workers.
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-3">
                            <span className="rounded-full bg-gray-100 dark:bg-gray-950 px-4 py-2 text-sm text-gray-800 dark:text-gray-200 ring-1 ring-gray-200 dark:ring-gray-800">
                                Outbound-only workers (pull model)
                            </span>
                            <span className="rounded-full bg-gray-100 dark:bg-gray-950 px-4 py-2 text-sm text-gray-800 dark:text-gray-200 ring-1 ring-gray-200 dark:ring-gray-800">
                                OIDC/SSO integration
                            </span>
                            <span className="rounded-full bg-gray-100 dark:bg-gray-950 px-4 py-2 text-sm text-gray-800 dark:text-gray-200 ring-1 ring-gray-200 dark:ring-gray-800">
                                Kubernetes-native deploy
                            </span>
                            <span className="rounded-full bg-gray-100 dark:bg-gray-950 px-4 py-2 text-sm text-gray-800 dark:text-gray-200 ring-1 ring-gray-200 dark:ring-gray-800">
                                Open standards: A2A + MCP
                            </span>
                        </div>

                        <div className="flex flex-wrap gap-4">
                            <Button href="/#contact" color="cyan">
                                Request an Intro
                            </Button>
                            <Button href="/security-whitepaper" variant="outline" color="gray">
                                Security Whitepaper
                            </Button>
                            <Button
                                href="https://github.com/rileyseaburg/codetether"
                                variant="outline"
                                color="gray"
                                target="_blank"
                                rel="noreferrer"
                            >
                                GitHub
                            </Button>
                        </div>
                    </div>
                ),
            },
            {
                title: 'The Incident',
                subtitle:
                    'The risk isn’t that agents make mistakes. It’s that you can’t prove who authorized what ran, what it touched, and how it was contained.',
                body: (
                    <div className="space-y-6">
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/60 dark:bg-gray-950/30 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                A story you can picture
                            </p>
                            <ul className="mt-4 space-y-3 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                                <li className="flex gap-3">
                                    <span className="font-mono text-xs tabular-nums text-gray-500 dark:text-gray-400 flex-none">02:17</span>
                                    <span className="min-w-0 break-words">
                                        An agent is allowed to “help” with an ops task. It runs with a shared service account.
                                    </span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="font-mono text-xs tabular-nums text-gray-500 dark:text-gray-400 flex-none">02:19</span>
                                    <span className="min-w-0 break-words">
                                        It changes an IAM role / security group / firewall rule. Production degrades.
                                    </span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="font-mono text-xs tabular-nums text-gray-500 dark:text-gray-400 flex-none">09:06</span>
                                    <span className="min-w-0 break-words">
                                        In the postmortem, the question isn&apos;t “why did the model do that?” It&apos;s “who approved it—and where is the evidence?”
                                    </span>
                                </li>
                            </ul>
                        </div>

                        <BulletList
                            items={[
                                'Autonomous execution is not a human user and it is not CI/CD—existing IAM and change management controls don’t fit.',
                                'Tool access typically means shared credentials and over-broad service accounts.',
                                'Security teams can’t answer: who/what ran, what it touched, and whether it was authorized.',
                                'Most agent deployments don’t match enterprise network realities (no inbound ports, no SaaS data egress, no VPN exceptions).',
                                'DIY becomes a hidden platform project: queues, retries, state, audit evidence, and approvals become permanent on-call debt.',
                            ]}
                        />
                    </div>
                ),
            },
            {
                title: 'The missing control plane',
                subtitle:
                    'Agents are a new class of privileged actor. They need identity, policy, auditability, and a “stop button” as first-class primitives.',
                body: (
                    <BulletList
                        items={[
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Owned risk:</span> “an agent did it” is not an acceptable control story to a CISO, CIO, or regulator.
                            </>,
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Governance gap:</span> humans have IAM, services have CI/CD, agents have… nothing standard.
                            </>,
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Evidence gap:</span> without immutable execution records, you can&apos;t prove control (or negligence).
                            </>,
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Operational gap:</span> long-running agent work needs queues, retries, state, and visibility—or it becomes permanent on-call debt.
                            </>,
                        ]}
                    />
                ),
            },
            {
                title: 'Solution',
                subtitle:
                    'Govern execution where it runs: inside the perimeter. Make every action attributable, reviewable, and auditable.',
                body: (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-950/30 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                Deploy inside the customer network
                            </p>
                            <p className="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                                Workers run behind the firewall and <span className="font-medium text-gray-900 dark:text-white">pull</span> tasks outward. No inbound ports. No VPN exceptions. Data stays in-place.
                            </p>
                            <div className="mt-4">
                                <BulletList
                                    items={[
                                        'Outbound-only workers (pull model) for regulated environments',
                                        'OIDC/SSO-ready identity path (Keycloak-ready)',
                                        'Operational primitives: queues, retries, streaming output, session history',
                                    ]}
                                />
                            </div>
                        </div>

                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                Make execution governable
                            </p>
                            <p className="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                                The runtime becomes the system of record: what ran, why it ran, what it touched, and who approved it.
                            </p>
                            <div className="mt-4">
                                <BulletList
                                    items={[
                                        'Per-agent identity + least privilege (RBAC / API tokens)',
                                        'Audit trail you can export and retain for evidence',
                                        'Policy + approval gates for sensitive tool calls',
                                        'Centralized containment: stop/disable execution paths quickly',
                                    ]}
                                />
                            </div>
                        </div>
                    </div>
                ),
            },
            {
                title: 'Why now',
                subtitle:
                    'We&apos;re crossing the line: from copilots to autonomous systems with permissions. Security/compliance becomes the bottleneck—and the control plane becomes the platform.',
                body: (
                    <BulletList
                        items={[
                            'Every enterprise is experimenting with agents. The first production incident will create the category.',
                            'The buying center already exists: platform engineering + security/compliance (budgeted, accountable).',
                            'The transition happens fast once a new control surface is visible (think: CI/CD, cloud IAM, zero trust).',
                            'The first standard governance layer becomes the default system of record for agent execution.',
                        ]}
                    />
                ),
            },
            {
                title: 'Proof',
                subtitle:
                    'Infrastructure is hard to fake. Here&apos;s what exists today and what we ship next.',
                body: (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-950/30 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                Built today
                            </p>
                            <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-300">
                                {[
                                    'A2A protocol server + agent runtime',
                                    'Redis task queues + streaming output (SSE)',
                                    'Session history + resumption API',
                                    'MCP client integration',
                                    'Keycloak OIDC integration',
                                    'Kubernetes Helm chart + blue/green deploy path',
                                ].map((item) => (
                                    <li key={item} className="flex gap-3">
                                        <CheckIcon className="h-5 w-5 flex-none text-cyan-700 dark:text-cyan-300" />
                                        <span className="min-w-0 break-words">{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                What we ship next
                            </p>
                            <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-300">
                                {[
                                    'Fine-grained RBAC + API tokens',
                                    'Audit export + retention controls',
                                    'Policy engine + approval gates for tool calls',
                                    'Secrets integrations (Vault/SSM/AKV)',
                                    'OpenTelemetry metrics + traces',
                                ].map((item) => (
                                    <li key={item} className="flex gap-3">
                                        <CheckIcon className="h-5 w-5 flex-none text-cyan-700 dark:text-cyan-300" />
                                        <span className="min-w-0 break-words">{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                ),
            },
            {
                title: 'Why we win',
                subtitle:
                    'We win by being enterprise-first in deployment and standards-first in integration—then becoming the system of record for execution.',
                body: (
                    <BulletList
                        items={[
                            'Private-network native: pull workers + in-perimeter execution is the deployment wedge.',
                            'Standards-based (A2A + MCP): integrate broadly, avoid lock-in fear, ride the ecosystem.',
                            'Governance becomes the product: identity, auditability, approvals, and policy are durable.',
                            'Once the runtime holds the evidence trail, it becomes infrastructure you don’t rip out.',
                        ]}
                    />
                ),
            },
            {
                title: 'Business + GTM',
                subtitle:
                    'Land with developers via open source. Expand to security via compliance controls. Monetize via Pro and Enterprise.',
                body: (
                    <div className="grid gap-6 lg:grid-cols-2">
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">How we sell</p>
                            <BulletList
                                items={[
                                    'Start with builders: ship a runtime that works in real networks.',
                                    'Make the decision legible to security: SOC2/ISO/NIST control mapping + audit exports.',
                                    'Convert through regulated design partners (VPC/on-prem) who are blocked today.',
                                ]}
                            />
                        </div>
                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">How we monetize</p>
                            <BulletList
                                items={[
                                    'Open Source: adoption + integration surface area.',
                                    'Pro (Managed): hosted control plane + upgrades/support for production teams.',
                                    'Enterprise: VPC/on-prem, SSO, policy/approvals, audit retention, and compliance workflows.',
                                ]}
                            />
                        </div>
                    </div>
                ),
            },
            {
                title: 'The market',
                subtitle:
                    'Every enterprise deploying agents is in this market. We start where security is non-negotiable and budgets are real.',
                body: (
                    <BulletList
                        items={[
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Wedge:</span> regulated + high-trust environments where agent deployment is blocked today.
                            </>,
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Buyers:</span> platform engineering + security/compliance (accountable owners, existing budgets).
                            </>,
                            <>
                                <span className="font-medium text-gray-900 dark:text-white">Expansion:</span> once agents become standard, governance becomes table stakes like CI/CD and IAM.
                            </>,
                        ]}
                    />
                ),
            },
            {
                title: 'Next 3 months',
                subtitle:
                    'A de-risking sprint: ship GA governance v1 and turn design partner deployments into repeatable pilots.',
                body: (
                    <div className="grid gap-6 md:grid-cols-3">
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">Month 1</p>
                            <BulletList
                                items={[
                                    'Per-agent tokens + RBAC baseline',
                                    'Audit export v1 (evidence-ready)',
                                    'Reference deployment playbook (K8s + SSO)',
                                ]}
                            />
                        </div>
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">Month 2</p>
                            <BulletList
                                items={[
                                    'Approval gates for high-risk tool calls',
                                    'Secrets integrations (Vault/SSM/AKV)',
                                    'OTel traces/metrics for production ops',
                                ]}
                            />
                        </div>
                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">Month 3</p>
                            <BulletList
                                items={[
                                    'Enterprise packaging (VPC/on-prem path)',
                                    'Pro MVP packaging (managed control plane)',
                                    'Design partner deployments → paid pilots',
                                ]}
                            />
                        </div>
                    </div>
                ),
            },
            {
                title: 'The Ask',
                subtitle:
                    'Raising a Seed round to own the control plane category for autonomous execution.',
                body: (
                    <div className="space-y-6">
                        <div className="rounded-2xl border border-cyan-200 dark:border-cyan-900/40 bg-cyan-50 dark:bg-cyan-950/20 p-5">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                Raising: <span className="font-bold">$3M Seed</span>
                            </p>
                            <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                                Goal: in <span className="font-semibold text-gray-900 dark:text-white">3 months</span>, ship GA governance v1 and prove repeatable, in-perimeter deployments that convert to paid pilots.
                            </p>
                        </div>

                        <div className="grid gap-6 lg:grid-cols-2">
                            <div className="min-w-0">
                                <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                    What this unlocks
                                </p>
                                <BulletList
                                    items={[
                                        'GA governance v1: per-agent RBAC + API tokens, audit export/retention, policy/approval gates.',
                                        'Enterprise packaging: VPC/on-prem deployment patterns, SSO, compliance workflows.',
                                        'Pro MVP: managed control plane with upgrades/support for production teams.',
                                        'A design partner motion that turns “blocked” deployments into paid pilots.',
                                    ]}
                                />
                            </div>
                            <div className="min-w-0">
                                <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                    What we need besides capital
                                </p>
                                <BulletList
                                    items={[
                                        'Introductions to CISOs / platform security leaders adopting agents.',
                                        'Design partners willing to deploy inside their perimeter (VPC/on-prem).',
                                        'Feedback on enterprise procurement + compliance review patterns.',
                                    ]}
                                />
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-4">
                            <Button href="/#contact" color="cyan">
                                Request a Meeting
                            </Button>
                            <Button href="/security-whitepaper" variant="outline" color="gray">
                                Security Whitepaper
                            </Button>
                            <Button
                                href="https://github.com/rileyseaburg/codetether"
                                variant="outline"
                                color="gray"
                                target="_blank"
                                rel="noreferrer"
                            >
                                GitHub
                            </Button>
                        </div>
                    </div>
                ),
            },
        ],
        [],
    )

    const slideCount = slides.length

    const goTo = (index: number) => {
        setSlideIndex(clamp(index, 0, slideCount - 1))
    }

    const next = () => goTo(slideIndex + 1)
    const prev = () => goTo(slideIndex - 1)

    const toggleFullscreen = async () => {
        const element = deckRef.current
        if (!element) return

        if (document.fullscreenElement) {
            await document.exitFullscreen()
            return
        }

        await element.requestFullscreen()
    }

    useEffect(() => {
        const slideFromHash = parseHashSlideNumber(window.location.hash)
        if (!slideFromHash) return
        setSlideIndex(clamp(slideFromHash - 1, 0, slideCount - 1))
    }, [slideCount])

    useEffect(() => {
        if (showOverview) return
        const slideNumber = slideIndex + 1
        const url = new URL(window.location.href)
        url.hash = `slide-${slideNumber}`
        window.history.replaceState(window.history.state, '', url.toString())
    }, [slideIndex, showOverview])

    useEffect(() => {
        const onFullscreenChange = () => {
            setIsFullscreen(document.fullscreenElement === deckRef.current)
        }
        document.addEventListener('fullscreenchange', onFullscreenChange)
        return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
    }, [])

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const target = event.target as HTMLElement | null
            const tag = target?.tagName?.toLowerCase()
            if (tag === 'input' || tag === 'textarea' || (target && target.isContentEditable)) return

            if (event.key === 'o' || event.key === 'O') {
                event.preventDefault()
                setShowOverview((value) => !value)
                return
            }

            if (event.key === 'f' || event.key === 'F') {
                event.preventDefault()
                void toggleFullscreen()
                return
            }

            if (showOverview) {
                if (event.key === 'Escape') {
                    event.preventDefault()
                    setShowOverview(false)
                }
                return
            }

            switch (event.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                case 'PageDown':
                case ' ':
                    event.preventDefault()
                    next()
                    break
                case 'ArrowLeft':
                case 'ArrowUp':
                case 'PageUp':
                    event.preventDefault()
                    prev()
                    break
                case 'Home':
                    event.preventDefault()
                    goTo(0)
                    break
                case 'End':
                    event.preventDefault()
                    goTo(slideCount - 1)
                    break
                default:
                    break
            }
        }

        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [showOverview, slideIndex, slideCount])

    const currentSlide = slides[slideIndex]
    const progressPercent = Math.round(((slideIndex + 1) / slideCount) * 100)

    return (
        <div
            ref={deckRef}
            className={clsx(
                'bg-white dark:bg-gray-950',
                isFullscreen ? 'min-h-screen' : 'py-12 sm:py-16',
            )}
        >
            <Container>
                <div className="mx-auto max-w-5xl">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="min-w-0">
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                                Investor Deck
                            </p>
                            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 break-words">
                                CodeTether • {slideIndex + 1}/{slideCount} • {currentSlide.title}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                variant="outline"
                                color="gray"
                                onClick={() => setShowOverview((value) => !value)}
                            >
                                {showOverview ? 'Close overview (O)' : 'Overview (O)'}
                            </Button>
                            <Button
                                variant="outline"
                                color="gray"
                                onClick={() => void toggleFullscreen()}
                            >
                                {isFullscreen ? 'Exit full screen (F)' : 'Full screen (F)'}
                            </Button>
                        </div>
                    </div>

                    <div className="mt-6">
                        {showOverview ? (
                            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                {slides.map((slide, index) => (
                                    <button
                                        key={`${index}-${slide.title}`}
                                        type="button"
                                        onClick={() => {
                                            setShowOverview(false)
                                            goTo(index)
                                        }}
                                        className={clsx(
                                            'rounded-2xl border p-4 text-left transition-colors',
                                            index === slideIndex
                                                ? 'border-cyan-300 bg-cyan-50 dark:border-cyan-900/60 dark:bg-cyan-950/20'
                                                : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:hover:bg-gray-800',
                                        )}
                                    >
                                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                            Slide {index + 1}
                                        </p>
                                        <p className="mt-2 font-semibold text-gray-900 dark:text-white">
                                            {slide.title}
                                        </p>
                                        {slide.subtitle ? (
                                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 break-words">
                                                {slide.subtitle}
                                            </p>
                                        ) : null}
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <div className="min-h-[60vh]">
                                <Slide number={`${slideIndex + 1}`} title={currentSlide.title} subtitle={currentSlide.subtitle}>
                                    {currentSlide.body}
                                </Slide>
                            </div>
                        )}
                    </div>

                    <div className="mt-6 flex items-center justify-between gap-4">
                        <Button
                            variant="outline"
                            color="gray"
                            onClick={prev}
                            disabled={showOverview || slideIndex === 0}
                            className="disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            ← Prev
                        </Button>

                        <div className="text-sm text-gray-600 dark:text-gray-400 tabular-nums">
                            {progressPercent}%
                        </div>

                        <Button
                            color="cyan"
                            onClick={next}
                            disabled={showOverview || slideIndex === slideCount - 1}
                            className="disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            Next →
                        </Button>
                    </div>

                    <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800">
                        <div
                            className="h-full bg-cyan-600 dark:bg-cyan-400 transition-[width] duration-300"
                            style={{ width: `${progressPercent}%` }}
                        />
                    </div>

                    <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                        Controls: ←/→ (or Space) to navigate • O overview • F full screen • URL supports `#slide-3`
                    </p>
                </div>
            </Container>
        </div>
    )
}
