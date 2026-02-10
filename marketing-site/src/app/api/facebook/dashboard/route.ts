/**
 * Facebook Ads Dashboard API
 *
 * Internal route for the dashboard UI — no API key required,
 * uses session auth inherited from the dashboard layout.
 *
 * GET  /api/facebook/dashboard            → account + campaigns + videos summary
 * POST /api/facebook/dashboard            → actions: launch, report, pause, activate, delete
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    getAdAccount,
    listCampaigns,
    updateCampaignStatus,
    getCampaignInsights,
} from '@/lib/facebook';
import {
    launchFacebookVideoAd,
    getFacebookVideoReport,
    type LaunchFacebookVideoAdParams,
} from '@/lib/facebook';

function err(message: string, status = 400) {
    return NextResponse.json({ error: message }, { status });
}

/** GET — fetch everything the dashboard needs in one call */
export async function GET() {
    try {
        const [account, campaigns] = await Promise.all([
            getAdAccount().catch(() => null),
            listCampaigns().catch(() => []),
        ]);

        // Get insights for up to 10 campaigns in parallel
        const campaignsWithInsights = await Promise.all(
            campaigns.slice(0, 20).map(async (c) => {
                try {
                    const insights = await getCampaignInsights(c.id, {
                        datePreset: 'last_30d',
                        fields: [
                            'impressions',
                            'clicks',
                            'spend',
                            'cpc',
                            'cpm',
                            'ctr',
                            'actions',
                            'video_thruplay_watched_actions',
                            'cost_per_thruplay',
                        ],
                    });
                    return { ...c, insights: (insights as Record<string, unknown>[])[0] ?? null };
                } catch {
                    return { ...c, insights: null };
                }
            }),
        );

        // Compute totals
        const totals = campaignsWithInsights.reduce(
            (acc, c) => {
                const ins = c.insights as Record<string, unknown> | null;
                if (!ins) return acc;
                acc.impressions += Number(ins.impressions ?? 0);
                acc.clicks += Number(ins.clicks ?? 0);
                acc.spend += parseFloat(String(ins.spend ?? '0'));
                return acc;
            },
            { impressions: 0, clicks: 0, spend: 0 },
        );

        return NextResponse.json({
            account,
            campaigns: campaignsWithInsights,
            totals: {
                ...totals,
                ctr: totals.impressions > 0 ? ((totals.clicks / totals.impressions) * 100).toFixed(2) : '0',
                campaignCount: campaigns.length,
                activeCampaigns: campaigns.filter((c) => c.status === 'ACTIVE').length,
            },
        });
    } catch (error) {
        console.error('[Facebook Dashboard API] GET error:', error);
        return err(error instanceof Error ? error.message : 'Failed to load dashboard data', 500);
    }
}

/** POST — perform actions */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { action, ...params } = body;

        switch (action) {
            case 'launch': {
                if (!params.videoUrl) return err('videoUrl required');
                const result = await launchFacebookVideoAd(params as LaunchFacebookVideoAdParams);
                return NextResponse.json({ success: true, ...result }, { status: 201 });
            }

            case 'pause': {
                if (!params.campaignId) return err('campaignId required');
                await updateCampaignStatus(params.campaignId, 'PAUSED');
                return NextResponse.json({ success: true, status: 'PAUSED' });
            }

            case 'activate': {
                if (!params.campaignId) return err('campaignId required');
                await updateCampaignStatus(params.campaignId, 'ACTIVE');
                return NextResponse.json({ success: true, status: 'ACTIVE' });
            }

            case 'delete': {
                if (!params.campaignId) return err('campaignId required');
                await updateCampaignStatus(params.campaignId, 'DELETED');
                return NextResponse.json({ success: true, status: 'DELETED' });
            }

            case 'report': {
                const report = await getFacebookVideoReport({
                    days: params.days ?? 30,
                    campaignId: params.campaignId,
                });
                return NextResponse.json({ report });
            }

            default:
                return err(`Unknown action: ${action}`);
        }
    } catch (error) {
        console.error('[Facebook Dashboard API] POST error:', error);
        return err(error instanceof Error ? error.message : 'Internal error', 500);
    }
}
