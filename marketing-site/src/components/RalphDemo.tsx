'use client'

import { useState, useEffect, useRef } from 'react'
import { Container } from '@/components/Container'

interface UserStory {
    id: string
    title: string
    status: 'pending' | 'running' | 'passed' | 'failed'
    iteration?: number
    commitHash?: string
}

interface RalphEvent {
    id: string
    type: 'start' | 'story_start' | 'code' | 'check' | 'commit' | 'story_pass' | 'story_fail' | 'learning' | 'complete' | 'rlm_trigger' | 'rlm_load' | 'rlm_analyze' | 'rlm_subcall' | 'rlm_complete'
    content: string
    storyId?: string
    duration?: number
}

const demoPRD = {
    project: "TaskApp",
    branch: "ralph/task-status",
    description: "Add task status tracking with filters",
    stories: [
        { id: "US-001", title: "Add status field to database", status: 'pending' as const },
        { id: "US-002", title: "Display status badge on cards", status: 'pending' as const },
        { id: "US-003", title: "Add status toggle to list", status: 'pending' as const },
        { id: "US-004", title: "Filter tasks by status", status: 'pending' as const },
    ],
}

const demoEvents: RalphEvent[] = [
    {
        id: '1',
        type: 'start',
        content: `Starting Ralph autonomous loop
Project: ${demoPRD.project}
Branch: ${demoPRD.branch}
Stories: ${demoPRD.stories.length} to complete
RLM: Enabled (threshold: 80K tokens)`,
        duration: 2.0,
    },
    {
        id: '2',
        type: 'story_start',
        storyId: 'US-001',
        content: `Iteration 1: US-001 - Add status field to database
Spawning fresh OpenCode instance...
Context: 2,340 tokens (progress.txt empty)`,
        duration: 2.5,
    },
    {
        id: '3',
        type: 'code',
        storyId: 'US-001',
        content: `Creating migration file...
ALTER TABLE tasks ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
Valid values: 'pending', 'in_progress', 'done'`,
        duration: 3.0,
    },
    {
        id: '4',
        type: 'check',
        storyId: 'US-001',
        content: `Running quality checks...
$ npx tsc --noEmit ✓
$ npm run test:migrations ✓
All checks passed!`,
        duration: 2.5,
    },
    {
        id: '5',
        type: 'commit',
        storyId: 'US-001',
        content: `git add -A && git commit -m "feat(US-001): Add status field"
[ralph/task-status a3f7b2c] feat(US-001): Add status field
 2 files changed, 45 insertions(+)`,
        duration: 1.5,
    },
    {
        id: '6',
        type: 'story_pass',
        storyId: 'US-001',
        content: `US-001 PASSED ✓
Updating prd.json: passes: true`,
        duration: 1.0,
    },
    {
        id: '7',
        type: 'learning',
        storyId: 'US-001',
        content: `Appending to progress.txt (now 8,420 tokens):
---
### US-001 PASSED
- Database uses PostgreSQL with ENUM types
- Migration pattern: timestamp_description.sql  
- Test command: npm run test:migrations
- Gotcha: Remember to run migrations before tests`,
        duration: 1.5,
    },
    {
        id: '8',
        type: 'story_start',
        storyId: 'US-002',
        content: `Iteration 2: US-002 - Display status badge on cards
Fresh OpenCode instance (no memory of iteration 1)
Reading progress.txt for context... 8,420 tokens loaded`,
        duration: 2.5,
    },
    {
        id: '9',
        type: 'code',
        storyId: 'US-002',
        content: `Creating StatusBadge component...
export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <Badge color={statusColors[status]}>
      {status.replace('_', ' ')}
    </Badge>
  )
}`,
        duration: 3.0,
    },
    {
        id: '10',
        type: 'check',
        storyId: 'US-002',
        content: `Running quality checks...
$ npx tsc --noEmit ✓
$ npm run test:components ✓
All checks passed!`,
        duration: 2.0,
    },
    {
        id: '11',
        type: 'commit',
        storyId: 'US-002',
        content: `git commit -m "feat(US-002): Add status badge component"
[ralph/task-status b8e4c1d] feat(US-002): Add status badge
 3 files changed, 89 insertions(+)`,
        duration: 1.5,
    },
    {
        id: '12',
        type: 'story_pass',
        storyId: 'US-002',
        content: `US-002 PASSED ✓ (2/4 stories complete)`,
        duration: 1.0,
    },
    {
        id: '13',
        type: 'learning',
        storyId: 'US-002',
        content: `Appending to progress.txt (now 45,230 tokens):
---
### US-002 PASSED  
- Component path: src/components/StatusBadge.tsx
- Uses existing Badge from @/components/ui
- Color map in src/lib/constants.ts
- 12 tool calls, 3 file edits recorded`,
        duration: 1.5,
    },
    // RLM KICKS IN HERE - this is the key integration point
    {
        id: '14',
        type: 'rlm_trigger',
        content: `⚠️ Context threshold approaching!
progress.txt: 85,420 tokens (exceeds 80K threshold)
Triggering RLM compression before next iteration...`,
        duration: 2.0,
    },
    {
        id: '15',
        type: 'rlm_load',
        content: `RLM: Loading context into REPL environment
$ context = load("progress.txt")  # 85,420 tokens
$ context_type = "conversation"
Variable 'context' ready for analysis`,
        duration: 2.5,
    },
    {
        id: '16',
        type: 'rlm_analyze',
        content: `RLM: Executing analysis code...
\`\`\`python
lines = context.split("\\n")
print(f"Total: {len(lines)} lines")
# Find key patterns
files_modified = grep(r"src/.*\\.tsx?")
errors = grep(r"error|failed", ignore_case=True)
decisions = grep(r"Gotcha|Remember|Pattern")
\`\`\`
Found: 23 files, 0 errors, 8 key decisions`,
        duration: 3.0,
    },
    {
        id: '17',
        type: 'rlm_subcall',
        content: `RLM: Sub-LM call for semantic compression
Prompt: "Summarize key learnings, preserve file paths..."
Sub-call 1/2: Analyzing iterations 1-2...
Sub-call 2/2: Extracting patterns and gotchas...`,
        duration: 3.5,
    },
    {
        id: '18',
        type: 'rlm_complete',
        content: `RLM: Compression complete!
85,420 → 24,180 tokens (3.5x compression)
Preserved: 23 file paths, 8 decisions, 0 errors
progress.txt updated with compressed context`,
        duration: 2.0,
    },
    {
        id: '19',
        type: 'story_start',
        storyId: 'US-003',
        content: `Iteration 3: US-003 - Add status toggle to list
Fresh OpenCode instance
Loading compressed progress.txt... 24,180 tokens
(Would have been 85K without RLM!)`,
        duration: 2.5,
    },
    {
        id: '20',
        type: 'code',
        storyId: 'US-003',
        content: `Adding StatusToggle to TaskRow...
onClick={() => updateTaskStatus(task.id, nextStatus)}
Using optimistic UI update with rollback on error
(Found pattern in progress.txt: use existing Badge)`,
        duration: 3.0,
    },
    {
        id: '21',
        type: 'commit',
        storyId: 'US-003',
        content: `git commit -m "feat(US-003): Add inline status toggle"
[ralph/task-status c9f5d2e] feat(US-003): Add inline status
 2 files changed, 67 insertions(+)`,
        duration: 1.5,
    },
    {
        id: '22',
        type: 'story_pass',
        storyId: 'US-003',
        content: `US-003 PASSED ✓ (3/4 stories complete)`,
        duration: 1.0,
    },
    {
        id: '23',
        type: 'story_start',
        storyId: 'US-004',
        content: `Iteration 4: US-004 - Filter tasks by status
Final story! Context: 38,450 tokens (still under threshold)`,
        duration: 2.5,
    },
    {
        id: '24',
        type: 'code',
        storyId: 'US-004',
        content: `Adding StatusFilter dropdown...
const [filter, setFilter] = useQueryState('status')
<Select value={filter} onValueChange={setFilter}>
  <Option value="">All</Option>
  <Option value="pending">Pending</Option>
  <Option value="in_progress">In Progress</Option>
  <Option value="done">Done</Option>
</Select>`,
        duration: 3.0,
    },
    {
        id: '25',
        type: 'commit',
        storyId: 'US-004',
        content: `git commit -m "feat(US-004): Add status filter dropdown"
[ralph/task-status d0a6e3f] feat(US-004): Add status filter
 2 files changed, 54 insertions(+)`,
        duration: 1.5,
    },
    {
        id: '26',
        type: 'story_pass',
        storyId: 'US-004',
        content: `US-004 PASSED ✓ - All stories complete!`,
        duration: 1.0,
    },
    {
        id: '27',
        type: 'complete',
        content: `<promise>COMPLETE</promise>

Ralph + RLM finished successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Iterations: 4
Stories: 4/4 passed  
Commits: 4
RLM compressions: 1 (saved 61K tokens)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Branch ready: ralph/task-status`,
        duration: 2.5,
    },
]

export function RalphDemo() {
    const [isRunning, setIsRunning] = useState(false)
    const [currentEvent, setCurrentEvent] = useState(0)
    const [completedEvents, setCompletedEvents] = useState<RalphEvent[]>([])
    const [stories, setStories] = useState<UserStory[]>(demoPRD.stories)
    const [stats, setStats] = useState({ iterations: 0, passed: 0, commits: 0, rlmCompressions: 0, tokensSaved: 0 })
    const scrollRef = useRef<HTMLDivElement>(null)

    const runDemo = () => {
        setIsRunning(true)
        setCurrentEvent(0)
        setCompletedEvents([])
        setStories(demoPRD.stories.map(s => ({ ...s, status: 'pending' as const })))
        setStats({ iterations: 0, passed: 0, commits: 0, rlmCompressions: 0, tokensSaved: 0 })
    }

    const resetDemo = () => {
        setIsRunning(false)
        setCurrentEvent(0)
        setCompletedEvents([])
        setStories(demoPRD.stories.map(s => ({ ...s, status: 'pending' as const })))
        setStats({ iterations: 0, passed: 0, commits: 0, rlmCompressions: 0, tokensSaved: 0 })
    }

    useEffect(() => {
        if (!isRunning) return
        if (currentEvent >= demoEvents.length) {
            setIsRunning(false)
            return
        }

        const event = demoEvents[currentEvent]
        const delay = (event.duration || 0.5) * 1000

        const timer = setTimeout(() => {
            setCompletedEvents(prev => [...prev, event])
            
            // Update stories and stats based on event type
            if (event.type === 'story_start' && event.storyId) {
                setStories(prev => prev.map(s => 
                    s.id === event.storyId ? { ...s, status: 'running' as const } : s
                ))
                setStats(s => ({ ...s, iterations: s.iterations + 1 }))
            }
            if (event.type === 'story_pass' && event.storyId) {
                setStories(prev => prev.map(s => 
                    s.id === event.storyId ? { ...s, status: 'passed' as const } : s
                ))
                setStats(s => ({ ...s, passed: s.passed + 1 }))
            }
            if (event.type === 'commit') {
                setStats(s => ({ ...s, commits: s.commits + 1 }))
            }
            if (event.type === 'rlm_complete') {
                setStats(s => ({ ...s, rlmCompressions: s.rlmCompressions + 1, tokensSaved: s.tokensSaved + 61240 }))
            }
            
            setCurrentEvent(prev => prev + 1)
        }, delay)

        return () => clearTimeout(timer)
    }, [isRunning, currentEvent])

    // Auto-scroll
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [completedEvents])

    const typeConfig: Record<string, { icon: string; label: string; color: string }> = {
        start: { icon: '🚀', label: 'Start', color: 'border-blue-500/50 bg-blue-950/50' },
        story_start: { icon: '📋', label: 'Story', color: 'border-yellow-500/50 bg-yellow-950/50' },
        code: { icon: '💻', label: 'Code', color: 'border-green-500/50 bg-green-950/50' },
        check: { icon: '✓', label: 'Check', color: 'border-cyan-500/50 bg-cyan-950/50' },
        commit: { icon: '📦', label: 'Commit', color: 'border-purple-500/50 bg-purple-950/50' },
        story_pass: { icon: '✅', label: 'Pass', color: 'border-emerald-500/50 bg-emerald-950/50' },
        story_fail: { icon: '❌', label: 'Fail', color: 'border-red-500/50 bg-red-950/50' },
        learning: { icon: '📝', label: 'Memory', color: 'border-orange-500/50 bg-orange-950/50' },
        rlm_trigger: { icon: '⚠️', label: 'RLM Trigger', color: 'border-pink-500/50 bg-pink-950/50' },
        rlm_load: { icon: '📥', label: 'RLM Load', color: 'border-pink-500/50 bg-pink-950/50' },
        rlm_analyze: { icon: '🔬', label: 'RLM Analyze', color: 'border-pink-500/50 bg-pink-950/50' },
        rlm_subcall: { icon: '🔄', label: 'RLM Sub-LM', color: 'border-pink-500/50 bg-pink-950/50' },
        rlm_complete: { icon: '🗜️', label: 'RLM Done', color: 'border-pink-500/50 bg-pink-950/50' },
        complete: { icon: '🎉', label: 'Done', color: 'border-emerald-500/50 bg-emerald-950/50' },
    }

    const isRlmEvent = (type: string) => type.startsWith('rlm_')

    return (
        <section id="ralph-demo" className="py-20 sm:py-28 bg-gray-950">
            <Container>
                <div className="mx-auto max-w-5xl">
                    {/* Header */}
                    <div className="text-center mb-12">
                        <span className="inline-flex items-center rounded-full bg-gradient-to-r from-purple-950 to-pink-950 px-4 py-1.5 text-sm font-medium text-purple-300 ring-1 ring-inset ring-purple-500/20 mb-4">
                            Ralph + RLM Integration
                        </span>
                        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                            Watch a Feature Build Itself
                        </h2>
                        <p className="mt-4 text-lg text-gray-400 max-w-2xl mx-auto">
                            Ralph runs AI agents in a loop until your PRD is complete.
                            When context grows too large, <span className="text-pink-400 font-medium">RLM compresses it</span> so the next iteration can continue.
                        </p>
                    </div>

                    <div className="grid lg:grid-cols-3 gap-6">
                        {/* PRD Panel */}
                        <div className="lg:col-span-1">
                            <div className="rounded-xl bg-gray-900 border border-gray-800 overflow-hidden h-full">
                                <div className="px-4 py-3 bg-gray-800 border-b border-gray-700">
                                    <h3 className="text-sm font-medium text-white flex items-center gap-2">
                                        <span>📄</span> prd.json
                                    </h3>
                                </div>
                                <div className="p-4 space-y-4">
                                    <div>
                                        <p className="text-xs text-gray-500 mb-1">Project</p>
                                        <p className="text-sm text-white font-mono">{demoPRD.project}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-500 mb-1">Branch</p>
                                        <p className="text-sm text-cyan-400 font-mono">{demoPRD.branch}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-500 mb-2">User Stories</p>
                                        <div className="space-y-2">
                                            {stories.map((story) => (
                                                <div 
                                                    key={story.id}
                                                    className={`flex items-center gap-2 p-2 rounded-lg text-xs font-mono transition-all ${
                                                        story.status === 'passed' 
                                                            ? 'bg-emerald-950/50 border border-emerald-500/30' 
                                                            : story.status === 'running'
                                                            ? 'bg-yellow-950/50 border border-yellow-500/30 animate-pulse'
                                                            : 'bg-gray-800/50 border border-gray-700/50'
                                                    }`}
                                                >
                                                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                                                        story.status === 'passed' ? 'bg-emerald-500 text-white' :
                                                        story.status === 'running' ? 'bg-yellow-500 text-black' :
                                                        'bg-gray-600 text-gray-300'
                                                    }`}>
                                                        {story.status === 'passed' ? '✓' : 
                                                         story.status === 'running' ? '→' : '○'}
                                                    </span>
                                                    <span className={`flex-1 ${
                                                        story.status === 'passed' ? 'text-emerald-300' :
                                                        story.status === 'running' ? 'text-yellow-300' :
                                                        'text-gray-400'
                                                    }`}>
                                                        {story.id}: {story.title}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    
                                    {/* RLM Status */}
                                    <div className="pt-3 border-t border-gray-700">
                                        <p className="text-xs text-gray-500 mb-2">RLM Status</p>
                                        <div className={`p-2 rounded-lg text-xs font-mono ${
                                            stats.rlmCompressions > 0 
                                                ? 'bg-pink-950/50 border border-pink-500/30' 
                                                : 'bg-gray-800/50 border border-gray-700/50'
                                        }`}>
                                            <div className="flex justify-between">
                                                <span className="text-gray-400">Compressions:</span>
                                                <span className="text-pink-400">{stats.rlmCompressions}</span>
                                            </div>
                                            {stats.tokensSaved > 0 && (
                                                <div className="flex justify-between mt-1">
                                                    <span className="text-gray-400">Tokens saved:</span>
                                                    <span className="text-pink-400">{stats.tokensSaved.toLocaleString()}</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Execution Panel */}
                        <div className="lg:col-span-2">
                            <div className="rounded-xl bg-gray-900 border border-gray-800 overflow-hidden">
                                {/* Terminal Header */}
                                <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
                                    <div className="flex items-center gap-2">
                                        <div className="flex gap-1.5">
                                            <div className="h-3 w-3 rounded-full bg-red-500" />
                                            <div className="h-3 w-3 rounded-full bg-yellow-500" />
                                            <div className="h-3 w-3 rounded-full bg-green-500" />
                                        </div>
                                        <span className="ml-3 text-sm text-gray-400 font-mono">Ralph + RLM Loop</span>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        {isRunning && (
                                            <div className="flex items-center gap-2 text-xs text-purple-400">
                                                <div className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
                                                Running...
                                            </div>
                                        )}
                                        {!isRunning && completedEvents.length === 0 && (
                                            <button
                                                onClick={runDemo}
                                                className="px-4 py-1.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white text-sm font-medium rounded-lg transition-colors"
                                            >
                                                Start Ralph
                                            </button>
                                        )}
                                        {!isRunning && completedEvents.length > 0 && (
                                            <button
                                                onClick={resetDemo}
                                                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
                                            >
                                                Reset
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Stats Bar */}
                                <div className="flex items-center gap-6 px-4 py-2 bg-gray-900/50 border-b border-gray-700 text-xs font-mono">
                                    <div>
                                        <span className="text-gray-500">Iterations: </span>
                                        <span className="text-purple-400">{stats.iterations}</span>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">Passed: </span>
                                        <span className="text-emerald-400">{stats.passed}/{stories.length}</span>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">Commits: </span>
                                        <span className="text-cyan-400">{stats.commits}</span>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">RLM: </span>
                                        <span className="text-pink-400">{stats.rlmCompressions > 0 ? `${stats.rlmCompressions} compression` : 'standby'}</span>
                                    </div>
                                </div>

                                {/* Execution Log */}
                                <div ref={scrollRef} className="h-96 overflow-y-auto p-4 space-y-3">
                                    {completedEvents.length === 0 && !isRunning && (
                                        <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
                                            <p>Click &quot;Start Ralph&quot; to watch autonomous development</p>
                                            <p className="text-xs mt-2 text-gray-600">
                                                Watch how <span className="text-pink-400">RLM</span> compresses context when it gets too large
                                            </p>
                                            <p className="text-xs mt-4 text-gray-600">
                                                Based on <a href="https://ghuntley.com/ralph" className="text-purple-400 hover:underline" target="_blank" rel="noopener noreferrer">Geoffrey Huntley&apos;s Ralph pattern</a>
                                            </p>
                                        </div>
                                    )}

                                    {completedEvents.map((event) => {
                                        const config = typeConfig[event.type]
                                        const isRlm = isRlmEvent(event.type)
                                        return (
                                            <div
                                                key={event.id}
                                                className={`rounded-lg border ${config.color} p-3 animate-fadeIn ${isRlm ? 'ring-1 ring-pink-500/30' : ''}`}
                                            >
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-2 text-xs">
                                                        <span>{config.icon}</span>
                                                        <span className={`font-medium ${isRlm ? 'text-pink-300' : 'text-gray-300'}`}>
                                                            {config.label}
                                                        </span>
                                                        {event.storyId && (
                                                            <span className="text-gray-500">({event.storyId})</span>
                                                        )}
                                                    </div>
                                                    {event.duration && (
                                                        <span className="text-[10px] text-gray-500">{event.duration}s</span>
                                                    )}
                                                </div>
                                                <pre className={`text-xs font-mono whitespace-pre-wrap break-words ${isRlm ? 'text-pink-200' : 'text-gray-300'}`}>
                                                    {event.content}
                                                </pre>
                                            </div>
                                        )
                                    })}

                                    {isRunning && currentEvent < demoEvents.length && (
                                        <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
                                            <div className="flex gap-1">
                                                <span className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                                                <span className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                                                <span className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                                            </div>
                                            <span>Processing...</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Key Features - Updated to show Ralph + RLM */}
                    <div className="mt-12 grid sm:grid-cols-3 gap-6">
                        <div className="text-center p-6 rounded-xl bg-gray-900/50 border border-gray-800">
                            <div className="text-3xl mb-3">🔄</div>
                            <h3 className="text-white font-semibold mb-2">Ralph: Fresh Context Loop</h3>
                            <p className="text-sm text-gray-400">Each iteration spawns a new AI agent. Memory persists via git commits and progress.txt.</p>
                        </div>
                        <div className="text-center p-6 rounded-xl bg-gradient-to-b from-pink-950/30 to-gray-900/50 border border-pink-500/20">
                            <div className="text-3xl mb-3">🗜️</div>
                            <h3 className="text-pink-300 font-semibold mb-2">RLM: Smart Compression</h3>
                            <p className="text-sm text-gray-400">When progress.txt exceeds threshold, RLM compresses it using sub-LM calls while preserving key learnings.</p>
                        </div>
                        <div className="text-center p-6 rounded-xl bg-gray-900/50 border border-gray-800">
                            <div className="text-3xl mb-3">⚡</div>
                            <h3 className="text-white font-semibold mb-2">A2A: Distributed Workers</h3>
                            <p className="text-sm text-gray-400">Run stories in parallel across multiple workers. 3 workers = 3x faster feature development.</p>
                        </div>
                    </div>

                    {/* How It Works */}
                    <div className="mt-12 p-6 rounded-xl bg-gray-900/50 border border-gray-800">
                        <h3 className="text-white font-semibold mb-4 text-center">How Ralph + RLM Work Together</h3>
                        <div className="flex flex-wrap justify-center items-center gap-3 text-sm">
                            <span className="px-3 py-1.5 rounded-lg bg-purple-950/50 text-purple-300 border border-purple-500/30">
                                📋 PRD Story
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-green-950/50 text-green-300 border border-green-500/30">
                                💻 Ralph Codes
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-cyan-950/50 text-cyan-300 border border-cyan-500/30">
                                ✓ Tests Pass
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-purple-950/50 text-purple-300 border border-purple-500/30">
                                📦 Git Commit
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-orange-950/50 text-orange-300 border border-orange-500/30">
                                📝 Update Memory
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-pink-950/50 text-pink-300 border border-pink-500/30">
                                🗜️ RLM Compress*
                            </span>
                            <span className="text-gray-500">→</span>
                            <span className="px-3 py-1.5 rounded-lg bg-blue-950/50 text-blue-300 border border-blue-500/30">
                                🔁 Next Story
                            </span>
                        </div>
                        <p className="text-xs text-gray-500 text-center mt-3">*RLM compression triggers automatically when context exceeds threshold (default: 80K tokens)</p>
                    </div>

                    {/* CTA */}
                    <div className="mt-12 text-center">
                        <a
                            href="/register"
                            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-3 text-sm font-semibold text-white hover:from-purple-500 hover:to-pink-500 transition-colors"
                        >
                            Try Ralph + RLM on Your Codebase
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                        </a>
                        <p className="mt-4 text-sm text-gray-500">
                            Create a PRD → Convert to prd.json → Let Ralph + RLM build it
                        </p>
                    </div>
                </div>
            </Container>
        </section>
    )
}
