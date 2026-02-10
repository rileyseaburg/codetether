'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
    )
}

function ServerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 00-.12-1.03l-2.268-9.64a3.375 3.375 0 00-3.285-2.602H7.923a3.375 3.375 0 00-3.285 2.602l-2.268 9.64a4.5 4.5 0 00-.12 1.03v.228m19.5 0a3 3 0 01-3 3H5.25a3 3 0 01-3-3m19.5 0a3 3 0 00-3-3H5.25a3 3 0 00-3 3m16.5 0h.008v.008h-.008v-.008zm-3 0h.008v.008h-.008v-.008z" />
        </svg>
    )
}

function CogIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12a7.5 7.5 0 0015 0m-15 0a7.5 7.5 0 1115 0m-15 0H3m16.5 0H21m-1.5 0H12m-8.457 3.077l1.41-.513m14.095-5.13l1.41-.513M5.106 17.785l1.15-.964m11.49-9.642l1.149-.964M7.501 19.795l.75-1.3m7.5-12.99l.75-1.3m-6.063 16.658l.26-1.477m2.605-14.772l.26-1.477m0 17.726l-.26-1.477M10.698 4.614l-.26-1.477M16.5 19.794l-.75-1.299M7.5 4.205L12 12m6.894 5.785l-1.149-.964M6.256 7.178l-1.15-.964m15.352 8.864l-1.41-.513M4.954 9.435l-1.41-.514M12.002 12l-3.75 6.495" />
        </svg>
    )
}

function LockIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
    )
}

function WarningIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
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

const comparisonRows = [
    { feature: 'Language', openclaw: 'Node.js', codetether: 'Rust (memory-safe)' },
    { feature: 'Auth default', openclaw: 'auth: none', codetether: 'Mandatory HMAC-SHA256 — cannot disable' },
    { feature: 'Plugin isolation', openclaw: 'None — shared process', codetether: 'Sandboxed + Ed25519 code-signed' },
    { feature: 'Audit trail', openclaw: 'None', codetether: 'Append-only JSON Lines — every action' },
    { feature: 'Cognition model', openclaw: 'Request/response', codetether: 'Perpetual thought loops' },
    { feature: 'Agent coordination', openclaw: 'Single bot', codetether: 'Persona swarms w/ scoped permissions' },
    { feature: 'Self-modification', openclaw: 'Not supported', codetether: 'Auditable gates + logged decisions' },
    { feature: 'Deployment', openclaw: 'Manual setup', codetether: 'Self-deploys on Kubernetes' },
]

export function OpenClawComparison() {
    return (
        <>
            {/* Section 1: The Hook */}
            <section className="relative overflow-hidden bg-gray-950 py-20 sm:py-28">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--tw-gradient-stops))] from-red-950/20 via-gray-950 to-gray-950" />
                <Container className="relative">
                    <div className="mx-auto max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full bg-red-950/50 border border-red-900/50 px-3 py-1 mb-6">
                            <WarningIcon className="h-4 w-4 text-red-400" />
                            <span className="text-xs font-medium text-red-400">Security Advisory</span>
                        </div>

                        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl leading-tight">
                            They Gave an AI Agent Root Access to Their Entire Digital Life — Then Shipped It with the Password Set to{' '}
                            <span className="text-red-400">&quot;None.&quot;</span>
                        </h2>
                        <p className="mt-4 text-lg text-gray-400">
                            And 145,000 developers starred it on GitHub.
                        </p>

                        <div className="mt-10 space-y-6 text-base leading-relaxed text-gray-300">
                            <p>
                                I&apos;m not going to pretend you haven&apos;t heard of OpenClaw. It&apos;s everywhere right now. Your Twitter feed. Your Discord servers. Your coworker&apos;s Slack status. &quot;The future of AI agents&quot; they&apos;re calling it.
                            </p>
                            <p>
                                And I&apos;ll give credit where it&apos;s due: Peter Steinberger proved the market. He showed the world that people want an AI agent that actually does things — not just another chatbot you talk to in a browser tab. That took vision. That took execution. And he shipped it at exactly the right moment.
                            </p>
                            <p className="text-white font-medium">
                                But here&apos;s what nobody in those breathless Twitter threads is talking about.
                            </p>
                        </div>

                        {/* The auth:none callout */}
                        <div className="mt-10 rounded-2xl bg-red-950/30 border border-red-900/50 p-6 sm:p-8">
                            <p className="text-lg text-white font-semibold mb-4">
                                The thing shipped with authentication disabled by default.
                            </p>
                            <div className="space-y-3 text-gray-300">
                                <p>
                                    Not &quot;weak authentication.&quot; Not &quot;basic auth.&quot; <span className="text-red-400 font-mono font-semibold">No authentication.</span> <code className="text-red-400 bg-red-950/50 px-2 py-0.5 rounded text-sm">auth: none</code>. The gateway — the thing that controls your email, your files, your shell, your entire digital life — was wide open on the public internet for anyone who found the port.
                                </p>
                                <p>
                                    When the project renamed itself from Clawdbot to Moltbot, crypto scammers hijacked the old Twitter handle and GitHub namespace in ten seconds flat. A malicious VS Code extension called &quot;ClawdBot Agent&quot; appeared on the marketplace the same day. People deployed it on DigitalOcean droplets with the port exposed and no auth, because that&apos;s what the YouTube tutorials told them to do.
                                </p>
                            </div>
                        </div>

                        <p className="mt-8 text-lg text-gray-300">
                            There is a difference between a <span className="text-gray-400">demo</span> and <span className="text-white font-semibold">infrastructure</span>. And the entire world just confused the two.
                        </p>
                    </div>
                </Container>
            </section>

            {/* Section 2: The 80% Problem */}
            <section className="bg-gray-900 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                            Here&apos;s My Problem With{' '}
                            <span className="text-gray-400">&quot;80% of Software Goes Away&quot;</span>
                        </h3>

                        <div className="mt-8 space-y-6 text-base leading-relaxed text-gray-300">
                            <p>
                                Steinberger said in an interview that he thinks 80% of software goes away and people don&apos;t really care where their data is stored.
                            </p>
                            <p>
                                That&apos;s the kind of thing that sounds profound on a podcast and falls apart the second you think about it for more than thirty seconds.
                            </p>
                            <p className="text-white">
                                Your company cares where its data is stored. Your customers care. Your users care. Anyone who&apos;s ever dealt with a breach, a leaked database, a compromised API key, or an angry email from a customer whose data ended up somewhere it shouldn&apos;t — <span className="font-semibold">they care</span>.
                            </p>
                            <p>
                                &quot;People don&apos;t care where their data is stored&quot; is the worldview of someone who&apos;s never been responsible for anyone&apos;s data but their own.
                            </p>
                        </div>

                        <div className="mt-8 rounded-xl bg-cyan-950/30 border border-cyan-900/50 p-6">
                            <p className="text-cyan-400 font-semibold text-lg">
                                And that&apos;s the gap I built CodeTether to fill.
                            </p>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Section 3: Engineered Like Infrastructure */}
            <section className="bg-gray-950 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                            What If Your AI Agent Was Engineered Like{' '}
                            <span className="text-cyan-400">the Systems It Operates On?</span>
                        </h3>

                        <div className="mt-8 space-y-6 text-base leading-relaxed text-gray-300">
                            <p>
                                Here&apos;s the thing nobody else in the &quot;AI agent&quot; space seems to understand:
                            </p>
                            <p className="text-xl text-white font-semibold">
                                An autonomous agent with system-level access IS infrastructure.
                            </p>
                            <p>
                                Full stop. It&apos;s not an app. It&apos;s not a productivity hack. It&apos;s not a weekend project you install from npm. It&apos;s a piece of software that can read your files, execute commands, make decisions, and take actions — on its own, without asking you first.
                            </p>
                            <p className="text-white">
                                That means it needs to be built like infrastructure.
                            </p>
                        </div>

                        <div className="mt-12 grid gap-6 sm:grid-cols-3">
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center mb-4">
                                    <CogIcon className="h-5 w-5 text-cyan-400" />
                                </div>
                                <h4 className="text-lg font-semibold text-white mb-2">Written in Rust</h4>
                                <p className="text-sm text-gray-400">
                                    Not Node.js, not Python. When your agent has elevated privileges on your system, memory safety isn&apos;t a nice-to-have. It&apos;s the bare minimum. You wouldn&apos;t write a database in JavaScript. You shouldn&apos;t write an autonomous agent in it either.
                                </p>
                            </div>

                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center mb-4">
                                    <ServerIcon className="h-5 w-5 text-cyan-400" />
                                </div>
                                <h4 className="text-lg font-semibold text-white mb-2">Self-Deploys on K8s</h4>
                                <p className="text-sm text-gray-400">
                                    CodeTether manages its own pods and recovers from failures automatically. Because if your &quot;AI assistant&quot; crashes and takes your workflow with it, you don&apos;t have an assistant — you have a liability.
                                </p>
                            </div>

                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center mb-4">
                                    <LockIcon className="h-5 w-5 text-cyan-400" />
                                </div>
                                <h4 className="text-lg font-semibold text-white mb-2">Auth Is Mandatory</h4>
                                <p className="text-sm text-gray-400">
                                    It&apos;s not a flag you set. You cannot turn it off. Because when you let developers opt out of security, they opt out. Every single time. And then they write a postmortem.
                                </p>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Section 4: Perpetual Cognition Runtime */}
            <section className="bg-gray-900 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                            This Is Not a Chatbot.{' '}
                            <span className="text-cyan-400">This Is a Perpetual Cognition Runtime.</span>
                        </h3>

                        <div className="mt-8 space-y-6 text-base leading-relaxed text-gray-300">
                            <p>
                                Most AI agents work like this: you send a message, they think, they respond. Request-response. Just like every chatbot since the 1960s, except now there&apos;s an LLM in the middle.
                            </p>
                            <p className="text-white font-medium">
                                CodeTether doesn&apos;t work like that.
                            </p>
                            <p>
                                CodeTether runs continuous thought loops that persist across restarts, survive node failures, and scale horizontally. Your agents aren&apos;t waiting for you to type something. They&apos;re reasoning. They&apos;re planning. They&apos;re acting. Right now, while you&apos;re reading this.
                            </p>
                        </div>

                        <div className="mt-12 space-y-6">
                            {/* Persona Swarms */}
                            <div className="rounded-2xl bg-gray-950 border border-gray-800 p-6 sm:p-8">
                                <div className="flex items-start gap-4">
                                    <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center shrink-0">
                                        <ShieldIcon className="h-5 w-5 text-cyan-400" />
                                    </div>
                                    <div>
                                        <h4 className="text-lg font-semibold text-white mb-2">Persona Swarms</h4>
                                        <p className="text-gray-300">
                                            You don&apos;t get one bot. You get a coordinated team. A monitoring persona that watches your systems. A deployment persona that manages your staging environment. A review persona that reads pull requests. Each with its own scoped permissions. Each in its own security boundary.
                                        </p>
                                        <p className="mt-3 text-cyan-400 font-medium text-sm">
                                            A compromised monitor can&apos;t escalate to deploy access. That&apos;s not paranoia — that&apos;s basic engineering.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Self-Modification */}
                            <div className="rounded-2xl bg-gray-950 border border-gray-800 p-6 sm:p-8">
                                <div className="flex items-start gap-4">
                                    <div className="h-10 w-10 rounded-lg bg-cyan-500/10 flex items-center justify-center shrink-0">
                                        <CogIcon className="h-5 w-5 text-cyan-400" />
                                    </div>
                                    <div>
                                        <h4 className="text-lg font-semibold text-white mb-2">Self-Modification Within Boundaries</h4>
                                        <p className="text-gray-300">
                                            Your agents can write their own code, open their own PRs, and evolve their own capabilities. But every modification goes through an auditable gate that you define. Every decision is logged. Every action is traceable. The agents get smarter. You stay in control.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* 48-hour proof */}
                        <div className="mt-10 rounded-xl bg-cyan-950/30 border border-cyan-900/50 p-6">
                            <p className="text-gray-300">
                                I had CodeTether running for <span className="text-white font-semibold">48 hours straight</span> — self-deploying on Kubernetes, making its own pull requests, managing its own lifecycle. Not because I was watching it. <span className="text-cyan-400 font-medium">Because that&apos;s what it does.</span>
                            </p>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Section 5: What "Open Source AI Agent" Actually Means */}
            <section className="bg-gray-950 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                            Let&apos;s Talk About What{' '}
                            <span className="text-cyan-400">&quot;Open Source AI Agent&quot;</span>{' '}
                            Actually Means Right Now
                        </h3>

                        <div className="mt-8 space-y-6 text-base leading-relaxed text-gray-300">
                            <p>
                                The first wave of AI agents — OpenClaw included — proved something important: people are ready for this. Developers want agents that go beyond chat. They want agents that act. That open PRs. That manage infrastructure. That handle the work you don&apos;t want to do at 11 PM on a Tuesday.
                            </p>
                            <p>
                                But the first wave also proved something else: <span className="text-white font-medium">most of these tools were built for the demo, not for the day after the demo.</span>
                            </p>
                            <p>
                                They work great in the tweet. They work great in the screen recording. They work great when you&apos;re showing your friends on Discord. But then you try to run one in an environment that matters — where your team depends on it, where your client data flows through it, where a failure means more than restarting a process — and the cracks show up fast.
                            </p>
                        </div>

                        {/* Failure modes */}
                        <div className="mt-10 grid gap-4 sm:grid-cols-2">
                            {[
                                'No isolation between plugins',
                                'No audit trail',
                                'No way to scope agent permissions',
                                'One bad npm package = compromised agent',
                            ].map((issue) => (
                                <div key={issue} className="flex items-center gap-3 rounded-lg bg-red-950/20 border border-red-900/30 px-4 py-3">
                                    <XIcon className="h-4 w-4 text-red-400 shrink-0" />
                                    <span className="text-sm text-gray-300">{issue}</span>
                                </div>
                            ))}
                        </div>

                        <p className="mt-8 text-base text-gray-300">
                            CodeTether exists because I got tired of watching smart developers plug security holes with duct tape and ship it as &quot;the future.&quot;
                        </p>
                    </div>
                </Container>
            </section>

            {/* Section 6: Comparison Table */}
            <section className="bg-gray-900 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl text-center">
                            Side by Side
                        </h3>
                        <p className="mt-4 text-center text-gray-400">
                            Same category. Different engineering.
                        </p>

                        <div className="mt-12 overflow-hidden rounded-2xl border border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-950">
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-gray-400 sm:px-6">Feature</th>
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-gray-500 sm:px-6">OpenClaw</th>
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-cyan-400 sm:px-6">CodeTether</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800 bg-gray-900">
                                    {comparisonRows.map((row) => (
                                        <tr key={row.feature}>
                                            <td className="px-4 py-4 text-sm font-medium text-white sm:px-6">{row.feature}</td>
                                            <td className="px-4 py-4 text-sm text-gray-500 sm:px-6">{row.openclaw}</td>
                                            <td className="px-4 py-4 text-sm text-cyan-300 font-medium sm:px-6">{row.codetether}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Section 7: Two Paths */}
            <section className="bg-gray-950 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl text-center">
                            Here&apos;s What This Comes Down To
                        </h3>
                        <p className="mt-4 text-center text-lg text-gray-400">
                            You&apos;ve got two paths in front of you right now.
                        </p>

                        <div className="mt-12 grid gap-6 sm:grid-cols-2">
                            {/* Path One */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 sm:p-8">
                                <div className="inline-flex items-center gap-2 rounded-full bg-gray-800 px-3 py-1 mb-4">
                                    <span className="text-xs font-medium text-gray-400">Path One</span>
                                </div>
                                <p className="text-gray-300 text-sm leading-relaxed">
                                    You install the thing with 145,000 GitHub stars. The one that shipped with no auth. The one built in Node.js by a guy who thinks people don&apos;t care where their data is stored. You connect it to your email and your shell and your git repos, and you hope that the plugin you downloaded from a Discord marketplace doesn&apos;t have a supply chain attack baked in.
                                </p>
                                <p className="mt-4 text-gray-400 text-sm">
                                    And for a while, it&apos;s cool. It texts you a morning briefing. It manages your to-do list. And then one day something goes sideways, and you realize you handed the keys to your system to software that was designed for <span className="text-gray-300">convenience</span>, not for <span className="text-gray-300">consequences</span>.
                                </p>
                            </div>

                            {/* Path Two */}
                            <div className="rounded-2xl bg-cyan-950/30 border border-cyan-900/50 p-6 sm:p-8">
                                <div className="inline-flex items-center gap-2 rounded-full bg-cyan-900/50 px-3 py-1 mb-4">
                                    <span className="text-xs font-medium text-cyan-400">Path Two</span>
                                </div>
                                <p className="text-gray-200 text-sm leading-relaxed">
                                    You deploy an agent runtime built by someone who runs production systems for a living. Written in Rust. Deployed on Kubernetes. Auth mandatory. Plugins sandboxed and signed. Every autonomous decision audit-logged.
                                </p>
                                <p className="mt-4 text-gray-300 text-sm">
                                    Not because those things are trendy — because when you&apos;ve been the person who gets paged when things break, <span className="text-cyan-400 font-medium">you build differently</span>.
                                </p>
                            </div>
                        </div>

                        <p className="mt-10 text-center text-gray-300">
                            CodeTether is open source. It&apos;s free to self-host. And it&apos;s built for people who understand that the most dangerous thing in technology is a powerful tool built by someone who&apos;s never had to clean up the mess when it breaks.
                        </p>
                    </div>
                </Container>
            </section>

            {/* Section 8: CTA */}
            <section className="relative overflow-hidden bg-gray-900 py-20 sm:py-28">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,var(--tw-gradient-stops))] from-cyan-950/30 via-gray-900 to-gray-900" />
                <Container className="relative">
                    <div className="mx-auto max-w-2xl text-center">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                            Here&apos;s What I Want You to Do Right Now
                        </h3>

                        <p className="mt-6 text-base text-gray-300 leading-relaxed">
                            Go to codetether.run, pull the repo, and deploy it on your own infrastructure. Read the code. Audit the architecture. Compare it to anything else on the market.
                        </p>

                        <p className="mt-4 text-base text-gray-300 leading-relaxed">
                            If you&apos;re the kind of developer who actually thinks about what happens after the demo — who cares about what your code does when you&apos;re not watching, who understands that giving an AI agent root access to your machine is a decision that deserves more than a one-liner install script — <span className="text-white font-semibold">you&apos;ll see the difference in the first ten minutes.</span>
                        </p>

                        <p className="mt-6 text-gray-400 text-sm">
                            And if you just want something to manage your calendar and text you the weather? The other guys have you covered. Seriously. No shade.
                        </p>

                        <p className="mt-6 text-lg text-white font-semibold">
                            But if you build things that need to keep running, keep working, and keep your data where it belongs —
                        </p>
                        <p className="mt-2 text-xl text-cyan-400 font-bold">
                            CodeTether was built for you. By someone who builds the same kind of things you do.
                        </p>

                        <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4">
                            <Button href="https://codetether.run" color="cyan" className="text-base px-8 py-3">
                                Deploy CodeTether Now
                            </Button>
                            <Button
                                href="https://github.com/rileyseaburg/codetether"
                                variant="outline"
                                className="text-gray-300 text-base px-8 py-3"
                            >
                                Star on GitHub
                            </Button>
                        </div>

                        <div className="mt-8 flex flex-wrap justify-center gap-6 text-sm text-gray-400">
                            <span className="flex items-center gap-2">
                                <CheckIcon className="h-4 w-4 text-cyan-400" />
                                Open source — MIT License
                            </span>
                            <span className="flex items-center gap-2">
                                <CheckIcon className="h-4 w-4 text-cyan-400" />
                                Free to self-host
                            </span>
                            <span className="flex items-center gap-2">
                                <CheckIcon className="h-4 w-4 text-cyan-400" />
                                Free to modify
                            </span>
                        </div>

                        <p className="mt-6 text-xs text-gray-500">
                            Because your infrastructure shouldn&apos;t depend on someone else&apos;s business model.
                        </p>
                    </div>
                </Container>
            </section>
        </>
    )
}
