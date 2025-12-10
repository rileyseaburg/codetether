import { CallToAction } from '@/components/CallToAction'
import { ContactForm } from '@/components/ContactForm'
import { Faqs } from '@/components/Faqs'
import { Hero } from '@/components/Hero'
import { Pricing } from '@/components/Pricing'
import { PrimaryFeatures } from '@/components/PrimaryFeatures'
import { Roadmap } from '@/components/Roadmap'
import { SecondaryFeatures } from '@/components/SecondaryFeatures'
import { SocialProof, Testimonials } from '@/components/SocialProof'
import { UseCases } from '@/components/UseCases'

export default function Home() {
    return (
        <>
            <Hero />
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
