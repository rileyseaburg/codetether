'use client'

import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react'
import clsx from 'clsx'

import { Container } from '@/components/Container'

const features = [
    {
        name: 'Objective → PRD → Code',
        description:
            'Describe an outcome. CodeTether creates an OKR, generates a structured PRD, runs Ralph through each user story, tests changes, and delivers a merge-ready branch.',
        icon: AutonomousIcon,
        code: `# One command. Objective to implementation.
$ codetether go "Add OAuth2 login with GitHub and Google"

# CodeTether automatically:
# 1. Creates an OKR with measurable outcomes
# 2. Generates a PRD with user stories
# 3. Runs Ralph in isolated implementation loops
# 4. Executes tests, lint, and type checks
# 5. Maps results back to OKR progress
# 6. Returns a ready-to-merge branch

# Plan mode for complex tasks
$ codetether plan "Refactor auth to support SSO"
# Step 1/3: Audit existing auth middleware ✓
# Step 2/3: Add SAML/OIDC providers      ✓
# Step 3/3: Update RBAC policies         ✓
# Ready to merge → feature/sso-refactor`,
    },
    {
        name: 'Swarm & Relay',
        description:
            'Spawn specialized sub-agents in parallel or chain them via relay. Each agent has full tool access, its own context, and persistent memory across sessions.',
        icon: SwarmIcon,
        code: `# Parallel swarm execution
const result = await swarmExecute({
  tasks: [
    { name: 'Security', instruction: 'Audit all API routes',
      specialty: 'Security Reviewer' },
    { name: 'Perf', instruction: 'Profile critical path latency',
      specialty: 'Performance Engineer' },
    { name: 'Docs', instruction: 'Generate API reference',
      specialty: 'Technical Writer' }
  ],
  concurrency: 3,
  strategy: 'best_effort'
});

# Relay: chain agents sequentially
relay.delegate({
  target_agent: 'Architect',
  message: 'Design the rate-limiting system'
});
# → Architect hands off to Implementer
# → Implementer hands off to Reviewer
# → Results aggregate automatically`,
    },
    {
        name: 'Multi-Modal Tools',
        description:
            'Voice, video, browser, podcasts, YouTube, image input, web search, and MCP — 60+ registered tool IDs behind a Rust-native agent runtime.',
        icon: CognitionIcon,
        code: `# Voice: Text-to-speech with cloned voice
await voice.speak({
  text: "Build complete. All tests passing.",
  voice_id: "960f89fc"  // Your cloned voice
});

# Podcast: Generate & publish
const pod = await podcast.create_episode({
  podcast_id: "tech-weekly",
  script: "Today we cover WebAssembly...",
  title: "Ep 42: WASM in Production"
});

# Browser: Headless automation
await browser.goto("https://dashboard.example.com");
await browser.click_text("Deploy");
await browser.wait({ text: "Deployment complete" });
# Capture real app traffic, then replay with patches
await browser.replay({ url_contains: "/api/deploy", body_patch: { env: "prod" } });

# MCP: Connect to any external tool server
const mcpTools = await mcp.listTools({
  command: "npx @modelcontextprotocol/server-postgres"
});`,
    },
    {
        name: 'Production Infrastructure',
        description:
            'K8s-native deployment with OPA policy engine, RBAC, tenant isolation, and Ed25519 plugin signing. Built in Rust for single-binary performance across 11 platforms.',
        icon: InfraIcon,
        code: `# Deploy to Kubernetes
$ kubectl apply -f chart/a2a-server/

# OPA Policy Engine — RBAC across your org
policies/
├── authz.rego          # Permission checks
├── api_keys.rego       # Key scope enforcement
├── tenants.rego        # Tenant isolation
└── data.json           # Role→permission mappings

# 11 platform binaries (Linux, macOS, Windows)
$ curl -fsSL https://codetether.run/install.sh | bash
# x64, ARM64, musl, baseline — one binary, zero deps

# Kubernetes tool: manage from the agent
$ kubectl scale --replicas=3 deployment/api
$ kubectl logs --tail=50 pod/worker-7x2a`,
    },
]

function AutonomousIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06B6D4" fillOpacity={0.2} />
            <path d="M16 8v8l5 3" stroke="#06B6D4" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
            <circle cx={16} cy={16} r={7} stroke="#06B6D4" strokeWidth={2} fill="none" />
        </svg>
    )
}

function SwarmIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <circle cx={16} cy={12} r={3} fill="#8B5CF6" />
            <circle cx={10} cy={20} r={2.5} fill="#8B5CF6" />
            <circle cx={22} cy={20} r={2.5} fill="#8B5CF6" />
            <path d="M16 15v3M13 14l-2 4M19 14l2 4" stroke="#8B5CF6" strokeWidth={1.5} />
        </svg>
    )
}

function CognitionIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#10B981" fillOpacity={0.2} />
            <path d="M10 16a6 6 0 0 1 6-6M16 10a6 6 0 0 1 6 6M22 16a6 6 0 0 1-6 6M16 22a6 6 0 0 1-6-6" stroke="#10B981" strokeWidth={2} fill="none" />
            <circle cx={16} cy={16} r={2} fill="#10B981" />
        </svg>
    )
}

function InfraIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#F59E0B" fillOpacity={0.2} />
            <rect x={10} y={8} width={12} height={6} rx={1} stroke="#F59E0B" strokeWidth={1.5} fill="none" />
            <rect x={10} y={18} width={12} height={6} rx={1} stroke="#F59E0B" strokeWidth={1.5} fill="none" />
            <path d="M16 14v4M13 11h6M13 21h6" stroke="#F59E0B" strokeWidth={1.5} strokeLinecap="round" />
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
                {features.map((feature) => (
                    <Tab
                        key={feature.name}
                        className={clsx(
                            'rounded-2xl p-6 text-left transition-colors',
                            'hover:bg-gray-100 dark:hover:bg-gray-800/30 focus:outline-none',
                            'data-[selected]:bg-cyan-50 dark:data-[selected]:bg-cyan-900/20 data-[selected]:ring-2 data-[selected]:ring-cyan-500'
                        )}
                    >
                        <feature.icon className="h-8 w-8" />
                        <h3 className="mt-6 text-lg font-semibold text-gray-900 dark:text-white">
                            {feature.name}
                        </h3>
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{feature.description}</p>
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
                    <div className="rounded-2xl bg-gray-50 dark:bg-gray-800 p-6">
                        <feature.icon className="h-8 w-8" />
                        <h3 className="mt-6 text-lg font-semibold text-gray-900 dark:text-white">
                            {feature.name}
                        </h3>
                        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{feature.description}</p>
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
            id="how-it-works"
            aria-label="CodeTether capabilities"
            className="bg-white dark:bg-gray-950 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-3xl">
                    <h2 className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white">
                        The AI development platform
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        Autonomous objectives, swarm intelligence, persistent context, multi-modal tools, and production-grade infrastructure —
                        60+ registered tools, one control plane.
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
