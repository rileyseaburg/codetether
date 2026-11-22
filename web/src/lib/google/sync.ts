/**
 * Google Ads ↔ Thompson Sampling Sync
 *
 * Pulls real performance data from Google Ads campaigns and syncs it
 * into the AdBrain's Thompson Sampling optimizer. Then applies
 * optimization decisions (budget changes, pauses) back to Google Ads.
 *
 * This is the closed-loop: Google data → Thompson Sampling → Google actions.
 *
 * @module lib/google/sync
 */

import { AdBrain, createSeedCampaigns } from '../optimization/adBrain';
import type { CampaignArm } from '../optimization/types';
import {
    getCampaignMetricsForOptimizer,
    getCampaignReport,
} from './reporting';
import {
    updateCampaignBudget,
    updateCampaignStatus,
    centsToMicros,
    microsToCents,
    dollarsToMicros,
    microsToDollars,
} from './client';

// ============================================================================
// Types
// ============================================================================

export interface SyncResult {
    syncedAt: string;
    campaignsSynced: number;
    optimizationRun: boolean;
    decisions: Array<{
        campaignId: string;
        action: string;
        reason: string;
        applied: boolean;
        error?: string;
    }>;
    totalSpendDollars: number;
    totalConversions: number;
    overallRoas: number;
}

// ============================================================================
// Campaign ID mapping
// ============================================================================

/**
 * Maps Google Ads campaign IDs to AdBrain campaign IDs.
 * In production, this would be stored in a database.
 * For now, we match by naming convention.
 */
const CAMPAIGN_NAME_MAP: Record<string, string> = {
    // Google Ads campaign name prefix → AdBrain campaign ID
    'CodeTether AI Agent': 'ct-google-ai-agent',
    'CodeTether Security': 'ct-google-security',
    'CT Search - AI': 'ct-google-ai-agent',
    'CT Search - Security': 'ct-google-security',
};

function resolveAdBrainId(googleCampaignName: string): string | null {
    for (const [prefix, brainId] of Object.entries(CAMPAIGN_NAME_MAP)) {
        if (googleCampaignName.startsWith(prefix)) return brainId;
    }
    // Fallback: use Google campaign name as-is (lowercase, hyphened)
    return `ct-google-${googleCampaignName.toLowerCase().replace(/\s+/g, '-').substring(0, 40)}`;
}

// ============================================================================
// Sync: Google Ads → Thompson Sampling
// ============================================================================

/**
 * Pull Google Ads metrics and update AdBrain campaign arms
 */
export async function syncGoogleAdsToAdBrain(
    adBrain: AdBrain,
    params: {
        startDate?: string;
        endDate?: string;
        customerId?: string;
    } = {}
): Promise<{ campaignsSynced: number }> {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);

    const startDate = params.startDate ?? start.toISOString().split('T')[0];
    const endDate = params.endDate ?? end.toISOString().split('T')[0];

    const metrics = await getCampaignMetricsForOptimizer({
        startDate,
        endDate,
        customerId: params.customerId,
    });

    let synced = 0;

    for (const m of metrics) {
        const brainId = resolveAdBrainId(m.campaignName);
        if (!brainId) continue;

        // Find existing campaign arm or create one
        const state = adBrain.exportState();
        let arm = state.campaigns.find(c => c.campaignId === brainId);

        if (!arm) {
            // Register new campaign from Google Ads
            const newArm: CampaignArm = {
                campaignId: brainId,
                platform: 'google',
                audience: `Google Ads: ${m.campaignName}`,
                alpha: 1,
                beta: 1,
                impressions: 0,
                clicks: 0,
                conversions: 0,
                signups: 0,
                spend: 0,
                revenue: 0,
                ltvRevenue: 0,
                subscriptionCount: 0,
            };
            adBrain.addCampaign(newArm);
            arm = newArm;
        }

        // Update with real Google Ads data
        arm.impressions = m.impressions;
        arm.clicks = m.clicks;
        arm.conversions = m.conversions;
        arm.spend = m.spendCents;
        arm.revenue = m.revenueCents;

        // Update Beta distribution posterior
        // alpha = conversions + 1 (prior), beta = clicks - conversions + 1
        arm.alpha = m.conversions + 1;
        arm.beta = Math.max(1, m.clicks - m.conversions + 1);

        synced++;
    }

    return { campaignsSynced: synced };
}

// ============================================================================
// Apply: Thompson Sampling → Google Ads
// ============================================================================

/**
 * Run optimization and apply decisions back to Google Ads.
 * Budget changes and pause/enable actions are sent to the API.
 */
export async function applyOptimizationToGoogleAds(
    adBrain: AdBrain,
    params: {
        dailyBudgetDollars: number;
        dryRun?: boolean;
        customerId?: string;
    }
): Promise<SyncResult> {
    const dailyBudgetCents = Math.round(params.dailyBudgetDollars * 100);
    const { allocations, decisions } = await adBrain.optimize(dailyBudgetCents);

    const results: SyncResult['decisions'] = [];
    const state = adBrain.exportState();
    let totalSpendCents = 0;
    let totalConversions = 0;
    let totalRevenueCents = 0;

    for (const arm of state.campaigns) {
        if (arm.platform !== 'google') continue;
        totalSpendCents += arm.spend;
        totalConversions += arm.conversions;
        totalRevenueCents += arm.revenue;
    }

    for (const decision of decisions) {
        // Only apply Google campaigns
        const arm = state.campaigns.find(c => c.campaignId === decision.campaignId);
        if (!arm || arm.platform !== 'google') continue;

        if (params.dryRun || !decision.shouldApply) {
            results.push({
                campaignId: decision.campaignId,
                action: decision.action,
                reason: decision.reason,
                applied: false,
            });
            continue;
        }

        try {
            // Extract Google campaign ID from the campaign name map (reverse lookup)
            // In production this would come from a database
            const googleCampaignId = extractGoogleCampaignId(decision.campaignId);

            if (!googleCampaignId) {
                results.push({
                    campaignId: decision.campaignId,
                    action: decision.action,
                    reason: decision.reason,
                    applied: false,
                    error: 'No Google campaign ID mapping found',
                });
                continue;
            }

            switch (decision.action) {
                case 'pause':
                    await updateCampaignStatus(googleCampaignId, 'PAUSED', params.customerId);
                    break;
                case 'scale_up':
                case 'scale_down':
                    await updateCampaignBudget(
                        googleCampaignId,
                        centsToMicros(decision.recommendedBudget),
                        params.customerId
                    );
                    break;
                case 'maintain':
                    // No action needed
                    break;
            }

            results.push({
                campaignId: decision.campaignId,
                action: decision.action,
                reason: decision.reason,
                applied: true,
            });
        } catch (error) {
            results.push({
                campaignId: decision.campaignId,
                action: decision.action,
                reason: decision.reason,
                applied: false,
                error: error instanceof Error ? error.message : String(error),
            });
        }
    }

    return {
        syncedAt: new Date().toISOString(),
        campaignsSynced: state.campaigns.filter(c => c.platform === 'google').length,
        optimizationRun: true,
        decisions: results,
        totalSpendDollars: totalSpendCents / 100,
        totalConversions,
        overallRoas: totalSpendCents > 0 ? totalRevenueCents / totalSpendCents : 0,
    };
}

// ============================================================================
// Full sync cycle
// ============================================================================

/**
 * Complete sync cycle:
 * 1. Pull Google Ads metrics → update AdBrain
 * 2. Run Thompson Sampling optimization
 * 3. Apply decisions back to Google Ads
 */
export async function runFullSyncCycle(params: {
    dailyBudgetDollars: number;
    dryRun?: boolean;
    customerId?: string;
}): Promise<SyncResult> {
    const adBrain = new AdBrain({
        explorationBudgetPct: 0.10,
        campaigns: createSeedCampaigns().filter(c => c.platform === 'google'),
    });

    // Step 1: Pull real data from Google Ads
    await syncGoogleAdsToAdBrain(adBrain, {
        customerId: params.customerId,
    });

    // Step 2+3: Optimize and apply
    return applyOptimizationToGoogleAds(adBrain, params);
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * In production, this would look up the mapping in a database.
 * For now, we store the Google campaign ID in env vars.
 */
function extractGoogleCampaignId(brainCampaignId: string): string | null {
    // Check env vars for explicit mapping
    const envKey = `GOOGLE_CAMPAIGN_${brainCampaignId.toUpperCase().replace(/-/g, '_')}`;
    const fromEnv = process.env[envKey];
    if (fromEnv) return fromEnv;

    return null;
}
