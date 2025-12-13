import type { Metadata } from 'next'

import { InvestorDeck } from './InvestorDeck'

export const metadata: Metadata = {
    title: 'Investor Deck - CodeTether',
    description: 'Seed deck for CodeTether: the control plane for autonomous execution inside enterprise networks.',
}

export default function InvestorPitchPage() {
    return <InvestorDeck />
}
