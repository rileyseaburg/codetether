'use client'

import { useState } from 'react'
import { useRalphStore, type PRD, type UserStory } from './store'
import { ModelSelector } from '@/components/ModelSelector'

// ============================================================================
// Props
// ============================================================================

interface PRDBuilderProps {
    onPRDComplete: (prd: PRD) => void
    onCancel: () => void
}

// ============================================================================
// Icons
// ============================================================================

function PlusIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
    )
}

function TrashIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
    )
}

function ChevronUpIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
    )
}

function ChevronDownIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
    )
}

function SparklesIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
    )
}

// ============================================================================
// Story Templates
// ============================================================================

const storyTemplates = [
    {
        category: 'Database',
        templates: [
            {
                title: 'Add database column',
                description: 'As a developer, I need to add a new column to store {data}',
                acceptanceCriteria: ['Migration file created', 'Column has correct type and constraints', 'Existing data is preserved', 'Typecheck passes']
            },
            {
                title: 'Create new table',
                description: 'As a developer, I need a new table to store {entity} data',
                acceptanceCriteria: ['Migration creates table with all columns', 'Primary key and indexes defined', 'Foreign keys set up correctly', 'Typecheck passes']
            }
        ]
    },
    {
        category: 'API',
        templates: [
            {
                title: 'Create GET endpoint',
                description: 'As a user, I want to retrieve {resource} via API',
                acceptanceCriteria: ['GET endpoint returns correct data', 'Pagination implemented', 'Error handling for not found', 'Typecheck passes']
            },
            {
                title: 'Create POST endpoint',
                description: 'As a user, I want to create {resource} via API',
                acceptanceCriteria: ['POST endpoint creates resource', 'Input validation implemented', 'Returns created resource', 'Typecheck passes']
            },
            {
                title: 'Create PUT endpoint',
                description: 'As a user, I want to update {resource} via API',
                acceptanceCriteria: ['PUT endpoint updates resource', 'Validates ownership/permissions', 'Returns updated resource', 'Typecheck passes']
            },
            {
                title: 'Create DELETE endpoint',
                description: 'As a user, I want to delete {resource} via API',
                acceptanceCriteria: ['DELETE endpoint removes resource', 'Validates ownership/permissions', 'Handles cascading deletes', 'Typecheck passes']
            }
        ]
    },
    {
        category: 'UI Component',
        templates: [
            {
                title: 'Create form component',
                description: 'As a user, I want a form to {action}',
                acceptanceCriteria: ['Form renders all required fields', 'Validation shows errors', 'Submit calls API correctly', 'Loading state shown', 'Typecheck passes']
            },
            {
                title: 'Create list component',
                description: 'As a user, I want to see a list of {items}',
                acceptanceCriteria: ['List renders items correctly', 'Empty state shown when no items', 'Loading skeleton shown', 'Pagination or infinite scroll works', 'Typecheck passes']
            },
            {
                title: 'Create detail view',
                description: 'As a user, I want to view details of {item}',
                acceptanceCriteria: ['All fields displayed correctly', 'Edit/delete actions available', 'Loading state handled', 'Not found state handled', 'Typecheck passes']
            },
            {
                title: 'Add filter/search',
                description: 'As a user, I want to filter {items} by {criteria}',
                acceptanceCriteria: ['Filter UI renders correctly', 'Filtering updates results', 'Filter state persists in URL', 'Clear filter works', 'Typecheck passes']
            }
        ]
    },
    {
        category: 'Authentication',
        templates: [
            {
                title: 'Add authentication check',
                description: 'As a developer, I need to protect {route} with authentication',
                acceptanceCriteria: ['Unauthenticated users redirected to login', 'Authenticated users can access', 'Session validated on server', 'Typecheck passes']
            },
            {
                title: 'Add role-based access',
                description: 'As an admin, I want to restrict {feature} to {role} users',
                acceptanceCriteria: ['Role check implemented', 'Unauthorized users see error', 'UI hides restricted features', 'Typecheck passes']
            }
        ]
    },
    {
        category: 'Integration',
        templates: [
            {
                title: 'Add email notification',
                description: 'As a user, I want to receive email when {event}',
                acceptanceCriteria: ['Email template created', 'Email sent on trigger', 'Unsubscribe option works', 'Typecheck passes']
            },
            {
                title: 'Add webhook integration',
                description: 'As a developer, I need to send webhook when {event}',
                acceptanceCriteria: ['Webhook payload defined', 'Webhook sent on trigger', 'Retry logic implemented', 'Typecheck passes']
            }
        ]
    }
]

// ============================================================================
// Component
// ============================================================================

export function PRDBuilder({ onPRDComplete, onCancel }: PRDBuilderProps) {
    // Get shared state from Zustand store (only what we need locally)
    const { selectedCodebase, setSelectedCodebase } = useRalphStore()
    
    // Local state for builder
    const [step, setStep] = useState<'project' | 'stories' | 'review'>('project')
    const [project, setProject] = useState('')
    const [description, setDescription] = useState('')
    const [branchName, setBranchName] = useState('')
    const [stories, setStories] = useState<UserStory[]>([])
    const [showTemplates, setShowTemplates] = useState(false)
    const [editingStory, setEditingStory] = useState<string | null>(null)
    const [newCriterion, setNewCriterion] = useState<Record<string, string>>({})

    // Auto-generate branch name from project
    const handleProjectChange = (value: string) => {
        setProject(value)
        if (!branchName || branchName.startsWith('ralph/')) {
            const kebab = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
            setBranchName(`ralph/${kebab}`)
        }
    }

    // Add story from template
    const addFromTemplate = (template: { title: string; description: string; acceptanceCriteria: string[] }) => {
        const newId = `US-${String(stories.length + 1).padStart(3, '0')}`
        setStories([...stories, {
            id: newId,
            title: template.title,
            description: template.description,
            acceptanceCriteria: [...template.acceptanceCriteria],
            priority: stories.length + 1,
            passes: false
        }])
        setShowTemplates(false)
    }

    // Add blank story
    const addBlankStory = () => {
        const newId = `US-${String(stories.length + 1).padStart(3, '0')}`
        setStories([...stories, {
            id: newId,
            title: '',
            description: 'As a user, I want to ',
            acceptanceCriteria: ['Typecheck passes'],
            priority: stories.length + 1,
            passes: false
        }])
        setEditingStory(newId)
    }

    // Update story
    const updateStory = (id: string, updates: Partial<UserStory>) => {
        setStories(stories.map(s => s.id === id ? { ...s, ...updates } : s))
    }

    // Delete story
    const deleteStory = (id: string) => {
        const filtered = stories.filter(s => s.id !== id)
        // Re-number priorities
        setStories(filtered.map((s, i) => ({ ...s, priority: i + 1 })))
    }

    // Move story up/down
    const moveStory = (id: string, direction: 'up' | 'down') => {
        const index = stories.findIndex(s => s.id === id)
        if (direction === 'up' && index > 0) {
            const newStories = [...stories]
            ;[newStories[index - 1], newStories[index]] = [newStories[index], newStories[index - 1]]
            setStories(newStories.map((s, i) => ({ ...s, priority: i + 1 })))
        } else if (direction === 'down' && index < stories.length - 1) {
            const newStories = [...stories]
            ;[newStories[index], newStories[index + 1]] = [newStories[index + 1], newStories[index]]
            setStories(newStories.map((s, i) => ({ ...s, priority: i + 1 })))
        }
    }

    // Add acceptance criterion
    const addCriterion = (storyId: string) => {
        const criterion = newCriterion[storyId]?.trim()
        if (criterion) {
            const story = stories.find(s => s.id === storyId)
            if (story) {
                updateStory(storyId, {
                    acceptanceCriteria: [...story.acceptanceCriteria, criterion]
                })
                setNewCriterion({ ...newCriterion, [storyId]: '' })
            }
        }
    }

    // Remove acceptance criterion
    const removeCriterion = (storyId: string, index: number) => {
        const story = stories.find(s => s.id === storyId)
        if (story) {
            updateStory(storyId, {
                acceptanceCriteria: story.acceptanceCriteria.filter((_, i) => i !== index)
            })
        }
    }

    // Build final PRD
    const buildPRD = (): PRD => ({
        project,
        branchName,
        description,
        userStories: stories
    })

    // Validate current step
    const canProceed = () => {
        if (step === 'project') {
            return project.trim() && description.trim() && branchName.trim()
        }
        if (step === 'stories') {
            return stories.length > 0 && stories.every(s => s.title.trim() && s.description.trim())
        }
        return true
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-xl bg-white dark:bg-gray-800 shadow-2xl flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">PRD Builder</h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {step === 'project' && 'Step 1: Define your project'}
                            {step === 'stories' && 'Step 2: Add user stories'}
                            {step === 'review' && 'Step 3: Review and create'}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Progress dots */}
                        <div className="flex gap-1.5">
                            <div className={`h-2 w-2 rounded-full ${step === 'project' ? 'bg-cyan-500' : 'bg-cyan-500'}`} />
                            <div className={`h-2 w-2 rounded-full ${step === 'stories' || step === 'review' ? 'bg-cyan-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
                            <div className={`h-2 w-2 rounded-full ${step === 'review' ? 'bg-cyan-500' : 'bg-gray-300 dark:bg-gray-600'}`} />
                        </div>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {/* Step 1: Project Details */}
                    {step === 'project' && (
                        <div className="space-y-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Project Name *
                                </label>
                                <input
                                    type="text"
                                    value={project}
                                    onChange={(e) => handleProjectChange(e.target.value)}
                                    placeholder="MyApp"
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Feature Description *
                                </label>
                                <textarea
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    placeholder="Describe what this feature does..."
                                    rows={3}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent resize-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Branch Name *
                                </label>
                                <input
                                    type="text"
                                    value={branchName}
                                    onChange={(e) => setBranchName(e.target.value)}
                                    placeholder="ralph/feature-name"
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent font-mono text-sm"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Ralph will create this branch and commit to it
                                </p>
                            </div>

                            {/* Tips */}
                            <div className="p-4 bg-cyan-50 dark:bg-cyan-900/20 rounded-lg border border-cyan-200 dark:border-cyan-800">
                                <h4 className="text-sm font-medium text-cyan-800 dark:text-cyan-300 mb-2">Tips for good PRDs</h4>
                                <ul className="text-xs text-cyan-700 dark:text-cyan-400 space-y-1">
                                    <li>• Keep stories small - each should be completable in one iteration</li>
                                    <li>• Order by dependency - database changes before API, API before UI</li>
                                    <li>• Be specific in acceptance criteria - vague criteria lead to failures</li>
                                    <li>• Always include &quot;Typecheck passes&quot; as a criterion</li>
                                </ul>
                            </div>
                        </div>
                    )}

                    {/* Step 2: User Stories */}
                    {step === 'stories' && (
                        <div className="space-y-4">
                            {/* Add Story Buttons */}
                            <div className="flex gap-2">
                                <button
                                    onClick={addBlankStory}
                                    className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 text-sm font-medium"
                                >
                                    <PlusIcon className="h-4 w-4" />
                                    Add Story
                                </button>
                                <button
                                    onClick={() => setShowTemplates(!showTemplates)}
                                    className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-medium"
                                >
                                    <SparklesIcon className="h-4 w-4" />
                                    From Template
                                </button>
                            </div>

                            {/* Templates Panel */}
                            {showTemplates && (
                                <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Story Templates</h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {storyTemplates.map((category) => (
                                            <div key={category.category}>
                                                <h5 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{category.category}</h5>
                                                <div className="space-y-1">
                                                    {category.templates.map((template, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => addFromTemplate(template)}
                                                            className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                                                        >
                                                            {template.title}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Stories List */}
                            {stories.length === 0 ? (
                                <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                                    <p>No stories yet. Add a story or use a template to get started.</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {stories.map((story, index) => (
                                        <div
                                            key={story.id}
                                            className={`p-4 rounded-lg border ${
                                                editingStory === story.id
                                                    ? 'border-cyan-500 bg-cyan-50 dark:bg-cyan-900/20'
                                                    : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900'
                                            }`}
                                        >
                                            {/* Story Header */}
                                            <div className="flex items-start justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs font-mono rounded">
                                                        {story.id}
                                                    </span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        Priority {story.priority}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <button
                                                        onClick={() => moveStory(story.id, 'up')}
                                                        disabled={index === 0}
                                                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                                                    >
                                                        <ChevronUpIcon className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => moveStory(story.id, 'down')}
                                                        disabled={index === stories.length - 1}
                                                        className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                                                    >
                                                        <ChevronDownIcon className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => setEditingStory(editingStory === story.id ? null : story.id)}
                                                        className="px-2 py-1 text-xs text-cyan-600 hover:text-cyan-500"
                                                    >
                                                        {editingStory === story.id ? 'Done' : 'Edit'}
                                                    </button>
                                                    <button
                                                        onClick={() => deleteStory(story.id)}
                                                        className="p-1 text-red-400 hover:text-red-600"
                                                    >
                                                        <TrashIcon className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Story Content */}
                                            {editingStory === story.id ? (
                                                <div className="space-y-3">
                                                    <input
                                                        type="text"
                                                        value={story.title}
                                                        onChange={(e) => updateStory(story.id, { title: e.target.value })}
                                                        placeholder="Story title"
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm"
                                                    />
                                                    <textarea
                                                        value={story.description}
                                                        onChange={(e) => updateStory(story.id, { description: e.target.value })}
                                                        placeholder="As a user, I want to..."
                                                        rows={2}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-sm resize-none"
                                                    />
                                                    <div>
                                                        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                                                            Acceptance Criteria
                                                        </label>
                                                        <div className="space-y-1">
                                                            {story.acceptanceCriteria.map((criterion, i) => (
                                                                <div key={i} className="flex items-center gap-2">
                                                                    <span className="flex-1 text-sm text-gray-600 dark:text-gray-300">• {criterion}</span>
                                                                    <button
                                                                        onClick={() => removeCriterion(story.id, i)}
                                                                        className="text-red-400 hover:text-red-600 text-xs"
                                                                    >
                                                                        Remove
                                                                    </button>
                                                                </div>
                                                            ))}
                                                        </div>
                                                        <div className="flex gap-2 mt-2">
                                                            <input
                                                                type="text"
                                                                value={newCriterion[story.id] || ''}
                                                                onChange={(e) => setNewCriterion({ ...newCriterion, [story.id]: e.target.value })}
                                                                onKeyDown={(e) => e.key === 'Enter' && addCriterion(story.id)}
                                                                placeholder="Add criterion..."
                                                                className="flex-1 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800"
                                                            />
                                                            <button
                                                                onClick={() => addCriterion(story.id)}
                                                                className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-sm hover:bg-gray-200 dark:hover:bg-gray-600"
                                                            >
                                                                Add
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div>
                                                    <h4 className="font-medium text-gray-900 dark:text-white">{story.title || '(untitled)'}</h4>
                                                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{story.description}</p>
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {story.acceptanceCriteria.slice(0, 3).map((c, i) => (
                                                            <span key={i} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded">
                                                                {c.length > 30 ? c.slice(0, 30) + '...' : c}
                                                            </span>
                                                        ))}
                                                        {story.acceptanceCriteria.length > 3 && (
                                                            <span className="px-2 py-0.5 text-gray-500 text-xs">
                                                                +{story.acceptanceCriteria.length - 3} more
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Step 3: Review */}
                    {step === 'review' && (
                        <div className="space-y-6">
                            <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Project</h4>
                                <p className="text-lg font-semibold text-gray-900 dark:text-white">{project}</p>
                                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{description}</p>
                                <p className="text-xs text-cyan-600 dark:text-cyan-400 font-mono mt-2">{branchName}</p>
                            </div>

                            {/* Model Selection */}
                            <ModelSelector visualVariant="card" />

                            <div>
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                                    User Stories ({stories.length})
                                </h4>
                                <div className="space-y-2">
                                    {stories.map((story) => (
                                        <div key={story.id} className="flex items-start gap-3 p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
                                            <span className="px-2 py-1 bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300 text-xs font-mono rounded">
                                                {story.id}
                                            </span>
                                            <div className="flex-1">
                                                <h5 className="font-medium text-gray-900 dark:text-white text-sm">{story.title}</h5>
                                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{story.description}</p>
                                                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                                                    {story.acceptanceCriteria.length} acceptance criteria
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* JSON Preview */}
                            <div>
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Generated prd.json</h4>
                                <pre className="p-4 bg-gray-900 text-gray-100 rounded-lg text-xs font-mono overflow-x-auto max-h-48">
                                    {JSON.stringify(buildPRD(), null, 2)}
                                </pre>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                    <button
                        onClick={step === 'project' ? onCancel : () => setStep(step === 'review' ? 'stories' : 'project')}
                        className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                    >
                        {step === 'project' ? 'Cancel' : 'Back'}
                    </button>
                    <div className="flex gap-2">
                        {step === 'review' ? (
                            <button
                                onClick={() => onPRDComplete(buildPRD())}
                                className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 text-sm font-medium"
                            >
                                Create PRD & Start Ralph
                            </button>
                        ) : (
                            <button
                                onClick={() => setStep(step === 'project' ? 'stories' : 'review')}
                                disabled={!canProceed()}
                                className="px-6 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Continue
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
