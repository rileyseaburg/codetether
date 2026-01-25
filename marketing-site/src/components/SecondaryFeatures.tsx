import { Container } from '@/components/Container'

const features = [
    {
        name: 'RLM: Infinite Context',
        description:
            'Based on MIT/Harvard research. Process your entire codebase, all your content, every spreadsheet—no token limits. AI that finally reads everything.',
        icon: RLMIcon,
    },
    {
        name: 'Works with Zapier',
        description:
            'Trigger agents from any Zap. New row in Google Sheets? Customer fills out a form? Agent starts working immediately, results POST back to your workflow.',
        icon: ZapierIcon,
    },
    {
        name: 'Works with n8n',
        description:
            'Self-hosted n8n users love it. HTTP Request node triggers the agent, wait for callback or poll for results. Full control, no vendor lock-in.',
        icon: N8nIcon,
    },
    {
        name: 'Works with Make',
        description:
            'Integromat/Make scenarios connect via webhook. Complex multi-step workflows with AI in the middle. Scenarios that were impossible are now simple.',
        icon: MakeIcon,
    },
    {
        name: 'Real File Output',
        description:
            'Agents don\'t just respond—they create files. HTML pages, Python scripts, Excel reports, PDF documents. Download or auto-deploy.',
        icon: FileIcon,
    },
    {
        name: 'Email to Continue',
        description:
            'Agent finishes? Get an email. Reply to keep the conversation going. No dashboard needed—work from your inbox.',
        icon: EmailIcon,
    },
]

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

function ZapierIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#FF4A00" fillOpacity={0.2} />
            <path
                d="M16 8l-8 8 8 8 8-8-8-8z"
                stroke="#FF4A00"
                strokeWidth={2}
                fill="none"
            />
            <circle cx={16} cy={16} r={3} fill="#FF4A00" />
        </svg>
    )
}

function N8nIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#EA4B71" fillOpacity={0.2} />
            <path
                d="M8 16h4M20 16h4M12 12v8M20 12v8"
                stroke="#EA4B71"
                strokeWidth={2}
                strokeLinecap="round"
            />
            <path
                d="M12 16h8"
                stroke="#EA4B71"
                strokeWidth={2}
                strokeLinecap="round"
                strokeDasharray="2 2"
            />
        </svg>
    )
}

function MakeIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#6D00CC" fillOpacity={0.2} />
            <circle cx={10} cy={16} r={3} fill="#6D00CC" />
            <circle cx={22} cy={16} r={3} fill="#6D00CC" />
            <path
                d="M13 16h6"
                stroke="#6D00CC"
                strokeWidth={2}
            />
        </svg>
    )
}

function FileIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06B6D4" fillOpacity={0.2} />
            <path
                d="M10 8h8l4 4v12a2 2 0 01-2 2H10a2 2 0 01-2-2V10a2 2 0 012-2z"
                stroke="#06B6D4"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M18 8v4h4"
                stroke="#06B6D4"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

function EmailIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#10B981" fillOpacity={0.2} />
            <path
                d="M6 10h20v12H6z"
                stroke="#10B981"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M6 10l10 7 10-7"
                stroke="#10B981"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

export function SecondaryFeatures() {
    return (
        <section
            id="secondary-features"
            aria-label="Features for automation builders"
            className="py-20 sm:py-32 bg-gray-50 dark:bg-gray-900"
        >
            <Container>
                <div className="mx-auto max-w-2xl sm:text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white">
                        Built for Automation Builders
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        You&apos;ve mastered the automation stack. Now add the AI layer that actually gets work done.
                    </p>
                </div>
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 text-sm sm:mt-20 sm:grid-cols-2 md:gap-y-10 lg:max-w-none lg:grid-cols-3"
                >
                    {features.map((feature) => (
                        <li
                            key={feature.name}
                            className="rounded-2xl border border-gray-200 dark:border-gray-800 p-8 hover:border-cyan-500 dark:hover:border-cyan-500 hover:shadow-lg hover:shadow-cyan-500/10 transition-all bg-white dark:bg-gray-950"
                        >
                            <feature.icon className="h-8 w-8" />
                            <h3 className="mt-6 font-semibold text-gray-900 dark:text-white">
                                {feature.name}
                            </h3>
                            <p className="mt-2 text-gray-600 dark:text-gray-300">{feature.description}</p>
                        </li>
                    ))}
                </ul>
            </Container>
        </section>
    )
}
