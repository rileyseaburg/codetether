/**
 * CodeTether Self-Selling Platform - Shared Types
 *
 * Type definitions for the Thompson Sampling optimization system
 * that enables CodeTether to autonomously optimize its own marketing.
 */

// ============================================================================
// Marketing Page Slots
// ============================================================================

/**
 * A customizable region on the marketing page.
 * Each slot can have multiple variants tested via Thompson Sampling.
 */
export type MarketingSlot =
    | 'hero_headline'
    | 'hero_subheadline'
    | 'hero_cta'
    | 'social_proof'
    | 'pricing_emphasis'
    | 'comparison_focus'
    | 'ciso_banner'
    | 'faq_order'
    | 'use_case_highlight'
    | 'call_to_action';

/**
 * A variant for a marketing page slot with Thompson Sampling parameters
 */
export interface SlotVariant {
    id: string;
    slot: MarketingSlot;
    name: string;
    content: Record<string, string>;
    /** Beta distribution success parameter (α) */
    alpha: number;
    /** Beta distribution failure parameter (β) */
    beta: number;
    impressions: number;
    conversions: number;
    signups: number;
    revenueCents: number;
    isControl: boolean;
    isActive: boolean;
}

/**
 * Selected variant for a slot
 */
export interface SlotSelection {
    slot: MarketingSlot;
    variantId: string;
    variantName: string;
    content: Record<string, string>;
    selectedVia: 'thompson' | 'context_rule' | 'exploration' | 'control';
    thompsonSample: number;
}

/**
 * Complete page assembly result
 */
export interface PageAssembly {
    sessionId: string;
    slots: Record<MarketingSlot, SlotSelection>;
    renderTimeMs: number;
    adContext: AdContext;
    timestamp: string;
}

// ============================================================================
// Ad Context & Attribution
// ============================================================================

/**
 * Visitor ad context extracted from UTM params and referrer
 */
export interface AdContext {
    utmSource?: string;
    utmMedium?: string;
    utmCampaign?: string;
    utmContent?: string;
    utmTerm?: string;
    referrer?: string;
    landingPage?: string;
    deviceType?: 'mobile' | 'tablet' | 'desktop';
    /** GitHub presence indicator (from referrer or utm) */
    isGitHubUser?: boolean;
}

// ============================================================================
// Campaign Arms (Ad Brain)
// ============================================================================

export type AdPlatform = 'facebook' | 'google' | 'tiktok' | 'linkedin' | 'github';

/**
 * A campaign arm in the multi-armed bandit for ad budget allocation
 */
export interface CampaignArm {
    campaignId: string;
    platform: AdPlatform;
    /** Beta distribution success parameter (α) */
    alpha: number;
    /** Beta distribution failure parameter (β) */
    beta: number;
    impressions: number;
    clicks: number;
    conversions: number;
    signups: number;
    /** Total spend in cents */
    spend: number;
    /** Total revenue in cents (from tenant subscriptions) */
    revenue: number;
    /** LTV-weighted revenue from Stripe */
    ltvRevenue: number;
    /** Number of paid subscriptions acquired */
    subscriptionCount: number;
    /** Target audience descriptor */
    audience: string;
    /** Creative variant ID */
    creativeId?: string;
}

/**
 * Recommended budget allocation for a campaign
 */
export interface BudgetAllocation {
    campaignId: string;
    platform: AdPlatform;
    currentBudget: number;
    recommendedBudget: number;
    allocationPercentage: number;
    sampledRoas: number;
    expectedRoas: number;
    confidence: number;
}

// ============================================================================
// Optimization Decisions
// ============================================================================

export type OptimizationAction =
    | 'scale_up'
    | 'scale_down'
    | 'pause'
    | 'maintain'
    | 'insufficient_data';

export interface OptimizationDecision {
    campaignId: string;
    action: OptimizationAction;
    reason: string;
    recommendedBudget: number;
    currentBudget: number;
    shouldApply: boolean;
    warnings: string[];
}

// ============================================================================
// Conversion Events
// ============================================================================

export type ConversionEventType =
    | 'page_view'
    | 'cta_click'
    | 'signup_start'
    | 'signup_complete'
    | 'trial_start'
    | 'subscription_start'
    | 'subscription_renewal';

export interface ConversionEvent {
    sessionId: string;
    eventType: ConversionEventType;
    timestamp: string;
    valueCents: number;
    metadata: Record<string, string>;
    adContext: AdContext;
    pageAssembly?: string; // JSON-serialized slot selections
}

// ============================================================================
// Self-Selling Report
// ============================================================================

export interface SelfSellingReport {
    generatedAt: string;
    periodDays: number;

    // Traffic
    totalVisitors: number;
    uniqueVisitors: number;

    // Conversion funnel
    signupStarts: number;
    signupCompletes: number;
    trialStarts: number;
    paidSubscriptions: number;

    // Revenue
    totalRevenueCents: number;
    totalAdSpendCents: number;
    overallRoas: number;
    customerAcquisitionCost: number;

    // Optimization performance
    variantTestsRunning: number;
    variantTestsCompleted: number;
    winningVariants: Array<{
        slot: MarketingSlot;
        variantName: string;
        conversionRate: number;
        confidence: number;
    }>;

    // Campaign performance
    campaignAllocations: BudgetAllocation[];
    campaignDecisions: OptimizationDecision[];
}

// ============================================================================
// Prior Parameters
// ============================================================================

export interface PriorParameters {
    /** Prior alpha for Beta distribution */
    alpha0: number;
    /** Prior beta for Beta distribution */
    beta0: number;
    /** Prior shape for Gamma distribution */
    k0: number;
    /** Prior scale for Gamma distribution */
    theta0: number;
}
