/**
 * CodeTether FunnelBrain - Dynamic Marketing Page Optimizer
 *
 * Adapts the Spotless Bin Co "Two-Brain" architecture for CodeTether:
 * - Uses Thompson Sampling to select optimal page variants for each visitor
 * - Personalizes messaging based on ad context (UTM params, referrer, device)
 * - Tracks impressions → signups → subscriptions for continuous learning
 * - Assembles the page in <5ms for zero-latency personalization
 *
 * Each customizable "slot" on the marketing page has multiple variants.
 * The FunnelBrain selects variants that maximize signup conversion rate
 * for each visitor's specific context (e.g., GitHub devs from LinkedIn ads
 * see different messaging than devops engineers from Google search).
 *
 * @module lib/optimization/funnelBrain
 */

import { ThompsonSamplingOptimizer } from './thompsonSampling';
import type {
    MarketingSlot,
    SlotVariant,
    SlotSelection,
    PageAssembly,
    AdContext,
} from './types';

// ============================================================================
// Default variant library
// ============================================================================

/**
 * Built-in variants for every marketing slot.
 * These are the starting population that Thompson Sampling evolves from.
 * Winners get more traffic, losers get starved, and we keep exploring.
 */
const DEFAULT_VARIANTS: SlotVariant[] = [
    // --- Hero Headlines ---
    {
        id: 'hero-hl-security',
        slot: 'hero_headline',
        name: 'Security-first',
        content: {
            headline: 'The AI Agent Platform That Ships with Security Built In',
            subheadline: 'HMAC-SHA256 auth, Ed25519 plugin signing, immutable audit trails. Not optional—mandatory.',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'hero-hl-replace',
        slot: 'hero_headline',
        name: 'Replace-OpenClaw',
        content: {
            headline: 'Stop Paying for OpenClaw\'s Security Theater',
            subheadline: 'CodeTether ships Ed25519 code-signing and OPA policy enforcement. They ship a "coming soon" badge.',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'hero-hl-deploy',
        slot: 'hero_headline',
        name: 'Deploy-30-seconds',
        content: {
            headline: 'Deploy Your First AI Agent in 30 Seconds',
            subheadline: 'One command. Full Kubernetes orchestration. Zero-trust security from line one.',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'hero-hl-github',
        slot: 'hero_headline',
        name: 'GitHub-native',
        content: {
            headline: 'Built for Developers Who Live in GitHub',
            subheadline: 'A2A protocol, MCP tools, and Rust-level performance. The agent platform that thinks like you do.',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },

    // --- Hero CTAs ---
    {
        id: 'cta-free-trial',
        slot: 'hero_cta',
        name: 'Free-trial',
        content: { text: 'Start Free Trial', href: '/register' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'cta-deploy-now',
        slot: 'hero_cta',
        name: 'Deploy-now',
        content: { text: 'Deploy Your Agent Now', href: '/register' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'cta-get-started',
        slot: 'hero_cta',
        name: 'Get-started-free',
        content: { text: 'Get Started — It\'s Free', href: '/register' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },

    // --- Social Proof ---
    {
        id: 'proof-security',
        slot: 'social_proof',
        name: 'Security-stats',
        content: {
            stat1: '100%', stat1Label: 'Mandatory Auth',
            stat2: 'Ed25519', stat2Label: 'Plugin Signing',
            stat3: 'OPA', stat3Label: 'Policy Engine',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'proof-performance',
        slot: 'social_proof',
        name: 'Performance-stats',
        content: {
            stat1: '<1ms', stat1Label: 'Auth Latency',
            stat2: '30s', stat2Label: 'Deploy Time',
            stat3: 'Rust', stat3Label: 'Native Speed',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'proof-developer',
        slot: 'social_proof',
        name: 'Developer-love',
        content: {
            stat1: 'A2A', stat1Label: 'Protocol Native',
            stat2: 'MCP', stat2Label: 'Tool System',
            stat3: 'K8s', stat3Label: 'Auto Scaling',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },

    // --- Pricing Emphasis ---
    {
        id: 'pricing-free-first',
        slot: 'pricing_emphasis',
        name: 'Free-tier-first',
        content: { emphasis: 'free', badge: 'Most Popular', highlight: 'Free' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'pricing-pro-value',
        slot: 'pricing_emphasis',
        name: 'Pro-value',
        content: { emphasis: 'pro', badge: 'Best Value', highlight: 'Pro' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },

    // --- Comparison Focus ---
    {
        id: 'comparison-openclaw',
        slot: 'comparison_focus',
        name: 'OpenClaw-comparison',
        content: { focus: 'openclaw', headline: 'CodeTether vs OpenClaw' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'comparison-copilot',
        slot: 'comparison_focus',
        name: 'Copilot-comparison',
        content: { focus: 'copilot', headline: 'CodeTether vs GitHub Copilot Extensions' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'comparison-temporal',
        slot: 'comparison_focus',
        name: 'Temporal-comparison',
        content: { focus: 'temporal', headline: 'CodeTether vs Temporal' },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },

    // --- Call to Action Section ---
    {
        id: 'bottom-cta-urgency',
        slot: 'call_to_action',
        name: 'Urgency',
        content: {
            headline: 'Every Day Without Proper Auth Is a Day You\'re Vulnerable',
            cta: 'Secure Your Agents Now',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
    {
        id: 'bottom-cta-easy',
        slot: 'call_to_action',
        name: 'Easy-start',
        content: {
            headline: 'Start Building in 30 Seconds. No Credit Card Required.',
            cta: 'Create Free Account',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: true, isActive: true,
    },
    {
        id: 'bottom-cta-competitive',
        slot: 'call_to_action',
        name: 'Competitive',
        content: {
            headline: 'Your Competitors Are Already Deploying AI Agents. Are You?',
            cta: 'Deploy My First Agent',
        },
        alpha: 1, beta: 1, impressions: 0, conversions: 0, signups: 0, revenueCents: 0,
        isControl: false, isActive: true,
    },
];

// ============================================================================
// Context-specific affinity boosts
// ============================================================================

interface ContextAffinityRule {
    /** Predicate that matches an ad context */
    match: (ctx: AdContext) => boolean;
    /** Variant IDs that get boosted for this context */
    boostVariants: string[];
    /** Multiplier applied to the Thompson sample (e.g., 1.3 = 30% boost) */
    boost: number;
}

/**
 * Rules that boost specific variants for specific ad contexts.
 * These encode domain knowledge: GitHub users respond to different
 * messaging than general search traffic.
 */
const CONTEXT_RULES: ContextAffinityRule[] = [
    {
        match: ctx => ctx.utmSource === 'github' || ctx.isGitHubUser === true,
        boostVariants: ['hero-hl-github', 'comparison-copilot', 'proof-developer'],
        boost: 1.4,
    },
    {
        match: ctx => ctx.utmSource === 'linkedin',
        boostVariants: ['hero-hl-security', 'proof-security', 'bottom-cta-urgency'],
        boost: 1.3,
    },
    {
        match: ctx => ctx.utmMedium === 'cpc',
        boostVariants: ['hero-hl-replace', 'cta-deploy-now', 'bottom-cta-competitive'],
        boost: 1.2,
    },
    {
        match: ctx => ctx.utmCampaign?.includes('security') === true,
        boostVariants: ['hero-hl-security', 'proof-security', 'bottom-cta-urgency'],
        boost: 1.5,
    },
    {
        match: ctx => ctx.utmCampaign?.includes('devops') === true || ctx.utmCampaign?.includes('k8s') === true,
        boostVariants: ['hero-hl-deploy', 'proof-developer'],
        boost: 1.3,
    },
    {
        match: ctx => ctx.deviceType === 'mobile',
        boostVariants: ['cta-get-started', 'hero-hl-deploy'],
        boost: 1.1,
    },
];

// ============================================================================
// FunnelBrain
// ============================================================================

/**
 * Marketing FunnelBrain: Thompson Sampling optimizer for CodeTether's
 * marketing page. Selects the best variant for each page slot given
 * the visitor's ad context.
 */
export class MarketingFunnelBrain {
    private readonly optimizer: ThompsonSamplingOptimizer;
    private readonly explorationRate: number;
    private variants: SlotVariant[];

    constructor(options: {
        explorationRate?: number;
        variants?: SlotVariant[];
    } = {}) {
        this.explorationRate = options.explorationRate ?? 0.05;
        this.optimizer = new ThompsonSamplingOptimizer();
        this.variants = options.variants ?? [...DEFAULT_VARIANTS];
    }

    /**
     * Assemble the full marketing page for a visitor.
     *
     * Given a session ID and ad context, this selects the optimal variant
     * for every slot on the page and returns a complete assembly.
     */
    assemblePage(sessionId: string, adContext: AdContext): PageAssembly {
        const startTime = Date.now();

        // Get all unique slots
        const uniqueSlots = [...new Set(this.variants.map(v => v.slot))];

        const slots: Record<string, SlotSelection> = {};
        for (const slot of uniqueSlots) {
            const selection = this.selectVariant(slot, adContext);
            if (selection) {
                slots[slot] = selection;
            }
        }

        return {
            sessionId,
            slots: slots as Record<MarketingSlot, SlotSelection>,
            renderTimeMs: Date.now() - startTime,
            adContext,
            timestamp: new Date().toISOString(),
        };
    }

    /**
     * Select the best variant for a slot using Thompson Sampling
     */
    selectVariant(slot: MarketingSlot, adContext: AdContext): SlotSelection | null {
        const slotVariants = this.variants.filter(v => v.slot === slot && v.isActive);
        if (slotVariants.length === 0) return null;

        // 5% pure exploration for learning
        if (Math.random() < this.explorationRate) {
            const randomIdx = Math.floor(Math.random() * slotVariants.length);
            const variant = slotVariants[randomIdx];
            return {
                slot,
                variantId: variant.id,
                variantName: variant.name,
                content: variant.content,
                selectedVia: 'exploration',
                thompsonSample: 0,
            };
        }

        // Build context boost map
        const boostMap = new Map<string, number>();
        for (const rule of CONTEXT_RULES) {
            if (rule.match(adContext)) {
                for (const variantId of rule.boostVariants) {
                    const existing = boostMap.get(variantId) ?? 1.0;
                    boostMap.set(variantId, existing * rule.boost);
                }
            }
        }

        // Thompson Sampling: Sample from each variant's Beta distribution
        let bestVariant: SlotVariant = slotVariants[0];
        let bestSample = -Infinity;
        let selectedVia: SlotSelection['selectedVia'] = 'thompson';

        for (const variant of slotVariants) {
            const sample = this.optimizer.sampleBeta(variant.alpha, variant.beta);
            const boost = boostMap.get(variant.id) ?? 1.0;
            const boostedSample = sample * boost;

            if (boost > 1.0 && boostedSample > bestSample) {
                selectedVia = 'context_rule';
            }

            if (boostedSample > bestSample) {
                bestSample = boostedSample;
                bestVariant = variant;
                if (boost <= 1.0) selectedVia = 'thompson';
            }
        }

        return {
            slot,
            variantId: bestVariant.id,
            variantName: bestVariant.name,
            content: bestVariant.content,
            selectedVia,
            thompsonSample: bestSample,
        };
    }

    /**
     * Record an impression for a slot variant
     */
    recordImpression(variantId: string): void {
        const variant = this.variants.find(v => v.id === variantId);
        if (variant) {
            variant.impressions += 1;
            variant.beta += 1; // Assume non-conversion initially
        }
    }

    /**
     * Record a conversion (signup, CTA click) for all variants shown in a session
     */
    recordConversion(
        variantIds: string[],
        eventType: 'cta_click' | 'signup_complete' | 'subscription_start',
        valueCents: number = 0
    ): void {
        for (const variantId of variantIds) {
            const variant = this.variants.find(v => v.id === variantId);
            if (variant) {
                // Undo the non-conversion assumption
                variant.beta = Math.max(1, variant.beta - 1);
                // Record success
                variant.alpha += 1;
                variant.conversions += 1;
                variant.revenueCents += valueCents;

                if (eventType === 'signup_complete') {
                    variant.signups += 1;
                }
            }
        }
    }

    /**
     * Get performance stats for all variants
     */
    getPerformanceReport(): Array<{
        id: string;
        slot: MarketingSlot;
        name: string;
        impressions: number;
        conversions: number;
        conversionRate: number;
        expectedCvr: number;
        confidence: number;
        credibleInterval: [number, number];
        isWinning: boolean;
    }> {
        const bySlot = new Map<MarketingSlot, SlotVariant[]>();
        for (const v of this.variants) {
            const arr = bySlot.get(v.slot) ?? [];
            arr.push(v);
            bySlot.set(v.slot, arr);
        }

        const report: ReturnType<MarketingFunnelBrain['getPerformanceReport']> = [];

        for (const [slot, variants] of bySlot) {
            // Find the best expected CVR in this slot
            let bestExpectedCvr = 0;
            for (const v of variants) {
                const ecvr = this.optimizer.getPosteriorMean(v.alpha, v.beta);
                if (ecvr > bestExpectedCvr) bestExpectedCvr = ecvr;
            }

            for (const v of variants) {
                const expectedCvr = this.optimizer.getPosteriorMean(v.alpha, v.beta);
                const totalTrials = v.alpha + v.beta - 2;
                const confidence = Math.min(totalTrials / 100, 1);
                const credibleInterval = this.optimizer.getCredibleInterval(v.alpha, v.beta);

                report.push({
                    id: v.id,
                    slot,
                    name: v.name,
                    impressions: v.impressions,
                    conversions: v.conversions,
                    conversionRate: v.impressions > 0 ? v.conversions / v.impressions : 0,
                    expectedCvr,
                    confidence,
                    credibleInterval,
                    isWinning: expectedCvr === bestExpectedCvr && confidence >= 0.5,
                });
            }
        }

        return report;
    }

    /**
     * Export variant state for persistence
     */
    exportState(): SlotVariant[] {
        return this.variants.map(v => ({ ...v }));
    }

    /**
     * Import variant state from persistence
     */
    importState(state: SlotVariant[]): void {
        this.variants = state.map(v => ({ ...v }));
    }

    /**
     * Add a new variant to test
     */
    addVariant(variant: SlotVariant): void {
        this.variants.push(variant);
    }

    /**
     * Deactivate a losing variant
     */
    deactivateVariant(variantId: string): void {
        const variant = this.variants.find(v => v.id === variantId);
        if (variant) variant.isActive = false;
    }
}

/**
 * Extract ad context from URL search params and headers
 */
export function extractAdContext(
    searchParams: Record<string, string | undefined>,
    headers?: Record<string, string | undefined>
): AdContext {
    const referrer = headers?.referer ?? headers?.referrer ?? '';
    const userAgent = headers?.['user-agent'] ?? '';

    const isGitHubUser =
        referrer.includes('github.com') ||
        searchParams.utm_source === 'github' ||
        searchParams.ref === 'github';

    let deviceType: AdContext['deviceType'] = 'desktop';
    if (/mobile|android|iphone/i.test(userAgent)) {
        deviceType = 'mobile';
    } else if (/tablet|ipad/i.test(userAgent)) {
        deviceType = 'tablet';
    }

    return {
        utmSource: searchParams.utm_source,
        utmMedium: searchParams.utm_medium,
        utmCampaign: searchParams.utm_campaign,
        utmContent: searchParams.utm_content,
        utmTerm: searchParams.utm_term,
        referrer,
        landingPage: searchParams.landing_page,
        deviceType,
        isGitHubUser,
    };
}
