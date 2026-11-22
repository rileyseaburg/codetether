/**
 * CodeTether Self-Selling API - Optimization Report
 *
 * GET /api/optimization/report
 *   Returns current performance stats for all variants and campaigns.
 *   Used by the dashboard to visualize Thompson Sampling progress.
 *
 * This is the "self-selling dashboard" - shows how CodeTether is
 * optimizing its own marketing in real-time.
 */

import { NextRequest, NextResponse } from 'next/server';
import { MarketingFunnelBrain, AdBrain, createSeedCampaigns } from '@/lib/optimization';

// Re-use the same singletons (in production, backed by database)
let funnelBrain: MarketingFunnelBrain | null = null;
let adBrain: AdBrain | null = null;

function getFunnelBrain(): MarketingFunnelBrain {
    if (!funnelBrain) {
        funnelBrain = new MarketingFunnelBrain();
        if (typeof globalThis !== 'undefined' && (globalThis as any).__funnelBrainState) {
            funnelBrain.importState((globalThis as any).__funnelBrainState);
        }
    }
    return funnelBrain;
}

function getAdBrain(): AdBrain {
    if (!adBrain) {
        adBrain = new AdBrain({ campaigns: createSeedCampaigns() });
        if (typeof globalThis !== 'undefined' && (globalThis as any).__adBrainState) {
            adBrain.importState((globalThis as any).__adBrainState);
        }
    }
    return adBrain;
}

/**
 * GET /api/optimization/report
 *
 * Returns the self-selling performance report.
 */
export async function GET(_request: NextRequest) {
    const brain = getFunnelBrain();
    const ad = getAdBrain();

    const variantPerformance = brain.getPerformanceReport();
    const adReport = await ad.generateReport(30);
    const bids = ad.calculateBids();

    return NextResponse.json({
        generatedAt: new Date().toISOString(),
        funnelBrain: {
            totalVariants: variantPerformance.length,
            activeTests: variantPerformance.filter(v => v.impressions > 0).length,
            winningVariants: variantPerformance.filter(v => v.isWinning),
            allVariants: variantPerformance,
        },
        adBrain: {
            ...adReport,
            optimizedBids: bids,
        },
    });
}
