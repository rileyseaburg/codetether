import dynamic from 'next/dynamic'
import { Suspense } from 'react'

import { Hero } from '@/components/Hero'

const SocialProof = dynamic(
    () => import('@/components/SocialProof').then((m) => m.SocialProof),
    { ssr: true }
)
const Testimonials = dynamic(
    () => import('@/components/SocialProof').then((m) => m.Testimonials),
    { ssr: true }
)
const PrimaryFeatures = dynamic(
    () => import('@/components/PrimaryFeatures').then((m) => m.PrimaryFeatures),
    { ssr: true }
)
const SecondaryFeatures = dynamic(
    () => import('@/components/SecondaryFeatures').then((m) => m.SecondaryFeatures),
    { ssr: true }
)
const RalphDemo = dynamic(
    () => import('@/components/RalphDemo').then((m) => m.RalphDemo),
    { ssr: true }
)
const RLMExplainer = dynamic(
    () => import('@/components/RLMExplainer').then((m) => m.RLMExplainer),
    { ssr: true }
)
const UseCases = dynamic(
    () => import('@/components/UseCases').then((m) => m.UseCases),
    { ssr: true }
)
const Roadmap = dynamic(
    () => import('@/components/Roadmap').then((m) => m.Roadmap),
    { ssr: true }
)
const Pricing = dynamic(
    () => import('@/components/Pricing').then((m) => m.Pricing),
    { ssr: true }
)
const CallToAction = dynamic(
    () => import('@/components/CallToAction').then((m) => m.CallToAction),
    { ssr: true }
)
const Faqs = dynamic(
    () => import('@/components/Faqs').then((m) => m.Faqs),
    { ssr: true }
)
const ContactForm = dynamic(
    () => import('@/components/ContactForm').then((m) => m.ContactForm),
    { ssr: true }
)

function SectionSkeleton() {
    return (
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="animate-pulse">
                <div className="mx-auto mb-8 h-8 w-1/3 rounded bg-gray-200 dark:bg-gray-800" />
                <div className="space-y-4">
                    <div className="h-4 w-full rounded bg-gray-200 dark:bg-gray-800" />
                    <div className="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-800" />
                </div>
            </div>
        </div>
    )
}

export default function Home() {
    return (
        <>
            <Hero />

            <Suspense fallback={<SectionSkeleton />}>
                <SocialProof />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <PrimaryFeatures />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <Testimonials />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <SecondaryFeatures />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <RalphDemo />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <RLMExplainer />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <UseCases />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <Roadmap />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <Pricing />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <CallToAction />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <Faqs />
            </Suspense>

            <Suspense fallback={<SectionSkeleton />}>
                <ContactForm />
            </Suspense>
        </>
    )
}
