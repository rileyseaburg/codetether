import { CallToAction } from '@/components/CallToAction'
import { CISOBanner } from '@/components/CISOBanner'
import { ContactForm } from '@/components/ContactForm'
import { CopilotComparison } from '@/components/CopilotComparison'
import { Faqs } from '@/components/Faqs'
import { Hero } from '@/components/Hero'
import { Pricing } from '@/components/Pricing'
import { PrimaryFeatures } from '@/components/PrimaryFeatures'
import { Roadmap } from '@/components/Roadmap'
import { SecondaryFeatures } from '@/components/SecondaryFeatures'
import { SocialProof, Testimonials } from '@/components/SocialProof'
import { TemporalComparison } from '@/components/TemporalComparison'
import { UseCases } from '@/components/UseCases'
import { WhyNotDIY } from '@/components/WhyNotDIY'

export default function Home() {
    return (
        <>
            <CISOBanner />
            <Hero />
            <CopilotComparison />
            <TemporalComparison />
            <WhyNotDIY />
            <SocialProof />
            <PrimaryFeatures />
            <SecondaryFeatures />
            <UseCases />
            <Roadmap />
            <Testimonials />
            <Pricing />
            <CallToAction />
            <Faqs />
            <ContactForm />
        </>
    )
}
