import { Container } from '@/components/Container'

const useCases = [
    {
        title: 'FinTech & Banking',
        description:
            'Trading algorithms and ledger systems can\'t leave your network. AI agents run inside your secure infrastructure, process financial data locally, and only send task status to the cloud. The ledger never moves.',
        icon: '🏦',
        features: ['Ledger stays local', 'SEC/FINRA ready', 'Audit trail built-in'],
    },
    {
        title: 'Healthcare & Life Sciences',
        description:
            'Patient records, clinical trials, research data—none of it touches external APIs. AI agents process PHI inside your HIPAA boundary while orchestration happens safely in the cloud.',
        icon: '🏥',
        features: ['HIPAA compliant', 'PHI stays internal', 'BAA-friendly architecture'],
    },
    {
        title: 'Source Code & IP Protection',
        description:
            'Your proprietary algorithms and source code are your competitive advantage. AI coding assistants run where your code lives—no code ever uploads to external AI services.',
        icon: '🔐',
        features: ['Zero code exfiltration', 'Air-gap compatible', 'Full repo access'],
    },
    {
        title: 'Government & Defense',
        description:
            'Classified environments with strict network controls. Workers poll from inside secure enclaves—no inbound connections required. AI capability without the security exceptions.',
        icon: '🏛️',
        features: ['FedRAMP aligned', 'Air-gap ready', 'Zero inbound ports'],
    },
    {
        title: 'Manufacturing & ICS',
        description:
            'Industrial control systems and manufacturing data stay behind OT firewalls. AI analyzes production data locally while coordinating with enterprise systems safely.',
        icon: '🏭',
        features: ['OT/IT separation', 'Edge deployment', 'SCADA compatible'],
    },
    {
        title: 'Legal & Professional Services',
        description:
            'Client privileged information never leaves your document management system. AI reviews contracts and analyzes cases without compromising attorney-client privilege.',
        icon: '⚖️',
        features: ['Privilege preserved', 'DMS integration', 'Matter separation'],
    },
]

export function UseCases() {
    return (
        <section
            id="use-cases"
            aria-labelledby="use-cases-title"
            className="bg-white dark:bg-gray-950 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="use-cases-title"
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        Enterprise AI Without Enterprise Risk
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        Regulated industries can finally deploy AI at scale. Your sensitive data stays exactly where compliance requires it.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 sm:mt-20 lg:max-w-none lg:grid-cols-3">
                    {useCases.map((useCase) => (
                        <div
                            key={useCase.title}
                            className="flex flex-col rounded-2xl border border-gray-200 dark:border-gray-800 p-8 hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-lg dark:hover:shadow-gray-900/50 transition-all bg-white dark:bg-gray-900"
                        >
                            <div className="text-4xl">{useCase.icon}</div>
                            <h3 className="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
                                {useCase.title}
                            </h3>
                            <p className="mt-2 flex-grow text-sm text-gray-600 dark:text-gray-300">
                                {useCase.description}
                            </p>
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
