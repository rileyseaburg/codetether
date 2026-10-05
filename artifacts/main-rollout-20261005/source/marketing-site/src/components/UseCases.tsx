import { Container } from '@/components/Container'

const useCases = [
    {
        title: 'Engineering Teams',
        description:
            'Write a PRD, run Ralph. Wake up to implemented features with tests passing and commits pushed. RLM ensures infinite context so your full workspace is understood, not just single files.',
        icon: '🔄',
        features: ['Autonomous dev', 'PRD → Code', 'RLM context'],
        workflow: 'PRD → Ralph implements → Review PR in morning'
    },
    {
        title: 'Course Creators',
        description:
            'Stop spending hours on landing pages. Tell the agent "build me a sales page for my new course" and get production-ready HTML in minutes. It reads your existing content, matches your brand, and writes converting copy.',
        icon: '🎓',
        features: ['Landing pages', 'Sales copy', 'Email sequences'],
        workflow: 'New course idea → Agent builds funnel → You review & launch'
    },
    {
        title: 'Agency Owners',
        description:
            'Your clients need reports, audits, and content. RLM agents analyze entire websites, generate SEO reports, and write blog posts—all triggered from your project management tool via webhook.',
        icon: '🏢',
        features: ['Client reports', 'SEO audits', 'Content at scale'],
        workflow: 'Client request → n8n triggers agent → Deliverable ready'
    },
    {
        title: 'E-commerce Sellers',
        description:
            'Product descriptions that convert. Feed the agent your inventory spreadsheet and get optimized listings for Amazon, Shopify, and Etsy. Bulk processing hundreds of SKUs overnight.',
        icon: '🛒',
        features: ['Product descriptions', 'Listing optimization', 'Bulk processing'],
        workflow: 'CSV upload → Agent writes listings → Export to platforms'
    },
    {
        title: 'No-Code Automators',
        description:
            '18 Zapier components connect CodeTether to 6,000+ apps. Trigger autonomous tasks from Airtable, Slack, or Gmail. No code required—just connect and configure.',
        icon: '⚡',
        features: ['Zapier triggers', '18 components', 'No-code setup'],
        workflow: 'Zap trigger → Agent runs task → Result to destination'
    },
    {
        title: 'DevOps & Infrastructure',
        description:
            'Agents that monitor your systems, manage deployments, and self-heal on Kubernetes. Integrity-checked plugins and sandboxed tools limit what reaches production. Every action audit-logged for compliance.',
        icon: '⚙️',
        features: ['K8s management', 'Incident response', 'Audit compliance'],
        workflow: 'Alert fires → Agent diagnoses → Auto-remediation + audit log'
    },
    {
        title: 'SaaS Founders',
        description:
            'Your product workspace is growing. RLM agents can analyze your full source context, find bugs, write tests, and generate documentation across teams and tools.',
        icon: '💻',
        features: ['Code review', 'Test generation', 'Documentation'],
        workflow: 'Push to GitHub → Agent reviews → Issues created'
    },
    {
        title: 'Content Marketers',
        description:
            'Research, outline, write, optimize. Agents that read your competitors\' content, analyze what ranks, and produce SEO-optimized articles. Triggered from your editorial calendar.',
        icon: '✍️',
        features: ['Blog posts', 'Research reports', 'Social content'],
        workflow: 'Calendar event → Agent researches & writes → Ready for review'
    },
    {
        title: 'Consultants & Coaches',
        description:
            'Client intake forms trigger personalized analysis. The agent reads their questionnaire, analyzes their situation, and drafts a custom proposal—before your first call.',
        icon: '🎯',
        features: ['Proposal generation', 'Client analysis', 'Custom reports'],
        workflow: 'Form submission → Agent analyzes → Proposal in inbox'
    },
]

export function UseCases() {
    return (
        <section
            id="use-cases"
            aria-labelledby="use-cases-title"
            className="bg-gray-50 dark:bg-gray-900 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="use-cases-title"
                        className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white"
                    >
                        Background Tasks for Every Workflow
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        Trigger from dashboard, API, or automation platform. Kick back. Get real deliverables in your inbox.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 sm:mt-20 lg:max-w-none lg:grid-cols-3">
                    {useCases.map((useCase) => (
                        <div
                            key={useCase.title}
                            className="flex flex-col rounded-2xl border border-gray-200 dark:border-gray-800 p-8 hover:border-cyan-500 dark:hover:border-cyan-500 hover:shadow-lg hover:shadow-cyan-500/10 transition-all bg-white dark:bg-gray-950"
                        >
                            <div className="text-4xl">{useCase.icon}</div>
                            <h3 className="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
                                {useCase.title}
                            </h3>
                            <p className="mt-2 flex-grow text-sm text-gray-600 dark:text-gray-300">
                                {useCase.description}
                            </p>
                            <div className="mt-4 p-3 rounded-lg bg-cyan-50 dark:bg-cyan-900/20">
                                <p className="text-xs font-medium text-cyan-700 dark:text-cyan-300">
                                    {useCase.workflow}
                                </p>
                            </div>
                            <ul className="mt-4 flex flex-wrap gap-2">
                                {useCase.features.map((feature) => (
                                    <li
                                        key={feature}
                                        className="rounded-full bg-gray-100 dark:bg-gray-800 px-3 py-1 text-xs font-medium text-gray-700 dark:text-gray-300"
                                    >
                                        {feature}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>
            </Container>
        </section>
    )
}
