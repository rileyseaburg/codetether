import Link from 'next/link'

import { Button } from '@/components/Button'
import { Container } from '@/components/Container'
import { Logomark } from '@/components/Logo'
import { NavLinks } from '@/components/NavLinks'

function GitHubIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
            <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
        </svg>
    )
}

export function Footer() {
    return (
        <footer className="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
            <Container>
                <div className="flex flex-col items-start justify-between gap-y-12 pt-16 pb-6 lg:flex-row lg:items-center lg:py-16">
                    <div className="w-full lg:w-auto">
                        <div className="flex items-center text-gray-900 dark:text-white">
                            <Logomark className="h-10 w-10 flex-none fill-cyan-500" />
                            <div className="ml-4">
                                <p className="text-base font-semibold">CodeTether</p>
                                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Production A2A Coordination Platform</p>
                            </div>
                        </div>
                        <nav className="mt-11 flex flex-wrap gap-x-6 gap-y-3 sm:gap-8">
                            <NavLinks />
                        </nav>
                    </div>
                    <div className="flex flex-col items-center gap-4 sm:flex-row">
                        <Link
                            href="https://github.com/rileyseaburg/codetether"
                            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                            target="_blank"
                        >
                            <GitHubIcon className="h-6 w-6" />
                            <span>Star on GitHub</span>
                        </Link>
                        <Button href="/dashboard" color="cyan">
                            Open Dashboard
                        </Button>
                    </div>
                </div>
                <div className="flex flex-col items-center border-t border-gray-200 dark:border-gray-800 pt-8 pb-12 md:flex-row-reverse md:justify-between md:pt-6">
                    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 text-sm text-gray-600 dark:text-gray-400 px-2 sm:gap-x-6 sm:px-0">
                        <Link href="/privacy" className="hover:text-gray-900 dark:hover:text-white">
                            Privacy Policy
                        </Link>
                        <Link href="/terms" className="hover:text-gray-900 dark:hover:text-white">
                            Terms of Service
                        </Link>
                        <Link href="/investors" className="hover:text-gray-900 dark:hover:text-white">
                            Investor Pitch
                        </Link>
                        <Link href="https://github.com/rileyseaburg/codetether/blob/main/LICENSE" className="hover:text-gray-900 dark:hover:text-white">
                            Apache 2.0 License
                        </Link>
                        <Link href="https://github.com/rileyseaburg/codetether/blob/main/CONTRIBUTING.md" className="hover:text-gray-900 dark:hover:text-white">
                            Contributing
                        </Link>
                        <Link href="https://github.com/rileyseaburg/codetether/discussions" className="hover:text-gray-900 dark:hover:text-white">
                            Community
                        </Link>
                    </div>
                    <p className="mt-6 text-sm text-gray-500 dark:text-gray-500 md:mt-0">
                        &copy; {new Date().getFullYear()} CodeTether. Open source under <a href="https://github.com/rileyseaburg/codetether/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-gray-700 dark:hover:text-gray-300">Apache 2.0</a>.
                    </p>
                </div>
            </Container>
        </footer>
    )
}
