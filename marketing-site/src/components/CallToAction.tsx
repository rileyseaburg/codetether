import { CircleBackground } from '@/components/CircleBackground'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

export function CallToAction() {
    return (
        <section
            id="get-started"
            className="relative overflow-hidden bg-gray-900 py-20 sm:py-28"
        >
            <div className="absolute top-1/2 left-20 -translate-y-1/2 sm:left-1/2 sm:-translate-x-1/2">
                <CircleBackground color="#fff" className="animate-spin-slower" />
            </div>
            <Container className="relative">
                <div className="mx-auto max-w-md sm:text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-white sm:text-4xl">
                        Keep Your Data. Get AI Capability.
                    </h2>
                    <p className="mt-4 text-lg text-gray-300">
                        Deploy in your secure environment today. Open source with enterprise support available.
                        Your compliance team will thank you.
                    </p>
                    <div className="mt-8 flex flex-col sm:flex-row justify-center gap-4">
                        <Button href="https://github.com/rileyseaburg/codetether" color="cyan">
                            View on GitHub
                        </Button>
                        <Button href="/dashboard" variant="outline" className="text-white border-white hover:bg-white/10">
                            Open Dashboard
                        </Button>
                    </div>
                </div>
            </Container>
        </section>
    )
}
