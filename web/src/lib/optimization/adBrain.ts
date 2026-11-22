/**
 * CodeTether AdBrain - Automated Ad Campaign Optimizer
 *
 * Manages CodeTether's self-advertising across platforms:
 * - Facebook/Instagram (developer audiences)
 * - LinkedIn (enterprise/CISO audiences)
 * - Google Ads (search intent: "AI agent platform", "MCP server")
 * - GitHub Sponsors/Ads (direct developer reach)
 *
 * Uses Thompson Sampling to:
 * 1. Allocate budget across campaigns based on LTV-weighted ROAS
 * 2. Calculate optimal CPC bids per platform
 * 3. Decide when to scale, maintain, or pause campaigns
 * 4. Generate self-selling reports
 *
 * @module lib/optimization/adBrain
 */

import { ThompsonSamplingOptimizer } from './thompsonSampling';
import type {
    CampaignArm,
    BudgetAllocation,
    OptimizationDecision,
    OptimizationAction,
    AdPlatform,
    SelfSellingReport,
    ConversionEvent,
} from './types';

// ============================================================================
// Decision thresholds (CodeTether-specific)
// ============================================================================

const THRESHOLDS = {
    // ROAS thresholds for a SaaS developer tool
    MIN_ROAS_TO_SCALE: 2.5,        // SaaS margins support 2.5x ROAS
    MIN_ROAS_TO_MAINTAIN: 1.0,     // Break-even with LTV considered
    // CAC thresholds (developer SaaS)
    MAX_CAC_TO_SCALE: 5000,        // $50 CAC for dev-tool SaaS
    MAX_CAC_TO_MAINTAIN: 10000,    // $100 CAC ceiling
    // Budget guardrails
    MAX_BUDGET_INCREASE_PCT: 0.50,
    MAX_BUDGET_DECREASE_PCT: 0.50,
    MIN_DAILY_BUDGET_CENTS: 500,   // $5/day minimum
    MAX_DAILY_BUDGET_CENTS: 50000, // $500/day maximum
    // Confidence requirements
    MIN_CONFIDENCE_TO_SCALE: 0.60,
    MIN_CONFIDENCE_TO_PAUSE: 0.75,
    // Data requirements
    MIN_CONVERSIONS_TO_ACT: 3,
    MIN_IMPRESSIONS_TO_ACT: 500,
} as const;

// ============================================================================
// AdBrain
// ============================================================================

/**
 * AdBrain: Autonomous ad campaign optimizer for CodeTether
 *
 * Tracks campaign performance, maintains Bayesian posteriors,
 * and produces actionable decisions on budget allocation.
 */
export class AdBrain {
    private readonly optimizer: ThompsonSamplingOptimizer;
    private campaigns: CampaignArm[];
    private conversionLog: ConversionEvent[];
    private lastOptimization: Date | null = null;

    constructor(options: {
        explorationBudgetPct?: number;
        campaigns?: CampaignArm[];
    } = {}) {
        this.optimizer = new ThompsonSamplingOptimizer({
            explorationBudgetPct: options.explorationBudgetPct ?? 0.10,
            mcSamples: 5000,
        });
        this.campaigns = options.campaigns ?? [];
        this.conversionLog = [];
    }

    /**
     * Register a new campaign arm
     */
    addCampaign(campaign: CampaignArm): void {
        this.campaigns.push(campaign);
    }

    /**
     * Record an ad impression
     */
    recordImpression(campaignId: string): void {
        const campaign = this.campaigns.find(c => c.campaignId === campaignId);
        if (campaign) {
            campaign.impressions += 1;
            campaign.beta += 1;
        }
    }

    /**
     * Record a click
     */
    recordClick(campaignId: string): void {
        const campaign = this.campaigns.find(c => c.campaignId === campaignId);
        if (campaign) {
            campaign.clicks += 1;
        }
    }

    /**
     * Record a conversion (signup, subscription, etc.)
     */
    recordConversion(event: ConversionEvent): void {
        this.conversionLog.push(event);

        // Find matching campaign from UTM
        const campaignId = this.resolveCampaignId(event);
        if (!campaignId) return;

        const campaign = this.campaigns.find(c => c.campaignId === campaignId);
        if (!campaign) return;

        // Undo the non-conversion assumption
        campaign.beta = Math.max(1, campaign.beta - 1);
        campaign.alpha += 1;
        campaign.conversions += 1;
        campaign.revenue += event.valueCents;

        if (event.eventType === 'signup_complete') {
            campaign.signups += 1;
        }
        if (event.eventType === 'subscription_start' || event.eventType === 'subscription_renewal') {
            campaign.subscriptionCount += 1;
            campaign.ltvRevenue += event.valueCents;
        }
    }

    /**
     * Run the optimization cycle: recommend allocations + make decisions
     */
    async optimize(totalDailyBudget: number): Promise<{
        allocations: BudgetAllocation[];
        decisions: OptimizationDecision[];
    }> {
        if (this.campaigns.length === 0) {
            return { allocations: [], decisions: [] };
        }

        const allocations = await this.optimizer.recommendAllocation(
            totalDailyBudget,
            this.campaigns
        );

        const decisions = allocations.map(alloc =>
            this.makeDecision(alloc, this.campaigns.find(c => c.campaignId === alloc.campaignId)!)
        );

        this.lastOptimization = new Date();
        return { allocations, decisions };
    }

    /**
     * Calculate optimal bids for each platform
     */
    calculateBids(): Record<AdPlatform, { bidCents: number; confidence: number; method: string }> {
        const platforms: AdPlatform[] = ['facebook', 'google', 'linkedin', 'tiktok', 'github'];
        const bids: Record<string, { bidCents: number; confidence: number; method: string }> = {};

        for (const platform of platforms) {
            bids[platform] = this.optimizer.calculateOptimalBid(this.campaigns, platform, {
                targetRoas: platform === 'linkedin' ? 2.0 : 3.0, // LinkedIn has higher CPCs
                defaultBidCents: platform === 'linkedin' ? 150 : 75,
            });
        }

        return bids as Record<AdPlatform, { bidCents: number; confidence: number; method: string }>;
    }

    /**
     * Generate a self-selling performance report
     */
    async generateReport(periodDays: number = 30): Promise<SelfSellingReport> {
        const { allocations, decisions } = await this.optimize(
            THRESHOLDS.MAX_DAILY_BUDGET_CENTS
        );

        const totalVisitors = this.campaigns.reduce((s, c) => s + c.clicks, 0);
        const signupCompletes = this.conversionLog.filter(e => e.eventType === 'signup_complete').length;
        const paidSubs = this.conversionLog.filter(e => e.eventType === 'subscription_start').length;
        const totalRevenue = this.campaigns.reduce((s, c) => s + c.revenue, 0);
        const totalSpend = this.campaigns.reduce((s, c) => s + c.spend, 0);

        return {
            generatedAt: new Date().toISOString(),
            periodDays,
            totalVisitors,
            uniqueVisitors: totalVisitors,
            signupStarts: this.conversionLog.filter(e => e.eventType === 'signup_start').length,
            signupCompletes,
            trialStarts: this.conversionLog.filter(e => e.eventType === 'trial_start').length,
            paidSubscriptions: paidSubs,
            totalRevenueCents: totalRevenue,
            totalAdSpendCents: totalSpend,
            overallRoas: totalSpend > 0 ? totalRevenue / totalSpend : 0,
            customerAcquisitionCost: paidSubs > 0 ? totalSpend / paidSubs : 0,
            variantTestsRunning: 0,
            variantTestsCompleted: 0,
            winningVariants: [],
            campaignAllocations: allocations,
            campaignDecisions: decisions,
        };
    }

    // ---- Decision engine ----

    private makeDecision(alloc: BudgetAllocation, campaign: CampaignArm): OptimizationDecision {
        const warnings: string[] = [];

        // Insufficient data check
        if (campaign.conversions < THRESHOLDS.MIN_CONVERSIONS_TO_ACT) {
            return {
                campaignId: campaign.campaignId,
                action: 'insufficient_data',
                reason: `Only ${campaign.conversions} conversions (need ${THRESHOLDS.MIN_CONVERSIONS_TO_ACT})`,
                recommendedBudget: alloc.currentBudget,
                currentBudget: alloc.currentBudget,
                shouldApply: false,
                warnings: ['Insufficient conversion data'],
            };
        }

        if (campaign.impressions < THRESHOLDS.MIN_IMPRESSIONS_TO_ACT) {
            return {
                campaignId: campaign.campaignId,
                action: 'insufficient_data',
                reason: `Only ${campaign.impressions} impressions (need ${THRESHOLDS.MIN_IMPRESSIONS_TO_ACT})`,
                recommendedBudget: alloc.currentBudget,
                currentBudget: alloc.currentBudget,
                shouldApply: false,
                warnings: ['Insufficient impression data'],
            };
        }

        const roas = campaign.spend > 0 ? campaign.revenue / campaign.spend : 0;
        const cac = campaign.conversions > 0 ? campaign.spend / campaign.conversions : Infinity;
        const budgetChangePct = alloc.currentBudget > 0
            ? (alloc.recommendedBudget - alloc.currentBudget) / alloc.currentBudget
            : 0;

        // PAUSE: poor performance
        if (roas < THRESHOLDS.MIN_ROAS_TO_MAINTAIN && alloc.confidence >= THRESHOLDS.MIN_CONFIDENCE_TO_PAUSE) {
            return {
                campaignId: campaign.campaignId,
                action: 'pause',
                reason: `ROAS ${roas.toFixed(2)}x below ${THRESHOLDS.MIN_ROAS_TO_MAINTAIN}x minimum`,
                recommendedBudget: 0,
                currentBudget: alloc.currentBudget,
                shouldApply: true,
                warnings,
            };
        }

        if (cac > THRESHOLDS.MAX_CAC_TO_MAINTAIN && alloc.confidence >= THRESHOLDS.MIN_CONFIDENCE_TO_PAUSE) {
            return {
                campaignId: campaign.campaignId,
                action: 'pause',
                reason: `CAC $${(cac / 100).toFixed(2)} exceeds $${(THRESHOLDS.MAX_CAC_TO_MAINTAIN / 100).toFixed(2)} max`,
                recommendedBudget: 0,
                currentBudget: alloc.currentBudget,
                shouldApply: true,
                warnings,
            };
        }

        // SCALE UP
        if (
            roas >= THRESHOLDS.MIN_ROAS_TO_SCALE &&
            cac <= THRESHOLDS.MAX_CAC_TO_SCALE &&
            alloc.confidence >= THRESHOLDS.MIN_CONFIDENCE_TO_SCALE &&
            budgetChangePct > 0.05
        ) {
            const maxIncrease = alloc.currentBudget * (1 + THRESHOLDS.MAX_BUDGET_INCREASE_PCT);
            const capped = Math.min(alloc.recommendedBudget, maxIncrease, THRESHOLDS.MAX_DAILY_BUDGET_CENTS);
            if (capped !== alloc.recommendedBudget) {
                warnings.push(`Budget capped from $${(alloc.recommendedBudget / 100).toFixed(2)} to $${(capped / 100).toFixed(2)}`);
            }
            return {
                campaignId: campaign.campaignId,
                action: 'scale_up',
                reason: `ROAS ${roas.toFixed(2)}x, CAC $${(cac / 100).toFixed(2)}, confidence ${(alloc.confidence * 100).toFixed(0)}%`,
                recommendedBudget: Math.round(capped),
                currentBudget: alloc.currentBudget,
                shouldApply: true,
                warnings,
            };
        }

        // SCALE DOWN
        if (budgetChangePct < -0.10) {
            const maxDecrease = alloc.currentBudget * (1 - THRESHOLDS.MAX_BUDGET_DECREASE_PCT);
            const capped = Math.max(alloc.recommendedBudget, maxDecrease, THRESHOLDS.MIN_DAILY_BUDGET_CENTS);
            return {
                campaignId: campaign.campaignId,
                action: 'scale_down',
                reason: `Thompson Sampling recommends ${Math.abs(budgetChangePct * 100).toFixed(0)}% decrease`,
                recommendedBudget: Math.round(capped),
                currentBudget: alloc.currentBudget,
                shouldApply: true,
                warnings,
            };
        }

        // MAINTAIN
        return {
            campaignId: campaign.campaignId,
            action: 'maintain',
            reason: 'Performance acceptable, no significant change',
            recommendedBudget: alloc.currentBudget,
            currentBudget: alloc.currentBudget,
            shouldApply: false,
            warnings,
        };
    }

    // ---- Attribution ----

    private resolveCampaignId(event: ConversionEvent): string | null {
        if (!event.adContext.utmCampaign) return null;

        // Exact match on campaign name
        const exact = this.campaigns.find(c =>
            c.campaignId === event.adContext.utmCampaign
        );
        if (exact) return exact.campaignId;

        // Match by platform from utm_source
        const platformMap: Record<string, AdPlatform> = {
            facebook: 'facebook', fb: 'facebook', instagram: 'facebook',
            google: 'google', gads: 'google',
            linkedin: 'linkedin', li: 'linkedin',
            tiktok: 'tiktok', tt: 'tiktok',
            github: 'github', gh: 'github',
        };
        const platform = platformMap[event.adContext.utmSource ?? ''];
        if (platform) {
            const platformMatch = this.campaigns.find(c => c.platform === platform);
            if (platformMatch) return platformMatch.campaignId;
        }

        return null;
    }

    // ---- State management ----

    exportState(): { campaigns: CampaignArm[]; conversionLog: ConversionEvent[] } {
        return {
            campaigns: this.campaigns.map(c => ({ ...c })),
            conversionLog: [...this.conversionLog],
        };
    }

    importState(state: { campaigns: CampaignArm[]; conversionLog: ConversionEvent[] }): void {
        this.campaigns = state.campaigns.map(c => ({ ...c }));
        this.conversionLog = [...state.conversionLog];
    }
}

// ============================================================================
// Seed campaigns (CodeTether's initial ad campaigns)
// ============================================================================

/**
 * Default seed campaigns for CodeTether self-selling.
 * These represent the initial ad campaigns that the AdBrain
 * will optimize. Start with uniform priors and let Thompson
 * Sampling discover what works.
 */
export function createSeedCampaigns(): CampaignArm[] {
    return [
        {
            campaignId: 'ct-fb-dev-security',
            platform: 'facebook',
            audience: 'Software developers interested in security',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-fb-devops-k8s',
            platform: 'facebook',
            audience: 'DevOps engineers, Kubernetes users',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-google-ai-agent',
            platform: 'google',
            audience: 'Search: "AI agent platform", "MCP server", "A2A protocol"',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-google-security',
            platform: 'google',
            audience: 'Search: "secure AI agents", "agent authentication"',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-linkedin-ciso',
            platform: 'linkedin',
            audience: 'CISOs, VP Engineering, Security leads at tech companies',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-linkedin-devrel',
            platform: 'linkedin',
            audience: 'Developer advocates, tech leads, platform engineers',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-github-sponsors',
            platform: 'github',
            audience: 'GitHub developers following AI/LLM/agent repos',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-youtube-demo',
            platform: 'google',
            audience: 'YouTube: Developer audiences, AI/automation viewers',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
        {
            campaignId: 'ct-youtube-retarget',
            platform: 'google',
            audience: 'YouTube: Retargeting site visitors with video ads',
            alpha: 1, beta: 1,
            impressions: 0, clicks: 0, conversions: 0, signups: 0,
            spend: 0, revenue: 0, ltvRevenue: 0, subscriptionCount: 0,
        },
    ];
}
