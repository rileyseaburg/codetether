import { Container } from '@/components/Container'

export function ReleaseBanner() {
    return (
        <div className="bg-cyan-50 dark:bg-cyan-950/30 border-b border-cyan-200 dark:border-cyan-800 py-3">
            <Container>
                <div className="flex items-center justify-center gap-2 text-sm">
                    <span className="inline-flex items-center rounded-full bg-cyan-100 dark:bg-cyan-900 px-2 py-0.5 text-xs font-medium text-cyan-800 dark:text-cyan-200">
                        New
                    </span>
                    <span className="font-medium text-gray-900 dark:text-white">
                        CodeTether v1.2.0 Released
                    </span>
                    <span className="text-gray-600 dark:text-gray-300">
                        - A2A Protocol v0.3 Compliant
                    </span>
                    <a
                        href="https://github.com/rileyseaburg/codetether/releases/tag/v1.2.0"
                        className="ml-2 font-medium text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300"
                    >
                        Learn more →
                    </a>
                </div>
            </Container>
        </div>
    )
}
