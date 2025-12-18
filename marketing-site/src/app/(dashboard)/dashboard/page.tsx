'use client'

import { useState, useEffect, useCallback } from 'react'

// API base URL - use environment variable or default
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface Codebase {
    id: string
    name: string
    path: string
    description?: string
    status: string
    worker_id?: string
}

interface Worker {
    worker_id: string
    name: string
    hostname?: string
    status: string
    global_codebase_id?: string
    last_seen?: string
}

interface Model {
    id: string
    name: string
    provider: string
    custom?: boolean
}

function FolderIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
    )
}

function PlusIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
    )
}

function RefreshIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

export default function DashboardPage() {
    const [codebases, setCodebases] = useState<Codebase[]>([])
    const [workers, setWorkers] = useState<Worker[]>([])
    const [models, setModels] = useState<Model[]>([])
    const [selectedCodebase, setSelectedCodebase] = useState('')
    const [selectedAgent, setSelectedAgent] = useState('build')
    const [selectedModel, setSelectedModel] = useState('')
    const [prompt, setPrompt] = useState('')
    const [loading, setLoading] = useState(false)
    const [showRegisterModal, setShowRegisterModal] = useState(false)
    const [registerForm, setRegisterForm] = useState({
        name: '',
        path: '',
        description: '',
        worker_id: ''
    })

    const loadCodebases = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/list`)
            if (response.ok) {
                const data = await response.json()
                const items = Array.isArray(data) ? data : (data?.codebases ?? [])
                setCodebases(
                    (items as any[])
                        .map((cb) => ({
                            id: String(cb?.id ?? ''),
                            name: String(cb?.name ?? cb?.id ?? ''),
                            path: String(cb?.path ?? ''),
                            description: typeof cb?.description === 'string' ? cb.description : undefined,
                            status: String(cb?.status ?? 'unknown'),
                            worker_id: typeof cb?.worker_id === 'string' ? cb.worker_id : undefined,
                        }))
                        .filter((cb) => cb.id)
                )
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    const loadWorkers = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/workers`)
            if (response.ok) {
                const data = await response.json()
                setWorkers(data || [])
            }
        } catch (error) {
            console.error('Failed to load workers:', error)
        }
    }, [])

    const loadModels = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/models`)
            if (response.ok) {
                const data = await response.json()
                setModels(data.models || [])
                if (data.default) setSelectedModel(data.default)
            }
        } catch (error) {
            console.error('Failed to load models:', error)
            // Fallback models
            setModels([
                { id: 'google/gemini-3-flash-preview', name: 'Gemini 3 Flash (Preview)', provider: 'Google' },
                { id: 'z-ai/coding-plain-v1', name: 'Z.AI Coding Plain v1', provider: 'Z.AI Coding Plan' },
                { id: 'z-ai/coding-plain-v2', name: 'Z.AI Coding Plain v2', provider: 'Z.AI Coding Plan' },
                { id: 'anthropic/claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'Anthropic' },
                { id: 'openai/gpt-4o', name: 'GPT-4o', provider: 'OpenAI' },
            ])
        }
    }, [])

    useEffect(() => {
        loadCodebases()
        loadWorkers()
        loadModels()
        const interval = setInterval(() => {
            loadCodebases()
            loadWorkers()
        }, 10000)
        return () => clearInterval(interval)
    }, [loadCodebases, loadWorkers, loadModels])

    const triggerAgent = async () => {
        if (!selectedCodebase || !prompt.trim()) return
        setLoading(true)
        try {
            const payload: { prompt: string; agent: string; model?: string } = { prompt, agent: selectedAgent }
            if (selectedModel) payload.model = selectedModel

            const response = await fetch(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            if (response.ok) {
                setPrompt('')
                alert('Agent triggered successfully!')
            }
        } catch (error) {
            console.error('Failed to trigger agent:', error)
            alert('Failed to trigger agent')
        } finally {
            setLoading(false)
        }
    }

    const registerCodebase = async () => {
        if (!registerForm.name || !registerForm.path) return
        try {
            const payload: { name: string; path: string; description?: string; worker_id?: string } = {
                name: registerForm.name,
                path: registerForm.path
            }
            if (registerForm.description) payload.description = registerForm.description
            if (registerForm.worker_id) payload.worker_id = registerForm.worker_id

            const response = await fetch(`${API_URL}/v1/opencode/codebases`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            if (response.ok) {
                setShowRegisterModal(false)
                setRegisterForm({ name: '', path: '', description: '', worker_id: '' })
                loadCodebases()
            }
        } catch (error) {
            console.error('Failed to register codebase:', error)
        }
    }

    const deleteCodebase = async (id: string) => {
        if (!confirm('Delete this codebase?')) return
        try {
            await fetch(`${API_URL}/v1/opencode/codebases/${id}`, { method: 'DELETE' })
            loadCodebases()
        } catch (error) {
            console.error('Failed to delete codebase:', error)
        }
    }

    const getStatusClasses = (status: string) => {
        const classes: Record<string, string> = {
            idle: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
            running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
            watching: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
            completed: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
            failed: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
            pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
        }
        return classes[status] || classes.idle
    }

    // Group models by provider and ensure unique IDs
    const seenModelIds = new Set<string>()
    const modelsByProvider = models.reduce((acc, m) => {
        if (seenModelIds.has(m.id)) return acc
        seenModelIds.add(m.id)
        const provider = m.provider || 'Other'
        if (!acc[provider]) acc[provider] = []
        acc[provider].push(m)
        return acc
    }, {} as Record<string, Model[]>)

    return (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            {/* Left sidebar - Codebases */}
            <div className="lg:col-span-1">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Codebases</h2>
                            <button
                                onClick={() => setShowRegisterModal(true)}
                                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                            >
                                <PlusIcon className="h-4 w-4 inline mr-1" />
                                Add
                            </button>
                        </div>
                    </div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[calc(100vh-300px)] overflow-y-auto">
                        {codebases.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
                                <p className="mt-2 text-sm">No codebases registered</p>
                            </div>
                        ) : (
                            codebases.map((cb) => (
                                <div
                                    key={cb.id}
                                    className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                                    onClick={() => setSelectedCodebase(cb.id)}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{cb.name}</p>
                                            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{cb.path}</p>
                                        </div>
                                        <span className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getStatusClasses(cb.status)}`}>
                                            {cb.status}
                                        </span>
                                    </div>
                                    {cb.worker_id && (
                                        <p className="mt-1 text-xs text-gray-400">Worker: {cb.worker_id}</p>
                                    )}
                                    <div className="mt-2 flex gap-2">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); deleteCodebase(cb.id) }}
                                            className="text-xs text-red-600 dark:text-red-400 hover:underline"
                                        >
                                            🗑️ Delete
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Main content - Trigger Agent */}
            <div className="lg:col-span-2">
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Trigger Agent</h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Select a codebase and run an AI agent</p>
                    </div>
                    <div className="p-6 space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Codebase
                            </label>
                            <select
                                value={selectedCodebase}
                                onChange={(e) => setSelectedCodebase(e.target.value)}
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                            >
                                <option value="">Select a codebase...</option>
                                {codebases.map((cb) => (
                                    <option key={cb.id} value={cb.id}>{cb.name}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Agent Type
                            </label>
                            <select
                                value={selectedAgent}
                                onChange={(e) => setSelectedAgent(e.target.value)}
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                            >
                                <option value="build">🔧 Build - Full access agent</option>
                                <option value="plan">📋 Plan - Read-only analysis</option>
                                <option value="coder">💻 Coder - Code writing focused</option>
                                <option value="explore">🔍 Explore - Codebase search</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Model
                            </label>
                            <select
                                value={selectedModel}
                                onChange={(e) => setSelectedModel(e.target.value)}
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                            >
                                <option value="">🤖 Default Model</option>
                                {Object.entries(modelsByProvider).map(([provider, providerModels]) => (
                                    <optgroup key={provider} label={provider}>
                                        {providerModels.map((m) => (
                                            <option key={m.id} value={m.id}>{m.name}</option>
                                        ))}
                                    </optgroup>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Prompt
                            </label>
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                rows={4}
                                placeholder="Enter your instructions for the AI agent..."
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 placeholder-gray-400"
                            />
                        </div>
                        <button
                            onClick={triggerAgent}
                            disabled={loading || !selectedCodebase || !prompt.trim()}
                            className="w-full rounded-md bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? '⏳ Running...' : '🚀 Run Agent'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Right sidebar - Quick Actions & Workers */}
            <div className="lg:col-span-1 space-y-6">
                {/* Workers Section */}
                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Active Workers</h3>
                    </div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-[300px] overflow-y-auto">
                        {workers.length === 0 ? (
                            <div className="p-4 text-center text-xs text-gray-500 dark:text-gray-400">
                                No workers connected
                            </div>
                        ) : (
                            workers.map((w) => (
                                <div key={w.worker_id} className="p-3">
                                    <div className="flex items-center justify-between">
                                        <div className="min-w-0 flex-1">
                                            <p className="text-xs font-medium text-gray-900 dark:text-white truncate">{w.name}</p>
                                            <p className="text-[10px] text-gray-500 dark:text-gray-400 truncate">{w.hostname || w.worker_id}</p>
                                        </div>
                                        <span className={`ml-2 h-2 w-2 rounded-full ${w.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}`} />
                                    </div>
                                    {w.global_codebase_id && (
                                        <button
                                            onClick={() => setSelectedCodebase(w.global_codebase_id!)}
                                            className="mt-2 w-full rounded bg-indigo-50 dark:bg-indigo-900/30 px-2 py-1 text-[10px] font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 flex items-center justify-center gap-1"
                                        >
                                            💬 Chat Directly
                                        </button>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Quick Actions</h3>
                    </div>
                    <div className="p-4 space-y-2">
                        <button
                            onClick={() => setShowRegisterModal(true)}
                            className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                        >
                            <span>📁</span> Register Codebase
                        </button>
                        <button
                            onClick={loadCodebases}
                            className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                        >
                            <RefreshIcon className="h-4 w-4" /> Refresh All
                        </button>
                    </div>
                </div>
            </div>

            {/* Register Modal */}
            {showRegisterModal && (
                <div className="fixed inset-0 z-50">
                    <div className="fixed inset-0 bg-gray-500/75 dark:bg-gray-900/75" onClick={() => setShowRegisterModal(false)} />
                    <div className="fixed inset-0 z-10 overflow-y-auto">
                        <div className="flex min-h-full items-center justify-center p-4">
                            <div className="relative w-full max-w-lg rounded-lg bg-white dark:bg-gray-800 shadow-xl">
                                <div className="p-6">
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Register Codebase</h3>
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                                            <input
                                                type="text"
                                                value={registerForm.name}
                                                onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                                                placeholder="my-project"
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Path</label>
                                            <input
                                                type="text"
                                                value={registerForm.path}
                                                onChange={(e) => setRegisterForm({ ...registerForm, path: e.target.value })}
                                                placeholder="/home/user/projects/my-project"
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description (optional)</label>
                                            <input
                                                type="text"
                                                value={registerForm.description}
                                                onChange={(e) => setRegisterForm({ ...registerForm, description: e.target.value })}
                                                placeholder="A brief description"
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Worker ID (optional)</label>
                                            <input
                                                type="text"
                                                value={registerForm.worker_id}
                                                onChange={(e) => setRegisterForm({ ...registerForm, worker_id: e.target.value })}
                                                placeholder="For remote codebases"
                                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                            />
                                        </div>
                                    </div>
                                    <div className="mt-6 flex gap-3 justify-end">
                                        <button
                                            onClick={() => setShowRegisterModal(false)}
                                            className="rounded-md px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={registerCodebase}
                                            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
                                        >
                                            Register
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
