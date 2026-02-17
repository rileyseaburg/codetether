'use client'

import { useState, useEffect, useCallback } from 'react'
import { listToolsMcpV1ToolsGet, hasApiAuthToken } from '@/lib/api'
import { useSession } from 'next-auth/react'

interface MCPTool {
    name: string
    description?: string
    category?: string
}

const TOOL_CATEGORIES: Record<string, { label: string; color: string }> = {
    'File Ops': { label: 'File Ops', color: 'bg-blue-500/20 text-blue-400' },
    'Search': { label: 'Search', color: 'bg-green-500/20 text-green-400' },
    'Execution': { label: 'Execution', color: 'bg-red-500/20 text-red-400' },
    'Code Intelligence': { label: 'Code Intelligence', color: 'bg-purple-500/20 text-purple-400' },
    'Web': { label: 'Web', color: 'bg-orange-500/20 text-orange-400' },
    'Agent Orchestration': { label: 'Agent Orchestration', color: 'bg-cyan-500/20 text-cyan-400' },
    'Planning': { label: 'Planning', color: 'bg-yellow-500/20 text-yellow-400' },
    'Knowledge': { label: 'Knowledge', color: 'bg-pink-500/20 text-pink-400' },
}

const KNOWN_TOOLS: Record<string, string> = {
    read: 'File Ops', write: 'File Ops', edit: 'File Ops', multiedit: 'File Ops',
    apply_patch: 'File Ops', glob: 'File Ops', list: 'File Ops',
    grep: 'Search', codesearch: 'Search',
    bash: 'Execution', task: 'Execution',
    lsp: 'Code Intelligence',
    webfetch: 'Web', websearch: 'Web',
    agent: 'Agent Orchestration', swarm_execute: 'Agent Orchestration',
    relay_autochat: 'Agent Orchestration', go: 'Agent Orchestration',
    ralph: 'Planning', prd: 'Planning', okr: 'Planning',
    todoread: 'Planning', todowrite: 'Planning',
    memory: 'Knowledge', skill: 'Knowledge', mcp: 'Knowledge',
}

function categorize(name: string): string {
    return KNOWN_TOOLS[name] || 'Other'
}

export default function MCPToolsPage() {
    const [tools, setTools] = useState<MCPTool[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [filter, setFilter] = useState('')
    const [activeTab, setActiveTab] = useState<'catalog' | 'setup'>('catalog')
    const { data: session } = useSession()

    const loadTools = useCallback(async () => {
        try {
            setLoading(true)
            const { data, error: apiError } = await listToolsMcpV1ToolsGet()
            if (apiError) {
                setError('Failed to load tools from server')
                return
            }
            const toolList = Array.isArray(data) ? data : (data as any)?.tools || []
            setTools(toolList.map((t: any) => ({
                name: t.name || t,
                description: t.description || '',
                category: categorize(t.name || t),
            })))
            setError(null)
        } catch {
            setError('Could not connect to MCP server')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        if (session?.accessToken || hasApiAuthToken()) {
            loadTools()
        } else {
            setLoading(false)
        }
    }, [session?.accessToken, loadTools])

    const filtered = tools.filter(t =>
        t.name.toLowerCase().includes(filter.toLowerCase()) ||
        (t.description || '').toLowerCase().includes(filter.toLowerCase()) ||
        (t.category || '').toLowerCase().includes(filter.toLowerCase())
    )

    const grouped = filtered.reduce<Record<string, MCPTool[]>>((acc, tool) => {
        const cat = tool.category || 'Other'
        if (!acc[cat]) acc[cat] = []
        acc[cat].push(tool)
        return acc
    }, {})

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">MCP Tools</h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    {tools.length} tools exposed via the <a href="https://modelcontextprotocol.io/" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">Model Context Protocol</a> over
                    stdio. Works with VS Code (GitHub Copilot), Claude Desktop, and any MCP-compatible client.
                </p>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-4">
                    {(['catalog', 'setup'] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab
                                ? 'border-cyan-500 text-cyan-400'
                                : 'border-transparent text-gray-400 hover:text-gray-300'
                                }`}
                        >
                            {tab === 'catalog' ? 'Tool Catalog' : 'Setup Guide'}
                        </button>
                    ))}
                </nav>
            </div>

            {activeTab === 'catalog' && (
                <div className="space-y-6">
                    {/* Search */}
                    <input
                        type="text"
                        placeholder="Filter tools..."
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        className="w-full max-w-md rounded-lg border border-gray-600 bg-gray-700 px-4 py-2 text-sm text-white placeholder-gray-400 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                    />

                    {loading ? (
                        <div className="flex items-center gap-2 text-gray-400">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Loading tools...
                        </div>
                    ) : !session?.accessToken && !hasApiAuthToken() ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to view live tool catalog</h3>
                            <p className="text-sm text-gray-400">Connect your account to load tools from your connected workers.</p>
                        </div>
                    ) : error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">
                            {error}
                        </div>
                    ) : null}

                    {/* Tool groups */}
                    {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([category, categoryTools]) => (
                        <div key={category}>
                            <div className="flex items-center gap-2 mb-3">
                                <span className={`text-xs font-medium px-2 py-0.5 rounded ${TOOL_CATEGORIES[category]?.color || 'bg-gray-500/20 text-gray-400'}`}>
                                    {category}
                                </span>
                                <span className="text-xs text-gray-500">{categoryTools.length} tools</span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {categoryTools.map(tool => (
                                    <div key={tool.name} className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                                        <code className="text-sm font-mono text-cyan-400">{tool.name}</code>
                                        {tool.description && (
                                            <p className="mt-1 text-xs text-gray-400 line-clamp-2">{tool.description}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {activeTab === 'setup' && (
                <div className="max-w-3xl space-y-6">
                    {/* VS Code setup */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">VS Code (Recommended)</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Add a <code className="text-xs bg-gray-700 text-cyan-400 px-1 rounded">.vscode/mcp.json</code> to your workspace:
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">{`{
  "servers": {
    "codetether": {
      "command": "codetether",
      "args": ["mcp", "serve"]
    }
  }
}`}</pre>
                        <p className="mt-3 text-xs text-gray-500">
                            Reload VS Code — the {tools.length || 26} tools appear in the MCP panel automatically.
                        </p>
                    </div>

                    {/* Claude Desktop setup */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">Claude Desktop</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Edit your Claude Desktop config:
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">{`{
  "mcpServers": {
    "codetether": {
      "command": "codetether",
      "args": ["mcp", "serve"]
    }
  }
}`}</pre>
                    </div>

                    {/* SSH remote setup */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">Remote (SSH)</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            For remote machines, pipe through SSH:
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">{`{
  "mcpServers": {
    "codetether-remote": {
      "command": "ssh",
      "args": ["-t", "user@host", "codetether", "mcp", "serve"]
    }
  }
}`}</pre>
                    </div>

                    {/* CLI helpers */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">CLI Helpers</h3>
                        <div className="space-y-3 font-mono text-sm">
                            {[
                                { cmd: 'codetether mcp list-tools', desc: 'List available MCP tools' },
                                { cmd: 'codetether mcp list-tools --json', desc: 'JSON output' },
                                { cmd: 'codetether mcp serve', desc: 'Start stdio MCP server' },
                                { cmd: 'codetether mcp serve --bus-url URL', desc: 'With agent bus integration' },
                            ].map(item => (
                                <div key={item.cmd} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 rounded-lg bg-gray-700/50 px-4 py-3">
                                    <code className="text-cyan-400 shrink-0">{item.cmd}</code>
                                    <span className="text-gray-400 text-xs">{item.desc}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
