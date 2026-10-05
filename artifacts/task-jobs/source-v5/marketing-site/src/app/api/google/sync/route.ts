/**
 * Google Ads ↔ Thompson Sampling Sync API
 *
 * POST /api/google/sync  - Run full optimization cycle
 * GET  /api/google/sync  - Dry-run: see what would happen
 *
 * This is the closed-loop endpoint that:
 * 1. Pulls real Google Ads campaign data
 * 2. Updates Thompson Sampling posteriors
 * 3. Makes budget/pause/scale decisions
 * 4. Applies decisions back to Google Ads (POST only)
 */

import { NextRequest, NextResponse } from 'next/server';
import { runFullSyncCycle } from '@/lib/google/sync';

/**
 * GET: Dry run - show what optimization would do without applying changes
 */
export async function GET(request: NextRequest) {
    const { searchParams } = new URL(request.url);
    const dailyBudget = Number(searchParams.get('dailyBudgetDollars') ?? '50');

    try {
        const result = await runFullSyncCycle({
            dailyBudgetDollars: dailyBudget,
            dryRun: true,
        });

        return NextResponse.json({
            mode: 'dry_run',
            ...result,
        });
    } catch (error) {
        console.error('[Google Ads Sync] Dry run error:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal error' },
            { status: 500 }
        );
    }
}

/**
 * POST: Full sync cycle - apply optimization decisions to Google Ads
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const dailyBudget = body.dailyBudgetDollars ?? 50;
        const dryRun = body.dryRun ?? false;

        // Verify internal API key for write operations
        if (!dryRun) {
            const key = request.headers.get('x-api-key');
            const expected = process.env.GOOGLE_ADS_INTERNAL_API_KEY;
            if (expected && key !== expected) {
                return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
            }
        }

        const result = await runFullSyncCycle({
            dailyBudgetDollars: dailyBudget,
            dryRun,
            customerId: body.customerId,
        });

        return NextResponse.json({
            mode: dryRun ? 'dry_run' : 'applied',
            ...result,
        });
    } catch (error) {
        console.error('[Google Ads Sync] Error:', error);
        return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Internal error' },
            { status: 500 }
        );
    }
}
