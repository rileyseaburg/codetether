import dynamic from 'next/dynamic'
import { Suspense } from 'react'

// Above-the-fold components - load immediately
import { CISOBanner } from '@/components/CISOBanner'
import { Hero } from '@/components/Hero'
import { RLMFeature } from '@/components/RLMFeature'
import { CopilotComparison } from '@/components/CopilotComparison'

// Below-the-fold components - lazy load for faster initial page load
const TemporalComparison = dynamic(
    () =>
        import('@/components/TemporalComparison').then(
            (m) => m.TemporalComparison
        ),
    { ssr: true }
)
const WhyNotDIY = dynamic(
    () => import('@/components/WhyNotDIY').then((m) => m.WhyNotDIY),
    { ssr: true }
)
const SocialProof = dynamic(
    () => import('@/components/SocialProof').then((m) => m.SocialProof),
    { ssr: true }
)
const PrimaryFeatures = dynamic(
    () =>
        import('@/components/PrimaryFeatures').then((m) => m.PrimaryFeatures),
    { ssr: true }
)
const SecondaryFeatures = dynamic(
    () =>
        import('@/components/SecondaryFeatures').then(
            (m) => m.SecondaryFeatures
        ),
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
const Testimonials = dynamic(
    () => import('@/components/SocialProof').then((m) => m.Testimonials),
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

// Loading placeholder for lazy-loaded sections
function SectionSkeleton() {
    return (
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="animate-pulse">
                <div className="mx-auto mb-8 h-8 w-1/3 rounded bg-gray-200" />
                <div className="space-y-4">
                    <div className="h-4 w-full rounded bg-gray-200" />
                    <div className="h-4 w-5/6 rounded bg-gray-200" />
                    <div className="h-4 w-4/6 rounded bg-gray-200" />
                </div>
            </div>
        </div>
    )
}

export default function Home() {
    return (
        <>
            {/* Critical above-the-fold content - no lazy loading */}
            <CISOBanner />
            <Hero />
            <RLMFeature />
            <CopilotComparison />

            {/* Below-the-fold content - lazy loaded with SSR */}
            <Suspense fallback={<SectionSkeleton />}>
                <TemporalComparison />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <WhyNotDIY />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <SocialProof />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <PrimaryFeatures />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <SecondaryFeatures />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <UseCases />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <Roadmap />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <Testimonials />
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
