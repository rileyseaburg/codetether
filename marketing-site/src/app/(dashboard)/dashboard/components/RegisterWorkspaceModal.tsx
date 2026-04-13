// RegisterWorkspaceModal - Single Responsibility: Workspace registration form modal

import { useState } from 'react'
import { WorkerSelector } from '@/components/WorkerSelector'
import type { Worker, RegisterForm } from '../types'

interface RegisterWorkspaceModalProps {
    isOpen: boolean
    onClose: () => void
    onSubmit: (form: RegisterForm) => void
    workers: Worker[]
    mode: 'local' | 'git' | 'external'
    runtime: 'container' | 'vm'
    form: RegisterForm
    onFormChange: (form: RegisterForm) => void
    canSubmit: boolean
    submitLabel: string
}

export function RegisterWorkspaceModal({
    isOpen,
    onClose,
    onSubmit,
    workers,
    mode,
    runtime,
    form,
    onFormChange,
    canSubmit,
    submitLabel,
}: RegisterWorkspaceModalProps) {
    if (!isOpen) return null

    const effectiveRuntime = runtime

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div className="p-6">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                        Register Workspace
                    </h2>

                    <div className="space-y-4">
                        {/* Name */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Name
                            </label>
                            <input
                                type="text"
                                value={form.name}
                                onChange={(e) => onFormChange({ ...form, name: e.target.value })}
                                placeholder="my-project"
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            />
                        </div>

                        {/* Path */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Path
                            </label>
                            <input
                                type="text"
                                value={form.path}
                                onChange={(e) => onFormChange({ ...form, path: e.target.value })}
                                placeholder="/path/to/project"
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            />
                        </div>

                        {/* Git URL (git mode) */}
                        {mode === 'git' && (
                            <>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Git URL
                                    </label>
                                    <input
                                        type="text"
                                        value={form.git_url}
                                        onChange={(e) => onFormChange({ ...form, git_url: e.target.value })}
                                        placeholder="https://github.com/user/repo.git"
                                        className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Branch
                                    </label>
                                    <input
                                        type="text"
                                        value={form.git_branch}
                                        onChange={(e) => onFormChange({ ...form, git_branch: e.target.value })}
                                        placeholder="main"
                                        className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                    />
                                </div>
                            </>
                        )}

                        {/* External mode */}
                        {mode === 'external' && (
                            <>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        External Provider
                                    </label>
                                    <input
                                        type="text"
                                        value={form.external_provider}
                                        onChange={(e) => onFormChange({ ...form, external_provider: e.target.value })}
                                        placeholder="Canva, HubSpot, Salesforce..."
                                        className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        External Reference
                                    </label>
                                    <input
                                        type="text"
                                        value={form.external_reference}
                                        onChange={(e) => onFormChange({ ...form, external_reference: e.target.value })}
                                        placeholder="campaign-2026-q1"
                                        className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                    />
                                </div>
                            </>
                        )}

                        {/* Description */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Description (optional)
                            </label>
                            <input
                                type="text"
                                value={form.description}
                                onChange={(e) => onFormChange({ ...form, description: e.target.value })}
                                placeholder="A brief description"
                                className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            />
                        </div>

                        {/* Worker selector */}
                        {effectiveRuntime !== 'vm' && mode !== 'external' && (
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Worker
                                </label>
                                <WorkerSelector
                                    value={form.worker_id}
                                    onChange={(worker_id) => onFormChange({ ...form, worker_id })}
                                    workers={workers}
                                    onlyConnected={false}
                                    disableDisconnected={false}
                                    includeAutoOption
                                    autoOptionLabel="Auto-assign"
                                    className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Registered standalone workers remain selectable here even when they are currently offline.
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Actions */}
                    <div className="mt-6 flex gap-3 justify-end">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={() => onSubmit(form)}
                            disabled={!canSubmit}
                            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {submitLabel}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
