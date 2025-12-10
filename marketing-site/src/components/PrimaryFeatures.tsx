'use client'

import { useId } from 'react'
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react'
import clsx from 'clsx'

import { Container } from '@/components/Container'
import { CircleBackground } from '@/components/CircleBackground'

const features = [
    {
        name: 'Distributed Agent Workers',
        description:
            'Deploy workers on remote machines with codebases. Workers automatically poll for tasks, execute OpenCode agents, and stream results back in real-time.',
        icon: WorkerIcon,
        code: `# Worker polls for tasks
async def poll_loop(self):
    while self.running:
        tasks = await self.get_pending_tasks()
        for task in tasks:
            await self.execute_task(task)

# Execute with OpenCode
result = await self.run_opencode(
    codebase_path="/app",
    prompt="Refactor the auth module",
    agent_type="build"
)`,
    },
    {
        name: 'Session History & Resumption',
        description:
            'Browse past AI coding sessions from any device. Resume conversations exactly where you left off with full context preservation.',
        icon: SessionIcon,
        code: `# List all sessions
GET /v1/opencode/codebases/{id}/sessions

# Resume a session
POST /v1/opencode/codebases/{id}/sessions/{session_id}/resume
{
  "prompt": "Continue with the refactoring"
}

# Stream real-time output
GET /v1/opencode/tasks/{task_id}/output/stream
event: output
data: {"content": "Analyzing code..."}`,
    },
    {
        name: 'Real-time Output Streaming',
        description:
            'Watch agent responses as they happen via Server-Sent Events. Perfect for long-running tasks where you need immediate feedback.',
        icon: StreamIcon,
        code: `// Subscribe to task output (Swift)
let url = URL(string: "\\(serverURL)/tasks/\\(taskId)/output/stream")!
let source = EventSource(url: url)

source.onMessage { event in
    if event.type == "output" {
        print(event.data) // Real-time output
    } else if event.type == "done" {
        print("Task completed!")
    }
}`,
    },
]

function WorkerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#A3A3A3" fillOpacity={0.2} />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M16 6a2 2 0 00-2 2v2H8a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V12a2 2 0 00-2-2h-6V8a2 2 0 00-2-2zm-1 6h2v2h-2v-2zm-4 4h2v2h-2v-2zm10 0h2v2h-2v-2zm-8 4h2v2h-2v-2zm6 0h2v2h-2v-2z"
                fill="#737373"
            />
        </svg>
    )
}

function SessionIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#A3A3A3" fillOpacity={0.2} />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M8 8a2 2 0 012-2h12a2 2 0 012 2v16a2 2 0 01-2 2H10a2 2 0 01-2-2V8zm2 0v16h12V8H10zm2 3h8v2h-8v-2zm0 4h8v2h-8v-2zm0 4h5v2h-5v-2z"
                fill="#737373"
            />
        </svg>
    )
}

function StreamIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#A3A3A3" fillOpacity={0.2} />
            <path
                d="M8 16h4m4 0h4m4 0h4M8 12h16M8 20h16"
                stroke="#737373"
                strokeWidth={2}
                strokeLinecap="round"
            />
            <circle cx={16} cy={16} r={3} fill="#06b6d4" />
        </svg>
    )
}

function FeatureCode({ code }: { code: string }) {
    return (
        <div className="overflow-hidden rounded-xl bg-gray-900 shadow-xl">
            <div className="flex items-center gap-2 border-b border-gray-700 px-4 py-2">
                <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-500" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
            </div>
            <pre className="p-4 text-sm text-gray-300 overflow-x-auto">
                <code>{code}</code>
            </pre>
        </div>
    )
}

function FeaturesDesktop() {
    return (
        <TabGroup className="hidden lg:block">
            <TabList className="grid grid-cols-3 gap-x-8">
                {features.map((feature, featureIndex) => (
                    <Tab
                        key={feature.name}
                        className={clsx(
                            'rounded-2xl p-6 text-left transition-colors',
                            'hover:bg-gray-800/30 focus:outline-none',
                            'data-[selected]:bg-gray-800'
                        )}
                    >
                        <feature.icon className="h-8 w-8" />
                        <h3 className="mt-6 text-lg font-semibold text-white">
                            {feature.name}
                        </h3>
                        <p className="mt-2 text-sm text-gray-400">{feature.description}</p>
                    </Tab>
                ))}
            </TabList>
            <TabPanels className="mt-8">
                {features.map((feature) => (
                    <TabPanel key={feature.name}>
                        <FeatureCode code={feature.code} />
                    </TabPanel>
                ))}
            </TabPanels>
        </TabGroup>
    )
}

function FeaturesMobile() {
    return (
        <div className="space-y-10 lg:hidden">
            {features.map((feature) => (
                <div key={feature.name}>
                    <div className="rounded-2xl bg-gray-800 p-6">
                        <feature.icon className="h-8 w-8" />
                        <h3 className="mt-6 text-lg font-semibold text-white">
                            {feature.name}
                        </h3>
                        <p className="mt-2 text-sm text-gray-400">{feature.description}</p>
                    </div>
                    <div className="mt-4">
                        <FeatureCode code={feature.code} />
                    </div>
                </div>
            ))}
        </div>
    )
}

export function PrimaryFeatures() {
    return (
        <section
            id="features"
            aria-label="Features for distributed AI agent orchestration"
            className="bg-gray-900 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-3xl">
                    <h2 className="text-3xl font-medium tracking-tight text-white">
                        The mesh that makes agents work together.
                    </h2>
                    <p className="mt-2 text-lg text-gray-400">
                        CodeTether provides the A2A protocol–native platform for connecting agents.
                        Routing, sessions, history, observability, and MCP tool integration—so
                        agents can safely coordinate real work in production.
                    </p>
                </div>
                <div className="mt-16">
                    <FeaturesDesktop />
                    <FeaturesMobile />
                </div>
            </Container>
        </section>
    )
}
