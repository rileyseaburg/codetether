import type { Metadata } from 'next'

import { InvestorDeck } from './InvestorDeck'

export const metadata: Metadata = {
    title: 'Investor Deck - CodeTether',
    description: 'Seed deck for CodeTether: the control plane for autonomous execution inside enterprise networks.',
}

// Force static generation at build time
export const dynamic = 'force-static'

export default function InvestorPitchPage() {
    return <InvestorDeck />
}
