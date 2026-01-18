'use client'

import { useId } from 'react'
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react'
import clsx from 'clsx'

import { Container } from '@/components/Container'
import { CircleBackground } from '@/components/CircleBackground'

const features = [
    {
        name: 'RLM: Infinite Context Processing',
        description:
            'Revolutionary Recursive Language Models break free from context limits. Process entire monorepos, audit massive codebases, generate docs at scale—the AI writes Python that calls llm_query() recursively.',
        icon: RLMIcon,
        code: `# RLM: Process arbitrarily long contexts
context = load_entire_codebase()  # 500+ files, no limit

# AI writes Python that analyzes programmatically
for file in context.split("--- FILE: ")[:50]:
    # Each subcall gets fresh context window
    issues = llm_query(f"""
        Find security vulnerabilities in:
        {file[:8000]}
    """)
    if "vulnerability" in issues.lower():
        results.append(issues)

# Synthesize final insights
FINAL(llm_query(f"Summarize {len(results)} issues"))`,
    },
    {
        name: 'Pull Architecture (Zero Inbound Ports)',
        description:
            'Workers sit inside your secure network and reach OUT to poll for tasks. No inbound firewall rules, no VPN tunnels, no attack surface. Security teams say "yes" on day one.',
        icon: WorkerIcon,
        code: `# Worker PULLS tasks - no inbound ports needed
async def poll_loop(self):
    while self.running:
        # Outbound HTTPS only - works behind any firewall
        tasks = await self.fetch_tasks(self.server_url)
        for task in tasks:
            # Execute locally with full data access
            result = await self.run_agent(task)
            # Stream status + approved artifacts back (configurable)
            await self.submit_result(task.id, result)`,
    },
    {
        name: 'Zero Third-Party Storage (by CodeTether)',
        description:
            'CodeTether doesn\'t proxy prompts or source code. Sensitive context is handled on the Worker; if you use a hosted model, the Worker connects directly to your approved model tenant (e.g., Azure OpenAI with private networking) using your keys. The Control Plane only needs orchestration metadata.',
        icon: SessionIcon,
        code: `# Example: Healthcare
Worker runs INSIDE hospital VPC:
├── Reads PHI from local DB / EHR
├── Applies policy checks / redaction (optional)
├── Calls your approved model endpoint directly (optional)
└── Streams status/telemetry without proxying payloads

# Example: FinTech
Worker runs ON the trading floor:
├── Reads proprietary algorithms
├── Executes "optimize portfolio" task
└── CodeTether never stores prompts/source code`,
    },
    {
        name: 'Real-time Output Streaming',
        description:
            'Watch agent progress as it happens via Server-Sent Events. Perfect for long-running tasks where stakeholders need visibility without exposing underlying data.',
        icon: StreamIcon,
        code: `// Subscribe to task progress (Swift/Web)
const source = new EventSource(
  \`\${serverURL}/tasks/\${taskId}/output/stream\`
);

source.onMessage(event => {
  // See progress without seeing raw data
  // "Analyzing file 3 of 150..."
  // "Refactoring auth module..."
  // "Tests passing: 47/50"
  updateUI(event.data);
});`,
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

function RLMIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M8 16c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4zm8 0c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4z"
                stroke="#8B5CF6"
                strokeWidth={2}
                fill="none"
            />
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
            <TabList className="grid grid-cols-4 gap-x-6">
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
                        The &quot;Brain in Cloud, Hands on Prem&quot; architecture.
                    </h2>
                    <p className="mt-2 text-lg text-gray-400">
                        AI demos require you to upload your data. Enterprise AI requires you to keep it.
                        CodeTether&apos;s pull-based worker model solves the firewall problem that kills
                        95% of enterprise AI projects before they start.
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
