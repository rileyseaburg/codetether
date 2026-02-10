import dynamic from 'next/dynamic'
import { Suspense } from 'react'

// Above-the-fold components - load immediately
import { CISOBanner } from '@/components/CISOBanner'
import { Hero } from '@/components/Hero'
import { ChatWidget } from '@/components/ChatWidget'

// Below-the-fold components - lazy load
const OpenClawComparison = dynamic(
    () => import('@/components/OpenClawComparison').then((m) => m.OpenClawComparison),
    { ssr: true }
)
const RLMExplainer = dynamic(
    () => import('@/components/RLMExplainer').then((m) => m.RLMExplainer),
    { ssr: true }
)
const RLMDemo = dynamic(
    () => import('@/components/RLMDemo').then((m) => m.RLMDemo),
    { ssr: true }
)
const RalphDemo = dynamic(
    () => import('@/components/RalphDemo').then((m) => m.RalphDemo),
    { ssr: true }
)
const CopilotComparison = dynamic(
    () => import('@/components/CopilotComparison').then((m) => m.CopilotComparison),
    { ssr: true }
)
const TemporalComparison = dynamic(
    () => import('@/components/TemporalComparison').then((m) => m.TemporalComparison),
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
const Testimonials = dynamic(
    () => import('@/components/SocialProof').then((m) => m.Testimonials),
    { ssr: true }
)
const UseCases = dynamic(
    () => import('@/components/UseCases').then((m) => m.UseCases),
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
                <div className="mx-auto mb-8 h-8 w-1/3 rounded bg-gray-200" />
                <div className="space-y-4">
                    <div className="h-4 w-full rounded bg-gray-200" />
                    <div className="h-4 w-5/6 rounded bg-gray-200" />
                </div>
            </div>
        </div>
    )
}

export default function Home() {
    return (
        <>
            {/* Above the fold */}
            <CISOBanner />
            <Hero />
            
            {/* OpenClaw Comparison - direct response sales letter */}
            <Suspense fallback={<SectionSkeleton />}>
                <OpenClawComparison />
            </Suspense>
            
            {/* RLM Explainer - the tech behind CodeTether */}
            <Suspense fallback={<SectionSkeleton />}>
                <RLMExplainer />
            </Suspense>
            
            {/* RLM Demo - interactive demonstration */}
            <Suspense fallback={<SectionSkeleton />}>
                <RLMDemo />
            </Suspense>
            
            {/* Core value props */}
            <Suspense fallback={<SectionSkeleton />}>
                <Testimonials />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <CopilotComparison />
            </Suspense>
            
            {/* Ralph Demo - autonomous agent loop (moved after ChatGPT comparison) */}
            <Suspense fallback={<SectionSkeleton />}>
                <RalphDemo />
            </Suspense>
            
            <Suspense fallback={<SectionSkeleton />}>
                <TemporalComparison />
            </Suspense>
            <Suspense fallback={<SectionSkeleton />}>
                <WhyNotDIY />
            </Suspense>
            
            {/* Social proof */}
            <Suspense fallback={<SectionSkeleton />}>
                <SocialProof />
            </Suspense>
            
            {/* Use cases */}
            <Suspense fallback={<SectionSkeleton />}>
                <UseCases />
            </Suspense>
            
            {/* Conversion */}
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
            
            {/* Floating Chat Widget */}
            <ChatWidget />
        </>
    )
}
