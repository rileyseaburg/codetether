'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
    )
}

function CopyIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
    )
}

function GitHubIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
        </svg>
    )
}

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

function ZapIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
    )
}

const SETUP_STEPS = [
    {
        step: 1,
        title: 'Get your API token',
        description: 'Generate a CodeTether API token from Settings. You\'ll add this as a GitHub secret.',
    },
    {
        step: 2,
        title: 'Add secret to repo',
        description: 'Go to your repo → Settings → Secrets → New secret. Name it CODETETHER_TOKEN.',
    },
    {
        step: 3,
        title: 'Add workflow file',
        description: 'Copy the workflow below into .github/workflows/codetether-review.yml',
    },
    {
        step: 4,
        title: 'Open a PR',
        description: 'Every new pull request will automatically get an AI-powered code review.',
    },
]

function generateWorkflowYaml(serverUrl: string, mode: 'server' | 'local', extraPrompt?: string) {
    const extraPromptLine = extraPrompt ? `\n          # extra_prompt: "${extraPrompt}"` : ''

    if (mode === 'local') {
        return `# CodeTether Code Review — Self-Hosted (BYOK)
#
# Runs the agent in your GitHub Actions runner with your own LLM keys.
# No data leaves your infrastructure.
#
# Setup:
#   1. Add OPENAI_API_KEY (or ANTHROPIC_API_KEY) as a repo secret
#   2. Add CODETETHER_TOKEN as a repo secret
#   3. Copy this file to .github/workflows/codetether-review.yml

name: CodeTether Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: codetether-review-\${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: CodeTether Review (BYOK)
        uses: rileyseaburg/codetether-agent@main
        with:
          token: \${{ secrets.CODETETHER_TOKEN }}
          mode: "local"
          api_key: \${{ secrets.OPENAI_API_KEY }}
          model: "gpt-4o"${extraPromptLine}
`
    }

    return `# CodeTether Code Review
#
# AI-powered code review on every pull request.
# Setup takes 2 minutes — no LLM keys needed.
#
# Setup:
#   1. Sign up at https://codetether.run
#   2. Go to Settings → API Tokens → Create Token
#   3. Add token as repo secret: CODETETHER_TOKEN
#   4. Copy this file to .github/workflows/codetether-review.yml
#   5. Done — every PR gets an AI review.

name: CodeTether Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: codetether-review-\${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: CodeTether Review
        uses: rileyseaburg/codetether-agent@main
        with:
          token: \${{ secrets.CODETETHER_TOKEN }}${extraPromptLine}
`
}

function generateFullWorkflowYaml(serverUrl: string) {
    return `# CodeTether — Full Integration (Review + Fix + Issue handling)
#
# This workflow handles:
#   - PR reviews on every pull request
#   - @codetether fix requests via comments
#   - Issue handling when assigned or labeled
#
# Setup:
#   1. Create a CodeTether API token (Settings → API Tokens)
#   2. Add CODETETHER_TOKEN as a repo secret
#   3. (Optional) Create a GitHub App for bot identity comments
#   4. Copy this file to .github/workflows/codetether-review.yml

name: CodeTether Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issues:
    types: [assigned, labeled]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

concurrency:
  group: codetether-review-\${{ github.event_name }}-\${{ github.event.pull_request.number || github.event.issue.number }}
  cancel-in-progress: true

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    if: >
      github.event_name == 'pull_request' ||
      (github.event_name == 'issues' && (
        github.event.action == 'assigned' ||
        contains(github.event.issue.labels.*.name, 'codetether')
      )) ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@codetether')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@codetether'))
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: CodeTether Review
        uses: rileyseaburg/codetether-agent@main
        with:
          token: \${{ secrets.CODETETHER_TOKEN }}
          max_steps: "60"
          task_wait_seconds: "1200"
`
}

export default function GitHubActionsPage() {
    const { tenantFetch, isAuthenticated } = useTenantApi()
    const [apiKeys, setApiKeys] = useState<Array<{ key: string; name: string; created_at: string }>>([])
    const [loadingKeys, setLoadingKeys] = useState(true)
    const [mode, setMode] = useState<'server' | 'local' | 'full'>('server')
    const [copied, setCopied] = useState<string | null>(null)
    const [extraPrompt, setExtraPrompt] = useState('')

    const serverUrl = typeof window !== 'undefined'
        ? `${window.location.protocol}//${window.location.host.replace(/^app\./, 'api.')}`
        : 'https://api.codetether.run'

    const fetchApiKeys = useCallback(async () => {
        if (!isAuthenticated) { setLoadingKeys(false); return }
        try {
            const res = await tenantFetch<{ keys?: Array<{ key: string; name: string; created_at: string }> }>('/v1/agent/api-keys')
            setApiKeys(res.data?.keys || [])
        } catch {
            // ignore
        } finally {
            setLoadingKeys(false)
        }
    }, [isAuthenticated, tenantFetch])

    useEffect(() => {
        fetchApiKeys()
    }, [fetchApiKeys])

    const workflowYaml = mode === 'full'
        ? generateFullWorkflowYaml(serverUrl)
        : generateWorkflowYaml(serverUrl, mode, extraPrompt || undefined)

    const copyToClipboard = (text: string, id: string) => {
        navigator.clipboard.writeText(text)
        setCopied(id)
        setTimeout(() => setCopied(null), 2000)
    }

    return (
        <div className="space-y-8 pb-12">
            {/* Header */}
            <div className="flex items-center gap-4">
                <div className="flex-shrink-0 w-12 h-12 bg-gray-900 dark:bg-white rounded-xl flex items-center justify-center">
                    <GitHubIcon className="w-7 h-7 text-white dark:text-gray-900" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">GitHub Actions</h1>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        AI-powered code review on every pull request. 2-minute setup.
                    </p>
                </div>
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                    {
                        icon: ZapIcon,
                        title: 'Auto Review',
                        desc: 'Every PR gets an instant AI review covering bugs, security, performance, and style.',
                    },
                    {
                        icon: ShieldIcon,
                        title: 'Auto Fix',
                        desc: 'Comment @codetether fix this on any PR line and the agent writes, commits, and pushes the fix.',
                    },
                    {
                        icon: GitHubIcon,
                        title: 'Bot Identity',
                        desc: 'Reviews post as the codetether[bot] — clean timeline, no personal account needed.',
                    },
                ].map(({ icon: Icon, title, desc }) => (
                    <div
                        key={title}
                        className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700"
                    >
                        <Icon className="w-6 h-6 text-blue-500 mb-2" />
                        <h3 className="font-semibold text-gray-900 dark:text-white text-sm">{title}</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{desc}</p>
                    </div>
                ))}
            </div>

            {/* Setup steps */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Setup (2 minutes)</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {SETUP_STEPS.map(({ step, title, description }) => (
                        <div key={step} className="flex gap-3">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center text-sm font-bold">
                                {step}
                            </div>
                            <div>
                                <h3 className="font-medium text-gray-900 dark:text-white text-sm">{title}</h3>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* API Token status */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span
                            className={`inline-block h-2.5 w-2.5 rounded-full ${
                                apiKeys.length > 0 ? 'bg-green-500' : 'bg-yellow-500'
                            }`}
                        />
                        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                            API Token{apiKeys.length !== 1 ? 's' : ''}
                        </h2>
                    </div>
                    <a
                        href="/dashboard/settings"
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    >
                        {apiKeys.length > 0 ? 'Manage tokens →' : 'Create token →'}
                    </a>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    {apiKeys.length > 0
                        ? `You have ${apiKeys.length} API key${apiKeys.length !== 1 ? 's' : ''}. Add one as the CODETETHER_TOKEN secret in your GitHub repo.`
                        : 'Create an API token in Settings and add it as a GitHub repo secret named CODETETHER_TOKEN.'}
                </p>
            </div>

            {/* Mode selector */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Choose your setup</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {([
                        {
                            id: 'server' as const,
                            label: 'Cloud',
                            badge: 'Recommended',
                            desc: 'Fastest setup. Reviews run on CodeTether servers. No LLM keys needed.',
                        },
                        {
                            id: 'local' as const,
                            label: 'Self-Hosted (BYOK)',
                            badge: 'Private',
                            desc: 'Runs on your GitHub runner with your own OpenAI/Anthropic keys. No data leaves GitHub.',
                        },
                        {
                            id: 'full' as const,
                            label: 'Full Integration',
                            badge: 'Advanced',
                            desc: 'Review + fix comments + issue handling. Uses @codetether mentions for auto-fix.',
                        },
                    ] as const).map(({ id, label, badge, desc }) => (
                        <button
                            key={id}
                            onClick={() => setMode(id)}
                            className={`text-left p-4 rounded-lg border-2 transition-colors ${
                                mode === id
                                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-sm text-gray-900 dark:text-white">{label}</span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium">
                                    {badge}
                                </span>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{desc}</p>
                        </button>
                    ))}
                </div>
            </div>

            {/* Workflow YAML */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-2">
                        <div className="flex gap-1.5">
                            <div className="w-3 h-3 rounded-full bg-red-400" />
                            <div className="w-3 h-3 rounded-full bg-yellow-400" />
                            <div className="w-3 h-3 rounded-full bg-green-400" />
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-mono ml-2">
                            .github/workflows/codetether-review.yml
                        </span>
                    </div>
                    <button
                        onClick={() => copyToClipboard(workflowYaml, 'workflow')}
                        className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white bg-white dark:bg-gray-600 px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-500 transition-colors"
                    >
                        {copied === 'workflow' ? (
                            <>
                                <CheckIcon className="w-3.5 h-3.5 text-green-500" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <CopyIcon className="w-3.5 h-3.5" />
                                Copy
                            </>
                        )}
                    </button>
                </div>
                <pre className="p-4 text-xs text-gray-800 dark:text-gray-200 font-mono overflow-x-auto leading-relaxed">
                    {workflowYaml}
                </pre>
            </div>

            {/* Extra prompt (server/local mode) */}
            {mode !== 'full' && (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">Custom instructions (optional)</h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                        Add extra instructions to focus the review. E.g. &quot;Focus on security&quot; or &quot;Check for SQL injection&quot;.
                    </p>
                    <input
                        type="text"
                        value={extraPrompt}
                        onChange={(e) => setExtraPrompt(e.target.value)}
                        placeholder="e.g. Focus on security issues and SQL injection"
                        className="w-full text-sm px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                </div>
            )}

            {/* Links */}
            <div className="flex flex-wrap gap-4">
                <a
                    href="https://github.com/rileyseaburg/codetether-agent"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                >
                    <GitHubIcon className="w-4 h-4" />
                    View on GitHub
                </a>
                <a
                    href="/dashboard/settings"
                    className="flex items-center gap-2 px-4 py-2.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 rounded-lg text-sm font-medium border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                    <ShieldIcon className="w-4 h-4" />
                    Manage API Tokens
                </a>
            </div>
        </div>
    )
}
