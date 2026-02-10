/**
 * Video Ad Pipeline API
 *
 * Bridges Creatify video generation → YouTube → Google Ads.
 *
 * POST /api/google/video-pipeline
 *   action: "launch" - Take a YouTube video ID → create full campaign
 *   action: "report" - Get video campaign performance
 *   action: "list"   - List all video ads across campaigns
 *
 * The expected flow:
 * 1. Generate video with Creatify (a2a_server/creatify_video.py)
 * 2. Upload result to YouTube (manual or via YouTube Data API)
 * 3. POST here with { action: "launch", youtubeVideoId: "..." }
 *    → Creates VIDEO campaign + ad group + in-stream/bumper ad
 * 4. Review in Google Ads UI, enable campaign
 * 5. Monitor with { action: "report" }
 */

import { NextRequest, NextResponse } from 'next/server';
import {
    launchVideoAdFromYouTube,
    listVideoAds,
    getVideoReport,
} from '@/lib/google/videoAds';

function errorResponse(message: string, status = 400) {
    return NextResponse.json({ error: message }, { status });
}

export async function POST(request: NextRequest) {
    // Check API key for write operations
    const key = request.headers.get('x-api-key');
    const expected = process.env.GOOGLE_ADS_INTERNAL_API_KEY;
    if (expected && key !== expected) {
        return errorResponse('Unauthorized', 401);
    }

    try {
        const body = await request.json();
        const { action, ...params } = body;

        switch (action) {
            case 'launch': {
                if (!params.youtubeVideoId)
                    return errorResponse('youtubeVideoId required');

                const result = await launchVideoAdFromYouTube({
                    youtubeVideoId: params.youtubeVideoId,
                    campaignName:
                        params.campaignName ??
                        `CodeTether Video Ad ${new Date().toISOString().split('T')[0]}`,
                    dailyBudgetDollars: params.dailyBudgetDollars ?? 25,
                    finalUrl: params.finalUrl ?? 'https://codetether.run',
                    displayUrl: params.displayUrl ?? 'codetether.run',
                    headline: params.headline ?? 'AI Agents That Actually Deliver',
                    callToAction: params.callToAction ?? 'Start Free',
                    adType: params.adType ?? 'IN_STREAM',
                    customerId: params.customerId,
                });

                return NextResponse.json(
                    {
                        pipeline: 'video_ad_launched',
                        ...result,
                        nextSteps: [
                            'Review campaign in Google Ads UI',
                            'Enable campaign when ready to spend',
                            'Monitor with action: "report"',
                        ],
                    },
                    { status: 201 }
                );
            }

            case 'list': {
                const ads = await listVideoAds({
                    adGroupId: params.adGroupId,
                    campaignId: params.campaignId,
                    customerId: params.customerId,
                });
                return NextResponse.json({ videoAds: ads });
            }

            case 'report': {
                const end = new Date();
                const start = new Date();
                start.setDate(start.getDate() - (params.days ?? 30));

                const report = await getVideoReport({
                    startDate:
                        params.startDate ?? start.toISOString().split('T')[0],
                    endDate:
                        params.endDate ?? end.toISOString().split('T')[0],
                    customerId: params.customerId,
                });

                return NextResponse.json({ report });
            }

            default:
                return errorResponse(
                    `Unknown action: ${action}. Valid: launch, list, report`
                );
        }
    } catch (error) {
        console.error('[Video Pipeline] Error:', error);
        return errorResponse(
            error instanceof Error ? error.message : 'Internal error',
            500
        );
    }
}
