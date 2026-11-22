/**
 * Thompson Sampling Optimizer for CodeTether Self-Selling
 *
 * Implements Bayesian multi-armed bandit for:
 * 1. Ad budget allocation across campaigns (Ad Brain)
 * 2. Marketing page variant selection (Funnel Brain)
 * 3. Optimal bid calculation for CPC campaigns
 *
 * Uses Beta-Gamma compound distribution to sample LTV-weighted ROAS,
 * ensuring the optimizer maximizes actual customer lifetime value
 * rather than raw conversion counts.
 *
 * Ported from Spotless Bin Co's production Thompson Sampling system.
 *
 * @module lib/optimization/thompsonSampling
 */

import type { PriorParameters, BudgetAllocation, CampaignArm, AdPlatform } from './types';

/**
 * Thompson Sampling Optimizer
 *
 * Samples ROAS by combining:
 * 1. Conversion rate ~ Beta(α, β)
 * 2. Value per conversion ~ Gamma(k, θ)
 * 3. ROAS = (conversion_rate × value_per_conversion) / cost_per_impression
 */
export class ThompsonSamplingOptimizer {
    private readonly explorationBudgetPct: number;
    private readonly confidenceThreshold: number;
    private readonly priors: PriorParameters;
    private readonly mcSamples: number;

    constructor(options: {
        explorationBudgetPct?: number;
        confidenceThreshold?: number;
        priors?: Partial<PriorParameters>;
        mcSamples?: number;
    } = {}) {
        this.explorationBudgetPct = options.explorationBudgetPct ?? 0.10;
        this.confidenceThreshold = options.confidenceThreshold ?? 100;
        this.priors = {
            alpha0: options.priors?.alpha0 ?? 1,
            beta0: options.priors?.beta0 ?? 1,
            k0: options.priors?.k0 ?? 1,
            theta0: options.priors?.theta0 ?? 100,
        };
        this.mcSamples = options.mcSamples ?? 5000;
    }

    /**
     * Sample ROAS for each campaign arm
     */
    async sampleArms(arms: CampaignArm[]): Promise<number[]> {
        return arms.map(arm => this.sampleRoas(arm));
    }

    /**
     * Combine Beta and Gamma to sample ROAS for a single arm
     */
    private sampleRoas(arm: CampaignArm): number {
        const alpha = this.priors.alpha0 + arm.conversions;
        const beta = this.priors.beta0 + Math.max(arm.impressions - arm.conversions, 0);
        const conversionRate = this.sampleBeta(alpha, beta);

        const conversions = Math.max(arm.conversions, 1);
        const meanValuePerConv = arm.revenue / conversions;
        const k = this.priors.k0 + conversions;
        const theta = (this.priors.theta0 * this.priors.k0 + meanValuePerConv * conversions) / k;
        const valuePerConversion = this.sampleGamma(k, theta);

        const impressions = Math.max(arm.impressions, 1);
        const costPerImpression = arm.spend / impressions;

        return costPerImpression > 0
            ? (conversionRate * valuePerConversion) / costPerImpression
            : 0;
    }

    /**
     * Recommend budget allocation using Thompson Sampling
     */
    async recommendAllocation(
        totalBudget: number,
        arms: CampaignArm[]
    ): Promise<BudgetAllocation[]> {
        if (arms.length === 0) return [];

        const sampledRoas = await this.sampleArms(arms);
        const totalSampledRoas = sampledRoas.reduce((sum, roas) => sum + Math.max(roas, 0), 0);

        // Exploitation allocations (proportional to sampled ROAS)
        const baseAllocations = sampledRoas.map(roas =>
            totalSampledRoas > 0 ? Math.max(roas, 0) / totalSampledRoas : 1 / arms.length
        );

        // Exploration allocations (proportional to uncertainty)
        const uncertainties = arms.map(arm => {
            const alpha = this.priors.alpha0 + arm.conversions;
            const beta = this.priors.beta0 + Math.max(arm.impressions - arm.conversions, 0);
            return this.getPosteriorVariance(alpha, beta);
        });
        const totalUncertainty = uncertainties.reduce((sum, u) => sum + u, 0);
        const explorationAllocations = uncertainties.map(u =>
            totalUncertainty > 0 ? u / totalUncertainty : 1 / arms.length
        );

        // Blend exploitation + exploration
        const explorationBudget = this.explorationBudgetPct * totalBudget;
        const exploitationBudget = totalBudget - explorationBudget;

        const allocations: BudgetAllocation[] = arms.map((arm, idx) => {
            const exploitationAmount = baseAllocations[idx] * exploitationBudget;
            const explorationAmount = explorationAllocations[idx] * explorationBudget;
            const recommendedBudget = Math.round(exploitationAmount + explorationAmount);

            const alpha = this.priors.alpha0 + arm.conversions;
            const beta = this.priors.beta0 + Math.max(arm.impressions - arm.conversions, 0);
            const expectedConvRate = this.getPosteriorMean(alpha, beta);
            const conversions = Math.max(arm.conversions, 1);
            const expectedValuePerConv = arm.revenue / conversions;
            const impressions = Math.max(arm.impressions, 1);
            const costPerImpression = arm.spend / impressions;

            const expectedRoas = costPerImpression > 0
                ? (expectedConvRate * expectedValuePerConv) / costPerImpression
                : 0;

            const totalTrials = alpha + beta - 2;
            const confidence = Math.min(totalTrials / this.confidenceThreshold, 1.0);

            return {
                campaignId: arm.campaignId,
                platform: arm.platform,
                currentBudget: Math.round(arm.spend),
                recommendedBudget,
                allocationPercentage: 0,
                sampledRoas: Math.round(sampledRoas[idx] * 100) / 100,
                expectedRoas: Math.round(expectedRoas * 100) / 100,
                confidence: Math.round(confidence * 100) / 100,
            };
        });

        // Normalize to exactly totalBudget
        let totalAllocated = allocations.reduce((sum, a) => sum + a.recommendedBudget, 0);
        if (totalAllocated !== totalBudget && totalAllocated > 0) {
            const factor = totalBudget / totalAllocated;
            allocations.forEach(a => { a.recommendedBudget = Math.round(a.recommendedBudget * factor); });
            totalAllocated = allocations.reduce((sum, a) => sum + a.recommendedBudget, 0);
            if (totalAllocated !== totalBudget) {
                const diff = totalBudget - totalAllocated;
                const maxAlloc = allocations.reduce((max, a) => a.recommendedBudget > max.recommendedBudget ? a : max);
                maxAlloc.recommendedBudget += diff;
            }
        }

        allocations.forEach(a => {
            a.allocationPercentage = Math.round((a.recommendedBudget / totalBudget) * 10000) / 100;
        });

        return allocations;
    }

    /**
     * Calculate expected loss (regret) for each arm via Monte Carlo
     */
    async calculateExpectedLoss(arms: CampaignArm[]): Promise<Map<string, number>> {
        const losses = new Map<string, number>();
        arms.forEach(arm => losses.set(arm.campaignId, 0));

        for (let i = 0; i < this.mcSamples; i++) {
            const samples = await this.sampleArms(arms);
            const maxSample = Math.max(...samples);
            samples.forEach((sample, idx) => {
                const arm = arms[idx];
                losses.set(arm.campaignId, (losses.get(arm.campaignId) || 0) + (maxSample - sample));
            });
        }

        losses.forEach((total, id) => losses.set(id, total / this.mcSamples));
        return losses;
    }

    /**
     * Calculate optimal CPC bid using Thompson Sampling posteriors
     *
     * Formula: bid = (P(conversion) × E[LTV|conversion]) / target_ROAS
     */
    calculateOptimalBid(
        arms: CampaignArm[],
        platform: AdPlatform,
        options: {
            targetRoas?: number;
            minBidCents?: number;
            maxBidCents?: number;
            defaultBidCents?: number;
        } = {}
    ): { bidCents: number; confidence: number; method: 'thompson' | 'platform_avg' | 'default' } {
        const {
            targetRoas = 3.0,
            minBidCents = 10,
            maxBidCents = 500,
            defaultBidCents = 75,
        } = options;

        const platformArms = arms.filter(arm => arm.platform === platform);
        if (platformArms.length === 0) {
            return { bidCents: defaultBidCents, confidence: 0, method: 'default' };
        }

        const totalClicks = platformArms.reduce((sum, arm) => sum + Math.max(arm.clicks, 1), 0);
        const totalConversions = platformArms.reduce((sum, arm) => sum + arm.conversions, 0);
        const totalRevenue = platformArms.reduce((sum, arm) => sum + arm.revenue, 0);
        const totalSpend = platformArms.reduce((sum, arm) => sum + arm.spend, 0);

        if (totalClicks < 10 || totalSpend < 100) {
            if (totalSpend > 0 && totalClicks > 0) {
                const avgCpc = Math.round(totalSpend / totalClicks);
                return { bidCents: Math.max(minBidCents, Math.min(maxBidCents, avgCpc)), confidence: 0.3, method: 'platform_avg' };
            }
            return { bidCents: defaultBidCents, confidence: 0, method: 'default' };
        }

        const alpha = this.priors.alpha0 + totalConversions;
        const beta = this.priors.beta0 + Math.max(totalClicks - totalConversions, 0);
        const expectedConvRate = this.getPosteriorMean(alpha, beta);
        const expectedLtvPerConv = totalRevenue / Math.max(totalConversions, 1);

        const optimalBid = Math.round((expectedConvRate * expectedLtvPerConv) / targetRoas);
        const clamped = Math.max(minBidCents, Math.min(maxBidCents, optimalBid));
        const confidence = Math.min((alpha + beta - 2) / this.confidenceThreshold, 1.0);

        return { bidCents: clamped, confidence, method: 'thompson' };
    }

    // ---- Distribution sampling ----

    sampleBeta(alpha: number, beta: number): number {
        const x = this.sampleGamma(alpha, 1);
        const y = this.sampleGamma(beta, 1);
        return x / (x + y);
    }

    private sampleGamma(shape: number, scale: number): number {
        if (shape < 1) {
            return this.sampleGamma(shape + 1, scale) * Math.pow(Math.random(), 1 / shape);
        }
        const d = shape - 1 / 3;
        const c = 1 / Math.sqrt(9 * d);
        while (true) {
            let x: number, v: number;
            do {
                x = this.sampleNormal(0, 1);
                v = 1 + c * x;
            } while (v <= 0);
            v = v * v * v;
            const u = Math.random();
            const x2 = x * x;
            if (u < 1 - 0.0331 * x2 * x2) return d * v * scale;
            if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) return d * v * scale;
        }
    }

    private sampleNormal(mean: number, stdDev: number): number {
        const u1 = 1 - Math.random();
        const u2 = 1 - Math.random();
        const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
        return mean + stdDev * z;
    }

    // ---- Posterior statistics ----

    getPosteriorMean(alpha: number, beta: number): number {
        return alpha / (alpha + beta);
    }

    getPosteriorVariance(alpha: number, beta: number): number {
        const total = alpha + beta;
        return (alpha * beta) / (total * total * (total + 1));
    }

    getCredibleInterval(alpha: number, beta: number): [number, number] {
        const mean = this.getPosteriorMean(alpha, beta);
        const stdDev = Math.sqrt(this.getPosteriorVariance(alpha, beta));
        return [
            Math.max(0, Math.round((mean - 1.96 * stdDev) * 10000) / 10000),
            Math.min(1, Math.round((mean + 1.96 * stdDev) * 10000) / 10000),
        ];
    }
}
