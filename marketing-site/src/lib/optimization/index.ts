/**
 * CodeTether Self-Selling Platform
 *
 * Barrel export for the Thompson Sampling optimization system.
 * This system enables CodeTether to autonomously optimize its own
 * marketing using the same Bayesian multi-armed bandit algorithms
 * that power Spotless Bin Co's ad platform.
 *
 * Architecture (Two-Brain model):
 * - AdBrain: Optimizes WHERE to spend (campaign budget allocation)
 * - FunnelBrain: Optimizes WHAT to show (page variant selection)
 * - Thompson Sampling: Core algorithm shared by both brains
 *
 * @module lib/optimization
 */

export { ThompsonSamplingOptimizer } from './thompsonSampling';
export { MarketingFunnelBrain, extractAdContext } from './funnelBrain';
export { AdBrain, createSeedCampaigns } from './adBrain';
export type {
    MarketingSlot,
    SlotVariant,
    SlotSelection,
    PageAssembly,
    AdContext,
    AdPlatform,
    CampaignArm,
    BudgetAllocation,
    OptimizationAction,
    OptimizationDecision,
    ConversionEvent,
    ConversionEventType,
    SelfSellingReport,
    PriorParameters,
} from './types';
