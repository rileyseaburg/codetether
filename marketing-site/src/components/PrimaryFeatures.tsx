'use client'

import { Tab, TabGroup, TabList, TabPanel, TabPanels } from '@headlessui/react'
import clsx from 'clsx'

import { Container } from '@/components/Container'

const features = [
    {
        name: 'Webhook Integration',
        description:
            'Trigger agents from Zapier, n8n, Make, or any tool that sends webhooks. Pass your data as JSON, get results streamed back or via callback URL.',
        icon: WebhookIcon,
        code: `// Trigger from Zapier/n8n/Make
POST /api/v1/agents/trigger
{
  "prompt": "Analyze this customer feedback",
  "context": {
    "reviews": [...],  // Your data
    "callback_url": "https://hooks.zapier.com/..."
  }
}

// Agent processes with RLM (no token limits)
// Results POST back to your callback URL
{
  "status": "complete",
  "output": "Analysis: 89% positive sentiment...",
  "files_created": ["report.pdf"]
}`,
    },
    {
        name: 'Real Code Output',
        description:
            'Not just chat responses—agents write actual files. Landing pages, scripts, reports, spreadsheets. Download or auto-deploy.',
        icon: CodeIcon,
        code: `// Agent creates real deliverables
You: "Build a landing page for my course on productivity"

Agent Output:
├── index.html      (2.3 KB)
├── styles.css      (1.1 KB)
├── script.js       (0.8 KB)
└── images/
    ├── hero.svg
    └── features.svg

Preview: https://preview.codetether.run/abc123
Download: https://api.codetether.run/download/abc123.zip

// Auto-deploy to Netlify, Vercel, or your server`,
    },
    {
        name: 'Bulk Processing',
        description:
            'Upload a CSV with 1000 rows. Agent processes each one. Product descriptions, personalized emails, data transformations—at scale.',
        icon: BulkIcon,
        code: `// Bulk process from spreadsheet
Upload: products.csv (1,247 rows)

Agent Task: "Write SEO-optimized product descriptions"

Progress:
[=========>          ] 47% (586/1247)
├── Row 586: Nike Air Max 90 → ✓ Description generated
├── Row 587: Adidas Ultraboost → Processing...
└── Est. completion: 12 minutes

// Results export to new CSV or direct to Shopify`,
    },
    {
        name: 'Session Memory',
        description:
            'Agents remember context across messages. Start a task, come back later, continue where you left off. Reply to the email notification to keep working.',
        icon: MemoryIcon,
        code: `// Session persists across interactions
Session: proj_abc123 (Course Launch Funnel)

Day 1: "Start building my funnel"
Agent: Created landing page structure...

Day 2: (reply to email notification)
You: "Add a testimonials section"
Agent: Added testimonials. Here's the updated preview...

Day 3: "Now create the email sequence"
Agent: I remember the course details. Creating 5-email sequence:
├── Email 1: Welcome + free resource
├── Email 2: Pain point story
├── Email 3: Case study
├── Email 4: FAQ + objections
└── Email 5: Limited time offer`,
    },
]

function WebhookIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#F97316" fillOpacity={0.2} />
            <path
                d="M10 16l6-4v8l-6-4zm6-4l6 4-6 4V12z"
                fill="#F97316"
            />
        </svg>
    )
}

function CodeIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M12 10l-4 6 4 6M20 10l4 6-4 6M14 22l4-12"
                stroke="#8B5CF6"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    )
}

function BulkIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06B6D4" fillOpacity={0.2} />
            <path
                d="M8 10h16M8 16h16M8 22h12"
                stroke="#06B6D4"
                strokeWidth={2}
                strokeLinecap="round"
            />
        </svg>
    )
}

function MemoryIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#10B981" fillOpacity={0.2} />
            <path
                d="M16 8v8l4 4"
                stroke="#10B981"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <circle cx={16} cy={16} r={6} stroke="#10B981" strokeWidth={2} fill="none" />
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
            aria-label="How CodeTether works with your automation stack"
            className="bg-white dark:bg-gray-950 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-3xl">
                    <h2 className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white">
                        How it fits your workflow
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        You already know Zapier, n8n, and Make. CodeTether adds AI that actually executes—
                        triggered by webhook, delivering real output.
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
