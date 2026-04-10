'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useTenantApi } from '@/hooks/useTenantApi'

const ZAPIER_INVITE_LINK = 'https://zapier.com/developer/public-invite/235522/dc2a275ee1ca4688be5a4f18bf214ecb/'

function ZapierIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 14.036h-3.43l2.426 2.426a.5.5 0 010 .707l-.707.707a.5.5 0 01-.707 0l-2.426-2.426v3.43a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-3.43l-2.426 2.426a.5.5 0 01-.707 0l-.707-.707a.5.5 0 010-.707l2.426-2.426h-3.43a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h3.43L7.21 9.61a.5.5 0 010-.707l.707-.707a.5.5 0 01.707 0l2.426 2.426v-3.43a.5.5 0 01.5-.5h1a.5.5 0 01.5.5v3.43l2.426-2.426a.5.5 0 01.707 0l.707.707a.5.5 0 010 .707l-2.426 2.426h3.43a.5.5 0 01.5.5v1a.5.5 0 01-.5.5z" />
        </svg>
    )
}

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
    )
}

function ArrowRightIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
    )
}

function TerminalIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

function WebhookIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
    )
}

const integrationMethods = [
    {
        name: 'Zapier',
        description: 'Connect CodeTether to 6,000+ apps with no code. 18 components: triggers, actions, searches for tasks, agents, workspaces, cron jobs, billing, and more.',
        icon: ZapierIcon,
        color: 'bg-orange-500',
        href: ZAPIER_INVITE_LINK,
        external: true,
        featured: true,
        features: [
            '3 triggers: task created, completed, and failed',
            '9 actions: tasks, messages, agents, Ralph, cron jobs, PRDs',
            '7 searches: agents, workspaces, models, usage, Ralph runs',
            'No coding required — OAuth2 authentication'
        ],
        cta: 'Connect with Zapier',
    },
    {
        name: 'REST API',
        description: 'Full programmatic access to create tasks, send messages, and monitor agent activity.',
        icon: TerminalIcon,
        color: 'bg-cyan-500',
        href: 'https://docs.codetether.run/api',
        external: true,
        featured: false,
        features: [
            'Create and manage tasks programmatically',
            'Real-time webhooks for task updates',
            'Full conversation history access',
            'Bearer token authentication'
        ],
        cta: 'View API Docs',
    },
    {
        name: 'Webhooks',
        description: 'Receive real-time notifications when tasks complete, fail, or need attention.',
        icon: WebhookIcon,
        color: 'bg-cyan-500',
        href: '/dashboard/settings',
        external: false,
        featured: false,
        features: [
            'Task completion notifications',
            'Error and failure alerts',
            'Custom payload formatting',
            'Retry with exponential backoff'
        ],
        cta: 'Configure Webhooks',
    },
]

const quickStartSteps = [
    {
        step: 1,
        title: 'Connect Zapier',
        description: 'Click the button below to add CodeTether to your Zapier account.',
        action: { label: 'Add to Zapier', href: ZAPIER_INVITE_LINK, external: true },
    },
    {
        step: 2,
        title: 'Create Your First Zap',
        description: 'Use any trigger (Gmail, Slack, etc.) and add CodeTether\'s "Create Task" action.',
        action: { label: 'Zapier Dashboard', href: 'https://zapier.com/app/zaps', external: true },
    },
    {
        step: 3,
        title: 'Monitor Results',
        description: 'View task progress and AI responses in your CodeTether dashboard.',
        action: { label: 'View Tasks', href: '/dashboard/tasks', external: false },
    },
]

const zapierUseCases = [
    {
        trigger: 'New email in Gmail',
        action: 'Create task to analyze and draft response',
        icon: '📧',
    },
    {
        trigger: 'New Slack message',
        action: 'Send to specific AI agent for code review',
        icon: '💬',
    },
    {
        trigger: 'New GitHub issue',
        action: 'Auto-create task to investigate bug',
        icon: '🐛',
    },
    {
        trigger: 'New Notion page',
        action: 'Generate PRD → start Ralph run automatically',
        icon: '📝',
    },
    {
        trigger: 'Create a cron job',
        action: 'Schedule daily code reviews at 9am',
        icon: '🕐',
    },
    {
        trigger: 'Task failed (trigger)',
        action: 'Auto-retry with different model or alert team',
        icon: '🔄',
    },
    {
        trigger: 'Weekly budget check',
        action: 'Get usage summary → alert if over budget',
        icon: '💰',
    },
    {
        trigger: 'New Trello card',
        action: 'Send async message to builder agent',
        icon: '📋',
    },
]

export default function GettingStartedPage() {
    const [activeTab, setActiveTab] = useState<'cli' | 'k8s' | 'zapier' | 'api'>('cli')
    const { tenantFetch, isAuthenticated, isLoading: authLoading } = useTenantApi()

    const [workerCount, setWorkerCount] = useState<number | null>(null)
    const [serverOk, setServerOk] = useState<boolean | null>(null)
    const [statusLoading, setStatusLoading] = useState(true)

    const fetchStatus = useCallback(async () => {
        try {
            const [healthRes, workersRes] = await Promise.all([
                tenantFetch<{ status?: string }>('/v1/admin/health'),
                tenantFetch<{ id?: string }[]>('/v1/agent/workers'),
            ])
            if (
                healthRes.error?.toLowerCase().includes('session expired') ||
                workersRes.error?.toLowerCase().includes('session expired')
            ) {
                setServerOk(null)
                setWorkerCount(null)
                return
            }
            setServerOk(healthRes.data?.status === 'ok' || healthRes.data?.status === 'healthy')
            if (Array.isArray(workersRes.data)) setWorkerCount(workersRes.data.length)
        } catch {
            setServerOk(false)
        }
    }, [tenantFetch])

    useEffect(() => {
        if (!isAuthenticated) { setStatusLoading(false); return }
        setStatusLoading(true)
        fetchStatus().finally(() => setStatusLoading(false))
        const interval = setInterval(fetchStatus, 30000)
        return () => clearInterval(interval)
    }, [isAuthenticated, fetchStatus])

    return (
        <div className="space-y-8 pb-12">
            {/* Hero */}
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Get Started</h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Run locally with the CLI, deploy workers to Kubernetes, or integrate via Zapier and REST API.
                </p>
            </div>

            {/* Live connection status */}
            {isAuthenticated && !authLoading && !statusLoading && (
                <div className="grid grid-cols-3 gap-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 flex items-center gap-3">
                        <span className={`inline-block h-2.5 w-2.5 rounded-full ${serverOk ? 'bg-green-500' : serverOk === false ? 'bg-red-500' : 'bg-gray-500'}`} />
                        <div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">Server</div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">{serverOk ? 'Connected' : serverOk === false ? 'Unreachable' : 'Checking...'}</div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 flex items-center gap-3">
                        <span className={`inline-block h-2.5 w-2.5 rounded-full ${workerCount && workerCount > 0 ? 'bg-green-500' : 'bg-yellow-500'}`} />
                        <div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">Workers</div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                {workerCount !== null ? `${workerCount} online` : 'Unknown'}
                            </div>
                        </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 flex items-center gap-3">
                        <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
                        <div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">Auth</div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Authenticated</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-4">
                    {([
                        { key: 'cli' as const, label: '🖥️ Local CLI' },
                        { key: 'k8s' as const, label: '☸️ Kubernetes' },
                        { key: 'zapier' as const, label: 'Zapier' },
                        { key: 'api' as const, label: 'REST API & Webhooks' },
                    ]).map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key
                                ? 'border-cyan-500 text-cyan-400'
                                : 'border-transparent text-gray-400 hover:text-gray-300'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </nav>
            </div>

            {activeTab === 'cli' && (
                <div className="max-w-3xl space-y-6">
                    {/* Install */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">1. Install</h3>
                        <div className="space-y-4">
                            <div>
                                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Linux / macOS</span>
                                <pre className="mt-1 rounded-lg bg-gray-900 p-4 text-sm text-cyan-400 font-mono overflow-x-auto">
                                    {`curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.sh | bash`}
                                </pre>
                            </div>
                            <div>
                                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Windows (PowerShell)</span>
                                <pre className="mt-1 rounded-lg bg-gray-900 p-4 text-sm text-cyan-400 font-mono overflow-x-auto">
                                    {`Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.ps1" -UseBasicParsing).Content`}
                                </pre>
                            </div>
                        </div>
                    </div>

                    {/* Launch TUI */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">2. Launch the TUI</h3>
                        <p className="text-sm text-gray-400 mb-4">Interactive terminal interface with chat, file tree, and real-time tool output.</p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-sm text-cyan-400 font-mono">codetether</pre>
                    </div>

                    {/* /go workflow */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">3. Start an OKR-driven task</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Type <code className="text-xs bg-gray-700 text-cyan-400 px-1 rounded">/go</code> with a natural language objective.
                            The agent creates Key Results, asks for approval, then executes autonomously.
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-sm text-cyan-400 font-mono overflow-x-auto">
                            {`/go Add dark mode toggle to the settings page`}
                        </pre>
                        <div className="mt-4 flex gap-4">
                            <Link href="/dashboard/okr" className="text-sm text-cyan-400 hover:underline">Learn about OKR →</Link>
                            <Link href="/dashboard/swarm" className="text-sm text-cyan-400 hover:underline">Parallel swarm execution →</Link>
                        </div>
                    </div>

                    {/* MCP setup */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">4. Connect to VS Code or Claude Desktop</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            CodeTether exposes 26 tools via the Model Context Protocol. Add this config to your project:
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">{`// .vscode/mcp.json
{
  "servers": {
    "codetether": {
      "command": "codetether",
      "args": ["mcp", "serve"]
    }
  }
}`}</pre>
                        <div className="mt-4">
                            <Link href="/dashboard/mcp" className="text-sm text-cyan-400 hover:underline">Full MCP setup guide →</Link>
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'k8s' && (
                <div className="max-w-3xl space-y-6">
                    <div className="rounded-xl border border-purple-500/30 bg-purple-500/5 p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-xs font-semibold px-2 py-1 rounded bg-purple-500/20 text-purple-400">☸️ Kubernetes</span>
                            <span className="text-xs text-gray-500">Persistent worker pods</span>
                        </div>
                        <p className="text-sm text-gray-300 mb-4">
                            In Kubernetes mode, CodeTether agents run as persistent <strong className="text-white">worker pods</strong> that
                            connect to the A2A server via SSE, register workspaces, and pick up tasks automatically.
                            This is different from local mode where you run the CLI directly.
                        </p>
                    </div>

                    {/* Deploy worker */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">1. Deploy a Worker</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Workers connect to the A2A server and poll for tasks. Deploy using the helper script or Helm chart.
                        </p>
                        <div className="space-y-4">
                            <div>
                                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Quick deploy script</span>
                                <pre className="mt-1 rounded-lg bg-gray-900 p-4 text-sm text-cyan-400 font-mono overflow-x-auto">
                                    {`./deploy-worker.sh --codebases /path/to/project`}
                                </pre>
                            </div>
                            <div>
                                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Direct Docker</span>
                                <pre className="mt-1 rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">
                                    {`docker run -d \\
  -e CODETETHER_SERVER=https://api.codetether.run \\
  -e CODETETHER_TOKEN=<your-token> \\
  -e CODETETHER_WORKER_NAME=worker-1 \\
  -v /path/to/project:/workspace \\
  ghcr.io/rileyseaburg/codetether-agent:latest \\
  worker --codebases /workspace`}
                                </pre>
                            </div>
                        </div>
                    </div>

                    {/* Register workspaces */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">2. Register Workspaces</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Workers register their workspace paths with the server on startup.
                            The server routes tasks to workers based on which workspaces they manage.
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">
                            {`# Worker CLI flags
codetether worker \\
  --server https://api.codetether.run \\
  --token <token> \\
  --codebases /project-a,/project-b \\
  --auto-approve safe`}
                        </pre>
                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                            <div className="rounded bg-gray-700/50 px-3 py-2">
                                <span className="text-cyan-400 font-medium">--codebases</span>
                                <p className="text-gray-400 mt-0.5">Workspace paths (legacy flag name)</p>
                            </div>
                            <div className="rounded bg-gray-700/50 px-3 py-2">
                                <span className="text-cyan-400 font-medium">--auto-approve</span>
                                <p className="text-gray-400 mt-0.5">all | safe | none</p>
                            </div>
                            <div className="rounded bg-gray-700/50 px-3 py-2">
                                <span className="text-cyan-400 font-medium">--email</span>
                                <p className="text-gray-400 mt-0.5">Completion reports</p>
                            </div>
                        </div>
                    </div>

                    {/* Monitor */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">3. Monitor Workers</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Workers POST heartbeats to the server. View active workers, their workspaces, and available models in the dashboard.
                        </p>
                        <div className="flex gap-4">
                            <Link href="/dashboard/workers" className="text-sm text-cyan-400 hover:underline">View Workers →</Link>
                            <Link href="/dashboard/tasks" className="text-sm text-cyan-400 hover:underline">View Tasks →</Link>
                        </div>
                    </div>

                    {/* Local vs K8s summary */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Local vs Kubernetes at a Glance</h3>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-gray-400 border-b border-gray-700">
                                    <tr>
                                        <th className="py-2 pr-4"></th>
                                        <th className="py-2 pr-4">🖥️ Local</th>
                                        <th className="py-2">☸️ Kubernetes</th>
                                    </tr>
                                </thead>
                                <tbody className="text-gray-300">
                                    {[
                                        { label: 'How you start', local: 'codetether (TUI)', k8s: 'codetether worker' },
                                        { label: 'Runs as', local: 'Interactive process', k8s: 'Background pod/service' },
                                        { label: 'Task source', local: 'Direct CLI or /go', k8s: 'SSE from A2A server' },
                                        { label: 'Workspaces', local: 'Current directory', k8s: 'Registered via --workspace-paths (--codebases legacy)' },
                                        { label: 'Swarm agents', local: 'Threads (same process)', k8s: 'Isolated pods' },
                                        { label: 'Health checks', local: 'N/A', k8s: 'Liveness + readiness probes' },
                                        { label: 'Secrets', local: 'Env vars / .env', k8s: 'Vault + forwarded env vars' },
                                    ].map(row => (
                                        <tr key={row.label} className="border-b border-gray-800">
                                            <td className="py-2 pr-4 text-white font-medium">{row.label}</td>
                                            <td className="py-2 pr-4 text-cyan-400 font-mono text-xs">{row.local}</td>
                                            <td className="py-2 text-purple-400 font-mono text-xs">{row.k8s}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'zapier' && (
                <div className="space-y-8">
                    {/* Zapier hero */}
                    <div className="rounded-2xl bg-gradient-to-r from-orange-500 to-orange-600 p-8 text-white">
                        <div className="flex items-center gap-3 mb-4">
                            <ZapierIcon className="h-10 w-10" />
                            <span className="text-sm font-medium bg-white/20 px-3 py-1 rounded-full">Recommended</span>
                        </div>
                        <h2 className="text-3xl font-bold mb-2">Connect with Zapier</h2>
                        <p className="text-lg text-orange-100 mb-6 max-w-2xl">
                            The fastest way to automate CodeTether. Connect to 6,000+ apps and start
                            triggering AI tasks from emails, Slack, forms, and more — no code required.
                        </p>
                        <a
                            href={ZAPIER_INVITE_LINK}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 bg-white text-orange-600 px-6 py-3 rounded-lg font-semibold hover:bg-orange-50 transition-colors"
                        >
                            <ZapierIcon className="h-5 w-5" />
                            Connect CodeTether to Zapier
                            <ArrowRightIcon className="h-4 w-4" />
                        </a>
                    </div>

                    {/* Quick Start Steps */}
                    <div className="rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 ring-gray-200 dark:ring-gray-700 p-6">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">Quick Start (3 minutes)</h2>
                        <div className="grid gap-6 md:grid-cols-3">
                            {quickStartSteps.map((step) => (
                                <div key={step.step} className="relative">
                                    <div className="flex items-start gap-4">
                                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 font-bold">
                                            {step.step}
                                        </div>
                                        <div className="flex-1">
                                            <h3 className="font-semibold text-gray-900 dark:text-white">{step.title}</h3>
                                            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{step.description}</p>
                                            {step.action.external ? (
                                                <a
                                                    href={step.action.href}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-orange-600 dark:text-orange-400 hover:underline"
                                                >
                                                    {step.action.label}
                                                    <ArrowRightIcon className="h-3 w-3" />
                                                </a>
                                            ) : (
                                                <Link
                                                    href={step.action.href}
                                                    className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-orange-600 dark:text-orange-400 hover:underline"
                                                >
                                                    {step.action.label}
                                                    <ArrowRightIcon className="h-3 w-3" />
                                                </Link>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Zapier Use Cases */}
                    <div className="rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 ring-gray-200 dark:ring-gray-700 p-6">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">Popular Automations</h2>
                        <p className="text-gray-600 dark:text-gray-400 mb-6">Examples of what you can build with CodeTether + Zapier</p>
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {zapierUseCases.map((useCase, idx) => (
                                <div key={idx} className="flex items-start gap-3 p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                                    <span className="text-2xl">{useCase.icon}</span>
                                    <div>
                                        <p className="text-sm font-medium text-gray-900 dark:text-white">{useCase.trigger}</p>
                                        <p className="text-sm text-gray-500 dark:text-gray-400">→ {useCase.action}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'api' && (
                <div className="space-y-6">
                    {/* All Integration Methods */}
                    <div className="grid gap-6 lg:grid-cols-3">
                        {integrationMethods.map((method) => (
                            <div
                                key={method.name}
                                className={`rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 p-6 ${method.featured
                                    ? 'ring-orange-500 ring-2'
                                    : 'ring-gray-200 dark:ring-gray-700'
                                    }`}
                            >
                                {method.featured && (
                                    <span className="inline-block mb-3 text-xs font-semibold text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-900/30 px-2 py-1 rounded-full">
                                        Recommended
                                    </span>
                                )}
                                <div className="flex items-center gap-3 mb-3">
                                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${method.color} text-white`}>
                                        <method.icon className="h-5 w-5" />
                                    </div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{method.name}</h3>
                                </div>
                                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{method.description}</p>
                                <ul className="space-y-2 mb-6">
                                    {method.features.map((feature, idx) => (
                                        <li key={idx} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                                            <CheckIcon className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                                {method.external ? (
                                    <a
                                        href={method.href}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${method.featured
                                            ? 'bg-orange-500 text-white hover:bg-orange-600'
                                            : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600'
                                            }`}
                                    >
                                        {method.cta}
                                        <ArrowRightIcon className="h-4 w-4" />
                                    </a>
                                ) : (
                                    <Link
                                        href={method.href}
                                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                                    >
                                        {method.cta}
                                        <ArrowRightIcon className="h-4 w-4" />
                                    </Link>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Help Section */}
            <div className="rounded-xl bg-gray-50 dark:bg-gray-800/50 p-6 text-center">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Need Help?</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                    Our team is here to help you get set up.
                </p>
                <div className="flex flex-wrap justify-center gap-4">
                    <a
                        href="https://docs.codetether.run"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-cyan-600 dark:text-cyan-400 hover:underline"
                    >
                        Documentation
                    </a>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <a
                        href="mailto:support@codetether.io"
                        className="text-sm font-medium text-cyan-600 dark:text-cyan-400 hover:underline"
                    >
                        Email Support
                    </a>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <a
                        href="https://discord.gg/codetether"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-cyan-600 dark:text-cyan-400 hover:underline"
                    >
                        Discord Community
                    </a>
                </div>
            </div>
        </div>
    )
}
